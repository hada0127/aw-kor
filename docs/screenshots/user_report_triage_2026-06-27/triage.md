# 2026-06-27 사용자 추가 스크린샷 triage

입력 contact: `docs/screenshots/user_report_triage_2026-06-27/download_contact.png`.
최종 확인 ROM SHA: `fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093`.

| 이미지 | 판정 | 후속 처리 |
| --- | --- | --- |
| `user_00.png` | Part1 작전실/작전명 표시 결함 계열. ROM 표시문은 compact title/repoint 우선순위 수정으로 정상화됐지만, scene editor checkpoint가 stale savestate라 깨진 캐시를 다시 보여 주는 문제가 남아 있었다. | `41_part1_operation_room`을 coldboot fresh nav로 전환. 증거 `temp/scene_screenshots/41_part1_operation_room_patched/frame.png`. |
| `user_01.png` | Part1 모드 선택 대형 OBJ 라벨이 하단 도움말을 강하게 덮던 이전 결함. | compact OBJ 라벨 수정 후 current fresh route에서 강한 침범은 재현 안 됨. 후속으로 하단 도움말 자체의 공백 없는 임시 문구도 `전투 방법 알려 줄게` / `와서 들어 봐`로 정리. `qa_visual_regions.py` PASS. |
| `user_02.png` | `single_map`의 `??????` 3행. | 원본 `？` placeholder 데이터라 한글 fallback은 아니었지만, 사용자 체감상 깨진 문장처럼 보여 현재 ROM에서는 `미공개`로 교체 완료. 증거 `docs/screenshots/part1_single_map_unknown_label_fix_2026-06-27/contact.png`. |
| `user_03.png` | Part1 대전/작전룸 라벨 도움말 침범 계열. | current fresh route에서 강한 침범은 재현 안 됨. 도움말 문구는 `처음부터 대전` 등 공백 있는 표시로 후속 정리. |
| `user_04.png` | Part1 통신 하위 메뉴 라벨 도움말 침범 계열. | current fresh route 및 scene capture에서 강한 침범은 재현 안 됨. 도움말 문구는 `친구와 연결해` / `대전 가능` 등으로 후속 정리. |
| `user_05.png` | Part1 멀티카드 통신 라벨 도움말 침범 계열. | compact OBJ 라벨 수정 범위로 닫힘. 하단 도움말 공백도 후속 복원. |
| `user_06.png` | Part1 통신/맵 교환 라벨 도움말 침범 계열. | compact OBJ 라벨 수정 범위로 닫힘. 하단 도움말 공백도 후속 복원. |

추가 전수 contact sweep에서 사용자 스크린샷과 직접 겹치지 않지만 같은 stale 캡처 계열인
`scene_19e7_part1_hoip_co_weather_help`, `scene_19f_part1_extra_story`,
`scene_29_part2_result_summary`도 current ROM 재진입 checkpoint로 교체했다.
`scene_29`는 `0x59DA5C` full-sheet 보존형 패치로 결과 요약 라벨의 원본 조각 누수를 제거하면서
점수 숫자/랭크 타일은 유지하도록 수정했다.

2026-06-27 후속 재확인: SHA `3e3bae33…` 기준 `tools/capture_scene_screenshots.py`로 stale scene screenshot
58개를 재캡처했고, `tools/audit_scene_entrypoints.py --strict` 결과 missing/stale 0, critical 0이다.
따라서 위 판정은 최신 output ROM의 UI 에디터 screenshot provenance 기준으로도 유지된다.

2026-06-27 추가 후속: SHA `b9eea881…` 기준 Part1 메뉴 도움말 `0xDFA64A..0xDFA9E9`의 화면 전용
공백 없는 임시 문구를 자연스러운 짧은 문구로 교체했다. 증거는
`docs/screenshots/part1_menu_help_spacing_2026-06-27/contact.png` 및
`docs/screenshots/part1_menu_help_spacing_2026-06-27/help_crops_4x.png`에 보존했다.
Claude/agy 리뷰 후 current fresh route 30프레임(mode/operation/single/link)을 추가로 캡처해
`docs/screenshots/part1_menu_help_spacing_2026-06-27/full_sweep_contact.png`에 보존했다.
후속으로 `tools/qa_part1_compact_help.py`를 추가해 이 범위 34개 override의 current ROM bytes/level 0 fit/
보수 폭/1바이트 printable 부재를 배포 게이트에서 검사한다.
`single_map`의 `??????`는 여전히 원본 `8148` x 6 placeholder로 판정한다.
campaign/hidden/player-count 등 진행도 조건이 필요한 Part1 도움말은 `todo.md` E16에 잔여 검증으로 남겼다.

