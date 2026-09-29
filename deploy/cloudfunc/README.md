# 云函数中转：让没有海外出口的服务器也能查 WM

原理：服务器（只能出国内）→ 国内云函数（有公网出网）→ `api.warframe.market`。

```
wm-bot ──HTTPS(国内可达)──► 云函数 ──公网──► api.warframe.market
```

适合：服务器出境被封、又不想依赖 NAS / 海外 VPS / 常开本地机。

## 部署（腾讯云 SCF，约 3 分钟）

1. 控制台 → 云函数 SCF → 新建 → **Web 函数**
   - 运行环境：Python 3.10
   - 入口：`wm_proxy.main_handler`
   - 把 `wm_proxy.py` 内容贴进去
2. 环境变量加 `WM_TOKEN`，值用一个随机串（例如 `openssl rand -hex 16` 生成）
3. 触发器用默认公网访问地址（或绑 API 网关），记下 URL，形如
   `https://service-xxxxxx-xxxxxxxx.gz.apigw.tencentcs.com/release/`
4. 在服务器上配置：

```bash
# /opt/wm-helper/bot/.env
WM_BASE_URL=https://service-xxxxxx-xxxxxxxx.gz.apigw.tencentcs.com/release/v2
WM_TOKEN=<刚才的随机串>
```

然后 `systemctl restart wm-bot`。

阿里云 FC 同理，用 **Web 函数 / WSGI**，入口填 `wm_proxy.handler`。

## 自检

```bash
# 1) 云函数是否通（本机测也行）
curl -sS -H "X-WM-Token: <token>" \
  "https://<函数URL>/release/v2/versions" | head -c 200

# 2) 服务器上测
curl -sS -H "X-WM-Token: <token>" \
  "https://<函数URL>/release/v2/orders/item/volt_prime_set/top" | head -c 300
```

## 成本

- 腾讯云 SCF 免费额度：每月 100 万次调用 + 40 万 GBs，本场景每天几十次请求，**免费额度完全够**
- 物品表（2.4MB）每天只拉一次并落磁盘缓存，其余都是小请求

## 安全

- 函数只接受 GET，路径必须 `/v2/` 开头，目标固定 `api.warframe.market`（不能当开放代理）
- 必须带 `X-WM-Token`，token 只存在云函数环境变量与服务器 `.env`，不要进仓库
- 若发现被滥用，直接改 `WM_TOKEN` 两边同步即可
