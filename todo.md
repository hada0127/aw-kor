# AW Korean Patch 통합 TODO

이 파일 하나가 현재 진행 기준이다. 완료=`docs/success.md`, 실패/dead-end=`docs/fail.md`,
RE 사실=`docs/research.md`. 막힘/완료 시 codex+agy 엄격 리뷰(`temp/review_prompt.md` → 병렬).
과거 완료(scene 에디터 Phase 0~8 등)는 success.md + git history.

---

# 🎯 /goal: codex·agy 적대적 엄격 검사에서 **잔존 결함 0**

> 사용자 지시(2026-06-24): 완료분 success.md 이전, 남은 작업 전부 정석으로 자율 진행.
> codex·agy 적대 검사 시 잔존 결함 없음이 목표. 쪼롱이/B팀 번역 불변.
> **추가 요구: 쪼롱이님이 웹에디터(:8782)로 모든 대사·스프라이트를 수정 가능해야 한다.**
> 비교 기준/근거: `docs/reports/COMPARISON_AND_GAP_CLOSE_2026-06-24.md`.

## A. 실화면 잔존 결함 0 (최우선 — codex+agy가 보는 화면). **codex·agy 공통: 아직 실잔존(미닫힘)**
> 2026-06-24 후반 codex·agy 적대 재리뷰: A1/A2/A3는 현재 캡처에 실제로 보이는 결함이며, stale-BG는
> **fresh-boot 재캡처로 입증 전 "오탐"으로 닫지 말 것**(savestate VRAM stale 가능성은 증거 아님).
- [x] **A1 CO 프로필 이름 OBJ 19개 한글 렌더 완료**(2026-06-24): OBJ는 96×8이 아니라 **48×16 col-major(8×16 글리프)**
  → 11px galmuri 직접 렌더(render_galmuri_8x16, ink=15). `patch_part2_domino_co_name_obj` 전면 교체:
  캐서린/도미노/맥스/호이프/빌리/키쿠치요/아스카/이글/모프/헬보우즈/콩/캣/스네이크/호크/하치/이반/한나/야마모토.
  전 19개 원본 압축 슬롯에 in-place fit. **ROM 디코드+렌더로 한글 검증**(temp/co_names_patched.png).
  ※ **인게임 시각 확증 완료(2026-06-24)**: `tools/capture_freshrender.py`(savestate 로드+refresh-nav로 ROM 재렌더)로
  CO 프로필 스크롤 시 이름박스 **맥스/도미노 한글 표시 확인**(stale 가타카나→한글). 증거 docs/screenshots/SUCCESS_A1_*.
- [x] **fresh-render 캡처 엔진**: savestate stale-BG 우회. A3(24/30f2 등) 확증에도 재사용 가능(매니페스트 확장).
- [ ] **A1b 대사 화자 이름박스 가타카나**(80c コシゲ 등): CO 프로필 OBJ(0x452xxx)와 **별도 메커니즘** — 미조사. 화자명 소스 RE 필요.
- [ ] **A2 맵 선택 섬 이름 '??'** (de-risked): 대사 3렌더러(313/B11/A3, 0x8840-0xE2A7→KOR_BASE)는 마/메 정상.
  맵선택=**4번째 미훅 렌더러**(fallback 0x8148). 정석: `/tmp/mgbah`로 8BC3/8BED read·0x8148 write PC trace →
  4번째 렌더러에 A3식 hook 또는 글리프뱅크 확장.
- [x] **A3 확증 완료(fresh-render)**: 결과 = **실제 잔존**(stale-BG 아님). 맵선택·CO선택 거친 fresh 렌더(증거
  A3_rule_labels_REAL_residual_*.png)에서도 룰 요약 라벨 **収入/日数/能力/アニメ/天気 일본어 유지**(하단 fog 도움말만 한글).
  codex가 옳았음(내 stale-BG 추정 철회). 부수: 동일 nav에서 A1 도미노(한글)·A2 소라??섬 재확인.
- [⏳] **A3-fix 룰 요약 라벨 한글화 (진행 중, OBJ 타일 위치 확인 단계)**: 24 campaign-map 룰 요약 라벨(日数/能力/天気/アニメ)은
  **baked OBJ 그래픽 확정**(출력 ROM 能力 SJIS=0인데 화면 표시 → dict 텍스트 아님). A1 이름OBJ·`patch_part2_status_header_labels`(종류/체력/연료/탄약)와 동류.
  fix 경로: 룰요약 OBJ 타일 오프셋 찾기 → 기존 `render_label`(Galmuri7, 16x8 OBJ타일)로 한글 렌더 주입.
  **타깃 한글(외부 AW2 디코드 확보)**: 제한 일수/지휘관 파워/날씨 설정/안개 설정/전투와 점령 표시 → `data/reference/gap_targets.json`.
  ※ 룰 SETTING 메뉴(0xB839AC)는 이미 번역됨(수입/날씨/사령브레이크). 미해결은 campaign-map 요약 HUD뿐.
- [x] **외부 패치 전체 번역 디코드(2026-06-24)**: `tools/decode_reference_patch.py`로 USA AW2 한글패치 복원+디코드(2940 문자열,
  미해독 0%). 폰트 0x810000/8x16 4bpp, code→glyph idx=(low)+(-0x90+(lead-0xc0)*122), galmuri glyph-match.
  `data/reference/aw2_korean_strings.json`(벤치마크) + `gap_targets.json`(우리 UI 갭 타깃). USA 미션/CO파워/진영/맵명은 기반게임差로 제외.
