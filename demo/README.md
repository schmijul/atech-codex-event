# Atech home assistant demo

A 30-second animated film, generated in Python at 1280×720, 24 fps, with sound.

Open `atech-home-assistant.mp4` to play the film. `cover.png` previews the
medication reminder; `storyboard.jpg` shows the six main story beats.

The film introduces the kit, plays a reminder chime, displays “Have you taken
your meds?”, animates a hand pressing the physical YES button, and confirms
“Meds taken”. It then shows a scripted voice conversation with synthesized
speech and animated audio bars. The voice section is labeled as a concept:
voice-agent firmware has not yet been implemented.

The board drawing is illustrative. Current project wiring is a display on
ports 13–14, a speaker on 3–4, and a physical button on 9. The screen is not
represented as a touchscreen.

## Regenerate

Requires Python 3, Pillow, NumPy, ffmpeg, ffprobe, and the Inter font installed
at `/usr/share/fonts/opentype/inter/`. Install `espeak` for the spoken dialogue;
without it the film still includes the generated chime and button sound.

```sh
python3 demo/create_video.py
```

The script saves the MP4, cover, and storyboard beside itself. Temporary audio
files are cleaned up automatically. Change the scene timings, text, colors,
and drawing directly in `create_video.py`.
