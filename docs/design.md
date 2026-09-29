# wm-helper：QQ 群 Warframe Market 查询机器人 — 设计方案（v0.2）

## 0. 已确认的需求决策

| 项 | 决策 | 影响 |
| --- | --- | --- |
| 服务器 | **国际服（global）** | warframe.market 本身就是国际服数据，无需区分；请求固定 `Platform: pc` |
| 检索语言 | **中文检索 + 英文原名都能查** | 官方 `i18n` 提供中文名；社区外号（电男 P）靠别名表 |
| 使用范围 | **单个群自用** | 不做多群配额/白名单系统，群 ID 写配置；限流保留但放宽 |
| 部署 | **国内服务器** | 需实测到 `api.warframe.market` 的连通性，必要时走代理 |
| 技术栈 | 见第 2 节对比（推荐 NapCat + NoneBot2） | — |

> 关于"国际服"：WM 只有一套全球市场数据，按平台（pc/ps4/xbox/switch）区分；国服数据不在 WM 上。所以"国际服"= 默认 `Platform: pc`，默认关闭 crossplay（也可按需开启）。

---

## 1. 中文检索与别名设计（重点）

官方 `GET /v2/items` 带 `Language: zh-hans` 时，Item 模型返回 `i18n` map，其中 `i18n['zh-hans'].name` 即中文名（如 "圣装伏特 套装"）。因此**三层检索**：

1. **官方中文名**（自动同步，每日刷新）：`圣装伏特` → `volt_prime_set`
2. **英文原名 / slug**：`volt prime`、`volt_prime_set`、`vp`
3. **社区外号别名表**（手工维护 + 群内可加）：`电男`=Volt、`电男p`=圣装伏特、`圣装`=Prime、`P`=Prime、`沙甲`=Inaros、`奶妈`=Trinity …

匹配顺序：精确 slug/中文名 → 别名表 → 前缀 → 子串 → 模糊（difflib） → 拼音首字母（可选）。

规范化处理（搜索前统一）：
```
小写、去空格/下划线、去掉「圣装/prime/p/之/·」等噪声词后做二次匹配
```
例：`电男 p` → `电男p` → 别名 `volt` + `prime` 词元 → 命中 `volt_prime_*` 一组 → 若命中多个，给编号选择：
```
🔎 命中 4 个「电男/Prime」，回复序号（30s）
1. 圣装伏特 套装
2. 圣装伏特 蓝图
3. 圣装伏特 机体
4. 圣装伏特 系统
```

别名表建议独立成 `data/aliases.yaml`（可提交、可人工补充），并支持群内维护：
```
/wm 别名 电男p = volt_prime_set     （管理员，写入自定义别名表）
```
> 别名表是体验差异最大的部分：官方中文名能解决 70%，剩下 30% 靠社区外号表。初期可只维护 30~50 条高频战甲/武器外号。

---

## 2. 三种方案对比与实现难度

| 维度 | A. NapCat + NoneBot2 | B. AstrBot（+NapCat） | C. QQ 开放平台官方机器人 |
| --- | --- | --- | --- |
| 本质 | 第三方协议端 + Python 框架 | 一体化机器人平台（含 WebUI） | 官方 API（合规） |
| 账号要求 | 一个**小号 QQ** 扫码登录 | 同 A | 开发者资质 + 创建机器人 + 审核 |
| 安装难度 | ★★★☆☆（Docker 起 NapCat，配反向 WS） | ★★☆☆☆（Docker 一键 + 网页配置） | ★★☆☆☆（无需协议端，但要配公網回调/WS 与审核） |
| 开发难度 | ★★★☆☆（写插件：指令、缓存、限流） | ★★☆☆☆（插件更简单，或直接用现成插件） | ★★★☆☆（官方 SDK、消息模板/Ark 规范） |
| 消息能力 | **几乎无限制**：任意触发、合并转发、图片、@、主动推送 | 同 A（底层也是 NapCat） | 受限：基本只支持 @/指令触发，**主动推送（订阅提醒）受限** |
| 稳定性/风控 | 有掉线、风控、极端情况封号风险 | 同 A | **最稳**，官方支持 |
| 迭代风险 | QQ 协议更新时可能临时失效 | 同 A | 接口稳定但有审核/配额 |
| 适合场景 | 自定义业务逻辑（我们这种） | 想快速上手 + 以后接 LLM/闲聊 | 面向大量陌生用户、要求合规 |
| M1 工作量 | 约 1~2 天 | 约 0.5~1 天 | 约 2 天 + 等待审核（数天） |

