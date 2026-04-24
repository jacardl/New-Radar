# -*- coding: utf-8 -*-
"""Fix mojibake in engine files"""
import re
import os

files = [
    'backend/engines/query/agent.py',
    'backend/engines/media/agent.py',
    'backend/engines/insight/agent.py',
]

# Known mojibake patterns and their corrections
replacements = {
    'ä¸»ç±»': 'inherits from BaseHermesAgent',
    'åå§åLLMå®¢æ·ï¿½?': 'initialize LLM client',
    'åå§åå¤çèï¿½?': 'initialize search nodes',
    'æ£æ¥': 'search',
    'åç»': 'query',
    'è¿è¡': 'execute',
    'ç»ä¼': 'result',
    'æµè': 'test',
    'å¼æ': 'call',
    'æ¶æ': 'time',
    'æå®': 'config',
    'å®è²': 'verify',
    'æé': 'data',
    'æ¥å': 'query',
    'è¿ç»': 'result',
    'å§å': 'init',
    'æå¤': 'search',
    'çæ': 'API',
    'è·¯å¾': 'route',
    'å¤å¾': 'return',
    'åç': 'call',
    'ä¿®': 'fix',
    'æ°': 'count',
    'è¿è¡': 'execute',
}

for filepath in files:
    if not os.path.exists(filepath):
        print(f'Skipping (not found): {filepath}')
        continue

    with open(filepath, 'rb') as f:
        content = f.read()

    # Try UTF-8 first
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    # Apply replacements
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    # Remove non-printable and mojibake characters in docstrings/comments
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        # Check if line has docstring markers
        if '"""' in line or "'''" in line:
            # Replace sequences of non-ASCII mojibake chars with space
            # This regex matches runs of extended Latin chars common in mojibake
            line = re.sub(r'[\u0080-\u00ff]{3,}', ' ', line)
        fixed_lines.append(line)

    text = '\n'.join(fixed_lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')


# Also fix report agent
report_agent = 'backend/engines/report/agent.py'
if os.path.exists(report_agent):
    with open(report_agent, 'rb') as f:
        content = f.read()
    try:
        text = content.decode('utf-8')
    except:
        text = content.decode('latin-1')

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        if '"""' in line or "'''" in line:
            line = re.sub(r'[\u0080-\u00ff]{3,}', ' ', line)
        fixed_lines.append(line)

    text = '\n'.join(fixed_lines)

    with open(report_agent, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'Fixed: {report_agent}')

print('Done!')