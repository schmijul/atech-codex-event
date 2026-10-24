# Tagly staff dashboard

Start the existing dashboard server with `python3 dashboard.py`, then open:

- `http://localhost:8000/` for the medication log and reminder schedule
- `http://localhost:8000/staff` for the staff view

The staff page refreshes every five seconds. Its **TEST ONLY** buttons record simulated events. They do not contact the physical board.

## Event and alert behavior

`POST /api/events` keeps the existing behavior: `{}` records `meds_taken`, returns HTTP 201, and writes to the existing `medication_events` history. It also accepts an optional `type` (`presence`, `company`, or `meds_taken`), `patient_id` (currently 1), and `source` (defaults to `device`). The staff test buttons use `source: simulated`.

`GET /api/alerts` lists open alerts. `POST /api/alerts/<id>` accepts `{"action":"on_my_way"}` or `{"action":"done"}`. Presence and a later medication confirmation close their matching alerts automatically. A background check runs every 30 seconds.

Set the wake deadline at `/staff`. It defaults to 09:00 in the browser's IANA timezone. Medication missed alerts use the existing reminder schedule and open 30 minutes after its set time if no medication event has been recorded.

`GET /api/board/state?patient_id=1` returns the display/speech message and a sequence number. The sequence changes only when the message changes. A company request shows `KOMMT GLEICH`, staff acknowledgement shows `UNTERWEGS`, and closing the alert clears the message.

`POST /api/family-update?patient_id=1` returns a short family update based on today's recorded events, with an English `EN:` line. When `OPENAI_API_KEY` is available in the environment or ignored `.env`, the server asks the OpenAI chat completions API to write the update; without a key, it uses a fixed template. If the API call fails, the fixed template is returned.

## Three-minute demo

1. Open `/staff` and point out today's status, open alerts, and the 09:00 wake deadline.
2. Click **Gets up**. The event log records a simulated presence event and the morning status changes.
3. Click **Takes pills**. The event appears in the log and the existing medication history receives the confirmation.
4. Click **Wants company**. Show the company alert, then click **On my way** and **Done**; the board state progresses through `KOMMT GLEICH`, `UNTERWEGS`, and empty.
5. Click **Write update** to show the German family message and its English translation.
