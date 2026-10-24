#!/usr/bin/env python3
"""Small LAN bridge: board PCM -> one audio model request -> spoken PCM."""

import base64
import io
import json
import os
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.request
import wave
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from voice_tools import TOOLS

HOST = "0.0.0.0"
PORT = 8001
SAMPLE_RATE = 16000
MAX_AUDIO_BYTES = SAMPLE_RATE * 2 * 3
OPENAI_BASE = "https://api.openai.com/v1"
BACKEND_URL = "http://127.0.0.1:8000"
SESSION_FILE = Path(__file__).with_name(".voice_session.json")
MAX_HISTORY_MESSAGES = 40
has_disclosed_voice = False
conversation_history = []
last_activity = 0
conversation_lock = threading.Lock()
SYSTEM_PROMPT = Path(__file__).with_name("system_prompt.md").read_text()


def call_backend(tool_call):
    function = tool_call["function"]
    body = json.dumps({"request_id": tool_call["id"], "patient_id": 1,
                       "arguments": json.loads(function["arguments"])}).encode()
    request = urllib.request.Request(
        BACKEND_URL + "/api/voice/tools/" + function["name"], data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read())
        print("tool:", function["name"], "result:", result, flush=True)
        return result
    except (urllib.error.URLError, TimeoutError):
        return {"error": "Action could not be confirmed. Do not claim success or retry; check the dashboard."}


def openai_request(path, data, content_type):
    request = urllib.request.Request(
        OPENAI_BASE + path,
        data=data,
        headers={
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
            "Content-Type": content_type,
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def make_wav(pcm):
    samples = array("h", pcm)
    peak = max((abs(sample) for sample in samples), default=0)
    if peak:
        gain = min(20.0, 16000 / peak)
        if gain > 1:
            pcm = array("h", (int(sample * gain) for sample in samples)).tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return output.getvalue()


def transcribe(wav_data):
    boundary = "----voice" + secrets.token_hex(12)
    form = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\ngpt-transcribe\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n"
        "Accurately transcribe personal names, ages, medication terms, and the exact words spoken.\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"utterance.wav\"\r\n"
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav_data + f"\r\n--{boundary}--\r\n".encode()
    result = json.loads(openai_request(
        "/audio/transcriptions",
        form,
        "multipart/form-data; boundary=" + boundary,
    ))
    transcript = result.get("text", "").strip()
    if not transcript:
        raise RuntimeError("no speech recognized")
    return transcript


def save_session():
    temporary_file = SESSION_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps({
        "version": 2,
        "updated_at": last_activity,
        "messages": conversation_history,
    }))
    temporary_file.replace(SESSION_FILE)


def clear_session(reason):
    global conversation_history, has_disclosed_voice, last_activity
    conversation_history = []
    has_disclosed_voice = False
    last_activity = 0
    SESSION_FILE.unlink(missing_ok=True)
    print(f"conversation ended: {reason}", flush=True)


def load_session():
    global conversation_history, has_disclosed_voice, last_activity
    if not SESSION_FILE.exists():
        return
    try:
        session = json.loads(SESSION_FILE.read_text())
        if session.get("version") != 2:
            clear_session("old session format")
            return
        last_activity = float(session["updated_at"])
        conversation_history = session["messages"][-MAX_HISTORY_MESSAGES:]
        has_disclosed_voice = bool(conversation_history)
        print(f"restored conversation: {len(conversation_history) // 2} turns", flush=True)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        clear_session("invalid saved session")


def create_voice_reply(transcript):
    global has_disclosed_voice, conversation_history, last_activity
    disclosure = "Your first words must be: I am an AI voice assistant. " if not has_disclosed_voice else ""
    user_message = {
        "role": "user",
        "content": transcript,
    }
    request_body = json.dumps({
        "model": "gpt-audio-1.5",
        "modalities": ["text", "audio"],
        "audio": {"voice": "marin", "format": "wav"},
        "messages": [
            {
                "role": "system",
                "content": disclosure + SYSTEM_PROMPT + "\nKeep replies to one or two short sentences. Preserve personal facts exactly. Current local time: " + datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="minutes") + ". Timezone: Europe/Berlin.",
            },
            *conversation_history,
            user_message,
        ],
    })
    request_data = json.loads(request_body)
    request_data.update(tools=TOOLS, parallel_tool_calls=False)
    for round_number in range(3):
        request_data["tool_choice"] = "none" if round_number == 2 else "auto"
        result = json.loads(openai_request("/chat/completions", json.dumps(request_data).encode(), "application/json"))
        message = result["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            break
        request_data["messages"].append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            request_data["messages"].append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(call_backend(call))})
    audio = message["audio"]
    transcript = audio.get("transcript", "").strip()
    wav_data = base64.b64decode(audio["data"])
    with wave.open(io.BytesIO(wav_data), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 24000:
            raise RuntimeError("voice model returned an unsupported WAV format")
        pcm_24k = wav.readframes(wav.getnframes())

    # The audio model returns 24 kHz PCM; the board speaker uses 16 kHz.
    samples_24k = memoryview(pcm_24k).cast("h")
    samples_16k = bytearray()
    for index in range(0, len(samples_24k) - 2, 3):
        # Two output samples for every three input samples: 24 kHz -> 16 kHz.
        first = samples_24k[index]
        second = (samples_24k[index + 1] + samples_24k[index + 2]) // 2
        samples_16k.extend(int(first).to_bytes(2, "little", signed=True))
        samples_16k.extend(int(second).to_bytes(2, "little", signed=True))
    has_disclosed_voice = True
    conversation_history.extend([
        user_message,
        {"role": "assistant", "content": transcript},
    ])
    conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]
    last_activity = time.time()
    save_session()
    return transcript, bytes(samples_16k)


class VoiceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_POST(self):
        if self.path == "/api/voice/end":
            with conversation_lock:
                clear_session("end endpoint requested")
            self.send_response(204)
            self.end_headers()
            return
        if self.path != "/api/voice":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 8000 or length > MAX_AUDIO_BYTES or length % 2:
                self.send_error(400, "Expected 0.25-3 seconds of 16 kHz mono PCM")
                return
            pcm = self.rfile.read(length)
            if len(pcm) != length:
                self.send_error(400, "Incomplete audio body")
                return
            print(f"received audio: {length // 2} samples from {self.client_address[0]}", flush=True)
            started = time.monotonic()
            transcript = transcribe(make_wav(pcm))
            print(f"transcription_seconds: {time.monotonic() - started:.2f}", flush=True)
            print("heard:", transcript, flush=True)
            voice_started = time.monotonic()
            with conversation_lock:
                reply, speech = create_voice_reply(transcript)
            print(f"voice_model_seconds: {time.monotonic() - voice_started:.2f}", flush=True)
            print("reply:", reply, flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(speech)))
            self.end_headers()
            self.wfile.write(speech)
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, RuntimeError, ssl.SSLError) as error:
            print("voice request failed:", error, flush=True)
            self.send_error(502, "Voice model request failed; check host log")

    def log_message(self, format_string, *args):
        print(format_string % args, flush=True)


if __name__ == "__main__":
    # Read a local ignored .env beside the script or in the current directory.
    for env_path in (Path(__file__).with_name(".env"), Path.cwd() / ".env"):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in this terminal before starting the voice bridge.")
    load_session()
    print(f"Voice bridge listening on http://0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), VoiceHandler).serve_forever()
