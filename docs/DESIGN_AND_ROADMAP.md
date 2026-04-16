# New Radar 系统改造与详细设计说明

## 1. 系统核心设计目标
1.  **彻底的前后端分离**：将原有杂糅的 Python/Flask + HTML/JS/CSS 代码分离。后端仅负责数据采集、Agent 推理和 API 服务；前端采用 Vue3 独立构建。
2.  **全本地化数据流**：切断原 Agent（Query, Media, Insight 等）依赖外部搜索引擎（如 Tavily）的路径。所有数据均来自 `MediaCrawler` 采集的本地 PostgreSQL 数据库。
3.  **内嵌式自我进化**：采用 Nous Research 开源的 `Hermes Agent` 替换繁杂的 Agent 调度框架。利用其原生的 FTS5 记忆检索、行为建模和自动化技能提取，实现 Agent 的“越用越聪明”。
4.  **微服务爬虫解耦**：将极其重依赖的 `MediaCrawler`（含 Playwright、滑块破解、代理池）从主业务流中剥离，作为独立服务运行。

---

## 2. 总体架构设计 (Architecture)

### 2.1 基础设施层 (Infrastructure)
*   **PostgreSQL + pgvector**：作为全系统的单一事实来源（SSOT）。
    *   存储 `MediaCrawler` 爬取的海量社媒帖子和评论。
    *   通过 `pgvector` 提供基于 `L2 距离` 的语义检索能力。

### 2.2 爬虫微服务层 (Microservices)
*   **MediaCrawler (`microservices/MediaCrawler`)**：
    *   **输入**：接收监控任务（如：监听“某品牌”在小红书、抖音的帖子）。
    *   **处理**：负责反爬、抓取、清洗，并调用轻量级模型对文本进行向量化（Embedding）。
    *   **输出**：将清洗后的结构化数据和向量写入 PostgreSQL。

### 2.3 核心智能引擎层 (Backend)
所有的 Engine 都继承自 `BaseHermesAgent`，内嵌了 `Hermes Agent`。它们默认能够使用 `LocalDatabaseSearchTool` 进行本地舆情检索，同时系统支持通过读取 `.env` 配置（如 `ENABLE_TAVILY=True` 等）动态挂载外部网络数据源工具。
*   **QueryEngine**：负责在本地库中进行大范围的关键词和向量搜索，并在开启 `ENABLE_TAVILY` 时调用 Tavily 搜索全网最新新闻补充观点。
*   **MediaEngine**：专注于理解抓取回来的图片 OCR 文本、视频元数据。在开启 `ENABLE_BOCHA` 时，调用 Bocha 提取外部的高度结构化 Modal Card。
*   **InsightEngine**：负责深度的本地 SQL 查询和数据聚合，以及与 `SentimentAnalysisModel`（本地算法库）联动进行情感分类。如果开启 `ENABLE_ANSPIRE`，则能扩展至私域知识搜索。
*   **ForumEngine**：作为“圆桌会议室”，引导 Query、Media、Insight 三个 Agent 进行链式讨论，消除信息盲区。
*   **ReportEngine**：最终接收 ForumEngine 的共识结果，结合 Markdown 模板（`report_template`），输出高质量的长篇 HTML/PDF 研报。

### 2.4 前端交互层 (Frontend)
*   **Vue 3 SPA (`frontend/`)**：
    *   提供美观的 B2B Dashboard。
    *   实时展示爬虫运行状态。
    *   通过 WebSocket 或 SSE (Server-Sent Events) 展示 Agent 的链式思考过程。
    *   交互式查看和下载最终生成的分析报告。

---

## 3. 后续待办任务清单 (Roadmap)

目前我们已经完成了**项目骨架重构**、**PostgreSQL + pgvector 部署与测试**、**底层 BaseHermesAgent 基类封装**、**阶段一（数据层打通）**、**阶段二（Agent 引擎重构）**、**阶段三（Open WebUI 集成）**、**阶段四（本地模型对接）**、**阶段五（Vue 3 前端重建）**。所有阶段均已完成！

