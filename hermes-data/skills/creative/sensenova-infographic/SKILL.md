---
name: sensenova-infographic
description: SenseNova U1 信息图生成 — 将文本/数据/文档直接转换为信息图。触发条件：用户要求生成信息图、infographic，或需要将内容可视化的场景。结合 baoyu-infographic skill 使用效果最佳。
---

# SenseNova U1 信息图生成

## 核心定位

**SenseNova U1 Fast** 是商汤 SenseNova 平台的多模态图像生成模型，专为信息图（Infographics）设计，支持 **11种宽高比**，可生成高密度信息大图。

- API平台：https://platform.sensenova.cn
- 文档：https://platform.sensenova.cn/docs
- 模型ID：`sensenova-u1-fast`
- 独立端点：`POST /v1/images/generations`（不是 chat/completions）

## 前置条件

1. 在 [SenseNova 控制台](https://platform.sensenova.cn/console/keys) 注册账号并创建 API Key（`sk-` 开头）
2. 设置环境变量 `SENSENOVA_API_KEY`，或在 `.env` 中配置
3. 当前环境已安装 `requests` 库（`pip install requests -q`）

## 使用方式

### 方式一：通过 `image_generate` 工具（推荐）

配置 `config.yaml` 后，`image_generate` 工具自动路由到 SenseNova：

```yaml
image_gen:
  provider: sensenova
  sensenova:
    # API key via SENSENOVA_API_KEY env var
    pass
```

```python
# 提示词工程（参考 baoyu-infographic skill）
prompt = """
A infographic poster showing [TOPIC] in a [STYLE] style.

Layout: [LAYOUT DESCRIPTION]
Sections:
- [Section 1]: [key data point]
- [Section 2]: [key data point]
...

Style requirements:
- Clean, readable typography
- Data visualizations with clear labels
- Minimalist color palette
- High information density
"""
```

### 方式二：直接调用 Provider

```python
from agent.image_gen_registry import get_active_provider

provider = get_active_provider()
result = provider.generate(
    prompt="A clean infographic about...",
    aspect_ratio="landscape"   # or "portrait", "square", "4:3", "16:9"...
)
print(result['image'])   # URL
print(result['success'])
```

### 方式三：直接 HTTP 调用

```python
import requests

resp = requests.post(
    "https://token.sensenova.cn/v1/images/generations",
    headers={"Authorization": "Bearer sk-xxxxx"},
    json={
        "model": "sensenova-u1-fast",
        "prompt": "A modern infographic about...",
        "size": "2752x1536",   # 16:9
        "n": 1
    },
    timeout=120
)
image_url = resp.json()["data"][0]["url"]
```

## 支持的宽高比

| 名称 | 尺寸 | 比例 |
|------|------|------|
| `landscape` | 2752×1536 | **16:9** |
| `square` | 2048×2048 | 1:1 |
| `portrait` | 1536×2752 | 9:16 |
| 2:3 | 1664×2496 | 2:3 |
| 3:2 | 2496×1664 | 3:2 |
| 3:4 | 1760×2368 | 3:4 |
| 4:3 | 2368×1760 | 4:3 |
| 4:5 | 1824×2272 | 4:5 |
| 5:4 | 2272×1824 | 5:4 |
| 21:9 | 3072×1376 | 21:9 |
| 9:21 | 1344×3136 | 9:21 |

**推荐信息图宽高比**：`landscape`(16:9) 或 `portrait`(9:16)

## 工作流程（结合 baoyu-infographic）

```
baoyu-infographic（内容结构化）
    ↓
structured-content.md + prompts/infographic.md
    ↓
SenseNova U1 Fast（image_generate 工具）
    ↓
infographic.png → 推送给佳哥
```

**推荐组合**：
- 布局（baoyu-infographic）：`dense-modules` / `bento-grid` / `dashboard`
- 风格：详细描述（SenseNova 支持高质量文本渲染）
- 宽高比：`landscape`（16:9）或 `portrait`（9:16）

## 提示词技巧

SenseNova U1 对提示词的理解能力强，但信息图需要：

```
[主题标题]
一句话概括的核心洞察

模块1: [模块标题]
- 数据点1: [具体数值]
- 数据点2: [具体数值]

模块2: [模块标题]
- [可视化描述]

风格: [具体描述，如"Museum infographic style, vintage paper texture, serif fonts"]
```

**关键要点**：
- 明确指定字体风格（serif/sans-serif）
- 指出背景偏好（white/minimal/dark）
- 说明图表类型（bar chart/pie chart/timeline）
- 提及信息密度（high-density / clean-minimal）

## 错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `auth_error` | API Key 无效 | 检查 `SENSENOVA_API_KEY` 是否正确 |
| `network_error` | 网络超时 | 增加 timeout 或检查网络 |
| `api_error 400` | Prompt 过长 | 缩短 prompt（max 4096 tokens） |
| `api_error 429` | 频率超限 | 等待后重试（限制：1500次/5小时） |
| Provider not registered | 插件未加载 | 重启 hermes-agent |

## 速率限制

- **SenseNova U1 Fast**：1500 次/5小时
- 注意与 `sensenova-6.7-flash-lite`（文本模型）共享限额
