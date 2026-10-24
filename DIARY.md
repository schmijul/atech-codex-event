# Development diary

## 2026-10-24 — Dashboard reminder schedule

- User asked to set the daily reminder start time from the dashboard and separately delegated microphone input research for ports 5–6 to an isolated subagent branch.
- Current dashboard only reads the confirmation history; the firmware starts speaking immediately after display initialization. The schedule must persist in SQLite and be read by the board over the existing Wi-Fi API.
- Plan: save a local wall-clock time plus IANA timezone in a small settings table; expose a read-only endpoint that returns today's scheduled UTC epoch and server epoch, so ESP32 timing needs no separate NTP dependency. Firmware will poll, wait until the scheduled instant, then run the existing reminder loop.
- Added dashboard controls to save or disable a daily reminder. The new `dashboard_settings` table stores `HH:MM` and the browser's IANA timezone; `/api/reminder` reads/writes settings and `/api/reminder/next` returns the scheduled instant, current server epoch, and local date. The server creates the settings table at startup, so its running process must be restarted to serve these endpoints.
- Updated firmware source (not generated `build/` output) to poll the schedule over Wi-Fi every 30 seconds, start the existing spoken/repeating reminder at the scheduled time, clear the taken state when the configured local date changes, and keep slot-1 manual reset behavior. It relies on the server's epoch, not external NTP.
- Updated slot project documentation. The running API at 172.20.10.5 is still serving its previous process version; its GET `/api/events` works, but `/api/reminder` currently is not deployed. No settings or medication confirmation rows have been written as part of this implementation.
- `atech validate .` passed and `atech build .` compiled the firmware (25.6% RAM, 32.3% flash). The first validate invocation used the wrong relative venv path; corrected it to `../.venv/bin` from the project directory. Python bytecode compilation also succeeded. Firmware has not been flashed because the API host has not loaded the new schedule endpoints yet.
- Microphone subagent completed on isolated branch `codex/microphone-input` in `/tmp/atech-microphone-input`. The Atech SDK microphone module supports PCM recording/capture and sound-level readings on ports 5–6, but has no speech-to-text API; its branch adds the microphone module and level-event proof of concept. Validation/build passed there; no flash or API writes.

- User asked to verify live microphone input. Board was found on `/dev/cu.usbmodem101`; flashed the microphone proof of concept from the isolated branch. `atech check` reported the microphone initialized (the module has no hardware read-back). Serial monitor then produced `microphone_level` values every 250 ms, typically about 70–340 in the room; while the user clapped/tapped, peaks rose to 628, 740, and 1142. This confirms the board receives sound through the microphone. Stopped the monitor, removed the temporary Wi-Fi secrets copy, and restored generated build outputs. No medication button was pressed and no database row was created.

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

## 2026-10-24 — Missing incoming updates

- Checked SQLite directly and GET /api/events through localhost and Wi-Fi IP: all return the single original record, id 1 at 10:37:35 UTC.
- Running server logs show repeated successful dashboard GETs and no incoming POST requests. Dashboard polling is working; no new API writes have reached this process.
- Current firmware emits meds_taken over serial, with no Wi-Fi HTTP integration. No meds_logger.py process is running on this host. Asked which device/client is sending updates and for its HTTP response to identify the missing connection.

- User confirmed the board has Wi-Fi and is on the same network. Fetched origin: no newer commits. The checked-in YAML and generated C++ contain no Wi-Fi/HTTP calls; they emit serial events only. No USB board device is present here, so the running firmware cannot be inspected directly from this host. Need the sending firmware or its HTTP response to continue tracing the board-to-API path.

- Pulled commit 095300a (Send medication confirmations over Wi-Fi). Preserved both upstream firmware notes and local investigation notes when resolving the diary conflict. New firmware targets the correct API URL and uses JSON {}; prior serial-only diagnosis described the older checkout.

