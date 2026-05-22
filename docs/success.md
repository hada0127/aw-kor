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
