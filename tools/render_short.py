# -*- coding: utf-8 -*-
"""story-shorts-producer renderer v2.
usage: python tools/render_short.py output/YYYY-MM-DD/NN
Reads script.json, generates TTS (Windows OneCore ko-KR voice for prototype; replace via channels.yaml),
composes 1080x1920 frames with PIL, muxes with ffmpeg -> final.mp4, cover.jpg, timeline.json.

v2 rules (operator feedback 2026-10-07):
- Title: no box, white bold angular font, accent colour only on numbers / key words, bigger size.
- No AI cat stickers. Reaction images = crops of reaction shots from the source broadcast (counted as captures)
  or operator-licensed memes from assets/memes/manifest.yaml.
- No zoom by default. Only beats with "zoom": "in" get a slow, smooth centre zoom (sub-pixel, no jitter).
- Source credit sits in a fixed strip under the panel, never over the image. No "장면 인용" wording.
- Opening (~2 s): narrator reads the hook title over the hook broadcast scene; frame 0 doubles as thumbnail.

v3 (operator feedback 2026-10-09):
- TTS: Google Gemini TTS (channels.yaml tts). One request per video -> tools/tts_split.py makes per-beat wavs.
  Windows voice (tts_winrt.ps1) only as fallback when provider is "windows".
- Subtitles: one cut per sentence, 1~2 lines, line break at natural phrase boundaries; long sentences split into
  several 1~2 line cuts. Font 80->66px (1 line) / 72->62px (2 lines).
- BGM: script.json "bgm" segments from 소스/ (operator-provided), synced to beats, -18 dB under narration,
  crossfade between segments, fade-out at the end. ffmpeg only reads from RENDER_STAGE and writes to stdout.

v4 (operator feedback 2026-10-09):
- No AI-generated illustrations. Situation cuts use GIPHY GIFs: visual "gif:assets/gifs/..." plays (looping) for the
  whole sentence of that beat, credit strip shows b["credit"] (e.g. "GIF: GIPHY @user"). No zoom on GIF cuts.
- Last beat ("end": true): channel end card assets/brand/ending.png in the panel + "구독 + 좋아요" text, whatever its visual.
"""
import json, os, sys, subprocess, wave, shutil, math, re, hashlib, tempfile, bisect
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_tts_cfg():
    cfg = {'provider': 'windows', 'model': 'gemini-3.1-flash-tts-preview', 'voice': 'Kore', 'tempo': 1.0, 'enabled': True}
    try:
        txt = open(os.path.join(ROOT, 'config', 'channels.yaml'), encoding='utf-8').read()
        block = re.search(r'^tts:\s*\n((?:[ \t]+.*\n?)+)', txt, re.M).group(1)
        for k in ('provider', 'model', 'voice', 'tempo', 'enabled'):
            m = re.search(rf'^\s+{k}:\s*"?([^"#\n]+?)"?\s*(#.*)?$', block, re.M)
            if m:
                v = m.group(1).strip()
                cfg[k] = float(v) if k == 'tempo' else (v.lower() not in ('false', 'no', 'off', '0') if k == 'enabled' else v)
    except Exception:
        pass
    return cfg


TTS_CFG = _load_tts_cfg()
BGM_DUCK_DB = -18.0       # BGM level relative to narration
TARGET_LUFS = -14.0
FFMPEG = os.path.join(ROOT, 'tools', 'ffmpeg-9.0.2-essentials_build', 'bin', 'ffmpeg.exe')
TTS_PS = os.path.join(ROOT, 'tools', 'tts_winrt.ps1')
FONT_MAIN = os.path.join(ROOT, 'assets', 'fonts', 'BlackHanSans-Regular.ttf')   # OFL, commercial use OK
FONT_SMALL = r'C:\Windows\Fonts\malgun.ttf'
W, H, FPS = 1080, 1920, 30
GAP = 0.2
LEAD = 0.05
TITLE_Y = 170
PANEL = (0, 470, 1080, 1150)
CREDIT_Y = 1162
SUB_CENTER = 1300
SUB_MAXW = 960
MEME_BOX = (40, 820, 380, 1140)
GIF_MAX_FRAMES = 180
END_IMG = os.path.join(ROOT, 'assets', 'brand', 'ending.png')   # channel end card (꿀잼/꿀잠), shown on the last beat
END_TEXT = '구독 + 좋아요'


