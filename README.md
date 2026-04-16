# New Radar — 深度舆情分析与知识挖掘引擎

> 基于**多智能体架构**的实时舆情分析系统，全本地化数据流、彻底前后端分离、多 Agent 协作消除幻觉。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面                              │
│     Open WebUI (:3000, Docker) + REST API (:5000)         │
└──────────────────────┬──────────────────────────────────────┘
                       │ /v1/chat/completions (SSE)
┌──────────────────────▼──────────────────────────────────────┐
│                     Backend (Python Flask :5000)             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │     MultiEngineDispatcher (并行三引擎 + ForumAgent)   │   │
│  └──────┬────────┬────────┬────────┬────────────────────┘   │
│         │        │        │        │                        │
│  ┌──────▼──┐ ┌──▼─────┐ ┌▼──────┐ │                        │
│  │ Insight │ │ Media  │ │ Query │ │                        │
│  │ Engine  │ │ Engine │ │ Engine│ │                        │
│  └────┬────┘ └───┬────┘ └───┬───┘ │                        │
│       └─────────┴──────────┴──────┘                        │
│                          │                                  │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │       BaseHermesAgent + LocalDatabaseSearchTool        │  │
│  │            (keyword_search / vector_search)             │  │
│  └───────────────────────┬───────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│           PostgreSQL + pgvector (:5432)                     │
│              crawled_data 表 (embedding 列)                  │
└─────────────────────────────────────────────────────────────┘
```

## 核心数据流

所有引擎（Query / Insight / Media）**优先查询本地 PostgreSQL**，外部 API 仅作为降级备选：

| 引擎 | 主数据源 | 降级策略 |
|------|----------|----------|
| **QueryEngine** | `LocalDatabaseSearchTool` → `crawled_data` 表 | 本地无结果时降级至 Tavily |
| **InsightEngine** | `LocalDatabaseSearchTool` → `crawled_data` 表 | 本地结果<3条时降级至 MediaCrawlerDB（平台评论/分区数据） |
| **MediaEngine** | `LocalDatabaseSearchTool` → `crawled_data` 表 | 本地无结果时降级至 Bocha |
| **ForumAgent** | 调度三引擎综合分析，自身使用 Hermes 工具 | 仅在已开启外部工具开关时调用 Tavily/Bocha/Anspire 做补充搜索 |

> **设计原则**：`crawled_data` 表存在有效数据时，引擎**不会**调用外部 API。外部降级仅在本地数据匮乏时触发。

## 项目结构

```
new-radar/
├── backend/
│   ├── app.py                          # Flask 主应用 /v1 路由注册
│   ├── config.py                       # 全局配置（Pydantic Settings）
│   ├── api/routes/openai_compat.py     # OpenAI 兼容端点
│   ├── core/
│   │   ├── base_agent.py               # BaseHermesAgent + LocalDatabaseSearchTool
│   │   ├── external_tools.py            # 外部工具封装（Tavily/Bocha/Anspire/Firecrawl）
│   │   └── sentiment_tool.py            # 情感分析 Tool（Hermes 工具）
│   ├── engines/
│   │   ├── base.py                     # MultiEngineDispatcher（三引擎并行 + ForumAgent 综合）
│   │   ├── insight/agent.py            # InsightEngine（舆情 + 情感分析）
│   │   ├── media/agent.py              # MediaEngine（多媒体内容分析）
│   │   ├── query/agent.py              # QueryEngine（深度搜索）
│   │   ├── forum/agent.py              # ForumAgent（多 Agent 协作调度）
│   │   └── report/                     # ReportEngine（报告生成）
│   ├── db/connection.py                # 数据库连接管理
│   └── clients/                        # 数据源客户端
├── microservices/                      # 爬虫微服务层
│   ├── MediaCrawler/                   # 社媒爬虫（小红书/抖音/微博/B站/知乎）
│   ├── MindSpider/                     # 深度舆情爬取
│   └── last30days/                     # 近30天数据导入
├── docs/
│   ├── DESIGN_AND_ROADMAP.md           # 详细设计文档（阶段一到五全部完成 ✅）
│   └── open-webui-analysis.md          # Open WebUI 集成分析
├── .env                                # 环境变量
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 15+ (需安装 pgvector 扩展)
- Docker & Docker Compose

