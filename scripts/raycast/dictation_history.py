#!/usr/bin/env python3
# ^ Shebang is updated by setup.sh to point to the gglisten venv

# @raycast.title gGlisten History
# @raycast.mode fullOutput
# @raycast.schemaVersion 1
# @raycast.icon 📜

"""
Show recent transcription history.
"""

from gglisten.cli import history_cmd

if __name__ == "__main__":
    history_cmd(limit=10)
