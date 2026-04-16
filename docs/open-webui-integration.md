# Open WebUI 集成实施指南

> **版本：** 1.0 | **日期：** 2026-04-15
> **目标：** 将 Open WebUI 作为 New Radar 的对话前端，通过 OpenAI 兼容 API 与后端交互

---

## 一、方案概述

### 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Open WebUI (Docker)                       │
│               http://localhost:3000                          │
│  聊天界面 / 历史记录 / 用户认证 / PWA / 语音输入             │
└──────────────────────┬────────────────────────────────────────┘
                       │ OpenAI Chat Completions API
                       │ POST /v1/chat/completions
┌──────────────────────▼────────────────────────────────────────┐
│                 New Radar Backend (Flask)                      │
│                  http://localhost:5000                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  /v1/chat/completions   ← Hermes Agent API Server      │   │
│  │  (hermes-agent gateway/platforms/api_server.py)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Hermes Agent（多引擎编排 / 防幻觉 / 工具调用）                │
│                                                                  │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                  │
│  │Insight │ │ Media  │ │ Query  │ │ Report │                  │
│  │ Engine │ │ Engine │ │ Engine │ │ Engine │                  │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘                  │
│      └──────────┴──────────┴──────────┴──────────┘           │
│                         │                                      │
│              PostgreSQL + pgvector                              │
└─────────────────────────┬──────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│                 Microservices (数据采集层)                      │
│  last30days / MediaCrawler / MindSpider / web-access          │
└────────────────────────────────────────────────────────────────┘
```

### 关键事实

- ✅ **Hermes Agent 已有完整的 `/v1/chat/completions` 端点**（`gateway/platforms/api_server.py`）
- ✅ **需要将其集成到 Flask 主应用中**
- ✅ **Open WebUI 只需一个 OpenAI 兼容的 `/v1/chat/completions` 端点即可工作**
- ✅ **Open WebUI 支持 SSE 流式响应**

---

## 二、实施步骤

### Phase 1：集成 Hermes API Server 到 Flask 主应用

**目标：** 在 `backend/app.py` 中加载 hermes-agent 的 API Server，使其可通过 `http://localhost:5000/v1/chat/completions` 访问。

#### 步骤 1.1：创建集成模块

```python
# backend/api/hermes_integration.py

from backend.frameworks.hermes_agent.gateway.platforms.api_server import HermesAPIServer
from backend.frameworks.hermes_agent.platforms import PlatformConfig
import logging

logger = logging.getLogger(__name__)

# 全局 API Server 实例
_api_server = None

def get_hermes_api_server():
    """获取或创建 Hermes API Server 实例"""
    global _api_server
    if _api_server is None:
        config = PlatformConfig(
            name="new-radar",
            platform_api_key="sk-hermes-local",  # 本地开发用任意值
            model="claude-sonnet-4-20250514",
            allowed_origins=["http://localhost:3000"],  # Open WebUI 地址
        )
        _api_server = HermesAPIServer(config)
        logger.info("Hermes API Server 初始化完成")
    return _api_server

def register_hermes_routes(app):
    """将 Hermes API Server 的路由注册到 Flask 应用"""
    api_server = get_hermes_api_server()

    # Hermes API Server 内部已经有这些端点：
    # - GET  /health      → 健康检查
    # - GET  /v1/models   → 模型列表
    # - POST /v1/chat/completions → 聊天补全
    # - GET  /v1/responses/{id}   → 获取响应
    # - DELETE /v1/responses/{id} → 删除响应

    async def wsgi_app(environ, start_response):
        """WSGI 适配器：将 Flask 请求转换为 aiohttp 请求"""
        from aiohttp import web
        from io import BytesIO

        # 转换 WSGI → aiohttp 请求
        method = environ['REQUEST_METHOD']
        path = environ['PATH_INFO']
        query = environ['QUERY_STRING']

        # 读取 body
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''

        # 构建 aiohttp Request
        message = web.Request.rel_url.make_internal_url(path)
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_key = key[5:].replace('_', '-')
                headers[header_key] = value

        # 调用 Hermes API Server
        request = ...  # 需要构建 aiohttp Request
        return await api_server.handle(request)

    # 挂载到 /api/v1 前缀
    app.wsgi_app = wsgi_app
    logger.info("Hermes API Server 已注册到 /api/v1")
```

#### 步骤 1.2：修改 backend/app.py

在 `backend/app.py` 末尾添加：

```python
# === Hermes Agent API Server 集成 ===
# 在现有路由之后添加

from backend.api.hermes_integration import register_hermes_routes

# 注册 Hermes API Server 路由
# 注意：Hermes API Server 使用独立的端口，我们通过反向代理方式集成
try:
    register_hermes_routes(app)
    app.logger.info("Hermes API Server 集成成功")
except Exception as e:
    app.logger.warning(f"Hermes API Server 未启用: {e}")
```

#### 步骤 1.3：验证集成

```bash
# 启动后端
python -m backend.app

# 测试端点
curl http://localhost:5000/v1/models
# 应返回可用模型列表

curl http://localhost:5000/health
# 应返回 {"status": "ok"}
```

---

### Phase 2：配置 Open WebUI

#### 步骤 2.1：启动 Open WebUI

```bash
# 方式 A：Docker 直接启动（推荐）
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main

# 方式 B：使用 docker-compose（推荐）
# 见下方 docker-compose.yml 更新
```

#### 步骤 2.2：在 Open WebUI 中配置 New Radar

