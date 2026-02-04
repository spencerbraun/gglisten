#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building level-meter..."
cargo build --release

# Create destination directory
INSTALL_DIR="$HOME/.local/share/gglisten"
mkdir -p "$INSTALL_DIR"

# Copy the binary
cp "target/release/level-meter" "$INSTALL_DIR/AudioLevelMeter"

# Sign the binary (required for macOS to allow running from other apps)
echo "Signing binary..."
codesign --force --sign - "$INSTALL_DIR/AudioLevelMeter"

echo "Installed to $INSTALL_DIR/AudioLevelMeter"