- Rechecked missing button updates after pulling Wi-Fi firmware: server is bound to 0.0.0.0:8000, host still has 172.20.10.5, UFW is inactive, and nftables has no host-input blocking rules. Database still has one row and server logs contain no POSTs. Need board serial output/Wi-Fi status after a reset-confirm cycle to distinguish lack of association, request failure, and suppressed repeat confirmations. No local USB device is available for direct inspection.

## 2026-10-24 — Pull latest changes

- Fast-forwarded main from 095300a to 2ba5e10. Initial pull was blocked by local diary and SQLite edits; saved them in a Git stash before pulling.
- Combined upstream and local diary additions. Restored the local medication database without merging event records; both original database versions are backed up at /tmp/atech-pull-backup-tqcg948j/ and the stash remains available.
- Python is available as python3; the initial python backup command failed before the successful python3 backup. A bytes-literal encoding error interrupted the first diary resolution script; corrected it with UTF-8 encoding and verified the final diff.

## 2026-10-24 — Show the reminder button

- The running dashboard predates the pulled reminder controls: GET / has no schedule form and GET /api/reminder returns 404. The latest source already implements daily reminder persistence and board polling endpoints.
- Renamed the submit button to “Set reminder”, made its submit type explicit, and removed the obsolete footer claim that no schedule is configured. Updated the usage instructions to match.
- Verified set/read/board-schedule/disable endpoints against a temporary database without adding medication events. Restarted dashboard.py and reloaded the existing browser tab; confirmed the Daily reminder time field, Set reminder button, Turn off button, and disabled-schedule status are visible. No live reminder time was chosen.

## 2026-10-24 — Person picker

- User wants the starting page to select a person, with only the existing patient available for now. Used the minimalist UI skill to keep the current warm monochrome style.
- Added a single Patient 1 link at /, moved the existing medication dashboard to /patients/1, and added an All people return link plus patient context in the title/header. Shared the existing CSS between the two pages in the same Python file.
- Kept the current SQLite history, reminder settings, and board API endpoints. Additional patients and data separation are outside this one-person step; no invented patient identity or registration UI.
- Verified Python compilation and whitespace checks, restarted the dashboard, and exercised the browser round trip from picker to Patient 1 and back. Existing four confirmations, reminder controls, and timezone rendered correctly; left the browser on the picker. Saved a visual preview at /tmp/atech-person-picker.png.

## 2026-10-24 — Push dashboard updates

- Reviewed the person picker, patient dashboard navigation, Set reminder label, and usage documentation. Fetched origin/main and confirmed no divergence. Python compilation, whitespace validation, live page routes, and read-only API checks passed.
- Committing the dashboard source, documentation, and diary for push to main. Keeping the locally modified runtime medication database uncommitted.

## 2026-10-24 — Exposed ElevenLabs credential

- User asked whether the ElevenLabs key was pushed. Confirmed a populated ELEVENLABS_API_KEY in tracked .env matches the value on origin/main, introduced by commit 442d40d before the dashboard changes. Never printed the secret value.
- GitHub metadata confirms this repository is public. The key must be revoked in ElevenLabs; deleting a file cannot revoke a credential or erase prior downloads/history.
- Removing .env from Git tracking while preserving the local file, and ignoring .env variants except .env.example. This cleanup leaves historical commits intact; history rewriting requires separate coordination with other checkouts.

## 2026-10-24 — Pull rewritten main history

- `git pull --ff-only` fetched a forced update but could not fast-forward because upstream history was rewritten.
- Compared local main (687dc72) and origin/main (2459428): their tracked file trees are identical; the seven divergent commits have matching subjects.
- Saved the previous local history in branch `codex/before-pull-20261024-687dc72`, then aligned main with origin/main using `git reset --keep origin/main`. The locally modified medication database was preserved.

## 2026-10-24 — Voice agent tools

