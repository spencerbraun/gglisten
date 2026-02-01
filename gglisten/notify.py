"""macOS audio feedback for gglisten - sound-only, no persistent notifications"""

import subprocess
from pathlib import Path

from .config import get_config


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
    """Sound for recording start - immediate signal to start talking"""
    config = get_config()
    play_sound(config.start_sound)


def recording_stopped():
    """Quick confirmation sound that recording stopped"""
    config = get_config()
    play_sound(config.stop_sound)


def transcription_success():
    """Success sound when transcription completes"""
    config = get_config()
    play_sound(config.done_sound)


def transcription_error(error_type: str = "generic"):
    """Error sound with type differentiation"""
    config = get_config()
    if error_type == "no_speech":
        play_sound(config.warning_sound)  # Softer for "no speech detected"
    else:
        play_sound(config.error_sound)  # Stronger for actual failures
