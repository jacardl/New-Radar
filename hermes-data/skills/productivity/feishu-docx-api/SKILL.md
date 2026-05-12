---
name: feishu-docx-api
description: Write content to Feishu/Lark Docx documents via REST API — authentication, block structure, common pitfalls
---

# Feishu Docx API 写入指南

## 认证
```python
import urllib.request, json
creds = {}
with open('/app/.hermes/.env', 'r') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            creds[k] = v
app_id = creds.get('FEISHU_APP_ID', '')
app_secret = creds.get('FEISHU_APP_SECRET', '')
url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
data = json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, timeout=10) as resp:
    token = json.loads(resp.read()).get('tenant_access_token')
```

## 添加 Block 到文档
**关键发现：**
- 根 block ID = 文档 token（不是 "0"）
- 添加路径：`/documents/{doc_token}/blocks/{doc_token}/children`
- 分隔符 block（block_type=22）会返回 HTTP 400 invalid param，**不要用**

```python
from urllib.error import HTTPError
import time

def add_children(children, doc_token, token, retry=2):
    add_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children'
    for attempt in range(retry):
        payload = json.dumps({"children": children}).encode('utf-8')
        req = urllib.request.Request(add_url, data=payload, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
            time.sleep(2)
    return {"code": -1}
```

## Block 类型对照表

| 类型 | block_type | 写法 |
|-----|-----------|------|
| 普通文本 | 2 | `{"block_type": 2, "text": {"elements": [{"text_run": {"content": "...", "text_element_style": {}}}], "style": {}}}` |
| 标题1 | 3 | `{"block_type": 3, "heading1": {"elements": [...], "style": {}}}` |
| 标题2 | 4 | `{"block_type": 4, "heading2": {"elements": [...], "style": {}}}` |
| 标题3 | 5 | `{"block_type": 5, "heading3": {"elements": [...], "style": {}}}` |
| 无序列表 | 12 | `{"block_type": 12, "bullet": {"elements": [...], "style": {"indent_level": 1}}}` |
| 有序列表 | 13 | `{"block_type": 13, "ordered": {"elements": [...], "style": {"indent_level": 1}}}` |
| 分隔符 | 22 | ❌ HTTP 400，不要使用 |

## Helper 函数
```python
def h1(content): return {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {}}}
def h2(content): return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {}}}
def h3(content): return {"block_type": 5, "heading3": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {}}}
def p(content): return {"block_type": 2, "text": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {}}}
def bullet(content): return {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {"indent_level": 1}}}
def ordered(content): return {"block_type": 13, "ordered": {"elements": [{"text_run": {"content": content, "text_element_style": {}}}], "style": {"indent_level": 1}}}
```

## 添加文档协作者

```python
# 添加协作者（正确方式：GET + query params，不是 POST body）
def add_doc_member(doc_token, token, member_email, perm="full_access"):
    add_url = (f'https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_token}/members'
               f'?type=docx&need_notification=false'
               f'&member_type=email&member_id={urllib.parse.quote(member_email)}&perm={perm}')
    req = urllib.request.Request(add_url, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# ❌ 错误方式（POST body）：返回 1770001 invalid param
payload = json.dumps({"member_type": "email", "member_id": email, "perm": "full_access"})
```

## 查询用户是否为租户成员

```python
# 通过邮箱查询 open_id（只有 tenant 内用户才有 user_id）
def get_user_open_id(token, email):
    search_url = 'https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id?user_id_type=open_id'
    data = json.dumps({"emails": [email]}).encode('utf-8')
    req = urllib.request.Request(search_url, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        user_list = result.get('data', {}).get('user_list', [])
        if user_list and user_list[0].get('user_id'):
            return user_list[0]['user_id']
    return None  # 用户不在租户内

# 注意：返回 email 但无 user_id = 用户存在但未激活飞书账号
```

## 经验总结

1. **不要用 block_type=22（分隔符）**——会返回 1770001 invalid param，用空文本段落代替
2. 每次批量写入后建议 `time.sleep(1)` 避免限流
3. 添加 children 的正确目标是 `{doc_token}/blocks/{doc_token}/children`，不是 `0/children`
4. 列表缩进通过 `style.indent_level` 控制（从1开始）
5. `text_element_style` 为空字典 `{}` 表示无特殊样式
6. 文档 token 可从飞书文档 URL 中获取：`https://feishu.cn/docx/{token}`
7. **添加协作者用 GET + query params**，不是 POST body
8. 用户不在飞书租户内时，无法通过 API 加权限——让用户通过「申请访问权限」解决
9. **批量插入有50块限制**——单次 `add_children` 超过50块会返回 99992402 field validation failed。大量内容必须分批发送。
10. **删除块返回403 Forbidden**——`DELETE /documents/{doc_id}/blocks/{block_id}` 在此 tenant 下无权限。如需重写内容，创建新文档而非删除旧内容。
11. **WSL 9p 挂载 Windows 文件系统的坑**——`D:\` 挂载到 `/app/.env` 但它是一个文件而非目录。`/mnt/d` 不存在。Windows 文件访问需要通过其他方式（如 cmd.exe 或确认挂载方式）。
