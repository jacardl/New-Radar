#!/usr/bin/env python3
"""
直隶按察使 · 公众号草稿发布脚本

用法:
  # 标准发布（无封面图）
  python3 publish_zhili.py "<title>" "<author>" "<digest>" "<html_content>"

  # 自动生成封面图（Sensenova，备选 MiniMax）+ 发布
  python3 publish_zhili.py --title "<title>" --author "<author>" --digest "<digest>" --content "<html>" --cover-prompt "<prompt>"

  # 跳过封面图
  python3 publish_zhili.py "<title>" "<author>" "<digest>" "<html_content>" --skip-cover
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request

try:
    import requests
except ImportError:
    requests = None

# ============ 配置路径 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SKILL_DIR, "references/config.md")
TOOLS_PATH = os.path.join(os.path.dirname(SKILL_DIR), "../workspace/TOOLS.md")
DEFAULT_COVER_PATH = "/tmp/cover-thumb.jpg"


# ============ 凭证加载 ============

def load_config():
    """从 config.md 中解析微信凭证"""
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: 配置文件不存在: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, encoding='utf-8') as f:
        content = f.read()
    config = {}
    for line in content.splitlines():
        if ":" in line and not line.startswith("#"):
            key, val = line.split(":", 1)
            config[key.strip()] = val.strip()
    required = ["APPID", "APPSECRET"]
    for k in required:
        if k not in config:
            print(f"ERROR: 配置文件缺少字段: {k}")
            sys.exit(1)
    return config


def load_sensenova_key():
    """从 TOOLS.md 读取 Sensenova API Key"""
    path = os.path.expanduser(TOOLS_PATH)
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # 找 Sensenova API Key
        for line in content.splitlines():
            if "sk-uRDC" in line:
                key = line.split("sk-uRDC")[1].split('"')[0].split("'")[0].split()[0]
                return "sk-uRDC" + key
        return ""
    except:
        return ""


def load_minimax_key():
    """从 OpenClaw 全局配置读取 MiniMax API Key"""
    import re
    openclaw_config_paths = [
        "/home/gem/workspace/agent/openclaw.json",
        os.path.expanduser("~/.openclaw/openclaw.json"),
    ]
    for path in openclaw_config_paths:
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    raw = f.read()
                m = re.search(
                    r'"minimax"\s*:\s*\{.*?"apiKey"\s*:\s*"([^"]+)"',
                    raw, re.DOTALL
                )
                if m:
                    key = m.group(1)
                    if key and key != "__OPENCLAW_REDACTED__":
                        return key
            except Exception:
                pass
    return os.environ.get("MINIMAX_API_KEY", "")


# ============ 封面图生成（Sensenova 首选，MiniMax 备选）============

def generate_cover(prompt: str, output_path: str = DEFAULT_COVER_PATH) -> str:
    """
    生成封面图：Sensenova 首选（TOOLS.md 配置），MiniMax 备选
    1. 生成 2048x2048 图片
    2. 尝试裁剪为 900x900（如 Pillow 可用）
    3. 保存为 JPEG
    返回本地文件路径
    """
    # 优先用 Sensenova
    sensenova_key = load_sensenova_key()
    if sensenova_key:
        print(f"[INFO] 使用 Sensenova 生成封面图...")
        result = _generate_sensenova(prompt, output_path)
        if result:
            return result
        print("[WARN] Sensenova 失败，尝试 MiniMax...")

    # 备选 MiniMax
    minimax_key = load_minimax_key()
    if minimax_key:
        print(f"[INFO] 使用 MiniMax 生成封面图...")
        result = _generate_minimax(prompt, output_path)
        if result:
            return result
        print("[WARN] MiniMax 也失败了")

    print("[WARN] 无可用封面图生成服务，跳过封面图")
    return ""


def _generate_sensenova(prompt: str, output_path: str) -> str:
    """调用 Sensenova API 生成封面图"""
    api_key = load_sensenova_key()
    url = "https://token.sensenova.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sensenova-u1-fast",
        "prompt": prompt,
        "size": "2048x2048",
        "n": 1,
    }

    for attempt in range(3):
        try:
            if requests:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
            else:
                payload_bytes = json.dumps(payload).encode("utf-8")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
                resp = urllib.request.urlopen(req, timeout=120, context=ctx)

            data = resp.json()
            if "data" in data and data["data"]:
                img_url = data["data"][0].get("url") or data["data"][0].get("image_url")
                if img_url:
                    print("[OK] Sensenova 封面图生成成功")
                    return _download_and_crop(img_url, output_path)
            print(f"[WARN] Sensenova 失败: {data}")
        except Exception as e:
            print(f"[WARN] Sensenova 请求异常: {e}")
        if attempt < 2:
            time.sleep(3)
    return ""


def _generate_minimax(prompt: str, output_path: str) -> str:
    """调用 MiniMax image-01 API 生成封面图"""
    api_key = load_minimax_key()
    if not api_key:
        return ""

    url = "https://api.minimaxi.com/v1/image_generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "image-01",
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "response_format": "url",
    }

    for attempt in range(3):
        try:
            if requests:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                data = resp.json()
            else:
                return ""
            if "data" in data and data["data"]:
                img_url = (
                    data["data"].get("image_urls", [None])[0]
                    or data["data"].get("url", "")
                    or (data["data"][0].get("url") if isinstance(data["data"], list) else "")
                )
                if img_url:
                    print("[OK] MiniMax 封面图生成成功")
                    return _download_and_crop(img_url, output_path)
            print(f"[WARN] MiniMax 失败: {data}")
        except Exception as e:
            print(f"[WARN] MiniMax 请求异常: {e}")
        if attempt < 2:
            time.sleep(3)
    return ""


def _download_and_crop(img_url: str, output_path: str) -> str:
    """下载图片并裁剪为 900x900"""
    # 下载
    print("[INFO] 下载封面图...")
    try:
        if requests:
            r = requests.get(img_url, timeout=120)
            raw_path = output_path.replace(".jpg", "_raw.jpg")
            with open(raw_path, "wb") as f:
                f.write(r.content)
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw_path = output_path.replace(".jpg", "_raw.jpg")
            with urllib.request.urlopen(img_url, timeout=120, context=ctx) as resp:
                with open(raw_path, "wb") as f:
                    f.write(resp.read())
        print(f"[OK] 图片已下载: {raw_path}")
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        return ""

    # 裁剪为 900x900
    try:
        from PIL import Image
        img = Image.open(raw_path)
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img_cropped = img.crop((left, top, left + side, top + side))
        img_cropped = img_cropped.resize((900, 900), Image.LANCZOS)
        img_cropped.convert("RGB").save(output_path, "JPEG", quality=85)
        print(f"[OK] 封面图已裁剪并保存: {output_path} (900×900)")
        os.remove(raw_path)
        return output_path
    except ImportError:
        print("[WARN] Pillow 未安装，使用原始图片")
        # 直接用 raw 图作为 JPEG
        try:
            img = Image.open(raw_path)
            img.convert("RGB").save(output_path, "JPEG", quality=85)
            return output_path
        except:
            return raw_path
    except Exception as e:
        print(f"[WARN] 裁剪失败: {e}，使用原始图片")
        try:
            img = Image.open(raw_path)
            img.convert("RGB").save(output_path, "JPEG", quality=85)
            return output_path
        except:
            return raw_path


# ============ 微信 API ============

def get_access_token(appid, appsecret):
    """获取 Access Token，带自动重试"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={appsecret}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "access_token" in result:
                    print(f"[OK] Access Token 获取成功")
                    return result["access_token"]
                else:
                    print(f"[WARN] Access Token 获取失败: {result.get('errmsg', result)}")
                    if attempt < 2:
                        time.sleep(5)
        except Exception as e:
            print(f"[WARN] 请求异常: {e}")
            if attempt < 2:
                time.sleep(5)
    print(f"ERROR: Access Token 获取失败")
    sys.exit(1)


