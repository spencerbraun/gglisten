"""Command-line interface for gglisten"""

import argparse
import sys
import time
from datetime import datetime

from .config import get_config


def toggle():
    """Toggle recording on/off. Main entry point for dictation."""
    from . import recorder  # Always needed

    if recorder.is_recording():
        # Lazy imports - only needed when stopping
        from . import transcriber, storage, clipboard, notify

        # Get duration before stopping
        state = recorder._read_state()
        duration_so_far = time.time() - state.start_time if state.start_time else 0

        # Immediate feedback
        print(f"Transcribing {duration_so_far:.1f}s...")
        sys.stdout.flush()

        # Sound for stop
        notify.recording_stopped()

        # Stop recording
        success, duration = recorder.stop_recording()
        if not success:
            print("Failed to stop recording")
            notify.transcription_error()
            return 1

        # Get the audio file
        audio_file = recorder.get_audio_file()
        if not audio_file:
            print("No audio file found")
            notify.transcription_error()
            recorder.cleanup()
            return 1

        # Transcribe
        try:
            text = transcriber.transcribe(audio_file)
        except FileNotFoundError as e:
            print(f"Setup error: {e}")
            notify.transcription_error()
            recorder.cleanup()
            return 1
        except RuntimeError as e:
            print(f"Transcription failed: {e}")
            notify.transcription_error()
            recorder.cleanup()
            return 1
        except Exception as e:
            print(f"Error: {e}")
            notify.transcription_error()
            recorder.cleanup()
            return 1

        if not text:
            print("No speech detected")
            notify.transcription_error("no_speech")
            recorder.cleanup()
            return 1

        # Success - save, copy, notify
        word_count = len(text.split())
        config = get_config()
        storage.save(
            text=text,
            duration=duration,
            audio_path=audio_file,
            model=str(config.whisper_model.name),
        )

        clipboard.copy_and_paste(text)
        notify.transcription_success()
        recorder.cleanup()

        # Show preview with word count
        preview = text[:60] + "..." if len(text) > 60 else text
        print(f"{preview} ({word_count} words)")
        return 0
    else:
        # Lazy import - only need notify for start
        from . import notify

        # Start recording
        print("Recording...")
        sys.stdout.flush()

        if recorder.start_recording():
            notify.recording_started()
            return 0
        else:
            print("Mic unavailable - check System Settings > Privacy")
            notify.transcription_error()
            return 1


def transcribe_cmd(audio_path: str | None = None, paste: bool = True):
    """Transcribe an audio file or the last recording"""
    from . import recorder, transcriber, clipboard, notify

    if audio_path:
        from pathlib import Path
        path = Path(audio_path)
    else:
        path = recorder.get_audio_file()

    if not path or not path.exists():
        print("No audio file found")
        notify.transcription_error()
        return 1

    try:
        text = transcriber.transcribe(path)
        if text:
            if paste:
                clipboard.copy_and_paste(text)
                notify.transcription_success()
            word_count = len(text.split())
            preview = text[:60] + "..." if len(text) > 60 else text
            print(f"{preview} ({word_count} words)")
            return 0
        else:
            print("No speech detected")
            notify.transcription_error("no_speech")
            return 1
    except Exception as e:
        print(f"Transcription failed: {e}")
        notify.transcription_error()
        return 1


def history_cmd(limit: int = 10, search_query: str | None = None):
    """Show transcription history"""
    from . import storage

    if search_query:
        records = storage.search(search_query, limit=limit)
    else:
        records = storage.get_recent(limit=limit)

    if not records:
        print("No transcriptions found")
        return 0

    for record in records:
        dt = datetime.fromtimestamp(record.timestamp)
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

        # Truncate text for display
        text = record.text
        if len(text) > 80:
            text = text[:77] + "..."

        duration_str = f" ({record.duration:.1f}s)" if record.duration else ""
        print(f"[{record.id}] {date_str}{duration_str}: {text}")

    return 0


def clean_cmd():
    """Clean up clipboard text using AI"""
    from . import clipboard
    from .ai import processor  # Lazy import - only load when needed

    text = clipboard.get()
    if not text.strip():
        print("Clipboard is empty")
        return 1

    try:
        cleaned = processor.clean_text(text)
        clipboard.copy_and_paste(cleaned)
        print(cleaned)
        return 0
    except Exception as e:
        print(f"AI processing failed: {e}")
        return 1


def status_cmd():
    """Show current recording status"""
    from . import recorder, storage

    if recorder.is_recording():
        print("Recording in progress...")
    else:
        print("Idle")

    # Show recent transcription
    latest = storage.get_latest()
    if latest:
        dt = datetime.fromtimestamp(latest.timestamp)
        print(f"\nLast transcription ({dt.strftime('%H:%M:%S')}):")
        text = latest.text[:100] + "..." if len(latest.text) > 100 else latest.text
        print(f"  {text}")

    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="gglisten",
        description="Local speech-to-text using whisper.cpp",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # toggle command
    subparsers.add_parser("toggle", help="Start or stop recording")

    # transcribe command
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe audio file")
    transcribe_parser.add_argument("file", nargs="?", help="Audio file path")

    # history command
    history_parser = subparsers.add_parser("history", help="Show transcription history")
    history_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of records")
    history_parser.add_argument("-s", "--search", help="Search query")

    # clean command
    subparsers.add_parser("clean", help="Clean up clipboard text using AI")

    # status command
    subparsers.add_parser("status", help="Show current status")

    args = parser.parse_args()

    if args.command == "toggle" or args.command is None:
        # Default to toggle if no command given
        sys.exit(toggle())
    elif args.command == "transcribe":
        sys.exit(transcribe_cmd(args.file))
    elif args.command == "history":
        sys.exit(history_cmd(limit=args.limit, search_query=args.search))
    elif args.command == "clean":
        sys.exit(clean_cmd())
    elif args.command == "status":
        sys.exit(status_cmd())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
