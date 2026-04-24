# New Radar → Hermes Agent 迁移实施计划

> 版本：v1.0 | 日期：2026-04-24
> 预计总工时：15-20 小时 | 预计工期：3-5 天

---

## 目录

1. [前置条件](#1-前置条件)
2. [阶段一：环境搭建](#2-阶段一环境搭建)
3. [阶段二：MCP 工具服务器开发](#3-阶段二mcp-工具服务器开发)
4. [阶段三：引擎 → Skills 改造](#4-阶段三引擎--skills-改造)
5. [阶段四：API 层迁移](#5-阶段四api-层迁移)
6. [阶段五：集成测试与清理](#6-阶段五集成测试与清理)
7. [回滚方案](#7-回滚方案)
8. [风险清单](#8-风险清单)

---

## 1. 前置条件

### 1.1 WSL2 环境

官方 Hermes Agent **不支持原生 Windows**。必须使用 WSL2。

**安装步骤：**

```powershell
# 管理员 PowerShell
wsl --install -d Ubuntu-22.04
# 重启电脑
# 首次进入设置用户名密码
```

**验证：**

```bash
wsl
uname -r  # 应显示 Linux 内核
python3 --version  # 需要 3.10+
node --version  # 需要 18+（Hermes CLI 依赖）
```

**如缺少依赖：**

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nodejs npm
```

### 1.2 数据库确认

确认 PostgreSQL + pgvector 运行正常：

```bash
# 在 Windows 或 WSL2 中
docker compose up -d db
docker exec radar-db pg_isready -U radar -d radar
docker exec radar-db psql -U radar -d radar -c "SELECT extname FROM pg_extension WHERE extname='vector';"
# 应输出: vector
```

### 1.3 现有数据备份

```bash
# 导出 crawled_data 表
docker exec radar-db pg_dump -U radar -d radar -t crawled_data > backup_crawled_data.sql

# 备份 .env
cp .env .env.backup.$(date +%Y%m%d)
```

### 1.4 Git 分支策略

```bash
cd /mnt/d/Users/new\ radar/
git checkout -b migration/hermes-agent
git push -u origin migration/hermes-agent
```

---

## 2. 阶段一：环境搭建

**预计工时：1.5 小时**

### 2.1 安装 Hermes Agent

```bash
# 在 WSL2 中
curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash

# 验证
hermes --version
hermes doctor  # 检查环境
```

**如果安装脚本失败，手动安装：**

```bash
git clone https://github.com/nousresearch/hermes-agent.git
cd hermes-agent
pip install -e .
hermes setup
```

### 2.2 配置 Hermes Provider

```bash
# 添加 LLM Provider（每个 Skill 可独立配置）
hermes auth add openai-codex    # 或其他 Provider

# 或使用自定义 OpenAI 兼容端点
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_API_KEY=your-key
```

**配置文件位置：** `~/.hermes/config.yaml`

需要添加的 Provider 对应关系：

| Skill | Provider | Base URL |
|-------|----------|----------|
| radar-insight | kimi | https://api.moonshot.cn/v1 |
| radar-media | gemini (aihubmix) | https://aihubmix.com/v1 |
| radar-query | deepseek | https://api.deepseek.com |
| radar-report | gemini (aihubmix) | https://aihubmix.com/v1 |
| radar-forum | qwen (siliconflow) | https://api.siliconflow.cn/v1 |

### 2.3 验证 Hermes API Server

```bash
# 启动 API Server
hermes serve --port 5000 --platform api

# 另一个终端测试
curl http://localhost:5000/v1/models
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"default","messages":[{"role":"user","content":"hello"}],"stream":false}'
```

**⚠️ 注意：** 如果 `hermes serve` 命令不存在或不支持 `--platform api`，需要查看当前版本的文档确认正确命令。Hermes 版本迭代快，命令可能有变化。

### 2.4 项目目录初始化

```bash
cd /mnt/d/Users/new\ radar/

# 创建 MCP 工具服务器目录
mkdir -p mcp-servers/db-query
mkdir -p mcp-servers/crawler-coordinator
mkdir -p mcp-servers/external-search

# 创建 Skills 目录（与已有 skills/ 合并）
# 注意：现有 skills/ 已有 business-analyst, content-research-writer, keyword-research, web-access
# 新增 radar-* 系列 skills
mkdir -p skills/radar-insight/scripts
mkdir -p skills/radar-insight/references
mkdir -p skills/radar-media/scripts
mkdir -p skills/radar-media/references
mkdir -p skills/radar-query/scripts
mkdir -p skills/radar-query/references
mkdir -p skills/radar-forum/scripts
mkdir -p skills/radar-forum/references
mkdir -p skills/radar-report/scripts
mkdir -p skills/radar-report/references
```

### 2.5 里程碑验证

- [ ] WSL2 运行正常
- [ ] Hermes Agent 安装成功
- [ ] `hermes serve` 可启动 API Server
- [ ] 数据库连接正常
- [ ] Git 分支创建成功

---

## 3. 阶段二：MCP 工具服务器开发

**预计工时：4 小时**

MCP (Model Context Protocol) 是 Hermes Agent 的工具注册标准。每个 MCP Server 是一个独立的进程，通过 stdio 或 SSE 与 Hermes Agent 通信。

### 3.1 db-query MCP Server

**目标：** 封装 `backend/db/connection.py` 和 `backend/core/base_agent.py` 中的 `LocalDatabaseSearchTool`

**实现文件：** `mcp-servers/db-query/server.py`

```python
#!/usr/bin/env python3
"""
MCP Server: 数据库查询工具
提供 keyword_search、vector_search、get_recent_data、get_stats 四个工具
"""
import os
import json
import asyncio
import asyncpg
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("radar-db-query")

# 数据库连接池（复用现有配置）
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "5444")),
            user=os.getenv("DB_USER", "radar"),
            password=os.getenv("DB_PASSWORD", "radar"),
            database=os.getenv("DB_NAME", "radar"),
            min_size=2, max_size=10,
        )
    return _pool

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="keyword_search",
            description="搜索本地 crawled_data 表中的舆情数据（关键词匹配）",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "description": "返回条数", "default": 10}
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="vector_search",
            description="使用 pgvector 语义相似度搜索 crawled_data 表",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "查询向量"
                    },
                    "limit": {"type": "integer", "description": "返回条数", "default": 10}
                },
                "required": ["query_embedding"]
            }
        ),
        Tool(
            name="get_recent_data",
            description="获取最近N小时内的采集数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "平台过滤（可选）"},
                    "hours": {"type": "integer", "description": "最近N小时", "default": 24}
                }
            }
        ),
        Tool(
            name="get_stats",
            description="获取数据库统计信息（各平台数据量、最近入库时间等）",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    pool = await get_pool()
    
    if name == "keyword_search":
        keyword = arguments["keyword"]
        limit = arguments.get("limit", 10)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT platform, content_type, content, source_url, source_keyword,
                          create_time, ip_location, user_id, nickname,
                          liked_count, collected_count, comment_count, share_count
                   FROM crawled_data
                   WHERE content ILIKE $1
                   ORDER BY create_time DESC LIMIT $2""",
                f"%{keyword}%", limit
            )
        results = [dict(r) for r in rows]
        return [TextContent(type="text", text=json.dumps({"results": results, "total": len(results)}, ensure_ascii=False, default=str))]
    
    elif name == "vector_search":
        # ... 类似现有 _vector_search 实现
        pass
    
    elif name == "get_recent_data":
        # ... 按时间范围查询
        pass
    
    elif name == "get_stats":
        # ... 统计查询
        pass

if __name__ == "__main__":
    import mcp.server.stdio
    mcp.server.stdio.run(app)
```

**依赖文件：** `mcp-servers/db-query/requirements.txt`

```
mcp>=1.0.0
asyncpg>=0.29.0
```

**注册到 Hermes：**

```bash
hermes mcp add radar-db-query python /mnt/d/Users/new\ radar/mcp-servers/db-query/server.py
```

### 3.2 crawler-coordinator MCP Server

**目标：** 统一调用 DataCollector / MediaCrawler / MindSpider / web-access

**关键设计决策：** 爬虫仍作为独立 Python 进程运行，MCP Server 作为协调层。

**实现文件：** `mcp-servers/crawler-coordinator/server.py`

```python
#!/usr/bin/env python3
"""
MCP Server: 爬虫协调器
统一调用各爬虫微服务，提供 crawl_keyword、crawl_media、crawl_deep 等工具
"""
import os
import json
import asyncio
import subprocess
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("radar-crawler-coordinator")

PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/mnt/d/Users/new radar")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="crawl_keyword",
            description="使用 DataCollector 通过 API 采集关键词数据（Anspire/Bocha/Tavily/Firecrawl）",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "source": {"type": "string", "enum": ["anspire", "bocha", "tavily", "firecrawl", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="crawl_media",
            description="使用 MediaCrawler 采集社媒平台数据（小红书/抖音/微博/B站/知乎）",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "enum": ["xhs", "dy", "wb", "bili", "zhihu"]},
                    "keyword": {"type": "string"}
                },
                "required": ["platform", "keyword"]
            }
        ),
        Tool(
            name="crawl_deep",
            description="使用 MindSpider 进行深度舆情爬取",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"}
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_crawler_status",
            description="获取爬虫系统运行状态",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "crawl_keyword":
        keyword = arguments["keyword"]
        source = arguments.get("source", "all")
        # 调用 DataCollector
        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "microservices.DataCollector.main",
            "--source", source, "--keyword", keyword,
            cwd=PROJECT_ROOT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return [TextContent(type="text", text=stdout.decode() or stderr.decode())]
    
    elif name == "crawl_media":
        # 类似，调用 MediaCrawler
        pass
    
    elif name == "crawl_deep":
        # 类似，调用 MindSpider
        pass
    
    elif name == "get_crawler_status":
        # 检查爬虫进程状态
        pass

if __name__ == "__main__":
    import mcp.server.stdio
    mcp.server.stdio.run(app)
```

### 3.3 external-search MCP Server

**目标：** 封装 `backend/core/external_tools.py` 中的 4 个外部搜索 API

**实现文件：** `mcp-servers/external-search/server.py`

```python
#!/usr/bin/env python3
"""
MCP Server: 外部搜索工具
封装 Anspire/Bocha/Tavily/Firecrawl API
"""
import os
import json
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("radar-external-search")

@app.list_tools()
async def list_tools():
    return [
        Tool(name="anspire_search", description="Anspire 深度网络搜索", inputSchema={...}),
        Tool(name="bocha_search", description="Bocha 多模态搜索", inputSchema={...}),
        Tool(name="tavily_search", description="Tavily 实时新闻搜索", inputSchema={...}),
        Tool(name="firecrawl_scrape", description="Firecrawl 网页深度抓取", inputSchema={...}),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    # 直接复用 external_tools.py 的逻辑
    # 注意：需要将 httpx 同步调用改为异步
    pass
```

### 3.4 注册所有 MCP Server

```bash
hermes mcp add radar-db-query python ./mcp-servers/db-query/server.py
hermes mcp add radar-crawler-coordinator python ./mcp-servers/crawler-coordinator/server.py
hermes mcp add radar-external-search python ./mcp-servers/external-search/server.py

# 验证
hermes mcp list
```

### 3.5 里程碑验证

- [ ] `db-query` MCP Server 启动正常
- [ ] `keyword_search` 返回正确结果
- [ ] `vector_search` 返回正确结果
- [ ] `crawler-coordinator` 能调用 DataCollector
- [ ] `external-search` 能调用 Anspire/Bocha/Tavily
- [ ] Hermes Agent 能发现所有 MCP 工具

---

## 4. 阶段三：引擎 → Skills 改造

**预计工时：6 小时**

这是最核心的阶段。每个引擎需要：
1. 编写 `SKILL.md`（定义 + 指令）
2. 将 `agent.py` 改造为 `scripts/` 下的可执行脚本
3. 将 Prompt 模板移到 `references/`
4. 删除对 `BaseHermesAgent` / `LocalDatabaseSearchTool` 的依赖，改为 MCP 调用

### 4.1 radar-insight Skill

**源文件：** `backend/engines/insight/`

**目标结构：**

```
skills/radar-insight/
├── SKILL.md                     # Skill 定义
├── scripts/
│   └── insight_agent.py         # Agent 实现（从 agent.py 改造）
└── references/
    ├── insight_prompts.md        # Prompt 模板
    └── sentiment_guide.md        # 情感分析指南
```

**SKILL.md：**

```markdown
---
name: radar-insight
description: 深度洞察分析引擎 - 情感分析、趋势预测、热点发现。优先查询本地 crawled_data 表，本地结果不足时降级至 Anspire 外部搜索。
---

# Insight Engine - 深度舆情洞察

## 功能
- 接收用户查询，从本地 PostgreSQL crawled_data 表检索相关内容
- 进行情感倾向分析（正面/负面/中性）
- 计算传播指标（点赞/评论/转发）评估内容影响力
- 识别热点内容和关键传播节点

## 数据源
1. **主数据源**: MCP 工具 `radar-db-query` → keyword_search / vector_search
2. **降级数据源**: MCP 工具 `radar-external-search` → anspire_search

## 降级策略
- 本地搜索结果 < 3 条时，自动调用 Anspire 外部搜索补充
- 本地搜索结果 ≥ 3 条时，仅使用本地数据

## 使用方式
[/insight 人工智能发展趋势]

## LLM 配置
推荐模型: kimi-k2-0711-preview
Provider: moonshot
Base URL: https://api.moonshot.cn/v1
```

**agent.py 改造要点：**

```python
# 改造前 (backend/engines/insight/agent.py)
from backend.core.base_agent import BaseHermesAgent

class DeepSearchAgent(BaseHermesAgent):
    def __init__(self, config=None, session_id=None):
        super().__init__(
            name="InsightEngine",
            role_instruction=INSIGHT_ENGINE_ROLE_INSTRUCTION,
            session_id=session_id,
        )
    # self.db_tool.keyword_search() → 内置方法

# 改造后 (skills/radar-insight/scripts/insight_agent.py)
# 不再继承 BaseHermesAgent，改为直接使用 Hermes Agent + MCP 工具
# Agent 通过 MCP 协议调用 radar-db-query 和 radar-external-search
```

**关键改造逻辑：**

1. 删除 `from backend.core.base_agent import BaseHermesAgent`
2. 删除 `self.db_tool = LocalDatabaseSearchTool()` — 改为 MCP 工具
3. 所有 `self.db_tool.keyword_search()` → MCP 工具调用
4. 所有 `self.db_tool.vector_search()` → MCP 工具调用
5. 保留 InsightEngine 特有的：nodes/（搜索流程节点）、tools/sentiment_analyzer、clustering 逻辑
6. Prompt 模板移到 `references/insight_prompts.md`

### 4.2 radar-media Skill

**源文件：** `backend/engines/media/`

**改造要点同上，差异：**
- 降级策略：本地无结果 → `bocha_search`
- 保留 MediaEngine 特有的：多媒体内容类型过滤（视频/图片/图文）

### 4.3 radar-query Skill

**源文件：** `backend/engines/query/`

**改造要点同上，差异：**
- 降级策略：本地无结果 → `tavily_search`
- 保留 QueryEngine 特有的：深度搜索流程

### 4.4 radar-forum Skill

**源文件：** `backend/engines/forum/`

**改造要点：**
- Forum Agent 不直接搜索数据，而是调度其他三个 Skill
- 需要实现 Skill 间调用机制（Hermes 支持 `delegate` 工具）
- 主持人逻辑（`llm_host.py`）保留，移到 `scripts/`

### 4.5 radar-report Skill

**源文件：** `backend/engines/report/`

**改造要点：**
- 报告生成是纯 LLM 任务，不直接搜索数据
- 接收其他 Skill 的输出，生成结构化报告
- IR（中间表示）系统保留
- HTML/PDF/Markdown 渲染器保留
- 模板系统保留

### 4.6 安装 Skills

```bash
hermes skills install ./skills/radar-insight
hermes skills install ./skills/radar-media
hermes skills install ./skills/radar-query
hermes skills install ./skills/radar-forum
hermes skills install ./skills/radar-report

# 验证
hermes skills list
```

### 4.7 里程碑验证

- [ ] 每个 Skill 的 SKILL.md 格式正确
- [ ] `hermes skills install` 成功
- [ ] 每个 Skill 能独立执行分析
- [ ] MCP 工具调用正常
- [ ] 降级策略正常触发

---

## 5. 阶段四：API 层迁移

**预计工时：3 小时**

### 5.1 启动 Hermes API Server

Hermes 官方已有 `gateway/platforms/api_server.py`，提供：
- `/v1/chat/completions` — OpenAI 兼容（**Open WebUI 直接对接**）
- `/v1/responses` — Hermes 原生格式
- `/v1/models` — 模型列表

**启动命令：**

```bash
hermes serve --port 5000 --platform api
```

### 5.2 自定义端点迁移

现有 Flask 中有一些自定义端点需要迁移到 Hermes Plugin：

| Flask 端点 | 迁移方式 |
|-----------|---------|
| `/api/report/status` | Hermes Plugin 或保留 Flask 辅助服务 |
| `/api/v1/crawler/status` | MCP 工具 `get_crawler_status` |
| `/api/v1/logs/stream` | 保留 Flask 辅助服务（SSE 日志流） |
| `/api/v1/task/start` | Hermes 异步任务 API |
| `/api/v1/reports` | 保留 Flask 辅助服务或 Hermes Plugin |
| `/v1/sentiment` | MCP 工具或 Hermes Plugin |
| `/api/config` | Hermes 配置系统替代 |

**策略：** 核心对话走 Hermes API Server，辅助管理端点（日志、报告下载、配置）保留一个轻量 Flask 或 FastAPI 辅助服务。

### 5.3 Open WebUI 对接

```bash
# docker-compose.yml 已有 open-webui 配置
# 只需更新 API 指向 Hermes
```

更新 `docker-compose.yml` 中的环境变量：

```yaml
open-webui:
  environment:
    - OAI_API_BASE=http://radar:5000/v1  # 指向 Hermes API Server
```

Open WebUI 配置：
- API URL: `http://host.docker.internal:5000/v1`
- API Key: 任意值
- Model: `new-radar-agent`

### 5.4 docker-compose.yml 更新

```yaml
services:
  radar:
    build:
      context: .
      dockerfile: Dockerfile.hermes  # 新 Dockerfile
    container_name: radar
    command: ["hermes", "serve", "--port", "5000", "--platform", "api"]
    env_file: .env
    ports:
      - "5000:5000"
    volumes:
      - ./skills:/app/skills
      - ./mcp-servers:/app/mcp-servers
      - ./logs:/app/logs
      - ./final_reports:/app/final_reports
      - ./.env:/app/.env
      - ~/.hermes:/root/.hermes
    depends_on:
      db:
        condition: service_healthy

  # 辅助服务（管理端点）
  radar-admin:
    build:
      context: .
      dockerfile: Dockerfile.admin  # 轻量 Flask 服务
    container_name: radar-admin
    command: ["python", "-m", "backend.admin"]
    env_file: .env
    ports:
      - "5001:5001"
    depends_on:
      - radar

  # 数据库（不变）
  db:
    image: pgvector/pgvector:pg15
    container_name: radar-db
    # ... 同现有配置

  # Open WebUI（不变）
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: radar-open-webui
    # ... 同现有配置
```

### 5.5 里程碑验证

- [ ] Hermes API Server 在 :5000 启动
- [ ] `/v1/chat/completions` 返回正确响应
- [ ] `/v1/models` 返回模型列表
- [ ] Open WebUI 能连接并对话
- [ ] 辅助管理端点（报告/日志/配置）可用
- [ ] Docker Compose 全栈启动正常

---

## 6. 阶段五：集成测试与清理

**预计工时：3 小时**

### 6.1 集成测试用例

```python
# tests/test_hermes_migration.py

def test_keyword_search_mcp():
    """MCP db-query keyword_search 返回正确结果"""
    pass

def test_vector_search_mcp():
    """MCP db-query vector_search 返回正确结果"""
    pass

def test_insight_skill_with_local_data():
    """Insight Skill 使用本地数据完成分析"""
    pass

def test_insight_skill_fallback():
    """Insight Skill 本地无数据时降级至 Anspire"""
    pass

def test_media_skill():
    """Media Skill 正常运行"""
    pass

def test_query_skill():
    """Query Skill 正常运行"""
    pass

def test_forum_skill_synthesis():
    """Forum Skill 能综合三引擎结果"""
    pass

def test_report_skill():
    """Report Skill 生成 HTML/PDF/MD 报告"""
    pass

def test_openai_compat_api():
    """POST /v1/chat/completions 返回 OpenAI 格式"""
    pass

def test_streaming_response():
    """SSE 流式响应正常"""
    pass

def test_open_webui_connection():
    """Open WebUI 能完成一次完整对话"""
    pass

def test_crawler_coordinator():
    """MCP crawler-coordinator 能触发爬虫"""
    pass
```

### 6.2 清理旧代码

确认所有功能迁移完成后：

```bash
# 删除旧的 Flask 主应用（已被 Hermes API Server 替代）
rm backend/app.py

# 删除旧的 OpenAI 兼容端点（已被 Hermes 内置替代）
rm backend/api/routes/openai_compat.py

# 删除旧的 BaseHermesAgent（已被 Hermes Agent Runtime 替代）
rm backend/core/base_agent.py

# 删除旧的引擎目录（已迁移到 skills/）
rm -rf backend/engines/

# 删除旧的外部工具（已迁移到 MCP）
rm backend/core/external_tools.py

# 保留
# - backend/db/connection.py（MCP Server 复用）
# - backend/config.py（配置管理）
# - microservices/（爬虫层不变）
```

### 6.3 文档更新

- [ ] 更新 README.md（替换为 README-HERMES.md 内容）
- [ ] 更新 rules.md（添加 Hermes 开发规范）
- [ ] 更新 docker-compose.yml
- [ ] 更新 .env.example
- [ ] 合并到 main 分支

### 6.4 最终里程碑

- [ ] 全部测试通过
- [ ] 旧代码已清理
- [ ] 文档已更新
- [ ] Docker Compose 全栈正常运行
- [ ] Open WebUI 能完成完整分析流程
- [ ] Git 合并到 main

---

## 7. 回滚方案

如果迁移过程中遇到不可解决的问题：

### 7.1 代码回滚

```bash
git checkout main  # 回到迁移前的代码
```

### 7.2 数据库回滚

数据库未做任何结构变更，无需回滚。

### 7.3 服务回滚

```bash
# 恢复 Flask 后端
python -m backend.app

# 恢复 docker-compose
docker compose -f docker-compose.yml.backup up -d
```

---

## 8. 风险清单

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Hermes `hermes serve` 命令不可用或 API 不兼容 | 阻塞 | 阶段一先验证；备选：保留 Flask + 只迁移 Skills |
| MCP 协议版本不兼容 | 部分功能不可用 | 查看 Hermes 当前 MCP 版本要求 |
| WSL2 网络与 Docker 网络冲突 | 数据库连接失败 | 使用 `host.docker.internal` 或 `localhost` 转发 |
| Skills 间调度机制不支持 | Forum Skill 无法调度其他 Skill | 使用 Hermes `delegate` 工具或回退到 Flask 调度 |
| Hermes Agent 版本更新快，API 变化 | 代码需要跟进 | 锁定版本（git tag 或 pip freeze） |
| MediaCrawler 需要 GUI 浏览器 | WSL2 无 GUI | 使用 CDP 模式或 X11 转发 |
| 编码问题（WSL2 vs Windows） | 文件读写乱码 | 统一使用 UTF-8，设置 `PYTHONIOENCODING` |

---

## 附录 A：文件对照表

| 当前文件 | 迁移操作 | 目标位置 |
|---------|---------|---------|
| `backend/app.py` | **删除** | → Hermes `api_server.py` |
| `backend/api/routes/openai_compat.py` | **删除** | → Hermes 内置 |
| `backend/engines/base.py` | **删除** | → Hermes Skills Router |
| `backend/engines/insight/agent.py` | **改造** | → `skills/radar-insight/scripts/insight_agent.py` |
| `backend/engines/insight/nodes/` | **迁移** | → `skills/radar-insight/scripts/nodes/` |
| `backend/engines/insight/tools/` | **改造** | → `skills/radar-insight/scripts/tools/` |
| `backend/engines/insight/prompts/` | **迁移** | → `skills/radar-insight/references/` |
| `backend/engines/insight/state/` | **迁移** | → `skills/radar-insight/scripts/state/` |
| `backend/engines/insight/llms/` | **删除** | → Hermes Provider 路由 |
| `backend/engines/media/agent.py` | **改造** | → `skills/radar-media/scripts/media_agent.py` |
| `backend/engines/query/agent.py` | **改造** | → `skills/radar-query/scripts/query_agent.py` |
| `backend/engines/forum/agent.py` | **改造** | → `skills/radar-forum/scripts/forum_agent.py` |
| `backend/engines/forum/monitor.py` | **改造** | → `skills/radar-forum/scripts/monitor.py` |
| `backend/engines/forum/llm_host.py` | **改造** | → `skills/radar-forum/scripts/llm_host.py` |
| `backend/engines/report/` | **改造** | → `skills/radar-report/scripts/` |
| `backend/core/base_agent.py` | **删除** | → Hermes Agent Runtime |
| `backend/core/external_tools.py` | **改造** | → `mcp-servers/external-search/server.py` |
| `backend/core/sentiment_tool.py` | **改造** | → MCP Tool 或 `skills/radar-insight/scripts/` |
| `backend/db/connection.py` | **保留** | MCP Server 复用 |
| `backend/config.py` | **保留** | 配置管理 |
| `backend/clients/last30days_importer.py` | **迁移** | → `mcp-servers/crawler-coordinator/` |
| `microservices/*` | **保留不动** | MCP Server 调用 |
| `skills/web-access/` | **保留** | Hermes Skill |

## 附录 B：Hermes Skill 格式参考

```markdown
---
name: skill-name
description: 一句话描述 Skill 的功能
---

# Skill Name

## 功能
详细说明 Skill 的功能和适用场景。

## 使用方式
[/skill-name 参数]

## 依赖
- MCP 工具: radar-db-query, radar-external-search
- 环境: Python 3.10+, asyncpg

## 配置
- LLM Provider: moonshot / kimi-k2
- 降级策略: 本地 < 3 条 → Anspire
```

## 附录 C：MCP Server 格式参考

```python
#!/usr/bin/env python3
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("server-name")

@app.list_tools()
async def list_tools():
    return [Tool(name="tool_name", description="...", inputSchema={...})]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    # 实现逻辑
    return [TextContent(type="text", text=result)]

if __name__ == "__main__":
    mcp.server.stdio.run(app)
```
