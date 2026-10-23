# T1 자모 자산 — 결과 보고 (PLAN-v5 T1)

- 계획: `temp/name-grid-phaseB/PLAN-v5.md` sha256 `60a7574a957e5277ac8bbb826ad3bee54c39362907fd30864cc26c47809521b4` (재계산 일치)
- 검토 판정: `PLAN-REVIEW-v5.md` — `CONTEXT: match` · `AUTHOR: fable` · `VERDICT: APPROVE sha256=60a7574a…09521b4` 확인 후 시작
- 수행 주체: `ROUTING_UPDATE.md`(사용자 「이 pc 하네스대로」) → 라우터 code=claude, 로컬 Claude 구현
- 기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`, branch `sweep3-p2-20261023c`. 커밋·스테이지·push 안 함.
- 환경: Python 3.9.6, Pillow 11.3.0. 실행 시 `TMPDIR=temp/name-grid-phaseB/t1-assets/tmp`(종료 후 빈 디렉터리 삭제), `PYTHONDONTWRITEBYTECODE=1`. `__pycache__` 생성 없음 확인.

## 변경 파일 (전부 신규, untracked)

| 파일 | SHA-256 | 크기 |
|---|---|---|
| `data/jamo_to_code_40.json` | `628404ed7bbb567872108431f30c76fd8824acebbe3049ac4031923eeda2b7e9` | 683B |
| `data/jamo_glyphs_40.bin` | `1417db5cb058782f3cd3f133cead8da711de47e3185bbfaf900ad8841f7c4980` | 2,560B |
| `tools/gen_jamo_assets.py` | `cea26186de57ef5878668586817f8645b86239302bfe2cdef9ea4d4793604f54` | |
| `tools/test_jamo_assets.py` | `eab2fb18c6414dcfe47fb565bc7b8e782e0cdc631b9f2bb1cb03780fda4193be` | |

파생값(저장 안 함, 함수 출력): `dense_table(2350)` 22,344B sha `ba9b674aea9be6a84c7f3587864905385d75f09045b4281ee9fab98be2dc2a4b` · `jamo_table_entries` 240B sha `51fa18ea9cc5615e37f348a0ffd8fbdbd9563482da19e28af3767e16e75b3f6a`.

## 코드표 (PREVIEW_JAMO = L_LIST + V_LIST 순)

ㄱE2A8 ㄲE2AB ㄴE2AD ㄷE2AE ㄸE2AF ㄹE2B0 ㅁE2B1 ㅂE2B2 ㅃE2B8 ㅅE2B9 ㅆE2BD ㅇE2BE ㅈE2BF ㅉE2C3 ㅊE2C4 ㅋE2C5 ㅌE2C6 ㅍE2CA ㅎE2CB · ㅏE2CC ㅐE2EE ㅑE2F4 ㅒE2F6 ㅓE2FC ㅔE341 ㅕE343 ㅖE344 ㅗE345 ㅘE346 ㅙE347 ㅚE348 ㅛE349 ㅜE34A ㅝE34B ㅞE34C ㅟE34D ㅠE34E ㅡE34F ㅢE351 ㅣE352

첫 4개 E2A8/E2AB/E2AD/E2AE는 계획 §1.7 기재값과 일치. 테스트가 풀을 오름차순으로 따로 훑어 「2350에 없는 첫 40개」와 같음을 확인했다.

## API (계획 §3)

- `load_jamo_codes() -> dict[str,int]` — JSON 읽고 순서=PREVIEW_JAMO·40개·중복 0·2350 미중복·lead∈[0x88,0xEA]·trail≥0x40 검증(위반 `ValueError`).
- `jamo_tiles() -> bytes` — bin 읽고 2,560B·40쌍 ink>0 검증.
- `dense_table(syl_to_code) -> bytes` — `(L*21+V)*28+T` 위치에 u16 LE 코드, 없음 0, 22,344B.
- `jamo_table_entries(sylmap, codes) -> bytes` — 엔트리 i = `code BE, (1275+2i)|0x8000 LE, (1276+2i)|0x8000 LE`, 240B. 기존 음절 타일 최대값이 1273(빈 타일)·1274(사설 자)에 닿으면 `ValueError`(현재 최대 1272).
- 내부: `select_jamo_codes(rom, syl_to_code)`(extend_pool − 2350 정렬 첫 40), `render_jamo_tiles()`(render_char 기본 ink 9, 폰트 상대경로 때문에 ROOT로 잠시 chdir), `generate()`(원본 SHA `a8ad7c7d…2413831c` 가드).
- CLI: `python3 tools/gen_jamo_assets.py`(두 자산 기록) · `--check`(재생성 바이트 대조만, 불일치 exit 1).

## 실행한 명령과 결과 (원문 로그: 같은 디렉터리 `gen.log`·`test.log`·`check.log`·`hangul_compose_regress.log`)

| 명령 | 결과 |
|---|---|
| `python3 -I tools/gen_jamo_assets.py` | `wrote data/jamo_to_code_40.json (683B), data/jamo_glyphs_40.bin (2560B)` exit=0 |
| `python3 -I tools/test_jamo_assets.py` (최종) | `Ran 14 tests … OK` exit=0 |
| `python3 -I tools/gen_jamo_assets.py --check` (최종) | `OK jamo assets byte-identical` exit=0 |
| `python3 -I tools/test_hangul_compose.py` (회귀 확인, 무변경 파일) | exit=0, reached=2345 |

생성 후 파일 핸들 ResourceWarning 정리(`_read_bytes`/`_read_json`)만 고쳤고, 그 뒤 테스트·check를 다시 돌려 위 최종 결과를 얻었다. 자산 바이트는 수정 전후 동일(고정 SHA 테스트 통과).

## 완료 기준 대조 (계획 T1)

| 기준 | 테스트 | 결과 |
|---|---|---|
| 40개·중복 0·2350 미중복·풀 소속·lead/trail 범위 | `JamoCodes.*` | PASS |
| bin SHA 고정 + 40쌍 ink>0 | `JamoGlyphs.test_size_sha_ink` | PASS |
| dense: 2350 코드 정확히 2,350개 비영, 각 위치 코드 일치 | `DenseTable.test_size_and_exact_codes` | PASS |
| `갣`·`뢔 쌰 쎼 쓔 쬬` 자리 0 (2350 밖임도 확인) | `DenseTable.test_missing_are_zero` | PASS |
| 재실행 byte-identical | `test_regeneration_byte_identical`·`test_matches_render`·`--check` | PASS |
| 완료 명령 `python3 -I tools/test_jamo_assets.py` exit 0 | | PASS |

원본 ROM이 없는 환경에서는 풀 소속·재생성 테스트 2개가 skip된다(이번 실행은 ROM 있음, skip 0).

## 보호 파일 (읽기만, 변경 없음)

- `git diff --stat` 빈 출력(tracked 변경 0). temp 밖 untracked는 위 4파일뿐.
- 원본 ROM `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- `data/syllable_to_code_2350.json` `7f4f3202…26548f` · `data/kor_glyphs_2350.bin` `b92bba2f…d67eb9` · `data/syllable_to_glyph_2350.json` `c906d3b5…40d0b4` (모두 HEAD와 동일 — git diff 0)
- 읽은 입력 SHA: `tools/hangul_compose.py` `7f442ca1ceb1cd6b98ca04135e9e0f6636747972dde63462fc95619fe65cb2d4`, `tools/build_korean2350.py` `3af6adc4b17ba5b7a50864774213d265c8f6b4577a24197fb85fbe8856f335c6`, `tools/render_galmuri_8x16.py` `850adc40f9d6aa55372da02ef749a1b8f3f1af33813bf135111b3652fc95c68d`, `tools/bdf.py` `20babb52e49054063986e2deaf0b9dc29d3c3a61a906fb69a4809773ba50de30`, `reference/fonts/Galmuri11-Condensed.bdf` `5c19d39413241e272810e115ee810feaea6c4b5684bfa3e17a98ef1cb3a7df63`, `data/game_wars_found_texts.csv` `41cb0adb19f03817bc63c036588e176c84e85ce8ff19677824571c957307a3f5`
- `output/game_wars_korean_{full,final,title_test}.gba`: 이 체크아웃에 파일 없음(건드리지 않음). dist/b44/baseline: 접근·쓰기 없음.
- ROM 빌드·에뮬레이터 실행 안 함.

