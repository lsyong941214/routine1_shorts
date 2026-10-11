---
name: dcbest-shorts-producer
description: 디시인사이드 실시간 베스트(dcbest) 게시판을 100개씩 보기로 탐색해 조회수·추천 상위 10% 글을 고르고, 쇼츠로 만들 수 있는지 검증한 뒤 하루 3편의 9:16 쇼츠(Gemini AI 내레이션 + 게시글 카드 + GIPHY GIF + 운영자 BGM + 자막)를 만들어 자체 검수하고, 썸네일·제목·설명·해시태그·태그 등 업로드 정보를 만든 뒤 QA를 통과한 편은 꿀잼잠 채널에 바로 공개 업로드하고 보고한다. "실베 쇼츠 만들어", "디시 쇼츠 루틴 실행", "게시판 쇼츠 만들어" 같은 요청이나 예약 실행에 사용.
---

# 게시판 글 쇼츠 스킬 (실베 탐색 → 상위 10% → 검증 → 제작 → 검수 → 업로드 정보 → 즉시 공개 → 보고)

`story-shorts-producer`(방송 영상 재구성형)와 같은 제작 방식이며, **주제 선정만 디시 실시간 베스트 게시글**로 바꾼 루틴이다. 게시글에는 방송 장면이 없으므로, 방송 캡처 자리를 원문 문장을 옮긴 **게시글 카드**가 대신한다.

- 프로젝트 폴더: `C:\Users\tkddy\OneDrive\바탕 화면\claude\쇼츠영상`
- 먼저 이 문서, `config/dcbest.yaml`, `config/channels.yaml`(도구 경로·색·TTS 모델/음성·BGM `mood_map`·자막 기준)을 읽는다. `channels.yaml`의 `tts/bgm/subtitles/gif`의 `enabled: false`는 방송 구간 추출형 설정이므로 이 루틴에는 적용하지 않는다. `SKILL2.md`와 `archive/`는 읽거나 쓰지 않는다.
- 하루 **3편** (`dcbest.yaml`의 `shorts_per_day`). 산출물은 `output/dcbest/YYYY-MM-DD/NN/`(NN = 01~03).
- 도구: `tools/dcbest_list.js`, `tools/dcbest_post.js`(브라우저 페이지에서 실행), `tools/dcbest_rank.py`, `tools/make_post_cards.py`, `tools/make_upload_info.py`, 그리고 기존 `tools/tts_prepare.py`·`tts_gemini.ps1`(또는 `repl_net.js`)·`tts_split.py`·`render_short.py`·`qa_check.py`·`preview_sheet.py`·`giphy_fetch.ps1`·`bgm_analyze.py`.
- Python: `channels.yaml`의 `tools.python`. Python은 인터넷이 막혀 있으므로 네트워크(게시판 읽기, TTS, GIF)는 브라우저·PowerShell·REPL로 하고 파일은 프로젝트 폴더에 저장해 로컬에서 처리한다. PowerShell에 인터넷이 없으면 REPL에서 `tools/repl_net.js`(`NET.ttsGemini`, `NET.giphyFetch`)를 쓴다.
- 렌더·QA 임시 폴더 권한 오류가 나면 `$env:RENDER_STAGE`를 세션 tmp 아래 `stage`로 지정한다. 프로젝트 폴더(OneDrive·한글 경로)는 ffmpeg 임시 폴더로 쓰지 않는다.
- 계정: 디시는 로그인하지 않는다(읽기만, 추천·댓글·글쓰기 금지). 업로드는 브라우저에 이미 로그인된 YouTube Studio(꿀잼잠)만 쓴다. 비밀번호·토큰은 입력·기록하지 않는다. 로그인이 풀려 있으면 업로드를 건너뛰고 보고에 "YouTube 로그인 필요"라고 적는다. API 키는 `config/secrets.local.json`에서만 읽고 어디에도 출력하지 않는다.

## 0. 실행 모드
- `daily`(기본, 예약 실행): 시작 정리 → 1~2단계(탐색·순위·검증) → 편마다 3~10단계(제작·검수·업로드 정보) → **바로 11단계 업로드·즉시 공개** → 다음 편 → 12단계 정리 → 13단계 보고.
  - 예약 실행이므로 중간에 확인을 묻지 않는다. 기준이 없으면 보수적인 쪽(사용 안 함, 건너뜀, "확인 필요")을 고른다. 한 편이 실패해도 나머지는 계속 만든다.