2026-06-27 추가 후속 2: AW1 진행도 save를 `loadtempsav` 후 coldboot 메뉴로 진입하는 route를 추가해
전적/맵 디자인/shop 도움말 direct evidence 5건(`0xDFA68C`, `0xDFA71B`, `0xDFA72E`,
`0xDFA6E2`, `0xDFA6FB`)을 확보했다. shop은 AW1 8495-front tempsav에서 `DOWN` x8 후
최종 프레임이 해당 도움말을 보여 주는 경우만 승격했고, raw watch의 중간 메뉴 hit는 증거로 세지 않았다.
증거는 `docs/screenshots/part1_unlocked_menu_help_2026-06-27/`에 보존했다. 또한 `맵 디자인`/`맵 기록` 등
non-`싱글 대전`/`통신` Part1 submenu 라벨을 저프로파일 렌더로 바꿔 도움말 침범을 줄였다.
최종 output/dist SHA는 `dee641f76e9c450cbc7d73e8f1b4d7160faa432c2e4d85518f5b81ea94ea4484`이며,
`verify_dist_integrity.py`와 release QA는 PASS다.

2026-06-27 추가 후속 3: 위 route 탐색 중 사용자 원본 contact에는 없던 별도 실제 결함을 발견했다.
Part1 `싱글 대전 -> 룰 설정` 원형 버튼에 `サクテキ/テンキ/収入/日数/ユウセイ/能力/アニメ`와
`アリ/ランダム/ナシ/タイプA` 값이 일본어 OBJ로 남아 있었다. Part2 룰 요약 raw OBJ가 아니라
Part1 전용 LZ77 block `0x00C2C6EC`로 확인했고, 라벨 7개/값 9개를 한글 OBJ로 렌더 후 재압축했다.
증거는 `docs/screenshots/part1_rule_circle_labels_fix_2026-06-27/`에 보존했다.
최종 output/dist SHA는 `c1d1b28909d318373a58603d08f2bdf55e9a774af960a8cbee61902a38957280`이며,
release QA, editor API, Chrome CDP, dist integrity 모두 PASS다.

2026-06-27 추가 후속 4: `single_map`의 `??????`는 원인상 원본 placeholder였으나,
사용자 보고 화면에서는 깨진 텍스트처럼 보이는 UX 결함으로 처리했다. 일반 한글 예약코드와 compact kanji 우회는
해당 리스트 renderer에서 blank가 되어 실패했다. 전역 `ガ/ギ/グ` remap은 다른 가나 표시와 name-grid 슬롯 충돌
위험 때문에 폐기했고, 최종적으로 `0x00DF8C2A`를 `？` 3개+전각공백 3개
(`814881488148814081408140`)로 바꾼 뒤 `0x08B1319C -> 0x08F30600` 국소 compact-renderer hook이
source pointer `0x08DF8C2A/2C/2E`에만 `미/공/개` 타일을 복사한다. fresh mGBA route에서
`미공개` 표시를 확인했고, 증거는 `docs/screenshots/part1_single_map_unknown_label_fix_2026-06-27/contact.png`와
`map_unknown_label_crop_4x.png`에 보존했다. 최종 output/dist SHA는
`fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093`이며,
`python3 tools/verify_dist_integrity.py`와
`python3 tools/run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_single_map_unknown_label_safe_hook.json`가 PASS다.

검증 명령:

```bash
python3 tools/capture_scene_screenshots.py --force --checkpoint 41_part1_operation_room
python3 tools/build_scene_catalog.py
python3 tools/audit_scene_entrypoints.py --strict
python3 tools/audit_scene_catalog.py --strict
python3 tools/run_release_qa.py
python3 tools/run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_single_map_unknown_label_safe_hook.json
python3 tools/run_release_qa.py --only-editor --editor --timeout 300
python3 tools/run_release_qa.py --only-editor --cdp --timeout 300
python3 tools/verify_dist_integrity.py
```
