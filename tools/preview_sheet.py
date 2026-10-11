# -*- coding: utf-8 -*-
"""Extract frames at given seconds from final.mp4 and build a contact sheet. usage: preview_sheet.py <folder> <out.jpg> t1 t2 ..."""
import os, sys, subprocess
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = os.path.join(ROOT, 'tools', 'ffmpeg-9.0.2-essentials_build', 'bin', 'ffmpeg.exe')
folder, out = sys.argv[1], sys.argv[2]
ts = [float(x) for x in sys.argv[3:]]
tmp = os.path.join(folder, '_prev'); os.makedirs(tmp, exist_ok=True)
ims = []
for i, t in enumerate(ts):
    p = os.path.join(tmp, f'p{i}.jpg')
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', str(t), '-i', os.path.join(folder, 'final.mp4'), '-frames:v', '1', p])
    ims.append(Image.open(p).convert('RGB').resize((270, 480)))
cols = min(6, len(ims)); rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 270, rows * 504), 'white')
d = ImageDraw.Draw(sheet); f = ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf', 18)
for i, im in enumerate(ims):
    x, y = (i % cols) * 270, (i // cols) * 504
    sheet.paste(im, (x, y + 24)); d.text((x + 6, y + 2), f'{ts[i]:.1f}s', fill='black', font=f)
sheet.save(out, quality=85)
for f_ in os.listdir(tmp): os.remove(os.path.join(tmp, f_))
os.rmdir(tmp)
print('ok')
