# New Radar 项目开发规则

> **⚠️ 本文件为强制遵守的开发规则。所有开发者在提交代码前必须确认符合以下规范。**

---

## 第一部分：项目架构规则

### A1. 目录结构规范

```
new-radar/
├── backend/          # 所有后端 Python 代码
│   ├── app.py        # Flask 主入口（唯一入口）
│   ├── config.py     # 全局配置（唯一配置源）
│   ├── engines/      # 业务引擎（Insight/Media/Query/Forum/Report）
│   ├── db/           # 数据库层（统一连接管理）
│   ├── core/         # 核心模块（base_agent, external_tools）
│   ├── models/       # 本地 ML 模型
│   ├── clients/      # 数据源客户端适配器
│   ├── utils/        # 通用工具函数
│   ├── frameworks/   # 第三方框架（hermes-agent submodule）
│   └── api/          # REST API 路由层
├── frontend/         # 前端代码（已弃用，对话功能由 Open WebUI 替代）
├── microservices/    # 爬虫微服务（独立进程，数据写入 PostgreSQL）
├── scripts/          # 工具/迁移/调试脚本（禁止放置业务代码）
├── docs/             # 设计文档
├── storage/          # 运行时数据（cache/logs/reports）
├── skills/           # AI 技能插件
└── tests/            # 测试代码
```

### A2. 禁止事项

- ❌ **禁止在根目录创建 Python 业务脚本** — 所有 .py 文件必须放在对应模块目录下
- ❌ **禁止在 engines 中直接发起网络请求** — 分析引擎只从本地 PostgreSQL 读取数据
- ❌ **禁止在 microservices 中引入分析逻辑** — 爬虫只负责采集和入库
- ❌ **禁止跨层级直接 import** — engines 只能通过 `backend.db` 访问数据库
- ❌ **禁止在 `scripts/` 中放置会被主应用 import 的模块** — scripts 为一次性执行脚本
- ❌ **禁止硬编码 API Key** — 所有密钥必须通过 `.env` 和 `config.py` 管理
- ❌ **禁止在根目录放置 `debug_*.py`、`fix_*.py`、`test_*.py`** — 统一放入 `scripts/debug/` 或 `tests/`

### A3. 模块引用规范

```python
# ✅ 正确的 import 方式
from backend.config import settings
from backend.db.connection import fetch_all, execute_write
from backend.engines.insight.agent import create_agent

# ❌ 错误的 import 方式
from config import settings              # 缺少 backend. 前缀
from InsightEngine.utils.db import ...   # 旧路径，已废弃
import sys; sys.path.append(...)        # 禁止手动修改 sys.path
```

### A4. 数据流边界（读写分离）

```
[互联网/社交媒体]
       │
       ▼
┌─────────────────┐
│ Microservices   │ ← 数据采集层（可访问互联网）
│ (爬虫/搜索/API）│
└────────┬────────┘
         │ 写入
         ▼
┌─────────────────┐
│ PostgreSQL +    │ ← 数据存储层
│ pgvector        │
└────────┬────────┘
         │ 只读
         ▼
┌─────────────────┐
│ Engines         │ ← 分析层（禁止访问互联网）
│ Insight/Media/ │
│ Query/Report    │
└─────────────────┘
```

**规则：**
1. 新增数据源 → 在 `microservices/` 新建爬虫 → 数据写入 PostgreSQL
2. 新增分析能力 → 在 `backend/engines/` 新建引擎 → 从 PostgreSQL 读取数据
3. **新增爬虫时，绝对不需要修改任何分析引擎代码**

### A5. Hermes Agent 更新规范

- `backend/frameworks/hermes-agent/` 为 Git Submodule，与上游同步
- 项目内的 `backend/core/base_agent.py` 是对 Hermes 的本地适配层
- 修改 Hermes 本身代码时应提交到上游仓库，不要在 submodule 内直接修改

---

## 第二部分：代码质量规则

### C1. LLM 防幻觉护栏（最高优先级）

所有涉及 LLM 处理搜索结果的 Prompt **必须**在最高权重位置加入：

