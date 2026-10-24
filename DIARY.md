# Development diary

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
