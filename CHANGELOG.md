# 更新日志

## [0.2.0] - 2026-11-27

### 修复

- **源健康徽章不再说谎**（核心卖点的可信性）：
  - 瞬时失败（超时/5xx）重试 2 次再判死，GitHub Trending 等慢源不再被偶发超时误杀
  - 失败分类 `transient` / `structural`，维护者一眼分清是对方挂了还是解析器该改
  - `to_badge` 增加 `checked_at` 时效判定，超过 48 小时未更新显示 `stale` 灰色
  - `health_check.py` 有源下线时退出码 1（原无条件 0，CI 永远绿）；workflow 改为
    用 step output 传递状态，health.json 总能提交上去
- GitHub Trending 改为按 `<article>` 块解析：修复多仓库时简介错位的隐患

### 新增

- MCP `get_hot_list` 支持**多源一次查询**（`sources: list[str]`），
  错误结构化返回（源名写错带 `available_sources`，模型可自纠；单源失败不影响其他源）
- **mcp SDK 1.x / 2.x 双兼容**（FastMCP → MCPServer），解除 `<2` 版本锁
- **streamable-http 传输**：`dailyhot serve --http --port 8000`（Glama 云端部署/远程客户端）
- GitHub Trending 条目增加 "N stars today · 语言" 字段
- `scripts/health_check.py --out PATH`

### 变更

- 测试 39 → 51；版本 0.1.1 → 0.2.0

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
