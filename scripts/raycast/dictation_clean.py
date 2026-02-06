#!/usr/bin/env python3
# ^ Shebang is updated by setup.sh to point to the gglisten venv

# @raycast.title gGlisten Clean
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon ✨

"""
Clean up clipboard text using AI.
Removes filler words, fixes grammar, improves clarity.
"""

from gglisten.cli import clean_cmd

if __name__ == "__main__":
    clean_cmd()
