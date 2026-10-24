# Voice assistant

The board listens for nearby speech, records up to 3 seconds, and sends it over Wi-Fi to this computer. The computer transcribes it with OpenAI, gets a short response from the model, generates speech, and sends 16 kHz audio back to the board speaker. The first reply identifies the voice as AI generated.

## Start the host service

Connect this computer and the board to the same hotspot. Put `OPENAI_API_KEY` in the local ignored `.env`, then start the service from that directory. The service also accepts an exported environment variable.

```sh
python3 voice_assistant.py
```

The service listens on port 8001. The firmware currently targets `172.20.10.14`, the computer's hotspot address. If that address changes, configure it over USB with `atech send voice_host 172.20.10.14` (replace the address). This setting lasts until the board restarts. Update the default `/api/voice` URL in `slot-8-display/project.yaml` for a permanent change.

The generated voice uses `speed: 0.8` for slower speech, and the board speaker starts at 70% volume.

## Use it

Speak after the board has joined Wi-Fi. Sound level triggers recording; a 900 ms pause ends the utterance. Keep each command under 3 seconds. The board waits for the host's response and then plays it through the speaker. There is an 8-second cooldown between recordings.

For a controlled sound check over USB, run `atech send voice_auto off` and then `atech send voice_record`. Speak immediately after the beep; recording lasts three seconds. Re-enable automatic capture with `atech send voice_auto on`.

The assistant only answers verbally. It has no tools to change medication records or control the board. The OpenAI Speech API currently returns raw 24 kHz PCM; the host converts it to the speaker's 16 kHz format. That Speech API model is deprecated for shutdown on 2027-01-06, so migrate the speech generation step to Realtime before that date.
