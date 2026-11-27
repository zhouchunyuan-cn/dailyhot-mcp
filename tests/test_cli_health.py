"""
CLI 与健康检查测试（离线：monkeypatch 网络层）
"""

import json

import pytest

import dailyhot.health as H_module
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

    def test_version_flag(self, capsys):
        from dailyhot import __version__

        with pytest.raises(SystemExit) as ei:
            cli_main(["--version"])
        assert ei.value.code == 0
        assert __version__ in capsys.readouterr().out

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
        assert all(r["attempts"] == 1 for r in health.values())

    def test_transient_failure_retried_before_declared_dead(self, monkeypatch):
        """瞬时失败（超时）重试 2 次才判死——避免 GitHub Trending 这类慢源被误杀"""
        import dailyhot.health as H

        calls = {"n": 0}

        def flaky(name, limit):
            calls["n"] += 1
            raise RuntimeError("请求失败: The read operation timed out")

        monkeypatch.setattr(H, "get_hot", flaky)
        monkeypatch.setattr(H.time, "sleep", lambda s: None)  # 跳过重试等待
        r = H.check_source("github")
        assert r["ok"] is False
        assert r["kind"] == "transient"
        assert r["attempts"] == H.RETRIES + 1
        assert calls["n"] == H.RETRIES + 1

    def test_transient_recovers_after_retry(self, monkeypatch):
        import dailyhot.health as H

        calls = {"n": 0}

        def flaky(name, limit):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("请求失败: timed out")
            return _fake_items(3)

        monkeypatch.setattr(H, "get_hot", flaky)
        monkeypatch.setattr(H.time, "sleep", lambda s: None)
        r = H.check_source("github")
        assert r["ok"] is True and r["attempts"] == 2

    def test_structural_failure_not_retried(self, monkeypatch):
        """解析为空（结构变了）重试无意义，立即判死并标 structural"""
        import dailyhot.health as H

        calls = {"n": 0}

        def empty(name, limit):
            calls["n"] += 1
            return []

        monkeypatch.setattr(H, "get_hot", empty)
        r = H.check_source("zhihu")
        assert r["ok"] is False
        assert r["kind"] == "structural"
        assert calls["n"] == 1

    def test_summary_and_badge(self, monkeypatch):
        health = {
            "zhihu": {"ok": True, "items": 3},
            "github": {"ok": False, "error": "HTTP 403", "kind": "structural"},
        }
        s = summary(health)
        assert s["total"] == 2 and s["online"] == 1
        assert s["down"]["github"]["kind"] == "structural"
        fresh = "2999-01-01T00:00:00Z"  # 未来时间 → 永不过期
        assert to_badge({"a": {"ok": True}, "b": {"ok": True}}, fresh)["color"] == "brightgreen"
        mixed = {f"s{i}": {"ok": i < 7} for i in range(10)}
        assert to_badge(mixed, fresh)["color"] == "orange"
        bad = {f"s{i}": {"ok": i < 3} for i in range(10)}
        assert to_badge(bad, fresh)["color"] == "red"
        assert to_badge(health, fresh)["message"] == "1/2"

    def test_stale_badge_when_checked_at_old(self):
        """health.json 过期（CI 停摆）→ 徽章 stale 灰色，而不是永远显示旧的绿色"""
        all_ok = {f"s{i}": {"ok": True} for i in range(9)}
        assert to_badge(all_ok, "2020-01-01T00:00:00Z")["message"] == "stale"
        assert to_badge(all_ok, "2020-01-01T00:00:00Z")["color"] == "lightgrey"
        assert to_badge(all_ok, None)["message"] == "stale"  # 无时间戳视为过期
        assert to_badge(all_ok, "not-a-date")["message"] == "stale"
        # 新鲜的不受影响
        assert to_badge(all_ok, "2999-01-01T00:00:00Z")["message"] == "9/9"

    def test_format_report(self, monkeypatch):
        report = format_report(
            {
                "zhihu": {"ok": True, "items": 3, "elapsed_ms": 120, "attempts": 2},
                "github": {
                    "ok": False,
                    "error": "HTTP 403",
                    "elapsed_ms": 50,
                    "kind": "structural",
                    "attempts": 1,
                },
            }
        )
        assert "✓ zhihu" in report and "重试 1 次后成功" in report
        assert "✗ github" in report and "[structural]" in report and "1/2" in report

    def test_failure_recorded(self, monkeypatch):
        def boom(url, timeout=10.0, headers=None):
            raise RuntimeError("HTTP 403: denied")

        monkeypatch.setattr(S, "fetch_json", boom)
        monkeypatch.setattr(S, "fetch_text", boom)
        monkeypatch.setattr(H_module.time, "sleep", lambda s: None)
        health = check_all()
        assert all(not r["ok"] for r in health.values())
        assert "403" in health["zhihu"]["error"]


class TestHealthScript:
    """CI 脚本：源下线必须非零退出——这是'徽章不说谎'的另一半"""

    def _run(self, tmp_path, monkeypatch, health_result):
        import importlib.util

        import dailyhot.health as H

        monkeypatch.setattr(H, "check_all", lambda: health_result)
        spec = importlib.util.spec_from_file_location("health_check", "scripts/health_check.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.run(str(tmp_path / "health.json"))

    def test_exit_zero_when_all_online(self, tmp_path, monkeypatch):
        code = self._run(tmp_path, monkeypatch, {"a": {"ok": True, "items": 3, "attempts": 1}})
        assert code == 0

    def test_exit_one_when_source_down(self, tmp_path, monkeypatch):
        health = {
            "a": {"ok": True, "items": 3, "attempts": 1},
            "b": {"ok": False, "error": "HTTP 403", "kind": "structural", "attempts": 1},
        }
        code = self._run(tmp_path, monkeypatch, health)
        assert code == 1
        # 文件仍然写好（徽章要能变红）
        import json

        data = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
        assert data["badge"]["message"] == "1/2"
        assert data["badge"]["color"] == "red"
        assert "checked_at" in data


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
