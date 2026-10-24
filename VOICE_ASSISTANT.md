# Voice assistant

The board listens for nearby speech, records up to 3 seconds, and sends it over Wi-Fi to this computer. The computer transcribes it with OpenAI, gets a short response from the model, generates speech, and sends 16 kHz audio back to the board speaker. The first reply identifies the voice as AI generated.

## Start the host service

Connect this computer and the board to the same hotspot. On the computer, set an OpenAI API key in the terminal without putting it in the firmware or chat, then start the service:

```sh
export OPENAI_API_KEY='your-key'
python3 voice_assistant.py
```

The service listens on port 8001. The firmware currently targets `172.20.10.2`, the computer's hotspot address. If that address changes, update the `/api/voice` URL in `slot-8-display/project.yaml` and rebuild/upload.

## Use it

Speak after the board has joined Wi-Fi. Sound level triggers recording; a 900 ms pause ends the utterance. Keep each command under 3 seconds. The board waits for the host's response and then plays it through the speaker. There is an 8-second cooldown between recordings.

The assistant only answers verbally. It has no tools to change medication records or control the board. The OpenAI Speech API currently returns raw 24 kHz PCM; the host converts it to the speaker's 16 kHz format. That Speech API model is deprecated for shutdown on 2027-01-06, so migrate the speech generation step to Realtime before that date.
