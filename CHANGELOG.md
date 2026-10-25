# 更新日志

## [0.1.1] - 2026-10-25

- CLI 新增 `--version`（`dailyhot --version` 输出版本号）
- 依赖锁定 `mcp>=1.20,<2`：mcp SDK 2.x 将 FastMCP 改名为 MCPServer，
  此前干净安装会直接崩溃；新增 Dockerfile（目录站容器化健康检查用）

## [0.1.0] - 2026-10-24

首个版本：9 源聚合，库/CLI/MCP 三层接入，源可用性每日实测。

### 新增

- 9 个源（全部经真实端点验证）：知乎热榜、百度热搜、今日头条、B站热门、
  少数派、华尔街见闻快讯、V2EX 热帖、Hacker News、GitHub Trending
- 三层接入：Python 库（核心零依赖，纯标准库 urllib）、CLI
  （list/get/health/serve）、MCP server（官方 SDK FastMCP，stdio，
  可选依赖 `pip install dailyhot-mcp[mcp]`）
- 源健康体系：`dailyhot health` 逐源实测；CI 每天定时检查全部源并提交
  health.json（shields 徽章实时显示 X/9 在线）；源下线自动开 issue
- 37 个离线测试：9 个解析器基于录制 fixtures 的回归（源字段变化立刻红）、
  CLI 输出与退出码、健康汇总/徽章着色、MCP 工具注册

### 已知限制

- 微博（403）、抖音（空响应）因反爬暂缓接入，方案欢迎 PR
- GitHub Trending 对未登录请求可能仅返回部分条目