def hexc(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def wav_dur(p):
    with wave.open(p) as w:
        return w.getnframes() / float(w.getframerate())


def tts(text, out, rate=1.1):
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return
    r = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', TTS_PS,
                        '-Text', text, '-Out', out, '-Rate', str(rate)], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError('TTS failed: ' + r.stderr[:300])


def tts_text(beat):
    t = beat.get('tts') or beat['text']
    return t.replace('“', '').replace('”', '').replace('"', '')


def blur_capture(path, boxes):
    im = Image.open(path).convert('RGB')
    for (x0, y0, x1, y1) in boxes:
        region = im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(28))
        mask = Image.new('L', (x1 - x0, y1 - y0), 0)
        if (y1 - y0) > 200:
            ImageDraw.Draw(mask).ellipse((0, 0, x1 - x0, y1 - y0), fill=255)
        else:
            ImageDraw.Draw(mask).rectangle((0, 0, x1 - x0, y1 - y0), fill=255)
        im.paste(region, (x0, y0), mask)
    return im


def fit_cover(im, bw, bh, focus=(0.5, 0.5)):
    r = max(bw / im.width, bh / im.height)
    nw, nh = int(im.width * r + 0.5), int(im.height * r + 0.5)
    im = im.resize((nw, nh), Image.LANCZOS)
    x = int((nw - bw) * focus[0]); y = int((nh - bh) * focus[1])
    return im.crop((x, y, x + bw, y + bh))


