검토에 필요한 자료는 모두 확보했다. 이제 결론을 정리한다.

**결론: 차단 결함 없음.** 정적 검토 범위에서 `tools/build_korean_full.py`, `tools/test_dialogue_script_safety.py`, `tools/qa_text_fit.py`의 이번 변경에 실제 차단 결함은 발견하지 못했다. 최종 판정은 진행 중 빌드의 게이트 통과 확인이 남아 있어 아래 "Needs verification" 항목으로 분리한다.

**검증한 논리 경로**

- **override 가드 범위**: `patch_script_row`(`tools/build_korean_full.py:13260`)의 `numeric_repoint`는 `is_part2_story_address && ASCII 영숫자 && raw_len > slot`으로 명시돼 있고, 참이면 원본 바이트 staging + `required_script_repoints` 등록, 거짓이고 encode_fit 실패면 예외. Part1 부채 9행은 건드리지 않는 범위 제한이 코드와 일치한다.
- **non-override overflow**: `source_text` 있고 `needs_safe_dialogue_punctuation`이면 원본 staging + 필수 등록, 아니면 예외. 원문 임시 출하 경로 없음.
- **필수 재배치 게이트**: `verify_required_script_repoints`(10699행)가 `completed_script_repoints`(manifest `relocated`의 `fixed` 집합, 20878행)와 대조해 출력 전(20913행, `atomic_write_bytes` 이전) 실패시킨다. `--no-repoint-dialogue`이면 completed가 빈 집합이라 필수행 존재 시 항상 실패하는데, 이는 의도된 제한으로 인정한다.
- **재배치 수용 조건**: 0xA250EC는 `apply_script_span_ownership`으로 owner(10B, '2대1이라면')가 되고, `_rp_dlg`는 owner 텍스트를 반환(B팀 아님: `data/bteam_addresses.json` 0건), `_rp_fixable` 참, `_rp_fit_level`은 encode_fit 실패로 99 ≥ min_level 1, 셀 폭 12 ≤ 50, `fixed_bytes`는 '２대１이라면'(제어바이트 없음). 병합중복·stray-code 게이트도 통과 가능한 입력이다.
- **제어/포인터 안전**: staging은 원본 바이트 그대로라 제어 gap 비교(`skip_control_changed`)·terminator 게이트(`orig[me-1]==0`)·`validate_script_message_span`(0x00/0x6B 금지)에 영향이 없다. 포인터는 모든 site가 테이블 엔트리일 때만 갱신된다.
- **qa_text_fit 주소 전달**: `check_text`가 `encode_fit(..., a)`로 addr을 넘기고, AST 파서가 4요소 tuple `(0xA250EC, 0xA250F6, '2대1이라면', label)`을 direct patch로 수집한다.
- **테스트**: 52건 PASS 로그 확인(`temp/full_audit_2026-09-15/part2_alnum_resume_tests.log`). `test_numeric_story_without_fitting_fallback_can_stage_original`이 원본 staging·필수 등록·override 경로를 실제 writer 함수로 검증한다.

**Needs verification (빌드 완료 후 확인 필요)**

1. `part2_alnum_complete_build.log`는 현재 스프라이트 단계 2줄까지만 기록돼 있어 repoint 통계와 `verify_required_script_repoints` 통과 여부가 아직 없다. 완료 후 `temp/repoint_manifest.json`에서 0xA250EC를 포함하는 메시지가 `relocated`이고 `fixed`에 `0xA250EC`가 있는지 확인해야 한다. 이전 manifest에는 인접 메시지 0xA25128(ptr 0xA37614)·0xA25188이 재배치됐으므로 이 구간이 테이블 커버리지 안일 가능성은 높지만, 메시지 시작 주소가 테이블 엔트리인지와 `skip_mid_ref`/`skip_ptr` 통과는 정적으로 확정할 수 없다. 실패하면 빌드가 출력 없이 중단되므로 조용한 결함으로는 남지 않는다.
2. 새 후보 ROM의 SHA가 이전 후보(645656ea)와 다름을 확인하고 `qa_text_fit`·`qa_repoint_integrity`를 새 후보로 다시 돌려야 한다. 이전 후보 로그는 재사용할 수 없다.

**비차단 관찰 (기록만)**

- `qa_text_fit`는 필수 재배치 행을 `overflow(슬롯초과 skip→원문)`으로 집계한다. 이전 후보 로그는 overflow 2였고 이번엔 3이 될 것이다. 라벨이 "원문 유지"를 뜻하므로 이제 의미가 틀리며, qa가 repoint manifest를 참조하지 않아 "staging 후 재배치됨"과 "진짜 원문 잔존"을 구분하지 못한다. `run_release_qa`의 text-fit 게이트는 종료코드만 보므로 배포 게이트에는 영향 없다. CLAUDE.md의 "텍스트 overflow 0" 문구와는 불일치하나 docs는 보류 상태다.
- `numeric_repoint`의 `raw_len`은 정규화 전 `encode_text` 길이라, `normalize_for_fit`으로 level 0에 맞을 수 있는 override도 강제 재배치된다. 과대 범위지만 커버리지 없으면 빌드 실패로 드러나므로 안전 방향이다.
- 가드가 ASCII 영숫자만 보므로 편집기 override에 전각 숫자가 이미 들어 있고 슬롯을 넘기면 staging 대신 `override overflow` 예외가 난다. 명시된 범위 안이지만 편집기 사용자에게는 비대칭이다.
- 테스트 공백: `repoint_messages`가 staged-original 라인을 `fix_addrs`로 채택하는 경로는 단위 테스트가 없고 빌드 게이트에만 의존한다. `qa_text_fit`의 AST 수집이 새 tuple을 잡는지도 테스트가 없다.

**부수 사항**: 이 세션은 plan 모드이고 파일 쓰기 도구가 없어 플랜 파일은 만들지 않았다. 요청이 읽기 전용 리뷰라 위 보고가 최종 산출물이다.
