# ATECH display fix

Confirmed working by the user on 24 October 2026: the screen shows
“Hello from Codex!” on a blue background.

## Hardware and software

- ATECH 14-port ESP32-S3 motherboard.
- USB-C connection at position 8.
- ST7735 160×80 color display spanning ports 13–14.
- USB device during this session: `/dev/cu.usbmodem101`.
- ATECH Python SDK `1.0.0a11`, installed in the repository's `.venv`.
- Adafruit GFX `1.13.0` and Adafruit ST7735/ST7789 `1.12.0`.

## What was wrong

Firmware uploaded successfully, and serial logs confirmed the drawing code ran,
but the screen kept its previous “Hi Peter!” image. Software acknowledgements
confirmed handler execution, not that the panel received the commands.

The bundled ATECH driver constructs `Adafruit_ST7735` in **software SPI** mode,
then calls `setSPISpeed(40000000)` during initialization. In the installed Adafruit
GFX implementation, `Adafruit_SPITFT::setSPISpeed()` writes the **hardware SPI**
settings without checking the connection type. Hardware and software SPI state
share a C++ union, so that write overwrites software SPI state, including signal
pin fields on this ESP32 build. Later drawing commands therefore use corrupted
connection settings.

Calling `setSPISpeed(1000000)` did not solve it: it uses the same invalid code
path. Software SPI speed is not configurable through that method.

## The working changes

The project uses a local copy of the SDK display module via:

```yaml
modules_path: ./my_modules
modules:
  - {id: st7735_tft, instance: display, ports: [13, 14]}
```

In `my_modules/st7735_tft/st7735_tft.cpp`:

1. Removed `_tft->setSPISpeed(40000000)` from `_initDisplay()`.
2. Made the wrapper's `ST7735_TFT::setSPISpeed(uint32_t)` a documented no-op,
   preventing callers from corrupting the software SPI state again.
3. Removed the clock-speed call from `project.yaml`.

The final module metadata uses the **original SDK pin mapping**:

| Signal | Port line | GPIO on this board |
| --- | --- | --- |
| Clock | 14, B | 35 |
| Chip select | 13, B | 38 |
| Data/MOSI | 14, A | 36 |
| Data/command | 13, A | 39 |

These GPIO values are generated from the SDK board definition; they are not
hardcoded in the project. The generated constructor is:

```cpp
ST7735_TFT display(35, 38, 36, 39);
// Constructor argument order: clock, chip select, MOSI, data/command.
```

The driver header and module metadata had conflicting pin descriptions. Testing
the alternative mapping did not fix the screen. Restoring the SDK mapping and
removing the invalid speed-setting calls produced the readable output.

## How we verified it

- The USB device disappeared when the user unplugged the photographed kit,
  confirming we were programming the correct hardware.
- Placement validation passed; compilation and flash verification succeeded.
- Numbered pin tests changed the screen to noise, but did not establish a working
  mapping. They led us to inspect the actual SPI implementation.
- After the speed-call fix, the user confirmed “Hello from Codex!” was visible.
  That visual confirmation is the decisive check for this output-only module.

## Rebuild and upload the working project

Run from the repository root:

```sh
source .venv/bin/activate
atech validate slot-8-display
atech upload slot-8-display --port /dev/cu.usbmodem101
```

`atech upload` regenerates and rebuilds from `project.yaml`. Run `atech ports`
if the serial device name changes. Keep the display on ports 13–14 unless the
project placement is also updated.

Edit the `display.displayText(...)` calls in `project.yaml` to change the message.
Preserve the local module override until the upstream driver fixes this issue.
Do not edit generated files under `build/`.

The `pin-test/` project and `my_modules/display_probe/` are diagnostic artifacts,
not the working display application. Do not upload `pin-test/` for normal use.

The working application currently draws once during setup, then reinitializes and
draws the blue screen after two seconds. Its `display_refresh` serial action
redraws the screen; `display_status` reports the intended text, not panel read-back.
