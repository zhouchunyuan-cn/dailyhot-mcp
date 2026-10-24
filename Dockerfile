# Glama / MCP 目录站的容器化健康检查用：
# 容器启动 stdio MCP server，需能响应 initialize / tools/list 请求
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY dailyhot ./dailyhot

RUN pip install --no-cache-dir ".[mcp]"

# stdio MCP server（Glama 检查：启动 + introspection）
ENTRYPOINT ["dailyhot-mcp"]