- `draft`: 탐색·업로드 없이 `sources/dcbest_queue.yaml`의 `status: new` 글로 3~10단계만.
- `publish`: 오늘 `output/dcbest/YYYY-MM-DD/` 중 QA 통과했지만 `upload_log.json`에 없는 편만 11단계로 올린다.
- 시작 정리(모든 제작 모드):
  1. `sources/dcbest_queue.yaml`의 `status: tts_pending`(전날 TTS 한도로 못 만든 편)을 먼저 만들고, 그만큼 새 편 수를 줄인다.
  2. `state/tts_usage.json`(태평양 시간 날짜 키)에서 오늘 남은 Gemini 요청 수를 확인한다. **기존 쇼츠 루틴과 한도를 공유**하므로 남은 한도 안에서만 편 수를 정하고, 넘는 편은 대본·카드 작업을 시작하지 않는다.

## 공통 금지 사항
- 원글 작성자 닉네임·IP·프로필, 댓글 작성자 정보는 수집·표시·기록하지 않는다. 글 속 일반인의 실명·얼굴·연락처·학교·직장 등 신상은 쓰지 않는다.
- 게시글 본문 이미지·영상(타인 사진, 기사 사진, 방송·영화·만화 캡처)은 내려받거나 화면에 넣지 않는다. 화면은 게시글 카드(텍스트 재구성), GIPHY GIF, 숫자·인용 카드, 채널 엔딩 카드만 쓴다.
- 욕설은 카드·자막·내레이션에서 ○로 가리거나 뜻이 같은 순한 말로 바꾼다(인용 따옴표 안이면 ○ 가림만, 단어를 바꾸지 않음). 비하·혐오·조롱 표현이 있는 문장은 인용하지 않는다.
- 확인하지 못한 사실 주장은 단정하지 않는다. 개인 경험담은 "글쓴이에 따르면", "~했다고 해요"처럼 전달한다.
- 저작권 탐지를 피하기 위한 변형은 하지 않는다. AI 이미지 생성, 실존 인물 음성 흉내·합성은 하지 않는다.

## 노출 최적화 원칙
`story-shorts-producer`와 같다: 첫 1~3초 시청 유지(목표 70% 이상), 길이 35~45초(상한 60초), 제목·첫 화면이 약속한 내용이 영상에 실제로 나옴, 과장 금지, 반복성 회피(같은 날·직전 3편과 훅·구조·BGM·GIF·카드 테마를 겹치지 않게, 매 영상에 운영자 관점의 정리·질문 1개).

## 1. 게시판 탐색 (100개씩 보기)
1. 브라우저로 `https://gall.dcinside.com/board/lists?id=dcbest&list_num=100&page=1`을 연다(로그인·쿠키 동의는 필수 항목만).
2. 페이지에서 `tools/dcbest_list.js` 내용을 그대로 실행한다. 공지(`icon_notice`)·광고 줄은 스크립트가 뺀다. 반환된 JSON 배열(보통 100개, 약 24시간치)을 `sources/dcbest/YYYY-MM-DD_list.json`으로 저장한다. 100개 미만이면 `page=2`도 실행해 합친다.
3. 목록이 비거나 구조가 바뀌어 `views`/`rec`가 비면 페이지 텍스트로 다시 확인하고, 그래도 안 되면 "탐색 실패"로 보고하고 끝낸다.

## 2. 조회수·추천 상위 10% + 쇼츠 가능성 검증
### 2-1. 순위
- `python tools/dcbest_rank.py sources/dcbest/YYYY-MM-DD_list.json` → `*_rank.json`과 후보 표.
  - 상위 10% = 100개 중 10개. 조회수 10위 값 이상 = `view_top`, 추천 10위 값 이상 = `rec_top`.
  - `tier: both`(둘 다 상위 10%) = **1차 후보**. `tier: either`(score 상위 10% 안에서 한쪽만) = 1차 후보로 3편을 못 채울 때만 검증하는 보충 후보.
  - `state/dcbest_used.json`에 있는 글(`used`)은 제외된다. 직전 7일에 쓴 소재와 같은 이야기(같은 사건·같은 썰의 재게시)도 제외한다.
- 후보는 `score` 높은 순으로 검증한다(both 전체 → either).

