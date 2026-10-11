# -*- coding: utf-8 -*-
"""BGM 분석: 길이, 통합 음량, 1초 단위 단기 음량(LUFS) 곡선 -> 고조 구간(드롭) 위치 추정.
ffmpeg는 이 환경에서 OneDrive 경로를 못 읽으므로 RENDER_STAGE(스크래치)로 복사 후 분석한다.
usage: python tools/bgm_analyze.py  -> assets/bgm/bgm_index.json"""
import os, re, json, shutil, subprocess, tempfile, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'tools', 'ffmpeg-9.0.2-essentials_build', 'bin')
SRC = os.path.join(ROOT, '소스')
stage = tempfile.mkdtemp(prefix='bgm_', dir=os.environ.get('RENDER_STAGE') or None)
index = []
for i, p in enumerate(sorted(glob.glob(os.path.join(SRC, '*.mp3')))):
    s = os.path.join(stage, f'{i}.mp3'); shutil.copy(p, s)
    r = subprocess.run([os.path.join(BIN, 'ffmpeg.exe'), '-hide_banner', '-nostats', '-i', s, '-af', 'ebur128=framelog=info', '-f', 'null', '-'],
                       capture_output=True)
    err = r.stderr.decode('utf-8', 'replace')
    dur = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    dur = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
    # per-frame lines: t: 0.399 ... S: -23.4
    curve = {}
    for t, sl in re.findall(r't:\s*([\d.]+)\s+TARGET.*?S:\s*(-?[\d.]+|-inf)', err):
        sec = int(float(t))
        if sl != '-inf':
            curve[sec] = max(curve.get(sec, -99), float(sl))
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', err)
    pts = [curve.get(k, -70.0) for k in range(int(dur))]
    # 고조 지점: 이전 4초 평균 대비 이후 4초 평균 상승폭 최대 지점
    best, rise = 0, -99
    for k in range(4, len(pts) - 4):
        d = sum(pts[k:k + 4]) / 4 - sum(pts[k - 4:k]) / 4
        if d > rise:
            best, rise = k, d
    # 후렴(추정): 평균 음량이 가장 큰 10초 창. 시작점은 창 앞 4초 안에서 음량이 가장 크게 오르는 지점으로 당긴다.
    WIN = min(10, max(1, len(pts) // 3))
    ch = max(range(0, max(1, len(pts) - WIN + 1)), key=lambda k: sum(pts[k:k + WIN]))
    cs, cr = ch, -99
    for k in range(max(1, ch - 4), ch + 1):
        d = pts[k] - pts[k - 1]
        if d > cr:
            cs, cr = k, d
    index.append({'file': os.path.relpath(p, ROOT).replace('\\', '/'), 'name': os.path.splitext(os.path.basename(p))[0],
                  'duration': round(dur, 2), 'integrated_lufs': float(I[-1]) if I else None,
                  'peak_rise_at': best, 'peak_rise_db': round(rise, 1),
                  'chorus_start': cs, 'chorus_end': ch + WIN, 'loudness_per_sec': [round(x, 1) for x in pts]})
    print(index[-1]['name'], index[-1]['duration'], index[-1]['integrated_lufs'], 'rise@', best, round(rise, 1), 'chorus', cs, ch + WIN)
os.makedirs(os.path.join(ROOT, 'assets', 'bgm'), exist_ok=True)
json.dump(index, open(os.path.join(ROOT, 'assets', 'bgm', 'bgm_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
shutil.rmtree(stage, ignore_errors=True)

