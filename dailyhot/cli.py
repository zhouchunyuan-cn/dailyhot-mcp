"""
CLI：dailyhot

  dailyhot list                 # 列出全部源
  dailyhot get zhihu -n 10      # 抓取热榜（--json 输出 JSON）
  dailyhot health               # 逐源实测可用性（--json 输出 JSON）
  dailyhot serve                # 启动 MCP server（stdio，需 mcp 可选依赖）
"""

import argparse
import json
import sys

from .sources import SOURCES, get_hot, list_sources


def _print_items(items) -> None:
    for item in items:
        score = f"  [{item.score}]" if item.score else ""
        print(f"{item.rank:>3}. {item.title}{score}")
        if item.url:
            print(f"      {item.url}")


def cmd_list(args) -> None:
    for s in list_sources():
        print(f"  {s['name']:14s} {s['title']}")


def cmd_get(args) -> None:
    try:
        items = get_hot(args.source, limit=args.limit)
    except KeyError as e:
        print(f"错误：{e.args[0]}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # 网络错误：退出码 1，信息走 stderr
        print(f"错误：源 '{args.source}' 抓取失败：{e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2))
    else:
        print(f"【{SOURCES[args.source].title}】")
        _print_items(items)


def cmd_health(args) -> None:
    from .health import check_all, format_report, to_badge

    health = check_all()
    if args.json:
        print(
            json.dumps({"badge": to_badge(health), "detail": health}, ensure_ascii=False, indent=2)
        )
    else:
        print(format_report(health))


def cmd_serve(args) -> None:
    from .mcp_server import main as serve_main

    serve_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dailyhot",
        description="中文热榜聚合 —— 库 / CLI / MCP server 三层接入",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出全部可用源").set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="抓取指定源热榜")
    p_get.add_argument("source", help="源标识（见 dailyhot list）")
    p_get.add_argument("-n", "--limit", type=int, default=10, help="最多返回条数（默认 10）")
    p_get.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_get.set_defaults(func=cmd_get)

    p_health = sub.add_parser("health", help="逐源实测可用性")
    p_health.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_health.set_defaults(func=cmd_health)

    sub.add_parser("serve", help="启动 MCP server（stdio）").set_defaults(func=cmd_serve)
    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()
