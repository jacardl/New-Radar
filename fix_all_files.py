#!/usr/bin/env python3
"""Properly fix all Python files in hermes-agent directory."""
import os
import re

def fix_file_hermes(path):
    """Fix a single Python file for hermes-agent."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()

        # Check for CRLF and convert
        has_crlf = b'\r\n' in raw

        # Try to decode as UTF-8 first
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            # Try GBK (common on Chinese Windows)
            try:
                text = raw.decode('gbk')
            except:
                text = raw.decode('latin-1')

        # Remove all \r characters
        text = text.replace('\r', '')

        # The text might have mojibake from double encoding
        # Try to fix common patterns
        # EN DASH: – (U+2013) encoded as UTF-8 is \xe2\x80\x93
        # But double latin-1 conversion makes it \xc3\xa2\xc2\x80\xc2\x93
        text = re.sub(r'\xc3\xa2\xc2\x80\xc2\x93', '-', text)  # EN DASH mojibake
        text = re.sub(r'\xc3\xa2\xc2\x80\xc2\x9c', '-', text)  # same for other dash
        text = re.sub(r'\xe2\x80\x93', '-', text)  # proper EN DASH
        text = re.sub(r'\xe2\x80\x94', '-', text)  # EM DASH
        text = re.sub(r'\xe2\x81\x9c', '-', text)  # HYPHEN
        text = re.sub(r'\xe2\x81\x9d', '-', text)

        # Fix arrow characters
        text = re.sub(r'\xe2\x86\x91', '^', text)  # UP ARROW
        text = re.sub(r'\xe2\x86\x93', 'v', text)  # DOWN ARROW
        text = re.sub(r'\xe2\x86\x92', '->', text)  # RIGHT ARROW

        # Fix box drawing characters that cause issues
        text = re.sub(r'\xe2\x94\x8c', '+', text)  # BOX DRAWINGS DOWN LIGHT
        text = re.sub(r'\xe2\x94\x80', '-', text)  # BOX DRAWINGS LIGHT HORIZONTAL
        text = re.sub(r'\xe2\x94\x90', '+', text)  # BOX DRAWINGS DOWN LIGHT
        text = re.sub(r'\xe2\x94\x82', '|', text)  # BOX DRAWINGS LIGHT VERTICAL
        text = re.sub(r'\xe2\x94\xac', '+', text)  # BOX DRAWINGS DOWN LIGHT
        text = re.sub(r'\xe2\x94\xb4', '+', text)  # BOX DRAWINGS UP LIGHT
        text = re.sub(r'\xe2\x95\xb0', '+', text)  # BOX DRAWINGS DOWN LIGHT

        # Fix any remaining control characters that shouldn't be in source
        # Remove \x80-\x9f range which are control chars in ISO-8859-1
        text = re.sub(r'[\x80-\x9f]', '', text)

        # Write back as proper UTF-8 with LF line endings
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)

        return 'fixed'
    except Exception as e:
        return f'error: {e}'

def main():
    base = '/mnt/d/Users/New Radar/backend/frameworks/hermes-agent'
    fixed = 0
    errors = 0
    for root, dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith('.py'):
                path = os.path.join(root, fn)
                result = fix_file_hermes(path)
                if result == 'fixed':
                    fixed += 1
                elif result.startswith('error'):
                    errors += 1
                    print(f'Error: {path}: {result}')

    print(f'Fixed {fixed} files, {errors} errors')

if __name__ == '__main__':
    main()
