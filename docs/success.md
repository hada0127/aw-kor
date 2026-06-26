# Success Log — 작동 검증된 방법·산출물

> 사용자가 향후 참조하기 위한 **실제로 작동한 방법 모음**. 모순·실패 사유는 [fail.md](fail.md) 참조.

---

## 화면(scene) 기반 통합 UI 에디터 — Phase 0~3 (2026-06-17)

기존 분리 편집기(대사 :8780 / 스프라이트 :8781)를 게임 흐름(scene) 기반 단일 통합 편집기로 재설계.
claude/codex/agy 3자 독립 계획 → 교차 검증(temp/{claude,codex,agy}_plan.md) 후 구현.

- **scene_catalog**: `tools/build_scene_catalog.py` → `data/scene_catalog.json`. 게임 흐름순 큐레이션
  20 scene(공통/선택/1편/2편 scope, subtag=인트로/시작화면/메뉴선택/캠페인선택/전투/결과/대사…) +
  자동배정(스프라이트=source_contains 첫매칭, 대사=region+addr_range) + 미배정 `99_unassigned_review`로
  **100% 수렴**. 결과: 대사그룹 9061/9061 배정, 텍스트 스프라이트 112, 미배정=scan_lz77 1874(비텍스트
  그래픽)+FONT_BASE 글리프 1(편집 대상 아님). 수동보정 `data/scene_catalog_overrides.json`(add/remove).
- **통합 서버**: `tools/scene_editor/server.py`(:8782, stdlib). 핵심 = 기존 두 서버를 `importlib`로
  모듈 로드(`DE`=dialogue_editor, `SE`=sprite_editor)해 helper 재사용 → **중복 구현 0**, 기존 서버 유지.
  API: `/api/state`(ROM sha·dirty·build) · `/api/scenes?scope=&q=` · `/api/scene/items?id=&type=` ·
  `/api/dialogue/{line,preview}` · `/api/sprite/{tile,render,compare,onscreen_data,save,revert,setpalette}` ·
  `/api/build`+`/api/jobs`(비동기 풀빌드 job) · `/api/download/gba`(현재 ROM 전송). HTTP 전수 검증.
- **통합 프런트**(`static/{index.html,style.css,app.js}`, vanilla JS): GNB(scope segmented 전체/1+2선택/
  1편/2편 + 검색 + dirty/build 상태 + ⬇ROM 다운로드 + 적용(빌드)) / 중앙 scene 카드 그리드(게임순,
  subtag chip) / scene 상세 중앙 항목 리스트(좌측 메뉴 없음, 대사·스프라이트 탭) / 우측 편집 패널 /
  미리보기 모달(원본↔편집 + '적용' 버튼).
- **요구7(바이트 예산+멀티라인)**: JS `encLen`(한글2/전각공백2/줄바꿈1/ASCII1) = 서버 `encoded_len` 동형.
  **대사 슬롯 권위 = `encoded_len ≤ slot`(NUL 미포함 — 빌드는 [addr,addr+slot)만 기록, codex 교정)**,
  순한글 최대 = `slot//2`. `\n` 분할 멀티라인 입력칸(+줄/−줄, 최대4) + 줄별/합계 바이트 인디케이터 +
  초과 시 저장 차단(하드게이트). slot(=ROM 슬롯 바이트길이)은 dialogue_groups member 필드.
- **검증**: `python3 -m py_compile`(서버) + `node --check`(app.js) + HTTP 스모크(정적 서빙, scene/state/
  items, 스프라이트 render PNG 768×48, 다운로드 Content-Disposition·16MB, scope 필터). 기존 ROM·QA 무변경
  (이 작업은 도구/카탈로그만 추가, 빌드 산출물 불변 sha 1623481a).

