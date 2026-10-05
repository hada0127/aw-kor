# 2026-09-22 사용량 절약을 위한 작업 정리

사용자 요청에 따라 추가 플레이/리뷰 호출을 멈추고 저장·기록을 정리했다. 목표는 여전히 **1·2편 실제 엔딩까지 플레이 검수하며 발견 결함 수정**이다. 두 편 모두 엔딩 미도달. 사용자는 Claude 재로그인 및 Chrome 로그인을 알렸고 가능한 자동 진행을 원한다. 이번 정리에서는 Chrome 세션을 검사하거나 사용하지 않았다. 재개 시 필요한 범위에서 로그인 상태를 확인한다. 정확한 주간 잔여 사용량은 확인하지 못했다.

## 현재 진행과 안전한 재개

두 메인 레코더 모두 정상 종료(exit 0). 실행 중인 게임 세션에 입력하지 말 것.

| 구분 | 진행 | 마지막 기록 | 일반 저장 영수증 |
|---|---|---|---|
| 1편 | 첫 캠페인 DAY14 승리, 둘째 전투 DAY4 중간. 자금11600 | `output/qa/part1_2026-09-22/second_day3_cold_live`, segment106/frame19029 | `temp/full_audit_2026-09-15/part1_pause_day4_save/game_save.json` |
| 2편 | M4 DAY15 A255/누적1155 승리, M5 해상 도시를 노려라! DAY1 중간. 자금4000 | `output/qa/part2_2026-09-22/naval_day1_cold_live`, segment101/frame22020 | `temp/full_audit_2026-09-15/part2_pause_naval_day1_save/game_save.json` |

메인 ROM은 `temp/full_audit_2026-09-15/naval_quote_final_candidate.gba`, SHA `17dff0c0af7a91afcefdfe80b1bf7f4e88f0ef12da2e1b6560eaf9d591d0e0e9`.
새 수정 ROM을 도입할 때 위 검증된 일반 저장으로 **cold boot**한다. 서로 다른 ROM의 state 사용 금지. 모든 실제 입력 전 프레임 무손실 기록 유지. `playthrough_capture.py` release_frames 최대1800; 긴 적 턴은 A1800 + NONE1200. temp 이외 임시물 금지. canonical ROM 3종/BPS는 미갱신.

재개 명령 형식(새 출력 디렉터리 사용):
```sh
python3 tools/playthrough_capture.py --rom temp/full_audit_2026-09-15/naval_quote_final_candidate.gba --harness temp/part1_playthrough_2026-09-15/mgbah_game_save --out output/qa/part1_2026-09-22/resumed_after_pause --game-save temp/full_audit_2026-09-15/part1_pause_day4_save/game_save.json
```
2편은 part1 경로를 part2 및 해당 영수증으로 변경. `live_status.py`, `read_live_cursor.py`, own-unit helper의 run 경로도 새 run으로 변경한다. P1 부팅: NONE1380 START180 A1260 START360 START361 A180 A1200. P2 부팅: NONE1380 START180 DOWN120 A1260 START360 START180 A1200 A1200. 입력 후 실제 화면에서 저장 복구를 확인한다.

## 전투 상태

1편: Arty8,9가 적 Mech7,8을 공격한 뒤 건강한 Tank7,9가 segment69에서 격파. City Tank8,8 HP40 공격은 취소했고 아직 행동 가능. 전방Tank11,9 HP25, APC9,9에 Infantry 탑승. Inf8,10 및5,10. factory2,9에서 APC를 구매했다(중전차를 의도했으나 메뉴 선택을 잘못 읽음, 기록 유지; 되돌리지 않음). 자금11600, factory3,10 비어 있음. 적 포대의 현재 위치 미확정. R94에서13,9는 빈 도로였다. R로 본 적만 판단하며 own-unit dump를 숨은 적 정보에 사용하지 않는다. 메뉴 선택 후120frames 확보해 세부창 갱신을 기다릴 것. P1 맵 메뉴는 부대/작전/저장/시스템/종료, 저장 index2. cursor13,9에서 저장 완료.

