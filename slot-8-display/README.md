# slot-8-display

Atech project targeting the **14port** board.

Medication reminder: display on ports **13–14**, speaker on **3–4**, meds-taken
button on **9**, push-to-talk button on **1**, and volume knob on **10–11**.
Turn the knob to adjust speaker volume from silent to 80%; the LED ring shows the
level. Position 12 is the board's built-in Restart button and cannot host a
module. Press the knob to end the current voice conversation. Hold button 1 to start recording
(the board beeps), then release it to send the recording to the voice assistant.
Recordings stop at three seconds even if button 1 is still held.
The slot-1 button no longer resets or replays the medication reminder.
The screen asks “Have you taken your meds?” and shows the two button functions.
Press button 9 after taking medication to stop reminders and show “Meds taken” on
a green background.
When the meds-taken button is pressed, firmware sends one HTTP POST with `{}` to
`http://172.20.10.5:8000/api/events`. The API server must be running on the same
network. Configure hotspot credentials in the ignored local file `.wifi_secrets.h`.

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
