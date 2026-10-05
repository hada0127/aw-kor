> **중단 상태:** Codex 사용량40% 도달로 정상 저장·종료 완료. 1편 DAY31, 2편 M8 DAY2. 새 작업·자동 재개 금지. [최신 인계](SESSION_HANDOFF_2026-09-23_QUOTA40.md). 아래는 검증과 진행의 이력이다.

# 2026-09-23 정적 검사·문맥 검토·짧은 재현

사용자 승인 순서는 최종 ROM 전수 검사 → 문맥 검토 → 관련 화면 짧은 재현 → 남은 전체 플레이다. 두 편 엔딩은 미도달이며 배포하지 않았다. Codex 사용률 40% 이상이면 저장·인계 후 중단한다. 마지막 확인 39% (2026-09-23 18:02 KST); 40%에서 저장 후 중단한다.

## 정상 플레이 보존

- 1편 세 번째 전투 DAY30, 정상 저장 checkpoint840/frame151355. `output/qa/part1_2026-09-23/mission3_day16_round8_cold_live` 입력 없이 대기.
- 2편 M7 승리 후 M8 DAY2, 정상 저장 checkpoint266/frame85850. `output/qa/part2_2026-09-23/round8_m7_live` 입력 없이 대기.
- 두 본선 ROM은 round8 `8a9dfa35e8eada035f9abe103459e5b77a4cb39594010e1cdd6b81990346bf41`. 후보 진단을 본선 진행으로 집계하지 않는다.

## round12 확인 범위

후보 `temp/part2_2026-09-23/round12/candidate.gba`, SHA256 `a73f32b993cca220b89e774d4339de2667cb4f68108f29aea4302fbdcdd5c223`.

- 240개 등록 수정행의 전체 payload와 다음 원본 경계 통과. 그러나 전체 메시지 제어 비교 4건은 실패했다. D8FE00/D913AC/D9169C/D98DF0의 기존 넓은 writer가 강조 제어를 삭제한 것이므로 전체 QA 통과 후보가 아니다.
- 빌드 입력 receipt, 무결성/재배치, 18,079개 활성 payload와 1,996개 재배치 payload의 부호·글리프 검사 통과. 42개 소개 포인터·84개 전체 소개 문구, native 제목179개 중 strict pair121개 통과. PCM 충돌3곳의 샘플·드라이버 원본 보존 확인. 남은 lossless 보류7개는 해결로 집계하지 않는다.
- 2편 native 포인터3315개 중 story2276메시지/6086합성줄을 검사하여 구조·active제목pair 오류0. 실제 소비 렌더러 근거가 있는 것은 별도 검증목록의 A01D24 한 메시지다. 긴줄 후보10개, native제목58개 및 다른 UI경로는 미검증. 나머지851개 포인터는 별도 임시검사에서 범위·종료만 확인했으며 의미/렌더/글리프 완료 주장이 아니다.
- 6어형으로 선별한 부정·조건·주체 문맥74개 후보의 개별 검토를 마쳤다. 후보군 외 인접 중복1건도 별도 발견했다. 전체 번역의 의미 검수가 완료됐다는 뜻은 아니다. 단순 문자열 치환 규칙으로 번역을 변경하지 않는다.

## 실제 화면

동일 후보를 일반 저장 SRAM에서 cold boot하여 입력을 재생했다. 다른 ROM의 savestate를 재사용하지 않았다.

- 1편 첫 전투 훈련의 대기/바주카 안내4장면: seed operation room에서148입력·34146frame, boot 포함37877frame. '대기하면 못 쓰러뜨려', '바주카병 무서움을 느껴 봐!', '바주카병이라도 수는 우리가 더 많아!' 표시 확인. 산 설명 첫 줄의 '산은 보병은2'는 여전히 결함으로 남아 다음 수정에 포함했다. 실제 글자 강조색 변화까지 확인했다고 주장하지 않는다.
- 2편 M7 승리 저장에서 M8 구매창61입력·29089frame. 시야/이동 및 보병/차량/헬기/비행기 분류4개 표시와 아이콘 확인. 15개 패치 자산의 나머지 화면은 아직 관측하지 않았다.
- [스크린샷 색인](../screenshots/continuation_2026-09-23/round12_screenshot_index.json), [1편 입력·ROM·저장 증거](../screenshots/continuation_2026-09-23/round12_runtime_p1_bazooka_retry_evidence.json), [2편 증거](../screenshots/continuation_2026-09-23/round12_runtime_m8_purchase_evidence.json).