### 2-2. 검증 (후보마다, 3편이 차면 중단)
글을 열고 `tools/dcbest_post.js`를 실행해 결과를 `sources/dcbest/posts/<no>.json`으로 저장한 뒤, 아래를 순서대로 본다. 하나라도 **불가**면 사유를 적고 다음 후보로.
1. **주제 제외(불가)**: 정치·선거(정당·정치인·국정감사·정치인 재판·이념 갈등), 지역·성별·세대·인종·종교·장애 비하나 갈등이 핵심, 성적·선정적 내용(제목·본문 암시 포함), 범죄·사고 피해자 특정이나 사망·부상 희화화, 미성년자 중심 갈등, 일반인 신상 노출, 연예인 외모 평가·사생활 루머, 의료·투자 단정 조언, 자해·자살.
2. **원저작물 의존(불가)**: 본문 절반 이상이 언론 기사 전재(외부 언론 링크 + 기사체), 방송·영화·웹툰·만화(`[카연]` 연재, `manhwa`) 장면이 핵심, 사진·움짤·영상 위주 글(제목 `.jpg/.gif/.mp4` 등이고 본문 텍스트 `body_chars` < 150), 게임·스포츠 하이라이트 영상. → 카드로 재구성하면 내용이 전달되지 않거나 권리가 따로 있다.
3. **이야기성(가능 조건)**: 본문(+대표 댓글 반응)에서 상황 → 전개(갈등·궁금증) → 반전·결론 3비트 이상을 뽑을 수 있고, 내레이션 220~300자를 원문 내용만으로 채울 수 있다. 본문 300자 이상 권장, 150~300자면 댓글 반응으로 보완 가능한 경우만.
4. **사실성**: 통계·사건·제도 같은 사실 주장이 핵심이면 공식 출처(정부·통계청·공공기관·원 보도)와 대조할 수 있어야 한다. 확인 안 되는 루머가 핵심이면 불가. 개인 썰은 "글쓴이에 따르면"으로 전달 가능하면 가능.
5. **공감도**: 전 연령이 이해할 수 있는 주제(직장·돈·연애·결혼·가족·일상·음식·동물·감동·황당·생활 정보) 우선. 특정 갤러리 내부 용어·밈 없이는 이해가 안 되면 보류.
6. **다른 커뮤니티 퍼온 글**(블라인드·에타·네이트판 등): 가능하나 설명란에 "원 출처: ○○(디시 실베 경유)"를 적고, 원 출처 작성자 정보도 쓰지 않는다.
- 판정: 가능 / 보류(사유) / 불가(사유). 가능한 글을 score 순으로 슬롯 01~03에 넣는다. 같은 날 3편은 서로 다른 주제 유형(썰·감동·황당·정보·연애 등)이 되게 하고, 같은 갤러리는 하루 최대 2편.
- 3편이 안 차면 있는 만큼만 만든다.
- 발굴 결과 표를 `sources/dcbest/discovery_YYYY-MM-DD.md`에 저장: 순위, tier, 글 번호·제목·갤러리, 조회, 추천, 댓글, score, 판정·사유, 슬롯.
- `sources/dcbest_queue.yaml`에 선정 글 추가: `no`, `url`, `title`, `gallery_tag`, `views`, `rec`, `comments`, `date`, `topic_type`, `slot`, `status: new`, `note`(한 줄 요약).

## 3. 원문 정리 (`source_notes.json`)
- `output/dcbest/YYYY-MM-DD/NN/post.json`(2-2 수집 결과 복사)과 `source_notes.json`: 원글 정보(url, 갤러리, 제목, 작성일, 조회·추천·댓글), 본문 요약, 핵심 문장 4~6개(원문 그대로, 각 40자 이내로 자름·뜻 보존), 대표 댓글 반응 2~4개(작성자 정보 없이), 훅 문장, 사실관계 메모(확인한 출처 또는 "글쓴이 주장"), 순화한 표현 목록.

