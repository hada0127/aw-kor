# Phase B QA — 2편 맵 에디터 이름 입력 두벌식 조합

작성 2026-10-23. 승인 계획 `PLAN-v5.md` sha `60a7574a…21b4`([`PHASE_B_PLAN_APPROVAL.md`](PHASE_B_PLAN_APPROVAL.md)). RE 근거는 [`PHASE_B_RE.md`](PHASE_B_RE.md)다. 아래 링크의 증거는 [`evidence/`](evidence/)에 temp 원본과 바이트 동일하게 복사했다. 출처 경로·SHA·크기는 [`evidence/INDEX.md`](evidence/INDEX.md)·[`evidence/index.json`](evidence/index.json)에 있다. ROM·카트리지 세이브·savestate는 커밋하지 않고 SHA만 적는다.

**상태: T1~T5의 최종 채택 실행은 전부 exit 0, T5 15개 케이스 PASS(케이스 13은 T7-FIX1 정정 실행 기준, §4).** 첫 실패·재시도 이력(text-fit 첫 EXIT 3, T5 `cases.py` 묶음·`case15.py analyze`·하네스 빌드의 첫 exit 1 등)은 §3·§4와 각 보고서에 그대로 남겼다. 실기(GBA 하드웨어)는 미검증이고 Link는 BLOCKED다. 최종 Astra 코드 리뷰·secret-scan·커밋·main 병합은 **pending**이다(PLAN §4.5 T7, 총괄 진행).

## 1. 대상 식별

| 대상 | SHA-256 |
|---|---|
| 원본 ROM | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |
| baseline(같은 소스, 조합기 없음) `output/game_wars_korean_namegrid_baseline_20261023.gba` | `ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a` |
| b44 참조 `output/game_wars_korean_b44_reference_20261023.gba` | `1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02` |
| **후보** `output/game_wars_korean_namecompose_20261023.gba` | **`1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb`** |
| 같은 빌드 `temp/integrity_map.json` / `repoint_manifest.json` / `encode_report.csv` | `eb0da58c…b025` / `a7cf6fc1…53ee` / `9bb62710…dee7` (baseline RETRY1과 바이트 동일) |
| 빌드 입력 snapshot manifest(3,206 파일) | `e6c9fcf8b8b53c6abd68c8cbc73da24fab149bf4ed13424c3fd5e42f38e21b66` — [`t4/snapshot_manifest.json`](evidence/t4/snapshot_manifest.json) |
| blob `CODE_SHA`(2,739B) | `8dd9460864ad3b0f9703ce12c80667323935b8055f9c8966e6aa023fae6c3b2f` |

