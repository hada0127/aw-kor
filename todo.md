# AW Korean Patch 통합 TODO

이 파일 하나를 현재 진행 기준으로 사용한다. 완료 항목은 `docs/success.md`로 이전하고,
상세 증거·과거 로그는 git history와 `archive/todo_archive_2026-06-17.md`(2026-06-17 이전 무손실
스냅샷)에 보존한다. 이 파일은 지금 해야 할 작업과 완료 판단에만 집중한다.

---

# 🟢 /goal: 화면(scene) 기반 통합 UI 에디터 — 현재 최우선 (2026-06-17 시작)

> **사용자 /goal: 전체 계획 완수.** 게임 흐름(scene) 기반으로, 한 화면에 포함되는 텍스트·스프라이트를
> 한 번에 편집할 수 있는 단일 통합 편집기를 만든다.
>
> **요구사항 7가지**
> 1. 화면에서 편집할 항목 선택 → (화면별 다른 주소/네비로) **바로 그 화면 진입**.
> 2. 범위 선택 기본: **전체 / 1+2편 선택 화면 / 1편 / 2편**.
> 3. 세부 범위(인트로/시작화면/메뉴선택/캠페인선택/싱글모드선택 …)를 화면마다 태그, **게임 메뉴 순서**로 출력.
> 4. 기존 스프라이트+텍스트 에디터를 **하나의 scene 아래 포함 항목 일괄 편집**. 항목 선택은 **가운데**(좌측 메뉴 아님).
> 5. 편집 완료 시 **원본↔편집 미리보기 비교**. 미리보기 '적용' → **바로 패치**.
> 6. GNB 상단에서 **현재 상태 .gba 즉시 다운로드**.
> 7. 대사 편집: 줄당 **최대 출력 글자수 내에서만 입력**(한글 폭 정확 계산), **2줄=2칸**.

## 3자 교차 검증 합의 (claude + codex + agy, 근거: temp/{claude,codex,agy}_plan.md)
- **단일 통합 서버** `tools/scene_editor/server.py`(:8782, stdlib). 게이트웨이/iframe 아님(상태·빌드락·다운로드·캐시 분산 회피). 기존 :8780/:8781 2서버는 폐기 판단 전까지 유지.
- **정본** `data/scene_catalog.json` = 자동생성(`tools/build_scene_catalog.py`) + 수동보정(`data/scene_catalog_overrides.json`). 입력: screen_checkpoints(게임순 prefix) + sprites_index(classify/section/order_rank) + dialogue_groups(region/address). **미배정은 숨기지 말고 `99_unassigned_review` scene으로 100% 수렴**(누락 0 검증).
- **scope**: `all/shared_select/part1/part2`. `01/02/03/05 select` 계열은 shared_select로 묶되 화면명 분리. order=scene_id 숫자 prefix.
- **요구7 바이트 예산(codex 교정 채택)**: 한글=2B·전각공백=2B·검증된 ASCII=1B. **대사 슬롯 = `encoded_len ≤ slot_len`(빌드 NUL 미추가)**, 순한글 최대=`floor(slot_len/2)`. **canvas 프리뷰 주입만 NUL 필요** → `encoded_len+1 ≤ canvas_len`. 바이트=하드게이트, **픽셀폭=경고게이트**(renderer advance/실측 필요).
- **멀티라인**: dialogue_groups의 `{kind:newline}`(0x0A)로 visual line 분할 → N칸. **fragment별 `encoded_len ≤ member.slot`이 저장 최종권위**(멀티 fragment를 한 textarea로 합치면 슬롯 저장 깨짐). 자동 줄바꿈(렌더러 wrap) 화면은 RE 부족 → `line_layout.manual/max_px/max_lines` 수동보정.
- **요구5 적용**: 풀빌드 job(`build_korean_full.py`가 체크섬/hook/출력동기 책임) + 비동기 큐·polling. hot-patch(텍스트 슬롯 in-place)는 병목 확인 후 후속(별도 검증).
- **프런트**: 바닐라 JS 신규(기존 앱 작아 재구성이 이득). GNB(scope segmented + 검색 + dirty/build 상태 + .gba 다운로드) / 중앙상단 scene 카드(subtag chip, 게임순) / 중앙하단 포함항목 카드 / 우측 편집패널 / 미리보기 모달(원본·편집·빌드적용 3열, '적용' 버튼).
- **위험(3자 공통)**: ① scene 자동배정 오탐 → 수동 override 필수. ② canvas 1종뿐 → scene별 "실캡처 지원/미지원" 명시. ③ "정확한 글자수"=byte cap(저장안정)일 뿐 픽셀폭 아님 → 과장 금지.

