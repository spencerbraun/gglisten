"""Clipboard operations for macOS"""

import subprocess


def copy(text: str):
    """Copy text to clipboard using pbcopy"""
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=True,
    )


def paste() -> bool:
    """
    Paste clipboard contents to active window using AppleScript.
    Returns True if successful, False if failed (e.g., no accessibility permission).
    """
    script = '''
    tell application "System Events"
        keystroke "v" using command down
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
    )
    return result.returncode == 0


def copy_and_paste(text: str) -> bool:
    """
    Copy text to clipboard and paste to active window.
    Returns True if paste succeeded, False otherwise (text is still on clipboard).
    """
    copy(text)
    return paste()


def get() -> str:
    """Get current clipboard contents"""
    result = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
    )
    return result.stdout
