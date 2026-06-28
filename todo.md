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
- [x] **A1b 화자명 박스 — 해결(2026-06-24): 이미 A1 한글화 완료, コシゲ는 stale VRAM 오탐**. 이름창=OBJ LZ77 그래픽(테이블 0x81BE68, SWI 0x11 디코드), 19 distinct 슬롯 전부 A1이 한글화(캐서린~야마모토). state_21의 コシゲ는 구 ROM savestate VRAM 잔상 — 재렌더 시 '콩'(한글) 확증. docs/research.md 상세.
- [x] **A2 맵 선택 섬 이름 '??' 완료(2026-06-24, ASM hook)**: 근본원인 = watchaddr trace로 확정 — 맵선택 리스트
  렌더러(파서 0x0831Bxxx, glyph는 A3 hook 공유)가 **ASCII 공백 0x20을 소비 안 함** → 공백 뒤 1바이트 밀림으로
  [0x20,다음high]를 잘못된 코드로 읽어 fallback '?'. B팀 맵명("소라 마메 섬")이 12B 슬롯 fit 위해 전각(0x8140,2B)
  대신 반각(0x20,1B)을 써서 발생(슬롯 빠듯해 데이터로 0x8140 치환 불가 → 렌더러 수정 필수).
  **fix**: `PART2_HOOK_SPACE_A2CC`(0xF30400) — 루프top(0x831BCFC) 트램폴린. [r4]==0x20이면 0x8140(빈칸) 렌더 +
  r4=space-1(→+2후 space+1) → 0x831BD10 bl 복귀; 아니면 원본 4명령 재현 후 0x831BD04 복귀.
  **인게임 확증**: 소라 마메 섬·타마 타마 섬 공백 정상 빈칸 렌더, '?' 제거(docs/screenshots/SUCCESS_A2_*).
  **B팀 드리프트 0**(오버라이드 텍스트 불변, 인코딩/렌더만 수정).
- [x] **A3 확증 완료(fresh-render)**: 결과 = **실제 잔존**(stale-BG 아님). 맵선택·CO선택 거친 fresh 렌더(증거
  A3_rule_labels_REAL_residual_*.png)에서도 룰 요약 라벨 **収入/日数/能力/アニメ/天気 일본어 유지**(하단 fog 도움말만 한글).
  codex가 옳았음(내 stale-BG 추정 철회). 부수: 동일 nav에서 A1 도미노(한글)·A2 소라??섬 재확인.
- [x] **A3-fix 룰 요약 라벨 한글화 완료(2026-06-24)**: VRAM trace(dumpvram+OAM)로 룰 라벨 = **0x45D334~0x45D934 7개 32×16 OBJ**(raw, 0x100 간격) 발견.
  `patch_part2_campaign_rule_summary_labels`로 정찰/날씨/수입/일수/우세/능력/애니 렌더(render_galmuri_8x16, ink=15). **fresh-render 인게임 확증**
  (docs/screenshots/SUCCESS_A3_rule_labels_korean_*).
- [x] **A3 값 라벨 한글화 완료(2026-06-24)**: 8px 벽은 galmuri11 탓 — **Galmuri7(7px)**은 8px에 들어감(status header가 그 방식).
  VRAM/OAM trace로 값 풀 위치 확정(0x45DA34~0x45DC74): アリ→있음, ランダム→랜덤, ユキ→눈, ナシ→없음, ハレ→맑음, タイプA/B/C→타입A/B/C.
  `patch_part2_campaign_rule_value_labels`(Galmuri7, 8px 타일, ink=15, raw in-place). **fresh-render 인게임 확증**(라벨+값 전부 한글).
  증거 docs/screenshots/SUCCESS_A3_rule_labels_AND_values_korean_*. → **A3 완전 완료**.
- [~] **A3-old(진행중이던 설명)**: 24 campaign-map 룰 요약 라벨(日数/能力/天気/アニメ)은
  **baked OBJ 그래픽 확정**(출력 ROM 能力 SJIS=0인데 화면 표시 → dict 텍스트 아님). A1 이름OBJ·`patch_part2_status_header_labels`(종류/체력/연료/탄약)와 동류.
  fix 경로: 룰요약 OBJ 타일 오프셋 찾기 → 기존 `render_label`(Galmuri7, 16x8 OBJ타일)로 한글 렌더 주입.
  **타깃 한글(외부 AW2 디코드 확보)**: 제한 일수/지휘관 파워/날씨 설정/안개 설정/전투와 점령 표시 → `data/reference/gap_targets.json`.
  ※ 룰 SETTING 메뉴(0xB839AC)는 이미 번역됨(수입/날씨/사령브레이크). 미해결은 campaign-map 요약 HUD뿐.
- [x] **외부 패치 전체 번역 디코드(2026-06-24)**: `tools/decode_reference_patch.py`로 USA AW2 한글패치 복원+디코드(2940 문자열,
  미해독 0%). 폰트 0x810000/8x16 4bpp, code→glyph idx=(low)+(-0x90+(lead-0xc0)*122), galmuri glyph-match.
  `data/reference/aw2_korean_strings.json`(벤치마크) + `gap_targets.json`(우리 UI 갭 타깃). USA 미션/CO파워/진영/맵명은 기반게임差로 제외.
- [x] **A4 영어 sprite UI — 해결(2026-06-24): 표시 영문 전부 이미 한글화, GALLERY/R.MAP은 미존재(오독)**.
  실재 영문 = NEXT PHASE/PRESS A BUTTON(@0x391454)→'다음단계/결정키', COLOR(@0x391980)→'색상', TURN/SAKU 등 —
  전부 빌드 텍스트 import가 한글화 완료(2바이트 한글코드 디코드 확증). EXIT/NO/UNIT(@0x17/0x4ca)는 코드/압축/디버그
  포맷('UNIT C0 C1 PSQ(%1d)')=미표시. qa_ascii_residuals 큐레이션 잔존 0 + scene audit critical 0 교차확인.
- [x] **A5 단어붙음 — 정밀 재진단+추가해소(2026-06-24, codex P4 계기)**: qa_spacing 도구는 WRITE_LOG(in-place stale)를
  디코드 → **대량 오탐**. 렌더 기준 정밀분석: 524 jammed 중 **451 relocated(공백복원)·47 in-place공백보유** = 오탐,
  **진짜 jammed 26행**(96% 이미 해소). Part2 커맨드스트림(테이블 0xA357B4)은 이미 451행 repoint 완료.
  **추가 해소**: 진짜 26행 중 **단일 포인터(0x19 아닌 opcode 참조) 10행 발견 → extra_messages 추가로 +7행 공백 복원**
  (보급 수송차/하늘의 용사!/지혜의 고리 섬 등). repoint 362→369 lines.
  **잔여 ~19**: 0xE0xxxx 순차(포인터0)·decompose 실패 3·0xA2C484(폭51>박스50 WONTFIX) — fail.md의 다세션
  이벤트시스템 RE 필요분.
- [x] **A5b qa_spacing 도구 렌더 정확화 완료(2026-06-24)**: ① repoint 매니페스트로 relocated 메시지 제외(공백복원
  렌더), ② 비-relocated는 실 ROM 바이트 디코드(패딩 strip), ③ JAMMED는 같은번역 정확일치 공백제거만(다른/축약 제외).
  **jammed 433→159(진짜만), ABBREV 74→24**. codex P4 해소.
- [x] **A5c 단어붙음 대량 해소(2026-06-25): jam 102→19 (81% 감소)**. 5기법 결합(span_of terminator 세분화 + CSV-source 확장 + trusted_message_start 단일포인터 coverage + in-place-jam 강제재배치 + 비B팀 잼-override skip). repoint 369→448msgs/504lines, free 48KB(ROM 확장 불요). drift 0/integrity/scene critical 0/dist PASS. 잔여 19=구조한계(0x19 sub-start/무포인터/다중포인터/merged). docs/research.md 상세.
- [x] **A5d render-jam 멀티페이지 재조사(2026-06-25)**: `0xDFC248` 중간 spurious `0x00` 가설 반증(출하/재빌드 모두 `0xDFC430` 종단 1개). 실제 병목은 `skip_mid_ref`가 그래픽/압축 데이터의 pointer-shaped 값을 고아 포인터로 오인한 것. orphan 가드를 라인/메시지 entry-target 기준으로 정교화 + QA 동기화 → `0xDFC248/0xDFC3A1` 부모 메시지 재배치 성공, render-jam **792→718**, repoint 2860, integrity/repoint/B팀/phase6 PASS.

- [x] **A6 결론(2026-06-24)**: 0xA2C378/0xA2C484 = B팀 텍스트 un-jam 시 **51셀 > 박스 50셀** → repoint가
  **올바르게 skip**(공백복원 시 클리핑). 단어붙음(완전텍스트)이 클리핑보다 안전 → WONTFIX(텍스트 불변 원칙).
  0xA27AAD = ROM은 올바른 한글 대사('헬보우즈님... 호크 무슨 짓을...!') 렌더 — '헤,' override는 stale/무해, 실결함 0.
- [x] **A7 Part2 프롤로그/호크 대사 에뮬레이터 수동 확인(2026-06-27)**:
  `0xA019BB` leading space는 fresh route에서 `지금 침략자`로 분리되어 보였고, `0xA01A2C` 리포인트 흐름은
  최신 SHA `95bc2486…` 기준 route 캡처에서 진행 가능함을 확인했다. 단 `0xA01A5C/0xA01A70` 보고 문장은
  renderer가 `77 72` 제어 gap을 끼운 2조각을 같은 박스에 갱신하면서 `공격 준비`가 겹쳐 보이는 잔여가 있어
  E15에서 별도 해결했다. 최종 SHA `11098045…` 기준 A-only/focus/wait route 모두 정상 표시.


## B. 데이터 무결성
- [x] **B1 CSV 손상 ROM-진실 검증 완료**: `qa_csv_integrity.py`를 출하 ROM 디코드 기반으로 재작성.
  CSV 손상 239행이나 **출하 ROM 실제 일본어 텍스트 잔존 0**(빌드 inline 리터럴 권위; 109행 디코드 = 한글61/혼합26/노이즈22).
  `--fail-on-rom-japanese` 게이트 PASS + 배포 게이트 연동. (codex 보강 필요: 손상행 한정 40B 디코더 → 전수 디코더로 확장)
- [x] **B2 CSV 손상 239행 소스 위생 복구 완료(2026-06-27)**:
  단순 length-only가 아니라 행병합/필드밀림/주소 누출/일본어·한국어 필드 오염이었다.
  `game_wars_found_texts.csv`의 원문+length와 `temp/integrity_map.json`의 실제 출하 `ship_ko`를 우선 권위로 삼아
  `data/translation_for_import.csv`를 재구성했다. 결과: 손상 239→0, 234행 필드 복구,
  malformed artifact 5행(`0x00A23/0x00A2D/0x00A32/0x00D/0x00E0952`) 제거, 신규 행 0.
  전체 rebuild 후 full/final/title_test SHA는 `d96a7e13…`로 byte-identical 유지.
  `qa_csv_integrity.py --fail-on-rom-japanese`, `lint_translation.py --severity error`,
  `qa_text_fit.py`, `audit_scene_catalog.py --strict`, `verify_dist_integrity.py` PASS.
  agy 리뷰도 B2 완료 PASS, 후속 부채는 B4/E11/E14에 분리.
- [x] **B3 container residual scan 현재 SHA 재생성 + 감사 하드닝 완료(2026-06-26)**:
  `tools/reverify_scene_residual_scans.py` 추가. 기존 raw 가타카나 blanket-pass를 폐기하고
  `game_wars_found_texts.csv` 추출행 + `qa_japanese_residuals.py`의 covered/same-original 판정 재사용.
  raw kana는 별도 observation으로 남기며 설명 없는 항목은 `audit_scene_residual_scans.py --strict`가 critical 처리.
  현재 SHA `8a34a570…` 기준 15 container/2890 dialogue, residual/evidence case 16, hit 0, critical 0. `verify_dist_integrity.py`
  배포 게이트에도 연결. E8 시각 evidence까지 포함한 residual audit도 case 16/hit 0/critical 0.
  2026-06-27 현재 SHA `11098045…` 기준 16 container/3359 dialogue, case 17, hit 0, critical 0으로 재동기화.
- [x] **B4 CSV/스크립트 override 권위 shadow 감사 완료(2026-06-27)**:
  `tools/audit_csv_override_shadow.py --strict` 추가. CSV와 최종 출력이 다를 때
  `ADDRESS_TEXT_OVERRIDES`/`TEXT_OVERRIDES`/`SOURCE_TEXT_OVERRIDES`/`display_overrides.json`/
  `dialogue_overrides.json`/direct patch/repoint/write kind 중 설명 가능한 권위가 있는지 집계한다.
  현재 CSV 17,758행 중 shadow/explained 11,595행, **unexplained output shadow 0**,
  model/actual divergence 95건은 후단 fixed/direct writer 정보성 차이로 리포트에 보존.
  `verify_dist_integrity.py` 배포 게이트에 `CSV override shadow --strict`를 연결했고 전체 dist gate PASS.
  Claude/agy B4 리뷰 재시도는 CLI timeout/비리뷰 출력으로 실질 결과 없음.

## C. 웹에디터 전(全) 대사·스프라이트 편집 가능 (쪼롱이 요구)
- [x] **C1 대사 편집 커버리지**: 실대사(addr≥0x800000) 19650 중 **19450(99.0%) 편집가능**. 차단 200=전부 정당
  (font/컴팩트UI테이블/미션타이틀 pair). line_budget이 reason 노출.
