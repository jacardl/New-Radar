#!/usr/bin/env python3
"""
cleanup_html.py — 微信文章 HTML 空行清理工具

读取 HTML 文件，逐行移除所有纯空行（或纯空白行），
输出紧凑版本（block 元素间无换行符）。

用法：
    python3 cleanup_html.py <input.html> [output.html]
    # 如果不指定 output，则覆盖原文件（先备份 .bak）

验证（不修改）：
    python3 cleanup_html.py --check <input.html>
"""
import sys, os

def strip_empty_lines(html_content):
    """移除所有纯空行，逐行拼接"""
    lines = html_content.split('\n')
    clean_lines = [line for line in lines if line.strip()]
    return '\n'.join(clean_lines)

def check_empty_lines(html_content):
    """返回空行数和空行位置"""
    lines = html_content.split('\n')
    empty = [(i+1, line) for i, line in enumerate(lines) if not line.strip()]
    return len(empty), empty

def check_json_newlines(html_content):
    """验证 HTML 嵌入 JSON payload 后是否含意外换行符"""
    import json
    payload = {'content': html_content}
    data = json.dumps(payload, ensure_ascii=False)
    # json.dumps 默认会在 : 后加空格，在 , 后加换行，这是正常的
    # 我们关心的是 content 值内的换行（来自 HTML 本身）
    content_newlines = data.count('\\n')
    return content_newlines

def main():
    argv = sys.argv
    if len(argv) < 2:
        print("用法: python3 cleanup_html.py <input.html> [output.html]")
        print("       python3 cleanup_html.py --check <input.html>")
        print("       python3 cleanup_html.py --json-check <input.html>")
        sys.exit(1)

    input_path = argv[1]

    if "--json-check" in argv:
        with open(input_path, encoding='utf-8') as f:
            content = f.read()
        newlines = check_json_newlines(content)
        print(f"[{'OK' if newlines == 0 else 'WARN'}] JSON payload 换行符数量: {newlines} (应为 0)")
        return

    if "--check" in argv:
        with open(input_path, encoding='utf-8') as f:
            content = f.read()
        count, empties = check_empty_lines(content)
        if count == 0:
            print(f"[OK] {input_path}: 0 空行，干净")
        else:
            print(f"[WARN] {input_path}: {count} 个空行")
            for num, line in empties[:10]:
                print(f"  Line {num}: |{repr(line)}|")
        return

    output_path = argv[2] if len(argv) > 2 else input_path
    overwrite = (output_path == input_path)

    with open(input_path, encoding='utf-8') as f:
        content = f.read()

    before_size = len(content)
    before_lines = len(content.split('\n'))
    clean = strip_empty_lines(content)
    after_size = len(clean)
    after_lines = len(clean.split('\n'))
    count, _ = check_empty_lines(content)

    if count == 0:
        print(f"[OK] {input_path}: 已干净，跳过（0 空行）")
        return

    if overwrite:
        bak = input_path + '.bak'
        with open(bak, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[BAK] 备份原文件 → {bak}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(clean)

    print(f"[OK] {input_path} → {output_path}")
    print(f"     {before_size} bytes ({before_lines} lines, {count} empty) → {after_size} bytes ({after_lines} lines, 0 empty)")

if __name__ == "__main__":
    main()
