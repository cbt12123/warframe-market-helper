# 部署说明（当前实际状态）

## 1. 已完成的部署

| 项 | 状态 |
| --- | --- |
| 服务器 | `<服务器IP>:27135`（Debian 13 / 4C8G），已配置本机 SSH 密钥登录 |
| 海外出口 | 服务器**无任何海外出口**（国内站点通，cloudflare/docker hub/WM 全超时） |
| 出口方案 | 服务器本地 sing-box（`127.0.0.1:7890`，仅本机能用）；**待填节点** |
| 机器人 | `/opt/wm-helper`，venv + systemd 服务 `wm-bot`，已部署（监听 8080；物品表需代理通了才能拉取） |
| 协议端 NapCat | **未安装**（见第 4 节） |

> 早期曾临时用「本机代理 + ssh 反向隧道」借出口，已按需求彻底拆除（脚本已删除），运行期不依赖任何本地机器。

## 2. 目录与命令

```
/opt/wm-helper/
├─ wm_helper/        核心库（client / items / search / price / format / cli）
├─ data/aliases.yaml 社区外号别名表
├─ bot/              NoneBot2 应用（bot.py + src/plugins/wm_market）
├─ bot/.env          运行配置（WM_PROXY 等）
└─ .cache/           物品表磁盘缓存
```

```bash
# 服务运维
systemctl status|restart|stop wm-bot
journalctl -u wm-bot -f

# 本地联调（不依赖 QQ）
python -m wm_helper.cli "电男p" --pick 1
python -m wm_helper.cli "盲怒" --rank 10
python -m wm_helper.cli "圣装伏特" --all-orders --side sell

# 订阅转 sing-box 配置
python3 tools/clash2singbox.py /tmp/sub.yaml --pick "荷兰-NL-4" -o /tmp/sb.json
```

> 早期曾临时用「本机代理 + ssh 反向隧道」借出口，已彻底拆除（脚本已删除），运行期不依赖任何本地机器。

## 3. 代理（关键约束）

服务器 **必须** 能通过某种出口访问 `api.warframe.market`，出口地址配置在 `bot/.env` 的 `WM_PROXY`。

### 3.1 主方案：服务器本地 sing-box + 订阅（适用于有海外出口的机器）

```bash
# 1) 拉订阅（部分订阅校验 UA，不加会返回「访问受限」占位节点）
curl -sSL -A "clash-verge/v1.7.0" -o /tmp/sub.yaml "<你的订阅链接>"

# 2) 转成 sing-box 配置并挑节点
python3 tools/clash2singbox.py /tmp/sub.yaml --pick "荷兰-NL-4,爱沙尼亚-EE-1,日本-TY-3" -o /tmp/sb.json

# 3) 部署到服务器并校验
scp /tmp/sb.json <服务器>:/etc/sing-box/config.json
ssh <服务器> 'sing-box check -c /etc/sing-box/config.json && systemctl restart singbox'

# 4) 机器人指向它
WM_PROXY=socks5://127.0.0.1:7890
```

sing-box 只监听 `127.0.0.1:7890`（mixed = HTTP + SOCKS5 同端口），**只给 `wm-bot` 用**，不改全局路由。详见 `deploy/singbox/README.md`。

### 3.2 服务器出境被封时的备选

| 方案 | 说明 |
| --- | --- |
| **国内云函数中转**（`deploy/cloudfunc/`） | 服务器 → 云函数 → WM。已本地端到端验证，免费额度足够 |
| **WireGuard 直连家里 NAS**（`deploy/wireguard/`） | 云服务器做监听端（有公网 IP 即可），NAS **主动连入**并跑 sing-box 做出口；家里是局域网也没关系，不需要公网 IP 或端口映射 |
| 换/加一台有海外出口的机器 | 最省事 |

> ⚠️ 若服务器出境被封，Tailscale 同样不可用：其控制面（`login/controlplane/derp.tailscale.com`）全在海外，实测均不可达；代理节点的 IP 也不可达，所以「在服务器上装任何代理软件」都无效。

## 4. NapCat 待安装

已准备好的材料：`NapCat.Shell.zip`（v4.18.28）已下载在 Mac `/tmp/NapCat.Shell.zip`。

两种安装路径：

- **A. Docker（推荐，但需先解决拉镜像）**：给 `/etc/docker/daemon.json` 配 `proxies.httpProxy` 指向隧道端口，并放宽 `tools/local_proxy.py` 的域名白名单（docker.io / cloudflare 相关域名），再 `docker pull mlikiowa/napcat-docker:latest`
- **B. 无 Docker**：在服务器上安装 Linux QQ（`dpkg -i linuxqq_*.deb`，需先拿到官方直链）+ 解压 `NapCat.Shell.zip` 用 systemd 托管

装好后需要：用 **QQ 小号** 在 NapCat WebUI（`:6099`）扫码登录，并把反向 WS 指向 `ws://127.0.0.1:8080/onebot/v11/ws`，然后小号进群即可。

## 5. 已踩的坑（避免重复）

1. **NoneBot 不会把 `.env` 写进 `os.environ`** → 核心库用 `Config.from_env()` 读不到 `WM_PROXY`，必须显式 `load_dotenv()`（已在 `state.config()` 处理）
2. 部署同步代码时 **不要把本地 `bot/.env` 覆盖到服务器**（同步命令需排除 `bot/.env`）
3. 服务器 `python3 -m venv` 需要先 `apt install python3.13-venv`
4. Docker Hub 与国内加速站的 blob 都走海外/CloudFront → 这台机器 `docker pull` 不可用（除非走代理）
5. 检索必须按 slug 分词精确匹配，不能子串匹配（否则「电男」会命中 High Voltage / Voltaic Lance）
