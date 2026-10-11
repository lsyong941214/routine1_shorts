# -*- coding: utf-8 -*-
"""Gemini 전체 내레이션 wav를 문장(비트)별 wav로 자른다.
- 10ms 창 RMS로 무음 구간을 찾고, 가장 긴 무음 N-1개를 문장 경계로 쓴다.
- 각 조각 앞뒤 무음은 40ms만 남긴다. 조각 길이가 글자 수 비율과 크게 어긋나면 실패로 알린다.
- 필요하면 SPEED(atempo, 기본 channels 설정) 적용: ffmpeg는 스크래치에서 읽고 stdout으로만 쓴다.
usage: python tools/tts_split.py output/YYYY-MM-DD/NN"""
import json, os, sys, wave, array, math, glob, re, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_short import tts_text, wav_name, TTS_CFG, FFMPEG


def rms_frames(samples, sr, win=0.01):
    n = int(sr * win); out = []
    for i in range(0, len(samples) - n, n):
        seg = samples[i:i + n]
        out.append(math.sqrt(sum(x * x for x in seg) / n))
    return out, n


def speedup(path, tempo):
    if abs(tempo - 1.0) < 0.01:
        return
    stage = tempfile.mkdtemp(prefix='tempo_', dir=os.environ.get('RENDER_STAGE') or None)
    s = os.path.join(stage, 'in.wav'); shutil.copy(path, s)
    r = subprocess.run([FFMPEG, '-v', 'error', '-i', s, '-af', f'atempo={tempo}', '-f', 'wav', 'pipe:1'], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 1000:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:300])
    open(path, 'wb').write(r.stdout)
    shutil.rmtree(stage, ignore_errors=True)


def main(folder):
    folder = os.path.abspath(folder)
    S = json.load(open(os.path.join(folder, 'script.json'), encoding='utf-8'))
    job = json.load(open(os.path.join(folder, 'tts', 'jobs.json'), encoding='utf-8'))
    full = job['items'][0]['out']
    voice = job['voice']
    tempo = S.get('tts_tempo', TTS_CFG.get('tempo', 1.0))
    if abs(tempo - 1.0) >= 0.01:
        sped = full.replace('.wav', f'_x{tempo}.wav')
        if not os.path.exists(sped):
            shutil.copy(full, sped); speedup(sped, tempo)
        full = sped
    w = wave.open(full); sr, sw, ch = w.getframerate(), w.getsampwidth(), w.getnchannels()
    data = array.array('h', w.readframes(w.getnframes())); w.close()
    if ch == 2:
        data = data[::2]
    env, n = rms_frames(data, sr)
    peak = sorted(env)[int(len(env) * 0.95)]
    thr = max(peak * 0.06, 120)
    quiet = [e < thr for e in env]
    runs, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            runs.append((i, j)); i = j
        else:
            i += 1
    speech = [k for k, q in enumerate(quiet) if not q]
    first, last = speech[0], speech[-1] + 1
    inner = [r for r in runs if r[0] > first and r[1] < last]
    N = len(S['beats'])
    texts = [tts_text(b) for b in S['beats']]
    weights = [max(1, len(re.sub(r'[\s,.?!…“”"\'~]', '', t))) for t in texts]
    if len(inner) < N - 1:
        raise SystemExit(f'FAIL: 무음 구간 {len(inner)}개 < 필요한 {N - 1}개 (문장 사이 쉼이 부족)')
    # DP 정렬: 무음 후보 중 N-1개를 골라, 각 문장 조각 길이가 (글자 수 x 평균 속도)에 가깝고
    # 경계 무음이 길수록 유리하도록 비용 최소화. 쉼표 쉼(짧음)보다 문장 사이 쉼(김)을 선호한다.
    inner = [r for r in inner if r[1] - r[0] >= 5]          # 50ms 이상
    cand = [((a + b) / 2, b - a) for a, b in inner]
    M = len(cand)
    speech_frames = sum(1 for q in quiet[first:last] if not q)
    rate = (last - first) / sum(weights)                    # frames per char (쉼 포함 평균)
    exp_len = [w_ * rate for w_ in weights]
    pos = [first] + [c[0] for c in cand] + [last]
    sil = [0] + [c[1] for c in cand] + [0]
    INF = float('inf')
    # dp[j][m] = 최소 비용: 문장 j개를 끝냈고 마지막 경계가 pos[m]
    dp = [[INF] * (M + 2) for _ in range(N + 1)]; prv = [[-1] * (M + 2) for _ in range(N + 1)]
    dp[0][0] = 0.0
    for j in range(1, N + 1):
        ms = range(M + 1, M + 2) if j == N else range(1, M + 1)
        for m in ms:
            for p in range(0, m):
                if dp[j - 1][p] == INF:
                    continue
                seg = pos[m] - pos[p]
                c = ((seg - exp_len[j - 1]) / exp_len[j - 1]) ** 2 * 10
                if j < N:
                    c -= min(sil[m], 60) / 60 * 3                # 긴 쉼 보너스(최대 0.6s)
                if dp[j - 1][p] + c < dp[j][m]:
                    dp[j][m] = dp[j - 1][p] + c; prv[j][m] = p
    if dp[N][M + 1] == INF:
        raise SystemExit('FAIL: 정렬 불가')
    path, m = [], M + 1
    for j in range(N, 0, -1):
        path.append(m); m = prv[j][m]
    path = path[::-1]
    bounds = [first] + [int(pos[m]) for m in path[:-1]] + [last]
    report = []
    pad = 4  # 40ms
    for bi in range(N):
        a, b = bounds[bi], bounds[bi + 1]
        while a < b and quiet[a]: a += 1
        while b > a and quiet[b - 1]: b -= 1
        a, b = max(0, a - pad), min(len(env), b + pad)
        seg = data[a * n:b * n]
        out = os.path.join(folder, 'tts', wav_name(bi, texts[bi], voice))
        wo = wave.open(out, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(sr); wo.writeframes(seg.tobytes()); wo.close()
        dur = len(seg) / sr
        report.append((bi, round(dur, 2), round(dur / weights[bi], 3), texts[bi]))
    rates = [r[2] for r in report]
    med = sorted(rates)[len(rates) // 2]
    bad = [r for r in report if r[2] > med * 2.2 or r[2] < med * 0.45]
    for r in report:
        print(r)
    print('sec/char median', med, 'suspicious', [r[0] for r in bad])
    if bad:
        raise SystemExit('FAIL: 분할 결과 문장 길이 비율 이상 -> 수동 확인 필요')


if __name__ == '__main__':
    main(sys.argv[1])
