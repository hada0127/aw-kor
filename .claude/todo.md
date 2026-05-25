# TODO — 본문 대화 한글화 구현 (3 세션 계획)

> **새 세션 START: 먼저 이 순서로 읽어라**
> 1. `CLAUDE.md` (작업 지침)
> 2. `docs/research.md` 맨 끝 2개 섹션 (대화 렌더 파이프라인 완전 RE — 주소·테이블·공식)
> 3. `docs/success.md` 맨 끝 3개 PoC 섹션 (FONT_BASE 주입 / 멀티음절 / 예약코드)
> 4. `docs/DIALOGUE_KOREAN_IMPLEMENTATION_PLAN.md` (Phase A~E 로드맵)
> 5. `data/reserved_codes.json` (예약 코드 풀)
>
> **작업 규칙(필수)**: 막히거나 의미있는 작업 완료 시 **codex+gemini 엄격 리뷰**.
> `codex exec "$(cat temp/p.md)" </dev/null` / `gemini -e none --approval-mode yolo -p "$(cat temp/p.md)"`.
> (gemini는 `-e none` 없으면 MCP 오류로 실패. codex는 `</dev/null` 없으면 stdin hang.)
> 완료 시 docs/{success,fail,research,plan}.md 갱신 + commit + push.

---

## ✅ 이미 검증된 것 (2026-05-25) — 다시 하지 말 것
- **FONT_BASE(0x08B974D0)+idx*0x20 에 galmuri 글리프(ink 인덱스 10) 주입 → 대화에 한글 렌더.** 인게임 확인 완료. ASM hook 불요(글리프 자체).
- **예약 한자코드(미사용) → 한자 테이블 lookup → 그 글리프 렌더** 도 확인(PoC: 0x8AEF→"테"). 텍스트 rewrite 전파 확인.
- **합성 키 입력 작동** → mgbah 헤드리스 네비로 인게임 검증 가능.
- 재현 PoC 빌드: `temp/poc_ha2han.gba`, `temp/poc_multi.gba`, `temp/poc_reserved.gba`.

## 🔑 핵심 주소 치트시트 (RE 완료)
| 항목 | 주소 |
|---|---|
| FONT_BASE (글리프, 타일=idx*0x20, 파일오프셋 0xB974D0) | 0x08B974D0 |
| 변환 루틴 IWRAM / **ROM 소스(패치 대상)** | 0x030065E0 / **0x08EFE788** |
| 변환 루틴 내 테이블 start/end 리터럴 (IWRAM) | 0x030067C8=0x08B80B7C, 0x030067CC=0x08B8180C |
| → ROM 소스 내 해당 리터럴 (추정, 검증 필요) | 0x08EFE788+0x1E8=0x08EFE970 부근 |
| **한자 테이블** (530엔트리×6B = [SJIS_LE, top_idx, bot_idx]) | 0x08B80B7C ~ 0x08B8180C |
| 타일복사+팔레트리맵 IWRAM | 0x03006744 (copy 호출자 veneer lr=0x08B1BF0D) |
| 빈 ROM 공간 | 0xA3CF14(780KB,0xFF) · 0xF00000(896KB,0x00) · 0x27FCCE(513KB) |
| 헤드리스 대화 네비 | `frames 400` + (`keys 8;f12;keys 0;f30;keys 1;f12;keys 0;f40`)×10 → hajimemashite 도달 |

## ⚠️ 알려진 함정
- 텍스트가 ROM→EWRAM 복사 후 파싱되기도 함. 텍스트 rewrite는 **실제 렌더되는 메시지**를 패치해야 함(hajimemashite 0xDF8E3C는 ROM에서 렌더됨 확인. welcome 0xDF8E16은 내 네비에서 미렌더였음).
- 글리프 idx는 16비트 → FONT_BASE+0xFFFF*0x20=0x08D974B0 까지만 도달. 한글 글리프는 이 범위 빈 공간에.
- 체크섬: 헤더(0xA0–0xBC) 안 건드리면 0xBD 유지. 그래도 `chk=(-(0x19+sum(rom[0xA0:0xBD])))&0xFF; rom[0xBD]=chk` 재계산.
- 예약 코드는 **유효 SJIS 한자만**(trail byte 제어코드 충돌 회피). VWF: 예약코드 width=8 고정.

---

## 📌 SESSION 1 — 커버리지 확인 + 글리프 영역 빌드 ✅ 완료 (2026-05-25)

**목표**: 풀게임 렌더 경로가 단일한지 확인 + 음절 글리프 블롭 생성. → 달성. 상세 research/success.md.

