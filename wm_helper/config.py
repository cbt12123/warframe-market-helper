from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """运行时配置。默认值针对国际服 PC + 中文检索。"""

    platform: str = "pc"           # pc / ps4 / xbox / switch / mobile
    language: str = "zh-hans"      # 检索与展示语言
    crossplay: bool = False
    proxy: str | None = None       # 例如 http://127.0.0.1:7890 / socks5://127.0.0.1:1080
    # 无海外出口时可指向云函数中转（见 deploy/cloudfunc/），默认直连官方
    base_url: str = "https://api.warframe.market/v2"
    token: str | None = None       # 中转函数的 X-WM-Token
    user_agent: str = "wm-helper/0.1.0 (+https://github.com/yourname/wm-helper)"
    cache_dir: str = ".cache"

    # 缓存 TTL（秒）
    items_ttl: int = 12 * 3600     # 物品表：12 小时
    orders_ttl: int = 30           # 订单：30 秒
    full_orders_ttl: int = 60

    # 限速：WM 公共接口 3 req/s
    rate_per_second: float = 3.0
    timeout: float = 15.0

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            platform=os.getenv("WM_PLATFORM", "pc"),
            language=os.getenv("WM_LANGUAGE", "zh-hans"),
            crossplay=_env_bool("WM_CROSSPLAY", False),
            proxy=os.getenv("WM_PROXY") or os.getenv("HTTPS_PROXY") or None,
            base_url=os.getenv("WM_BASE_URL", cls.base_url).rstrip("/"),
            token=os.getenv("WM_TOKEN") or None,
            user_agent=os.getenv("WM_USER_AGENT", cls.user_agent),
            cache_dir=os.getenv("WM_CACHE_DIR", ".cache"),
            items_ttl=int(os.getenv("WM_ITEMS_TTL", str(12 * 3600))),
            orders_ttl=int(os.getenv("WM_ORDERS_TTL", "30")),
            full_orders_ttl=int(os.getenv("WM_FULL_ORDERS_TTL", "60")),
            rate_per_second=float(os.getenv("WM_RATE", "3.0")),
            timeout=float(os.getenv("WM_TIMEOUT", "15.0")),
        )
