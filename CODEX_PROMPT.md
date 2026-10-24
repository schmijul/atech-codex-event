# Codex prompt: Tagly daily-routine assistant

Paste everything below the line into Codex, run from the root of this repository.
A working reference implementation of the same idea lives in `reference/tagly-platform/`
(FastAPI, in-memory). Use it to borrow the rules and the test console layout; do not copy
its framework.

---

You are working in the `atech-codex-event` repository. Read `AGENTS.md`, `DIARY.md`,
`MEDICATION_LOGGING.md`, `dashboard.py`, `slot-8-display/README.md` and
`slot-8-display/project.yaml` before changing anything. Follow AGENTS.md strictly: the
simplest code that works, standard library only, single files, no frameworks, and keep
DIARY.md updated as you go.

## What we are building

**Tagly**: a bedside device (Atech ESP32-S3 board on the 14-port motherboard) that helps
older residents in assisted living with their daily routine, plus a simple staff view.
The repo already does case 2 partly: a daily spoken pill reminder and a meds-taken button
that POSTs to `/api/events`. Extend it to three cases:

1. **Morning "I'm up" signal**: the distance sensor (or any button press) marks the resident
   as up. No activity by their wake deadline (e.g. 09:00) → staff alert
   "No morning activity". A later event closes it automatically.
2. **Pill reminder**: keep the existing reminder and button. New: if there is no
   confirmation 30 minutes after the reminder time → staff alert
   "Pills not confirmed". A late confirmation closes it automatically.
3. **Company request + family update**: holding the meds button for 2+ seconds means
   "I'd like company" → staff alert. Staff press "On my way" (the board shows/says
   that someone is coming) and later "Done". A "Family update" button writes a short,
   warm 2–3 sentence German message for the family from today's events, plus one line
   starting "EN:" with an English translation. Never invent events.

## Rules you must keep

- **Do not break existing contracts.** `POST /api/events` with `{}` must still record a
  medication confirmation exactly as today (HTTP 201, same response). `GET /api/events`,
  `/api/reminder` and `/api/reminder/next` keep working unchanged. The flashed firmware
  depends on them.
- New event types are an **optional** `"type"` field on the same endpoint:
  `{"type":"presence"}`, `{"type":"company"}`; missing type means `"meds_taken"`.
  Optional `"patient_id"` (default 1) and `"source"` (default `"device"`).
- Never commit `.env`, `slot-8-display/.wifi_secrets.h`, firmware binaries with
  credentials, or the runtime `meds_taken.sqlite3` changes.
- Do not send real POSTs to the running server while testing. Test against a temporary
  database, as was done before (see DIARY.md).
- Times: store UTC, show local time in the browser, as today.

## Steps (verify each one before the next, note results in DIARY.md)

1. **Events table.** Add `device_events(id, patient_id, type, at_utc, source)` to the
   existing SQLite file. Keep writing `medication_events` for meds_taken so the current
   dashboard and history still work.
2. **Per-patient settings.** Add a wake deadline (default 09:00, local time + IANA
   timezone, like the reminder) to `dashboard_settings`. One patient exists today
   (Patient 1); keep it that way unless asked.
3. **Alerts.** Add `alerts(id, patient_id, type, title, created_utc, status, closed_utc,
   note)` with type `no_wake | meds_missed | company` and status
   `open | on_the_way | done`. Check the rules once every 30 seconds in a background
   thread of `dashboard.py` (it already serves on `ThreadingHTTPServer`):
   - no event of any type today and now > wake deadline → one `no_wake` alert per day;
   - reminder is set, now > reminder time + 30 min, no meds_taken since the reminder
     time today → one `meds_missed` alert per day; close it on a later meds_taken;
   - every `company` event creates an alert unless one is already open.
   Endpoints: `GET /api/alerts`, `POST /api/alerts/<id>` with
   `{"action":"on_my_way"}` or `{"action":"done"}`.
4. **Board state.** Add `GET /api/board/state?patient_id=1` returning
   `{"word": "...", "say": "...", "seq": n}`: "KOMMT GLEICH" while a company alert is
   open, "UNTERWEGS" when staff are on the way, otherwise empty. `seq` changes only when
   the content changes, so the board speaks once per change.
5. **Firmware** (`slot-8-display`). Use `atech describe .` first to see the placed modules
   and their APIs. Then:
   - distance sensor: when something is closer than ~80 cm for 3 s, POST
     `{"type":"presence"}`, at most once every 2 minutes. If no distance sensor is placed
     yet, say which port it should go on and stop for confirmation.
   - meds button: short press unchanged; hold 2 s+ → POST `{"type":"company"}` instead.
   - poll `/api/board/state` with the existing 30-second schedule check; when `seq`
     changes, show `word` on the display and speak `say`.
   - keep the existing retry rules (retry only on 503 or a request that never started).
   Run `atech validate .` and `atech build .`. Only `atech upload .` when the user says so.
6. **Staff view.** Add a page at `/staff` in the existing calm monochrome style of
   `dashboard.py`: today's status per patient (up / pills / company), open alerts with
   **On my way** and **Done** buttons, an event log, and a **Family update** button.
   Plain tables, no charts. For testing without the board add a small
   "Test" row with **Gets up / Takes pills / Wants company** buttons that POST with
   `"source":"simulated"`, clearly labelled as test buttons.
7. **Family update.** `POST /api/family-update?patient_id=1` builds the message from
   today's events. If `OPENAI_API_KEY` is set in the environment (or the ignored `.env`),
   call the OpenAI chat completions API with `urllib`; otherwise use a fixed template.
8. **Docs.** Update `MEDICATION_LOGGING.md` (or add a short `TAGLY.md`) with the new event
   types, endpoints, the staff page and a 3-minute demo script.

## Acceptance checks (against a temporary database)

- `POST /api/events {}` still returns 201 and appears in `GET /api/events` as before.
- `{"type":"presence"}` before the wake deadline → no `no_wake` alert that day.
- No event by the deadline → exactly one `no_wake` alert; a later presence closes it.
- Reminder at T, no confirmation by T+30 → one `meds_missed` alert; a meds_taken closes it.
- `{"type":"company"}` → one open alert; `/api/board/state` shows KOMMT GLEICH;
  `on_my_way` → UNTERWEGS; `done` → empty again; `seq` changes each time, not otherwise.
- Family update without an API key returns the template and mentions only real events.

Report what you changed, what you verified, and anything you could not test (for example
the physical distance sensor).