## 4. 대본 (`script.json`, 전체 AI 내레이션)
- 길이 35~45초(최대 60초), 내레이션 220~300자(공백 제외), 한 문장 25자 이내, 문장마다 화면 1컷(2~4초).
- 구조:
  | 비트 | 시간 | 내용 |
  |---|---|---|
  | 오프닝(훅) | 0~2초 | 상단 제목 2줄을 그대로 읽는다. 하단 자막 없음. 인사·자기소개·"디시에 올라온 글인데" 같은 군말 금지 |
  | 상황 | 2~10초 | 누가, 어떤 상황에서, 무슨 일이 |
  | 전개 | 10~30초 | 핵심 2~3비트, 원문 문장 1~3개를 따옴표로 인용(각 15자 이내) |
  | 반전·결론 | 30~38초 | 글의 결말 또는 댓글 반응(가장 많이 공감받은 방향을 요약, 단정 금지) |
  | 엔딩 | 38~45초 | 한 줄 정리(20자 이내, 중립) / 시청자 질문 / "더 많은 이야기는 구독과 좋아요로 만나요."(고정, `"end": true`) |
- 인용: 따옴표 안은 원문과 글자 단위로 같게(욕설만 ○ 가림). 서로 다른 문장을 이어 붙이거나 부정·조건을 잘라 뜻을 바꾸지 않는다.
- 훅 유형·엔딩 정리·질문 표현은 `state/phrase_history.json`의 직전 3편과 겹치지 않게 고르고 기록한다.
- 영상 단위 키: `"narration": "tts"`(필수, TTS 강제), `"category": "community"`, `"topic_type"`, `"source": {"program": "디시 실베 [갤러리]", "url": ..., "no": ...}`, `"hook_title": [줄1, 줄2]`, `"title_keywords"`, `"palette": {"bg", "accent", "quote"}`(`channels.yaml` 색에서, 영상마다 변주), `"captures"`(5단계), `"thumbnail"`, `"bgm"`(7단계).
- 비트 키: `text`, `tts`(숫자·영문·은어를 한글 발음으로), `quote`, `visual`(카드 ID / `gif:assets/gifs/...` / `quote` / `card`), GIF 비트는 `gif_terms`·`gif_score`·`gif_reason`·`credit`, `emotion`, `keywords`, `zoom`("in"은 1~2컷만), `opening`/`end`.
- 형식 예시는 기존 루틴의 `script.json`(방송 캡처 대신 카드 ID)과 같다. `segment` 키는 넣지 않는다.

## 5. 화면 — 게시글 카드 (`tools/make_post_cards.py`)
- 비트마다 먼저 "이 문장을 보여줄 원문 문장·댓글이 있는가"를 보고 카드를 배정한다. 우선순위: ① 그 문장의 원문이 담긴 **본문 카드**(`body`, 해당 구절 `highlight`) ② 반응 문장은 **댓글 카드**(`comments`) ③ 숫자·관심도는 **통계 카드**(`stat`, `caption`) 또는 숫자 카드 ④ 위가 없고 대본의 대상·행동을 그대로 보여줄 수 있을 때만 **GIF**.
- 카드 종류: `title`(갤러리·제목·조회/추천/댓글), `body`(원문 2~6줄 + 강조 구절), `comments`(댓글 2~4개, 작성자 없음), `stat`(조회·추천·댓글 큰 숫자).
- 영상당 카드 **7~10장**, 카드 노출 합계 **60~75%**, GIF **1~3컷·25% 이하**, 나머지 숫자·인용 카드. 오프닝과 처음 10초는 카드만. 같은 카드를 두 비트 이상 쓰지 않는다(같은 문단이면 다른 줄·다른 강조로 새 카드).
- 테마는 영상마다 `light`/`dark`를 번갈아 쓰고(직전 편과 다르게), 카드 문장은 원문 그대로(욕설 ○ 가림)이며 요약·각색 문장을 원문처럼 넣지 않는다.
- `output/dcbest/YYYY-MM-DD/NN/cards.json`을 쓰고(`out_dir`: `assets/captures/dcbest/YYYY-MM-DD/NN`) `python tools/make_post_cards.py output/dcbest/YYYY-MM-DD/NN` → 출력된 `captures` 조각을 `script.json`의 `captures`에 넣는다. 출처 줄은 자동으로 "출처: 디시인사이드 실시간 베스트 [갤러리] 게시글".
- 카드 이미지는 `python tools/preview_sheet.py`나 직접 열어 글자 잘림·오탈자·○ 가림을 확인한다.
- **썸네일 = 오프닝 카드**: 비트 0의 `visual`은 훅 문장을 강조한 `body` 카드(또는 제목이 강한 글이면 `title` 카드)이고, `"thumbnail": {"capture": "P1", "reason": "..."}`를 적는다. GIF·숫자 카드·엔딩 카드는 썸네일이 될 수 없다(`render_short.py` 썸네일 가드가 막음). 그 카드는 다른 비트에서 다시 쓰지 않는다.

