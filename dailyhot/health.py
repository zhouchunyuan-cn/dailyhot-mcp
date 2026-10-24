"""
源健康检查：逐源实测可用性，产出报告与 shields.io 徽章数据

这是本项目的核心卖点：README 徽章实时显示"X/9 源在线"，
CI 每天实测并提交 health.json——别的热榜工具坏没坏要用户自己踩坑，
这里把可用性做成可见信号。
"""

import time
from typing import Any

from .sources import SOURCES, get_hot

# 每源探测返回的条目数（够验证解析成功即可）
PROBE_LIMIT = 3


def check_source(name: str) -> dict[str, Any]:
    """实测单个源：能否抓到至少 1 条"""
    started = time.monotonic()
    try:
        items = get_hot(name, limit=PROBE_LIMIT)
        if not items:
            raise RuntimeError("解析结果为空")
        return {
            "ok": True,
            "items": len(items),
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:200],
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }


def check_all() -> dict[str, dict[str, Any]]:
    """逐源实测全部源（串行：快、且不触发现有速率限制）"""
    return {name: check_source(name) for name in SOURCES}


def summary(health: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """汇总：在线数/总数/明细"""
    ok = [n for n, r in health.items() if r["ok"]]
    down = {n: r.get("error", "") for n, r in health.items() if not r["ok"]}
    return {"total": len(health), "online": len(ok), "down": down}


def to_badge(health: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    产出 shields.io endpoint 徽章 JSON

    用法：README 里
    ![sources](https://img.shields.io/endpoint?url=<raw 链接>/health.json)
    """
    total = len(health)
    online = sum(1 for r in health.values() if r["ok"])
    if online == total:
        color = "brightgreen"
    elif online >= total * 0.7:
        color = "orange"
    else:
        color = "red"
    return {
        "schemaVersion": 1,
        "label": "sources online",
        "message": f"{online}/{total}",
        "color": color,
    }


def format_report(health: dict[str, dict[str, Any]]) -> str:
    """人类可读的健康报告（CLI / CI 日志用）"""
    lines = []
    for name, r in health.items():
        mark = "✓" if r["ok"] else "✗"
        detail = f"{r['items']} 条 / {r['elapsed_ms']}ms" if r["ok"] else r.get("error", "")[:80]
        title = SOURCES[name].title
        lines.append(f"  {mark} {name:14s} {title:12s} {detail}")
    s = summary(health)
    lines.append(f"\n在线 {s['online']}/{s['total']}")
    return "\n".join(lines)
