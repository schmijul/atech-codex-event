# Voice assistant

Hold the slot 1 button while speaking. The board records up to 3 seconds and sends the recording over Wi-Fi to this computer when you release the button. The computer sends one audio request to OpenAI and returns 16 kHz reply audio to the board speaker. The first reply identifies the voice as AI generated.

## Start the host service

Connect this computer and the board to the same hotspot. Put `OPENAI_API_KEY` in the local ignored `.env`, then start the service from that directory. The service also accepts an exported environment variable.

```sh
python3 voice_assistant.py
```

The service listens on port 8001. The firmware currently targets `172.20.10.14`, the computer's hotspot address. If that address changes, configure it over USB with `atech send voice_host 172.20.10.14` (replace the address). This setting lasts until the board restarts. Update the default `/api/voice` URL in `slot-8-display/project.yaml` for a permanent change.

The bridge uses `gpt-audio-1.5` with the `marin` voice. Combining speech understanding, response generation, and speech output in one request removes two serial network calls from the previous pipeline.

## Use it

Wait for the board to join Wi-Fi. Hold the slot 1 button, speak after the beep, and release it when finished. The three-second microphone limit ends and sends a recording automatically if you keep holding the button.

The rotary encoder spans slots 10 and 11. The speaker is temporarily fixed at 100% volume while encoder input is diagnosed. Pressing the encoder still ends the active conversation.

Follow-up requests share up to the previous 20 exchanges. The host first creates an accurate text transcript with `gpt-transcribe`, then stores that text so personal facts are not repeatedly reinterpreted from old audio. Press the volume knob to end the conversation; a low tone confirms that the host cleared it. The conversation has no inactivity timeout and remains in the local ignored `.voice_session.json` across host restarts until explicitly ended.

The assistant only answers verbally. It has no tools to change medication records or control the board. The audio model returns 24 kHz WAV; the host converts it to the speaker's 16 kHz format. The request starts after button release. A persistent Realtime API session is the next step if still lower first-audio latency is required.
