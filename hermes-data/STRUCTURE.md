# Hermes Agent 文件夹结构说明

> 最后更新：2026-05-10 | 小艾玛整理

---

## 一级目录总览

```
/app/.hermes/                         ← HERMES HOME（~根目录）
├── config.yaml                       配置文件
├── .env                              API密钥（不上传）
├── SOUL.md                           人格定义
│
├── memories/                         持久记忆（小艾玛的脑子）
│   ├── MEMORY.md                     工作规范、环境事实、工具经验
│   └── USER.md                       用户画像（佳哥的偏好习惯）
│
├── skills/                           用户级 Skills（可写）
│   ├── .hub/                         Hub 缓存（索引、锁定、审计日志）
│   ├── .bundled_manifest             已安装技能清单（含哈希）
│   ├── .usage.json                   技能使用统计
│   ├── web/                          网页抓取类（scrapling / obscura / lightpanda）
│   ├── competitor-discovery/         竞品识别
│   ├── skill-creator/                技能创建
│   ├── feeds/
│   ├── data-science/
│   │   └── sentiment-data-collection/ 舆情数据采集
│   └── ...（共32个分类，与内置技能互补）
│
├── hermes-agent/skills/              内置 Skills（只读模板库）
│   ├── index-cache/                  已迁移至 ~/.hermes/cache/skills_index-cache/
│   └── apple / creative / github / ...（系统自带，参考用）
│
├── hermes-agent/optional-skills/     可选 Skills（需手动启用）
│   └── blockchain / finance / health / security / ...
│
├── sessions/                          会话历史（可搜索）
├── logs/                              日志文件
├── cache/                             缓存
│   ├── documents/                    文档缓存
│   ├── images/                       图片缓存
│   └── skills_index-cache/           技能索引缓存（已迁移）
│
├── final_reports/                    用户产出目录（Windows 可直接访问）
│   └── [项目名]-GEO/
│       ├── urls/                     数据源 URL 列表
│       └── report/                   完整分析报告
│
├── cron/output/                      定时任务产出
├── checkpoints/                      模型检查点
├── platforms/                        平台配对数据
│
├── kanban.db                         看板数据库
├── state.db                          核心状态数据库
├── response_store.db                 回复缓存
└── models_dev_cache.json             模型缓存
```

---

## 核心规范

### 1. Skills 的三层结构

| 层级 | 路径 | 说明 |
|------|------|------|
| 用户自建 | `~/.hermes/skills/` | 可写，优先级最高 |
| 内置模板 | `hermes-agent/skills/` | 只读参考副本 |
| 可选扩展 | `hermes-agent/optional-skills/` | 需手动安装 |

**原则**：同名技能，用户级 > 内置级。用户自建技能覆盖内置版本。

### 2. Skills 命名规范

```
技能名（英文slug）/
├── SKILL.md              ← 必须：主文档（含 frontmatter）
├── references/           ← 可选：参考资料
├── templates/            ← 可选：模板文件
├── scripts/              ← 可选：脚本
└── assets/               ← 可选：图片/数据
```

### 3. 产出文档路径规范

所有用户可直接访问的产出，放 `~/.hermes/` 外：

```
/app/final_reports/         ← 用户文件根目录
└── [项目名]-GEO/            ← 每个项目单独文件夹
    ├── urls/               ← 数据源 URL 列表
    ├── report/             ← 完整报告
    └── data/               ← 原始数据（可选）
```

> 对应 Windows 路径：`D:\`（即 `/mnt/d/`）

### 4. 缓存清理规范

```
~/.hermes/cache/           可随时清空，不影响持久数据
~/.hermes/logs/            保留最近30天
~/.hermes/sessions/        保留最近7天（重要会话可置顶）
```

### 5. 禁止变动的文件

- `config.yaml` — 修改需通过 `hermes config set` 而非直接编辑
- `state.db` / `kanban.db` — SQLite 运行时数据库，直接编辑会损坏
- `.env` — API 密钥文件

---

## 当前Skills清单（用户级 32 个分类）

```
/app/.hermes/skills/
├── apple                       Apple 生态（Notes/Reminders/FindMy/iMessage）
├── autonomous-ai-agents        AI Agent 编排（Claude Code/Codex/OpenCode）
├── competitor-discovery        竞品识别（AI回答中高精度识别目标品牌）
├── creative                    创意生成（ASCII艺术/设计/漫画/视频/音乐）
├── data-science                数据科学（Jupyter/人群画像/舆情采集）
├── devops                      DevOps（Kanban/Webhook/WSL）
├── diagramming                 图表（Excalidraw/架构图）
├── dogfood                     探索性QA（web app bug发现）
├── domain                      域名相关
├── email                       邮件（IMAP/SMTP）
├── feeds                       RSS/Atom 订阅
├── gaming                      游戏（Minecraft/宝可梦）
├── gifs                        GIF 搜索
├── github                      GitHub 工作流
├── inference-sh               推理框架
├── mcp                         MCP 协议客户端
├── media                       媒体（Spotify/YouTube/GIF/音乐生成）
├── mlops                       机器学习运维
├── note-taking                笔记（Obsidian）
├── productivity                效率工具（飞书/Notion/Airtable/Linear/Maps）
├── red-teaming                红队攻防
├── research                    学术研究（arXiv/Blog/Polymarket）
├── skill-creator               技能创建（创建规范/参考文档）
├── smart-home                  智能家居（Philips Hue）
├── social-media                社媒平台（X/Twitter）
├── software-development        软件开发（调试/测试/代码审查）
├── web                          网页抓取（Scrapling/Obscura/LightPanda）⭐
└── yuanbao                     腾讯元宝
```

---

## 变更记录

| 日期 | 变更内容 |
|------|---------|
| 2026-05-10 | 清理重复报告文件（`数据源URL列表.md` / `GEO研究报告.md`） |
| 2026-05-10 | 迁移 `skills/.curator_state` → `HERMES_HOME/curator_state` |
| 2026-05-10 | 迁移 `hermes-agent/skills/index-cache/` → `~/.hermes/cache/skills_index-cache/` |
