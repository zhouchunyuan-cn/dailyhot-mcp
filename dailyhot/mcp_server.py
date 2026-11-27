"""
MCP server（Model Context Protocol）

提供两个工具：
- sources：全部可用源
- get_hot_list(sources, limit)：抓取一个或多个源的热榜

设计要点（让模型用起来更顺）：
- 错误结构化返回而非抛异常：源名写错时返回 available_sources，
  模型下一步能自己选对源，而不是看到一段 traceback 文本
- 支持多源一次查询：模型问"知乎和 B 站什么最热"是 MCP 场景最常见用法，
  不该逼它调两次

传输：stdio（Claude Code / Cursor / Claude Desktop 直接配置）或
streamable-http（`dailyhot serve --http`，Glama 等目录站的云端部署需要）。
兼容 mcp SDK 1.x（FastMCP）与 2.x（MCPServer）。
依赖官方 mcp SDK（可选依赖：pip install dailyhot-mcp[mcp]）。
"""

import logging

logger = logging.getLogger(__name__)

MAX_LIMIT = 50


def _make_server():
    """
    兼容 mcp SDK 1.x 与 2.x：2.x 把 FastMCP 改名为 MCPServer，API 一致

    Returns:
        (server_instance, ServerClass)
    """
    try:
        from mcp.server.fastmcp import FastMCP as ServerClass  # mcp 1.x
    except ImportError:
        try:
            from mcp.server.mcpserver import MCPServer as ServerClass  # mcp 2.x
        except ImportError as e:
            raise ImportError("未安装官方 mcp SDK。请运行：pip install 'dailyhot-mcp[mcp]'") from e
    return ServerClass("dailyhot"), ServerClass


def build_server():
    """构造 MCP server 实例并注册工具"""
    mcp, _ = _make_server()
    from .sources import SOURCES, get_hot

    @mcp.tool()
    def sources() -> list[dict]:
        """列出全部可用的热榜源（name 与显示名）"""
        return [{"name": s.name, "title": s.title} for s in SOURCES.values()]

    @mcp.tool()
    def get_hot_list(sources: list[str], limit: int = 10) -> dict:
        """抓取一个或多个源的热榜。

        Args:
            sources: 源标识列表，如 ["zhihu", "bilibili"]；
                     可用源见 sources 工具（zhihu/baidu/toutiao/bilibili/
                     sspai/wallstreetcn/v2ex/hackernews/github）
            limit: 每个源最多返回条数（1-50，默认 10）

        Returns:
            {"results": {源名: [条目...]}, "errors": {源名: 错误信息}}
            ——源名写错时 errors 里带 available_sources，便于下一步自纠
        """
        limit = max(1, min(int(limit or 10), MAX_LIMIT))
        if not sources:
            return {
                "results": {},
                "errors": {"_": "sources 不能为空", "available_sources": sorted(SOURCES)},
            }

        results: dict[str, list[dict]] = {}
        errors: dict[str, object] = {}
        for name in sources:
            spec = SOURCES.get(name)
            if spec is None:
                errors[name] = f"未知源 {name!r}"
                continue
            try:
                results[name] = [item.to_dict() for item in get_hot(name, limit=limit)]
            except Exception as e:  # 网络失败：结构化返回，其他源不受影响
                errors[name] = f"抓取失败: {e}"
        if errors:
            unknown = [n for n in errors if n not in SOURCES]
            if unknown:
                errors["available_sources"] = sorted(SOURCES)
        return {"results": results, "errors": errors}

    return mcp


def main(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    启动 server

    Args:
        transport: "stdio"（默认，Claude Code/Cursor 配置用）或
                   "http"（streamable-http，Glama 云端部署/远程客户端用）
        host/port: http 模式的监听地址
    """
    mcp = build_server()
    if transport == "http":
        # 1.x 与 2.x 均支持 streamable-http；settings 参数名一致
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
