# Voice assistant

Hold the slot 1 button while speaking. The board records up to 3 seconds and sends the recording over Wi-Fi to this computer when you release the button. The computer transcribes it, generates a spoken reply, and returns 16 kHz audio to the board speaker. The first reply identifies the voice as AI generated.

## Start the host service

Connect this computer and the board to the same hotspot. Put `OPENAI_API_KEY` in the local ignored `.env`, then start the service from that directory. The service also accepts an exported environment variable.

```sh
python3 voice_assistant.py
```

The service listens on port 8001. The firmware currently targets `172.20.10.14`, the computer's hotspot address. If that address changes, configure it over USB with `atech send voice_host 172.20.10.14` (replace the address). This setting lasts until the board restarts. Update the default `/api/voice` URL in `slot-8-display/project.yaml` for a permanent change.

The bridge uses `gpt-transcribe` for the input transcript and `gpt-audio-1.5` with the `marin` voice for the spoken answer.

On this computer the voice service is installed in the permanent `atech-codex-voice` checkout. The local LaunchAgent at `~/Library/LaunchAgents/local.atech.voice.plist` starts it when the user logs in and restarts it if it exits. It reads the existing ignored `.env` in the `atech-codex-event` working directory; no API key is embedded in the LaunchAgent. Logs are in `~/Library/Logs/atech-voice/`. Use `launchctl kickstart -k gui/$(id -u)/local.atech.voice` after changing the script.

## Use it

Wait for the board to join Wi-Fi. Hold the slot 1 button, speak after the beep, and release it when finished. The three-second microphone limit ends and sends a recording automatically if you keep holding the button.

The speaker stays at 100% volume. No rotary encoder is required.

Follow-up requests share up to the previous 20 exchanges. The host transcribes speech with `gpt-transcribe` and stores text so personal facts are not repeatedly reinterpreted from old audio. The conversation has no inactivity timeout and remains in the local ignored `.voice_session.json` across host restarts until explicitly ended. To start fresh, run `curl -X POST http://localhost:8001/api/voice/end` on the host.

The assistant only answers verbally. It has no tools to change medication records or control the board. The audio model returns 24 kHz WAV; the host converts it to the speaker's 16 kHz format. The request starts after button release. A persistent Realtime API session is the next step if still lower first-audio latency is required.