- [x] **C2 스프라이트 커버리지**: 스프라이트 1979개 전부 scene/review 버킷으로 도달·편집 가능(font 1만 deny).
- [x] **C3 차단 사유 노출**: line_budget.reason + budget.bteam_warn으로 사유/경고 내려줌.
- [x] **C4 B팀 보호 게이트(3+층)**: ① 권위문 복원, ② `data/bteam_addresses.json`(3340)+`bteam_baseline.json`+`tools/qa_bteam_drift.py`(drift 0),
  ③ :8782·:8780 `_save_line` save-time 차단(confirm_bteam 필요), ④ `--accept`는 AW_BTEAM_ACCEPT=1, ⑤ verify_dist_integrity 게이트 연동.
- [x] **C5 프런트(app.js) confirm_bteam 전송·bteam_warn 표시 완료(2026-06-26)**:
  모든 조각을 `dry_run`으로 서버 `encode_fit` 기준 사전검증한 뒤 실제 저장을 시작한다.
  B팀 변경은 dry-run 단계에서 confirm을 받고, 승인 시 `confirm_bteam:true`로 저장. 취소/초과/미수록은 저장 시작 전 반환.
- [x] **C6 8782 브라우저/저장 게이트 전수 검증 완료(2026-06-26)**:
  현재 SHA `19a2ea71…`에서 Chrome CDP 63 scene/107 sprite 열람 failure 0. `tools/verify_scene_editor_roundtrip.py`로
  :8782 라이브 API 기준 80 scene/10,336 dialogue group/1,990 sprite/17,975 editable member dry-run failure 0,
  B팀 2,805 member confirm dry-run failure 0/skip 0. 대표 실제 저장/원복 2건(일반 0x00DFA5E6, B팀 0x00DFA616)
  성공. direct script 확장-span 대표 0x00D8FD26는 실제 저장→임시 ROM 빌드→build slot 44 < direct slot 52 조건에서 span 바이트 대조 성공. 테스트 후 편집 파일은
  실행 전 해시로 원복.
  2026-06-27 현재 SHA `11098045…`에서 재검증: Chrome CDP 63 scene/107 sprite failure 0,
  `verify_scene_editor_apply_state.py` OK, `verify_scene_editor_roundtrip.py`는 81 scene/10,859 dialogue group/1,990 sprite/
  18,668 editable member dry-run failure 0, B팀 3,150 member confirm failure 0/skip 0, 실제 저장/복원 2건 및 direct script
  확장-span 빌드 샘플 PASS.

## D. 에디터/QA 폴리시 (Phase 6~8 잔여)
- [x] D1 공통 `text_metrics.py` 추출 + py↔js 일치 테스트, 2350 미수록 음절 차단 일원화 완료(2026-06-26).
  `text_metrics.syllable_set()`/`unmapped_syllables()`/`has_unmapped_syllables()`를 추가하고,
  `qa_text_fit.py`, `lint_translation.py`, `scene_editor/server.py`, `verify_scene_editor_roundtrip.py`가 공통
  `encoded_len`/2350 음절 권위를 쓰도록 전환했다. `lint_translation.py`는 빌드의 `encode_fit`/direct script span/
  dialogue override overlay를 반영하며, B팀 baseline byte-budget은 `qa_bteam_drift.py`/repoint 게이트로 위임한다.
  검증: `tools/test_text_metrics.py` py↔js 25,296 코퍼스 PASS, `lint_translation.py --severity error` 0건.
- [x] D2 인게임 대사 박스 셀 폭 실측 → 줄당 최대 글자수(현재 fragment slot 총량 권위).
  - [x] 2026-06-26: `tools/qa_pixel_width.py` 정적 근사 범위를 빌드 입력원에 맞춰 확장.
    `dialogue_overrides`/직접 패치 텍스트/
    `ADDRESS_TEXT_OVERRIDES`/`SOURCE_TEXT_OVERRIDES`/`translation_comprehensive.csv` fallback/`encode_fit(addr)`/
    DENY/placeholder를 반영하고, 최종 encoded half-cell 폭 + scene 힌트를 출력한다.
    현재 `qa_text_fit.py` overflow 0, `qa_pixel_width.py` 기준 story/dialogue 계열의 `>50` 행은 관측되지 않았다.
  - [x] 남은 `final encoded cells > 50` 후보는 대사문이 아니라 메뉴/공통 UI 테이블 계열임을 닫았다.
    현재 `temp/dialogue_box_width_over_max.tsv` 후보 9개:
    (`0x804FD4`, `0x805B04`,
    `0xD83278`, `0xD83138`, `0x94298C`, `0x97AE40`, `0x9B36E4`, `0x9EBF88`, `0xEFAAD4`),
    모두 scene fresh capture/보조 캡처에서 항목 단위로 쪼개져 표시되는 UI 테이블로 확인했다.
    - [x] 2026-06-26 재캡처 1차: `0x804FD4/0x805B04` 및 동일 테이블 계열 `0xD83278` 공통 compact 메뉴,
      `0xD83138` Part1 정보 화면, `0x94298C/0x97AE40/0x9B36E4/0x9EBF88` 공통 START 메뉴,
      `0xEFAAD4` 전투 시스템 메뉴는 현재 캡처에서 항목 단위로 쪼개져 표시되어 한 줄 50셀 초과 클리핑은 관측되지 않음.
      증거: `docs/screenshots/d2_width_candidates_2026-06-26/`.
    - [x] `0xD721B5`는 실제 UI 문장이 아니라 문장부호/폭 테이블성 데이터로 판정해 DENY 추가.
      출력 ROM `0xD721B5..0xD7222F`는 원본과 byte-identical 복구됐고, `qa_pixel_width.py` 후보에서 제거됨.
    - [x] 2026-06-26 추가 해결: 맵 디자인 도움말 `플레이 조건` 화면에서 숫자/쉼표가 `????`로 깨지는 실제 화면을
      재현하고 수정했다. 원인은 compact 도움말 renderer가 본문 ASCII 숫자/구분자에서 2바이트 소비 정렬을 잃는
      경로였고, `dialogue_overrides.json` 최종 overlay가 `display_overrides`를 다시 덮는 빌드 순서 문제도 있었다.
      `data/display_overrides.json`에 `0x00A2C720..0x00A2C868` 및 `0x00D82134..0x00D822AC` 화면 전용 안전문을 추가하고,
      최종 dialogue overlay 안에서도 display override가 우선되도록 `tools/build_korean_full.py`를 보강했다.
      D2 정적 후보였던 `0xD81C24` 직접 도움말 행은 42셀 요약
      `조건수도둘이상각군병종거점필요대전통신가능`으로 줄여 `qa_pixel_width.py` `>50` 후보에서 제거했다.
      최종 SHA `7bf452715d5dc9da63b58cb45eb4e23e45e785b5cb699714760a23411455a680`에서 fresh route 캡처
      `docs/screenshots/d2_map_design_help_fix_2026-06-26/fresh_route_contact.png`와
      `fresh_play_condition_help.png`에 물음표/클리핑 없음. 보조 cross-state D821 캡처도
      `cross_state_d821_contact.png`에 보존.
    - [x] 2026-06-27 추가 종결: `0xA3B880/0xB842E8`은 CO 파워명 화면 문자열이 아니라
      compact CO 파워명 렌더러용 2바이트 글리프 사전이다. `0x08380564`는 입력 문자열의 각 2바이트 코드를
      `0x08A3B880` 사전에서 찾아 타일 인덱스로 변환하고, `0x08B3C184` 계열도 `0x08B842E8` 사전을
      사용해 타일 복사를 수행한다. 따라서 이어붙은 `하이퍼리페어...` 값은 한 줄 출력 후보가 아니며,
      `tools/build_korean_full.py::GLYPH_DICTIONARY_TEXT_ADDRS`로 분리했다. `qa_pixel_width.py --top 40` 기준
      `final encoded cells > 50` 후보는 11->9로 감소했고, `data/dialogue_map.json`에는 `is_noise=true` 감사 행으로만
      남기며 `data/dialogue_groups.json`/`data/scene_catalog.json`에서는 제외했다.
    - [x] 2026-06-27 codex/agy 리뷰 후 보강: `0xA3B880` 사전에 ASCII `_`가 1바이트로 들어가던 정렬 결함을 제거하고,
      A3/B842 사전 모두 실제 compact 표시문 unique glyph set으로 재작성했다. `data/display_overrides.json`에
      A2/B84 CO 파워명 compact 표시용 짧은 명칭을 추가해 사전 coverage와 화면 표시 바이트를 맞췄고,
      `tools/qa_glyph_dictionary_tables.py`를 신규 하드게이트로 추가했다. 이 게이트는 사전 payload뿐 아니라
      대상 36개/11개 count, dialogue_map 노출, output ROM 바이트, 전체 슬롯 0 패딩(0x20 잔존 금지)까지 검사한다.
      또한 agy/codex 리뷰 지적에 따라 `0xB81800..0xB85000` B8 실제 표시문 459개가 `region=font`라는 이유로
      UI 에디터 catalog에서 빠지던 문제를 `23d_part2_b8_compact_display_tables` container scene으로 배정해 닫았다.
      `build_dialogue_map.py`의 짧은 CJK 라벨 노이즈 휴리스틱도 보강해 `거점수입` 같은 실제 UI 라벨이 누락되지 않게 했다.
      2026-06-27 후속 E13 보강으로 compact glyph dictionary는 `data/display_overrides.json`에서 빌드 시 자동 산출된다.
      현재 최종 output/dist SHA는
      `d1cebfde9764606dcc3b7b3017fcfc8c2cc0faf30afa4e69568b604f5ae12854`이며 `verify_dist_integrity.py`가
      CO glyph dictionary coverage/text fit/visual region/sprite override fit 게이트까지 포함해 PASS.
- [x] D3 적용 직후 .gba SHA = output SHA 자동검증, dirty→"적용 필요" UX 완료(2026-06-26).
  :8782 `/api/state`가 output full/final/title_test SHA 동기성을 `output_sync`로 노출하고, `/api/build` 완료 직후
  SHA 불일치 또는 freshness threshold 이전 산출물이면 fail 처리한다. dirty 판정은 ns mtime 기준 `apply_needed`로 내려가며 프런트 상단은 `적용됨`/`적용 필요`와
  `output SHA 검증`을 표시. `tools/verify_scene_editor_apply_state.py`가 clean→mtime dirty→restore 상태를
  비파괴 검증하고, `tools/verify_scene_editor_cdp.py`로 상단 DOM + Chrome CDP 63 scene/107 sprite failure 0 UI 회귀도 확인.
  CDP 리포트는 scene별 중간 저장으로 내구화.
- [x] D4 frame-sweep 캡처 엔진 + part1 welcome/battle dialogue canvas 신뢰성 완료(2026-06-26, part1_welcome/part2_menu/89a surrender/89b defeat ready).
  - 2026-06-26 부분 완료: `tools/preview_capture.py`에 frame-sweep 선택(`sweep.frames`/`score_box`)과
    NUL 없는 command-stream span 패치(`terminator:none`, `pad`) 지원 추가. `part1_welcome` canvas는 실제 표시
    복사본 `0x00A7AA56` 37B span + frame 108/120/132/144 sweep으로 승격했고,
    `tools/verify_preview_canvases.py`가 active canvas 2개(part1_welcome, part2_menu)에 대해 서로 다른 payload가
    실제 캡처 픽셀을 바꾸는지 검증한다.
  - 2026-06-26 재검증: 현재 repoint SHA `7e79670c…`에서 이전 `0x00A7AB56`은 뒤쪽 안내문으로 밀려 payload diff 0이 됨.
    ROM prefix 디코드로 welcome runtime span을 `0x00A7AA56..0x00A7AA7A`로 재확정했고,
    `preview_capture.py`는 `temp/repoint_manifest.json`의 `0xDF8E14 -> new_addr`, fixed `0xDF8E16` delta로 slot을 자동 계산
    (fallback `0x00A7AA56`)하도록 보강했다.
    `verify_preview_canvases.py` 결과 failure 0(`part1_welcome` diff 314px, `part2_menu` diff 7383px).
  - 2026-06-26 추가 조사: `31_battle_dialog` 캡처는 이름과 달리 대사창이 아닌 전투/정보 UI 화면이며 provenance도
    구 SHA stale라 battle dialogue canvas 근거로 사용 금지. `89a_common_battle_surrender_confirm`,
    `89b_common_battle_defeat_comm_messages`는 실제 대사 화면이지만 최종 savestate를 slot hijack하면 payload diff 0
    (이미 렌더된 VRAM). `89b` 직전 후보 `state_000_before_a`도 현 하네스 단독 replay에서는 같은 중간 메시지로
    재진입하지 못한다고 판단했으나, 실제 해소 조건은 아래처럼 최종 표시 state가 아니라 직전 state에서 A 입력으로
    대사창을 다시 생성하는 방식이었다.
  - 2026-06-26 추가 완료: `89a` 항복 확인은 최종 표시 state가 아니라
    `part2_3p_surrender_defeat_probe_v4/state_008_sub_down_to_surrender.ss0`에서 A 입력으로 대사창을 재생성해야
    payload diff가 난다. 후보 pair scan 결과 실제 소스는 공통 `0xEFDAA0/0xEFDAC1`이 아니라
    Part2 복제본 `0xA34CB0/0xA34CD1`(`A34CB0` diff 614px, 다른 후보 diff 0). `battle_surrender_confirm`
    canvas를 `0xA34CB0` 32B span + `terminator:none`/space pad + frame-sweep으로 승격했고,
    active canvas 3개 failure 0(`battle_surrender_confirm` diff 302px). UI 에디터는 실제 89a scene에
    `g_00A34CB0`만 preview-ready로 노출하고, `g_00EFDAA0/g_00EFDAC1` 공통 복제본은 별도 container
    `89a_common_battle_surrender_confirm_common_copies`로 분리해 false preview를 막는다.
  - 2026-06-26 추가 완료: `89b` 패배 메시지는
    `part2_3p_surrender_defeat_probe_v4/state_010_confirm_left_yes.ss0`에서 A 입력으로 재생성해야 payload diff가 난다.
    실제 런타임 소스는 공통 `0xEFD8A4` 계열이 아니라 Part2 복제본 `0xA34D18`이며,
    `battle_defeat_message` canvas를 `0xA34D18` 32B span + `terminator:none`/space pad + frame-sweep으로 승격했다.
    `state_011_confirm_yes.ss0`는 이미 렌더된 뒤라 diff 0인 실패 state로 기록. active canvas 4개 failure 0
    (`battle_defeat_message` diff 302px), UI 에디터 89b scene은 실제 Part2 패배 메시지 5개만 preview-ready로 노출하고
    공통/통신오류 복제본은 `89b_common_battle_defeat_comm_messages_common_copies` container로 분리했다.
