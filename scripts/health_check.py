#!/usr/bin/env python3
"""
CI 健康检查入口：逐源实测 → 写 health.json（shields 徽章数据 + 明细）

用法（GitHub Actions 每日定时跑）：
    python scripts/health_check.py            # 写 health.json，退出码 0
health.json 被提交回 main 分支，README 徽章通过
https://img.shields.io/endpoint?url=<raw>/health.json 实时显示在线数。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dailyhot.health import check_all, to_badge  # noqa: E402


def main() -> int:
    health = check_all()
    payload = {
        "badge": to_badge(health),
        "detail": health,
        "checked_at": __import__("time").strftime(
            "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()
        ),
    }
    out_path = os.path.join(os.path.dirname(__file__), "..", "health.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    badge = payload["badge"]
    print(f"{badge['message']} sources online (badge color: {badge['color']})")
    # 源挂了不阻断 CI：徽章变橙/红 + 下游步骤负责开 issue
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
