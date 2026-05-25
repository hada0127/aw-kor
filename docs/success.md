# Success Log — 작동 검증된 방법·산출물

> 사용자가 향후 참조하기 위한 **실제로 작동한 방법 모음**. 모순·실패 사유는 [fail.md](fail.md) 참조.

---

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
