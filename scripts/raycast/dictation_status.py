#!/Users/spencerbraun/.raycast_scripts/.venv/bin/python

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
