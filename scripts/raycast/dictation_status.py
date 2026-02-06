#!/usr/bin/env python3
# ^ Shebang is updated by setup.sh to point to the gglisten venv

# @raycast.title gGlisten Status
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon ℹ️

"""
Show current recording status and last transcription.
"""

from gglisten.cli import status_cmd

if __name__ == "__main__":
    status_cmd()
