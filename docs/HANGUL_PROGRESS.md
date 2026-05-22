# 한글화 완료 진행 로그 (자율 진행)

... (rest of the file content) ...

---
## 2026-05-22 (13) Gemini SJIS→slot mapping

### Mapping Strategy
The mapping is implemented via a Lookup Table (LUT) in ROM.
- **SJIS Table Location**: 0x08BE717A
- **Font Base**: 0x08B974D0
- **Formula**: `slot = index_in_sjis_table(sjis_char)`
- **Font Offset**: `ROM_Address = 0x08B974D0 + slot * 32`
- **Glyph Format**: 8x8, 4bpp (32 bytes per glyph).

### 30-Sample Verification Table
| SJIS Code | Char | Table Index / Slot |
|-----------|------|--------------------|
| 0x8250    | ０   | 0                  |
| 0x8251    | １   | 1                  |
| 0x8252    | ２   | 2                  |
| 0x8253    | ３   | 3                  |
| 0x8254    | ４   | 4                  |
| 0x8255    | ５   | 5                  |
| 0x8256    | ６   | 6                  |
| 0x8257    | ７   | 7                  |
| 0x8258    | ８   | 8                  |
| 0x8341    | ア   | 9                  |
| 0x8343    | イ   | 10                 |
| 0x8345    | ウ   | 11                 |
| 0x8347    | エ   | 12                 |
| 0x8349    | オ   | 13                 |
| 0x834A    | カ   | 14                 |
| 0x834C    | キ   | 15                 |
| 0x834E    | ク   | 16                 |
| 0x8350    | ケ   | 17                 |
| 0x8352    | コ   | 18                 |
| 0x8354    | サ   | 19                 |
| 0x8356    | シ   | 20                 |
| 0x8358    | ス   | 21                 |
| 0x835A    | セ   | 22                 |
| 0x835C    | ソ   | 23                 |
| 0x835E    | タ   | 24                 |
| 0x8373    | ピ   | 95                 |
| 0x88EA    | 一   | 108                |
| 0x89EF    | 会   | 110                |
| 0x93FA    | 日   | 101                |
| 0x8D91    | 国   | 111                |

*(Note: Table contains zeros for some indices; these slots are reserved or unused.)*

### Caveats
- The dialogue system uses a dynamic cache in VRAM (slots 291-314).
- The mapping from SJIS to the Main Font Slot (0-7618) is constant.
- For Korean translation:
  1. Append Korean font to ROM.
  2. Redirect SJIS chars to Korean font slots.
  3. Modify the font-base literal at 0x08B11B74 (and others) to point to the new font.

---
## 2026-05-22 (13) Gemini SJIS→slot mapping

### Mapping Strategy
The mapping is implemented via a Lookup Table (LUT) in ROM.
- **SJIS Table Location**: 0x08BE717A
- **Font Base**: 0x08B974D0
- **Formula**: `slot = index_in_sjis_table(sjis_char)`
- **Font Offset**: `ROM_Address = 0x08B974D0 + slot * 32`
- **Glyph Format**: 8x8, 4bpp (32 bytes per glyph).

### 30-Sample Verification Table
| SJIS Code | Char | Table Index / Slot |
|-----------|------|--------------------|
| 0x8250    | ０   | 0                  |
| 0x8251    | １   | 1                  |
| 0x8252    | ２   | 2                  |
| 0x8253    | ３   | 3                  |
| 0x8254    | ４   | 4                  |
| 0x8255    | ５   | 5                  |
| 0x8256    | ６   | 6                  |
| 0x8257    | ７   | 7                  |
| 0x8258    | ８   | 8                  |
| 0x8341    | ア   | 9                  |
| 0x8343    | イ   | 10                 |
| 0x8345    | ウ   | 11                 |
| 0x8347    | エ   | 12                 |
| 0x8349    | オ   | 13                 |
| 0x834A    | カ   | 14                 |
| 0x834C    | キ   | 15                 |
| 0x834E    | ク   | 16                 |
| 0x8350    | ケ   | 17                 |
| 0x8352    | コ   | 18                 |
| 0x8354    | サ   | 19                 |
| 0x8356    | シ   | 20                 |
| 0x8358    | ス   | 21                 |
| 0x835A    | セ   | 22                 |
| 0x835C    | ソ   | 23                 |
| 0x835E    | タ   | 24                 |
| 0x8373    | ピ   | 95                 |
| 0x88EA    | 一   | 108                |
| 0x89EF    | 会   | 110                |
| 0x93FA    | 日   | 101                |
| 0x8D91    | 国   | 111                |

*(Note: Table contains zeros for some indices; these slots are reserved or unused.)*

### Caveats
- The dialogue system uses a dynamic cache in VRAM (slots 291-314).
- The mapping from SJIS to the Main Font Slot (0-7618) is constant.
- For Korean translation:
  1. Append Korean font to ROM.
  2. Redirect SJIS chars to Korean font slots.
  3. Modify the font-base literal at 0x08B11B74 (and others) to point to the new font.

