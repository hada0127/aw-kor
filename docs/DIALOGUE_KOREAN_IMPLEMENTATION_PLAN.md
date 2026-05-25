# 본문 대화 한글화 구현 계획 (2026-05-25)

> RE 완료 + 인게임 PoC 2건 성공 + codex/gemini 2차 리뷰 반영 후 작성한 실행 로드맵.
> 근거: `docs/research.md`(파이프라인 RE), `docs/success.md`(PoC), `docs/screenshots/SUCCESS_dialogue_korean_*`.

## 검증된 사실 (재확인 완료)
- 대화 글리프는 **FONT_BASE(0x08B974D0)+idx*0x20** 비압축 타일을 per-char로 VRAM 복사(IWRAM 0x03006744, 팔레트 리맵).
- **PoC**: 그 자리에 galmuri 글리프(ink 인덱스 10) 주입 → 대화에 한글 렌더(단일·멀티음절, full-width 간격, 색 정상). ASM hook 없이 글리프 렌더됨.
- SJIS→idx 변환: IWRAM 0x030065E0(**ROM 소스 0x08EFE788**). 한자(>0x8397)는 **테이블 0x08B80B7C**(530엔트리×6B=[SJIS_LE, top_idx, bot_idx], 끝 0x08B8180C) 검색.
- 합성 키 입력 작동 → mgbah 헤드리스 네비로 인게임 검증 가능.
- 예약 코드 풀 확보: `data/reserved_codes.json` (미사용 유효 SJIS 3326개).

## 핵심 설계 결정 (리뷰 수렴)
1. **매핑**: gemini 권장 — 원본 공식 역산 대신, 변환 루틴 ROM(0x08EFE788)에 **ASM hook** 또는
   **한자 테이블 확장**으로 예약 코드를 한글 글리프로. (둘 중 테이블 확장이 데이터 위주라 더 단순할 수 있음)
2. **width(VWF)**: gemini #1 경고 — 예약 코드 width를 **8 고정**(기본 ip=8 활용). 자간 불균일 방지.
3. **글리프**: galmuri, ink 인덱스 10, top/bot 타일 각 0x20. 세로 위치는 통일(최악 UI 기준), 필요 시 변환 루틴에서 Y-offset 분기.
4. **예약 코드**: JIS L2 고대역 우선, 원문·테이블·런타임 harvest 전수 미사용 확인.

## 구현 단계

### Phase A — 커버리지 확인 (리뷰 최대 리스크, 먼저)
- [ ] FONT_BASE(0x08B974D0) read watchpoint + 0x03006744 BP를 걸고 헤드리스로 도달 가능한 모든
  화면(타이틀/모드선택/이름입력/대화) 순회 → caller set 수집. (이미 그리드+대화 = 0x03006744 확인)
- [ ] 가능하면 전투/맵/스탯 진입(세이브 활용 or 긴 네비) → 같은 경로인지. **안 걸리면 별도 파이프라인**(tilemap/OBJ) → 그 경로 별도 RE 필요.
- 산출: 렌더 경로별 caller 문서. (research.md 갱신)

### Phase B — 예약코드 end-to-end PoC (테이블 경로)
- [ ] 예약 코드 1개(테이블 추가 or repoint), 그 글리프 idx에 한글 주입, 도달 가능 대화 텍스트(EWRAM/ROM)에
  그 코드 1개 삽입 → 인게임에서 한글 렌더 확인. (text rewrite는 EWRAM 복사 경로 주의 — Phase A에서 실제
  텍스트 소스 주소 확정 후)
- 이게 "예약코드→테이블→글리프" 전체 사슬 검증. (현 PoC는 기존 코드/오프셋만 검증)

### Phase C — 한글 글리프 영역 + 테이블 확장
- [ ] 1028 음절 galmuri top/bot 타일 생성(ink 10, width 8 디자인). `data/korean_glyphs_8px.json` 활용/확장.
- [ ] 글리프를 FONT_BASE 도달 가능 idx 범위(16bit idx*0x20)의 빈 영역에 배치. 공간/idx 한계 확인.
- [ ] 한자 테이블(0x08B80B7C) 확장: 빈 ROM으로 relocate + 1028 한글 엔트리 추가, 변환 루틴(0x08EFE788)의
  테이블 start/end 리터럴(0x08B80B7C/0x08B8180C) 갱신. 또는 ASM hook.
- [ ] 체크섬 재계산.

### Phase D — 번역문 인코딩 + 빌드
- [ ] `translation_for_import.csv`의 각 음절 → 예약 코드(2바이트)로 인코딩.
- [ ] 빌드 검증(빌드타임 게이트): 예약 테이블 밖 코드 사용 시 실패, 원문 잔존 텍스트가 예약 코드 포함 시 실패.
- [ ] 길이 예산(bytes) 재확인 — 한글 2바이트/음절(예약 코드도 2바이트)이라 기존 예산 모델 유지.

### Phase E — QA
- [ ] 헤드리스 네비 + 스크린샷으로 주요 화면 한글 확인.
- [ ] 텍스트 폭/줄바꿈(한국어가 길어져 박스 넘침) 대량 QA — `tools/lint_translation.py` + reflow.
- [ ] 받침/세로 위치/색 최종 점검.

## 미해결 리스크 (리뷰 지적)
1. **대화 외 렌더 경로 분기** (Phase A에서 해소). 가장 큼.
2. 예약 코드 충돌(미번역/시스템 텍스트) — 빌드 게이트로 방어.
3. 글리프 용량/idx 한계(16bit idx → FONT_BASE+0xFFFF*0x20=0x08D974B0 까지). 1028*0x40≈64KB 배치 공간.
4. 텍스트 폭 오버플로(한국어 길이) — QA 필요.
5. SJIS 제어코드 경계(trail byte 0x5C 등) — 예약 코드는 유효 SJIS 한자만.

## 도구 (현재까지)
- `tools/find_reserved_codes.py` — 예약 코드 풀 (`data/reserved_codes.json`).
- `tools/render_galmuri_8x16.py`, `galmuri_cell.py`, `bdf.py` — 글리프 생성(ink 10).
- `tools/mgba_harness.c`(/tmp/mgbah) — 헤드리스 BP/watch/네비/스크린샷.
- PoC 빌드 예: `temp/poc_ha2han.gba`, `temp/poc_multi.gba` (재현 가능).
