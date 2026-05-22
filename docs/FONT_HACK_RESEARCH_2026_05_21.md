# 한글 폰트 ROM 삽입 — 리서치 & 실행 계획

**작성일**: 2026-05-21
**목표**: Game Boy Wars Advance 1+2 (GBA, 일본판) **원본 ROM을 패치**하여 한글 폰트를 넣고, **실기(real GBA hardware) 및 에뮬레이터에서 한글이 정상 출력**되게 한다. 배포는 원본 대비 패치(BPS) 형태.
**검증 전략**: mGBA(사이클 정확)는 실기의 신뢰할 수 있는 프록시. 단, **실기 부팅 요건(아래 §0)을 반드시 충족**해야 함.
**현재 상태**: 번역 텍스트(18,262행)는 준비됨. 하지만 (1) ROM에 한글 폰트가 없고, (2) 텍스트 삽입 도구가 ROM을 손상시켜 부팅이 안 되며, (3) 게임 자동 진행 검증이 막혀 있었음(해결책 확보).

---

## 0. 실기(Real Hardware) 패치 요건 — 최우선 준수

원본 ROM을 패치해 플래시카트/실기에서 돌리려면 GBA BIOS 부팅 검증을 통과해야 한다.

1. **닌텐도 로고 (0x04–0x9F, 156바이트)**: BIOS가 부팅 시 검증. **절대 손상 금지.** (우리 텍스트/폰트 편집은 고주소 영역이므로 영향 없음 — 단, ROM 재작성 시 보존 확인.)
2. **헤더 체크섬 (0xBD)**: GBATEK 공식 = `chk = (-(0x19 + sum(bytes 0xA0..0xBC))) & 0xFF`.
   - ⚠️ **버그**: 현재 `tools/execute_phase5_5.py`는 `(0 - sum) & 0xFF`로 계산하여 **`0x19`를 누락** → 잘못된 체크섬을 써넣음 → **실기에서 부팅 거부**(에뮬은 관대해서 통과될 수 있음). **반드시 `-0x19` 포함하도록 수정.**
3. **세이브 타입 식별 문자열 보존**: ROM 내 `EEPROM_V`/`SRAM_V`/`FLASH_V`/`FLASH512_V`/`FLASH1M_V` 등 문자열로 세이브 타입을 감지함. 편집/확장 시 이 문자열을 깨지 않도록 주의(세이브 불가/오작동 방지).
4. **ROM 크기/확장**: 16MB 유지가 가장 안전. 폰트 데이터 추가로 확장이 필요하면 2의 거듭제곱(예: 32MB)로, 대부분의 플래시카트가 지원. 확장 영역은 ROM 끝에 append.
5. **배포**: IPS 대신 **BPS**(CRC 무결성 포함) 권장. 원본 ROM(16,777,216 bytes) 대비 생성.
6. **실기 특이사항**: 데이터(폰트/텍스트)만 바꾸는 한 타이밍/DMA 이슈는 거의 없음. mGBA에서 정확히 동작하면 실기도 동작한다고 봐도 무방.

---

## 1. 현재까지의 진단 요약

| 항목 | 상태 |
|------|------|
| 번역 CSV (`data/translation_for_import.csv`) | 18,262행 (EUC-KR로 삽입하도록 작성됨 — **이 게임은 Shift-JIS 기반이라 부적절**) |
| 한글 폰트 ROM 삽입 | ❌ 미완료 (이전 PHASE5-3은 *구조 분석*만, 실제 글리프 삽입 안 함) |
| `output/game_wars_korean_final.gba` | ❌ 흰 화면(부팅 실패) — 삽입 length-overflow로 ROM 손상 |
| 에뮬레이터 캡처 | ✅ **brew mgba 0.10.5 + screencapture** 로 해결 (VBA-M은 GPU 캡처 안 됨) |
| 게임 자동 진행(키 입력) | ⚠️ 합성 키 이벤트가 mGBA 게임 입력에 전달 안 됨 → **mGBA Lua 스크립팅으로 우회**(아래) |