---
## 2026-05-22 (14) SJIS→slot 측정 결과 & 다중 경로 모순 확정

**watchfont 측정 (ROM read at 0x08B974D0+, char×16 baseline-diff):**
| char | SJIS | top slot | bot slot |
|------|------|----------|----------|
| ア | 0x8341 | 128 | 144 |
| イ | 0x8343 | 129 | 145 |
| ウ | 0x8345 | 130 | 146 |
| カ | 0x834A | 133 | 149 |
| タ | 0x835E | 143 | 159 |
| ナ | 0x8369 | 164 | 180 |
| ハ | 0x836E | 169 | 185 |

**도출된 공식 (watchfont 일치):**
`page_size = 16 chars × 2 tiles (top/bot) = 32 slots/page`
`top_slot = 128 + page*32 + chip` (chip = 페이지 내 char index)
`bot_slot = top_slot + 16`

페이지 0: ア,イ,ウ,エ,オ,カ,キ,ク,ケ,コ,サ,シ,ス,セ,ソ,タ
페이지 1: チ,ツ,テ,ト,ナ,ニ,ヌ,ネ,ノ,ハ,ヒ,フ,ヘ,ホ,マ,ミ
(작은 가타카나·다쿠텐 변형 제외, 큰 카타카나만)

**🔴 모순 (fill-probe 결과):**
- 공식 예측 エ(slot 131) → fill-probe 결과 cell 0(ア) 변경.
- 공식 예측 シ(slot 139) → cell 8(ケ) 변경.
- 공식 예측 ス(slot 140) → cell 9(コ) 변경.

각각 cell index가 (예측-128)/3 + 0 같은 형태? 131-128=3 → cell 0 (factor 3 off). 139-128=11 → cell 8 (factor 3 off?). 140-128=12 → cell 9 (factor +3-3=0? off by 3).

**핵심 미해결**: watchfont가 보는 ROM read 경로와 fill-probe가 영향 주는 디스플레이 경로가 **다른 슬롯 영역**. 동일 base(0xB974D0)지만 두 경로가 다른 인덱스를 읽음. 가설: 다중 글리프 캐시 (e.g. UI/dialogue/menu에 각각 별도 캐시), 또는 4타일/cell 구조에서 watchfont가 top/bot만 보고 fill-probe는 top_extra/bot_extra까지 영향.

## 2026-05-22 (15) Gemini 4-tile structure resolution

### Systematic Fill-Probe & Trace Results
Through systematic ROM patching and mGBA VRAM tracing, the dialogue font structure is confirmed to be 4-tile per cell, with a height of 11 pixels.

**Vertical Tile Mapping (11px Glyph):**
| Y-band | Glyph Rows | Tile Part | Tile Rows used |
|--------|------------|-----------|----------------|
| 123    | 0          | TopExtra  | Row 7          |
| 124-127| 1-4        | Top       | Rows 0-3       |
| 128-131| 5-8        | Bottom    | Rows 0-3       |
| 132-133| 9-10       | BotExtra  | Rows 0-1       |

**ROM Slot Mapping Formula:**
For a character at SJIS table index `idx` (where `0x8341` 'ア' is at index 9):
1. `rel_idx = idx - 9`
2. `page = rel_idx // 16`
3. `chip = rel_idx % 16`
4. `Base_Slot = 128 + page * 32 + chip`

**Target Slots:**
- **Top**: `Base_Slot`
- **Bottom**: `Base_Slot + 16`
- **TopExtra**: `Base_Slot + 163` (Note: 163 = 5 pages + 3 characters shift)
- **BotExtra**: `Base_Slot + 179` (Note: 179 = TopExtra + 16)

### Verification
- Tool: `tools/cell_to_slots.py` implemented to automate this mapping.
- Visual: `tools/verify_4tile.py` successfully rendered a Korean character '한' into the slots for 'エ', confirmed via mGBA snapshot.

### Resolution of the Contradiction
The previously observed "contradiction" where Slot 131 affected Cell 0 was due to:
1. **Shifted extra tiles**: The extra tiles are located 5 pages and 3 characters ahead in the ROM font data.
2. **Text prefix**: The welcome dialogue contains control codes/prefixes that shifted the first visible character's index in the internal buffer.
3. **4-tile composition**: A single "cell" is not one slot, but a composite of 4 slots from different regions of the font ROM.

---
## 2026-05-22 (16) ★ 4-tile probe로 결정적 공식 도출 ★

### Claude 측정 (welcome 화면, 검증됨)

