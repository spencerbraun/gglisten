#!/usr/bin/env python3
# ^ Shebang is updated by setup.sh to point to the gglisten venv

# @raycast.title gGlisten Retranscribe
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon 🔄

"""
Retranscribe the last recording.
"""

from gglisten.cli import transcribe_cmd

if __name__ == "__main__":
    transcribe_cmd()