## Phase 0 — 재계획 + 완료 항목 이전 ✅ 완료
- [x] 기존 todo.md 완료 항목 457건 → `docs/success.md` 이전, 무손실 스냅샷 `archive/todo_archive_2026-06-17.md`.
- [x] claude/codex/agy 3자 독립 계획 + 교차 검증 → 본 todo.md 확정.

## Phase 1 — scene_catalog 토대 ✅ 완료
- [x] `tools/build_scene_catalog.py` 작성: 게임순 큐레이션 20 scene 정의 + skeleton 생성.
- [x] 스프라이트 후보 배정(source_contains 토큰): 112 텍스트 스프라이트 배정.
- [x] 대사 후보 배정(region + addr_ranges, font 제외): **9063/9063 그룹 100% 배정**.
- [x] `data/scene_catalog_overrides.json`(add/remove 수동보정) 로드 구현 + 스텁.
- [x] `99_unassigned_review` 생성 + 미배정 count 노출(비-scan 미배정=FONT_BASE 글리프 1뿐, scan_lz77 1874=비텍스트).
- 완료기준: `data/scene_catalog.json`(20 scene+review) 생성, count 출력, 대사 100% 배정 ✓.

## Phase 2 — 단일 서버 read-only MVP ✅ 완료
- [x] `tools/scene_editor/server.py`(:8782) + 기존 두 서버 모듈 importlib 재사용(중복구현 0).
- [x] `GET /api/state`(dirty/building/ROM sha·mtime), `/api/scenes?scope=&q=`, `/api/scene/items?id=&type=`.
- 완료기준: :8782에서 scope 필터별 scene·포함 항목이 게임 순서대로 조회됨 ✓(HTTP 검증).

## Phase 3 — 통합 UI 뼈대 (요구 1~4 탐색 흐름) ✅ 완료
- [x] GNB: scope segmented(전체/1+2편 선택/1편/2편) + 검색 + dirty/build 상태 + .gba 다운로드.
- [x] **레이아웃 재구성(2026-06-17, 사용자 정정 "LNB 목록 유지 + 우측 메인 편집", 미리보기 옵션A 선택)**:
  카드 그리드 → **좌측 LNB(게임순 scene 아코디언: 펼치면 포함 대사·스프라이트 항목) + 우측 메인(편집 화면)**.
  scene head 클릭=펼침/접힘(단일 펼침), 항목 클릭=우측 편집. 대형 scene는 렌더 상한+더보기, 썸네일 lazy.
- 완료기준: 요구1~4 탐색 흐름 동작(LNB scene→항목→우측 편집). index/css/app.js 서빙·문법·API 스모크 ✓.

## Phase 4 — 편집 기능 이식 (대사 + 스프라이트) ✅ 완료
- [x] 대사 line 저장(주소별 `dialogue_overrides.json`) + 사전검사(클라이언트) + dialogue_map 동기.
- [x] 스프라이트 픽셀 편집(canvas paint)·save/revert/setpalette(`sprites_overrides.json`).
- [x] **proper_nouns 통일사전 CRUD UI**(2026-06-17): GNB '📖 사전' → 모달(카테고리별 용어 add/edit/delete, DOM 입력), 서버 POST /api/dict. add→edit→delete 왕복 검증.
- [x] **요구7 "2줄=2칸" 확인**: dialogue_groups가 멀티-fragment 구조(줄바꿈=ctrl gap)라 각 fragment=한 줄·자체 슬롯 → fragment별 입력칸이 곧 줄별 칸. segments newline 6467/1533그룹 확인.
- [x] **스프라이트 onscreen WYSIWYG 뷰 통합(2026-06-17)**: 레이아웃 있는 스프라이트는 별도 모드 분리 없이 기본 타일그리드 자체를 실제 화면 출력 bbox 크기/OAM 배치와 실캡처 팔레트로 표시해 편집. 클릭 좌표를 visible bbox→OAM cell→tile pixel로 역매핑해 기존 `indices` 저장/빌드 경로와 호환.

