"""Audio level meter UI for visual feedback during recording"""

import os
import signal
import subprocess
from pathlib import Path

from .config import get_config

STOP_FILE = Path("/tmp/gglisten-level-meter-stop")
PID_FILE = Path("/tmp/gglisten-level-meter.pid")


class LevelMeter:
    """Manages the AudioLevelMeter Rust app subprocess"""

    def __init__(self):
        self.process: subprocess.Popen | None = None

    def start(self) -> bool:
        """
        Launch the level meter app.
        Returns True if started successfully, False otherwise.
        """
        config = get_config()

        if not config.show_level_meter:
            return False

        app_path = config.level_meter_app
        if not app_path.exists():
            # Silently skip if app not built
            return False

        # Clean up any stale stop file
        STOP_FILE.unlink(missing_ok=True)

        try:
            self.process = subprocess.Popen(
                [str(app_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Save PID for cross-process stop
            PID_FILE.write_text(str(self.process.pid))
            return True
        except Exception:
            # Don't fail recording if level meter can't start
            self.process = None
            return False

    def stop(self):
        """Signal the app to close gracefully"""
        # Get PID from file if we don't have process handle (cross-process call)
        pid = None
        if self.process:
            pid = self.process.pid
        elif PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
            except (ValueError, OSError):
                pass

        if pid is None:
            return

        try:
            # Check if process is still running
            os.kill(pid, 0)
        except OSError:
            # Process not running
            PID_FILE.unlink(missing_ok=True)
            return

        try:
            # Signal stop via file
            STOP_FILE.touch()

            # Wait for graceful shutdown
            for _ in range(40):  # 2 seconds total
                try:
                    os.kill(pid, 0)
                    import time
                    time.sleep(0.05)
                except OSError:
                    # Process exited
                    break
            else:
                # Timeout - force kill
                os.kill(pid, signal.SIGKILL)
        except Exception:
            # Best effort kill
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

        # Cleanup
        STOP_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
        self.process = None
