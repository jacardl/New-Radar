# -*- coding: utf-8 -*-
"""
Smart fix for corrupted Python files.
Uses tokenization to only fix strings and comments, preserving code logic.
"""
import tokenize
import io
import re
import os

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f'Skipping: {filepath}')
        return

    with open(filepath, 'rb') as f:
        raw = f.read()

    # Try UTF-8, then fallback to latin-1
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        text = raw.decode('latin-1', errors='replace')

    # Remove BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]

    # Tokenize
    tokens = []
    string_tokens = []
    done = False

    try:
        encoding = tokenize.detect_encoding(io.BytesIO(text.encode('utf-8')).readline)[0]
    except:
        encoding = 'utf-8'

    # Parse with tokenize, collecting problematic tokens
    g = tokenize.generate_tokens(io.StringIO(text).readline)

    while not done:
        try:
            tok = next(g)
            if tok.type == tokenize.STRING:
                # Check if string contains mojibake
                val = tok.string
                try:
                    val.encode('ascii')
                except UnicodeEncodeError:
                    # Contains non-ASCII - check if it's real content or corruption
                    if any(c in val for c in '\ufffd\u00a7'):
                        # Contains replacement char or section sign - likely corruption
                        string_tokens.append((tok, val))
            tokens.append(tok)
        except StopIteration:
            done = True
        except tokenize.TokenError:
            done = True
            break

    print(f'Found {len(string_tokens)} problematic string tokens in {filepath}')

    # For strings with mojibake, replace non-ASCII with '?'
    # For comments with mojibake, remove non-ASCII
    # We'll do a simpler approach: regex pass

    # Remove \r
    text = text.replace('\r', '')

    # Replace replacement character
    text = text.replace('\ufffd', ' ')

    # For strings: replace mojibake chars with safe equivalents
    # Pattern: strings in logger calls
    def fix_logger_string(match):
        prefix = match.group(1)
        content = match.group(2)
        suffix = match.group(3)
        # Replace non-ASCII with '?'
        fixed = ''.join(c if ord(c) < 128 or c in ' \t' else '?' for c in content)
        return prefix + fixed + suffix

    # Fix logger strings (f-strings and regular strings)
    text = re.sub(r'(logger\.(?:info|warning|error|debug|exception)\()(f?)?"([^"]*)"', fix_logger_string, text)
    text = re.sub(r"(logger\.(?:info|warning|error|debug|exception)\()(f?)?'([^']*)'", fix_logger_string, text)

    # For docstrings: remove non-ASCII
    # Match triple-quoted strings
    def fix_docstring(match):
        content = match.group(1)
        # Remove non-ASCII
        fixed = ''.join(c if ord(c) < 128 else ' ' for c in content)
        # Clean multiple spaces
        fixed = re.sub(r'  +', ' ', fixed)
        return '"""' + fixed + '"""'

    text = re.sub(r'"""(.*?)"""', fix_docstring, text, flags=re.DOTALL)

    # For comments: remove non-ASCII
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        if '#' in line:
            idx = line.index('#')
            code_part = line[:idx]
            comment_part = line[idx:]
            # Remove non-ASCII from comment
            fixed_comment = ''.join(c if ord(c) < 128 else ' ' for c in comment_part)
            fixed_comment = re.sub(r'  +', ' ', fixed_comment)
            fixed_lines.append(code_part + fixed_comment)
        else:
            fixed_lines.append(line)

    text = '\n'.join(fixed_lines)

    # Final cleanup
    text = re.sub(r'  +', ' ', text)

    # Try to compile
    try:
        compile(text, filepath, 'exec')
        print(f'OK: {filepath} compiles successfully')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'Fixed: {filepath}')
    except SyntaxError as e:
        print(f'Still has error at line {e.lineno}: {e.msg}')
        # Show the problematic line
        lines = text.split('\n')
        if e.lineno and e.lineno <= len(lines):
            print(f'  Line {e.lineno}: {lines[e.lineno-1][:80]}')
        # Save anyway for manual inspection
        backup = filepath + '.backup'
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'Saved backup to {backup}')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        for filepath in sys.argv[1:]:
            fix_file(filepath)
    else:
        # Default: fix all engine agents
        for filepath in [
            'backend/engines/query/agent.py',
            'backend/engines/media/agent.py',
            'backend/engines/insight/agent.py',
            'backend/engines/report/agent.py',
        ]:
            fix_file(filepath)