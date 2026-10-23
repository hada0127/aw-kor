# F1/F2 수정 증거

기준 HEAD: `6d846d9db0f2e69fff2c8e6bfe841429cc7b420f`. 실행 기기 nyarch-pc / Python 3.14. 원본은 `/home/taro1/project/aw-kor/original/Game Boy Wars Advance 1+2 (Japan).gba`를 읽기만 했으며 SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`를 확인했다. 최종 commit/diff 해시는 외부 인계 보고 `/home/taro1/weekend-20261024/aw-kor-fix-report.md`에 기록한다.

## Change together 대조

- F1: `encode_fit → encode_required_full_fidelity → encode_full_fidelity`와 직접 `patch_script_row → encode_full_fidelity`, repoint `_rp_fixed_bytes → encode_full_fidelity`가 제목 strict pair 경로를 공유한다. `normalize_korean_terms`는 유지하고 대사용 `normalize_for_fit`만 제목에서 우회한다. 직접 writer의 override 및 `_rp_dlg`의 source 선택 순서는 변경하지 않았다. CSV `A2D61C`와 보호 override의 문구 차이를 통일하지 않았다.
- 독립 기대값은 `encode_pair_title`와 공백/괄호/중괄호/세미콜론/▼/중점의 명시 바이트다. 반복 반각·혼합 전각·앞뒤 공백, 지원 부호, 미지원 중점 `·`/탭/개행/이모지/미매핑 음절 거부, 합성 보호 override 우선권, 179주소 fit 경계를 검사한다. `・`와 `·`는 다르다. 인코딩 성공을 실제 글리프 공급/화면 지원으로 주장하지 않는다.
- 직접 writer AST 실행은 원본 슬롯 보존·재배치 등록·override 우선을 확인한다. repoint 실제 콜백 AST 실행은 동일 pair bytes와 부족/충분 슬롯의 재배치 결정(6/0)을 확인한다. 전체 repoint 실행은 아니다.
- F2: 상위 REPORT와 todo에서 실제 저장 수정 주장을 예산 helper 수정으로 좁혔고 테스트명도 `test_both_editor_budget_helpers_report_title_overflow`로 바꿨다. dialogue `_save_line`의 `protected_render_region`과 scene `_save_line`의 `deny_pair_status`, 그룹 dry-run 호출은 소스로 대조했으며 두 server 파일은 수정하지 않았다.
- Optional: `trace_fit.py`가 출력한 `Q.main` 반환값을 `sys.exit(rc)`로 전달한다. 이전 증거는 수정하지 않았다.

## 실행 결과

모든 검사는 단일 프로세스, `memcap -m 2G`, 스레드 증가 없음. 총괄 heavy lease 메시지 `msg_1b8d06e2e515`를 확인했다. 시작 CPU 38.6°C, 가용 RAM 41.5GB; 열로 보류하지 않았다.

| 명령(memcap prefix 생략) | 소스 | 실제 rc | 결과/로그 |
|---|---|---:|---|
| `python3 -I tools/test_pair_title_fit_contract.py` | 기준 HEAD builder + 최종 테스트 | 1 | 9 tests / 8 failures, `red_final.log` |
| `python3 docs/reports/residual_2026-10-24/run_regression.py` | 수정 소스 | 0 | 14 tests PASS, `regression_final.log` |
| `python3 -I tools/test_editor_safety.py` | 기준 HEAD builder | 1 | 38 tests / 4 failures + 5 errors, `editor_safety_baseline.log` |
| `python3 -I tools/test_editor_safety.py` | 수정 소스 | 1 | 동일 결과, `editor_safety.log` |
| `python3 temp/residual_fix_20261024/trace_fix.py` | 수정 소스 | 0 | `trace_after.log`, 출력 위치만 새 디렉터리로 바꾼 runner |

편집기 안전성 두 로그는 실행 시간 외 전체 내용이 동일하다. 원본/후보 ROM·생성 편집기 데이터가 없는 격리 환경에서 파일 없음 및 주소 없음 실패가 발생했으며 PASS로 세지 않는다. 이 수정의 회귀로 발견된 실패는 아니지만 실제 저장/전체 안전성 실행 검증 완료를 주장하지 않는다.

최종 테스트/소스 SHA-256은 `sha256.json`, red 대상은 `red_final_sources.json`에 기록했다. 문서 주석을 다듬기 전 편집기 안전성 실행 builder 해시는 `initial_execution_sha256.json`에 보존했다. 최종 주석 수정 뒤 집중 회귀와 trace를 재실행했다. 초기 테스트 작성 중 잘못된 합성 전제를 수정한 로그는 temp의 `red.log`/`green.log`에 남기고 최종 red/green과 구분했다.

## 추적 및 보존

기존 `temp/residual_20261024/` 전체를 새 `temp/residual_fix_20261024/previous/`에 복사했으며 원본 before/after 자료는 덮어쓰지 않았다. 기준 `previous/trace.json`과 새 `trace_after.json`의 18,584 호출 입력(주소·한글·일본어·slot override)이 모두 같다. 비제목 18,396호출의 모든 반환은 불변이다.

F1 수정으로 추가 변경된 호출은 `0xA2D674`의 `토이・박스` 하나다: 기존 `91eb8fa281408cac8e47` → `91eb8fa281458cac8e47`, 즉 중점을 공백으로 바꾸던 손실을 제거했다. 두 반환 모두 level 0이다. overflow 277/263주소, wider 507/507, layout-loss 151/151 집계는 그대로다. `trace_comparison.json` 참조. 앞선 수정의 4개 변경 및 기준 273/259 → 277/263 이력과 혼동하지 않는다.

## 검토 한계

자체 적대 점검: 제목만 early return하며 비제목 분기는 불변, 미지원 입력은 strict 예외, 새 쓰기/네트워크/공유 상태/배포 경로 없음, 저장 gate 불변을 확인했다. 소스/테스트/문서만 수정했다. 전체 빌드·폰트 생성·후보 ROM·최종 제목 글리프 검사·원본 대비 화면·실기는 실행하지 않았다. b44/full/final/title_test/dist 및 번역 데이터는 불변이다.

독립 델타 리뷰 PENDING. 사용자 지시대로 Claude·nested worker를 호출하지 않았다. 실행 주체는 Codex이며 이 세션에서 실제 serving model ID/effort를 확인할 수 없어 임의 모델 영수증을 만들지 않았다.