### 阶段一：数据层打通 (MediaCrawler 改造) ✅
- [x] **任务 1.1**：清理 `microservices/MediaCrawler` 中的冗余代码，精简依赖。
- [x] **任务 1.2**：改造 `MediaCrawler` 的存储管道（Pipeline）。不再存入 CSV/MongoDB，而是统一写入 PostgreSQL 的 `crawled_data` 表。
- [x] **任务 1.3**：在 `MediaCrawler` 写入库前，集成轻量级 Embedding 模型（如 `sentence-transformers`），计算文本向量并写入 `embedding` 列。

### 阶段二：Agent 引擎业务重构 (Backend) ✅
- [x] **任务 2.1**：重写 `QueryEngine`。使其继承 `BaseHermesAgent`，并设计专门的 `role_instruction`（系统提示词），让其熟练使用本地库查询工具。
- [x] **任务 2.2**：重写 `MediaEngine` 和 `InsightEngine`。规范它们的输入输出契约。
- [x] **任务 2.3**：重构 `ForumEngine`。实现一个多 Agent 协作调度器，能将一个复杂的分析需求拆解并分发给上述三个 Agent，并收集辩论结果。
- [x] **任务 2.4**：重构 `ReportEngine`。梳理原有的 `report_template`，确保它能正确消费 `ForumEngine` 产出的结构化 JSON/Markdown，并渲染为 PDF/HTML。

### 阶段三：Open WebUI 集成 ✅
- [x] **任务 3.1**：创建 Flask Blueprint，注册 `/v1/chat/completions`、`/v1/models`、`/v1/sentiment` 等路由。
- [x] **任务 3.2**：实现多引擎调度适配器 `backend/engines/base.py` (`MultiEngineDispatcher`)。
- [x] **任务 3.3**：SSE 流式响应支持（`stream_analyze`）。
- [x] **任务 3.4**：注册 Blueprint 到 `backend/app.py`。

### 阶段四：API 与本地模型对接 ✅
- [x] **任务 4.1**：FastAPI 迁移评估 — 当前 Flask + SocketIO 已提供 RESTful + SSE + WebSocket 功能，暂无需迁移。
- [x] **任务 4.2**：将 `SentimentAnalysisModel` 封装为 Hermes Tool（`backend/core/sentiment_tool.py`）和 Flask API（`POST /v1/sentiment`）。


#### 目标
让 New Radar 实现 OpenAI 兼容的 `/v1/chat/completions` 接口，接入 Open WebUI 作为前端。

#### 架构目标
```
Open WebUI (:3000)
    → POST /v1/chat/completions
    → New Radar Flask (:5000)
    → 多引擎并行 (Insight/Media/Query)
    → SSE 流式返回
```

#### 实施计划

##### 任务 3.1：实现 OpenAI 兼容端点（核心）

**文件：** `backend/api/routes/openai_compat.py`（新建）

| 子任务 | 说明 | 文件位置 |
|--------|------|---------|
| 3.1.1 | 创建 Blueprint，注册 `/v1/chat/completions` 路由 | `backend/api/routes/openai_compat.py` |
| 3.1.2 | 实现 `POST /v1/chat/completions` — 解析 messages、stream 参数 | `backend/api/routes/openai_completions.py` |
| 3.1.3 | 实现 SSE 流式响应格式 (`text/event-stream`) | `backend/api/routes/openai_compat.py` |
| 3.1.4 | 实现 `GET /v1/models` — 返回可用模型列表 | `backend/api/routes/openai_compat.py` |
| 3.1.5 | 注册 Blueprint 到 Flask app | `backend/app.py` |

**OpenAI Chat Completions 响应格式：**
```python
# 非流式
{
    “id”: “chatcmpl-xxx”,
    “object”: “chat.completion”,
    “model”: “new-radar-agent”,
    “choices”: [{
        “index”: 0,
        “message”: {“role”: “assistant”, “content”: “...”},
        “finish_reason”: “stop”
    }],
    “usage”: {“prompt_tokens”: 0, “completion_tokens”: 0, “total_tokens”: 0}
}

# 流式 (SSE)
data: {“id”:”chatcmpl-xxx”,”object”:”chat.completion.chunk”,”model”:”new-radar-agent”,”choices”:[{“index”:0,”delta”:{“content”:”...”},”finish_reason”:null}]}
data: {“id”:”chatcmpl-xxx”,”object”:”chat.completion.chunk”,”model”:”new-radar-agent”,”choices”:[{“index”:0,”delta”:{},”finish_reason”:”stop”}]}
data: [DONE]
```

