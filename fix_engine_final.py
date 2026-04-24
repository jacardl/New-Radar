# -*- coding: utf-8 -*-
"""Final fix for corrupted engine files - handles invalid UTF-8 and mojibake"""
import re
import os

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    # Read as binary first
    with open(filepath, 'rb') as f:
        raw = f.read()

    # Remove all \r (CRLF -> LF)
    raw = raw.replace(b'\r', b'')

    # Fix common mojibake patterns from double encoding
    # These are specific byte sequences that appear in the corrupted files
    replacements = [
        # EN DASH and EM DASH mojibake
        (b'\xc3\xa2\xc2\x80\xc2\x93', b'-'),
        (b'\xc3\xa2\xc2\x80\xc2\x9c', b'-'),
        (b'\xe2\x80\x93', b'-'),
        (b'\xe2\x80\x94', b'-'),
        (b'\xe2\x81\x9c', b'-'),
        (b'\xe2\x81\x9d', b'-'),
        # Quote marks
        (b'\xe2\x80\x99', b"'"),
        (b'\xe2\x80\x9c', b'"'),
        (b'\xe2\x80\x9d', b'"'),
        (b'\xe2\x80\x9e', b',,'),
        (b'\xe2\x80\x9f', b',,'),
        # Ellipsis
        (b'\xe2\x80\xa6', b'...'),
        # Arrow characters
        (b'\xe2\x86\x91', b'^'),
        (b'\xe2\x86\x93', b'v'),
        (b'\xe2\x86\x92', b'->'),
        # Box drawing (approximations)
        (b'\xe2\x94\x8c', b'+'),
        (b'\xe2\x94\x80', b'-'),
        (b'\xe2\x94\x90', b'+'),
        (b'\xe2\x94\x82', b'|'),
        (b'\xe2\x94\xac', b'+'),
        (b'\xe2\x94\xb4', b'+'),
        (b'\xe2\x95\xb0', b'+'),
    ]

    for old, new in replacements:
        raw = raw.replace(old, new)

    # Fix corrupted em-dash sequences: e3 80 ?? where ?? is ASCII
    # These are from Chinese chars being double-encoded
    raw = re.sub(b'\xe3\x80[\x00-\x7f]', b'--', raw)
    raw = re.sub(b'\xe3\x80{2,}', b'--', raw)

    # Fix remaining e3 xx patterns (partial corrupted sequences)
    raw = re.sub(b'\xe3[\x00-\x7f]', b'', raw)
    raw = re.sub(b'\xe3{2,}', b'', raw)

    # Remove remaining control characters in high range
    raw = re.sub(b'[\x80-\x9f]', b'', raw)

    # Now decode as UTF-8 with replacement for any remaining issues
    try:
        text = raw.decode('utf-8', errors='replace')
    except:
        # Fallback to latin-1 if UTF-8 fails completely
        text = raw.decode('latin-1', errors='replace')

    # Replace the Unicode replacement character with space
    text = text.replace('\ufffd', ' ')

    # Clean up any remaining non-ASCII in docstrings/comments
    # Find docstrings and clean them
    lines = text.split('\n')
    fixed_lines = []
    in_docstring = False

    for line in lines:
        # Detect docstring boundaries
        if '"""' in line or "'''" in line:
            # Clean non-ASCII from this line
            cleaned_line = ''.join(c if (ord(c) < 128 or c in ' \n\t') else ' ' for c in line)
            cleaned_line = re.sub(r'  +', ' ', cleaned_line)
            fixed_lines.append(cleaned_line)
        elif line.strip().startswith('#'):
            # Clean comment line
            cleaned_line = ''.join(c if (ord(c) < 128 or c in ' \n\t') else ' ' for c in line)
            cleaned_line = re.sub(r'  +', ' ', cleaned_line)
            fixed_lines.append(cleaned_line)
        else:
            fixed_lines.append(line)

    text = '\n'.join(fixed_lines)

    # Final cleanup: remove any remaining high Latin chars that are mojibake
    # Match sequences of 2+ non-ASCII Latin chars that are likely mojibake
    text = re.sub(r'[\u00a7\u00e4\u00b8\u00bb\u00e5\u00a7\u00ac\u00e6\u00a0\u00bc\u00ef\u00bf\u00bd]{2,}', ' ', text)

    # Remove multiple spaces
    text = re.sub(r'  +', ' ', text)

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')

if __name__ == '__main__':
    files = [
        'backend/engines/query/agent.py',
        'backend/engines/media/agent.py',
        'backend/engines/insight/agent.py',
        'backend/engines/report/agent.py',
    ]
    for f in files:
        fix_file(f)
    print('Done!')