**结论（针对本需求：单群自用、自定义查询、需要订阅主动推送）**

- 推荐 **A（NapCat + NoneBot2）**：我们的逻辑 90% 是「指令 → 调 WM API → 格式化」，需要精细控制缓存/限速/定时任务，NoneBot2 的插件结构最顺手；订阅提醒必须能主动发消息，官方平台（C）在这点上是硬伤。
- 选 **B** 的理由：想省事、要 WebUI 管理、后续想接 LLM 做闲聊/自然语言查价。代价是精细控制稍弱。
- 不推荐 **C**：审核周期 + 主动推送受限，与"订阅降价提醒"冲突。

**国内服务器对三方案的影响**：A/B 都需要跑 NapCat（Docker，国内云 1C2G 够用，QQ 登录通常手机扫码一次即可，之后无头运行）；C 需要公网 HTTPS 回调或官方 WS，国内服务器没障碍但要备案域名（回调方式）。

---

## 3. 架构

```
QQ 群 ──► NapCat(Docker, 小号登录)
             └─ OneBot v11 反向 WS ──► NoneBot2(bot 容器)
                                        ├─ 指令解析 / 单人+群级冷却
                                        ├─ items_index  (SQLite: 中文名 + 别名 + 模糊搜索)
                                        ├─ wm_client    (3 req/s 令牌桶 + 缓存 + UA + 退避)
                                        ├─ render       (文本卡片 / 合并转发)
                                        ├─ subscribe    (订阅表 + 定时轮询)
                                        └─ SQLite
                                              │
                                              ▼
                                   api.warframe.market/v2
                                   Headers: Platform: pc | Language: zh-hans | Crossplay: false
```

### 目录结构

```
wm-helper/
├─ docker-compose.yml            # napcat + bot
├─ data/aliases.yaml             # 社区外号别名表（可人工维护）
├─ bot/
│  ├─ pyproject.toml
│  ├─ .env                       # 不入库：QQ 号、群号、管理员、代理
│  └─ src/plugins/wm_market/
│     ├─ config.py
│     ├─ wm_client.py            # 限速/缓存/重试
│     ├─ items_index.py          # 物品表同步 + 别名 + 搜索
│     ├─ render.py
│     ├─ handlers/{price,subscribe,admin}.py
│     └─ models.py
└─ docs/design.md
```

---

## 4. 数据源与调用策略（国际服 / PC）

| 用途 | 接口 | 策略 |
| --- | --- | --- |
| 物品全量表（含中文名、Ducat、是否入库） | `GET /v2/items`，`Language: zh-hans` | 启动 + 每日 04:00 刷新，写 SQLite；另存 `i18n['en'].name` |
| 套装散件 | `GET /v2/item/{slug}/set` | 按需，TTL 24h（用于"套装 vs 散件哪个划算"） |
| 查价（主） | `GET /v2/orders/item/{slug}/top` | TTL 30s；在线用户各 5 条最优买卖单 |
| 完整榜单 | `GET /v2/orders/item/{slug}` | 用户显式要看榜单时，TTL 60s |
| 排序维度 | `/top` 支持 `rank` / `charges` / `subtype` / `amberStars` / `cyanStars` | 用于 Mods 等级、Arcane rank、雕像星数过滤 |

Item 可用字段（已确认）：`id`、`slug`、`i18n{lang:{name,icon,thumb,wikiLink}}`、`ducats`、`vaulted`、`setRoot`、`setParts`、`quantityInSet`、`maxRank`、`maxCharges`、`subtypes`、`bulkTradable`、`tradable`、`tradingTax`、`baseEndo`/`endoMultiplier`、`tags`。

Order 可用字段：`type`、`platinum`、`quantity`、`perTrade`、`rank`、`subtype`、`user{ingameName,status,platform,crossplay,reputation}`、`createdAt`。用户状态枚举：`online` / `ingame` / `offline`（`invisible` 对外显示为 offline）。

