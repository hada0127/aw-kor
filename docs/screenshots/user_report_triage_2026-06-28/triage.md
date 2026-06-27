# 2026-06-28 사용자 추가 스크린샷 triage

입력 contact: `docs/screenshots/user_report_triage_2026-06-28/download_contact.png`.
원본 파일 manifest: `docs/screenshots/user_report_triage_2026-06-28/manifest.json`.
최종 확인 ROM SHA: `f95a857354a84119452b69bdabb371c6f390e0ecd4faf13bc56d5208ec1bb292`.
검증 리포트: `release_qa_report.json`.
E12 DOWN16 음성 proof 요약: `e12_b8_down16_negative_summary.json`.

| 이미지 | 판정 | 후속 처리 |
| --- | --- | --- |
| `index 0` | Part1 작전실/작전명 compact title 깨짐 계열. | 현재 ROM의 coldboot fresh 작전실 캡처에서 `전투 개시`, `첫 전투`, `전선 기지 확보`, `고물 전차 출격`이 정상 표시된다. 증거: `current_operation_room_contact.png`. |
| `index 1` | Part1 모드 선택 대형 라벨/하단 도움말 침범 계열. | 현재 ROM fresh route에서 강한 침범 재현 없음. 도움말은 `전투 방법 알려 줄게 / 와서 들어 봐`로 정상 표시된다. 증거: `current_routes_contact.png`. |
| `index 2` | Part1 `single_map`의 `??????` 3행. | 현재 ROM에서는 국소 compact-renderer hook으로 `미공개`가 표시된다. `??????` 재현 없음. 증거: `current_routes_contact.png`. |
| `index 3` | Part1 대전/작전룸 라벨 및 도움말 침범 계열. | 현재 ROM fresh route에서 재현 없음. `처음부터 대전` 표시 정상. 증거: `current_routes_contact.png`. |
| `index 4` | Part1 통신 하위 메뉴 라벨/도움말 침범 계열. | 현재 ROM fresh route에서 재현 없음. `친구와 연결해 / 대전 가능` 표시 정상. 증거: `current_routes_contact.png`. |
| `index 5` | Part1 1카드 통신 라벨/도움말 침범 계열. | 현재 ROM fresh route에서 재현 없음. `카트리지 하나로 / 모두와 대전` 표시 정상. 증거: `current_routes_contact.png`. |
| `index 6` | Part1 맵 교환 라벨/도움말 침범 계열. | 현재 ROM fresh route에서 재현 없음. `친구와 / 맵 교환 가능` 표시 정상. 증거: `current_routes_contact.png`. |

## current 판정

- 이번 7장은 기존 `2026-06-27` 사용자 신고 계열과 같은 Part1 메뉴/작전실/통신/맵 선택 화면이다.
- 현재 SHA `f95a8573...`에서는 기존 Part1 라벨 축소, 도움말 공백 복원, `미공개` 국소 hook,
  작전실 compact title 정리 패치가 적용되어 신고 화면의 직접 깨짐이 재현되지 않는다.
- `qa_visual_regions.py` PASS, `qa_part1_compact_help.py` PASS(`issue_count=0`, direct visual 23, missing direct 11, synthetic/live-code smoke 11).
- E12/E16의 잔여 direct evidence 부채는 별도 TODO로 계속 유지한다. 이번 triage는 사용자 제보 화면의 현재 재현 판정이며, compact display 전수 완료 근거는 아니다.