## 다음 후보 준비

원본 제어를 밖에 남기는 순수 앞뒤 조각7개로 위4메시지를 복구했다. 가운데 공격/보병4개는 기존 고정 writer 소유권을 유지한다. 산 설명은 '예를 들어, 산에선 보병은 2가 들어'로 조사 중첩과 서술어 누락을 바로잡았다. 별도 2편 문맥 검토에서 확정한8조각(7개 순수 operand + 기존 fixed writer1개)을 추가 반영했다. 아직 이 소스로 빌드/실화면 검증하지 않았으며 round13에서 수행한다. 앞선47개 편집기 주소의 현재값·단일행·그룹·편집권한·슬롯 일치 확인 완료. 마지막3개 순수 operand를 더해 재확인한다.

지형 이동유형7개는 아이콘을 보존하면 기존32px에 완전한 단어를 넣기 어려워40px 배치와 BG꼬리 타일을 임시 시제품으로 준비한다. 원본 BG메모리 소유권·입장/퇴장 복구 및 비용 숫자 위치를 검증한 후에만 생산 통합한다. 임시 cave 삽입을 제품 완료로 집계하지 않는다.

무거운 빌드/재생은 한 번에 하나, 낮은 우선순위로 실행한다. 정적 분석과 읽기 전용 리뷰만 병렬화한다. Claude 엄격 리뷰를 수행하며 새 유효 결함은 수정 후 재검증한다. agy는 이전 OAuth 만료로 사용할 수 없어 추가 로그인하지 않았다.

## round13 통합 결과 (16:38 KST 추가)

후보 SHA256 `fd0b27949308a2293b81bbdba58f284400582e5c89647d8fafafa5a31a91c9b2`, `temp/part2_2026-09-23/round13/candidate.gba`. 생산 입력 동결 후 빌드·QA exit0. 등록 수정행254개 전체 payload/다음경계와 전체 메시지 제어, 목표42개 제어 통과. 이전 round12 네 메시지 제어 실패를 해소했다. 18,094개 활성 payload/1,996개 재배치 payload 부호·글리프 issue0, 소개84개/제목strict121개, PCM3개 원본보존 통과. 고정4단어의 실제생산 writer와강조경계 및 재배치된 조、4B도 별도 최종ROM에서 확인했다. 두 차례 Claude 읽기 후속리뷰 exit0에서 확정 출력결함 없음. 권고 중 옛 whole override/죽은 조사writer를 정리했다.

정상 SRAM cold의37877frame 짧은 재현에서 산 설명 '예를 들어, 산에선 보병은 2가 들어 / 하지만, 바주카병은 1이면 돼.'와 대기·바주카 안내3장면을 확인했다. 별도 정상 새게임27830frame에서 '지금 공격할 상대는 하나뿐 / A 버튼으로 전투 시작해!' 전체 문구·끝부호 확인. [산 설명](../screenshots/continuation_2026-09-23/round13_p1_mountain.png), [공격 안내](../screenshots/continuation_2026-09-23/round13_p1_attack_instruction.png), [정상저장 재현 증거](../screenshots/continuation_2026-09-23/round13_p1_evidence.json), [새게임 증거](../screenshots/continuation_2026-09-23/round13_p1_attack_evidence.json). 색 강조의 실제 시각효과나 미방문 문구까지 승인한 것은 아니다.