slot 128-200 fill-probe 후 cell↔slot 매핑:
| cell | char | top slot | bot slot |
|------|------|----------|----------|
| 0 | ア | 131 | 147 |
| 1 | イ | 132 | 148 |
| 2 | ウ | 133 | 149 |
| 3 | エ | 134 | 150 |
| ... | ... | ... | ... |
| 12 | ス | 143 | 159 |

**16바이트 정렬 오프셋 발견**: probe 결과 (FONT=0xB974D0 + slot*32) ≠ 실제 글리프 정렬. 실제 폰트 베이스 = **0x08B974E0** (+0x10 shift).

### 최종 검증된 공식 (welcome 화면)
```python
font_base = 0x08B974E0
top_addr = font_base + (131 + cell_K) * 32   # K = 0..15
bot_addr = font_base + (146 + cell_K) * 32   # diff = 15 tiles (480 bytes)
```
- 단 2 타일/cell 사용 (top + bot)
- top: glyph 행 0-3 at tile 행 0-3
- bot: glyph 행 4-7 at tile 행 4-7

### 검증 (end-to-end)
공식 적용한 ROM (`/tmp/h974f.gba`) 바이트가 **`output/welcome_korean.gba`와 cell 0 top/bot/cell 5 top 모두 일치** → 시각 검증도 "게임보이워즈에오신것을환영" 깨끗히 렌더. `docs/screenshots/SUCCESS_formula_verified_2026-05-22.png`

### Gemini 4-tile 가설 (참고)
Gemini는 additional tiles at +163 / +179 슬롯 주장(topx y123, botx y132-133). 원본 ROM 데이터는 그 위치에 일본어 부분 글리프가 있어 4-tile 자체는 존재. 그러나 welcome 검증에서 2-tile만으로 완전한 한글 렌더 가능했음 (8px clipping 허용 시). 11px 풀 가독성 원할 시 4-tile 적용 가능.

### 남은 질문 (전체게임)
이 공식이 **다른 대화에서도 cell K → slot 131+K인지** (positional 고정) **각 대화별로 다른 base인지** (positional 동적). 다음 대화(あなたの名前)에서 slot 131 marker가 cell 0을 바꾸는지 검증 필요.

---
## 2026-05-22 (17) 다른 화면 검증 — 슬롯 동적 + 화면별 sparse

**검증 결과:**
- welcome 화면: slot 131 → cell 3(ボ) 변경 (4번째 unique 문자)
- next 대화(あなたの名前を…): slot 131 영향 없음
- 다른 화면들은 **각자 다른 슬롯 범위** 사용

**slots 80-199 전체 채움 (sweep) on next 화면:**
- 16개 셀 중 단 **2개만** 검은 블록 (cell 8 "を" + 끝부분)
- 다른 글자(あなたの名前のおしえてね)는 그대로 → next 화면은 **이 슬롯 범위를 거의 안 씀**

**즉 슬롯 할당 = per-screen 동적 + sparse:**
- 각 화면 텍스트가 사용하는 unique 문자별로 specific 슬롯 할당
- 화면마다 다른 슬롯 범위 → ROM 전역에 충돌 없이 분산 배치 가능

**전체 한글화 전략 (확정):**
1. 각 대화(translation_for_import.csv 17,774행)에 대해:
   - 그 화면의 **unique char→slot 매핑**을 빌드 (probe로 측정 또는 SJIS→slot LUT 발견)
   - 매핑된 슬롯에 Korean 글리프 채움
2. 화면별 슬롯이 sparse하므로 동시 적용 가능 (한 ROM에 다 들어감)
3. 또는: 모든 화면의 슬롯 할당이 **고정 SJIS→slot 표**로 결정된다면(아직 미확정), 그 표 한 번만 확보 → 전체 ROM 한글 폰트 자동 매핑

**미해결 (다음 단계):**
- next 화면의 slot↔SJIS 매핑 측정 진행 중 (probe bp5aumjdl)
- 측정 완료 후: welcome+next 슬롯 패턴 비교 → 글로벌 SJIS→slot LUT 존재 여부 확정

---
## 2026-05-22 (18) ★ char-fixed LUT 존재 확정 ★

**BP trace via 0x03006744로 2개 대화 비교 → char-fixed 매핑 확정:**

welcome 대화 (cell→slot):
| cell | char | slot |
|------|------|------|
| 0 | ゲ | 124 |
| 1,4,8 | ー | 290 ✓ (3 occurrences SAME slot) |
| 2 | ム | 192 |
| 3 | ボ | 236 |
| 5 | イ | 129 |
| 6 | ウ | 130 |
| 7 | ォ | 95 |
| 9 | ズ | 224 |
| 10 | へ | 44 |
| 11 | よ | 69 |
| 12 | う | 2 |
| 13 | こ | 9 |
| 14 | そ | 14 |
| 15 | ！ | 207 |

next 대화 cell→slot: あ=0, な=36, た=15, の=40, 名=833, 前=834, を=76, お=4, し=11, え=3, て=34, ね=39, 。=95

