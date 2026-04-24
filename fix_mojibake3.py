# -*- coding: utf-8 -*-
"""Fix mojibake using proper Python tokenization"""
import re
import os
import tokenize
import io

files = [
    'backend/engines/query/agent.py',
    'backend/engines/media/agent.py',
    'backend/engines/insight/agent.py',
    'backend/engines/report/agent.py',
]

def is_mojibake_string(s):
    """Check if a string looks like corrupted mojibake (valid UTF-8 but nonsense)"""
    if not s:
        return False
    # If it contains high Latin chars but no actual words, likely mojibake
    try:
        s.encode('ascii')
        return False  # Pure ASCII
    except UnicodeEncodeError:
        pass

    # Count mojibake indicators
    mojibake_chars = sum(1 for c in s if ord(c) > 127)
    if mojibake_chars > len(s) * 0.3:
        return True
    return False

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    # Decode with replacement for invalid sequences
    text = content.decode('utf-8', errors='replace')

    # Tokenize and fix only comments and docstrings
    result = []
    lines = text.split('\n')

    for line in lines:
        # Check if line is a comment
        stripped = line.lstrip()
        if stripped.startswith('#'):
            # Remove non-ASCII from comments
            line = ''.join(c if ord(c) < 128 else ' ' for c in line)
            # Clean up multiple spaces
            line = re.sub(r' +', ' ', line)
            result.append(line)
            continue

        # Handle lines with docstrings
        if '"""' in line or "'''" in line:
            # Count quotes to handle docstring starts/ends
            dq_count = line.count('"""')
            sq_count = line.count("'''")

            if dq_count == 2 or sq_count == 2:
                # Single line docstring
                # Remove non-ASCII
                line = ''.join(c if ord(c) < 128 else ' ' for c in line)
                line = re.sub(r' +', ' ', line)
                result.append(line)
                continue

        # Regular code line - only remove non-ASCII if it's clearly mojibake in comments
        # being conservative
        if '#' in line:
            idx = line.index('#')
            before = line[:idx]
            after = line[idx:]
            after_clean = ''.join(c if ord(c) < 128 else ' ' for c in after)
            after_clean = re.sub(r' +', ' ', after_clean)
            result.append(before + after_clean)
        else:
            result.append(line)

    text = '\n'.join(result)

    # Final pass: remove any remaining problematic characters
    # Replace remaining mojibake runs with spaces
    text = re.sub(r'[\u0080-\u00ff]{2,}', ' ', text)
    text = re.sub(r'[^\x00-\x7f]', '', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')

for filepath in files:
    fix_file(filepath)

print('Done!')