기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a` + 미커밋 입력 15개. 후보는 baseline과 b44 둘 다 아니다(새 ignored 파일). `output/game_wars_korean_{full,final,title_test}.gba`는 이 체크아웃에 없고, 새 후보를 거기에 동기화하지 않았다(`--no-sync-outputs`). `dist/`·b44는 바꾸지 않았고 재배포하지 않았다.

blob `SOURCE_SHA`: `core.c` `aa99b4ca…9a01`, `tramp.s` `6c30f451…2f9d`, `image.ld` `40ce99f4…2a5e`, `gen_tables.py` `112dcdaa…78a4`, `build_image.py` `bec403f8…10a1c9`, `hangul_compose.py` `7f442ca1…b2d4`, `data/jamo_to_code_40.json` `628404ed…b7e9`, 생성 `tables.h` `26ceeeb9…0f9c`, `grid.inc` `d3cbcf60…bee9`.

생산 파일 SHA(T4 snapshot 입력 = T6 시점 작업트리, T6에서 다시 계산해 동일): `tools/build_korean_full.py` `be43e4ab…3229` · `tools/part2_native_controls.py` `88a6d8a2…f61f` · `tools/test_part2_native_controls.py` `faf421d2…d1bd` · `tools/part2_name_compose_blob.py` `3313d3d8…3c16` · `tools/gen_jamo_assets.py` `e7a36dbf…27e3` · `tools/test_jamo_assets.py` `434e148b…bee8` · `tools/test_name_compose_core.py` `bbe99bbc…a137` · `tools/test_part2_name_compose_build.py` `ce00d1a6…dd20` · `data/jamo_glyphs_40.bin` `1417db5c…4980`. **T7-FIX1(Astra full-v1 F3)**: 이 가운데 테스트 파일 `tools/test_part2_name_compose_build.py`만 임시 폴더를 레포 `temp/`로 고정하도록 바뀌어 `63a17421…c689`가 됐다. ROM을 만드는 코드·데이터·blob은 그대로라 후보를 다시 빌드하지 않았다. 생산·후보 불변의 독립 근거는 기존 [`sha-before.txt`](evidence/t7-fix1/sha-before.txt)·[`sha-after.txt`](evidence/t7-fix1/sha-after.txt)(테스트 파일 1행만 다름)와 [`T7-FIX1 보고서`](evidence/t7-fix1/REPORT.md)의 `validate_t7.py` 출력 기록이다. 부모 `temp/name-grid-phaseB/final-review/manifest-v2.json`도 `T4_differences`를 이 테스트 파일 1개로 기록한다. **T7-FIX2 F4 정정:** 과거 보조 비교의 RC0 성공 및 그 성공을 근거로 한 차이 범위 주장은 철회한다. 보존 [`compare_t4_snapshot.log`](evidence/t7-fix1/compare_t4_snapshot.log)는 최초 단순 비교의 `DIFFERENT`·`MISSING []`·**RC=1** 원문이다. 보존 `.py`는 이후 수정본(`DIFF_VS_T4` 등 출력)이라 이 로그와 동일 실행의 소스로 연결하지 않는다. 후속 RC0 실행은 원문 로그가 없어 `(unverified)`이며 판정 근거에서 제외한다. 원시 로그·스크립트는 수정·재실행하지 않았다. 다른 15case·F3의 실제 RC0 로그는 그대로 유효하다.

## 2. T1~T3 (자산·코어·빌더)

| 작업 | 명령 | 결과 | 원문 |
|---|---|---|---|
| T1 | `python3 -I tools/gen_jamo_assets.py` | exit 0 (JSON 683B, bin 2,560B) | [`t1/gen.log`](evidence/t1/gen.log) |
| T1 fix1 | `python3 -I tools/test_jamo_assets.py` | `Ran 15 tests … OK`, exit 0 | [`t1/fix1_test.log`](evidence/t1/fix1_test.log) |
| T1 fix1 | `python3 -I tools/gen_jamo_assets.py --check` | `OK jamo assets byte-identical`, exit 0 | [`t1/fix1_check.log`](evidence/t1/fix1_check.log) |
| T2 | `python3 -I tools/test_name_compose_core.py` | `Ran 12 tests … OK`, exit 0 — 전수 11,172: 도달 2,345·거부 8,827·지원 미도달 5 / 랜덤 20,000(seed 20261023) / 선택 90셀·표시 6행 일치 / 이미지 2,739B·relocation 0 | [`t2/test.log`](evidence/t2/test.log) |
| T2 | `python3 -I tools/name_compose/build_image.py --check --work …` | `OK blob byte-identical`, exit 0 | [`t2/blob_check.log`](evidence/t2/blob_check.log), [`t2/elf_inspect.log`](evidence/t2/elf_inspect.log) |
| T3 | `python3 -B tools/test_part2_name_compose_build.py -v` | `Ran 16 tests … OK`, exit 0 (`-I`도 OK) | [`t3/test_part2_name_compose_build.log`](evidence/t3/test_part2_name_compose_build.log) |
| T7-FIX1 | `env -u TMPDIR python3 -B tools/test_part2_name_compose_build.py -v`(F3 정정 뒤) | `Ran 16 tests … OK`, exit 0. 보조 audit hook 실행에서 `tempfile.mkdtemp` 1건이 `<repo>/temp/tmp…` 아래였다(exit 0) | [`t7-fix1/test_part2_name_compose_build.stderr.log`](evidence/t7-fix1/test_part2_name_compose_build.stderr.log), [`audit_tmp.stdout.log`](evidence/t7-fix1/audit_tmp.stdout.log) |
| T3 | `python3 -B tools/test_part2_native_controls.py -v` | `Ran 9 tests … OK`, exit 0 | [`t3/test_part2_native_controls.log`](evidence/t3/test_part2_native_controls.log) |
| T3 | `python3 -B tools/test_dialogue_script_safety.py -v`(폰트 env) | `Ran 94 tests … OK`, exit 0 | [`t3/test_dialogue_script_safety.log`](evidence/t3/test_dialogue_script_safety.log) |
| T3 | `test_part1_yesno_row` (baseline / fixture 후보) | PASS, exit 0 / 0 | [`t3/test_part1_yesno_row.log`](evidence/t3/test_part1_yesno_row.log) |
| T3 | 변이 검사 11종 | 11종 모두 테스트가 잡음 | [`t3/mutation.log`](evidence/t3/mutation.log) |

T1의 첫 가드는 빌더가 실제로 쓰는 사설 `자` 타일 1274를 막아서 정상 호출이 실패했다. fix1에서 가드를 1275 이상으로 좁혔다([`t1/REPORT.md`](evidence/t1/REPORT.md) fix1). T3는 계획에 없던 `tools/part2_native_controls.py` 수정이 필요했다. A3 hook 영역의 SHA 고정 때문에 빌드 안의 `NativeProfile`이 실패했기 때문이다. 총괄 승인을 받아 정확히 두 SHA(옛 바이트 `ed6ef698…`, max·end만 바뀐 새 바이트 `a36e078d…9cd2`)만 허용했다([`t3/REPORT.md`](evidence/t3/REPORT.md)).

기존 실패 2건 `test_part2_context_contract`(`data/dialogue_map.json` 없음)·`test_qa_part2_physical_rows`(0 vs 58)는 HEAD 사본에서도 똑같이 실패한다. 이번 변경과 무관하며 손대지 않았다([`t3/test_part2_context_contract.HEAD.log`](evidence/t3/test_part2_context_contract.HEAD.log)).

## 3. T4 후보 빌드·정적 관문

빌드 입력 snapshot(`namecompose-build/source/`, ignored)에서 1회 빌드했다. 부모 checkout은 `data/` 생성물 2개를 포함해 바뀌지 않았다.

```text
nice -n 15 python3 tools/build_korean_full.py --out output/game_wars_korean_namecompose_20261023.gba --no-sync-outputs --report temp/encode_report.csv   EXIT 0
python3 tools/phase6_basic_test.py <후보>                                                    EXIT 0  [OK] pre-flight (Checksum valid)
python3 tools/qa_integrity_map.py --rom <후보> --map temp/integrity_map.json --byte-only      EXIT 0  기대 577,856B 중 불일치 0
python3 tools/qa_text_fit.py --rom <후보> --map … --manifest …                               EXIT 0  layout-loss 152 / overflow 273 / wider 507 / protected 0/485
python3 tools/qa_bteam_drift.py --rom <후보> --map … --repoint-manifest … --json …            EXIT 0  mismatch 114 (listed 103, deferred 11, unlisted 0), drift 0
python3 tools/qa_part2_name_grid_shared_glyph.py <후보>                                       EXIT 0  dash 0x815B be419dc0…2bba
```

원문: [`t4/build.log`](evidence/t4/build.log), [`t4/gate1.log`](evidence/t4/gate1.log)~[`gate5.log`](evidence/t4/gate5.log), 러너 [`t4/run_build.py`](evidence/t4/run_build.py). 관문 exit 0은 잔여 0이 아니다. 회귀 판정은 아래 집합 비교로 했다.

| 검사 | 결과 | 증거 |
|---|---|---|
| 후보−baseline 바이트 diff | 8,156B, 전부 `NAME_COMPOSE_WRITES` 10영역 ∪ end 리터럴 4곳 안. 10영역 payload 직접 인코딩과 일치, 전부 실제 변경 | [`t4/analysis/diff_payload.json`](evidence/t4/analysis/diff_payload.json) |
| A3 자모 | 리터럴 min 8840 / max **E352** / start 08F20000 / end **08F24494** / mask 7FFF. 자모 40 전부 lookup ok, 그림 == bin. 2350 음절 결과 변화 0 | [`t4/analysis/a3_jamo.json`](evidence/t4/analysis/a3_jamo.json) |
| 공유 A3 가나 그림 | grid-map 선택∪표시∪행 코드(action marker 제외) **72개** 전부 존재, 노드 경로·64B 그림 baseline == 후보. 부재 0. 장음 815B 동일 | [`t4/analysis/shared_glyph.json`](evidence/t4/analysis/shared_glyph.json) |
| 쓰기 충돌 | F70000..F77800 교차 0. 유일한 교차는 계획이 정한 A3 max 리터럴 확장 1건. direct writer 190→192(추가 2건 모두 이번 함수) | [`t4/analysis/writer_crosscheck.json`](evidence/t4/analysis/writer_crosscheck.json) |
| B팀 | (주소, cause, decision) 집합 baseline 114 == 후보 114, new 0 / gone 0, 레코드 전체 동일. decision DEFER 11 / ALIGNMENT_RESTORE 1 / RESTORE_BASELINE 97 / NEW_STRICT_MISMATCH 5(기존 분류 이름) | [`t4/analysis/bteam_diff.json`](evidence/t4/analysis/bteam_diff.json), [`t4/bteam/`](evidence/t4/bteam/) |
| text-fit | 아래 | [`t4/analysis/textfit_diff.json`](evidence/t4/analysis/textfit_diff.json) |
| 보호·불변 | 원본·baseline·b44·dist 39파일 SHA 전후 동일, 부모 HEAD·status·파일 SHA 동일, snapshot 3,206 파일 불변 | [`t4/final_check.log`](evidence/t4/final_check.log) |

**text-fit 집합 비교 — 첫 EXIT 3과 정정.** `qa_text_fit.main`의 실제 `check_text(a, ko, ja, slot_override=None)`를 `sys.settrace`로 따라가 (주소, 유형) 이벤트를 모았다(분류 로직은 복제하지 않음). 첫 시도는 **EXIT 3**이었다([`t4/trace_baseline.attempt1.log`](evidence/t4/trace_baseline.attempt1.log)). 검사기가 「고유 주소 수 = 출력 개수」를 요구했는데, overflow는 같은 주소·인자로 `check_text`가 두 번 이상 불리는 13주소(이벤트 27개, 호출 줄 376/401/433/443)가 있어서 이벤트 273개 ≠ 고유 주소 259개였다. 추적 스크립트 자신을 외부 모듈로 센 오류도 함께 있었다. 데이터는 같고 검사기만 고쳤다(빌드 반복 없음). 총괄이 판정 기준을 이렇게 정했다: **stdout과는 이벤트 수를 대조하고, 회귀는 고유 (주소, 유형) 집합 + 키별 발생 횟수 + 이벤트 전체 tuple까지 대조한다.** 정정 결과: overflow 이벤트 273 == 출력 273(키 259), wider 507 == 507(키 507), baseline vs 후보 new 0 / gone 0 / 발생 횟수 변화 0 / 이벤트 목록 전체 동일, `pass: true`. 개수만 같다고 넘어간 것이 아니다.

## 4. T5 런타임 QA (공식 mGBA 0.10.5)

- 하네스: `tools/mgba_harness.c`(`1894c25c…a96f`) 사본에 BP 출력 r8–r11 필드 4개만 추가([`t5/harness/harness.diff`](evidence/t5/harness/harness.diff)). 공식 빌드와 같은 `-D` 29개·헤더·라이브러리(`libmgba` `83744c60…960da`)로 컴파일. 소스 `86378640…1b65`, 바이너리 `0427fc40…2fd2`([`t5/harness/build.json`](evidence/t5/harness/build.json)).
- 키 입력: 매 입력 전 `[0x03004650]`→obj `+0x1E/+0x20`을 읽고 D-pad로 목표 셀까지 간 뒤 A. (0,0) 시작을 가정하지 않았다. 오라클은 스텝마다 `hangul_compose.Composer` + live adapter, 저장은 stored adapter.
- 보호: `protect.py before/after`로 469개 보호 파일(원본·output ROM/세이브·dist·연구 산출물·조합 소스/자산·공식 mGBA)의 SHA, HEAD, `git status`·`git diff` SHA가 전후 같았다([`t5/protected-before.json`](evidence/t5/protected-before.json), [`t5/protected-after.json`](evidence/t5/protected-after.json)). RAM 쓰기는 케이스 15 mode0 합성 1건뿐이고 `loadstate`는 전부 T5 소유 후보 savestate다(`verify.py` hygiene).
- 기대값은 실행 전에 [`t5/expectations.json`](evidence/t5/expectations.json)에 고정했다. 집계 [`t5/summary.json`](evidence/t5/summary.json).

| # | 판정 | 내용 | 증거 |
|---|---|---|---|
| 1 | PASS | 그리드 키로 한글 `92af888a`·강철 `884990d3`·붉은달 `8d5c8f7e89e7`, 스텝마다 live == Composer. 자모 VRAM 64B == ROM 타일 == bin(ㄱ·ㅏ, ㅘ는 케이스 2) | [`case1-강철/`](evidence/t5/runs/case1-강철/), [`preview.png`](evidence/t5/runs/case1-강철/preview.png), [`vram-ㄱ.bin`](evidence/t5/runs/case1-강철/vram-ㄱ.bin) |
| 2 | PASS | 한+ㄱ+ㅏ→한가 `92af8840`, 닭+ㅏ→달가 `89e78840`, V-only ㅗ+ㅏ→ㅘ `e346`, 새 상태 ㅇㅗㅏ→와 `8f4c`, ㄱㅏㅎㅏㄴ→갛(884d)→가한 `884092af` | [`case2-wa-vonly/`](evidence/t5/runs/case2-wa-vonly/) 외 `case2-*` result |
| 3 | PASS | ㄱ 상태 START·OK 셀 → 소리 68, `+0x67`=0, 질문 없음, 상태·destination 불변 | [`case3/result.json`](evidence/t5/runs/case3/result.json) |
| 4 | PASS | 개+ㄷ·간+ㅒ·가+ㅋ: `not_in_2350`, 소리 68, live·len·tail 불변 | `case4-*/result.json` |
| 5 | PASS | 미완성 공백·숫자 거부, `가␣1！` `8840814082508149`, `가␣나` 저장 prefix `8840814088e9`+00, `가␣` 저장 `88400040…`(native trim) | [`case5-trail-space/result.json`](evidence/t5/runs/case5-trail-space/result.json) 외 |
| 6 | PASS | full8 `가나다라마바사안` 실제 키 17개 수락, 8번째 `아→안` active 편집, 9번째 ㄱ `no_slot`·68·8번째 미덮어쓰기, stored 16B `884088e989e28adf8bc38ca68da98ea2` — 11a·11b에서 두 번 | [`case11a-save/result.json`](evidence/t5/runs/case11a-save/result.json), [`full8.png`](evidence/t5/runs/case11a-save/full8.png) |
| 7 | PASS | 강→가→ㄱ→빈(tail `00ffff00`), committed 가 + active 나에서 B, B | `case7-*/result.json` |
| 8 | PASS | 취소 → 예 → 편집기 복귀, destination 불변, 재진입 시 `nc_alloc` 재실행·tail `00ffff00`+0×12 | [`case8/result.json`](evidence/t5/runs/case8/result.json) |
| 9 | PASS | legacy ア×8 재진입: len 8·active 0 → B → ㄱ: `8341×7 e2a8`, tail `0100ff00` | [`case9/result.json`](evidence/t5/runs/case9/result.json), [`prep-legacy/reentry.png`](evidence/t5/runs/prep-legacy/reentry.png) |
| 10 | PASS | 가카 경계: ㄱㅏ → OK → RIGHT(아뇨) → A → 가 committed·active 0·destination 불변 → ㅋㅏ → `88409163` | [`case10/result.json`](evidence/t5/runs/case10/result.json) |
| 11 | PASS | **전원 투입부터 정상 키만**(loadstate·w8·w16 없음, verify.py가 assert). 11a 빈 카트리지 → full8 → 저장 → 세이브 `8bf74323…692f`(패턴 `0x1E504`) → 별도 프로세스 cold. 11b ア×8 세이브 → 덮어쓰기 저장 `43ae680e…7606`(패턴 `0x1F504`) → 별도 cold. 두 cold 모두 목록 `0x0200B204` 16B·재진입 live 16B·len 8·active 0·destination 일치 | [`case11a-save/`](evidence/t5/runs/case11a-save/), [`case11a-cold/cold-list.png`](evidence/t5/runs/case11a-cold/cold-list.png), [`case11a-cold/reentry.png`](evidence/t5/runs/case11a-cold/reentry.png), [`case11b-cold/`](evidence/t5/runs/case11b-cold/) |
| 12 | PASS | 11b 세이브 + 기존 유효 맵 route → 「플레이 OK!」 → 세이브 `b70ea22e…c692` → 별도 cold → Versus 「디자인 맵」 목록에 `가나다라마바사안`, 8음절 A3 복사 확인 → TEAM SETTING | [`case12-build/valid-map.png`](evidence/t5/runs/case12-build/valid-map.png), [`case12-cold-versus/category5.png`](evidence/t5/runs/case12-cold-versus/category5.png), [`selected.png`](evidence/t5/runs/case12-cold-versus/selected.png), [`case12-result.json`](evidence/t5/case12-result.json) |
| 13 | PASS | 한글 active `가`와 미완성 자모 active `ㄱ`(`가`에서 B)에서 탁점·반탁점·R: 소리 68, live 불변. `ㄱ` 단계는 세 조작 직전·직후마다 live `e2a8`·len 1·tail `0100ff00`+0×12를 검사했다(T7-FIX1 재실행 — 정정 전 실행은 이 단계가 `각`이라 [무효](evidence/t5/superseded-case13/README.md)). legacy カ: 탁점→ガ, R→カ, 반탁점 거부 — 원본 ROM 같은 조작과 일치 | [`case13/result.json`](evidence/t5/runs/case13/result.json), [`steps.jsonl`](evidence/t5/runs/case13/steps.jsonl), [`bp.log`](evidence/t5/runs/case13/bp.log), [`case13b-…/result.json`](evidence/t5/runs/case13b-candidate-legacy-kana/result.json) |
| 14 | PASS | 원본 ROM 대조군: A 1회 → `ア`(8341), BP 경로 S1→sound→AE00→B0C6. ア×7カ 저장 `602471df…371e`(13b 대조용) | [`case14-original/result.json`](evidence/t5/runs/case14-original/result.json), [`one-a.png`](evidence/t5/runs/case14-original/one-a.png) |
| 15 | PASS | 실ROM BP 계약 위반 0 (아래) | [`case15-contracts.json`](evidence/t5/case15-contracts.json), [`case15-rowseq.json`](evidence/t5/case15-rowseq.json) |

케이스 15(ABI, T7-FIX1 케이스 13 재실행 뒤 다시 집계): S1 mode1 수락 116/거부 11, S2 mode1 수락 6/거부 2, S3 mode1 17, P1 9, D1 mode1 9, mode0의 D1/S1/S2/S3 각 1. C 진입 `sp%8==0`·`r0==obj`, 복귀 시 r4–r11·SP·LR 동일(D1 mode1은 계약대로 r5=0·r6=0x8000), 고정 복귀 PC B428/B0C6/B21A/AB44/ABA2. D1 mode1 rowdraw 6회 r0=6·r1=6+2i·r2=`0201BB40`·r3=`nc_row_priv_i`, r7=`08314EB1`(함수 주소가 r3를 덮지 않음). 스택 인자 `[sp]=8000`·`[sp+4]=0` 6행은 `watchaddr`로 확인했고 `verify.py`가 assert한다. P1: [`p1-return-witness.json`](evidence/t5/manager-cleanup/p1-return-witness.json)은 [`case15-pending/bp.log`](evidence/t5/runs/case15-pending/bp.log)(sha `1288228a…808abcf`)의 nc_alloc 진입(257행)과 호출자 `083162A2` 복귀(261행)를 뽑은 것이다. r4–r11·SP 동일, 복귀 r0 == 진입 LR(원본 B970 프레임과 같음). **mode0는 합성이다**: pending 상태에서 `w8 02003070 00` 한 번만 써서 mode0으로 바꿨다(정상 키로 mode0에 들어가는 경로는 찾지 못했다). baseline 정상 화면과 rowdraw 인자 6회·A 결과가 같다. 전체 화면 픽셀 비교는 배경 스크롤·1px 차이로 `pass:false`라 판정에 쓰지 않았다([`case15-mode0-SYNTHETIC/notes.json`](evidence/t5/runs/case15-mode0-SYNTHETIC/notes.json)).

**집계 재실행(T6).** 저장된 증거만 읽는 기존 `verify.py`를 T6에서 정확히 1회 다시 돌렸다(에뮬레이터 없음): `python3 -B temp/name-grid-phaseB/t5-runtime/verify.py` → **returncode 0, `T5_RESULT PASS missing evidence: []`**, stderr 빈 출력. 다시 만든 `summary.json`(`3e01dd88…1e93`)·`evidence-manifest.json`(`fcb08421…d405`) SHA는 재실행 전과 같다. 원문 [`t5/superseded-case13/t6-verify-rerun.log`](evidence/t5/superseded-case13/t6-verify-rerun.log) — 이 집계는 정정 전 케이스 13을 포함하므로 T7-FIX1에서 정정 전 원문 폴더로 옮겼다.

**T7-FIX1 정정(Astra full-v1 F1).** 정정 전 케이스 13은 「자모 active」 단계에서 `ㄱ`을 눌러 `가`를 `각`으로 만들었고, 세 조작이 모두 완성 음절 위에서 돌았다. 그래서 그 PASS는 미완성 자모 검증의 근거가 아니다. `B`로 `가→ㄱ`을 만들도록 고쳐 케이스 13만 다시 실행했다. 다른 14개 케이스는 다시 돌리지 않았다. 명령과 실제 종료코드는 다음과 같다(에뮬레이터는 케이스 13 1회뿐, 공식 mGBA 0.10.5 하네스, 후보 `1ac790a9…e1eb`). `python3 -B temp/name-grid-phaseB/t5-runtime/cases.py 13` → 0, 체크 15개 ok([`case13-t7fix1.stdout.log`](evidence/t5/logs/case13-t7fix1.stdout.log)). `… case15.py analyze` → 0, 위반 0, 수치는 위 문단([`case15-analyze-t7fix1.stdout.log`](evidence/t5/logs/case15-analyze-t7fix1.stdout.log)). `… verify.py` → 0, `T5_RESULT PASS`, hygiene OK([`verify-t7fix1.stdout.log`](evidence/t5/logs/verify-t7fix1.stdout.log)). T5 보고서 정정 뒤 manifest의 보고서 해시를 맞추려고 `verify.py`를 한 번 더 돌렸고 결과는 같다(0, [`verify-t7fix1-r2.stdout.log`](evidence/t5/logs/verify-t7fix1-r2.stdout.log)). 정정 전 원문 8개는 [`t5/superseded-case13/`](evidence/t5/superseded-case13/README.md)에 SHA 그대로 두었다. 경위는 [`t7-fix1/REPORT.md`](evidence/t7-fix1/REPORT.md).

## 5. 계획 대비 어긋남 — QA 러너 위치

- 계획 T5는 tracked `tools/qa_part2_name_compose.py`와 `namecompose-qa/`를 적었다. 실제로는 총괄 브리프의 「생산 파일 수정 금지」 경계에 따라 temp `t5-runtime/`의 스크립트와 route로 수행했다. 숨기지 않고 기록한다.
- 재현 자료가 ignored temp에만 남지 않도록 스크립트·기대값·route·하네스 diff·집계·진단 원문을 [`evidence/t5/`](evidence/t5/)에 보존했다. 이번 문서 단계에서 새 tracked QA 도구나 wrapper는 만들지 않았다(검증되지 않은 도구를 추가하지 않기 위해).
- **복원 실행 전제(정직 기록)**: 스크립트는 자기 위치 기준으로 `R=스크립트 폴더`, `B=R.parent`, `ROOT=R.parents[2]`를 계산한다. 그래서 `evidence/t5/`에서는 그대로 돌지 않는다. 다시 돌리려면 ① `evidence/t5/` 내용을 `temp/name-grid-phaseB/t5-runtime/`로, `evidence/t5/deps/`의 route를 `temp/name-grid-phaseB/{native-re,list-link-re}/` 원래 자리로 복사한다. ② 공식 mGBA 0.10.5를 `temp/name-grid-phaseB/official-mgba/`에 다시 빌드한다(절차 [`research/official-mgba/build.py`](evidence/research/official-mgba/build.py)) → `python3 harness/build.py`. ③ 원본 ROM·후보 ROM·baseline ROM과 원본에서 정상 키로 만든 `native-re/replay-normal/new-eight.sav`(`d6e26512…b481`, 커밋 안 함, [`replay_normal` route](evidence/research/native-re/replay-normal/route.txt)로 재생성)를 둔다. ④ `launch.json`·로그의 절대 경로는 작업 당시 이 맥의 체크아웃 기준이다.

## 6. 정리 기록

- T5가 repo 밖 세션 scratchpad에 만든 분석용 contact sheet PNG 1개는 T5 종료 뒤 총괄이 `temp/name-grid-phaseB/manager-cleanup/c11.png`로 SHA 동일 복사(`1368d4b8…05d1`)하고 원본 파일만 지웠다([`cleanup.json`](evidence/t5/manager-cleanup/cleanup.json)). T5 보고서의 「소유 폴더에만 썼다」는 이 한 파일에 대해서는 맞지 않는다. 이 contact sheet는 판정 근거가 아니어서 영구 보존 대상에서 뺐다.
- 실패·재실행 산출물은 temp `runs-failed/`·`runs-superseded/`에 지우지 않고 남아 있다(커밋 안 함). 판정은 최종 실행 기준이다.

## 7. 알려진 한계

- **조합 도달 불가 5음절**: 2350에는 있지만 표준 키열의 중간 후보가 2350 밖이라 이 계약(중간 후보 원자 거부)으로는 일반 키열로 입력할 수 없다 — **뢨**(중간 뢔)·**썅**(쌰)·**쏀**(쎼)·**쓩**(쓔)·**쭁**(쬬). T2 전수 11,172음절 결과(도달 2,345)이며 모델 결과와 같다([`COMPOSITION_SPEC.md`](COMPOSITION_SPEC.md)).
- 이름 혼동 주의: 연구 단계의 full8 `가한글가한글가한`은 **RAM 주입 후 native 저장**한 실험이다(candidate-re). 이번 기능의 full8 `가나다라마바사안`은 **그리드 실제 키 17개**로 입력했다(T5 케이스 6·11).
- 실기(GBA 하드웨어) 미검증. Link BLOCKED([`PHASE_B_RE.md`](PHASE_B_RE.md) §9). SRAM bank·checksum 포맷 해석은 (unverified). 자모 코드가 대화 렌더러(`0x030065E0`)에 나올 때의 표시는 대상이 아니었다. 그리드 자모가 좁게 몰려 보이는 것은 시각 관찰이며 디자인 판단은 하지 않았다. 힙 +16B 이웃 영향은 케이스 1·8·11에서 이상 없음(전수 증명 아님).
- 기존 잔여(B팀 114·overflow 273·wider 507·layout-loss 152)는 baseline과 같은 집합으로 남아 있다. 이번 회귀가 아니고 해결도 아니다.
