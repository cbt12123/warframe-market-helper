from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .client import WMClient
from .items import Item

STATUS_EMOJI = {
    "online": "🟢",
    "ingame": "🎮",
    "offline": "⚪",
    "invisible": "⚪",
}


@dataclass
class OrderView:
    """一条订单的展示视图。platinum 为单价。"""

    order_id: str
    type: str                 # buy / sell
    platinum: int             # 单价
    quantity: int
    per_trade: int | None = None
    rank: int | None = None
    subtype: str | None = None
    user_name: str = ""
    platform: str = ""
    crossplay: bool = False
    status: str = "offline"
    reputation: int = 0
    created_at: str = ""

    @classmethod
    def from_api(cls, raw: dict[str, Any], fallback_type: str = "") -> "OrderView":
        user = raw.get("user") or {}
        return cls(
            order_id=raw.get("id", ""),
            type=raw.get("type") or fallback_type,
            platinum=int(raw.get("platinum") or 0),
            quantity=int(raw.get("quantity") or 1),
            per_trade=raw.get("perTrade"),
            rank=raw.get("rank"),
            subtype=raw.get("subtype"),
            user_name=user.get("ingameName") or "",
            platform=user.get("platform") or "",
            crossplay=bool(user.get("crossplay")),
            status=user.get("status") or "offline",
            reputation=int(user.get("reputation") or 0),
            created_at=raw.get("createdAt") or "",
        )

    @property
    def status_text(self) -> str:
        return f"{STATUS_EMOJI.get(self.status, '⚪')}{self.status}"

    @property
    def total(self) -> int:
        return self.platinum * self.quantity


@dataclass
class PriceSnapshot:
    item: Item
    sells: list[OrderView] = field(default_factory=list)
    buys: list[OrderView] = field(default_factory=list)
    fetched_at: float = field(default_factory=time.time)
    platform: str = "pc"

    @property
    def lowest_sell(self) -> OrderView | None:
        return min(self.sells, key=lambda o: o.platinum) if self.sells else None

    @property
    def highest_buy(self) -> OrderView | None:
        return max(self.buys, key=lambda o: o.platinum) if self.buys else None

    @property
    def time_text(self) -> str:
        return datetime.fromtimestamp(self.fetched_at).strftime("%H:%M:%S")


async def fetch_top(
    client: WMClient,
    item: Item,
    *,
    rank: int | None = None,
    subtype: str | None = None,
    platform: str = "pc",
) -> PriceSnapshot:
    """取在线用户的最优 5 卖 / 5 买单。"""
    filters: dict[str, Any] = {}
    if rank is not None:
        filters["rank"] = rank
    if subtype:
        filters["subtype"] = subtype
    data = await client.orders_top(item.slug, **filters) or {}
    sells = [OrderView.from_api(o, "sell") for o in (data.get("sell") or [])]
    buys = [OrderView.from_api(o, "buy") for o in (data.get("buy") or [])]
    sells.sort(key=lambda o: o.platinum)
    buys.sort(key=lambda o: -o.platinum)
    return PriceSnapshot(item=item, sells=sells, buys=buys, platform=platform)


async def fetch_all_orders(client: WMClient, item: Item) -> list[OrderView]:
    """取该物品的完整可见订单。"""
    data = await client.orders_item(item.slug) or []
    orders = [OrderView.from_api(o) for o in data]
    return orders
