// REPL 네트워크 도구 (2026-10-09 추가)
// PowerShell/Python 셸은 인터넷이 막힐 수 있다(DNS 실패: "알려진 호스트가 없습니다").
// 그때는 Aside REPL에서 이 파일을 불러 GIF 다운로드와 Gemini TTS를 실행한다. REPL의 fetch는 네트워크가 된다.
// 사용법 (REPL):
//   const NET = eval(await fs.readFile('C:\\Users\\tkddy\\OneDrive\\바탕 화면\\claude\\쇼츠영상\\tools\\repl_net.js', 'utf8'));
//   await NET.giphyFetch('https://giphy.com/gifs/slug-ID', 'assets/gifs/YYYY-MM-DD/NN/g1.gif', '@user', 'keyword');
//   await NET.ttsGemini('output/YYYY-MM-DD/NN/tts/jobs.json');   // tools/tts_gemini.ps1 와 같은 규칙(한도·사용량 기록), 반환 {code:0|3|1, msg}
// API 키 값은 출력하지 않는다.
(() => {
  const ROOT = 'C:\\Users\\tkddy\\OneDrive\\바탕 화면\\claude\\쇼츠영상';
  const abs = (p) => (/^[A-Za-z]:\\/.test(p) ? p : path.join(ROOT, p.replace(/\//g, '\\')));

  function giphyId(url) {
    let m = url.match(/giphy\.com\/media\/(?:v1\.[^/]+\/)?([A-Za-z0-9]+)\//);
    if (!m) m = url.match(/i\.giphy\.com\/(?:media\/)?([A-Za-z0-9]+)(?:\.gif|\/)/);
    if (!m) m = url.match(/giphy\.com\/(?:gifs|stickers)\/(?:[^/?#]*-)?([A-Za-z0-9]+)(?:[/?#]|$)/);
    if (!m) throw new Error('GIPHY ID를 찾지 못함: ' + url);
    return m[1];
  }

  async function giphyFetch(pageUrl, out, user = '', keyword = '') {
    const id = giphyId(pageUrl);
    const p = abs(out);
    await fs.mkdir(path.dirname(p), { recursive: true });
    const srcs = [`https://i.giphy.com/${id}.gif`, `https://media.giphy.com/media/${id}/giphy.gif`];
    let buf = null, used = null, lastErr = '';
    for (const src of srcs) {
      for (let t = 1; t <= 2 && !buf; t++) {
        try {
          const r = await fetch(src);
          const b = Buffer.from(await r.arrayBuffer());
          if (b.slice(0, 4).toString('ascii') !== 'GIF8') throw new Error('GIF 형식 아님 (' + r.status + ')');
          buf = b; used = src;
        } catch (e) { lastErr = e.message; await sleep(1500 * t); }
      }
      if (buf) break;
    }
    if (!buf) throw new Error('GIF 다운로드 실패: ' + id + ' ' + lastErr);
    await fs.writeFile(p, buf);
    const meta = { id, page_url: pageUrl, media_url: used, user, keyword, downloaded: new Date().toISOString(), bytes: buf.length };
    await fs.writeFile(p.replace(/\.gif$/i, '.json'), JSON.stringify(meta, null, 2));
    return `ok ${out} (${buf.length} bytes)`;
  }

  // Gemini 무료 한도는 미국 태평양 시간 자정에 초기화 -> 사용량 날짜 키도 태평양 시간
  function ptDate() {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  }

  function wav(pcm, rate) {
    const h = Buffer.alloc(44);
    h.write('RIFF', 0); h.writeInt32LE(36 + pcm.length, 4); h.write('WAVEfmt ', 8);
    h.writeInt32LE(16, 16); h.writeInt16LE(1, 20); h.writeInt16LE(1, 22); h.writeInt32LE(rate, 24);
    h.writeInt32LE(rate * 2, 28); h.writeInt16LE(2, 32); h.writeInt16LE(16, 34); h.write('data', 36); h.writeInt32LE(pcm.length, 40);
    return Buffer.concat([h, pcm]);
  }

  async function apiKey() {
    const s = JSON.parse((await fs.readFile(path.join(ROOT, 'config', 'secrets.local.json'), 'utf8')).replace(/^\uFEFF/, ''));
    if (!s.GEMINI_API_KEY) throw new Error('GEMINI_API_KEY 없음');
    return s.GEMINI_API_KEY;
  }

  async function ttsGemini(jobsPath) {
    const job = JSON.parse((await fs.readFile(abs(jobsPath), 'utf8')).replace(/^\uFEFF/, ''));
    const usagePath = path.join(ROOT, 'state', 'tts_usage.json');
    const today = ptDate();
    const limit = job.daily_limit ? +job.daily_limit : 10;
    const load = async () => {
      let u = {};
      try { u = JSON.parse((await fs.readFile(usagePath, 'utf8')).replace(/^\uFEFF/, '')); } catch (e) {}
      u[today] = u[today] || {}; u[today][job.model] = u[today][job.model] || { requests: 0, ok: 0, exhausted: false };
      return u;
    };
    const save = (u) => fs.writeFile(usagePath, JSON.stringify(u, null, 2));
    const key = await apiKey();
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${job.model}:generateContent`;
    const log = [];
    for (const it of job.items) {
      try { const st = await fs.stat(it.out); if (st.size > 1000) { log.push('skip ' + it.out); continue; } } catch (e) {}
      let ok = false;
      for (let t = 1; t <= 2 && !ok; t++) {
        const u = await load(); const mu = u[today][job.model];
        if (mu.exhausted || mu.requests >= limit) { await save(u); return { code: 3, msg: `quota ${job.model} ${mu.requests}/${limit}`, log }; }
        mu.requests++; await save(u);
        const body = { contents: [{ parts: [{ text: it.prompt }] }], generationConfig: { responseModalities: ['AUDIO'],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: job.voice } } } } };
        const r = await fetch(url, { method: 'POST', headers: { 'x-goog-api-key': key, 'Content-Type': 'application/json; charset=utf-8' }, body: JSON.stringify(body) });
        if (r.status === 429) { const u2 = await load(); u2[today][job.model].exhausted = true; await save(u2); return { code: 3, msg: `429 quota ${job.model}`, log }; }
        if (!r.ok) { log.push(`HTTP ${r.status} try ${t}: ` + (await r.text()).slice(0, 200)); await sleep(5000 * t); continue; }
        const j = await r.json();
        const part = (j.candidates?.[0]?.content?.parts || []).find((x) => x.inlineData);
        if (!part) { log.push('no audio try ' + t); continue; }
        const m = /rate=(\d+)/.exec(part.inlineData.mimeType || ''); const rate = m ? +m[1] : 24000;
        await fs.mkdir(path.dirname(it.out), { recursive: true });
        await fs.writeFile(it.out, wav(Buffer.from(part.inlineData.data, 'base64'), rate));
        const u3 = await load(); u3[today][job.model].ok++; await save(u3);
        log.push(`ok ${it.out} (${mu.requests}/${limit})`); ok = true;
      }
      if (!ok) return { code: 1, msg: 'TTS 실패', log };
    }
    return { code: 0, msg: 'done', log };
  }

  return { giphyFetch, ttsGemini, ptDate, ROOT };
})();
