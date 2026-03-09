"""Daemon lifecycle management: start, stop, restart, launchd integration."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import get_config

_LAUNCHD_LABEL = "com.gglisten.daemon"


def _get_daemon_pid() -> int | None:
    """Read the daemon PID from its PID file. Returns None if not running."""
    config = get_config()
    pid_file = config.daemon_pid_file

    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Verify process is alive
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        # Stale PID file
        try:
            pid_file.unlink()
        except OSError:
            pass
        return None


def is_running() -> bool:
    """Check if daemon is running via PID file."""
    return _get_daemon_pid() is not None


def start_daemon(foreground: bool = False) -> bool:
    """
    Start the daemon process.

    Args:
        foreground: If True, run in the current process (blocking).
                    If False, fork to background.

    Returns True if started successfully.
    """
    if is_running():
        print("Daemon is already running")
        return False

    config = get_config()
    config.ensure_dirs()

    # Clean up stale socket
    if config.daemon_socket.exists():
        try:
            config.daemon_socket.unlink()
        except OSError:
            pass

    if foreground:
        # Run in current process (blocking)
        from .daemon import GGListenDaemon
        daemon = GGListenDaemon()
        daemon.run()
        return True

    # Fork to background
    # Find the gglisten executable
    gglisten_bin = _find_gglisten_bin()
    if not gglisten_bin:
        print("Cannot find gglisten executable")
        return False

    log_file = config.daemon_log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Start daemon subprocess
    with open(str(log_file), "a") as log_fd:
        proc = subprocess.Popen(
            [str(gglisten_bin), "daemon", "foreground"],
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,  # Detach from terminal
        )

    # Wait for daemon to be ready (socket created)
    for _ in range(100):  # Up to 10s
        time.sleep(0.1)
        if config.daemon_socket.exists():
            # Verify it responds to ping
            from .client import is_daemon_running
            if is_daemon_running():
                print(f"Daemon started (PID {proc.pid})")
                return True

    print("Daemon started but not responding yet (model may still be loading)")
    print(f"Check logs: {log_file}")
    return True


def stop_daemon() -> bool:
    """Stop the daemon gracefully. Returns True if stopped."""
    # Try socket shutdown first
    from .client import send_command
    resp = send_command("shutdown", timeout=5.0)
    if resp and resp.get("status") == "shutting_down":
        # Wait for process to exit
        for _ in range(30):  # Up to 3s
            time.sleep(0.1)
            if not is_running():
                print("Daemon stopped")
                return True

    # Fallback to SIGTERM via PID
    pid = _get_daemon_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for exit
            for _ in range(30):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    print("Daemon stopped")
                    return True
            # Force kill
            os.kill(pid, signal.SIGKILL)
            print("Daemon killed")
            return True
        except OSError:
            pass

    # Clean up stale files
    config = get_config()
    for f in [config.daemon_socket, config.daemon_pid_file]:
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass

    print("Daemon was not running")
    return False


def restart_daemon() -> bool:
    """Restart the daemon."""
    stop_daemon()
    time.sleep(0.5)
    return start_daemon()


def daemon_status() -> dict:
    """Get daemon status info."""
    from .client import send_command
    pid = _get_daemon_pid()

    if not pid:
        return {"running": False}

    resp = send_command("status", timeout=2.0)
    if resp:
        resp["running"] = True
        resp["pid"] = pid
        return resp

    return {"running": True, "pid": pid, "responsive": False}


# -- launchd integration --

def _launchd_plist_path() -> Path:
    """Path to the launchd plist file."""
    return Path.home() / "Library/LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"


def _find_gglisten_bin() -> Path | None:
    """Find the gglisten executable."""
    # Check common locations
    candidates = [
        Path.home() / ".local/bin/gglisten",
        Path.home() / ".local/share/gglisten/.venv/bin/gglisten",
    ]
    # Also check PATH
    import shutil
    path_bin = shutil.which("gglisten")
    if path_bin:
        candidates.insert(0, Path(path_bin))

    for p in candidates:
        if p.exists():
            return p
    return None


def install_launchd() -> bool:
    """Install launchd service for auto-starting daemon at login."""
    gglisten_bin = _find_gglisten_bin()
    if not gglisten_bin:
        print("Cannot find gglisten executable. Is it installed?")
        return False

    config = get_config()
    log_file = config.daemon_log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{gglisten_bin}</string>
        <string>daemon</string>
        <string>foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_file}</string>
    <key>StandardErrorPath</key>
    <string>{log_file}</string>
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
"""

    plist_path = _launchd_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Unload existing if present
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )

    plist_path.write_text(plist_content)

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"Installed launchd service: {_LAUNCHD_LABEL}")
        print(f"Daemon will auto-start at login")
        print(f"Logs: {log_file}")
        return True
    else:
        print(f"Failed to load launchd service: {result.stderr}")
        return False


def uninstall_launchd() -> bool:
    """Remove launchd service."""
    plist_path = _launchd_plist_path()

    if not plist_path.exists():
        print("Launchd service not installed")
        return False

    subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
    )

    plist_path.unlink()
    print(f"Uninstalled launchd service: {_LAUNCHD_LABEL}")

    # Also stop daemon if running
    stop_daemon()
    return True
