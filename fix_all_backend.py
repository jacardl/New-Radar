#!/usr/bin/env python3
"""Fix all Python files in backend directory."""
import os
import re


def fix_file_backend(path):
    """Fix a single Python file."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()

        # Remove all \r characters (CRLF -> LF)
        has_crlf = b'\r\n' in raw
        text = raw.replace(b'\r', b'')

        # Fix mojibake from double encoding
        # EN DASH: – (U+2013) encoded as UTF-8 is \xe2\x80\x93
        # But double latin-1 conversion makes it \xc3\xa2\xc2\x80\xc2\x93
        text = text.replace(b'\xc3\xa2\xc2\x80\xc2\x93', b'-')  # EN DASH mojibake
        text = text.replace(b'\xc3\xa2\xc2\x80\xc2\x9c', b'-')  # same for other dash
        text = text.replace(b'\xe2\x80\x93', b'-')  # proper EN DASH
        text = text.replace(b'\xe2\x80\x94', b'-')  # EM DASH
        text = text.replace(b'\xe2\x81\x9c', b'-')  # HYPHEN
        text = text.replace(b'\xe2\x81\x9d', b'-')

        # Fix arrow characters
        text = text.replace(b'\xe2\x86\x91', b'^')  # UP ARROW
        text = text.replace(b'\xe2\x86\x93', b'v')  # DOWN ARROW
        text = text.replace(b'\xe2\x86\x92', b'->')  # RIGHT ARROW

        # Fix box drawing characters
        text = text.replace(b'\xe2\x94\x8c', b'+')
        text = text.replace(b'\xe2\x94\x80', b'-')
        text = text.replace(b'\xe2\x94\x90', b'+')
        text = text.replace(b'\xe2\x94\x82', b'|')
        text = text.replace(b'\xe2\x94\xac', b'+')
        text = text.replace(b'\xe2\x94\xb4', b'+')
        text = text.replace(b'\xe2\x95\xb0', b'+')

        # Fix other common mojibake patterns
        text = text.replace(b'\xe2\x80\x99', b"'")  # RIGHT SINGLE QUOTATION MARK
        text = text.replace(b'\xe2\x80\x9c', b'"')  # LEFT DOUBLE QUOTATION MARK
        text = text.replace(b'\xe2\x80\x9d', b'"')  # RIGHT DOUBLE QUOTATION MARK
        text = text.replace(b'\xe2\x80\x9e', b',,')  # DOUBLE LOW-9 QUOTATION MARK
        text = text.replace(b'\xe2\x80\x9f', b',,')  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
        text = text.replace(b'\xe2\x80\xa6', b'...')  # HORIZONTAL ELLIPSIS

        # Remove remaining control characters
        text = re.sub(b'[\x80-\x9f]', b'', text)

        # Write back as proper UTF-8 with LF line endings
        with open(path, 'wb') as f:
            f.write(text)

        return 'fixed' if has_crlf or b'\\xe3\\x80' in raw or b'\\xc3\\xa2' in raw else 'ok'
    except Exception as e:
        return f'error: {e}'


def main():
    base = 'd:/Users/New Radar/backend'
    fixed = 0
    ok = 0
    errors = 0
    for root, dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith('.py'):
                path = os.path.join(root, fn)
                result = fix_file_backend(path)
                if result == 'fixed':
                    fixed += 1
                    print(f'Fixed: {path}')
                elif result == 'ok':
                    ok += 1
                elif result.startswith('error'):
                    errors += 1
                    print(f'Error: {path}: {result}')

    print(f'Fixed {fixed} files, {ok} ok, {errors} errors')


if __name__ == '__main__':
    main()
