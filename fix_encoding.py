#!/usr/bin/env python3
"""Fix all Python files using error handling replacement."""
import os


def fix_file(path):
    try:
        with open(path, 'rb') as f:
            raw = f.read()

        # Remove \r (CRLF -> LF)
        text = raw.replace(b'\r', b'')

        # Try to decode as UTF-8 with replacement for invalid sequences
        try:
            decoded = text.decode('utf-8')
        except UnicodeDecodeError:
            # If that fails, try latin-1 first then encode to UTF-8
            decoded = text.decode('latin-1', errors='replace').encode('utf-8', errors='replace').decode('utf-8', errors='replace')

        # Replace invalid UTF-8 sequences with replacement character
        fixed = decoded.encode('utf-8', errors='replace').decode('utf-8', errors='replace')

        # Write back
        with open(path, 'w', encoding='utf-8') as f:
            f.write(fixed)

        # Verify
        try:
            open(path, 'r', encoding='utf-8').read()
            return 'ok'
        except:
            return 'still_bad'
    except Exception as e:
        return f'error: {e}'


def main():
    base = 'd:/Users/New Radar/backend'
    ok_count = 0
    bad_count = 0
    error_count = 0

    for root, dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith('.py'):
                path = os.path.join(root, fn)
                result = fix_file(path)
                if result == 'ok':
                    ok_count += 1
                elif result == 'still_bad':
                    bad_count += 1
                    print(f'Still bad: {path}')
                else:
                    error_count += 1
                    print(f'Error: {path}: {result}')

    print(f'Ok: {ok_count}, Still bad: {bad_count}, Errors: {error_count}')


if __name__ == '__main__':
    main()