## 계획 대비 어긋난 점

- 없음(설계·범위). 추가한 것은 계획에 명시되지 않은 작은 보조뿐: `generate()`의 원본 SHA 가드(잘못된 ROM에서 코드가 조용히 바뀌는 것 방지), `jamo_table_entries`의 예약 타일 충돌 가드, `--check` CLI.
- 글리프는 계획대로 `render_char` 기본값(ink 9)이다. 자모 모양(예: ㅘ가 7px 폭에 맞춰 좁음)의 화면 적합성은 육안 미검수 — T5 케이스 1 VRAM 대조·preview에서 확인 대상 (unverified).

## 후속 반영

- 문서(AGENTS/CLAUDE/todo, `docs/reports/…`)는 T6 소유라 지금 수정 안 함. T6에 넘길 사실: 자모 JSON/bin 정본 경로, 재생성 명령 `python3 tools/gen_jamo_assets.py`(검증 `--check`), 위 SHA·코드표.
- T2(`gen_tables.py`)·T3(빌더)는 `load_jamo_codes()`·`jamo_tiles()`·`dense_table()`·`jamo_table_entries()`를 쓰면 된다. 코드/글리프를 바꾸면 `test_jamo_assets.py`의 고정 SHA 2개도 같이 갱신해야 한다.

