"""
热榜源注册表：每个源一个适配器（端点 + 解析器）

设计要点：
- 抓取与解析分离：解析器是纯函数（输入已解析的 JSON/HTML 文本），
  测试用录制的 fixtures 离线跑，不碰网络
- 新增源 = 写一个 parse 函数 + 注册一项（欢迎 PR 补源）
- 解析器对字段缺失保持宽容：单个条目缺字段跳过，不让一条坏数据毁掉整榜

v1 覆盖（全部经真实端点验证）：
知乎热榜 / 百度热搜 / 今日头条 / B站热门 / 少数派 / 华尔街见闻快讯 /
V2EX 热帖 / Hacker News / GitHub Trending

已知反爬、暂缓接入：微博（403）、抖音（空响应）——接入方案见 README 路线图。
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .fetcher import fetch_json, fetch_text
from .models import HotItem

MAX_LIMIT = 50


# ------------------------------------------------------------------
# 解析器（纯函数，可离线测试）
# ------------------------------------------------------------------


def _items(
    raw_items: list[Any],
    *,
    title: str,
    url: Callable[[Any], str] | None = None,
    score: Callable[[Any], str] | None = None,
) -> list[HotItem]:
    """把原始条目列表统一转成 HotItem（跳过缺标题的坏条目）"""
    result: list[HotItem] = []
    for item in raw_items:
        text = title(item)
        if not text:
            continue
        result.append(
            HotItem(
                rank=len(result) + 1,
                title=text.strip(),
                url=(url(item) or "").strip() if url else "",
                score=score(item) if score else None,
            )
        )
    return result


def parse_zhihu(d: dict) -> list[HotItem]:
    """知乎热榜：api.zhihu.com/topstory/hot-list"""

    def url_of(item: dict) -> str:
        target = item.get("target") or {}
        qid = target.get("id")
        if qid:
            return f"https://www.zhihu.com/question/{qid}"
        return (target.get("url") or "").replace("api.zhihu.com", "www.zhihu.com")

    return _items(
        d.get("data") or [],
        title=lambda x: (x.get("target") or {}).get("title"),
        url=url_of,
        score=lambda x: (x.get("detail_text") or "").replace("热度", "").strip() or None,
    )


def parse_baidu(d: dict) -> list[HotItem]:
    """百度热搜：top.baidu.com 实时板（content 为双层嵌套：card.content[].content[]）"""
    entries: list[dict] = []
    for card in (d.get("data") or {}).get("cards") or []:
        for wrapper in card.get("content") or []:
            entries.extend(wrapper.get("content") or [])
    return _items(
        entries,
        title=lambda x: x.get("word"),
        url=lambda x: x.get("url"),
        score=lambda x: str(x.get("hotScore")) if x.get("hotScore") else None,
    )


def parse_toutiao(d: dict) -> list[HotItem]:
    """今日头条热榜：toutiao.com/hot-event/hot-board"""
    entries = list(d.get("fixed_top_data") or []) + list(d.get("data") or [])
    return _items(
        entries,
        title=lambda x: x.get("Title"),
        url=lambda x: x.get("Url"),
        score=lambda x: f"{x.get('HotValue')} 热度" if x.get("HotValue") else None,
    )


def parse_bilibili(d: dict) -> list[HotItem]:
    """B站热门（全站排行榜）：api.bilibili.com ranking/v2"""
    return _items(
        (d.get("data") or {}).get("list") or [],
        title=lambda x: x.get("title"),
        url=lambda x: f"https://www.bilibili.com/video/av{x['aid']}" if x.get("aid") else "",
        score=lambda x: f"{x.get('stat', {}).get('view', 0)} 播放" if x.get("stat") else None,
    )


def parse_sspai(d: dict) -> list[HotItem]:
    """少数派最新文章：sspai.com"""
    return _items(
        d.get("data") or [],
        title=lambda x: x.get("title"),
        url=lambda x: f"https://sspai.com/post/{x['id']}" if x.get("id") else "",
        score=lambda x: f"{x.get('like_count', 0)} 赞" if x.get("like_count") else None,
    )


def parse_wallstreetcn(d: dict) -> list[HotItem]:
    """华尔街见闻实时快讯：api-one-wscn.awtmt.com"""
    return _items(
        (d.get("data") or {}).get("items") or [],
        title=lambda x: x.get("title") or x.get("content_text"),
        url=lambda x: x.get("uri") or "",
    )


def parse_v2ex(items: list) -> list[HotItem]:
    """V2EX 热帖（官方 API）"""
    return _items(
        items,
        title=lambda x: x.get("title"),
        url=lambda x: x.get("url"),
        score=lambda x: f"{x.get('replies', 0)} 回复" if x.get("replies") else None,
    )


def parse_hackernews(d: dict) -> list[HotItem]:
    """Hacker News 首页（Algolia 搜索 API，单次请求拿全量字段）"""
    return _items(
        d.get("hits") or [],
        title=lambda x: x.get("title") or x.get("story_title"),
        url=lambda x: x.get("url") or f"https://news.ycombinator.com/item?id={x.get('objectID')}",
        score=lambda x: f"{x.get('points', 0)} 分" if x.get("points") else None,
    )


_REPO_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="(/[^"]+)"', re.DOTALL)
_DESC_RE = re.compile(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_github_trending(html: str) -> list[HotItem]:
    """GitHub Trending（HTML 页解析：h2 仓库名 + p 简介）"""
    repos = _REPO_RE.findall(html)
    descs = _DESC_RE.findall(html)
    items: list[HotItem] = []
    for i, path in enumerate(repos):
        desc = _TAG_RE.sub("", descs[i]).strip() if i < len(descs) else ""
        items.append(
            HotItem(
                rank=i + 1,
                title=path.lstrip("/") + (f" — {desc[:80]}" if desc else ""),
                url=f"https://github.com{path}",
            )
        )
    return items


# ------------------------------------------------------------------
# 源注册表
# ------------------------------------------------------------------


@dataclass
class SourceSpec:
    """一个热榜源的声明：抓取方式 + 解析方式"""

    name: str  # 源标识（CLI/MCP 参数用，如 "zhihu"）
    title: str  # 显示名（如 "知乎热榜"）
    endpoint: str  # 数据端点
    is_html: bool = False  # True: fetch_text；False: fetch_json
    parse: Callable[[Any], list[HotItem]] = None  # type: ignore[assignment]


SOURCES: dict[str, SourceSpec] = {
    spec.name: spec
    for spec in [
        SourceSpec(
            "zhihu",
            "知乎热榜",
            "https://api.zhihu.com/topstory/hot-list?limit=20",
            parse=parse_zhihu,
        ),
        SourceSpec(
            "baidu",
            "百度热搜",
            "https://top.baidu.com/api/board?platform=wise&tab=realtime",
            parse=parse_baidu,
        ),
        SourceSpec(
            "toutiao",
            "今日头条",
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            parse=parse_toutiao,
        ),
        SourceSpec(
            "bilibili",
            "B站热门",
            "https://api.bilibili.com/x/web-interface/ranking/v2",
            parse=parse_bilibili,
        ),
        SourceSpec(
            "sspai",
            "少数派",
            "https://sspai.com/api/v1/article/index/page/get?free=1&limit=20",
            parse=parse_sspai,
        ),
        SourceSpec(
            "wallstreetcn",
            "华尔街见闻",
            "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=20",
            parse=parse_wallstreetcn,
        ),
        SourceSpec(
            "v2ex", "V2EX 热帖", "https://www.v2ex.com/api/topics/hot.json", parse=parse_v2ex
        ),
        SourceSpec(
            "hackernews",
            "Hacker News",
            "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30",
            parse=parse_hackernews,
        ),
        SourceSpec(
            "github",
            "GitHub Trending",
            "https://github.com/trending",
            is_html=True,
            parse=parse_github_trending,
        ),
    ]
}


def list_sources() -> list[dict[str, str]]:
    """全部可用源（name + 显示名）"""
    return [{"name": s.name, "title": s.title} for s in SOURCES.values()]


def get_hot(name: str, limit: int = 10) -> list[HotItem]:
    """
    抓取指定源的热榜

    Args:
        name: 源标识（见 list_sources）
        limit: 最多返回条数（上限 50）

    Raises:
        KeyError: 源不存在
        RuntimeError: 抓取或解析失败
    """
    spec = SOURCES.get(name)
    if spec is None:
        raise KeyError(f"未知源 {name!r}，可用: {sorted(SOURCES)}")
    limit = max(1, min(limit, MAX_LIMIT))
    raw = fetch_text(spec.endpoint) if spec.is_html else fetch_json(spec.endpoint)
    items = spec.parse(raw)
    return items[:limit]
