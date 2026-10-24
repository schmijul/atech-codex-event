# Development diary

## 2026-10-24 — Microphone input proof of concept

- Created isolated branch `codex/microphone-input` in `/tmp/atech-microphone-input`; the primary worktree has unrelated local edits and was not modified.
- Inspected the installed SDK catalog (`atech list-modules`, `atech info microphone`, and `atech info speaker`). The exact microphone module is ICS-43434, spans adjacent ports 5 and 6, starts a background capture task on I2S_NUM_1, and emits RMS sound level as `microphone_level` every 250 ms. Speaker on ports 3–4 uses I2S_NUM_0, so the buses do not conflict.
- The module API also exposes `startRecording()`, `stopRecording()`, `isRecording()`, `getRecording()` and `getRecordingLength()` for up to 3 seconds of PCM capture. The SDK does not include speech recognition or a live audio-to-host stream; audio transcription requires an additional host/service path.
- Added the catalog microphone module at ports [5, 6]. Its template automatically reports sound levels, so no custom loop code or behavior changes to the medication buttons are necessary. This is an audio-input/sound activity proof of concept, not speech-to-text.
- `atech validate slot-8-display` passed with the microphone placement. The first build lacked the ignored local `.wifi_secrets.h`; temporarily copied that local file for compilation, then removed it. The subsequent PlatformIO build succeeded (25.9% RAM, 31.9% flash). Restored generated `build/` outputs afterward so only source and diary changes remain. No board flash or API write was made.
- Follow-up hardware check: flashed this proof-of-concept to the connected board at `/dev/cu.usbmodem101`. `atech check` reported the microphone initialized (no module read-back is available). The serial monitor streamed `microphone_level` every 250 ms: quiet room readings were usually 70–340, and while the user clapped/tapped the peaks reached 628, 740, and 1142. This verifies sound input on the attached module. No medication button was pressed and no API POST occurred. Stopped the monitor, removed the temporary Wi-Fi secrets copy, and restored generated build artifacts.

## 2026-10-24 — Medication reminder

- Request: display “Have you taken your meds?”, play a reminder sound, and show “Meds taken” after a button press.
- Existing project: `slot-8-display/project.yaml`, 14-port board, display on 13–14 and speaker on 3–4. Preserve the local display driver fix documented in `slot-8-display/DISPLAY_FIX.md`.
- Read the project instructions: edit YAML, not generated `build/`; use nonblocking timing and the catalog button API; validate before building.
- Asked for the button port because it is not present in the existing configuration. Button wiring must be confirmed before adding it or flashing firmware.
- `atech` is not on the shell PATH. Existing documentation points to the repository `.venv/bin/atech`; use that executable instead.
- Intended behavior: reminder at startup and every 30 seconds until acknowledged; a button press stops the sound and leaves “Meds taken” visible until restart. No medication schedule was supplied.
- User confirmed button on port 9, display 13–14, speaker 3–4. SDK catalog confirms `button.wasPressed()`, `speaker.playNote()`, and `speaker.stop()`.
- Placement validation passed. First upload failed because PlatformIO was not on PATH; reran with the virtual environment bin directory on PATH.
- Inspected speaker implementation: back-to-back `playNote()` calls overwrite its pending queue instead of reliably sequencing. Simplified reminder to one 180 ms C5 note.
- Implemented prompt and green confirmation screen in YAML, using one press-edge read per loop and `millis()` for 30-second reminders. Preserved the known-working delayed display initialization and status/refresh actions. First chime starts after this refresh, rather than during setup.
- Final firmware compiled and uploaded successfully to `/dev/cu.usbmodem101` after the single-note change. `atech check` reports display, speaker, and button initialized, with no physical read-back available for these modules. The board answered `display_status` with “Have you taken your meds?”.
- Remaining physical verification: user must confirm visible prompt, audible chime, and that pressing port-9 button changes the display to “Meds taken” and stops subsequent reminders. Serial state is not proof of visible/audible output.
- User requested a spoken “Take your meds” reminder instead of the chime. Generated a 16 kHz mono voice clip and IMA ADPCM-compressed it 4:1 so it fits in firmware without an added audio library.
- Added the embedded clip and lightweight decoder. Validation and a full PlatformIO build succeeded; firmware uses 9.9% RAM and 11.8% flash.
- For future dashboard tracking, confirmed the firmware emits a `state` event with key `meds_taken` and boolean value `true` once on button press. The installed Atech Python package exposes `Board.connect(port=...)` and filtered `board.events(types=[...], keys=[...])`, so the host logger can safely consume events through the SDK while owning the serial connection.
- Added `meds_logger.py`, a small host-side service that writes UTC timestamps to SQLite, plus `MEDICATION_LOGGING.md` with run commands and the dashboard query. Kept the default serial port at `/dev/cu.usbmodem101` and made `--port`/`--db` overrides available. Did not open the hardware port while the firmware work may be using it.
- Replaced the earlier local synthetic clip with ElevenLabs Flash v2.5 output: Sarah's reassuring voice at 0.8× speed, speaking “Take your meds.” The response was raw PCM, downsampled to 8 kHz, IMA ADPCM-compressed, then expanded to 16 kHz on the board during playback. This preserves the 1.16-second phrasing without an MP3 decoder.
- The updated firmware validated and built successfully: 18.3% RAM and 11.9% flash.
- User added a second button in slot 1. Configured it as resetButton: pressing it clears the meds-taken acknowledgement, redraws the question, and causes the spoken reminder to replay immediately. It does not create a medication-taken database entry.

