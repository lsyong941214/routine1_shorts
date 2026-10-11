# -*- coding: utf-8 -*-
"""디시 실시간 베스트 목록(100개)에서 조회수·추천 상위 10% 후보를 고른다.
usage: python tools/dcbest_rank.py sources/dcbest/YYYY-MM-DD_list.json [top_ratio=0.1]
- 조회수 순위·추천 순위를 각각 매기고, 두 순위의 백분위 평균(score)으로 정렬한다.
- 1차 후보: 조회수 상위 10% 와 추천 상위 10% 에 모두 든 글(both).
- 보충 후보: score 상위 10% 안에 들지만 한쪽만 상위 10%인 글(either). 1차 후보가 모자랄 때만 검증한다.
- 이미 쓴 글(state/dcbest_used.json 의 no)은 제외한다.
출력: 같은 폴더에 *_rank.json (전체 순위 + 후보 표시) 과 표준출력 표."""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pct_rank(vals):
    """높을수록 1.0에 가까운 백분위(동점은 같은 값)."""
    s = sorted(vals)
    n = len(vals)
    return [(sum(1 for x in s if x < v) + 0.5 * (s.count(v) - 1)) / max(1, n - 1) for v in vals]


def main(path, ratio=0.1):
    posts = json.load(open(path, encoding='utf-8-sig'))
    used_p = os.path.join(ROOT, 'state', 'dcbest_used.json')
    used = set(json.load(open(used_p, encoding='utf-8-sig')).get('nos', [])) if os.path.exists(used_p) else set()
    n = len(posts)
    k = max(1, math.ceil(n * ratio))
    vt = sorted((p['views'] for p in posts), reverse=True)[k - 1]
    rt = sorted((p['rec'] for p in posts), reverse=True)[k - 1]
    pv, pr = pct_rank([p['views'] for p in posts]), pct_rank([p['rec'] for p in posts])
    for p, a, b in zip(posts, pv, pr):
        p['view_top'] = p['views'] >= vt
        p['rec_top'] = p['rec'] >= rt
        p['score'] = round((a + b) / 2, 4)
        p['used'] = p['no'] in used
    posts.sort(key=lambda p: (-p['score'], -p['views']))
    score_cut = posts[k - 1]['score']
    for i, p in enumerate(posts, 1):
        p['rank'] = i
        if p['used']:
            p['tier'] = 'used'
        elif p['view_top'] and p['rec_top']:
            p['tier'] = 'both'
        elif (p['view_top'] or p['rec_top']) and p['score'] >= score_cut:
            p['tier'] = 'either'
        else:
            p['tier'] = ''
    out = os.path.splitext(path)[0].replace('_list', '') + '_rank.json'
    json.dump({'source': path, 'n': n, 'top_k': k, 'view_cut': vt, 'rec_cut': rt, 'posts': posts},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'n={n} top{k}: 조회 >= {vt}, 추천 >= {rt}  -> {out}')
    print('| 순위 | 구분 | 조회 | 추천 | 댓글 | score | 제목 | no |')
    print('|---|---|---|---|---|---|---|---|')
    for p in posts:
        if p['tier']:
            print(f"| {p['rank']} | {p['tier']} | {p['views']} | {p['rec']} | {p['comments']} | {p['score']} | {p['title']} | {p['no']} |")


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.1)
