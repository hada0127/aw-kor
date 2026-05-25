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

## 📌 SESSION 1 — 커버리지 확인 + 글리프 영역 빌드 (저위험, 인프라)

**목표**: 풀게임 렌더 경로가 단일한지 확인 + 1028 음절 글리프 블롭 생성.

1. **Phase A 커버리지** (리뷰 최대 리스크)
   - [ ] mgbah로 `break 0x03006744` + `keys`로 도달 가능한 모든 화면(타이틀/모드선택/이름입력/대화/가능하면 맵·전투) 순회. copy 호출자(lr) 분포 수집.
   - [ ] 도달 가능 화면은 이미 단일 경로(lr=0x08B1BF0D) 확인됨. **전투/맵/스탯** 진입 시도(세이브 파일 `output/*.sav` 활용 or 긴 네비).
   - [ ] 글자 렌더되는데 0x03006744 BP 안 걸리면 → **별도 파이프라인**(tilemap/OBJ). 그 경로 별도 RE 항목으로 fail.md/research.md 기록.
   - 산출: 렌더 경로별 caller 문서(research.md). **acceptance: 대화+UI가 같은 경로면 OK, 다르면 추가 RE 범위 확정.**

2. **Phase C-1 글리프 블롭**
   - [ ] `data/translation_for_import.csv`의 고유 한글 음절 추출(약 1028개, `data/korean_glyphs_8px.json`에 사전렌더 있음).
   - [ ] `tools/render_galmuri_8x16.render_char`로 각 음절 top/bot 타일(각 0x20, ink 인덱스 10) 생성 → 글리프 블롭(`data/korean_glyph_blob.bin`) + 음절→글리프idx 맵.
   - [ ] 세로 위치 통일(현 PoC는 약간 높음 — top_pad 조정 검토. 최악 UI 기준).
   - **acceptance: 1028 음절 × (top+bot) 블롭 생성, FONT_BASE 빈 idx 범위에 배치 계획 확정.**

3. 리뷰 + 커밋.

---

## 📌 SESSION 2 — 테이블 확장 + 1개 대화 풀 한글 빌드·검증

**목표**: 예약 코드 1028개 → 한자 테이블 확장 + 글리프 주입 + **한 대화를 통째로 한글**로 렌더(인게임 확인).

1. **예약 코드 할당**
   - [ ] `data/reserved_codes.json`의 extend_pool에서 1028개 선정(JIS L2 고대역 우선, 원문·테이블·런타임 harvest로 미사용 재확인). 음절→예약코드 1:1 맵(`data/syllable_to_code.json`).

2. **Phase C-2 글리프 주입 + 테이블 확장**
   - [ ] 한글 글리프 블롭을 FONT_BASE 빈 idx 영역(예: idx 0x1000~, offset 0x20000~)에 주입. idx 16비트 한계 확인.
   - [ ] 한자 테이블(530엔트리)을 빈 ROM(0xF00000)으로 relocate + 1028 한글 엔트리([code_LE, kor_top_idx, kor_bot_idx]) 추가 = 1558엔트리.
   - [ ] **변환 루틴 ROM 소스(0x08EFE788)의 테이블 start/end 리터럴**(0x08B80B7C/0x08B8180C → 추정 0x08EFE970 부근)을 새 테이블 주소로 패치. ⚠️ IWRAM은 ROM에서 복사되므로 **ROM 소스를 패치**해야 영구.
   - [ ] (대안) 테이블 확장이 까다로우면 gemini ASM hook: 0x08EFE788에 예약코드 선형매핑 분기 삽입.

3. **1개 대화 풀 한글 빌드**
   - [ ] hajimemashite "はじめまして　iさん！"를 한글 번역 → 각 음절을 예약코드로 인코딩 → 0xDF8E3C 텍스트 rewrite.
   - [ ] 빌드 + 헤드리스 네비 + 스크린샷. **acceptance: 대화 한 줄이 예약코드 경유로 통째로 한글 렌더 + 다른 화면 안 깨짐.**
   - [ ] 실패 시 fail.md 기록(텍스트 전파/테이블 포맷/idx 한계 중 무엇인지).

4. 리뷰 + 커밋(증거 스크린샷 docs/screenshots).

---

## 📌 SESSION 3 — 전체 인코딩 + QA + 빌드

**목표**: 18,262행 번역문 전체를 예약코드로 인코딩한 풀게임 ROM + QA.

1. **전체 인코딩 파이프라인**
   - [ ] `tools/execute_phase5_4.py`를 EUC-KR → **예약코드 인코딩**으로 교체(음절→예약코드, length 예산 내). 빌드타임 게이트: 예약 외 코드 사용/원문 잔존 충돌 시 실패.
   - [ ] 글리프·테이블·인코딩 일괄 빌드 스크립트.

2. **QA**
   - [ ] `tools/lint_translation.py` (error 0 유지 — hex_token 등).
   - [ ] 텍스트 폭/줄바꿈: 한국어가 일본어보다 길어 박스 넘침 → `tools/reflow_dialogs.py`로 점검(박스 폭 보정 필요).
   - [ ] 헤드리스로 주요 화면 순회 스크린샷 — 받침/색/세로위치/잘림 확인.
   - [ ] 실기 체크섬(0xBD) 유효 + 부팅 확인.

3. **배포**
   - [ ] BPS 패치 생성(`tools/make_bps.py`), dist/ 릴리스.

4. 리뷰 + success/plan.md 갱신 + 커밋·푸시.

---

## 미해결 리스크 (각 세션에서 부딪힐 수 있음)
1. 대화 외 렌더 경로 분기(Session 1 Phase A에서 판정).
2. 예약 코드 충돌(빌드 게이트로 방어).
3. 글리프 idx 16비트 한계 / 배치 공간(64KB).
4. 텍스트 폭 오버플로(Session 3 QA).
5. 변환 루틴 ROM 소스 리터럴 위치 — Session 2에서 실측 검증 필요(0x08EFE970은 추정).
