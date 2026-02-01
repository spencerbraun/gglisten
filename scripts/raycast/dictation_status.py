#!/usr/bin/env python3
# NOTE: Update shebang to your venv path, e.g.: #!/path/to/.venv/bin/python

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
