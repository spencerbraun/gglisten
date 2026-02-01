# gglisten

Local speech-to-text using whisper.cpp with Raycast integration.

## Features

- **Fast local transcription** - Uses whisper.cpp, no cloud API needed
- **Raycast integration** - Toggle recording with a hotkey
- **Auto-paste** - Transcribed text is copied and pasted automatically
- **History** - SQLite database of all transcriptions

## Requirements

- macOS
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (`brew install whisper-cpp`)
- [sox](https://sox.sourceforge.net/) (`brew install sox`)
- A whisper model (e.g., `ggml-large-v3-turbo-q5_0.bin`)

## Installation

```bash
# Clone the repo
git clone https://github.com/spencerbraun/gglisten.git
cd gglisten

# Create a venv and install
uv venv
uv pip install -e .
```

## Raycast Setup

1. Add `scripts/raycast/` to your Raycast script directories
2. Update the shebang in each script to point to your venv's Python:
   ```python
   #!/path/to/your/.venv/bin/python
   ```

## Usage

### Raycast Commands

- **gGlisten** - Toggle recording on/off. First press starts, second press stops and transcribes.
- **gGlisten Status** - Show current recording status and last transcription
- **gGlisten History** - Show recent transcriptions
- **gGlisten Clean** - Clean up clipboard text using AI (requires Anthropic API key)

### CLI

```bash
gglisten              # Toggle recording
gglisten toggle       # Same as above
gglisten status       # Show status
gglisten history      # Show recent transcriptions
gglisten transcribe   # Transcribe last recording
```

## Configuration

Default paths (in `gglisten/config.py`):

- Whisper model: `~/Library/Application Support/com.prakashjoshipax.VoiceInk/WhisperModels/ggml-large-v3-turbo-q5_0.bin`
- Whisper CLI: `/opt/homebrew/bin/whisper-cli`
- Database: `~/.local/share/gglisten/transcriptions.db`
- Temp files: `/tmp/gglisten/`

## License

MIT
