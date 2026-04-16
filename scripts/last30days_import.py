#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
last30days-cn search import entry point

Usage:
    python last30days_import.py --diagnose
    python last30days_import.py "keyword" --days 30 --deep
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from clients.last30days_importer import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
