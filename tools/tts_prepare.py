# -*- coding: utf-8 -*-
"""Gemini TTS 준비: 영상 1편의 내레이션 전체를 한 번의 요청으로 만들 jobs.json을 쓴다(무료 등급 하루 요청 수 절약).
usage: python tools/tts_prepare.py output/YYYY-MM-DD/NN [model]
다음 단계: powershell -File tools/tts_gemini.ps1 -Jobs <folder>/tts/jobs.json  ->  python tools/tts_split.py <folder>"""
import json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_short import tts_text, TTS_CFG

TONE = {'relationship': '차분하고 공감하는 톤으로', 'economy': '또렷하게 정보를 전달하는 톤으로', 'blackbox': '약간 긴장감 있는 톤으로',
        'community': '친구에게 썰을 풀듯 생생하고 리듬감 있는 톤으로'}


def prompt_for(S):
    lines = [tts_text(b).strip() for b in S['beats']]
    tone = TONE.get(S.get('category'), '자연스러운 톤으로')
    head = (f'다음 쇼츠 대본을 20대 후반 진행자처럼 또렷하고 조금 빠른 속도로, {tone} 읽어 주세요. '
            '각 줄은 한 문장이며, 줄과 줄 사이에는 반 박자 정도 짧게 쉬어 주세요. 지시문은 읽지 말고 대본만 읽어 주세요.\n\n')
    return head + '\n'.join(lines)


def main(folder, model=None):
    folder = os.path.abspath(folder)
    S = json.load(open(os.path.join(folder, 'script.json'), encoding='utf-8'))
    p = prompt_for(S)
    voice = S.get('tts_voice', TTS_CFG['voice'])
    h = hashlib.md5((voice + p).encode('utf-8')).hexdigest()[:8]
    tdir = os.path.join(folder, 'tts'); os.makedirs(tdir, exist_ok=True)
    job = {'model': model or TTS_CFG['model'], 'voice': voice, 'items': [{'prompt': p, 'out': os.path.join(tdir, f'full_{h}.wav')}]}
    json.dump(job, open(os.path.join(tdir, 'jobs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(os.path.join(tdir, 'jobs.json'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