⚠️ **待实测校准**：`Order.platinum` 文档描述为 "Total platinum currency"，与 `quantity`、`perTrade` 的关系需在真实响应里确认（显示"单价"还是"每笔总价"），M1 联调时对齐一次即可。

### 合规硬约束（WM 官方规则）

- `User-Agent: wm-helper/0.1.0 (+<仓库或联系方式>)`，禁止伪装浏览器
- 全局 **3 req/s** 令牌桶；缓存优先；失败指数退避 1s→2s→4s（最多 3 次）
- 不做数据镜像、不做交易自动化机器人

### 国内服务器：代理方案（已确认直连不通，必须走代理）

**结论：只有 bot 容器访问 `api.warframe.market` 需要代理；NapCat 连腾讯服务器，国内正常，不要走代理。**

#### 0) 先确认"是不是真的需要代理"（直连排查）

```bash
# ① 直连（不带 -x），看看到底通不通
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' --max-time 20 \
  -H 'User-Agent: wm-helper/0.1.0' https://api.warframe.market/v2/items

# ② DNS 能否解析
getent hosts api.warframe.market || nslookup api.warframe.market

# ③ 卡在哪一步（DNS / TCP / TLS / HTTP）
curl -v --max-time 15 https://api.warframe.market/v2/items 2>&1 | tail -20

# ④ 本机到底有没有代理进程在跑
ss -lntp | head -30
command -v clash sing-box v2ray xray gost 2>/dev/null
```

结果判读：
- `200` → **不需要代理**，直接用（很多云主机出口本来就在海外）
- 连接超时 / `Connection reset` → 网络层不通，必须换出口（代理或海外机）
- DNS 解析失败 → 先换 DNS（`echo 'nameserver 1.1.1.1' >> /etc/resolv.conf`）再试
- TLS 握手成功但 `403/503` → Cloudflare 拦了该出口 IP，需要换出口 IP

#### 1) 先验证代理可用性（在能出网的那台机器上）

```bash
# HTTP 代理（把 127.0.0.1:7890 换成你的代理地址）
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' \
  -x http://127.0.0.1:7890 \
  -H 'User-Agent: wm-helper/0.1.0' -H 'Platform: pc' -H 'Language: zh-hans' \
  https://api.warframe.market/v2/items

# SOCKS5 代理
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' \
  -x socks5h://127.0.0.1:1080 -H 'User-Agent: wm-helper/0.1.0' \
  https://api.warframe.market/v2/items
```
返回 `200` 且耗时可接受即可（首次数 MB 的 /v2/items 可能几秒，后续落缓存）。

#### 2) docker-compose 里给 bot 容器注入代理（不要给 napcat）

```yaml
services:
  bot:
    environment:
      - HTTP_PROXY=http://host.docker.internal:7890    # 或 socks5://...
      - HTTPS_PROXY=http://host.docker.internal:7890
      - ALL_PROXY=socks5://host.docker.internal:1080   # SOCKS5 时用它
      - NO_PROXY=localhost,127.0.0.1,napcat,ws         # 关键：NapCat 的 WS 不走代理
    extra_hosts:
      - "host.docker.internal:host-gateway"            # 让容器能访问宿主机上的代理
```
- 代理跑在**宿主机**（Clash/sing-box 等）→ 用 `host.docker.internal` + `extra_hosts`；或让代理监听 `0.0.0.0`
- 代理跑在**另一台机器** → 直接写那台机器的内网 IP/端口
- 如果嫌麻烦，可让 bot 用 `network_mode: host`（此时写 `127.0.0.1` 即可，但要改掉端口映射写法）

#### 3) httpx 客户端（默认 `trust_env=True`，会自动读环境变量，但显式写更可控）

```python
import httpx

HEADERS = {
    "User-Agent": "wm-helper/0.1.0 (+https://example.com/wm-helper)",
    "Platform": "pc",
    "Language": "zh-hans",
    "Accept": "application/json",
}

client = httpx.AsyncClient(
    base_url="https://api.warframe.market/v2",
    headers=HEADERS,
    timeout=httpx.Timeout(15.0),
    proxy=PROXY_URL or None,   # 从配置读；None 表示直连
    limits=httpx.Limits(max_connections=5, max_keepalive_connections=5),
)
```
> `NO_PROXY` 已排除 `napcat`，不会把 OneBot 的反向 WS 也绕到代理上。

