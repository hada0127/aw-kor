# T4 후보 빌드·정적 QA — 보고 (PLAN-v5 T4)

상태: **완료 — 빌드 1회 exit 0, 5관문 전부 exit 0, diff/payload·A3 자모·공유 글리프·충돌 교차·B팀·text-fit 집합 비교 전부 PASS.** 에뮬레이터·런타임·커밋·소스 수정은 하지 않았다(T5 이후 범위).

- 수행: 로컬 Claude(Orca task_e7e283a4f2fe / ctx_19328acb517b), role=code, risk high, effort high. `ROUTING_UPDATE.md`(「이 pc 하네스대로」) 기준.
- 계획: `PLAN-v5.md` sha256 `60a7574a…21b4`, `PLAN-REVIEW-v5.md` `VERDICT: APPROVE`(같은 sha). T1·T2·T3 완료 보고(`t1-assets/`·`t2-core/`·`t3-builder/REPORT.md`) 입력.
- 기준: HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`(branch `sweep3-p2-20261023c`) + T1~T3 미커밋 입력.

## 후보

| 항목 | 값 |
|---|---|
| 후보 ROM | `output/game_wars_korean_namecompose_20261023.gba`(ignored, 새 파일 — 전에 없었음) |
| **후보 SHA-256** | **`1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb`** (snapshot 산출물 = 부모 사본, 5관문 뒤에도 같음) |
| 같은 빌드 `temp/integrity_map.json` | `eb0da58c7a1c9a15a7b50324ba135cfb0ec196dfcea9a2d66ad77c30ef82b025` |
| 같은 빌드 `temp/repoint_manifest.json` | `a7cf6fc17184c6dcbd754bf0e566beb308c0bdc850d153f1167a508fe3de53ee` |
| 같은 빌드 `temp/encode_report.csv` | `9bb6271025b975f5b2e703180b1e34bb4c272935ad081228f98c650e5a5cdee7` |
| baseline | `output/game_wars_korean_namegrid_baseline_20261023.gba` `ebbca0ba…a8a` |

map·manifest·encode_report 세 SHA 는 baseline RETRY1 빌드(`RETRY1_METADATA.json` build_artifacts)와 **바이트 동일**하다 — 이름 조합 쓰기는 `WRITE_LOG`/manifest 에 넣지 않는 설계(T3)와 일치. 참고: 후보 SHA 는 T3 가 fixture 로 만든 후보(`1ac790a9…e1eb`, T3 보고)와 같다.

## 사전 확인

- `ps -axo pid,etime,command | grep build_korean|qa_|mgba|playthrough` → 출력 없음(부모 쪽 전체 빌드·하네스 미실행). 남의 프로세스 건드리지 않음.
- `harness-resources`: 주의(스왑 15.2GB, 아웃 0p/s, 여유 메모리 48%) — 차단 아님, 빌드 1개만 실행.
- 부모 `git status --porcelain` = T1~T3 의도 변경 11줄과 정확히 같음(러너가 assert).

## Snapshot(빌드 입력 고정)

- 러너 `run_build.py`, 메타 `METADATA.json`, manifest `snapshot_manifest.json`(sha `e6c9fcf8b8b53c6abd68c8cbc73da24fab149bf4ed13424c3fd5e42f38e21b66`, 3,206 파일 = `git ls-files` tracked + `git ls-files --others --exclude-standard` 미커밋 12개). 복사 직후 전 파일 SHA == 부모(assert). `source/`(ignored, `.gitignore:36 temp/`).
- T1~T3 입력 SHA(snapshot = 부모):

| 파일 | SHA-256 |
|---|---|
| tools/build_korean_full.py (M) | `be43e4ab0de0b519e4883d6e7b6329f3385bf649cce2f1ecfd6a20e315093229` |
| tools/part2_native_controls.py (M, T3 총괄 승인) | `88a6d8a2712552cce38f254dfc330aeaa65cdb566b06534678b433c784fdf61f` |
| tools/test_part2_native_controls.py (M, T3 총괄 승인) | `faf421d2887f22eb23d7743d8eeb2e8731620bda1a4bf16de2b28f7ff85ad1bd` |
| data/jamo_glyphs_40.bin | `1417db5cb058782f3cd3f133cead8da711de47e3185bbfaf900ad8841f7c4980` |
| data/jamo_to_code_40.json | `628404ed7bbb567872108431f30c76fd8824acebbe3049ac4031923eeda2b7e9` |
| tools/gen_jamo_assets.py | `e7a36dbfb00d5d48ec40a5ab078490d03d31c722ec6c91de914c13d0531927e3` |
| tools/name_compose/build_image.py | `bec403f8d3d9afd0bb5af0a5c7a427771ddc0b906905ff0a2f1bba03c110a1c9` |
| tools/name_compose/core.c | `aa99b4cad212c3c9c59b231b757d35cf677efe9ecb4b050957514238bfae9a01` |
| tools/name_compose/gen_tables.py | `112dcdaa75e5c724bd589a23d1da7ce2f292e48d582b585519acae6fc0ac78a4` |
| tools/name_compose/image.ld | `40ce99f46732befde9e15e76e18d67f3a89a042d37602604bd362aedbdcb2a5e` |
| tools/name_compose/tramp.s | `6c30f45143042e221184a46a6bcac127acaa7e0f471de633ab2f216b32a32f9d` |
| tools/part2_name_compose_blob.py | `3313d3d8672e5868b1af95f0ebfbaeb2cb6a1f88b43f0febabc3b5eb368a3c16` |
| tools/test_jamo_assets.py | `434e148b620cac078df44730aac2ccfd4a8079124c52846ba1ae0cc11bcbbee8` |
| tools/test_name_compose_core.py | `bbe99bbce16dd04f8c2c67cfbefb2b78e330e8a85e321a306a69851b6fd7a137` |
| tools/test_part2_name_compose_build.py | `ce00d1a6351799d964f2f4ccf2168739b54e733360de01361bfc6b3e71a8dd20` |

- 원본 읽기 사본 `source/original/...gba`(0444) `a8ad7c7d…831c`. 폰트 env: `AW_FONT_DIR=temp/name-grid-phaseB/fonts`, `AW_HADASANS_FONT`/`AW_HADASANS_BLACK_FONT` = `~/project/hada-font/fonts/hada-sans/otf/HadaSans-{Bold,Black}.otf`(SHA 는 METADATA `fonts_sha256`, baseline 과 같은 값). `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=source/temp/tmp`. EDITOR_LOCK 은 snapshot 의 기존 코드 그대로(빌더 `__main__` 에서 획득).
- 예외 2파일(`data/sprite_build_layouts.json` `5eabfda2…b04c`, `data/objlabel_sprites.json` `bcabd955…d0be`): 빌드 전후 SHA **동일**(재생성 결과가 같음). snapshot 전체 `snapshot_changed = []`.
- Python `/Applications/Xcode.app/Contents/Developer/usr/bin/python3` 3.9.6, Pillow 11.3.0(baseline 과 같음).

## 빌드·5관문 (cwd = `source/`, 원문 로그 = 이 폴더)

```text
nice -n 15 python3 tools/build_korean_full.py --out output/game_wars_korean_namecompose_20261023.gba --no-sync-outputs --report temp/encode_report.csv
→ output/game_wars_korean_namecompose_20261023.gba (16MB, chk recomputed) ...           EXIT 0   (build.log, 09:02→09:09 UTC, setpriority 경고 없음)
python3 tools/phase6_basic_test.py output/game_wars_korean_namecompose_20261023.gba
[OK] ROM passed pre-flight checks (Checksum valid: True)                                  EXIT 0   (gate1.log)
python3 tools/qa_integrity_map.py --rom <후보> --map temp/integrity_map.json --byte-only
[OK] 바이트 무결성: 기대 577856바이트 중 불일치 0 (40055 writes)                           EXIT 0   (gate2.log)
python3 tools/qa_text_fit.py --rom <후보> --map temp/integrity_map.json --manifest temp/repoint_manifest.json
layout-loss 152 / overflow 273 / visual-wider 507 (2.8%) / protected non-Korean 0/485       EXIT 0   (gate3.log)
python3 tools/qa_bteam_drift.py --rom <후보> --map temp/integrity_map.json --repoint-manifest temp/repoint_manifest.json --json temp/candidate_bteam_details.json
mismatch 114 (listed 103, deferred 11, unlisted 0) · [HARD-OK] drift 0                    EXIT 0   (gate4.log)
python3 tools/qa_part2_name_grid_shared_glyph.py <후보>
PASS shared Part 2 dash 0x815B pixels: be419dc0…2bba                                      EXIT 0   (gate5.log)
```

모든 관문은 후보 ROM·같은 빌드 map/manifest 를 명시 인자로 받았다(default 경로 ROM 묵시 검사 없음). argv 는 baseline `retry1_runner.py` 와 같고 bteam 에 `--json` 만 더했다. 관문 exit 0 은 잔여 0 을 뜻하지 않는다 — 아래 집합 비교가 회귀 판정이다.

## 회귀 비교 (개수가 아니라 집합)

### B팀 (`analyze.py` §5 → `analysis/bteam_diff.json`)
(address, cause, decision) 집합: baseline `baseline-build/source/temp/retry1_bteam_details.json` 114 · 후보 `source/temp/candidate_bteam_details.json` 114 → **new 0 / gone 0, 레코드 전체(baseline·rom_text 포함) 동일**. decision DEFER 11 / ALIGNMENT_RESTORE 1 / RESTORE_BASELINE 97 / NEW_STRICT_MISMATCH 5(기존 분류 이름, 이번 회귀 아님).

### text-fit (`trace_text_fit.py` → `compare_text_fit.py`)
- 방법: source 별 **새 프로세스**(`python3 -I -B`, cwd=각 source, sys.path=각 source/tools 만)에서 `qa_text_fit.main([--rom, --map, --manifest])` 실행. `sys.settrace` 전역 함수는 `co_name=='check_text'` 이고 그 파일의 code 일 때만 local tracer 를 돌려주고 `f_trace_lines=False`(line 이벤트 끔). call 시 local `a, ko, ja, slot_override` 와 nonlocal `overflow`/`wider`, return 시 증분을 읽어 (주소, 유형) 이벤트 기록. 분류 로직 복제 없음. 실제 함수(`tools/qa_text_fit.py:306` `check_text(a, ko, ja, slot_override=None)`, nonlocal `overflow`·`wider`)는 HEAD 와 동일 파일.
- 결과(baseline / 후보 동일): check_text 호출 18,584 · 미복귀 0 · 다른 source 모듈 혼입 0 · **overflow 이벤트 273 == 출력 273, wider 이벤트 507 == 출력 507**.
- 집합: (주소, 유형) 키는 overflow 259 + wider 507. overflow 는 **같은 주소·같은 인자로 check_text 가 두 번 이상 불린 13 주소(이벤트 27)** 가 있어 키 수(259) ≠ 출력(273)이다 — 호출 위치 `qa_text_fit.py:376/401/433/443`. 그래서 키별 발생 횟수(multiplicity)를 같이 보존했고 합계 == 출력으로 대조했다. 반복 주소: A06620·A07330·A074AC·A08930·A08B98·A090A4·A0BC9C·A250EC·D9F3E2·DC3822·DC4466(3)·DCDEEB·DCEA43.
- baseline vs 후보: **new 0 / gone 0 / multiplicity 변화 0, 이벤트 전체 목록(주소·유형·ko·ja·slot_override·호출줄) 동일** → `analysis/textfit_diff.json` `pass: true`, exit 0.
- 총괄 후속 지시(inbox, 반복 주소를 버리지 말고 이벤트 전체·고유 (주소,유형) 집합·다중도 모두 비교, EXIT3 증거 보존)와 같은 방식이다. 이벤트는 `textfit_*.json` `events` 배열에 호출 순서(배열 index = ordinal)대로 전부 보존했다.
- 첫 시도(`*.attempt1.*`)는 내 검사기의 판정 결함 2개로 exit 3: ① 추적 스크립트 자신(`__main__`)을 「다른 source 모듈」로 셈 ② overflow 에서 주소 집합 크기 = 출력 합계를 요구(위 반복 호출 때문에 불가). 데이터는 같았고 검사기만 고쳐 다시 돌렸다(빌드 반복 아님).
- baseline source 불변: `tree_hash.py` 전후 3,213 파일 집계 SHA `c46350e3…d4b1` 동일(`baseline_source_tree_{before,after}.json`).

## 후보 − baseline 바이트 diff + payload (`analyze.py` §1 → `analysis/diff_payload.json`)

- diff 8,156 바이트, **전부 `NAME_COMPOSE_WRITES` 10영역 ∪ end 리터럴 4곳 안**(outside 0). 영역별 변경 바이트: jamo_tiles 637 · nc_dense 4,700 · nc_image 2,532 · a3_table_tail 239 · a3_max 2 · S1 10 · S2 8 · S3 9 · D1 8 · P1 3 · end 리터럴 4곳 각 2.
- payload 필수 대조(빌더 헬퍼를 쓰지 않고 계획 §1.5/§1.7 로 직접 인코딩): 10영역 **전부 일치 + 전부 baseline 대비 실제 변경**. 사이트는 baseline == 원본 == expect 였음, 새 영역은 baseline 에서 0 이었음.
  - jamo_tiles == `data/jamo_glyphs_40.bin` · nc_dense == 2350 음절 `(ord−0xAC00)*2` u16 LE 직접 생성(gen_jamo_assets.dense_table 과도 같음) · nc_image == blob CODE(2,739B, sha `8dd94608…3b2f`) + 0 채움 8,192B · a3_table_tail == JSON 순서 i 의 `code BE, (1275+2i)|0x8000, (1276+2i)|0x8000` · a3_max == `0xE352` · S1 `00480047`+`nc_tramp_press|1`+`c046` · S2 `00480047`+`nc_tramp_confirm|1` · S3 `01480047c046`+`nc_tramp_backspace|1` · D1 `004b1847`+`nc_tramp_display|1` · P1 `nc_alloc|1`.
  - end 리터럴 EFE974·F3030C·314000·B11E28: baseline `0x08F243A4` → 후보 `0x08F24494`(= 0x08F20000 + 2,926×6).
- 보호 바이트(후보 == baseline): A3 min F30300 `0x8840` · start F30308 · **mask F30310 `0x7FFF`** · KOR base F30314 · 선택표 83FAF6..83FBAA · 표시행 83FE40..83FEF4 · row pointer 리터럴 34AC24..34AC3C · KEEP FD78/FDE0/FD28 · dispatch 34AFAE · allocator 315288..3153B0 · A3 트램펄린 A3C7E8. 원본 선택/표시표·포인터·dispatch·allocator 는 원본과도 같음(A3 hook 영역은 빌더 생성물이라 원본과 다른 게 정상).

## A3 자모 정합 (`analysis/a3_jamo.json`)

후보 hook 리터럴 F30300..F30317 = min `0x8840` / max `0xE352` / start `0x08F20000` / end `0x08F24494` / mask `0x7FFF` / KOR base `0x08F00000`(baseline 은 max `0xE2A7`, end `0x08F243A4`). 실제 hook 동작대로(min/max 범위 → start..end 6B 선형 검색 첫 일치 → top bit15 → `(idx&mask)*32 + base`) 조회:
- 자모 40: **전부 ok, 표 안 중복 0(정확히 1회), tile 1275+2i/1276+2i, 64B 그림 == bin, 잉크 있음**. baseline 에선 40개 전부 `range`(max 밖 → 한글 아님).
- 2350 음절: 후보·baseline 조회 결과(entry·중복·64B 그림) 변화 **0**.

## 공유 A3 가나 글리프 (`analysis/shared_glyph.json`)

`mode-scope-re/grid-map.json` 의 선택 ∪ 표시 ∪ 행 쌍에서 action marker 3131/3232/6262/6363/6565 제외 → **72 코드**. `tools/test_dialogue_script_safety.py:309` `native_glyph` 와 같은 탐색(root = LE32(rom[0x52F960])−0x08000000, bucket = root+((code&255)−0x40)*4, node 연결을 따라 off+4 == code>>8, 그림 off+6..off+70)을 baseline·후보 각각의 ROM 에 적용.
- 72개 전부 **존재**, root·bucket·경로·node·64B 그림 baseline == 후보(mismatch 0). 원본과도 같음.
- 부재 코드 **0** → 양쪽 부재·fallback 비교 대상 없음.
- 장음 815B 별도: node `0x809CD0`, 그림 `be419dc0…2bba` baseline 과 같음 + gate5 PASS. 한글 재배치 표 tile 검사는 이 검사에 섞지 않았다(위 A3 절과 분리).

## 쓰기 충돌 일회성 교차 (`analysis/writer_crosscheck.json`, 입력 SHA 파일 안)

대상: `F70000..F77800` 및 `NAME_COMPOSE_WRITES` 10영역.
- `candidate-re/integrity-ranges.json`(baseline 40,055행) · 후보 integrity_map(40,055행, baseline 과 동일) · baseline/후보 repoint_manifest(new_addr/new_len): **교차 0**.
- `candidate-re/writer-addresses.json`: a3_max(F30304..F30308) ↔ `PART2_HOOK_A3_FILE`(F30280..F30324) **1건 — 계획 §1.7 이 정한 소유 확장(기존 hook 의 max 리터럴)**, 나머지 0. F70000..F77800 교차 0.
- `candidate-re/direct-writers.json`(같은 AST 추출 재실행): 190 → 192, 추가 2건 모두 자기 writer — `_name_compose_a3_max`(`:13679` max pack_into), `_part2_name_compose`(`:13805` 영역 기록). 제거 0. tracked 테스트에 이 ignored JSON 의존을 추가하지 않았다.

## 보호·불변 (`final_check.py` → `final_check.log`, 모든 분석 뒤 실행, exit 0)

- 부모: HEAD 불변, tracked + 미커밋 입력 전 파일 SHA 전후 동일, `git status` 전후 동일(T1~T3 11줄). 부모 `data/` 생성물 2개 포함 쓰기 없음.
- 보호: 원본 `a8ad7c7d…831c` · baseline `ebbca0ba…a8a` · b44 `1ac68443…6f02` · dist 39파일 SHA 전후 동일(목록 final_check.log). output full/final/title_test 는 전후 모두 없음.
- snapshot: 빌드 뒤 모든 분석 후에도 manifest 3,206 파일 불변. 후보 부모 사본 == snapshot 산출물.

## 계획 대비 어긋난 점

1. text-fit 집합: (주소, 유형) 순수 집합 크기는 overflow 에서 출력 합계와 다르다(같은 인자 반복 호출 13주소). 키별 발생 횟수를 붙여 합계 == 출력, 이벤트 전체 목록 동일로 판정했다. 개수 폴백 아님 — 집합·다중도 둘 다 비교.
2. `native_glyph` 는 테스트 메서드 안 중첩 함수라 import 재사용이 불가해 같은 알고리즘을 `analyze.py` 에 옮겨 썼다(주소 공식·필드 동일).
3. 검사기 판정 결함으로 text-fit 추적을 1회 다시 돌렸다(빌드·소스 무관, attempt1 산출물 보존).
4. 같은 빌드로 phase6 이 성공했지만 「에뮬레이터 부팅」 증거는 아니다(정적 pre-flight).

## 남은 위험 (unverified)

- 실행 동작 전부 — 훅 진입/복귀·레지스터/스택, D1 6행 렌더, nc_alloc tail 초기화, 자모 VRAM 표시, 8자 저장·콜드 로드, mode0 회귀, 힙 +16B 이웃 영향 → **T5**.
- 자모 코드가 다른 렌더러(대화 0x030065E0 경로 등)에서 쓰일 때의 표시: end 리터럴 EFE974 도 늘었으나 이번엔 A3 경로만 정적 대조.
- 기존 잔여(B팀 114·overflow 273·wider 507·layout 152)는 baseline 과 같은 집합으로 남아 있다 — 이번 회귀는 아니나 해결도 아니다.
- 기존 실패 테스트 2건(`test_part2_context_contract` `data/dialogue_map.json` 없음, `test_qa_part2_physical_rows` 0 vs 58)은 T3 보고대로 HEAD 기준 실패이며 이번 범위에서 손대지 않았다.

## 산출물 (이 폴더)

`run_build.py` · `METADATA.json` · `snapshot_manifest.json` · `runner_stdout.log` · `build.log` · `gate1..5.log` · `analyze.py`/`analyze.log` · `trace_text_fit.py` · `compare_text_fit.py`/`.log` · `trace_{baseline,candidate}.log`(+attempt1) · `tree_hash.py` · `baseline_source_tree_{before,after}.json` · `final_check.py`/`.log` · `analysis/{summary,diff_payload,a3_jamo,shared_glyph,writer_crosscheck,bteam_diff,textfit_baseline,textfit_candidate,textfit_diff}.json` · `source/`(snapshot + 같은 빌드 temp/·output/, T5 재현용 보존).

## 후속 반영

없음 — T4 는 소스·문서 수정 금지 범위. T6 에 넘길 사실: 후보 SHA `1ac790a9…e1eb`, map `eb0da58c…b025`(baseline 과 동일), A3 max 0xE352·end 0x08F24494, diff 8,156B ⊆ WRITES+end 4, text-fit 반복 호출 13주소 특성.

정리: 띄운 프로세스 전부 종료(빌드·관문·분석). 워크트리·claim·브라우저·에뮬레이터 없음. `source/temp/tmp` 는 snapshot 안이라 함께 보존.

RECEIPT: model=claude-opus-5-5 effort=high role=code