## 2026-10-24 — Home assistant demo video

- User asked to pull the newest project version and create a demo video for an Atech Small Kit used as a home assistant for an elderly person: medication reminder with sound, display prompt, and confirmation; second concept is a voice agent using the board microphone and speaker.
- Pulled `origin/main` via fast-forward before examining the project. Existing firmware source already has the medication prompt/chime/button acknowledgement on the 14-port board. No voice-agent code or video asset exists.
- Created a 10-second, 720×1280 concept animation with ffmpeg and Pillow: first segment illustrates reminder and confirmation, second segment is explicitly labeled as the planned voice assistant concept. Added preview and README to `demo/`.
- Limitation: this is a designed animation, not live footage of the physical kit. Hardware imagery is illustrative; no microphone module is specified in the current project. Voice interaction is not implemented yet.

## 2026-10-24 — Rebuilt the animation in Python

- User rejected the first animation and requested a Python implementation.
- Added `demo/create_video.py`: a self-contained Pillow/NumPy renderer with ffmpeg encoding, smooth entry motion, sound-wave animation, animated hand and button press, medication confirmation, and a scripted voice-agent concept.
- Expanded the film to 30 seconds in landscape 1280×720 at 24 fps so the text and interaction have room. Added generated chime/button audio and local espeak dialogue.
- Saved reproducible source and regeneration instructions in the repo. Generated cover and six-beat storyboard; visually inspected the storyboard for layout and legibility. Matched the speaking state to the dialogue start after reviewing the storyboard.
- Board illustration is conceptual; existing physical firmware and wiring are unchanged. Voice remains explicitly labeled as a concept.

## 2026-10-24 — Local medication dashboard

- Resolved the diary conflict left by the previous pull by preserving both the incoming firmware/logger notes and the local demo notes.
- Inspected the live SQLite schema: medication_events contains id and taken_at_utc; the database currently has one confirmation.
- Added dashboard.py, a single standard-library HTTP server with a read-only SQLite endpoint, local-time history, today/total/latest summaries, pagination, and five-second refresh. Bound to localhost; no dependencies or database writes.
- Today is calculated in the browser timezone. Counts represent button confirmations, not scheduled-dose adherence.

