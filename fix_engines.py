# -*- coding: utf-8 -*-
"""
Fix corrupted engine agent files.
These files were committed with double-encoding mojibake.
We fix by rewriting the corrupted docstrings/comments with English.
"""
import re
import os

# File-specific fixes
# Format: filepath: {linenum: "replacement text"}

def fix_query_agent():
    filepath = 'backend/engines/query/agent.py'
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='replace')

    # Replace known corrupted patterns in docstrings
    replacements = [
        # Class docstring
        ('"""Deep Search Agentä¸»ç±»"""', '"""Deep Search Agent - inherits from BaseHermesAgent"""'),
        # Function docstrings
        ('"""åå§åLLMå®¢æ·ï¿½?"""', '"""Initialize LLM client."""'),
        ('"""åå§åå¤çèï¿½?"""', '"""Initialize processing nodes."""'),
        # Comment lines with mojibake
        ('# count?0?', '# count'),
        ('# count\n', '# count\n'),
        ('# searchæ¥ææ¯å¦æï¿½?', '# search result validation'),
        ('# searchæ¯å¦æ', '# search result format'),
        # f-string related mojibake
        ('? )', ')'),
        ('?)}', ')}'),
        ('?)\\n', ')\n'),
        ('??"', '"'),
        ('"?', '"'),
        (' ?', ' '),
        (" ?'", "'"),
        # Logger statements with mojibake
        ('logger.info(f"      {len(search_results)}  ?)', 'logger.info(f"      {len(search_results)} results")'),
        ('logger.info(f"      {j}. {result[\'title\'][:50]}...{date_info}")', None),  # Remove broken line
        ('logger.info("     ?)', 'logger.info("No results")'),
        # String literals with mojibake
        ('# API\n', None),  # Remove orphaned comment
        # Date validation mojibake
        ('# validationæ¥ææ¯å¦æ', '# validate date format'),
    ]

    for old, new in replacements:
        if new is None:
            text = text.replace(old, '')
        else:
            text = text.replace(old, new)

    # Clean up any remaining mojibake characters (U+0080 to U+00FF range that appears in docstrings)
    # These are Latin-1 Supplement characters used in mojibake
    text = re.sub(r'[\u0080-\u00ff]+', ' ', text)

    # Remove multiple spaces
    text = re.sub(r'  +', ' ', text)

    # Remove orphaned "Returns:" or "Args:" that are now empty
    text = re.sub(r'\n\s+Returns:\s*\n\s*\n', '\n', text)
    text = re.sub(r'\n\s+Args:\s*\n(\s+\w+:)', r'\n\1', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')


def fix_media_agent():
    filepath = 'backend/engines/media/agent.py'
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='replace')

    replacements = [
        ('"""Media Engineä¸»ç±»"""', '"""Media Engine - inherits from BaseHermesAgent"""'),
        ('"""åå§åLLMå®¢æ·ï¿½?"""', '"""Initialize LLM client."""'),
        ('"""åå§åå¤çèï¿½?"""', '"""Initialize processing nodes."""'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    text = re.sub(r'[\u0080-\u00ff]+', ' ', text)
    text = re.sub(r'  +', ' ', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')


def fix_insight_agent():
    filepath = 'backend/engines/insight/agent.py'
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='replace')

    replacements = [
        ('"""Insight Engineä¸»ç±»"""', '"""Insight Engine - inherits from BaseHermesAgent"""'),
        ('"""åå§åLLMå®¢æ·ï¿½?"""', '"""Initialize LLM client."""'),
        ('"""åå§åå¤çèï¿½?"""', '"""Initialize processing nodes."""'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    text = re.sub(r'[\u0080-\u00ff]+', ' ', text)
    text = re.sub(r'  +', ' ', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')


def fix_report_agent():
    filepath = 'backend/engines/report/agent.py'
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='replace')

    text = re.sub(r'[\u0080-\u00ff]+', ' ', text)
    text = re.sub(r'  +', ' ', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Fixed: {filepath}')


if __name__ == '__main__':
    fix_query_agent()
    fix_media_agent()
    fix_insight_agent()
    fix_report_agent()
    print('Done!')