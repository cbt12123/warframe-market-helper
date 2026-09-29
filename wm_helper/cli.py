"""本地命令行验证入口：python -m wm_helper.cli "电男p"

不走 QQ，仅用于联调检索与查价。
"""

from __future__ import annotations

import argparse
import asyncio

from .client import WMClient
from .config import Config
from .format import render_candidates, render_orders, render_price
from .items import ItemIndex
from .price import fetch_all_orders, fetch_top
from .search import ItemSearcher


async def main_async(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    async with WMClient(cfg) as client:
        raw = await client.items(refresh=args.refresh)
        index = ItemIndex.from_api(raw)
        searcher = ItemSearcher(index)

        hits = searcher.search(args.query, limit=args.limit)
        if not hits:
            print(f"未找到与「{args.query}」相关的物品")
            return 1
        if len(hits) > 1 and not args.pick:
            print(render_candidates(hits, args.query))
            return 0

        item = hits[0] if not args.pick else hits[args.pick - 1]
        if args.all_orders:
            orders = await fetch_all_orders(client, item)
            side = args.side
            filtered = [o for o in orders if o.type == side]
            filtered.sort(key=lambda o: o.platinum if side == "sell" else -o.platinum)
            print(render_orders(item, filtered[: args.limit], side))
            return 0

        snap = await fetch_top(client, item, rank=args.rank, platform=cfg.platform)
        print(render_price(snap))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Warframe Market 查价（本地验证）")
    parser.add_argument("query", help="物品名：电男p / 圣装伏特 / volt prime / 盲怒")
    parser.add_argument("--limit", type=int, default=8, help="候选/榜单条数")
    parser.add_argument("--pick", type=int, default=0, help="直接选第 N 个候选")
    parser.add_argument("--rank", type=int, default=None, help="Mod 等级过滤，如 0 或 10")
    parser.add_argument("--side", choices=["sell", "buy"], default="sell", help="榜单方向")
    parser.add_argument("--all-orders", action="store_true", help="查完整订单榜单")
    parser.add_argument("--refresh", action="store_true", help="强制刷新物品表缓存")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
