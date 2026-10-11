// 디시 실시간 베스트 목록 수집 (브라우저 페이지 안에서 실행)
// 사용: https://gall.dcinside.com/board/lists?id=dcbest&list_num=100&page=1 을 연 뒤 이 파일 내용을 그대로 실행.
// 반환값(JSON 배열)을 sources/dcbest/YYYY-MM-DD_list.json 으로 저장 -> python tools/dcbest_rank.py 로 순위 계산.
(() => {
  const num = s => parseInt(String(s || '').replace(/[^0-9]/g, ''), 10);
  return [...document.querySelectorAll('tr.ub-content')]
    .filter(r => r.dataset.no && r.dataset.type !== 'icon_notice')
    .map(r => {
      const a = r.querySelector('.gall_tit a');
      const title = (a?.innerText || '').trim();
      const tag = (title.match(/^\[([^\]]+)\]/) || [])[1] || '';
      return {
        no: num(r.dataset.no),
        url: 'https://gall.dcinside.com/board/view/?id=dcbest&no=' + r.dataset.no,
        title,
        gallery_tag: tag,
        date: r.querySelector('.gall_date')?.title || '',
        views: num(r.querySelector('.gall_count')?.innerText),
        rec: num(r.querySelector('.gall_recommend')?.innerText),
        comments: num(r.querySelector('.reply_num')?.innerText) || 0,
      };
    })
    .filter(p => Number.isFinite(p.views) && Number.isFinite(p.rec));
})()
