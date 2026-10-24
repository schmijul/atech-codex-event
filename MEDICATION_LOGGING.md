# Medication event log

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
`taken_at_utc` ISO-8601 timestamp in UTC. A future dashboard can read it with
Python's built-in `sqlite3` module:

```sql
SELECT id, taken_at_utc
FROM medication_events
ORDER BY taken_at_utc DESC;
```

The Atech Python package is already available in this repository's `.venv`;
SQLite is part of Python's standard library.
