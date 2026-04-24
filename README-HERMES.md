# New Radar — 基于 Hermes Agent 的深度舆情分析与知识挖掘引擎

> 从 Flask 自建架构迁移到**官方 Hermes Agent 框架**，利用其 Skills 系统、MCP 工具生态、内置 API Server 和记忆增强，构建更强大的多 Agent 舆情分析平台。

---

## 迁移动机

| 痛点 | 当前状态 | 迁移后 |
|------|----------|--------|
| Agent 管理 | 手动 `BaseHermesAgent` + 嵌入代码 | 官方 Hermes Agent 运行时 |
| 工具注册 | 硬编码在 `base_agent.py` | MCP 协议动态注册 |
| 前端对接 | 自写 Flask `/v1` 路由 | 官方 `api_server.py` 内置 OpenAI 兼容 |
| 记忆/上下文 | 无持久化 | Hermes 内置 FTS5 记忆 + 行为建模 |
| Skill 扩展 | 无 | Hermes Skills 市场体系 |
| 多 Provider | 每个 Engine 硬编码一个 LLM | Hermes 智能路由 + 多 Provider 池 |
| 流式输出 | 手动 SSE chunk | 官方原生 SSE 支持 |

---

## 目标架构

```
┌───────────────────────────────────────────────────────────────┐
│                        用户界面                                │
│              Open WebUI (:3000, Docker)                        │
└──────────────────────┬────────────────────────────────────────┘
                       │ /v1/chat/completions (SSE)
┌──────────────────────▼────────────────────────────────────────┐
│              Hermes Agent API Server (:5000)                   │
│         (官方 gateway/platforms/api_server.py)                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              Hermes Agent Runtime                       │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │            Skills Router (调度层)                  │  │   │
│  │  └──┬────────┬────────┬────────┬────────┬───────────┘  │   │
│  │     │        │        │        │        │               │   │
│  │  ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼──────┐     │   │
│  │  │Insight│ │Media │ │Query │ │Forum │ │Report   │     │   │
│  │  │Skill │ │Skill │ │Skill │ │Skill │ │Skill    │     │   │
│  │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬──────┘     │   │
│  │     └────────┴────────┴────────┴────────┘              │   │
│  │                        │                                │   │
│  │  ┌─────────────────────▼─────────────────────────────┐ │   │
│  │  │           MCP Tools (工具层)                        │ │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │ │   │
│  │  │  │DB Query  │ │Crawlers  │ │External Search   │   │ │   │
│  │  │  │(pgvector)│ │(6 platforms)│(Tavily/Bocha/...)│   │ │   │
│  │  │  └──────────┘ └──────────┘ └──────────────────┘   │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────────────────┐
│           PostgreSQL + pgvector (:5432)                       │
│              crawled_data 表 (embedding 列)                    │
└───────────────────────────────────────────────────────────────┘
```

### 与当前架构的关键差异

1. **Agent 运行时**：从 Flask + 嵌入式 Hermes → 官方 Hermes Agent（含 CLI、Gateway、Memory）
2. **API 层**：从 Flask Blueprint → Hermes `api_server.py`（原生 OpenAI 兼容 + Open WebUI 支持）
3. **引擎调度**：从 `MultiEngineDispatcher` → Hermes Skills Router
4. **工具注册**：从 `Tool(name=..., func=...)` 硬编码 → MCP 协议动态注册
5. **数据层**：**不变** — PostgreSQL + pgvector 继续使用
6. **爬虫层**：**不变** — MediaCrawler/MindSpider/DataCollector/web-access 继续使用
7. **前端**：**不变** — Open WebUI 继续使用

---

## 项目结构

