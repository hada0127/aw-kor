# 2편 숫자 인코딩·슬롯 초과 후속 검증 — 2026-09-21

마지막 세션의 `part2_alnum` 자동 빌드는 `현재 6000이야`가 전각 숫자 인코딩 후 17바이트가 되어 16바이트 슬롯을 넘으면서 중단됐다. 이 중단을 해소하고, 같은 원인으로 일본어 원문이 남던 `2대1이라면`도 재배치했다. 전체 캠페인 검수나 배포 완료 보고가 아니다.

## 후보와 수정

- 최종 후보: `temp/full_audit_2026-09-15/part2_alnum_complete_candidate.gba`.
- SHA-256: `12f65b063d2edf06347255625505c1a79d142dbba8ed30c0d943e27d966dfe3b`.
- 원본 ROM에서 전체 빌드, `--no-sync-outputs`. 정식 output/dist는 갱신하지 않았다.
- 숫자 확장으로 직접 쓰기 슬롯을 넘는 문구는 원본 슬롯을 임시 유지하고 정확한 번역문을 script owner로 등록한다. 기존 포인터·제어·종단 검사를 통과한 재배치 manifest의 `relocated`/`fixed`에 필수 주소가 없으면 ROM 저장 전에 실패한다.
- 편집기 override도 같은 2편 숫자 확장 조건을 검사한다. `encode_fit`으로 공백을 없애서 들어가더라도 필수 재배치 검사를 우회하지 않는다. `--no-repoint-dialogue`는 필수 행이 있으면 개발용 빌드도 실패한다.
- `qa_text_fit.py`는 실제 주소를 인코더에 전달한다. 숫자를 ASCII 길이로 계산하던 누락을 수정했다.

| 원래 주소 | 보존한 번역 | 원래 슬롯 | 재배치된 메시지 |
|---|---|---:|---|
| A0564C | 현재 6000이야 | 16 | A3F1CC |
| A0ABDC | 합계 6000 | 12 | A429D0 |
| A0B6C8 | 2일에 1번 | 10 | A4335C |
| A250EC | 2대1이라면 | 10 | A52030 |

네 문구 모두 최종 메시지 안의 `encode_full_fidelity` 결과와 바이트 일치를 확인했다. A250EC는 기존 검토 CSV의 번역을 그대로 사용했다. 이 네 장면 모두에 실제 플레이로 도달했다는 뜻은 아니다.

## 실행 증거

- 스크립트 회귀 52개 PASS. 실제 writer 추출 시험으로 override 유무·변경된 override 문구 보존·슬롯 밖 불변·fit 불가능 문구의 원본 staging·필수 재배치 누락 거부를 검사했다.
- 현재 입력과 빌드 receipt 일치 PASS.
- 바이트 무결성, 재배치 무결성, 중복 명령어, 기본 검사 PASS.
- 활성 payload 17,897개와 재배치 payload 1,932개 부호/글리프 검사 issue 0.
- 기존 결과/프롤로그 충실도 91행, 프롤로그 제어 메시지 13개 PASS.
- 최종 후보에서 기록 입력으로 콜드부팅 재생: 1편 603입력/134,320프레임, 2편 214입력/81,446프레임. 둘 다 에뮬레이터 종료코드 0. 각 21/62개 선택 체크포인트를 저장했다. 이 실행은 **모든 프레임의 캡처가 아니다**.
- 육안 확인: 2편 73,382프레임의 이동력 `3`/`6`과 대사, 2편 마지막 81,446프레임, 1편 마지막 134,320프레임. 83개 전체의 육안 승인으로 집계하지 않는다.
- 최종 후보의 2편 선택 체크포인트 62개는 직전 숫자 후보 `645656ea…7d3e`의 같은 프레임 RGB 해시와 모두 일치했다. A250EC는 이 경로 밖이므로 그 문구의 실화면 검증은 남아 있다.

정적 슬롯 QA는 overflow를 3회 집계하지만 최종 ROM의 원문 잔존 수가 아니다. A01B98와 A250EC(중복 집계)의 슬롯 부족이며 최종 manifest에서는 모두 재배치됐다. 이 도구의 `skip→원문` 표시는 재배치를 설명하지 못하므로 단독 합격/실패 근거로 쓰지 않는다.

## 화면

[수정 전 진단 화면](../screenshots/part2_numeric_fix_2026-09-21/before_diagnostic.png)은 이전 ROM의 동일 상태 진단이며 최종 콜드 재생과 증거 종류가 다르다. [최종 후보 콜드 재생](../screenshots/part2_numeric_fix_2026-09-21/after_final_cold.png)에서는 `보병은 이동력 3이지만 / 수송차는 6이나 되니까`가 표시된다.

[1편 마지막 체크포인트](../screenshots/part2_numeric_fix_2026-09-21/part1_final_checkpoint.png), [2편 마지막 체크포인트](../screenshots/part2_numeric_fix_2026-09-21/part2_final_checkpoint.png).

## 리뷰와 남은 작업

Claude 로그인 복구 후 엄격 리뷰를 세 차례 수행했다. 첫 리뷰의 override 우회와 QA 주소 누락을 수정했고, [최종 읽기 전용 리뷰](PART2_NUMERIC_FIX_2026-09-21_CLAUDE_REVIEW.md)는 이번 범위의 차단 결함 없음으로 판정했다. 리뷰 중 아직 진행 중이던 빌드의 `Needs verification`은 이후 최종 빌드·manifest·바이트 QA로 확인했다. agy는 재시도해도 인증 실패하여 외부 통과로 집계하지 않는다. Codex는 같은 범위를 자체 적대 검토하고 실행 검증했다.

모델 호출 없는 최종 후보 전 프레임 캡처와 직전 숫자 후보와의 전 프레임 비교를 추가로 실행 중이다. 상태는 `temp/full_audit_2026-09-15/part2_alnum_complete_continuation.json`, 실행은 `output/qa/part{1,2}_2026-09-21/alnum_complete_extended_replay/`에 기록된다. 이 작업의 완료와 화면 차이 검토는 아직 완료로 집계하지 않는다.

전체 캠페인·엔딩·분기, 네 재배치 문구의 미도달 실화면, 기존 1편 재배치 부채, 실기 검증은 남아 있고 배포는 보류한다. 이전 세션의 staged/unstaged 변경과 이번 수정이 동일 파일의 미완료 구현에 의존하므로 이번 단위만 분리 커밋하거나 기존 staging을 소비하지 않았다. 통합 검수 뒤 전체 변경의 커밋·push가 필요하다.

구조화 증거: [EVIDENCE.json](PART2_NUMERIC_FIX_2026-09-21_EVIDENCE.json). 상세 실행 로그와 재현 스크립트는 `temp/full_audit_2026-09-15/part2_alnum_complete_*` 및 `cold_verify_alnum_complete.py`에 있다.