#### 3.5) 临时方案：用 SSH 动态转发做 SOCKS5（无代理软件时最快）

在一台**能正常访问 WM 的机器**（你的 Mac、或任意海外 VPS）可达的前提下，在服务器上执行：

```bash
ssh -fN -D 127.0.0.1:1080 <user>@<可出网的机器IP>     # 服务器本地监听 1080，流量由对端出口
curl -sS -o /dev/null -w '%{http_code}\n' -x socks5h://127.0.0.1:1080 \
  -H 'User-Agent: wm-helper/0.1.0' https://api.warframe.market/v2/items
```
长期运行用 `autossh -M 0 -fN -D 127.0.0.1:1080 user@host` 或写进 systemd 保活；然后 `ALL_PROXY=socks5h://127.0.0.1:1080` 给 bot 容器即可（容器内用 `host.docker.internal` + `extra_hosts`）。

#### 4) 备选（不想在国内机上搞代理）
把 **bot 容器放海外轻量机**（只跑 Python + SQLite），**NapCat 留国内**，两者通过反向 WebSocket 连接（NapCat 主动连海外的 bot 地址，国内出网到海外一般没问题）。这样代理只影响 bot→WM 这一段，甚至不需要代理。

#### 5) 仍要注意
- 物品表（`/v2/items`，数 MB）是唯一大响应，落 SQLite，只在启动/每日 04:00 拉一次
- 3 req/s 令牌桶照旧，代理延迟高时把超时设到 15s 并做退避，别让群里干等

---

## 5. 交互设计

### 5.1 触发方式
- 指令：`/wm volt prime`、`wm 圣装伏特`、`/wm 电男p`
- @机器人：`@bot 电男p 多少`
- 私聊：直接发物品名（免前缀）

### 5.2 查价（主流程）

```
Tenno:  /wm 电男p
Bot:    🔎 命中 4 个「电男/Prime」，回复序号（30s）
        1. 圣装伏特 套装  2. 圣装伏特 蓝图  3. 圣装伏特 机体  4. 圣装伏特 系统
Tenno:  1
Bot:    ┌ WM · PC · 国际服 · 12:03:41 ┐
        圣装伏特 套装 / Volt Prime Set
        ─────────────────────
        最低卖  78p   Tenno_A  🟢在线
        最高买  60p   Tenno_B  🎮游戏中
        ─────────────────────
        卖单 43 · 买单 28 · 中间价 69p
        Ducat 100 · 入库 ✔
        ─────────────────────
        WTS [Volt Prime Set] 78p        ← 长按复制
```

要点：命中多个给编号；同一群记住上次选择 5 分钟；结尾附 `WTS/WTB` 话术（最高频刚需）；状态用 🟢在线 / 🎮游戏中 / ⚪离线。

### 5.3 榜单

```
Tenno:  /wm 卖单 圣装伏特 套装
Bot:    （合并转发「圣装伏特套装 · 最低 5 条卖单」）
        1) 78p  Tenno_A 🟢在线   12:03
        2) 79p  Tenno_C 🎮游戏中 12:01
        ...
        复制: WTS [Volt Prime Set] 78p
Tenno:  /wm 买单 电男p          → 最高 5 条买单 + WTB 话术
Tenno:  /wm 卖单 盲怒 r0        → 带 rank 过滤（Mods 常用）
```
列表一律合并转发，避免刷屏。

### 5.4 订阅提醒

```
Tenno:  /wm 订阅 圣装伏特 套装 卖 <= 70
Bot:    ✅ 已订阅 #1：圣装伏特套装 最低卖价 ≤ 70p（每小时检查，7 天过期）
...
Bot:    🔔 @Tenno 圣装伏特套装 最低卖价 68p（Tenno_A 🟢在线）
        WTS [Volt Prime Set] 68p
        （回复 /wm 订阅 1 可续订）
```

### 5.5 其他

```
/wm 套装 圣装伏特      → 套装价 vs 散件总价对比（用 /set）
/wm 杜卡 圣装伏特      → Ducat 与性价比（Ducanator，M3）
/wm 帮助              → 合并转发指令清单
/wm 别名 电男p = volt_prime_set   → 管理员维护别名
```