- [ ] **A4 영어 sprite UI**(PRESS A/ENEMY/R.MAP/SELECT/GALLERY/START): sprite editor로 한글/기호화(정책상 영어 0이면 결함).
- [ ] **A5 part1 단어붙음 117 + qa_integrity 부호소실 10행**: "띄어쓰기/누락 0" 목표 기준 잔여.
- [ ] **A6 0xA2C378/0xA2C484 폭>50 실화면 확인 + 0xA27AAD in-place stale**.

## B. 데이터 무결성
- [x] **B1 CSV 손상 ROM-진실 검증 완료**: `qa_csv_integrity.py`를 출하 ROM 디코드 기반으로 재작성.
  CSV 손상 239행이나 **출하 ROM 실제 일본어 텍스트 잔존 0**(빌드 inline 리터럴 권위; 109행 디코드 = 한글61/혼합26/노이즈22).
  `--fail-on-rom-japanese` 게이트 PASS + 배포 게이트 연동. (codex 보강 필요: 손상행 한정 40B 디코더 → 전수 디코더로 확장)
- [ ] **B2 CSV length-only 손상 239행 소스 위생 복구**(ROM 무해지만 정본 부채): 정수 length·꼬리잘림 복구.
- [ ] **B3 container residual scan 현재 SHA 재생성** → `audit_scene_residual_scans --strict` 현재 exit 1/critical 17
  (= scan SHA 스탬프 stale, 실 hit 0). breakpoint-scan 하네스 재실행 필요(부기).

## C. 웹에디터 전(全) 대사·스프라이트 편집 가능 (쪼롱이 요구)
- [x] **C1 대사 편집 커버리지**: 실대사(addr≥0x800000) 19650 중 **19450(99.0%) 편집가능**. 차단 200=전부 정당
  (font/컴팩트UI테이블/미션타이틀 pair). line_budget이 reason 노출.
- [x] **C2 스프라이트 커버리지**: 스프라이트 1979개 전부 scene/review 버킷으로 도달·편집 가능(font 1만 deny).
- [x] **C3 차단 사유 노출**: line_budget.reason + budget.bteam_warn으로 사유/경고 내려줌.
- [x] **C4 B팀 보호 게이트(3+층)**: ① 권위문 복원, ② `data/bteam_addresses.json`(3340)+`bteam_baseline.json`+`tools/qa_bteam_drift.py`(drift 0),
  ③ :8782·:8780 `_save_line` save-time 차단(confirm_bteam 필요), ④ `--accept`는 AW_BTEAM_ACCEPT=1, ⑤ verify_dist_integrity 게이트 연동.
- [ ] **C5 프런트(app.js) confirm_bteam 전송·bteam_warn 표시**(codex: 서버 게이트는 있으나 UI 미연결).
- [ ] **C6 8782 브라우저 전수 검증**: 모든 scene 대사·스프라이트 열림/저장 + B팀 confirm 흐름.

## D. 에디터/QA 폴리시 (Phase 6~8 잔여)
- [ ] D1 공통 `text_metrics.py` 추출 + py↔js 일치 테스트, 2350 미수록 음절 차단 일원화.
- [ ] D2 인게임 대사 박스 셀 폭 실측 → 줄당 최대 글자수(현재 fragment slot 총량 권위).
- [ ] D3 적용 직후 .gba SHA = output SHA 자동검증, dirty→"적용 필요" UX.
- [ ] D4 frame-sweep 캡처 엔진 + part1 welcome/battle dialogue canvas 신뢰성(현재 part2_menu만 ready).
- [ ] D5 lz77 실제 재압축 fit 검증, 빌드 skip 구조화 리포트.

## E. 백로그 (독립 트랙 — 결함 0 달성 후/병행)
- [ ] E1 전체 의미 audit(JA↔KO 전수 LLM 판정) — 오역·의미축소·뉘앙스.
- [ ] E2 fresh-boot 화면 매트릭스 확대(전투/결과/저장/상점/엔딩).
- [ ] E3 잔여 미번역 triage(제어마커/slot overflow/no group 자동제외분 수동검수).
- [ ] E4 표기흔들림 통일(국가명 붙임/띄움) + 구 apply_proper_nouns.py deprecate.
- [ ] E5 VRAM 팔레트 캡처(0x05000000/0x05000200) 스프라이트 실색.
- [ ] E6 CSV 권위 단일화(inline 리터럴 → overrides.tsv 분리).
- [ ] E7 캡처 지연 단축(슬롯 nav 단축 canvas + orig 캡처 영구 캐시).

## F. 하드웨어 (사용자/물리 필요)
- [ ] F1 실기(real GBA) 검증 — 플래시카트 부팅·주요화면. **자율 불가(하드웨어 필요)**.

---

## 완료 판정
- A·B·C 전부 닫고 `python3 tools/build_korean_full.py` 후 전 QA 게이트 PASS + scene 재캡처 critical 0
  + codex·agy 적대 재리뷰에서 신규 결함 0이면 /goal 달성. F1만 잔여로 사용자 통지.
