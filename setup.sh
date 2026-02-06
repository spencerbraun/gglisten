#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() { echo -e "${BLUE}==>${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}!${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/gglisten"
CONFIG_DIR="$HOME/.config/gglisten"
VENV_DIR="$INSTALL_DIR/.venv"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         gglisten installer           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check for Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    print_warning "Not running on Apple Silicon - parakeet-mlx won't work"
    print_warning "Will use whisper backend instead"
    DEFAULT_BACKEND="whisper"
else
    DEFAULT_BACKEND="parakeet"
fi

# Check dependencies
print_step "Checking dependencies..."

if ! command -v ffmpeg &> /dev/null; then
    print_error "ffmpeg not found. Install with: brew install ffmpeg"
    exit 1
fi
print_success "ffmpeg found"

if ! command -v uv &> /dev/null; then
    print_error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
print_success "uv found"

# Create directories
print_step "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
print_success "Created $INSTALL_DIR"
print_success "Created $CONFIG_DIR"

# Create virtual environment
print_step "Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    print_warning "Existing venv found, removing..."
    rm -rf "$VENV_DIR"
fi
uv venv "$VENV_DIR" --python 3.12
print_success "Created venv at $VENV_DIR"

# Install gglisten
print_step "Installing gglisten..."
uv pip install -e "$SCRIPT_DIR" --python "$VENV_DIR/bin/python"
print_success "Installed gglisten"

# Ask for backend preference
echo ""
print_step "Choose transcription backend:"
echo "  1) parakeet - NVIDIA's Parakeet via MLX (faster, better accuracy, Apple Silicon only)"
echo "  2) whisper  - OpenAI's Whisper via whisper.cpp (works everywhere)"
echo ""

if [[ "$DEFAULT_BACKEND" == "parakeet" ]]; then
    read -p "Choice [1]: " backend_choice
    backend_choice=${backend_choice:-1}
else
    read -p "Choice [2]: " backend_choice
    backend_choice=${backend_choice:-2}
fi

if [[ "$backend_choice" == "1" ]]; then
    BACKEND="parakeet"
    print_step "Installing parakeet-mlx..."
    # Install numba first to avoid dependency resolution issues
    uv pip install "numba>=0.58" --python "$VENV_DIR/bin/python"
    uv pip install parakeet-mlx --python "$VENV_DIR/bin/python"
    print_success "Installed parakeet-mlx"
    echo ""
    print_step "Parakeet model will download on first use (~600MB)"
else
    BACKEND="whisper"
    # Check for whisper-cli
    if ! command -v whisper-cli &> /dev/null && ! [ -f /opt/homebrew/bin/whisper-cli ]; then
        print_warning "whisper-cli not found"
        read -p "Install whisper.cpp with brew? [Y/n]: " install_whisper
        install_whisper=${install_whisper:-Y}
        if [[ "$install_whisper" =~ ^[Yy]$ ]]; then
            brew install whisper-cpp
        fi
    fi

    # Download whisper model if needed
    MODEL_PATH="$INSTALL_DIR/ggml-large-v3-turbo-q5_0.bin"
    if [ ! -f "$MODEL_PATH" ]; then
        print_step "Downloading Whisper model (~600MB)..."
        curl -L --progress-bar -o "$MODEL_PATH" \
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
        print_success "Downloaded model"
    else
        print_success "Whisper model already exists"
    fi
fi

# Create config
print_step "Creating config..."
cat > "$CONFIG_DIR/config.json" << EOF
{
  "transcription_backend": "$BACKEND"
}
EOF
print_success "Created config with backend=$BACKEND"

# Create symlink for gglisten command
print_step "Creating gglisten command symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$VENV_DIR/bin/gglisten" "$HOME/.local/bin/gglisten"
print_success "Created symlink at ~/.local/bin/gglisten"

# Raycast scripts are ready to use (they call the fixed venv path)
print_step "Raycast scripts ready at: $SCRIPT_DIR/scripts/raycast/"
print_success "Scripts use: $VENV_DIR/bin/gglisten"

# Build level meter (optional)
echo ""
read -p "Build audio level meter? (requires Rust) [Y/n]: " build_meter
build_meter=${build_meter:-Y}

if [[ "$build_meter" =~ ^[Yy]$ ]]; then
    if command -v cargo &> /dev/null; then
        print_step "Building level meter..."
        cd "$SCRIPT_DIR/level-meter"
        cargo build --release 2>/dev/null

        # Create app bundle
        APP_DIR="$INSTALL_DIR/AudioLevelMeter.app/Contents/MacOS"
        mkdir -p "$APP_DIR"
        cp target/release/level-meter "$APP_DIR/AudioLevelMeter"

        # Create Info.plist
        cat > "$INSTALL_DIR/AudioLevelMeter.app/Contents/Info.plist" << 'EOF'
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

        # Sign the app
        codesign --force --sign - "$INSTALL_DIR/AudioLevelMeter.app" 2>/dev/null
        print_success "Built and signed level meter"
        cd "$SCRIPT_DIR"
    else
        print_warning "Rust not found, skipping level meter build"
        print_warning "Install Rust with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    fi
fi

# Final instructions
echo ""
echo "╔══════════════════════════════════════╗"
echo "║            Setup complete!           ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "  1. Add ~/.local/bin to your PATH (if not already):"
echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "  2. Add Raycast scripts directory:"
echo "     $RAYCAST_DIR"
echo ""
echo "  3. Test it:"
echo "     gglisten status"
echo ""
echo "Configuration: $CONFIG_DIR/config.json"
echo "To switch backends: gglisten config backend <whisper|parakeet>"
echo ""