- [x] D5 lz77 실제 재압축 fit 검증, 빌드 skip 구조화 리포트 완료(2026-06-26).
  `build_korean_full.py`가 `data/sprites_overrides.json` 적용 시 `temp/sprite_override_report.json`에
  override SHA/records/applied/skipped/ignored와 LZ77 `compressed_size <= comp_size` 결과를 남긴다.
  `tools/audit_sprite_override_report.py --strict`와 `verify_dist_integrity.py`의 `sprite override fit` 게이트가
  non-empty override의 stale report, 재압축 초과, size mismatch, skip을 critical로 막는다. 현재 override 0건,
  report ok/skipped 0, output 3종 SHA `8a34a570…` 유지.
  추가로 claude/agy 리뷰 지적 반영: `문자 깨짐`/`[문자 깨짐]`/`해독·번역·판독 불가(문자 깨짐)` sentinel은
  `PLACEHOLDER_KO` skip으로 원본 보존. 고주소 sentinel 8행(0x009411A5..0x009EB69E)은 원본==출력 바이트로 확인.

## E. 백로그 (독립 트랙 — 결함 0 달성 후/병행)
- [ ] E1 전체 의미 audit(JA↔KO 전수 LLM 판정) — 오역·의미축소·뉘앙스.
- [ ] E2 fresh-boot 화면 매트릭스 확대(전투/결과/저장/상점/엔딩).
  - [x] 2026-06-26 해결: 사용자 mGBA 추가 스크린샷에서 Part1 모드 선택/대전/통신 하위 메뉴의
    대형 OBJ 라벨이 하단 반투명 도움말 위에서 과도하게 겹치는 실제 결함을 확인했다.
    원본도 라벨이 도움말 뒤를 지나가는 구조라 겹침 0이 기준은 아니며, 한글 패치의 굵은 외곽선/대형 획이
    도움말 문장보다 강하게 보이는 것이 결함이었다. `tools/build_title_hangul.py`의 Part1 option label을
    Galmuri11-Bold 12px 이하 본문-only compact 자산으로 바꾸고, 리뷰 반영으로 `1카드 통신`/`멀티카드 통신`
    원 표기는 보존했다.
    mGBA fresh route 7장 재캡처 결과 하단 설명문 가독성 회복. 최종 SHA `8a34a570…`에서 QA/배포 게이트 PASS. 증거:
    `docs/screenshots/part1_menu_label_shrink_2026-06-26/fresh_final_routes_contact.png`,
    `docs/screenshots/part1_menu_label_shrink_2026-06-26/fresh_final_filmstrip.png`.
    구 `final_menu.ss0` 계열에서 보이던 single/link 하단 노이즈는 stale savestate VRAM/text cache로, coldboot fresh route에서는 재현되지 않았다.
  - [x] 2026-06-26 추가 스크린샷 triage: 같은 contact의 `single_map` 화면에 보이는 `??????` 3행은
    한글 fallback/깨짐이 아니라 원본 `？` placeholder 데이터다(잠금/unknown 맵명으로 추정). read-watch 결과 `0x08DF8C2A` 12B가
    맵 리스트 렌더 중 144회 읽혔고, 원본/패치 모두 `8148`×6으로 byte-identical이다.
    4x crop에서도 물음표 글리프 겹침/타일 깨짐은 보이지 않는다. 증거 `data/part1_single_map_question_watch_20260626.json`.
  - [x] 2026-06-27 사용자 체감 UX 후속 수정: 위 판정은 원인 분석으로는 맞지만 실제 화면상
    `??????`가 깨진 문장처럼 보이므로 Part1 single-map unknown/locked 맵명을 `미공개`로 표시하도록 교체했다.
    이 리스트 renderer에서는 일반 예약 한글 코드(`미공개`)와 compact kanji 우회(`基工開`)가 blank로 렌더되어 실패했고,
    전역 `ガ/ギ/グ` glyph-table remap은 다른 가나 표시와 `ヒ/フ/ヘ` 슬롯 충돌 위험이 있어 폐기했다.
    최종 구현은 원본 `0x00DF8C2A`의 앞 3글자를 `8148`로 유지하고 뒤 3글자를 전각공백
    (`814881488148814081408140`)으로 blank 처리한 뒤, `0x08B1319C -> 0x08F30600` 국소 compact-renderer hook이
    source pointer `0x08DF8C2A/2C/2E`에만 `미/공/개` 전용 타일(`0x3E0/0x3E2/0x3E4`)을 VRAM에 복사한다.
    fresh mGBA evidence는 `docs/screenshots/part1_single_map_unknown_label_fix_2026-06-27/contact.png`,
    crop/report는 같은 디렉터리에 보존했다. 최종 output/dist SHA
    `fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093` 기준
    `verify_dist_integrity.py`와
    `run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_single_map_unknown_label_safe_hook.json` PASS.
  - [x] 2026-06-26 추가 수정: Part2 모드 메뉴 `상점` 도움말 `0x00A2C1B8`에서 fresh emulator 화면상
    `획득한 포인트????????` 및 우측 잘림이 재현됐다. B팀 권위문은 변경하지 않고 `data/display_overrides.json`에
    화면 전용 문구 `포인트로 쇼핑을 할 수 있습니다`를 분리해 적용했다. `dialogue_map`/`dialogue_groups`/정적 QA/audit도
    이 표시 계층을 반영한다. 증거:
    `docs/screenshots/part2_shop_help_fix_2026-06-26/fresh_shop_help.png`,
    `docs/screenshots/part2_shop_help_fix_2026-06-26/fresh_shop_help_bottom_zoom.png`.
  - [x] 2026-06-26 QA route 보정: `qa_visual_regions.py`의 Part1 fresh route가 이름 입력 뒤 A 17회로
    작전룸 내부에 들어간 상태를 `single/link`로 오판하던 것을 A 16회 모드 선택 기준점으로 수정했다.
    현재 SHA `19a2ea71…`에서 `visual_region_checks=39` PASS.
  - [x] 2026-06-27 사용자 추가 다운로드 스크린샷 triage: 7장 contact를
    `docs/screenshots/user_report_triage_2026-06-27/download_contact.png`로 보존했다. Part1 메뉴/통신 라벨 겹침은
    기존 compact OBJ 수정 후 현재 fresh route에서 재현되지 않고, `single_map`의 `??????`는 원본 `？` placeholder로
    유지되는 항목임을 재확인했다. 실제 신규 결함은 Part2 프롤로그 보고문 중복 표시였고 E15에서 수정 완료.
  - [x] 2026-06-27 사용자 추가 스크린샷 후속 수정: Part1 작전실/작전 메뉴에서 미션명이
    `전선 기지를 확보하라`, `적 부대를 해치워라`, `전투 개싸`, `지상 최강????`처럼 긴 문장·구두점·legacy repoint
    free-space 문자열로 표시되는 실제 결함을 fresh emulator route에서 재현했다. `0xB81D80..0xB82018` 작전명
    행을 compact title로 정리하고, `tools/build_korean_full.py`의 `_rp_dlg()`가 `dialogue_overrides.json`보다
    `ADDRESS_TEXT_OVERRIDES`/display override를 먼저 쓰도록 수정해 `0xB81FC4/0xB81FF4`의 stale free-space
    복사본을 제거했다. 당시 E9 모드 도움말 `0xDFA6AA/0xDFA6CD`도 `전투법알려줄게`/`와서들어봐`로
    1차 정리했고, 후속 Part1 도움말 공백 복원에서 `전투 방법 알려 줄게`/`와서 들어 봐`로 다시 개선했다.
    증거: `docs/screenshots/part1_operation_room_title_fix_2026-06-27/contact.png`.
    후속 E9 도움말 refresh까지 반영한 최종 SHA `d96a7e13…` 기준 `verify_dist_integrity.py` PASS.
  - [x] 2026-06-27 추가 스크린샷 후속 수정: `87_common_rule_settings`에서 B팀 맵 이름이
    `소라?? 섬`, `타마?? 섬`으로 깨지는 실제 결함을 확인했다. ROM의 B8 compact map-name copy는
    `소라 마메 섬`/`타마 타마 섬`처럼 ASCII space 뒤에 2바이트 한글이 이어졌고, 해당 renderer는 Part2 A2
    map-select 0x20 hook 경로가 아니라 공백 뒤 한글을 `?`로 오독했다. B팀 권위문
    `data/dialogue_overrides.json`/`data/bteam_baseline.json`은 그대로 두고, 화면 전용
    `data/display_overrides.json`에 `0x00B826A8 마른잎섬`, `0x00B8277C 타마타마섬`,
    `0x00B827AC 소라마메섬`을 추가했다. `scene_87_common_rule_settings` checkpoint도 stale savestate에서
    coldboot fresh nav로 승격해 scene editor가 깨진 RAM 캐시를 다시 참조하지 않게 했다.
    증거: `docs/screenshots/rule_settings_map_name_fix_2026-06-27/fresh_rule_settings.png`.
    최종 SHA `e6ca1081…` 기준 `run_release_qa.py`, `run_release_qa.py --only-editor --editor --timeout 300`,
    `verify_dist_integrity.py` PASS.
  - [x] 2026-06-27 추가 스크린샷 current 재검증 및 UI 에디터 작전실 캡처 수정:
    Downloads의 사용자 7장 contact를 다시 판독했고, Part1 메뉴/통신 라벨 덮침은 current fresh route에서
    재현되지 않으며 `single_map`의 `??????`는 원본 `？` placeholder 판정 유지다. 이 과정에서
    `41_part1_operation_room` scene editor screenshot이 current ROM SHA임에도 2026-06-08 savestate RAM 캐시로
    깨진 작전실 문자를 재생성하는 문제를 발견했다. checkpoint를 coldboot fresh nav로 승격하고
    `data/scene_entrypoints.json` provenance도 `data/screen_checkpoints.json` 기준으로 정리했다.
    증거: `docs/screenshots/user_report_triage_2026-06-27/triage.md`,
    `temp/scene_screenshots/41_part1_operation_room_patched/frame.png`.
    `capture_scene_screenshots.py --force`, `audit_scene_entrypoints.py --strict` stale 0,
    `audit_scene_catalog.py --strict` critical 0, `run_release_qa.py` PASS,
    :8782 서버 기동 후 `run_release_qa.py --only-editor --editor --timeout 300` PASS.
  - [x] 2026-06-27 추가 에뮬레이터/scene sweep 후속 수정:
    사용자 스크린샷과 전체 contact sheet를 다시 훑는 과정에서 ROM 데이터가 아니라 stale savestate/VRAM 때문에
    깨져 보이던 `scene_19e7_part1_hoip_co_weather_help`, `scene_19f_part1_extra_story`,
    `scene_29_part2_result_summary` 체크포인트를 current ROM 재진입 경로로 교체했다.
    `19e7`은 `state_012`가 아니라 `part1_aw1_save_placement_probe_a5/2111_front/after_route.ss0`에서
    `A,A`로 다시 렌더해 `사령관님께 말할게요`를 표시하고, `19f`는 `step_016.ss0 + A`로
    `게임보이 한 대로 / 한대대전모드`를 표시한다. `29`는 sparse cell 진단 과정에서 드러난 숫자/랭크 타일
    손실 위험을 반영해 `0x59DA5C` 1024타일 full-sheet를 보존하고 라벨/타이틀 영역만 지우도록 수정했으며,
    stale `state_016` 대신 pre-result `state_012 + A,A`로 캡처한다.
    이 과정에서 Part2 Sound Room 조작 라벨, 전투 시스템 `음악 있음`, Hoip player-name control leak,
    Part1 모드 설명 ASCII/digit artifact도 current ROM 기준으로 재검증했다.
    최종 output/dist SHA `a4e98a93daf1f545f6224814b0c55d8e981f98ec16ccc3872c2f30831ec0489e` 기준
    `capture_scene_screenshots.py --force`, contact sheet visual audit,
    `run_release_qa.py`, `run_release_qa.py --only-editor --editor`, `run_release_qa.py --only-editor --cdp`,
    `verify_dist_integrity.py`, scene/residual strict audit가 모두 PASS.
  - [x] 2026-06-27 Codex 추가 재검증:
    사용자 contact 대상 `40_part1_name_menu/41_part1_operation_room/42_part1_single_battle/43_part1_link`를
    current SHA `a4e98a93…`에서 강제 재캡처해 메뉴 라벨 도움말 침범과 작전실 깨진 title cache가
    재현되지 않음을 수동 시각 확인했다. `single_map`의 `??????`는 현재 output에서도 원본과 동일한
    `0x00DF8C2A` `8148`×6 바이트임을 `data/part1_single_map_question_watch_20260626.json`의
    `current_byte_recheck`로 보강했다. 같은 상태에서 `run_release_qa.py`,
    `run_release_qa.py --only-editor --editor --timeout 300`,
    `run_release_qa.py --only-editor --cdp --timeout 300`, `verify_dist_integrity.py`가 PASS.
  - [x] 2026-06-28 사용자 추가 스크린샷 재확인 및 Part1 작전실 제목 가독성 보강:
    `~/Downloads`의 사용자 7장 contact를 다시 대조했다. current fresh route에서 Part1 메뉴/통신 라벨 침범은
    재현되지 않고, single-map unknown 표시는 이미 `미공개`로 보인다. 다만 Part1 작전실 compact title은
    `전투개시`, `전선기지확보`, `키쿠치요실수`처럼 공백 없는 압축 제목이 실제 사용자 눈에는 깨진 제목처럼
    보일 여지가 커서 `0xB81D80..0xB82018` 작전명 32개를 슬롯 내에서 자연스러운 짧은 제목으로 재정리했다
    (`전투 개시`, `전선 기지 확보`, `키쿠치요 실수`, `고물 전차 출격`, `특수부대 도미노` 등).
    `tools/prove_compact_display_mutation.py`도 build `encode_fit()`을 사용하도록 고쳐, 새 작전명 안의 공백이
    compact renderer에서 실제 쓰는 전각 공백 바이트와 동일하게 검증되도록 했다. 증거:
    `docs/screenshots/part1_operation_room_title_readability_2026-06-28/scene_contact.png`,
    `fresh_routes_contact.png`, `single_map_left_crop_4x.png`.
    최신 output/dist SHA `f95a8573…` 기준 `verify_dist_integrity.py`,
    `run_release_qa.py --editor --cdp --timeout 300`,
    `capture_scene_screenshots.py --force`, UI editor CDP 63 scene/108 sprite verification이 PASS.
  - [x] 2026-06-27 전투 항복/모드 선택 복귀 확인창 `??????` 수정:
    E12 B84 power-menu probe 중 `scene_89_common_battle_system_results` 계열에서
    `모드 선택으로 돌아갈까??????`가 current ROM에서도 재현됐다. 원인은 `0x00A34CE8`/`0x00DF2A64`
    B팀 권위문 `모드 선택으로 돌아갈게요.괜찮을까요?`가 고정 폭 확인창 renderer의 실제 표시 한계를 넘으면서
    후행 글자가 fallback `?`로 그려진 것이다. 첫 임시안 `모드 선택으로 돌아갈까?`는 Claude/agy 리뷰에서
    반말·권위문 drift로 기각했고, 최종 표시문은 존댓말을 유지한 `모드 선택으로 돌아갈까요?`로 고정했다.
    `data/dialogue_overrides.json`과 `data/bteam_baseline.json`의 두 주소를 의도적으로 함께 갱신했으며,
    증거는 `docs/screenshots/battle_surrender_question_fix_2026-06-27/before_after_contact.png`.
    최종 output/dist SHA `3e3bae3363ce429df76505d1413906f82203dfaaea35b4df3d610bbd80e902d0` 기준
    `verify_dist_integrity.py`, `run_release_qa.py --timeout 300`,
    `run_release_qa.py --only-editor --editor --timeout 300` PASS.
  - [x] 2026-06-27 Part1 싱글 대전 룰 원형 라벨/값 일본어 잔존 수정:
    E16 route 탐색 중 `single_map -> 룰 설정` 화면에서 원형 버튼 상단/내부에
    `サクテキ`, `テンキ`, `収入`, `日数`, `ユウセイ`, `能力`, `アニメ`,
    `アリ`, `ランダム`, `ナシ`, `タイプA`가 그대로 보이는 실제 visual defect를 확인했다.
    OAM/VRAM 추적 결과 Part2 룰 요약 raw OBJ(`0x45D334..`)가 아니라 Part1 전용 LZ77 block
    `0x00C2C6EC`의 OBJ tile sheet였다. `tools/build_korean_full.py`에
    `patch_part1_rule_circle_labels()`를 추가해 라벨 7개(`정찰/날씨/수입/일수/우세/능력/애니`)와
    값 9개(`있음/랜덤/눈/없음/맑음/있음/타입A/B/C`)를 렌더 후 같은 LZ77 slot에 재압축한다.
    원본 slot 4792B 대비 패치 압축 3904B로 overflow 없음. mGBA `loadtempsav+reset+fresh menu` route에서
    실제 화면과 VRAM OBJ 영역(`0x10000 + tile*32`) 16개 전부 한글 렌더 바이트 일치 확인.
    증거: `docs/screenshots/part1_rule_circle_labels_fix_2026-06-27/`.
    최종 output/dist SHA `c1d1b28909d318373a58603d08f2bdf55e9a774af960a8cbee61902a38957280` 기준
    `verify_dist_integrity.py`, `run_release_qa.py --timeout 300`,
    `run_release_qa.py --only-editor --editor --timeout 300`,
    `run_release_qa.py --only-editor --cdp --timeout 300` PASS.
  - [x] 2026-06-27 Part1 메뉴 도움말 공백 복원:
    사용자 추가 스크린샷과 current fresh capture를 다시 대조하자 대형 OBJ 라벨의 강한 침범은 닫혔지만,
    하단 도움말 자체가 `전투법알려줄게`/`와서들어봐`, `처음부터대전`, `친구와연결해`처럼 공백 없는
    화면 전용 임시 문구로 남아 있어 가독성이 낮았다. 실제 `encode_fit()`으로 모든 후보가 level 0 slot-fit임을
    확인한 뒤 `0xDFA64A..0xDFA9E9` override를 `전투 방법 알려 줄게`/`와서 들어 봐`,
    `처음부터 대전`, `친구와 연결해`/`대전 가능`, `카트리지 하나로` 등 공백 있는 짧은 문구로 정리했다.
    증거: `docs/screenshots/part1_menu_help_spacing_2026-06-27/contact.png`,
    `docs/screenshots/part1_menu_help_spacing_2026-06-27/help_crops_4x.png`,
    `docs/screenshots/part1_menu_help_spacing_2026-06-27/full_sweep_contact.png`.
    최종 output/dist SHA `b9eea881356404e4643fadd6ca4f6d9bb7dcc31a649c1a928a7777ff170418b7` 기준
    `qa_text_fit.py`, `qa_visual_regions.py`, `audit_address_text_overrides.py --strict`,
    scene/catalog/residual strict audit, `verify_dist_integrity.py`, editor API/CDP QA PASS.
    Claude/agy 리뷰 후 추가로 current fresh route 30프레임(mode 9, operation 8, single 7, link 6)을
    재캡처해 visible route의 공백 도움말 깨짐은 보이지 않음을 확인했다.
