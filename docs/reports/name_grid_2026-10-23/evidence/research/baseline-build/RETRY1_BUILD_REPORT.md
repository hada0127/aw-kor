# T0 기준 후보 재현 RETRY1

트랙: bounded. 기존 소스 재현이며 새 기능 구현이 아니다.

- source: `git archive HEAD`, `90908180938c2bf40ee38dea43c4c1304b09df8a`. `.git` 없는 snapshot을 `source/`에 보존했다. 추출 직후 모든 tracked 입력의 SHA가 부모와 같았다.
- Python 3.9.6 / Pillow 11.3.0. 복구한 절대 폰트 경로를 그대로 사용했고 이전 입력 기록의 폰트 SHA와 일치했다. 전체 입력 SHA는 `RETRY1_METADATA.json`에만 보존했다.
- 부모의 2026-10-23T05:28UTC 전체 빌드 부재 확인을 근거로 실행했다. 자식 ps 불가를 새 gate로 만들지 않았다. snapshot의 기존 EDITOR_LOCK을 코드 변경 없이 사용했다.
- 후보: `/Users/konest/project/aw-kor/output/game_wars_korean_namegrid_baseline_20261023.gba`
- 후보 SHA-256: `ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a` (source/후보와 부모 output/후보 동일). b44 동일성 주장은 하지 않는다.
- 빌드 1회, exit 0. 지정 QA 5종 모두 exit 0. 실화면/실기/이름 조합 ROM 통합은 (unverified).

실행 cwd는 모두 `source/`, Python 실행기는 `/Applications/Xcode.app/Contents/Developer/usr/bin/python3`다.

```text
nice -n 15 python3 tools/build_korean_full.py --out output/game_wars_korean_namegrid_baseline_20261023.gba --no-sync-outputs --report temp/encode_report.csv
EXIT 0
python3 tools/phase6_basic_test.py output/game_wars_korean_namegrid_baseline_20261023.gba
[OK] ROM passed pre-flight checks
EXIT 0
python3 tools/qa_integrity_map.py --rom output/game_wars_korean_namegrid_baseline_20261023.gba --map temp/integrity_map.json --byte-only
[OK] 바이트 무결성: 기대 577856바이트 중 불일치 0
EXIT 0
python3 tools/qa_text_fit.py --rom output/game_wars_korean_namegrid_baseline_20261023.gba --map temp/integrity_map.json --manifest temp/repoint_manifest.json
layout-loss fallback(level>=6, 재배치 검토): 152
overflow(슬롯초과 skip→원문): 273
visual-wider than JA: 507 (2.8%)
final-ROM protected non-Korean: 0/485 ()
EXIT 0
python3 tools/qa_bteam_drift.py --rom output/game_wars_korean_namegrid_baseline_20261023.gba --map temp/integrity_map.json --repoint-manifest temp/repoint_manifest.json
B팀 최종 ROM 검사: 3340개, mismatch 114개 (listed residual 103, deferred 11, unlisted 0)
[HARD-OK] B팀 권위문 drift 0
EXIT 0
python3 tools/qa_part2_name_grid_shared_glyph.py output/game_wars_korean_namegrid_baseline_20261023.gba
PASS shared Part 2 dash 0x815B pixels: be419dc0b96ddc2fa1d67385f46909c1ea950eafaeba5fa59816cde935bc2bba
EXIT 0
```

게이트 exit 0은 잔여 문제 0을 뜻하지 않는다. B팀 114건은 이 소스의 gate가 listed/deferred로 분류한 결과다. 각 주소·baseline·실제 ROM 문구·cause·decision은 같은 gate의 `--json temp/retry1_bteam_details.json` 재실행(exit 0)으로 보존했다. JSON decision은 DEFER 11 / ALIGNMENT_RESTORE 1 / RESTORE_BASELINE 97 / NEW_STRICT_MISMATCH 5다. NEW_STRICT_MISMATCH라는 기존 분류 이름을 이번 재시도가 새로 만든 결함이라는 뜻으로 해석하지 않는다. 과거 ROM과의 개별 회귀 비교는 (unverified). overflow/폭 위험도 그대로 기록하며 이 작업에서 소스/데이터를 수정하지 않았다. phase6은 정적 pre-flight이며 에뮬레이터 부팅 증거가 아니다.

변경 파일: 부모에는 요청한 별도 후보와 본 영역 retry1 스크립트·로그·보고·metadata, source snapshot만 생성했다. snapshot의 tracked 유래 입력은 빌드 후에도 전부 동일하다(부수 data 2파일도 재생성 결과 SHA 동일). tools 코드는 모두 동일하다. 같은 실행의 `source/temp/integrity_map.json`, `repoint_manifest.json`, `encode_report.csv` SHA를 metadata에 기록했다. 이전 BUILD_REPORT/OUTPUT_METADATA/rawlog는 보존했다.

보호 검증: `parent_tracked_unchanged=true`, `protected_unchanged=true`, `previous_evidence_unchanged=true`. 부모 `git status --porcelain=v1` 빈 출력/exit 0, `git diff --exit-code` exit 0. 원본·정본 3종의 존재 여부까지 포함해 전후 동일, dist 해시 동일. 부모 temp 지도는 사용/변경하지 않았다. 추가 워커·리뷰·commit·push 없음.

PLAN 대비 어긋난 점: `nice: setpriority: Operation not permitted`로 우선순위 낮추기는 적용되지 않았다. builder는 그대로 계속 실행되어 exit 0이며 반복 빌드하지 않았다.

정리: 실행 세션 61004는 exit 0으로 종료했다. source와 증거는 후속 runtime QA를 위해 지시대로 보존한다. harness-session-check의 D1 0건; B10 증거 읽기 및 보고 공유 락 검사 실패, ps 검사 불가 참고가 있다. 보고된 Downloads 2건은 본 작업이 만든 것이 아니며 건드리지 않았다.

후속 반영: 없음 — tracked 수정 금지와 T0 재현 범위에 따라 본 보고서에만 기록했다.
