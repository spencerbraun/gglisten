#!/usr/bin/env -S uv run --script

# @raycast.title Dictation Status
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon ℹ️

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Show current recording status and last transcription.
"""

import sys
from pathlib import Path

# Add gglisten package to path
GGLISTEN_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(GGLISTEN_ROOT))

from gglisten.cli import status_cmd

if __name__ == "__main__":
    status_cmd()
