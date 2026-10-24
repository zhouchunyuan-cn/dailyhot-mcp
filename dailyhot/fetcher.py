"""
HTTP 抓取层：纯标准库 urllib，零依赖

- 统一浏览器 UA 与超时（很多公开热榜端点校验 UA）
- get_json / get_text 两个入口，异常信息带状态码与响应片段，
  便于健康检查报告"为什么挂了"
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 10.0


def fetch_text(url: str, timeout: float = DEFAULT_TIMEOUT, headers: dict | None = None) -> str:
    """GET 并返回响应文本；非 2xx 抛 RuntimeError（带状态码与响应片段）"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": DEFAULT_UA, "Accept": "*/*", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        raise RuntimeError(f"HTTP {e.code}: {body or e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"请求失败: {e}") from e


def fetch_json(url: str, timeout: float = DEFAULT_TIMEOUT, headers: dict | None = None) -> Any:
    """GET 并解析 JSON；解析失败抛 RuntimeError（响应不是合法 JSON）"""
    text = fetch_text(url, timeout=timeout, headers=headers)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"响应不是合法 JSON（前 200 字符: {text[:200]!r}）") from e