재현: `python3 tools/build_scene_catalog.py && python3 tools/scene_editor/server.py`(→ http://127.0.0.1:8782).

## 2026-06-17 — 전투 시작 회전/개시 오버레이 UI 에디터 보강

**결과**: 2편 전투 시작 시 노출되는 `전투개시!` 배너와 회전/아핀 변환 소스 블록을 별도 scene
`26a_part2_battle_start_overlays`로 분리했다. LNB는 raw 타일시트 대신 출력배치 썸네일을 사용하고,
우측 편집 화면은 `0xC10B34`를 원본 256×16 타일시트가 아니라 실제 OBJ 출력 128×32로 재조립한다.

**구현**: `tools/sprite_editor/server.py`에 2편 빌드 기반 레이아웃 fallback을 추가했다. 적용 범위는
미션/전투 시작 타이틀 3개(128×32), 전투 시작 회전 소스 9개(256×40/24/8), 결과 축하 타이틀
`0xBFB45C`(128×51)이다. `tools/build_scene_catalog.py`는 전투 시작 장면을 별도 분리하고,
기존 전투 라벨 장면에는 체크/데미지 예측 라벨만 남긴다.

**검증**: `py_compile`, `node --check`, API `onscreen_data` 전수 확인, 배정 스프라이트 112개 감사
실패 0(onscreen 94, raw fallback 18), Chrome headless CDP 브라우저 검증. 증거:
`temp/browser_verify/8782_battle_start_overlays_scene.png`,
`temp/browser_verify/8782_battle_start_editor.png`,
`temp/browser_verify/assigned_sprite_audit.json`.

## 2026-06-07 — Low-address UI `未設定` 잔여 제거

**결과**: 기본 import pass가 건너뛰는 `0x800000` 미만 UI 테이블의 `未設定` 잔여를 `미설정`으로
교체했다. 출력 ROM에서 `未設定`, `サクテキの設定`, `テンキの設定` SJIS 원문 검색은 모두 0건이다.

**구현**: `tools/build_korean_full.py`의 low-address 직접 패치 경로에서 `0x5A3768` 6바이트 슬롯을
`미설정` 예약코드로 덮는다. 같은 테이블의 `0x5A375F` `코멘트` 패치와 인접한 UI 문자열이다.

**검증**: `py_compile`, `qa_text_fit.py`(`overflow=0`, `level1~5=0`), `qa_japanese_residuals.py`
`--min-score 13` candidate 0, low-address range `0x5A3000:0x5A4000` 재스캔에서 `未設定` 제거,
`qa_placeholder_residuals.py` ROM placeholder 0, `phase6_basic_test.py` full/final/title_test,
`prepare_patch_distribution.py` round-trip, `git diff --check` 통과. 세 ROM SHA-256은
`c09cc09ac8d724c35b1bd5c5869bdba2e07e8f785b09f663251d0627da6c5feb`.

## 2026-06-07 — Part 1 튜토리얼 full 정보창 `SPEC`/`WEAPON` fresh-run 해소

**결과**: Part 1 튜토리얼 전투 full 정보창에서 즉시 보이는 영어 `SPEC`/`WEAPON` 잔여를 제거했다.
콜드부트 실제 입력 라우트 증거는 `temp/fresh_part1_fullinfo_cold_route_after_spec_patch_20260607/sheet.png`
및 최종 프레임 `42_R.png`다. 상단 라벨은 `정보`, 무기 구역은 `무기`로 표시된다.

**작동한 라우트**: 콜드부트 → 이름 `A` 확정 → Part 1 튜토리얼 전투 기준점(`A x120`) → 첫 보병
`LEFTx4 DOWN A`, `RIGHTx3 A`, 대기 → 두 번째 보병 `LEFT UP UP A`, `RIGHTx3 A`, 대기 → `B -> R`.

**구현**: `tools/build_korean_full.py`의 `patch_part1_full_info_spec_obj_label()`이 LZ77
`0xBC7C00` decompressed tile 0~3을 `정보`로 교체한다. 기존 Part 1 info BG `WEAPON` 5개 LZ77
변형은 `patch_part1_info_screen_bg_labels()`의 `무기` 렌더로 유지된다.

**검증**: `py_compile`, `qa_text_fit.py`(`overflow=0`, `level1~5=0`), `qa_japanese_residuals.py`
`--min-score 13` candidate 0, `qa_placeholder_residuals.py` ROM placeholder 0, `phase6_basic_test.py`
full/final/title_test, `prepare_patch_distribution.py` round-trip, `git diff --check` 통과.
세 ROM SHA-256은 `7cbebd389e7a5cd19510c9e452e0ac4aa8609acaf16c4463e557340db62cad0b`.

## 1. 번역 데이터 (완료)
- **원본 추출**: ROM 텍스트 → `data/game_wars_found_texts.csv` (28,347행, 추출 노이즈 포함)
- **번역본**: `data/translation_for_import.csv` (address,japanese,korean,length — 한글 18,262행)
- **재인코딩 길이 타당성**: 17,774 한글 행 중 17,508행이 원본 바이트 예산 내(98.5%). 음절=2바이트, ASCII=1바이트 가정.
- **고유 음절**: 정확히 **1028개** (Galmuri11-Condensed에 100% 존재, 누락 0)

## 2. 한글 폰트 결정·자산
- **선택**: Galmuri11-Condensed (7×11 비트맵, 닌텐도 DS 폰트 기반)
- **이유**: 8x8 TTF 다운스케일은 받침 글자(한·받·글)가 검은 덩어리로 뭉개짐 → 픽셀 전용 폰트로 해결. 폭 7 ≤ 셀 8px이라 그대로 들어감.
- **라이선스**: SIL OFL 1.1 — 임베딩·수정·재배포 자유, 폰트 자체 판매만 금지. ROM 한글화 배포에 안전.
- **자산**:
  - `reference/fonts/Galmuri11-Condensed.bdf` (비트맵 원본)
  - `data/korean_glyphs_8px.json` — 1028 음절 사전렌더 (top,bot) 타일 hex
  - `tools/bdf.py` — BDF 파서
  - `tools/galmuri_cell.py` — 글리프 → 4타일(또는 8px top/bot) 변환

## 3. 인게임 한글 렌더 (단일 화면 검증)
**달성**: welcome 대화 "게임보이워즈에오신것을환영" 13음절이 원본 부팅 ROM에서 깨끗하게 한글로 렌더.

**산출물**:
- `output/welcome_korean.gba` — 정상 부팅(흰화면 아님, 0% bright 검증), 대화줄 한글 잉크 337px
- `dist/welcome_korean.bps` — 697바이트 패치, **적용 검증 통과**(원본+패치=타깃 일치, 385바이트 변경)
- 증거 스크린샷: `docs/screenshots/SUCCESS_korean_sentence_2026-05-22.png`, `partial_8px_inemulator_2026-05-22.png`, `dialogue_galmuri11_han_2026-05-22.png`

**작동한 정확한 파이프라인 (welcome 한정)**:
1. 텍스트(`0xDF8E16`)를 원본 길이 유지하며 16개 distinct 카타카나로 재작성 (`アイウエオカキクケコサシスセソタ`) → 타이핑/내비 타이밍 보존
2. cell K → top 슬롯 `42+K`, bottom 슬롯 `57+K` (실측·검증, 본 화면 한정)
3. Galmuri11-Condensed 11px 글리프 → **LANCZOS로 7×8 스케일**(행 잘라내기 금지: "이→ㅣㅣ" 왜곡) → top 4행 + bot 4행 분할
4. `0xB98000 + slot*32`에 32바이트 타일 주입
5. 헤더 체크섬 `(-(0x19 + sum(0xA0..0xBC))) & 0xFF`로 0xBD에 기록
6. BPS 인코딩(원본 → 타깃) → 검증 적용

## 4. 도구 체인 (작동 검증)
- **`tools/mgba_harness.c`** — libmgba 기반 헤드리스 디버거
  - 명령: `frames N`, `keys MASK`, `w8 ADDR HEX`, `dumpvram FILE`, `dumpmem ADDR LEN FILE`, `shot FILE`, `watchaddr ADDR LEN r/w/a LOG`, `watchfont BASE COUNT LOG`, `break ADDR LOG`, `quit`
  - 워치/브레이크 적중 시 r0-r7, sp, lr, pc, 주소, old/new 값 캡처
  - **핵심 fix**: 디버거 연결 시 `core->runFrame` 대신 `mDebuggerRunFrame(&dbg)`를 호출해야 BP 발화. 워치포인트는 runFrame로도 작동했지만 BP는 안 됐음 — 이 한 줄로 정공법 RE 길이 열렸음.
  - 빌드: `clang -O2 -I/opt/homebrew/include tools/mgba_harness.c -L/opt/homebrew/lib -lmgba -o /tmp/mgbah`
  - 실행: `DYLD_LIBRARY_PATH=/opt/homebrew/lib /tmp/mgbah <rom> [logfile]`
- **`tools/lz77_scan.py` + `tools/lz77_compress.py`** — GBA BIOS LZ77 코덱. Roundtrip 검증됨(605→605 on 0x228AC, 1152→1152 on 0xBB7A64). vram_safe=True로 disp≥2 강제.
- **`tools/make_bps.py`** — 최소 BPS 인코더(원본과 타깃 동일 크기). SourceRead/TargetRead 스팬. 적용 검증 통과.
- **에뮬레이터**: brew mgba 0.10.5 (`/opt/homebrew/bin/mgba`). VBA-M은 GPU 캡처 안 됨, mgba+screencapture 사용.

## 5. 렌더링 아키텍처 RE (관찰된 사실)
- **텍스트 = raw Shift-JIS** (예: welcome 대화 = ROM `0xDF8E16`).
- **텍스트 파서**: PC `0x08B11E48` / `0x08B1205A` (다단계 점프테이블 상태기계).
- **SJIS 2바이트 분기**: PC `0x08B1215A` (글리프 핸들러로 분기).
- **타이프라이터 렌더러**: PC `0x08B0FFF0` (첫바이트 high-nibble로 디스패치 테이블 `0x08D8263C` 인덱싱). 호출자 LR=`0x08B10020`.
- **BIOS LZ77 SWI thunk**: `0x08B7A878` (`svc #0x11; bx lr`) — 글리프가 LZ77 압축돼 BIOS로 VRAM에 해제됨.
- **IWRAM 폰트 복사 루틴 (상수 레이아웃용)**: PC `0x03006744` / `0x03006758`. r7=글리프 ROM 소스 주소, r6=VRAM 대상. 4bpp 픽셀별 **팔레트 리맵 변환**(값>임계 시 오프셋 가산) 적용 → VRAM 글리프가 ROM과 직접 매칭되지 않는 이유.
- **글리프 저장**: LZ77 압축 블록. 예: `0xBB7A64` (압축 899B → 해제 1152B = 36 타일, 해제 대상 VRAM `0x06003780`).
- **대화 텍스트 VRAM 위치**: `0x06003940`+ (VRAM diff로 확인).
- **카타카나 그리드 표**: `0x80505C` (83자, 슬롯 = 42+카타카나_고주온_index).

## 6. ROM 안정성·체크섬
- **체크섬 버그 수정**: 헤더 체크섬 = `(-(0x19 + sum(0xA0..0xBC))) & 0xFF` 를 0xBD에 기록. 이전 버그(0x19 누락)로 실기 부팅 거부했던 문제 해결.
- **삽입 길이 제한**: `tools/execute_phase5_4.py`에 `SAFE_MIN_ADDR = 0x800000` + 원본 슬롯 길이 제한. 인접 데이터 손상 방지.

## 7. AI 협업 가치 (Gemini)
Gemini가 제공한 구체적 기술 조언 3가지:
1. **VRAM write 워치포인트 + 점진적(per-char) 쓰기 패턴** → 타이프라이터 렌더러 식별 (실제로 0x08B0FFF0 발견에 결정적이었음)
2. **SJIS→glyph index는 보통 수식 `(Hi-off)*0x5E + (Lo-off)` 또는 LUT**
3. **전체화 전략 = allocator 하이재킹** (한글 폰트 추가 + 베이스포인터 patch). per-string 카타카나 재인코딩은 슬롯 부족으로 실패한다고 경고 — 실제로 정확함.

---

## 8. Welcome Dialog 완성 (v25, 2026-05-23)

**최종 ROM**: `output/welcome_1line_v25.gba`

**구성:**
- 1바이트 엔진 패치 불필요 (단일 라인이라 line 2 영역 reset 안 함)
- Hook A (40 bytes) @ 0x08A3CF14: dialog init 시 text addr 비교, EWRAM flag 설정
- Hook B (~140 bytes) @ 0x08A3D000: loop exit 시 flag 검사하고 line 1 tilemap + 글리프 데이터 작성
- BL trampolines at 0x8B129D4 (init) + 0x8B12798 (loop exit)
- Data: tilemap row 1+2 entries + 22 cells × 2 tiles glyph (= 1408 bytes) + A1B9 marker cell

**핵심 통찰:**
- 시스템 노란 ▼ 마커(0xA1B9 tile)를 행 2의 marker_cell 위치에 직접 배치 → 텍스트 끝에 자동 정렬
- 반각 띄어쓰기 (12px → 6px) 로 텍스트 압축
- 좌측 정렬 col 7 (= 첫 dialog cell)

**증거**: `docs/screenshots/SUCCESS_v25_system_marker_2026-05-23.png`

## 9. 원본 ROM 베이스 재구성 (v27, 2026-05-23)

**최종 ROM**: `output/v27_original_base.gba`

**핵심**: v14_tight font slot 패치 (0xB98000 영역) 제거 → 다른 화면 (name input grid 등)에 한글 잔재 없음. Welcome + name prompt 둘 다 hook B만으로 정상 렌더.

**산출물**:
- v14_tight 의존성 제거
- Dialog text 변경 minimal: welcome (0xDF8E16) + name prompt (0xDF8DB2) 모두 16 katakana로 시작 (engine ▼ 트리거)
- 그 외 모든 ROM 영역 원본 보존

## 10. SJIS→Slot 매핑 공식 발견 (B1-a RE, 2026-05-23)

**공식**: `slot_addr = 0xB984D0 + (sjis_low_byte - 0x41) * 0x10`

**검증 (자동화 스크립트로 캡처)**:
- ア (0x8341) → 0xB984D0
- イ (0x8343) → 0xB984F0
- ウ (0x8345) → 0xB98510
- エ (0x8347) → 0xB98530
- オ (0x8349) → 0xB98550

**도구**: `tools/find_katakana_slots.py` — 각 katakana SJIS 코드를 welcome dialog 첫 char로 치환 → 게임 실행 → blitter BP로 r7(ROM 소스) 캡처. 자동화된 SJIS→ROM 매핑.

**활용**: name input grid의 katakana 글리프 슬롯에 alphabet 글리프 주입 → grid 영문화

## 11. Name Input Grid 부분 알파벳 (v33, 2026-05-23)

**산출물**: `output/v33_alphabet_grid.gba`

**작동**: 첫 행 (ア-カ) 위치에 A-F 알파벳 정상 표시.

**제한**: 슬롯 stride 0x10 + 글리프 32 bytes 쓰기 → 인접 슬롯 (dakuten) overlap → 행 2+ 글리프 깨짐. 8x4 글리프(v34)는 sparse하여 가독성 낮음. 32-byte 글리프 + slot overlap 해결 필요.

## 12. 정확한 SJIS→Slot 매핑 + Name Input Grid 알파벳 표시 (v37, 2026-05-23)

**산출물**: `output/v37_grid_AZ_idx.gba`

**핵심 발견**:
1. **`tools/cell_to_slots.py`의 4-tile 공식이 정답**: 각 글자는 4개 타일 슬롯 (top_extra/top/bottom/bot_extra) 사용. 그리드 셀(8x16)은 top_extra(상단 8x8) + bot_extra(하단 8x8) 사용.
2. **SJIS lookup table at 0x08BE717A**가 진짜 매핑 소스. 게임 변종 SJIS 사용:
   - 표준 ツ=0x8362, 게임 테이블=0x8363
   - 표준 テ=0x8364, 게임 테이블=0x8365
   - 표준 ト=0x8366, 게임 테이블=0x8367
3. **테이블 idx 9-46이 그리드 셀**(ア,イ,ウ,...). 인덱스 순서대로 SJIS 코드 추출 후 cell_slots()에 넣으면 슬롯이 페이지 경계 빼고는 연속.

**검증**: 그리드 첫 2행에 "ABCDE" "FGHIJ" 정확 표시. 한글 dialog ("네 이름을 알려 줘") 유지.

**제한**: K-Z, 0-9는 화면 위치 매핑(tilemap)이 불완전. 모드 토글(hira/kata) RE 미완.

**도구**:
- `tools/cell_to_slots.py` — SJIS → 4-tile 슬롯 변환 (FONT_BASE=0xB974D0, SJIS_TBL=0xBE717A)
- `tools/build_grid_v37.py` — SJIS 테이블 인덱스 직접 추출하여 v27 베이스에 알파벳 주입
- `/tmp/mgbah` — 헤드리스 mGBA harness (frames/keys/shot/break)

## 13. 좌측 Name Input 그리드 알파벳 정상 표시 (v45, 2026-05-23)

**산출물**: `output/v45_grid_8x16.gba`
**스크린샷**: `docs/screenshots/SUCCESS_v45_grid_alphabet_2026-05-23.png`

**핵심 발견 (대규모 RE)**:
1. **그리드는 두 영역 분리**:
   - 좌측 메인 그리드 = cell_to_slots의 **top + bottom** 슬롯 (8x16 셀)
   - 우측 작은 패널 (1-9 + 작은 카타카나) = **top_extra + bot_extra** 슬롯
2. **이전 v37의 ABCDE는 우측 패널**에서 보였던 것 (오해)
3. 좌측 셀 N (idx 9+N) → top=128+N, bottom=144+N (page 0), 페이지 1+에서는 +32 stride
4. SJIS 테이블 (0x08BE717A) 인덱스 순으로 SJIS 코드 추출 후 cell_slots 사용해야 함

**검증 단계 (실험적 발견)**:
- v37: top_extra에 ABCDE → 우측 패널에 표시 (잘못된 가설)
- v38: 슬롯 288-511에 marker → 우측 패널만 영향 → 좌측 ≠ 288+
- v41: 슬롯 0-287에 'O' → 좌측 그리드 전체 'O' → 좌측은 0-287 범위
- v42: 슬롯 0-71에 alphabet → 좌측 안 바뀜 → 좌측은 72+ 범위
- v43: 슬롯 128-191에 'X' → 좌측 첫 32 셀 X → 좌측 메인 영역 = 슬롯 128-191
- v44: cell_to_slots의 top+bottom 페어로 알파벳 주입 → 작동 (작음)
- v45: 8x16 풀크기 글리프로 가독성 향상 → **완성**

**결과**:
- 좌측 그리드 5x5: ABCDE / FGHIJ / KLMNO / PQRST / U... 정확 표시
- 한글 dialog ("네 이름을 알려 줘") 유지
- 우측 패널 디지트 (01234/56789) 원본 유지

**도구**:
- `tools/render_8x16.py` — 8x16 풀크기 알파벳/숫자 글리프
- `tools/build_grid_v45.py` — SJIS 테이블 idx → cell_slots top+bottom 주입
- `tools/probe_bisect.py` — 슬롯 범위 이분탐색

## 14. 이름 입력 → NAME 박스 알파벳 표시 검증 (v45, 2026-05-23)

**스크린샷**:
- `docs/screenshots/SUCCESS_v45_name_C_input_2026-05-23.png` (C 입력 후)
- `docs/screenshots/SUCCESS_v45_name_5_digit_2026-05-23.png` (5 입력 후)

**검증**:
1. 그리드 셀 선택 → A 버튼 → 셀의 알파벳이 NAME 박스에 표시
2. 여러 글자 누적 가능 ("BLLL" 입력 시 모두 알파벳 표시)
3. 숫자 셀도 작동 (5 표시)

**핵심 통찰**:
- 그리드와 NAME 박스 모두 **같은 다이얼로그 폰트 슬롯** 사용
- 사용자가 "A" 셀 (실제로 ア=SJIS 0x8341) 선택 시:
  - 게임은 ア (0x8341) 코드를 name buffer에 저장
  - NAME 박스 렌더링 시 슬롯 128(top) + 144(bottom)에서 글리프 로드
  - 우리가 그 슬롯에 'A' 글리프 주입했으므로 → NAME 박스에 'A' 표시
- 이 원리로 **다음 화면 출력도 자동으로 알파벳** (별도 hook 불필요)
- 모든 katakana 사용 위치가 알파벳으로 표시되는 side-effect (전체 한글화 시 무관)

## 15. 이름 입력 OK 셀 navigation + 다음 화면 출력 검증 (v52, 2026-05-23)

**산출물**:
- `output/v52_dialog_alpha2.gba` — 그리드 + 다음 dialog 2개 (はじめまして, 私はキャサリン) 모두 distinct 카타카나로 패치
- `output/v51_dialog_alpha.gba` — v52 한 단계 전 (はじめまして만 패치)

**스크린샷**:
- `docs/screenshots/SUCCESS_grid_ok_navigation_2026-05-23.png` — 그리드에서 OK 셀에 커서
- `docs/screenshots/SUCCESS_v52_dialog1_ABCDEF_AGH_2026-05-23.png` — 다음 화면 dialog 1 ("ABCDEF [A] GH!", A=사용자 입력)
- `docs/screenshots/SUCCESS_v52_dialog2_ABCDEFG_2026-05-23.png` — 다음 화면 dialog 2 ("ABCDEFG.")

**OK 셀 navigation 시퀀스**:
1. 그리드 화면 진입 후 dialog "네 이름을 알려 줘" 추가 A 한 번 더 → 진짜 input mode (cursor 'A' 셀)
2. 글자 입력 후 OK 셀 좌표 = `DOWN×5 + RIGHT×10`
3. A 누르면 다음 화면 진입

**다음 화면 dialog 패치 패턴** (`tools/build_grid_v51.py`, `tools/build_grid_v52.py`):
- 0xDF8E3E "はじめまして" (12 bytes) → "アイウエオカ" → 우리 알파벳 슬롯 → "ABCDEF" 표시
- 0xDF8E4C 0x69 (name placeholder) 유지 → 사용자 입력 'A' 자동 삽입
- 0xDF8E4D "さん" (4 bytes) → "キク" → "GH" 표시
- 0xDF8E58 "私はキャサリン" (14 bytes) → "アイウエオカキ" → "ABCDEFG" 표시
- 전각 공백/!/. 유지

**검증 결과**:
- ✅ 그리드 좌측 알파벳 (ABCDEFGHIJKLMNOPQRSTUVWXYZ + 0123) 정상
- ✅ 그리드 dialog "네 이름을 알려 줘" 한글 정상
- ✅ 사용자 셀 선택 → A 입력 → NAME 박스 "A" 표시
- ✅ OK 셀 (D5+R10) → A → 다음 화면 진입
- ✅ 다음 화면 dialog 1: "ABCDEF [A] GH!" — 사용자 입력 'A' 정상 위치 표시
- ✅ 다음 화면 dialog 2: "ABCDEFG." — 캐서린 자기소개 깔끔 표시

**제한**: 다음 화면 dialog가 한글이 아닌 알파벳. 한글로 표시하려면 welcome v25처럼 hook A/B 확장 필요 (다음 단계).

## 16. Hook A/B 확장 + "처음 뵙겠습니다" 한글 overlay (v53, 2026-05-23)

**산출물**:
- `output/v53_korean_overlay.gba` — name input OK 후 다음 화면 dialog "처음 뵙겠습니다" 한글 표시
- `tools/build_grid_v53.py` — hook A 재작성 + hook B 확장 + 한글 glyph 데이터 빌더

**스크린샷**:
- `docs/screenshots/SUCCESS_v53_korean_overlay_2026-05-23.png` — "처음 뵙겠습니다 ▼" 한글 dialog

**Hook A 재작성** (0xA3CF14, 52 bytes code + 16 bytes data):
- 3-way dialog 비교: addr1=0xDF8E14 (welcome) → flag=1, addr2=0xDF8DB0 (name prompt) → flag=2, addr3=0xDF8E3C (hajimemashite) → flag=3
- 기존 2-way 구조 확장. Thumb 명령어 직접 인코딩 + PC-relative offset 재계산
- 데이터 word-aligned at 0xA3CF48 (addr1,addr2,addr3,flag_ptr)

**Hook B 확장** (0xA3D00E + 0xA3D086):
- 0xA3D00E의 `b SKIP` (0xE020) → `b FLAG3_CHECK` (0xE03A → 0xA3D086)
- @ 0xA3D086 새 핸들러: `cmp r0, #3; bne SKIP; ldr r4=0xA3D300; ldr r5=0xA3E000; b COMMON`
- flag=3 시 welcome의 row 2 tilemap 재사용 (▼ marker 포함) + 새 glyph 데이터

**한글 Glyph 데이터** (0xA3E000, 1408 bytes):
- 22 cells: "처음 (공백) 뵙겠습니다" (8 cells) + 14 blank cells
- 글리프 위치 재조정: Galmuri json 8px char를 16px 셀 중앙으로 shift
  - top tile: Galmuri top rows 0-3 → 새 top rows 4-7 (push 아래로)
  - bot tile: Galmuri bot rows 4-7 → 새 bot rows 0-3 (push 위로)
- 결과: char가 셀 중앙 (rows 4-11)에 위치, 가독성 좋음

**검증 결과 (v53_x3)**:
- ✅ 이름 입력 → OK → 다음 화면에서 "처음 뵙겠습니다 ▼" 한글 dialog 깔끔 표시
- ✅ Welcome (flag=1), name prompt (flag=2), hajimemashite (flag=3) 모두 한글
- ✅ 그리드 알파벳 (A-Z, 0-9) 표시 유지
- ⚠️ 그 다음 dialog "私はキャサリン" 미패치 (추가 hook flag=4 필요)

**기술 핵심**:
- BL trampoline (0xB129D4 → hook A, 0xB12798 → hook B)는 그대로 유지
- 모든 patch는 in-place + 새 데이터 영역 (0xA3E000)
- 체크섬: `(-(0x19 + sum(0xA0..0xBC))) & 0xFF`

---

## [2026-05-25] 무라마사 한글화 프로젝트 QA 도구 이식 (번역 품질 파이프라인)

`~/project/muramasa-kor`(PS Vita 오보로 무라마사, v1.0.0 성공 종료)의 번역 QA 방법론을
aw-kor CSV 포맷에 맞게 적응 이식. 상세·매핑: `docs/muramasa_reference/README.md`.

### 이식한 도구 (모두 `data/translation_for_import.csv` 기반, 실행 검증 완료)
- **`tools/lint_translation.py`** — 번역 품질 검수기. hex토큰누출/가나·한자잔존/바이트예산초과/
  글리프밖글자/부호공백 검사. Galmuri11-Condensed BDF를 글리프 소스로.
- **`tools/export_proper_nouns.py`** + **`tools/apply_proper_nouns.py`** — 같은 일본어가
  다른 한국어로 번역된 불일치 탐지 → 검토 → CSV 역적용 (용어 일관화).
- **`tools/fix_punctuation.py`** — 한국어 종결어미 분류표(무라마사 919줄에서 이식) + aw-kor
  안전 게이트(일본어 원문이 종결부호로 끝날 때만 미러링 → 메뉴 라벨 과잉부호 방지).

### lint 베이스라인 (2026-05-25, 18,262 번역행)
| 규칙 | 건수 | 의미 |
|---|---|---|
| **hex_token (error)** | **250** | 추출 시 포인터 주소가 번역에 새어든 손상 (`유0x00D9991D`). ROM 삽입 전 반드시 0으로. |
| byte_budget (error) | 1 | 재인코딩 바이트수 > length 예산 (삽입 손상) |
| jp_kana (warn) | 432 | 가나 잔존 (일부 추출 노이즈) |
| jp_kanji (warn) | 316 | 한자 잔존 |
| punct_space/bad_punct (warn) | 184 | 부호 공백·연속부호 |
| empty_budget (info) | 524 | length 비어 예산검사 불가 |

### 검증 결과
- **proper_nouns**: 첫 추출에서 **813개 용어 불일치** 발견. 예: `「もぐる」`(잠수 능력)이
  잠수/잠복/잠항 3종 혼용, `下のタイプのユニットに`가 유형/타입 혼용. apply CSV 라운드트립
  무결(18,767행·헤더·주소열 보존, 의도 행만 변경) 확인.
- **fix_punctuation**: ja 종결부호 8,371행 중 98.3%가 이미 한국어 부호 있음 → 보정 대상 1행뿐.
  **aw-kor 번역의 부호 품질이 이미 우수**하다는 검증이자, 도구가 라벨 139행을 올바르게 SKIP함을 확인.

### 다음 활용
- ROM 빌드 전 `python tools/lint_translation.py --severity error`로 hex_token 250행 + byte_budget
  1행을 먼저 해소(삽입 손상 직결).
- `export_proper_nouns` → 불일치 검토 → `apply`로 유닛/지형/CO명 용어 통일.

---

## [2026-05-25] 게임 용어 표기 통일 (사용자 결정 기반)

`tools/export_proper_nouns.py`가 같은 일본어→다른 한국어 814건 불일치 탐지. 분석 결과
대부분은 추출 문장 조각이라 블랭킷 통일은 churn 대비 이득이 낮고 품질 열화 위험(다수결/
최장 휴리스틱 모두 `없는 건 아니지만`→`건 아니지만` 잘림, `피해`→`데미지` 등 부작용 확인).
→ **무라마사식 "사람이 표준 결정"** 으로 전환: 전체 CSV 빈도가 비등한 핵심 게임 용어만 사용자
결정으로 전역 표준화.

### 적용 (common_terms 전역 치환, 304행)
| 일본어 | 표준(사용자 결정) | 통일 |
|---|---|---|
| マップ | **지도** | 맵 242 → 0 |
| ダメージ | **피해** | 데미지 33 → 0 |
| タイプ | **타입** | 유형 23 → 0 |
| マシンガン | **기관총** | 머신건 5 → 0 |
| もぐる | **잠수** | 잠복 2 → 0 (잠수함 능력) |

- '맵'(1자)→'지도'(2자)로 멀티플레이 맵 라벨 5행이 예산 1B 초과 → 공백 제거로 3건 '지도'
  유지, 예산 4~5B로 빠듯한 2건은 '맵' 유지. **lint error 최종 0건**, 레코드 18320 보존.
- 충돌 점검: '맵' 뒤 글자 전부 조사/공백(맵다·맵게 오탐 0), '잠복' 2행 모두 もぐる 문맥 확인.
- 조각 단위 불일치(685건)는 의도적 미적용 — 동일 원문이라도 미세 문맥이 달라 단일 통일 부적합.

---

## [2026-05-25] reflow_dialogs.py 이식 (박스 폭 줄바꿈, 향후용)

무라마사 `reflow_dialogs.py`의 DP 균형 줄바꿈을 CSV에 맞춰 이식. 마침표·쉼표 우선 분리 +
줄 폭 균형 분배. 폭=한글/전각 1.0, ASCII 0.5.

- `--test "문장"`으로 동작 시연 검증(긴 문장 → max-width 이내 N줄 균형 분배 확인).
- **현재 CSV에는 미적용**: aw-kor는 단일행 + 게임 타이프라이터 자동 줄바꿈이라 강제 개행
  불필요. max-width는 미보정 추정치(15)라 적용 시 1939행에 원치 않는 개행이 들어가 렌더·
  바이트수 손상 위험. → 향후 대사 박스 폭을 RE로 확정한 뒤 보정해 사용.
- condense_dialogs(greedy)는 reflow DP가 상위호환이라 미이식.

### 부수 확인: 멀티라인 33행은 손상이었음 (데이터 손실 0)
hex 복구 과정에서 사라진 "멀티라인 korean 33행"은 진짜 대사가 아니라 **원본 CSV의 따옴표
깨짐으로 여러 레코드가 한 필드에 뭉친 손상**이었다. 갇힌 주소 186개 중 184개가 독립 행으로
별도 존재, 나머지 2개(0x00D951BB/0x00A0B17C)도 갇힌 ko가 이미 hex/빈값 → **실제 번역 손실 0**.
collapse는 손상 정리였음.

---

## [2026-05-25] ROM 빌드 파이프라인 검증 — 체크섬·삽입 버그 해결 확인, 부팅 ROM 생성

CLAUDE.md(2026-05-21)에 "핵심 과제"로 적힌 체크섬·삽입 손상 버그를 점검한 결과,
**둘 다 이미 코드상 수정돼 있었고** 검증을 통해 확정했다.

### 검증 (output/game_wars_korean_final.gba)
- **체크섬**: `execute_phase5_5.py:21` = `(-(0x19 + sum(0xA0..0xBC))) & 0xFF` (올바른 GBATEK 식).
  검증: 0xBD=0x72가 식 계산값과 일치. 텍스트 삽입은 헤더(0xA0–0xBC) 무변경이라 0xBD 유효 유지.
- **삽입 안전**: `execute_phase5_4.py`는 EUC-KR 길이>orig_len이면 skip(2298건), 정확히 orig_len만
  clear/write, `SAFE_MIN_ADDR=0x800000` 미만(코드영역) skip. **검증: 코드영역(<0x800000) 변경 0바이트.**
- **부팅**: mgba 하네스(420프레임) 캡처에서 한글 ROM이 **원본과 픽셀 동일하게 부팅**(흰 화면 해소).
  헤더 유효, 크기 16MB 동일. → CLAUDE.md의 "흰 화면(부팅 실패)" 상태 해소.
- 재현: `python tools/execute_phase5_4.py && python tools/execute_phase5_5.py`,
  부팅확인 `printf "frames 420\nshot temp/b.raw\nquit\n" | DYLD_LIBRARY_PATH=/opt/homebrew/lib /tmp/mgbah <rom>`

### 폰트 구조 RE (이번에 확정)
- **그리드/메뉴 폰트(이름입력)**: `FONT_BASE=0xB974D0 + slot*32`에 **비압축**으로 존재 → 직접 주입 가능
  (build_grid의 A-Z/0-9 grid가 이 방식, 렌더 검증됨). 가나(ア 0x8341)도 여기 있음.
- **SJIS→슬롯 테이블 0xBE717A**: 5498 엔트리. 단 흔한 대화 한자 攻(0x8D55)/撃(0x8C82)은 **테이블에 없음**
  → 이 테이블은 대화 폰트 전체 인덱스가 아님.

---

## [2026-05-25] 🎉 PoC: FONT_BASE 직접 주입으로 대화 한글 렌더 성공 (hook 불필요)

리뷰가 우려한 "복사 지점 hook" 없이, **대화 글자가 쓰는 FONT_BASE 오프셋에 한글 글리프를
직접 덮어쓰면 대화가 한글로 렌더됨**을 인게임 검증.

### 방법 (재현 가능)
1. は 글리프 자리 `FONT_BASE+0x520` (파일오프셋 0xB979F0, top 0x20 + bot 0x20 = 0x40B)에
   galmuri "한" 글리프(`render_galmuri_8x16.render_char`, ink 인덱스 10) 주입.
2. 체크섬 재계산, `temp/poc_ha2han.gba` 저장.
3. mgbah 헤드리스 네비(타이틀→…→hajimemashite 대화)로 도달, 스크린샷.

### 결과
- 대화 "はじめまして アさん！" → "**한**じめまして アさん！" — 첫 글자 は가 한글 "한"으로 렌더.
- **색·위치 정상**(다른 글자와 동일 색, 검은 네모/색깨짐 없음) → 팔레트 포맷 일치 확인
  (원본 글리프 ink 인덱스 10 = galmuri ink 10).
- 증거: `docs/screenshots/SUCCESS_dialogue_korean_FONTBASE_injection_2026-05-25.png`

### 함의 (접근법 확정)
- 대화 한글화 = **FONT_BASE 오프셋에 한글 글리프 주입 + 텍스트를 해당 오프셋으로 매핑되는 SJIS
  코드로 인코딩**. ASM hook 불필요(그리드와 동일 메커니즘, 대화에도 적용됨).
- 남은 일: ① SJIS→offset 매핑 도출(안 쓰는 한자 코드→offset 선정) ② 1028 음절 글리프 주입
  ③ 번역문을 그 코드들로 인코딩 ④ 전 화면 커버리지 확인.

---

## [2026-05-25] 멀티음절 한글 PoC — "안녕하십니까" 대화 렌더 (full-width 간격 정상)

단일 글자 PoC를 확장: hajimemashite 대화의 "はじめまして" 6글자 자리(は,じ,め,ま,し,て의
FONT_BASE 오프셋 0x520/0xCC0/0x820/0x5C0/0x160/0x440)에 한글 6음절(안,녕,하,십,니,까) 주입.

### 결과
- 대화가 "**안녕하십니까** アさん！"로 렌더. 6음절이 x=44~102 (음절당 ~9.7px)에 **정상 간격**(겹침 없음).
- 이 가나 오프셋들의 advance가 full-width(~8-10px)라 한글이 겹치지 않음 → **full-width 코드(가나/한자)
  슬롯을 쓰면 한글 간격 정상**. (리뷰가 경고한 커서폭 문제: 좁은 advance 코드는 피하면 됨)
- 증거: `docs/screenshots/SUCCESS_dialogue_korean_multichar_2026-05-25.png`
- 미세 polish 여지: galmuri 세로 위치(rows 3-13)가 가나 baseline보다 약간 높음 — 추후 top_pad 조정 가능.

### 접근법 확정 (요약)
대화 한글화 = ① 안 쓰는 **full-width 코드**(한자) 1028개 예약 → ② 각 코드의 FONT_BASE 오프셋에
한글 글리프 주입 → ③ 번역문을 그 코드들로 인코딩. ASM hook 불필요. 남은 핵심: 코드→오프셋 매핑 확보.

---

## [2026-05-25] 🎉 Phase B PoC — 예약 코드 → 한자 테이블 → 한글 렌더 (프로덕션 메커니즘 검증)

PoC(기존 코드 글리프 주입)를 넘어, **프로덕션 경로**(안 쓰는 코드 예약 → 테이블 → 한글) 전체 검증.

### 방법 (재현 가능)
1. 예약 코드 **0x8AEF**(한자 테이블 0x08B814CA 엔트리, 원문 미사용 = repoint 후보) 선정.
   엔트리: stored=0xEF8A(byteswap), top_idx=0x048A(offset 0x9140), bot_idx=0x049A(offset 0x9340).
2. 그 글리프 자리(FONT_BASE+0x9140 top, +0x9340 bot)에 galmuri "테" 주입.
3. hajimemashite 텍스트 첫 글자 は(0xDF8E3E: 0x82CD) → **0x8AEF**(예약 한자 코드)로 rewrite.
4. 헤드리스 네비 → 대화 첫 글자 확인.

### 결과
- 대화가 "**테**じめまして アさん！"로 렌더 — 예약 한자 코드가 **한자 테이블 lookup**을 거쳐 내가 주입한
  "테" 글리프로 표시됨. **텍스트 rewrite 전파 확인.**
- 증거: `docs/screenshots/SUCCESS_dialogue_korean_RESERVED_code_2026-05-25.png`

### 함의 — 프로덕션 경로 완전 검증
이제 풀게임 대화 한글화의 모든 사슬이 입증됨:
**안 쓰는 SJIS 코드 예약(3326개 풀) → 한자 테이블 엔트리(repoint 13 + 확장) → 한글 글리프 주입
→ 번역문을 예약 코드로 인코딩 → 대화에 한글 렌더.** ASM hook 없이 데이터(테이블+글리프+텍스트)만으로 가능.
남은 건 1028 음절분 테이블 확장(끝 리터럴 0x08B8180C 갱신) + 글리프 배치 + 인코딩 + 커버리지(Phase A).

---

## [2026-05-25] SESSION 1 완료 — 글리프 블롭(800 dedup) + 배치 전략 확정 (커버리지·경계 RE)

### Phase C-1: 한글 글리프 블롭 ✅
- `python tools/build_korean_glyph_blob.py` → CSV 고유 음절 **1030개** → top/bot 타일 렌더 →
  **dedup 고유 800타일 = 25,600 bytes** (top 437 + bot 363, 겹침 0, empty render 0).
- 산출: `data/korean_glyph_blob.bin`(25600B, sha1 2f345701…), `data/syllable_to_glyph.json`(음절→로컬 top/bot idx).
- 로컬 idx 0-based. 실제 FONT_BASE idx = KOR_TILE_BASE + local_idx (배치 단계에서 확정).

### Phase A: 렌더 경로 커버리지 ✅(정적+동적)
- **번역 텍스트(대화/메뉴/유닛명)는 단일 변환루틴**(0x030065E0 / ROM 0x08EFE788)이 담당.
  veneer 0x08B1BEFC 호출자 정확히 2곳(0x08B1275E, 0x08B12B1A), 동적 167히트 전부 lr=0x08B1BF0D 단일.
- 별개로 **폰트 bulk DMA→VRAM 업로드 경로 2곳**(0xB11B54: 704타일, 0xB6A86C: 16타일) 존재 — 프리로드
  +타일맵 렌더(가나 입력 그리드/심볼). 번역 텍스트가 이 경로를 쓰는지는 잔여 확인 항목.

### 배치 전략 결정 (codex+gemini 리뷰 + 디스어셈블로 확정)
- 핵심 제약: 한글 글리프는 16-bit idx로 FONT_BASE에서 도달해야 하나, 도달범위 2MB에 안전한 25KB
  연속 빈공간이 **없음**. ROM 끝 0xF00000에 896KB 빈공간 있으나 현 FONT_BASE 기준 도달 밖.
- **변환루틴 디스어셈블 결과 idx에 bound check 없음**(gemini 우려 반증) + per-char 경로는 ROM→VRAM
  동적 글리프 복사(gemini의 VRAM/10-bit 우려는 메커니즘 오해, 73KB는 ROM에 위치).
- **채택 1순위(데이터-only, 경계 확정):** per-char 경로 FONT_BASE 리터럴 **0xEFE97C 1곳만 0x08F00000으로
  repoint** + 원본 폰트 idx 0..0x5FF(48KB)를 0xF00000으로 복사 + 한글 800타일을 그 뒤(idx 0x600~0x920,
  16-bit OK)에 배치 + 한자 테이블 확장(start/end 리터럴 0xEFE970/0xEFE974 갱신). bulk-DMA 경로는 원본
  FONT_BASE 유지(영향 없음). PoC(0x8AEF→테)가 이미 동일 메커니즘 입증.
- **2순위(최대 견고, 두 리뷰어 추천):** 변환루틴에 한글 예약코드 전용 ASM hook → 별도 한글 base
  (0x08F00000)+kor_idx*0x20. 16-bit/경계 우회. repoint가 문제 시 fallback.
- 두 방안 모두 **한글 글리프는 0x08F00000(파일 0xF00000)에 배치**. 너비는 8px 고정(ip 기본 8).

---

## [2026-05-25] 🎉 SESSION 2 완료 — 데이터-only 풀파이프라인으로 대화 한 줄 통째 한글 (인게임 검증)

PoC를 넘어 **프로덕션 풀파이프라인**(repoint+글리프주입+테이블확장+예약코드인코딩)을 한 번에 적용,
대화 "はじめまして"(6가나)를 **"안녕하십니까"(6한글)로 인게임 렌더 성공.** ASM 무수정, 데이터-only.

### 방법 (재현: `python tools/build_korean_poc.py --stage b`)
1. **FONT_BASE repoint**: per-char 변환루틴 리터럴(파일 0xEFE97C) 0x08B974D0 → **0x08F00000**.
2. **폰트 복사**: 원본 폰트 idx0..0x5FF(48KB, 파일 0xB974D0..0xBA34D0) → 파일 0xF00000.
3. **한글 글리프**: `korean_glyph_blob.bin`(800 dedup타일) → 파일 0xF0C000 (글로벌 idx 0x600~0x920).
4. **예약코드 할당**: 미사용 한자대역(원문·테이블 비충돌) 1030음절 1:1 → `data/syllable_to_code.json`.
5. **테이블 확장**: 한자테이블(536) → 파일 0xF20000으로 복사+한글 1030엔트리=**1566엔트리**.
   엔트리=[원본SJIS바이트(lead,trail), top_global_idx(LE), bot_global_idx(LE)]. (검색키=byteswap(SJIS) 정합)
6. **start/end 리터럴 패치**: 0xEFE970→0x08F20000, 0xEFE974→0x08F224B4 (end exclusive, off-by-one 없음 확인).
7. **텍스트 인코딩**: 0xDF8E3E의 가나 6자 → 예약코드 6쌍(8EA2 897B 92A9 8E58 89D4 8895).
8. 헤더 체크섬(0xBD) 무변경 검증, 크기 16MB 유지.

### 결과 (Stage A → B 격리 검증)
- **Stage A**(repoint+폰트복사만): "はじめまして アさん！" **일본어로 동일 렌더** → repoint 메커니즘 격리 검증.
- **Stage B**(전체): "**안녕하십니까** アさん！" → 6음절 전부 예약코드→확장테이블→글리프 경로로 한글 렌더.
  나머지 "アさん！"·배경 그래픽 정상(폰트 보존 확인). 색·간격 정상(약간 높은 세로위치는 polish 여지).
- 증거: `docs/screenshots/SUCCESS_dialogue_korean_FULL_PIPELINE_s2_2026-05-25.png`

### 함의 — 풀게임 경로 데이터-only로 입증
PoC(개별 글리프) → **프로덕션 풀파이프라인(800글리프+1566테이블+1030코드)** 입증. Session 3는 전체
18,262행 인코딩 + QA만 남음. **byte budget 사전분석: 17,925행 전부 슬롯 내(0행 초과)** — 예약코드 한글
=2B/음절 = 기존 EUC-KR과 동일비용이라 기존 길이 QA가 그대로 유효.

### codex+gemini 리뷰 — Session 3 진입 조건 (수렴)
폰트/테이블은 견고; 실패지점은 **문자열 컨테이너·별도 렌더경로·레이아웃**. Session 3 착수 전:
1. 전체 byte budget 리포트 + overflow fail-fast (제어코드 길이 포함).
2. **화면별 렌더경로 매트릭스** — bulk-DMA 경로(가나그리드 등) 한글 누락 판정(최우선 리스크).
3. 줄바꿈 기준(byte/glyph/pixel) 확정 + 빌드타임 줄길이 강제.
4. cold-boot 직행 테스트(캐시 글리프 false positive 회피), 테이블 선형검색 3배→프레임드랍 확인.

---

## [2026-05-25] SESSION 3 (1차) — 풀게임 한글 인코딩 빌드 + 인게임 렌더 검증 (기술검증 빌드)

전체 번역문을 예약코드로 인코딩한 **풀게임 한글 ROM** 빌드. 인게임에서 한글 렌더 확인.
**솔직한 위상(codex 리뷰)**: "ROM 빌드 성공 + 핵심 렌더링 검증 완료"인 **기술검증 빌드**이며,
"검증된 풀게임 한글판"은 아직 아님(잔존 일본어 분류·박스폭/줄바꿈·전화면 스윕·실기 미완).

### 방법 (재현: `python tools/build_korean_full.py`)
- `build_korean_poc` 메커니즘(repoint+글리프800+테이블1566) 재사용 + `translation_for_import.csv` 전체 인코딩.
- 인코딩: 한글→예약코드(2B), ASCII→1B, 일본어 가나/한자/전각구두점→shift_jis passthrough(원본 글리프 렌더),
  실패문자→？(2자뿐: —,～). 슬롯길이=found_texts(권위). encoded>슬롯이면 **skip**(원문유지)+리포트.
- 슬롯 정확히 clear 후 ≤슬롯 바이트만 기록 → **인접 데이터 손상 없음(by design)**. 헤더 체크섬 무변경.

### 결과
- 18,320행 중 **13,280행 한글 인코딩(written)**, overflow 2,322(skip→원문), 코드영역(<0x800000) 2,441 skip,
  no_ko 120, bad_addr 157. unmapped 2자. 16MB·체크섬 OK·부팅.
- **인게임 렌더 검증(cold-boot 네비)**: 이름입력/메뉴 화면에서 한글 정상 렌더 — 색·간격·받침 정상.
  증거: `docs/screenshots/SUCCESS_fullgame_korean_menu_s3_2026-05-25.png`, `..._nameUI_s3_2026-05-25.png`.
- overflow 분포: 대화(0xE+) 59행뿐, 대부분(2,253)은 중간대역(튜토리얼/브리핑/맵) 타이트슬롯. **1,286행은 ≤2B
  초과**라 번역 미세축약으로 해소 가능. 산출: `temp/encode_report.csv`.

## [2026-05-26] 실기 피드백 반영 — 대사 자동넘어감(#1/#4) + 그리드 손상(#2/#3) 수정

사용자 실기 테스트 버그 보고 대응.

### #1/#4 대사 자동 넘어감 — 슬롯 패딩 0x00→0x20 (FIXED)
- 원인: 인코더가 슬롯 빈공간을 0x00으로 채움. 파서 단일바이트 점프테이블(base @0x08B1216C 값=0x08B12170)
  분석 결과 **0x00 = 종료 핸들러(0x08B12350)**, **0x20(공백)·0x6B = 기본/특수 핸들러**. 0x00이 슬롯 뒤
  ▼입력대기(0x6B→0x08B123E6) 전에 메시지를 종료시켜 자동넘어감.
- 수정: `FILL_BYTE=0x20`. welcome "게임보이워즈에어서와▼" ▼ 복원 인게임 확인.

### #2/#3 이름 그리드/미리보기 손상 — SJIS 슬롯 테이블 덮어쓰기 (FIXED)
- 원인: 인코더가 **SJIS→슬롯 테이블(0xBE717A)을 4곳 덮어씀**(0xBE7178/71CC/720C/7308 — 데이터
  테이블이 텍스트로 오추출됨). SAFE_MIN_ADDR=0x800000은 코드만 보호, 0x800000 위 데이터 테이블 무방비.
- 수정: `DENY_REGIONS`(SJIS테이블/폰트/baseptr/한자테이블/한글데이터) denylist 추가 → 4행 skip(deny).
  그리드가 원본 가나로 **복원(기능적)**, NAME 미리보기 깨짐("ㄱ") 해소.

### 영문 이름 그리드(#2) — v56 로직 전이 실패 (미해결, 별도 RE 필요)
- 이전 build_grid v56의 영문 그리드는 `cell_slots`(FONT_BASE 슬롯)+`v27_original_base.gba` 기반.
- 내 데이터-only 빌드에 적용 시: VRAM 덤프 결과 주입한 'A' 글리프가 VRAM에 없음 → **cell_slots가 이
  ROM/화면에서 잘못된 슬롯을 가리킴**(그리드 폰트 실제 소스가 FONT_BASE 0-1023 아님). v27 base 부재로
  정확 재현 불가. **그리드 폰트 실제 VRAM 소스 RE가 선행 필요.** 현재는 기능적 가나 그리드 유지.

### 남은 QA (Session 3 잔여 — fail.md 참조)
1. 잔존 일본어 분류(overflow-skip vs bulk-DMA/고정타일/압축 경로).
2. 박스폭/줄바꿈/페이지넘김 — 슬롯-fit ≠ 레이아웃/제어코드 의미보존(codex 지적). → 아래서 정량화.
3. 텍스트엔진별 대표화면 스윕(전투HUD/상점/저장/팝업/엔딩).
4. overflow 2,322행 축약(축약번역→용어표→핵심 repoint 순).
5. 실기/cycle-accurate 확인. → 아래 BPS로 사용자 실기검증 가능.

## [2026-05-26] SESSION 3 (2차) — 박스폭 정량화 + BPS preview 패치

### 줄바꿈/박스폭 — 바이트예산이 폭도 사실상 보장 (리스크 낮음)
- 대화는 **수동 줄바꿈(0x0A)** 구조(자동 wrap 아님), 줄 시작 0x09, 줄 끝 제어바이트(ASCII letter).
  제어코드는 슬롯 밖 → 인코딩 시 보존됨.
- **핵심 불변식**: 인코딩이 슬롯 바이트(≤원본)를 지키고 한글음절=2B=일본어 전각과 동일이므로,
  **전각↔전각 줄은 한글 폭 ≤ 일본어 폭**(원본이 이미 박스에 맞음). 예외는 ASCII→전각(숫자/메뉴).
- `tools/qa_text_fit.py` 정량화: written 13,280행 중 **한글이 시각적으로 더 넓은 행 116(0.9%)**,
  대부분 ≤1글자 또는 'korean'에 일본어 잔존한 노이즈 행. → **박스폭 오버플로우는 경미.**
- overflow(슬롯초과→skip) 2,322행 중 **1,286행은 ≤2B 초과** → 번역 미세축약으로 해소 가능.

### BPS preview 패치 (실기 검증 enabler)
- `python tools/make_bps.py <원본> output/game_wars_korean_full.gba <out.bps>` → 399KB BPS.
- **round-trip 검증**: 원본+BPS = 한글빌드 정확히 일치, 소스 CRC 일치 → 표준 패처(flips/beat) 호환.
- 배치: `dist/game_wars_korean_full_preview_2026-05-26.bps` + `dist/manifest_preview.json`(체크섬).
  원본 ROM sha1 0e805762…, 패치본 sha1 66f031a0…. **preview/기술검증 빌드**로 명시(풀 QA 미완).

## [2026-05-26] 🎉 ASM hook으로 대화 한글 + 영문 그리드 양립 (repoint 충돌 해결)

사용자 실기 피드백 #1~#5 대응의 핵심. repoint 방식이 v56 영문 그리드와 충돌하던 문제를
**ASM hook**(codex/gemini 원안)으로 해결. 원본 FONT_BASE 보존 → 그리드(영문)+대화 가나/한자 정상,
예약 한글코드만 별도 KOR_BASE 사용.

### 메커니즘 (`tools/build_korean_full.py --base output/v56_polished.gba`)
- **repoint/폰트복사 없음.** 원본 FONT_BASE(0x08B974D0) 그대로 → v56 영문 그리드 + 대화 가나/한자 작동.
- 한글 800 글리프 → 0xF00000(KOR_BASE). 한자테이블 한글 엔트리 idx에 **bit15 마커**(local|0x8000).
- 변환루틴 글리프소스 계산 **2곳**(TOP 0xEFE86C, BOT 0xEFE8E8)에 트램폴린 삽입:
  - FONT_BASE 리터럴(0xEFE97C) → hook_top|1(0x08F30001).
  - TOP: `bx r3`(r3=hook_top). BOT: `adds r1,#0x30; bx r1`(r1=hook_top→hook_bot, 별도 리터럴 불요).
  - hook(0xF30000/0xF30030): `if(idx&0x8000) r7=KOR_BASE+(idx&0x7FFF)*0x20 else r7=FONT_BASE+idx*0x20`.
    ⚠️ GBA=ARMv4T(BLX 없음) → bx 기반, 하드코딩 IWRAM 복귀(top 0x030066C9, bot 0x03006745).
    r0,r3만 clobber(이후 dead), r2 보존.
- ⚠️ 함정(해결): SJIS 슬롯테이블(0xBE717A) 등 데이터테이블 덮어쓰기 방지 denylist 필수.

### 검증 (인게임)
- 대화: welcome "게임보이워즈에어서와 ▼" 한글 정상(원본 base, top+bot 둘 다 hook). 
- 영문 그리드: NAME "AAAA" + "UVWXY Zabcd" 영문 정상(v56 base, FONT path).
- 증거: `docs/screenshots/SUCCESS_hook_dialogue_korean_2026-05-26.png`, `..._english_grid_2026-05-26.png`.
- 디버깅: bot 타일도 0xEFE97C로 base 로드해 두번째 hook 필요했음(첫 시도 garbled). BLX 미지원(ARMv4T)으로
  bx+하드코딩복귀로 전환. 트램폴린 바이트 엔디안 오타(adds r0,#0x31 vs adds r1,#0x30) 수정.

### 5개 실기 피드백 종합
1. #1/#4 자동넘어감 → 0x00→0x20 패딩 (✅). 2. #2 영문그리드 → ASM hook (✅).
3. #3 미리보기 → SJIS테이블 denylist (✅). 5. #5 일본어대사 → overflow(번역축약 과제, 잔여).

## [2026-05-26] #5 overflow 감소 — 단계적 압축 인코딩 (2322→886)

overflow로 일본어 잔존하던 행을 **단계적 압축 인코딩**으로 감소. 번역문 자체는 보존(의미 변경 없음),
인코딩만 슬롯에 맞게 조정: level0=원본(공백/전각구두점) → level1=반각구두점 → level2=반각+내부공백제거 → skip.
- `tools/build_korean_full.py` encode_fit(): 맞는 행은 공백 유지(가독성), overflow 행만 점진 압축.
- 결과: **한글 14,705행**(level0 13,270 / level2 1,432) / 잔존 일본어 **886행**(2,322에서 62%↓).
- 빌드 검증: 대화 한글 + 영문 그리드 정상 유지. BPS sha1 e13a77a3.
- 잔존 886행은 압축해도 슬롯 초과(주로 0123456789+긴 라벨 등). `dist/overflow_priority_report.csv`.

## [2026-05-26] 이름 입력 화면 3개 수정 (codex 통과) — charset 데이터 슬롯 인코딩 제외

사용자 실기 피드백 #1(프롬프트 깨짐)/#2·#4(영문 그리드 윗줄 누락)/#5(미리보기 불가) — 모두 한 원인.
**원인**: 텍스트 인코더가 **이름 그리드 charset/레이아웃 데이터 슬롯**(가나 시퀀스, 셀↔글자 매핑 정의)을
한글 예약코드로 인코딩 → 그리드 매핑 파괴(글자 누락/미리보기 불가/프롬프트 파편).
**수정**(`build_korean_full.py`): `NAME_GRID_DATA`{0x805A24,0xDA4337} + `NAME_GRID_RANGES`(0x83FAF0~0x83FF00
클러스터, 0xDF8C00~0xDF8E00, 0xDF9F00~0xDF9FF0) denylist로 원본(가나) 유지.
**결과(인게임)**: 그리드 ABCDE~Zabcd 6행 영문 정상, NAME 미리보기 "AAAAB", 프롬프트 "네 이름을 알려 줘" 깨끗.
증거: `docs/screenshots/SUCCESS_namegrid_english_full_2026-05-26.png`, `..._name_preview_2026-05-26.png`.
**codex 통과**(조건부): 진단·해법 타당, 3개 통과. 잔여=우측 소형 카타카나 열(영문그리드 수락기준 외).
**별도 불량**: 2편(Part2) 대사 전체 "?" — 별도 타일맵 렌더러/테이블(분리 작업).

---

## 2026-05-26 — 이름 그리드 완전 해결 (갭 제거 + 우측 기호 제거 + 26자 전부)

**최종 결과(인게임 검증)**: 좌 `ABCDE/FGHIJ/KLMNO/PQRST/UVWXY/Z`(A-Z) · 중 `abcde/fghij/klmno/pqrst/uvwxy/z`
(a-z, **갭 없음, 대문자와 동일 정렬**) · 우 `01234/56789`(숫자만, **기호행 제거**). 선택+미리보기 정상("Aab" 검증).
증거: `docs/screenshots/SUCCESS_name_grid_clean_2026-05-26.png`, `..._select_2026-05-26.png`.

**핵심 RE (재현 가능)**:
1. **가나 슬롯 테이블 = base8 = *(0x08B80278) = 0x08B8087C**. kidx=((SJIS-0x8140)&0xFFF8)*2+(SJIS&7)-0x400.
   **top=base8[kidx], bottom=base8[kidx+8]**. 변환루틴 0x08EFE788(코드범위별 base[0]/[4]/[8]).
   - 작은가나(ァィゥェォ ッャュョ)는 top=95(공유 블랭크), ン/ワ bottom=220(별도 엔트리·값 동일). → q-y top·p bottom을
     미사용 빈 슬롯(328-346,348)으로 재배치(KANA_REMAP)해 26자 전부 고유 슬롯 확보.
   - 글자 슬롯 ground-truth는 슬롯-프로브(폰트슬롯에 니블1-9 슬롯번호 마커 주입→신규 부팅네비→BG0 타일맵 디코드)로 확정.
2. **라이브 그리드 레이아웃 = ROM 0x08DF8C38/60/88/B0/CC/E8** (행별 SJIS 문자열, `0A 09` 프리픽스 + `0A 00 00 00`
   종단). 렌더 루틴 **0x08B48910~0x08B48960** (6× `bl 0x08B1311C`, x/y=6,6.. / r3=행주소). ★SET1(0x83FAF6)·
   SET2(0x83FE41)·charlist(0x80505c→EWRAM 0x02010CEC)는 **dead/미사용** — 편집해도 그리드 불변. 진짜는 0xDF8C38.
   - 중간 갭(`ヤ_ユ_ヨ`)·우측 기호행(`゛゜・！？`)은 이 행 문자열 데이터. → 중간을 5열 연속 카나로 재배치(갭 제거),
     우측 기호행을 0x8140 공백으로 교체. 재배치된 카나 순서가 base8 슬롯맵과 정렬되어 a-z 순서로 렌더.

**구현**: `tools/build_korean_full.py` `patch_name_grid()` + `KANA_REMAP` + `NAME_GRID_SLOTS` + `NAME_GRID_ROW_LAYOUTS`.
**워크플로**: codex가 렌더루틴 RE+레이아웃 패치 구현, Claude가 헤드리스 mGBA(부팅네비+VRAM디코드)로 검수.
**대화 영향**: base8 공유라 ァィゥェォ ッャュョ ン이 대화에도 영향 가능하나, 미번역 200행 중 5행·번역행 0(charset/노이즈 제외)
= 실질 무시 가능.

---

## 2026-05-26 — 2편(Advance 2) 대사 한글 렌더 (타일맵 렌더러 + A3 glyph-cache 경로)

**결과(인게임 검증)**: 2편 MODE SELECT 하단 설명문("스토리를즐기면서플레이...", "있는 모드입니다") + PROLOGUE
텍스트가 **한글 렌더**(이전 전부 "?"). Part 1 그리드/대사 그대로 정상.
증거: `docs/screenshots/SUCCESS_part2_modeselect_korean_2026-05-26.png`, `..._prologue_korean_2026-05-26.png`.

**핵심 RE (codex, `docs/PART2_RENDER_RE_2026-05-26.md`)**:
- 2편은 **타일맵 렌더러**(idx를 BG 타일맵에 strh) 3경로:
  - 0x08313F8C~ (Advance 2 타일맵 writer, table 0x083902E4 = 0x08B80B7C 동일 536엔트리)
  - 0x08B11BB0~ (공통 타일맵 writer, table 0x08B80B7C)
  - **0x08A3C7E4 / IWRAM 0x03006080** (MODE SELECT 설명·PROLOGUE 텍스트 = local glyph-cache 경로; "?"의 진짜 원인)
- 패치: ① 0x313/0xB11 테이블 리터럴을 relocated 한글테이블 0x08F20000으로 repoint. ② bit15 마커가 BG attr로
  새지 않게 hook(0xF30100~)에서 KOR_BASE 글리프를 동적 VRAM 타일로 복사 후 실제 tile id 기록. ③ A3 경로
  0x08A3C7E8에 hook(0xF30280) — 한글 예약코드(0x8840~0x9369)를 relocated 테이블에서 찾아 KOR_BASE 글리프를
  대상 VRAM 타일에 복사(fallback "?" 전에 가로챔).

**워크플로**: codex가 2편 렌더러 RE+hook 구현(2라운드), Claude가 헤드리스 mGBA 2편 네비(boot500f→Start→Start→A=
게임선택, Down→A=Advance2)로 검수. 메뉴 라벨(ウォーズショップ 등)은 그래픽 자산이라 별개.

---

## 2026-05-27 — 2편 텍스트 띄어쓰기(단어 공백) 렌더

**결과**: 2편 PROLOGUE 내레이션 + MODE SELECT 설명문에 **단어 공백 렌더**(이전 다 붙어 나옴).
증거: `docs/screenshots/SUCCESS_part2_spacing_2026-05-27.png`.

**원인/수정**: 2편 렌더러가 ASCII 공백(0x20)을 2바이트 SJIS처럼 먹고 cursor 미전진. A3 텍스트 경로는 **문자
디스패치 점프테이블 0x08314270**(바이트값 인덱스) 사용 — 0x20 엔트리(0x083142CC)를 공백 hook(0x08F30340,
cursor state +1)으로 patch. 0x313/0xB11 타일맵 루프 head에도 0x20 공백 hook. Part 1 무영향.
※ 공백 폭이 다소 넓음(+2 advance) — 필요시 +1로 조정 가능. 잔여: 낱 한자 번역갭(今 등 ~5행).

## 2026-05-27 — full preview 빌드 완료(overflow 0) + 배포 패치 갱신 (이후 안정화로 superseded)

**결과(당시)**: `tools/build_korean_full.py` 기준 전체 빌드가 **overflow 0**으로 통과. 다만 이후 실기
스크린샷에서 truncation fallback이 대사를 깨뜨리는 것이 확인되어, 다음 섹션의 안정화 빌드가 현재 기준이다.

### 빌드 통계
- rows 18,320
- written 15,566
- level0 13,250 / level1 3 / level2 1,431 / level3 521 / level4 rule-shortened 64 / level5 truncation 297
- overflow 0
- deny 29, v56 skip 7, no_ko 120, code_region 2,441, bad_addr 157

### 검증
- `python3 tools/phase6_basic_test.py` 통과(크기·헤더·GBA 체크섬·한글 검출).
- `python3 tools/qa_text_fit.py`가 실제 `encode_fit()` 기준으로 갱신됨.
- BPS/IPS round-trip 검증 통과.
- 헤드리스 mGBA 대표화면 캡처:
  - `docs/screenshots/SUCCESS_final_name_grid_2026-05-27.png`
  - `docs/screenshots/SUCCESS_final_part2_prologue_2026-05-27.png`

### 산출물 해시
- patched ROM sha1: `eebd6da6adc8c54d299917aac5bbd072addaf315`
- BPS sha1: `d23ee5b3719134667bf7f228028eff2f5be2b952`
- IPS sha1: `0d9cc357aa5d6f13a614879f36350d11796752fb`

### 남은 폴리시
- `temp/encode_report.csv`의 297행은 slot-fit을 위해 문자 경계 truncation 처리됨. 플레이 가능성 확보 목적의
  fallback이며, 공개 최종판 전 사람이 자연스럽게 축약하면 품질이 올라간다.

## 2026-05-27 — 실기 스크린샷 피드백 안정화

사용자 스크린샷에서 확인된 문제를 안정성 우선으로 수정.

- **대사 깨짐/색 혼재 완화**: 문자 경계 truncation fallback을 비활성화. 슬롯 초과 297행은 깨진 한글 대신 원문 유지.
- **예/아니오 깨짐 수정**: 8바이트 슬롯 `はいえ▼`는 `예아니오▼`가 들어가지 않으므로 `예/아▼`로 별도 오버라이드.
- **이름 입력 k→i 불일치 수정**: 중간 소문자 영역의 시각 레이아웃을 게임의 원래 선택 논리와 같은 공백 포함 구조로 복원.
  `k`는 `ijklm` 행의 세 번째 위치에 표시되며 선택/미리보기 lookup과 다시 일치한다.
- 산출물 갱신:
  - patched ROM sha1: `1264fcab27d0e349b6caf461fd0247380e981c53`
  - BPS sha1: `640c2053c3fc8b4213ca640c3ca17b35f4b2196a`
  - IPS sha1: `5d3798f13e01cab55d4dc17c2f46a07fd750acca`

## 2026-06-15~16 — 독립 전수 재검수: 무결성맵 + 문장부호 복원

codex 기본 한글화 완료분을 처음부터 엄격 재검수(워크플로 감사 25건 확정 + codex/gemini 리뷰).

- **빌드 무결성은 양호**: 코드영역 무변경, 헤더 체크섬 유효, full/final/title_test 3종 동일 SHA, 완전 재현(원본 ROM base; `v56_polished`는 부재/구버전 — 문서 정정).
- **배포 무결성 게이트**(`tools/verify_dist_integrity.py`): manifest.patched_sha == output sha == BPS/IPS 적용결과 sha 3중 일치 검증. 현재 dist STALE(output d680820d ≠ manifest/patch 4004d2c3, 06-14) → Phase F 재생성.
- **빌드 무결성맵**(Phase C-min): `build_korean_full.py`가 모든 텍스트 write를 `temp/integrity_map.json`(addr·slot·기대바이트·fill·ko·level·kind, 25,357건)으로 덤프. 계측은 출력 바이트 무변경(SHA d680820d 동일 검증). `tools/qa_integrity_map.py`가 last-writer-wins 재구성으로 `ROM==기대bytes` 1차 게이트(391,370B 불일치 0=PASS) + import 문장부호 소실 정량화.
- **문장부호 일괄 소실 복원**(Phase B): `encode_fit`(build:8844) 무조건 strip 제거 → 전각→ASCII 정규화(`…`→`...`, `。`→`.`, `、`→`,`, `「」『』`→`"`, smart quotes→ASCII) + **부호 보존 후보(level 0~5) 우선 + strip 후보(level 6~11) fallback**.
  - 문장부호 소실 **11,401행/15,947자 → 7행/9자**(남은 7: 미번역 일본어 3·garbage 2·꽉 찬 슬롯 trailing 2). qqq 연출 복원.
  - **overflow 0 / no_ko 0 / 일본어 폴백 증가 0**. qa_text_fit written 19052, level6 사용 2행, visual-wider 17(증가 없음).
  - 렌더 근거: 출하본이 이미 ASCII 부호 렌더(Part1 1737·Part2 942·캠페인 41행, welcome/0xDCBC12). 픽셀 확정은 Phase E.
  - temp 빌드 SHA `f3c0014d82f61cda2b3a198dd4b890ae53e8f6a16930aba62cfe0e4ec4afcd8d`(output 동기화는 리뷰 후).

## 2026-06-16 — 전체 화면 비교 시트 생성기 (시각 회귀 backbone)

사용자 지시(/loop): 진행별 세이브 데이터로 전체 화면 비교 시트를 만들고 claude/codex/agy가 엄격 리뷰 → 무결점까지 개선.

- **신규 도구** `tools/build_comparison_sheet.py`: 진행 체크포인트별로 ROM 화면을 캡처해 라벨 montage 시트(PNG) 생성. `qa_visual_regions.MGBADriver`(헤드리스 `/tmp/mgbah`) 재사용.
  - `fresh` 모드: 콜드부트 + 합성키 네비 → **현재 ROM 그대로 렌더(ground truth)**. stale VRAM 없음.
  - `savestate` 모드: 세이브스테이트 + refresh 프레임 → 빠르지만 정적 BG/기존 텍스트는 캡처 시점 VRAM(시트에 `[STALE-BG]` 표기).
  - `--compare`: 원본 vs 패치 좌우 배치(fresh는 동일 네비, savestate는 `orig_state`).
  - 매니페스트 `data/screen_checkpoints.json`(fresh 6 + savestate 5). nav 스텝: `[frames,n]`/`[press,KEY,after]`/`[keys,mask]`/`[loadstate,path]`.
- **fresh-boot ground truth 검증**: 콜드부트 닌텐도 제공, 공통 타이틀(시작하기), 1/2 선택, 1·2편 타이틀 — 원본(NINTENDO PRESENTS/PRESS START) 대비 한글 정상 렌더. 시트 `temp/comparison_sheets/sheet_compare.png`.
- **핵심 원칙 확립(리뷰 반영 예정)**: 세이브스테이트 캡처는 정적 BG와 이미 그려진 텍스트가 **stale**이라 텍스트/배경 회귀 판정에 신뢰 불가. 따라서
  - 텍스트(의미/명사/띄어쓰기) 검증 → **ROM 슬롯 디코드**(qa_integrity_map / dialogue_map) 기준.
  - 그래픽 깨짐 검증 → **fresh-boot 캡처** 기준.
- **재현**: `python3 tools/build_comparison_sheet.py --compare --only fresh` (신뢰 시트) / `python3 tools/build_comparison_sheet.py` (전체 patched 3x). 부팅 타이틀은 ~600프레임에 출력(매니페스트 타이밍 반영).
- 빌드 무영향(신규 파일만 추가, `build_korean_full.py` 무변경). py_compile OK, 매니페스트 JSON OK.

## 2026-06-16 — 명사 통일 ROM 게이트 + 72행 통일 (codex 리뷰 반영)

codex 엄격 리뷰 반영: "CSV 시뮬레이션이 아니라 post-build ROM 역디코드가 권위" → ROM-디코드 명사 게이트 신설 + 발견 결함 통일.

- **신규 hard gate** `tools/qa_terms_from_rom.py`: integrity_map enc_hex를 역디코드(2350+1030 음절맵)해 **출하 ROM 실제 한글** 기준으로 `proper_nouns.json` 정본 대비 금지 표기 흔들림을 검사. 1건이라도 있으면 exit 1.
- **발견·통일된 72행 결함**(출하 ROM 역디코드 기준, 비-고유명사 충돌 0 검증):
  - リョウ: `료우` 32 → `료`
  - ホイップ: `휩` 24 + `호이프` 10 → `휘프`(기존 빌드 partial 규칙 `휩 장군→휘프 쇼군` 보완)
  - マクロランド: `마크로랜드` 3 → `매크로랜드`
  - イエローコメット: `옐로 코멧` 2 → `옐로코멧`
  - グリーンアース: `그린 어스` 1 → `그린어스`
- 적용 경로: `build_korean_full.py` `TERM_NORMALIZATION`(encode_fit 내 normalize_korean_terms — CSV import·inline·직접패치 전 경로 공통 적용). 국가명 띄어쓰기 정본 붙임 통일도 추가(레드스타/블루문/블랙홀 future-proof).
- **검증**: 재빌드 후 `qa_terms_from_rom` PASS(hard 0), 역디코드 잔존 료우/휩/호이프/마크로랜드/옐로 코멧 모두 0, 휘프 110·료 312 통일. `qa_integrity_map` PASS(바이트OK). `qa_text_fit` **overflow 0 / no_ko 0**(휩→휘프 +2바이트 확장이 fallback으로 흡수, 회귀 없음). full/final/title_test 동기화.
- 비교 시트 도구 codex 결함 수정: `panel()` 종횡비 보존(고정 240폭 → 실제 폭), 기본 `--only fresh`(stale는 `--include-stale` opt-in), savestate orig_state fallback 금지, 캡처별 provenance.json(ROM/state SHA·git commit·nav) sidecar.

## 2026-06-16 — 띄어쓰기 결함 대폭 감소 (fit 순서 재배열 + 공백 collapse) + 띄어쓰기 게이트

/goal #2(띄어쓰기·줄바꿈 0) 공략. 신규 hard gate + 결정적 수정.

- **신규 게이트** `tools/qa_spacing_from_rom.py`: 출하 ROM 역디코드로 JAMMED(단어붙음)/ABBREV(SHORTEN 축약)/GRAMMAR(있·없 관형형 훼손)/DOUBLE(연속공백) 분류. `--json` 워크리스트.
- **근본 수정 1 — `_fit_variants` 순서 재배열**: 전각공백 → **반각공백** → 전각+축약 → 반각+축약 → 공백제거 → 공백제거+축약. 기존엔 전각+축약(L1)이 반각공백(L2)보다 먼저라, 슬롯을 1~2바이트만 초과해도 문법 깨지는 SHORTEN(있는→있, 에게→에)이 적용됐다. 반각공백을 축약보다 우선 → 단어/문법 최대 보존.
  - 결과: **GRAMMAR 49→5, ABBREV 226→27**. 전각공백이 맞는 다수 행(level0=17753)은 byte-identical(회귀 0).
- **근본 수정 2 — 中점/이중공백 정리**: `スキ　・X`(좋아함:X) 구분자를 인접 공백과 합쳐 단일화 + 연속/혼합(전각·반각) 공백 collapse. **DOUBLE 24→0**. 단일공백 행은 level0 재전각화로 byte-identical. 예/아니오 메뉴 위치샘플 트릭은 `WS_COLLAPSE_EXEMPT`로 예외.
- **검증**: integrity PASS, terms PASS, overflow 0, no_ko 0. 남은 JAMMED 142 + ABBREV 27 + GRAMMAR 5(슬롯 대비 진짜 긴 행)는 재번역 워크플로로 처리 중.
- 재현: `python3 tools/qa_spacing_from_rom.py --json temp/spacing_worklist.json`.

## 2026-06-16 — 띄어쓰기 결함 0 달성 + 의미 드리프트 검사 (codex 리뷰 반영)

대량 재번역 워크플로 + encode_fit 구조 개선 + 신규 게이트 2종으로 /goal #2(띄어쓰기) 0화.

- **재번역 워크플로 2라운드**(claude 생성 + adversarial 검증 + 결정적 byte-fit): 슬롯 미달로 단어붙음/축약/문법훼손된 대사를 슬롯에 맞는 자연스러운 한국어로 재작성. 1차 110행 + 2차 29행 + 수동 12행 → `ADDRESS_TEXT_OVERRIDES`. 검증이 의미반전(알고 싶잖아↔알고 싶지 않아)·명령형 변질·하지마 띄어쓰기·바이트초과를 색출.
  - 누계: **JAMMED 142→0, ABBREV 226→0, GRAMMAR 49→0, DOUBLE 24→0**(`qa_spacing_from_rom` PASS).
- **encode_fit 비용기반 재설계**(codex 핵심 지적): 기존엔 '마침표 제거+공백유지'보다 '공백제거+마침표유지'가 먼저라, 마침표 하나만 버리면 들어갈 문장을 단어 붙여 출하했다. `_fit_candidates`로 전체보존 → `.!?,`제거 → `:;"'`제거 → 축약 → (최후)공백제거 순. 괄호 `()[]{}`는 의미훼손(을(를)→을를)이라 jam 직전만 제거. 다수행 byte-identical, 모든 게이트 PASS.
- **신규 게이트 `qa_meaning_from_rom.py`**(codex: LLM 자기검증 백스톱): 출하 KO↔원문 JA 대조. NUMBER(JA 숫자가 KO에 누락+고유어 대체도 없음, 고유어 인식으로 오탐 103→21) / NEGATION(부정 극성 불일치 WARN). 실드리프트 색출: 이동력3→느리지만, CO파워8 누락, 승리조건 3개 누락, 10HP→최대 등 21행.
- 검증 권위 3종 모두 PASS: `qa_integrity_map`(바이트) / `qa_terms_from_rom`(명사 0) / `qa_spacing_from_rom`(0/0/0/0). overflow 0, no_ko 0.
- 잔여: 숫자드리프트 21행 재번역(워크플로 진행), 전각/반각 공백 폭 실측, 부정 극성 정밀화, 전체 의미 audit.

## 2026-06-16 — 의미 숫자드리프트 0 + 이중권위(인라인 리터럴) 문제 해결

`qa_meaning_from_rom` NUMBER 0 달성. codex 지적한 "CSV vs 인라인 리터럴 이중권위" 실증·해결.

- 워크플로(wf_80f24953, 24에이전트) + 수동으로 숫자누락 21행 판정·복원. 검증이 원문에 없는 내용 창작(블랙캐논 "격파 승리", "0이 되면 파괴")을 반려.
- **이중권위 발견**: 일부 주소(0xA2B332 등 CO파워, 0xA348F0 블랙캐논, 0xD8FEFE 초기HP, 0xDC2CEE)는 `script:` 인라인 리터럴(직접패치 span 튜플)이 import-csv를 **나중에 덮어**(last-writer-wins) `ADDRESS_TEXT_OVERRIDES`가 무효. → 해당 리터럴을 직접 수정해야 함(Hawke 회복/피해 1·2, Sturm 메테오 8, 블랙캐논 3개, 초기 체력 10, 남은 두 메뉴). dead override 정리.
- **qa_meaning 정밀화**: 인접 슬롯 숫자 인식(다행 대사 "0이 되면"이 다음 줄), もう１→또/다른, 자릿수 분해(234=2,3,4), 손상 구두점 노이즈 제외. 오탐 103→0.
- 전 게이트 PASS: integrity / spacing(0/0/0/0) / terms(0) / meaning NUMBER(0). overflow 0, no_ko 0.
- **도구 신뢰성 메모**: agy(Antigravity)는 trivial 프롬프트만 동작, 실질 리뷰 프롬프트엔 반복 hang. 3자 리뷰는 claude(본체/서브에이전트) + codex로 운용, agy는 짧은 개념 질문만.

## 2026-06-16 — 의미 audit 완료(3자 검증) + 시각 커버리지 정리

- **전체 의미 audit 완료**: 6997 import-csv 대사행 3청크 LLM 판정 → adjacent-aware verify-fix → **확정 ~76행 수정**(CAN/CANNOT 반전, 오역, 정렬오류 라이트닝어설트→쇼군 캐서린·오정렬→이글! 적당히, 대머리→애송이, 화자반전, 누락복원, 조사/관용구). **codex 독립 리뷰**가 표본 31행 정상 확인 + 과교정 2(잃지 않았다 중복·시야 잘림)·주체 1 정정. claude(audit judge)+verify-agent+codex 3자 검증.
- **휩→휘프 조사 회귀 5행** 발견·수정(받침-조사 보정).
- **시각 커버리지 현황**(/goal #1):
  - 글리프 데이터: 2350음절 contact sheet clean(render_glyph_sheet).
  - 렌더러 4경로 전부 한글 정상: per-char 대사, A3(모드선택/프롤로그, ? 결함 수정 완료), 0x313, 0xB11.
  - fresh-boot 화면(닌텐도 제공/타이틀/1·2 선택/Part2 메뉴+설명문/프롤로그) clean.
  - 전투 화면(맵/유닛정보 HUD/튜토리얼 대사) 동적 렌더 current-ROM clean.
  - **잔여**: 결과/저장/상점/엔딩 등 정적 화면은 savestate가 stale이라 직접 캡처 불가 → **텍스트는 ROM-디코드 게이트로 전수 검증됨**(의미/띄어쓰기/명사 0). 그래픽 직접 캡처는 진행 SRAM seed 또는 Lua 자동진행 필요(잔여 인프라).
- 현재 출하 ROM: integrity PASS, spacing 0, terms 0, meaning NUMBER 0, overflow 0, no_ko 0.

## QA 디코더 신뢰성 + 글리프 커버리지 게이트 + 전략지도 화면 정리 (2026-06-16, iter19)

**핵심**: 인게임 「비트맵 깨짐 0」을 폰트 음절 커버리지로 정면 보증 + 무결성 게이트의 가짜 결함 제거 + codex 리뷰로 전략지도 화면 정정.

- **qa_integrity_map.py 디코더 수정**: SYLCODE `syllable_to_code.json`(1030) → `syllable_to_code_2350.json`(2350, superset·공유코드 mismatch 0). 구 맵은 1320개 추가 예약코드(예 뤘=0x9868)를 몰라 SJIS 폴백→한자(鷲) 오표시(가짜 '부호소실'). 수정 후 0xDFCA93 '능숙한…다뤘을…'를 정상 디코드. `phase6_basic_test.py` 한글검출도 2350 우선.
- **신규 게이트 `tools/qa_glyph_coverage.py`**(codex 지적 반영 — ko 필드가 아니라 **enc_hex 출하바이트** 기준이라 ko=None인 script/raw_replace까지 전 경로 커버): integrity_map 25296행·14경로에서 예약-한글 코드 160015회/959음절이 전부 glyph 보유 음절로 해석 → **미렌더 0**. code∩glyph 대칭(2350) + 빌드 encode_text의 `syl_to_code[ch]` KeyError 가드(2350 외 음절 들어오면 빌드 크래시)로 폰트측 보증.
- **Mode4 전략지도 한글화 완료(codex 리뷰 반영, 사용자 승인)**: SWI/DMA 로그(`temp/auto_fresh_p2/mgbah.stderr.log:7800~7806`)로 `0xC2FD70`/`0xC30EE8`은 **표시되는** Mode4 풀스크린 전략지도 확정(LZ77→EWRAM 0x02000000→DMA 0x06000000/0x06004B00=240×160 fb 상/하단). 타일 간접 없어 오프라인 렌더=인게임. `patch_part2_strategic_map_mode4_labels`로 원본 픽셀 zoom 직접 enumerate한 실측 3라벨만 한글화: 레드스타 궁전(파랑 idx16)/공장(암적 idx24)/그린어스 궁전(암 idx4). codex_bgblocks의 'Blue moon Palace'·half-B Factory 좌표는 원본 검증 결과 phantom(미존재)이라 제외(빈 영역 가짜라벨 방지). 'Cosmo earth'=녹색국가→배너/범례와 동일 그린어스 통일(#3). 재압축 A4249/4471·B3996/4161 OK. 빌드ROM 렌더 확정: `temp/smap_built_verify.png`. (상단 해양 소형 라벨 'Cayo/Cargo?'는 판독불가 미번역.) 별개 화면 = step073 Mode0 대륙 오버맵(BG3 0xC34E10, 타일 6px 필기체, 추후): `over_bg3.png`.
- **0xBF66F0 배너 한글화 블록 식별 100% 확정**: 원본 0xBF66F0 비공백 타일 312/312가 인게임 배너 화면 VRAM(step057_A)과 verbatim 일치 → 표시 블록 확정. (레드스타/블루문/그린어스/코멧/옐로 한글, KEEP)
- 재실행: `python3 tools/qa_glyph_coverage.py` (PASS=0). 5게이트(integrity/terms/spacing/meaning/glyph_coverage) 전부 PASS, overflow 0.

## 배포 최종 (Phase F) — 2026-06-16 release (iter21)

`python3 tools/prepare_patch_distribution.py --date 2026-06-16` → BPS/IPS(원본→output/full) 재생성 + 라운드트립 + manifest×2/README/RELEASE_NOTES×2. `verify_dist_integrity.py` 3중 해시 게이트 PASS.

**adversarial 독립 검증(워크플로 5병렬, 전부 PASS)** — 내장 round-trip이 생성코드(make_bps/ips)와 동일 코드라 갖는 사각을 메우려 독립 적용기로 재검증:
- 독립 BPS 적용기(spec에서 새로 작성, make_bps 미import): 원본+BPS == output **byte-exact**, footer CRC 3종(src 49ee1fdd/tgt d8c17c98/patch fcc4a10e) 일치, footer 경계 정확 착지, source 변조 시 결과 변함(=true source dependence).
- 독립 IPS 적용기(make_ips 미import): byte-exact, 44517 레코드 well-formed·non-overlap·clean EOF, max offset 0xF66F56 < IPS ceiling 0xFFFFFF(무절단), 음성 컨트롤 통과.
- manifest 16해시필드(src/tgt/bps/ips × size·crc32·sha1·sha256) 전수 재계산 일치, synced_outputs 3종 일치, manifest.json==manifest_preview.json byte-identical.
- 문서(README/RELEASE_NOTES×2): stem·target sha·source sha·date 전부 2026-06-16 release와 일치, stale 참조 0.
- 음성테스트: apply_bps가 wrong-source를 source-CRC로 거부 / 산출물 3종 triple-identity(1d825104).
- 해시: source a8ad7c7d…831c, target 1d825104…97b3. 패치 크기 BPS 4.46% / IPS 5.22%(폰트+한자테이블+대사 확장 규모로 타당).
- stale 미트래킹 패치(full 06-10/06-14, preview 06-08) 정리. 재현: `python3 tools/verify_dist_integrity.py`(PASS=0).

## A3 렌더러 예약코드 범위 버그 수정 (2026-06-16) — UI 에디터 실캡처 부산물

UI 에디터 실캡처 기능 검증 중(canvas-hijack: 0xA2C098 슬롯을 임의 문자열로 덮어 07_part2_main_menu 헤드리스 캡처) **A3 경로의 잠복 렌더 버그** 발견·수정.
- 버그: PART2_HOOK_A3가 예약-한글 코드를 [0x8840,**0x9369**](구 1030 상한)로 판별 → 2350 확장분(0x936A~0xE2A7, 1320음절)이 A3에서 '?'. (Part1 per-char·313/B11은 bit15 마커라 무영향)
- 출하 영향: 코드>0x9369 사용 행은 2건뿐이고 둘 다 part1(뤘/뀔) → part1 경로로 정상. A3 화면엔 코드>0x9369 미사용 → 출하 빌드 무영향. 잠복 버그(Part2 편집 시 표면화).
- 수정: max 0x9369→**0xE2A7**. canvas-hijack 검증으로 가/뤘/캡/뀔/힝/한 전부 정상·인사말 무회귀(`temp/cap_validate/a3fix_*`). build에 회귀 가드 추가(max code>hook max→assert).
- ROM sha 1d825104→**61d51a2a**. dist 재생성(verify_dist_integrity PASS). 5게이트 PASS.
- 핵심 인프라 검증: **canvas-hijack 실캡처 작동**(슬롯 패치→헤드리스 nav→실화면 캡처) = UI 에디터 실캡처의 토대.

## 추출 노이즈 placeholder 행 정리 = 비트맵 손상 수정 (2026-06-17)

사용자 요청 "해독 불가인것도 다 해결". `translation_for_import.csv`의 placeholder 마커 행
(해독 불가 94 / 판독 불가 202 / 깨진 문자열·[깨진 문자열] 29 / 의미 불명 20 = **345행**)을
`archive/extraction_noise_placeholder_rows.csv`로 보존 후 제거.
- 판정 근거: 302행 <0x800000(코드영역, 빌드 skip). 43행 ≥0x800000은 ROM 실바이트가 전부
  비텍스트(가나 음절표 `8341 8344…`, 기호테이블 `8157 8156…`, 픽셀 그라데이션 `9d 98 95…`,
  단색채움 `9999…`, 반복글리프 `劔劔劔劔`). 자연어 0건. 대사구조(dialogue_groups) 교집합 0.
- **핵심 발견(codex+스프라이트에이전트 독립 수렴)**: `깨진 문자열`/`[깨진 문자열]`이 빌드
  `PLACEHOLDER_KO` skip-set에 **누락** → ≥0x800000·deny밖 **18행이 그래픽 위에 예약코드로
  인코딩되어 비트맵 손상**(0x8A298C·0xE88C50 등). 제거로 18/18 span이 원본 ROM과 일치 복원
  (자체 재검증). 구 baseline `61d51a2a`만 손상 보유 → 권위 ROM sha **1623481a**.
- 방어 강화: `PLACEHOLDER_KO`에 깨진문자열 계열 추가 + 18 span을 DENY_REGIONS에 영구 등록 +
  `qa_placeholder_residuals.py`를 빌드 PLACEHOLDER_KO 단일소스로 통일(ROM 스캔은 부분문자열
  모호토큰 '불명/미상/불가' 제외 — '행방불명' 등 거짓양성 회피).
- 검증: 5게이트 PASS(바이트 0불일치/placeholder 0·0/glyph 미렌더 0/overflow 0/부팅 OK).
  dist 2026-06-17 재생성, verify_dist_integrity PASS(BPS·IPS 적용 sha=1623481a).
- 교훈: "integrity_map 교집합 0 ≠ 미표시". stale integrity_map 기준이라 18 손상행을 못 봤음.
  실제 빌드 ROM 바이트 비교가 권위.

## 스프라이트 WYSIWYG 빌드레이아웃 계측 확장 (2026-06-17)

스프라이트 에디터가 캡처 없이도 "실화면 형태"로 텍스트 라벨을 편집하도록, 빌드의 라벨 패치
함수에 `rec_label_layout` 계측(순수 추가, 출력 무변경) 확장. **2 → 26 blocks**.
- 16개 LZ77 라벨 함수 계측(정보/피해/레벨/확인/캠페인/레드스타/가자!/미션1/작전성공·실패 등),
  각 off가 `sprites_index.json`과 링크 확인(NOT-LINKED 0). 편집기 `build_layout_cells` 소비 검증.
- 바이트 무변경: 계측 전/후 빌드 sha 동일(1623481a), qa_integrity_map/glyph PASS.
- 후속: OBJ 직접기록 4종(action_menu/status_header/info_screen_obj/battle_obj)은 단일
  스프라이트 offset 미매칭 → 합성 스프라이트 필요.

## OBJ 직접기록 라벨 → 합성 스프라이트 WYSIWYG (2026-06-17)

흩어진 ROM 오프셋에 4bpp 타일을 직접 기록하는 4개 OBJ 라벨 함수(단일 LZ77 블록 미매칭이라
기존 빌드레이아웃으로 노출 불가)를 편집기에 **실화면 형태(WYSIWYG)**로 노출.
- 빌드: `rec_objlabel` 헬퍼 + 4함수에 기록 호출(순수 추가, 출력 byte-identical, sha 1623481a 불변)
  → `data/objlabel_sprites.json`(8 합성 스프라이트). 각 라벨=base 오프셋의 tw×th 연속 타일.
  status_terrain만 OBJ 분할 재배열이라 perm=[0,1,4,2,3,5](시각→ROM) 기록.
- 편집기(`sprite_editor/server.py`): 새 type `synthetic`. decode_from_rom이 라벨별 perm 보정해
  세그먼트 조립, `synthetic_layout_cells`가 라벨 적층 셀 생성(tile_off=조립순번 일치),
  classify/section/order에 part2_objlabel 분기, objlabel 고대비 편집 팔레트(잉크 1/5 짙음).
- 커버: terrain_status(15+육)·terrain_compact(24)·unit_status(18)·unit_compact(19)·co_banner(휘프)·
  status_header(종류/체력/연료/탄약)·info_screen(정보/비용/설명)·action_menu(공격/대기 등) = 8 스프라이트.
- 검증: 8종 전부 목록 노출·디코드·onscreen 렌더 OK. 7종 시각확인(라벨 정확·perm 정상). 5게이트 PASS,
  dist 무결성 PASS(해시 불변). ⚠ 편집→ROM 라운드트립은 전체 스프라이트 공통 미구현(별도 후속).

## 잘린/형식이상 주소 행 정리 (2026-06-17)

translation_for_import.csv의 잘린 주소 2행('7EBF'·'808', 코드영역이라 미기록)은 정주소 행
(0xDC7BDB/0xDC7EBF/0xE03808, 전부 기록됨)과 동일 ja+ko **중복**임을 ROM 전수검색으로 확정 → 제거.
빈 garbage 3행도 제거, 0x 없는 정상주소 6개 정규화. 전부 출력 무영향(sha 1623481a 불변).
archive/malformed_address_rows.csv 보존.

## 스프라이트 편집 → ROM 라운드트립 (2026-06-17)

스프라이트 에디터 픽셀 편집이 실제 게임 ROM에 반영되도록 빌드 오버레이 구현.
- 빌드(`build_korean_full.py`): `apply_sprite_overrides(rom)` — 라벨 자동그리기 뒤 최종
  오버레이로 `data/sprites_overrides.json` 적용. **오버라이드 없으면 무동작→byte-identical(해시 1623481a)**.
  synthetic=라벨별 perm 역변환(시각→ROM), lz77=재압축≤comp_size(초과 시 skip+리포트), raw=size 이내.
  체크섬 재계산 직전 호출(편집이 0xBD에 반영).
- 편집기: `_save`가 overrides 기록 → `/api/build`(재빌드)로 ROM 반영, `_PATCHED` 캐시 무효화.
  프런트 '적용(ROM 반영)' 버튼 추가.
- E2E 검증: synthetic(status_header 타일0→index5)·lz77(world_map 0x54214C) 둘 다 편집→재빌드→
  ROM 오프셋 바이트 0x55 반영·decode 일치, 타 라벨 무변경. 오버라이드 제거→재빌드→해시 1623 복귀.
  /api/build HTTP OK. 5게이트 PASS.


---

## 📦 todo.md 완료 항목 이전 (2026-06-17, UI 에디터 재계획)

> 사용자 지시로 기존 todo.md의 완료 항목(`[x]`)을 success.md로 이전했다. 각 항목의 상세 증거·경로 sub-bullet과 미완료 항목은 `archive/todo_archive_2026-06-17.md`에 무손실 보존했고, 이후 todo.md는 화면(scene) 기반 통합 UI 에디터 목표로 재작성했다.


총 완료 항목 457건.


### 🟢 /loop: 무결점 한글화 (2026-06-16 시작) — 현재 최우선

- [x] **iter1: 비교 시트 backbone** `tools/build_comparison_sheet.py` + `data/screen_checkpoints.json`. fresh-boot ground truth(닌텐도 제공/타이틀/선택) 원본 대비 정상 확인.
- [x] **iter2: codex 리뷰 반영(1차)** — 비교 시트 도구 결함 수정(panel 종횡비/기본 fresh/orig_state 가드/provenance). **명사 통일 hard gate `qa_terms_from_rom.py` 신설 + 72행 통일**(료우→료, 휩/호이프→휘프, 마크로랜드→매크로랜드, 옐로 코멧/그린 어스→붙임). 게이트 PASS, overflow 0.
- [x] **iter3: 띄어쓰기 결정적 수정** — `qa_spacing_from_rom.py` 신설. `_fit_variants` 재배열(반각공백을 축약보다 우선) → GRAMMAR 49→5, ABBREV 226→27. 中점/이중공백 collapse → DOUBLE 24→0. byte-identical 다수 유지, integrity/terms PASS. **README 번역가 가이드**(서브에이전트) + Pillow 의존성.
- [x] iter4: 재번역 워크플로 1차(169행, 186에이전트) → byte-fit 통과 110행 적용. JAMMED 142→37, ABBREV 226→5, GRAMMAR 49→3, DOUBLE 0. gate JAMMED 오탐(명사통일) 수정.
- [x] iter5: 재번역 2차+수동 → **띄어쓰기 결함 0 달성**(JAMMED/ABBREV/GRAMMAR/DOUBLE 0). encode_fit 비용기반 재설계(codex: 공백제거 최후수단). 의미검사 `qa_meaning_from_rom` 신설(숫자드리프트 21·부정 WARN).
- [x] iter6: 숫자드리프트 복원 → **qa_meaning NUMBER 0**. 이중권위(script 인라인 리터럴이 import 덮음) 해결, qa_meaning 정밀화(인접슬롯/もう１/노이즈). agy 실리뷰 hang 확인→claude+codex로 운용.
- [x] iter7: 글리프 데이터 clean 확인(render_glyph_sheet, 2350음절 깨짐 0). **fresh-boot Part2 메뉴에서 /goal #1 실결함 발견**: CO 인사말 A3 렌더러 다수 음절 `?` fallback. 증거+research 기록, codex 심층분석 의뢰.
- [x] iter8: **A3 `?` 결함 수정 완료**(codex: relocated table-end literal을 2350 전범위로 data-driven 주입). fresh-boot 검증 — 메뉴 인사말 `캠페인을 처음부터 플레이합니다` 정상, `?` 0. 전 게이트 PASS.
- [x] iter9: A3 전각공백 "이중" 오진 정정 — **픽셀 실측 결과 이미 1칸(9px) 정상**. codex hook은 no-op이라 revert. 교훈: 띄어쓰기 폭은 흰픽셀 gap 실측으로 판정(육안 확대 금지).
- [x] iter10: A3 ? 수정 **프롤로그/메뉴 설명문 등 전 A3 화면 적용 확인**(스토리를 즐기며 플레이하는 모드 등 정상). 의미 audit 1차: **부정 극성 불일치 1226행 → LLM 판정 워크플로(wzqkamakv)** 실제 반전/왜곡만 색출 중.
- [x] iter11: 부정 의미 audit(1226행 LLM 판정) → **실제 의미오류 18행 수정**(CAN/CANNOT 반전 6, 깨진 단편 부정/누락, distortion 7). 판정 오탐(じゃない 발견맥락 등) 식별·skip. 이중권위 script 리터럴 직접수정 다수.
- [x] iter13: **전체 의미 audit 6997행 완료** — 3청크 LLM 판정 + adjacent-aware verify-fix → 확정 ~72행 수정(반전/오역/정렬오류/관용구/누락/조사). 전 게이트 PASS.
- [x] iter14: **codex 독립 리뷰로 의미 audit 검증** — 표본 31행 정상 확인, 과교정 2(잃지 않았다 중복·시야 잘림)+주체 1 정정. 의미 audit 3자 리뷰 완료(~75행 수정).
- [x] iter15: **자동진행 도구 `auto_playthrough.py` 구축**(사용자 선택). 콜드부트 BG-신뢰 캡처로 캠페인 월드맵=한글(블루문) 확정. **영어 잔존 BG 2종 발견**(전략 오버맵 필기체 Red star Palace 등, 작전선택 BG RED STAR/BLUE MOON) — 과거 stale 기각이 실잔존을 가림.
- [x] iter16: **작전선택 BG(0xBF66F0) 영어 국가명 5종 한글화 완료** — 레드스타/블루문/그린어스/코멧/옐로. galmuri7 7px, 측면장식 보존, 재압축 2756/2952. 전 게이트 PASS, 증거 SUCCESS_op_select_bg_korean.
- [x] iter17: **결과/엔딩 자동도달 강화**(사용자 선택). auto_playthrough 전투정책+savestate저장 강화 → 전투 애니메이션/부대목록/월드맵 등 깊은 화면 다수 검증(전부 한글 정상). 부대목록 탄약 무탄약표시 `닛` 미세잔여 발견.
- [x] iter18: **작전선택 BG(0xBF66F0) 한글화 확정** — 레드스타/블루문/그린어스/코멧/옐로. **블록 식별 100% 검증**(원본 비공백 타일 312/312가 인게임 배너 VRAM step057과 verbatim 일치). ~~전략오버맵(0xC2FD70, 8bpp) 한글화~~는 iter19에서 **오식별로 판명·revert**.
- [x] iter19: **QA 디코더 결함 수정 + 신규 글리프 커버리지 게이트 + 전략지도 화면 2종 정리(codex 리뷰 반영)**.
- [x] iter20: **Mode4 전략지도 한글화 완료**(사용자 승인). `patch_part2_strategic_map_mode4_labels` — 원본 픽셀 zoom으로 라벨 직접 enumerate(codex 좌표 일부 phantom 확인: 'Blue moon Palace'·half-B Factory 미존재). 실측 3건만: 레드스타 궁전(파랑)/공장(암적)/그린어스 궁전(암). 'Cosmo earth'=녹색국가→그린어스 통일(#3). 오프라인 렌더=인게임(Mode4 fb 직접 DMA, 타일 간접 없음) → `temp/smap_built_verify.png` 확정. 재압축 A4249/4471·B3996/4161 OK. 5게이트 PASS. (상단 해양 소형 라벨 'Cayo/Cargo?'는 판독불가로 미번역 유…
- [x] iter21: **배포 최종(Phase F) — 사용자 선택**. Mode0 오버맵은 6px 필기체가 지형 텍스처 위라 한글화 시 글자 뭉개짐/지형 손상(=비트맵 깨짐)으로 판단 → **장식 원본 유지**. `prepare_patch_distribution.py --date 2026-06-16`로 BPS(747759B,4.46%)/IPS(876262B,5.22%)+manifest×2+README+RELEASE_NOTES×2 재생성. `verify_dist_integrity` 3중 해시 게이트 PASS. **adversarial 검증 워크플로(5병렬)**: 독립 BPS 적용기(byte-exact·footer CRC 3종·true source dependence), 독립 IPS 적용기(byte-exact·max…


### T1 — 한글 2350자 폰트 확보 ✅ 완료

- [x] KS X 1001 완성형 2350 hangul 글리프 생성 + 매핑 2350 확장(`tools/build_korean2350.py` → syllable_to_code_2350.json/syllable_to_glyph_2350.json/kor_glyphs_2350.bin)
- [x] 기존 1030 byte-identical 호환(코드값·local idx·블롭 prefix 보존), 한자테이블 1030→2350 확장
- [x] **빌드 통합 완료**(build:SYLCODE/GLYPH_BLOB_2350/SYLMAP_2350): 2350 전 음절 인코딩 가능(매핑 누락 0, 코드 유니크), 무결성맵 PASS, 부팅/체크섬 OK. output 74af7863(additive, 기존 렌더 불변).


### T2 — 원본 ROM 스프라이트 전수 JSON + 픽셀아트 에디터 ✅ 완료(잔여: 팔레트 캡처·ROM 역기록)

- [x] `tools/export_sprites.py` → `data/sprites_index.json` (1979 스프라이트: curated LZ77 104 + scan LZ77 1874 + font, 4bpp/LZ77 디코드+PNG 렌더)
- [x] **픽셀아트 에디터** `tools/sprite_editor/`(stdlib server + canvas): ROM→4bpp 인덱스 그리드+16색 팔레트, 확대캔버스 픽셀 페인트, 팔레트 색 지정(원본색), 격자/타일경계, 저장→sprites_overrides.json. (:8781)


### T3 — 통일 사전 JSON (명사/인칭/지명/캐릭터명) ✅ 완료(잔여: 구 generic 도구 충돌 정리)

- [x] `tools/export_proper_nouns_dict.py` → `data/proper_nouns.json`(카테고리형): characters12/nations5/places4/common_terms9 + freq/variants/issues(표기흔들림)
- [x] `tools/apply_proper_nouns_dict.py`(edit 기준 CSV 통일, 드라이런 기본 --apply 반영)


### T4 — 대사 원문→번역 JSON + 편집기 UI (③ 연동) ✅ 완료

- [x] `tools/build_dialogue_map.py` → `data/dialogue_map.json`: {id,address,ja,ko,ship_ko,slot,kind,region,is_noise} (28,974행/실대사21,605)
- [x] 웹 편집기 `tools/dialogue_editor/`(stdlib server+web, :8780): 대사 JA→KO 표시·편집·저장(→dialogue_overrides.json)
- [x] **사전(T3) 연동**: 편집기에서 사전 조회/추가/수정/삭제 + "사전 검사"(명사 KO 불일치 행 플래그, 현재 286건 검출)
- [x] 편집→dialogue_overrides.json 역기록(빌드 적용 경로는 잔여)


### TZ — 전체 기능 점검 (진행)

- [x] 전 QA 실행: 무결성 PASS, overflow0/no_ko0, 영어잔존0, ROM placeholder0, 부팅/체크섬 OK (output fa7b08df).
- [x] 도구체인 4종 데이터 검증 + codex 리뷰(최대 누락=실화면 시각회귀 QA, VRAM 팔레트 먼저, 미번역 triage, 깨진주소 복구). agy는 긴 리뷰 프롬프트 반복 hang(unreliable) — 짧은 프롬프트만 가능.
- [x] **깨진 주소 복구**: `tools/fix_broken_addresses.py` — 드롭됐던 번역 7행 복구·출하(색적/미사일 섬 쟁탈전!/14일/상대 공격력 등), 중복106·junk93 정리, 3 슬롯-핏 override로 overflow 0 유지.


### Phase A0 — 문서·배포 무결성 게이트 (지금, ROM 무변경) [small] ✅ 완료

- [x] CLAUDE.md/AGENTS.md의 stale base(`v56_polished`=부재 파일) → 실제 base(원본 ROM)로 정정
- [x] dist 현행본 stale 확인: `tools/verify_dist_integrity.py` 실행 시 FAIL(output d680820d ≠ manifest/patch 4004d2c3)로 명시
- [x] `manifest.patched_sha == 실제 output sha == BPS/IPS 적용결과 sha` 3중 일치 검증 게이트 `tools/verify_dist_integrity.py` 작성(검증만; 재생성은 Phase F)


### Phase C-min — 빌드 무결성맵 + 부호소실 리포트 (검증 토대) [medium] ✅ 완료

- [x] 빌드가 write-log 부산물 생성: `temp/integrity_map.json` (addr·slot·기대바이트·fill·ko·level·kind), 25,357 텍스트 write 포착(import 18,041 + script 6,648 + fixed/raw/opt). 출력 바이트 무변경(SHA d680820d 동일) 검증.
- [x] 1차 QA 게이트 `tools/qa_integrity_map.py`: last-writer-wins 재구성 → `ROM == 기대 bytes`. 현재 391,370바이트 불일치 0 = PASS.
- [x] 부호소실 정량화(qa_integrity_map): import 부호보유 11,401행 전부 소실, 15,947자(`.`7522 `!`3539 `,`3222 `?`1093…) — **Phase B before 지표**.


### Phase P1 — 문장부호 글리프 스트레스 테스트 (Phase B 전제) [small] ✅ 정적 확인 완료

- [x] 정적 확인(무결성맵): 모든 스크립트 렌더러가 ASCII 부호를 이미 출하·렌더 — Part1 `.`441/`!`992/`?`350/`,`113/`(`3/`)`3/`:`2, Part2 `.`500/`!`125/`?`49/`,`300, 캠페인 `.`32 등. import 전용 영역(0x92-0x9E)만 부호 0(strip 피해).
- [x] 증거 강도: `. ! ? ,` 강(전 영역). `( ) :` 약(Part1만). **`" ' [ ] ;`는 출하 선례 0** → v1 정책에 반영(아래).


### Phase B — 문장부호 소실 복원 (최우선 실제 결함) [medium] ✅ 인코딩 검증 완료 (시각=Phase E)

- [x] `encode_fit`(build:8844) blanket strip 제거 → 부호 보존 후보(level 0~5) + strip 폴백(level 6~11). overflow/일본어 폴백 증가 0 보장.
- [x] 전각→ASCII 정규화: `…`/`・・・`→`...`, `。`→`.`, `、`→`,`, `「」『』`→`"`, smart quotes→ASCII. **보수적 v1: `[] {} ;`·`▼` 제거**, `. ! ? , ( ) :` 보존(`( ) :` provisional).
- [x] **中점(`・`/`·`) 버그 수정**(codex/gemini): 단독 제거의 단어결합 오류(`토이·박스`→`토이박스`) + `·` FALLBACK SJIS 재출하(208행)를 해결 — 연속→`...`, 단독→공백. `tools/qa_integrity_map.py`에 中점 잔존 FAIL 게이트 추가(현재 import 0).
- [x] 결과: 부호소실 11,401행/15,947자 → **11행/17자**(전부 benign: 미번역 JP 2·garbage 2·placeholder`[]`4·꽉찬슬롯 trailing 2). qqq 6행 복원 확인. overflow 0, no_ko 0, 무결성맵 PASS. temp SHA `f3c0014d`(中점 수정 후 재빌드).


### Phase C-full — QA 도구 진실화 (C-min 이후, Phase E와 병행) [medium]

- [x] phase6 EUC-KR 검출 → 예약코드(0x8840-0x9369) 카운트로 교체(패치 183k vs 원본 62k, 임계 100k로 분리; 정확검증=qa_integrity_map)
- [x] **신설 완료: `tools/qa_ascii_residuals.py`** — 큐레이션 UI 토큰 잔존 0 확인(PRESS START·GREEN EARTH·MISSION 등 전부 제거됨), 일반 sweep은 그래픽/폰트 노이즈뿐


### Phase E — 인게임 시각 회귀 매트릭스 (에뮬 fresh-boot + frame-hash) [large]

- [x] **월드맵 배경 영어 국가명 = stale savestate 확정**: 현재 ROM fresh 렌더는 한글 "레드스타"(영어 RED STAR 아님). qa_ascii_residuals도 GREEN EARTH/RED STAR 등 잔존 0. → 06시 savestate 비교 이미지가 stale이었음(실 잔존 아님).
- [x] **시각 검증(부분, 2026-06-16)**: 세이브스테이트 로드+A 진행 fresh 렌더로 CO프로필·전투 명령메뉴(정보/작전/시스템/저장/종료)·유닛/지형 정보(보병/평지)·월드맵 스토리 대사 전부 한글 정상, 깨짐/오버플로 없음. import-csv Phase B 대사(0xA0E71A `지키러 가겠지.`, 0xA0E771 `이건 전쟁이야.`)에 마침표 복원 확인, 박스 내 정상. 증거 docs/screenshots/SUCCESS_phaseE_*_2026-06-16.png.


### 최종 목표

- [x] 캠페인 전체 한글화 완료.
- [x] 전투 화면, HUD, 메뉴, 팝업, 결과 화면 한글화 완료.
- [x] 튜토리얼 구간을 먼저 끝까지 검수하고, 실제 화면 기준으로 깨짐을 제거.
- [x] `full`, `final`, `title_test` 산출물이 같은 한글화 상태로 빌드되도록 정리.
- [x] 잔여 일본어, 깨진 글자, 잘린 문장, 잘못된 색상/스프라이트를 제거.
- [x] 최종 BPS/IPS 패치 생성 및 round-trip 검증.


### 최근 완료

- [x] Part 2 오프닝 데모 신문/타이틀 잔여 영어 그래픽 정리.
- [x] 공통 콜드부트 `NINTENDO PRESENTS` 잔여 그래픽 한글화.
- [x] 공통 타이틀 화면 작은 부제/저작권/TM 잔여 영어 그래픽 정리.
- [x] Part 2 모드 메뉴/작전 선택 잔여 영어 그래픽 정리.
- [x] Part 2 컴패니언/작전실/오퍼레이션 선택 배경 그래픽 current ROM 재검증.
- [x] Part 2 튜토리얼 전투 메뉴/상태창/팝업 current ROM 재검증.
- [x] 1+2 선택 화면, Part 1, Part 2 타이틀/시작 텍스트 스타일 재검증.
- [x] Part 2 성공 결과 오버레이 current ROM 재검증.
- [x] Part 1/2 코스모랜드 진입 대사 span 잔여 정리.
- [x] 최신 preview BPS/IPS 패치와 manifest 재생성 및 round-trip 검증.
- [x] 잔여 visual-width 마지막 실제 문장 조각 추가 축약.
- [x] 잔여 visual-width 반복 UI/짧은 대사 후보 2차 축약.
- [x] 잔여 visual-width 실제 문장 후보 추가 축약.
- [x] 직접 패치 span 기준 visual-width QA 오탐 축소.
- [x] 튜토리얼/전투/캠페인 level1 표시 폭 잔여 0화.
- [x] 튜토리얼/전투/캠페인 level1 표시 폭 후보 2차 정리.
- [x] 튜토리얼/전투/캠페인 level1 표시 폭 후보 추가 정리.
- [x] 튜토리얼/전투/캠페인 표시 폭 상위 후보 추가 정리.
- [x] 보조 번역/고정 라벨 QA 커버리지 정합화.
- [x] Part 2 전투 ASCII HUD 테이블 잔여 정리.
- [x] `에게→에` 축약 부작용 문장 추가 정리.
- [x] `있는/없는` 축약 부작용 문장 추가 정리.
- [x] 조사 오류 전역 보정과 튜토리얼/캠페인 초반 축약 문장 추가 정리.
- [x] Part 2 유닛 설명 후반/승리 조건/통신 메뉴 문장 추가 정리.
- [x] Part 2 유닛/무기 설명 주소 override 추가 정리.
- [x] Part 2 캠페인 후반 제목/작전 안내 직접 패치 행 추가 정리.
- [x] Part 2 중후반 캠페인/유닛 설명 직접 스크립트 행 추가 정리.
- [x] Part 2 유닛 설명/CO 설명 소스 override와 작전 메뉴 화면 최신 ROM 재검증.
- [x] Part 2 CO 프로필/유닛 설명/전투 옵션 잔여 붙은 표현 추가 정리.
- [x] Part 2 전투 튜토리얼/브리핑/CO 설명 잔여 붙은 표현 추가 정리.
- [x] 튜토리얼 잔여 버튼명/국가명 표기와 캠페인 초반 직접 패치 행 추가 정리.
- [x] 튜토리얼 해상 유닛/색적/과외 메뉴/생산·점령·지형 수업 직접 패치 행 추가 정리.
- [x] 튜토리얼 저장/점령/수리/합류/보급/헬기/대공·로켓 설명 직접 패치 행 추가 정리.
- [x] 튜토리얼 전투 공격/체력/턴 종료 설명 직접 패치 행 추가 정리.
- [x] 전투/메뉴 고정폭 라벨 음악/표시 항목 추가 정리.
- [x] 캠페인 이글 생존 반복 후일담/료 재대결/최종 자유 전투 조언 직접 패치 행 추가 정리.
- [x] 캠페인 아스카 아버지 평가/이글 생존 확인/전후 정리 직접 패치 행 추가 정리.
- [x] 캠페인 호이프 정신 회복/블루문 재건/아스카 부녀 재회 직접 패치 행 추가 정리.
- [x] 캠페인 헬보우즈 격퇴/빌리·호이프 승리 직후 대화 직접 패치 행 추가 정리.
- [x] 캠페인 호이프·모프·이글 합류/헬보우즈 본격 전투 조언 직접 패치 행 추가 정리.
- [x] 캠페인 흑막 확인/아스카 위험/맥스·빌리·호이프 합류 직접 패치 행 추가 정리.
- [x] 캠페인 료 복제인간 등장/이글 합류/최종전 초입 수도 점령 조언 직접 패치 행 추가 정리.
- [x] 캠페인 정찰부대 구출/도미노 선배 언급/보병 수송 경로 조언 직접 패치 행 추가 정리.
- [x] 캠페인 도미노 대 이글 반복 대면/료 오해 해소/항공 유닛 격파 조언 직접 패치 행 추가 정리.
- [x] 캠페인 도미노 수송선 보호/탑승 유닛 피해 없음 조언 직접 패치 행 추가 정리.
- [x] 캠페인 그린어스 반복 진입/15거점 점령/수송선 하차 조언 직접 패치 행 추가 정리.
- [x] 캠페인 해상 유닛/수송선 보호/보급·잠수함 유지 조언 직접 패치 행 추가 정리.
- [x] 캠페인 시간 제한 색적 맵 조언/이글 반복 대화/항공 유닛 격추 조언 직접 패치 행 추가 정리.
- [x] 캠페인 그린어스 진입/맥스 정면승부/15일 제한 전멸전 직접 패치 행 추가 정리.
- [x] 캠페인 숨은 중요 물자 수송선/암초·잠수함 탐색 조언 직접 패치 행 추가 정리.
- [x] 캠페인 이글 3차전/그린어스 습격 오해/항공 유닛 격추 조언 직접 패치 행 추가 정리.
- [x] 캠페인 대공미사일 방어/10일 생존/수송선·암초 이동 조언 직접 패치 행 추가 정리.
- [x] 캠페인 모프 침공/12거점 점령 조건/쇼군 브레이크 조언 직접 패치 행 추가 정리.
- [x] 캠페인 아스카 자백 추궁/료 능력 평가/동료 선택 조언 직접 패치 행 추가 정리.
- [x] 캠페인 료·도미노 대 아스카 직전 대화 직접 패치 행 추가 정리.
- [x] 캠페인 아스카 도미노 능력 평가/료 유인/16거점 조언 직접 패치 행 추가 정리.
- [x] 캠페인 빌리·아스카·휘프 추적 대화 직접 패치 행 추가 정리.
- [x] 캠페인 도미노/아스카 색적·수송선 보호/점령 승부 조언 직접 패치 행 추가 정리.
- [x] 캠페인 맥스 단독/아스카 전술 평가/수면제 함정 조언 직접 패치 행 추가 정리.
- [x] 캠페인 키쿠치요 포위전/공장·공항·항구 안내/15거점 조언 직접 패치 행 추가 정리.
- [x] 캠페인 10장/공장 사용 안내/다리 방어 조언 직접 패치 행 추가 정리.
- [x] 캠페인 옐로코멧/키쿠치요 특전부대/간접 공격 유닛 처리 조언 직접 패치 행 추가 정리.
- [x] 캠페인 그린어스 공중부대/이글 도입/폭격기 우선 격추 조언 직접 패치 행 추가 정리.
- [x] 캠페인 숲/암초 매복/빌리·캐서린 대화/수송선 반복 조언 직접 패치 행 추가 정리.
- [x] 캠페인 휘프 중요 거점/12거점 점령 조건/눈 맵 반복 조언 직접 패치 행 추가 정리.
- [x] 캠페인 색적 맵 반복/빌리 숲 매복 조언 직접 패치 행 추가 정리.
- [x] 캠페인 맥스 전함/간접 공격/쇼군 능력 조언 직접 패치 행 추가 정리.
- [x] 캠페인 눈 이동력/휘프 재패배/수송선 보호 조언 직접 패치 행 추가 정리.
- [x] 캠페인 색적 맵/휘프 해군/해상전 우회 조언 직접 패치 행 추가 정리.
- [x] 캠페인 맥스 도입/공장·항구/휘프 해상전/포위 대응 직접 패치 행 추가 정리.
- [x] 캠페인 그린어스 조우/공중 유닛/２회 행동 조언 직접 패치 행 추가 정리.
- [x] 캠페인 얀 후속/공장 생산/빌리 간접 공격 조언 직접 패치 행 추가 정리.
- [x] 캠페인 첫 전투 무전/쇼군 브레이크 조언 직접 패치 행 추가 정리.
- [x] 튜토리얼 지형 과외/공격 전략 연장 수업 직접 패치 행 추가 정리.
- [x] 튜토리얼 전투 기본/지형 방어력 수업 직접 패치 행 추가 정리.
- [x] 튜토리얼 생산 유닛 이동/점령/수입 설명 직접 패치 행 추가 정리.
- [x] 튜토리얼 공장/공항/항구 생산/기본 생산 실습 직접 패치 행 추가 정리.
- [x] 튜토리얼 과외 수업/색적 이동 경로/메뉴 설명 직접 패치 행 추가 정리.
- [x] 튜토리얼 매복/쇼군 브레이크/날씨/색적/정찰차 직접 패치 행 추가 정리.
- [x] 튜토리얼 잠수함 잠항/수송 유닛 패배 안내 직접 패치 행 추가 정리.
- [x] 튜토리얼 수송선 탑재/하차/해상 유닛 연료 직접 패치 행 추가 정리.
- [x] 튜토리얼 상륙/호위함/전함/잠수함 직접 패치 행 추가 정리.
- [x] 튜토리얼 공략 후속/대공미사일/로켓포 직접 패치 행 추가 정리.
- [x] 튜토리얼 공중 유닛 연료/대공전차 직접 패치 행 추가 정리.
- [x] 튜토리얼 중전차/수송헬기/전투헬기 직접 패치 행 추가 정리.
- [x] 튜토리얼 합류/보급/자주포/수송차 직접 패치 행 추가 정리.
- [x] 튜토리얼 수리/공격 범위/벽 만들기/합류 직접 패치 행 추가 정리.
- [x] 튜토리얼 점령 내구도/공략 힌트/결과 대사 직접 패치 행 추가 정리.
- [x] 튜토리얼 저장/맵 메뉴/점령 수업 직접 패치 행 추가 정리.
- [x] 튜토리얼 초기 전투/지형 효과/이동 비용 직접 패치 행 추가 정리.
- [x] 튜토리얼 생산/점령/전투 수업 직접 패치 행 추가 정리.
- [x] 튜토리얼 지형/이동 비용 직접 패치 행 표기 추가 정리.
- [x] 튜토리얼 보정 행/맵 메뉴/지형 설명 잔여 표기 정리.
- [x] 튜토리얼 인트로/초반 전투/점수 설명 표기 추가 정리.
- [x] 튜토리얼 전투 초중반 점령/회복/공격범위 안내 압축문 추가 정리.
- [x] 후기 튜토리얼 색적/공중/해상 유닛 설명 압축문 추가 정리.
- [x] 튜토리얼 생산/이동/전투 기초 안내 압축문 추가 정리.
- [x] Part 2 캠페인 전투 조언/작전 안내 압축문 추가 정리.
- [x] Part 2 전투/유닛 정보 설명 압축문 추가 정리.
- [x] Part 2 전투/룰/유닛/상점 설명 압축문 표기 정리.
- [x] Part 2 표시/애니/통신 일반 UI 문자열 표기 정리.
- [x] Part 2 전투/메뉴 고정폭 UI 라벨 표기 정리.
- [x] Part 2 캠페인 최종전 합류/헬보우즈전/후일담/마지막 이글전 문장 정리.
- [x] Part 2 캠페인 도미노-이글 재습격/보병 8일 방어/복제 료 초입 문장 정리.
- [x] Part 2 캠페인 이글 반복/모프 해상전/수송선 보호 미션 문장 정리.
- [x] Part 2 캠페인 대공미사일 방어 후반/이글 3차전/숨은 수송선/맥스 시간제한 미션 문장 정리.
- [x] Part 2 캠페인 아스카 매복/도미노 분석/모프 초입 조언 문장 정리.
- [x] Part 2 캠페인 10장 공장/공항/항구 조언과 키쿠치요 공장 대사 정리.
- [x] Part 2 캠페인 초반 공중부대/이글/도미노/키쿠치요 초입 문장 정리.
- [x] Part 2 캠페인 초반 거점 점령/빌리 숲 매복/공중부대 조언 문장 정리.
- [x] Part 2 캠페인 초반 수송선/맥스 전함/색적 반복 조언 문장 정리.
- [x] Part 2 캠페인 초반 휩해군/눈 지형 조언 문장 정리.
- [x] Part 2 캠페인 초반 맥스/휩 해상전/색적맵 조언 문장 정리.
- [x] Part 2 캠페인 초반 얀/빌리/그린어스 조언 문장 정리.
- [x] Part 2 튜토리얼 지형 과외 후반/첫 캠페인 조언 문장 정리.
- [x] Part 2 튜토리얼 전투/지형 수업 문장 추가 정리.
- [x] Part 2 튜토리얼 점령 심화/전투 수업 초입 문장 정리.
- [x] Part 2 튜토리얼 생산 메뉴/기본 조작 설명 문장 정리.
- [x] Part 2 튜토리얼 과외수업 생산 설명 후속 문장 정리.
- [x] Part 2 튜토리얼 과외수업 명령 설명 문장 정리.
- [x] Part 2 튜토리얼 후속 색적/정찰차/이동경로 설명 문장 정리.
- [x] Part 2 튜토리얼 후속 수송선/잠항/날씨 설명 문장 추가 정리.
- [x] Part 2 튜토리얼 후속 해상 유닛 설명 후보 문장 정리.
- [x] Part 2 튜토리얼 `공중전` DAY 2~DAY 4 bad-route 전투/메뉴/전환 UI current ROM 검수.
- [x] Part 2 튜토리얼 `공중전` DAY 1 턴 종료 후 적 턴 대사/전투/일자 전환 current ROM 검수.
- [x] Part 2 튜토리얼 `공중전` 초입 전투 애니메이션 HUD current ROM 검수.
- [x] Part 2 튜토리얼 `공중전` 초입 자유 행동과 첫 공격 UI current ROM 검수.
- [x] Part 2 튜토리얼 `하늘 제패!` 성공 후 `공중전` 초입 대사 current ROM 재검수 및 문장 깨짐 보정.
- [x] Part 2 튜토리얼 `하늘 제패!` 성공 조건 record72 잔존 디버그 및 DAY 5 record69 선처리 분기 재검수.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 3/5 턴 종료 입력 역추적 및 DAY 6 후속 적용.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 5 record67 5HP 분기 후속 재확인.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 4 record09 위치 변형과 DAY 5/6 후속 분기 추가 비교.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 5 포병 타깃 재탐색과 record66 제거 분기 확인.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 6 이후 진행 가능성 추가 확인.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 4 대체 분기와 DAY 5 후속 행동 비교.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 4~DAY 7 진행 후보 검증.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 3 실제 조작 루트와 DAY 4 전환 검증.
- [x] Part 2 튜토리얼 `하늘 제패!` DAY 2 실제 조작 후보 재검수 및 상태 팝업 지형 테이블 보강.
- [x] Part 2 튜토리얼 `하늘 제패!` 성공 후/다음 작전 연결부 디버그 검수 및 문장 깨짐 정리.
- [x] Part 2 튜토리얼 `하늘 제패!` 초입/대공미사일/로켓포 설명 실기 검수 및 문장 경계 정리.
- [x] Part 2 튜토리얼 `하늘의 적` 대공전차 실기 루트 검증 및 전투 화면 잔여 영어 정리.
- [x] 전체 한글 예약코드/글리프 기반 빌드 파이프라인 구축.
- [x] Part 1 대화 ASM hook과 Part 2 tilemap/glyph-cache renderer hook 적용.
- [x] 이름 입력 그리드 A-Z/a-z/0-9 표시와 미리보기 흐름 안정화.
- [x] GBA 헤더 체크섬 QA를 `0xA0..0xBC` inclusive 기준으로 정리.
- [x] 타이틀/선택 화면 한글 로고 방향 정리 및 기본 색상/배치 조정.
- [x] Part 2 지도/미션/레벨/체크/캐서린 등 주요 OBJ 라벨 일부 한글화.
- [x] Part 2 튜토리얼 초반 커서/보병/수송차/이동/점령/지형/자주포/맥스/수송헬기 구간 문장 깨짐 교정.
- [x] Part 2 `0xA06B80-0xA14000` 구간의 일본식 말줄임표, 장음 기호, 미매핑 보조 번역을 정리.
- [x] `docs/plan.md`와 `.claude/todo.md`를 제거하고 진행 기준을 루트 `todo.md` 하나로 통합.
- [x] 활성 안내 문서의 구식 `docs/plan.md`/`.claude/todo.md` 참조를 루트 `todo.md` 기준으로 정리.
- [x] Part 2 `0xA14000-0xA30000` 구간의 CSV 텍스트 슬롯 기준 잔여 일본어/깨짐 후보 정리.
- [x] Part 2/캠페인 추가 슬롯 정리.
- [x] `D8F000-E18000` 문장형 튜토리얼/캠페인 후보 감사.
- [x] Part 2 보호 전투 UI 테이블의 `항복` 명령 표시 개선.
- [x] Part 2 보호 전투 UI 테이블의 짧은 명령/상태 토큰 추가 개선.
- [x] Part 2 보호 UI의 메뉴/상태 공통 토큰 추가 개선.
- [x] Part 2 보호 UI의 반복 국가명 라벨 개선.
- [x] Part 2 보호 UI의 무기/시스템/플레이어 라벨 추가 개선.
- [x] Part 2 보호 UI의 초반 미션 제목 일부 개선.
- [x] Part 2 보호 UI의 미션 제목 추가 개선.
- [x] Part 2 보호 UI의 유닛/무기 풀 일부 추가 개선.
- [x] Part 2 보호 UI의 문맥 충돌 라벨 개선.
- [x] Part 2 튜토리얼 실제 ROM 대사 범위 1차 잔여 일본어 감사.
- [x] Part 2 후속 실제 ROM 대사 범위 1차 잔여 일본어 감사.
- [x] Part 2 후속 UI/통신 실제 ROM 문자열 추가 정리.
- [x] Part 2 후속 사거리/유닛명 UI 라벨 추가 정리.
- [x] Part 2 통신 UI 문장 품질 정리.
- [x] Part 2 반복 UI/미션 제목 테이블 추가 정리.
- [x] Part 2 전투/도감 반복 테이블의 유닛·무기·미션 라벨 추가 정리.
- [x] Part 1 이름/문자 그리드 보호 범위 보강.
- [x] Part 1 보호 UI 테이블의 공통 전투/룰 설정 토큰 한글화.
- [x] Part 1 이름 입력 첫 프롬프트 깨짐 완화.
- [x] Part 1 이름 확정 뒤 숨은 이름 패딩 글자 정리.
- [x] Part 1 이름 인사말 suffix 공백 통일.
- [x] 최근 빌드 검증:
- [x] Part 2 튜토리얼 턴 종료 안내 문장 간격 개선.
- [x] Part 2 튜토리얼 전투 중 쇼군 프로필/전술 설명 문장 품질 개선.
- [x] Part 2 튜토리얼 전투 메뉴의 쇼군 라벨 가독성 개선.
- [x] Part 2 튜토리얼 작전 설명의 보병 안내 문장 깨짐 수정.
- [x] Part 2 튜토리얼 작전 설명의 승리조건 문장 경계 수정.
- [x] Part 2 튜토리얼 전투 행동 메뉴의 `待機` 잔여 일본어 수정.
- [x] Part 2 튜토리얼 대기 명령 설명 문장 재분절.
- [x] Part 2 튜토리얼 작전 설명의 점령 조건/명령 문장 재분절.
- [x] Part 2 튜토리얼 초반 선택/버튼 안내 문구 안정화.
- [x] Part 2 튜토리얼 하단 대화 폰트 취약 표현 추가 정리.
- [x] Part 2 튜토리얼 컨트롤 키 표기 한글화.
- [x] Part 2 튜토리얼 지형 정보 설명의 `COST` 영문 잔여 제거.
- [x] Part 2 튜토리얼 시스템 메뉴 설명의 `BGM` 영문 잔여 제거.
- [x] Part 2 전투 상태 팝업 유닛명 OBJ 라벨 한글화.
- [x] Part 2 첫 전투 커서 팝업의 본부 OBJ 라벨 한글화.
- [x] Part 2 첫 전투 커서 팝업의 소형 지형/유닛 OBJ 라벨 한글화.
- [x] Part 2 전투 상태 목록 헤더 한글화.
- [x] Part 2 전투 시작 오버레이의 잔여 일본어 제거.
- [x] Part 2 전투 HUD의 고정 `DAY` 문자 타일 한글화 준비.
- [x] Part 2 전투 HUD의 `DAY` 영문 라벨 제거.
- [x] Part 2 첫 전투 진입 직후 소개 대사 줄붙음 개선.
- [x] Part 2 첫 전투 메뉴의 쇼군 라벨 깨짐 완화.
- [x] Part 2 첫 전투 정보 패널의 프로필 라벨 오독 완화.
- [x] Part 2 캠페인 프롤로그 초반 대사 일본어/깨짐 정리.
- [x] Part 2 캠페인 진입 메뉴의 주요 OBJ 그래픽 라벨 한글화.
- [x] Part 2 모드 선택 화면의 잔여 대형 영어 로고와 편집 하위 버튼 한글화.
- [x] Part 2 진입 스플래시 BG 로고 한글화.
- [x] Part 2 프롤로그 후반/첫 전투 진입 대사 일본어 갭과 줄잘림 정리.
- [x] Part 2 첫 전투 튜토리얼 `종료` 명령 설명 분기 정리.
- [x] Part 2 첫 전투 튜토리얼 수송차 설명의 일본어 잔여 제거.
- [x] Part 2 첫 전투 튜토리얼 보급/연료 설명 조각 정리.
- [x] Part 2 첫 전투 수송차 실제 탑승/하차 조작 및 후속 전투 진행 검증.
- [x] Part 2 점령/상태창 설명 튜토리얼 루트 탐색.
- [x] Part 2 첫 전투 실제 공격 명령과 전투 화면 검증.
- [x] Part 2 첫 전투 클리어 결과 화면 그래픽 잔여 제거.
- [x] Part 2 첫 전투 수송차 이후 공격 설명 문장 재정리.
- [x] Part 2 첫 전투 공격 튜토리얼 문장/입력 대기 안정화.
- [x] Part 2 전투 시스템 메뉴의 애니 옵션 ASCII 잔여 제거.
- [x] 레포 임시 산출물 용량 정리.
- [x] 레포 대형 임시 탐색 산출물 재정리.
- [x] 레포 재생성 산출물 재정리.
- [x] Part 2 첫 전투 분기 탐색 산출물 재정리.
- [x] Part 2 첫 튜토리얼 범위의 추가 제어 갭 일본어 감사.
- [x] Part 2 튜토리얼 후속 범위의 2글자 제어 갭 일괄 정리.
- [x] Part 2 후속 대사/정보 범위의 짧은 일본어 조각 정리.
- [x] Part 2 `0xA00000-0xA40000` 캠페인/튜토리얼 제어 갭 정리.
- [x] Part 2 초반 튜토리얼 제어 갭 추가 정리.
- [x] Part 2 `0xA00000-0xA14000` 슬롯 밖 제어 갭 재감사.
- [x] Part 2 `0xA14000-0xA30000` 슬롯 밖 제어 갭 재감사.
- [x] Part 2 `0xA30000-0xA34000` 유닛 설명/도움말 갭 정리.
- [x] Part 2/공통 튜토리얼·유닛명 슬롯 밖 조사 갭 추가 정리.
- [x] Part 2/공통 반복 전투 UI 라벨 추가 정리.
- [x] Part 2/공통 수입·편집 UI 라벨 겹침 수정.
- [x] Part 2/공통 옵션값 반복 테이블 추가 정리.
- [x] Part 1/공통 전투 메뉴 반복 `상황` 라벨 정리.
- [x] Part 1/Part 2 보호 UI의 CO명·통신 상태 라벨 정리.
- [x] Part 1/Part 2 보호 유닛·장비명 코드열 정리.
- [x] Part 1 이름 확정 직후 인사 문장 붙음 완화.
- [x] Part 2 미션 시작 오버레이의 흰 조각 깨짐 제거.
- [x] Part 2 튜토리얼 직접 패치 대사의 로마자 버튼 표기 추가 제거.
- [x] Part 2 전투 상태 팝업 유닛명 가독성 개선.
- [x] Part 1 첫 작전/전투 진입 오버레이 한글화.
- [x] Part 1 튜토리얼 전투 화면의 `CHECK!` OBJ 라벨 한글화.
- [x] Part 2 미션 전환 BG의 `MISSION` 영문 잔여 제거.
- [x] Part 1 메뉴 로고 하단 영문 보조문구 제거.
- [x] `full`, `final`, `title_test` 산출물 한글화 상태 통일.
- [x] Part 1 이름 입력 UI의 고정 영어 라벨 한글화.
- [x] Part 2 첫 전투 튜토리얼 보병/점령 안내 문장 품질 개선.
- [x] Part 2 첫 전투 튜토리얼 점령 설명 줄잘림 추가 개선.
- [x] Part 2 첫 전투 튜토리얼 수송차 설명 깨짐 정리.
- [x] Part 2 첫 전투 튜토리얼 수송차 후속 설명 줄잘림 추가 개선.
- [x] Part 2 첫 전투 튜토리얼 공격/커서창 설명 깨짐 정리.
- [x] Part 2 첫 전투 튜토리얼 점령 내구력 설명 사전 정리.
- [x] Part 2 첫 전투 튜토리얼 종료 오입력 안내 문구 가독성 개선.
- [x] Part 2 튜토리얼/후속 설명의 `HP` 표기 잔여 제거.
- [x] Part 2 통신/링크 UI 문장 조사 오류와 영문 잔여 정리.
- [x] Part 1/Part 2 잔여 ASCII 국가명·캠페인 라벨 정리.
- [x] Part 1/Part 2 공통 전투·메뉴 ASCII 라벨 정리.
- [x] Part 2 CO/컴패니언 설명 테이블의 남은 `HP`/일본식 프로필 문구 정리.
- [x] Part 2 후속 튜토리얼의 작전/상황 메뉴 설명 문구 개선.
- [x] Part 2 프롤로그 화면 상단 OBJ 라벨 오독 개선.
- [x] Part 2 모드/캠페인 선택 화면 OBJ 라벨 가독성 보강.
- [x] Part 1 이름 확정 뒤 인사말 공백/문장부호 회귀 수정.
- [x] Part 1 작전룸 선택 화면의 짧은 옵션 라벨 가독성 개선.
- [x] Part 2 튜토리얼/CO 설명의 잔여 깨짐 후보 추가 정리.
- [x] Part 2 첫 전투 튜토리얼 전투 설명 문구 재검수.
- [x] Part 2 첫 전투 소형 커서 팝업의 보급차 라벨 순서 수정.
- [x] 레포 대형 임시/중복 생성물 정리.
- [x] Part 2 첫 전투 진입부의 작은 폰트 오독 문구 정리.
- [x] Part 1/Part 2 보호 전투 UI 사전의 자금 `G` 라벨 제거.
- [x] Part 1 이름 확정 뒤 작전룸 안내 문구 표기 통일.
- [x] Part 2 튜토리얼/전투 설명의 잔여 `HP` 표기 추가 제거.
- [x] Part 2 캠페인/상점 안내의 잔여 `SELECT` 표기 제거.
- [x] 공통 전투/통신 UI의 고정 ASCII 라벨 추가 정리.
- [x] 레포 용량 재정리.
- [x] 공통 전투 유닛/지형/장군/스탯 고정 ASCII 테이블 한글화.
- [x] Part 1/Part 2 설정·CO 보조 ASCII 테이블 추가 한글화.
- [x] Part 1/Part 2 디버그·백업 유틸 보조 ASCII 테이블 정리.
- [x] Part 2 프롤로그/첫 전투 전 지도 대사 문구 품질 개선.
- [x] Part 2 첫 전투 시작 연출 잔여 일본어 그래픽 제거.
- [x] Part 2 첫 전투 조작 UI 1차 분기 검수.
- [x] Part 2 첫 전투 상단 자금 HUD와 진입 대사 깨짐 추가 정리.
- [x] Part 2 전투 시스템 옵션 메뉴 라벨 가독성 개선.
- [x] Part 2 첫 전투 첫 턴 유닛 이동/대기 메뉴 추가 검수.
- [x] 재생성 가능한 임시 산출물 정리.
- [x] Part 2 첫 전투 첫 턴 전체 종료 경로 재검수.
- [x] 잔여 일본어 감사 도구 루프 버그와 저주소 UI 라벨 정리.
- [x] Part 2 모드 선택 화면 하단 설명문 줄깨짐 개선.
- [x] 레포 재생성 산출물 추가 정리.
- [x] Part 2 첫 전투 수송차/보급 튜토리얼 조각 경계 재정리.
- [x] 레포 임시 산출물 정리.
- [x] Part 1 이름 확정 뒤 모드/작전룸 안내 문구 재검수.
- [x] Part 2 CO 정보/프로필의 잔여 `HP`/오독 문구 정리.
- [x] Part 2 첫 전투 클리어 뒤 결과/랭크 설명 문구 선제 정리.
- [x] Part 2 두 번째 미션 진입/브리핑/지형효과 설명 정리.
- [x] Part 2 월드맵 지역명 라벨 잔여 픽셀 정리.
- [x] 레포 임시 산출물 재정리.
- [x] Part 2 저장 확인 선택지 fresh 경로 재검증.
- [x] Part 2 두 번째 미션 후반 대사와 CO 정보 패널 정리.
- [x] 레포 임시 캡처/캐시 재정리.
- [x] 빌드 안정성과 save 관련 보호 테이블 복구.
- [x] Part 2 미션 2 자주포 설명 슬롯 선제 정리.
- [x] Part 2 튜토리얼 공격 복습 목표 마커 회귀 수정.
- [x] Part 2 튜토리얼 미션 2 지형/이동비용/지형효과 설명 재분절.
- [x] Part 2 튜토리얼 미션 2 지형효과 뒤 종료 안내/경고 문장 재분절.
- [x] Part 2 튜토리얼 미션 2 지형효과 뒤 공격/턴종료/2일째 지형 설명 루트 확인.
- [x] Part 2 튜토리얼 미션 2 작전 중 저장 설명 분기 정리.
- [x] 레포 대량 임시 산출물 재정리.
- [x] 레포 임시 캡처 추가 정리.
- [x] Part 2 튜토리얼 미션 2 저장 설명 이후 적 전멸/성공 대사 검증.
- [x] 레포 임시 산출물 재정리.
- [x] 레포 불필요 산출물 추가 정리.
- [x] Part 2 저장 확인 뒤 다음 작전 선택/점령훈련 초반 브리핑 정리.
- [x] 레포 대형 임시 탐색 산출물 재정리.
- [x] Part 2 점령훈련 이동/점령/바주카 초반 조작 루트 정리.
- [x] 레포 대형 임시 탐색 산출물 추가 정리.
- [x] Part 2 점령훈련 둘째 날 점령 완료 구간 검수.
- [x] Part 2 점령훈련 바주카병 도시 선택/힌트 구간 검수.
- [x] 레포 임시 probe 산출물 재정리.
- [x] Part 2 점령훈련 후 자주포/보급/간접공격 분기 검수.
- [x] Part 2 자주포 설명 뒤 도시 방어 분기 초입 문장 보정.
- [x] Part 2 도시 방어 경전차/바주카병 이동 분기 검수.
- [x] 레포 대형 생성 산출물 정리.
- [x] Part 2 도시 방어 턴 종료/수송차 탑재·하차 분기 검수.
- [x] Part 2 수송차 설명 뒤 공략 힌트/첫 자유 행동 검수.
- [x] Part 2 도시 방어 자유 행동 보급차/턴 종료 루트 탐색.
- [x] Part 2 도시 방어 3일째 공격 분기와 행동 메뉴 축약 라벨 1차 패치.
- [x] Part 2 도시 방어 4~9일째 상단 전선 정리 루트와 휘프 UI명 보정.
- [x] Part 2 도시 방어 10일째 왼쪽 바주카병 공격 진행과 지형 OBJ 용어 통일.
- [x] Part 2 도시 방어 day12~15 적 전멸 승리 루트와 중전차 초입 문장 보정.
- [x] Part 2 중전차 작전 공략 힌트 문장과 조작 시작 상태 검수.
- [x] Part 2 중전차 작전 day1 전선 배치와 적 턴 대사 검수.
- [x] Part 2 중전차 작전 day2~day4 하단 도시 점령 루트 검수.
- [x] Part 2 중전차 작전 day4~day6 바주카 압박/턴 종료 루트 검수.
- [x] Part 2 중전차 작전 day6 공격과 day7 복귀 루트 검수.
- [x] Part 2 중전차 작전 day7~day11 전선 진행 루트 검수.
- [x] Part 2 중전차 작전 day11~day14 전선 압박 루트 검수.
- [x] Part 2 중전차 작전 성공 후보 루트 day1 재구축.
- [x] Part 2 중전차 작전 새 성공 후보 day2~day4 분기 검수.
- [x] Part 2 중전차 작전 새 성공 후보 day3 회피 분기 검수.
- [x] Part 2 중전차 작전 새 성공 후보 day4~day7 중전차 제거 루트 검수.
- [x] Part 2 중전차 작전 새 성공 후보 day7~day12 잔여 적 정리 한계 확인.
- [x] Part 2 중전차 작전 새 성공 후보 day7~day10 빠른 압박 분기 재검수.
- [x] Part 2 행동 메뉴 `공격`/`대기` OBJ 아이콘 가독성 개선.
- [x] Part 2 중전차 작전 day9~day10 record 68 겹침 우회 분기 추가 검수.
- [x] Part 2 중전차 작전 day8 추가 선제피해와 day5 로켓포 입력 재검수.
- [x] Part 2 중전차 작전 day8 재현 분기와 record 03 생존 로켓포 경로 재검수.
- [x] Part 2 중전차 작전 record 03 조기 전진과 탄약/미끼 효과 재검수.
- [x] Part 2 중전차 작전 early-r3 후속 target switch와 record 01 보병 처리 분기 검수.
- [x] Part 2 튜토리얼 행동 메뉴/상태 팝업 그래픽 캐시 여부 재검수.
- [x] Part 2 튜토리얼 fresh-run 행동 메뉴 `대기` 표시 검증.
- [x] Part 2 튜토리얼 fresh-run 행동 메뉴 `공격` 표시 재확보.


### 현재 우선순위

- [x] 미션 2 공격 복습 뒤 보병 선택, 지형 이동비용 설명, 산 지형 공격, 지형효과 비교 설명을 실제 캡처로 재검증한다.
- [x] 지형효과 비교 뒤 종료 안내와 조기 종료 경고 문장을 실제 캡처로 재검증한다.
- [x] 지형효과 비교 뒤 두 보병 공격, 턴 종료, 적 턴, 2일째 지형효과/이동비용 설명까지 실제 캡처로 재검증한다.
- [x] 2일째 자유 행동 복귀 뒤 저장 메뉴 설명 분기까지 실제 캡처로 재검증한다.
- [x] 저장 설명 뒤 남은 적 전멸, 성공 대사, 결과 화면, 저장 확인창까지 실제 캡처로 재검증한다.
- [x] 저장 확인 뒤 다음 작전 선택, 점령훈련 초반 브리핑, 첫 전투 진입 안내까지 실제 캡처로 재검증한다.
- [x] 점령훈련 이동/점령 조작 분기에서 실제 진행 루트를 확정하고 후속 대사를 검수한다.
- [x] 점령훈련 남은 부대 이동, 턴 종료, 적 턴/다음 점령 대사까지 실제 캡처로 이어간다.
- [x] 자주포·간접공격 설명 분기까지 실제 캡처로 재검증한다.
- [x] 자주포 설명 뒤 도시 방어/경전차 이동 안내 분기를 실제 캡처로 이어간다.
- [x] 도시 방어 힌트 뒤 공격범위 표시, 남은 유닛 이동, 턴 종료/적 턴 분기를 실제 캡처로 이어간다.
- [x] 수송차 설명 뒤 공략 힌트와 첫 경전차 도시 배치 분기를 실제 캡처로 이어간다.
- [x] 도시 방어 자유 행동의 바주카병/보병/보급차 대기와 턴 종료/다음 일자 복귀를 실제 캡처로 이어간다.
- [x] 도시 방어 3일째 경전차/바주카병 공격 분기를 실제 캡처로 이어간다.
- [x] 도시 방어 4~9일째 상단 전선의 경전차/보병 제거 루트를 실제 캡처로 이어간다.
- [x] 도시 방어 자유 행동의 자주포/승리조건 진행을 이어간다.
- [x] 중전차 작전 새 성공 후보 루트를 `p2_heavy_success_day10_after_day9_opt_pressure_endturn.ss0` 또는 `p2_heavy_success_day9_after_day8_opt_u0_3_6_endturn.ss0`에서 이어가고, 마지막 record 68을 day10 안에 제거하거나 브레이크/회복 입력으로 마무리하는 루트를 실제 캡처로 확정한다.
- [x] 경전차/전차 행동 메뉴의 `공격`/`대기` 축약 라벨 패치를 current ROM 전투 화면에서 검증한다.
- [x] 적 턴 CO명 `휘프` 보호 UI 치환을 current ROM 적 턴 배너에서 검증한다.
- [x] 보급차 행동 메뉴와 작전 메뉴의 아이콘형 라벨 경로를 추적해 한글화한다.
- [x] 중전차 작전 day2~day4 작전/행동 메뉴의 current-ROM visible 잔여를 재검증하고, 새 일본어/영어 라벨이 보이면 별도 그래픽 경로를 추적한다.
- [x] 중전차 작전 새 성공 후보 day2 화면에서 확인된 상태 팝업 지형명 `道路`/`都市`와 행동 메뉴 OBJ 라벨을 실제 ROM 그래픽 경로로 추적한다.
- [x] Part 2 성공 결과 OBJ 오버레이 `作戦成功`을 `작전성공`으로 패치한다.
- [x] `vwxy` 소문자 미리보기는 상태 파일 캡처 기준 정상 표시.
- [x] `예/아니오` 선택지는 상태 파일 캡처 기준 정상 표시.
- [x] 이름 입력 첫 프롬프트는 콜드부트 재진입 기준 `이름알려줘`로 정상 표시.
- [x] Part 2 미션 시작 오버레이의 흰 픽셀 조각/가로선 깨짐은 `sel_064` 캡처 기준 제거.
- [x] 대사 끝 하얀 픽셀 깨짐과 회색 글자 변화는 후속 대사 흐름에서 추가 검증.
- [x] Part 2 저장 확인 compact 선택지는 fresh 진행 기준 문장 붙음 없이 `예아니`로 표시 확인.
- [x] Part 1 튜토리얼 전투 화면의 기타 잔여 OBJ/팝업 라벨 한글화.


### 남은 큰 항목

- [x] Part 2 튜토리얼 잔여 대사 전체 검수 및 깨짐 수정.
- [x] Part 2 튜토리얼 전투 화면 명령, 메뉴, 도움말, 팝업 검수.
- [x] Part 2 본편 캠페인 대사 전체 플레이스루 검수.
- [x] Part 2 본편 전투 HUD, OBJ 라벨, 결과 화면, 상점, CO 정보 검수.
- [x] Part 2 컴패니언/작전실/오퍼레이션 선택 화면 잔여 그래픽 한글화.
- [x] Part 1 본편 캠페인 대사 전체 플레이스루 검수.
- [x] Part 1 본편 전투 HUD, OBJ 라벨, 결과 화면, 작전실, 상점, CO 정보 검수.
- [x] 1+2 선택 화면, 1편 본편, 2편 본편의 타이틀/시작 텍스트 스타일 재검증.
- [x] final/title_test/full 산출물 간 한글화 차이 제거.
- [x] 배포 전 BPS/IPS 재생성, manifest 갱신, round-trip 검증.


### 🟢 UI 에디터 실캡처/비교 (2026-06-16, 사용자 요청 "임의 라인까지 실캡처 대공사")

- [x] canvas-hijack 실캡처 검증: 빠른도달 화면(07_part2_main_menu)의 텍스트 슬롯(0xA2C098)을 임의 문자열로 덮어 헤드리스 nav→실렌더 캡처 성공. = 임의 라인 실캡처의 토대.
- [x] **A3 렌더러 범위버그 발견·수정**(부산물): 0x9369(1030 상한)→0xE2A7. 2350 확장분 1320음절 A3 '?' 깨짐 해소. 출하 무영향(잠복)이었으나 Part2 편집/프리뷰 충실성에 필수. 회귀 가드+dist 재생성.
- [x] `tools/preview_capture.py`: 임의 텍스트 인게임 실캡처 엔진(compare(ja,ko)=원본 ROM↔패치 ROM). canvas 레지스트리(확장형)+해시 캐시+CLI.
- [x] 대사 에디터(8780): 행별 🎮 실캡처 버튼→원본(JA)↔적용(KO) 헤드리스 캡처 모달. /api/preview+/preview 서빙. E2E 검증.
- [x] 스프라이트 에디터(8781): 원본↔적용 비교(타일 디코드=인게임 1:1). /api/compare+/api/render(orig/patched/edit). build_changed 감지. E2E 검증.


### 🟢 추출 노이즈 정리 + 비트맵 손상 수정 + 스프라이트 계측 (2026-06-17)

- [x] **해독 불가/판독 불가/깨진 문자열/의미 불명 345행 해결**: 전부 추출 노이즈(코드영역 302 +
- [x] **비트맵 손상 수정(부산물·중요)**: `깨진 문자열`이 빌드 PLACEHOLDER_KO에 누락되어 18행이
- [x] 방어: PLACEHOLDER_KO에 깨진문자열 계열 추가 + 18 span DENY_REGIONS 등록 + qa_placeholder_residuals
- [x] **스프라이트 WYSIWYG 빌드레이아웃 계측 2→26 blocks**(서브에이전트): 16 LZ77 라벨 함수


### 🟢 OBJ 합성 스프라이트 WYSIWYG + 잘린주소 정리 (2026-06-17, 사용자 "1,2 다")

- [x] **OBJ 직접기록 4종 합성 스프라이트 노출**: 흩어진 ROM 오프셋 라벨군을 type=synthetic으로
- [x] **잘린 주소 2행(7EBF·808) 정리**: 정주소 행과 동일 중복 확정 → 제거(+빈행3, 주소정규화6).


### 🟢 스프라이트 편집→ROM 라운드트립 (2026-06-17, 사용자 "스프라이트 반영도")

- [x] **편집→ROM 역기록 구현**: build `apply_sprite_overrides`(synthetic perm역변환/lz77 재압축/raw),
- [x] E2E 검증: synthetic·lz77 편집→재빌드→ROM 반영·decode 일치, revert→해시복귀, lz77 fit/overflow skip.


### 🟢 통합 scene 에디터 실캡처/분리/WYSIWYG 보강 (2026-06-17)

- [x] **scene별 실제 스크린샷 연결**: `tools/capture_scene_screenshots.py`로 `data/scene_catalog.json`의 `screenshot.checkpoint`를 헤드리스 mGBA에서 캡처해 `temp/scene_screenshots/<checkpoint>_patched/frame.png`와 provenance를 생성. 신규 서버 경로 `/scene_shots/<checkpoint>.png`로 안전 서빙. 실제 game scene 28/28 캡처 존재(고유 checkpoint 16개), `99_unassigned_review`는 검토 bucket으로 제외.
- [x] **merged scene 분리**: scene catalog를 20 scene+review에서 29 scene+review(실제 game scene 28 + review 1)로 확장. 1+2 선택 Part1/Part2, Part1 월드메뉴/싱글·맵 하위메뉴/통신 하위메뉴/작전로고/캠페인/전투, Part2 인트로/캠페인/전투/결과 계열을 화면 단위로 분리. 중복 `source` 라벨은 `sprite_ids` 정확 배정으로 오프셋별 분리.
- [x] **스프라이트 실화면 배치 편집**: 통합 에디터 스프라이트 패널은 `실화면 배치`/`타일 그리드` 2모드가 아니라, 레이아웃 있는 스프라이트의 기본 타일그리드 자체를 실제 화면 출력 bbox 크기와 cell별 OBJ 팔레트로 배치해 렌더. 클릭 좌표를 visible bbox→OAM cell→tile pixel로 역매핑해 기존 `sprites_overrides.json` 저장/빌드 경로와 호환. 투명 픽셀도 출력 크기 배치 타일그리드에서 직접 칠할 수 있음.
- [x] **1편 LZ77 타일 레이어 fallback 정정**: 1편 로고/하위메뉴 라벨은 ROM 저장 순서가 `64×32 + 16×32`이고 실제 출력은 80×32이므로, 빌드 인코더(`part1_logo_layer_to_tiles`)의 역배치로 단일 편집면을 구성. 1편 옵션 블록도 `64×32 + 64×32` 저장 순서를 실제 128×32 출력 레이어로 재조립. 기존 캡처 OAM이 더 큰 bbox(`152×68`, `80×128`, `170×128`)로 잡힌 1편 항목도 빌드 레이어 역배치를 우선한다. 미션 로고는 128×32, 캐서린 이름은 96×8 편집면으로 보정. 8782 직접 검증: `케이블 대전` 64×40 타일시트 → 출력 80×32, canvas 240×96.
- [x] **LNB 출력배치/대사 병합 수정**: 좌측 스프라이트 썸네일은 `has_onscreen`이면 raw `/render` 대신 `/api/sprite/onscreen`을 사용하고 `출력배치` 배지를 표시. 그래픽 중심 scene도 관련 대사 bucket을 같은 좌측 목록에 병합해 스프라이트와 대사 행을 함께 선택/편집할 수 있게 함. 접힌 scene count에는 `관련대N`을 표시.
- [x] **미배정 스프라이트 표시 정정**: `99_unassigned_review`의 1875개는 텍스트 누락이 아니라 자동 LZ77 scan 그래픽 1874 + 폰트 1임을 coverage/LNB에서 `미배정 텍0·폰트1·그래픽1874`로 분리 표시. 텍스트 후보 미배정은 0.
- [x] **리뷰 반영**: agy 9건 + codex P2 5건을 반영. `obj1d=false` 로컬 tile 변환, 투명 hit-test 2단계, cell별 팔레트, 정적 배경 dim+OAM bbox 마스킹, `/scene_shots` allowlist/`no-store`, stale provenance 검출, skip 전 ROM SHA 검증, pending 요청 무효화, explicit `sprite_ids` 검증을 추가.
- [x] **검증**: `python3 tools/build_scene_catalog.py`, `python3 tools/capture_scene_screenshots.py --force`, `python3 -m py_compile tools/build_scene_catalog.py tools/capture_scene_screenshots.py tools/scene_editor/server.py tools/sprite_editor/server.py`, `node --check tools/scene_editor/static/app.js`, JSON 검사, HTTP API/path 스모크, Chrome headless CDP 브라우저 검증 통과. 사용자 정정 반영 후 8782에서 layout 있음/1편 LZ77 역배치/LNB 썸네일/관련대사 표시 확인. 전체 배정 스프라이트 112개는 tile API, onscreen_data, onscreen PNG를 일괄 검증해 실패 0(onscreen 81, raw fallback 31). 브라우저 증거 스크린샷/감사 결과: `temp/browser_verify/scene_editor_visible_output_grid.png`, `temp/browser_verify/8782_lnb_related_dialogue_final.png`, `temp/browser_verify/assigned_sprite_audit.json`.


### 🟢 B팀/쪼롱이님 스크립트 안전 병합 + UI 에디터 동기화 (2026-06-17)

- [x] **병합 원칙 적용**: `docs/MERGE_PLAN_BTEAM_2026-06-16.md`에 따라 B ROM/코드테이블은 병합하지 않고, `temp/bteam/script.txt`의 0x08Fxxxxx 포인터를 원본 ROM 포인터와 대조해 원본 주소로만 매핑. 제어마커(`㉠㉡㉢`)·inline 제어 토큰·slot overflow·no slot 항목은 자동 적용 제외.
- [x] **안전 후보 32건 적용**: 현재 UI/빌드 표시 번역이 비어 있고 슬롯에 들어가는 B팀 텍스트만 `data/dialogue_overrides.json`에 추가. 대표 항목: `플레이 조건`, `평지/산/숲`, `이름 입력`, `정보`, `종료`, Part2 미션명(`경계 방어전`, `포로 구출 작전`, `전율의 2주일`, `희망의 대해로`, `해상 요새 폭격`, `대함대 전격전`, `불의 비`, `결전 전`), 통신 상태(`미접속`, `준비 중`, `접속 중`), `색적`.
- [x] **도구화**: `tools/import_bteam_script.py` 추가. 기본 실행은 `temp/bteam/import_candidates.json` 리포트 생성, `--apply-missing`일 때만 안전 후보를 적용. 재실행 기준 `safe_missing_candidates=0`, `applied=0`로 중복 적용 없음.
- [x] **UI 맵을 빌드 권위로 동기화**: `tools/build_dialogue_map.py`가 `build_korean_full.py`의 주소/원문/TEXT override, `data/dialogue_overrides.json`, direct script patch, `temp/integrity_map.json`의 ship_ko를 반영하도록 수정. ROM에는 한글인데 UI 에디터에는 미번역으로 보이던 항목(`플레이법`, `신병기 탈취!`, `둘의 두뇌전`, `해 VS 공!` 등)을 현재 빌드 기준으로 표시.
- [x] **검증**: `build_korean_full.py` 재빌드 overflow 0/no_ko 0, `qa_text_fit.py` overflow 0/no_ko 0, `qa_placeholder_residuals.py` 0, `qa_japanese_residuals.py --min-score 13` 신규 문제 없음, `qa_visual_regions.py` 23 checks, `phase6_basic_test.py` ROM OK. 8782 서버 재시작 후 `/api/state` dirty=false, ROM SHA `24c073c2ec5c57c6`.
- [x] **UI 에디터 반영 검증**: 새 ROM 기준 `tools/capture_scene_screenshots.py --force`로 scene screenshot 16개 재캡처, API stale/missing 0(`99_unassigned_review` 제외). Chrome headless CDP로 `http://127.0.0.1:8782` 검증: 전투 시작 회전/개시 오버레이 scene은 스프라이트 10개+관련 대사 300행이 LNB에 함께 표시, LNB 썸네일은 `/api/sprite/onscreen` 출력배치 사용, 우측 스프라이트 편집 캔버스는 `타일 그리드 · 출력 크기 배치`/실화면 레이아웃으로 열림. 증거: `temp/browser_verify/8782_bteam_battle_start_sprite.png`, `temp/browser_verify/8782_bteam_battle_start_dialogue.png`, `temp/browser_verify/8782_part1_submenu_onscreen.png`, `temp/browser_verify/8782_bteam_verify.json`.


### 🟢 쪼롱이님/B팀 권위 대사·용어사전 덮어쓰기 반영 (2026-06-17)

- [x] **권위 반영 원칙 전환**: 미번역만 채우는 방식에서 벗어나, `temp/bteam/script.txt`가 원본 ROM 포인터와 안전하게 매핑되고 빌드 슬롯에 들어가는 조각은 기존 번역이 있어도 쪼롱이님/B팀 문장으로 덮어씀. 재현 명령: `python3 tools/import_bteam_script.py --apply-authoritative --out temp/bteam/import_authoritative.json`.
- [x] **적용 규모 정정(리뷰 반영)**: B script 6403행 전체 매핑, 후보 6414행, 최종 안전 적용 counter 6726건(`applied_authoritative_line` 969, `applied_authoritative_group` 2372 중심), 최종 `data/dialogue_overrides.json` 7615건(기존 base override 811 포함). codex 리뷰에서 B팀 제어표식 과적용 누수를 확인해, override를 HEAD 기준으로 재생성한 뒤 안전 파서 결과만 다시 적용. 자동 제외는 `line_slot_overflow` 301, `group_slot_overflow` 338, `no_group` 357, fragment mismatch/제어마커 등이며 `temp/bteam/import_authoritative.json`에 전부 남김.
- [x] **명사/인칭/지명 사전 재작성**: `data/proper_nouns.json`과 빌드 정규화가 쪼롱이님 계열 표기를 권위로 사용. 주요 확정: `ショーグン`=`사령관`, `ホイップ`=`호이프`(문맥상 `휩` 허용), `コスモランド`=`코스모 랜드`, `マクロランド`=`매크로 랜드`, `맵 디자인`, `사령관 브레이크/선택`.
- [x] **CSV/빌드/UI 동기화**: `python3 tools/apply_proper_nouns_dict.py --apply`로 `data/translation_for_import.csv`도 동일 용어로 461행 갱신. `data/dialogue_map.json`/scene editor API가 현재 출하 ROM 기준 문장을 표시하도록 재생성. Part2 적 턴 CO 배너/OBJ 라벨 `휘프`도 `호이프`로 직접 그래픽 패치하고, `tools/export_proper_nouns_dict.py` 시드도 같은 기준으로 수정해 사전 재생성 시 되돌아가지 않게 함.
- [x] **CSV 개행 정책**: `data/translation_for_import.csv`는 기존 CRLF 포맷 유지. 전체 LF 정규화로 18k행 churn을 만들지 않기 위해 `.gitattributes`에서 해당 CSV의 whitespace check만 제외해 `git diff --check`가 통과하도록 함.
- [x] **잔류 금지 표기 0 확인**: ROM 게이트에서 `휘프`, `쇼군`, bare `장군`, `코스모랜드`, `매크로랜드`, `마크로랜드`, `디자인 지도`, `지도 디자인` 잔류 0. `qa_terms_from_rom.py`에 B팀 제어표식 hard gate를 추가해 `i` 플레이어명 마커, menu/control prefix, branch/wait marker, `㉠㉡㉢`, B팀 변수 토큰 잔류 0도 확인. UI API term check: Part1 story `사령관` 201/`호이프` 64/`휩` 5/`코스모 랜드` 2, Part2 story `사령관` 225/`호이프` 12/`휩` 14/`코스모 랜드` 4/`매크로 랜드` 16, 금지 표기 0.
- [x] **최종 agy 리뷰 반영**: `tools/export_proper_nouns_dict.py`는 기존 사전의 `edit`/`allowed`/`allowed_ko`를 보존 병합하도록 수정해 재생성 시 수동 예외가 사라지지 않게 함. `qa_terms_from_rom.py`의 B팀 변수 토큰 검사는 `import_bteam_script._VAR_TOKEN_TERMS` 전체 목록을 사용하도록 확장하고, `i`/menu prefix/branch-wait 경계 조건을 보강. temp export 테스트와 ROM gate 재실행 모두 PASS.
- [x] **UI 초과 표시 정합화**: scene editor의 대사 목록/저장 API가 raw byte 길이만 보던 문제를 수정. 서버가 `build_korean_full.encode_fit`으로 실제 빌드 fallback(공백/구두점 정리)을 계산해 `fits/encoded_len/fit_level`을 내려주고, 프런트는 그 값을 기준으로 `초과` 배지를 표시. 2편 스토리 3046그룹 `fits_false=0`, 브라우저 `visibleOverBadges=0` 확인.
- [x] **검증**: `python3 tools/build_korean_full.py` 후 ROM SHA `ee17c7d97cd7913d`(full/final/title_test 동일). `qa_integrity_map.py` PASS(바이트 불일치 0), `qa_text_fit.py` overflow 0/no_ko 0, `qa_terms_from_rom.py --show 20` hard 0 PASS + B팀 제어표식 잔류 0, `qa_placeholder_residuals.py` 0, `qa_japanese_residuals.py --min-score 13` 후보 1(기존 table-like 카나열), `phase6_basic_test.py` ROM OK, `qa_visual_regions.py` 23 checks. `tools/capture_scene_screenshots.py --force`로 scene screenshot 고유 checkpoint 16개 재캡처, API stale/missing 0(`99_unassigned_review` 제외).
- [x] **8782 브라우저 실검증**: Chrome headless CDP로 `http://127.0.0.1:8782` 직접 조작. 홈 `scene 30 · 대사그룹 9061/9061 · 텍스트 스프 112 · 미배정 텍0·폰트1·그래픽1874`, mixed scene `2편 메인 메뉴`는 `스프라이트 14`와 `대사 3607`을 같은 LNB 아래 표시. 스프라이트 편집은 출력 120×16px OAM 재조립 canvas(nonblank 4608/4608 sample)로 열림. `2편 전투 시작 회전/개시 오버레이`는 스프라이트 10/10개가 `/api/sprite/onscreen` 출력배치 썸네일이며, `전투개시 배너`가 출력 128×32px 편집면으로 열림(nonblank 8192/8192 sample). 사전 모달 input 값도 `사령관`/`호이프`/`코스모 랜드`/`매크로 랜드`로 확인. 전체 배정 스프라이트 112개 API 검증(tile/onscreen_data/PNG 실패 0, onscreen 94, raw fallback 18). 증거: `temp/browser_verify/browser_verify_report_final.json`, `temp/browser_verify/scene_editor_sprite_editor_final.png`, `temp/browser_verify/scene_editor_battle_start_sprite_editor_final.png`, `temp/browser_verify/scene_editor_bteam_dialogue_final.png`, `temp/browser_verify/scene_editor_dict_final.png`.


### 🟢 UI 에디터 전 장면 실화면 진입점/잔여 컨테이너 재검증 (2026-06-22)

- [x] **1편 잔여 컨테이너 실렌더 스캔**: `temp/story_range_breakscan.py`/`temp/story_exact_watch.py`에 병렬 worker와 입력 정책을 보강한 뒤 실제 savestate 기반으로 19d, 19b, 19a, 19e 잔여 범위를 재검증. 결과: 19d exact 352건 hit 0, 19d range 2376건 hit 0, 19b 224건 hit 0, 19a 430건 hit 0, 19e 24건 hit 0.
- [x] **2편 잔여 컨테이너 실렌더 스캔**: 30a 14건 hit 0, 30b는 기존 split `30b1` hit를 확인 후 제외 재스캔 48건 hit 0, 30c 68건 hit 0, 30d/30g 경계 보정 후 294건 hit 0, 30e 264건 hit 0, 30f 910건 hit 0. 모든 결과는 `temp/scene_entrypoints/part2_*_residual_break_subset_*/results.json`에 재현 가능하게 남김.
- [x] **30d/30g 경계 오류 수정**: render-breakpoint가 `0x00A1C000`(`g_00A1BFD8`)에서 호크/블랙홀 대사를 실제 화면으로 잡았고, 기존 `30d2_part2_green_earth_story_late` 끝이 `0xA1C000`이라 대사 그룹을 중간에서 잘랐음. `tools/build_scene_catalog.py`에서 30d2/30d 끝을 `0xA1C06C`로 늘리고 30g 시작을 `0xA1C06C`로 이동. 기존 `scene_30d2_part2_green_earth_story_late` 화면 흐름에 속하는 것으로 판정.
- [x] **카탈로그/진입점/브라우저 검증**: `python3 tools/build_scene_catalog.py` 재생성 후 `audit_scene_catalog.py --strict`, `audit_scene_entrypoints.py --strict`, `audit_scene_semantics.py --strict` 모두 critical 0. Chrome CDP 검증 `python3 tools/verify_scene_editor_cdp.py` 결과 game scene 63, total scene 78, sprite 107, failure 0. 리포트: `temp/browser_verify/all_scene_editor_verify.json`.
- [x] **codex+agy 리뷰 반영**: 두 리뷰 모두 13개 container를 완료로 간주하지 말 것, 특히 container에 대표 entrypoint/checkpoint가 남으면 실제 scene으로 오해될 수 있음을 지적. `tools/build_scene_catalog.py`가 container에는 `entrypoint`를 붙이지 않도록 수정하고, `audit_scene_catalog.py`/`audit_scene_entrypoints.py`/`audit_scene_semantics.py`가 container entrypoint를 critical로 잡도록 강화. 원천 `data/scene_entrypoints.json`/`data/screen_checkpoints.json`에서도 container 13개 대표 항목을 제거. 재생성 후 checkpoint 88→75, game scene unique checkpoint 63 유지, strict audit critical 0, CDP failure 0.
- [x] **잔여 container 증거 정식화**: `data/scene_residual_scans.json`과 `tools/audit_scene_residual_scans.py` 추가. 13개 container(대사 2884개)에 대해 결과 파일 존재/case 수/hit 수/known split hit를 strict로 감사한다. 19c/30b/30d에서 나온 hit 3건은 기존 split 또는 경계 수정으로 설명되고, 최종 감사 결과 scan case 7793, hit 3, known hit 3, critical 0. 마지막 `88_common_comm_labels`는 Part1/Part2 menu/focus/row 상태 1967건에서 hit 0으로 독립 화면 노출 없음.
- [x] **최종 리뷰 반영 보강**: codex가 지적한 스프라이트 편집면 crop 문제를 수정. `tools/scene_editor/static/app.js`의 onscreen 편집 viewbox는 nontransparent content bbox가 아니라 서버 layout `os.x0/os.y0/os.w/os.h`를 그대로 사용한다. `tools/verify_scene_editor_cdp.py`는 onscreen 원본/편집 캔버스 native size가 layout×zoom과 일치하지 않으면 실패하도록 강화했고, 재검증 결과 scene 63, sprite 107, failure 0. residual evidence도 현재 ROM SHA와 각 `results.json` SHA를 `data/scene_residual_scans.json`에 고정하고 audit가 검사하도록 보강했다.


### 🟢 캠페인 대사 단어붙음 해소 — 메시지 재배치(repoint) + 완성도 인프라 (2026-06-23)

> 외부 서양판 한글패치(락이다님 GPT 영어베이스)와 완성도 비교 중, **qa_text_fit가 dialogue_overrides
> (쪼롱이님/B팀)를 walk에서 누락**해 단어붙음 504건을 못 보던 QA 사각지대를 발견. 쪼롱이님 **어절/단어를
> 바꾸지 않고**(빌드 공통 정규화 `・・・→...`·전각공백→반각만 — in-place 렌더와 동일, 새 변형 아님)
> 외부판과 동일한 free-space repoint 기법으로 해소.

- [x] **메시지 포인터 테이블 RE**: Part2 대사 = `0x08A357B4`(3315엔트리, 단조증가) 테이블 참조, 메시지 중간
  참조 없음(순차). 여유공간 `0xA3CF14~0xB00000`(799KB 미사용 0xFF). docs/research.md에 기록.
- [x] **재배치 엔진** `tools/dialogue_repoint.py`: 슬롯-fit으로 공백 제거된 쪼롱이님 라인만 `encode_full_fidelity`
  (반각공백 완전충실)로 복원, 메시지 전체를 0xA3D000~에 쓰고 포인터 갱신. 비대상 라인·제어 스켈레톤·구주소 불변.
  **5중 안전가드**: ①포인터 ROM 내 정확히 1개(테이블) ②(라인+gap) 정확분해 ③라인 간 텍스트 중첩(병합 override) 없음
  ④여유공간 비중첩 ⑤un-jam 후 시각폭>50(박스한계) 라인 제외(=잘림 회귀 방지).
- [x] **빌드 통합**: `build_korean_full.py` "2.9" 블록(체크섬 직전), `--no-repoint-dialogue` 플래그.
  `encode_fit`의 정규화를 `normalize_for_fit`로 추출(동작 보존) + `encode_full_fidelity` 추가.
- [x] **결과**: **188 메시지 / 214 라인 단어붙음 해소**, merged-skip 4, wide-skip 2. ROM SHA `0725a175fae699b9`.
- [x] **검증**: 구조 무결성 errors=0(`temp/compare/verify_repoint_struct.py`, --no-repoint 베이스 기준 —
  A=587 control gap / B=214 fixed / C=373 non-fix preserved / 포인터 188/188). 부팅·체크섬 OK,
  무결성맵 PASS(바이트OK), overflow0/no_ko0, 일본어 잔존 새 노출 0. **3-렌즈 적대검증(crash/fidelity/render)
  모두 safe·high**, 독립 에이전트가 pre-repoint 베이스 복원→재배치 재실행 시 출하 ROM과 byte-identical(diff=0) 확인.
- [x] **QA 사각지대 해소** `tools/qa_dialogue_jamming.py`: dialogue_overrides 단어붙음 추적 + repoint 효과
  (in-place 단어붙음 429 / 축약 73 → repoint 214 해소 → 잔여 단어붙음 244는 Part1·0xB8 분산포인터 영역).
- [x] **ROM 직접 무결성 게이트** `tools/qa_repoint_integrity.py`(codex 리뷰): temp manifest 불신,
  출하 ROM에서 in-place 베이스 복원→repoint 재실행이 출하본과 **byte-identical** 검증. PASS.
- [x] **바이트예산 SSOT** `tools/text_metrics.py`(+`test_text_metrics.py`): encoded_len/visual_cells,
  app.js encLen 미러 박제 + node 패리티 테스트(py↔js 25,319행 일치) + 2350 미수록 음절 검출.
- [x] **엔드유저 원클릭 배포** `dist/apply_patch.py`(stdlib only, BPS 적용+SHA256/CRC 검증+자동탐색) +
  `dist/README_KO.md` + 2026-06-23 BPS/IPS/manifest 재생성. verify_dist_integrity PASS,
  apply_patch 엔드투엔드(원본→결과 SHA=output) 일치 확인.
- [x] **외부 참조 정리** `docs/external_ref/create-kr-patch/`(mcpads/create-retro-game-kr-patch 스킬, MIT)
  + `CREATE_KR_PATCH_NOTES.md`(GBA 적용 인사이트). 증거리포트 `docs/reports/COMPLETENESS_EVIDENCE_2026-06-23.md`.
- 잔여: Part1(0xD8~0xE0)·0xB8 단어붙음 244건은 분산포인터 구조라 repoint 테이블 확장에 별도 RE 필요(후속).
  실기(real GBA) 검증, 재배치 폭>50 제외 2건의 실화면 확인 미완.


### 🟢 Part1 캠페인 대사 단어붙음 해소 — 커맨드-스트림(0x19) repoint, 런타임 트레이싱 (2026-06-23)

> Part2 메시지테이블 repoint(214라인) 후, Part1 대사는 테이블이 아니라 **커맨드 스트림**임을 mGBA
> 디버거 런타임 트레이싱으로 RE하고 repoint 확장. 상세 docs/research.md 續3.

- [x] **mGBA 소스 빌드/디버거 RE**: mGBA 0.10.5 소스 클론(temp/mgba-src). 디버거 구동(mDebuggerRun의
  hasBreakpoints→step-mode→checkBreakpoints) 확인 → **디버거는 원래 정상**(이전 "사망" 결론은 테스트 주소
  false-negative). breakpoint·loadstate 후 breakpoint 작동 확정(0x08337382 7352히트).
- [x] **런타임 트레이싱**: 텍스트 ptr store 0x08B1299C에 breakpoint, 작전룸(base_a)에서 메뉴 이동 →
  r4=메시지주소 캡처(0x08DF5D60 등) → 포인터 위치(0xDF7A9C) 앞 워드 = **opcode 0x19**(show-message).
- [x] **커맨드-스트림 repoint**: `dialogue_repoint.scan_command_messages`(0x19+ptr 1805 메시지) +
  `extra_messages` 파라미터. 기존 가드(단일포인터/decompose/헤더갭struct/폭/merged) + **과확장 span
  가드**(참조 포인터가 자기 span 안이면 skip). 빌드 통합(build "2.9" 블록).
- [x] **결과**: Part1+2 합쳐 **357 메시지 / 403 라인 단어붙음 해소**(Part1 169 메시지 추가). 잔여 244→85.
  ROM SHA `b59df0e252ad6b59`.
- [x] **검증(10 게이트 PASS)**: 부팅/체크섬, 무결성맵 바이트OK, overflow0/no_ko0, ROM 직접 무결성
  (in-place 복원→재배치=byte-identical, 357/403), 구조검증 errors=0, 단어붙음 회귀게이트(85≤85),
  일본어잔존 무변, text_metrics, 배포 무결성, apply_patch 엔드투엔드 SHA 일치. 디코드 검증: 재배치 Part1
  메시지가 실제 캐서린 튜토리얼 한글("거기가 아니에요. 여기서 A 버튼이에요." 등)로 un-jam.
- [x] **디버거 도구**: tools/mgba_harness.c에 break hasBreakpoints 진단 추가(/tmp/mgbah_dbg). 핵심 명령
  `break ADDR LOG`(HARDWARE만; SOFTWARE는 mGBA에서 abort), `watchaddr`(fresh-boot만), `loadstate`.
- 잔여: 단어붙음 85(0xB8/0xEC 비-0x19 + merged/wide/multi-ptr/과확장). 실기 플레이테스트(savestate가
  구빌드라 폰트캐시 불일치로 시각검증은 신빌드 savestate 필요).


### 🟢🟢 Part1 repoint 인게임 검증 완료 — fresh-boot 풀 네비 신규 트리거 (2026-06-23)

> savestate는 pre-repoint라 캐시된 구 포인터/폰트 VRAM 때문에 검증 불가(research.md 續4). **fresh-boot
> 풀 네비**(콜드부트→타이틀→Part1→새게임→이름입력 'AAA'→인트로 대사)로 **신규 0x19 트리거** 달성.

- [x] **fresh-boot 네비**: screen_checkpoints의 fresh nav 패턴(press/frames) 확장. 콜드부트→Part1 타이틀
  →새게임→**이름 그리드**(A-Z/a-z/0-9, fresh라 글리프 깨끗) 'AAA' 입력→확인→캐서린 인트로 대사.
- [x] **결정적 증거 ①(메커니즘)**: 인트로 대사 진행 중 store(0x8B1299C)가 **r4=0x08A446DC** 캡처 —
  **재배치 여유공간(0xA3D000~0xB00000) 주소**. 게임이 갱신된 커맨드-스트림 포인터를 따라 **재배치본을
  여유공간에서 로드**함을 인게임 확증.
- [x] **결정적 증거 ②(디코드)**: 0xA446DC(게임이 읽은 곳)=`"레드스타의 사령관,캐서린이에요."`(공백 복원,
  un-jam) ↔ 원위치 0xDF8E6C(in-place 죽은 사본, 안 읽힘)=`"레드스타의사령관캐서린이에요"`(단어붙음).
  → 재배치본=쪼롱이님 원문, 게임이 그걸 읽음.
- [x] **결정적 증거 ③(시각)**: fresh-boot 대사가 모두 깨끗한 공백 렌더 — "반가워 AAA 님" /
  "나는 캐서린." / "첫 번째 작전은 전투 개시 예요" / "레드스타의 사령관,…". 증거:
  `docs/screenshots/SUCCESS_part1_repoint_freshboot_reloc_2026-06-23.png` 외 2.
- **결론**: Part1 repoint가 실게임(에뮬 fresh-boot)에서 작동 확정. 재배치 메시지 = 여유공간에서 로드 +
  un-jam 렌더. ROM SHA 08d50127.

## [2026-06-24] 외부판 비교 재분석 + 격차 클로징 (claude+codex+agy 적대적)
- **전 63 game scene 재캡처**: ROM 변경(08d50127→a582a7cb)으로 stale된 76 캡처를 `capture_scene_screenshots.py --force`로
  재생성 → `audit_scene_entrypoints.py` critical=0. "장면 진입기로 모든 장면 진입 확인" 요구 충족.
- **실화면 잔존 시각검증(13에이전트)**: 정적 잔존스캔 21k행이 거의 노이즈임을 확증하고, 실제 화면 잔존을
  HIGH 3(이름 라벨 가타카나)·MED 4로 정밀 도출. `temp/visual_verify_result.json`.
- **B팀 대사 변형 복원**: codex 적발 — 작업트리에서 `0x00DF5E12/35/56`(코스모랜드 설명 대사)이 슬롯 여유에도
  축약·개작돼 있었음 → HEAD 권위본 복원, 재빌드 검증. 절대제약(쪼롱이/B팀 불변) 보호.
- **신규 QA 도구 2종**: `qa_pixel_width.py`(렌더러 advance 8px/4px 모델), `qa_csv_integrity.py`(CSV 손상 탐지·심각도분류).
- **UI 에디터 라이브 검증**: :8782 대사 save/슬롯 하드게이트/스프라이트 save·revert 전부 동작.
- **dist 재생성+PASS**: 보정 ROM a582a7cb에 BPS/IPS/manifest 동기, `verify_dist_integrity` PASS.
- 전체: `docs/reports/COMPARISON_AND_GAP_CLOSE_2026-06-24.md`. ROM SHA a582a7cb.

## [2026-06-24 정리] scene 기반 통합 UI 에디터 /goal — Phase 0~8 완료 이전
> todo.md에서 이전. 상세 증거는 git history(2026-06-17~24 커밋)와 아래 항목.

- **Phase 0~4 완료**: scene_catalog 토대(20→78 scene, 대사 9061 100%배정), 단일서버 :8782(read-only MVP),
  통합 UI(LNB scene 아코디언+우측 편집), 대사+스프라이트 편집 이식, proper_nouns 사전 CRUD, 2줄=2칸, 스프라이트 onscreen WYSIWYG.
- **Phase 5 완료**: 대사/스프라이트 preview 모달, POST /api/build 비동기 job + polling, /api/download/gba.
- **Phase 6 완료**: encLen 바이트예산 하드게이트(한글2/ASCII1), \n 멀티라인 입력칸, 초과 저장차단.
- **Phase 7 완료(part1 canvas 제외)**: scene canvas ready/none, preview_canvases.json 외부화, 캐시키 수정,
  scene proof screenshot(capture_scene_screenshots.py), merged scene 분리(29), 전투개시 오버레이 분리.
- **Phase 8 검증**: byte-identical 정합성, 구 2서버 기능 parity, py_compile+node --check, Chrome CDP 브라우저 검증.
- **codex+agy 1·2차 리뷰 반영**: static 경로탈출 가드, 슬롯 하드게이트, 2350 미수록 차단, 모달 닫힘 버그,
  프리뷰 canvas 불일치, 워크플로 5차원 감사(43에이전트, critical 0) 12 major 반영.
- **쪼롱이/B팀 권위 반영**: bteam/script.txt 재매핑 override 7615, 용어사전 정규화(사령관/호이프/코스모랜드/매크로랜드),
  qa_terms_from_rom.py B팀 control residual hard gate.
- **1·2편 모든 화면 캡처/진입점 재검증(2026-06-22)**: 1편 19x·2편 30x story bucket savestate+렌더 breakpoint
  재검증 hit 0, scene catalog 엄격감사 critical 0, 8782 game scene 63/sprite 107 failure 0,
  13 container residual scan manifest(scan 7793/hit 3 known).
- **외부판 비교 완성도(2026-06-23)**: Part2 repoint 214라인+Part1 repoint 191라인(합계 357/403, 쪼롱이 불변),
  qa_dialogue_jamming.py, text_metrics.py SSOT, dist/apply_patch.py 원클릭 배포.

## [2026-06-24 후반] B팀 보호 5중화 + CSV ROM-진실 + 편집 커버리지 (정석 전수 진행)
- **B팀(쪼롱이) 보호 5층** (codex·agy 적대 리뷰 반영): ①권위문 복원(0xDF5E12/35/56) ②`data/bteam_addresses.json`(3340)
  +`bteam_baseline.json`+`tools/qa_bteam_drift.py`(drift 0) ③`:8782`+`:8780` `_save_line` save-time 차단(confirm_bteam 필요)
  ④`--accept`=`AW_BTEAM_ACCEPT=1` 승인 ⑤`verify_dist_integrity`에 drift+CSV 게이트 연동. 절대제약 사고 방지 다중화.
- **B1 CSV 손상 ROM-진실 검증**: `qa_csv_integrity.py`를 출하 ROM 디코드 권위로 재작성(가나/한자만 일본어, 0x81 심볼 제외,
  의도적 테이블 제외). CSV 손상 239행이나 **ROM 실제 일본어 텍스트 잔존 0**. 빌드 inline 리터럴이 권위라 CSV 손상 미전파 입증.
- **편집 커버리지(쪼롱이 요구)**: 실대사 19450/19650(99.0%) 편집가능, 차단 200=정당(font/컴팩트UI/pair, 사유 노출).
  스프라이트 1979 전부 scene/review 도달·편집.
- **A1 de-risk**: `korean_glyphs_8px.json`(1028음절 8x8)으로 96×8 CO 이름 OBJ에 한글 직접 렌더 경로 확보. CO 테이블 0x081BE68/stride0x44/19 OBJ.
- 전 게이트 PASS: integrity/overflow0/no_ko0/ascii0/scene critical0/bteam drift0/csv ROM잔존0/dist PASS. ROM SHA a582a7cb.

## [2026-06-24] A1 완료 — CO 프로필 이름 OBJ 19개 가타카나→한글 렌더
- **핵심 RE 정정**: CO 이름 OBJ는 96×8이 아니라 **48×16 col-major**(글리프=8×16=top+bot 2타일, 6글리프).
  이전 "8px 높이라 한글 illegible" 판단은 오판 — 실제 16px라 11px galmuri가 깔끔히 들어감.
- **방법**: CO 테이블 0x081BE68(stride 0x44) 첫 포인터로 19개 OBJ 식별 → `render_galmuri_8x16(ink=15)`로
  한글 직접 렌더(48×16 col-major 384B) → LZ77 압축 → 원본 슬롯 in-place(전 19개 fit, repoint 불요).
- **결과**: 캐서린/도미노/맥스/호이프/빌리/키쿠치요/아스카/이글/모프/헬보우즈/콩/캣/스네이크/호크/하치/이반/한나/야마모토.
  `patch_part2_domino_co_name_obj`(구: Domino만 blank)를 전 19개 렌더로 교체. ROM 디코드+렌더로 한글 검증.
- **stale-BG 확정 입증**: ROM OBJ를 한글로 바꿔도 30f2 savestate 캡처는 가타카나 유지 → savestate VRAM frozen 확정.
  fresh-boot 시 한글 렌더(동일 렌더러가 ROM에서 읽음). 시각 최종확인은 fresh-boot 캡처 필요.
- 잔여: 80c コシゲ 등 대사 화자/소수인물 이름박스는 0x452xxx 테이블·SJIS에 없는 **별도 메커니즘**(A1b, 추적).

## [2026-06-24] A1 인게임 시각 확증 + fresh-render 캡처 엔진
- **fresh-render 엔진**(`tools/capture_freshrender.py` + `data/freshrender_checkpoints.json`): savestate 로드 후
  refresh-nav(스크롤/재진입)로 OBJ/BG를 현재 ROM에서 **재렌더** → savestate frozen-VRAM(stale-BG) 우회.
- **A1 확정**: CO 프로필 savestate 로드 시 이름박스는 ﾄﾞﾐﾉ(가타카나, stale VRAM)였으나, RIGHT 스크롤로
  CO 전환 시 이름 OBJ가 ROM에서 재렌더 → **맥스 / 도미노 한글 표시 확인**.
  증거: `docs/screenshots/SUCCESS_A1_*_2026-06-24.png`(맥스/도미노 한글, stale→korean montage).
- 이로써 codex·agy가 요구한 "fresh-boot 입증"을 충족: A1 CO 이름 OBJ는 인게임에서 한글 렌더됨이 시각 확증됨.
- 이 엔진은 30f2/80c/24 등 다른 stale-BG 의심 scene도 동일 기법(load+refresh-nav)으로 확증 가능(후속 매니페스트 확장).

## [2026-06-24] fresh-render 엔진으로 A3 확증 — stale-BG vs 실잔존 판별
- **fresh-render 엔진이 두 사례를 명확히 구분**:
  - **A1 = stale-BG(수정됨)**: CO 프로필 스크롤 재렌더 시 이름박스 한글(맥스/도미노) → savestate만 stale.
  - **A3 = 실제 잔존(미수정)**: 맵선택·CO선택 거친 fresh 렌더(state_020→B,B,B,A,A,START,A)에서도 룰 요약
    라벨 収入/日数/能力/アニメ/天気 일본어 유지 → **stale-BG 아님, 미번역 그래픽**. (codex 지적이 옳았고 내 stale-BG 추정 철회.)
- 증거: `docs/screenshots/A3_rule_labels_REAL_residual_freshrender_2026-06-24.png`(fog 도움말만 한글, 룰 라벨 일본어),
  `SUCCESS_A1_domino_korean_freshrender2_*.png`(동일 nav에서 A1 한글 재확인).
- **방법론적 성과**: savestate 캡처의 stale-BG 한계를 fresh-render(load+refresh-nav)로 우회해, 실잔존을 과대(A3)도
  과소(A1)도 아닌 정확히 판별. `data/freshrender_checkpoints.json`에 co_profile/rule_summary 등록.
- A3-fix(룰 요약 라벨 한글화)는 별도 과제로 todo 등록.

## [2026-06-24] 외부 USA판 한글패치 전체 번역 디코드 (갭 타깃 확보)
- **사용자 통찰 실현**: 다운로드한 외부 AW1/AW2 개별 한글패치를 분석해 우리 미번역 UI 갭의 타깃 번역을 확보.
- **방법**(`tools/decode_reference_patch.py`): full-delta(.bin) 복원 → 커스텀 한글 인코딩 디코드.
  폰트 0x810000(AW2)/8x16 4bpp, **code→glyph idx = (low byte) + (-0x90 + (lead-0xc0)*122)**(c0:-0x90,c1:-0x16,c2:+0x64),
  Galmuri11-Condensed로 glyph-match(픽셀 일치)해 code→음절 표 자동 구축(2350 참조). AW2 **2940 문자열 디코드, 미해독 0%**.
- **갭 분석**: 그들 UI 라벨 378개 중 우리에 없는 103개 → USA 전용(CO명 앤디/맥스/이글, 맵명 누에콩섬, 진영 오렌지스타령, 테마) 필터 후
  **보편 UI/룰/시스템 갭** 도출. A3 룰 라벨 타깃 확보: 거점수입/제한일수/지휘관파워/날씨설정/안개설정/전투와점령표시.
  검증: 제한일수·지휘관파워·안개설정·전투와점령표시는 우리 미번역 확정.
- 산출물: `data/reference/aw2_korean_strings.json`(벤치마크), `aw2_gap_candidates.json`, `gap_targets.json`.
- 한계: 우리 대사는 쪼롱이님 완료, 잔존은 대부분 그래픽(룰라벨/sprite UI). 외부 텍스트는 **타깃 한글 출처**로 활용(A3-fix 등).
  맵명은 외부=의미번역(누에콩섬), 우리=음역(소라마메섬)으로 다르나 쪼롱이 영역이라 불변.

## [2026-06-24] A3-fix 완료 — campaign-map 룰 요약 라벨 7개 한글 (VRAM trace)
- **소스 발견(VRAM trace)**: 룰 요약 라벨이 dict 텍스트도 아니고 OBJ인데 위치 불명 → 하네스 `dumpvram`+OAM 덤프로
  실렌더 타일 역추적. 룰 라벨 = OAM sprite 16/18/20/22/24/29 → VRAM 타일 0x372~0x39A → **ROM 0x45D334~0x45D934
  (7개 32×16 OBJ, raw, 0x100 간격 깔끔한 테이블)**.
- **fix(A1식)**: `patch_part2_campaign_rule_summary_labels` — render_galmuri_8x16(ink=15)로 32×16 OBJ에 한글 렌더.
  サクテキ(索敵)→정찰, テンキ(天気)→날씨, 収入→수입, 日数→일수, ユウセイ(優勢)→우세, 能力→능력, アニメ→애니.
  타깃은 외부 AW2 디코드(gap_targets.json)와 일관.
- **인게임 확증**: fresh-render(state_020→B,B,B,A,A,START,A)로 7개 라벨 전부 한글 표시 확인.
  증거 `docs/screenshots/SUCCESS_A3_rule_labels_korean_freshrender_2026-06-24.png`.
- 잔여(minor): 값 라벨(アリ/ナシ/ハレ/ユキ/ランダム/タイプ)은 32×16에 16×8 값 4개 패킹 구조 — 후속.
- 전 QA PASS, scene critical 0, dist PASS. ROM SHA cdeccf3a.

## [2026-06-24] A3 값 라벨 완료 — 8px 값을 Galmuri7로 한글 (A3 완전 완료)
- **8px 벽 돌파**: 이전 "8px라 한글 불가"는 galmuri11(11px) 기준 오판. **Galmuri7(7px)**은 8px에 legible하게 들어감
  (빌드의 status header 종류/체력/연료/탄약이 이미 그 방식). 값 8개 음절 전부 Galmuri7 렌더 가독 확인.
- **값 풀 매핑(VRAM/OAM trace)**: 0x45DA34~0x45DC74. アリ→있음, ランダム→랜덤(4타일), ユキ→눈, ナシ→없음,
  ハレ→맑음, アリ중복→있음, タイプA/B/C→타입A/B/C(각 4타일).
- **fix**: `patch_part2_campaign_rule_value_labels` — Galmuri7로 8px 높이 OBJ(16×8/32×8)에 한글 렌더, ink=15, raw in-place.
- **인게임 확증**: fresh-render로 룰 요약 화면 **라벨(정찰/날씨/수입/일수/우세/능력/애니) + 값(있음/랜덤/없음/타입) 전부 한글**.
  증거 `docs/screenshots/SUCCESS_A3_rule_labels_AND_values_korean_2026-06-24.png`.
- 전 QA PASS, scene critical 0, dist PASS. ROM SHA 6c54adac. → A3(라벨+값) 완전 완료.

## [2026-06-24] A2 맵 선택 섬 이름 '??' 완료 — 4번째 렌더러 공백 ASM hook
- **근본원인(watchaddr trace 확정)**: 맵선택 리스트 렌더러(파서 0x0831Bxxx; glyph는 A3 hook 0xF30280 공유)는
  2바이트씩만 처리하고 **ASCII 공백 0x20을 소비 안 함**. 공백 뒤 1바이트 밀림 → hook이 [0x20,다음high]=0x208B
  같은 out-of-range 코드를 형성 → 원본 fallback '?'(0x8148). 정상 이름(도넛[8140]섬)은 전각공백(SJIS 0x8140,
  2B, 렌더러가 2바이트 코드로 정상 처리) 사용. 영향명은 B팀 권위번역("소라 마메 섬"/"타마 타마 섬"/"마른 잎 섬")이
  12B 슬롯 fit 위해 반각(0x20) 사용 → 슬롯 빠듯해 데이터로 0x8140 치환 불가(overflow).
- **fix(ASM hook, B팀 텍스트 불변)**: `PART2_HOOK_SPACE_A2CC`(RT 0x08F30400, 56B). 루프top 0x0831BCFC(원본
  d620800040440188)에 `_abs_tramp` → hook. [r4]==0x20이면 0x8140(빈칸) 코드를 리터럴로 렌더(r0=&0x8140,
  r4=space-1로 +2후 space+1 정렬) → 0x831BD10 bl 0x831bbdc 복귀; 비공백이면 원본 4명령 재현 후 0x831BD04 복귀.
  파서 디스어셈블+capstone 검증. far-call 회피 위해 렌더는 원본 bl 사이트(0x831BD10)로 복귀시켜 수행.
- **인게임 확증**: fresh-render(state_020→B,B,B,A) 맵선택 = 클래식/소라 마메 섬/도넛 섬/주먹밥 섬/타마 타마 섬/곡옥 섬.
  공백 정상 빈칸, '?' 완전 제거. 증거 docs/screenshots/SUCCESS_A2_map_names_spaces_korean_2026-06-24.png.
- **B팀 보호**: dialogue_overrides.json 미변경 → qa_bteam_drift 0. 텍스트가 아닌 렌더러 메커니즘만 수정.
- 전 QA PASS, 체크섬 OK, scene critical 0, dist PASS. ROM SHA 432d0ec8.

## [2026-06-24] A5 단어붙음 정밀 재진단 + 추가 해소 (codex P4 계기)
- **qa_spacing 도구 대량 오탐 규명**: 도구가 WRITE_LOG(repoint 전 in-place) 디코드 → relocated 라인을 stale
  jammed로 표시. 렌더 기준 정밀분석(Part2 테이블 0xA357B4 relocation + 0x19 + 단일포인터 추적):
  **524 jammed 중 451 relocated + 47 in-place공백보유 = 오탐, 진짜 jammed 26행**(단어붙음 96% 기해소).
- **추가 해소 +7행**: 진짜 26행 중 단일 포인터(0x19 아닌 opcode가 참조, Part2테이블/0x19스캔 미커버) 10행을
  repoint extra_messages에 추가(포인터 검증). 7행 free space 재배치+공백 복원(보급 수송차/하늘의 용사!/백은의
  세계/대공을 제압하라!/지혜의 고리 섬/반달가슴곰 운하·섬). repoint 362→369 lines. drift 0, QA PASS.
- **잔여 ~19**: 0xE0xxxx Part1 대사 순차접근(포인터0)·decompose 실패 3·0xA2C484(폭51>박스50 WONTFIX).
  fail.md가 적시한 이벤트/스크립트 시스템 RE(다세션) 필요. ROM SHA b27ba3d.

---
## [2026-06-25] ★Part1 대사 반각공백(0x20) 렌더 hook 완성 — 단어붙음 근본해결

단어붙음의 진짜 원인(0x20 미렌더)을 **ASM hook 2개로 근본해결**. render-jam 718→11(Part1 707 hook 렌더, 98.5%).
in-game 확증. codex 37분 미해결 + 11시간+ 추적 끝에 완성.

**파서 구조(런타임 트레이스 확정, state=0x03000E00)**:
- 화면 위치 = `[state+0x28](base) + [state+0x32](열)×2 + [state+0x33](행)×64`, 계산함수 **0x08B11B80**.
- caller(0x08B126F0~, 글자당 1회 호출되는 render-one-char): ①0x8b1271e `bl 0x8b11b80`→위치(**파서 전** 계산)
  ②0x8b12728 파서 ③0x8b12758~ render(0x8b12762 `adds r0,r4; adds r1,r5; bl 0x8b12640`) ④0x8b1277A~ 전진
  ⑤0x8b12792 `ldrsb [r6]`([state+0x39]) **return 검사**(루프 아님 — 상위가 글자당 호출).
- **[state+0x34]는 글리프 타일인덱스(저장위치, +2/char=2타일)** — 위치 아님. codex/1차가 이걸 advance해 무효.

**off-by-one 근본**: 위치가 파서 전(0x8b1271e)에 [state+0x32]로 계산 → 0x20 열 advance가 다음 글자 적용.

**hook 2개(build_korean_full.py PART1_DIALOG_SPACE_HOOK / RENDER_HOOK)**:
1. jump table 0x20엔트리(0xB120F4→0xF30500): 다음=한글이면 [state+0x32](열)+1, 0x20 소비, loop top 복귀.
2. render site 0x8b12764(**4정렬 필수** — _abs_tramp는 ldr[pc,#0]라 4정렬 site여야; 0x8b12762=2정렬 회피)→
   0xF30540: render 직전 위치를 [state+0x32]로 **재계산**, 0x8b12640 호출, 0x8b1276A replicate, 0x8b1276C 복귀.
   ★함정: .after 복귀 ldr offset 오류(`[pc,#8]`→render주소 재로드=무한루프 262853회)→`[pc,#12]`(복귀주소)로 수정.

**검증**: 함수호출 19회(작동본 동일, 무한루프0), 위치 0x20에서 +4(char+2+공백+2), in-game
"여기까지 온 너라면 그 정도는"(SUCCESS_renderjam_hook_yeogikkaji). **회귀0**: fullwidth "캐서린이 없는 레드스타 군"
(SUCCESS_..._fullwidth_noregression), Part2 맵라벨 정상. drift0/qa_repoint/integrity/dist 전부 PASS.

**재현**: `python3 tools/build_korean_full.py` → hook 자동 적용. `python3 tools/qa_render_jam.py`(Part1 hook 707 렌더).
잔여 11=Part2(0xA0-0xA3 별도 파서 0x313/0xB11/0xA3 — follow-up).

### codex 적대 리뷰 반영(2026-06-25)
codex 지적 3건 반영: ①**hook 조건 협소**(0x88-0xE2 한글만 → 0x20 앞 전각기호 0x81-0x87 미처리) → hook을
**0x81-0xE2(SJIS content lead)로 확장**(content path>0x77라 render hook 적용, 안전). ②**QA 과면제**(Part1 전체
면제) → next 바이트 종류로 정밀화: Part1 next=SJIS만 hook 렌더, **Part1 next=ASCII(jump table 경로)는 잔여**.
③**stale tile** → 여기까지=페이지전환(하지만 다음) 공백 깨끗으로 확증.
정밀 게이트 결과: **Part1 SJIS hook 1565메시지(2485 공백) 렌더**, Part2 면제(313/B11 자체 공백hook, 기존 완료),
**진짜 잔여 186메시지(188 공백)=Part1 next-ASCII**(숫자/기호 앞 0x20, jump table 렌더라 content render hook 미적용
— "이동력 3인데 2칸뿐" 등). 잔여 해소엔 jump table 렌더 hook 또는 해당 슬롯 데이터 fullwidth화 필요(follow-up).

### Part1 next-ASCII(숫자/기호 앞 공백) 데이터 변환 — 끝까지 완료(2026-06-25)
render hook 사각(jump table 경로의 0x20-before-ASCII)을 **데이터 변환**으로 해소. `_fw_before_ascii`
(build_korean_full.py): enc 내 standalone 0x20의 다음이 ASCII(0x21-0x7E)면 **전각공백 0x8140**(content path
글리프=정상 렌더)으로 변환, slot slack 한도 greedy. 0x20-before-한글은 hook 처리라 보존(바이트 절약).
적용 경로: encode_fit / patch_script_row / fixed_zero_text_patch(authoritative writer=script:* 가 import-csv 덮어씀).
**region 가드**(0xA0-0xE1 대사밴드)로 비대사(UI) 보호.

**다중에이전트 적대검증(워크플로 wf_222b09cd, 5에이전트)**:
- decode-safety **PASS**: 변환공백 682엔트리 음절경계 침범 0, "이동력 3이지만"·"체력 10"·"수송차는 6이나" 정상
  디코드. ??40 코드 오인 구조적 불가(high 0x81+low 0x40 = 0x8140 단 하나).
- regression **PASS**: 4게이트 통과, 변환 180건 100% 대사밴드 내.
- scan: content 0x20-before-ASCII 8건은 전부 **재배치 orphan 소스/숫자정렬 템플릿**(포인터 미지정=렌더 안 됨),
  재배치 목적지·렌더 텍스트는 잼 0. 진짜 단어붙음(0x20→한글) 10,552건 정상 공백.
- 게이트 qa_render_jam을 **content(enc_len) 범위·마지막 writer**로 수정(슬롯 끝 FILL이 다음 구조 ▼와 잼 오인하던
  156 false positive 제거) → **render-jam 잔여 0**.
- FAIL 0. 잔여 우려는 비치명(부호소실 정책, greedy 부분변환 경고, 재배치 stray 0xEF — 공백변환과 무관 별도 follow-up).

### 재배치/인코딩 stray-code 잔여 전수 정리(2026-06-25)
decode-safety 워크플로가 발견한 stray 0xEF를 단서로 **렌더되는 전체 content를 valid-codes(예약+한자테이블+
전각) 전수 검증** → 모든 garbage 코드 근절:
- **repoint stray-code 게이트**(dialogue_repoint.py): new_msg의 모든 2바이트 코드가 렌더 가능한지 검증, 다른
  writer의 slot 경계가 코드 분할로 만든 orphan(8DEF '수'→0xEF) 등 invalid 있으면 재배치 skip→in-place 유지.
  valid_codes는 build가 syl_to_code+한자테이블(rom)+0x8140로 구성해 전달. skip 2건(number-template line-split).
- **encode_text 렌더가능 검증**(build_korean_full.py): fallback이 ─(박스드로잉)·宀(비음절한자)·Υ/Χ(그리스)·
  Б(키릴) 등을 렌더불가 SJIS로 emit하던 것을 **안전코드(ASCII/전각 0x81-0x82)만 emit, 노이즈 drop**. FALLBACK에
  대시류(─―━→'-') 추가 → "젠장────!!!"이 "젠장----!!!"로 정상 렌더.
- 검증: 렌더 content(in-place 마지막writer + 재배치목적지, content-bound) **한글+invalid 동시 0건**. drift0/
  qa_repoint(2852)/integrity/render-jam0/dist 전부 PASS.
- 비-residual: 0xD6/0xD7 추출노이즈(원본도 garbage tile data "宀＋「）ー？楡6␣5␣4...", 대사 미렌더)는 대상 외.

### merged-skip 가드 정밀화 — 미션목표 nosp-jam 추가 해소(2026-06-25)
잔여 nosp 단어붙음 baseline 검증 중, merged-skip 가드(라인 텍스트가 다른 라인의 부분문자열이면 재배치 skip)가
**미션목표 패턴**("산을 넘어, 캣의 연구 기지를 공격하라!" + 짧은 목표 "공격하라!")을 과잉 차단함을 발견. 짧은 라인
(L2)이 **별도 포인터 0개**(메시지 단위로만 표시)임을 확인 → 메시지 재배치 시 L1+L2 구조 그대로 보존되어
중복노출 위험 없음. 가드를 **부분문자열 라인이 sorted_t(테이블/0x19 별도참조)일 때만 skip**으로 정밀화.
결과: 재배치 2852→**2881**(+29), nosp 단어붙음 **15→8**, 전 게이트 PASS(drift0/qa_repoint 2881 0문제/
integrity/render-jam0), 재배치 목적지 invalid 코드 0. 남은 8 = false positive 5(relocated/script-row 공백 렌더,
qa가 in-place orphan 라인 카운트) + 무포인터 하드한계 3(0xE0/0xEC 룰텍스트, 재배치할 포인터 없음).

---
## [2026-06-26] VS설정 도움말 4건 단축 → 재배치 → in-game 공백렌더 확증

박스폭 초과로 단어붙음(nosp) 남던 B팀 도움말/대사 4건을, **사용자 승인 + codex/agy 합의**로 자연스럽게 단축:
- 0xEC312E/0xA2C378 "종료되었을 때"→"종료되면", 0xA2C484 "고르는 것으로"→"선택하면",
  0xDFD082 "여기서만 하는 얘긴데"→"이건 비밀인데" (각 visual_cells 46, 박스 ~30자).

포인터 발견(0xEC312C→테이블0xEC2708@0xEC2714, 0xEC3244→코드 LDR0xB71218)으로 재배치 + fullwidth 공백 렌더.
B팀 baseline `AW_BTEAM_ACCEPT=1 qa_bteam_drift --accept`로 단축본 확정 갱신.

**★fresh-render 확증**(scene_87→A×3 룰진입→우측이동, 타자기 완료 대기): 룰설정 도움말 바에
**"지정일이 종료되면 소유 거점 수로 결판을 냅니다"** 공백 정상 + 한 줄 완전 표시(잘림0).
증거: docs/screenshots/SUCCESS_rule_help_shortened_2026-06-26.png. drift0/qa_repoint2890/render-jam0/dist PASS. 커밋 86cac17.

---
## [2026-06-26] container residual 감사 하드닝 + :8782 저장 UX 검증

codex/agy/claude 엄격 리뷰가 지적한 "green check가 자기확인" 문제를 반영해 B3/C5를 정리.

- **B3 재검증 방식 교체**: `tools/reverify_scene_residual_scans.py` 추가. 기존 raw Shift-JIS 가타카나 스캔의
  blanket allow를 폐기하고, `game_wars_found_texts.csv` 추출 행 + `qa_japanese_residuals.py`의 covered/same-original
  판정을 재사용. 한글 예약코드를 Shift-JIS CJK로 오인하는 문제를 피하기 위해 임의 CJK raw scan은 residual 권위로
  쓰지 않는다. 이 게이트가 증명하는 범위는 CSV 추출행 + raw kana observation이며, 전체 화면 비노출성은 scene capture/
  browser 검증 및 E8 후속 확인과 함께 해석한다.
- **감사 하드닝**: `tools/audit_scene_residual_scans.py`가 `hit`뿐 아니라 `translation_residual`,
  `raw_kana_unexplained_count`도 strict critical로 본다. `verify_dist_integrity.py` 배포 게이트에 연결했다.
  당시 SHA `6cb201dc…` 기준 13 container/2884 dialogue, extracted case 13, hit 0, critical 0.
- **raw kana observation 투명화**: 이름 그리드 charset continuation(0xDA4342)과 공통 통신 numeric/control table의
  단일 `ソ`(0xEE22AC)는 좁은 allowlist와 reason으로만 허용. `0xEE22AC`는 잔류 문장 후보는 아니나, UI 노출 여부
  보강 확인은 todo E8에 남김.
- **C5 저장 UX 수정**: :8782 `app.js`가 모든 조각을 서버 `dry_run`으로 먼저 검증한다. 슬롯 초과는 서버
  `encode_fit` 권위로 차단해 raw 길이 과차단을 피하고, B팀 변경은 dry-run 단계에서 confirm을 먼저 받는다.
  승인 시 `confirm_bteam:true`, 취소/초과/미수록은 실제 저장 시작 전 반환.
- **브라우저 검증**: Chrome CDP로 63 scene/107 sprite 열람 failure 0. B팀 대표 대사 `0x00DFA616`
  취소(false, ko 불변)→승인 저장(true)→원복(true), 초과 입력 `2000/6B` dry-run 차단(false),
  서버 초과 하드게이트 `2000B>6B` 확인. 테스트 후 `dialogue_overrides.json`/`dialogue_map.json` diff 0.
- **D1 부분 진전**: `scene_editor/server.py`가 `text_metrics.encoded_len`을 참조. `test_text_metrics.py`는
  py↔js 25,319 코퍼스 PASS. 단, `qa_text_fit.py` 등 중복 예산 함수가 남아 완전 SSOT는 아님.
- **동시 QA**: `qa_integrity_map.py` 바이트 불일치 0(부호소실 1731행은 기존 정책 리스크), `qa_text_fit.py`
  overflow 0/no_ko 0, `qa_japanese_residuals.py --min-score 13` 후보 1(0x80089B 테이블형 기존 부채),
  placeholder 0, ASCII curated 0, B팀 drift 0, repoint 문제 0, visual regions 23 checks, dist PASS,
  phase6 basic 3종 PASS.

---
## [2026-06-26] :8782 전 대사 저장 게이트 + 88 공통 통신 라벨 시각 재확인

C6/E8의 미완 증거를 닫았다. 단, 이 증거는 "에디터 저장 게이트와 관련 메뉴 캡처" 범위이며,
하드웨어 실기 검증(F1)과 전체 fresh-boot 매트릭스 확대(E2)를 대체하지 않는다.

- **C6 라운드트립 검증 도구화**: `tools/verify_scene_editor_roundtrip.py` 추가. 라이브 :8782 API에서 모든 scene의
  editable 대사 member에 대해 실제 저장 API와 같은 `/api/dialogue/line dry_run`을 호출한다. 전체 쓰기는 churn을 만들기
  때문에 dry-run을 기본으로 하고, 대표 2건만 실제 저장 후 원복한다.
- **C6 결과**: 당시 ROM SHA `6cb201dc…` 기준 78 scene, 10,336 dialogue group, 1,990 sprite,
  23,411 editable member dry-run failure 0. B팀 editable 3,260 member는 미승인 dry-run confirm 요구 +
  승인 dry-run 성공 흐름 failure 0/skip 0. 실제 저장/원복 샘플은 일반 `0x00DFA5E6`와 B팀 `0x00DFA616` 2건 모두 성공.
  direct script 확장-span 대표 `0x00D8FD26`는 실제 저장→임시 ROM 빌드→build slot 44 < direct slot 52 조건에서 span 바이트 expected/actual 대조까지 성공.
  테스트 후 편집 관련 파일은 실행 전 해시로 원복.
- **저장 API false-positive 수정**: :8782 `line_budget`이 direct `script:*` patch의 명시 span 대신 found_texts 첫 조각
  길이를 슬롯으로 보던 문제를 수정했다. 빌드는 direct script span 전체에 쓰므로, 기존 방식은 현재 출하 문장 자체를
  over-budget으로 오판했다. 또한 `deny_pair_status`가 `build_korean_full.in_deny()`를 호출하도록 해 name-grid/false-text
  데이터가 editable로 노출되는 문제를 막았다.
- **direct script 빌드 반영 수정**: `build_korean_full.py`의 direct `patch_script_row`가 `dialogue_overrides.json`을
  최종 권위로 보되, 서버와 같은 `encode_fit` 기준으로 span-fit을 판단하게 했다. 이전에는 에디터 저장이 성공해도
  direct script 하드코딩 문장이 빌드 말미에 다시 덮어써 사용자 수정이 ROM에 반영되지 않을 수 있었다. 이 전환 과정에서
  이미 묵살 중이던 B팀 direct override 2건(`0x00A039E4`, `0x00DF6A7A`)과 일반 direct override 1건(`0x00A03A46`)을
  출하 가능 문장으로 정리하고 B팀 baseline을 갱신했다.
- **E8 현재 SHA 시각 재확인**: `data/comm_label_visual_reverify.json` 추가. `88_common_comm_labels`의 raw 단일 `ソ`
  (`0x00EE22AC`)는 잔류 문장이 아니라 원본과 동일한 통신 숫자/control table observation으로 유지한다. 현재 SHA
  통신/공통 메뉴 캡처 7장을 수동 확인해 visible `ソ` 0. 이 중 primary current-sha 증거는 fresh/ground-truth
  4장(`23b_part2_comm_multiplayer`, `86_common_compact_menu_tables`, Part2 main/shop)이며, Part1 link/name/single
  3장은 stale_state라 보조 증거로만 분류했다. 오래된 `scene_88_common_comm_labels_patched` 캡처는 ROM SHA
  `a27f083…`라 현 증거에서 제외했다.
- **E8 감사 연결**: 과거 동적 scan 원본은
  `data/scene_residual_reverify/88_common_comm_labels_dynamic_scan_results.json`으로 고정해
  1967 case/281 state/hit 0/break_size nonzero 0를 재검증 가능하게 보존했다. 새 시각 리포트를
  `data/scene_residual_scans.json` evidence에 연결했고, audit가 리포트 SHA뿐 아니라 7개 PNG SHA,
  캡처 provenance ROM SHA, primary/stale 증거 역할, 보조 scan SHA까지 확인한다.
  `tools/audit_scene_residual_scans.py --strict` 결과 container 13, case 14, hit 0, critical 0.

---
## [2026-06-26] :8782 적용 상태 D3 하드닝

- **output SHA 자동검증**: `tools/scene_editor/server.py`가 `output/game_wars_korean_full.gba`,
  `output/game_wars_korean_final.gba`, `output/game_wars_korean_title_test.gba` 3종 SHA를 `/api/state.output_sync`로
  노출한다. `/api/build` 완료 직후에도 같은 검증을 수행하며, 세 산출물 중 하나라도 없거나 full SHA와 다르면
  build status를 `fail`로 내리고 다운로드를 409로 차단한다. 빌드 직후 검증은 1초 안전 마진을 둔 freshness threshold로
  각 산출물 mtime을 확인해 오래된 sync 파일을 성공으로 오판하지 않는다.
- **dirty → 적용 필요 UX**: override mtime이 output ROM보다 최신이면 `/api/state.apply_needed=true`가 내려가고,
  프런트 상단은 `적용 필요(override N건)`으로 표시한다. 판정은 ns mtime 기준이다. 깨끗한 상태는
  `적용됨 · output SHA 검증`으로 표시하며, 적용 버튼에는 warning outline을 붙인다.
- **다운로드 variant 정합성**: `/api/download/gba?variant=full|final|title_test`는 요청 variant의 실제 파일을 내려주고,
  알 수 없는 variant는 400으로 거부한다.
- **비파괴 verifier**: `tools/verify_scene_editor_apply_state.py` 추가. 라이브 :8782에서 clean 상태와 output SHA sync를
  확인한 뒤 `dialogue_overrides.json` mtime만 임시로 미래로 옮겨 `apply_needed=true`를 검증하고 원래 mtime으로 복구한다.
  검증 중 파일 mtime이 다른 값으로 바뀌면 동시 편집으로 보고 강제 복구하지 않고 실패한다.
- **CDP 리포트 내구성**: `tools/verify_scene_editor_cdp.py`는 상단 상태 DOM(`적용됨`, `output SHA 검증`,
  다운로드 활성)을 직접 단언하고, `temp/browser_verify/all_scene_editor_verify.json`을 검증 시작/scene별 진행/완료
  시점에 갱신해 중간 실패 때도 진행 증거를 남긴다.
- **검증 결과**: 당시 ROM SHA `6cb201dc…` 기준
  `python3 tools/verify_scene_editor_apply_state.py` PASS
  (`rom_sha256 == output_sha256 == 6cb201dc81d0d23417980d738dc6b588c6d90c728ec02be22f97e4a75576bca8`).
  실제 Chrome CDP에서 상단 상태 DOM은 `ROM 6cb201dc81d0d234 · 16MB · 적용됨· output SHA 검증`,
  `apply.need=false`, `download.disabled=false`. `python3 tools/verify_scene_editor_cdp.py`도
  scene 63/sprite 107/failure 0.

---
## [2026-06-26] D4 frame-sweep preview canvas 부분 완료

- **frame-sweep 엔진**: `tools/preview_capture.py`에 `sweep.frames`/`score_box` 기반 프레임 선택을 추가했다.
  고정 프레임 1장 캡처 대신 nav 후 여러 프레임을 찍고 대사창 ROI ink score가 가장 큰 프레임을 최종 PNG로 사용한다.
- **command-stream span 패치**: NUL 종료 슬롯 외에 `terminator:none` + `pad` 옵션을 지원한다. 1편 welcome은
  원본 슬롯 `0xDF8E16`이 아니라 실제 표시 복사본 37B span을 패치해야 했고, 뒤따르는
  `0x6B/0x0A` 제어코드는 보존해야 대사창이 유지된다. 초기 `0x00A7AB56` 주소는 이후 repoint에서 뒤쪽 안내문으로
  이동했으며, 현재는 `temp/repoint_manifest.json` 기반 동적 slot 계산이 정본이다.
- **part1_welcome 승격**: `data/preview_canvases.json`에 `part1_welcome` 추가. `scene_19a1_part1_tutorial_opening`
  scene이 `canvas=ready`가 됐다. probe 결과 `캡처테스트입니다`가 실제 mGBA 캡처에 반영됨.
- **검증 도구**: `tools/verify_preview_canvases.py` 추가. active canvas 2개(`part1_welcome`, `part2_menu`)에 대해
  서로 다른 payload 2종을 캡처하고, 선택 ROI 픽셀 차이가 발생하는지 검사한다. 결과:
  canvas 2/failure 0, `part1_welcome` diff 314px, `part2_menu` diff 7383px.
- **남은 범위**: battle dialogue canvas는 아직 미승격. 대사창 직전 정밀 savestate 또는 별도 frame-sweep 검증 필요.

---
## [2026-06-26] 89b 전투 패배 메시지 scene 실제 표시 주소 연결 보정

- `89b_common_battle_defeat_comm_messages`의 최신 캡처는 실제 중간 패배 메시지 화면이지만, 런타임 watch log는
  공통 `0xEFD8A4`가 아니라 Part2 복사본 `0xA34D18`을 읽는다.
- `data/scene_catalog_overrides.json`로 `g_00A34D18`~`g_00A34DB0`을 89b에 이동 연결했다. 최종 재생성 후
  `89b` dialogue count는 실제 Part2 패배 메시지 5개이고, 공통/통신오류 복제본은
  `89b_common_battle_defeat_comm_messages_common_copies` container로 분리했다.
- `tools/audit_scene_semantics.py`에 89b watch-log 기반 가드를 추가했다. `defeat_watch.log`의
  `addr=08A34D18` hit를 `g_00A34D18`로 환산해 scene dialogue_ids와 대조하므로, 3P surrender defeat 화면이
  실제 런타임 hit 그룹 없이 green 처리되는 것을 막는다.

---
## [2026-06-26] D5 sprite override LZ77 fit/skip 리포트 게이트 완료

- `build_korean_full.py`의 `apply_sprite_overrides`가 항상 `temp/sprite_override_report.json`을 쓴다.
  리포트에는 `data/sprites_overrides.json` SHA, override count, per-sprite status, synthetic tile 수,
  raw decoded size, LZ77 `compressed_size`/`comp_size`, skipped reason이 들어간다.
- `tools/audit_sprite_override_report.py --strict`를 추가했다. non-empty override에서 report 누락/stale,
  `ok=false`, skipped record, applied LZ77의 cap 초과를 critical로 실패시킨다.
- `verify_dist_integrity.py`에 `sprite override fit` 게이트를 연결했다. 당시 override 0건 기준 report
  `applied=0/skipped=0/ignored=0`, output full/final/title_test SHA는 당시 `6cb201dc…`로 유지.
- temp 검증: 원본 `lz77_000228AC` indices override는 `compressed_size 368 <= comp_size 605`로 applied,
  의도적으로 줄인 grid는 size mismatch skipped로 audit 실패를 확인했다.

---
## [2026-06-26] D1 text metrics SSOT 완료 + 현재 SHA 전수 검증

이번 라운드는 `7e79670c7a99134b91ba1071f839cb800021bcab8e2b643c9c7074fb06001d91` 기준으로 문서/배포/에디터
증거를 다시 맞췄다.

- **text metrics SSOT**: `tools/text_metrics.py`에 2350 음절 집합(`syllable_set`)과
  `unmapped_syllables`/`has_unmapped_syllables`를 추가했다. `qa_text_fit.py`, `lint_translation.py`,
  `scene_editor/server.py`, `verify_scene_editor_roundtrip.py`가 공통 `encoded_len`/2350 미수록 음절 권위를 쓰도록 정리했다.
- **lint 빌드권위 정합화**: `lint_translation.py`는 `build_korean_full.encode_fit`을 byte-budget 권위로 쓰고,
  `dialogue_overrides.json` 최종 overlay와 direct script span을 반영한다. B팀 baseline 주소는 byte-budget lint 대상에서
  제외하고 `qa_bteam_drift.py`/repoint 무결성 게이트가 보호한다.
- **리뷰 적발 결함 수정**: codex 리뷰가 B-team override 11건의 CO 파워명이 카타카나로 남아 실제 출력이 blank/drop될 수 있음을 적발했다.
  `메테오 스트라이크` 등 CSV의 한국어 권위문으로 `data/dialogue_overrides.json`/`bteam_baseline.json`을 맞췄고,
  `qa_bteam_drift.py` drift 0과 ROM 역디코드로 확인했다.
- **렌더 불가 문자 차단/노이즈 보존**: `lint_translation.py`와 :8782 저장 게이트가 `encode_text` drop을 실패로 처리하게 했다.
  agy/claude 리뷰 후 `98_extraction_noise_review`의 non-editable 조건은 build renderer가 보존하지 못하는 unsupported/error member로만 좁혔다.
  B팀 실제 문장 `0x00DF3AFA`는 API에서 `editable:true`/B팀 경고 노출을 확인했다. `문자 깨짐`/`[문자 깨짐]`/
  `해독·번역·판독 불가(문자 깨짐)` sentinel은 `PLACEHOLDER_KO` skip으로 원본 보존하며, 고주소 sentinel 8행
  (`0x009411A5..0x009EB69E`, `0x009B2DFA` 포함)은 원본==출력 바이트로 확인했다.
  `verify_scene_editor_roundtrip.py`는 임시 direct-script build 후 `temp/integrity_map.json`을 원복하며,
  roundtrip 전후 map SHA `498ff629…` 동일 + `qa_integrity_map.py` PASS로 확인했다.
- **D4 회귀 보정**: 새 repoint 후 `part1_welcome` runtime span이 `0x00A7AA56..0x00A7AA7A`로 이동했다.
  기존 `0x00A7AB56`은 뒤쪽 안내문 위치라 payload diff 0이었고, `verify_preview_canvases.py`가 이를 잡았다.
  레지스트리는 `temp/repoint_manifest.json`의 `0xDF8E14 -> new_addr`, fixed `0xDF8E16` delta로 slot을 자동 계산하고,
  `0x00A7AA56`을 fallback으로 둔다. 갱신 후 active canvas 2개 failure 0(`part1_welcome` diff 314px,
  `part2_menu` diff 7383px).
- **scene screenshot 현재화**: `tools/capture_scene_screenshots.py --force`로 카탈로그 참조 screenshot/extra 70개를
  현재 ROM으로 재캡처했다. `tools/audit_scene_entrypoints.py --strict` 결과 game scene 63, audited capture 76,
  missing/stale 0, critical 0.
- **:8782 전수 검증**: 라이브 서버에서 `tools/verify_scene_editor_roundtrip.py` 결과 78 scene, 10,336 dialogue group,
  1,990 sprite, 23,374 editable member dry-run failure 0. B팀 3,260 member confirm failure 0/skip 0. 실제 저장/원복
  2건과 direct-script 임시 ROM build byte 대조 성공. Chrome CDP `tools/verify_scene_editor_cdp.py`는 63 scene/107 sprite
  failure 0.
- **배포/QA 결과**: output 3종 full/final/title_test SHA 동일 `7e79670c…`, BPS/IPS round-trip OK,
  `verify_dist_integrity.py` PASS. `test_text_metrics.py` py↔js 25,296 코퍼스 PASS, `lint_translation.py --severity error`
  0건, `qa_text_fit.py` overflow 0/no_ko 0, `audit_scene_residual_scans.py --strict` case 14/hit 0/critical 0,
  `audit_scene_entrypoints.py --strict` missing/stale 0/critical 0, `qa_integrity_map.py` byte mismatch 0,
  `qa_visual_regions.py` 23 checks, placeholder 0, B팀 drift 0, `qa_terms_from_rom.py` hard 0, phase6 basic PASS.

---
## [2026-06-26] D4 battle_surrender_confirm canvas 승격

- **실제 런타임 소스 특정**: 3P free-battle 항복 확인 화면은 공통 `0xEFDAA0/0xEFDAC1`이 아니라
  Part2 복제본 `0xA34CB0/0xA34CD1`을 읽는다. 전체 후보 동시 패치 diff 614px, pair scan에서는
  `0xA34CB0/0xA34CD1`만 diff 614px이고 `0xEFDAA0/0xEFDAC1` 등 다른 후보는 diff 0이었다.
- **canvas 승격**: `data/preview_canvases.json`에 `battle_surrender_confirm` 추가.
  `0xA34CB0` 32B 첫 줄 span만 `terminator:none` + `pad=0x20`으로 hijack하고,
  `state_008_sub_down_to_surrender.ss0`에서 A 입력 후 frame-sweep으로 항복 확인 대사창을 선택한다.
- **UI 에디터 매핑 보정**: `89a_common_battle_surrender_confirm`은 실제 검증 그룹 `g_00A34CB0`만
  `canvas=ready`로 노출한다. `g_00EFDAA0/g_00EFDAC1` 공통 복제본은
  `89a_common_battle_surrender_confirm_common_copies` container로 분리해, preview가 반응하지 않는 주소를
  실제 화면 preview처럼 보이게 하는 false feedback을 막았다.
- **검증**: `python3 tools/verify_preview_canvases.py` active canvas 3/failure 0
  (`battle_surrender_confirm` diff 302px, `part1_welcome` diff 314px, `part2_menu` diff 7383px).
  `python3 tools/audit_scene_catalog.py --strict`, `audit_scene_entrypoints.py --strict`,
  `audit_scene_semantics.py --strict` 모두 critical 0. 라이브 :8782 API preview는 대사창 영역 diff 518px,
  `tools/verify_scene_editor_roundtrip.py --no-actual-sample --no-build-sample`는 79 scene/10,336 dialogue group/
  23,374 editable member dry-run failure 0. Chrome CDP `tools/verify_scene_editor_cdp.py`는
  63 scene/107 sprite/failure 0.
- **리뷰 반영**: agy가 지적한 “공통 복제본을 preview-ready scene에 섞으면 잘못된 주소 편집이 정상 preview처럼
  보일 수 있다”는 blocker를 container 분리로 해소했다. claude는 최종 변경의 런타임 소스 식별과
  32B command-stream 경계(`0xA34CD0` 제어코드 보존)를 타당하다고 평가했다.

---
## [2026-06-26] D4 battle_defeat_message canvas 승격

- **실제 런타임 소스 특정**: 3P free-battle 항복 후 패배 메시지는 공통 `0xEFD8A4` 계열이 아니라
  Part2 복제본 `0xA34D18`을 읽는다. watch log의 `08A34D18` hit와 payload scan으로 확인했다.
- **state/nav 보정**: 최종 표시 뒤 상태인 `state_011_confirm_yes.ss0`은 이미 렌더된 VRAM이라 payload diff 0이다.
  `part2_3p_surrender_defeat_probe_v4/state_010_confirm_left_yes.ss0`에서 A 입력으로 대사창을 다시 생성해야
  diff가 발생한다. ad-hoc scan에서 해당 경로는 frame 80 기준 diff 288px였고,
  `part2_3p_surrender_confirm_fine/state_000_before_a.ss0` + A도 같은 조건으로 동작했다. scene entrypoint의
  최종 화면 스크린샷 state와 preview canvas의 재생성 직전 state는 목적이 다르므로 분리 유지한다.
- **canvas 승격**: `data/preview_canvases.json`에 `battle_defeat_message` 추가.
  `0xA34D18` 32B span을 `terminator:none` + `pad=0x20`으로 hijack하고, frame-sweep `32/48/64/80/96` 중
  대사창 ROI ink score가 큰 프레임을 선택한다.
- **UI 에디터 매핑 보정**: `89b_common_battle_defeat_comm_messages`는 실제 검증 그룹
  `g_00A34D18/g_00A34D3C/g_00A34D60/g_00A34D88/g_00A34DB0` 5개만 `canvas=ready`로 노출한다.
  공통/통신오류 복제본 `g_00EFD8A4` 계열과 `g_00EFDDBD` 계열은
  `89b_common_battle_defeat_comm_messages_common_copies` container로 분리했다.
- **검증**: `python3 tools/verify_preview_canvases.py` active canvas 4/failure 0
  (`battle_defeat_message` diff 302px, selected frame 48). `audit_scene_catalog.py --strict`,
  `audit_scene_entrypoints.py --strict`, `audit_scene_semantics.py --strict` 모두 critical 0. 라이브 :8782 API preview는
  대사창 영역 diff 229px. Chrome CDP `tools/verify_scene_editor_cdp.py`는 63 scene/107 sprite/failure 0.
  전체 roundtrip은 80 scene/10,336 dialogue group/1,990 sprite/23,374 editable member dry-run failure 0,
  B팀 confirm failure 0, actual save/restore 2건과 direct-script 임시 ROM build byte 대조 성공.