- [ ] E3 잔여 미번역 triage(제어마커/slot overflow/no group 자동제외분 수동검수).
- [ ] E4 표기흔들림 통일(국가명 붙임/띄움) + 구 apply_proper_nouns.py deprecate.
- [ ] E5 VRAM 팔레트 캡처(0x05000000/0x05000200) 스프라이트 실색.
- [ ] E6 CSV 권위 단일화(inline 리터럴 → overrides.tsv 분리).
- [ ] E7 캡처 지연 단축(슬롯 nav 단축 canvas + orig 캡처 영구 캐시).
- [x] E8 `88_common_comm_labels` raw 단일 `ソ`(0x00EE22AC) 실제 UI 노출 재확인 완료(2026-06-26).
  당시 SHA `edff0a12…` 관련 통신/공통 메뉴 캡처 7장 수동 시각검사에서 visible `ソ` 0. Part1 3장은
  coldboot fresh route로, Part2/공통 4장은 current checkpoint로 재캡처했다. 최신 증거:
  `docs/screenshots/e8_comm_label_reverify_2026-06-27/contact.png`.
  기존 1967-case menu/focus/row 동적 스캔 hit 0 원본은
  `data/scene_residual_reverify/88_common_comm_labels_dynamic_scan_results.json`에 보존. `data/comm_label_visual_reverify.json`을
  residual manifest에 연결했고 audit가 리포트/PNG/provenance/primary-stale 역할/보조 scan SHA까지 검증한다.
  `audit_scene_residual_scans.py --strict` 결과 case 16/hit 0/critical 0.
  2026-06-26 추가 갱신: 현재 SHA `19a2ea71…` 기준 Part1 single/link와 Part2 shop 캡처 3장으로
  `data/comm_label_visual_reverify.json` 및 `data/scene_residual_scans.json` provenance를 재동기화했고,
  `audit_scene_residual_scans.py --strict` 결과 case 16/hit 0/critical 0.
  2026-06-27 추가 갱신: 현재 SHA `95bc2486…` 기준 7장 전체
  (`11/12/13/23/23a/23b/86`)를 재캡처해 `data/comm_label_visual_reverify.json`과
  `data/scene_residual_scans.json` provenance를 재동기화했다. `audit_scene_residual_scans.py --strict` 결과
  case 17/hit 0/critical 0.
  2026-06-27 E15 수정 후 현재 SHA `11098045…` 기준 같은 7장 증거를 다시 갱신했고, residual audit는
  case 17/hit 0/critical 0.
  2026-06-27 E9 refresh 후 현재 SHA `d96a7e13…` 기준 7장 전체를 재캡처해
  `data/comm_label_visual_reverify.json`과 `data/scene_residual_scans.json` provenance를 다시 동기화했다.
  residual audit 결과 case 17/hit 0/critical 0.
  2026-06-27 `87_common_rule_settings` 맵명 수정 후 현재 SHA `e6ca1081…` 기준 7장 전체를 다시 재캡처했다.
  Part1 3개 stale-state 캡처는 `supplementary_stale_state`로 강등하고, Part2/공통 4개 current capture를
  primary로 유지했다. residual audit 결과 case 17/hit 0/critical 0.
  2026-06-27 추가 에뮬레이터 sweep 후 현재 SHA `a4e98a93…` 기준 같은 7장 증거와 contact sheet를 다시 동기화했다.
  이번에는 7장 모두 current capture `primary_current_sha`로 기록했고, residual audit 결과 case 17/hit 0/critical 0.
  2026-06-27 항복 확인창 수정 후 현재 SHA `3e3bae33…` 기준 같은 7장 증거를 다시 캡처해
  `data/comm_label_visual_reverify.json`과 `data/scene_residual_scans.json`을 재동기화했다. residual critical 0 유지.
  2026-06-27 Part1 도움말 공백 복원 후 현재 SHA `b9eea881…` 기준 같은 7장 증거를 다시 캡처해
  `data/comm_label_visual_reverify.json`과 `data/scene_residual_scans.json`을 재동기화했다.
  `audit_scene_residual_scans.py --strict` 결과 case 17/hit 0/critical 0 유지.
- [x] E9 Part1 compact help text 의미/자연스러움 보강 완료(2026-06-27).
  `ADDRESS_TEXT_OVERRIDES`의 Part1 메뉴 도움말 중 `대결 법 가르 드려`류 어색한 축약을 먼저 짧은 문구로 정리했고,
  이후 사용자 스크린샷 후속 재확인에서 공백 없는 임시 문구도 안전 슬롯 안에서 다시 복원했다.
  현재 대표 문구는 `전투 방법 알려 줄게`/`와서 들어 봐`, `둘부터 넷까지`/`대전 가능`,
  `카트리지 하나로`/`모두와 대전`, `친구와 연결해`/`맵 교환 가능`이다.
  `0xDFA68C`는 compact 권역 리스크를 줄이기 위해 `전투기록볼수있어`로 유지한다.
  fresh mGBA route로 mode/single/link와 작전룸 하위 메뉴를 재캡처했고 도움말/대사 깨짐 없음.
  증거: `docs/screenshots/e9_part1_compact_help_refresh_2026-06-27/contact.png`,
  `docs/screenshots/part1_menu_help_spacing_2026-06-27/contact.png`,
  `docs/screenshots/part1_menu_help_spacing_2026-06-27/help_crops_4x.png`.
  최종 SHA `b9eea881…` 기준 `audit_address_text_overrides.py --strict`, `qa_text_fit.py`,
  `qa_visual_regions.py`, scene/residual strict audit, `verify_dist_integrity.py`, editor API/CDP QA PASS.
- [x] E10 `ADDRESS_TEXT_OVERRIDES` 거버넌스 하드닝 완료(2026-06-26).
  `tools/audit_address_text_overrides.py --strict` 추가. source duplicate key 142주소/145라인을 최종 effective 값
  보존 방식으로 제거해 source entries=effective=4118, duplicate 0, runtime/static mismatch 0.
  리뷰 반영으로 final effective 산정은 raw `ADDRESS_TEXT_OVERRIDES`가 아니라 pair-renderer normalize 4건과
  후단 direct patch collision 970건(분기 502)을 포함한다. `dialogue_overrides` 보호주소 collision 1111
  (분기 1072/동일 39)은 리포트로 남기고 hard fail 대상에서는 제외한다. `dialogue_map.json` 보호주소 표시
  mismatch 0, `dialogue_groups.json` 보호주소 표시 mismatch 0. `verify_dist_integrity.py` 배포 게이트에 strict audit 연결.
