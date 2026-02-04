# gglisten

Local speech-to-text using whisper.cpp with Raycast integration.

## Features

- **Fast local transcription** - Uses whisper.cpp, no cloud API needed
- **Raycast integration** - Toggle recording with a hotkey
- **Auto-paste** - Transcribed text is copied and pasted automatically
- **Audio level meter** - Visual feedback during recording with real-time audio levels
- **History** - SQLite database of all transcriptions

## Requirements

- macOS
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (`brew install whisper-cpp`)
- [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- [Rust](https://rustup.rs/) (for building the level meter)
- A whisper model (e.g., `ggml-large-v3-turbo-q5_0.bin`)

## Installation

```bash
# Clone the repo
git clone https://github.com/spencerbraun/gglisten.git
cd gglisten

# Create a venv and install
uv venv
uv pip install -e .

# Download a whisper model
mkdir -p ~/.local/share/gglisten
curl -L -o ~/.local/share/gglisten/ggml-large-v3-turbo-q5_0.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin

# Build and install the audio level meter (optional but recommended)
cd level-meter
cargo build --release
mkdir -p ~/.local/share/gglisten/AudioLevelMeter.app/Contents/MacOS
cp target/release/level-meter ~/.local/share/gglisten/AudioLevelMeter.app/Contents/MacOS/AudioLevelMeter

# Create Info.plist for the app bundle
cat > ~/.local/share/gglisten/AudioLevelMeter.app/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AudioLevelMeter</string>
    <key>CFBundleIdentifier</key>
    <string>com.gglisten.audiolevelmetr</string>
    <key>CFBundleName</key>
    <string>AudioLevelMeter</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

# Sign the app bundle
codesign --force --sign - ~/.local/share/gglisten/AudioLevelMeter.app
cd ..
```

To disable the level meter, set `show_level_meter: false` in your config file.

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

Create `~/.config/gglisten/config.json` to override defaults:

```json
{
  "whisper_model": "~/path/to/your/model.bin",
  "whisper_cli": "/opt/homebrew/bin/whisper-cli"
}
```

Alternatively, use environment variables: `GGLISTEN_WHISPER_MODEL`, `GGLISTEN_WHISPER_CLI`.

### Other Paths

- Database: `~/.local/share/gglisten/transcriptions.db`
- Temp files: `/tmp/gglisten/`
- API key (for clean command): `~/.config/gglisten_anthropic_key`
- Level meter app: `~/.local/share/gglisten/AudioLevelMeter.app`

## License

MIT
