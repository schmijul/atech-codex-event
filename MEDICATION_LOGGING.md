# Medication event log

## Wi-Fi API (board to SQLite)

The board sends a POST to `http://172.20.10.5:8000/api/events` with body `{}`
when the meds-taken button is pressed. The server records the current time, so
the board does not supply a timestamp. The board and API host must be on the
same Wi-Fi network. Firmware uses the iPhone hotspot credentials stored in the
ignored local file `slot-8-display/.wifi_secrets.h`; do not commit that file or
share firmware binaries containing the credentials.

Read confirmations with `GET /api/events`. Do not run `meds_logger.py` alongside
the Wi-Fi API; both would record the same physical button press.
The firmware retries an explicit `503` or a request that did not start. If the
POST times out or loses its connection after sending, it does not retry because
the server may already have saved it. Check `GET /api/events` before manually
retrying an uncertain confirmation.

Run the logger while the board is connected:

```bash
.venv/bin/python meds_logger.py
```

The default board port is `/dev/cu.usbmodem101`. Choose another port or database
file when needed:

```bash
.venv/bin/python meds_logger.py --port /dev/cu.usbmodem1101 --db ./data/meds.sqlite3
```

The logger owns the board's serial connection while it runs. Stop `atech monitor`
and any other serial monitor first. Pressing the board's meds-taken button saves
one row in `meds_taken.sqlite3` (or the file passed to `--db`).

The database has a `medication_events` table with an integer `id` and a
`taken_at_utc` ISO-8601 timestamp in UTC. The dashboard reads it with
Python's built-in `sqlite3` module:

```sql
SELECT id, taken_at_utc
FROM medication_events
ORDER BY taken_at_utc DESC;
```

The Atech Python package is already available in this repository's `.venv`;
SQLite is part of Python's standard library.

## Local dashboard

Run in a second terminal while the logger runs:

```bash
python3 dashboard.py
```

Open http://127.0.0.1:8000. The dashboard reads `meds_taken.sqlite3`
and refreshes every five seconds. Its GET endpoint does not modify records;
the POST endpoint below adds confirmations. It shows today's
confirmations, the total, the latest timestamp, and history in pages of 50.
Dates use your browser's timezone. No additional Python packages are required.
Stop the server with Ctrl-C.

## Wi-Fi write API

The dashboard server listens on all network interfaces on port 8000. Devices
on the same network can open `http://172.20.10.5:8000` (the host IP can change).
No authentication is required: anyone able to reach this port can read and add
confirmations. Keep it on your trusted local network.

Record a confirmation using the server's current UTC time:

```bash
curl -X POST http://172.20.10.5:8000/api/events \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Or supply an ISO-8601 timestamp with a timezone:

```bash
curl -X POST http://172.20.10.5:8000/api/events \
  -H 'Content-Type: application/json' \
  -d '{"taken_at_utc":"2026-10-24T14:30:00+02:00"}'
```

Success returns HTTP 201 with `id` and the normalized UTC `taken_at_utc`.
Invalid input returns 400; a database failure returns 503. Each POST inserts
one new row. Read entries with `GET /api/events`. The logger and API can run
together. The host must stay awake, and its firewall must allow TCP port 8000.

### Instructions for an API client agent

- Base URL on the current Wi-Fi: `http://172.20.10.5:8000`.
- `GET /api/events` returns a JSON array, newest first, with `id` and
  `taken_at_utc` fields.
- `POST /api/events` with `Content-Type: application/json` and body `{}`
  records a confirmation at the server's current time.
- To record a specific time, send `{"taken_at_utc":"2026-10-24T14:30:00+02:00"}`.
  A timezone is required; timestamps are stored and returned in UTC.
- Success is HTTP 201 with the inserted record. Invalid input is HTTP 400;
  database errors are HTTP 503. Bodies must be JSON objects up to 4096 bytes.
- Only record real confirmations when instructed. Every successful POST creates
  a row; there is no deduplication. If a request times out after sending, inspect
  the history before retrying to avoid duplicates.
- No authentication is required. The server must be running and reachable on
  the same network. Its IP may change when the host reconnects.
