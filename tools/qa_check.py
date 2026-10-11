# -*- coding: utf-8 -*-
"""QA helper: contact sheet (frame 0 + each beat midpoint), stream info, loudness.
ffmpeg cannot read/write the OneDrive project path here, so the mp4 is staged in RENDER_STAGE and frames are piped.
usage: python tools/qa_check.py output/YYYY-MM-DD/NN"""
import json, os, sys, subprocess, shutil, io, re, tempfile
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'tools', 'ffmpeg-9.0.2-essentials_build', 'bin')
folder = os.path.abspath(sys.argv[1])
stage = os.path.join(os.environ.get('RENDER_STAGE') or tempfile.gettempdir(), 'qa_' + os.urandom(4).hex()); os.makedirs(stage)  # mkdtemp ACL issue on py3.13
mp4 = os.path.join(stage, 'f.mp4'); shutil.copy(os.path.join(folder, 'final.mp4'), mp4)
tl = json.load(open(os.path.join(folder, 'timeline.json'), encoding='utf-8'))
S = json.load(open(os.path.join(folder, 'script.json'), encoding='utf-8'))
probe = json.loads(subprocess.run([os.path.join(BIN, 'ffprobe.exe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', mp4],
                                  capture_output=True).stdout)
v = [s for s in probe['streams'] if s['codec_type'] == 'video'][0]
a = [s for s in probe['streams'] if s['codec_type'] == 'audio'][0]
lr = subprocess.run([os.path.join(BIN, 'ffmpeg.exe'), '-hide_banner', '-nostats', '-i', mp4, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True)
m = re.findall(r'I:\s+(-?[\d.]+) LUFS', lr.stderr.decode('utf-8', 'replace'))
times = [0.0] + [round((b['start'] + b['end']) / 2, 2) for b in tl['beats']]
ims = []
for t in times:
    r = subprocess.run([os.path.join(BIN, 'ffmpeg.exe'), '-v', 'error', '-ss', str(t), '-i', mp4, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1'], capture_output=True)
    ims.append(Image.open(io.BytesIO(r.stdout)).convert('RGB').resize((270, 480)))
cols = 7; rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 270, rows * 504), 'white'); d = ImageDraw.Draw(sheet)
fnt = ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf', 18)
for i, im in enumerate(ims):
    x, y = (i % cols) * 270, (i // cols) * 504
    sheet.paste(im, (x, y + 24)); d.text((x + 6, y + 2), f'{times[i]:.1f}s ' + ('cover' if i == 0 else S['beats'][i - 1]['visual'][-18:]), fill='black', font=fnt)
sheet.save(os.path.join(folder, 'contact_sheet.jpg'), quality=85)
cover = Image.open(os.path.join(folder, 'cover.jpg'))
caps = set(b['visual'] for b in S['beats'] if b['visual'] in S.get('captures', {}))
info = {'width': v['width'], 'height': v['height'], 'fps': v['r_frame_rate'], 'vcodec': v['codec_name'], 'acodec': a['codec_name'],
        'duration': float(probe['format']['duration']), 'lufs': float(m[-1]) if m else None,
        'cover': [cover.width, cover.height, os.path.getsize(os.path.join(folder, 'cover.jpg'))],
        'captures_used': len(caps), 'capture_ratio': tl['capture_ratio'], 'opening_end': tl['beats'][0]['end']}
# thumbnail check: cover.jpg (= YouTube thumbnail) must come from a highlight-scene broadcast capture, never a GIF/card
v0 = S['beats'][0]['visual']
info['cover_visual'] = v0
info['cover_from_capture'] = v0 in S.get('captures', {})
info['cover_sec'] = (tl.get('cover') or {}).get('sec')
if not info['cover_from_capture']:
    info['FAIL'] = 'cover/thumbnail is not a broadcast capture (beat 0 = ' + v0 + ')'
print(json.dumps(info, ensure_ascii=False))
shutil.rmtree(stage, ignore_errors=True)
