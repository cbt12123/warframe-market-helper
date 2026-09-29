"""把 Clash 订阅 YAML 转成 sing-box 出站配置（供服务器上 wm-helper 使用）。

用法：
    # 1) 先拉订阅（部分订阅校验 UA，不加 UA 会返回「访问受限」占位节点）
    curl -sSL -A "clash-verge/v1.7.0" -o /tmp/sub.yaml "<订阅链接>"

    # 2) 选节点（按关键字或序号），生成配置
    python3 tools/clash2singbox.py /tmp/sub.yaml --pick "荷兰-NL-4,爱沙尼亚-EE-1,荷兰-NL-1,日本-TY-3" \
        --listen 127.0.0.1 --port 7890 -o /tmp/sb.json

    # 3) 上传到服务器并校验
    scp -i <key> -P <port> /tmp/sb.json root@<host>:/etc/sing-box/config.json
    ssh ... 'sing-box check -c /etc/sing-box/config.json && systemctl restart singbox'

注意：脚本只在本地运行，产物里含节点凭据，不要提交进仓库。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import yaml


def convert_node(name: str, p: dict[str, Any]) -> dict[str, Any] | None:
    """Clash 节点 -> sing-box 出站。"""
    server = p.get("server")
    port = int(p.get("port") or 0)
    if not server or not port:
        return None
    out: dict[str, Any] = {"server": server, "server_port": port}
    tls_cfg: dict[str, Any] = {
        "enabled": True,
        "insecure": bool(p.get("skip-cert-verify", False)),
        "utls": {"enabled": True, "fingerprint": "chrome"},
    }
    if p.get("sni"):
        tls_cfg["server_name"] = p["sni"]
    elif p.get("servername"):
        tls_cfg["server_name"] = p["servername"]

    kind = p.get("type")
    if kind == "trojan":
        out.update(type="trojan", password=p.get("password", ""), tls=tls_cfg)
    elif kind in {"hysteria2", "hy2"}:
        out.update(type="hysteria2", password=p.get("password", ""), tls=tls_cfg)
        if p.get("up") or p.get("up_mbps"):
            out["up_mbps"] = int(str(p.get("up") or p.get("up_mbps")).rstrip(" Mbps"))
        if p.get("down") or p.get("down_mbps"):
            out["down_mbps"] = int(str(p.get("down") or p.get("down_mbps")).rstrip(" Mbps"))
        if p.get("obfs"):
            out["obfs"] = {"type": "salamander", "password": p["obfs"]}
    elif kind == "ss":
        out.update(
            type="shadowsocks",
            method=p.get("cipher", "aes-128-gcm"),
            password=p.get("password", ""),
        )
        plugin = p.get("plugin")
        if plugin:
            opts = p.get("plugin-opts") or {}
            if plugin == "obfs":
                out["plugin"] = "obfs"
                out["plugin_opts"] = f"obfs={opts.get('mode')};obfs-host={opts.get('host')}"
            elif plugin == "v2ray-plugin":
                out["plugin"] = "v2ray-plugin"
                out["plugin_opts"] = f"mode={opts.get('mode')};host={opts.get('host')}"
    elif kind == "vmess":
        out.update(
            type="vmess",
            uuid=p.get("uuid", ""),
            alter_id=int(p.get("alterId") or 0),
            security=p.get("cipher", "auto"),
            tls=tls_cfg if p.get("tls") else {"enabled": False},
        )
        _apply_transport(out, p)
    elif kind == "vless":
        out.update(
            type="vless",
            uuid=p.get("uuid", ""),
            tls=tls_cfg if p.get("tls") else {"enabled": False},
        )
        if p.get("flow"):
            out["flow"] = p["flow"]
        _apply_transport(out, p)
    else:
        return None

    out["tag"] = name
    return out


def _apply_transport(out: dict[str, Any], p: dict[str, Any]) -> None:
    net = p.get("network") or p.get("net")
    if net in (None, "tcp"):
        return
    opts = p.get(f"{net}-opts") or p.get(f"{net}-opt") or {}
    transport: dict[str, Any] = {"type": net}
    if net == "ws":
        transport["path"] = opts.get("path", "/")
        if opts.get("headers", {}).get("Host"):
            transport["headers"] = {"Host": opts["headers"]["Host"]}
        if opts.get("max-early-data"):
            transport["max_early_data"] = int(opts["max-early-data"])
    elif net == "grpc":
        transport["service_name"] = opts.get("grpc-service-name", "")
    out["transport"] = transport


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sub", help="Clash 订阅 YAML 文件")
    ap.add_argument("--pick", default="", help="按名称关键字挑选，逗号分隔；留空取全部")
    ap.add_argument("--limit", type=int, default=6, help="最多取几个节点")
    ap.add_argument("--listen", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7890)
    ap.add_argument("-o", "--out", default="/tmp/sing-box.json")
    args = ap.parse_args()

    data = yaml.safe_load(open(args.sub, encoding="utf-8"))
    proxies = data.get("proxies") or []
    keywords = [k.strip() for k in args.pick.split(",") if k.strip()]

    chosen: list[dict[str, Any]] = []
    if keywords:
        for kw in keywords:
            for p in proxies:
                if kw in str(p.get("name", "")):
                    chosen.append(p)
                    break
    else:
        chosen = proxies[: args.limit]
    chosen = chosen[: args.limit]

    outbounds: list[dict[str, Any]] = []
    tags: list[str] = []
    for i, p in enumerate(chosen):
        tag = f"n{i}"
        conv = convert_node(tag, p)
        if conv:
            outbounds.append(conv)
            tags.append(tag)
            print(f"已选 {tag}: {p.get('type')} {p.get('name')} -> {p.get('server')}:{p.get('port')}")

    if not outbounds:
        raise SystemExit("没有可用节点（订阅可能是「访问受限」占位内容，检查 UA）")

    outbounds.insert(
        0,
        {
            "type": "urltest",
            "tag": "proxy",
            "outbounds": tags,
            "url": "https://www.gstatic.com/generate_204",
            "interval": "5m",
            "tolerance": 100,
        },
    )
    outbounds.append({"type": "direct", "tag": "direct"})

    config = {
        "log": {"level": "info", "timestamp": True},
        "inbounds": [
            {"type": "mixed", "tag": "mixed-in", "listen": args.listen, "listen_port": args.port}
        ],
        "outbounds": outbounds,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"已生成 {args.out}（节点 {len(tags)} 个）")


if __name__ == "__main__":
    main()
