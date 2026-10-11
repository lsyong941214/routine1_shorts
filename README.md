# routine1_shorts — 디시 실베 게시글 쇼츠 루틴

디시인사이드 실시간 베스트(100개씩 보기)에서 **조회수·추천 상위 10%** 글을 골라, 쇼츠로 만들 수 있는지 검증한 뒤
하루 3편의 9:16 쇼츠(Gemini AI 내레이션 + 게시글 카드 + GIPHY GIF + BGM + 자막)와 업로드 정보(썸네일·제목·설명·해시태그·태그)를 만들고
QA 통과 편을 YouTube 꿀잼잠 채널에 즉시 공개 업로드하는 Claude 스킬 루틴입니다.

## 구성
| 경로 | 역할 |
|---|---|
| `.claude/skills/dcbest-shorts-producer/SKILL.md` | 루틴 전체 절차 (탐색 → 상위 10% → 검증 → 제작 → 검수 → 업로드 정보 → 업로드 → 보고) |
| `config/dcbest.yaml` | 루틴 설정 (편수, 상위 비율, 출력 경로, 채널) |
| `tools/dcbest_list.js` | 실베 목록 페이지에서 실행 → 글 번호·제목·조회·추천·댓글 JSON |
| `tools/dcbest_post.js` | 게시글 페이지에서 실행 → 본문·통계·댓글 JSON (작성자 정보 수집 안 함) |
| `tools/dcbest_rank.py` | 조회·추천 상위 10% 계산, 1차(both)·보충(either) 후보 표 |
| `tools/make_post_cards.py` | 원문 문장으로 게시글 카드(1080x680) 생성 → `script.json` captures |
| `tools/make_upload_info.py` | `meta.json` 점검 + 최종 설명란 조립 + `upload_info.md` |
| `tools/render_short.py` 외 | 공용 렌더·TTS·QA 도구 (기존 쇼츠 루틴과 공유) |
| `schedule/dcbest-shorts-daily.md` | 매일 09:00 예약 작업 프롬프트 사본 |

## 저장소에 없는 것 (로컬 전용)
`config/channels.yaml`(공용 설정), `config/secrets.local.json`(Gemini API 키), `tools/ffmpeg-*`, `소스/`(BGM), 산출물(`output/`, `assets/captures/`, `assets/gifs/`), 상태(`state/`, `sources/`).

## 실행
- 수동: Claude Code에서 "실베 쇼츠 만들어" 또는 `/dcbest-shorts-producer`
- 자동: 예약 작업 `dcbest-shorts-daily` (매일 09:00)
