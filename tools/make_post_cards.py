# -*- coding: utf-8 -*-
"""게시글 카드 생성: post.json(게시글 원문) + cards.json(카드 구성) -> 1080x680 JPG 카드 (render_short.py의 중앙 패널 크기).
게시판 글은 방송 장면이 없으므로, 원문 문장을 그대로 옮긴 '게시글 카드'가 방송 캡처 자리를 대신한다(captures에 등록).
작성자 닉네임·IP는 카드에 넣지 않는다. 본문 이미지(타인 사진·기사 사진 등)는 카드에 넣지 않는다.
usage: python tools/make_post_cards.py output/YYYY-MM-DD/NN
cards.json 예:
{"theme": "light", "gallery": "싱글벙글 갤러리", "out_dir": "assets/captures/2026-10-11/01",
 "cards": [
   {"id": "P1", "type": "title"},                                          # 갤러리·제목·조회/추천/댓글
   {"id": "P2", "type": "body", "lines": ["원문 문장1", "원문 문장2"], "highlight": "강조할 구절"},
   {"id": "P3", "type": "comments", "items": ["댓글1", "댓글2", "댓글3"]},  # 닉네임 없이 내용만
   {"id": "P4", "type": "stat"}                                            # 조회·추천·댓글 큰 숫자
 ]}
출력: <out_dir>/post_<id>.jpg 와 표준출력에 script.json 'captures' 조각(JSON)."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 680
F_HEAD = os.path.join(ROOT, 'assets', 'fonts', 'BlackHanSans-Regular.ttf')
F_BODY = r'C:\Windows\Fonts\malgun.ttf'
F_BOLD = r'C:\Windows\Fonts\malgunbd.ttf'
THEMES = {
    'light': {'bg': (246, 247, 251), 'paper': (255, 255, 255), 'bar': (59, 72, 144), 'bar_t': (255, 255, 255),
              'text': (28, 28, 34), 'sub': (120, 124, 138), 'hl': (255, 222, 89), 'bubble': (238, 241, 250), 'line': (222, 226, 236)},
    'dark': {'bg': (22, 23, 30), 'paper': (34, 36, 46), 'bar': (59, 72, 144), 'bar_t': (255, 255, 255),
             'text': (240, 240, 245), 'sub': (150, 154, 170), 'hl': (255, 212, 0), 'bubble': (48, 51, 66), 'line': (60, 64, 80)},
}


def f(path, size): return ImageFont.truetype(path, size)


def wrap(d, text, font, width):
    """글자 단위 줄바꿈(한국어), 가능하면 공백에서 끊는다."""
    out, cur = [], ''
    for ch in text:
        if d.textlength(cur + ch, font=font) <= width:
            cur += ch
            continue
        cut = cur.rfind(' ')
        if cut > len(cur) * 0.5:
            out.append(cur[:cut]); cur = cur[cut + 1:] + ch
        else:
            out.append(cur); cur = ch
    if cur: out.append(cur)
    return out


def fmt(n): return f'{int(n):,}'


def frame(T, gallery):
    im = Image.new('RGB', (W, H), T['bg']); d = ImageDraw.Draw(im)
    d.rounded_rectangle([40, 30, W - 40, H - 30], 28, fill=T['paper'], outline=T['line'], width=2)
    d.rounded_rectangle([40, 30, W - 40, 104], 28, fill=T['bar'])
    d.rectangle([40, 76, W - 40, 104], fill=T['bar'])
    d.text((76, 44), '실시간 베스트', font=f(F_HEAD, 38), fill=T['bar_t'])
    if gallery:
        g = f(F_BOLD, 28); gw = d.textlength(gallery, font=g)
        d.text((W - 76 - gw, 52), gallery, font=g, fill=(205, 212, 245))
    return im, d


def card_title(P, C, T, gallery):
    im, d = frame(T, gallery)
    title = C.get('title') or P['title']
    ft = f(F_BOLD, 58)
    lines = wrap(d, title, ft, W - 160)[:3]
    y = 104 + (H - 30 - 104 - (len(lines) * 82 + 110)) // 2   # 제목+구분선+조회 줄 묶음을 세로 가운데로
    for ln in lines:
        d.text((80, y), ln, font=ft, fill=T['text']); y += 82
    d.line([80, y + 24, W - 80, y + 24], fill=T['line'], width=2)
    meta = f"조회 {fmt(P.get('views', 0))}   ·   추천 {fmt(P.get('rec', 0))}   ·   댓글 {fmt(P.get('comments', 0))}"
    d.text((80, y + 50), meta, font=f(F_BOLD, 34), fill=T['sub'])
    return im


def card_body(P, C, T, gallery):
    im, d = frame(T, gallery)
    fh = f(F_BODY, 26)
    head = wrap(d, P['title'], fh, W - 160)[0]
    d.text((80, 122), head, font=fh, fill=T['sub'])
    fb = f(F_BOLD, 46); lh = 66
    hl = C.get('highlight', '')
    lines = []
    for s in C['lines']:
        lines += wrap(d, s, fb, W - 170)
    lines = lines[:6]
    y = 178 + max(0, (6 - len(lines)) * lh // 2)
    for ln in lines:
        if hl and hl in ln:
            a = ln.index(hl)
            x0 = 84 + d.textlength(ln[:a], font=fb); x1 = x0 + d.textlength(hl, font=fb)
            d.rectangle([x0 - 4, y + 8, x1 + 4, y + lh - 8], fill=T['hl'])
            d.text((84, y), ln[:a], font=fb, fill=T['text'])
            d.text((x0, y), hl, font=fb, fill=(20, 20, 28))
            d.text((x1, y), ln[a + len(hl):], font=fb, fill=T['text'])
        else:
            d.text((84, y), ln, font=fb, fill=T['text'])
        y += lh
    return im


def card_comments(P, C, T, gallery):
    im, d = frame(T, gallery)
    d.text((80, 122), f"댓글 {fmt(P.get('comments', 0))}", font=f(F_BOLD, 32), fill=T['sub'])
    fc = f(F_BOLD, 40); y = 182
    for it in C['items'][:4]:
        ls = wrap(d, it, fc, W - 230)[:2]
        bh = 30 + 56 * len(ls)
        if y + bh > H - 50: break
        d.ellipse([80, y + 8, 128, y + 56], fill=T['line'])
        d.rounded_rectangle([146, y, W - 80, y + bh], 22, fill=T['bubble'])
        yy = y + 14
        for ln in ls:
            d.text((172, yy), ln, font=fc, fill=T['text']); yy += 56
        y += bh + 20
    return im


def card_stat(P, C, T, gallery):
    im, d = frame(T, gallery)
    items = [('조회', P.get('views', 0)), ('추천', P.get('rec', 0)), ('댓글', P.get('comments', 0))]
    cw = (W - 160) / 3
    for i, (k, v) in enumerate(items):
        cx = 80 + cw * i + cw / 2
        fv = f(F_HEAD, 92); s = fmt(v)
        d.text((cx - d.textlength(s, font=fv) / 2, 250), s, font=fv, fill=T['text'] if i else T['bar'])
        fk = f(F_BOLD, 38)
        d.text((cx - d.textlength(k, font=fk) / 2, 380), k, font=fk, fill=T['sub'])
    cap = C.get('caption', '')
    if cap:
        fc = f(F_BOLD, 36)
        d.text(((W - d.textlength(cap, font=fc)) / 2, 500), cap, font=fc, fill=T['sub'])
    return im


KINDS = {'title': card_title, 'body': card_body, 'comments': card_comments, 'stat': card_stat}


def main(folder):
    folder = os.path.abspath(folder)
    P = json.load(open(os.path.join(folder, 'post.json'), encoding='utf-8-sig'))
    spec = json.load(open(os.path.join(folder, 'cards.json'), encoding='utf-8-sig'))
    T = THEMES[spec.get('theme', 'light')]
    gallery = spec.get('gallery') or (P.get('gallery_tag') or '')
    out_dir = os.path.join(ROOT, spec['out_dir']); os.makedirs(out_dir, exist_ok=True)
    credit = spec.get('credit') or f"출처: 디시인사이드 실시간 베스트 {('[' + P['gallery_tag'] + '] ') if P.get('gallery_tag') else ''}게시글"
    caps = {}
    for C in spec['cards']:
        im = KINDS[C['type']](P, C, T, gallery)
        name = f"post_{C['id']}.jpg"
        im.save(os.path.join(out_dir, name), quality=92)
        caps[C['id']] = {'file': spec['out_dir'].rstrip('/') + '/' + name, 'credit': credit}
    print(json.dumps(caps, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