## Phase 5 — 미리보기 + 적용(풀빌드 job) + 다운로드 (요구 5·6) ✅ 대부분 완료
- [x] 대사 preview 모달(원본 JA↔편집 KO 실캡처) + 스프라이트 orig/patched/edit compare 모달.
- [x] `POST /api/build`(비동기 job) + `GET /api/jobs` polling + 빌드 후 ROM 캐시 무효화 + 모달 '적용' 버튼.
- [x] `GET /api/download/gba` 다운로드(Content-Disposition, 16MB 헤더 검증) + 빌드 중 비활성.
- [ ] (잔여) 적용 직후 .gba SHA = output SHA 자동 검증(현재 수동), dirty→"적용 필요" UX 강화.

## Phase 6 — 요구7 입력 제한(바이트 예산 + 멀티라인) ✅ 대부분 완료
- [x] JS `encLen`(한글2/전각2/줄바꿈1/ASCII1) + 서버 `encoded_len` 동형. slot 예산 = `encoded_len ≤ slot`(NUL 미포함, codex 교정).
- [x] `\n` 분할 멀티라인 입력칸(+줄/−줄, 최대4) + 줄별/합계 바이트 인디케이터 + 초과 시 저장 차단(하드게이트).
- [ ] (잔여) 공통 `tools/text_metrics.py` 추출 + py↔js 일치 테스트, 2350 미수록 음절 차단(현재 hangul=2 추정).
- [ ] (RE) 인게임 대사 박스 셀 폭 실측 → 줄당 최대 글자수(현재 fragment slot 총량 권위).

## Phase 7 — canvas/nav 확장 (요구1 scene별 진입)
- [x] scene별 canvas 상태(ready/none) 카탈로그 노출 + UI 표시. 대사 preview는 scene canvas 사용.
- [x] **canvas 레지스트리 외부화**: `data/preview_canvases.json`(key→slot/len/render/nav/checkpoint), preview_capture `_load_registry()` 병합, build_scene_catalog가 canvas.checkpoint로 scene 매핑. 새 canvas=코드수정 0.
- [x] **캐시 키 버그 수정(codex)**: preview 캐시 키에 canvas sig(slot/len/nav)+base_rom(size:mtime) 포함(기존 name+text만 → nav/ROM 변경 시 stale).
- [x] **scene proof screenshot 연결(2026-06-17)**: `tools/capture_scene_screenshots.py` 추가. scene_catalog의 `screenshot.checkpoint`를 헤드리스 mGBA로 `temp/scene_screenshots/<checkpoint>_patched/frame.png`에 캡처하고 provenance 기록. UI LNB/scene 상세에 실제 캡처 썸네일 표시. 실제 game scene 28/28 캡처 존재(고유 checkpoint 16개, `99_unassigned_review`는 검토 bucket).
- [x] **merged scene 분리(2026-06-17)**: 20 scene+review → 29 scene+review(실제 game scene 28 + review 1). 1+2 선택 Part1/Part2, Part1 월드메뉴/싱글·맵 하위메뉴/통신 하위메뉴/작전로고/캠페인/전투, Part2 인트로 신문/블랙홀, 캠페인맵/미션타이틀, 전투라벨/OBJ라벨, 결과상태/요약 분리. source 중복 라벨은 `sprite_ids` 정확 배정으로 분리.
- [⏳] **part1 대사 canvas는 fresh-nav fragility로 보류**(6회 실측): 인트로 대사 자동진행→캡처 불안정, 안정적인 건 텍스트슬롯 없는 이름그리드뿐. 신뢰성 canvas는 **frame-sweep(대사창 비공백 프레임 선택) 또는 정밀 savestate** 필요(research.md 기록). 검증 안 된 canvas는 출하 금지(현재 part2_menu만 ready).
- [ ] (후속) frame-sweep 캡처 엔진 + part1 welcome/battle dialogue canvas 신뢰성 확보.
- 완료기준(수정): part2_menu 검증·정식 등록 / 레지스트리 외부화로 확장 경로 확보 / part1·battle은 frame-sweep 후속.

