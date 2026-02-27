#!/usr/bin/env python3
"""
MIRA Terminal Client - entry point.

Usage:
    python talkto_mira.py              # Interactive chat
    python talkto_mira.py --headless "message"  # One-shot query
    python talkto_mira.py --show-key   # Display API key
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ui.terminal import main

main()
