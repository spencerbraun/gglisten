#!/usr/bin/env -S /Users/spencerbraun/.cargo/bin/uv run --script

# @raycast.title Clean Dictation
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon ✨

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "litellm",
#     "instructor",
#     "pydantic",
# ]
# ///

"""
Clean up clipboard text using AI.
Removes filler words, fixes grammar, improves clarity.
"""

import sys
from pathlib import Path

# Add gglisten package to path
GGLISTEN_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(GGLISTEN_ROOT))

from gglisten.cli import clean_cmd

if __name__ == "__main__":
    clean_cmd()
