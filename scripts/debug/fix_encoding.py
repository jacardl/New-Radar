#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import codecs

with open('backend/clients/last30days_importer.py', 'rb') as f:
    content = f.read()

# Common replacement bytes
content = content.replace(b'\xc2\xa0', b' ')
content = content.replace(b'\xe2\x80\x99', b"'")
content = content.replace(b'\xe2\x80\x9c', b'"')
content = content.replace(b'\xe2\x80\x9d', b'"')
content = content.replace(b'\xe2\x80\x94', b'-')
content = content.replace(b'\xe2\x80\x93', b'-')
content = content.replace(b'\xe2\x80\x95', b'--')
content = content.replace(b'\xe2\x80\x98', b"'")

with open('backend/clients/last30days_importer.py', 'wb') as f:
    f.write(content)

print('Fixed encoding')