### GIF (보조 컷, GIPHY)
- `story-shorts-producer` 4-4와 같은 기준: 그 문장의 **대상·행동이 화면에 그대로 보이는** GIF만(연관성 2점 이상, 1점은 감정 문장 1컷만), 검색은 `https://giphy.com/search/<영어 검색어>` 상위 25개, 최대 4번 재검색, 없으면 카드로 대체. 다운로드는 `tools/giphy_fetch.ps1`(또는 `NET.giphyFetch`) → `assets/gifs/dcbest/YYYY-MM-DD/NN/gN.gif`. 출처 줄 "GIF: GIPHY @업로더".
- 폭력·선정·혐오, 글자가 내레이션과 어긋나는 것, 실제 사고 영상처럼 보이는 것, 연예인을 글 속 당사자처럼 보이게 하는 것은 쓰지 않는다. 같은 날·직전 3편과 같은 GIF 금지. `license_log.json`에 기록.

## 6. TTS (Gemini, 한도 안에서만)
1. `python tools/tts_prepare.py output/dcbest/YYYY-MM-DD/NN` (톤: `community` = 친구에게 썰을 풀듯 생생하고 리듬감 있는 톤)
2. `powershell -File tools/tts_gemini.ps1 -Jobs output/dcbest/YYYY-MM-DD/NN/tts/jobs.json` (PowerShell 인터넷이 막히면 REPL `await NET.ttsGemini(...)`). 종료 코드 3(한도)이면 예비 모델로 `tts_prepare.py <폴더> gemini-2.5-flash-preview-tts` 후 1회 재시도. 예비 모델도 한도면 그 편과 남은 편은 `status: tts_pending`으로 넘기고 멈춘다.
3. `python tools/tts_split.py output/dcbest/YYYY-MM-DD/NN`
- 영상 1편 = 요청 1회, 오류 재시도 1회까지. Windows TTS 등 다른 음성으로 대체하지 않는다. 45초를 넘으면 `tempo` 1.05~1.15.

## 7. BGM
- `소스/` 폴더의 mp3 1곡만(`channels.yaml`의 `bgm.mood_map`). 글의 분위기·핵심 비트 `emotion`으로 고르고, 같은 날·직전 3편과 겹치지 않게 한다. 슬픈 사연에 신나는 곡 금지.
- `"bgm": [{"file": "소스/파일명.mp3", "start_beat": 0, "align_beat": <핵심 비트>, "align_track_time": <bgm_index.json의 chorus_start>, "gain_db": 0}]` — 핵심 비트에 후렴이 오게. 내레이션 대비 -18dB 내외, 끝 1.2초 페이드아웃.

## 8. 렌더 (`tools/render_short.py`)
- `python tools/render_short.py output/dcbest/YYYY-MM-DD/NN` → `final.mp4`, `cover.jpg`(0프레임 = 오프닝 카드 + 상단 제목), `timeline.json`.
- 레이아웃·자막·오프닝·엔딩 카드 규칙은 렌더러 기본값(`story-shorts-producer` 5·6단계)과 같다: 상단 제목 2줄(흰 글씨 + 강조색), 중앙 패널 = 카드/GIF, 패널 아래 출처 줄, 자막 1~2줄(인용은 보조색), 마지막 비트는 채널 엔딩 카드 + "구독 + 좋아요".

## 9. 제목·설명·해시태그·태그·썸네일 (`meta.json` → `upload_info.md`)
- **제목**: 40자 이내, 앞 20자 안에 상황 키워드(인물 관계·쟁점·숫자). 후보 3개 → 내용 일치도·키워드 배치로 1개 선택(나머지 2개 기록). 따옴표 안은 원문 문장만. 허위·미확인 단정·비하·무관한 자극어("충격", "경악") 금지, 이모지 최대 1개, 해시태그 없음. "디시", "실베" 같은 출처 단어는 제목에 넣지 않는다.
- **설명란**(`youtube_description`, 해시태그 제외 본문):
  1. 첫 줄: 내용 한 문장 요약(검색 키워드 포함)
  2. 원글: "원글: 디시인사이드 실시간 베스트 [갤러리] <원글 URL>" (+ 퍼온 글이면 "원 출처: ○○")
  3. "게시글 내용을 요약·재구성했으며, 화면의 게시글 카드는 해설 목적의 인용입니다. 작성자 정보는 표시하지 않습니다."
  4. GIF 출처 목록("GIF: GIPHY @업로더"), 사실 주장 출처(있으면)
  5. "내레이션은 AI 음성(Google Gemini TTS)으로 만들었습니다."
