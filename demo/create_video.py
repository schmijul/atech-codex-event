"""Render the Atech home-care concept film with Pillow, NumPy and ffmpeg."""
from pathlib import Path
import math
import shutil
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT, FPS, DURATION = 1280, 720, 24, 30
INK = '#163D36'
MUTED = '#65786E'
GREEN = '#227857'
MINT = '#D7E9D9'
ORANGE = '#D57C50'
FONT = '/usr/share/fonts/opentype/inter/Inter-Regular.otf'
BOLD = '/usr/share/fonts/opentype/inter/Inter-Bold.otf'
FONTS = { (s, b): ImageFont.truetype(BOLD if b else FONT, s)
          for s in [13, 15, 17, 19, 21, 24, 27, 30, 34, 42, 48, 58, 64] for b in [False, True] }


def ease(value):
    value = min(1, max(0, value))
    return value * value * (3 - 2 * value)


def text(draw, xy, words, size=21, fill=INK, bold=False, anchor=None):
    draw.text(xy, words, font=FONTS[size, bold], fill=fill, anchor=anchor, spacing=9)


def rounded(draw, bounds, color, radius=18, outline=None, width=1):
    draw.rounded_rectangle(tuple(round(v) for v in bounds), radius=radius,
                           fill=color, outline=outline, width=width)


def check(draw, x, y, color, scale=1):
    draw.line([(x - 10 * scale, y), (x - 2 * scale, y + 8 * scale),
               (x + 14 * scale, y - 10 * scale)], fill=color, width=max(2, int(4 * scale)))


def sound_wave(draw, x, y, time, color, count=21):
    for i in range(count):
        height = 5 + 22 * abs(math.sin(time * 7 + i * .59)) * math.sin((i + 1) / (count + 1) * math.pi)
        rounded(draw, (x + i * 10, y - height, x + i * 10 + 4, y + height), color, 2)


def device(time, mode):
    """Illustrative kit, with display and separate physical confirmation button."""
    im = Image.new('RGBA', (610, 470))
    d = ImageDraw.Draw(im)
    # Soft grounded shadow and a shallow base give the board a physical presence.
    for i in range(14, 0, -1):
        d.ellipse((56-i, 381-i/3, 560+i, 413+i/3), fill=(30, 55, 43, 2))
    rounded(d, (52, 118, 563, 389), '#C8C6B9', 30)
    rounded(d, (52, 104, 563, 374), '#EEEDE4', 30, '#CDCFC2', 2)
    # Seven module locations along each edge, representing the 14-port board.
    for i in range(7):
        x = 81 + i * 65
        rounded(d, (x, 119, x + 35, 132), '#B8BFB0', 4)
        rounded(d, (x, 345, x + 35, 358), '#B8BFB0', 4)
        text(d, (x+17, 111), str(i+1), 13, MUTED, anchor='mm')
    text(d, (77, 320), 'ATECH', 19, MUTED, True)
    text(d, (270, 327), 'SMALL KIT', 13, MUTED)
    # Display module.
    rounded(d, (77, 152, 340, 297), '#374B43', 12)
    rounded(d, (88, 163, 329, 286), '#143A33', 7)
    if mode == 'idle':
        text(d, (208, 202), 'Good morning.', 24, '#F3F3DF', True, 'mm')
        text(d, (208, 245), 'Here to help.', 19, '#A7C7B2', anchor='mm')
    elif mode == 'reminder':
        text(d, (208, 193), 'Have you taken', 21, '#FCF8E9', True, 'mm')
        text(d, (208, 226), 'your meds?', 27, '#FCF8E9', True, 'mm')
        text(d, (208, 264), 'Press YES to confirm', 15, '#BBDAB7', anchor='mm')
    elif mode == 'confirmed':
        d.ellipse((187, 173, 229, 215), fill='#BEE5BA')
        check(d, 208, 194, '#174B35', .8)
        text(d, (208, 244), 'Meds taken', 27, '#DDF3D1', True, 'mm')
        text(d, (208, 272), 'Thank you.', 15, '#BBDAB7', anchor='mm')
    else:
        text(d, (208, 189), 'Listening...' if time < 19 else 'Speaking...', 21, '#FCF8E9', True, 'mm')
        sound_wave(d, 114, 236, time, '#BEE5BA', 19)
    # Speaker module.
    rounded(d, (360, 151, 446, 253), '#D8D9CC', 12, '#B6BDAE')
    for row in range(7):
        for col in range(6):
            x, y = 377 + col * 10, 170 + row * 10
            d.ellipse((x,y,x+3,y+3), fill='#586E5C')
    # Large accessible physical button. Its caption is outside the tiny display.
    pressed = 10.5 <= time < 10.95
    d.ellipse((469, 175, 542, 249), fill='#205139')
    d.ellipse((469, 168 + (6 if pressed else 0), 542, 241 + (6 if pressed else 0)), fill='#69A97A')
    text(d, (505, 205 + (6 if pressed else 0)), 'YES', 21, '#FFFFFF', True, 'mm')
    if 5 <= time < 8:
        for i in range(3):
            phase = ((time-5)*.8 + i/3) % 1
            radius = 36 + phase * 70
            d.arc((403-radius,201-radius,403+radius,201+radius), -48, 48,
                  fill=(61, 122, 82, int((1-phase)*180)), width=3)
    # Hand travels to button, presses, then withdraws.
    if 9.3 < time < 12:
        amount = ease((time-9.3)/1.2) * (1-ease((time-11.05)/.95))
        x, y = 505 + (1-amount)*80, 213 + (1-amount)*250
        rounded(d, (x-16, y, x+16, y+118), '#D9B69D', 16, '#C6987B')
        rounded(d, (x-16, y+65, x+86, y+168), '#D9B69D', 24, '#C6987B')
    return im


