# 예/아니오 확인창 추가 검수

- ROM SHA: `83ae254bf25fc938bb5dd7825955637ebbce2c7370c0d615c89cebf65b2ba646`
- 최종본 전체 시트: `yesno_final_screen_sheet_after_fix.png`
- 최종본 하단 crop: `yesno_final_bottom_crops_after_fix.png`
- 초기 프레임 crop: `yesno_final_early_frame_crops_after_fix.png`
- 이름 확인 원본/최종 fresh 비교: `name_confirm_fresh_original_vs_final_after_fix.png`
- 기계 판정/주소 watch: `report_after_fix.json`

| 화면 | 재현 경로 | 실제 read-watch | 판정 |
|---|---|---:|---|
| 1편 이름 확인 | coldboot fresh → 이름 입력 → OK | `D8273C` 4회, `D835BC` 4회 | 수정 후 `▷예 아니오`, `예▷아니오` 모두 글자 가림 없음 |
| 전투 메뉴 항복 확인 | system menu `DOWN,A` | `A34B6C` 23회 | 초기/LEFT/RIGHT 모두 흔들림 없음 |
| 전투 메뉴 모드 복귀 확인 | system menu `DOWNx4,A` | `A34B6C` 23회 | 초기/LEFT/RIGHT 모두 흔들림 없음 |
| 89a 항복 확인 pre-state | pre-surrender state + `A` redraw | `A34B6C` 21회 | 초기/LEFT/RIGHT 모두 흔들림 없음 |

## 이름 확인 수정 근거

`D835BC`를 일반 row처럼 바꾸는 후보들은 실패했다. `copy_A34B6C`는 후속 글자가 새고, `generic_942CC4`/`lead1_gap2_full_no`는 RIGHT 선택에서 커서가 사라졌다. 후보 시트는 `name_d835bc_candidate_sheet.png`.

VRAM diff에서 이름 확인 초기 상태는 cursor tile `A1BA/A1BB`가 BG tilemap x7에 있고, RIGHT 후에는 x7이 blank가 되지만 x9에 cursor가 새로 그려지지 않았다. 그래서 `PART1_YESNO_HOOK` 끝에 조건부 보정 helper를 추가했다. x7에 yes cursor가 없으면 x9에 `A1BA/A1BB`를 복구한다. 보정 후보 시트는 `name_cond_cursor_candidate_sheet.png`.

## 검증

- `python3 tools/build_korean_full.py`
- `python3 tools/qa_transient_overlays.py`
- `python3 -m py_compile tools/build_korean_full.py tools/qa_transient_overlays.py`
- `python3 tools/qa_visual_regions.py --harness temp/mgbah --action-menu-save ''`
- `python3 tools/verify_dist_integrity.py`
- `python3 tools/run_release_qa.py --timeout 300 --report temp/release_qa_report_yesno_dist_sync_20260706_after_scene.json`
- `git diff --check`

후속 배포 재동기화도 완료했다. `dist/manifest*.json`, 2026-07-06 BPS/IPS, compact visual matrix, Part1 link sweep, scene residual evidence를 모두 ROM SHA `83ae254bf25fc938bb5dd7825955637ebbce2c7370c0d615c89cebf65b2ba646` 기준으로 맞췄고, `verify_dist_integrity.py`와 release QA가 PASS했다.
