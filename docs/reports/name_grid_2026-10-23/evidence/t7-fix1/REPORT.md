# T7-FIX1 — Astra full-v1 지적 F1·F3·N1 정정 (진행 중 기록)

- 시작: 2026-10-23 19:16 KST · 워커 task `task_7addef95422d` / dispatch `ctx_3c0881637860` · 역할 code(Claude Opus 5.5, high 지시)
- 입력: `temp/name-grid-phaseB/T7_FIX1_BRIEF.md`, `final-review/REVIEW-full-v1.md`(Critical 0 · 필수 2 · Nit 1)
- 기준: HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`, 리뷰 대상 manifest `da80c8cd…a7f6` / patch `51ab29b6…2669`
- 생산 SHA 기준선: `sha-before.txt`(T6 `production-sha-before.txt`와 동일 확인 — `SAME_AS_T6`), dist `dist-sha-before.txt`(39파일), 소유 문서 `owned-sha-before.txt`, `git-status-before.txt`

## T7-FIX2 정정 이력 — F4 (2026-10-23)

Astra delta1-v2 F4에 따라 진행 9번·명령표 5번·검증결과 비교 항목의 잘못된 RC0 성공 주장을 철회했다. 원시 `compare_t4_snapshot.log`와 이후 수정본 `.py`는 바이트 그대로 보존하며 재실행하지 않았다. 최초 단순 비교의 실제 RC=1과 후속 성공 `(unverified)`를 구분한다. 이 보조 비교의 성공은 판정 근거에서 제외한다. 별도 역사 사본은 만들지 않았다.

생산·후보 불변의 독립 근거인 기존 `sha-before.txt`/`sha-after.txt`, `validate_t7.py` 보존 출력에 대한 아래 기록, 부모 `temp/name-grid-phaseB/final-review/manifest-v2.json`의 `T4_differences = ['tools/test_part2_name_compose_build.py']` 기록은 유지한다. F4 정정은 다른 15case·F3의 실제 RC0 로그를 무효로 하지 않는다. 이 절 이외의 실행·정리 기록과 마지막 영수증은 당시 T7-FIX1 작업 이력이다.

## 진행

1. (19:16) 브리프·리뷰·T5 러너(`cases.py`·`t5lib.py`·`case15.py`·`verify.py`)·T6 수집/색인/검증 스크립트 읽음.
2. (19:17) F3: `tools/test_part2_name_compose_build.py` — `TemporaryDirectory(dir=os.environ.get('TMPDIR'))` → `tmp_root = ROOT / 'temp'; tmp_root.mkdir(exist_ok=True); TemporaryDirectory(dir=tmp_root)`. 유일한 `os` 사용처가 사라져 `import os` 1줄도 뺐다(미사용 import 방지). T3 snapshot 대비 diff는 이 두 군데뿐.
3. (19:18) 리뷰 명령 1 `env -u TMPDIR … python3 -B tools/test_part2_name_compose_build.py -v` → RC=0, `Ran 16 tests … OK`. 보조: audit hook으로 같은 테스트 메서드 1개를 TMPDIR 미설정 상태로 돌려 `tempfile.mkdtemp` 경로가 `ROOT/temp/tmp9xc8eu6w` 1건뿐임을 기록(RC=0). 실행 뒤 `temp/tmp*` 잔여 0.
4. (19:19) F1: `t5-runtime/cases.py` 케이스 13 — `c.jamo('ㄱ')` → `c.backspace()` + 세 조작 직전·직후 `ㄱ state` 체크. 정정 전 사본 `pre-fix/cases.py`.
5. (19:19) 리뷰 명령 2 `python3 -B temp/name-grid-phaseB/t5-runtime/cases.py 13` → RC=0, case13 PASS(체크 15개 ok). 옛 run은 `runs-superseded/case13-1792750756/`로 자동 이동(sha가 영구 증거의 옛 result/steps와 같음). 프로세스 원장 start/end exit 0, 잔여 하네스 0.
6. (19:20) 리뷰 명령 3 `case15.py analyze` → RC=0, 위반 0, S1/mode1/c_ret0 117→116, S3/mode1/c_ret0 16→17.
7. (19:20) 리뷰 명령 4 `verify.py` → RC=0 `T5_RESULT PASS`. 이후 T5 REPORT 정정 → manifest의 REPORT 해시를 맞추려고 `verify.py`를 한 번 더(r2) 실행, RC=0, stdout 동일, manifest 차이는 REPORT.md 행뿐.
8. (19:21) T5 `REPORT.md` 정정(케이스 13 행·케이스 15 수치·명령표 T7-FIX1 3행·「T7-FIX1 정정」 절). 정정 전 사본 `pre-fix/t5/REPORT.md`.
9. (19:22 기록 정정 — T7-FIX2 F4) 당시 보조 비교를 RC=0으로 보고했으나 그 주장을 철회한다. 보존 `compare_t4_snapshot.log`는 최초 단순 비교의 `DIFFERENT`(F3 테스트 파일 + T6 문서 6개)·`MISSING []`·**RC=1** 원문이다. 현재 보존 `.py`는 이후 수정본(`DIFF_VS_T4` 등 출력)이므로 이 로그와 동일 실행의 소스로 연결하지 않는다. 후속 RC0 실행은 원문 로그가 보존되지 않아 `(unverified)`이며 판정 근거에서 제외한다.
10. (19:23) `PHASE_B_QA.md` 정정(N1 상태 문장, F3 SHA 메모·T7-FIX1 테스트 행, 케이스 13 행, 케이스 15 수치, T6 집계 로그 링크 이동, T7-FIX1 정정 문단).

## F1 · F3 · N1 판정

| 지적 | 상태 | 바꾼 것 | 검증 |
|---|---|---|---|
| F1 필수 — 케이스 13 미완성 자모 미검사 | **fixed** | `t5-runtime/cases.py` 케이스 13: `c.jamo('ㄱ')` → `c.backspace()`(가→ㄱ, 소리 66). 세 조작 직전·직후 `ㄱ state` 체크(live `e2a80000`·len 1·tail `0100ff00`·`+74..+7F` 0) + 조작별 소리 68·live/len/tail 불변 체크 | `cases.py 13` RC=0, 체크 15개 ok. steps: `B`→`ㄱ`, 이후 세 스텝 `preview="ㄱ"`·`e2a8…`·`0100ff00…`·sounds `['68']`·bp_seq `['sound']`(트램펄린 진입 없음) |
| F3 필수 — 빌더 테스트 임시 파일이 레포 밖 | **fixed** | `tools/test_part2_name_compose_build.py`: `TemporaryDirectory(dir=ROOT/'temp')`, `temp/` 없으면 생성, `import os` 제거 | TMPDIR 미설정 16 tests OK RC=0, audit hook mkdtemp 1건 `<repo>/temp/tmp9xc8eu6w`, 잔여 0 |
| N1 Nit — 「실행 명령 전부 exit 0」 | **fixed** | `PHASE_B_QA.md` 상태 문장을 「최종 채택 실행」으로 좁히고 첫 실패·재시도 이력 위치를 명시. 정정 전 케이스 13 자료는 무효 표시 폴더로만 연결 | 문서 검토 + `validate_t7.py` 링크 검사 |

## 검증 명령 (원문은 이 폴더·`t5-runtime/logs/`; 보조 비교 5번은 아래 정정 참조)

| # | 명령 | RC | 원문 |
|---|---|---:|---|
| 1 | `env -u TMPDIR PYTHONDONTWRITEBYTECODE=1 nice -n 15 python3 -B tools/test_part2_name_compose_build.py -v` | 0 | `test_part2_name_compose_build.{stdout,stderr}.log`·`.exit.txt`·`.env.txt` (unittest 출력은 stderr, stdout 0B) |
| 1b | (보조) `env -u TMPDIR python3 -B temp/name-grid-phaseB/t7-fix1/audit_tmp.py` | 0 | `audit_tmp.*` |
| 2 | `TMPDIR=<t5-runtime>/tmp/ python3 -B temp/name-grid-phaseB/t5-runtime/cases.py 13` | 0 | `t5-runtime/logs/case13-t7fix1.*`, run `runs/case13/` |
| 3 | `… python3 -B temp/name-grid-phaseB/t5-runtime/case15.py analyze` | 0 | `t5-runtime/logs/case15-analyze-t7fix1.*` |
| 4 | `… python3 -B temp/name-grid-phaseB/t5-runtime/verify.py` | 0 | `t5-runtime/logs/verify-t7fix1.*` |
| 4b | 같은 `verify.py` 재실행(T5 REPORT 정정 뒤 manifest 해시 갱신용) | 0 | `t5-runtime/logs/verify-t7fix1-r2.*` (stdout이 4와 동일) |
| 5 | 최초 단순 비교의 당시 명령 경로 `python3 -B temp/name-grid-phaseB/t7-fix1/compare_t4_snapshot.py`(당시 소스 미보존; 현재 보존본은 이후 수정본) | 1 | `compare_t4_snapshot.log`(`DIFFERENT`·`MISSING` 출력). 과거 RC0 연결은 철회, 후속 성공은 `(unverified)`·판정 근거 제외 |
| 6 | `python3 -B temp/name-grid-phaseB/t7-fix1/update_evidence.py` | 0 | `update_evidence.log` |
| 7 | `python3 -B temp/name-grid-phaseB/t7-fix1/make_index_t7.py` | 0 | `make_index_t7.log` |
| 8 | `python3 -B temp/name-grid-phaseB/t7-fix1/validate_t7.py` | 0 | `validate_t7.log` |

케이스 13 실행: 공식 mGBA 0.10.5 T5 하네스(`harness/mgbah-t5`), 후보 `1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb`(Emu가 assert), loadstate `runs/prep-fresh/name-entry.ss0`(T5 소유), cwd·TMPDIR·log 전부 `runs/case13/`, `nice -n 15`. 원장 `processes.jsonl`: superseded → start pid 19646 → end exit 0. 실행 뒤 `pgrep -fl mgbah-t5` 없음.

## 변경 파일 SHA

| 파일 | 전 | 후 |
|---|---|---|
| `tools/test_part2_name_compose_build.py` | `ce00d1a6351799d964f2f4ccf2168739b54e733360de01361bfc6b3e71a8dd20` | `63a17421b71c16332b0d75e7647030de084ae9254599b7b273589beb7315c689` |
| `temp/name-grid-phaseB/t5-runtime/cases.py` | `45f6561b22b8c1484f1fa192ff39d2886bfca24ea075212abcf6942e1bfde7bf` | 증거 `t5/cases.py` 행 |
| `temp/name-grid-phaseB/t5-runtime/REPORT.md` | `37326b309525225e03fd206d4bc1da4c73c50233ebeb5be3492e5d08decd001b` | `e643304e8cc5fbc3507aa621b9be44c50900fb79131181eb1b3320dcb455b31a` |
| 생성: `summary.json` / `case15-contracts.json` / `evidence-manifest.json` / `processes.jsonl` / `runs/case13/*` | 정정 전은 `../t5/superseded-case13/README.md` 표 | 증거 `index.json` 행 |

나머지 생산 파일 18개(빌더·native controls·blob·자산·코어 소스·후보/baseline/b44/원본 ROM)와 T6 문서 6개는 `sha-before.txt` == `sha-after.txt`(테스트 파일 1행만 다름). dist 39파일은 `validate_t7.py` §5가 다시 대조.

## 동반 갱신

- 영구 증거 `docs/reports/name_grid_2026-10-23/evidence/`
  - 교체(같은 경로, 새 실행 결과) 8: `t5/cases.py`, `t5/runs/case13/result.json`, `t5/runs/case13/steps.jsonl`, `t5/summary.json`, `t5/case15-contracts.json`, `t5/evidence-manifest.json`, `t5/REPORT.md`, `t5/processes.jsonl`.
  - 정정 전 원문 보존 `t5/superseded-case13/`(무효 표시 README + 8파일, sha 옛 index와 같음 assert). `t5/t6-verify-rerun.log`는 정정 전 케이스 13을 PASS로 집계한 로그라 이 폴더로 **옮겼다**(같은 바이트).
  - 추가: `t5/runs/case13/{bp.log,commands.jsonl,launch.json,exit.json}`(BP 증거), `t5/logs/*t7fix1*` 12개, `t7-fix1/` 그룹(이 보고서·F3 테스트 로그·audit·diff 2개·비교 스크립트/로그·SHA 전후·갱신/색인/검증 스크립트).
  - `t3/`의 옛 테스트 로그·snapshot·REPORT는 덮지 않았다(F3 결과는 `t7-fix1/`에 따로).
- `index.json`·`INDEX.md`(그룹 `t5-superseded`·`t7-fix1` 추가, T7-FIX1 메모, 공백 메모의 옮긴 경로 반영). `INDEX.md`는 `make_index_t7.py`(= T6 `make_index.py` + 그룹 2개·메모)로 다시 썼다.
- `PHASE_B_QA.md`(위 10번).

## 증거 갱신·검증 결과

- `update_evidence.py` RC=0: `index rows 324 added 43 replaced 8 moved 1`(282 − 1 + 43). 옮긴/보존 8파일은 옛 index sha와 같음을 assert, 교체·추가 파일은 temp 원본과 sha 대조.
- `make_index_t7.py` RC=0: `INDEX rows 324`.
- `validate_t7.py` RC=0, `ERRORS 0`: 증거 324파일 = index 목록·sha·크기 일치, 금지 확장자 0, 상대 링크 455개·축약 SHA 65개 해석, `git diff --check` exit 0, 생산·새 문서(미추적 17 + INDEX/index) 공백 지적 0, `PRODUCTION_CHANGED ['tools/test_part2_name_compose_build.py']`(25행 중 1), `DIST_UNCHANGED True 39`.
- 원시 증거 공백(보고만, 고치지 않음 — `.gitattributes` 등 억제 없음): T6 시점 5파일 19건은 그대로(`t6-verify-rerun.log`는 `t5/superseded-case13/`로 옮겨진 경로로 보고됨). T7-FIX1이 새로 넣은 원시 로그 중 `t5/logs/verify-t7fix1.stdout.log`·`verify-t7fix1-r2.stdout.log`가 각 8건(빈 비고 케이스 줄의 줄 끝 공백, `verify.py` 출력 원문). 합계 7파일 35건.
- **T7-FIX2 F4 정정:** 과거의 `compare_t4_snapshot.py` 후속/r2 RC0 및 그 성공에 의존한 차이 범위 주장은 철회한다. 해당 실행의 원문 로그는 보존되지 않아 `(unverified)`·판정 근거 제외다. 보존 로그는 최초 단순 비교 RC=1이며, 이후 수정본 `.py`나 다른 old/current 실행에 연결하지 않는다.
- `git status --short` 전후 동일(새 파일은 모두 이미 미추적이던 폴더 안). `temp/tmp*` 0, `t5-runtime/tmp` 비어 있음, `mgbah` 프로세스 없음.

## 브리프 대비 어긋난 점

- `verify.py`를 리뷰 목록의 1회가 아니라 2회 실행했다(T5 REPORT 정정 뒤 manifest의 REPORT 해시 갱신). 두 실행 모두 RC=0, stdout 동일.
- `import os` 1줄 삭제는 지시 문구에 없지만, F3 변경으로 유일한 사용처가 사라져 미사용 import가 되기 때문에 같이 뺐다.
- 영구 증거 `t5/t6-verify-rerun.log`를 같은 바이트로 `t5/superseded-case13/`에 **옮겼다**(복사 아님). 정정 전 케이스 13을 PASS로 집계한 로그를 현재 경로에 두지 않기 위해서다. INDEX의 공백 메모와 `PHASE_B_QA.md` 링크를 새 경로로 바꿨다.
- T6 스크립트(`collect.py`는 대상 폴더가 있으면 거부, `validate.py` §5는 테스트 파일 변경을 오류로 봄)는 고치지 않고, 같은 로직의 사본 `update_evidence.py`·`make_index_t7.py`·`validate_t7.py`를 이 폴더에 두었다.

## 남은 위험

- 케이스 13 외 14개 케이스는 정정 전 실행 그대로다(지시대로 재실행 안 함). F1 결함은 케이스 13 스크립트에만 있었고, 다른 케이스 판정 파일의 sha는 `update_evidence.py`가 temp 원본과 다시 대조했다(불일치 0).
- 케이스 15 집계는 `runs/`의 모든 후보 `bp.log`를 다시 읽으므로 수치(116·17)가 바뀌었다. 계약 검사 로직은 그대로이고 위반 0이다.
- 실기 미검증·Link BLOCKED는 그대로(범위 밖).
- 이 보고서의 증거 사본(`evidence/t7-fix1/REPORT.md`)은 마지막 `--refresh-t7` 시점의 내용이다. 그 뒤 최종 `validate_t7.py` 재실행 로그(`validate_t7.r2.log`)는 temp에만 있다.

## 정리

띄운 에뮬레이터는 케이스 13 1개(pid 19646, exit 0)뿐이고 종료 확인. 워크트리·stash·claim·브라우저·`~/Downloads` 임시물 없음. 커밋·push 안 함. 추가 리뷰어·하위 에이전트 없음.

RECEIPT: model=claude-opus-5-5 effort=high role=code
