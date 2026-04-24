# -*- coding: utf-8 -*-
"""Fix corrupted docstrings in insight/agent.py"""
import re

filepath = 'backend/engines/insight/agent.py'

with open(filepath, 'rb') as f:
    content = f.read()

text = content.decode('utf-8', errors='replace')

# Targeted replacements for corrupted docstrings/comments only
replacements = [
    # Line 61
    (' """Deep Search Agent for Insight Engine"""', ' """Deep Search Agent for Insight Engine"""'),
    # Line 105
    (' """ LLM ?"""', ' """Initialize LLM client."""'),
    # Line 113
    (' """ ?"""', ' """Initialize processing nodes."""'),
    # Line 121
    (' """ ?"""', ' """Get clustering model (lazy load)."""'),
    # Line 123
    ('logger.info(" 载 类模 (paraphrase-multilingual-MiniLM-L12-v2)..."', 'logger.info("Loading clustering model (paraphrase-multilingual-MiniLM-L12-v2)...'),
    # Line 131
    ('格 为YYYY-MM-DD', 'Validate date format as YYYY-MM-DD'),
    # Line 134
    ('date_str: 符 ?', 'date_str: Date string'),
    # Line 137
    ('为 格 ?', 'Returns: True if valid format'),
    # Line 142
    ('# ?', '# validate pattern'),
    # Line 147
    ('# ?', '# check parsing'),
]

for old, new in replacements:
    text = text.replace(old, new)

# Clean any remaining mojibake characters (U+0080-U+00FF range)
# This is conservative - only removes chars that are clearly mojibake
text = re.sub(r'[\u0080-\u00ff]{2,}', ' ', text)

# Remove replacement characters
text = text.replace('\ufffd', ' ')

# Remove multiple spaces
text = re.sub(r'  +', ' ', text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print(f'Fixed: {filepath}')