- [x] E11 통합 QA runner/CI 정리 완료(2026-06-27).
  codex/agy 리뷰 지적: 현재 배포 전 QA는 수동 나열 중심이다. `build`, text QA, visual QA, scene audit,
  editor smoke, dist integrity를 한 번에 실행하는 runner와 CI/로컬 gate 분리를 설계한다.
  - [x] 2026-06-27 claude 리뷰 후속: `data/display_overrides.json`과 compact display 관련 신규 QA/분석 스크립트가
    빌드 하드 의존이므로, 배포/커밋 전 누락을 잡는 packaging audit를 통합 runner에 포함한다.
  - [x] 2026-06-27 B2 리뷰 후속: `qa_csv_integrity.py --fail-on-rom-japanese`,
    `lint_translation.py --severity error`, rebuild SHA 동기성, temp 부산물 비의존성 검사(복구 전용 `temp/*`가
    빌드 권위로 쓰이지 않는지)를 통합 runner에 포함한다.
    `tools/run_release_qa.py`를 추가해 로컬/static gate와 editor/CDP gate를 분리했다. 기본 profile은 py_compile,
    CSV/placeholder/Japanese/text-fit/repoint/override/scene/visual/dist integrity를 한 번에 실행하고 PASS했다.
    `--only-editor --editor` profile도 :8782 scene editor API 기준 PASS했다.
    2026-06-27 최종 SHA `a4e98a93…`에서는 Chrome remote debugging 9224를 임시 프로필로 띄워
    `--only-editor --cdp`도 PASS했다. 결과 리포트:
    `temp/release_qa_report_20260627.json`, `temp/release_qa_editor_report_20260627.json`,
    `temp/release_qa_cdp_report_20260627.json`. B4 CSV shadow와 E14 repoint punctuation/integrity는
    `verify_dist_integrity.py` 하위 게이트로 통합 완료.
    2026-06-27 Part1 도움말 공백 복원 후 SHA `b9eea881…`에서도 기본 release QA는 마지막 `editor-cdp`만
    Chrome 9224 미기동으로 실패했고, Chrome CDP를 임시 프로필로 기동한 뒤
    `run_release_qa.py --only-editor --cdp --timeout 300`가 PASS했다.
    리포트: `temp/release_qa_report_20260627_part1_menu_help_spacing.json`,
    `temp/release_qa_report_20260627_part1_menu_help_spacing_cdp.json`.
