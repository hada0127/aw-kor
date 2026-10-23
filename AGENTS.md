# AGENTS.md — Game Wars 한글화 프로젝트 (Codex/Claude 공용 컨텍스트)

> 리뷰는 **Codex + Claude**.
> 이 파일은 Codex와 Claude 리뷰 세션이 프로젝트 규칙·사실을 읽도록 두는
> 공용 진입점이다. **상세 작업 지침과 최신 사실은 [`CLAUDE.md`](CLAUDE.md)가 정본**이며,
> 이 파일은 그 요약 + 리뷰어 역할 안내다.

## 프로젝트
- 대상: **Game Boy Wars Advance 1+2 (GBA, 일본판)** 한글화. 배포는 BPS/IPS 패치.
- 목표: 실기/에뮬에서 한글 정상 출력 + **원본 화면 대비 누락·깨짐·스프라이트 손상·띄어쓰기 오류 0**.
- 모든 응답/리뷰는 **한국어**로 작성한다.

## 핵심 산출물 / 파이프라인
- 원본 ROM: `original/Game Boy Wars Advance 1+2 (Japan).gba` (SHA-256 `a8ad7c7d…`).
- 빌드: `python3 tools/build_korean_full.py` (base=**원본 ROM** 기본 → `output/game_wars_korean_full.gba`; `v56_polished`는 부재/구버전, `--base`로만).
  글리프 주입 + 한자테이블 확장 + 예약코드 인코딩 + 1편 이름그리드 + 2편 hook + 그래픽/OBJ 패치 + 체크섬.
- 산출물 3종(full/final/title_test)은 항상 동일 SHA로 동기화한다.
- 번역 데이터: `data/translation_for_import.csv`, 추출 원본 `data/game_wars_found_texts.csv`(노이즈 포함).
- QA: `tools/qa_text_fit.py`, `qa_japanese_residuals.py`, `qa_placeholder_residuals.py`,
  `qa_visual_regions.py`, `phase6_basic_test.py`.
- RE 사실: `docs/research.md`, 성공/실패 기록 `docs/success.md` / `docs/fail.md`. 진행 기준은 `todo.md`.

## 리뷰어에게 (Codex / Claude)
- 톤: **엄격·비판적**. 결함·누락·근거 부족·대안을 적극 지적한다. 통과시키려 하지 말 것.
- 특히 **"꼼수"(fragile hack)** 여부를 본다: 고정주소 raw OBJ 덮어쓰기, LZ77 in-place 재압축,
  ASCII 테이블 blank, 전각→반각 padding 글리프, 폭 맞추기용 텍스트 축약(의미 손상),
  KANA_REMAP, 예약코드 재사용 — 이들이 실제로 안전한지, 더 견고한 해법이 있는지 따진다.
- 근거 없는 "깨끗하다" 결론을 경계한다. QA 도구의 green check가 **실제 화면**을 보장하는지 의심한다.

## 작업 디렉토리 규칙
- 임시물은 전부 `temp/`. `/tmp/` 및 루트 직접 생성 금지. 백업은 git으로(`*.bak` 만들지 않음).

## 토큰·자원 절약
- 정본: [`CLAUDE.md`](CLAUDE.md)의 「토큰·컴퓨터 자원 절약 원칙」. 검증된 ROM 규칙을 재사용하고 반복 생성·검사·재생은 로컬 도구로 처리한다.
- 필요한 주소/함수/실패 항목만 읽고 상세 로그는 파일로 보존한다. AI는 새 원인 분석·의미·시각 검수에 집중한다.
- 전체 빌드/대량 재생은 하나씩, 정상 플레이 하네스는 편당 하나·최대 둘. 무거운 작업은 낮은 우선순위로 실행한다. 공유 파일 소유권을 나눠 충돌을 피한다.
- 절약을 이유로 의미·제어 토큰·회귀/실화면 증거·필수 리뷰를 생략하거나 미검증 구간을 완료 처리하지 않는다.

## 2026-10-23 이름 입력 조합 Phase A

