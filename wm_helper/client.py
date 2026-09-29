from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from .config import Config


class WMError(RuntimeError):
    """Warframe Market API 调用失败。"""


class RateLimiter:
    """简单令牌桶：限制每秒请求数。"""

    def __init__(self, rate: float) -> None:
        self._interval = 1.0 / rate if rate > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self._interval
        if wait:
            await asyncio.sleep(wait)


class WMClient:
    """Warframe Market v2 API 客户端：限速 + 内存缓存 + 文件缓存 + 代理。"""

    def __init__(self, config: Config | None = None) -> None:
        self.cfg = config or Config.from_env()
        self._limiter = RateLimiter(self.cfg.rate_per_second)
        self._memory: dict[str, tuple[float, Any]] = {}
        self._cache_dir = Path(self.cfg.cache_dir)
        headers = {
            "User-Agent": self.cfg.user_agent,
            "Platform": self.cfg.platform,
            "Language": self.cfg.language,
            "Accept": "application/json",
        }
        if self.cfg.token:
            headers["X-WM-Token"] = self.cfg.token
        self._client = httpx.AsyncClient(
            base_url=self.cfg.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.cfg.timeout),
            proxy=self.cfg.proxy,
            follow_redirects=True,
        )

    # ---------- 底层 ----------

    def _memory_get(self, key: str) -> Any | None:
        hit = self._memory.get(key)
        if not hit:
            return None
        expires, value = hit
        if expires < time.time():
            self._memory.pop(key, None)
            return None
        return value

    def _file_get(self, key: str, ttl: int) -> Any | None:
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _file_put(self, key: str, value: Any) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._limiter.acquire()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if resp.status_code >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if resp.status_code >= 400:
                    raise WMError(f"WM API {resp.status_code}: {resp.text[:200]}")
                payload = resp.json()
                if payload.get("error"):
                    raise WMError(f"WM API error: {payload['error']}")
                return payload.get("data")
            except (httpx.HTTPError, WMError) as exc:
                last_err = exc
                if attempt == 2:
                    break
                await asyncio.sleep(2 ** attempt)
        raise WMError(
            f"请求 {path} 失败: {last_err or '未知错误（可能超时、被限速或被网关拦截）'}"
        )

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: int | None = None,
        file_cache: str | None = None,
    ) -> Any:
        """带缓存的 GET。ttl>0 走内存缓存；file_cache 指定文件名走磁盘缓存。"""
        key = f"{path}?{sorted((params or {}).items())}"
        if ttl:
            cached = self._memory_get(key)
            if cached is not None:
                return cached
        if file_cache:
            cached = self._file_get(file_cache, ttl or self.cfg.items_ttl)
            if cached is not None:
                return cached
        data = await self._request(path, params)
        if ttl:
            self._memory[key] = (time.time() + ttl, data)
        if file_cache:
            self._file_put(file_cache, data)
        return data

    # ---------- 业务接口 ----------

    async def items(self, refresh: bool = False) -> list[dict[str, Any]]:
        """全量物品表（含 i18n 中文名、ducats 等）。默认走 12h 磁盘缓存。"""
        key = f"items_{self.cfg.language}"
        if refresh:
            data = await self._request("/items")
            self._file_put(key, data)
            return data
        return await self.get("/items", ttl=self.cfg.items_ttl, file_cache=key)

    async def orders_top(self, slug: str, **filters: Any) -> dict[str, list[dict[str, Any]]]:
        """在线用户的最优 5 卖 / 5 买单。filters: rank/charges/subtype/..."""
        params = {k: v for k, v in filters.items() if v is not None}
        return await self.get(
            f"/orders/item/{slug}/top", params, ttl=self.cfg.orders_ttl
        )

    async def orders_item(self, slug: str) -> list[dict[str, Any]]:
        """某物品的完整可见订单列表。"""
        return await self.get(f"/orders/item/{slug}", ttl=self.cfg.full_orders_ttl)

    async def item_set(self, slug: str) -> list[dict[str, Any]]:
        """套装成员物品。"""
        return await self.get(f"/item/{slug}/set", ttl=24 * 3600)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "WMClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