## Phase 8 — QA + 구서버 폐기판단 + dist + 커밋 ✅ 검증
- [x] **byte-identical 정합성**: 편집기 작업(도구/카탈로그/프런트만)은 빌드 무관 → output ROM sha **1623481a 불변** 확인.
- [x] 기능 parity: 통합 에디터가 구 2서버 편집 기능 포섭(대사 line/사전 CRUD/preview, 스프라이트 tile/render/compare/onscreen/save/revert/setpalette/build/download). 구 :8780/:8781 모듈 import 정상(폐기 전 유지).
- [x] 전 도구 py_compile + app.js node --check + 데이터 JSON 유효 + 3자 리뷰(codex/agy/워크플로) 반영.
- [x] **브라우저 검증(2026-06-17)**: Chrome headless CDP로 `http://127.0.0.1:8783` 렌더 확인. scene row 29, game scene screenshot 28/28(API), `1편 싱글/맵 하위 메뉴` 스프라이트 단일 타일그리드가 `타일 그리드 · 출력 크기 배치`로 표시, 모드 버튼 0개, raw layout 80×128/0,-96에서 실제 출력 bbox 80×32만 편집면으로 사용(canvas 240×96), cell별 팔레트 2개, 투명 픽셀 canvas 클릭 `0→6` 변경 확인. 증거 `temp/browser_verify/scene_editor_visible_output_grid.png`.
- [ ] (후속) dist 재생성은 ROM 변경 없으므로 불필요. 구서버 정식 폐기는 frame-sweep까지 완료 후 판단.
- 완료기준: scene editor 단독으로 편집·preview·apply·download 가능.

## 1차 구현 codex+agy 엄격 리뷰 반영 (2026-06-17)
**즉시 반영(critical/major)**: ✅ static 경로탈출 가드(resolve+containment, 직접 단위검증 4케이스) · ✅ 서버측 슬롯 예산 하드게이트(_save_line: encoded_len≤slot) · ✅ 2350 미수록 음절 차단(서버 `unsupported_syllables`+JS `/api/syllables` 셋, '믜' 등 저장불가) · ✅ 빌드중 다운로드 409 가드 · ✅ 빌드중 저장 차단(대사·스프라이트) · ✅ start_build 경합 락(이중 스레드 방지) · ✅ scope/section 교차 가드(part1_battle_day_banner의 part2 scene 오배정 차단→14_part1_campaign) · ✅ dirty=mtime기반(빌드후 깨끗) · ✅ slot미상/코드영역(<0x800000) 조각 read-only(빌드 skip 노출) · ✅ 프리뷰/비교 '적용'=현재 편집 저장 후 빌드(미저장 누락 방지) · ✅ 빌드후 SE 캐시(_OBJLABELS/_BUILD_LAYOUTS/_LAYOUTS/sprites) 무효화 · ✅ dirty 다운로드 confirm · ✅ build catalog dialogue add/remove override · ✅ lz77 재압축 skip 가능성 빌드후 경고.
**후속(Phase 6/8로 이관)**: ⏳ 빌드 권위 인코더(encode_fit)로 부호 정규화(…/스마트따옴표/▼/괄호) 길이 일치 · ⏳ 세그먼트(0x0A/변수삽입 0x33..0x30) 위치 보존·표시 멀티라인 · ⏳ render_png BytesIO 스레드안전 · ⏳ subtag chip 필터 UI · ⏳ /api/jobs job id.