## 2026-10-24 — Wi-Fi write API

- Changed dashboard.py to listen on 0.0.0.0:8000 and added POST /api/events. An empty JSON object records server UTC time; optional taken_at_utc must include a timezone and is normalized to UTC.
- Kept inserts parameterized, limited request bodies to 4 KB, and added JSON input/database error responses. Initializes the existing table if absent. No authentication, as requested for shared LAN access.
- Current Wi-Fi interface wlp4s0 has address 172.20.10.5. Documented curl examples, response codes, shared logger access, and network requirements.

## 2026-10-24 — Git handoff

- Verified POST creation, timezone normalization, invalid timestamp rejection, and history reads against a temporary database. Confirmed the running server responds through its Wi-Fi IP; a separate client device has not been checked.
- Prepared dashboard/API source, usage documentation, existing demo source and outputs, and diary for commit. Added Python cache ignores.
- Added API agent instructions including duplicate-write behavior and avoiding blind retries after ambiguous timeouts.
- Validated, built, and uploaded the slot-1 reset firmware to the connected board. The previous local voice sample is now excluded from compilation because the ElevenLabs sample supersedes it.
- New request: send a database event over Wi-Fi to a simple API on this network whenever the meds-taken button is pressed. The board is an ESP32-S3 and supports Wi-Fi; its current event is emitted over USB serial. The computer currently reports no associated AirPort Wi-Fi network, and an interface has IP `172.20.10.2`, so SSID/password and confirmation of the board's network are needed for firmware configuration.
- Added `meds_api.py`, a small standard-library HTTP server that accepts `POST /meds_taken` and stores the API receive timestamp in the existing SQLite table. Documented how to start it and the expected endpoint. Firmware remains pending network credentials and reachable host IP.
- User supplied the iPhone hotspot SSID/password. Kept these in the ignored local `slot-8-display/.wifi_secrets.h`. The host interface IP was `172.20.10.2`; configured a retrying HTTP POST on the existing meds-taken button, with a 3-second request timeout and a success log event. The serial `meds_taken` state event was removed to prevent duplicate DB writes if the legacy USB logger is also running; docs direct users to run only the API.
- `atech validate` passed and the firmware compiled successfully (25.6% RAM, 31.8% flash). Initial build needed the venv bin directory added to PATH. First upload found `/dev/cu.usbmodem101` held by the existing `meds_logger.py`; stopped that logger because the new API replaces it, then upload and flash verification succeeded. Started `meds_api.py`; confirmed it is listening on TCP 8000. Still needs a physical button press to verify the iPhone hotspot association and end-to-end API insert.
- User supplied the actual API contract at `172.20.10.5:8000`: POST `/api/events` with `{}`, GET returns newest-first records. Read-only GET confirmed the service is reachable and returned the existing row (no POST was sent). Updated firmware target and docs to match; this server now replaces the temporary local `meds_api.py` endpoint.
- Applied the API's no-deduplication timeout rule: firmware now retries only explicit 503 responses or a request that fails before starting. An ambiguous negative POST result is logged as `meds_api_uncertain` and is not retried; inspect GET before a manual retry. Other non-201 HTTP responses are logged and not retried.
- Validated, rebuilt, and uploaded the revised endpoint/timeout behavior successfully. The API host IP is currently hardcoded as `172.20.10.5`; if it changes, update the URL in `my_modules/st7735_tft/st7735_tft.h`, rebuild, and upload. No POST was sent during setup; only the read-only GET was used.
- Dashboard still had only the pre-existing row, confirming the board has not produced a successful POST. Added serial `wifi_status` transitions and `meds_button` logs for read-only diagnosis; these do not write to the API. USB port is available for a monitor check.
- Observed board button event in serial diagnostics, but Wi-Fi status alternated `1` (SSID unavailable) and `6` (disconnected), even after the user enabled iPhone Maximize Compatibility and firmware tried `iPhone von Julian` capitalization. The API database still contains only the original row. Replaced blind `WiFi.begin` retry with async visible-network scans, logging the visible AP count and whether the configured SSID (case-insensitive) is present; when found, connect using the broadcast spelling.
- Final verification succeeded: scan found the hotspot among 24 visible networks; the firmware connected (status 3), observed the button event, and logged `meds_api_saved` (only on HTTP 201). Read-only GET showed new row id 2 at 2026-10-24T11:04:35+00:00. The SSID scan matched case-insensitively and connects using the exact broadcast spelling. No test POST was sent.

