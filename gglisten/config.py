"""Configuration management for gglisten"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_user_config() -> dict:
    """Load user config from ~/.config/gglisten/config.json if it exists"""
    config_file = Path.home() / ".config/gglisten/config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


_user_config = _load_user_config()


def _get_path(key: str, default: str | Path) -> Path:
    """Get path from user config, env var, or default"""
    if key in _user_config:
        return Path(_user_config[key]).expanduser()
    env_key = f"GGLISTEN_{key.upper()}"
    if env_key in os.environ:
        return Path(os.environ[env_key]).expanduser()
    return Path(default).expanduser() if isinstance(default, str) else default


@dataclass
class Config:
    """Configuration for gglisten dictation system"""

    # Whisper model and CLI
    whisper_model: Path = field(default_factory=lambda: _get_path(
        "whisper_model", "~/.local/share/gglisten/ggml-large-v3-turbo-q5_0.bin"))
    whisper_cli: Path = field(default_factory=lambda: _get_path(
        "whisper_cli", "/opt/homebrew/bin/whisper-cli"))
    language: str = "en"

    # Audio recording
    rec_bin: Path = field(default_factory=lambda: Path("/opt/homebrew/bin/rec"))
    sample_rate: int = 16000
    channels: int = 1
    bit_depth: int = 16

    # Storage
    db_path: Path = field(default_factory=lambda: Path.home() / ".local/share/gglisten/transcriptions.db")

    # Temp files
    temp_dir: Path = field(default_factory=lambda: Path("/tmp/gglisten"))

    # AI processing
    anthropic_key_file: Path = field(default_factory=lambda: Path.home() / ".config/gglisten_anthropic_key")
    default_model: str = "anthropic/claude-sonnet-4-5-20250929"

    # Audio feedback
    enable_sounds: bool = True
    start_sound: str = "Ping"      # Recording started
    stop_sound: str = "Tink"       # Recording stopped
    done_sound: str = "Glass"      # Transcription success
    error_sound: str = "Basso"     # Hard error
    warning_sound: str = "Sosumi"  # Soft warning (no speech detected)

    def __post_init__(self):
        """Ensure paths are Path objects"""
        if isinstance(self.whisper_model, str):
            self.whisper_model = Path(self.whisper_model).expanduser()
        if isinstance(self.whisper_cli, str):
            self.whisper_cli = Path(self.whisper_cli)
        if isinstance(self.rec_bin, str):
            self.rec_bin = Path(self.rec_bin)
        if isinstance(self.db_path, str):
            self.db_path = Path(self.db_path).expanduser()
        if isinstance(self.temp_dir, str):
            self.temp_dir = Path(self.temp_dir)
        if isinstance(self.anthropic_key_file, str):
            self.anthropic_key_file = Path(self.anthropic_key_file).expanduser()

    @property
    def audio_file(self) -> Path:
        """Path to the current recording audio file"""
        return self.temp_dir / "recording.wav"

    @property
    def state_file(self) -> Path:
        """Path to the state file"""
        return self.temp_dir / "state.json"

    @property
    def pid_file(self) -> Path:
        """Path to the recording PID file"""
        return self.temp_dir / "rec.pid"

    def ensure_dirs(self):
        """Create necessary directories"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_anthropic_key(self) -> str | None:
        """Read Anthropic API key from file"""
        if self.anthropic_key_file.exists():
            return self.anthropic_key_file.read_text().strip()
        return None


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global config instance"""
    global _config
    if _config is None:
        _config = Config()
        _config.ensure_dirs()
    return _config
