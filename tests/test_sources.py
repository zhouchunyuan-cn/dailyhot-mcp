"""
解析器测试：全部离线，基于录制 fixtures（不碰网络）

验证每个源：能解析出条目、标题/链接非空、名次连续、截断正确。
fixtures 过期导致字段变化时，这些测试会第一时间红——这正是"源监控"的另一半。
"""

import json
import os

import pytest

from dailyhot.models import HotItem
from dailyhot.sources import MAX_LIMIT, SOURCES, list_sources

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str):
    if name == "github":
        with open(os.path.join(FIXTURE_DIR, "github_trending.html"), encoding="utf-8") as f:
            return f.read()
    with open(os.path.join(FIXTURE_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


class TestRegistry:
    def test_nine_sources_registered(self):
        assert len(SOURCES) == 9

    def test_list_sources_shape(self):
        entries = list_sources()
        assert {"name", "title"} <= set(entries[0])
        assert {e["name"] for e in entries} == set(SOURCES)


class TestParsers:
    @pytest.mark.parametrize("name", sorted(k for k in SOURCES if k != "github"))
    def test_json_source_parses(self, name):
        items = SOURCES[name].parse(_load(name))
        assert len(items) >= 3, f"{name} 解析条目过少"
        for item in items:
            assert isinstance(item, HotItem)
            assert item.title.strip()
            assert item.rank >= 1

    def test_github_parses(self):
        items = SOURCES["github"].parse(_load("github"))
        assert len(items) >= 5
        # 仓库路径形如 owner/repo，URL 指向 github.com
        assert items[0].url.startswith("https://github.com/")
        assert "/" in items[0].title.split(" — ")[0]

    @pytest.mark.parametrize("name", sorted(SOURCES))
    def test_ranks_sequential(self, name):
        items = SOURCES[name].parse(_load(name))
        assert [i.rank for i in items] == list(range(1, len(items) + 1))

    def test_bad_items_skipped_not_fatal(self):
        """坏条目（无标题）跳过，不毁掉整榜"""
        items = SOURCES["v2ex"].parse([{"url": "https://x"}, {"title": "正常", "url": "https://y"}])
        assert len(items) == 1 and items[0].title == "正常"

    def test_zhihu_url_rewritten_to_www(self):
        items = SOURCES["zhihu"].parse(_load("zhihu"))
        assert all("api.zhihu.com" not in i.url for i in items)
        assert items[0].url.startswith("https://www.zhihu.com/question/")


class TestGetHot:
    def test_unknown_source_raises(self):
        from dailyhot.sources import get_hot

        with pytest.raises(KeyError, match="未知源"):
            get_hot("nope")

    def test_limit_clamped(self, monkeypatch):
        from dailyhot import sources as S

        recorded = {}

        def fake_fetch(url, timeout=10.0, headers=None):
            recorded["url"] = url
            return _load("v2ex")

        monkeypatch.setattr(S, "fetch_json", fake_fetch)
        monkeypatch.setattr(S, "fetch_text", fake_fetch)
        # 请求 999 条：内部钳制到 MAX_LIMIT；v2ex fixture 只有 9 条 → 返回 9
        items = S.get_hot("v2ex", limit=999)
        assert len(items) == 9
        assert len(items) <= MAX_LIMIT
        assert recorded["url"] == SOURCES["v2ex"].endpoint

    def test_html_source_uses_text_fetcher(self, monkeypatch):
        from dailyhot import sources as S

        calls = {}

        def fake_fetch_text(url, timeout=10.0, headers=None):
            calls["text"] = url
            return _load("github")

        monkeypatch.setattr(S, "fetch_text", fake_fetch_text)
        items = S.get_hot("github", limit=5)
        assert calls["text"] == SOURCES["github"].endpoint
        assert len(items) == 5
