"""macOS notifications and audio feedback"""

import subprocess
from pathlib import Path

from .config import get_config


def notify(
    message: str,
    title: str = "gGlisten",
    sound: bool = True,
    sound_name: str | None = None,
):
    """
    Show a macOS notification.

    Args:
        message: The notification message
        title: The notification title
        sound: Whether to play a sound
        sound_name: Name of sound to play (e.g., "Ping", "Glass")
    """
    if sound_name is None:
        sound_name = "Ping"

    sound_clause = f'sound name "{sound_name}"' if sound else ""

    script = f'display notification "{message}" with title "{title}" {sound_clause}'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def play_sound(sound_name: str, blocking: bool = False):
    """
    Play a system sound.

    Args:
        sound_name: Name of sound file (without extension) from /System/Library/Sounds/
        blocking: If True, wait for sound to finish. If False, play async.
    """
    config = get_config()
    if not config.enable_sounds:
        return

    sound_path = Path(f"/System/Library/Sounds/{sound_name}.aiff")
    if sound_path.exists():
        if blocking:
            subprocess.run(["afplay", str(sound_path)], check=False)
        else:
            subprocess.Popen(
                ["afplay", str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def recording_started():
    """Sound and notification for recording start"""
    config = get_config()
    # Play sound first - this is the immediate signal to start talking
    play_sound(config.start_sound)
    # Then show toast (async, may appear slightly after sound)
    notify("Recording...", sound=False)


def recording_stopped(preview: str | None = None):
    """Notification and sound for recording stop/transcription complete"""
    config = get_config()
    message = preview[:50] + "..." if preview and len(preview) > 50 else preview or "Done"
    notify(message, title="Transcribed", sound=True, sound_name=config.done_sound)
