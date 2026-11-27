#!/usr/bin/env python3
"""
CI 健康检查入口：逐源实测 → 写 health.json（shields 徽章数据 + 明细）

用法（GitHub Actions 每日定时跑）：
    python scripts/health_check.py [--out PATH]

退出码：
    0  全部源在线
    1  有源下线（health.json 仍会写好，徽章变橙/红；下游步骤据此开 issue）

health.json 每次运行都会更新 checked_at 并被提交回 main——
徽章据此判断时效，CI 停摆时会显示 "stale" 而不是永远停在最后一次的绿色。
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dailyhot.health import check_all, summary, to_badge  # noqa: E402

DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "health.json")


def run(out_path: str = DEFAULT_OUT) -> int:
    """执行检查并落盘；返回退出码（0 全在线 / 1 有下线）"""
    health = check_all()
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {
        "badge": to_badge(health, checked_at=checked_at),
        "detail": health,
        "checked_at": checked_at,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = summary(health)
    print(
        f"{payload['badge']['message']} sources online (badge color: {payload['badge']['color']})"
    )
    if s["down"]:
        print("下线源：")
        for name, info in s["down"].items():
            print(f"  - {name} [{info['kind']}]: {info['error'][:100]}")
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="源健康检查（CI 入口）")
    parser.add_argument("--out", default=DEFAULT_OUT, help="health.json 输出路径")
    args = parser.parse_args(argv)
    return run(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