## 2차 버그헌트 반영 (2026-06-17, 사용자 "모달 안 닫힘" 보고 → codex+agy+워크플로 5차원 감사)
- [x] **모달 안 닫힘(critical, 사용자 보고)**: 근본원인 CSS `#modal{display:flex}`(ID) > UA `[hidden]{display:none}` → `[hidden]{display:none!important}`로 항상 우선. (agy는 이 버그를 놓침, claude가 잡음)
- [x] **프리뷰 canvas 불일치(critical, codex 라이브 테스트 발견)**: scene.canvas에 checkpoint id(`07_part2_main_menu`)가 들어가 모든 scene이 "지원"인데 엔진은 `part2_menu`만 알아 전부 실패. → catalog가 checkpoint(게임순)와 canvas(preview_capture 키)를 분리, `canvas_status=ready`는 실제 지원 화면만(현재 22_part2_main_menu→part2_menu 1종), 서버 `_dialogue_preview` canvas 검증.
- [x] **agy 10건 직접 수정 반영**: 캔버스 mouseup 생명주기(mousedown 내부 등록), 멀티조각 프리뷰 readonly 누락(전 멤버 조립), readonly 사전검사 오진(fragTextFor readonly 처리), 입력칸 HTML 변조(DOM createElement), revert 목록 미갱신(items 재조회), 탭 전환 시 에디터 초기화, 빌드후 대사 캐시 무효화(DE._GROUPS_CACHE/groups/addr_slot), preview 디렉터리 가드, 검색 대소문자, mouseup 리스너 누수.
- [x] **워크플로 5차원 감사(43에이전트, critical 0/major 12/minor 13) 반영 완료**:
  - [x] **M1/M7/M8 모달 '적용'이 저장 실패에도 20분 빌드 강행**: saveDialogue/saveSprite가 실패=false·성공=true 일관 반환, modalApply 게이트 `if(!ok)return`(undefined 차단)+연타 disable.
  - [x] **M9 슬롯 출처 불일치(편집기 dialogue_groups vs 빌드 found_texts length, 49건)**: server가 `build_korean_full.load_slots()`(found length)를 권위로 사용(min), 0xA02F00=12 확정.
  - [x] **M10 DENY/PAIR 영역 편집 노출**: `deny_pair_status`로 DENY_REGIONS(font/테이블/노이즈)·PAIR_RENDERER 겹침 시 editable=False + _save_line 차단(font 저장불가 확인).
  - [x] **M6 빌드 락 1200s 점유**: `_run_build`가 _BUILD_LOCK은 상태변경에만, subprocess는 락 밖 → 빌드 중 다른 요청 응답.
  - [x] **M4 거대 스프라이트 per-pixel fillRect 프리즈**: drawSprite를 ImageData 1회+스케일 드로로 교체, 캔버스 변 1400px 상한(줌 연동).
  - [x] **M2/M5 대형 scene(3000행/1875썸네일) jank·폭주**: renderItems 렌더 상한 300+DocumentFragment+"더 보기", 썸네일 loading=lazy.
  - [x] **M3 멀티조각 부분저장**: 실패 시 이미 저장분 renderItems+부분저장 토스트.
  - [x] **M12 모달 재진입 시 적용버튼 잔존**: openModal에서 항상 disabled=true 리셋, 성공 시만 활성.
  - [x] 부수 minor: revert 재선택 순서(renderItems→select), api() HTTP 오류 처리+loadScenes/openScene try/catch, scene 연속클릭 경합 토큰, 모달 오버레이/Escape 닫기, 검색 0건 안내, render?which=edit 편집본 없으면 404, _sprite_save 차원검증, ROM 없을 때 썸네일 orig 폴백, dirty 문구 정정, 빌드완료 cry-wolf 경고 정밀화.
  - [ ] (후속) lz77 실제 재압축 fit 검증, 빌드 skip 구조화 리포트, S.supported await(현재 서버 하드게이트가 안전망).

