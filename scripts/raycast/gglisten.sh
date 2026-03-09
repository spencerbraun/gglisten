#!/bin/bash

# @raycast.title gGlisten
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon 🎙️

# Toggle voice dictation on/off.
# First press starts recording, second press stops and transcribes.

SOCK="/tmp/gglisten/daemon.sock"

# Fast path: if daemon socket exists, talk to it directly (~5ms, no Python)
if [ -S "$SOCK" ]; then
    RESP=$(echo '{"cmd":"toggle"}' | nc -U "$SOCK" -w 30 2>/dev/null)

    if [ -n "$RESP" ]; then
        # Parse status from JSON response
        STATUS=$(echo "$RESP" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)

        case "$STATUS" in
            recording_started)
                echo "Recording..."
                exit 0
                ;;
            transcription_complete)
                TEXT=$(echo "$RESP" | sed 's/.*"text":"\([^"]*\)".*/\1/')
                WORDS=$(echo "$RESP" | grep -o '"words":[0-9]*' | cut -d: -f2)
                # Truncate preview
                if [ ${#TEXT} -gt 60 ]; then
                    echo "${TEXT:0:60}... ($WORDS words)"
                else
                    echo "$TEXT ($WORDS words)"
                fi
                exit 0
                ;;
            busy)
                echo "Busy, try again"
                exit 1
                ;;
            error)
                ERR=$(echo "$RESP" | sed 's/.*"error":"\([^"]*\)".*/\1/')
                echo "$ERR"
                exit 1
                ;;
        esac
    fi
    # If nc failed or no response, fall through to Python fallback
fi

# Fallback: full Python path (no daemon running)
~/.local/share/gglisten/.venv/bin/gglisten toggle
