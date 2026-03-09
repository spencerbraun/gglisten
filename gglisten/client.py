"""Thin daemon client for gglisten. Minimal imports for fast startup."""

import json
import socket
from pathlib import Path

# Hardcoded to avoid importing config (which loads user config JSON on import)
_SOCKET_PATH = Path("/tmp/gglisten/daemon.sock")


def send_command(cmd: str, timeout: float = 30.0) -> dict | None:
    """
    Send a command to the daemon and return the JSON response.

    Returns None if the daemon is not running or communication fails.
    """
    sock_path = _SOCKET_PATH
    if not sock_path.exists():
        return None

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(sock_path))

        # Send newline-delimited JSON
        message = json.dumps({"cmd": cmd}) + "\n"
        sock.sendall(message.encode("utf-8"))

        # Read response (read until newline)
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        sock.close()

        if data:
            return json.loads(data.decode("utf-8").strip())
        return None

    except (ConnectionRefusedError, FileNotFoundError, OSError):
        # Daemon not running or stale socket
        _cleanup_stale_socket()
        return None
    except (json.JSONDecodeError, TimeoutError):
        return None


def is_daemon_running() -> bool:
    """Check if the daemon is running by sending a ping."""
    resp = send_command("ping", timeout=2.0)
    return resp is not None and resp.get("status") == "pong"


def _cleanup_stale_socket():
    """Remove stale socket file if daemon is dead."""
    if _SOCKET_PATH.exists():
        try:
            _SOCKET_PATH.unlink()
        except OSError:
            pass