## 2026-10-24 — Voice assistant bridge

- User asked to route voice commands from the board through a model and play the response on its speaker, using the OpenAI API for speech-to-text.
- Added a small standard-library LAN server at `voice_assistant.py`: accepts up to 3 seconds of 16 kHz mono PCM, wraps it as WAV for `gpt-transcribe`, asks `gpt-6-luna` for a short reply, generates PCM speech, downsamples 24 kHz output to the board's 16 kHz speaker rate, and returns raw PCM. The API key is read only from the host's `OPENAI_API_KEY` environment.
- Wired firmware voice activity capture to the microphone on ports 5–6. It starts at a measured sound-level threshold, stops after 900 ms of quiet or the microphone's 3-second cap, POSTs audio to the host at `172.20.10.2:8001`, and streams the returned samples into the speaker on ports 3–4. It requires at least 0.75 seconds of captured audio and has an 8-second cooldown.
- Reference: OpenAI docs recommend `gpt-transcribe` for completed audio files and document the Speech API's raw PCM as 24 kHz signed 16-bit little-endian. `gpt-4o-mini-tts` remains usable but is deprecated for shutdown on 2027-01-06; plan migration to Realtime before then.
- The host currently has no `OPENAI_API_KEY` environment variable. A live transcription/model/TTS round trip cannot be verified until the user starts the service in a terminal with a configured key. Do not ask the user to paste the key into chat.
- Validated the YAML, compiled the host script, built the firmware, and uploaded it to `/dev/cu.usbmodem101`. `atech check` reports display, speaker, microphone, and both buttons initialized; live Wi-Fi status reached connected (3). A compiler warning showed that 90,000 ms overflowed the board HTTP timeout type; changed it to 60,000 ms and rebuilt/uploaded. No OpenAI request was made because the host key is missing.

## 2026-10-24 — Live voice transcription check and credential cleanup

- Removed the tracked `.env` from the public remote branch histories; local `.env` files stay private and ignored. The previously published ElevenLabs key must still be rotated. No key values were printed.
- User added an OpenAI key to the ignored local `.env`. Authentication/model listing succeeded for the transcription, response, and speech models. Added automatic loading from a local ignored `.env`.
- First requested board utterance did not reach the host: board Wi-Fi status alternated SSID unavailable/disconnected. The computer hotspot IP changed to `172.20.10.3`. Updated the default voice endpoint and added a `voice_host` serial action for later address changes.
- Corrected 24-to-16 kHz speech conversion to produce two samples per three input samples. Reset the microphone cooldown after playback and reminder audio to avoid recording the speaker response. Live capture/transcription verification is in progress.
- Host-only transcription test passed: a generated speech fixture saying "Hello, can you hear me?" returned that exact transcript from OpenAI. A full request to the local `/api/voice` service then returned HTTP 200 and 192,000 bytes of 16 kHz reply audio (6 seconds). These are host checks, not proof of board audio delivery.
- Updated firmware built and uploaded successfully. The board scan sees 35 nearby networks but reports `target_visible: false` for the configured hotspot. Waiting for the user to enable the hotspot compatibility settings before repeating a physical speech test.
- Diagnosed the Wi-Fi mismatch with macOS network information: the computer is on "Easwaran’s iPhone" using channel 44 / 5 GHz, while board credentials target "iPhone von Julian". Asked the user to choose a common hotspot; the current board cannot see Julian’s AP. The board supports 2.4 GHz, so the chosen iPhone hotspot needs Maximize Compatibility.

