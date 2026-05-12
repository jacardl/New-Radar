---
name: wsl-windows-filesystem
description: WSL2 访问 Windows 宿主机文件系统 (D:\ 等) 的挂载机制和限制
category: devops
---

# WSL2 访问 Windows 宿主机文件系统

## 当前环境的挂载机制

```
D:\ → /app/.env (9p + drvfs)
```

**关键发现：**
- `/app/.env` 本身是 Windows 的 `.env` 文件，**不是目录**
- 这导致 `mkdir /app/.env/Users/xxx` 和 `cp -r xxx /app/.env/yyy` 失败
- 挂载参数：`aname=drvfs;path=D:\\;uid=0;gid=0;metadata;symlinkroot=/mnt/host/`

## ✅ 正确方式：通过 /mnt/host/ 访问

**`/mnt/host/` 是挂载的 `symlinkroot`，才是真正的 Windows 文件系统入口！**

```bash
# 验证路径
ls /mnt/host/          # → Users
ls /mnt/host/Users/     # → New Radar
ls /mnt/host/Users/New Radar/

# 直接复制项目到 D:\Users\New Radar\
cp -r /tmp/open-design "/mnt/host/Users/New Radar/"
```

| 操作 | 结果 |
|------|------|
| `ls /app/.env` | ❌ 列出 `.env` 文件内容（不是目录） |
| `mkdir -p /app/.env/Users/xxx` | ❌ Not a directory |
| `ls /mnt/host/` | ✅ 列出 D:\ 根目录 |
| `cp -r xxx /mnt/host/Users/New Radar/` | ✅ 成功复制到 D:\Users\New Radar\ |

## 已知问题

| 操作 | 结果 | 原因 |
|------|------|------|
| `ls /app/.env` | 列出 .env 文件内容 | 9p 映射的是文件而非目录 |
| `mkdir -p /app/.env/Users/New Radar` | Not a directory | 无法在文件上创建子目录 |
| `git clone xxx /app/.env/repo` | 失败 | 同上 |

## 教训

- **不要假设** `/app/.env` 是可写的目录入口
- **正确方式**：使用 `/mnt/host/` 而非 `/app/.env/` 访问 Windows 文件
- `symlinkroot=/mnt/host/` 在 9p 挂载参数中，指明了真正的 Windows 根目录
