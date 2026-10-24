"""Save Atech medication-taken events to a local SQLite database."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from atech import Board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/cu.usbmodem101", help="Atech board serial port")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).with_name("meds_taken.sqlite3"),
        help="SQLite database file",
    )
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS medication_events (
                id INTEGER PRIMARY KEY,
                taken_at_utc TEXT NOT NULL
            )
        """)
        db.commit()

    print(f"Recording meds_taken events from {args.port} into {args.db}")
    print("Press Ctrl-C to stop.")
    try:
        with Board.connect(port=args.port) as board, sqlite3.connect(args.db) as db:
            for event in board.events(types=["state"], keys=["meds_taken"]):
                if event.value is True or event.value == "true":
                    taken_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    db.execute(
                        "INSERT INTO medication_events (taken_at_utc) VALUES (?)",
                        (taken_at,),
                    )
                    db.commit()
                    print(f"Saved medication taken at {taken_at}")
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
