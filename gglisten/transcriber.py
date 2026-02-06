"""Transcription backends: whisper.cpp and parakeet-mlx"""

import subprocess
from pathlib import Path

from .config import get_config

# Lazy-loaded parakeet model (kept in memory for fast subsequent transcriptions)
_parakeet_model = None


def transcribe(audio_path: Path | None = None) -> str | None:
    """
    Transcribe audio file using the configured backend.

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

    if config.transcription_backend == "parakeet":
        return _transcribe_parakeet(audio_path)
    else:
        return _transcribe_whisper(audio_path)


def _transcribe_whisper(audio_path: Path) -> str | None:
    """Transcribe using whisper-cli (whisper.cpp)"""
    config = get_config()

    # Verify whisper-cli and model exist
    if not config.whisper_cli.exists():
        raise FileNotFoundError(f"whisper-cli not found at {config.whisper_cli}")
    if not config.whisper_model.exists():
        raise FileNotFoundError(f"Whisper model not found at {config.whisper_model}")

    # Run whisper-cli
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
        error = result.stderr.strip() if result.stderr else "Unknown error"
        raise RuntimeError(f"Whisper transcription failed: {error}")

    # Clean up the output
    text = result.stdout.strip()
    text = " ".join(text.split())

    return text if text else None


def _transcribe_parakeet(audio_path: Path) -> str | None:
    """Transcribe using parakeet-mlx (Apple Silicon optimized)"""
    global _parakeet_model

    try:
        from parakeet_mlx import from_pretrained
    except ImportError:
        raise ImportError(
            "parakeet-mlx is not installed. Install it with: pip install parakeet-mlx"
        )

    config = get_config()

    # Load model on first use (stays in memory for speed)
    if _parakeet_model is None:
        _parakeet_model = from_pretrained(config.parakeet_model)

    # Transcribe
    result = _parakeet_model.transcribe(str(audio_path))

    text = result.text.strip() if result.text else None
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
