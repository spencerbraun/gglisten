"""Whisper transcription using whisper-cli"""

import subprocess
from pathlib import Path

from .config import get_config


def transcribe(audio_path: Path | None = None) -> str | None:
    """
    Transcribe audio file using whisper-cli.

    Args:
        audio_path: Path to audio file. If None, uses the default recording path.

    Returns:
        Transcribed text, or None if transcription failed.
    """
    config = get_config()

    if audio_path is None:
        audio_path = config.audio_file

    if not audio_path.exists():
        return None

    # Verify whisper-cli and model exist
    if not config.whisper_cli.exists():
        raise FileNotFoundError(f"whisper-cli not found at {config.whisper_cli}")
    if not config.whisper_model.exists():
        raise FileNotFoundError(f"Whisper model not found at {config.whisper_model}")

    # Run whisper-cli
    # -m: model path
    # -f: input file
    # -l: language (or "auto" for auto-detect)
    # --no-timestamps: don't include timestamps in output
    # -np: no progress output (cleaner stdout)
    result = subprocess.run(
        [
            str(config.whisper_cli),
            "-m", str(config.whisper_model),
            "-f", str(audio_path),
            "-l", config.language,
            "--no-timestamps",
            "-np",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Try to get error info
        error = result.stderr.strip() if result.stderr else "Unknown error"
        raise RuntimeError(f"Whisper transcription failed: {error}")

    # Clean up the output
    text = result.stdout.strip()

    # whisper-cli sometimes outputs extra whitespace or newlines
    text = " ".join(text.split())

    return text if text else None


def get_audio_duration(audio_path: Path) -> float | None:
    """Get duration of audio file in seconds using ffprobe"""
    config = get_config()
    ffprobe = config.ffmpeg_bin.parent / "ffprobe"

    if not ffprobe.exists():
        return None

    try:
        result = subprocess.run(
            [
                str(ffprobe),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        pass

    return None
