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

The assistant can record help requests, invite same-floor residents, record lunch preferences, and read/change reminder settings through the backend tools. Medication confirmations still require the physical meds-taken button. The audio model returns 24 kHz WAV, which the host converts to the speaker's 16 kHz format.

## Ask the patient about lunch

In the dashboard or staff view, enter two meal labels and their dietary categories under “Ask patient about lunch,” then click “Ask patient.” The board polls every two seconds and speaks the queued question. The dashboard moves from “Queued” to “Question spoken” only after the board acknowledges complete playback.

The patient holds button 1, speaks after its beep, then releases it. A clear choice is saved to the question and displayed as “Patient answered.” Short answers such as “the first one” use the queued options as context. An unclear answer prompts clarification rather than completing the question. Staff can cancel an unanswered question before asking another one. This flow currently targets Patient 1 on the connected board.

Backend endpoints: `POST /api/lunch/ask` with `{patient_id, options: [{label, choice}, {label, choice}]}`, `GET /api/lunch`, `GET /api/lunch/pending`, and `POST /api/lunch/ID/spoken` or `/cancel` with `{}`. The voice host serves PCM at `GET /api/voice/prompt` and accepts playback acknowledgement at `POST /api/voice/prompt/ID/played`.