- Fetched and fast-forwarded main from 2459428 to f0db0e4, then created `codex/voice-agent-tools`. Upstream adds the companion system prompt and changes the firmware API host; it also replaces the person picker with the medication page.
- Preserved local diary and runtime SQLite edits in a Git stash and /tmp/atech-voice-tools-pull-t4zkz6b2; restored them on the new branch.
- Main has no live speech-to-text or conversational-agent client. Inspecting the microphone branch and asking which voice provider should call the tools. Backend already supports medication confirmations and daily reminder schedules.
- Requested four intents: help, socializing with people on the patient's floor, lunch/menu choice, and medication reminders. Implementing explicit callable tools and a durable backend record; speech understanding belongs to the voice model using tool descriptions and conversation context.

- Located the live OpenAI audio bridge on `origin/codex/microphone-input` at dc19b18, rather than main. Imported that host source and, after the user requested spoken invitations on each resident device, the verified microphone/encoder YAML configuration. Kept generated build output untouched.
- Added four function definitions, backend validation/persistence, HTTP dispatch, OpenAI audio/tool/result rounds, and six-turn conversation context. Medication tools share the dashboard schedule and read button confirmations; speech never records medication ingestion.
- User clarified the social flow must be visible in the dashboard, match registered neighbors on the same floor, and speak invitations on their devices. The existing DB has only medication_events (4 rows) and dashboard_settings; no resident directory existed. Added patients, voice_requests, and social_invitations tables, plus resident/floor editing, request history, and recipient inboxes in the dashboard. Only the existing Patient 1 is initialized; no fictional neighbors are added to the live database.
- Social requests derive the floor from the backend resident ID, exclude the requester and other floors, and create one invitation per neighbor in the same transaction. Repeated tool-call IDs return their saved result. Device polling returns pending invitation audio; an explicit playback acknowledgement marks it played. Failed/partial audio stays pending.
- Added a background firmware task to poll/play invitations without new waits in the main loop. Resident IDs are sent in X-Patient-ID and saved in NVS through the patient_id action. Muting, medication reminders, or cancellation defer invitation delivery. A pending acknowledgement is retried without replaying audio until acknowledged; reboot can cause a repeated announcement.
- Nine automated HTTP/SQLite/audio-loop tests passed against temporary databases, including floor isolation, duplicates, cross-resident acknowledgement rejection, and spoken delivery/acknowledgement with mocked OpenAI audio. Live API verification using synthesized speech was rejected immediately with HTTP 401 invalid_api_key; no live classification or hardware playback was verified.
- Browser preview uses a separate temporary database on port 8765. Verified editing Patient 1's floor and adding a test-only neighbor through the UI. The first exact-label selector for the resident dropdown did not match; the observed element ID worked.
- `atech validate slot-8-display` passed. Started a compile-only firmware build in /tmp/atech-invitation-firmware-4y_jd7ur with dummy Wi-Fi credentials; SDK is downloading this machine's initial ESP32 toolchain. No firmware has been flashed.

### Scope correction — tools only

- User clarified another person owns the dashboard and requested only the association tools. Removed all newly written dashboard HTML/CSS/JavaScript and verified the PAGE literal matches the pulled HEAD exactly. Restored all firmware source files to HEAD, removed the invitation-delivery header, stopped the temporary preview/build, and closed its browser tab. The firmware build was cancelled during initial toolchain installation, before compilation; no hardware was flashed.
- Also removed the voice bridge's experimental invitation-audio generation/delivery routes. Final scope is the four function tools, OpenAI intent/tool dispatch, backend resident/floor association and invitation queue APIs, tests, and VOICE_TOOLS.md for the dashboard/device implementers. Device speech playback and dashboard rendering are integration consumers, not implemented on this branch.
- The live dashboard process started for verification has stopped. Its startup added the tool tables and existing Patient 1 directory record; the four medication confirmations were not changed, and no real invitations or test residents were created in that database. Runtime SQLite remains uncommitted.

- Final tools-only validation: all 9 tests passed; Python compilation and git diff --check passed. Confirmed dashboard PAGE matches HEAD exactly and firmware has no diff. Live DB still has 4 medication confirmations, 1 existing resident, 0 voice requests, and 0 social invitations. Preparing a commit on codex/voice-agent-tools with code/docs/tests only; leaving the runtime database uncommitted.
