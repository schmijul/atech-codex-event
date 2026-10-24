#!/usr/bin/env python3
"""Small LAN bridge: board PCM -> transcription -> model -> spoken PCM."""

import io
import json
import os
import secrets
import ssl
import time
import urllib.error
import urllib.request
import wave
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8001
SAMPLE_RATE = 16000
MAX_AUDIO_BYTES = SAMPLE_RATE * 2 * 3
OPENAI_BASE = "https://api.openai.com/v1"
has_disclosed_voice = False


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


def multipart_audio(wav_data):
    boundary = "----voice" + secrets.token_hex(12)
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\ngpt-transcribe\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"utterance.wav\"\r\n"
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav_data + f"\r\n--{boundary}--\r\n".encode()
    return body, "multipart/form-data; boundary=" + boundary


def assistant_reply(transcript):
    global has_disclosed_voice
    request_body = json.dumps({
        "model": "gpt-6-luna",
        "reasoning": {"mode": "standard", "effort": "none"},
        "instructions": "You are a helpful, calm voice assistant for an older adult. Reply in one direct spoken sentence of 10 words or fewer. Do not claim to have changed devices, medication records, or external data unless a tool actually did so.",
        "input": transcript,
        "max_output_tokens": 48,
    }).encode()
    result = json.loads(openai_request("/responses", request_body, "application/json"))
    for item in result.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                reply = content["text"].strip()
                if not has_disclosed_voice:
                    reply = "I'm an AI voice assistant. " + reply
                    has_disclosed_voice = True
                return reply
    raise RuntimeError("model returned no text")


def create_speech(text):
    request_body = json.dumps({
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
        "speed": 1.0,
        "input": text[:500],
        "instructions": "Speak clearly, warmly, and at a natural conversational pace.",
        "response_format": "pcm",
    }).encode()
    pcm_24k = openai_request("/audio/speech", request_body, "application/json")
    # The speech endpoint returns 24 kHz PCM; the board speaker is configured for 16 kHz.
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
            form, content_type = multipart_audio(make_wav(pcm))
            transcription = json.loads(openai_request("/audio/transcriptions", form, content_type))
            print(f"transcription_seconds: {time.monotonic() - started:.2f}", flush=True)
            transcript = transcription.get("text", "").strip()
            if not transcript:
                self.send_error(422, "No speech recognized")
                return
            print("heard:", transcript, flush=True)
            stage_started = time.monotonic()
            reply = assistant_reply(transcript)
            print(f"model_seconds: {time.monotonic() - stage_started:.2f}", flush=True)
            print("reply:", reply, flush=True)
            stage_started = time.monotonic()
            speech = create_speech(reply)
            print(f"speech_seconds: {time.monotonic() - stage_started:.2f}", flush=True)
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
    print(f"Voice bridge listening on http://0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), VoiceHandler).serve_forever()