## 2026-10-24 — Mohit hotspot migration

- User supplied a new hotspot. macOS joined the actual broadcast name “Mohit’s iPhone” (curly apostrophe); the ASCII apostrophe name did not match. Updated ignored local Wi-Fi configuration without logging the password. Computer address is `172.20.10.14`; updated the voice and medication API destinations to this computer. Starting the local dashboard and repeating a physical microphone transcription check.
- Board joined Mohit’s hotspot (Wi-Fi status 3); local dashboard and voice health endpoints both return HTTP 200 at `172.20.10.14`.
- Luna subagent on `codex/slower-voice` produced commit `51ef6e9`; integrated its supported Speech API `speed: 0.8` setting into the live service.
- Initial real speech did not trigger capture. Metered speech was often 100–170 RMS, below the old 400 threshold. Lowered start/silence thresholds to 100/60 and normalized captured PCM before transcription (gain capped at 20). Added manual `voice_record` action for a full 3-second diagnostic capture.
- Further serial diagnosis revealed repeated recorder allocation failures: 124 KB total free heap was split into blocks too small for its 96 KB contiguous buffer. Replaced the 37 KB static reminder decode buffer with 256-sample playback chunks, and added allocation-failure logging/cooldown to avoid a busy retry loop. Rebuilding and repeating the physical audio test.
- Controlled physical test passed: board IP `172.20.10.2` sent 48,000 microphone samples over Wi-Fi; OpenAI transcribed exactly "Hello, can you hear me?". The board drained all 193,452 reply PCM bytes and logged `voice_reply_played: true`; user confirmed audible audio but requested more volume. Raised the live speaker from 0.4 to 0.7 and persisted it in setup.
- Added a manual recording beep and an auto-recording toggle for repeatable checks; drained the declared response body instead of stopping early on the socket connection flag. Shortened model replies to one sentence and handled transient TLS failures.
- Integrated the existing main-worktree dashboard reminder implementation into the microphone branch so flashing the voice firmware preserves configured reminder timing. The hosted `/api/reminder/next` endpoint returns HTTP 200.
- Final combined voice/reminder firmware built and uploaded successfully (14.6% static RAM). User confirmed the earlier reply was audible; increased speaker volume to 70% at their request. The later loudness-check capture contained no recognized speech (HTTP 422), so the increased level has not yet received a user quality confirmation. Restoring automatic listening after the controlled tests. Both dashboard and voice services remain hosted on this computer.

## 2026-10-24 — Voice response pace

- User reported the audio response was very slow. The live TTS request was explicitly set to 0.8x speed with measured-pace instructions, so changed it to the API's normal 1.0x speed and natural conversational pacing.
- Added separate host-side duration logs for transcription, model generation, and speech synthesis so a long pause before playback can be diagnosed independently from speaking rate.
- User measured about seven seconds of response wait. Recent logs show transcription around 0.7–1.6s, model generation 1.3–2.3s, and speech synthesis 1.1–1.6s. Confirmed the model was already GPT-6 Luna with reasoning effort `none`; made standard mode explicit and limited spoken replies to ten words to reduce generation and TTS time.

## 2026-10-24 — Slot-1 push-to-talk

- User asked to repurpose the reset button so voice capture has explicit start/stop points. Made slot 1 hold-to-talk: press starts recording and release stops/sends; the start beep indicates capture. Automatic sound-triggered recording is disabled/removed to prevent ambient speech from starting a request.
- The microphone module still has a three-second hard capture limit; recordings also send automatically at that limit. Lowered the minimum send length to 0.25 seconds (the voice API's minimum) for short explicit utterances.
- Slot 1 no longer clears medication status or replays a reminder. Updated the display labels and README to describe the new button behavior.