- ROM 비의존 참조 모델은 `tools/hangul_compose.py`, 검증은 `python3 -I tools/test_hangul_compose.py`와 `python3 -I tools/hangul_compose.py --report`다. 계약·해시·실제 출력은 `docs/reports/name_grid_2026-10-23/COMPOSITION_SPEC.md`를 따른다.
- 2350 밖 후보 키는 대체 없이 원자적으로 거부한다. committed/active를 분리하고 8번째 active 편집을 허용한다. 미완성 confirm/space는 거부하며 자모를 유지한다. 저장은 committed만 정확히 16바이트다.
- 매핑 2350개와 키열 도달 2345개(중간 후보 누락 5개)를 구분한다. 이 수치는 참조 모델 결과이며 ROM 동작 보장이 아니다. 공백 0x8140의 네이티브 저장 의미도 unverified다(Phase B에서 확인: 끝 공백은 native trim, 중간 공백은 유지 — `PHASE_B_RE.md` §5).
- Phase A 준비·테스트는 ROM 통합 완료가 아니다. (이력) 작성 당시에는 자산 복구 대기였고, 2026-10-23 Phase B에서 복구·조사·승인 계획을 거쳐 ROM 통합 후보를 만들었다(아래). 공유 A3 가나 그림을 보존한다. 구현 후 리뷰·커밋은 총괄이 맡는다.

## 2026-10-23 이름 입력 조합 Phase B (2편 맵 에디터 · 소스 main 반영, ROM은 별도 후보)

- 소스 반영 commit `4baba1f346c105d72a439f9af164f175a72544a0`: Astra 최종 코드 리뷰 full→delta2 승인(Critical·필수 지적 없음), feature push·main fast-forward·origin/main push 완료를 총괄의 ROOT_PROOF로 확인했다. secret scan은 RC1(후보 176건 전부 수동 오탐 판정, 미해결 0·시크릿 0)이다. 리뷰 원문·대상 해시·확인 출처는 [`PHASE_B_CODE_REVIEW.md`](docs/reports/name_grid_2026-10-23/PHASE_B_CODE_REVIEW.md)에 있다. 문서 마감 워커의 서버에는 `.git`가 없어 직접 Git 검증은 하지 않았다. 위 Phase A의 리뷰·커밋 대기는 당시 이력이다.
- 원본 ROM·폰트 복구 완료. RE·계획 승인·QA 정본은 `docs/reports/name_grid_2026-10-23/PHASE_B_RE.md`·`PHASE_B_PLAN_APPROVAL.md`·`PHASE_B_QA.md`, 증거 색인은 `evidence/INDEX.md`다.
- 리뷰 판정: 쓰기는 `tools/build_korean_full.py`의 `NAME_COMPOSE_WRITES` 10영역 + A3 표 end 리터럴 4곳뿐이다. 후보−baseline diff가 그 밖이면 결함이다. native 공유 선택표 `0x83FAF6`·표시표 `0x83FE40`·행 포인터 `0x34AC24..38`·공유 A3 가나 그림은 원형 유지(바꾸면 mode0 navigation·2편 대사 대시가 깨진다). 훅은 S1/S2/S3/D1 바이트 4곳 + P1 포인터 1곳(원본 expect 대조)뿐이고, 객체 0x80·tail `+70..+7F` ABI는 `PHASE_B_RE.md` §4를 따른다.
- 계약: 최대 8자·글자당 2바이트, 2350 밖 중간 후보는 원자 거부(대체 금지), 9번째는 `no_slot`(native의 8번째 덮어쓰기 금지), 지우기는 자모부터, 미완성 확인·공백 거부, `가카`는 확인→No 복귀로 확정한다. 2350 중 뢨·썅·쏀·쓩·쭁 5음절은 일반 키열로 도달할 수 없다(알려진 한계).
- 자모 40코드 `data/jamo_to_code_40.json`·글리프 `data/jamo_glyphs_40.bin`이 정본이다(`python3 tools/gen_jamo_assets.py --check`). `tools/part2_name_compose_blob.py`는 생성물이라 소스를 바꾸면 `python3 tools/name_compose/build_image.py`로 다시 만들고 `--check`가 일치해야 한다. 일반 빌드는 컴파일러가 필요 없다.
- 후보 `output/game_wars_korean_namecompose_20261023.gba`(`1ac790a9…e1eb`)는 `--out … --no-sync-outputs` 별도 산출물이다. full/final/title_test 동기화와 b44/dist 재배포는 범위 밖이고 정본은 여전히 b44다. 실기 미검증, Link BLOCKED.
