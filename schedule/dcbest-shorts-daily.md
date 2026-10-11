[매일 디시 실베 게시글 쇼츠 — 예약 실행]

1. 프로젝트 스킬 `dcbest-shorts-producer`(C:\Users\tkddy\OneDrive\바탕 화면\claude\쇼츠영상\.claude\skills\dcbest-shorts-producer\SKILL.md)를 `daily` 모드로 실행한다. 작업 폴더는 `C:\Users\tkddy\OneDrive\바탕 화면\claude\쇼츠영상`이다.
2. 스킬 문서, `config/dcbest.yaml`, `config/channels.yaml`을 먼저 읽고 규칙을 따른다. `SKILL.md`(방송 루틴), `SKILL2.md`, `archive/`는 쓰지 않는다.
3. 순서: 시작 정리(tts_pending 먼저, 남은 TTS 한도 확인) → 실베 100개 탐색 → 조회수·추천 상위 10% → 쇼츠 가능성 검증 → 하루 3편 제작(카드·TTS·BGM·렌더) → 자체 검수 → 업로드 정보(make_upload_info.py) → QA 통과 편은 바로 꿀잼잠에 공개 업로드 → 정리 → 마지막에 한 번만 보고.
4. 예약 실행이므로 중간에 확인을 묻지 않는다. 기준이 없으면 보수적인 쪽(사용 안 함, 건너뜀, "확인 필요")을 고른다. 한 편이 실패해도 나머지는 계속 만든다.
5. 디시는 로그인하지 않고 읽기만 한다. YouTube는 이미 로그인된 꿀잼잠 세션만 쓰고, 로그인이 풀려 있으면 업로드를 건너뛰고 보고한다. 비밀번호 입력 금지. API 키는 `config/secrets.local.json`에서만 읽고 출력·기록하지 않는다.
6. 보고는 한국어로 스킬 13단계 형식에 맞춰 쓰고 `output/dcbest/YYYY-MM-DD/summary.md`에도 저장한다.