```
new-radar/
├── skills/                          # Hermes Skills (迁移后的引擎)
│   ├── radar-insight/               # 深度洞察引擎
│   │   ├── SKILL.md                 # Skill 定义 + 指令
│   │   ├── scripts/                 # 可执行脚本
│   │   │   └── insight_agent.py     # Agent 实现
│   │   └── references/             # 参考文档
│   │       └── insight_prompts.md   # Prompt 模板
│   ├── radar-media/                 # 媒体分析引擎
│   ├── radar-query/                 # 查询引擎
│   ├── radar-forum/                 # 论坛调度引擎
│   └── radar-report/                # 报告生成引擎
│
├── mcp-servers/                     # MCP 工具服务器
│   ├── db-query/                    # 数据库查询 (PostgreSQL + pgvector)
│   │   ├── server.py               # MCP Server 实现
│   │   └── requirements.txt
│   ├── crawler-coordinator/         # 爬虫协调器
│   │   ├── server.py
│   │   └── requirements.txt
│   └── external-search/             # 外部搜索 (Tavily/Bocha/Anspire/Firecrawl)
│       ├── server.py
│       └── requirements.txt
│
├── microservices/                   # 爬虫微服务 (保留不动)
│   ├── DataCollector/               # API 数据采集 (Anspire/Bocha/Tavily/Firecrawl)
│   ├── MediaCrawler/                # 社媒爬虫 (小红书/抖音/微博/B站/知乎)
│   ├── MindSpider/                  # 深度舆情爬取 (BroadTopic + DeepSentiment)
│   └── web-access/                  # CDP 浏览器自动化
│
├── backend/                         # 过渡期保留 (最终精简)
│   ├── db/                          # 数据库层 (保留)
│   │   ├── connection.py            # SQLAlchemy 异步连接
│   │   └── __init__.py
│   └── config.py                    # 全局配置 (保留，迁移到 Hermes config)
│
├── docker-compose.yml               # 统一编排
├── Dockerfile                       # Hermes Agent 镜像
├── .env                             # 环境变量
├── .env.example                     # 环境变量模板
├── MIGRATION-PLAN.md                # 本迁移实施计划
└── README.md                        # 本文件
```

---

## 数据流详解

### 核心原则：本地数据优先

所有 Skill **优先查询本地 PostgreSQL**，外部 API 仅作为降级备选：

| Skill | 主数据源 | 降级策略 |
|-------|----------|----------|
| **radar-insight** | MCP `db_query` → `crawled_data` keyword/vector search | 本地<3条 → MCP `external_search` (Anspire) |
| **radar-media** | MCP `db_query` → `crawled_data` keyword search | 本地无结果 → MCP `external_search` (Bocha) |
| **radar-query** | MCP `db_query` → `crawled_data` keyword/vector search | 本地无结果 → MCP `external_search` (Tavily) |
| **radar-forum** | 调度上述三 Skill，自身不直接搜索 | 综合分析阶段可补充外部信息 |
| **radar-report** | 接收其他 Skill 的输出，生成结构化报告 | 无降级（纯生成） |

### 数据库表结构（不变）

`crawled_data` 表：
- `platform` — 来源平台（微博/抖音/B站/知乎/小红书）
- `content_type` — 内容类型（图文/视频/评论）
- `content` — 正文内容
- `source_url` — 来源链接
- `source_keyword` — 搜索关键词
- `create_time` — 时间戳
- `liked_count/collected_count/comment_count/share_count` — 互动数据
- `ip_location/user_id/nickname` — 用户信息
- `embedding` — 向量（JSON 格式，pgvector L2 距离索引）

---

## 快速开始

### 环境要求

- **WSL2** (Ubuntu 22.04+) — Hermes Agent 不支持原生 Windows
- Python 3.10+
- PostgreSQL 15+ (需安装 pgvector 扩展)
- Docker & Docker Compose
- Node.js 18+ (Hermes CLI 依赖)

### 启动步骤

```bash
# 1. 进入 WSL2
wsl

# 2. 安装 Hermes Agent
curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash
hermes setup

# 3. 注册 MCP 工具服务器
hermes mcp add db-query python /path/to/mcp-servers/db-query/server.py
hermes mcp add crawler-coordinator python /path/to/mcp-servers/crawler-coordinator/server.py
hermes mcp add external-search python /path/to/mcp-servers/external-search/server.py

# 4. 安装 New Radar Skills
hermes skills install ./skills/radar-insight
hermes skills install ./skills/radar-media
hermes skills install ./skills/radar-query
hermes skills install ./skills/radar-forum
hermes skills install ./skills/radar-report

# 5. 启动数据库
docker compose up -d db

# 6. 启动 Hermes API Server (替代原 Flask 后端)
hermes serve --port 5000 --platform api

# 7. 启动 Open WebUI
docker compose up -d open-webui
```

访问 **http://localhost:3000** → Settings → Connections → OpenAI：

```
API URL: http://host.docker.internal:5000/v1
API Key: 任意值（如 sk-new-radar）
Model: new-radar-agent
```

---

## 核心 API

Hermes `api_server.py` 原生提供：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 多引擎并行分析（SSE 流式） |
| `/v1/responses` | POST | Hermes 原生响应格式 |
| `/v1/models` | GET | 可用模型列表 |
| `/v1/runs` | POST | 异步任务执行 |

