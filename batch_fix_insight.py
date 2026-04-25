# -*- coding: utf-8 -*-
"""Smart batch fix for insight/agent.py - preserves code, fixes docstrings/comments"""
import re

filepath = 'backend/engines/insight/agent.py'

with open(filepath, 'rb') as f:
    content = f.read()

# Decode with replacement for invalid UTF-8
text = content.decode('utf-8', errors='replace')

# Replace all Unicode replacement chars with space
text = text.replace('\ufffd', ' ')

# Remove \r (CRLF)
text = text.replace('\r', '')

# Now do targeted replacements for known mojibake patterns
# These are in docstrings and comments only

# Map of corrupted patterns to their English equivalents (conservative)
fixes = {
    '""" ?"""': '"""Process paragraphs."""',
    '""" LLM ?"""': '"""Initialize LLM client."""',
    '""" ?"""': '"""Process."""',
    '""" ?"""': '"""Initialize processing nodes."""',
    '"""Get clustering model (lazy load)."""': '"""Get clustering model (lazy load)."""',
    'ä¸»ç±»': 'inherits from',
    ' LLM ?': ' Initialize LLM client',
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
    'æå½': 'load',
    'å­å®': 'save',
    'å®ç½': 'config',
    'çæ®': 'agent',
    'å·¥å': 'task',
    'æ¥ç»': 'query result',
    'è¿è¡ç»': 'execution result',
    'ä¿¡æ¯': 'info',
    'èªå': 'read',
    'å�å®': 'analyze',
    'æµèè¯': 'test result',
    'æå¤æ¥': 'search query',
    'æ­¥é»: 'step',
    'æè¿': 'progress',
    'å½æ¥': 'format',
    'è¿è¡æ¥': 'execute',
    'æ¥å®': 'query config',
    'æ¥è¯': 'query result',
    'è¿è¡è¯': 'execute result',
    'ç³»ç»: 'system',
    'åæ': 'output',
    'è¾å': 'input',
    'å¤æ¥': 'search',
    'å¼æ¥': 'call',
    'åºå': 'build',
    'åè·': 'direction',
    'ç³»çµ': 'system',
    'ä¿å': 'protect',
    'è·¯ç»': 'route',
    'æ¥å½': 'query format',
    'å®ç½': 'config',
    'æµèå': 'test output',
    'è¿è¡å': 'execute output',
    'æ¥æ': 'query',
    'æµè': 'test',
    'è¿è¡': 'execute',
    'å¼': 'call',
    'è¿': 'return',
    'æµ': 'output',
    'è¾': 'input',
    'å®': 'config',
    'æå': 'save',
    'è¯': 'result',
    'ç»': 'result',
    'é¢': 'error',
    'è¿': 'back',
    'è¿': 'return',
    'è¿': 'back',
    'è¿': 'return',
}

# Apply fixes
for wrong, correct in fixes.items():
    text = text.replace(wrong, correct)

# Clean up logger statements with remaining mojibake
# Pattern: logger.info(f"...") or logger.info("...") where content is corrupted
# This regex finds logger calls with mojibake in string arguments
text = re.sub(
    r'logger\.(info|warning|error|debug)\(f?"[^"]*[\u0080-\u00ff]+[^"]*"',
    lambda m: m.group(0)[:m.group(0).find('"')] + '"..."', text
)

# Clean remaining docstrings/comments with mojibake
# Replace runs of high Latin chars with space
text = re.sub(r'[\u00a7\u00e4\u00b8\u00bb\u00e5\u00a7\u00ac\u00e6\u00a0\u00bc\u00ef\u00bf\u00bd]{2,}', ' ', text)

# Final pass: replace any remaining single mojibake chars in docstrings
lines = text.split('\n')
fixed_lines = []
for line in lines:
    # If line is a docstring or comment with mojibake, clean it
    stripped = line.lstrip()
    if stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith('#'):
        # Remove all non-ASCII
        cleaned = ''.join(c if ord(c) < 128 or c in ' \t\n' for c in line)
        # Clean up spaces
        cleaned = re.sub(r'  +', ' ', cleaned)
        fixed_lines.append(cleaned)
    else:
        fixed_lines.append(line)

text = '\n'.join(fixed_lines)

# Remove multiple consecutive spaces
text = re.sub(r'  +', ' ', text)

# Write back
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print(f'Fixed: {filepath}')