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

## B. 데이터 무결성
- [x] **B1 CSV 손상 ROM-진실 검증 완료**: `qa_csv_integrity.py`를 출하 ROM 디코드 기반으로 재작성.
  CSV 손상 239행이나 **출하 ROM 실제 일본어 텍스트 잔존 0**(빌드 inline 리터럴 권위; 109행 디코드 = 한글61/혼합26/노이즈22).
  `--fail-on-rom-japanese` 게이트 PASS + 배포 게이트 연동. (codex 보강 필요: 손상행 한정 40B 디코더 → 전수 디코더로 확장)
- [ ] **B2 CSV length-only 손상 239행 소스 위생 복구**(ROM 무해지만 정본 부채): 정수 length·꼬리잘림 복구.
- [x] **B3 container residual scan 현재 SHA 재생성 + 감사 하드닝 완료(2026-06-26)**:
  `tools/reverify_scene_residual_scans.py` 추가. 기존 raw 가타카나 blanket-pass를 폐기하고
  `game_wars_found_texts.csv` 추출행 + `qa_japanese_residuals.py`의 covered/same-original 판정 재사용.
  raw kana는 별도 observation으로 남기며 설명 없는 항목은 `audit_scene_residual_scans.py --strict`가 critical 처리.
  현재 SHA `7e79670c…` 기준 13 container/2881 dialogue, residual/evidence case 14, hit 0, critical 0. `verify_dist_integrity.py`
  배포 게이트에도 연결. E8 시각 evidence까지 포함한 residual audit는 case 14/hit 0/critical 0.

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
  Chrome CDP 63 scene/107 sprite 열람 failure 0. `tools/verify_scene_editor_roundtrip.py`로
  :8782 라이브 API 기준 78 scene/10,336 dialogue group/1,990 sprite/23,374 editable member dry-run failure 0,
  B팀 3,260 member confirm dry-run failure 0/skip 0. 대표 실제 저장/원복 2건(일반 0x00DFA5E6, B팀 0x00DFA616)
  성공. direct script 확장-span 대표 0x00D8FD26는 실제 저장→임시 ROM 빌드→build slot 44 < direct slot 52 조건에서 span 바이트 대조 성공. 테스트 후 편집 파일은
  실행 전 해시로 원복.

## D. 에디터/QA 폴리시 (Phase 6~8 잔여)
- [x] D1 공통 `text_metrics.py` 추출 + py↔js 일치 테스트, 2350 미수록 음절 차단 일원화 완료(2026-06-26).
  `text_metrics.syllable_set()`/`unmapped_syllables()`/`has_unmapped_syllables()`를 추가하고,
  `qa_text_fit.py`, `lint_translation.py`, `scene_editor/server.py`, `verify_scene_editor_roundtrip.py`가 공통
  `encoded_len`/2350 음절 권위를 쓰도록 전환했다. `lint_translation.py`는 빌드의 `encode_fit`/direct script span/
  dialogue override overlay를 반영하며, B팀 baseline byte-budget은 `qa_bteam_drift.py`/repoint 게이트로 위임한다.
  검증: `tools/test_text_metrics.py` py↔js 25,296 코퍼스 PASS, `lint_translation.py --severity error` 0건.
- [ ] D2 인게임 대사 박스 셀 폭 실측 → 줄당 최대 글자수(현재 fragment slot 총량 권위).
  - [x] 2026-06-26: `tools/qa_pixel_width.py` 정적 근사 범위를 빌드 입력원에 맞춰 확장.
    `dialogue_overrides`/직접 패치 텍스트/
    `ADDRESS_TEXT_OVERRIDES`/`SOURCE_TEXT_OVERRIDES`/`translation_comprehensive.csv` fallback/`encode_fit(addr)`/
    DENY/placeholder를 반영하고, 최종 encoded half-cell 폭 + scene 힌트를 출력한다.
    현재 `qa_text_fit.py` overflow 0, `qa_pixel_width.py` 기준 story/dialogue 계열의 `>50` 행은 관측되지 않았다.
  - [ ] 남은 `final encoded cells > 50` 후보 13개는 대사문이 아니라 메뉴/도움말/CO 파워명/공통 UI 테이블 계열이지만,
    UI별 허용폭은 50셀보다 좁을 수 있으므로 **블로커 후보**로 취급한다.
    (`temp/dialogue_box_width_over_max.tsv`: `0xD81C24`, `0xA3B880`, `0x804FD4`, `0x805B04`,
    `0xD83278`, `0xD83138`, `0x94298C`, `0x97AE40`, `0x9B36E4`, `0x9EBF88`, `0xEFAAD4`,
    `0xD721B5`, `0xB842E8`). 각 scene fresh capture와 UI별 max-cell 산정으로 실제 줄분리/테이블 렌더/
    클리핑 여부 확인 전 D2 완료 금지.
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
  report ok/skipped 0, output 3종 SHA `7e79670c…` 유지.
  추가로 claude/agy 리뷰 지적 반영: `문자 깨짐`/`[문자 깨짐]`/`해독·번역·판독 불가(문자 깨짐)` sentinel은
  `PLACEHOLDER_KO` skip으로 원본 보존. 고주소 sentinel 8행(0x009411A5..0x009EB69E)은 원본==출력 바이트로 확인.

