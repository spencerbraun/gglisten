"""macOS notifications and audio feedback"""

import subprocess
from pathlib import Path

from .config import get_config


def notify(
    message: str,
    title: str = "gglisten",
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
    subprocess.run(
        ["osascript", "-e", script],
        check=False,  # Don't fail if notification fails
    )


def play_sound(sound_name: str):
    """
    Play a system sound.

    Args:
        sound_name: Name of sound file (without extension) from /System/Library/Sounds/
    """
    config = get_config()
    if not config.enable_sounds:
        return

    sound_path = Path(f"/System/Library/Sounds/{sound_name}.aiff")
    if sound_path.exists():
        subprocess.run(
            ["afplay", str(sound_path)],
            check=False,
        )


def recording_started():
    """Notification and sound for recording start"""
    config = get_config()
    notify("Recording...", sound=True, sound_name=config.start_sound)


def recording_stopped(preview: str | None = None):
    """Notification and sound for recording stop/transcription complete"""
    config = get_config()
    message = preview[:50] + "..." if preview and len(preview) > 50 else preview or "Done"
    notify(message, title="Transcribed", sound=True, sound_name=config.done_sound)
