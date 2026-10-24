"""
CLI 与健康检查测试（离线：monkeypatch 网络层）
"""

import json

import pytest

from dailyhot import sources as S
from dailyhot.cli import main as cli_main
from dailyhot.health import check_all, format_report, summary, to_badge
from dailyhot.models import HotItem


def _fake_items(n=3):
    return [HotItem(rank=i + 1, title=f"条目{i}", url=f"https://x/{i}") for i in range(n)]


@pytest.fixture
def offline_sources(monkeypatch):
    """patch dailyhot.health 命名空间的 get_hot，健康检查全部离线可用"""

    import dailyhot.health as H

    monkeypatch.setattr(H, "get_hot", lambda name, limit: _fake_items(3))


class TestCLI:
    """CLI 测试 patch dailyhot.cli 命名空间里的 get_hot 引用（避免真实联网）"""

    def test_list(self, capsys):
        cli_main(["list"])
        out = capsys.readouterr().out
        assert "zhihu" in out and "知乎热榜" in out
        assert "github" in out

    def test_get_json_output(self, monkeypatch, capsys):
        import dailyhot.cli as cli

        monkeypatch.setattr(cli, "get_hot", lambda name, limit: _fake_items(2))
        cli_main(["get", "zhihu", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2 and data[0]["rank"] == 1

    def test_get_human_output(self, monkeypatch, capsys):
        import dailyhot.cli as cli

        monkeypatch.setattr(cli, "get_hot", lambda name, limit: _fake_items(2))
        cli_main(["get", "zhihu", "-n", "2"])
        out = capsys.readouterr().out
        assert "知乎热榜" in out and "条目0" in out and "https://x/0" in out

    def test_get_unknown_source_exits_2(self, monkeypatch, capsys):
        import dailyhot.cli as cli

        def raise_key(name, limit):
            raise KeyError("未知源 'nope'，可用: ['zhihu']")

        monkeypatch.setattr(cli, "get_hot", raise_key)
        with pytest.raises(SystemExit) as ei:
            cli_main(["get", "nope"])
        assert ei.value.code == 2
        assert "未知源" in capsys.readouterr().err

    def test_no_subcommand_shows_help(self, capsys):
        with pytest.raises(SystemExit) as ei:
            cli_main([])
        assert ei.value.code == 2

    def test_get_network_error_exits_1(self, monkeypatch, capsys):
        import dailyhot.cli as cli

        def raise_net(name, limit):
            raise RuntimeError("HTTP 403")

        monkeypatch.setattr(cli, "get_hot", raise_net)
        with pytest.raises(SystemExit) as ei:
            cli_main(["get", "zhihu"])
        assert ei.value.code == 1
        assert "403" in capsys.readouterr().err


class TestHealth:
    def test_check_all_offline(self, offline_sources):
        health = check_all()
        assert len(health) == 9
        assert all(r["ok"] for r in health.values())

    def test_summary_and_badge(self, monkeypatch):
        health = {
            "zhihu": {"ok": True, "items": 3},
            "github": {"ok": False, "error": "HTTP 403"},
        }
        s = summary(health)
        assert s["total"] == 2 and s["online"] == 1
        assert s["down"] == {"github": "HTTP 403"}
        # 全在线 → 绿；9 成在线 → 橙；过半挂 → 红
        assert to_badge({"a": {"ok": True}, "b": {"ok": True}})["color"] == "brightgreen"
        mixed = {f"s{i}": {"ok": i < 7} for i in range(10)}
        assert to_badge(mixed)["color"] == "orange"
        bad = {f"s{i}": {"ok": i < 3} for i in range(10)}
        assert to_badge(bad)["color"] == "red"
        badge = to_badge(health)
        assert badge["message"] == "1/2"

    def test_format_report(self, monkeypatch):
        report = format_report(
            {
                "zhihu": {"ok": True, "items": 3, "elapsed_ms": 120},
                "github": {"ok": False, "error": "HTTP 403", "elapsed_ms": 50},
            }
        )
        assert "✓ zhihu" in report and "✗ github" in report and "1/2" in report

    def test_failure_recorded(self, monkeypatch):
        def boom(url, timeout=10.0, headers=None):
            raise RuntimeError("HTTP 403: denied")

        monkeypatch.setattr(S, "fetch_json", boom)
        monkeypatch.setattr(S, "fetch_text", boom)
        health = check_all()
        assert all(not r["ok"] for r in health.values())
        assert "403" in health["zhihu"]["error"]


class TestMCPServer:
    def test_build_server_registers_tools(self):
        import asyncio

        mcp = __import__("dailyhot.mcp_server", fromlist=["build_server"]).build_server()
        tools = asyncio.run(mcp.list_tools())  # FastMCP 的 list_tools 是协程
        names = {t.name for t in tools}
        assert {"sources", "get_hot_list"} <= names

    def test_missing_sdk_hint(self, monkeypatch):
        import sys as _sys

        # 子模块已缓存时 from import 不会触碰父模块，必须一并模拟为未安装
        monkeypatch.setitem(_sys.modules, "mcp", None)
        monkeypatch.setitem(_sys.modules, "mcp.server", None)
        monkeypatch.setitem(_sys.modules, "mcp.server.fastmcp", None)
        with pytest.raises(ImportError, match="pip install"):
            __import__("dailyhot.mcp_server", fromlist=["build_server"]).build_server()