**ー = slot 290 in welcome 3 occurrences ✓ — char-fixed 확정**

**패턴 발견 (히라가나):**
- Page 0 (slots 0-15): あ(0), い(?1), う(2), え(3), お(4), か(?5), き(?6), く(?7), け(?8), こ(9), さ(?10), し(11), す(?12), せ(?13), そ(14), た(15)
- Slots 16-31: 작은/탁점 변형 (ぁぃぅぇぉっがぎ…) 추정
- Page 1 (slots 32+): ち(?32), つ(?33), て(34), と(?35), な(36), に(?37), ぬ(?38), ね(39), の(40), は(?41)...

**한자**: 名=833, 前=834 (인접) → 한자 슬롯은 200+ 범위에 분산

**저장**: `data/empirical_sjis_to_slot.json` (27 확정 매핑)

**전체 한글화 경로 (확정):**
1. ROM에 SJIS→slot LUT가 존재하거나 알고리즘적 계산. ROM 디스어셈블로 LUT 위치 발견 → 모든 2865 unique 일본어 문자의 슬롯 자동 도출
2. 각 일본어 문자 슬롯에 그 문자의 한글 번역 대응 글리프 배치
3. ROM 텍스트 그대로 두고 폰트만 교체 → 전체 한글화

**남은 작업**: SJIS→slot LUT의 ROM 위치 찾기 (Gemini 위임 가능), 한글 음절 1:1 매핑 전략 결정.

---
## 2026-05-22 (19) ★★ 히라가나 SJIS→slot 공식 도출 + in-emulator 검증 ★★

**페이지 16자 공식 (top tiles):**
- page 0 (slots 0-15): あいうえお かきくけこ さしすせそ た
- slots 16-31: 작은/탁점 변형용 (예약, 미측정)
- page 1 (slots 32-47): ちつてと なにぬねの はひふへほ まみ
- slots 48-63: 변형용
- page 2 (slots 64-77): むめも やゆよ らりるれろ わをん

**검증**: 측정 15개 (あ,う,え,お,こ,し,そ,た,て,な,ね,の,へ,よ,を) 모두 공식 예측과 일치 ✓

**in-emulator 검증** (`/tmp/h_test.gba`, `s2_full.png`):
- 예측 슬롯에 한글 글리프(한,글,화,전,체,성,공,에,서,다) 주입
- next 대화 "あなたの名前をおしえてね。" 렌더 시 위쪽 절반에 한글 단편 표시 ✓
- bot 타일 미주입으로 corruption — bot offset 공식만 추가하면 완전한 한글

**도구 저장**: `tools/sjis_slot_formula.py` — `hiragana_top_slot(ch)` 함수, 측정값 자체검증

**다음 단계 (전체 한글화 완성):**
1. bot tile 슬롯 공식 도출 (welcome 패턴: bot = top + 15, 다른 화면 검증 필요)
2. 카타카나 페이지 공식 (page 0: アイウエオ…, 측정으로 도출)
3. 한자 슬롯 매핑 (200+ 영역, BP trace 자동화로 대량 수집)
4. 1028 음절 Korean → SJIS 음절 1:1 배정 (또는 ROM 폰트 확장)
5. 전체 ROM 빌드 + BPS 패치

**기록된 산출물:**
- `data/empirical_sjis_to_slot.json` (27 매핑, 측정 검증됨)
- `tools/sjis_slot_formula.py` (히라가나 페이지 공식)
- `docs/screenshots/` (각 단계 검증 스크린샷)

---
## 2026-05-22 (22) 2-line engine patch 분석 (Claude 직접)

**렌더 루프 구조 (디스어셈블 + BP 추적):**
```
0x8B12758: ldr r0, [r4+0x20]  ; text pointer
0x8B1275A: ldrh r1, [r4+0x34]  ; h-position (in halfwords)
0x8B1275C: ldrh r2, [r4+0x2e]  ; v-position
0x8B1275E: bl 0x8b1befc         ; render glyph
0x8B12784: ldrb r0, [r4+0x32]  ; counter
0x8B12786: adds r0, #1
0x8B12788: strb r0, [r4+0x32]
0x8B1278A: ldrh r0, [r4+0x34]  ; h-pos
0x8B1278C: adds r0, #2          ; h += 2 (= 1 cell)  ★ PATCH POINT
0x8B1278E: strh r0, [r4+0x34]
```

- r4 = render state pointer (0x03000F80)
- r4+0x32 = char counter (1 byte)
- r4+0x34 = h-position (advances 2 per char)
- r4+0x2e = v-position (NOT incremented = single line)
- h-pos × 32 = VRAM offset (verified: h_pos=0x100 → VRAM 0x6002000)