편집가능50주소의값/슬롯/단일행/그룹 일치 확인. fixed A22FFC 편집기 행은 이전 빌드 무결성맵에서 만든 '코,'를 보일 수 있어 다음 metadata 갱신 시 새 ship_ko를 반영해야 한다. 이 행은 읽기전용이며 새ROM 출력은 조、로 확인했다. 입력 동결 중에는 metadata를 바꾸지 않았다.

긴줄10후보 중 A0AB20은 과거 `max_cleared_cold_live` source52/frame29104 원화면에서마침표까지 보였다. round12와49B payload·native21영역/A3연결2영역·한글glyph40736B/table17316B/nativefont97896B동일. 증거는 `temp/part1_2026-09-23/static_audit/p2_width_routes/`. 현재ROM직접런타임이나consumerPC증거로승격하지않고 불필요한재생우선순위를낮추는근거로사용한다. 다른9는제한된720snapshot미발견이다.

최신 재개용 정상저장: `temp/part1_2026-09-23/mission3_day30_round8_save/game_save.json`, `temp/part2_2026-09-23/m8_day2_round8_save/game_save.json`. 원래checkpoint전체검증 후같은ROM에서프레임전진없이export했다. 새ROM에선이SRAM으로cold boot하고화면에서진행을확인해야한다.

## 본선 보존 및 지형 메뉴 전환 검증 (17:20 KST 추가)

두 본선은 round13 fd0b2794 정상 SRAM cold로 전환했다. 1편 새 checkpoint7/frame4933(세션14991)은 이전 DAY30 저장의 부대10개 전체 상태·자금54800·지도 배치와 일치한다. 새 화면의 DAY 배너 관측을 주장하지 않는다. 2편 새 checkpoint8/frame6012(세션93758)는 M8 DAY2 보병3개 전체 레코드·자금9000·배치 일치다. 이전 round8 세션은 exit0 정상 종료했고 새 세션은 전투/턴 종료 없이 inputless다. 증거: `temp/part1_2026-09-23/round13_migration/evidence.json`, `temp/part2_2026-09-23/round13_m8_migration.json`.

임시 지형 BG 시제품4678e35c는 바다·해안·반대쪽 창의 정지화면에서7개 이름을 모두 확인했지만, B hold1/2에서 꼬리 그림이 먼저 복원되어 글자가 잘렸다. 같은 round13 native 정상저장/7502frame 입력의 기준과 비교해63전환 표본 중6실패를 검출했다. native 자체 대조63개는 PASS다. shadow 타일맵은 이미 지워졌어도 실제 VRAM 타일맵과 OBJ는 두 프레임 남아 있었다. 원래 삭제 흐름은 유지하고 글리프 복원만 부모의 다음 콜백으로 미루는 최소 수정안을 준비했다. Claude는 콜백 지연도 한 프레임 빠를 수 있다는 가설을 지적했으므로 새 실제 캡처로 판단한다. 정지화면 PASS로 이 실패를 덮지 않으며 생산에는 아직 통합하지 않았다.

## 최소 수명 수정의 실화면 결과 (17:24 KST)

임시83305154 후보는 같은 정상SRAM/cold/7502frame의463snapshot에서 정지화면7종/128idle×3/DownUp PASS, native 대조63전환0회귀/0미판정으로 통과했다. root가 바다·해안·반대창 종료 전 이름 전체와 종료 후 잔상 없음을 육안 확인했다. held1/2에서 하드웨어꼬리6/12/10셀과glyph 유지, after1에서꼬리0 및원래source512B복원이함께관측됐다. [해안 종료 직전](../screenshots/continuation_2026-09-23/terrain_lifetime_coast_B_held2.png), [반대창 종료 직전](../screenshots/continuation_2026-09-23/terrain_lifetime_opposite_panel_B_held2.png), [종료 후](../screenshots/continuation_2026-09-23/terrain_lifetime_opposite_panel_exit_after1.png), [메모리 시점 기록](../screenshots/continuation_2026-09-23/terrain_lifetime_timing.json). CPU명령/VBlank 내 세부순서·항구7종동시·날씨/전지도는별도미검증이다. 정상닫기는B로재현했으며R닫기는동일native입력분기의정적근거만있다.

