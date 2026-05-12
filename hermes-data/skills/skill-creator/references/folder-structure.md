# Hermes Agent 文件夹结构规范

> 建立时间：2026-05-10 | 来源：桂格麦片-GEO项目整理经验

---

## HERMES HOME 结构（`~/.hermes/`）

HERMES_HOME 是智能体的根目录，所有持久化数据都在此处。

```
~/.hermes/                        # Linux: /app/.hermes/  |  Windows: C:\Users\<user>\.hermes\
├── config.yaml                   # 主配置（通过 hermes config set 修改，不要直接编辑）
├── .env                          # API密钥（隔离存储，不上传）
├── SOUL.md                       # 人格定义
│
├── memories/                     # 持久记忆（小艾玛的脑子）
│   ├── MEMORY.md                # 工作规范、环境事实、工具经验
│   └── USER.md                  # 用户画像（偏好、习惯、忌讳）
│
├── skills/                      # 用户级 Skills（可写，优先级最高）
│   ├── .hub/                    # Hub 缓存（索引、锁定、审计）
│   ├── .bundled_manifest        # 已安装技能清单（含哈希）
│   ├── .usage.json              # 技能使用统计
│   ├── competitor-discovery/    # 用户自建技能示例
│   ├── skill-creator/
│   ├── web/
│   └── ...（按类别分组）
│
├── hermes-agent/                # 内置Skills源（只读参考副本）
│   └── skills/                  # 系统自带技能模板，不要直接修改
│
├── hermes-agent/optional-skills/  # 可选Skills（需手动启用）
│
├── sessions/                    # 会话历史
├── logs/                       # 日志（保留30天）
├── cache/                      # 缓存（可随时清空）
│   ├── documents/
│   ├── images/
│   └── skills_index-cache/      # 技能索引缓存
│
├── final_reports/              # 用户产出（对应Windows D:\，可直接访问）
│   └── [项目名]-GEO/
│       ├── urls/               # 数据源 URL 列表
│       ├── report/             # 完整分析报告
│       └── data/               # 原始数据（可选）
│
├── cron/output/                # 定时任务产出
├── kanban.db                   # 看板数据库
├── state.db                    # 核心状态数据库
└── response_store.db           # 回复缓存
```

---

## Skills 三层优先级

| 层级 | 路径 | 说明 |
|------|------|------|
| **用户自建** | `~/.hermes/skills/<name>/` | 可写，优先级最高 |
| **内置模板** | `hermes-agent/skills/<name>/` | 只读参考副本 |
| **可选扩展** | `hermes-agent/optional-skills/<name>/` | 需手动启用 |

**原则**：同名技能，用户级覆盖内置级。用户自建 > 内置模板 > 可选扩展。

---

## Skills 标准结构

```
<skill-name>/
├── SKILL.md                    # 必须：主文档（frontmatter + 内容）
├── agents/                     # 可选：UI元数据
│   └── openai.yaml
├── references/                 # 可选：参考资料（按需加载）
│   └── <topic>.md
├── templates/                  # 可选：模板文件（可复制修改）
│   └── <name>.<ext>
└── scripts/                    # 可选：脚本（可直接执行）
    └── <name>.<ext>
```

---

## 产出文档路径规范（GEO项目示例）

```
/app/final_reports/             ← 根目录（对应 Windows D:\）
└── <项目名>-GEO/
    ├── urls/
    │   └── <项目名>-GEO数据源URL列表.md    # 数据源清单
    ├── report/
    │   └── <项目名>-GEO研究报告.md         # 完整报告
    └── data/                                     # 原始数据（可选）
```

---

## 禁止变动的文件

- `config.yaml` — 通过 `hermes config set` 修改
- `state.db` / `kanban.db` — SQLite 运行时数据库
- `.env` — API 密钥文件

---

## 迁移记录（2026-05-10）

| 操作 | 原因 |
|------|------|
| `skills/.curator_state` → `HERMES_HOME/curator_state` | curator状态属于HERMES_HOME根，不属于skills子目录 |
| `hermes-agent/skills/index-cache/` → `~/.hermes/cache/skills_index-cache/` | 索引缓存属于cache目录，不是skills目录 |

---

## 清理规范

```
~/.hermes/cache/           可随时清空，不影响持久数据
~/.hermes/logs/            保留最近30天
~/.hermes/sessions/        保留最近7天（重要会话可置顶）
```