1. **Phase A 커버리지** ✅
   - [x] 번역 텍스트(대화/메뉴/유닛명)는 **단일 변환루틴**(ROM 0x08EFE788) — veneer 0x08B1BEFC 호출자
     정확히 2곳(0x08B1275E, 0x08B12B1A), 동적 167히트 전부 lr=0x08B1BF0D.
   - [x] 별도 경로 발견: **폰트 bulk DMA→VRAM 업로드 2곳**(0xB11B54=704타일, 0xB6A86C=16타일) —
     프리로드+타일맵(가나 입력 그리드/심볼). per-char 변환루틴 안 거침.
   - [~] **잔여**: bulk-DMA 화면이 번역 텍스트를 쓰는지(가나 피커면 무관) — Session 3 QA에서 확인.
   - [~] 전투/맵/스탯 직접 진입은 미수행(세이브 없음). 정적 분석으로 단일 per-char 경로 확정했으므로
     배치 전략엔 영향 없음. Session 3 QA에서 화면별 스크린샷으로 보강.

2. **Phase C-1 글리프 블롭** ✅
   - [x] `tools/build_korean_glyph_blob.py`: CSV 고유 음절 **1030개**(사전JSON보다 궈·깎 2개 많음) →
     dedup **고유 800타일=25,600B**(top437+bot363) → `data/korean_glyph_blob.bin` + `data/syllable_to_glyph.json`.
   - [~] 세로위치 top_pad=3 기본값 사용(PoC와 동일). UI 잘림은 Session 3 QA에서 미세조정.

3. [x] codex+gemini 리뷰(gemini는 -e none에도 API오류 잦음 → 간결 프롬프트로 성공), 커밋.

**배치 전략 확정**: 한글 글리프는 **0x08F00000(파일 0xF00000, 896KB 빈공간)**에 배치.
1순위(데이터-only): per-char FONT_BASE 리터럴 **0xEFE97C만 0x08F00000으로 repoint** + 폰트 idx0..0x5FF(48KB)
복사 + 한글 800타일 idx0x600~0x920 + 테이블 확장(리터럴 0xEFE970/0xEFE974). **변환루틴에 idx bound check 없음 확인.**
2순위(fallback): 변환루틴 ASM hook + 별도 한글 base. 두 리뷰어 추천이나 RE로 1순위 장애물 해소됨.

---

## 📌 SESSION 2 — 테이블 확장 + 1개 대화 풀 한글 빌드·검증 (다음 세션 START)

**목표**: 800 글리프 주입 + 예약코드↔음절 매핑 + 테이블 확장 → **한 대화를 통째로 한글** 렌더(인게임).
**확정 파라미터(Session 1 RE)**: 한글 글리프 base **0x08F00000**, 폰트복사 48KB(idx0..0x5FF), 한글 idx 0x600~0x920.
변환루틴 리터럴: FONT_BASE@**0xEFE97C**, 테이블 start@**0xEFE970**(=0x08B80B7C), end@**0xEFE974**(=0x08B8180C).

1. **글리프 주입 + FONT_BASE repoint (1순위 데이터-only)**
   - [ ] 원본 폰트 파일 0xB974D0..0xBA34D0(48KB=idx0..0x5FF)를 **파일 0xF00000**으로 복사.
   - [ ] `data/korean_glyph_blob.bin`(800타일,25600B)을 0xF00000+0xC000=**0xF0C000**(idx 0x600)에 기록.
   - [ ] 리터럴 **0xEFE97C**: 0x08B974D0 → **0x08F00000** 패치. (bulk-DMA용 0xB11B74/0xB6A894는 건드리지 말 것)
   - [ ] 음절→로컬타일idx(`syllable_to_glyph.json`) → 글로벌 FONT idx = 0x600 + local_idx.

2. **예약 코드 할당 + 테이블 확장**
   - [ ] `data/reserved_codes.json` extend_pool에서 음절 1030개에 예약 SJIS 코드 1:1(repoint_pool 13 우선
     소진 후 extend_pool). 음절→예약코드 맵 `data/syllable_to_code.json`. (코드는 유효 SJIS 한자대역, trail
     제어코드 충돌 회피.)
   - [ ] 한자 테이블(536엔트리)을 빈 ROM(예 0xF20000)으로 relocate-copy + 1030 한글 엔트리
     [code_byteswap(2), top_global_idx(2), bot_global_idx(2)] 추가 = 1566엔트리. ⚠ 검색키는 **byteswap(SJIS)**
     (루틴 0xEFE848 `cmp r7,r2`, r7=byteswap). top/bot idx는 0x600+local.
   - [ ] 리터럴 0xEFE970(start)/0xEFE974(end)를 새 테이블 주소로 패치. (idx에 bound check 없음 — 안전)
   - [ ] (대안) 어려우면 ASM hook: 예약코드 감지→`idx=0x600+(code-KOR_BASE 매핑)`, base 0x08F00000.

