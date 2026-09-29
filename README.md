# warframe-market-helper

QQ 群里的 **Warframe Market 国际服查价机器人**：一句话查实时价格、看买卖单、复制 WTS/WTB 话术。

```
Tenno: /wm 电男p
Bot:   🔎 命中 4 个「电男/Prime」，回复序号（30s）
       1. Volt Prime 一套 / Volt Prime Set
       2. Volt Prime 蓝图 / Volt Prime Blueprint
       ...
Tenno: 1
Bot:   ┌ WM · PC · 12:03:41 ┐
       Volt Prime 一套 / Volt Prime Set
       ────────────────────────
       最低卖  78p  Tenno_A 🟢在线 ×1
       最高买  60p  Tenno_B 🎮游戏中 ×1
       ────────────────────────
       Ducat 180
       ────────────────────────
       WTS [Volt Prime Set] 78p   ← 长按复制
```

## 功能

- **混合检索**：中文官方名、英文原名、社区外号都能查（`圣装伏特` / `volt prime` / `电男p` 都指向同一件物品）
- **查价**：最低卖 / 最高买 + 卖家在线状态 + Ducat + 一键复制交易话术
- **买卖榜单**：`/wm 卖单 xxx`、`/wm 买单 xxx`，以 QQ 合并转发发送，不刷屏
- **等级过滤**：Mod 类物品支持 `r10` 等过滤（`盲怒 r0` 与 `盲怒 r10` 价格差很多）
- **平台与语言**：`Platform: pc/ps4/xbox/switch`，检索默认 `zh-hans`
- 群级冷却、本地缓存、严格的限速与重试（遵守 WM 官方规则）

暂不做：挂单 / 改单 / 撤单（需 WM 账号登录态）。

## 快速开始（不用 QQ 也能试）

```bash
python3 -m venv .venv && ./.venv/bin/pip install -e . && ./.venv/bin/pip install -r bot/requirements.txt

python -m wm_helper.cli "电男p"            # 候选列表
python -m wm_helper.cli "电男p" --pick 1   # 直接查套装
python -m wm_helper.cli "盲怒" --rank 10   # 满级价
python -m wm_helper.cli "圣装伏特" --all-orders --side sell
```

## 部署

架构：**NapCat**（QQ 协议端，OneBot v11 反向 WS）+ **NoneBot2**（本项目的 `bot/`）。

```bash
# 服务器端
cd /opt/wm-helper
python3 -m venv .venv && ./.venv/bin/pip install -r bot/requirements.txt
cp bot/.env.example bot/.env     # 填 WM_PROXY 等
systemctl enable --now wm-bot    # 见 docs/deploy.md 的 service 文件
```

详细步骤、常见问题与踩坑记录见 [`docs/deploy.md`](docs/deploy.md)；设计方案见 [`docs/design.md`](docs/design.md)。

### 海外出口

Warframe Market 的 API 在境外，国内服务器通常需要一个出口。主方案是服务器本地跑 **sing-box** 并使用你自己的订阅节点：

```bash
curl -sSL -A "clash-verge/v1.7.0" -o /tmp/sub.yaml "<订阅链接>"
python3 tools/clash2singbox.py /tmp/sub.yaml --pick "荷兰-NL-4,日本-TY-3" -o /tmp/sb.json
scp /tmp/sb.json <服务器>:/etc/sing-box/config.json
```

再把 `bot/.env` 的 `WM_PROXY` 设为 `socks5://127.0.0.1:7890`。
若服务器完全无境外出口，可参考 [`deploy/cloudfunc/`](deploy/cloudfunc/)（云函数中转）或 [`deploy/wireguard/`](deploy/wireguard/)（WireGuard 直连内网机器做出口）。

## 指令

| 指令 | 说明 |
| --- | --- |
| `/wm <物品>` | 查价；命中多个时给编号 |
| `/wm 卖单 <物品>` / `/wm 买单 <物品>` | 最低 5 条卖单 / 最高 5 条买单 |
| `/wm <物品> r10` | 指定 Mod 等级 |
| `/wm 平台 ps4` | 切换平台（pc/ps4/xbox/switch/mobile） |
| `/wm 帮助` | 指令清单 |
| `@机器人 <物品>` | 不加指令也能查 |

## 别名表

官方中文名形如「Volt Prime 一套」，和玩家口头称呼（电男 P）差别大，因此检索分三层：
官方中文名 → 英文原名/slug → **社区外号别名表**（`data/aliases.yaml`）。

外号表是体验差异最大的部分，欢迎直接编辑提交 PR；也可以按 `/wm 别名 xxx = slug` 在群里维护。

## 数据来源与合规

数据来自 [Warframe Market](https://warframe.market) 公开 API v2。本项目遵守其官方规则：

- 请求带可识别的 `User-Agent`，不伪装浏览器
- 全局限速 3 req/s，缓存优先、禁止紧密轮询（物品表 12 小时缓存）
- 不镜像数据、不复制站点、不做自动交易

## 目录

```
wm_helper/            核心库：client / items / search / price / format / cli
data/aliases.yaml     社区外号别名表
bot/                  NoneBot2 应用 + wm_market 插件
deploy/singbox/       sing-box 配置与 systemd
deploy/cloudfunc/     云函数中转（无境外出口时的备选）
deploy/wireguard/     WireGuard 出口方案（备选）
tools/clash2singbox.py  Clash 订阅 → sing-box 配置
docs/                 设计方案与部署说明
```

## 路线图

- [x] 检索 / 查价 / 榜单 / 话术
- [ ] 降价订阅提醒
- [ ] 套装 vs 散件比价
- [ ] Ducanator（杜卡特性价比榜）
- [ ] 裂罅 / 玄骸词库
- [ ] 结果图片化卡片
