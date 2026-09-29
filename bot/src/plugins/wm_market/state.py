"""全局单例：WM 客户端、物品索引、冷却与待选状态。"""

from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv
from nonebot import get_driver, logger

from wm_helper.client import WMClient
from wm_helper.config import Config
from wm_helper.items import Item, ItemIndex
from wm_helper.search import ItemSearcher

_cfg: Config | None = None
_client: WMClient | None = None
_searcher: ItemSearcher | None = None
_items_count = 0

# 群/用户级冷却（秒）
COOLDOWN = 3.0
_last_call: dict[str, float] = {}

# 待选状态：session_id -> (候选, 过期时间)
_pending: dict[str, tuple[list[Item], float]] = {}


def config() -> Config:
    global _cfg
    if _cfg is None:
        # NoneBot 只把 .env 读进自己的 settings，不会写进 os.environ，这里手动加载一次
        load_dotenv(os.getenv("WM_ENV_FILE", ".env"), override=False)
        _cfg = Config.from_env()
    return _cfg


def client() -> WMClient:
    global _client
    if _client is None:
        _client = WMClient(config())
    return _client


def searcher() -> ItemSearcher:
    global _searcher
    if _searcher is None:
        raise RuntimeError("物品索引尚未加载")
    return _searcher


def items_count() -> int:
    return _items_count


async def load_items(refresh: bool = False) -> int:
    """启动时与每日定时调用；失败不阻塞机器人启动。"""
    global _searcher, _items_count
    try:
        raw = await client().items(refresh=refresh)
        index = ItemIndex.from_api(raw)
        _searcher = ItemSearcher(index)
        _items_count = len(index)
        logger.info(f"WM 物品表已加载：{_items_count} 条")
        return _items_count
    except Exception as exc:  # noqa: BLE001
        logger.error(f"WM 物品表加载失败：{exc}")
        return 0


def cooldown_key(group_id: str | None, user_id: str) -> str:
    return f"{group_id or 'private'}:{user_id}"


def check_cooldown(key: str) -> float:
    """返回剩余冷却秒数；0 表示可用。"""
    last = _last_call.get(key, 0.0)
    left = COOLDOWN - (time.time() - last)
    return max(0.0, left)


def mark_called(key: str) -> None:
    _last_call[key] = time.time()


def set_pending(session_id: str, items: list[Item], ttl: float = 30.0) -> None:
    _pending[session_id] = (items, time.time() + ttl)


def pop_pending(session_id: str) -> list[Item] | None:
    hit = _pending.get(session_id)
    if not hit:
        return None
    items, expire = hit
    if time.time() > expire:
        _pending.pop(session_id, None)
        return None
    return items


@get_driver().on_startup
async def _on_startup() -> None:
    await load_items()


@get_driver().on_shutdown
async def _on_shutdown() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def scheduler_kwargs() -> dict[str, Any]:
    return {"trigger": "cron", "hour": 4, "minute": 0}
