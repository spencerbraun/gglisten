#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() { echo -e "${YELLOW}==>${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }

INSTALL_DIR="$HOME/.local/share/gglisten"
CONFIG_DIR="$HOME/.config/gglisten"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║        gglisten uninstaller          ║"
echo "╚══════════════════════════════════════╝"
echo ""

echo "This will remove:"
echo "  - $INSTALL_DIR (venv, models, database, level meter)"
echo "  - $CONFIG_DIR (config file)"
echo "  - ~/.local/bin/gglisten (symlink)"
echo ""

read -p "Continue? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""

if [ -d "$INSTALL_DIR" ]; then
    print_step "Removing $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    print_success "Removed"
else
    echo "  $INSTALL_DIR not found, skipping"
fi

if [ -d "$CONFIG_DIR" ]; then
    print_step "Removing $CONFIG_DIR..."
    rm -rf "$CONFIG_DIR"
    print_success "Removed"
else
    echo "  $CONFIG_DIR not found, skipping"
fi

if [ -L "$HOME/.local/bin/gglisten" ]; then
    print_step "Removing ~/.local/bin/gglisten symlink..."
    rm "$HOME/.local/bin/gglisten"
    print_success "Removed"
else
    echo "  ~/.local/bin/gglisten not found, skipping"
fi

# Clean up temp files
if [ -d "/tmp/gglisten" ]; then
    print_step "Removing /tmp/gglisten..."
    rm -rf "/tmp/gglisten"
    print_success "Removed"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         Uninstall complete!          ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Note: The git repo and Raycast scripts directory were not removed."
echo "Remove them manually if desired."
echo ""
