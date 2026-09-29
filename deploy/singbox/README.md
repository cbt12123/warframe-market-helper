# sing-box：给服务器上的 wm-helper 提供海外出口

只监听 `127.0.0.1:7890`（mixed = HTTP + SOCKS5 同端口），**只给机器人这一个进程用**，不改服务器全局路由。

## 已安装

- 二进制：`/usr/local/bin/sing-box`（v1.14.2，由本地下载后上传，运行期不依赖本地）
- 配置：`/etc/sing-box/config.json`
- 服务：`systemctl status|restart singbox`

## 启用步骤（拿到节点后）

1. 把 `/etc/sing-box/config.json` 里 `tag: "proxy"` 的 `direct` 出站换成真实节点，例如：

```json
{
  "type": "vless",
  "tag": "proxy",
  "server": "节点域名或IP",
  "server_port": 443,
  "uuid": "xxxx",
  "tls": { "enabled": true, "server_name": "节点SNI", "utls": { "enabled": true, "fingerprint": "chrome" } }
}
```

Trojan / VMess / Shadowsocks / Hysteria2 同理，只改 `type` 与对应字段即可。

2. 校验并重启：

```bash
sing-box check -c /etc/sing-box/config.json && systemctl restart singbox
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 \
  -x socks5://127.0.0.1:7890 -H 'User-Agent: wm-helper/0.1.0' \
  https://api.warframe.market/v2/versions
```

3. 把 `/opt/wm-helper/bot/.env` 的 `WM_PROXY` 改成 `socks5://127.0.0.1:7890`，再 `systemctl restart wm-bot`。

## 注意

- 当前配置**不含 `dns` 段**，走服务器系统 DNS（`/etc/resolv.conf`）。若节点域名被解析到错误 IP，再按 sing-box 1.14 语法加 `dns.servers[].domain_resolver` 的 DoH 配置。
- 出站只有 `direct` 与 `proxy` 两个 tag，填节点时只替换 `proxy` 那一条，`direct` 保留。
- 凭据只存在于服务器配置文件与 `bot/.env`，不要提交进仓库。
