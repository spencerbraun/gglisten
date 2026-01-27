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

    # Start recording with sox/rec
    # -r 16000: 16kHz sample rate (required by whisper)
    # -c 1: mono channel
    # -b 16: 16-bit depth
    proc = subprocess.Popen(
        [
            str(config.rec_bin),
            "-r", str(config.sample_rate),
            "-c", str(config.channels),
            "-b", str(config.bit_depth),
            str(config.audio_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for sox to actually start recording (file created and has data)
    # This prevents losing the first ~200ms of audio
    for _ in range(20):  # Up to 200ms
        time.sleep(0.01)
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

    return True


def stop_recording() -> tuple[bool, float | None]:
    """
    Stop audio recording.
    Returns (success, duration_seconds).
    """
    config = get_config()
    state = _read_state()

    if state.state != RecorderState.RECORDING or not state.pid:
        return False, None

    duration = None
    if state.start_time:
        duration = time.time() - state.start_time

    # Send SIGINT to gracefully stop sox
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


def cleanup():
    """Clean up state and temp files"""
    _clear_state()