##### 任务 3.2：多引擎调度适配

| 子任务 | 说明 | 涉及文件 |
|--------|------|---------|
| 3.2.1 | 设计统一的任务调度接口（Query/Insight/Media 并行） | `backend/engines/` |
| 3.2.2 | 改造现有引擎以支持流式输出（Generator/Yield） | `backend/engines/*/agent.py` |
| 3.2.3 | 实现结果聚合与格式化（Markdown 报告） | `backend/engines/report/` |

**流式接口设计：**
```python
# backend/engines/base.py
class BaseStreamingEngine:
    def stream_analyze(self, query: str) -> Generator[str, None, None]:
        “””流式返回分析片段”””
        yield “正在检索本地数据库...”
        # ... 多引擎并行分析
        yield “## 舆情分析报告\n\n”
        yield final_content
```

##### 任务 3.3：Open WebUI 配置指南

| 步骤 | 操作 |
|------|------|
| 1 | 部署 Open WebUI：`docker run -d -p 3000:8080 ... ghcr.io/open-webui/open-webui:main` |
| 2 | 访问 http://localhost:3000 注册管理员账号 |
| 3 | 管理面板 → Settings → Connections → OpenAI |
| 4 | 配置：`OpenAI API URL: http://host.docker.internal:5000/v1`，`API Key: new-radar-local`，`Model: new-radar-agent` |

##### 任务 3.4：Hermes Agent 已有支持

`backend/frameworks/hermes-agent/gateway/platforms/api_server.py` 已实现：
- `POST /v1/chat/completions` — OpenAI Chat Completions 格式
- `POST /v1/responses` — OpenAI Responses API 格式
- `GET /v1/models` — 模型列表
- `GET /v1/runs/{run_id}/events` — SSE 生命周期事件

**调研结论：** 优先利用 Hermes 内置的 `api_server.py`，或在其基础上改造适配 New Radar 的多引擎架构。

---

### 阶段四：API 与本地模型对接 ✅
- [x] **任务 4.1**：FastAPI 迁移评估 — 当前 Flask + SocketIO 已提供 RESTful + SSE + WebSocket 功能，暂无需迁移。
- [x] **任务 4.2**：将 `SentimentAnalysisModel` 封装为 Hermes Tool（`backend/core/sentiment_tool.py`）和 Flask API（`POST /v1/sentiment`）。

### 阶段五：前端重建 (Frontend) ✅
- [x] **任务 5.1**：以 **Open WebUI** 作为唯一前端（Docker 独立部署），通过 `/v1/chat/completions` SSE 与 New Radar Flask 通信。
- [x] **任务 5.2**：移除自研 React SPA（`frontend/` 目录），Flask 后端不再托管静态文件，`/` 根路径返回 API 入口信息 JSON。
- [x] **任务 5.3**：保留 `/api/report/*` 和 `/api/v1/crawler/*` 等 REST 端点，供 Open WebUI 插件或外部工具调用。
- [x] **任务 5.4**：所有对话式分析功能（舆情查询、多引擎并行、报告生成）通过 Open WebUI 对话界面完成。

---

## 附录：Open WebUI 集成技术细节

### 架构说明

New Radar 采用**单一前端**架构：**Open WebUI**，后端仅暴露 API。

```
┌─────────────────────────────────────────────────────────┐
│  Open WebUI (Docker, :3000)                             │
│  · 对话式分析入口                                       │
│  · SSE 流式渲染 Markdown                               │
│  · 模型配置 (连接 :5000/v1)                            │
└────────────────────┬──────────────────────────────────┘
                     │ /v1/chat/completions (SSE)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  New Radar Flask API (:5000)                            │
│                                                         │
│  /v1/chat/completions  ←── MultiEngineDispatcher        │
│  /v1/models             ←── 可用模型列表                 │
│  /v1/health             ←── 健康检查                    │
│  /v1/sentiment          ←── 情感分析工具                │
│  /api/report/*          ←── 报告管理 (历史/下载)        │
│  /api/v1/crawler/status ←── 爬虫状态                    │
│  /api/v1/logs/stream    ←── 爬虫日志 SSE               │
└────────────────────┬──────────────────────────────────┘
                     │
         ┌────────────┴────────────┐
         ▼             ▼             ▼
   QueryEngine   InsightEngine   MediaEngine
         └────────────┬────────────┘
                       ▼
              ForumAgent 🤝
         (BaseHermesAgent)
         · 三引擎结果交叉验证
         · 流式输出综合分析
                       │
                       ▼
                ReportEngine
```

