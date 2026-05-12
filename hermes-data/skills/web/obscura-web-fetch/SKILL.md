---
name: obscura-web-fetch
description: 使用 obscura 无头浏览器进行大规模网页抓取 — 轻量（30MB）、快速（85ms）、内置反检测。优先于普通 web_fetch 使用。
category: web
---

# Obscura 网页抓取指南

## 简介
Obscura 是一个 Rust 编写的轻量级无头浏览器引擎，专门为 AI 代理和网页抓取设计。相比 Chrome：
- 内存：30MB vs 200MB+
- 启动：即时 vs ~2s
- 页面加载：85ms vs ~500ms
- 内置反指纹和追踪器拦截

## 系统要求
- GLIBC 2.38+（Linux）
- macOS / Windows 直接下载使用

## 安装

### 下载预编译二进制
```bash
# Linux
curl -LO https://github.com/h4ckf0r0day/obscura/releases/download/v0.1.1/obscura-x86_64-linux.tar.gz
tar xzf obscura-x86_64-linux.tar.gz

# Windows
# 下载 obscura-x86_64-windows.zip

# macOS
curl -LO https://github.com/h4ckf0r0day/obscura/releases/download/v0.1.1/obscura-aarch64-macos.tar.gz
```

### 从源码编译（需要 Rust 1.75+）
```bash
git clone https://github.com/h4ckf0r0day/obscura.git
cd obscura
cargo build --release

# 启用 stealth 模式（反检测 + 追踪器拦截）
cargo build --release --features stealth
```

## 常用命令

### 单页面抓取
```bash
# 获取页面标题
obscura fetch https://example.com --eval "document.title"

# 提取所有链接
obscura fetch https://example.com --dump links

# 渲染 JS 并获取 HTML
obscura fetch https://example.com --dump html

# 等待动态内容加载
obscura fetch https://example.com --wait-until networkidle0
```

### 批量抓取
```bash
obscura scrape url1 url2 url3 \
  --concurrency 25 \
  --eval "document.querySelector('h1').textContent" \
  --format json
```

### 启动 CDP 服务器（配合 Puppeteer/Playwright）
```bash
obscura serve --port 9222

# Stealth 模式
obscura serve --port 9222 --stealth
```

## 当前环境限制
容器系统 GLIBC 版本为 2.36，不满足 obscura 要求的 2.38+。如需使用：
1. 在 Windows 本地运行（下载 Windows 版本）
2. 或在兼容的 Linux 环境中使用