- [ ] E12 B8/CO compact 표시문 실화면 matrix 확대.
  2026-06-27 claude/agy after-fix 리뷰 공통 잔여. `qa_glyph_dictionary_tables.py`가 A2 36개/B84 11개 사전·대상
  바이트와 0 패딩을 보장하고, `23d_part2_b8_compact_display_tables`가 B8 표시문 459개를 UI 에디터에 노출하지만,
  모든 CO 파워명/유닛·무기·상점·브레이크 라벨이 실제 각 화면에서 정확한 글리프로 렌더되는지 전수 visual matrix는
  아직 없다. 현재는 static QA + 대표 scene screenshot 70개 기준 PASS이며, 화면별 fresh 진입점을 추가해야 한다.
  - [x] 2026-06-27 E12 matrix 기반 구축:
    `tools/build_compact_display_visual_matrix.py`를 추가해 정적 바이트 검증, UI 에디터 노출, current-ROM screen capture,
    direct per-target visual evidence를 분리 집계한다. 초기 구축 당시 SHA `11098045…` 기준 결과
    (최신 수치는 아래 current 재동기화 항목과 matrix 보고서 기준):
    A2 CO 파워명 36개는 editor 36/screen-current 1/container-only 35/direct 0,
    B84 파워명 11개는 editor 11/container-only 11/direct 0,
    B8 compact table 459개는 editor 459/container-only 459/direct 0.
    보고서 `docs/reports/compact_display_visual_matrix_2026-06-27.md`, 대표 contact
    `docs/screenshots/e12_compact_display_matrix_2026-06-27/current_representative_contact.png`.
    agy 적대 리뷰 결론도 “E12 진척은 충분하지만 direct evidence 0이라 미완료 유지”이며, 다음 우선순위는
    B84 파워 발동 화면, B8 유닛/무기/상점 HUD, A2 CO 프로필 다중 CO 캡처 순서다.
  - [x] 2026-06-27 renderer breakpoint trace/code-context 기반 구축:
    `tools/trace_compact_renderer.py`를 추가하고 초기 SHA `11098045…`에서 Part2 메인 메뉴, 워즈숍,
    compact 메뉴, 룰 설정, 전투 공격/전투 OBJ 라벨/전투 시작 overlay, CO 프로필 maxg/domino refresh 9경로를
    `0x08380564/0x083806A8/0x08381294/0x08B3C184` 및 B84 pointer-table user 후보
    `0x08B3C2D0/0x08B3C300/0x08B3C320/0x08B3C4D6/0x08B3C550/0x08B3C5A0`
    break로 추적했지만 hit 0/direct 0이다. 결과는 `data/compact_display_renderer_trace.json` 및
    matrix 보고서의 Renderer Trace 섹션에 반영했다. 후속으로 `tools/analyze_compact_display_code_context.py`를
    추가해 literal entry 492/breakpoint 후보 24/function 후보 18을 산출했고, trace break set을 50개로 늘렸지만
    같은 9경로에서 hit 0/direct 0이다. 이 음성 결과로 B8/B84 미사용을 결론내리지 말 것.
  - [x] 2026-06-27 read-watch probe 1차 기반 구축:
    claude/agy 재리뷰 지적에 따라 `tools/probe_compact_display_reads.py`를 추가했다. A2/B84 range read-watch는
    fresh Part2 메인 메뉴 + CO profile maxg/domino refresh 3케이스에서 hit 0/direct read 0,
    B8 range read-watch는 compact 메뉴/워즈숍 savestate 2케이스에서 hit 0/direct read 0,
    B8 representative exact watch(`0xB81D40/0xB831BC/0xB8387C/0xB838BC/0xB839F0/0xB84CB8/0xB84F14`)는
    fresh Part2 메인 메뉴 + compact 메뉴/워즈숍 후보 3케이스와 전투 공격/OBJ 라벨/시작 overlay 3케이스에서
    hit 0/direct read 0이다. 전투 공격 1케이스는 B8 전체 range로도 감시했지만 hit 0/direct read 0이다.
    추가로 `--state/--state-step` 임의 savestate 모드를 붙여 외부 상점/프로필 후보 state 15케이스를 확인했으나
    모두 hit 0/direct read 0이고, 프레임상 해당 후보들은 target 화면이 아니라 상점 대화 화면이었다.
    후속으로 fresh `0x00A01970` 양성대조는 59 hit로 하니스가 ROM read를 잡는 것을 확인했고,
    `--screen-step`을 추가해 fresh `06_part2_title` + `part2_menu_sweep` 정책에서 B8 대표 7개를 감시했지만
    hit 0/direct read 0이다. 결과는 `data/compact_display_read_watch_probe*.json`,
    `data/compact_display_read_watch_positive_control_a01970.json`,
    `data/compact_display_read_watch_b8_fresh_menu_sweep_subset.json`과 matrix 보고서 Read-Watch Probes/
    Positive Controls 섹션에 반영했다. 이는 route/subset 음성 결과일 뿐 전역 미사용 증명이 아니다.
  - [x] 2026-06-27 static pointer xref 기반 구축:
    `tools/analyze_compact_display_xrefs.py`를 추가해 A2/B84/B8 compact target의 ROM 포인터 참조를 전수 집계했다.
    초기 SHA `11098045…` 기준 A2 36/36, B84 11/11, B8 371/459 target에 pointer ref가 있고,
    external pointer ref는 A2 36, B84 11, B8 355 target이다. `0x08DF2B54` B84 파워명 포인터 테이블은
    `0x08B3C318/0x08B3C540`에서 2차 참조된다. 이 결과는 `data/compact_display_xref_analysis.json`과
    matrix 보고서 Static Pointer Xrefs 섹션에 반영했다. 단, xref는 reachability 후보일 뿐 direct visual evidence가 아니다.
  - [x] 2026-06-27 current SHA `a4e98a93…` matrix/evidence 재동기화:
    대표 scene 8개(`23_part2_main_menu`, `23a_part2_wars_shop`, `86_common_compact_menu_tables`,
    `30f2_part2_co_profile_story`, `26_part2_battle_labels`, `24a_part2_operation_select`,
    `85_ui_common`, `87_common_rule_settings`)를 최신 ROM으로 재캡처하고,
    `data/compact_display_read_watch_current_exact.json`, `data/compact_display_read_watch_b8_map_territory_current.json`,
    positive control, renderer trace, static xref, code-context,
    `data/compact_display_visual_matrix.json`, `docs/reports/compact_display_visual_matrix_2026-06-27.md`를
    새 SHA로 갱신했다. 현 상태는 A2 editor 36/current capture 1/direct 0,
    B84 editor 11/direct 0, B8 editor 459/direct 0이다. static xref는 A2 36/36,
    B84 11/11, B8 402/459 target에 pointer ref가 있고, external pointer ref는 A2 36,
    B84 11, B8 386 target이다. renderer trace는 9경로 hit 0/direct 0,
    read-watch current-exact 11케이스 hit 0/direct 0, B8 map-territory exact 1케이스
    hit 0/direct 0, 양성대조 `0x00A01970`은 hit 8이다.
    CO profile nav probe와 candidate state triage contact도 추가했지만, 각각 파워명 페이지 미진입/지도·상점·메뉴 화면으로
    target direct evidence가 아니었다. 따라서 E12는 계속 미완료 유지한다.
  - [x] 2026-06-27 claude/agy 리뷰 반영:
    차단급 문제는 없고 E12 미완료 유지가 정당하다는 판정을 받았다. 단, 0-hit는 route 미진입뿐 아니라
    A2/B84/B8 override 주소가 실제 렌더 경로가 아닌 복사본/死 데이터일 가능성도 남긴다는 지적이 있었다.
    `tools/build_compact_display_visual_matrix.py`의 read-watch probe 집계는 수동 allowlist에서
    `data/compact_display_read_watch*.json` 자동 발견(positive control만 별도 분리)으로 바꿔 신규 probe 누락 위험을 줄였다.
    UI 에디터/CDP PASS는 데이터·카탈로그 검증이지 E12 실화면 증거가 아니라는 caveat도 문서에 반영한다.
  - [x] 2026-06-27 CO 파워명 compact 표시 whitelist/게이트 보강:
    `data/compact_power_display_whitelist.json`을 추가해 B팀/editor 풀네임과 compact 화면 표시명(`미라클 찬스`→`기적`,
    `메테오 스트라이크`→`메테오` 등)의 의도적 발산을 주소별로 문서화했다.
    `qa_glyph_dictionary_tables.py`는 whitelist 주소가 `data/display_overrides.json`의 A2/B84 target과 정확히 일치하는지,
    `full_ko`가 `data/dialogue_overrides.json` 권위문과 일치하는지, compact target 인코딩이 원 slot을 넘지 않고
    tail zero-fill을 지키는지 hard fail한다. 리뷰 후 `0x00A29618`의 풀네임 권위문(`와쇼이 페스타`) 누락을
    `dialogue_overrides.json`에 보강했고, `ADDRESS_TEXT_OVERRIDES`와 display override가 compact target에서
    갈라지면 QA가 실패하도록 추가했다. 표시 축약의 의미 적절성은 자동 게이트 범위 밖임을 whitelist `_doc`과
    release note에 명시했다.
  - [x] 2026-06-27 E12 source/dead-copy 반증 실험 1차:
    B84 지도 라벨 후보 `0xB84F5C/0xB84F6C`, `0xA35758`, 전체 `레드스타` ROM 발생 위치를 test label로 바꿔도
    `10_part2_region_map_redstar` 픽셀 diff는 0이었다. `0xB837A4/0xB84488` 메뉴 후보와 전체 `상점` 발생 위치도
    현재 메뉴 캡처에서 diff 0이었다. 전투 action menu는 `temp/first_battle_state31_a36_probe/after_a36.ss0`에서
    `A` 반복으로 실제 `공격` 메뉴까지 도달했지만 B8 exact 후보 7건 read-watch hit 0/direct 0이었다.
    따라서 이 화면들은 E12 직접 증거 후보가 아니라 baked graphic/VRAM cache/다른 source 후보로 분리한다.
    단, 양성대조 `0x00A01970`은 일반 텍스트 read-watch이지 compact renderer 양성대조가 아니므로,
    compact renderer 자체의 positive control은 아직 미확보 상태로 남긴다.
  - [x] 2026-06-27 B8 Part1 작전명 target/source provenance 1건 확보:
    사용자 작전실 신고 화면을 활용해 `0x00B81FF4`(`전선기지확보`) 단일 주소만 temp ROM에서
    `테스트확보`로 바꾼 뒤 `41_part1_operation_room` coldboot fresh checkpoint를 base/mutation 양쪽 캡처했다.
    픽셀 diff 209px, bbox `[9,75,56,86]`로 리스트 해당 행만 바뀌었다. 증거는
    `data/compact_display_manual_visual_evidence.json`과
    `docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_operation_title_b81ff4_mutation_contact.png`.
    `tools/build_compact_display_visual_matrix.py`는 current ROM SHA, 양수 픽셀 diff, contact sheet 존재,
    그룹/주소 일치가 모두 맞을 때만 target-level proof로 집계한다. 이는 live source 증거이지 전수 visual-layout
    품질 보장은 아니다. 현 matrix는 후속 추가 증거 반영 후 A2 direct 0, B84 direct 0, B8 direct 12이다.
    `verify_dist_integrity.py`에도 matrix SHA/invalid/stale/unmatched/manual contact/target-row attachment 동기화
    게이트를 추가했다.
  - [x] 2026-06-27 B8 Part1 작전명 추가 3건 target/source provenance 확보:
    `tools/prove_compact_display_mutation.py`를 추가해 단일 주소 mutation → 같은 checkpoint 캡처 →
    diff/contact/evidence 생성을 반복 가능하게 만들었다. `41_part1_operation_room` coldboot fresh route에서
    `0x00B82018`(`전투개시`→`검증개시`, diff 54px/bbox `[10,43,24,54]`),
    `0x00B8200C`(`초반전`→`검증전`, diff 64px/bbox `[9,59,24,70]`),
    `0x00B81FDC`(`고물전차출격`→`검증출격`, diff 215px/bbox `[9,91,56,102]`)가
    각각 해당 리스트 행만 바꾸는 것을 확인했다. contact는
    `docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_operation_title_00B82018_mutation_contact.png`,
    `..._00B8200C_...`, `..._00B81FDC_...`. 당시 matrix는 manual current/accepted 4, B8 direct 4로 갱신됐다.
    2026-06-27 agy 리뷰 지적 반영 후 matrix가 `contact_sheet_sha256`, `diff_mask`, `diff_mask_sha256`를
    포함하도록 재생성됐고, `verify_dist_integrity.py`는 accepted mutation evidence의 contact SHA, diff mask 존재,
    SHA, non-black pixel count를 hard gate로 확인한다. Claude CLI는 장시간 무응답 후 중단되어 실질 리뷰 결과 없음.
  - [x] 2026-06-27 B8 Part1 작전명 스크롤 행 4건 target/source provenance 추가:
    `tools/prove_compact_display_mutation.py`에 `--append-nav-step`과 docs diff-mask 자동 보존을 추가했다.
    `41_part1_operation_room` coldboot fresh route에서 DOWN 4회 위치의
    `0x00B81FC4`(`적부대격파`→`검증격파`, diff 167px/bbox `[10,75,48,86]`),
    `0x00B81FAC`(`지상최강중전차`→`검증중전차`, diff 209px/bbox `[9,91,64,102]`)와
    DOWN 7회 위치의 `0x00B81F98`(`드래곤플라이`→`검증플라이`, diff 218px/bbox `[9,59,56,70]`),
    `0x00B81F70`(`창공제패`→`검증제패`, diff 40px/bbox `[9,91,23,102]`)가 해당 리스트 행만 바꾸는 것을
    contact sheet로 확인했다. `0x00B81F80`(`하늘에서오는건`) mutation은 selected row 설명/애니메이션 diff가
    섞여 bbox가 커졌으므로 contact만 보존하고 accepted evidence에는 넣지 않았다.
    Matrix는 manual current/accepted 8, B8 direct 8로 갱신됐고 `verify_dist_integrity.py` PASS.
  - [x] 2026-06-27 항복 확인창 수정 후 E12 matrix current SHA 재동기화:
    최종 SHA `3e3bae33…` 기준 B8 accepted mutation evidence 8건을 다시 생성하고
    `data/compact_display_manual_visual_evidence.json`, `data/compact_display_visual_matrix.json`,
    `docs/reports/compact_display_visual_matrix_2026-06-27.md`를 재생성했다. 당시 수치는 A2 direct 0,
    B84 direct 0, B8 direct 8/459이며, `verify_dist_integrity.py`가 manual current/accepted 8과
    matrix SHA 동기화를 확인한다. 이는 SHA 동기화이며 E12 완료 근거가 아니다.
  - [x] 2026-06-27 B8 Part1 작전명 중반부 target/source provenance 4건 추가:
    `tools/prove_compact_display_mutation.py`의 긴 `--append-nav-step` checkpoint 이름이 macOS path limit을 넘는 문제를
    hash suffix로 고쳤다. 같은 `41_part1_operation_room` fresh route에서 DOWN 10회 위치의
    `0x00B81F5C`(`도그파이트`→`검증파이트`, diff 70px/bbox `[9,59,24,70]`),
    `0x00B81F4C`(`바다너머`→`검증너머`, diff 77px/bbox `[9,75,23,86]`),
    `0x00B81F40`(`백은세계`→`검증세계`, diff 48px/bbox `[9,91,23,102]`)와
    DOWN 13회 위치의 `0x00B81F38`(`결전`→`검증`, diff 58px/bbox `[9,91,24,102]`)가 해당 행만 바꾸는 것을
    contact sheet로 확인했다. DOWN 16회에서 `과외수업/개전/건파이터/하늘용사`는 pixel diff 0이어서
    direct evidence로 채택하지 않았다. Matrix는 manual current/accepted 12, A2 direct 0, B84 direct 0,
    B8 direct 12/459로 갱신됐고 `verify_dist_integrity.py` 및
    `run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_e12_b8_direct12.json` PASS.
    Claude/agy 리뷰도 12건은 live source provenance일 뿐 visual-fit/전수 품질 보장이 아니며,
    작전실 계열 편중과 compact-renderer 전용 positive control 부재를 caveat로 유지하라고 지적했다.
  - [x] 2026-06-27 E12 mutation proof 신뢰도 보강:
    `tools/prove_compact_display_mutation.py`에 same-ROM base repeat null-control과 `--expected-diff-box` 검사를 추가했다.
    기존 accepted 12건을 모두 재생성했고, 각 proof는 null-control pixel diff 0/deterministic true,
    expected box `0,32,80,104` 내부 bbox true를 기록한다. `tools/build_compact_display_visual_matrix.py`와
    `tools/verify_dist_integrity.py`는 null-control nonzero 또는 bbox outside를 accepted evidence 실패로 처리한다.
    최신 matrix는 manual current/accepted 12를 유지하지만, 이제 12건 모두 cursor/animation false-positive가 아닌
    좌측 작전명 row-local diff임을 hard gate로 확인한다. `verify_dist_integrity.py` 및
    `run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_e12_null_control.json` PASS.
  - [x] 2026-06-27 B84 power/menu route probe 음성:
    `temp/e12_b84_power_menu_probe_20260627`에서 `scene_89_common_battle_system_results` 기반 55 cases
    (무 RAM 패치 + gauge/state variant, `b_start`, `b_select`, `up_a` 등 입력)를 실행하고
    `0x08DF2B54`, `0x08B84E50` read-watch와 `0x08B3C184/0x08B3C254/0x08B3C4D8` break를 걸었지만 hit 0/direct 0이었다.
    contact는 항복/메뉴/대화 프레임을 포함했고 별도 항복 확인창 `??????` 결함을 드러냈으나,
    B84 파워명 target direct evidence는 얻지 못했다. E12는 A2 direct 0/B84 direct 0/B8 direct 12/459로 미완료 유지.
  - [x] 2026-06-28 B84 AW1 CO 파워명 `0x00B84F04` direct proof/fix:
    AW1 전투 중 rec1 gauge `0x0201ADC0=a0860100` 상태에서 메뉴 row 2를 선택해 `하이퍼수리` 컷인을 재현했다.
    `0x08DF2B54` pointer table -> `0x08B84F04`, renderer `0x08B3C184`, copy site `0x08B3C1DE`를 확인했다.
    중간에 `0x08F30680` VRAM copy hook도 시도했지만, `0x08B3C1DE`가 공용 compact renderer 경로라
    Part1 메뉴/scene capture 회귀를 만들 수 있어 최종 빌드에서는 비활성화했다.
    최종 구현은 16x32 4bpp glyph 생성 + `0x00BC9D0C` LZ77 source glyph 교체만 사용한다.
    current SHA `e1919e48...`에서 B84 body reads 157, pointer reads 2,
    화면 `하이퍼수리` 정상 표시를 확인했다.
    증거: `docs/screenshots/b84_aw1_power_title_fix_2026-06-28/`.
    matrix는 B84 direct 1/11이다. 나머지 B84 10개와 A2/B8 계열은 미완료 유지.
  - [x] 2026-06-27 A2 CO 프로필 power-name 후보 mutation 음성:
    `scene_30f2_part2_co_profile_story`에서 `0x00A295D8`(`강타`)를 `검증`으로 단일 mutation했지만
    pixel diff 0이었다(`temp/e12_a2_co_profile_mutation_probe_20260627_r2/summary.json`).
    이 savestate+1 frame CO 설명 checkpoint는 A2 compact power-name target의 direct evidence로 쓸 수 없다.
    단, coldboot fresh power-name 화면의 전역 미사용 증명은 아니므로 별도 fresh route가 필요하다.
  - [x] 2026-06-27 E12 read-watch/scene capture 최신 SHA 재동기화:
    최종 SHA `3e3bae33…` 기준 기존 `data/compact_display_read_watch*.json` 16개와 general positive control 1개를
    모두 재실행했고, 후속으로 `41_part1_operation_room` B8 live-source positive probe를 추가했다.
    현재 matrix의 read-watch 집계는 probes 17/current 17/stale 0/cases 46/hits 69/direct 69다.
    hit 69는 이미 mutation proof가 있는 Part1 작전명 4주소(`0xB81FDC/FF4/200C/2018`)에서 나온다.
    비작전실 A2/B84/Part2-B8 후보 45 cases는 여전히 hit 0/direct 0이고,
    양성대조 `0x00A01970`은 fresh prologue route에서 hit 8로 유지된다.
    따라서 하니스는 B8 live source read를 잡을 수 있지만 현재 비작전실 route/subset은 A2/B84/Part2-B8 target 직접 증거를
    주지 않는다는 음성 결과로만 해석한다.
    또한 `tools/capture_scene_screenshots.py`로 stale scene screenshot 58개를 재캡처해 `audit_scene_entrypoints.py --strict`
    missing/stale 0, critical 0으로 복구했다. matrix는 A2 current screen capture 1, B84 direct 0, B8 direct 12/459 유지.
    codex 리뷰가 renderer trace/code-context/xref stale 의존성을 지적해 세 파일도 current SHA로 재생성했고,
    matrix/report가 dependency `current_rom`을 표시하며 `verify_dist_integrity.py`가 stale dependency를 hard fail하도록 보강했다.
    Claude 리뷰 지적에 따라 manual direct 12건이 모두 `b8_compact_display_table_all::15_part1_operation_logos`
    한 화면 계열임을 `accepted_by_group_scene`/`accepted_by_checkpoint`로 matrix 보고서에 분해 표기했다.
    read-watch에서 관측된 B8 작전명 reader PC를 `trace_compact_renderer.py`에 양성대조 breakpoint로 추가했고,
    current trace는 10 cases, breakpoint hit 1762, direct target register hit 0이다.
    최종 검증은 `verify_dist_integrity.py`와
    `run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_e12_b8_operation_positive.json` PASS.
  - [x] 2026-06-27 Part1 도움말 공백 복원 후 E12/current evidence 재동기화:
    SHA 변경(`b9eea881…`)에 맞춰 `data/compact_display_manual_visual_evidence.json`의 accepted 12건을
    모두 재생성하고, `data/compact_display_visual_matrix.json`,
    `docs/reports/compact_display_visual_matrix_2026-06-27.md`,
    `data/compact_display_xref_analysis.json`, `data/compact_display_code_context.json`,
    `data/compact_display_renderer_trace.json`을 current ROM 기준으로 다시 만들었다.
    `verify_dist_integrity.py`는 manual_current 12/manual_accepted 12, stale/invalid 0을 확인한다.
    current trace는 10 cases, breakpoint hit 1775, direct target register hit 0이다.
    이 재동기화는 E12 증거 freshness 보강이며 완료가 아니다. direct 수치는 A2 0, B84 0, B8 12/459이고
    accepted 12건은 전부 `b8_compact_display_table_all::15_part1_operation_logos` / `41_part1_operation_room` 계열이다.
  - [x] 2026-06-27 Part1 룰 원형 라벨 수정 후 E12/current evidence 재동기화:
    SHA 변경(`c1d1b289…`)에 맞춰 compact xref/code-context/renderer trace/matrix와 scene residual evidence를
    current ROM 기준으로 다시 만들었다. `41_part1_operation_room` 기본 frame 4건에 더해 DOWN 4/7/10/13
    스크롤 route를 current SHA에서 다시 캡처해 기존 accepted 12건을 모두 복구했다.
    각 proof는 same-ROM null-control diff 0, expected box `0,32,80,104` 내부 bbox true다.
    `verify_dist_integrity.py`는 matrix SHA `c1d1b289`, manual_current 12/manual_accepted 12,
    stale/invalid 0을 확인한다. direct 수치는 A2 0, B84 0, B8 12/459이며 E12는 계속 미완료다.
  - [x] 2026-06-28 B8 Part1 작전명 `0x00B81F80` live-source provenance 추가:
    `41_part1_operation_room` DOWN 6 route에서 `하늘에서오는건`을 같은 7음절 길이의 `하늘에서검증건`으로
    단일 mutation했다. 짧은 `검증오는건` mutation은 selected/title cache 변화와 섞여 bbox가 전 화면으로 퍼졌으므로
    direct evidence로 쓰지 않았다. 같은 길이 mutation은 null-control diff 0, bbox `[41,91,55,102]`,
    expected box `0,32,80,104` 내부 true로 row-local diff만 만들었다.
    `data/compact_display_manual_visual_evidence.json`과 matrix를 갱신해 manual current/accepted 13,
    B8 direct 13/459가 됐다. 같은 current SHA에서 `data/compact_display_read_watch_current_exact.json`도
    재실행했으며 4 route 중 `41_part1_operation_room`만 B8 target reads 43건
    (`0xB81F80/0xB81FF4/0xB82018`)을 기록했다. A2/B84와 `scene_87_common_rule_settings`의
    `0xB827AC` 후보는 hit/diff 0이라 direct evidence가 아니다.
  - [x] 2026-06-28 current SHA evidence/release 재동기화:
    B84 copy-site hook 회귀를 제거한 최종 current SHA는
    `e1919e48b283026bbb353a1fb2bd623229fd1893f6dfe13c6029f778d8ed0ac1`다.
    `0x08B3C1DE` 공용 compact renderer hook은 Part1 메뉴/scene capture에서 invalid address loop를 만들 수 있어
    비활성화했고, B84 파워명 컷인은 LZ77 source glyph 교체만 사용한다.
    current ROM 기준으로 renderer trace/xref/code-context, B84 read-watch, B8 manual mutation evidence 13건,
    Part1 compact help evidence carry-forward range hash, scene residual/visual evidence, manifest/BPS/IPS를 모두 재생성했다.
    `verify_dist_integrity.py` PASS, `run_release_qa.py` PASS. 배포 패치는
    `dist/game_wars_korean_full_2026-06-28.bps` / `.ips`다.
  - [x] 2026-06-28 Part1 작전실 제목 가독성 수정 후 E12/current evidence 재동기화:
    SHA 변경(`f95a8573…`)에 맞춰 B8 manual mutation evidence 13건, B84 `0x00B84F04` read-watch,
    compact xref/code-context/renderer trace/matrix, scene screenshot 70개, scene residual evidence,
    manifest/BPS/IPS를 current ROM 기준으로 재생성했다. `tools/prove_compact_display_mutation.py`는
    `encode_fit()` 기반으로 바꿔 fullwidth space가 포함된 작전명도 base/mutation hex 검증과 정확히 일치한다.
    `data/compact_display_visual_matrix.json` 기준 direct 수치는 A2 0/36, B84 1/11, B8 13/459이며
    accepted manual evidence는 13건 모두 Part1 작전실 B8 계열이다. `verify_dist_integrity.py`와
    `run_release_qa.py --editor --cdp --timeout 300`은 PASS. E12는 계속 미완료다.
  - [x] 2026-06-28 E12 read-watch probe 전량 current SHA 재동기화:
    `data/compact_display_read_watch*.json` 19개를 current SHA `f95a8573...`로 다시 실행했다.
    matrix 기준 read-watch probes는 current 19/stale 0, cases 41, hits/direct reads 144다.
    A2 CO profile state `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0` + `DOWN,DOWN`에서
    `0x00A295AC` direct reads 34가 재현되어 A2 target runtime/source proof가 0/36 -> 1/36으로 올라갔다.
    B84는 `0x00B84F04` 1/11, B8은 Part1 작전실 계열 13/459 유지다.
    일반 read-watch positive control `0x00A01970`도 current SHA에서 8 hit를 유지한다.
    나머지 action-menu/battle/shop/comm/rule-settings 후보 0-hit는 route/subset 음성일 뿐 전역 미사용 증명이 아니다.
  - [x] 2026-06-28 사용자 추가 스크린샷 current triage 재확인:
    `temp/user_added_screenshots_20260628` 및 `~/Downloads` manifest의 7장 contact를 current SHA
    `f95a8573...`와 다시 대조했다. 원본 제보의 Part1 작전실 title 깨짐, mode/single/link 대형 라벨 하단 침범,
    `single_map ??????`, 1카드/멀티카드/맵교환 도움말 깨짐은 current fresh route에서 재현되지 않는다.
    이는 기존 라벨 축소/도움말 공백 복원/`미공개` hook/작전실 compact title 패치가 current ROM에서
    정상 작동함을 재확인한 것이다. 증거를 `docs/screenshots/user_report_triage_2026-06-28/`에 보존했다. 같은 확인에서
    `qa_visual_regions.py`와 `qa_part1_compact_help.py`는 PASS했다.
  - [x] 2026-06-28 E12 B8 DOWN16 현행 재시도 음성 기록:
    stale SHA `3e3bae33...` probe가 남겼던 `0x00B81F04/10/24/2C`
    (`하늘 용사`, `건 파이터`, `개전`, `과외수업`) 후보를 current SHA `f95a8573...`에서 다시
    `tools/prove_compact_display_mutation.py --append-nav-step press:DOWN:120` x16으로 검증했다.
    4주소 모두 null-control diff 0, mutation pixel diff 0이라 current route의 direct evidence로 승격하지 않았다.
    결과: `docs/screenshots/user_report_triage_2026-06-28/e12_b8_down16_negative_summary.json`.
  - [x] 2026-06-28 A2 CO 프로필 nav read-watch 2건 추가:
    같은 current SHA `f95a8573...`의 `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0`에서
    `DOWN,DOWN,DOWN`이 `0x00A295C0`(`대승`), `DOWN,DOWN,RIGHT`가
    `0x00A295D8`(`강타`)을 각각 34회 직접 읽는 것을 확인했다. 신규 영구 증거는
    `data/compact_display_read_watch_a2_profile_down3_current.json`,
    `data/compact_display_read_watch_a2_profile_right_current.json`이며,
    matrix read-watch probes는 current 21/stale 0, cases 43, hits/direct reads 280으로 갱신됐다.
    A2 target runtime/source proof는 1/36 -> 3/36이 됐다. 단, savestate 기반 read-watch라
    per-power visual layout 전수 proof는 아니며, 나머지 33개 A2 파워명은 계속 별도 route/증거가 필요하다.
  - [x] 2026-06-28 B84 AW1 CO 파워명 11/11 current read-watch + visual contact 확보:
    `temp/b84_aw1_power_select_probe_20260628/rec1_meter_100k/menu_open.ss0`에서 같은 row 2 파워 발동 route를
    쓰되, ROM/pointer table은 바꾸지 않고 live RAM의 rec1 CO id byte `0x0201ADBD`만 `0x00..0x0A`로 바꿨다.
    `0x08B3C254 -> 0x08B1C194 -> 0x08DF2B54[index] -> 0x08B3C184` 경로가 B84 target 11개
    (`기적/하이퍼수리/강타/설백/승리/저격/일도/탐색/번개강습/큰파도/메테오`)를 모두 직접 읽고,
    contact sheet에서도 11개 컷인 제목이 한글로 정상 표시된다.
    신규 영구 증거는 `data/compact_display_read_watch_b84_power_titles_coid_current.json` 및
    `docs/screenshots/b84_aw1_power_title_all_coid_2026-06-28/contact.png`다.
    matrix read-watch probes는 current 22/stale 0, cases 54, hits/direct reads 291로 갱신됐고,
    B84 target runtime/source proof는 1/11 -> 11/11이 됐다. 단, RAM-field near-fresh proof라
    자연 진행 route 전수 증명은 아니며, E12 전체는 A2/B8 잔여 때문에 계속 미완료다.
  - [ ] 2026-06-27 다음 실제 증거 확보:
    A2 `0x00A295AC/0x00A295C0/0x00A295D8` 3건, B84 파워명 11건, B8 작전명 13건은
    source가 current SHA에서 확정됐지만 A2는 3/36, B8도 13/459로 전체 중 일부에 불과하다.
    B8 유닛 상세/무기 상세/전투 데미지예측/실제 통신 대기문, A2 CO 프로필 다중 CO처럼
    target read가 강제되는 fresh 또는 near-fresh state를 확보한다. 목표는 `r0..r7` exact target address,
    source read hit, mutation diff, 또는 WRAM/VRAM/DMA write chain으로 "해당 override 주소 → 화면 타일" provenance를
    추가 확보하는 것이다. agy/codex 리뷰 지적대로 일반 대사 `0xA01970` 양성대조와 별개인 compact-renderer 전용
    positive control도 확보해야 한다. 단, Part1 작전실 B8 live-source read positive와 A2 CO profile direct read는
    확보됐고 B84는 RAM-field near-fresh read-watch + visual contact로 11/11 target source가 닫혔으므로
    남은 핵심은 Part2 HUD/B8 잔여/다중 A2 compact renderer 계열 양성대조다. 특히 A2는 savestate frames-only 음성이나
    representative screen current 캡처만으로 종결하지 않는다. fresh route, redraw가 보장되는 near-fresh route,
    target mutation diff, direct read-watch, 또는 WRAM/VRAM/DMA write chain 중 최소 1종 이상의 target-level
    양성 증거를 주소군별로 확보해야 한다.
