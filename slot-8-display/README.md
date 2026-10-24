# slot-8-display

Atech project targeting the **14port** board.

Medication reminder: display on ports **13–14**, speaker on **3–4**, meds-taken
button on **9**, and reminder-reset button on **1**.
Set a daily start time in the dashboard. The board reads the saved time and timezone
over Wi-Fi, starts the spoken reminder then, and repeats it every 30 seconds until
the meds-taken button is pressed. A new local day resets the confirmation.
Press the slot-1 button to reset the reminder and immediately replay the spoken prompt.
When the meds-taken button is pressed, firmware sends one HTTP POST with `{}` to
`http://172.20.10.5:8000/api/events`. The API server must be running on the same
network. Configure hotspot credentials in the ignored local file `.wifi_secrets.h`.

The dashboard stores the daily `HH:MM` and browser IANA timezone in SQLite. The
board checks `/api/reminder/next` every 30 seconds; it uses the server's current
epoch in that response, so no separate clock-sync service is needed.

Edit `project.yaml` to place modules, then:

```bash
atech describe .   # what is placed, each module's API, events and actions
atech validate .
atech build .
atech upload .
atech monitor      # events from the board
```

Working with a coding agent? `AGENTS.md` / `CLAUDE.md` in this folder tell it how
to use the SDK (same text as `atech guide`).
