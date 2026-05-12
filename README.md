# New Radar — 深度舆情分析与知识挖掘引擎

> 基于 **多智能体架构** 的实时舆情分析系统，全本地化数据流、彻底前后端分离、Multi-Agent 协作消除幻觉。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│              REST API (:8642)                                   │
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
├── hermes-agent/              # Hermes Agent 主项目（统一架构）
│   ├── tools/                # 内置工具
│   ├── skills/               # 技能（内置 + 业务）
│   │   ├── apple/           # 内置技能
│   │   ├── creative/
│   │   └── business/        # 业务技能
│   │       └── radar-engine/# 主技能：完整采集→分析→报告流程
│   ├── mcp/                 # MCP Server 实现
│   │   ├── data-collection/ # 数据采集 MCP
│   │   └── data-storage/    # 数据存储 MCP
│   ├── microservices/        # 微服务层
│   │   ├── DataCollector/  # 外部搜索 API 聚合
│   │   ├── MediaCrawler/   # 社媒平台爬虫 (xhs/dy/wb/bili/zhihu)
│   │   └── web-access/     # CDP 浏览器自动化
│   ├── MindSpider/         # AI 话题发现 + 深度舆情爬取
│   └── data/               # Hermes 运行时数据
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

- Python 3.10+ (用于本地开发)
- Docker & Docker Compose
- PostgreSQL 15+ with pgvector (Docker 内置)

### 启动

```bash
# 1. 启动所有服务
docker compose up -d

# 2. 初始化数据库
docker exec radar python scripts/db/init_db.py

# 3. 访问服务
# - radar API: http://localhost:8642
# - Adminer DB: http://localhost:8080
```

## Web UI

### Hermes Web UI (可选)

hermes-web-ui 提供图形化界面来管理 Hermes Agent，但需要本地安装 hermes-agent：

```bash
# 1. 安装 hermes-agent (需要 Python 环境)
pip install hermes-agent

# 2. 安装 hermes-web-ui
npm install -g hermes-web-ui

# 3. 启动 hermes-web-ui
hermes-web-ui start --port 8648
```

**注意**：hermes-web-ui 需要 hermes CLI 来管理网关进程。当前 hermes-agent 运行在 Docker 中，需要本地 Python 环境才能运行 hermes-web-ui。

### Adminer 数据库管理

http://localhost:8080

直接访问 PostgreSQL 数据库进行管理。

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
