"""Long-running daemon for gglisten. Keeps model warm and manages recording."""

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import wave
from enum import Enum
from pathlib import Path

import numpy as np

from .config import get_config

logger = logging.getLogger("gglisten.daemon")

# Number of PCM bytes per chunk fed to the streaming transcriber.
# 16000 Hz * 2 bytes * 1 channel * 1 second = 32000 bytes = 1 second of audio
_CHUNK_BYTES = 32000


class DaemonState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class GGListenDaemon:
    """Main daemon process. Loads model once, handles toggle via Unix socket."""

    def __init__(self):
        self.config = get_config()
        self.state = DaemonState.IDLE
        self.ffmpeg_proc: subprocess.Popen | None = None
        self.recording_start_time: float | None = None
        self.audio_buffer = bytearray()
        self._reader_task: asyncio.Task | None = None
        self._level_meter = None
        self._model = None
        self._model_loaded = False
        self._streamer = None  # StreamingParakeet context manager
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- Model management --

    def _load_model(self):
        """Load transcription model into memory (parakeet only)."""
        if self._model_loaded:
            return

        if self.config.transcription_backend == "parakeet":
            logger.info("Loading parakeet model: %s", self.config.parakeet_model)
            try:
                from parakeet_mlx import from_pretrained
                self._model = from_pretrained(self.config.parakeet_model)
                self._model_loaded = True
                logger.info("Parakeet model loaded successfully")
            except ImportError:
                logger.error("parakeet-mlx not installed")
                raise
        else:
            # Whisper uses external CLI, nothing to preload
            self._model_loaded = True
            logger.info("Whisper backend ready (external CLI)")

    # -- Recording --

    def _start_recording(self) -> dict:
        """Start ffmpeg recording, piping raw PCM to stdout for capture."""
        if self.state != DaemonState.IDLE:
            return {"status": "error", "error": f"Cannot start recording in state {self.state.value}"}

        self.config.ensure_dirs()
        self.audio_buffer = bytearray()
        self.recording_start_time = time.time()

        # Open streaming transcriber for parakeet (enters context manager)
        if self.config.transcription_backend == "parakeet" and self._model:
            self._streamer = self._model.transcribe_stream(
                context_size=(256, 256),
            )
            self._streamer.__enter__()
            logger.info("Streaming transcriber opened")

        # ffmpeg outputs raw PCM s16le to stdout
        try:
            self.ffmpeg_proc = subprocess.Popen(
                [
                    str(self.config.ffmpeg_bin),
                    "-f", "avfoundation",
                    "-i", ":default",
                    "-ar", str(self.config.sample_rate),
                    "-ac", str(self.config.channels),
                    "-f", "s16le",
                    "-acodec", "pcm_s16le",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            if self._streamer:
                self._streamer.__exit__(None, None, None)
                self._streamer = None
            return {"status": "error", "error": f"ffmpeg not found at {self.config.ffmpeg_bin}"}

        # Start async reader to drain ffmpeg stdout into buffer + stream to transcriber
        self._reader_task = self._loop.create_task(self._read_audio_pipe())

        self.state = DaemonState.RECORDING

        # Start level meter (non-critical)
        try:
            from .level_meter import LevelMeter
            self._level_meter = LevelMeter()
            self._level_meter.start()
        except Exception:
            self._level_meter = None

        # Play start sound (non-blocking)
        self._play_sound(self.config.start_sound)

        logger.info("Recording started")
        return {"status": "recording_started"}

    async def _read_audio_pipe(self):
        """Read raw PCM from ffmpeg stdout, buffer it, and feed to streaming transcriber."""
        loop = asyncio.get_event_loop()
        try:
            while self.ffmpeg_proc and self.ffmpeg_proc.stdout:
                # Read in executor to avoid blocking the event loop
                chunk = await loop.run_in_executor(
                    None, self.ffmpeg_proc.stdout.read, _CHUNK_BYTES
                )
                if not chunk:
                    break
                self.audio_buffer.extend(chunk)

                # Feed to streaming transcriber (parakeet only)
                if self._streamer:
                    await loop.run_in_executor(None, self._feed_chunk, chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Audio reader stopped: %s", e)

    def _feed_chunk(self, raw_bytes: bytes):
        """Convert PCM s16le bytes to mx.array and feed to streaming transcriber."""
        try:
            import mlx.core as mx
            # int16 → float32 normalized to [-1, 1]
            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            self._streamer.add_audio(mx.array(samples))
        except Exception as e:
            logger.debug("Feed chunk error: %s", e)

    def _stop_recording(self) -> dict:
        """Stop ffmpeg, get streaming result, save WAV, copy to clipboard."""
        if self.state != DaemonState.RECORDING:
            return {"status": "error", "error": f"Not recording (state: {self.state.value})"}

        self.state = DaemonState.TRANSCRIBING
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0

        # Stop level meter
        try:
            if self._level_meter:
                self._level_meter.stop()
        except Exception:
            pass
        self._level_meter = None

        # Play stop sound
        self._play_sound(self.config.stop_sound)

        # Stop ffmpeg gracefully
        if self.ffmpeg_proc:
            try:
                self.ffmpeg_proc.send_signal(signal.SIGINT)
                self.ffmpeg_proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.ffmpeg_proc.kill()
                    self.ffmpeg_proc.wait(timeout=1)
                except Exception:
                    pass
            self.ffmpeg_proc = None

        # Cancel reader task (it will stop naturally since ffmpeg stdout is closed)
        if self._reader_task and not self._reader_task.done():
            if self._loop:
                self._loop.call_soon_threadsafe(self._reader_task.cancel)
        self._reader_task = None

        # Brief wait for any remaining audio data to be flushed
        time.sleep(0.05)

        # Get transcription result
        text = None
        try:
            text = self._get_transcription_result()
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            self.state = DaemonState.IDLE
            self._play_sound(self.config.error_sound)
            return {"status": "error", "error": str(e)}

        # Save buffer as WAV (for storage/retranscribe)
        audio_path = self.config.audio_file
        if self.audio_buffer:
            self._save_wav(audio_path, self.audio_buffer)
            logger.info("Saved %d bytes of audio to %s (%.1fs)", len(self.audio_buffer), audio_path, duration)
        else:
            audio_path = None

        if not text:
            self.state = DaemonState.IDLE
            self._play_sound(self.config.warning_sound)
            return {"status": "error", "error": "No speech detected"}

        # Save to storage
        try:
            from . import storage
            storage.save(
                text=text,
                duration=duration,
                audio_path=audio_path,
                model=(self.config.parakeet_model
                       if self.config.transcription_backend == "parakeet"
                       else str(self.config.whisper_model.name)),
            )
        except Exception as e:
            logger.warning("Failed to save to storage: %s", e)

        # Copy to clipboard and paste
        try:
            from . import clipboard
            clipboard.copy_and_paste(text)
        except Exception as e:
            logger.warning("Clipboard failed: %s", e)

        self._play_sound(self.config.done_sound)
        self.state = DaemonState.IDLE
        logger.info("Transcription complete: %d words", len(text.split()))

        return {
            "status": "transcription_complete",
            "text": text,
            "duration": round(duration, 2),
            "words": len(text.split()),
        }

    def _get_transcription_result(self) -> str | None:
        """Get transcription from streaming result or fall back to file-based."""
        if self.config.transcription_backend == "parakeet" and self._streamer:
            # Streaming result is already computed — just read it
            try:
                result = self._streamer.result
                text = result.text.strip() if result.text else None
            finally:
                # Exit the streaming context manager
                self._streamer.__exit__(None, None, None)
                self._streamer = None
            return text if text else None

        # Whisper: file-based transcription (no streaming available)
        audio_path = self.config.audio_file
        if not self.audio_buffer:
            return None
        self._save_wav(audio_path, self.audio_buffer)
        return self._transcribe_whisper(audio_path)

    def _save_wav(self, path: Path, pcm_data: bytearray):
        """Write raw PCM s16le buffer as a WAV file."""
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(pcm_data)

    def _transcribe_whisper(self, audio_path: Path) -> str | None:
        """Transcribe using whisper-cli (external process)."""
        config = self.config
        if not config.whisper_cli.exists():
            raise FileNotFoundError(f"whisper-cli not found at {config.whisper_cli}")
        if not config.whisper_model.exists():
            raise FileNotFoundError(f"Whisper model not found at {config.whisper_model}")

        result = subprocess.run(
            [
                str(config.whisper_cli),
                "-m", str(config.whisper_model),
                "-f", str(audio_path),
                "-l", config.language,
                "--no-timestamps",
                "-np",
                "--max-context", "0",
                "--no-fallback",
                "--entropy-thold", "2.4",
                "--temperature", "0.2",
                "--prompt", "Hello, how are you doing? Nice to meet you.",
                "--vad",
                "--vad-model", str(config.whisper_model.parent / "ggml-silero-vad.bin"),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error = result.stderr.strip() if result.stderr else "Unknown error"
            raise RuntimeError(f"Whisper transcription failed: {error}")

        text = result.stdout.strip()
        text = " ".join(text.split())
        return text if text else None

    def _play_sound(self, sound_name: str):
        """Play a system sound non-blocking."""
        if not self.config.enable_sounds:
            return
        sound_path = Path(f"/System/Library/Sounds/{sound_name}.aiff")
        if sound_path.exists():
            try:
                subprocess.Popen(
                    ["afplay", str(sound_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    # -- Command handling --

    def _handle_command(self, data: dict) -> dict:
        """Route a command to the appropriate handler."""
        cmd = data.get("cmd", "")

        if cmd == "toggle":
            if self.state == DaemonState.IDLE:
                return self._start_recording()
            elif self.state == DaemonState.RECORDING:
                return self._stop_recording()
            else:
                return {"status": "busy", "state": self.state.value}

        elif cmd == "ping":
            return {"status": "pong"}

        elif cmd == "status":
            resp = {"state": self.state.value}
            if self.state == DaemonState.RECORDING and self.recording_start_time:
                resp["duration"] = round(time.time() - self.recording_start_time, 1)
            resp["model_loaded"] = self._model_loaded
            resp["backend"] = self.config.transcription_backend
            return resp

        elif cmd == "shutdown":
            # Stop any in-progress recording first
            if self.state == DaemonState.RECORDING:
                if self.ffmpeg_proc:
                    try:
                        self.ffmpeg_proc.kill()
                    except Exception:
                        pass
                if self._level_meter:
                    try:
                        self._level_meter.stop()
                    except Exception:
                        pass
                if self._streamer:
                    try:
                        self._streamer.__exit__(None, None, None)
                    except Exception:
                        pass
                    self._streamer = None
            # Schedule shutdown
            if self._loop:
                self._loop.call_soon(self._loop.stop)
            return {"status": "shutting_down"}

        elif cmd == "reload":
            # Reload config and model
            self._model = None
            self._model_loaded = False
            try:
                self._load_model()
                return {"status": "reloaded"}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        else:
            return {"status": "error", "error": f"Unknown command: {cmd}"}

    # -- Socket server --

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single client connection."""
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                writer.close()
                return

            data = json.loads(line.decode("utf-8"))
            logger.debug("Received command: %s", data.get("cmd"))

            # Handle toggle stop in executor — involves ffmpeg teardown + transcription
            cmd = data.get("cmd", "")
            if cmd == "toggle" and self.state == DaemonState.RECORDING:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self._stop_recording)
            else:
                response = self._handle_command(data)

            response_bytes = (json.dumps(response) + "\n").encode("utf-8")
            writer.write(response_bytes)
            await writer.drain()

        except asyncio.TimeoutError:
            logger.debug("Client connection timed out")
        except Exception as e:
            logger.error("Error handling client: %s", e)
            try:
                error_resp = json.dumps({"status": "error", "error": str(e)}) + "\n"
                writer.write(error_resp.encode("utf-8"))
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _run_server(self):
        """Start the Unix socket server."""
        socket_path = self.config.daemon_socket

        # Clean up stale socket
        if socket_path.exists():
            socket_path.unlink()

        server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(socket_path),
        )
        # Make socket accessible
        os.chmod(str(socket_path), 0o700)

        logger.info("Daemon listening on %s", socket_path)

        async with server:
            await server.serve_forever()

    def run(self):
        """Main entry point. Loads model and starts socket server."""
        config = self.config
        config.ensure_dirs()

        # Set up logging
        log_file = config.daemon_log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(str(log_file)),
                logging.StreamHandler(),
            ],
        )

        logger.info("Starting gglisten daemon (PID %d)", os.getpid())
        logger.info("Backend: %s", config.transcription_backend)

        # Write PID file
        config.daemon_pid_file.write_text(str(os.getpid()))

        # Load model (this is the slow part, ~5-8s for parakeet)
        try:
            self._load_model()
        except Exception as e:
            logger.error("Failed to load model: %s", e)
            self._cleanup()
            raise

        # Set up signal handlers
        def _signal_handler(sig, frame):
            logger.info("Received signal %s, shutting down...", sig)
            if self._loop:
                self._loop.call_soon_threadsafe(self._loop.stop)

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        # Run the event loop
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_server())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt")
        finally:
            logger.info("Daemon shutting down")
            self._cleanup()
            self._loop.close()

    def _cleanup(self):
        """Clean up socket and PID files on exit."""
        config = self.config
        if config.daemon_socket.exists():
            try:
                config.daemon_socket.unlink()
            except OSError:
                pass
        if config.daemon_pid_file.exists():
            try:
                config.daemon_pid_file.unlink()
            except OSError:
                pass

        # Kill any lingering ffmpeg
        if self.ffmpeg_proc:
            try:
                self.ffmpeg_proc.kill()
            except Exception:
                pass

        # Close streaming transcriber
        if self._streamer:
            try:
                self._streamer.__exit__(None, None, None)
            except Exception:
                pass
            self._streamer = None

        # Stop level meter
        if self._level_meter:
            try:
                self._level_meter.stop()
            except Exception:
                pass
