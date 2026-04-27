# New Radar — 深度舆情分析与知识挖掘引擎

> 基于 **多智能体架构** 的实时舆情分析系统，全本地化数据流、彻底前后端分离、Multi-Agent 协作消除幻觉。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│              Open WebUI (:3010) + REST API (:8642)              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ OpenAI-compatible API
┌──────────────────────────────▼──────────────────────────────────┐
│                      Hermes Agent Gateway                         │
│                      OpenAI-compatible API Server (:8642)          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Skills Layer                           │   │
│  │              radar-engine (主技能)                       │   │
│  │    采集 → 存储 → Insight/Media/Query → 报告生成        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────┬──────────────────────────────────┐   │
│  │  data-collection    │        data-storage              │   │
│  │       MCP           │           MCP                    │   │
│  └─────────────────────┴──────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      Microservices Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │DataCollector│  │MediaCrawler │  │   MindSpider        │   │
│  │ (外部搜索)  │  │ (社媒爬虫)  │  │  (AI话题发现+深度)  │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL + pgvector (:5432)               │   │
│  │                   crawled_data 表 (embedding)              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 核心数据流

```
用户请求 → radar-engine skill
              │
              ├── Phase 1: 数据采集 (data-collection MCP)
              │       ├── anspire_search / bocha_search / tavily_search → URL列表
              │       ├── firecrawl_scrape → 完整网页内容
              │       └── crawl_media → 社媒平台数据
              │
              ├── Phase 2: 数据存储 (data-storage MCP)
              │       └── save_crawled_data → crawled_data 表
              │
              ├── Phase 3: 数据分析
              │       ├── Insight Engine → 趋势/情感/热点分析
              │       ├── Media Engine → 视频/图片/互动分析
              │       └── Query Engine → 数据库查询
              │
              └── Phase 4: 报告生成
                      └── Markdown / HTML / PDF
```

## 项目结构

```
new-radar/
├── hermes-agent/              # [SUBMODULE] Nous Research Hermes Agent
├── hermes-data/              # Hermes 运行时数据
│   ├── config.yaml           # Agent 配置 (MCP servers, skills)
│   └── skills/              # 激活的 skills
├── mcp-servers/             # MCP Server 实现
│   ├── data-collection/     # 数据采集 MCP
│   │   └── server.py        # anspire/bocha/tavily/firecrawl + crawl_media
│   └── data-storage/        # 数据存储 MCP
│       └── server.py        # keyword/vector search + save_crawled_data
├── microservices/            # 微服务层
│   ├── DataCollector/       # 外部搜索 API 聚合
│   ├── MediaCrawler/      # 社媒平台爬虫 (xhs/dy/wb/bili/zhihu)
│   └── web-access/         # CDP 浏览器自动化
├── MindSpider/             # [SUBMODULE] AI 话题发现 + 深度舆情爬取
├── skills/                 # 项目 Skills
│   └── radar-engine/       # 主技能：完整采集→分析→报告流程
├── scripts/                # 工具脚本
│   └── db/init_db.py      # 数据库初始化
├── docker-compose.yml      # 容器编排
├── Dockerfile              # 应用镜像
├── .env                   # 环境变量
└── start.sh               # 启动脚本
```

## MCP Servers

### data-collection

| 工具 | 说明 |
|------|------|
| `anspire_search` | Anspire 深度搜索 (中国) |
| `bocha_search` | Bocha 多模态搜索 |
| `tavily_search` | Tavily 新闻搜索 (海外) |
| `firecrawl_scrape` | 网页内容抓取 |
| `crawl_media` | 社媒平台爬虫 |

### data-storage

| 工具 | 说明 |
|------|------|
| `keyword_search` | 关键词搜索 |
| `vector_search` | 向量相似度搜索 |
| `get_recent_data` | 获取最近数据 |
| `get_stats` | 统计信息 |
| `save_crawled_data` | 保存采集数据 |

## Skills

| Skill | 说明 |
|-------|------|
| **radar-engine** | 主技能：采集→存储→Insight/Media/Query→报告 |
| business-analyst | 业务分析 |
| content-research-writer | 内容写作 |
| keyword-research | 关键词研究 |
| web-access | 浏览器自动化 |

## 快速开始

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 15+ with pgvector (Docker 内置)

### 启动

```bash
# 1. 启动所有服务
docker compose up -d

# 2. 初始化数据库
docker exec radar python scripts/db/init_db.py

# 3. 访问 Open WebUI
# http://localhost:3010
```

### 连接配置

在 Open WebUI Settings → Connections → OpenAI：

```
API URL: http://host.docker.internal:8642/v1
API Key: hermes-secret-key-2026 (或 .env 中 API_SERVER_KEY)
Model: qwen-plus
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | OpenAI 兼容接口 |
| `/v1/models` | GET | 可用模型列表 |
| `/health` | GET | 健康检查 |

## 数据库表结构

```sql
CREATE TABLE crawled_data (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,        -- xhs, dy, wb, bili, tavily, etc.
    content_type VARCHAR(50) NOT NULL,  -- text, image, video, article
    content TEXT NOT NULL,
    source_url TEXT,
    source_keyword VARCHAR(255),
    create_time TIMESTAMP,
    nickname VARCHAR(255),
    liked_count INTEGER DEFAULT 0,
    collected_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    embedding JSONB,                     -- 向量 embedding
    metadata JSONB
);
```

## 外部 API 集成

| API | 用途 | 用于 |
|-----|------|------|
| Anspire | 深度搜索 | Insight Engine |
| Bocha | 多模态搜索 | Media Engine |
| Tavily | 海外搜索 | Query Engine |
| Firecrawl | 网页抓取 | Data Collection |
| DeepSeek | AI 话题提取 | MindSpider |

## 开发指南

遵循 `CLAUDE.md` 中的原则：
- **Think Before Coding** - 先思考，明确假设
- **Simplicity First** - 最少代码解决问题
- **Surgical Changes** - 只改必须改的
- **Goal-Driven Execution** - 定义成功标准，循环验证