RECEIPT: model=claude-opus-5-5 effort=unknown role=code

## fix1 (2026-10-23) — 실제 빌더 호출 호환

- **원인**: `jamo_table_entries`의 가드가 `max_tile >= FIRST_TILE - 2`(1273)였다. 실제 빌더는 `tools/build_korean_full.py:14317` `_private_ja = 1274` → `:14395` `sylmap['자']['top'] = _private_ja` 뒤에 테이블 엔트리를 붙이므로, 넘어오는 sylmap의 최대 타일이 1274라 정상 호출이 `ValueError`로 실패한다. 원래 테스트는 미패치 sylmap(최대 1272)만 넣어서 이걸 못 잡았다.
- **수정**: 가드를 `max_tile >= FIRST_TILE`(1275)로 좁혔다. 1273(기존 빈 타일)·1274(사설 자 top)는 허용, 1275 이상 자모 영역 충돌만 거부.
- **테스트**: 1273 거부 검사(구 계약)를 지우고 `test_accepts_builder_private_ja`(자 top=1274 패치 sylmap 성공, 출력이 미패치와 바이트 동일)·`test_rejects_jamo_tile_collision`(1275·1354 거부)을 넣었다.
- **결과**: `python3 -I tools/test_jamo_assets.py` → `Ran 15 tests … OK` exit=0 (`fix1_test.log`) · `python3 -I tools/gen_jamo_assets.py --check` → `OK jamo assets byte-identical` exit=0 (`fix1_check.log`).
- **source SHA**: `gen_jamo_assets.py` `cea26186…f54` → `e7a36dbf…27e3`, `test_jamo_assets.py` `eab2fb18…93be` → `434e148b…bee8` (전체 값 `fix1.log`). 자산 JSON `628404ed…b7e9`·bin `1417db5c…4980` 전후 동일.
- **한계**: 가드는 sylmap 쪽 타일 번호만 본다 — 1273/1274 자리에 실제로 무엇이 쓰였는지(빈 타일·사설 자 글리프)는 빌더 책임이고 여기선 검사하지 않는다. 빌더 실제 호출 경로로 돌려 본 것은 아니다(빌더 실행 금지 범위) — 테스트는 빌더의 패치 동작(자 top=1274)을 재현한 sylmap으로 확인했다. 실제 통합은 T3에서 확인 (unverified).
- 기존 로그(`gen.log`·`test.log`·`check.log`·`hangul_compose_regress.log`)는 그대로 보존.

RECEIPT(fix1): model=claude-opus-5-5 effort=high role=code
