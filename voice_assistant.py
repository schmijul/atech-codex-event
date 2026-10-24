#!/usr/bin/env python3
"""LAN bridge: board PCM -> OpenAI audio/tools -> spoken PCM."""

import base64
import io
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
import wave
from array import array
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from voice_tools import TOOLS

HOST = "0.0.0.0"
PORT = 8001
SAMPLE_RATE = 16000
MAX_AUDIO_BYTES = SAMPLE_RATE * 2 * 3
OPENAI_BASE = "https://api.openai.com/v1"
BACKEND_URL = os.environ.get("VOICE_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
LOCAL_TIMEZONE = os.environ.get("VOICE_TIMEZONE", "Europe/Berlin")
PATIENT_ID = int(os.environ.get("VOICE_PATIENT_ID", "1"))
SYSTEM_PROMPT = Path(__file__).with_name("system_prompt.md").read_text()
conversations = {}
conversation_lock = threading.Lock()


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


def call_backend(tool_call, patient_id=1):
    function = tool_call["function"]
    try:
        if function["name"] not in {tool["function"]["name"] for tool in TOOLS}:
            raise ValueError("Unknown voice tool.")
        body = json.dumps({
            "request_id": tool_call["id"], "patient_id": patient_id,
            "arguments": json.loads(function["arguments"])}).encode()
        request = urllib.request.Request(BACKEND_URL + "/api/voice/tools/" + function["name"],
                                         data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        return {"error": "Backend rejected the action.", "http_status": error.code,
                "message": "Do not claim success. Ask the patient to use the dashboard or call button."}
    except (urllib.error.URLError, TimeoutError, ValueError):
        # No automatic retry: a timeout may follow a successful database write.
        return {"error": "Could not confirm whether the action was recorded.",
                "message": "Do not claim success or repeat the action. Check the backend request history."}


def create_voice_reply(wav_data, session_id="board", patient_id=1):
    session_id = (session_id, patient_id)
    now = time.monotonic()
    previous, updated = conversations.get(session_id, ([], 0))
    if now - updated > 600:
        previous = []
    disclosure = "Your first words must be: I am an AI voice assistant. " if not previous else ""
    local_now = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).isoformat(timespec="minutes")
    messages = [{"role": "system", "content": disclosure + SYSTEM_PROMPT +
                 "\nCurrent local time: " + local_now + ". Timezone: " + LOCAL_TIMEZONE + "."}]
    # Keep complete turns so tool results never lose their matching tool calls.
    messages.extend(message for turn in previous for message in turn)
    turn = [{"role": "user", "content": [{"type": "input_audio", "input_audio": {
        "data": base64.b64encode(wav_data).decode(), "format": "wav"}}]}]
    messages.extend(turn)
    for round_number in range(3):
        request_body = json.dumps({
            "model": "gpt-audio-1.5", "modalities": ["text", "audio"],
            "audio": {"voice": "marin", "format": "wav"},
            "messages": messages, "tools": TOOLS,
            "tool_choice": "none" if round_number == 2 else "auto",
            "parallel_tool_calls": False,
        }).encode()
        result = json.loads(openai_request("/chat/completions", request_body, "application/json"))
        message = result["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            break
        if round_number == 2:
            raise RuntimeError("Voice model did not finish its tool calls")
        assistant = {"role": "assistant", "content": message.get("content"), "tool_calls": calls}
        messages.append(assistant)
        turn.append(assistant)
        for tool_call in calls:
            output = {"role": "tool", "tool_call_id": tool_call["id"],
                      "content": json.dumps(call_backend(tool_call, patient_id))}
            messages.append(output)
            turn.append(output)
    audio = message["audio"]
    transcript = audio.get("transcript", "").strip()
    speech = decode_speech(audio)
    turn.append({"role": "assistant", "content": transcript})
    conversations[session_id] = ((previous + [turn])[-6:], time.monotonic())
    return transcript, speech


def decode_speech(audio):
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
    return bytes(samples_16k)


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
        if self.path != "/api/voice":
            self.send_error(404)
            return
        try:
            patient_id = int(self.headers.get("X-Patient-ID", str(PATIENT_ID)))
            if patient_id < 1:
                self.send_error(400, "Invalid patient ID")
                return
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
            # One board turn at a time keeps spoken follow-ups in order.
            with conversation_lock:
                reply, speech = create_voice_reply(make_wav(pcm), self.client_address[0], patient_id)
            print(f"voice_model_seconds: {time.monotonic() - started:.2f}", flush=True)
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
    BACKEND_URL = os.environ.get("VOICE_BACKEND_URL", BACKEND_URL).rstrip("/")
    LOCAL_TIMEZONE = os.environ.get("VOICE_TIMEZONE", LOCAL_TIMEZONE)
    PATIENT_ID = int(os.environ.get("VOICE_PATIENT_ID", str(PATIENT_ID)))
    ZoneInfo(LOCAL_TIMEZONE)
    print(f"Voice bridge listening on http://0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), VoiceHandler).serve_forever()
