#!/usr/bin/env python3
with open('backend/clients/last30days_importer.py', 'rb') as f:
    data = f.read()
    print(f'File size: {len(data)} bytes')
    # Check around position 24
    for i in range(max(0, 24-10), min(len(data), 30)):
        c = data[i]
        char = chr(c) if 32 <= c < 127 else '?'
        print(f'{i}: {c:02x} ({char})')
