#!/Users/spencerbraun/.raycast_scripts/.venv/bin/python

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