def render(time):
    im = Image.new('RGB', (WIDTH, HEIGHT), '#F5F3EA')
    d = ImageDraw.Draw(im)
    # Quiet editorial framing throughout the film.
    text(d, (64, 42), 'atech', 30, INK, True)
    d.line((171, 45, 171, 73), fill='#BAC6B7', width=1)
    text(d, (192, 49), 'A little support. Every day.', 17, MUTED)
    text(d, (1216, 58), 'HOME ASSISTANT', 13, MUTED, True, 'rm')
    d.line((64, 98, 1216, 98), fill='#D8DDCF', width=1)
    d.ellipse((700, 139, 1250, 689), fill='#E5EBDD')
    # Scenes cut with a short slide and fade, leaving enough time to read each state.
    if time < 4:
        start, label, heading, body, mode = 0, 'CARE, CLOSE TO HOME', 'Small kit.\nEveryday help.', 'A home assistant for\nolder adults and their routines.', 'idle'
    elif time < 10.95:
        start, label, heading, body, mode = 4, '01 / MEDICATION REMINDER', 'A gentle nudge.\nA clear question.', 'A reminder sound gets attention.\nThe display asks about medication.', 'reminder'
    elif time < 15:
        start, label, heading, body, mode = 10.95, '01 / CONFIRMED', 'One press.\nReassurance.', '“Yes, I have taken it.”\nThe reminder stops.', 'confirmed'
    elif time < 25:
        start, label, heading, body, mode = 15, '02 / VOICE AGENT · CONCEPT', 'Just speak.\nIt listens.', 'A microphone to hear you.\nA speaker to answer.', 'voice'
    else:
        start, label, heading, body, mode = 25, 'ATECH / HOME CARE', 'Helpful routines.\nHuman moments.', 'Medication reminders today.\nVoice assistance, next.', 'idle'
    entry = ease((time-start)/.65)
    layer = Image.new('RGBA', im.size)
    ld = ImageDraw.Draw(layer)
    x = 64 + round((1-entry)*22)
    text(ld, (x, 164), label, 15, GREEN, True)
    text(ld, (x, 210), heading, 58, INK, True)
    text(ld, (x, 377), body, 21, MUTED)
    if mode == 'reminder':
        rounded(ld, (x, 479, x+365, 536), MINT, 12)
        text(ld, (x+20, 495), 'Have you taken your meds?', 21, INK, True)
        if time < 9.3:
            text(ld, (x, 562), 'Gentle reminder chime', 17, GREEN)
        else:
            text(ld, (x, 562), 'Press the YES button to confirm', 17, GREEN)
    elif mode == 'confirmed':
        ld.ellipse((x,482,x+40,522),fill=GREEN)
        check(ld,x+20,502,'#FFFFFF',.75)
        text(ld,(x+55,488),'Meds taken. Thank you.',21,GREEN,True)
    elif mode == 'voice':
        # Scripted conversation is visibly identified as a future interaction.
        rounded(ld,(x,474,x+447,575),'#E3EADD',12)
        if time < 19:
            text(ld,(x+20,489),'YOU',13,GREEN,True)
            text(ld,(x+20,519),'“Good morning.”',24,INK)
        elif time < 23.5:
            text(ld,(x+20,489),'ASSISTANT',13,GREEN,True)
            text(ld,(x+20,519),'“Good morning. How can I help?”',21,INK)
        else:
            text(ld,(x+20,489),'MICROPHONE → VOICE → SPEAKER',13,GREEN,True)
            sound_wave(ld,x+20,542,time,GREEN,36)
        text(ld,(x,596),'Scripted preview · voice agent not yet implemented',13,MUTED)
    elif time >= 25:
        rounded(ld,(x,480,x+330,535),INK,12)
        text(ld,(x+23,496),'Atech Small Kit · Home care',19,'#F5F3EA',True)
    layer.putalpha(layer.getchannel('A').point(lambda a: round(a*entry)))
    im = Image.alpha_composite(im.convert('RGBA'),layer)
    # A gentle float gives the kit continuous motion without moving its text too far.
    kit = device(time,mode)
    im.alpha_composite(kit,(619,177+round(math.sin(time*.7)*3)))
    d=ImageDraw.Draw(im)
    if mode=='reminder':
        text(d,(925,610),'DISPLAY + CHIME + PHYSICAL BUTTON',13,MUTED,True,'mm')
    elif mode=='voice':
        text(d,(925,610),'LISTEN → UNDERSTAND → RESPOND',13,GREEN,True,'mm')
    else:
        text(d,(925,610),'ILLUSTRATIVE KIT VIEW',13,MUTED,True,'mm')
    d.line((64,654,1216,654),fill='#D8DDCF',width=1)
    for i,(name,start,end) in enumerate([('REMIND',0,11),('CONFIRM',11,15),('CONNECT',15,30)]):
        bx=64+i*385
        d.line((bx,677,bx+350,677),fill='#D6DECF',width=3)
        progress=min(1,max(0,(time-start)/(end-start)))
        if progress: d.line((bx,677,bx+350*progress,677),fill=GREEN,width=3)
        text(d,(bx,690),name,13,MUTED,True)
    # Overall opening and closing fades.
    fade = ease(time/.65)*ease((DURATION-time)/.75)
    return Image.blend(Image.new('RGB',im.size,'#F5F3EA'),im.convert('RGB'),fade)


