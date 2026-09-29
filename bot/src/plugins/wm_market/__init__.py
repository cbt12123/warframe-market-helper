"""wm_market 插件：QQ 群内查 Warframe Market 国际服价格。"""

from __future__ import annotations

import re

from nonebot import on_command, on_message, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.params import Arg, CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from nonebot.typing import T_State

from wm_helper.format import (
    render_candidates,
    render_orders,
    render_price,
)
from wm_helper.price import fetch_all_orders, fetch_top

from . import state

__plugin_meta__ = PluginMetadata(
    name="WM 查价",
    description="在 QQ 群里查询 Warframe Market 国际服实时价格与买卖单",
    usage="/wm 电男p · /wm 卖单 圣装伏特 · /wm 买单 盲怒 r10",
)

HELP = """WM 查价用法
/wm 电男p            查价（最低卖 / 最高买）
/wm 卖单 圣装伏特     最低 5 条卖单（转发消息）
/wm 买单 盲怒 r10     最高 5 条买单，可带等级
/wm 平台 ps4         切换平台（默认 pc）
/wm 帮助             显示本帮助"""

wm = on_command("wm", aliases={"WM", "查价", "wm查价"}, priority=5, block=True)
wm_mention = on_message(rule=to_me(), priority=10, block=False)


def _session(event: MessageEvent) -> str:
    gid = getattr(event, "group_id", None)
    return f"{gid or 'p'}:{event.get_user_id()}"


async def _send_price(item, rank: int | None = None) -> str:
    snap = await fetch_top(state.client(), item, rank=rank, platform=state.config().platform)
    return render_price(snap)


async def _send_orders(bot: Bot, event: GroupMessageEvent, item, side: str) -> None:
    orders = await fetch_all_orders(state.client(), item)
    filtered = [o for o in orders if o.type == side]
    filtered.sort(key=lambda o: o.platinum if side == "sell" else -o.platinum)
    text = render_orders(item, filtered[:8], side)
    if not isinstance(event, GroupMessageEvent):
        await wm.finish(text)
    node = MessageSegment.node_custom(int(bot.self_id), "WM 查价", text)
    await bot.send_group_forward_msg(group_id=event.group_id, messages=Message([node]))


@wm.handle()
async def handle_wm(
    bot: Bot, event: MessageEvent, state_: T_State, args: Message = CommandArg()
):
    raw = args.extract_plain_text().strip()
    if not raw:
        await wm.finish(HELP)

    key = state.cooldown_key(getattr(event, "group_id", None), event.get_user_id())
    left = state.check_cooldown(key)
    if left > 0:
        await wm.finish(f"查询太频繁，{left:.1f}s 后再试")

    # 子命令：卖单 / 买单
    m = re.match(r"^(卖单|买单|卖|买)\s*(.+)$", raw)
    side = None
    if m:
        side = "sell" if m.group(1).startswith("卖") else "buy"
        raw = m.group(2).strip()

    if raw in {"帮助", "help"}:
        await wm.finish(HELP)
    if raw.startswith("平台"):
        platform = raw.replace("平台", "").strip() or "pc"
        if platform not in {"pc", "ps4", "xbox", "switch", "mobile"}:
            await wm.finish("平台只能是 pc / ps4 / xbox / switch / mobile")
        state.config().platform = platform
        await wm.finish(f"已切换平台为 {platform}")

    rank = None
    mr = re.search(r"(?:r|rank)\s*(\d{1,2})\s*$", raw, re.IGNORECASE)
    if mr:
        rank = int(mr.group(1))
        raw = raw[: mr.start()].strip()

    try:
        searcher = state.searcher()
    except RuntimeError:
        await wm.finish("物品表还没加载好，稍等 10 秒再试")

    hits = searcher.search(raw, limit=8)
    if not hits:
        await wm.finish(f"没找到「{raw}」，试试英文全名，例如 volt prime")

    state.mark_called(key)

    if side:
        await _send_orders(bot, event, hits[0], side)
        await wm.finish()

    if len(hits) == 1:
        await wm.finish(await _send_price(hits[0], rank=rank))

    state.set_pending(_session(event), hits)
    state_.update({"hits": hits, "rank": rank})
    await wm.send(render_candidates(hits, raw))


@wm.got("choice", prompt=None)
async def handle_choice(state_: T_State, choice: Message = Arg()):
    hits = state_.get("hits") or []
    rank = state_.get("rank")
    text = choice.extract_plain_text().strip()
    if not text.isdigit():
        await wm.finish("已取消")
    idx = int(text)
    if not 1 <= idx <= len(hits):
        await wm.finish(f"序号无效，请输入 1~{len(hits)}")
    await wm.finish(await _send_price(hits[idx - 1], rank=rank))


@wm_mention.handle()
async def handle_mention(event: MessageEvent):
    """@机器人 + 物品名也能查。"""
    text = event.get_plaintext().strip()
    if not text or text.startswith("/"):
        return
    key = state.cooldown_key(getattr(event, "group_id", None), event.get_user_id())
    if state.check_cooldown(key) > 0:
        return
    try:
        searcher = state.searcher()
    except RuntimeError:
        return
    hits = searcher.search(text, limit=8)
    if not hits:
        return
    state.mark_called(key)
    if len(hits) == 1:
        await wm_mention.finish(await _send_price(hits[0]))
    state.set_pending(_session(event), hits)
    await wm_mention.finish(render_candidates(hits, text))


# 每日 04:00 刷新物品表（需要 nonebot-plugin-apscheduler）
try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler

    @scheduler.scheduled_job("cron", hour=4, minute=0, id="wm_refresh_items")
    async def _refresh_items() -> None:
        await state.load_items(refresh=True)

except Exception:  # noqa: BLE001
    pass