## scene screenshot/WYSIWYG codex+agy 리뷰 반영 (2026-06-17)
- [x] `obj1d=false` 대비 로컬 tile index 변환(`localTileFor`) 추가. 현재 `data/sprite_layouts.json`는 obj1d=1만 존재하지만 향후 2D OBJ 레이아웃에서 `ty*32`를 compact grid에 직접 투영하지 않도록 방어.
- [x] onscreen hit-test를 2단계(보이는 픽셀 우선 → 없을 때 투명 셀 허용)로 수정해 겹친 투명 bbox 탈취와 투명 여백 편집 불가를 동시에 해결.
- [x] cell별 OBJ palette bank를 `/api/sprite/onscreen_data`의 `palettes`/`palette_key`로 내려주고, 프런트 렌더가 cell 팔레트를 적용하도록 수정.
- [x] 정적 scene screenshot 배경은 기본 45% dim + OAM cell bbox 마스킹 후 현재 스프라이트를 그리도록 수정. 배경 표시 토글 추가.
- [x] `/scene_shots/<checkpoint>.png` 정규식+basename+checkpoint allowlist + `Cache-Control: no-store` 적용. API `mtime` 쿼리 캐시버스터 유지.
- [x] scene screenshot provenance.rom_sha256 ↔ 현재 output ROM sha 비교로 stale 플래그/배지 추가. 캡처 도구는 기존 frame skip 전 provenance ROM SHA를 검증하고 불일치 시 재캡처.
- [x] 1편 하위 메뉴 merged 항목을 `12_part1_single_submenus`/`13_part1_link_submenus`로 분리하고 `43_part1_link` checkpoint를 실제 scene에 연결.
- [x] scope/search로 scene 목록 갱신 시 pending sprite 요청을 `_reqSeq++`로 무효화해 stale 응답이 우측 에디터를 되살리는 경합 차단.
- [x] `sprite_ids` explicit 배정 누락/중복 검증과 bucket 중복 방지 추가.
- [x] `capture_scene_screenshots.py`에 `MGBA_HARNESS`/`--harness` 지원, ROM/harness 존재 확인, 캡처 후 `frame.png`/`provenance.json` 생성 검증 추가.
- [x] agy 9건 + codex P2 5건 리뷰 반영 완료.

---

# 🟣 별도 트랙: 잔여(번역/QA/배포) — UI 에디터와 독립 (필요 시 진행)

> UI 에디터 /goal과 무관하나 보존하는 미완료 항목. UI 에디터 완수 후 또는 사용자 요청 시 처리.

- [ ] 전체 의미 audit(JA↔KO 전수 LLM 판정) — 숫자/부정 외 오역·의미축소·뉘앙스 색출(대규모).
- [ ] /goal #1 fresh-boot 화면 매트릭스 확대(전투/결과/저장/상점/엔딩) — 진행 SRAM seed/엔딩 도달.
- [ ] 미번역 1097종 triage(말줄임/중복/placeholder 제외 실대사·라벨) → 편집기로 번역.
- [ ] 표기흔들림 통일 결정·적용(국가명 붙임 vs 띄움 — **사용자 결정** 대기) + 구 export/apply_proper_nouns.py deprecate.
- [ ] VRAM 팔레트 캡처(0x05000000/0x05000200)로 스프라이트 실제 색 + raw OBJ 블록 추가 커버.
- [ ] qa 도구 진실화(ROM 슬롯 디코드 대조로 재설계), 영어 ASCII UI 잔존 전수 도구, 부호 4경로 픽셀 검증.
- [ ] dist 최종(Phase F): 모든 ROM 변경 완료 후 BPS/IPS+manifest 재생성, 구 tracked preview 패치 git rm 정리.
- [ ] CSV 권위 단일화(inline 리터럴 ~6749 → overrides.tsv 분리) — 선택/유지보수.
- [ ] 스프라이트 OBJ 직접기록 4종(action_menu/status_header/info_screen_obj/battle_obj) WYSIWYG.
- [ ] 캡처 지연(~30-60s/대사) 단축: 슬롯 nav 단축 canvas + orig 캡처 영구 캐시.

---

## 문서 규칙
- 진행 기준은 이 파일 하나. 완료=`docs/success.md`, 실패/dead-end=`docs/fail.md`, RE 사실=`docs/research.md`.
- 작업 완료/막힘 시 codex + agy 엄격 리뷰(`temp/review_prompt.md` → 병렬 실행).
