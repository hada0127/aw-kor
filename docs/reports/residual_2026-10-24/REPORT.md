# 2026-10-24 잔여 첫 증분 — 제목 슬롯의 손실 허용 수정

상태: **소스 수정·회귀 검증 완료, 독립 리뷰 및 후보 ROM/런타임 검증 대기. 미병합·미배포.**
기준 소스 `420e61657e5c9fad4307b5cf81940bd79d6a1eae`, 브랜치 `hada0127/weekend-aw-kor-residual-20261024`.
격리 체크아웃 `/home/taro1/orca/workspaces/aw-kor/weekend-aw-kor-residual-20261024`만 편집했다.

## 집합과 원인

[주소별 집합·발생 횟수](residual_sets.json)는 이름 입력 T4의 tracked 증거를 읽고 현 소스 `qa_text_fit.main`의 실제 `check_text` 반환을 추적해 재구성했다. 기존 overflow/wider 주소별 발생 횟수와 정확히 일치한다. layout-loss 주소 집합은 기존 증거에 없으므로 **이번 기준 소스 재실행에서** 복구했다. 이름 입력 기능을 재빌드하거나 수정하지 않았다.

| 분류 | 기준 이벤트 | 기준 고유 주소 | 수정 후 이벤트 / 고유 주소 |
|---|---:|---:|---:|
| B팀 최종 ROM 불일치 | 114 | 114 | 재검사 안 함; 해결 주장 없음 |
| overflow | 273 | 259 | 277 / 263 |
| wider | 507 | 507 | 507 / 507 |
| layout-loss(level≥6) | 152 | 152 | 151 / 151 |

B팀의 결정 분류는 RESTORE_BASELINE 97, DEFER 11, NEW_STRICT_MISMATCH 5, ALIGNMENT_RESTORE 1이다. compact 고정 UI·후행 writer 축약, 조각 정렬·보류, 에디터 아이콘 앞 공백 같은 서로 다른 원인이 섞여 있다. 판단 기준이나 보호 문구를 변경하지 않았다.

273 overflow는 13주소에서 27번 호출되어 14건 중복이 있다. 슬롯 기준 실패가 최종 ROM의 일본어 잔존을 뜻하지는 않는다. 후행 writer와 재배치가 있으므로 최종 포인터/manifest 검사가 별도로 필요하다. wider 역시 원문과 시각 폭 비교이지 실제 창 넘침 판정이 아니다. layout-loss는 축약·공백 삭제 후보를 선택한 소스 검사이며 최종 ROM 손실 건수와 동일하지 않다.

## 선택한 결함과 수정

`encode_fit('해 VS 공!', 10, ..., 0xA2D7D4)`가 level10, `92bb82758272886d8149`를 반환했다. 두 공백을 지운 `해ＶＳ공！`이므로 제목 보존 계약을 위반한다. 완전한 두 바이트 제목은 14바이트다. 두 실제 소비 함수 `dialogue_editor.server.validate_build_fit`와 `scene_editor.server.build_fit_budget`가 이것을 저장 가능으로 판정했다. `dialogue_fit_warning`은 제목 경로에 경고도 주지 않는다.

기존 `patch_script_row`와 repointer는 이미 제목 전체를 보존하고 재배치를 요구한다. 공용 fit 경로도 기존 `is_pair_title` 판정과 `encode_required_full_fidelity`를 사용하도록 1개 조건을 넓혔다. 제목이 슬롯을 넘으면 `(None, 99)`를 반환한다. 제목·공백·부호·폰트·임계값·재배치 로직은 바꾸지 않았다.

실제 전체 검사에서 바뀐 호출은 아래 네 개뿐이다. 기존 최종 ROM에 이 네 제목이 손실되어 있다고 주장하지 않는다. **입력/편집기 판정의 실제 결함 수정**이며 최종 ROM 재배치 보존 여부는 후속 검증 대상이다.

| 주소 | 문구 | 슬롯 | 수정 전 | 수정 후 |
|---|---|---:|---|---|
| A2D7D4 | 해 VS 공! | 10B | level10, 공백 2개 손실 | 14B 필요, 거부 |
| A2D61C | 산악의 결사행! | 14B | level1, 느낌표 손실 | 16B 필요, 거부 |
| A2D698 | 변경을 되찾아라! | 16B | level1, 느낌표 손실 | 18B 필요, 거부 |
| A2D5A0 | 해상 도시 공략! | 16B | level1, 느낌표 손실 | 18B 필요, 거부 |

