#!/usr/bin/env python3
"""
Piper TTS HTTP Server
Wraps the piper binary in a FastAPI-like HTTP API.

Endpoints:
    POST /tts         — Convert text to speech (returns WAV)
    GET  /health      — Health check
    GET  /voices      — List available voices
    GET  /metrics     — Prometheus metrics

Environment Variables:
    PIPER_MODEL       — Path to ONNX model file
    PIPER_CONFIG      — Path to model config JSON
    PIPER_PORT        — Server port (default: 5000)
    PIPER_THREADS     — Number of inference threads (default: 4)
    PIPER_LENGTH_SCALE — Speech speed multiplier (default: 1.0)
"""

import json
import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL = os.environ.get("PIPER_MODEL", "/models/en_US-lessac-medium.onnx")
MODEL_CONFIG = os.environ.get("PIPER_CONFIG", "/models/en_US-lessac-medium.onnx.json")
PORT = int(os.environ.get("PIPER_PORT", 5000))
THREADS = int(os.environ.get("PIPER_THREADS", 4))
LENGTH_SCALE = float(os.environ.get("PIPER_LENGTH_SCALE", 1.0))

# Simple metrics counters
_metrics = {"requests_total": 0, "requests_failed": 0, "tts_total": 0, "tts_duration_sec": 0.0}


# ---------------------------------------------------------------------------
# Request Handler
# ---------------------------------------------------------------------------
class TTSServer(BaseHTTPRequestHandler):
    """Simple HTTP server for TTS requests."""

    def log_message(self, fmt: str, *args) -> None:
        """Suppress default logging — use structured logging instead."""
        pass

    def _send_json(self, status: int, data: dict) -> None:
        """Send a JSON response with proper headers."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_audio(self, status: int, audio_data: bytes, sample_rate: int = 22050) -> None:
        """Send a WAV audio response."""
        self.send_response(status)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio_data)))
        self.send_header("X-Sample-Rate", str(sample_rate))
        self.end_headers()
        self.wfile.write(audio_data)

    def _send_text(self, status: int, text: str, content_type: str = "text/plain") -> None:
        """Send a plain text response."""
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        _metrics["requests_total"] += 1

        if path == "/health":
            self._handle_health()
        elif path == "/voices":
            self._handle_voices()
        elif path == "/metrics":
            self._handle_metrics()
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        _metrics["requests_total"] += 1

        if path == "/tts":
            self._handle_tts()
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # -- Handlers -----------------------------------------------------------

    def _handle_health(self) -> None:
        """Return health status."""
        health = {
            "status": "healthy",
            "service": "piper-tts",
            "version": "1.0.0",
            "model": os.path.basename(MODEL),
            "timestamp": time.time(),
        }
        self._send_json(200, health)

    def _handle_voices(self) -> None:
        """Return list of available voices."""
        voices = {
            "voices": [
                {
                    "id": "en_US-lessac-medium",
                    "name": "U.S. English (lessac, medium)",
                    "language": "en_US",
                    "quality": "medium",
                    "speaker_id": 0,
                }
            ]
        }
        self._send_json(200, voices)

    def _handle_metrics(self) -> None:
        """Return Prometheus-compatible metrics."""
        lines = [
            "# HELP piper_requests_total Total HTTP requests",
            "# TYPE piper_requests_total counter",
            f'piper_requests_total{{service="piper-tts"}} {_metrics["requests_total"]}',
            "# HELP piper_requests_failed Total failed requests",
            "# TYPE piper_requests_failed counter",
            f'piper_requests_failed{{service="piper-tts"}} {_metrics["requests_failed"]}',
            "# HELP piper_tts_total Total TTS conversions",
            "# TYPE piper_tts_total counter",
            f'piper_tts_total{{service="piper-tts"}} {_metrics["tts_total"]}',
            "# HELP piper_tts_duration_seconds Total TTS processing time",
            "# TYPE piper_tts_duration_seconds counter",
            f'piper_tts_duration_seconds{{service="piper-tts"}} {_metrics["tts_duration_sec"]:.3f}',
        ]
        self._send_text(200, "\n".join(lines) + "\n", "text/plain; version=0.0.4")

    def _handle_tts(self) -> None:
        """Process text-to-speech request."""
        start_time = time.time()

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"error": "Empty request body"})
                _metrics["requests_failed"] += 1
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            text = data.get("text", "").strip()

            if not text:
                self._send_json(400, {"error": "No text provided"})
                _metrics["requests_failed"] += 1
                return

            # Optional parameters
            length_scale = float(data.get("length_scale", LENGTH_SCALE))
            speaker_id = int(data.get("speaker_id", 0))

            # Run piper to generate audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                output_path = tmp.name

            try:
                cmd = [
                    "piper",
                    "--model", MODEL,
                    "--config", MODEL_CONFIG,
                    "--output_file", output_path,
                    "--length_scale", str(length_scale),
                    "--speaker", str(speaker_id),
                ]

                process = subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    capture_output=True,
                    timeout=30,
                )

                if process.returncode != 0:
                    _metrics["requests_failed"] += 1
                    self._send_json(500, {
                        "error": "TTS generation failed",
                        "details": process.stderr.decode("utf-8", errors="replace"),
                    })
                    return

                with open(output_path, "rb") as f:
                    audio_data = f.read()

                _metrics["tts_total"] += 1
                _metrics["tts_duration_sec"] += time.time() - start_time
                self._send_audio(200, audio_data)

            finally:
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

        except json.JSONDecodeError:
            _metrics["requests_failed"] += 1
            self._send_json(400, {"error": "Invalid JSON in request body"})
        except subprocess.TimeoutExpired:
            _metrics["requests_failed"] += 1
            _metrics["tts_duration_sec"] += time.time() - start_time
            self._send_json(504, {"error": "TTS generation timed out (30s)"})
        except Exception as exc:
            _metrics["requests_failed"] += 1
            self._send_json(500, {"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    """Start the TTS HTTP server."""
    server = HTTPServer(("0.0.0.0", PORT), TTSServer)
    print(f"[piper-tts] Server running on http://0.0.0.0:{PORT}")
    print(f"[piper-tts] Model: {MODEL}")
    print(f"[piper-tts] Threads: {THREADS}")
    print(f"[piper-tts] Health: http://localhost:{PORT}/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[piper-tts] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
