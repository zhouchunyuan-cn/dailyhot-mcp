"""
dailyhot —— 中文热榜聚合：库 / CLI / MCP server 三层接入

核心卖点：源可用性透明——CI 每天实测全部源，README 徽章实时显示在线数。

用法：
    from dailyhot.sources import get_hot, list_sources

    get_hot("zhihu", limit=10)      # -> [HotItem(rank, title, url, score), ...]

CLI：
    dailyhot list / get zhihu -n 10 / health / serve
"""

from .models import HotItem
from .sources import SOURCES, get_hot, list_sources

__version__ = "0.1.0"

__all__ = ["HotItem", "SOURCES", "get_hot", "list_sources", "__version__"]