원본 ROM은 mGBA에서 정상 부팅(NINTENDO PRESENTS → 타이틀 → 모드 선택) 확인됨.

---

## 2. 핵심 발견

### 2-1. 이 게임/유사 게임의 기존 번역 사례 (재사용 가능한 RE 자산)
- **romhacking.net Translations #7250** — "Game Boy Wars" 관련 번역 항목. **이 게임의 폰트/텍스트 시스템을 누군가 이미 분석했을 가능성**이 있어 최우선 확인 대상. (직접 fetch는 403 → 브라우저/대체 경로로 확인 필요)
  - https://www.romhacking.net/translations/7250/
- **Optiroc (David Lindecrantz)** — *Super Famicom Wars*(SNES) 영문 번역 제작자. **우리 게임(GBA)과는 다른 게임**이지만, 같은 Wars 계열 + 폰트/텍스트 렌더러 개조 노하우 + 범용 툴 보유.
  - GitHub: https://github.com/Optiroc
  - **SuperFamiconv** — 타일 그래픽 변환기(SNES/GB/GBC/**GBA** 등 지원). **한글 글리프 PNG → GBA 타일 포맷 변환에 직접 사용 가능.** https://github.com/Optiroc/SuperFamiconv
  - SuperFamicomWars-Translation (소스 공개): 텍스트 렌더러 개조/문자열 디코더 사례 참고용.
- **attilathedud/gba_dumper** — GBA 텍스트 수정 유틸. https://github.com/attilathedud/gba_dumper

### 2-2. 에뮬레이터 자동화 — mGBA Lua 스크립팅 (검증 자동화 해결책)
- mGBA 0.10+는 **Lua 스크립팅** 내장. "headless"(백그라운드 실행) 모드 언급 있음.
- 핵심 API (검증/자동화에 필요한 전부):
  - `emu:setKeys(keys)` / `emu:addKey(key)` — **버튼 입력**(합성 키 문제 우회)
  - `emu:runFrame()` — 프레임 진행
  - `emu:screenshot(filename)` — **실제 프레임버퍼 PNG 저장**
  - `emu:read8/16/32(addr)`, `emu:memory.vram:read8(offset)` — **메모리/VRAM 덤프** (폰트 글리프 추출에 핵심)
- 로드 방법: GUI `Tools > Scripting…`에서 .lua 로드(osascript 클릭 1회) → 이후 스크립트가 입력·진행·캡처·덤프를 **결정적으로** 수행.
- 문서: https://mgba.io/docs/scripting.html , https://mgba.io/2022/05/29/scripting/

### 2-3. GBA 폰트 해킹 방법론 (rh-reborn 가이드 외)
- 폰트는 ROM에 비트맵 타일로 저장(압축 or 비압축). **압축이면 런타임에 VRAM으로 풀리므로 VRAM 덤프로 확보 가능.**
- 글리프 포맷: 1bpp/4bpp/8bpp, 크기 보통 8x8 또는 8x16(가변도 있음). **대부분 문자는 3x5~16x16.**
- 인코딩: **.tbl 테이블**이 바이트값 ↔ 글리프 위치를 매핑. 커스텀 인코딩 문서화 필요.
- 도구: **CrystalTile2**(타일 뷰어+직접 타이핑 테스트+OCR), **Tinke**(NFTR, 문자 추가), TilEd.
- 가이드: https://rh-reborn.github.io/gba-and-ds-rom-hacking-guide/fonts.html

---

## 3. 한글(CJK) 특수 고려사항

- **글리프 수**: 완성형 한글 2,350자(+ASCII/기호). 일본어 폰트(수천 한자 글리프)가 있으면 글리프 슬롯은 충분할 가능성 큼.
- **셀 크기**: 한글은 8x8에 넣으면 매우 빡빡함. **12x12 이상**이 가독성 안전. → **게임의 실제 텍스트 폰트 셀 크기 확정이 선행 과제**(VRAM 덤프 또는 인게임 텍스트 화면 캡처로 측정).
- **인코딩 전략(중요)**: 이 게임은 **Shift-JIS** 2바이트. 현재 CSV는 EUC-KR이라 부적합. 두 가지 접근:
  - (A) **글리프 치환**: 기존 일본어 글리프 일부(예: 잘 안 쓰는 한자 영역)를 한글 글리프로 덮어쓰고, 번역 텍스트를 그 글리프를 가리키는 Shift-JIS 코드로 재인코딩.
  - (B) **렌더러/디코더 후킹**: 텍스트 렌더 루틴을 개조해 별도 한글 인코딩을 해석(난이도 높음, ASM 필요).
  - → 우선 (A)가 현실적. DTE/MTE(2글자→1코드) 등으로 공간 절약 가능.
- **공간/포인터**: 문자열이 포인터 테이블 참조인지 인라인인지 확인 필요. 길이 초과 시 포인터 재배치 또는 단축.

---

## 4. 권장 실행 계획 (단계별)

> 원칙: 각 단계는 **mGBA Lua로 결정적 검증** 가능해야 함.

1. **에뮬레이터 자동제어 하니스 구축** (foundation)
   - mGBA Lua 스크립트 작성: 부팅→타이틀→메뉴/대화까지 `setKeys`+`runFrame`로 진행, 주기적 `screenshot`, 그리고 `memory.vram` 덤프.
   - 이걸로 **인게임 텍스트 폰트의 실제 셀 크기·bpp 측정**(미해결 1순위).
2. **삽입 손상 수정 + 실기 체크섬 수정**
   - `execute_phase5_4.py`: 원본 일본어 바이트 길이를 넘겨 쓰지 않도록 제한(인접 데이터/코드 손상 방지) → 최소한 **부팅되는 ROM** 확보. mGBA로 부팅 확인.
   - `execute_phase5_5.py`: 헤더 체크섬에 **`-0x19` 포함**(§0-2) → 실기 부팅 가능. 닌텐도 로고/세이브 문자열 보존 검증.
3. **폰트 위치/포맷 확정**
   - VRAM 덤프에서 폰트 타일 식별 → ROM에서 동일 데이터 검색(비압축) 또는 압축 여부 판단.
4. **한글 글리프 제작**
   - 시스템 한글 폰트(예: `/Library/Fonts/NanumGothic.ttf`)를 PIL로 셀 크기(예: 12x12)에 맞춰 2,350자 비트맵 렌더 → SuperFamiconv 또는 자체 변환으로 GBA 타일(bpp 일치)로.
5. **글리프 삽입 + 인코딩 매핑 + 텍스트 재인코딩**
   - 글리프 치환(접근 A) → .tbl 작성 → 번역문을 새 코드로 재인코딩하여 삽입.
6. **PoC 검증 → 전체 적용 → 패치 배포**
   - 먼저 한 화면(예: 메뉴 몇 항목)만 한글로 → mGBA 스크린샷으로 정상 출력 확인 → 이후 전체 확대.
   - 최종 ROM에 대해 **실기 요건 재검증**(§0: 로고/체크섬/세이브 문자열/크기) → 원본 대비 **BPS 패치 생성**(flips 또는 python `beat`).
   - 가능하면 플래시카트로 실기 부팅 확인(사용자 협조).

---

## 5. 도구 & 환경 (이 머신에 준비됨)

- `mgba 0.10.5` (brew): `DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/mgba` , `libmgba.dylib`, 헤더(`/opt/homebrew/include/mgba`)
- `PIL 10.4.0` (글리프 렌더/타일 시트)
- 시스템 한글 폰트: `/Library/Fonts/NanumGothic.ttf` 등 (나눔고딕/바른고딕, AppleSDGothicNeo)
- `ffmpeg`, `brew`
- 자체 도구: `tools/font_dump.py`(타일 시트 렌더), `tools/loop_prepare_batch.py`/`loop_merge.py`(번역 파이프라인)
- 외부(설치/다운로드 검토): SuperFamiconv(빌드), CrystalTile2(Windows), Tinke

---

## 5-1. 확정된 기술 사실 (2026-05-21 실측)

mGBA 세이브스테이트 VRAM 추출 + 타일 렌더로 직접 확인:
- **폰트 포맷**: **8×8, 4bpp** GBA 타일 (타이틀 저작권 폰트·인게임 대화 폰트 모두). 한 글리프 = 32바이트.
- **폰트는 ROM에 LZ77 압축**되어 런타임에 VRAM으로 풀림. (VRAM의 폰트 타일 500여 개를 ROM에서 직접 검색 시 4개만 우연 매칭 = 비압축 아님)
- **부팅/체크섬 수정 완료**: `output/game_wars_korean_final.gba`는 이제 mGBA에서 정상 부팅·60fps. 단 텍스트는 폰트 부재로 깨져 보임(EUC-KR≠Shift-JIS).
- 인게임 대화 폰트 확인 화면: 게임 선택 화면 하단 "ムをプレイしますか？".

**검증 도구(확립됨)**:
- 입력: **Quartz CGEvent** (`/tmp/qkey.py` 패턴) — Return=36(Start), X=7(A), shift+F1(122)=세이브스테이트.
- 깨끗한 프레임/VRAM: 세이브스테이트 `.ss1`(PNG) → `gbAs` 청크 zlib 해제 → state 오프셋 **VRAM=0x1000(0x18000B)**, PRAM=0x800, OAM=0xC00. PNG 본문 = 240×160 프레임버퍼.

### LZ77 블록 조사 결과 (2026-05-21, `tools/lz77_scan.py`)
- ROM에 **유효 LZ77(0x10) 블록 914개**(4바이트 정렬, 폰트 크기대 필터). 큰 블록(0x14930=41KB/1282타일, 0x51E1EC 등)은 **맵/지형/일러스트 그래픽 타일**(렌더 확인) — 텍스트 폰트 아님.
- VRAM 폰트 타일(4bpp)을 914개 블록과 교차 매칭 → 상위는 화면 그래픽(예: 게임선택 화면 일러스트 0xC2FD70). **텍스트 폰트는 4bpp 비압축 타일로 매칭되지 않음.**
- 결론: **텍스트 폰트는 1bpp로 저장되거나, 표시되는 글자만 on-demand로 1bpp→4bpp 변환**되어 VRAM에 올라오는 구조로 추정. 단순 "4bpp 글리프 치환"이 안 통함 → 폰트 소스(1bpp) 위치 + 변환/디컴프 루틴 파악 필요(난이도 상승).
- 다음 조사: (a) ROM에서 **비압축 1bpp 폰트** 영역 탐색(ASCII '0-9'·가나 고주온 순서가 시그니처), (b) 폰트를 그리는 코드/디컴프 호출 추적(`tools/trace_font_pointers.py`, ASM).

### 압축 폰트 대응 경로 (택1)
- (1) **압축 폰트 블록 수정**: ROM에서 LZ77 블록(헤더 0x10) 스캔→VRAM 폰트 타일 포함하는 블록 탐색→해제→글리프를 한글로 치환→재압축→삽입(크기 변하면 리포인트). ASM 불필요, 자기완결적.
- (2) **폰트 로더 리포인트(ASM)**: 폰트 DMA/디컴프 호출을 찾아 확장 ROM의 비압축 한글 폰트로 교체.
- 8×8은 한글 가독성이 매우 빡빡 → 렌더러가 셀 크기를 키울 수 있는지(또는 2타일=8×16 사용 여부) 확인 필요.

---

## 5-2. 기존 영문 패치/디컴파일 RE 조사 (2026-05-21)

> 사용자 지정 방향: "기존 영문패치 RE 활용".

**핵심 사실**: 이 게임 **"Game Boy Wars Advance 1+2" = 서구판 Advance Wars + Advance Wars 2** (동일 엔진, 공식 영문판 존재).

조사한 자료:
- **ketsuban/advancewars** — *Advance Wars (USA)* **디컴파일**(바이트 동일 재현). 확인: 게임이 **BIOS `LZ77UnCompVram`/`LZ77UnCompWram`/`RLUnCompVram`** 로 그래픽·폰트를 VRAM에 로드(`asm/libraries.s`). 단, **저수준 asm이라 font/charmap 친절 라벨 없음**, 오프셋은 영문 ROM 기준(JP 컴필레이션과 다름).
- **eastebry/AdvanceWarsRomHackingToolkit** — AW2 **게임플레이 모드**(유닛 등)용 파이썬 툴. **폰트/텍스트와 무관.**
- 영문 Advance Wars는 **ASCII 인코딩**(단순)으로 텍스트 처리.

**시사점 / 권장 경로**:
- (A) **JP ROM 폰트를 타깃 추적**: 디컴파일에서 텍스트 폰트를 올리는 `LZ77UnCompVram` 호출 패턴을 참고해, JP ROM에서 폰트 LZ77 소스 포인터를 찾는다(맹목 스캔보다 표적화). 폰트는 **1bpp 가능성**(앞 §5-1에서 4bpp 비압축 매칭 실패) → 1bpp로 디컴프/렌더 확인.
- (B) **(전략적 대안) 영문 Advance Wars (USA) ROM을 베이스로 한글화**: 깨끗한 ASCII 라틴 폰트 + 디컴파일로 엔진 문서화됨 → 한글 글리프 추가/인코딩 확장이 JP 2바이트 시스템보다 **훨씬 용이**. 단, 현재 JP 기반 18k 번역 자산을 영문 스크립트 위치로 재매핑/재번역해야 함.
- 결론: 기존 RE는 **엔진(압축 로딩) 확인**까지는 줬지만 JP 컴필레이션용 폰트/인코딩 맵을 턴키로 주진 않음. 한글 표시는 여전히 (A) 표적 폰트 추적 or (B) 영문 ROM 리베이스가 필요.

---

## 6. 미해결 / 리스크

- **인게임 텍스트 폰트 셀 크기 미확정** — 8x8이면 한글 가독성 난제. (1순위 확인)
- **폰트 압축 여부 미확정** — 압축이면 ROM 직접 수정 어려움(VRAM은 풀려 있음).
- **인코딩 재매핑 규모** — 18,262행을 새 코드 체계로 재인코딩 필요.
- **합성 키 입력 불가** — mGBA Lua로 우회(GUI에서 스크립트 1회 로드 필요).
- 전체 난이도: 프로젝트 자체 추정 "2~4주, 전문 도구". 자동 루프로 완주 가능성은 불확실 → PoC로 조기 검증 권장.

---

## 7. 참고 링크

- Game Boy Wars 번역(확인 대상): https://www.romhacking.net/translations/7250/
- Optiroc GitHub: https://github.com/Optiroc — SuperFamiconv: https://github.com/Optiroc/SuperFamiconv
- gba_dumper: https://github.com/attilathedud/gba_dumper
- GBA/DS 폰트 해킹 가이드: https://rh-reborn.github.io/gba-and-ds-rom-hacking-guide/fonts.html
- mGBA 스크립팅: https://mgba.io/docs/scripting.html , https://mgba.io/2022/05/29/scripting/
- GBATEK(GBA 하드웨어/타일 포맷/헤더): https://problemkaputt.de/gbatek.htm , 헤더: https://problemkaputt.de/gbatek-gba-cartridge-header.htm
- 실기 헤더 검증 정리: https://deepwiki.com/davidgfnet/superfw-nds-flasher-tool/7.1-gba-header-validation
- 플래시카트 호환성: https://consolemods.org/wiki/GBA:Flash_Cart_Compatibility
- BPS 패치 도구: Floating IPS(flips) https://github.com/Alcaro/Flips , beat(BPS)
- 실기 패치/리프로 가이드: https://gbarompatcher.com/guide
