"""
源健康检查：逐源实测可用性，产出报告与 shields.io 徽章数据

这是本项目的核心卖点：README 徽章实时显示"X/9 源在线"，
CI 每天实测并提交 health.json——别的热榜工具坏没坏要用户自己踩坑，
这里把可用性做成可见信号。

可信性设计（徽章不能说谎）：
- 瞬时失败不判死：网络超时/5xx 重试 2 次仍失败才算下线，降低误报
- 区分失败类型：transient（网络/超时）vs structural（解析为空/字段变了），
  维护者一眼知道是对方挂了还是自己该改解析器
- 陈旧检测：health.json 超过 STALE_AFTER 未更新，徽章显示 "stale" 灰色——
  CI 停摆时徽章不会永远停留在最后一次的绿色
"""

import json
import time
from datetime import datetime, timezone
from typing import Any

from .sources import SOURCES, get_hot

# 每源探测返回的条目数（够验证解析成功即可）
PROBE_LIMIT = 3
# 瞬时失败的重试次数（不含首次）
RETRIES = 2
# 重试间隔（秒）
RETRY_DELAY = 1.5
# health.json 超过此时长未更新，徽章标记为 stale
STALE_AFTER_SECONDS = 48 * 3600

# 徽章颜色阈值
ORANGE_RATIO = 0.7


def _classify_error(error: Exception) -> str:
    """把异常归类：网络/超时类为 transient，其余（解析为空、结构变化）为 structural"""
    msg = str(error).lower()
    transient_markers = (
        "timed out",
        "timeout",
        "http 5",
        "http 429",
        "请求失败",
        "connection",
        "reset",
    )
    return "transient" if any(m in msg for m in transient_markers) else "structural"


def check_source(name: str) -> dict[str, Any]:
    """
    实测单个源：能否抓到至少 1 条

    瞬时类失败会重试 RETRIES 次再判死（避免 GitHub Trending 这类慢源被偶发超时误杀）；
    结果带 kind 字段区分 transient / structural。
    """
    started = time.monotonic()
    last_error: Exception | None = None
    attempts = 0
    for attempt in range(RETRIES + 1):
        attempts = attempt + 1
        try:
            items = get_hot(name, limit=PROBE_LIMIT)
            if not items:
                raise RuntimeError("解析结果为空")
            return {
                "ok": True,
                "items": len(items),
                "attempts": attempts,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
        except Exception as e:  # noqa: PERF203 -- 需要按轮次记录
            last_error = e
            if _classify_error(e) == "structural" or attempt == RETRIES:
                break
            time.sleep(RETRY_DELAY)
    assert last_error is not None
    return {
        "ok": False,
        "error": str(last_error)[:200],
        "kind": _classify_error(last_error),
        "attempts": attempts,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }


def check_all() -> dict[str, dict[str, Any]]:
    """逐源实测全部源（串行：快、且不触发现有速率限制）"""
    return {name: check_source(name) for name in SOURCES}


def summary(health: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """汇总：在线数/总数/下线明细（含失败类型）"""
    ok = [n for n, r in health.items() if r["ok"]]
    down = {
        n: {"kind": r.get("kind", "unknown"), "error": r.get("error", "")}
        for n, r in health.items()
        if not r["ok"]
    }
    return {"total": len(health), "online": len(ok), "down": down}


def to_badge(health: dict[str, dict[str, Any]], checked_at: str | None = None) -> dict[str, Any]:
    """
    产出 shields.io endpoint 徽章 JSON

    用法：README 里
    ![sources](https://img.shields.io/endpoint?url=<raw 链接>/health.json)

    checked_at（ISO8601）超过 STALE_AFTER_SECONDS 时输出 "stale"：
    防止 CI 停摆后徽章永远显示最后一次的绿色。
    """
    total = len(health)
    online = sum(1 for r in health.values() if r["ok"])
    if _is_stale(checked_at):
        color, message = "lightgrey", "stale"
    elif online == total:
        color, message = "brightgreen", f"{online}/{total}"
    elif online >= total * ORANGE_RATIO:
        color, message = "orange", f"{online}/{total}"
    else:
        color, message = "red", f"{online}/{total}"
    return {
        "schemaVersion": 1,
        "label": "sources online",
        "message": message,
        "color": color,
    }


def _is_stale(checked_at: str | None) -> bool:
    """health.json 的检查时间是否已过期（无法解析视为过期）"""
    if not checked_at:
        return True
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - checked).total_seconds() > STALE_AFTER_SECONDS


def format_report(health: dict[str, dict[str, Any]]) -> str:
    """人类可读的健康报告（CLI / CI 日志用）"""
    lines = []
    for name, r in health.items():
        mark = "✓" if r["ok"] else "✗"
        if r["ok"]:
            detail = f"{r['items']} 条 / {r['elapsed_ms']}ms"
            if r.get("attempts", 1) > 1:
                detail += f"（重试 {r['attempts'] - 1} 次后成功）"
        else:
            kind = r.get("kind", "?")
            retries = r.get("attempts", 1) - 1
            detail = f"[{kind}] {r.get('error', '')[:70]}" + (
                f"（已重试 {retries} 次）" if retries else ""
            )
        title = SOURCES[name].title
        lines.append(f"  {mark} {name:14s} {title:12s} {detail}")
    s = summary(health)
    lines.append(f"\n在线 {s['online']}/{s['total']}")
    return "\n".join(lines)


def load_health_file(path: str) -> dict[str, Any] | None:
    """读取已落盘的 health.json（CI 判断是否需要提交/开 issue 时用）"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
