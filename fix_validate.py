# -*- coding: utf-8 -*-
"""Fix _validate_date_format function"""
import re

filepath = 'backend/engines/insight/agent.py'

with open(filepath, 'rb') as f:
    content = f.read()

# Remove \r
content = content.replace(b'\r', b'')

# Fix the _validate_date_format function
# Find it by pattern and replace
pattern = rb'def _validate_date_format\(self, date_str: str\) -> bool:'
match = re.search(pattern, content)
if match:
    start = match.start()
    # Find the function body - look for next function def or end of class
    # Simple approach: find the indentation change
    before = content[:start]
    rest = content[start:]

    # Find where this function ends (next function at same indentation level)
    lines = rest.split(b'\n')
    func_lines = [lines[0]]  # def line
    for i in range(1, len(lines)):
        line = lines[i]
        if line and not line.startswith(b' '):
            # Found next top-level item
            break
        func_lines.append(line)
    else:
        i = len(lines)

    old_func = b'\n'.join(func_lines)

    # Create new function with correct indentation and no mojibake
    new_func = b'''    def _validate_date_format(self, date_str: str) -> bool:
        """
        Validate date format as YYYY-MM-DD.

        Args:
            date_str: Date string

        Returns:
            True if valid format
        """
        if not date_str:
            return False

        # Validate pattern
        pattern = r"^\\d{4}-\\d{2}-\\d{2}$"
        if not re.match(pattern, date_str):
            return False

        # Validate parsing
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
'''

    content = before + new_func + b'\n' + b'\n'.join(lines[i:])
    print('Fixed _validate_date_format')
else:
    print('_validate_date_format not found')

with open(filepath, 'wb') as f:
    f.write(content)

print('Done')