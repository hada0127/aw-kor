# T3 빌더 통합 — 진행 보고 (PLAN-v5 T3)

상태: **완료** (전체 ROM 빌드·커밋·push 안 함 — T4 범위)

- 계획 `PLAN-v5.md` sha256 `60a7574a957e5277ac8bbb826ad3bee54c39362907fd30864cc26c47809521b4`(재계산 일치), `PLAN-REVIEW-v5.md` `CONTEXT: match` · `AUTHOR: fable` · `VERDICT: APPROVE` 확인.
- 수행 주체: `ROUTING_UPDATE.md`(사용자 「이 pc 하네스대로」) → 로컬 Claude(Orca task_d591699ea0d7 / ctx_7b741ad5ee17), risk high.
- 기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`, branch `sweep3-p2-20261023c`. 시작 시 tracked 변경 0, untracked = T1·T2 산출물 7개.

## 시작 시 해시 (보호·입력)

| 파일 | SHA-256 |
|---|---|
| `tools/build_korean_full.py` (수정 전, HEAD) | `72739138ae3687c43284479eef16636d1cd23ee0d383b5a891dd27356b56a90d` |
| `tools/part2_name_compose_blob.py` (T2, 읽기만) | `3313d3d8672e5868b1af95f0ebfbaeb2cb6a1f88b43f0febabc3b5eb368a3c16` |
| `tools/gen_jamo_assets.py` (T1 fix1, 읽기만) | `e7a36dbfb00d5d48ec40a5ab078490d03d31c722ec6c91de914c13d0531927e3` |
| `data/jamo_to_code_40.json` | `628404ed7bbb567872108431f30c76fd8824acebbe3049ac4031923eeda2b7e9` |
| `data/jamo_glyphs_40.bin` | `1417db5cb058782f3cd3f133cead8da711de47e3185bbfaf900ad8841f7c4980` |
| 원본 ROM | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |
| `output/game_wars_korean_namegrid_baseline_20261023.gba` | `ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a` |
| `output/game_wars_korean_b44_reference_20261023.gba` | `1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02` |

`output/game_wars_korean_{full,final,title_test}.gba`는 이 체크아웃에 없음.

## 사전 확인 (원본·baseline 실측)

훅 사이트(S1 34B0BC/10, S2 34B084/8, S3 34B20E/10, D1 34AB3C/8, P1 83FD58/4)와 불변 포인터(FD78 `fda93408`, FDE0 `41b43408`, FD28 `55b43408`), dispatch AFAE·B2C8·B338·B3C0·B470 바이트가 원본 = baseline = 계획 expect. baseline A3: min 0x8840, max 0xE2A7, start 0x08F20000, end 0x08F243A4, mask 0x7FFF, end 리터럴 EFE974/314000/B11E28 = 0x08F243A4. baseline의 F243A4..F24494·F70000..F77800·F09F60..F0A960 전부 0.

## 계획 공백 → 총괄 승인 범위 확장 (escalation msg_1fb1cd76b0fb → 답 msg_b729bf9d6961)

`tools/part2_native_controls.py` `PATCH_REGIONS['a3_glyph_hook']`(0xF30280..0xF30340)이 sha `ed6ef698…` 하나만 받는다. 이 영역에 F30304(max)·F3030C(end)가 들어 있어, 계획 §1.7대로 바꾸면 실제 빌드 안의 `NativeProfile(rom)`(빌더 `reflow_sea_fortress_prompt`, `part2_context_contract` 등)이 `NativeConsumerError`로 실패한다. baseline에 두 값만 바꾼 sha = `a36e078dc12a77facf3d6b130b7375e071622678180577105713345b499b9cd2`.
총괄 답: `tools/part2_native_controls.py`·`tools/test_part2_native_controls.py` 추가 소유 허가. 옛 리뷰 바이트와 「max=E352·end=08F24494 두 리터럴만 다른 새 바이트」 정확히 두 SHA만 허용, 다른 fixture 자동 변경 금지.

## 변경 파일

| 파일 | 상태 | SHA-256(최종) |
|---|---|---|
| `tools/build_korean_full.py` | M (+214/−5) | `be43e4ab0de0b519e4883d6e7b6329f3385bf649cce2f1ecfd6a20e315093229` |
| `tools/test_part2_name_compose_build.py` | N | `ce00d1a6351799d964f2f4ccf2168739b54e733360de01361bfc6b3e71a8dd20` |
| `tools/part2_native_controls.py` (총괄 승인 추가 범위) | M (+7/−1) | `88a6d8a2712552cce38f254dfc330aeaa65cdb566b06534678b433c784fdf61f` (전 `91b1f41f…1ddd`) |
| `tools/test_part2_native_controls.py` (총괄 승인 추가 범위) | M (+18) | `faf421d2887f22eb23d7743d8eeb2e8731620bda1a4bf16de2b28f7ff85ad1bd` (전 `44c4f1f9…9827`) |

tracked diff 전체: `tracked.diff`(sha `5c461dbc…1b76`). 새 테스트 사본: `test_part2_name_compose_build.py.snapshot`.

## 구현 (build_korean_full.py)

- `DENY_REGIONS`에 `('part2_name_compose', 0xF70000, 0xF77800)` (korean_data 앞 — 이름이 좁게 잡힘).
- 상수(단일 정본): `NAME_COMPOSE_WRITES`(반열린 10영역: jamo_tiles F09F60..F0A960 · nc_dense F70000..F75748 · nc_image F75800..F77800 · a3_table_tail F243A4..F24494 · a3_max F30304..F30308 · S1 34B0BC/10 · S2 34B084/8 · S3 34B20E/10 · D1 34AB3C/8 · P1 83FD58/4), `NAME_COMPOSE_REGIONS`(이름→범위 조회), `NAME_COMPOSE_END_LITERALS`(EFE974·F3030C·314000·B11E28, 모듈 로드 시 P.LIT_TBL_END·A3+0x8C·PART2_PATCHES 와 같음을 assert), `NAME_COMPOSE_SITES`(원본 expect), `NAME_COMPOSE_KEEP`(FD78/FDE0/FD28), `PART2_HOOK_A3_MAX_OFF=0x84`(+ PART2_HOOK_A3 의 min/max/mask 위치 assert), `NAME_COMPOSE_TABLE_ENTRIES=(536,2350,40)`.
- `_name_compose_inputs(orig, syl_to_code)`: `load_jamo_codes` → 2350 비중복 → **원본 `extend_pool` 소속(매 빌드)** → 로드한 JSON SHA == blob `SOURCE_SHA['data/jamo_to_code_40.json']` → `verify_code()` → `check_sources()` 빈 목록 → IMAGE_RT/DENSE_RT/DENSE_BYTES·크기 ≤ 8,192. 컴파일러 불필요(0.11s 실측). 전역 캐시 없음.
- `_name_compose_a3_max(rom, syl_to_code, orig)` — 기존 `:14400` 상수 가드 자리: hook 영역 전체가 막 기록된 `PART2_HOOK_A3`(max E2A7·end 0·min·mask)와 같을 때만 `max(2350 ∪ 자모)`=**0xE352** 기록, 기록된 rom 값을 다시 읽어 모든 코드 이상인지 확인. 상수 PART2_HOOK_A3 만 읽던 옛 가드는 지움.
- `_name_compose_table_tail(rom, new_tbl, orig_tbl, sylmap, syl_to_code, orig)` — `_assert_relocated_korean_indices` 뒤·표 기록 앞: new_tbl == 원본 536 + 2350(sylmap 정렬, 자 top 1274) 정확 일치, tail 자리 F243A4 == 표 끝·영역 0 확인 뒤 240B 반환(new_tbl·rom 불변). 기존 end 리터럴 4곳 코드가 늘어난 길이(0x08F24494)를 그대로 씀.
- `_part2_name_compose(rom, orig)` — 체크섬 직전(`shift_dialogue_wait_cursor_right` 앞, 모든 writer 뒤) 1줄 호출(`st['part2_name_compose'] = …`). 사전조건 전부 모은 뒤 하나라도 있으면 ValueError·rom 불변: 앞 단계(A3 max·표 tail·min/mask/start·end 4곳·KEEP) 일치, 5 사이트 orig==expect **and** 현재==expect, KEEP orig, jamo_tiles 0, F70000..F77800(틈 F75748..F75800 포함) 0, tile 1273 0·1274 비영. 그 뒤 8영역 기록 → `_verify_part2_name_compose` 최종 대조(전 10영역 정확 일치 + A3 min/mask/start + end 4곳 + KEEP) 결과 dict 반환. WRITE_LOG 에는 넣지 않음.
- 사이트 바이트(계획 §1.5): S1 `00480047`+entry+`c046`, S2 `00480047`+entry, S3 `01480047c046`+entry(리터럴 0x34B214 4정렬), D1 `004b1847`+entry, P1 entry. entry = `blob.entry()`(IMAGE_RT+SYMBOLS|1).

## part2_native_controls.py (승인 범위)

`PATCH_REGION_VERSIONS = {'a3_glyph_hook': ('a36e078d…9cd2',)}` 추가, `verify_patch_connections` 는 `sha256`(옛 리뷰 바이트) 또는 이 목록의 정확한 SHA 만 허용. 다른 영역·정규화 없음. 새 테스트 `test_name_compose_a3_hook_version_is_exact`: 옛 HOOK_FIXTURE 에서 +0x84/+0x8C 만 바꿔 SHA 가 상수와 같음, 옛·새 둘 다 NativeProfile 통과(연결 SHA 값 확인), max 만/ end 만 바꾼 혼합·새 바이트의 opcode(0x00)·page 리터럴(0x7C)·max(0x84,0x85)·end(0x8C,0x8E)·mask(0x90)·끝(0xBF) 1비트 변조 전부 거부. 기존 HOOK_FIXTURE·다른 fixture 무변경. T3 fixture 후보에 `NativeProfile` 실행 → a3 `a36e078d…`, baseline → `ed6ef698…` (`native_profile_check.log`).

## 테스트 (`tools/test_part2_name_compose_build.py`, 16개)

fixture: 원본(SHA 고정) + baseline ROM(SHA 고정, 없으면 skip). baseline 의 A3 end 를 0 으로 되돌려 hook 기록 직후 상태(= PART2_HOOK_A3 정확 일치를 assert)를 만들고, 빌더 순서대로 a3_max → 표 tail(baseline 의 2886 표) → 표 기록·end 4곳(빌더 줄 재현) → `_part2_name_compose`. ignored 연구 JSON 미사용.
- 정상: 후보−baseline diff ⊆ WRITES ∪ end 4곳; 10영역마다 테스트가 따로 만든 기대 바이트와 정확 일치(사이트 인코딩 직접 hex)·5 사이트 실제 변경; 사이트 리터럴 4정렬·Thumb bit·함수 심볼 지시; A3 min 8840·max E352(≥ 모든 코드)·start·mask 7FFF·end 4곳 0x08F24494; 표 prefix(원본 536·baseline 2886) 불변 + 자모 40 엔트리(코드 BE, 1275+2i/1276+2i|0x8000); 공유 선택표·표시표·row 리터럴 AC24..AC38·FONT_BASE 가나·2350 글리프·tile 1273 blank/1274 private 자·KEEP·dispatch AFAE·A3 트램펄린 불변; 분류 90셀(원본 동작 셀은 원본 코드 그대로, 나머지 첫 바이트 ∉ {31,32,62,63,65}); 사설 표시행 6개 길이·`09…00` 형식·자모/공백 셀 == 선택표, 숫자·문장부호·legacy 814A/814B·간격 쌍 == 원본; DENY 이름·영역 비중첩.
- 거부·원자성(rom 바이트 불변까지 확인): 사이트 5개 orig 1바이트 변조·현재 rom 변조, KEEP 변조, 점유 영역 8곳(F09F60·F0A95F·F70000·F75747·틈 F75750·F75800·F777FF·tile1273), 앞 단계 누락(max E2A7·tail 0·end 옛값·mask), 두 번 적용; 최종 검증 1바이트 변조 14곳; A3 단계 opcode·min·max 2바이트·end·mask 변조와 이미 넓힌 상태 재적용; 표 단계 표 바이트 4곳·짧은 표·원본 표 변조·자 top 119·tail 영역 점유(new_tbl 도 불변); 입력 변조 — SOURCE_SHA·CODE_SHA·8,193B 이미지·JSON(두 코드 교환=컴파일본과 불일치/풀 밖 0x887F/2350 겹침)에서 세 단계 모두 ValueError·불변, 잉크 없는 글리프 bin 거부.
- 변이 검사(임시 사본, 정리 완료) 11종 전부 검출: 사이트 가드 제거·비원자 기록·A3 생성단계 가드 제거·표 대조 제거·D1 레지스터 오인코딩·틈 0 검사 누락·풀 검사 제거·JSON SHA 검사 제거·end 리터럴 검사 제거·native 아무 SHA 허용·max 미기록 (`mutation.log`, `mutation_logs/`).

## 실행한 명령과 결과 (원문 로그: 이 폴더)

환경: `TMPDIR=temp/name-grid-phaseB/t3-builder/tmp`(끝나고 비어 삭제), `PYTHONDONTWRITEBYTECODE=1`, `-B`. dialogue_script_safety 는 `AW_FONT_DIR=temp/name-grid-phaseB/fonts`, `AW_HADASANS_FONT`/`AW_HADASANS_BLACK_FONT`=`~/project/hada-font/.../otf/HadaSans-{Bold,Black}.otf`(T4 브리프와 같은 값). 기존 테스트들은 `-I`면 스크립트 폴더가 sys.path 에 없어 import 실패하므로 `-B` 로 실행(새 테스트는 `-I` 도 통과).

| 명령 | 결과 | 로그 |
|---|---|---|
| `python3 -B tools/test_part2_name_compose_build.py -v` | Ran 16 OK, EXIT 0 | `test_part2_name_compose_build.log` |
| `python3 -I tools/test_part2_name_compose_build.py` | OK, EXIT 0 | `…isolated.log` |
| `python3 -B tools/test_part2_native_controls.py -v` | Ran 9 OK, EXIT 0 (`:146` F70000 반전 fixture 포함 통과) | `test_part2_native_controls.log` |
| `python3 -B tools/test_dialogue_script_safety.py -v` (폰트 env) | Ran 94 OK, EXIT 0 | `test_dialogue_script_safety.log` |
| `AW_TEST_ROM=<baseline> python3 -B -m unittest test_part1_yesno_row -v` (tools/) | Ran 2 OK(live 포함), EXIT 0 | `test_part1_yesno_row.log` |
| `python3 -B tools/test_part1_yesno_row.py <baseline>` / `<T3 fixture 후보>` | PASS, EXIT 0 / 0 (후보 파일은 검사 후 삭제, sha `1ac790a9…e1eb`) | 같은 로그 |
| `test_jamo_assets` / `test_name_compose_core` (T1·T2 회귀) | 15 OK / 12 OK, EXIT 0 | 각 로그 |
| `test_part2_dialogue_layout_contracts` / `test_part2_volcano_context` (HOOK_FIXTURE 사용처) | 7 OK / 6 OK, EXIT 0 | 각 로그 |
| `test_part2_context_contract` / `test_qa_part2_physical_rows` | EXIT 1 / 1 — **HEAD 코드(git archive 사본)에서도 같은 실패**(`data/dialogue_map.json` 없음 · `native_title_unverified_pointers 0 != 58`), 이번 변경과 무관 | `*.log`, `*.HEAD.log` |

## 보호·불변 (끝난 뒤 재계산)

원본 `a8ad7c7d…831c` · baseline `ebbca0ba…a8a` · b44 `1ac68443…6f02` · `data/syllable_to_code_2350.json` `7f4f3202…548f` · `syllable_to_glyph_2350.json` `c906d3b5…d0b4` · `kor_glyphs_2350.bin` `b92bba2f…7eb9` · T1/T2 산출물(blob `3313d3d8…3c16`, gen_jamo `e7a36dbf…27e3`, JSON `628404ed…b7e9`, bin `1417db5c…4980`) 전부 시작과 같음. `dist/` git diff 없음. output full/final/title_test 파일 없음(안 만듦). 전체 ROM 빌드·에뮬레이터·커밋·stage 안 함. `__pycache__` 새로 안 생김.

## 계획 대비 어긋난 점

1. 함수 수: 계획 「`_part2_name_compose` 1함수 + A3 max·table append 인라인」 대신 테스트 가능한 헬퍼로 나눔 — `_name_compose_inputs`·`_name_compose_a3_max`·`_name_compose_table_tail`·`_name_compose_payload`·`_name_compose_expected`·`_name_compose_mismatches`·`_verify_part2_name_compose`. 호출 위치는 계획과 같음(`:14400` 가드 자리 1줄, `_assert_relocated_korean_indices` 뒤 1줄, 체크섬 직전 1줄). 전역 가변 상태 없음.
2. `_part2_name_compose` 호출 위치를 「모든 writer 뒤·체크섬 직전」으로 잡음(계획은 위치 미지정). 뒤에 덮어쓸 writer 가 없고 zero 가드가 최종 상태를 본다.
3. 추가 가드(계획보다 엄격): 로드한 자모 JSON SHA == blob SOURCE_SHA, KEEP 포인터 3개 orig/현재, tile 1273 0·1274 비영, 최종 payload 대조를 빌드 안에서도 실행.
4. **추가 소유 2파일**(`part2_native_controls.py`·그 테스트) — 계획 공백, 총괄 승인(msg_b729bf9d6961).
5. `test_part1_yesno_row.py` 는 ROM 인자가 필요한 검사기라 baseline 과 T3 fixture 후보로 실행(완성 후보 ROM 은 T4).

## 남은 위험 (unverified)

- 실제 전체 빌드에서의 통합(다른 writer 와의 충돌, 체크섬, integrity_map·qa 5관문)은 아직 안 돌렸다 → T4. T4 시 `part2_native_controls` 새 SHA 가 빌드 안 NativeProfile 호출에서 통과하는지가 첫 확인 대상(fixture 후보에선 통과).
- 훅·트램펄린 실행 동작(레지스터/스택, D1 렌더, nc_alloc)은 정적 대조만 — T5.
- 테스트는 ignored baseline ROM 이 있어야 돈다(없으면 skip). 다른 머신에서 skip 이면 검증이 빠진다.
- `test_part2_context_contract`·`test_qa_part2_physical_rows` 기존 실패 2건은 이번 범위 밖 — 따로 봐야 함.

## 후속 반영

문서(AGENTS/CLAUDE/todo, docs/reports)는 T6 소유라 안 건드림. T6 에 넘길 사실: `NAME_COMPOSE_WRITES` 정본 위치·10영역, A3 max 0xE352·표 end 0x08F24494, `part2_native_controls.PATCH_REGION_VERSIONS` 새 SHA, 테스트 명령.

정리: 띄운 프로세스·워크트리·claim·브라우저 없음. 임시 사본(HEAD 사본·변이 사본·fixture 후보 ROM)·TMPDIR 삭제. 이 폴더는 증거로 보존.

RECEIPT: model=claude-opus-5-5 effort=high role=code
