from __future__ import annotations

from .items import Item
from .price import OrderView, PriceSnapshot


def _line(text: str = "", width: int = 24) -> str:
    return "─" * width if not text else text


def trade_phrase(item: Item, price: int | None = None, side: str = "sell") -> str:
    """生成可直接粘贴到游戏内交易频道的 WTS/WTB 话术。"""
    name = item.name_en
    if side == "sell":
        return f"WTS [{name}] {price}p" if price else f"WTS [{name}]"
    return f"WTB [{name}] {price}p" if price else f"WTB [{name}]"


def _order_line(label: str, o: OrderView | None, empty: str) -> str:
    if not o:
        return f"{label}  {empty}"
    rank = f" r{o.rank}" if o.rank is not None else ""
    return f"{label}  {o.platinum}p  {o.user_name} {o.status_text} ×{o.quantity}{rank}"


def render_price(snap: PriceSnapshot) -> str:
    item = snap.item
    lines: list[str] = []
    lines.append(f"┌ WM · {snap.platform.upper()} · {snap.time_text} ┐")
    lines.append(item.display)
    lines.append(_line())

    sell = snap.lowest_sell
    buy = snap.highest_buy
    lines.append(_order_line("最低卖", sell, "暂无在线卖单"))
    lines.append(_order_line("最高买", buy, "暂无在线买单"))
    lines.append(_line())

    extra = []
    if item.ducats:
        extra.append(f"Ducat {item.ducats}")
    if item.vaulted is not None:
        extra.append("入库 ✔" if item.vaulted else "未入库")
    if extra:
        lines.append(" · ".join(extra))
    if item.max_rank:
        lines.append(f"提示：该物品有等级（0~{item.max_rank}），加 r10 可查满级价")
    if extra or item.max_rank:
        lines.append(_line())

    if sell:
        lines.append(trade_phrase(item, sell.platinum, "sell") + "   ← 长按复制")
    elif buy:
        lines.append(trade_phrase(item, buy.platinum, "buy") + "   ← 长按复制")
    return "\n".join(lines)


def render_candidates(items: list[Item], query: str) -> str:
    lines = [f"🔎 「{query}」命中 {len(items)} 个，回复序号选择（30s）"]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item.display}")
    return "\n".join(lines)


def render_orders(item: Item, orders: list[OrderView], side: str) -> str:
    title = "最低卖单" if side == "sell" else "最高买单"
    lines = [f"{item.display} · {title} {len(orders)} 条"]
    for i, o in enumerate(orders, 1):
        rank = f" r{o.rank}" if o.rank is not None else ""
        lines.append(f"{i}) {o.platinum}p  {o.user_name} {o.status_text} ×{o.quantity}{rank}")
    if orders:
        best = orders[0]
        lines.append(trade_phrase(item, best.platinum, side))
    return "\n".join(lines)
