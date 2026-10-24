# slot-8-display

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules

- **ST7735 TFT display — software SPI compatibility fix** (`st7735_tft`) as `display` on `port_13, port_14`
- **I2S Speaker (MAX98357A)** (`speaker`) as `speaker` on `port_3, port_4`
- **Button** (`button`) as `button` on `port_9`
- **Button** (`button`) as `resetButton` on `port_1`

## Build & flash

This folder is generated. Change `project.yaml` one level up and run, from there:

```bash
atech build .
atech upload .
```

It is also a plain PlatformIO project (`pio run`, `pio run -t upload`), but
anything edited here is overwritten by the next `atech build`.