### Open WebUI 配置步骤

| 步骤 | 操作 |
|------|------|
| 1 | 部署 Open WebUI：`docker run -d -p 3000:8080 ghcr.io/open-webui/open-webui:main` |
| 2 | 访问 http://localhost:3000 注册管理员账号 |
| 3 | 管理面板 → Settings → Connections → OpenAI |
| 4 | 配置：`OpenAI API URL: http://host.docker.internal:5000/v1`（Windows 下用 `http://localhost:5000/v1`），`API Key: new-radar-local`，`Model: new-radar-agent` |
| 5 | System Prompt 建议配置： |

```
你是一个专业的舆情分析助手。当用户提出分析需求时，系统会调用本地数据库和网络搜索工具获取最新数据，并返回三个引擎的分析结果（Insight / Media / Query）。请用清晰的 Markdown 格式呈现分析结论。
```

### SSE 流式响应规范（改进版）

所有三个引擎并行运行，各自完成后立即以 **小 chunk 流式** 输出（每 20 字符一个 SSE chunk），三引擎全部完成后 **ForumAgent** 对结果进行交叉验证和综合分析，流式输出最终结论：

```python
# Open WebUI 收到的 SSE 事件序列（简化）
data: {“id”:”chatcmpl-xxx”,”object”:”chat.completion.chunk”,”model”:”new-radar-agent”,”choices”:[{“index”:0,”delta”:{“content”:”🔍 正在启动全引擎分析（主引擎: insight）...\n\n”},”finish_reason”:null}]}
data: {“id”:”chatcmpl-xxx”,”object”:”chat.completion.chunk”,”model”:”new-radar-agent”,”choices”:[{“index”:0,”delta”:{“content”:”⏳ media/query engine(s) still running...\n\n”},”finish_reason”:null}]}
data: {“id”:”chatcmpl-xxx”,”object”:”chat.completion.chunk”,”model”:”new-radar-agent”,”choices”:[{“index”:0,”delta”:{“content”:”\n\n🧠 **Insight Engine（舆情分析）**\n\n”},”finish_reason”:null}]}
data: {“id”:”...”,”choices”:[{“index”:0,”delta”:{“content”:”近年来...”},”finish_reason”:null}]}  # 流式正文
...  (typing effect)
data: {“id”:”...”,”choices”:[{“index”:0,”delta”:{“content”:”\n\n---\n\n”},”finish_reason”:null}]}
data: {“id”:”...”,”choices”:[{“index”:0,”delta”:{“content”:”\n\n🎬 **Media Engine（多媒体分析）**\n\n”},”finish_reason”:null}]}
...  (next engine streams in)
data: {“id”:”...”,”choices”:[{“index”:0,”delta”:{},”finish_reason”:”stop”}]}
data: [DONE]
```

### 核心防幻觉护栏（必须遵守）
所有涉及 LLM 处理搜索结果的 Prompt **必须**在最高权重位置加入：
> “如果搜索结果中没有相关数据，你必须明确回复'未检索到相关数据'或'数据不足，无法分析'，**绝对禁止**自行编造数字、用户ID、评论、新闻事件或学术名词。”


### 开发量评估（已完成）

| 任务 | 状态 |
|------|------|
| 阶段一（数据层打通） | ✅ 已完成 |
| 阶段二（Agent 引擎重构 + ForumAgent） | ✅ 已完成 |
| 阶段三（Open WebUI 集成 + SSE 流式） | ✅ 已完成 |
| 阶段四（本地模型 API 封装） | ✅ 已完成 |
| 阶段五（React SPA 重构） | ✅ 已完成 |

**所有开发阶段均已完成，项目进入维护阶段。**

> 注：前端已确定为 **Open WebUI**（:3000，Docker），后端 Flask（:5000）不再托管 React SPA 静态文件。
