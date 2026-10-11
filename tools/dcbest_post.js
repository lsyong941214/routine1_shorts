// 디시 실시간 베스트 게시글 본문 수집 (브라우저 페이지 안에서 실행)
// 사용: 후보 글 URL을 연 뒤 이 파일 내용을 그대로 실행. 반환값을 output/YYYY-MM-DD/NN/post.json 으로 저장.
// 작성자 닉네임·IP는 수집하지 않는다(카드·대본·산출물 어디에도 쓰지 않음).
(() => {
  const num = s => parseInt(String(s || '').replace(/[^0-9]/g, ''), 10) || 0;
  const w = document.querySelector('.write_div');
  const head = document.querySelector('.gallview_head')?.innerText || '';
  const pick = re => num((head.match(re) || [])[1]);
  const drop = [/^- 관련게시물/, /^마우스 커서를 올리면/, /^이미지 순서를 ON\/OFF/, /^출처\s*:/];
  const body = (w?.innerText || '')
    .split('\n').map(s => s.trim())
    .filter(s => s && !drop.some(re => re.test(s)));
  const links = [...(w?.querySelectorAll('a[href]') || [])].map(a => a.href)
    .filter(h => !/dcinside\.com\/(list\.php|board)/.test(h));
  const title = document.querySelector('.title_subject')?.innerText.trim() || '';
  return {
    url: location.href.replace(/&(list_num|_dcbest|page)=[^&]*/g, ''),
    title,
    gallery_tag: (document.title.match(/^\[([^\]]+)\]/) || title.match(/^\[([^\]]+)\]/) || [])[1] || '',
    date: document.querySelector('.gall_date')?.title || document.querySelector('.gall_date')?.innerText || '',
    views: pick(/조회\s*([\d,]+)/),
    rec: pick(/추천\s*([\d,]+)/),
    comments: pick(/댓글\s*([\d,]+)/),
    body_lines: body,
    body_chars: body.join('').replace(/\s/g, '').length,
    images: w ? w.querySelectorAll('img').length : 0,
    videos: w ? w.querySelectorAll('video, iframe').length : 0,
    external_links: [...new Set(links)].slice(0, 10),
    comments_sample: [...document.querySelectorAll('.comment_box .usertxt')].map(e => e.innerText.trim()).filter(Boolean).slice(0, 40),
  };
})()
