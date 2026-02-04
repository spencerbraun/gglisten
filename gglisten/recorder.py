"""Audio recording using sox/rec"""

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import get_config
from .level_meter import LevelMeter

# Global level meter instance
_level_meter: LevelMeter | None = None


class RecorderState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


@dataclass
class StateInfo:
    state: RecorderState
    pid: int | None = None
    start_time: float | None = None


def _read_state() -> StateInfo:
    """Read current state from file"""
    config = get_config()
    if not config.state_file.exists():
        return StateInfo(state=RecorderState.IDLE)

    try:
        data = json.loads(config.state_file.read_text())
        return StateInfo(
            state=RecorderState(data.get("state", "idle")),
            pid=data.get("pid"),
            start_time=data.get("start_time"),
        )
    except (json.JSONDecodeError, ValueError):
        return StateInfo(state=RecorderState.IDLE)


def _write_state(info: StateInfo):
    """Write state to file"""
    config = get_config()
    data = {
        "state": info.state.value,
        "pid": info.pid,
        "start_time": info.start_time,
    }
    config.state_file.write_text(json.dumps(data))


def _clear_state():
    """Clear state file"""
    config = get_config()
    if config.state_file.exists():
        config.state_file.unlink()
    if config.pid_file.exists():
        config.pid_file.unlink()


def is_recording() -> bool:
    """Check if currently recording"""
    state = _read_state()
    if state.state != RecorderState.RECORDING:
        return False

    # Verify process is actually running
    if state.pid:
        try:
            os.kill(state.pid, 0)  # Signal 0 just checks if process exists
            return True
        except OSError:
            # Process not running, clean up stale state
            _clear_state()
            return False
    return False


def start_recording() -> bool:
    """Start audio recording. Returns True if started successfully."""
    config = get_config()
    config.ensure_dirs()

    if is_recording():
        return False  # Already recording

    # Remove old audio file if exists
    if config.audio_file.exists():
        config.audio_file.unlink()

    # Start recording with ffmpeg (better macOS device support than sox)
    # -f avfoundation: macOS audio/video framework
    # -i ":default": use default audio input device (respects System Settings)
    # -ar 16000: 16kHz sample rate (required by whisper)
    # -ac 1: mono channel
    # -y: overwrite output file
    proc = subprocess.Popen(
        [
            str(config.ffmpeg_bin),
            "-f", "avfoundation",
            "-i", ":default",
            "-ar", str(config.sample_rate),
            "-ac", str(config.channels),
            "-y",
            str(config.audio_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for sox to actually start recording (file created and has data)
    # Poll quickly to minimize delay while ensuring we don't lose audio
    for _ in range(20):  # Up to 100ms
        time.sleep(0.005)  # 5ms intervals
        if config.audio_file.exists() and config.audio_file.stat().st_size > 0:
            break

    # Save state
    _write_state(StateInfo(
        state=RecorderState.RECORDING,
        pid=proc.pid,
        start_time=time.time(),
    ))

    # Also save PID to separate file for robustness
    config.pid_file.write_text(str(proc.pid))

    # Start level meter UI (wrapped in try/except to not break recording)
    global _level_meter
    try:
        _level_meter = LevelMeter()
        _level_meter.start()
    except Exception:
        _level_meter = None

    return True


def stop_recording() -> tuple[bool, float | None]:
    """
    Stop audio recording.
    Returns (success, duration_seconds).
    """
    global _level_meter

    # Stop level meter UI first (wrapped in try/except to not break recording)
    # Always try to stop via LevelMeter - it can find the PID from file even if
    # _level_meter is None (which happens in a new process invocation)
    try:
        lm = _level_meter if _level_meter else LevelMeter()
        lm.stop()
    except Exception:
        pass
    _level_meter = None

    config = get_config()
    state = _read_state()

    if state.state != RecorderState.RECORDING or not state.pid:
        return False, None

    duration = None
    if state.start_time:
        duration = time.time() - state.start_time

    # Send SIGINT to gracefully stop ffmpeg
    try:
        os.kill(state.pid, signal.SIGINT)
        # Wait a bit for the process to finish writing
        time.sleep(0.3)
    except OSError:
        pass  # Process might have already exited

    # Update state
    _write_state(StateInfo(state=RecorderState.TRANSCRIBING))

    return True, duration


def get_audio_file() -> Path | None:
    """Get path to recorded audio file if it exists"""
    config = get_config()
    if config.audio_file.exists():
        return config.audio_file
    return None


def check_audio_has_content(audio_path: Path) -> bool:
    """Check if audio file has actual content (not silence)"""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", str(audio_path),
                "-af", "silencedetect=noise=-50dB:d=0.5",
                "-f", "null", "-"
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # If the entire file is silence, silencedetect will show silence
        # covering the whole duration
        stderr = result.stderr
        # Count silence periods - if there's only one that covers most of the file, it's silent
        silence_starts = stderr.count("silence_start:")
        silence_ends = stderr.count("silence_end:")

        # If we see silence_start but no silence_end, entire file is silent
        if silence_starts > 0 and silence_ends == 0:
            return False
        # If no silence detected at all, there's audio
        if silence_starts == 0:
            return True
        # Otherwise there's some audio
        return True
    except Exception:
        # If check fails, assume there's content
        return True


def cleanup():
    """Clean up state and temp files"""
    _clear_state()