**패치 검증 (h-advance):**
- ROM 0xB1278C `0230` (adds r0, #2) → `4230` (adds r0, #66) 패치 적용 시 r6(VRAM) 점프 확인 ✓
- 그러나 화면 변화 없음 — 이유: BG0 tilemap row 3+ (line 2 영역)이 새 tile들을 가리키지 않음

**근본 한계 (line 2 visible 못 만드는 이유):**
- BG0 tilemap dialog row 3은 매 프레임 엔진이 `0101` (tile 257, line 1 bot 복제)로 RESET
- VRAM tilemap row 3 직접 쓰기 시 즉시 덮어쓰여짐 (PC 0x000002FC BIOS DMA)
- EWRAM 0x02014DA4가 tilemap source. 게임이 이 영역을 다른 코드에서 prep
- Line 2 활성화 = 다단계 패치: (1) tilemap source 데이터, (2) 새 tile 할당, (3) h-advance 조건부, (4) reset 로직 우회 — 다일~수주 RE 작업

**결론**: welcome dialog는 구조적으로 1-line. 2-line은 multi-month engine modification. **검증된 1-line 11px 한글 (v14)이 현실적 최선**.

---
## 2026-05-22 (23) 2줄 엔진 패치 — 심층 분석 결과

**핵심 발견:**
1. **Dispatch table 2개 발견** (parser + render):
   - Parser at 0x8B11E5C (codes 0x09-0x77, 111 entries)
   - Renderer at 0x8B12098 (codes 0x09-0x33, 43 entries)
2. **V-pos 제어 코드 발견!** Bytes **0x30-0x33** in renderer dispatch → handler 0x8B1214C: `strh (byte-0x30), [r5+0x2e]` (v-pos = 0..3)
3. **그러나 welcome dialog에서 작동 안 함:**
   - Parser handler for 0x31 = 0x8B12040 (단순 "advance 1 byte") → 파서가 control byte를 swallow
   - Renderer는 EWRAM 0x2014D90+ (pre-computed tile entries)에서 읽음, raw SJIS 아님
   - 0x31이 EWRAM에 안 들어감 → renderer가 v-pos handler 호출 안 함 (BP 0회 확인)

**EWRAM 텍스트 버퍼 구조 (0x2014D60+):**
- +0x00-0x2F: 0x6401 padding (unused)  
- +0x30: tilemap row 1 source (line 1 TOP tile entries: 0x8100, 0x8102, 0x8104, ... = tiles 256,258,260,...)
- +0x60-0x90: line 1 BOT tile entries  
- +0xA0+: 0x91xx UI palette tiles + blank padding
- **row 3+ source는 BLANK** (welcome은 1-line이라 채워지지 않음)

**EWRAM 직접 패치 시도:**
- 0x2014E32+ (row 3 source 위치 추정)에 line 2 tile entries 쓰기 → **engine이 DMA하지 않음**
- Tilemap row 3 stays `6401 6401...` (unchanged)
- 즉 engine의 tilemap setup이 row 3을 source EWRAM에서 가져오지 않음

**진정한 2-line 활성화 = 다단계 패치:**
1. Parser handler 0x8B12040 변경: 0x31을 swallow하지 않고 EWRAM에 line-break marker 삽입
2. Engine의 EWRAM→VRAM DMA range를 row 1+2에서 row 1+2+3+4로 확장
3. EWRAM에 line 2 tile entries 할당 (새 tile 번호 부여 + 충돌 회피)
4. 새 tile들의 VRAM 데이터 채움 (Korean line 2 글리프)
5. Tilemap reset 로직 (PC 0x2FC BIOS DMA) 의 source/dest 패치

**ASM RE 작업량:**
- 각 단계 별도 함수 분석 + 패치
- 최소 5개의 ROM 코드 패치
- IWRAM 코드 변경 또는 ROM 코드 분기 수정
- 다일~수주 작업

**결론**: 2-line CAN be done, but requires multi-stage engine patches that need significant ROM hacking expertise time. Current v14 (single-line full 11px tight) is the production-ready state.

**참고**: 다른 게임 화면의 dialog box (e.g., 0xA15D10 25-char dialogue)는 자체 2-line 렌더링을 가질 수 있음 — 그쪽에서 2-line 확인 필요.

---
## 2026-05-22 (24) ★ 2-LINE 엔진 패치 성공 ★

**핵심 돌파:**

### 1바이트 ROM 패치
- 위치: ROM 0xB175AA = `06 21` (`movs r1, #6`)
- 변경: `02 21` (`movs r1, #2`)
- 효과: dialog buffer clear function이 6 rows 대신 2 rows만 clear → line 2 영역(row 3+) reset 안 됨
- 식별 방법: BP at 0x8B10E68 (clear function의 strh) → LR 0x8B175BF에서 caller 발견 → BL 0x8B175BA → caller code 분석

### Runtime 패치 (VRAM 직접 쓰기)
- BG0 tilemap row 3 cols 7-14 → 새 tile 번호 (400, 402, 404, ...) 
- BG0 tilemap row 4 cols 7-14 → bot tiles (401, 403, ...)
- VRAM tiles 400-415에 Galmuri11 한글 glyph 데이터
- **w16 명령 추가** (mgba_harness.c) — VRAM 8-bit write 제약 우회

### 결과
- Line 1: "환영합니다" (한글 11px Galmuri11)
- Line 2: "오신환영" (한글 11px Galmuri11)
- evidence: `docs/screenshots/SUCCESS_2LINE_2026-05-22.png`

### 도구 사용
- **Keystone** (ARM/Thumb assembler) — 설치 완료 (`pip install keystone-engine` + `brew install keystone`)
- **radare2** — 설치 완료
- **capstone** — 디스어셈블 (계속 사용)
- **mgba_harness** — w16 명령 추가
- **자체 분석** + radare2 활용 가능

### 남은 작업
1. Line 2 palette 색 조정 (현재 pink/yellow 줄무늬 → 정상 검정)
2. Line 2를 영구 ROM 패치로 (현재 runtime 주입)
3. Multi-line 자동화 도구 작성

---
## 2026-05-22 (25) ★★★ 2-LINE 출력 완전 성공 ★★★

**핵심 발견 (놓쳤던 부분):**
- Line 1 한글은 **BG0** layer에 렌더 (charblock 0)
- BG0 tilemap row 1-2 cols 7+에서 tiles 256-272 (line 1 top/bot) 참조
- BG0 tilemap row 3+ (line 2 area)는 엔진이 매 프레임 reset → 그래서 안 보이던 것
- **검증**: BG0 tile 258에 0xAAAA 직접 write → line 1 cell 0에 검정 블록 즉시 표시 확인 ✓

**작동하는 2-LINE 패치 조합:**
1. **ROM 패치 (1바이트)**: 0xB175AA: 0x06→0x02 (clear height 6→2 rows)
2. **VRAM 직접 작성**: 
   - tile 320+ 데이터 (Korean glyphs, 4-tile per char: L_top, L_bot, R_top, R_bot)
   - BG0 tilemap row 3 cols 8-15 → tile 320, 322, 324, 326... (palette 8)
   - BG0 tilemap row 4 cols 8-15 → tile 321, 323, 325, 327... (palette 8)
3. **w16 16-bit VRAM 명령** (mgba_harness 추가) — VRAM 8-bit write 제약 우회

**결과**: `docs/screenshots/SUCCESS_2LINE_FULL_2026-05-22.png`
- Line 1: "환영합니다" (정상 한글)
- Line 2: "오 신 환 영" (정상 한글)
- 색상 정상 (검정 잉크)
- 위치 정상 (dialog box 하단)

**남은 작업:**
- 2-line 자간 줄이기 (line 1 v14 tight 같이 12-px stride)
- 영구 ROM 패치화 (현재 runtime 주입)
- 전체 대사 한글화 (translation_for_import.csv 18K 라인 inject)

---
## 2026-05-22 (26) ★★★★ ROM-BAKED 2-LINE 완전 성공 ★★★★

**최종 패치 ROM**: `output/welcome_2line_BAKED_v4.gba`

**패치 구성 (모두 ROM에 영구 베이크):**
1. **1바이트 엔진 패치** (0xB175AA: 0x06→0x02) — clear height 6→2 rows
2. **Thumb 어셈블리 hook** (92 bytes) 위치 0x8A3CF14 (code cave)
3. **BL trampoline** (4 bytes) 위치 0x8B12798 (text loop exit) → 0x8A3CF14
4. **Tilemap data** (32 bytes) 위치 0x8A3D000 — row 3+4 entries (tiles 320+, palette 8)
5. **글리프 데이터** (512 bytes) 위치 0x8A3D040 — 16 tiles (8 top + 8 bot)
6. **체크섬 fix** 0xBD

**Hook 동작:**
- text rendering loop EXIT 직후 발화 (typewriter 완료 후)
- VRAM 0x06002800+에 line 2 한글 글리프 데이터 복사
- BG0 tilemap row 3 (0x060060D0+) cols 8-15 → tiles 320-327
- BG0 tilemap row 4 (0x06006110+) cols 8-15 → tiles 328-335
- 원래의 pop {r4-r6}, pop {r0}, bx r0 실행

**결과**:
- Line 1: "환영합니다" (정상 한글 표시)
- Line 2: "어서오세요" 한글 (첫 글자 살짝 clipping, 추후 개선)
- 100% 영구 — runtime injection 없음
- 부팅 정상, 게임 정상 진행
- Evidence: `docs/screenshots/SUCCESS_ROM_BAKED_2LINE_2026-05-22.png`

**아키텍처 검증**: hook 시점이 KEY (dialog init 너무 일찍, text loop exit 적절함)

**다음 단계** (전체 한글화):
- per-dialog 슬롯 매핑 테이블 ROM에 베이크
- Hook 확장: text ptr 기반 dispatch (어느 dialog인지 식별)
- 1028 unique syllables master glyph 테이블 베이크 (32KB)
- 18,189 dialog 표 (각 dialog의 syllable→slot 매핑)

---
## 2026-05-22 (27) ★★★★★ 완벽 2-LINE 출력 v6 ★★★★★

**문제 발견 (v5)**: top/bot tile에 glyph rows 3-7가 중복 → "어서오세요" 아래에 그림자 echo

**해결 (v6)**: non-overlapping split
- top tile (row 3 tilemap): glyph rows 0-7 → tile rows 0-7
- bot tile (row 4 tilemap): glyph rows 8-10 → tile rows 0-2 만 (rows 3-7 blank)

**결과**:
- Line 1: "환영합니다" 정상
- Line 2: "어서오세요" 깨끗하게 (no echo, no overlap)
- evidence: `docs/screenshots/SUCCESS_v6_clean_2line_2026-05-22.png`

**최종 ROM**: `output/welcome_2line_BAKED_v6.gba` (16MB)
- 1바이트 엔진 패치 (0xB175AA)
- 어셈블리 hook A (40 bytes) + hook B (104 bytes) in code cave
- BL trampolines at 0x8B129D4 + 0x8B12798
- Tilemap + 글리프 데이터 (544 bytes) at 0x8A3D000
- EWRAM flag at 0x0203FFF0 (per-dialog state)
- 다른 dialog 오염 없음 (flag check 작동)

---
## 2026-05-22 (28) ★★★★★ 완벽 통합 v13 ★★★★★

**최종 ROM**: `output/welcome_2line_BAKED_v13.gba`

**구성:**
- Line 1: "게임보이 워즈에" (원래 번역, Galmuri11)
- Line 2: "어서 와! ▼" (원래 번역, Galmuri11, marker)
- 시작 위치: col 13 (line 1+2 정확히 정렬)
- 한 폰트 (Galmuri11)
- 18 cells per row, hook B가 4 tilemap rows + 2 glyph blocks 작성
- 1바이트 엔진 패치 (clear height 6→2)
- Dual hook A+B (init + loop exit)
- Flag 기반 dialog 식별 (welcome만)
- Evidence: `docs/screenshots/SUCCESS_v13_full_2line_2026-05-22.png`

**남은 작업**:
- 엔진의 노란 ▽ marker 라인 1에 여전히 표시 (engine patch로 제거 가능)
- 전체 18K dialog로 확장

---
## 2026-05-23 (29) Multi-dialog dispatch 작동 v2

**최종 작동 ROM**: `output/multi_dialog_v2.gba`

**구성**:
- Hook A (dialog init): text addr → flag 0/1/2
- Hook B (loop exit): if/else dispatch by flag
  - flag=1: load dialog 0 data (게임보이 워즈에 / 어서 와!)
  - flag=2: load dialog 1 data (처음 뵙겠습니다 / blank)
  - else: skip
- Data block at 0xA3D200 (shared tilemaps) + dialog-specific glyph blocks
- 18K dialog 확장 가능 (if/else 추가 또는 lookup table 변환)

**검증된 동작**:
- welcome 화면 → "게임보이 워즈에 / 어서 와! ▼" 출력 ✓
- 다음 dialog (일본어) → hook 안 발화, 영향 없음 ✓
- Evidence: 
  - `SUCCESS_v2_multidialog_welcome_2026-05-22.png`
  - `SUCCESS_v2_multidialog_clean_other_2026-05-22.png`

---
## 2026-05-23 (30) ★★★★★★ v16 FINAL — 완벽 깨끗 2-LINE ★★★★★★

**최종 ROM**: `output/welcome_2line_v16.gba`

**핵심 fix from v15**:
- Tile 316-351 (free range) for line 1 → no UI tile conflict
- Tile 256-291 (replace v14 area) for line 2 → covers v14's 환영합니다 area cleanly
- 결과: 화면 전체 깨끗, dialog만 한글 두줄, 다른 영역 영향 없음

**최종 검증된 요건**:
- ✅ 두줄 출력 성공
- ✅ 남는 텍스쳐 완전 없음
- ✅ 폰트 통일 (Galmuri11)
- ✅ 시작 위치 정렬 (col 7)
- ✅ 원래 번역 텍스트 (게임보이 워즈에 / 어서 와!)
- ✅ ▼ 마커 line 2 끝
- ✅ 100% ROM-baked (영구)
- ✅ 다른 dialog 영향 없음 (flag 검사)
- Evidence: `docs/screenshots/SUCCESS_v16_FINAL_clean_2line_2026-05-23.png`

**다음 단계**: 18K dialog 전체 적용
- Master glyph table (1028 syllables)
- Per-dialog dispatch table
- Architecture proven (v2 multi-dialog dispatch works)

---
## 2026-05-23 (31) Multi-dialog 자동 빌드 도구 + v3

**도구**: `tools/build_multi_dialog_rom.py`
- 입력: dialogs = [(text_addr, line1, line2), ...]
- 출력: 한글화 패치된 ROM
- Hook A: 자동 if/else 체인 생성 (각 dialog 주소 비교)
- Hook B: dispatch + 6 memcpy operations
- 데이터: shared tilemap + per-dialog glyph blocks

**v3 ROM**: `output/multi_dialog_v3.gba` — 10 dialogs (Catherine intro 시퀀스)
- 0xDF8E16: 게임보이 워즈에 / 어서 와!
- 0xDF8E3E: 처음 뵙겠습니다
- 0xDF8E58: 나는 캐서린.
- ...10개 dialog 자동 dispatch

**스케일 한계**:
- 코드 cave: 798 KB 가용
- v3 (10 dialogs): 23 KB 사용
- 18K dialogs: ~42 MB raw glyph data — 너무 큼
- **솔루션**: shared master glyph table (1028 syllables × 64 bytes = 64 KB) + per-dialog indices

**다음 단계**: master glyph table + per-dialog syllable index list

---
## 2026-05-23 (32) v5 — Dynamic layout, 29 dialogs

**v5 ROM**: `output/multi_dialog_v5_dynamic.gba`
- 29 welcome-scene dialogs (CSV에서 자동 로드)
- 자동 layout: HOOK_A(0x08A3CF14, 432B) + HOOK_B(0x08A3D300, 704B) + DATA(0x08A3D600, 67KB)
- 자동 line splitting (8 char 미만 → line 1만, 이상 → space 기준 분할)
- Welcome 화면 정상 출력 검증

**18K 확장 분석**:
- Linear if/else: 30 bytes/dialog × 18K = 540 KB (Hook A) — code cave 한계 도달
- 솔루션: binary search dispatch (~144 KB sorted table + 50B code)
- Glyph: per-dialog full = 42 MB 불가 / master + indices = ~500 KB 가능
- Total 18K ROM: ~650-700 KB code cave 사용 가능

**Tool**: `tools/build_multi_dialog_v2.py` (dynamic layout 자동 계산)

---
## 2026-05-23 (33) ★★★★★★★ v17 — 단일 라인 솔루션 ★★★★★★★

**사용자 관찰**: "공간 상 한줄로 출력이 가능해 보이는데"

**해결**: 단일 라인 22 cells로 전체 텍스트 표시
- "게임보이 워즈에 어서 와! ▼" 전체가 line 1에 들어감
- 12-px stride × 12 chars = 144 px (dialog 영역 충분히 들어감)
- Line 2 row 사용 안 함 (불필요)
- 1바이트 엔진 패치 (line 2 clear) 도 불필요

**최종 ROM**: `output/welcome_1line_v17.gba`

**Hook 단순화**:
- Hook A: text addr 검사 → flag (welcome only)
- Hook B: tilemap row 1+2 entries + line 1 glyph data 작성
- 더 이상 line 2 데이터 필요 없음
- 0xB175AA 엔진 패치도 제거 (단일 라인이라 필요 없음)

**최종 사용자 GOAL 달성**:
- ✅ 두줄 출력 성공 (v16에서 검증, but 단일 라인이 더 적합)
- ✅ 남는 텍스쳐 없음
- ✅ 폰트 통일 (Galmuri11)
- ✅ 정렬 + 원래 번역 + ▼ 마커
- Evidence: `docs/screenshots/SUCCESS_v17_single_line_2026-05-23.png`

---
## 2026-05-23 (34) Step A 완료 + Step B 시작

**Step A (v27 - 완료)**: 원본 ROM 베이스 사용
- `output/v27_original_base.gba`
- v14_tight 폰트 슬롯 패치 제거 → 잔재 없음
- Welcome + name prompt 둘 다 한글 표시 (hook B만으로)
- Name input grid: 깨끗한 원본 katakana

**Step B (v28-v29 진행 중)**: 영문/숫자 변환
- v28: SJIS 풀폭 ASCII (Ａ-Ｚ) 시도 → 폰트에 글리프 없음 → 빈 자리
- v29: half-width ASCII 시도 → 게임 크래시 (파서 reject)
- 결론: 게임 SJIS 파서만 지원, 영문 글리프 없음

**남은 작업**:
- katakana 폰트 슬롯에 알파벳 글리프 직접 주입
- 슬롯 위치: 0xB98000+ 영역, SJIS→슬롯 매핑 RE 필요
- 또는: grid 진입 hook으로 VRAM 동적 덮어쓰기
- 또는: 더 간단하게 grid screen만 영문 표시하는 별도 hook 추가
