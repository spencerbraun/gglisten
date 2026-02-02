#!/usr/bin/env python3
# NOTE: Update shebang to your venv path, e.g.: #!/path/to/.venv/bin/python

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
