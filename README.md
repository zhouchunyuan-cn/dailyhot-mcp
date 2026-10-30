# DailyHot MCP

[![Sources Online](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/zhouchunyuan-cn/dailyhot-mcp/main/health.json)](.github/workflows/health.yml)
[![Glama rating](https://glama.ai/mcp/servers/zhouchunyuan-cn/dailyhot-mcp/badges/score.svg)](https://glama.ai/mcp/servers/zhouchunyuan-cn/dailyhot-mcp)
[![CI](https://github.com/zhouchunyuan-cn/dailyhot-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/zhouchunyuan-cn/dailyhot-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**中文热榜聚合，一层接入三种用法：MCP server / CLI / Python 库。**
知乎、百度、头条、B站、少数派、华尔街见闻、V2EX、Hacker News、GitHub Trending——
一个接口全部拿走。

> **为什么是"最可靠"的热榜工具**：热榜类项目的通病是悄悄坏掉——平台端点一变，
> 用户装了才发现源已经挂了。这里把可用性做成可见信号：**CI 每天实测全部源**
> （见顶部徽章的 X/9 与 [健康检查工作流](.github/workflows/health.yml)），
> 源下线自动开 issue，解析器有 37 个离线回归测试守护。

## 30 秒接入

**Claude Code / Cursor（MCP）**

```jsonc
// Claude Code: claude mcp add dailyhot -- python -m dailyhot.mcp_server
// 或 mcpServers 配置：
{
  "mcpServers": {
    "dailyhot": { "command": "dailyhot-mcp" }   // pip install dailyhot-mcp[mcp] 后
  }
}
```

对模型说："现在知乎和B站在热议什么？对比一下"——它会调用 `get_hot_list` 工具。

**命令行**

```bash
pip install -e ".[mcp]"
dailyhot --version               # 版本号
dailyhot list                    # 全部源
dailyhot get zhihu -n 10         # 知乎热榜前 10（--json 输出 JSON）
dailyhot health                  # 逐源实测可用性
```

**Python 库（核心零依赖）**

```python
from dailyhot import get_hot, list_sources

for item in get_hot("bilibili", limit=5):
    print(item.rank, item.title, item.score)  # HotItem(rank, title, url, score)
```

## 源清单（v1，全部经真实端点验证）

| 源 | 标识 | 说明 |
|---|---|---|
| 知乎热榜 | `zhihu` | 含热度值 |
| 百度热搜 | `baidu` | 实时板 |
| 今日头条 | `toutiao` | 热榜 |
| B站热门 | `bilibili` | 全站排行榜，含播放数 |
| 少数派 | `sspai` | 最新文章 |
| 华尔街见闻 | `wallstreetcn` | 实时快讯 |
| V2EX 热帖 | `v2ex` | 官方 API |
| Hacker News | `hackernews` | 首页（含分数） |
| GitHub Trending | `github` | 仓库 + 简介 |

**接入中（反爬，欢迎 PR 提供方案）**：微博（403）、抖音（空响应）。

## 设计

```
┌────────────────────────────────────────────┐
│  MCP server（FastMCP，stdio）  CLI（argparse）│  接入层
├────────────────────────────────────────────┤
│  sources.py：9 个源适配器（端点 + 纯函数解析）│  核心层
│  fetcher.py：urllib 抓取（零依赖）           │
├────────────────────────────────────────────┤
│  health.py：逐源实测 → 徽章数据             │  可观测层
│  CI：每日健康检查 + 坏源自动 issue          │
└────────────────────────────────────────────┘
```

- **解析与抓取分离**：解析器是纯函数，37 个测试全部基于录制 fixtures 离线运行
  （fixtures 就是真实响应的快照——字段结构变化会让测试立刻变红）
- **新增源 = 一个解析函数 + 一行注册**，欢迎 PR（附 fixture + 测试）
- **宽容解析**：单条坏数据跳过，不毁掉整榜

## English

**DailyHot MCP** aggregates Chinese & global hot lists (Zhihu, Baidu, Toutiao,
Bilibili, sspai, Wallstreetcn, V2EX, Hacker News, GitHub Trending) behind one
interface — as an **MCP server** (Claude Code / Cursor ready), a **CLI**, and a
**zero-dependency Python library**.

What makes it different: **source health is a visible signal.** A daily CI job
probes every source, the badge at the top shows X/9 online, failed sources
automatically open issues, and 37 offline regression tests guard the parsers.

```bash
pip install "dailyhot-mcp[mcp]"
dailyhot-mcp                    # stdio MCP server
dailyhot get hackernews -n 5    # CLI
```

## License

MIT
