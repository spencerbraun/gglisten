# gglisten

Local speech-to-text with Raycast integration. Press a hotkey to record, press again to transcribe and paste.

## Features

- **Two transcription backends:**
  - **Parakeet** (recommended) - NVIDIA's state-of-the-art ASR via MLX, optimized for Apple Silicon
  - **Whisper** - OpenAI's Whisper via whisper.cpp, works on any Mac
- **Raycast integration** - Toggle recording with a hotkey
- **Auto-paste** - Transcribed text is copied and pasted automatically
- **Audio level meter** - Visual feedback during recording
- **AI cleanup** - Optional post-processing to clean up transcriptions

## Quick Start

```bash
# Clone and run setup
git clone https://github.com/spencerbraun/gglisten.git
cd gglisten
./setup.sh
```

The setup script will:
1. Create a virtual environment at `~/.local/share/gglisten/.venv`
2. Install gglisten and dependencies
3. Let you choose between Parakeet or Whisper backend
4. Download the appropriate model
5. Configure Raycast scripts
6. Optionally build the audio level meter

## Raycast Setup

After running `setup.sh`:

1. Open Raycast Settings → Extensions → Script Commands
2. Add the scripts directory: `<repo>/scripts/raycast/`
3. Assign a hotkey to "gGlisten" (e.g., `⌥Space`)

## Uninstall

```bash
./uninstall.sh
```

Removes the venv, models, database, and config. Does not remove the git repo.

## Usage

### Raycast Commands

| Command | Description |
|---------|-------------|
| **gGlisten** | Toggle recording. First press starts, second stops and transcribes. |
| **gGlisten Status** | Show recording status and last transcription |
| **gGlisten History** | Show recent transcriptions |
| **gGlisten Clean** | Clean up clipboard text using AI |
| **gGlisten Retranscribe** | Re-transcribe the last recording |

### CLI

```bash
gglisten              # Toggle recording
gglisten status       # Show status
gglisten history      # Show recent transcriptions
gglisten config       # Show all configuration
gglisten config backend parakeet  # Switch to parakeet
gglisten config backend whisper   # Switch to whisper
```

## Configuration

Config file: `~/.config/gglisten/config.json`

```json
{
  "transcription_backend": "parakeet",
  "parakeet_model": "mlx-community/parakeet-tdt-0.6b-v3",
  "whisper_model": "~/.local/share/gglisten/ggml-large-v3-turbo-q5_0.bin",
  "show_level_meter": true
}
```

### Quick config changes

```bash
# Switch backends
gglisten config backend parakeet
gglisten config backend whisper

# Disable level meter
gglisten config show_level_meter false

# Use a different parakeet model
gglisten config parakeet_model mlx-community/parakeet-tdt-1.1b-v2
```

## Requirements

- macOS (Apple Silicon recommended for Parakeet)
- [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Rust](https://rustup.rs/) (optional, for level meter)

For Whisper backend only:
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (`brew install whisper-cpp`)

## Paths

| Item | Location |
|------|----------|
| Virtual environment | `~/.local/share/gglisten/.venv` |
| Config | `~/.config/gglisten/config.json` |
| Database | `~/.local/share/gglisten/transcriptions.db` |
| Whisper model | `~/.local/share/gglisten/ggml-large-v3-turbo-q5_0.bin` |
| Level meter | `~/.local/share/gglisten/AudioLevelMeter.app` |
| Anthropic API key | `~/.config/gglisten_anthropic_key` |

## Troubleshooting

**"parakeet-mlx not installed"**
```bash
~/.local/share/gglisten/.venv/bin/pip install numba>=0.58 parakeet-mlx
```

**"whisper-cli not found"**
```bash
brew install whisper-cpp
```

**Level meter not showing**
```bash
# Rebuild and re-sign
cd level-meter && cargo build --release
cp target/release/level-meter ~/.local/share/gglisten/AudioLevelMeter.app/Contents/MacOS/AudioLevelMeter
codesign --force --sign - ~/.local/share/gglisten/AudioLevelMeter.app
```

## License

MIT
