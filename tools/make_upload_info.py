# -*- coding: utf-8 -*-
"""업로드 정보 정리: meta.json -> 최종 설명란(upload_description) 조립 + 규칙 점검 + upload_info.md(사람이 보고 붙여넣는 용).
usage: python tools/make_upload_info.py output/YYYY-MM-DD/NN
meta.json 필수 키: title_candidates(3), selected_title, youtube_description(해시태그 제외 본문), hashtags(3~5, '#Shorts' 포함),
                  tags(5~15), reels_caption, source{url, gallery, title}
결과: meta.json에 upload_description 추가, upload_info.md 생성. 규칙 위반은 FAIL 줄로 출력하고 종료 코드 1."""
import json, os, re, sys

SUB_LINE = '구독과 좋아요는 꿀잼잠에게 큰 힘이 됩니다.'
CHANNEL_TAG = '#꿀잼잠'
BANNED = ['충격', '경악', '소름', '레전드', '역대급']   # 무관한 자극어 (내용과 직접 맞으면 운영자 판단)


def main(folder):
    folder = os.path.abspath(folder)
    mp = os.path.join(folder, 'meta.json')
    M = json.load(open(mp, encoding='utf-8-sig'))
    fails, warns = [], []
    t = M['selected_title']
    if len(t) > 40: fails.append(f'제목 {len(t)}자 (40자 이내)')
    if '#' in t: fails.append('제목에 해시태그 금지')
    if len(re.findall(r'[\U0001F300-\U0001FAFF☀-➿]', t)) > 1: fails.append('제목 이모지 2개 이상')
    for w in BANNED:
        if w in t: warns.append(f'제목 자극어 "{w}" 확인')
    if len(M.get('title_candidates', [])) != 3: fails.append('제목 후보 3개 필요')
    tags_h = [h if h.startswith('#') else '#' + h for h in M['hashtags']]
    if not 3 <= len(tags_h) <= 5: fails.append(f'해시태그 {len(tags_h)}개 (3~5개)')
    if '#Shorts' not in tags_h: fails.append('#Shorts 누락')
    src = M.get('source', {})
    if not src.get('url') or src['url'] not in M['youtube_description']: fails.append('설명란에 원글 URL 누락')
    if 'AI' not in M['youtube_description']: fails.append('설명란에 AI 음성 사용 안내 누락')
    if not 5 <= len(M.get('tags', [])) <= 15: warns.append(f"태그 {len(M.get('tags', []))}개 (5~15개 권장)")
    if sum(len(x) for x in M.get('tags', [])) + len(M.get('tags', [])) > 450: fails.append('태그 합계 500자 초과 위험')
    if CHANNEL_TAG not in tags_h: tags_h.append(CHANNEL_TAG)
    desc = M['youtube_description'].rstrip() + '\n\n' + SUB_LINE + '\n' + ' '.join(tags_h)
    if len(desc) > 4900: fails.append(f'설명란 {len(desc)}자 (5000자 제한)')
    M['upload_description'] = desc
    json.dump(M, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cover = os.path.join(folder, 'cover.jpg')
    cov = f'{cover} ({os.path.getsize(cover) // 1024} KB)' if os.path.exists(cover) else '없음 — 렌더 후 다시 실행'
    md = [f'# 업로드 정보 — {os.path.basename(os.path.dirname(folder))} / {os.path.basename(folder)}', '',
          '## 제목 (선택)', t, '', '### 다른 후보'] + [f'- {c}' for c in M['title_candidates'] if c != t] + [
          '', '## 설명란 (그대로 붙여넣기)', '```', desc, '```', '',
          '## 태그 (쉼표 구분)', ', '.join(M.get('tags', [])), '',
          '## 썸네일', cov, '',
          '## 릴스 캡션', '```', M.get('reels_caption', ''), '```', '',
          '## 업로드 설정', '- 채널: 꿀잼잠 (UCIiJbXHPhK-5FFmfAvZ8PGQ)', '- 시청자층: 아니요, 아동용이 아닙니다',
          '- 유료 프로모션: 아니요', '- 변경되거나 합성된 콘텐츠(AI 사용): 예 (AI 내레이션)', '- 공개 상태: 공개 (QA 통과 즉시)', '',
          '## 원글', f"- {src.get('gallery', '')} | {src.get('title', '')}", f"- {src.get('url', '')}"]
    if fails or warns:
        md += ['', '## 점검'] + [f'- FAIL {x}' for x in fails] + [f'- 확인 {x}' for x in warns]
    open(os.path.join(folder, 'upload_info.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    for x in fails: print('FAIL', x)
    for x in warns: print('WARN', x)
    print('upload_info.md', 'OK' if not fails else 'FAIL')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main(sys.argv[1])