- **해시태그**(`hashtags`) 3~5개: `#Shorts` + 주제 키워드 2~4개(예: `#직장썰` `#감동실화` `#생활꿀팁`). `#꿀잼잠`과 구독 문구는 도구가 붙인다.
- **태그**(`tags`) 5~15개: 주제어, 상황어, 유사 검색어. 갤러리 은어·비속어 금지.
- **릴스 캡션**(`reels_caption`): 첫 줄 질문형 훅 + 설명란 2~5번과 같은 출처·AI 안내 + 해시태그(#Shorts 제외).
- `source`: `{url, gallery, title}`.
- `python tools/make_upload_info.py output/dcbest/YYYY-MM-DD/NN` → 규칙 점검(제목 길이·해시태그 수·원글 URL·AI 안내) 후 `meta.json`에 최종 설명란 `upload_description`(구독 문구 + `#꿀잼잠` 포함)을 넣고, 붙여넣기용 `upload_info.md`(제목·후보·설명란·태그·썸네일 경로·릴스 캡션·업로드 설정)를 만든다. `FAIL`이 나오면 고치고 다시 실행한다.
- **썸네일**: `cover.jpg`(1080x1920, 2MB 미만) = 오프닝 카드 + 상단 제목. 핵심 글자는 중앙 1080x1080 안, 폭 200px로 줄여도 제목이 읽혀야 한다. 업로드 때 자동 썸네일을 쓰지 않고 이 파일을 직접 지정한다.

## 10. 자체 검수 (필수, 최대 3회 수정·재렌더)
`python tools/qa_check.py output/dcbest/YYYY-MM-DD/NN`(콘택트 시트 + 스트림·음량·커버 점검) 후 눈으로 확인한다. 실패가 남으면 `failed`로 표시하고 업로드하지 않는다.
- 내용: 인용 문장이 원문과 일치(욕설 ○ 가림만 허용), 사실 주장은 출처 대조 또는 "글쓴이에 따르면", 제목·커버가 약속한 장면이 앞 10초 안, 엔딩 3문장(고정 문장 정확히 일치), 직전 3편·같은 날 편과 훅·BGM·GIF·카드 테마가 겹치지 않음.
- 권리·안전: 작성자·댓글 작성자 정보 없음, 본문 이미지·영상 미사용, 일반인 신상 없음, 비하·혐오·선정 표현 없음, 정치 주제 아님, 모든 GIF가 `license_log.json`에 있고 점수 2 이상(1점은 감정 1컷).
- 화면·소리: `capture_ratio`(카드 노출) 0.60~0.75, 카드 7~10장, GIF ≤25%·1~3컷, `cover_from_capture: true`·`FAIL` 없음, 콘택트 시트 첫 칸이 카드(GIF·엔딩 아님), 길이 35~45초(최대 60초), 2~4초마다 화면 변화, 카드 글자 잘림 없음, 자막 1~2줄·폭 960px 안, 싱크 0.2초 이내, 1080x1920·30fps·H.264/AAC·-14 LUFS 내외.
- 업로드 정보: `make_upload_info.py`가 `OK`.
- 결과: `qa_report.md`(통과/실패 항목, 수정 내역, 최종 상태).

## 11. 업로드 (YouTube Studio 브라우저, 제작 즉시 공개)
`story-shorts-producer` 14단계와 같은 절차를 따른다. 요약:
1. **채널 확인**: `https://studio.youtube.com/` URL이 `/channel/UCIiJbXHPhK-5FFmfAvZ8PGQ`이고 채널 이름이 "꿀잼잠"인지 확인. 다른 채널이면 계정 전환. 개인 채널 "이상"(`UC0vBcEk1rPHebLvexkIkUNA`)에는 절대 올리지 않는다. 로그인 화면이면 멈추고 보고.
2. 파일 준비: `final.mp4`, `cover.jpg`를 현재 세션 tmp 폴더 아래 `upload/`에 `dcbest_YYYYMMDD_NN.mp4`, `dcbest_YYYYMMDD_NN_cover.jpg`로 복사(브라우저 파일 선택은 세션 폴더 파일만 받음). `timeline.json`의 `cover.source`가 `capture`인지 확인.
3. "동영상 업로드" → 파일 입력에 mp4 지정(브라우저 파일 업로드 도구 / `setInputFiles`).
4. 세부정보: 제목 = `meta.selected_title`, 설명 = `meta.upload_description`(그대로), 썸네일 파일 입력에 cover 지정(파일명 버튼으로 바뀌면 성공), "아니요, 아동용이 아닙니다", "자세히 보기" → 유료 프로모션 아니요 / "예, AI가 사용되었습니다." / 태그 `meta.tags`. 넘어가기 전에 모두 반영됐는지 확인.
5. 맞춤 썸네일이 막히면(미인증 하루 약 3개 한도) "동영상에서 선택"으로 **카드 프레임**을 고르고 `thumbnail: "frame"`. 후보가 GIF·엔딩뿐이면 비공개 저장 + `status: private`, `note: 썸네일 대기`.
6. "다음" 3번 → 저작권 검사에 문제가 있으면 비공개 저장 후 보고. 문제없으면 링크(`https://youtube.com/shorts/<id>`)를 읽고 "공개" → "게시" → 완료 창 확인. 실패 알림이 떠도 다시 누르기 전에 `/video/<id>/edit`에서 상태를 먼저 확인(중복 업로드 금지).
7. `upload_log.json`에 즉시 추가: `{date, nn: "dNN", routine: "dcbest", platform: "youtube", channel: "꿀잼잠", channel_id, video_id, url, title, status, published_at(+09:00), thumbnail, copyright_check, uploaded_at, note, source_url}`.
- 오류는 1회만 재시도, 실패하면 `status: failed`로 기록하고 다음 편 제작을 계속한다. 마지막 편 후 Studio 콘텐츠 목록에서 오늘 편들이 "공개"인지 한 번 더 확인한다.

## 12. 산출물·마무리
- `output/dcbest/YYYY-MM-DD/NN/`: `post.json`, `source_notes.json`, `cards.json`, `script.json`, `tts/`, `final.mp4`, `cover.jpg`, `timeline.json`, `contact_sheet.jpg`, `meta.json`, `upload_info.md`, `qa_report.md`
- `output/dcbest/YYYY-MM-DD/`: `license_log.json`(GIF·BGM), `summary.md`(편별 원글·제목·길이·카드 비율·GIF 수·QA·YouTube 링크·공개 시각)
- `sources/dcbest_queue.yaml` 사용 글을 `status: used`, `used_on`으로 바꾸고, `state/dcbest_used.json`의 `nos`에 글 번호, `topics`에 `{no, date, summary}`를 추가한다(7일 지난 항목은 정리). `state/phrase_history.json` 갱신.

## 13. 보고 (마지막에 한 번, 한국어)
- 탐색 요약: 수집 글 수, 조회·추천 상위 10% 기준값, both/either 후보 수, 검증 결과(가능/보류/불가 수와 대표 사유).
- 편별: 원글(갤러리·제목·조회·추천·score 순위), 선택 제목 + 후보 2개, 길이, 카드 수·노출 비율, GIF 수(연관성 점수), BGM, QA 결과, `upload_info.md` 경로, YouTube 링크·공개 시각·썸네일 적용(cover.jpg / frame / 대기).
- TTS 사용량(모델별 오늘 요청 수/한도), 한도로 미제작한 편.
- 실패: 단계(탐색 / 검증 / 카드 / TTS / 렌더 / QA / 업로드 정보 / 업로드)와 이유 한 줄씩.
- 마지막 줄: 수정 명령 "보류 d02"(비공개 전환) / "제목 d01-2"(제목을 2번 후보로) / "삭제 d03" — 처리 방법은 `story-shorts-producer`의 운영자 명령과 같고, `upload_log.json`에서 `routine: dcbest`인 항목을 찾는다.
- `output/dcbest/YYYY-MM-DD/summary.md`에도 같은 내용을 저장한다.
