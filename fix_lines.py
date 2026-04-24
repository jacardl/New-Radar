#!/usr/bin/env python3
path = "/mnt/d/Users/New Radar/backend/frameworks/hermes-agent/hermes_cli/main.py"
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Fix line 373-381 (0-indexed: 372-380)
# We need to replace lines 373-381 with proper code
fixed_lines = '''                if search_text:
                    header = f"  Browse sessions - filter: {search_text} - "
                    header_attr = curses.A_BOLD
                    if curses.has_colors():
                        header_attr |= curses.color_pair(3)
                else:
                    header = "  Browse sessions - navigate  Enter select  Type to filter  Esc quit"
                    header_attr = curses.A_BOLD
                    if curses.has_colors():
                        header_attr |= curses.color_pair(2)
                try:
'''

# Find the start of the if block and replace
new_lines = []
i = 0
while i < len(lines):
    if i == 372:  # Line 373 (0-indexed)
        # Skip old lines until we find "try:"
        while i < len(lines) and 'try:' not in lines[i]:
            i += 1
        # Now add our fixed lines
        new_lines.append(fixed_lines)
        new_lines.append(lines[i])  # the try: line
        i += 1
    else:
        new_lines.append(lines[i])
        i += 1

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(new_lines)

print("Fixed lines 373-381")

# Verify
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(372, min(382, len(lines))):
    print(f"Line {i+1}: {repr(lines[i][:80])}")