- [x] E13 compact glyph dictionary 자동 생성/거버넌스 완료(2026-06-27).
  `tools/build_korean_full.py`가 `data/display_overrides.json`의 A2 36개/B84 11개 compact 표시명에서 ordered unique
  glyph set을 산출해 `0xA3B880/0xB842E8` 사전 override를 자동 주입한다. 하드코딩 사전 문자열은 제거했고,
  `qa_glyph_dictionary_tables.py`와 `audit_address_text_overrides.py`는 runtime-generated 주소 2개를 별도 검증한다.
  최종 SHA `d1cebfde9764606dcc3b7b3017fcfc8c2cc0faf30afa4e69568b604f5ae12854`, 배포 게이트 PASS.
- [x] E14 repointed 대사 구두점 변환 범위 감사/게이트 완료(2026-06-27).
  `tools/audit_repoint_punctuation.py --strict` 추가. repoint manifest의 2,084 relocated message/2,417 fixed line을
  실제 output free-space 바이트에서 검사해 ASCII comma 잔존을 hard fail한다. 첫 감사에서 payload에 ASCII comma 1,323개가
  남아 있어, `dialogue_repoint.py`의 재구성 후단 `_conv`가 fixed/non-fixed 라인 구분 없이 단일바이트 comma(0x2C)를
  `、`(0x8141)로 전역 변환하도록 수정했다. 재빌드 후 payload ASCII comma 0, fullwidth comma 1,887,
  source 권위 분포 address 277/B팀 dialogue 380/csv 304/dialogue 734/display 2/write_log 720.
  `qa_repoint_integrity.py` PASS(2,084 재배치, 문제 0). `verify_dist_integrity.py`에 repoint punctuation/integrity 게이트를
  추가했고 새 output/dist SHA `d8be8aaf…` 기준 전체 PASS. E8 residual visual evidence도 같은 SHA로 재캡처/동기화했다.
- [x] E15 Part2 프롤로그 `0xA01A5C/0xA01A70` 보고문 renderer RE/수정 완료(2026-06-27).
  추가 사용자 스크린샷 route에서 보이던 `각 사령관 모두 공격 준비 / 공격 준비를 끝낸 참입니다.` 중복은
  이 프롤로그 renderer가 인접 메시지와 `77 72` gap을 공유하고, 첫 질문 `0xA01A2C`만 free-space repoint될 때
  glyph/cache 상태가 다음 보고문과 섞이는 문제였다. `0xA01A2C/0xA01A5C`는 forced skip으로 repoint 대상에서 제외하고,
  포인터 `0xA357C0/0xA357C4`를 원래 in-place 주소로 고정한 뒤 span 단위 직접 패치 2개를 적용했다.
  결과 표시문은 `매크로 랜드 침공 작전은, / 어찌 되었나?`,
  `각 사령관 모두, / 공격 준비를 끝낸 참입니다.`이며 B팀 drift 0.
  증거: `docs/screenshots/part2_prologue_inline_renderer_fix_2026-06-27/aonly_filmstrip.png`,
  `focus_filmstrip.png`, `wait_stability.png`. 최종 SHA `11098045…` 기준 정적 QA/scene audit/UI editor CDP/roundtrip PASS.