편집기metadata도round13 integrity로재생성하여fixed A22FFC를'조, '로갱신했다. 실제ROM은조、이며readonly/slot4유지. 기존50주소의값·슬롯·권한은이전검사결과와동일하다. map/groups갱신, catalog byte동일. 정식통합 round14 전체빌드와최종리뷰는다음단계다.

소비자미확인 범위를 줄이기 위한5분 읽기조사에서 A357B4 공통table→314B9C initializer→state+20→3148EE parser의하위사슬은확인했지만, 각descriptor/index에서그인수로오는상위호출/분기근거가부족했다. CO profile은같은3315표를다른PC로소비하는반례가있으므로표전체를한renderer로승격하지않는다. 검증소비자는1/2276유지. 근거: `temp/part1_2026-09-23/static_audit/consumer_coverage_round13/`. 불확실한경로를일괄PASS로바꾸지않고추가재생/무한검색을중단했다.

## round16 검증 후보 (2026-09-23 18:02 KST)

`temp/part2_2026-09-23/round16/candidate.gba` SHA256 `83305154eefa6ed82e4046cbb827ad33252d2bd35805b51947e0eede5bff3be2`, receipt SHA256 `3760250e2d4b5cc71388e2e778a5370188bd5dd99f9d52f3a1383ce16664cfad`. 전체 빌드와 QA exit0. 실화면 검증 시제품과 16MiB 전체 바이트가 같아 정상 저장 재현의 463개 캡처·63개 전환 표본을 같은 ROM 증거로 재사용한다. 254개 필수 수정행과 제어/42개 목표, 18,094 활성·1,996 재배치 payload, 84개 소개/121 strict 제목 검사는 유지됐다. 소비자 근거 1/2276과 그 외 미검증 범위도 그대로다.

정식 모듈/ASM과 편집기 자산을 등록했다. Claude 지적에 따라 원본 참조 12개 고정 및 hook 내부 진입 거부, ARM ADR ADD/SUB 계산을 수정하고 11종 합성 변이 시험을 추가했다. 지형 패치 13시험과 편집기 8시험이 통과했다. 두 편집기는 구 ROM의 빈 예약영역을 기본 캔버스로 쓰지 않으며, 실제 패치 비교는 설치된 ROM에서만 제공한다. 기존 사용자 편집 보존, 부분 설치와 메타데이터 불일치 저장 거부, 두 비교 API의 5가지 설치 상태를 검사했다. 현재 scene/자산 메타데이터는 round15 확인 이후와 바이트 동일하다.

Claude 후속 읽기 검토 `round16/claude_review.log`에서 수정 범위의 확정 회귀/저장 손실을 발견하지 못했다. 검토자가 실행한 시험으로 집계하지 않으며 시험 실행 근거는 각각 `production_adr_guard_tests.log`와 `terrain_compare_tests.log`다. agy는 이전 인증 실패로 사용하지 못했다. 새 코드가 모든 날씨·지도·항구 7종 동시 표시·양편 엔딩에서 검증됐다는 뜻은 아니다. 출력3종/배포 BPS는 동기화하지 않았다.

1편은 정상 SRAM으로 같은8330 ROM의 `mission3_day30_round14_cold_live` 세션51816/frame4933에 전환하고 아군10개/자금54800/배치를 확인했다. round16과 같은 바이트이므로 재부팅 없이 정상 플레이를 이어간다. 2편은 round13 세션93758/M8 DAY2/frame6012에서 입력 없이 보존 중이다. 재개 도구는 복제 에뮬레이터 없이 기록된 아군 상태만 읽으며, timeout을 성공으로 표시하던 문제를 고쳐 별도 Claude 후속 검토를 마쳤다. **두 편 엔딩 미도달.**