> "如果搜索结果中没有相关数据，你必须明确回复'未检索到相关数据'或'数据不足，无法分析'，**绝对禁止**自行编造数字、用户ID、评论、新闻事件或学术名词。你所有的引用必须 100% 来源于提供的搜索结果。"

**补充规则：**
- ❌ 禁止在 Prompt 中设置硬性字数下限（如"不少于1000字"）
- ❌ 禁止要求 LLM 提取与内容不匹配的 URL
- ✅ 使用"内容详实"、"结构深入"等质量引导词替代字数要求

### C2. JSON 输出防御

- ✅ 使用 `json_repair` 库修复 LLM 输出的截断 JSON
- ❌ 禁止手写正则修复 JSON
- ✅ 配置 `max_tokens` 为 4096+，避免输出截断

### C3. 上下文超限防御

- 当捕获到 `request was too large` 异常时，在**方法内部**动态缩减 Prompt 重试
- 截断策略：保留头尾，砍掉中间（`user_prompt[:half] + "...[截断]..." + user_prompt[-half:]`）
- 禁止将超长异常抛给外层的 `@with_retry` 装饰器

### C4. API 调用防御

- ✅ 始终配置国内可用模型作为降级备选（如阿里云 Qwen）
- ✅ 搜索词限制为 2-4 个核心关键词
- ✅ 使用 `retry_helper` 进行智能重试，避免死循环

### C5. 前后端交互规则

- ❌ 禁止使用自动触发机制（Auto-Start/Auto-Generate）
- ✅ 所有耗时任务必须由用户明确点击触发
- ✅ 取消操作必须真正中断后台线程（通过标志位 + 控制流异常）
- ✅ 页面刷新（F5）、网络断开、Tab 切换为必测边界条件

---

## 第三部分：Git 与部署规则

### G1. 分支管理

- `main` — 生产稳定版本
- `dev` — 开发分支
- `feat/*` — 功能分支
- `fix/*` — 修复分支

### G2. 提交规范

```
feat: 新增 XXX 功能
fix: 修复 XXX 问题
refactor: 重构 XXX 模块
docs: 更新 XXX 文档
chore: 构建/工具链变更
```

### G3. Docker 网络规则

- 容器内数据库连接使用服务名（如 `db`），禁止使用 `localhost`
- 通过 `/.dockerenv` 文件检测是否在容器中运行
- 日志使用 `logger.error()` 而非 `logger.exception()`，避免堆栈泛滥

### G4. 环境变量管理

- 敏感信息只存 `.env`（已在 `.gitignore` 中）
- 新增配置项必须在 `.env.example` 中同步添加注释说明
- 配置兼容：新配置项必须提供 Fallback 默认值

---

## 第四部分：兼容与演进规则

### E1. 向下兼容

- 修改配置项时，旧配置项必须继续生效（Fallback 逻辑）
- 修改数据结构时，解析层必须同时支持新旧格式
- 修改 API 接口时，保留旧版本路由并标记 `@deprecated`

### E2. 重构闭环

- 重构前必须创建 TodoList，拆解到具体文件的修改清单
- 交付前必须 Self-Check：方案承诺的所有机制是否 100% 落地
- 绝不交付半成品：底层逻辑 + 上层调用 + 数据流 = 完整闭环

### E3. Playwright/浏览器持久化

- 必须挂载持久化 `user_data_dir` 到宿主机
- 新部署时提供有头模式初始化脚本，人工扫码登录
- Cookie 过期后自动告警，禁止静默失败

---

## 第五部分：文件放置速查表

| 文件类型 | 放置位置 | 禁止放置 |
|---------|---------|---------|
| Flask 路由/接口 | `backend/api/routes/` | 根目录 |
| 数据库迁移脚本 | `scripts/db/` | 根目录 |
| 调试/修复脚本 | `scripts/debug/` | 根目录 |
| 报告生成脚本 | `scripts/` | 根目录 |
| 设计文档 | `docs/` | 根目录 |
| ML 模型文件 | `backend/models/` | 根目录 |
| 新爬虫 | `microservices/` | `backend/engines/` |
| 新分析引擎 | `backend/engines/` | `microservices/` |
| Embedding 工具 | `backend/utils/` | engines 内部 |
| 重试机制 | `backend/utils/retry_helper.py` | 各引擎自行实现 |