### 启动步骤

```bash
# 1. 初始化数据库
docker compose up -d db
python scripts/db/init_db.py

# 2. 启动 Flask 后端 (:5000)
python -m backend.app

# 3. 启动 Open WebUI (:3000)
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main
```

访问 **http://localhost:3000** → Settings → Connections → OpenAI：

```
API URL: http://host.docker.internal:5000/v1
API Key: 任意值（如 sk-local-dev）
Model: new-radar-agent
```

### 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 多引擎并行分析（SSE 流式） |
| `/v1/models` | GET | 可用模型列表 |
| `/v1/health` | GET | 健康检查 |
| `/v1/sentiment` | POST | 情感分析工具 |
| `/api/v1/crawler/status` | GET | 爬虫运行状态 |
| `/api/v1/logs/stream` | GET | 爬虫日志流（SSE） |

## 引擎数据源详解

### LocalDatabaseSearchTool

所有引擎继承 `BaseHermesAgent`，通过 `LocalDatabaseSearchTool` 查询 `crawled_data` 表：

```python
# backend/core/base_agent.py
class LocalDatabaseSearchTool:
    def keyword_search(self, query: str, limit: int = 10) -> str:
        # 返回 JSON: {"results": [...], "total": N}

    def vector_search(self, query_vector: list, limit: int = 10) -> str:
        # 使用 pgvector L2 距离进行语义检索
```

**表结构**（`crawled_data`）：
- `platform` 平台、`content_type` 内容类型、`content` 正文
- `source_url` 来源链接、`keyword` 关键词、`create_time` 时间戳
- `liked_count/collected_count/comment_count/share_count` 互动数据
- `embedding` 向量（JSON 格式，pgvector L2 距离索引）

### QueryEngine（查询引擎）

**数据方法**：`execute_search_tool()` → `_search_local_crawled_data()` → `db_tool.keyword_search()`

- **主路径**：keyword/vector search → crawled_data 表
- **降级**：仅在本地无结果时调用 `_tavily_fallback()`（TavilyNewsAgency）
- **特殊工具**（`search_images_for_news` 等）直接走 Tavily

### InsightEngine（洞察引擎）

**数据方法**：`execute_search_tool()` → `_search_local_crawled_data()` → `db_tool.keyword_search()`

- **主路径**：keyword search → crawled_data 表
- **降级**：本地结果<3条时调用 `_media_crawler_fallback()`（MediaCrawlerDB 平台专用查询）
- **情感分析**：`multilingual_sentiment_analyzer` 本地算法（22语言，支持微博/小红书/抖音）

### MediaEngine（媒体引擎）

**数据方法**：`execute_search_tool()` → `_search_local_crawled_data()` → `db_tool.keyword_search()`

- **主路径**：keyword search → crawled_data 表（含图片/视频/图文类型）
- **降级**：本地无结果时调用 `_bocha_fallback()`（BochaMultimodalSearch）

### ForumAgent（论坛调度引擎）

**数据方法**：不直接搜索数据，而是**调度** Query / Insight / Media 三引擎并行分析

- `_dispatch_to_engine()` 通过 Flask 内部路由（`/api/query/search` 等）调用各引擎
- 自身 Hermes 工具（Tavily/Bocha/Anspire）仅在**综合分析阶段**用于补充外部信息
- 最终通过 `_build_synthesis_prompt()` 让 LLM 做交叉验证和综合

## 多引擎并行流式输出

`MultiEngineDispatcher.stream_analyze()` 的执行流程：

```
1. 🔍  启动全引擎分析（主引擎: insight）
2. 并行执行 Query / Insight / Media（ThreadPoolExecutor）
3. 每个引擎完成 → 立即以 20 字符 chunk 流式输出
4. 三引擎全部完成 → ForumAgent 综合分析流式输出
5. finish_reason="stop" + "data: [DONE]\n\n"
```

## 文档

- [docs/DESIGN_AND_ROADMAP.md](docs/DESIGN_AND_ROADMAP.md) — 完整设计文档（阶段一至五全部完成 ✅）
- [rules.md](rules.md) — 开发规则
