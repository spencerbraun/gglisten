#!/usr/bin/env -S uv run --script

# @raycast.title Dictation History
# @raycast.mode fullOutput
# @raycast.schemaVersion 1
# @raycast.icon 📜

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Show recent transcription history.
"""

import sys
from pathlib import Path

# Add gglisten package to path
GGLISTEN_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(GGLISTEN_ROOT))

from gglisten.cli import history_cmd

if __name__ == "__main__":
    history_cmd(limit=10)