## E. 백로그 (독립 트랙 — 결함 0 달성 후/병행)
- [ ] E1 전체 의미 audit(JA↔KO 전수 LLM 판정) — 오역·의미축소·뉘앙스.
- [ ] E2 fresh-boot 화면 매트릭스 확대(전투/결과/저장/상점/엔딩).
- [ ] E3 잔여 미번역 triage(제어마커/slot overflow/no group 자동제외분 수동검수).
- [ ] E4 표기흔들림 통일(국가명 붙임/띄움) + 구 apply_proper_nouns.py deprecate.
- [ ] E5 VRAM 팔레트 캡처(0x05000000/0x05000200) 스프라이트 실색.
- [ ] E6 CSV 권위 단일화(inline 리터럴 → overrides.tsv 분리).
- [ ] E7 캡처 지연 단축(슬롯 nav 단축 canvas + orig 캡처 영구 캐시).
- [x] E8 `88_common_comm_labels` raw 단일 `ソ`(0x00EE22AC) 실제 UI 노출 재확인 완료(2026-06-26).
  현재 SHA 관련 통신/공통 메뉴 캡처 7장 수동 시각검사에서 visible `ソ` 0. fresh/ground-truth 4장은 primary,
  Part1 stale_state 3장은 보조 증거로 분리했다. 기존 1967-case menu/focus/row 동적 스캔 hit 0 원본은
  `data/scene_residual_reverify/88_common_comm_labels_dynamic_scan_results.json`에 보존. `data/comm_label_visual_reverify.json`을
  residual manifest에 연결했고 audit가 리포트/PNG/provenance/primary-stale 역할/보조 scan SHA까지 검증한다.
  `audit_scene_residual_scans.py --strict` 결과 case 14/hit 0/critical 0.

## F. 하드웨어 (사용자/물리 필요)
- [ ] F1 실기(real GBA) 검증 — 플래시카트 부팅·주요화면. **자율 불가(하드웨어 필요)**.

---

## 완료 판정
- A·B·C 전부 닫고 `python3 tools/build_korean_full.py` 후 전 QA 게이트 PASS + scene 재캡처 critical 0
  + codex·agy 적대 재리뷰에서 신규 결함 0이면 /goal 달성. F1만 잔여로 사용자 통지.

### B2 CSV 손상 — 재분류(2026-06-24, codex 반영): ROM benign, source dirty(load-bearing 필드부패)
- 정확 성격: 단순 length 손상이 아니라 **CSV 행병합/필드밀림/일본어·한국어 필드 오염**(주소가 ja/ko에 누출). codex 지적.
- **ROM benign**: qa_csv --fail-on-rom-japanese=0, 185행 한글 정상 렌더. 빌드는 손상행도 import해 한글 출력.
- **부패가 load-bearing**(검증): ①length 교정 ②ko 비움(18 회귀) ③ja-clean 모두 SHA 변경 → 빌드가 손상 ja의
  len을 fallback 슬롯길이로, ko를 렌더소스로 사용. 단순 필드패치는 byte-identical 불가(검증 ROM 회귀).
- **안전 클린 경로**(codex): 행별로 정본 ja(found_texts)+ko(authoritative)+length 재구성 후 **rebuild byte-identical
  (b27ba3d) 검증** 필수. 239행 deep 재구성(B1식, B1은 109행 완료) = 다세션. ROM은 이미 정확하므로 source 위생은
  비차단 부채. 현 상태 정직 분류: **ROM 결함 0, CSV source dirty(deep-clean 대기)**.
