# AGENTS.md — Game Wars 한글화 프로젝트 (codex/gemini 공용 컨텍스트)

> 이 파일은 `codex exec` / `gemini` 리뷰 세션이 프로젝트 규칙·사실을 읽도록 두는
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

## 리뷰어에게 (codex / gemini)
- 톤: **엄격·비판적**. 결함·누락·근거 부족·대안을 적극 지적한다. 통과시키려 하지 말 것.
- 특히 **"꼼수"(fragile hack)** 여부를 본다: 고정주소 raw OBJ 덮어쓰기, LZ77 in-place 재압축,
  ASCII 테이블 blank, 전각→반각 padding 글리프, 폭 맞추기용 텍스트 축약(의미 손상),
  KANA_REMAP, 예약코드 재사용 — 이들이 실제로 안전한지, 더 견고한 해법이 있는지 따진다.
- 근거 없는 "깨끗하다" 결론을 경계한다. QA 도구의 green check가 **실제 화면**을 보장하는지 의심한다.

## 작업 디렉토리 규칙
- 임시물은 전부 `temp/`. `/tmp/` 및 루트 직접 생성 금지. 백업은 git으로(`*.bak` 만들지 않음).
