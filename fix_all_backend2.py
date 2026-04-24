#!/usr/bin/env python3
"""Enhanced fix for all Python files in backend directory."""
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

        # Fix corrupted em-dash sequences: e3 80 ?? where ?? is not a valid continuation
        # The pattern e3 80 is typically from ã€ (U+00E3 U+0080 in latin-1)
        # which should have been em-dash e2 80 94 in UTF-8
        text = re.sub(b'\xe3\x80[\x00-\x7f]', b'--', text)  # e3 80 followed by ASCII
        text = re.sub(b'\xe3\x80{2,}', b'--', text)  # multiple e3 80

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

        # Fix remaining e3 xx patterns that are clearly corrupted Chinese
        # These appear as partial sequences
        text = re.sub(b'\xe3[\x00-\x7f]', b'', text)  # e3 followed by ASCII
        text = re.sub(b'\xe3{2,}', b'', text)  # multiple e3

        # Remove remaining control characters
        text = re.sub(b'[\x80-\x9f]', b'', text)

        # Write back as proper UTF-8 with LF line endings
        with open(path, 'wb') as f:
            f.write(text)

        # Check if file is valid UTF-8
        try:
            text.decode('utf-8')
            return 'fixed' if has_crlf else 'ok'
        except UnicodeDecodeError:
            return f'still_bad'
    except Exception as e:
        return f'error: {e}'


def main():
    base = 'd:/Users/New Radar/backend'
    fixed = 0
    ok = 0
    still_bad = 0
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
                elif result == 'still_bad':
                    still_bad += 1
                    print(f'Still bad: {path}')
                elif result.startswith('error'):
                    errors += 1
                    print(f'Error: {path}: {result}')

    print(f'Fixed {fixed} files, {ok} ok, {still_bad} still bad, {errors} errors')


if __name__ == '__main__':
    main()