### 5.6 输出形态
- M1：**纯文本卡片**（QQ 不渲染 Markdown，用符号 + emoji，最稳最快）
- 长内容（榜单、帮助）用 **合并转发**
- M3 可选：HTML → 图片的卡片（含物品图标、价格走势），依赖重、按需开关

---

## 6. 数据模型（SQLite）

```text
items(id, slug, name_en, name_zh, tags, tradable, max_rank, max_charges,
      subtypes(json), ducats, vaulted, set_root, set_parts(json), updated_at)
aliases(alias, slug, source)              # 内置外号 + 用户自定义
orders_cache(slug, platform, crossplay, kind, payload_json, fetched_at)  # 30~60s
subscriptions(id, user_id, group_id, slug, side, op, target_price,
              expires_at, last_value, fired)
group_settings(group_id, platform, crossplay, language, cooldown)
```

---

## 7. 风险与对策

| 风险 | 对策 |
| --- | --- |
| WM 429 / Cloudflare 509 | 令牌桶 3/s + 缓存 + 退避；超限回"稍后再试" |
| 国内访问慢/不通 | 实测；配 `HTTPS_PROXY`，或 bot 放海外、NapCat 留国内 |
| NapCat 掉线/风控 | 独立小号、`restart: unless-stopped`、掉线推管理群；不刷屏、群冷却 3s |
| 中文名缺失/翻译怪 | 官方 i18n + 别名表双层兜底；命中不到给最相近 3 个候选 |
| 安全 | 配置只在 `.env` 且不入库；管理员指令校验 QQ 号；用户输入只作查询参数，不拼 shell、不请求任意 URL（防 SSRF） |
| 合规 | 遵守 WM 规则：UA、缓存、不镜像、不做自动交易 |

---

## 8. 里程碑

| 阶段 | 交付 | 验收 |
| --- | --- | --- |
| M0 | docker-compose 起 NapCat + NoneBot2，`/ping` 有回复 | 群里收到消息 |
| M1 | 物品表同步（含中文名）+ 别名检索 + 查价 + 买卖单 + 复制话术 | `/wm 电男p` 5 秒内返回正确价格 |
| M2 | 订阅提醒 + 套装对比 + 群内限流 | 降价时 @ 到人 |
| M3 | Ducanator、裂罅/玄骸词库、图片卡片 | 可选 |

---

## 9. 附录：机器人"小号"是什么

- 指的是 **一个独立的 QQ 账号**（不是 Warframe 账号、也不是 WM 账号）。它就是用 NapCat 登录、在群里当"机器人"出现的那个 QQ。
- **不要用你自己的大号**：NapCat 是第三方协议实现，存在风控/限制登录/极端封号风险，用闲置号或小号隔离风险。
- 获取方式：新注册一个 QQ，或用长期不用的闲置号；建议先在手机 QQ 正常登录一次、完成基础安全验证，再交给 NapCat 扫码登录。
- 登录后 NapCat 无头运行、长期在线；掉线时通常需要重新扫码（偶尔会要求短信/人脸验证，用小号处理成本更低）。
- 群里的昵称/头像就是这个 QQ 号的资料，可自行改成"WM 查价"之类。
- **WM 侧不需要任何账号**：查价走的是 WM 公开只读 API（`/v2/items`、`/v2/orders/item/{slug}/top`），无需登录、无需 token；只有"挂单/改单"才需要 WM 账号，而我们不做。

---

## 10. 决策记录

| 项 | 结论 |
| --- | --- |
| 技术方案 | **A：NapCat + NoneBot2（OneBot v11 反向 WS）** |
| 服务器/平台 | 国际服，`Platform: pc`，默认不启 crossplay |
| 检索 | 中文（官方 i18n）+ 英文 + 社区外号别名表 |
| 部署 | 国内服务器；bot 容器走代理访问 WM，NapCat 不走代理 |
| 范围 | 单群自用 |

## 11. 待确认（确认后即可开工 M1）

1. 方案已定 **A（NapCat + NoneBot2）** ✅
2. 代理信息：**类型 + 地址:端口**（HTTP 还是 SOCKS5？跑在宿主机还是另一台机器？）→ 我写进 `docker-compose.yml` 与 `wm_client.py`
3. 小号 QQ 与群号是否就绪（有了就可以直接跑 M0：起 NapCat + `/ping`）