def make_audio(path):
    rate=24000
    audio=np.zeros(rate*DURATION,dtype=np.float64)
    # Soft two-note chime with rounded attack and exponential decay.
    for start,freq in [(5.0,523.25),(5.32,659.25),(5.65,783.99)]:
        t=np.arange(int(rate*.8))/rate
        tone=(np.sin(2*np.pi*freq*t)+.15*np.sin(2*np.pi*2*freq*t))
        tone*=.18*np.minimum(t/.025,1)*np.exp(-t*5)
        offset=int(start*rate); audio[offset:offset+len(tone)]+=tone
    # Brief tactile click when the physical button is pressed.
    t=np.arange(int(rate*.08))/rate
    click=.1*np.sin(2*np.pi*180*t)*np.exp(-t*60)
    offset=int(10.5*rate); audio[offset:offset+len(click)]+=click
    # Local speech synthesis keeps the entire video reproducible without an API key.
    if shutil.which('espeak'):
        with tempfile.TemporaryDirectory() as tmp:
            for i,(start,words,speed,pitch) in enumerate([
                (16.3,'Good morning.',145,46),
                (19.0,'Good morning. How can I help?',150,60)]):
                speech=Path(tmp)/f'{i}.wav'
                subprocess.run(['espeak','-v','en-us','-s',str(speed),'-p',str(pitch),'-w',str(speech),words],check=True)
                pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(speech),'-f','s16le','-ar',str(rate),'-ac','1','-'])
                samples=np.frombuffer(pcm,dtype='<i2').astype(float)/32768*.55
                offset=int(start*rate); audio[offset:offset+len(samples)]+=samples
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,rate,0,'NONE','not compressed'))
        out.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())


if __name__ == '__main__':
    for tool in ['ffmpeg','ffprobe']:
        if not shutil.which(tool): raise SystemExit(f'Install {tool} first.')
    render(6.5).save(ROOT/'cover.png')
    # Keep a small contact sheet to inspect the actual six story beats.
    sheet=Image.new('RGB',(1280,1080))
    for i,time in enumerate([2,6.5,10.5,12.5,20,27]):
        thumb=render(time).resize((640,360),Image.Resampling.LANCZOS)
        sheet.paste(thumb,((i%2)*640,(i//2)*360))
    sheet.save(ROOT/'storyboard.jpg',quality=92)
    with tempfile.TemporaryDirectory() as tmp:
        audio=Path(tmp)/'audio.wav'; make_audio(audio)
        command=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
                 '-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','-', '-i',str(audio),
                 '-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p',
                 '-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',
                 str(ROOT/'atech-home-assistant.mp4')]
        process=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for frame in range(FPS*DURATION):
                process.stdin.write(render(frame/FPS).tobytes())
                if frame%(FPS*5)==0: print(f'Rendered {frame/FPS:.0f}/{DURATION}s',flush=True)
        finally:
            process.stdin.close()
        if process.wait(): raise SystemExit('ffmpeg could not encode the video.')
    print(f'Saved {ROOT / "atech-home-assistant.mp4"}')
