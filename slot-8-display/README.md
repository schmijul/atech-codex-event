# slot-8-display

Atech project targeting the **14port** board.

Medication reminder: display on ports **13–14**, speaker on **3–4**, button on **9**.
The screen asks “Have you taken your meds?” and plays a short chime after startup,
then every 30 seconds. Press the button after taking medication to stop reminders
and show “Meds taken” on a green background. This confirmation stays until restart;
there is no daily schedule or saved state.

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