def upload_article_image(token, image_path):
    """
    上传文章内容图片到微信素材库，返回公网 URL。
    ⚠️ 必须用此接口，不能用 add_material（返回 media_id 无法在草稿中渲染）
    """
    if not os.path.exists(image_path):
        print(f"[ERROR] 图片不存在: {image_path}")
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"
    boundary = "----PythonFormBoundary123456789"
    with open(image_path, 'rb') as f:
        file_data = f.read()

    fname = os.path.basename(image_path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{fname}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('User-Agent', 'Mozilla/5.0')

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            resp = json.loads(r.read())
            if 'url' in resp:
                print(f"[OK] 文章图片上传成功: {resp['url'][:60]}...")
                return resp['url']
            else:
                print(f"[ERROR] 文章图片上传失败: {resp}")
                return None
    except Exception as e:
        print(f"[ERROR] 文章图片上传异常: {e}")
        return None


def upload_thumb_material(token, thumb_path):
    """上传封面图到永久素材（缩略图），返回 media_id"""
    if not os.path.exists(thumb_path):
        print(f"[ERROR] 封面图不存在: {thumb_path}")
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=thumb"
    boundary = "----PythonFormBoundary7MA4YWxkTrZu0gW"
    with open(thumb_path, "rb") as f:
        img_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + img_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "media_id" in result:
                print(f"[OK] 封面图上传成功: {result['media_id']}")
                return result["media_id"]
            else:
                print(f"[ERROR] 封面图上传失败: {result}")
                return None
    except Exception as e:
        print(f"[ERROR] 封面图上传异常: {e}")
        return None


def check_article_images(content):
    """发布前强制检查：HTML 正文中必须包含 mmbiz 图片，否则拒绝发布"""
    if 'mmbiz' not in content:
        print("[ERROR] 发布被拦截：HTML 正文中未找到任何 mmbiz 图片！")
        print("       必须先上传项目截图到 WeChat（media/uploadimg），获取 mmbiz URL 后嵌入 HTML。")
        print("       检查步骤：")
        print("       1. 下载项目截图/GIF 到 /tmp")
        print("       2. 用 upload_article_image() 上传，获取 mmbiz URL")
        print("       3. 在 HTML 中 <img src=\"mmbiz_url\" ...> 嵌入")
        print("       4. 重新执行发布")
        sys.exit(1)
    # 统计图片数量
    count = content.count('mmbiz')
    print(f"[INFO] 检测到 {count} 张正文图片（mmbiz URL）")


def create_draft(token, title, author, digest, content, thumb_media_id, original=1):
    """创建草稿"""
    payload = {
        "articles": [{
            "title": title,
            "author": author,
            "digest": digest,
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
            "original": original,
        }]
    }
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "media_id" in result:
                print(f"[OK] 草稿创建成功!")
                print(f"     media_id: {result['media_id']}")
                return result["media_id"]
            else:
                print(f"[ERROR] 草稿创建失败: {result}")
                return None
    except Exception as e:
        print(f"[ERROR] 草稿创建异常: {e}")
        return None


# ============ 入口 ============

def main():
    parser = argparse.ArgumentParser(description="直隶按察使 · 公众号草稿发布脚本")
    parser.add_argument("title", nargs="?", help="文章标题")
    parser.add_argument("author", nargs="?", help="作者（建议≤2个中文字，超长会报45003错误）")
    parser.add_argument("digest", nargs="?", help="摘要")
    parser.add_argument("content", nargs="?", help="HTML 内容")
    parser.add_argument("--skip-cover", action="store_true", help="跳过封面图")
    parser.add_argument("--cover-only", action="store_true", help="仅生成封面图")
    parser.add_argument("--cover-prompt", type=str, default="", help="封面图生成 Prompt")
    parser.add_argument("--cover-path", type=str, default="", help="指定本地封面图路径")
    args = parser.parse_args()

    title = args.title or ""
    author = args.author or ""
    digest = args.digest or ""
    content = args.content or ""

    # ⚠️ 强制 UTF-8 读取，防止中文乱码
    # HTML 内容如从文件读取，必须 open(..., encoding='utf-8')

    cover_path = DEFAULT_COVER_PATH

    # ============ 封面图处理 ============
    if args.cover_only:
        if args.cover_prompt:
            path = generate_cover(args.cover_prompt, DEFAULT_COVER_PATH)
            if path:
                print(f"========== 封面图生成完成 ==========")
                print(f"路径: {path}")
            else:
                print("封面图生成失败")
                sys.exit(1)
        else:
            print("ERROR: --cover-only 需要配合 --cover-prompt")
            sys.exit(1)
        return

    if args.cover_path:
        cover_path = args.cover_path
        if not os.path.exists(cover_path):
            print(f"ERROR: 封面图不存在: {cover_path}")
            sys.exit(1)
        print(f"[INFO] 使用指定封面图: {cover_path}")
    elif args.cover_prompt:
        path = generate_cover(args.cover_prompt, DEFAULT_COVER_PATH)
        if path:
            cover_path = path
        else:
            print("[WARN] 封面图生成失败，将跳过封面上传")
    elif not args.skip_cover and os.path.exists(DEFAULT_COVER_PATH):
        print(f"[INFO] 使用已存在的封面图: {DEFAULT_COVER_PATH}")
        cover_path = DEFAULT_COVER_PATH
    elif args.skip_cover:
        print("[INFO] 跳过封面图")
    else:
        print("[WARN] 未找到封面图，跳过封面上传")

    # ============ 发布流程 ============
    if not title:
        print("ERROR: 缺少标题")
        sys.exit(1)

    print(f"========== 开始发布: {title} ==========")
    if len(author) > 4:
        print(f"[WARN] 作者名较长（{len(author)}字符），建议≤2个中文字，否则可能报 author size out of limit")
    if len(title) > 10:
        print(f"[WARN] 标题较长（{len(title)}字符），建议≤10个中文字，否则可能报 title size out of limit")

    config = load_config()
    APPID = config["APPID"]
    APPSECRET = config["APPSECRET"]

    token = get_access_token(APPID, APPSECRET)

    thumb_media_id = None
    if not args.skip_cover and os.path.exists(cover_path):
        thumb_media_id = upload_thumb_material(token, cover_path)
        if not thumb_media_id:
            print("[ERROR] 封面图上传失败，无法创建草稿")
            sys.exit(1)

    if thumb_media_id:
        check_article_images(content)  # 🚫 硬性拦截：无图片不发布
        media_id = create_draft(token, title, author, digest, content, thumb_media_id, original=1)
    else:
        print("[WARN] 无封面图，创建草稿（无封面）")
        check_article_images(content)  # 🚫 硬性拦截：无图片不发布
        payload = {
            "articles": [{
                "title": title,
                "author": author,
                "digest": digest,
                "content": content,
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
                "original": 1,
            }]
        }
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            media_id = result.get("media_id")

    if media_id:
        print(f"========== 发布完成 ==========")
        print(f"草稿 media_id: {media_id}")
        print(f"请到微信公众平台后台编辑并发布")
    else:
        print(f"========== 发布失败 ==========")
        sys.exit(1)


if __name__ == "__main__":
    main()