def fit_contain(im, bw, bh, bg):
    r = min(bw / im.width, bh / im.height)
    nw, nh = int(im.width * r), int(im.height * r)
    canvas = Image.new('RGB', (bw, bh), bg)
    canvas.paste(im.resize((nw, nh), Image.LANCZOS), ((bw - nw) // 2, (bh - nh) // 2))
    return canvas


def load_gif(path, bw, bh, bg, fit='cover'):
    """animated GIF -> (fitted RGB frames, cumulative frame end times in sec)"""
    im = Image.open(path)
    frames, ends, t = [], [], 0.0
    for fr in ImageSequence.Iterator(im):
        dur = max(0.02, (fr.info.get('duration') or im.info.get('duration') or 100) / 1000.0)
        rgb = fr.convert('RGB')
        frames.append(fit_contain(rgb, bw, bh, bg) if fit == 'contain' else fit_cover(rgb, bw, bh))
        t += dur; ends.append(t)
        if len(frames) >= GIF_MAX_FRAMES:
            break
    return frames, ends


def gif_frame(gif, sec):
    frames, ends = gif
    return frames[min(len(frames) - 1, bisect.bisect_right(ends, max(0.0, sec) % ends[-1]))]


def end_card(bw, bh):
    """channel end card centred in the panel; side bars use the average colour of the image's left / right edges"""
    im = Image.open(END_IMG).convert('RGB')
    s = min(bw, bh); im = im.resize((s, s), Image.LANCZOS)
    edge = max(4, s // 40)
    avg = lambda box: im.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))
    out = Image.new('RGB', (bw, bh), avg((0, 0, edge, s)))
    out.paste(Image.new('RGB', (bw // 2, bh), avg((s - edge, 0, s, s))), (bw - bw // 2, 0))
    out.paste(im, ((bw - s) // 2, (bh - s) // 2))
    return out


def rounded(im, rad, border=8, bcol=(255, 255, 255)):
    w, h = im.size
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), rad, fill=255)
    out = Image.new('RGBA', (w + border * 2, h + border * 2), (0, 0, 0, 0))
    bm = Image.new('L', out.size, 0)
    ImageDraw.Draw(bm).rounded_rectangle((0, 0, out.size[0] - 1, out.size[1] - 1), rad + border, fill=255)
    out.paste(Image.new('RGBA', out.size, bcol + (255,)), (0, 0), bm)
    out.paste(im.convert('RGBA'), (border, border), mask)
    return out


def smooth_zoom(im, z):
    """centre zoom with sub-pixel precision (no jitter)."""
    if abs(z - 1.0) < 1e-4:
        return im
    w, h = im.size
    cx, cy = w / 2.0, h / 2.0
    a = 1.0 / z
    return im.transform((w, h), Image.AFFINE, (a, 0, cx - a * cx, 0, a, cy - a * cy), resample=Image.BICUBIC)


def is_kw(word, keywords):
    if re.search(r'\d', word):
        return True
    core = re.sub(r'[\s“”"?!.,…]', '', word)
    for k in keywords:
        if not k:
            continue
        for part in k.split(' '):
            if part and (part in core or (core and core in part and len(core) >= 2)):
                return True
    return False


def tokenize(text, keywords):
    out, inq = [], False
    for w in text.split(' '):
        starts = '“' in w or w.startswith('"')
        if starts: inq = True
        kind = 'quote' if inq else ('kw' if is_kw(w, keywords) else 'normal')
        out.append((w, kind))
        if '”' in w or (w.endswith('"') and not starts): inq = False
    return out


def chunk_text(text, maxchars=15):
    words = text.split(' ')
    n = max(1, math.ceil(len(text.replace(' ', '')) / maxchars))
    target = len(text.replace(' ', '')) / n
    chunks, cur = [], ''
    for w in words:
        if cur and len(chunks) < n - 1 and len(cur.replace(' ', '')) >= target * 0.85:
            chunks.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur: chunks.append(cur)
    return chunks


FONT_CACHE = {}
def font(size, path=None):
    key = (path or FONT_MAIN, size)
    if key not in FONT_CACHE:
        FONT_CACHE[key] = ImageFont.truetype(path or FONT_MAIN, size)
    return FONT_CACHE[key]


def draw_rich_line(d, y, toks, f, pal, stroke=7, center_x=W / 2):
    lw = d.textlength(' '.join(w for w, _ in toks), font=f)
    x = center_x - lw / 2
    for w, kind in toks:
        col = {'normal': (255, 255, 255), 'kw': hexc(pal['accent']), 'quote': hexc(pal['quote'])}[kind]
        d.text((x, y), w, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0))
        x += d.textlength(w + ' ', font=f)


def draw_sub(img, text, keywords, pal):
    d = ImageDraw.Draw(img)
    toks = tokenize(text, keywords)
    plain = ' '.join(w for w, _ in toks)
    for size in range(84, 59, -2):
        f = font(size)
        if d.textlength(plain, font=f) <= SUB_MAXW:
            draw_rich_line(d, SUB_CENTER - size // 2, toks, f, pal)
            return
    f = font(62)
    lines, cur = [], []
    for t in toks:
        if cur and d.textlength(' '.join(w for w, _ in cur + [t]), font=f) > SUB_MAXW:
            lines.append(cur); cur = [t]
        else:
            cur.append(t)
    if cur: lines.append(cur)
    lh = 78; y = SUB_CENTER - lh * len(lines) // 2
    for ln in lines[:2]:
        draw_rich_line(d, y, ln, f, pal); y += lh


def ease(p):
    return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, p)))


def wav_name(i, text, voice=''):
    key = (voice + '|' + text) if voice else text
    return f'b{i:02d}_{hashlib.md5(key.encode("utf-8")).hexdigest()[:8]}.wav'


# ---------------- subtitles v3: 1~2 line cuts with natural line breaks
BREAK_AFTER = ('고', '며', '서', '아', '어', '는데', '지만', '면', '니까', '해', '데', '도', '은', '는', '이', '가', '을', '를', '에', '에게', '께', '와', '과')


def _tok_len(toks):
    return sum(len(w) for w, _ in toks)


def _break_score(toks, k):
    """penalty for breaking before toks[k] (lower is better)"""
    prev, nxt = toks[k - 1][0], toks[k][0]
    hang = re.sub(r'[^가-힣]', '', prev)
    pen = 0.0
    if prev.endswith((',', '…')) or '”' in prev or prev.endswith('"'):
        pen -= 6          # after a comma / closing quote
    elif len(hang) <= 2 and not hang.endswith(('고', '며', '서', '아', '어', '면', '에', '을', '를', '와', '과', '도')):
        pen += 6          # after a short modifier (한두, 좋은, 그, 더 ...) -> keep it with the next word
    elif hang.endswith(BREAK_AFTER):
        pen -= 2
    nh = re.sub(r'[^가-힣]', '', nxt)
    if nh and nh[0] in '수건것거게줄적뿐데' and len(nh) <= 3:
        pen += 8          # before a bound noun (기다릴 / 수, 챙기는 / 건) -> keep together
    if hang in ('가장', '더', '덜', '아주', '너무', '정말', '진짜', '제일', '매우', '좀', '꼭', '잘', '안', '못', '다'):
        pen += 6          # right after an adverb (가장 / 큰) -> keep it with the next word
    if k == len(toks) - 1 and len(re.sub(r'[^가-힣]', '', nxt)) <= 3:
        pen += 7          # orphan short last word (거죠. / 해요.)
    if nxt.startswith(('“', '"')):
        pen -= 3          # just before an opening quote
    if toks[k - 1][1] == 'quote' and toks[k][1] == 'quote' and '”' not in prev:
        pen += 20         # never split inside a quoted line
    if len(toks[k][0]) <= 2 and k == len(toks) - 1:
        pen += 5          # orphan short word
    return pen


def layout_cuts(d, toks):
    """returns list of cuts; cut = (lines(list of token lists), font size)"""
    plain = lambda ts: ' '.join(w for w, _ in ts)
    for size in range(80, 65, -2):
        if d.textlength(plain(toks), font=font(size)) <= SUB_MAXW and _tok_len(toks) <= 16:
            return [([toks], size)]
    best = None
    if len(toks) >= 2:
        for size in range(72, 61, -2):
            f = font(size)
            for k in range(1, len(toks)):
                a, b = toks[:k], toks[k:]
                wa, wb = d.textlength(plain(a), font=f), d.textlength(plain(b), font=f)
                if wa > SUB_MAXW or wb > SUB_MAXW:
                    continue
                score = abs(wa - wb) / 60.0 + _break_score(toks, k) - size / 10.0
                if best is None or score < best[0]:
                    best = (score, [a, b], size)   # all sizes compared: a natural break at 68px beats an awkward one at 72px
    if best and _tok_len(toks) <= 30:
        return [(best[1], best[2])]
    # too long for one cut -> split at the most natural point near the middle, recurse
    half = _tok_len(toks) / 2; cand = None
    for k in range(1, len(toks)):
        score = abs(_tok_len(toks[:k]) - half) / 3.0 + _break_score(toks, k)
        if cand is None or score < cand[0]:
            cand = (score, k)
    k = cand[1]
    return layout_cuts(d, toks[:k]) + layout_cuts(d, toks[k:])


def draw_cut(img, cut, pal):
    d = ImageDraw.Draw(img)
    lines, size = cut
    f = font(size); lh = int(size * 1.24)
    y = SUB_CENTER - lh * len(lines) // 2 + (lh - size) // 2
    for ln in lines:
        draw_rich_line(d, y, ln, f, pal)
        y += lh


# ---------------- audio helpers (ffmpeg reads only from the stage dir, writes only to stdout)
def stage_dir():
    # Python 3.13 mkdtemp applies an owner-only ACL on Windows that blocks subfolders here -> plain makedirs
    base = os.environ.get('RENDER_STAGE') or tempfile.gettempdir()
    p = os.path.join(base, 'render_' + os.urandom(4).hex()); os.makedirs(p); return p


def measure_lufs(path):
    r = subprocess.run([FFMPEG, '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True)
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr.decode('utf-8', 'replace'))
    return float(m[-1]) if m else -20.0


def bgm_filter(S, tl, total, stage, first_input):
    """build ffmpeg inputs/filters for BGM segments. returns (input_args, filter_parts, labels, info)"""
    segs = (S.get('bgm') or [])[:1]   # one track per video (operator rule 2026-10-09)
    if not segs:
        return [], [], [], []
    idx = {}
    try:
        for e in json.load(open(os.path.join(ROOT, 'assets', 'bgm', 'bgm_index.json'), encoding='utf-8')):
            idx[e['file']] = e
    except Exception:
        pass
    X = 0.6
    starts = [0.0 if s.get('start_beat', 0) == 0 else tl[s['start_beat']]['start'] for s in segs]
    inputs, parts, labels, info = [], [], [], []
    for j, s in enumerate(segs):
        vs = starts[j]; ve = starts[j + 1] if j + 1 < len(segs) else total
        a = max(0.0, vs - (X / 2 if j > 0 else 0)); b = min(total, ve + (X / 2 if j + 1 < len(segs) else 0))
        align_t = tl[s['align_beat']]['start'] if 'align_beat' in s else 0.0
        off = s.get('align_track_time', 0.0) + (a - align_t)
        if off < 0:
            off = 0.0
        dur = b - a
        src = os.path.join(stage, f'bgm{j}.mp3'); shutil.copy(os.path.join(ROOT, s['file']), src)
        e = idx.get(s['file'])
        if e:
            win = e['loudness_per_sec'][int(off):int(off + dur) + 1] or [e['integrated_lufs']]
            win = [x for x in win if x > -60] or [e['integrated_lufs']]
            lev = 10 * math.log10(sum(10 ** (x / 10) for x in win) / len(win))
        else:
            lev = measure_lufs(src)
        # 자막형(내레이션 없음)이면 BGM이 주 음원 -> -15 LUFS 근처로 올린다
        base = (TARGET_LUFS - 1.0) if S.get('_silent') else (TARGET_LUFS + BGM_DUCK_DB)
        gain = base - lev + s.get('gain_db', 0.0)
        k = first_input + j
        inputs += ['-i', src]
        f = (f'[{k}:a]atrim=start={off:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,'
             f'aformat=sample_rates=48000:channel_layouts=stereo,volume={gain:.2f}dB')
        if j > 0:
            f += f',afade=t=in:st=0:d={X}'
        fo = X if j + 1 < len(segs) else 1.2
        f += f',afade=t=out:st={max(0, dur - fo):.3f}:d={fo},adelay={int(a * 1000)}|{int(a * 1000)}[bg{j}]'
        parts.append(f); labels.append(f'[bg{j}]')
        info.append({'file': s['file'], 'video_from': round(a, 2), 'video_to': round(b, 2), 'track_from': round(off, 2),
                     'gain_db': round(gain, 1), 'align_beat': s.get('align_beat'), 'align_track_time': s.get('align_track_time')})
    return inputs, parts, labels, info


def check_thumbnail(S):
    """Thumbnail guard (2026-10-09): frame 0 = cover.jpg = YouTube thumbnail must be a broadcast capture of the
    highlight scene inside this video's segment. GIF / card / quote cuts can never be the cover.
    script.json may set "thumbnail": {"capture": "C1", "sec": 852, "reason": "..."}; beat 0 must use that capture."""
    caps_def = S.get('captures', {})
    th = S.get('thumbnail') or {}
    v0 = S['beats'][0]['visual']
    if v0 not in caps_def:
        raise SystemExit(f'thumbnail guard: beat 0 visual "{v0}" is not a broadcast capture (GIF/card cannot be the cover)')
    if th.get('capture') and th['capture'] != v0:
        raise SystemExit(f'thumbnail guard: thumbnail.capture {th["capture"]} != beat 0 visual {v0}')
    m = re.search(r'cand_(\d+(?:\.\d+)?)', caps_def[v0]['file'])
    sec = th.get('sec', float(m.group(1)) if m else None)
    hl = S.get('segment') or {}
    if sec is not None and isinstance(hl.get('start'), (int, float)) and isinstance(hl.get('end'), (int, float)):
        if not (hl['start'] - 2 <= sec <= hl['end'] + 2):
            raise SystemExit(f'thumbnail guard: cover capture {sec}s is outside highlight segment {hl["start"]}~{hl["end"]}s')
    return {'source': 'capture', 'visual': v0, 'file': caps_def[v0]['file'], 'sec': sec, 'reason': th.get('reason', '')}


def main(folder):
    folder = os.path.abspath(folder)
    S = json.load(open(os.path.join(folder, 'script.json'), encoding='utf-8'))
    pal = S['palette']; bg = hexc(pal['bg'])
    tdir = os.path.join(folder, 'tts'); os.makedirs(tdir, exist_ok=True)
    beats = S['beats']
    cover_info = check_thumbnail(S)
    wavs = []
    provider = S.get('tts_provider', TTS_CFG['provider'])
    voice = S.get('tts_voice', TTS_CFG['voice'])
    # 자막형(내레이션 없음, 2026-10-11 운영자 결정): TTS가 꺼져 있거나 script.json에 "narration": "none"이면
    # 음성 없이 문장 길이로 시간을 정하고(읽는 속도 기준) 자막 + BGM으로 만든다. 원본 음성은 쓰지 않는다.
    silent = S.get('narration') == 'none' or (S.get('narration') != 'tts' and not TTS_CFG.get('enabled', True))
    S['_silent'] = silent
    if silent:
        provider = 'none'
    for i, b in enumerate(beats):
        if silent:
            n = len(re.sub(r'\s', '', b['text']))
            sec = 2.0 if (b.get('opening') or b.get('end')) else min(4.0, max(1.8, 0.5 + 0.13 * n))
            p = os.path.join(tdir, f'silent_{i:02d}.wav')
            with wave.open(p, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x00' * int(sec * 24000) * 2)
        elif provider == 'gemini':
            p = os.path.join(tdir, wav_name(i, tts_text(b), voice))
            if not os.path.exists(p):
                raise SystemExit(f'TTS 조각 없음({p}). tools/tts_prepare.py -> tools/tts_gemini.ps1 -> tools/tts_split.py 먼저 실행')
        else:
            p = os.path.join(tdir, wav_name(i, tts_text(b)))
            tts(tts_text(b), p, S.get('tts_rate', 1.1))
        wavs.append(p)
    durs = [wav_dur(p) for p in wavs]
    t = LEAD; tl = []
    for i, b in enumerate(beats):
        tl.append({'i': i, 'start': round(t, 3), 'end': round(t + durs[i], 3), 'visual': b['visual']})
        t += durs[i] + GAP
    total = t + 0.25
    with wave.open(wavs[0]) as w0:
        sr, sw, ch = w0.getframerate(), w0.getsampwidth(), w0.getnchannels()
    def silence(sec): return b'\x00' * int(sec * sr) * sw * ch
    audio = silence(LEAD)
    for p in wavs:
        with wave.open(p) as w:
            audio += w.readframes(w.getnframes())
        audio += silence(GAP)
    audio += silence(0.25)
    nar = os.path.join(folder, 'narration.wav')
    with wave.open(nar, 'wb') as w:
        w.setnchannels(ch); w.setsampwidth(sw); w.setframerate(sr); w.writeframes(audio)
    caps = {}
    for k, c in S.get('captures', {}).items():
        im = blur_capture(os.path.join(ROOT, c['file']), c.get('blur', []))
        if c.get('crop'): im = im.crop(tuple(c['crop']))
        caps[k] = (im, c.get('credit', ''))
    pw, ph = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
    cache = {}
    def panel_img(b):
        vis = b['visual']
        if b.get('end') and os.path.exists(END_IMG):
            if '__end__' not in cache:
                cache['__end__'] = (end_card(pw, ph), '', 'brand')
            return cache['__end__']
        key = vis + '|' + b.get('fit', '') + '|' + (b.get('card') or b.get('quote') or (b['text'] if vis in ('card', 'quote') else ''))
        if key in cache: return cache[key]
        if vis in caps:
            im, cr = caps[vis]
            if b.get('fit') == 'cover':
                out = (fit_cover(im, pw, ph, tuple(b.get('focus', (0.5, 0.5)))), cr, 'capture')
            else:
                out = (fit_contain(im, pw, ph, bg), cr, 'capture')
        elif vis.startswith('gif:'):
            out = (load_gif(os.path.join(ROOT, vis[4:]), pw, ph, bg, b.get('fit', 'cover')), '', 'gif')
        elif vis.startswith('il:'):
            out = (fit_cover(Image.open(os.path.join(ROOT, vis[3:])).convert('RGB'), pw, ph, (0.5, 0.35)), '', 'illustration')
        elif vis == 'quote':
            card = Image.new('RGB', (pw, ph), hexc('#1E1E2A')); d = ImageDraw.Draw(card); f = font(92)
            lines = b.get('quote', '').split('\n'); y = ph // 2 - len(lines) * 62
            d.text((70, y - 130), '“', font=font(170), fill=hexc(pal['quote']))
            for ln in lines:
                lw = d.textlength(ln, font=f); d.text(((pw - lw) / 2, y), ln, font=f, fill=(255, 255, 255)); y += 124
            out = (card, S['source']['program'] + ' 방송 대사', 'graphic')
        else:
            card = Image.new('RGB', (pw, ph), hexc(pal['accent'])); d = ImageDraw.Draw(card); f = font(96)
            msg = b.get('card', b['text']); words = msg.split(' ')
            lines, cur = [], ''
            for w_ in words:
                if cur and d.textlength(cur + ' ' + w_, font=f) > pw - 120:
                    lines.append(cur); cur = w_
                else:
                    cur = (cur + ' ' + w_).strip()
            if cur: lines.append(cur)
            y = ph // 2 - len(lines) * 64
            for ln in lines:
                lw = d.textlength(ln, font=f); d.text(((pw - lw) / 2, y), ln, font=f, fill=(20, 20, 28)); y += 128
            out = (card, '', 'graphic')
        cache[key] = out
        return out
    memes = {}
    def meme_img(m):
        key = json.dumps(m, ensure_ascii=False)
        if key not in memes:
            if isinstance(m, dict):
                src = Image.open(os.path.join(ROOT, m['file'])).convert('RGB')
                if m.get('crop'): src = src.crop(tuple(m['crop']))
            else:
                src = Image.open(os.path.join(ROOT, m)).convert('RGB')
            bw, bh = MEME_BOX[2] - MEME_BOX[0] - 16, MEME_BOX[3] - MEME_BOX[1] - 16
            memes[key] = rounded(fit_cover(src, bw, bh), 30)
        return memes[key]
    # base frame: background + title (no box, white text, accent on key words / numbers)
    base = Image.new('RGB', (W, H), bg)
    bd = ImageDraw.Draw(base)
    for yy in range(H):
        k = 0.85 + 0.3 * yy / H
        bd.line([(0, yy), (W, yy)], fill=tuple(min(255, int(c * k)) for c in bg))
    tkw = S.get('title_keywords', [])
    ty = TITLE_Y
    for ln in S['hook_title']:
        toks = tokenize(ln, tkw)
        size = 112
        while size > 70 and bd.textlength(ln, font=font(size)) > 1000:
            size -= 4
        draw_rich_line(bd, ty, toks, font(size), pal, stroke=8)
        ty += int(size * 1.18)
    f_credit = font(26, FONT_SMALL)
    subs = []   # (start, end, cut, plain text)
    md = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    for seg in tl:
        b = beats[seg['i']]
        if b.get('no_sub') or b['visual'] == 'card':
            continue
        cuts = layout_cuts(md, tokenize(b['text'], b.get('keywords', [])))
        lens = [max(1, sum(len(w) for ln in c[0] for w, _ in ln)) for c in cuts]
        st = seg['start']; span = seg['end'] - st
        for c, n_ in zip(cuts, lens):
            dd = span * n_ / sum(lens)
            subs.append((st, st + dd, c, ' / '.join(' '.join(w for w, _ in ln) for ln in c[0]))); st += dd
    fdir = os.path.join(folder, '_frames')
    if os.path.exists(fdir): shutil.rmtree(fdir)
    os.makedirs(fdir)
    nframes = int(total * FPS); cap_time = 0.0; meme_time = 0.0; gif_time = 0.0
    for fi in range(nframes):
        tt = fi / FPS
        seg = next((s for s in tl if tt < s['end'] + GAP), tl[-1])
        b = beats[seg['i']]
        pim, credit, kind = panel_img(b)
        credit = b.get('credit', credit)
        if kind == 'capture': cap_time += 1.0 / FPS
        if kind == 'gif':
            gif_time += 1.0 / FPS
            pim = gif_frame(pim, tt - seg['start'])
        elif b.get('zoom') == 'in':
            p = (tt - seg['start']) / max(0.5, seg['end'] + GAP - seg['start'])
            pim = smooth_zoom(pim, 1.0 + 0.08 * ease(p))
        fr = base.copy()
        fr.paste(pim, (PANEL[0], PANEL[1]))
        d = ImageDraw.Draw(fr)
        if credit:
            d.text((PANEL[0] + 30, CREDIT_Y), credit, font=f_credit, fill=(200, 200, 205))
        if b.get('meme'):
            meme_time += 1.0 / FPS
            mi = meme_img(b['meme'])
            a = min(1.0, max(0.0, (tt - seg['start']) / 0.2))
            if a < 1.0:
                mi = mi.copy(); mi.putalpha(mi.getchannel('A').point(lambda v: int(v * a)))
            fr.paste(mi, (MEME_BOX[0], MEME_BOX[1]), mi)
        sub = next((s for s in subs if s[0] <= tt < s[1] + GAP), None)
        if sub and not b.get('no_sub') and b['visual'] != 'card':
            draw_cut(fr, sub[2], pal)
        if b.get('end') and tt > seg['start'] + 0.3:
            msg = END_TEXT; f = font(70)
            d.text(((W - d.textlength(msg, font=f)) / 2, 1420), msg, font=f, fill=hexc(pal['accent']), stroke_width=6, stroke_fill=(0, 0, 0))
        fr.save(os.path.join(fdir, f'{fi:05d}.jpg'), quality=90)
        if fi == 0:
            fr.save(os.path.join(folder, 'cover.jpg'), quality=90)
    out = os.path.join(folder, 'final.mp4')
    # ffmpeg cannot open files under the OneDrive/Korean project path in this environment -> stage in a temp dir
    stage = stage_dir()
    sframes = os.path.join(stage, 'frames'); shutil.copytree(fdir, sframes)
    snar = os.path.join(stage, 'narration.wav'); shutil.copy(nar, snar)
    vgain = 0.0 if silent else TARGET_LUFS - measure_lufs(snar)
    b_in, b_parts, b_labels, bgm_info = bgm_filter(S, tl, total, stage, 2)
    fc = [f'[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vgain:.2f}dB[vo]'] + b_parts
    mix_in = '[vo]' + ''.join(b_labels)
    fc.append(f'{mix_in}amix=inputs={1 + len(b_labels)}:normalize=0:duration=first,alimiter=limit=0.84:level=false[aout]')
    cmd = [FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-framerate', str(FPS), '-i', os.path.join(sframes, '%05d.jpg'),
           '-i', snar] + b_in + ['-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[aout]',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest',
           # ffmpeg.exe is denied file writes in this environment -> stream fragmented MP4 to stdout, Python writes the file
           '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', 'pipe:1']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 1000:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:500])
    with open(out, 'wb') as fo:
        fo.write(r.stdout)
    shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(fdir)
    json.dump({'total_sec': round(total, 2), 'capture_sec': round(cap_time, 2), 'capture_ratio': round(cap_time / total, 3),
               'reaction_overlay_sec': round(meme_time, 2), 'gif_sec': round(gif_time, 2), 'cover': cover_info, 'narration': 'none' if silent else 'tts', 'tts': {'provider': provider, 'voice': voice}, 'bgm': bgm_info,
               'beats': tl, 'subs': [(round(a, 2), round(b_, 2), len(c[0]), c[1], txt) for a, b_, c, txt in subs]},
              open(os.path.join(folder, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('done', round(total, 2), 'sec; capture ratio', round(cap_time / total, 3), '; reaction overlay', round(meme_time, 2))


if __name__ == '__main__':
    main(sys.argv[1])
