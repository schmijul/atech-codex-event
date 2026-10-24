# display-pin-diagnostic

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules

- **Display signal assignment diagnostic** (`display_probe`) as `screen` on `port_13, port_14`

## Build & flash

This folder is generated. Change `project.yaml` one level up and run, from there:

```bash
atech build .
atech upload .
```

It is also a plain PlatformIO project (`pio run`, `pio run -t upload`), but
anything edited here is overwritten by the next `atech build`.
