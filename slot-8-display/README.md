# slot-8-display

Atech project targeting the **14port** board.

Medication reminder: display on ports **13–14**, speaker on **3–4**, meds-taken
button on **9**, and reminder-reset button on **1**.
The screen asks “Have you taken your meds?” and says “Take your meds” after startup,
then every 30 seconds. Press the button after taking medication to stop reminders
and show “Meds taken” on a green background. This confirmation stays until restart;
there is no daily schedule or saved state.
Press the slot-1 button to reset the reminder and immediately replay the spoken prompt.

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