## 실행과 증거

기기 nyarch-pc / Python 3, 기준 revision 위 SHA + 이 변경. 원본을 기존 프로젝트에서 읽기 전용으로 찾았고 SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` 일치를 확인했다. 원본 경로는 `/home/taro1/project/aw-kor/original/Game Boy Wars Advance 1+2 (Japan).gba`. 다른 체크아웃에 쓰지 않았다.

- 수정 전 `python3 -I tools/test_pair_title_fit_contract.py`: **exit 1**, 4 tests / 174 subtest failures. `temp/residual_20261024/test_before.log` 보존. 이후 실측 느낌표 3건 테스트를 추가했다.
- 수정 후 `python3 -I tools/test_pair_title_fit_contract.py`: 처음 4 tests **exit 0**, `test_after.log`.
- 최종 `memcap -m 2G -n aw-residual-test -- python3 temp/residual_20261024/regression.py`: **exit 0**, **10 tests**. 신규 5개 + 기존 QA CLI 3개 + 기존 제목 실제 writer/인코더 2개. [실행 로그](regression.log). 테스트 runner는 `B.P.ROM`만 위 읽기 전용 원본 경로로 지정한다.
- `python3 temp/residual_20261024/trace.py`: 기준 소스 **exit 0**, 기존 stdout의 273/507/152 재현. `trace_before.json` / `trace_before.log` 보존.
- `memcap -m 2G -n aw-residual-trace -- python3 temp/residual_20261024/trace.py`: 수정 후 **exit 0**, 277/507/151. `trace.json` / `trace_after.log` 보존. 재실행용 [추적 스크립트](trace_fit.py)는 체크아웃 루트에서 실행하고 먼저 `mkdir -p temp/residual_20261024` 한다.
- `python3 temp/residual_20261024/summarize.py`: **exit 0**, 추적 전후의 호출 주소·입력 일치 및 기존 overflow/wider 집합 일치 assertion, 변경 호출 4개. 집합 JSON의 해시로 tracked 입력을 고정했다.
- `git diff --check`: **exit 0**.

총괄이 02:21 heavy lease를 명시 부여했다. memcap 작업 전 CPU 39.6°C, 가용 RAM 약39.7GiB; 단일 프로세스, 스레드 증설 없음. 발열로 보류한 작업은 없다. 전체 ROM 빌드·에뮬레이터·폰트 생성은 실행하지 않았다.

## 적대 자체 점검 및 남은 검증

- 범위/회귀: 네 실측 호출 외 전체 fit 반환 불변. 기존 제목 writer 회귀는 원본 바이트를 보존하고 필수 재배치 등록을 확인한다. native 179개 제목 주소의 경계 fit, 구 주소대 바깥 제목, 두 편집기, 비제목 기존 fallback을 검사했다.
- 실패/보안: 기존 엄격 인코더의 unmapped 예외를 유지한다. 새 파일 쓰기·포인터 쓰기·공유 상태·권한·네트워크·배포 경로를 추가하지 않았다.
- 제약: 합성 문구를 179개 주소에 적용한 검사는 정책 경계 검사이며 실제 179제목의 화면 통과 증거가 아니다. 모든 편집기 HTTP 저장 흐름/브라우저 UX를 실행한 것은 아니다.
- **독립 리뷰 PENDING**: OPERATING-CONTRACT.md의 월요일08:00 전 Claude 금지, 이 dispatch의 nested worker 금지를 준수했다. 총괄이 별도 Codex/Astra 리뷰를 배정해야 한다. 자체 점검을 독립 승인으로 세지 않는다.
- **최종 ROM/런타임 검증 PENDING**: 원본 ROM은 확보했으므로 자산 부재로 막혔다고 주장하지 않는다. 이번 bounded increment에서 후보 빌드·최종 B팀/포인터 검사·원본 대비 화면 캡처는 미실행이다. 후보 배포/최종 완료 주장은 이 검증과 리뷰가 끝날 때까지 차단한다. b44/output/dist는 불변이다.
- 총괄 통신: 지정 heartbeat 명령이 실제 CLI 실행 identity를 coordinator로 판정하여 exit 1로 거절됐다. 다른 발신자를 사칭하지 않았다. 마지막 worker_done도 지정 명령을 정확히 한 번 시도하고 거절 시 오류를 보고한다.