3. **1개 대화 풀 한글 빌드 + 검증**
   - [ ] hajimemashite(0xDF8E3C)를 한글 번역 → 음절을 예약코드로 인코딩 → 텍스트 rewrite.
   - [ ] 체크섬 재계산, 빌드 + 헤드리스 네비(`temp/raw2png.py`로 PNG) + 스크린샷.
     **acceptance: 대화 한 줄이 예약코드 경유로 통째로 한글 + 다른 화면 안 깨짐.**
   - [ ] 실패 시 fail.md(텍스트전파/테이블포맷/idx/리터럴위치 중 무엇).

4. 리뷰 + 커밋(증거 docs/screenshots).
**도구**: `tools/build_korean_glyph_blob.py`, `temp/raw2png.py`(raw→png), 헤드리스 네비 레시피(아래 치트시트).

---

## 📌 SESSION 2 ✅ 완료 (2026-05-25) — 데이터-only 풀파이프라인 인게임 검증
"はじめまして"→"안녕하십니까" 렌더 성공. `tools/build_korean_poc.py --stage {a,b}`. 상세 success.md.
산출: `data/syllable_to_code.json`(음절→예약코드), repoint+테이블확장 메커니즘 확정.

---

## 📌 SESSION 3 — 전체 인코딩 + QA + 빌드 (다음 세션 START)

**목표**: 18,262행 번역문 전체를 예약코드로 인코딩한 풀게임 ROM + QA.
**Session2 완료로 메커니즘은 확정** — 남은 건 스케일업 + 레이아웃/커버리지 QA. byte budget 0행 초과(사전확인).

### ⚠️ 착수 전 게이트 (codex+gemini 리뷰 수렴 — 폰트보다 이게 실패지점)
0. [ ] **화면별 렌더경로 매트릭스(최우선)**: bulk-DMA 경로(0xB11B74=704타일,0xB6A894=16타일)로 렌더되는
   화면(이름입력 가나그리드/도움말/메뉴/전투UI/맵/통신)이 번역 텍스트를 쓰는지 판정. 쓰면 그 경로 별도 처리
   필요. 판정법: 화면 진입 시 폰트소스가 0x08F00000인지 vs 원본 blob인지 + per-char 변환루틴 히트 여부.
0b.[ ] **줄바꿈 기준 확정**: 자동wrap이 byte/glyph/pixel 중 무엇인지. 제어코드(0x0A 줄바꿈,0x09 등) 포맷.
   한국어가 길어 박스밖 출력/다음줄침범/선택지겹침이 주 실패 → 빌드타임 줄길이 강제.

1. **전체 인코딩 파이프라인** ✅(1차 완료)
   - [x] `tools/build_korean_full.py`: 전체 CSV 인코딩(한글→예약코드, ASCII 1B, 일본어→shift_jis passthrough).
     슬롯길이=found_texts(권위), encoded>슬롯이면 skip+리포트. → **13,280행 written, overflow 2,322**.
   - [x] 인접손상 없음(슬롯 clear후 ≤슬롯 기록). 헤더체크섬·16MB·부팅 OK. 산출 `output/game_wars_korean_full.gba`.
   - [x] overflow 리포트 `temp/encode_report.csv`. 인게임 한글 렌더 검증(이름입력/메뉴 화면).
   - [ ] (잔여) 제어코드 의미보존 검증, 예약외코드/테이블 lookup실패 빌드게이트 강화.

2. **QA**
   - [ ] `tools/lint_translation.py` error 0 유지.
   - [ ] 헤드리스 **cold-boot 직행** 주요화면 순회 스크린샷(`temp/raw2png.py`) — 받침/색/세로위치/잘림.
     (캐시 글리프 false positive 회피)
   - [ ] 테이블 선형검색 1566엔트리(3배)→대량출력 프레임드랍 확인.
   - [ ] 실기 체크섬(0xBD) 유효 + 부팅. (헤더 무변경이면 유지)

3. **배포**
   - [ ] BPS 패치 생성(`tools/make_bps.py` 또는 신규), dist/ 릴리스.

4. 리뷰 + success/plan.md 갱신 + 커밋·푸시.

---

## 미해결 리스크 (각 세션에서 부딪힐 수 있음)
1. 대화 외 렌더 경로 분기(Session 1 Phase A에서 판정).
2. 예약 코드 충돌(빌드 게이트로 방어).
3. 글리프 idx 16비트 한계 / 배치 공간(64KB).
4. 텍스트 폭 오버플로(Session 3 QA).
5. 변환 루틴 ROM 소스 리터럴 위치 — Session 2에서 실측 검증 필요(0x08EFE970은 추정).
