# WireGuard 直连家里 NAS：给云服务器一个海外出口

拓扑（**不需要家里有公网 IP，也不用路由器端口映射**）：

```
云服务器（有公网 IP，WireGuard 监听端）  ←──主动连入──  家里 NAS（WireGuard 客户端）
        │                                                    │
   wm-bot / NapCat                                     sing-box（订阅节点）
   WM_PROXY=socks5://10.9.0.2:7890  ──► 10.9.0.2:7890 ──► 公网 ──► api.warframe.market
```

- 隧道地址：服务器 `10.9.0.1`，NAS `10.9.0.2`
- 端口：UDP `51820`（服务器 ufw 已放行）
- NAS 侧 `AllowedIPs = 10.9.0.1/32`：**只走这一条隧道**，不影响 NAS 正常上网

## 1. 服务器端（已完成）

`/etc/wireguard/wg0.conf`：

```ini
[Interface]
Address = 10.9.0.1/24
ListenPort = 51820
PrivateKey = <服务器私钥>
SaveConfig = false

[Peer]
PublicKey = <NAS 公钥>
AllowedIPs = 10.9.0.2/32
PersistentKeepalive = 25
```

启动：`systemctl enable --now wg-quick@wg0`，查看：`wg show`

## 2. NAS 侧（需要你操作）

`/etc/wireguard/wg0.conf`（或群晖/UnRAID 的导入界面）：

```ini
[Interface]
Address = 10.9.0.2/24
PrivateKey = <NAS 自己生成的私钥>
DNS = 223.5.5.5

[Peer]
PublicKey = v8LP/ZDY0w0ohfz91a3SffSK4N7V25nqqbZChGSxfSU=
Endpoint = <服务器IP>:51820
AllowedIPs = 10.9.0.1/32
PersistentKeepalive = 25
```

生成密钥对：`wg genkey | tee privatekey | wg pubkey > publickey`，把 **publickey 发我**。

各系统安装方式：
- **Linux**：`apt install wireguard wireguard-tools`（或 `apk add wireguard-tools`）
- **群晖 DSM**：Docker 跑 `linuxserver/wireguard`，或装第三方套件
- **UnRAID**：Apps 里装 WireGuard 插件
- **威联通**：Container Station 跑 `linuxserver/wireguard`

## 3. NAS 上跑 sing-box（做出口）

用 `tools/clash2singbox.py` 生成的配置，把入站监听改成隧道地址：

```json
"inbounds": [{ "type": "mixed", "tag": "mixed-in", "listen": "10.9.0.2", "listen_port": 7890 }]
```

若 NAS 上已有 Clash / sing-box 在跑，只要让它**监听 `10.9.0.2`**（或开 allow-lan）即可，不必重装。

## 4. 打通后

服务器 `/opt/wm-helper/bot/.env`：

```
WM_PROXY=socks5://10.9.0.2:7890
```

验证：

```bash
ping 10.9.0.2
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 -x socks5://10.9.0.2:7890 \
  -H 'User-Agent: wm-helper/0.1.0' https://api.warframe.market/v2/versions
```

返回 200 即可，之后 docker 也能走这条通道拉 NapCat 镜像。
