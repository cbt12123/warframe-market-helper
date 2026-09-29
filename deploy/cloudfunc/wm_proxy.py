"""Warframe Market API 中转（部署在腾讯云 SCF / 阿里云 FC 的 Web 函数）。

用途：当服务器没有海外出口时，用国内云函数的公网出网做中转。

协议：
    GET <函数URL>/v2/orders/item/volt_prime_set/top
    Header: X-WM-Token: <你的随机 token>
            X-WM-Platform: pc            （可选，默认 pc）
            X-WM-Language: zh-hans       （可选，默认 zh-hans）

安全约束（写死，避免被当成开放代理）：
  - 仅允许 GET
  - 目标固定 api.warframe.market，且路径必须以 /v2/ 开头
  - 必须带正确的 X-WM-TOKEN
  - 超时 20s，最多重试 1 次

部署：
  - 腾讯云 SCF：创建「Web 函数」，运行环境 Python 3.10，入口 main_handler
  - 阿里云 FC：创建「Web 函数」，运行环境 Python 3.10，入口 handler
"""

from __future__ import annotations

import gzip
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus

UPSTREAM = "https://api.warframe.market"
TIMEOUT = 20
TOKEN = os.environ.get("WM_TOKEN", "")  # 在云函数环境变量里配置

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "X-WM-Token,X-WM-Platform,X-WM-Language",
}


def _fetch(path: str, platform: str, language: str, query: str) -> tuple[int, bytes, str]:
    url = f"{UPSTREAM}{path}"
    if query:
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "wm-helper/0.1.0 (+cloud-function-relay)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Platform": platform,
            "Language": language,
        },
    )
    last: Exception | None = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
                        raw = fh.read()
                return resp.status, raw, resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as exc:  # 上游 4xx/5xx 原样透出
            body = exc.read()
            return exc.code, body, "application/json"
        except Exception as exc:  # noqa: BLE001
            last = exc
    return 502, json.dumps({"error": f"upstream failed: {last}"}).encode(), "application/json"


def _handle(headers: dict[str, str], path: str, query: str) -> tuple[int, bytes, dict[str, str]]:
    if TOKEN and headers.get("x-wm-token") != TOKEN:
        return 403, b'{"error":"forbidden"}', {"Content-Type": "application/json", **CORS}
    if not path.startswith("/v2/"):
        return 400, b'{"error":"bad path"}', {"Content-Type": "application/json", **CORS}
    platform = headers.get("x-wm-platform", "pc")
    language = headers.get("x-wm-language", "zh-hans")
    status, body, ctype = _fetch(path, platform, language, query)
    return status, body, {"Content-Type": ctype, **CORS}


def _parse_path(raw_path: str) -> tuple[str, str]:
    """从 '/v2/orders/item/x/top?a=1' 里拆出 ('/v2/orders/item/x/top', 'a=1')。"""
    parsed = urllib.parse.urlparse(raw_path)
    path = parsed.path
    if path.startswith("/v2"):
        path = "/v2" + path[3:]
    return path, parsed.query


# ---------- 阿里云 FC（WSGI） ----------
def handler(environ, start_response):
    if environ.get("REQUEST_METHOD", "GET").upper() != "GET":
        start_response("405 Method Not Allowed", [("Content-Type", "application/json")])
        return [b'{"error":"GET only"}']
    # WSGI 里 X-WM-Token 对应 environ['HTTP_X_WM_TOKEN'] -> 转成 x-wm-token
    headers = {
        k[5:].lower().replace("_", "-"): v
        for k, v in environ.items()
        if k.startswith("HTTP_")
    }
    path, query = _parse_path(environ.get("PATH_INFO", "") or environ.get("RAW_URI", ""))
    status, body, hdrs = _handle(headers, path, query)
    reason = HTTPStatus(status).phrase if status in HTTPStatus.__members__.values() else "OK"
    start_response(f"{status} {reason}", list(hdrs.items()))
    return [body]


# ---------- 腾讯云 SCF（HTTP 触发） ----------
def main_handler(event: dict, context=None):
    if (event.get("httpMethod") or event.get("requestContext", {}).get("httpMethod", "GET")).upper() != "GET":
        return {"statusCode": 405, "headers": {"Content-Type": "application/json"}, "body": '{"error":"GET only"}'}
    headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    path, query = _parse_path(event.get("path", "") or (event.get("requestContext") or {}).get("path", ""))
    query = query or urllib.parse.urlencode(event.get("queryString") or {})
    status, body, hdrs = _handle(headers, path, query)
    return {
        "statusCode": status,
        "headers": hdrs,
        "isBase64Encoded": False,
        "body": body.decode("utf-8", "replace"),
    }
