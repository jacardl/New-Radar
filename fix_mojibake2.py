# -*- coding: utf-8 -*-
"""Aggressively fix mojibake by removing all non-ASCII chars in docstrings/comments"""
import re
import os

files = [
    'backend/engines/query/agent.py',
    'backend/engines/media/agent.py',
    'backend/engines/insight/agent.py',
    'backend/engines/report/agent.py',
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f'Skipping (not found): {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    # Decode as UTF-8, replacing invalid sequences
    text = content.decode('utf-8', errors='replace')

    # Find all docstrings (triple-quoted strings)
    # Match triple-quoted strings ("""...""" or '''...''')
    def replace_in_docstring(match):
        return '"""'

    # Replace content inside docstrings with ASCII equivalents
    # Pattern: find triple quotes followed by any non-ASCII, replace with just the quotes
    lines = text.split('\n')
    fixed_lines = []
    in_docstring = False
    docstring_start = None

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        indent = line[:len(line) - len(line.lstrip())]

        # Check for docstring start/end
        if '"""' in line or "'''" in line:
            # Simple approach: replace any non-ASCII in lines that look like docstrings
            # Replace runs of extended Latin chars (mojibake) with space
            # This matches characters in range U+0080 to U+00FF (Latin-1 Supplement)
            cleaned = re.sub(r'[\u0080-\u00ff]+', ' ', line)
            # Also remove other non-ASCII
            cleaned = re.sub(r'[^\x00-\x7f]', '', cleaned)
            fixed_lines.append(cleaned)
        elif stripped.startswith('#'):
            # Comment line - remove non-ASCII
            cleaned = re.sub(r'[^\x00-\x7f]', '', line)
            fixed_lines.append(cleaned)
        else:
            # Regular code line - remove only high non-ASCII in strings
            # This is tricky, so just do a conservative clean
            cleaned = re.sub(r'[\u0080-\u00ff]+', ' ', line)
            fixed_lines.append(cleaned)

    text = '\n'.join(fixed_lines)

    # Final pass: remove any remaining non-ASCII characters
    text = re.sub(r'[^\x00-\x7f]', '', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')

for filepath in files:
    fix_file(filepath)

print('Done!')