自定义扩展端点（通过 Hermes Plugin）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/sentiment` | POST | 情感分析 |
| `/v1/crawler/status` | GET | 爬虫运行状态 |
| `/v1/crawler/ingest` | POST | 触发爬虫采集 |
| `/v1/reports` | GET | 历史报告列表 |

---

## MCP 工具服务器

### db-query (数据库查询)

```python
# mcp-servers/db-query/server.py
# 提供以下 MCP 工具：
# - keyword_search(keyword, limit) → 关键词搜索 crawled_data
# - vector_search(query_embedding, limit) → pgvector 语义检索
# - get_recent_data(platform, hours) → 获取最近数据
# - get_stats() → 数据库统计信息
```

### crawler-coordinator (爬虫协调)

```python
# mcp-servers/crawler-coordinator/server.py
# 提供以下 MCP 工具：
# - crawl_keyword(keyword, platforms) → 关键词采集（调用 DataCollector）
# - crawl_media(platform, keyword) → 社媒平台采集（调用 MediaCrawler）
# - crawl_deep(keyword) → 深度舆情采集（调用 MindSpider）
# - get_crawler_status() → 爬虫状态
```

### external-search (外部搜索)

```python
# mcp-servers/external-search/server.py
# 提供以下 MCP 工具：
# - anspire_search(query, limit) → Anspire 深度搜索
# - bocha_search(query, limit) → Bocha 多模态搜索
# - tavily_search(query, depth) → Tavily 新闻搜索
# - firecrawl_scrape(url) → Firecrawl 网页抓取
```

---

## 配置

### LLM Provider 配置

每个 Skill 可独立配置 LLM Provider（通过 Hermes config）：

| Skill | 推荐 LLM | 原因 |
|-------|----------|------|
| radar-insight | kimi-k2 | 长上下文，适合深度分析 |
| radar-media | gemini-2.5-pro | 多模态理解 |
| radar-query | deepseek-chat | 性价比高，搜索任务足够 |
| radar-report | gemini-2.5-pro | 报告生成需要强模型 |
| radar-forum | qwen-plus | 主持人角色，需要快速响应 |

Hermes 支持通过 `hermes auth add` 添加多个 Provider，自动路由。

### 环境变量

`.env` 文件保持与现有项目兼容，新增 Hermes 相关变量：

```bash
# Hermes Agent
HERMES_DEFAULT_MODEL=kimi-k2
HERMES_API_PORT=5000
HERMES_ENABLE_MEMORY=true

# 数据库（不变）
DB_HOST=127.0.0.1
DB_PORT=5444
DB_USER=radar
DB_PASSWORD=radar
DB_NAME=radar

# LLM Providers（不变）
INSIGHT_ENGINE_API_KEY=...
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2-0711-preview

# 外部搜索工具（不变）
TAVILY_API_KEY=...
ANSPIRE_API_KEY=...
BOCHA_WEB_API_KEY=...
```

---

## 迁移对照表

| 当前组件 | 迁移目标 | 迁移方式 |
|---------|---------|---------|
| `backend/app.py` (Flask 主应用) | Hermes `api_server.py` | **删除**，用官方 API Server |
| `backend/api/routes/openai_compat.py` | Hermes 内置 `/v1/chat/completions` | **删除**，官方已实现 |
| `backend/engines/base.py` (MultiEngineDispatcher) | Hermes Skills Router | **重写**，Skill 间调度 |
| `backend/engines/insight/` | `skills/radar-insight/` | **改造**，加 SKILL.md |
| `backend/engines/media/` | `skills/radar-media/` | **改造**，加 SKILL.md |
| `backend/engines/query/` | `skills/radar-query/` | **改造**，加 SKILL.md |
| `backend/engines/forum/` | `skills/radar-forum/` | **改造**，加 SKILL.md |
| `backend/engines/report/` | `skills/radar-report/` | **改造**，加 SKILL.md |
| `backend/core/base_agent.py` (BaseHermesAgent) | Hermes Agent Runtime | **删除**，用官方 AIAgent |
| `backend/core/external_tools.py` | `mcp-servers/external-search/` | **改造**，MCP 协议 |
| `backend/core/sentiment_tool.py` | MCP Tool 或 Hermes Plugin | **改造** |
| `backend/db/connection.py` | `mcp-servers/db-query/` + 保留原文件 | **复用**，MCP 封装 |
| `backend/clients/last30days_importer.py` | `mcp-servers/crawler-coordinator/` | **改造** |
| `microservices/*` | 保留不动，通过 MCP 调用 | **复用** |
| `skills/*` (现有4个skill) | 迁移到 Hermes skills 目录 | **迁移** |

---

## License

MIT