2편: Mech2,8→1,7, Mech4,8→2,8 대기. Lander8,12 설명42..51을 보고 대기; Tank8,10→Lander8,12 탑승62. Arty4,11→7,11 대기73. Rocket2,11 선택 시 설명이 나와 이동 입력은 아직 수행되지 않았고, 중간 선택은 취소 후 저장했다. Bship11,10, Sub11,9 잠항, Cruiser11,11, Tcop10,11, Mech9,11, Tank6,10은 이전에 사용한 상태. DAY2에 Mech9,11→Tcop10,11 탑승 후 HQ8,1 방향 진격 구상. 10,10/10,11은 모래톱이라 일반 군함 진입 불가. 적 초기 Cruiser13,6/Sub9,6/AA11,3·11,4는 현재 위치 재확인 필요. HUD 남은7일이며 실제 승리조건/진행은 플레이로 확인한다.

## 수정 결과와 남은 일

- 검증된 누적 후보17dff: 긴 미션 제목 잘림, 잠항/부상 인용부호와 연결어, 빌리 이름표, 호칭/승리/코인 대사 수정 포함. 99개 수정행/75개 대사 안전시험, 원본 일반 저장 cold 재생과 Claude 유효 지적 처리 기록은 `ENDING_PLAYTHROUGH_2026-09-21.md` 및 temp 증거 참조.
- 새 `tools/part2_remaining_days.py`: 일본어「あと7日」의 native96B만「남은7일」로 교체. 원본 loader/pointer/source SHA guard, editor 등록, 최종 freeze. 숫자/렌더러 변경 없음. 4tests PASS.
- 최신 후보 `remaining_days_guarded_candidate.gba` SHA `73e6de3ce26e09fb3c404caaa1bd8cb8987213d32a793bdce5b41faef2309894`. 메인17dff 대비 변경81B, 모두483D14..483D74 내. `remaining_days_guarded_probe_cold` 일반 저장 부팅8 및hud_left 양쪽 실제 화면을 보았고 전체 빌드와 ROM 전체 동일. 메인 플레이에는 아직 도입하지 않았다.
- Claude 리뷰는 3회 수행. 실제 prefix/suffix 경계 번짐 지적은 독립 clipping 및 prefix15열 투명 보존으로 수정. suffix는+1px 이동해 양쪽 outline 확보. 마지막 리뷰의 prefix 왼쪽 outline/픽셀시험 보강 등은 다음 재개 시 평가할 것. 원본 palette집합 동일 주장과 BL주소 오류 주장은 반증/철회되었다. **최종 출하 승인이나 엔딩 검수 완료로 표현하지 말 것.**
- 신규 확인 필요: 2편 Rocket 설명84의 `공격 범위3-5라고 해.`에 경계 공백이 없어 보임. A0907B..A09085의 `공격 범위`와 다음 강조 숫자3-5 경계. 확대 화면과 실제 payload 확인 후 필요하면 공백 추가/repoint 및 동일 정상 저장 cold로 재검수. 아직 변경하지 않음.
- 전체 전 프레임은 저장되었지만 모든 프레임을 사람처럼 시각 판정한 것은 아님. `visual_review:pending`을 임의 PASS 처리하지 않는다.

## 다음 작업 순서

1. 일수 표시 마지막 리뷰 잔여를 평가하고 필요한 수정만 수행; material 변경이면 Claude 재리뷰.
2. 최신 일반 저장에서 cold boot해 두 편 이어서 플레이. 2편 Rocket 숫자 경계 확인/수정.
3. 엔딩까지 계속 검수하되 현재 사용량 절약 중단 요청을 존중해 자동 백그라운드 플레이를 새로 시작하지 않는다.