1. 打开 **http://localhost:3000**
2. 首次访问时注册管理员账号
3. 点击左下角 **设置（Settings）**
4. 进入 **连接（Connections）** 标签
5. 找到 **OpenAI** 部分，配置：

```
API Base URL:  http://host.docker.internal:5000/v1
API Key:       sk-hermes-local  # 任意值，与 backend 配置一致
```

6. 点击保存

#### 步骤 2.3：验证连接

1. 在 Open WebUI 顶部模型选择器中，选择 `claude-sonnet-4-20250514`
2. 发送测试消息：`帮我分析一下"达巴水痕之地"游戏的舆情`
3. 如果看到流式响应返回，说明集成成功

---

### Phase 3：更新 docker-compose.yml

```yaml
version: '3.8'

services:
  # === New Radar 后端 ===
  backend:
    build: .
    container_name: new-radar-backend
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://radar:radar123@db:5432/newradar
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}
    volumes:
      - ./storage:/app/storage
      - ./backend:/app/backend
    depends_on:
      - db
    networks:
      - newradar-net

  # === Open WebUI 前端 ===
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    ports:
      - "3000:8080"
    environment:
      - OAI_API_BASE=http://backend:5000/v1
      - OAI_API_KEY=sk-hermes-local
      - WEBUI_AUTH=false  # 开发环境关闭认证，生产环境改为 true
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - open-webui-data:/app/backend/data
    depends_on:
      - backend
    networks:
      - newradar-net
    restart: unless-stopped

  # === PostgreSQL 数据库 ===
  db:
    image: ankane/pgvector:pg15
    container_name: newradar-db
    environment:
      - POSTGRES_USER=radar
      - POSTGRES_PASSWORD=radar123
      - POSTGRES_DB=newradar
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/db/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - newradar-net
    restart: unless-stopped

networks:
  newradar-net:
    driver: bridge

volumes:
  pgdata:
  open-webui-data:
```

---

### Phase 4：Open WebUI 定制（可选）

#### 定制欢迎消息

在 Open WebUI 管理面板 → 设置 → 定制 → 欢迎消息：

```markdown
# 🐙 New Radar 舆情分析助手

欢迎使用 New Radar！我可以帮你：
- 📊 分析品牌和产品的网络舆情
- 🔍 监控论坛和社交媒体的讨论热度
- 📈 生成深度舆情分析报告

**使用示例：**
- "帮我分析 XXX 品牌的最近舆情"
- "监控一下 XX 论坛的用户反馈"
- "生成一份 XX 产品的舆情周报"
```

#### 隐藏不需要的功能

Open WebUI 管理面板 → 设置 → 界面：
- 关闭 `语音输入`（如果不需要）
- 关闭 `图片上传`（如果不需要）
- 自定义 Logo 和主题色

---

## 三、开发调试

### 查看 Hermes API Server 日志

```bash
# 查看后端日志
docker compose logs -f backend

# 查看 Open WebUI 日志
docker compose logs -f open-webui
```

### 测试 OpenAI 兼容端点

```bash
# 测试 /v1/chat/completions（非流式）
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-hermes-local" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 测试 /v1/models
curl http://localhost:5000/v1/models \
  -H "Authorization: Bearer sk-hermes-local"
```

### 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| Open WebUI 连接失败 | CORS 跨域问题 | 检查 Hermes API Server 的 `allowed_origins` 配置 |
| 连接成功但无响应 | 模型未配置 | 在 Open WebUI 中确认选择了正确的模型 |
| SSE 流式中断 | 后端超时 | 增加 Hermes Agent 的超时配置 |
| 认证失败 | API Key 不匹配 | 确认 Open WebUI 和 backend 的 API Key 一致 |

---

## 四、后续优化

### 当前状态（Phase 1 完成后的基本可用版本）

- Open WebUI 作为对话前端 ✅
- Hermes Agent 处理对话并编排多引擎 ✅
- SSE 流式响应 ✅
- 基本的用户认证 ✅

### 优化方向

1. **Tools 集成**：在 Open WebUI 中注册 New Radar 的专用工具
   - 舆情查询工具（替代手动输入查询词）
   - 报告生成工具（直接生成 PDF 报告）
   - 数据源状态监控工具

2. **Webhook 告警**：当舆情出现重大变化时，通过 Open WebUI 推送通知

3. **多模型路由**：根据查询类型自动选择最合适的引擎/模型

4. **Vue 前端保留**：将 `frontend/` 改造为管理后台（爬虫管理、数据源配置等非对话功能）

---

## 五、技术参考

### 相关文件

| 文件 | 说明 |
|------|------|
| `backend/frameworks/hermes-agent/gateway/platforms/api_server.py` | Hermes API Server 实现（`/v1/chat/completions`） |
| `backend/api/hermes_integration.py` | 待创建：Flask 集成适配器 |
| `docker-compose.yml` | 待更新：添加 Open WebUI 服务 |
| `backend/app.py` | 待更新：注册 Hermes API Server 路由 |

### Hermes Agent API Server 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 可用模型列表 |
| `/v1/chat/completions` | POST | 聊天补全（支持 SSE 流式） |
| `/v1/responses/{id}` | GET | 获取已存储的响应 |
| `/v1/responses/{id}` | DELETE | 删除响应 |

### Open WebUI 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OAI_API_BASE` | OpenAI 兼容 API 地址 | `http://localhost:5000/v1` |
| `OAI_API_KEY` | API Key | `sk-any` |
| `WEBUI_AUTH` | 是否启用认证 | `true` |
| `WEBUI_NAME` | 应用名称 | `Open WebUI` |

---

*本指南为实施初稿，具体实现时可根据实际情况调整。*
