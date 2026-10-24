"""
MCP server（Model Context Protocol，官方 SDK）

提供两个工具：
- list_sources：全部可用源
- get_hot_list(source, limit)：抓取指定源热榜

传输：stdio（Claude Code / Cursor / Claude Desktop 直接配置）。
依赖官方 mcp SDK（可选依赖：pip install dailyhot-mcp[mcp]）。
"""

import logging

logger = logging.getLogger(__name__)


def build_server():
    """构造 FastMCP 实例（延迟导入 mcp SDK）"""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            "未安装官方 mcp SDK。请运行：pip install 'mcp>=1.20'"
            "（或 pip install 'dailyhot-mcp[mcp]'）"
        ) from e

    from .sources import get_hot, list_sources

    mcp = FastMCP("dailyhot")

    @mcp.tool()
    def sources() -> list[dict]:
        """列出全部可用的热榜源（name 与显示名）"""
        return list_sources()

    @mcp.tool()
    def get_hot_list(source: str, limit: int = 10) -> list[dict]:
        """抓取指定源的热榜。

        Args:
            source: 源标识，如 zhihu / baidu / bilibili / github / hackernews
            limit: 最多返回条数（1-50，默认 10）
        """
        items = get_hot(source, limit=limit)
        return [item.to_dict() for item in items]

    return mcp


def main() -> None:
    """stdio 入口：dailyhot serve"""
    build_server().run()
