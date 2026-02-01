#!/usr/bin/env python3
# NOTE: Update shebang to your venv path, e.g.: #!/path/to/.venv/bin/python

# @raycast.title gGlisten
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon 🎙️

"""
Toggle voice dictation on/off.
First press starts recording, second press stops and transcribes.
"""

from gglisten.cli import toggle

if __name__ == "__main__":
    toggle()