- [ ] E16 Part1 compact 도움말 잔여 route/폭 모델 보강.
  2026-06-27 Claude/agy 리뷰 후속. SHA `dee641f7…`에서 mode/operation/single/link current fresh route
  30프레임은 직접 캡처했고 깨짐은 없지만, 진행도/잠금 해제 조건이 필요한 campaign/hidden/player-count 계열
  도움말 일부는 아직 최신 SHA에서 직접 화면 진입 증거가 없다. 남은 작업:
  - [x] Part1 compact 도움말 전용 정적 게이트 추가:
    `tools/qa_part1_compact_help.py`가 `0xDFA64A..0xDFA9E9` override 34개를 전수 검사한다.
    현재 ROM prefix가 `encode_fit()` 결과와 일치하는지, tail padding이 `00/20`뿐인지, active payload에
    1바이트 printable이 섞이지 않는지, 모든 row가 level 0인지, 보수 상한 24 half-cell 이하인지 확인한다.
    Claude 리뷰 후 보강으로 한글 코드 lead max `0xE2` 가드, full-slot row 직후 제어바이트 확인,
    `Counter()` 기반 unmapped 진단, current visual evidence count 핀도 추가했다.
    `verify_dist_integrity.py`와 `run_release_qa.py`에 hard gate로 연결했고, 현재 결과는
    target 34/issue 0/direct visual evidence metadata 22/missing direct visual 12이다.
  - [x] 2026-06-27 AW1 unlocked save route direct evidence 5건 추가:
    `tools/probe_part1_compact_help_reads.py`에 `--tempsav`와 `tempsav_part1_menu` 시작 모드를 추가해
    외부 AW1 진행도 save를 `loadtempsav` 후 coldboot 메뉴로 진입시켰다.
    `docs/screenshots/part1_unlocked_menu_help_2026-06-27/`에 전적/맵 디자인 도움말 contact와 4x crop,
    read-watch report, shop 도움말 contact/crop/report를 보존했다. 현재 SHA `dee641f7…`에서
    `0xDFA68C`, `0xDFA71B`, `0xDFA72E`, `0xDFA6E2`, `0xDFA6FB`가 직접 화면 source로 확인됐고,
    `qa_part1_compact_help.py` evidence count가 18로 상승했다. shop route는 AW1 8495-front tempsav에서
    `DOWN` x8 최종 프레임이 `워즈 코인으로`/`물건 살 수 있어`를 보여 주는 경우만 승격했다.
    raw watch에는 경유 메뉴 hit도 섞이므로 `shop_read_watch_report.json`의 `final_visual_targets` 두 주소만
    direct evidence로 본다.
    비 `싱글 대전`/`통신` Part1 submenu 라벨은 도움말 침범을 줄이기 위해 저프로파일 렌더로 교체했으며
    `qa_visual_regions.py`는 기존 `싱글 대전`/`통신` 특수 라벨 가시성을 보존한 상태로 PASS한다.
  - [x] 2026-06-27 current SHA top-level fresh single-session probe:
    Part1 모드 선택 화면을 한 mGBA 세션에서 DOWN 12회/UP 4회 이동하며 watch+frame을 동시 기록했다.
    결과 `0xDFA6AA/6CD/6E2/6FB/752/775/79A/942/95B/972/989`만 hit했고,
    E16 missing 16개는 새로 잡히지 않았다. contact는
    `temp/e16_fresh_mode_single_session_probe_20260627/contact.png`에 보존했다.
    따라서 `0xDFA64A/66B`를 포함한 잔여군은 단순 top-level cursor sweep가 아니라 잠금/진행도/하위 조건 route로 본다.
  - [x] 2026-06-27 사용자 추가 스크린샷 재대조 + unlocked route current probe:
    Downloads 7장 contact와 최신 증거를 다시 대조했다. 기존 신고의 `single_map ??????`는 current SHA
    `fb760c65...`에서 `미공개`로 닫혔고, 작전룸 긴 작전명/Part1 룰 원형 일본어/프롤로그 중복문도 기존 후속 수정 증거와
    일치한다. 추가로 AW1 8495-front `loadtempsav+reset` route에서 `DOWN` 1..10 및
    `DOWN` x6 -> 통신 하위 item 0..4 `A` probe를 current ROM으로 재실행했다. 결과 top-level/link route는
    이미 증거가 있는 `0xDFA68C/6AA/6CD/6E2/6FB/71B/72E/752/775/79A/942/95B/972/989/9AE/9C7/9DA/9E9`
    계열만 읽었고, 남은 16개와 교차 0이었다. contact:
    `temp/e16_probe_8495_front_down1_5_current_contact.png`,
    `temp/e16_probe_8495_front_down6_10_current_contact.png`,
    `temp/e16_probe_8495_link_items_current_contact.png`.
  - [x] unlocked Part1 mode carousel 도움말 뒤 격자 artifact provenance/수정:
    AW1 8495-front `DOWN` 1/3 화면에서 도움말 박스 왼쪽에 작은 검은/노랑/초록 격자가 남는다.
    OAM상 ROI를 덮는 OBJ는 idx 30, x=-4, y=100, 64x32, tile 504, pal 8이고 VRAM 1D 렌더는 `트라`
    option half다. 그러나 option text y-shift, `trial/campaign` 왼쪽 half blank temp ROM 모두 격자를 없애지 못했다.
    추가 temp ROM에서 option label palette를 11/12/13으로 바꾸거나 `trial/campaign` option block 전체를 blank 처리해도
    같은 격자성 블록이 남았다. blank ROM의 tile504 VRAM bytes는 0으로 바뀌었으므로 최소한
    `OBJ idx30/tile504` option glyph 단독 원인은 배제한다. 단, BG/tilemap 원인이라고 단정할 양성 증거는 아직 없다.
    원본 일본판 같은 mode sweep에서도 동일 ROI에 주황/검은 격자성 조각이 반복 노출되어 한글 패치 회귀가 아닌
    원본 메뉴의 투명 도움말 뒤 배경/라벨 합성으로 판정했다. 자산 패치 없음.
    관련 증거: `temp/e16_unlocked_artifact_oam_20260627/`,
    `temp/e16_blankleft_option_compare_20260627/crops.png`,
    `temp/e16_option_palette_tests_20260627/contact.png`,
    `temp/e16_option_blank_tests_20260627/contact.png`,
    `temp/e16_blank_oam_match_20260627/`,
    `docs/screenshots/part1_unlocked_original_baseline_2026-06-27/original_mode_sweep_contact.png`.
  - [x] 2026-06-27 Part1 campaign 처음/이어하기 도움말 direct evidence 4건 추가:
    2111-front `after_route.ss0`에서 `UP,A`가 `이어서 캠페인 / 진행 가능`,
    `UP,A,DOWN` 및 `UP,A,UP`이 `처음부터 캠페인 / 시작해요`를 최종 프레임에 표시했다.
    read-watch direct target은 `0xDFA7E2`, `0xDFA7FD`, `0xDFA80E`, `0xDFA829`이며,
    evidence count는 18 -> 22로 상승했다. `0xDFA83A/84D` hidden 후보도 같은 route에서 read-hit했지만
    최종 프레임에 표시되지 않으므로 direct visual evidence로 승격하지 않는다.
    증거: `docs/screenshots/part1_campaign_help_2026-06-27/`.
  - [x] 2026-06-28 사용자 추가 스크린샷 재확인 및 E16 잔여 route 추가 음성 probe:
    `~/Downloads`, Desktop, Pictures의 최근 스크린샷을 재확인했으며 새로 확인된 이미지는
    `docs/screenshots/user_report_triage_2026-06-27/download_contact.png`의 7장과 같은 계열이었다.
    current 증거에서 작전실 작전명 깨짐, `single_map ??????`, Part1 메뉴 라벨/도움말 침범, 룰 원형 일본어 잔존은
    각각 기존 수정 증거로 닫힌 상태다.
    E16 잔여 12개는 current SHA `fb760c65...`에서 추가 probe를 돌렸다. hidden/campaign 후보 state 27건
    frames-only watch, AW1 converted save 8개 top-level 120프레임 sweep, 3285 state default route 부분 33건,
    `DOWN×5,A,A` 맵/팀/SELECT/L/R 계열, VS continue 생성 시도 모두 direct visual evidence 0이었다.
    `0xDFA7BE`는 map/team 계열에서 read-hit가 나왔지만 최종 프레임에 `이어서 대전`이 보이지 않아
    evidence로 승격하지 않는다. player-count `0xDFA8AA/8CB/8EA/90A/926` hit도 0이다.
    agy 리뷰는 실제 VS suspend/continue save, hard campaign unlock/completed save, true player-count 선택 화면 또는
    AW2 free battle route 확보를 다음 후보로 제안했다. claude CLI는 timeout/`Execution error`로 실질 리뷰 결과 없음.
    음성 증거는 `docs/fail.md`, help renderer 인덱스 구조는 `docs/research.md`에 기록했다.
  - [x] 2026-06-28 E16 broad state scan + forced renderer smoke:
    Part1/AW1/E16/menu/single/link/campaign/freebattle 이름이 걸리는 `temp/**/*.ss0` 8,085개를 current ROM으로
    순차 로드해 `0x02000000+0x30` 메뉴 item code 배열을 덤프했다. active menu 후보 중 잔여 code 5/6/16..19는
    없었고, 유일한 code17 후보 `temp/final_original_vs_final_20260615/original_menu.ss0`는 active 길이 6 뒤 tail 값이었다.
    해당 state 직접 watch probe에서도 기존 visible 도움말만 읽혔고 잔여 target hit 0이라 false positive로 닫았다.
    별도로 temp ROM에서 Part1 compact help pointer table의 visible code(10/13/20/14/21/22/23)를 잔여 pointer로
    바꿔 실제 메뉴 redraw를 유도한 synthetic renderer smoke를 수행했다. 결과 잔여 12개
    (`0xDFA64A/66B/7BE/83A/84D/872/885/8AA/8CB/8EA/90A/926`)가 모두 화면에서 깨짐/클리핑 없이 렌더됐다.
    증거: `docs/screenshots/part1_compact_help_forced_render_2026-06-28/contact.png`,
    `report.json`. `tools/qa_part1_compact_help.py`는 direct visual 22/missing direct 12와 별도로
    synthetic render 12/render-missing 0을 hard gate로 보고한다.
  - [x] 2026-06-28 VS suspend save route로 `이어서 대전` direct evidence 확보:
    앞선 실패는 `DOWN×5`로 통신 메뉴에 들어간 잘못된 route였다. 올바른 single route
    `DOWN,A,A,A,A`로 전투를 시작한 뒤 전투 중 `SELECT -> A -> DOWN -> DOWN -> A`로 저장 확인창을 열고
    `예`를 눌러 SRAM을 만들었다. 이 save를 `loadtempsav+reset` 후 1편으로 진입하면
    single submenu 첫 항목이 `이어서 대전`으로 표시되고 read-watch가 `0xDFA7BE`를 잡는다.
    증거: `docs/screenshots/part1_vs_continue_help_2026-06-28/contact.png`,
    `read_watch_report.json`. `qa_part1_compact_help.py` direct visual evidence는 22->23,
    missing direct는 12->11, synthetic render는 12->11로 갱신했다.
  - [x] 2026-06-28 E16 menu-code writer RE + live-code injection smoke:
    agy/Claude 리뷰 공통 지적대로 입력 brute-force 대신 `0x0200002C..0x0200006B` write-watch로 Part1 compact
    menu builder를 역추적했다. 공통 writer는 `0x08B4AF50`이며, menu object는 `0x02000000+0x2F`
    cursor와 `+0x30+cursor` item code를 사용한다. fresh/current route의 active code는 top
    `[10,13,20,10,13,20]`, single `[14,14,14,14]`, link `[22,21,23,22,21,23]`,
    campaign 후보 `[4,3,4,3]` 또는 `[3,3,3,3]`로 확인됐다.
    pointer-table forced-render보다 강한 보조 증거로, current ROM의 live menu object에서 `+0x30` item code만
    `0/5/6/16..19`로 주입하고 실제 cursor 이동으로 help redraw를 유도했다. 이 방식은 pointer table을 바꾸지 않아
    실제 `code -> 0x08DFAAB8 pointer lookup -> help renderer` 경로를 사용한다.
    결과 남은 11개(`0xDFA64A/66B/83A/84D/872/885/8AA/8CB/8EA/90A/926`)가 모두
    화면에서 깨짐/클리핑 없이 표시됐다. 증거:
    `docs/screenshots/part1_compact_help_live_code_injection_2026-06-28/contact_primary.png`,
    `contact_player19.png`, reports 2종.
    후속 재실행으로 reports 2종을 current SHA `f95a8573...` 직접 캡처로 갱신했고,
    `qa_part1_compact_help.py`의 `carry_forwarded_live_code_report_count`는 2->0이 됐다.
    `tools/qa_part1_compact_help.py`는 direct visual 23/missing direct 11,
    synthetic render 11, **live-code injection 11**, render-missing 0을 hard gate로 검사한다.
  - [ ] 남은 direct visual route 확보:
    `0xDFA64A`, `0xDFA66B`, `0xDFA83A`, `0xDFA84D`, `0xDFA872`,
    `0xDFA885`, `0xDFA8AA`, `0xDFA8CB`, `0xDFA8EA`, `0xDFA90A`,
    `0xDFA926`은 아직 direct visual evidence가 없다.
    2026-06-27 추가 probe: 8495-front `UP` 1..8, 2111/2113/2954 front `after_route.ss0` 기본 입력,
    2111 campaign `A` 후 `DOWN/UP/A/B`를 current ROM으로 돌렸지만 missing 16과 direct target 교차 0.
    `loadtempsav+reset`으로 11186/2111/2112 front를 coldboot route에 넣는 방식은 일부 save에서 전투맵으로
    지나쳐 버려 help watch 0으로 판정되므로, front save는 `after_route.ss0` state route로만 신뢰한다.
    2026-06-28 추가 probe까지 반영하면 단순 top-level, 통신 하위, 맵/룰/팀 설정, SELECT/L/R 도움말 트리거,
    진행도 save sweep으로는 남은 12개가 보이지 않는다. 이후 `0xDFA7BE`는 VS suspend route로 닫혔고,
    나머지 11개는 live-code injection smoke로 renderer/code-lookup 안전성은 보강됐지만 real gameplay route direct
    evidence는 아니다. 다음 직접 증거 후보는 code0 VS 헤더, hard/hidden campaign unlock, 또는 메뉴 item code
    16..19가 활성화되는 진짜 player-count 화면이다.
  `qa_visual_regions.py` 또는 별도 harness에 Part1 campaign/hidden/player-count 도움말 진입 route를 추가하고,
  `0xDFA64A..0xDFA885` 중 미노출 문구를 fresh capture로 묶는다.
  `0xDFAxxx` 도움말이 0x20 공백을 안전하게 렌더하지 못하는 다른 renderer에서도 공유되는지 xref/read-watch로 확인한다.
  `single_map`의 `??????` UX 항목은 2026-06-27 전역 가나 remap 없는 국소 hook 방식의 `미공개` 표시로 닫았다.

## F. 하드웨어 (사용자/물리 필요)
- [ ] F1 실기(real GBA) 검증 — 플래시카트 부팅·주요화면. **자율 불가(하드웨어 필요)**.

---

## 완료 판정
- A·B·C 전부 닫고 `python3 tools/build_korean_full.py` 후 전 QA 게이트 PASS + scene 재캡처 critical 0
  + codex·agy 적대 재리뷰에서 신규 결함 0이면 /goal 달성. F1만 잔여로 사용자 통지.

### B2 CSV 손상 — 완료(2026-06-27): ROM benign 유지, source dirty 제거
- 정확 성격: 단순 length 손상이 아니라 **CSV 행병합/필드밀림/일본어·한국어 필드 오염**(주소가 ja/ko에 누출)이었다.
- 복구 원칙: `game_wars_found_texts.csv`의 원문/length를 구조 권위로, `temp/integrity_map.json`의 실제 `ship_ko`를
  출력 권위로 우선 사용했다. 현 CSV의 안전한 한글 필드는 보존하고, clean backup은 보조 근거로만 사용했다.
- 결과: 복구 전 `empty_len 36 + bad_len 203 = 239` → 복구 후 손상 0. CSV row는 17763→17758,
  234행 변경, malformed artifact 5행 제거, 신규 행 0.
- 검증: rebuild 후 `output/game_wars_korean_full.gba`, `final.gba`, `title_test.gba`가 모두
  `d96a7e13db4ceed1694cad6a7f6d39334a97ff59a75c84dfddde261c4eb810e9`로 이전과 byte-identical.
  `qa_csv_integrity.py --fail-on-rom-japanese`, `lint_translation.py --severity error`,
  `qa_text_fit.py`, `audit_scene_catalog.py --strict`, `verify_dist_integrity.py` PASS.
- 남은 부채: CSV와 스크립트 override의 권위 shadow 감사는 B4/E11/E14로 분리한다.
