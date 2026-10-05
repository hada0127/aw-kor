# 양편 엔딩까지 정상 플레이 검수 — 진행 중

사용자 요청: 실제로 1·2편 엔딩까지 플레이하면서 발견한 문제를 수정한다. 기존 입력의 전 프레임 비교만으로 엔딩 도달을 대체하지 않는다.

현재 도달 지점은 1편 야전 훈련 3(기지 점령), 2편 첫 캠페인 임무 Cleanup이다. 양편 모두 엔딩 미도달. 임무 진행은 화면을 보고 정상 패드 입력으로 수행한다. 메모리 변경이나 승리 강제는 사용하지 않는다.

## 이번 연속 플레이에서 발견한 결함

기준 ROM SHA-256: `12f65b063d2edf06347255625505c1a79d142dbba8ed30c0d943e27d966dfe3b`.

| 결함 | 관측 프레임 | 원인 / 수정 |
|---|---:|---|
| 1편 부대 설명 단어 붙음 | 135046, 135288 | 강조 명령 양쪽의 경계 공백을 명시 전각 공백으로 보존 |
| 1편 부하 사용 허락 의미 누락 | 135530 | `내 부하야 맘대로`로 끝나는 고정 writer를 원문 의미가 있는 전체 번역으로 수정 |
| 1편 점령 안내 A 버튼·강조 누락 | 136916 | D92846:D92870 전체 덮기 writer 제거, 원본 0x32/0x30 강조 명령 유지, D92850 suffix의 A 버튼 안내 복원 |
| 2편 공격 설명에서 `공격` 누락 | 85738 | A03B02 writer 끝을 A03B14로 교정하여 원본 0x72 줄바꿈 보존 |
| 2편 설명 명령 침범 | 같은 설명 구간 | A03B32 끝 A03B58, A03B90 끝 A03BAE로 교정하여 원본 0x77 대기 명령 보존 |
| 2편 상태 설명 큰 간격 / 초상 아래 잔상 의심 | 87548, 87788 | 원인 및 수정본 화면 비교 진행 중. 해결로 집계하지 않음 |

기준 증거: `output/qa/part1_2026-09-21/run14_to_ending/` (134321–142092), `output/qa/part2_2026-09-21/run07_to_ending/` (81447–88512). 각 실행은 정상 종료했고 입력·모든 프레임 원장·PNG·동일 ROM 재개 체크포인트가 있다.

## 수정 후보와 검증 상태

- 후보: `temp/full_audit_2026-09-15/tutorial_controls_candidate.gba`
- SHA-256: `bab4e2d36b03918a22feb74624da6fa4d54ff485e689bfa064489542b16c8691`
- 스크립트 안전성 테스트 54개 통과. 새 경계 / 강조 명령 변조 거부 검사를 포함한다.
- 전체 빌드 통과. 17,901개 활성 payload·1,932개 재배치 payload 부호/글리프 검사, 91행 충실도, 13개 프롤로그 제어, 바이트 무결성·재배치·중복 명령·기본 검사 통과.
- 증거: `temp/full_audit_2026-09-15/tutorial_controls_evidence/` 및 `tutorial_controls_build.log`, `ending_tutorial_tests.log`.
- 새 ROM은 기존 ROM 세이브를 재사용하지 않고 콜드부트 정상 입력 재생 중이다. 기록 경로는 양편 `output/qa/part{1,2}_2026-09-21/tutorial_controls_cold_live/`.
- 별도 선택 장면 콜드 재현은 빠른 결함 진단용이며 전 프레임 승인으로 집계하지 않는다.
- Claude 첫 검토 요청은 시간 초과. 추가 수정 포함 후속 읽기 전용 검토 진행 중. 시간 초과를 승인으로 취급하지 않는다.
- canonical ROM 3종 및 배포 패치는 이번 후보로 교체하지 않았다. 실기·오디오·미도달 임무·엔딩은 미검증이다.

## 후속 조사 — 채움 바이트와 표시 공백 분리

- `tutorial_controls` 콜드 재현에서 1편 문장·A 버튼·강조 복원 및 2편 `공격` 표기를 확인했다. 양편 전 프레임 재생은 142092/88512까지 도달했고 그 뒤 실제 플레이를 이어갔다.
- 2편 잔상은 기존 A3 ASCII 0x20 훅이 슬롯 채움 바이트까지 x 좌표 전진으로 처리한 결과다. 원본 dispatcher(0x3142CC→0x0831431C)는 이를 소비만 한다. 원본 dispatch 복원만 적용한 동일 상태 진단에서 잔상이 사라졌다. 다른 ROM 상태를 쓴 이 실험은 원인 진단이며 최종 검증으로 집계하지 않는다.
- 문장별 패딩 제거 임시 실험은 큰 간격을 없앴지만 이전 대사에서 생긴 잔상을 남겼다. 주소별 예외를 늘리는 구현안은 적용하지 않았다.
- 원본 dispatch를 유지하고, 실제 어절 경계는 명시 전각 공백으로 보존하는 후보 `tutorial_padding_candidate.gba`를 빌드했다. SHA `1842af2bd4a38fbd18b7f0d9ad5b91ef0fb318755b9f7305883dc339050ddf1c`. 55개 테스트와 기존 전체 정적 QA 통과.
- 후보에서 2편 처음부터 정상 플레이를 재수집 중이다(`tutorial_padding_cold_live`). 채움 처리 시간이 달라 기존 전체 입력을 그대로 재생하면 후반 장면이 어긋나므로, 확인된 초반 60입력 이후는 화면을 보고 다시 진행한다.
- Claude 이전 리뷰 H1의 prefix 일본어 의심은 기존 raw replacement와 실제 ROM `D92846:D92850=8fa28140328d468d4330`, 콜드 실화면으로 기각했다. D92766=8140 및 실화면 확인. 유효한 인접 공백 지적, D92846/D9284B/D92850의 canonical metadata 범위, D924F8 TSV 권위는 보완했다. 원본 슬롯만 검사하는 게이트의 한계와 미도달 구간의 경계 공백은 미검증으로 유지한다. 후속 Claude 검토 진행 중.
- 추가 관측: 1편 frame146594의 `20이면바주카의`, `이틀에점령` 경계 공백 누락. 아직 수정·검증 완료가 아니다.


## 추가 진행과 저장 이어하기 (2026-09-21)

- 1편: 야전 훈련3 4일차, 도시 점령 후 적 보병과 교전·남쪽 수도 진격 중. 2편: Cleanup 첫 임무를 정상 입력으로 6일차에 격파, S랭크 결과 화면 도달. **양편 엔딩은 아직 미도달**.
- 추가 후보 `tutorial_save_candidate.gba` SHA `6d7ffb4ab70512866569c889b8b14416900d6316397f4977a0a1d998777678e3`: A034F6:FE writer가 원본 대기/줄바꿈을 덮는 문제를 A034F7:FB 텍스트 전용 writer로 수정. 메시지 A03434 재배치 성공, 원본 제어 유지. 1편 D93013/D9303E/D9306F/D930CA/D931A4/D931B8/D93253/D93280 어절 경계도 보완. 후속 실화면 검증 전이므로 해당 1편 수정은 완료 판정하지 않는다.
- 56개 스크립트 테스트, 17,902 활성 payload/1,932 재배치/91 충실도/13 프롤로그 및 기타 정적 게이트 통과. 증거 `tutorial_save_evidence/`, `tutorial_save_validation.log`. 이후 캡처 도구 보완으로 현재 작업 트리와 빌드 입력 receipt는 달라졌으며 이 ROM은 위 SHA의 고정 후보로만 취급한다.
- A3 렌더러 실행 중단점: mode-select/prologue에서 원본 space handler와 A3 glyph, 이전 전투 대화에서 advancing hook과 A3 glyph 진입을 관찰. `renderer_attribution_runtime/`에 출처와 로그. 3,315개 Part2 원본 포인터 스캔은 파싱 실패0, 759 경계 후보/15 내부 ASCII 공백 후보를 발견했으나 별도 UI 소비자도 포함하므로 모두 결함으로 단정하지 않았다.
- `game_save_evidence.py`로 동일 ROM 체크포인트에서 정상 카트리지 저장을 무변경 추출하고, 새 ROM은 게임 저장만 읽어 frame0부터 정상 부팅한다. 새 ROM에 다른 ROM 에뮬레이터 상태를 로드하지 않는다. 원본 `FLASH1M_V102`(0x27D8B0), 128KiB 저장을 확인했다. `mgba/flags.h`를 core 헤더보다 먼저 포함하여 설치 라이브러리 vtable ABI를 맞췄다.
- 게임 내 Save 후 `part2_day5_saved_yes/game_save.json`의 저장 SHA `7005d53effbb9a3e2590ddfbdb888b844175c1d20b3e18d2e79c2eba3e37bc48`을 원본/수정 ROM에서 모두 정상 Continue하여 같은 5일차 보드를 확인했다. 증거 `part2_save_continue_observation.json`, 양 실행 `0008_A_0004214.png`. 처음 복구 확인이 실패한 것처럼 보인 것은 메뉴에서 New를 선택한 조작 실수였다.
- 수정 후보의 실제 이어하기: `output/qa/part2_2026-09-21/tutorial_save_day5_live/`. 원본 비교: `original_day5_saved_yes/`. 각 frame4705 전투의 DEF 반복은 원본에도 같아 번역 결함으로 분류하지 않는다. 이는 해당 전투 HUD 비교에 한정한다.
- 게임 저장 바이트 무결성은 게임의 수용/저장 진행도/이전 장면 검증을 대신하지 않는다. 원본 증거를 옮기거나 삭제하면 출처 검증은 실패하도록 유지한다. 소스·부모 체인 정체성/해시, 비정상 저장 크기/경로/로드 바이트, seed를 빈 저장 루트로 잘못 내보내는 경로에 대한 방어를 추가했다. save 테스트9개, replay 테스트10개 통과. Claude 두 차례 저장 도구 검토의 유효 항목을 반영 중이며 전체 코드 완료 승인은 아직 아니다.


## 첫 승리 결과 화면 결함

- 정상 플레이로 첫 임무 결과에 도달한 뒤 속도/화력/기술 숫자와 합계가 잘린 것을 발견했다. 원본 ROM의 정상 저장 이어하기 → 동일 임무 격파 → 결과에서 각100/합계300이 정상인 것을 확인했다. 원본 `original_first_result_reference/0012_A_0010316.png`, `0014_A_0012120.png`; 수정 전 `tutorial_save_day5_live/0022_A_0009954.png`, `0024_A_0011758.png`.
- 원인: `patch_part2_result_summary_obj`의 광역 사각형이 0x59DA5C 아틀라스의 숫자행(y64:80 및 y80:96 일부)을 지웠고, 결과 항목의 실제 타일 위치와도 어긋났다. 제목은 y48:51 원문 획346픽셀을 지우지 않아 잔상도 남겼다.
- 실제 타일 경계에 맞춘 항목별 영역으로 교체하고 제목4개의64×64할당을 모두 교체했다. 숫자/NEXT/등급 그림 타일의 바이트 불변성을 검사한다. 관련 실제 ROM 회귀검사 포함57개 테스트 통과. `result_tiles_complete_candidate.gba` 전체 빌드와 새ROM 정상 이어하기 결과 재검증, Claude 결과 그래픽 검토 진행 중. 이 결함은 아직 실화면 수정 완료로 판정하지 않는다.
- 캡처 도구 schema3는 baseline JSON 해시를 체크포인트에 바인딩하며, 비영 시작 프레임에 부모가 없거나 저장 파일에 seed metadata가 없으면 거부한다. 기존 schema2 기록의 호환성을 유지한다. replay11개/save9개 테스트 및 실제 schema3 2프레임 생성·종료·검증 통과. Claude 마지막 저장 재검토는 계획 한 줄만 반환해 유효한 리뷰 결과로 집계하지 않는다.


### 결과 그래픽 두 번째 검증

`result_tiles_complete_candidate.gba` SHA `02c78855cb95397788c53f3ffdff09631ffb2779b923141ac4c9852f25f815c7`의 정상 저장 이어하기 → 임무 격파에서100/100/100/300 복구를 확인했다(`result_tiles_cold_live/0022_A_0009954.png`). 축하 문구 끝의 S! 원문 잔여, 화력 잘림, 색상/두 번째 페이지 + 위치 오류는 남아 있어 후보를 승인하지 않았다.

원본 결과 체크포인트를 같은 원본 ROM에서 읽기전용 로드하고 OAM/VRAM을 원본0x59DA5C 아틀라스와 바이트 대조했다. DISPCNT=0x1D60으로 OBJ는1D지만, 게임이32열 ROM 아틀라스의 직사각형을1D VRAM으로 복사함을 확인했다. 제목은각64×64. 실제폭은 축하144(x80..224), 속도48(x0..48), 화력40(x64..104), 기술64(x128..192), 합계64(x0..64), +16(x64..80), ALL32(x80..112)이다. 상세 `result_summary_probe/oam_mapping_evidence.json`, OAM/VRAM 덤프.

이 근거로 폭을 수정하고 +는 원본 보존, ALL만 누계로 번역했다. 원본 팔레트 인덱스(축하6/14, 항목6/15)를 유지하며 제목크기를 조정했다. 원본 아틀라스SHA 고정, 압축왕복검사, 실제 숫자/NEXT/+ 보호 타일 테스트 범위도 보완했다.57개 테스트 통과. 후속 `result_layout_candidate.gba` 빌드/실화면/Claude 재검토 진행 중.


- `result_layout_candidate.gba` SHA `a6e2fe44254fb4b90a252c23c2f42ac995b13bd7423964e975a791adc2b28f67` 전체 빌드/17,902 payload·1,932 재배치·91충실도/13프롤로그 게이트 통과. `result_layout_cold_live`에서 실제 재격파 검증 중.
- Claude 결과 레이아웃 후속 리뷰에서 실제 사용 위치 미확인 y240의3개 라벨 수정은 보류했다. 후속소스에서는 원본 tail을 통째로 보존하며, 실제확인한결과페이지 항목만 고친다. 네이티브11px폰트 강제/맞지않을때예외/폰트존재검사도 추가했다. 관련57tests통과. `result_guard_candidate.gba` 빌드 및 마지막delta리뷰 진행 중.


- `result_layout_cold_live/0022_A_0009954.png`에서 속도·화력·기술각100, 합계300, 축하 및 작전성공 제목을 확인했고, `0024_A_0011758.png`에서 원본+기호/누계300을 확인했다. 원문 잔여 S! 및 항목 잘림이 사라졌다. 이 검증은 첫 임무S등급두결과페이지에한정하며 전등급/전페이지 승인이 아니다.
- 1편 `tutorial_controls_cold_live/0970_A_0195072.png`에서 야전훈련3을 정상 수도 점령으로 완료(11일차), 이후 넬 종료 대사 검수 중. 2편은 첫 캠페인임무 완료. **각각 전체캠페인 엔딩은 여전히 미도달**.


- 최종 결과 보호 후보 `result_guard_candidate.gba` SHA `d8c6a61ec9d9784fa29353375089da731173bae6cc463abe40f3faebe2eb7941`: 전체 빌드/57tests/17,902payload/1,932repoint/91충실도/13프롤로그 등 정적게이트 통과. `result_guard_cold_live`에서 정상 저장 이어하기부터 최종 재검증 중.
- Claude 마지막 결과delta리뷰 `result_guard_claude_review.txt`는 새delta에 출하 차단 결함 없음을 명시했다. 색/폰트 역할을 문자열·경로 비교로 판단하는 유지보수 제안은 현 상수 입력의 결함이 아니며, 원문 잔획 위험은 원본아틀라스해시·OAM증거와 두 결과화면 실관측으로 범위를 확인했다. 대체등급/실패페이지·미검증tail 소비자는 별도 미검증으로 유지한다. 전체패치 또는 엔딩완료 승인으로 확대하지 않는다.


- 최종 `result_guard_cold_live/0022_A_0009954.png`, `0024_A_0011758.png`에서도 동일 정상 입력의 두 결과 페이지를 재확인했다. 각 RGB는 앞서 관측한 수정 레이아웃과 완전히 같고 숫자/제목/항목/+/누계가 읽힌다. 증거 `result_guard_visual_evidence.json`. 첫 임무 결과 그래픽 결함의 해당 두 페이지 수정은 확인 완료. 이제 이 후보에서 캠페인 다음 임무로 진행한다.


## 월드맵 제목 lookup key 복구 (2026-09-22 계속)

첫 임무 저장 후 월드맵 왼쪽에 무지개 OBJ가 표시됐다. 원본 `CAMPAIGN`(0xA3929C), `HARD*CAMPAIGN`(0xA392A8)은 일반 본문이 아니라 ASCII 그래픽 선택키였다. 전역 문자열 치환에서 두 키를 제외하고 최종 바이트 불변 검증과 회귀검사를 추가했다. 원본 전체 검색에서 CAMPAIGN은 이 두 키(후자는 부분문자열) 외에 없었다. 원본 OAM과 잘못된 후보 OAM 비교, 월드맵 초기화 전 상태의 키 복구 진단은 `worldmap_header_probe/`에 있다. 교차ROM 진단은 QA 근거로 집계하지 않는다.

`worldmap_keys_candidate.gba` SHA `1954343f8159b47291e51880e161dab21245b74776d6a2776a8e3b02c2be27bf`: 58tests 및 전체 빌드/정적 게이트 통과. 정상 첫 임무 완료 저장을 새 ROM에서 콜드 부팅해 Continue한 `worldmap_keys_saved_continue/0008_A_0004214.png`에서 무지개가 사라지고 한글 제목이 표시됨을 확인했다. 첫 시도 `worldmap_keys_cold_live`는 메뉴 조작에서 New를 선택하여 프롤로그에 진입한 별도 경로로 닫았으며 저장 실패로 판단하지 않는다.

Claude `worldmap_keys_claude_review.txt`는 남은 전역 ASCII 치환의 소비자/경계 위험을 지적했다. CAMPAIGN 제거가 다른 문자열의 영어 회귀를 낳는다는 우려는 원본 전체 occurrence 조사로 범위를 두 키로 한정했다. 다른 국가명 치환 및 HARD 그래픽은 추가 검증 필요하며 전체 출하 승인으로 집계하지 않는다.

1편은 훈련3 결과 저장 후 게임 내 목록에서 마지막 훈련 `결전`을 선택하여 정상 진입했다. 이 경로로 캠페인 해금을 진행한다. 양편 엔딩은 아직 미도달.


## 마지막 훈련/미션1 도입부 추가 검수

- 1편 `결전`은 적 탐지(안개) 훈련이다. 보병 정상 이동/도시 점령, 바주카병 정상 산 이동으로 시야 설명까지 진행. `1040_A_0215329.png`, `1050_A_0217939.png`에서 보병·바주카병 사이 조사/공백 및 `병는` 오류를 관측. 원본 highlight32/30 사이 2바이트 `と` operand만 `과　`로 재배치하고 뒤 `는`을 `은`으로 수정하는 후속 후보 준비. 원본 제어 바이트 보호 범위와 테스트를 추가했다.
- 2편 월드맵 커서는 타일 선택이 아닌 픽셀 이동이다. 국기 위치까지 오른쪽으로 이동하고 A로 다음 임무에 진입했다. `0013_A_0004919.png` 임무 선택, `0018_A_0007453.png` 미션1 시작. 앞서 완료한 임무는 미션0 프롤로그(첫 임무)였다. 월드맵 위 도입 대사는 원본에도 같고 이후 전투 지도 전환도 정상임을 `original_second_intro`로 확인했다.
- 2편 미션1 도입부 7개 텍스트 경계 수정 후보 `mission1_intro_candidate.gba` SHA `6d5d4a881062178b9602f4e2273c2efda0b3cb8dd877e613220d53375949972f`: 59tests/전체 빌드/17,902payload·1,934repoint·91충실도 등 PASS. 최종 ROM의 7개 full-fidelity 바이트가 실제 재배치 메시지에 들어간 것을 별도검사(`mission1_intro_boundary_fidelity.json`)했다. 아직 해당 후보 콜드 화면은 미검증.
- 이후 실제 플레이에서 추가 경계를 발견해 모아서 후속 `briefing_boundaries_candidate.gba`를 빌드한다. 2편 A04368/A0443F/A04478/A0448E/A044B4/A0456D/A0458D/A045D1/A04612/A04661/A04687과 1편 조사 수정이 포함되며 60tests PASS. 후속 소스/원본제어/구간 목록 `briefing_boundary_delta.json`. A047C0/A047E2 등 이어지는 지형 설명에서 새로 발견한 경계는 별도 미해결 목록에 남겨 이번 빌드 검증 범위를 과장하지 않는다.
- Claude 첫 미션1 검토는 가상의 도구 출력만 반환하여 리뷰로 집계하지 않는다. 두 번째 검토는 코드 일부만 보고 재배치 경로가 없다고 판단했으나 전체 빌드와 최종 ROM 7개 바이트 보존은 실제 통과했다. 생략됐던 후단 `_rp_fit_level`/최종 재배치 검증 및 실제 증거를 포함한 후속 검토가 필요하다. 아직 전체 코드 리뷰 완료/출하를 선언하지 않는다.


- 후속 `briefing_boundaries_candidate.gba` SHA `5ad2589bacd26d963ebaf053c683c4451e455f2668596ebceaf3d6066922b538`: 전체빌드/60tests/17,902payload·1,938repoint 등 PASS. 15개 추가operand의 실제 최종payload 충실도도 모두 통과(`briefing_boundary_fidelity.json`). 콜드실화면 미검증.
- 추가 지형설명 경계9개 및 1편 정찰차 소개의 `된` 중복을 수정했다. 후자는 기존 `dialogue_overrides`의 `된 「`가 앞줄 `...된`과 겹친 것이며 원본 `なった「` 슬롯8바이트를 canonical text operand로 고정해 `「`만 넣는다. highlight32/30과 줄바꿈은 보존한다.
- Claude의 "축약 후 재배치가 실패해도 해당 수정이 완료처럼 보일 수 있음" 우려에 대응해 이번 실관측32행에는 `PLAYTHROUGH_REPAIR_ROWS` 전용 writer를 둔다. encode_fit/strip을 쓰지 않고 full-fidelity 그대로 쓰거나, 슬롯초과 시 원본을 임시보존하고 필수repoint 성공을 강제한다. 실제writer를 실행하는 32행×override유무 테스트(초과시 missingrepoint 거부 포함)와 quote-only 소유권검사 등 61tests PASS. `terrain_guard_candidate.gba` 빌드와 Claude 새delta 재검토 진행 중.


- `terrain_guard_candidate.gba` SHA `bfdb4f828088893626ecd508b6f6e5e6e0a70d07df66d797fd394a68ab360c65`: 전체빌드/61tests/17,902payload·1,941repoint·91충실도·13프롤로그 게이트 통과. 관측32행의 실제 최종 ROM full-fidelity검사32/32 PASS (`terrain_guard_playthrough_fidelity.json`). 후속 잔여 수정 전 검증 기준을 고정했다.
- 새 콜드 세션은 양편 `output/qa/part{1,2}_2026-09-22/terrain_guard_cold_live`. 정상 카트리지 저장만 읽었다. 2편 도입4장(frame5521/6004/6487/6970), 판단/조언응답3장(frame9985/12400/12883)에서 경계 공백이 살아 있고 대사가 읽힘을 확인했다. 이후 지형설명, 1편 훈련 수정은 해당경로 재진입 검증 중.
- 이전 실진행 세션은 정상종료했다: 1편 `tutorial_controls_cold_live` frame229222, 2편 `worldmap_keys_saved_continue` frame27357. 오류 없음/에뮬 exit0. 2편 미션1첫전차 공격 정상결과(아군HP78/적45) 후 자주포 설명 중, 1편 결전에서 정찰차를 숲 옆으로 정상 이동해 로켓포 발견 설명 중이었다. 새후보에서는 같은 정상입력 경로를 재진행한 뒤 계속한다.


- terrain_guard 실제 재배치15개 메시지의 제어 skeleton을 원본과 직접대조하여15/15동일을 확인했다(`terrain_guard_repaired_control_skeleton.json`). _rp_fixed_bytes는 실제로 encode_full_fidelity를 호출한다. Claude의 일부 차단 지적은 이 후단 함수/완성ROM 증거가 프롬프트에서 빠진 데서 나온 것으로 구분한다. 유효한 F10(평지나 뒤 newline앞 공백)과 새 화면 `싸울 땐평지나`는 수정대상으로 수용: 공백위치를A04994에서A0497D로 옮긴다. 전체 리뷰 승인 아님.
- 2편 콜드 도입/지형설명 추가15화면을 비교했고 기존수정경계는 읽히나, 위A0497D 경계1곳이 남았다. contact sheet `terrain_guard_cold_briefing_sheet.png`, 관측목록 `terrain_guard_cold_observation.json`. 자주포 설명은 그다음 신규검수로 진행하며 공백과 `이동후공격공격 못 해` 중복을 추가기록했다.

- terrain_guard 동일 입력 프레임1..21,577 비교: 8,573프레임 차이 중 텍스트 영역 밖 차이12프레임. 이전 후보20231에서만 지도 1프레임 검정,20926에서만 대화층 1프레임 누락(각 인접프레임 정상); 새 후보 해당프레임은 정상. 원인은 미확정이며 전 화면 무결성 통과를 선언하지 않음. `terrain_guard_frame_comparison/visual_disposition.json` 및 인접프레임 증거 보존.
- 새 후보1편 cold60/64/68에서 조사·공백 및 중복된 된 제거 실화면 확인. 이후1편 정찰차 비교/로켓포 설명,2편 자주포 설명에서 발견한19개 조각 후속 수정. 특히 이동후공격공격 못 해 → 이동 후 공격을 할 수 없어, B 정보 키로 → B 버튼을 누르면. 입력해석/원본제어코드 보존, 실제새ROM 검증은 대기. 61개 회귀테스트 PASS.

- artillery 후보 SHA `bbd798ca3018a280f91efd87a4f38d9a61ad03043fbad358c799015c7e904462`: 전체 빌드, 17,902 payload/1,943 repoint, 기존91행/13프롤로그 게이트 PASS. 누적 실관측50행 최종ROM full-fidelity50/50, 관련21개 재배치 메시지 제어코드 원본 대비21/21 동일. 일반 카트리지 저장을 불러오는 양편 cold replay 시작; 세이브스테이트 ROM교체 사용 안 함.

- artillery 후보 양편 cold 실화면 확인: 1편83/99(보병과 바주카병, 이런 곳에 로켓포),2편45/61/62/63/66/67/68/69/70/71(공백·중복문장·B버튼 안내). 기존 정상입력까지 재생 후 실제 추가 진행 중: 1편 결전 DAY1 전차 전진,2편 Mission1 DAY2 도시회복/자금 안내 완료. 추가 관측 D9DF51/A05222/A053C5/A055C2는 다음 수정 묶음으로 기록했으며 미해결이다.
- Claude 이번delta 리뷰 첫호출 Read/Grep/Glob 사용은600초 동안 결과 없이 timeout. 도구 없이 실제 관련코드/원문/검증결과를 제공하는 축소 재시도 진행. 로그인 실패라고 단정하지 않으며, 외부 리뷰 통과로 집계하지 않음.

- Claude 축소 재시도도240초 무응답 timeout. `artillery_review_disposition.json`에 외부리뷰 불가 및 자체 적대검토(제어경계/overflow/실제최종byte/UX/보안/테스트/배포범위) 기록. 승인으로 집계하지 않는다. 계속 실제 플레이 중.

- 실제 전투 진행: 1편 결전 DAY4, 적 중전차 격파, 아군 일부 손실/회복 및 남쪽 도시 점령·동쪽 정찰. 2편 Mission1 첫시도 DAY6 보병/자주포/바주카병 손실 후 일반 시스템→항복→네 경로로 재도전 절차 검수 중. 승리나 체력 조작 없음. 첫 시도에서 읽은 실제 대사/전투/상실 기록은 그대로 보존하며, 승리·엔딩 증거로 계산하지 않는다.

- recovery候補 SHA `9ba89c59d3ae4159a80aaf20835634a68c56ab7ae1a3a1301eb746ea92e1292d`: 61tests/기존 빌드게이트/누적56관측행 최종바이트56/56 PASS. 누락 바주카병으로·아군 도시, 추가4문장 수정은 새ROM 실화면 대기.
- 패배후 월드맵에서 A35758 레드스타 영토가 레드스타 영으로 보이는 추가결함 발견. ASCII공백 포함13B+00 최종ROM에 토의바이트는있지만 화면에서누락됨. 원본14B operand안에서FW공백을쓰는진단후보를일반저장coldboot하면 전체 레드스타 영토 표시 확인. 원본 일본어14B/후행00 2B고정, 해당필드전용full-fidelity writer+최종검증+인접불변/ASCII회귀/종단변조거부2tests 추가(63tests PASS). 생산파이프라인 후보 region_alignment 빌드중. 진단후보를 배포산출물로 취급하지 않는다.
- Claude auth status는 loggedIn=true. 일반 리뷰호출은600/240/120초 무응답. --bare는 OAuth를읽지않으므로 사용불가(전역로그아웃이 아님); OAuth를유지하고플러그인등을끄는--safe-mode로구체코드/원본/테스트를제공하여 재시도중.


- region_alignment_final 후보 SHA `78c144da650494bd23160f743c8847483e9990f3cf58d18c5c576ae69025ded2`: 63 tests, 전체 빌드/17,902 payload/1,943 repoint/91충실도/13프롤로그/관측56행 최종바이트 PASS. final 검증 위치를 모든 텍스트 writer 뒤로 옮겼고 이전 region_alignment 후보와 ROM byte-identical. 5개 영토명 전체 단어의 2바이트 셀을 검사했으며 다른4영토는 이미 내부FW공백 사용(실화면 미도달). Redstar의3개 겹치는 staging writer는 모두 동일14B, 최종검증으로 후단변경을 거부한다. 증거 `region_alignment_territory_inventory.json`.
- 정상 저장 콜드부팅 실화면: 1편83 D9DF51, 2편117 A05222 /136 A053C5+A053D8 /144 A055C2 /159 A058EF /8+164 A35758 읽힘 확인. A053D8 뒤77+일본어で는 번역된 조사 서이므로 위에서로 이어지는 것이 맞다. 두 번째2편 항복은 수정된 패배조언과 월드맵 복귀 재표시를 검증하려고 DAY2에 정상 메뉴로 선택했다. 이후 새 도전 시작. `region_alignment_cold_observation.json`.
- 1편 결전 DAY8: 적 중전차와 경전차2대 격파, 전진 보병/경전차 등 손실. 남은 중전차로 동쪽을 정찰하고 후방 보병을 APC에 탑승시켰다. 승리/엔딩 미도달. 이전에 전진 보병의 본부 접근만으로 성공을 예상한 것은 부정확했으며 실제 손실을 그대로 기록한다.
- Claude safe-mode 읽기전용 리뷰가 응답했다. 명백한 로직결함은 찾지 못했으나 생산빌드·다른영토명·최종writer·6문장실화면의 증거를 요구. 전체제품 출하 승인으로 취급하지 않는다. 후속 증거를 제공해 재검토한다.

- 1편 DAY9 항복 및 패배안내/작전룸 복귀 후 재도전 도입까지 일반 입력. 기존 recorder는 segment613/frame119662에서 정상종료(exit0). 시스템 메뉴에서 항복/나가기/음악 라벨이 깨진 것을 발견. 원본 ROM을 같은 정상저장으로 콜드 재생한 메뉴는 BGMあり/降伏する/マップをぬける가 모두 정상이다(`part1_system_original/system_menu.png`). action 라벨만 추가했던 battle dictionary에서 System 문자열이 빠진 원인을 조사 중. 새 dictionary 후보에9개 고정 문자열의 코드 추가, ASCII공백과NUL을 구분하는 안전 파서/잘린코드·후행비영거부 등65tests PASS. 원본대비 진단 콜드화면 대기.
- 2편 다른 순서의 바주카병 설명에서 A052BA 지휘 보병계는 공격력이 높아...의 불완전한 주어를 관측. 원문あなたが指揮する歩兵系は攻撃力が高い・・・에 맞춰 당신의 보병 계열은 공격력이 높아・・・로 복원하고 관측57번째 full-fidelity/repoint 보호행에 포함. 새후보 system_dictionary 빌드중, 현 진행ROM은 region_alignment에 고정.
- Claude 지역명 증거보완 후속180초 무응답으로 완료판정을 보류. 새 system dictionary 변경과 테스트/콜드검증조건을 짧은 프롬프트로 다시 리뷰요청.

- 시스템 메뉴 단순사전확장 진단은 폐기: 총130글자로 확장하면 bank1 tile100..11F가 대사 출력으로 덮여 음악/설정이 다른 글자로 변한다. 기존Full-menu overlay는 stock BGM음표 tile1B1..1B4도 덮는다. overlay만 제거한 진단에서음표만회복되어 두원인을 분리했다(`menu_collision_findings.json`).
- 수정안: 이미 존재하고 등록된 compact UI별칭의 한글글리프를 실제bitmap검증 후 메뉴31문자열에서 사용, 부족13글자만 사전추가. 원본92글자 순서/코드는 유지, 전체105글자 tile1C..ED로 대사100경계를 넘지않음. 모든31문구 의미/원본operand/인접metadata 불변 검사, 최종payload/사전/원본menu renderer검증 추가. Full-menu overlay 설치 자체 제거. 새VRAM/ASM추가없음. 진단콜드 main/system 메뉴에서 부대/저장/시스템/종료 및 음표·음악 있음/항복/나가기 정상. 68tests PASS; 생산 menu_font_owned 빌드/추가행동·5행메뉴QA/Claude재검토 진행중.

### 2026-09-22 메뉴 수정 정식 후보 재관측

후보 SHA `38304726c39e0d2a034ce52568b0588e4f39c9a275f8d8fbd33f497a85f85288` 빌드와 68개 테스트, 17,902 payload/1,943 repoint, 57개 관측 문장 및 25개 메시지 제어구조 검증을 통과했다. 정식 후보를 일반 저장으로 콜드 실행한 `menu_font_owned_cold_live`에서 시스템 142, 음악 끄기 143/켜기 144, 공격·대기 158 화면의 글자와 아이콘을 육안 확인했다. `mech_commander_cold_production/mech_4.png`에서는 “당신의 보병 계열은 공격력이 높아…”를 확인했다. 증거: `temp/full_audit_2026-09-15/menu_font_owned_production_observation.json`.

Claude Sonnet 읽기 전용 후속 리뷰는 코드/테스트/문서를 직접 읽고 114개 상한, 쓰기 전 초과 거부, 원래 사전 순서 유지, 기존 전체 메뉴 overlay 제거에서 논리적 결함을 찾지 못했다. 초기 후속 호출은 도구가 없어 읽기를 제안만 했으므로 리뷰 완료로 세지 않는다. 실제 읽기 리뷰는 `menu_font_owned_claude_read_review.jsonl`. 실행 검증은 작업 에이전트가 수행했으며 캠페인 5행 메뉴는 여전히 대기다.

1편 마지막 훈련은 DAY9 항복 후 DAY1 재도전 중이다. 2편 첫 임무는 DAY8에 적을 모두 격파하고 승리 대사에 진입했다. 엔딩과 전체 캠페인 검증은 양편 모두 미완료이며 기존 배포 ROM 3종/패치는 변경하지 않았다.

2편 경계 방어전 정상 승리 증거: `region_alignment_cold_live` segment476..484 승리 대사, 485 S랭크/속도100·화력100·기술100=300점, 486 승리 지휘관 그림, 487..488 WIN 및 누계600, 489 저장 확인 선택, 490 월드맵. recorder는169120프레임에서 정상 종료(exit0). `part2_border_skirmish_cleared_save/game_save.json`으로 해당 일반 저장을 내보내 최신383047… 후보 콜드부팅을 시작했다.

### 2편 다음 임무 진입과 추가 결함

월드맵 방향키2프레임 입력은 커서 이동이 불충분했다. 원본·후보 양쪽 일반 저장 콜드진단에서 긴 입력은 정상 이동했다. 기록 도구에 선택형 HOLD_FRAMES를 추가하고 replay/export까지 같은 길이를 보존했다. 기본2프레임 입력은 유지. 14개 재생/9개 저장 테스트, 실제12held+180release=192연속프레임 대조, 258프레임 2회 재생 및 최종수정본 참조비교 차이0, export byte동일. Claude 후속 엄격 읽기 리뷰에서 차단 결함 미발견. `held_input_verification.json`.

정상 기록 `part2_2026-09-22/menu_font_held_input_live`에서 다음 임무에 진입했다. 원본 같은 저장/입력의 전환은 MISSION 3 / 戦いの幕開け지만 후보는 미션1만 표시한다. 기존 `patch_part2_mission_number_obj`가 MISSION과0..9를 함께 담은 글꼴을 고정 미션1 이미지로 바꾸고, `_mission_title_hangul_glyph`가 제목 글리프를 빈칸으로 돌려주던 결함을 실제 확인했다. 원본 `max_intro_original/page_17.png`, 후보segment19. 숫자 원형과 제목 렌더러를 복원하는 진단 후보를 조사 중이며 아직 수정 완료로 세지 않는다. 추가로segment17 “녀석은부순다”, segment36 “특기라공격력” 등 문장 경계 공백 누락을 발견했다.

### 2026-09-22 미션 번호/제목 및 Max 설명 복원 검증
- 원본 MISSION3/戦いの幕開け와 달리 미션1 고정·제목 누락을 확인. 원본 LZ 68타일 중 MISSION 24타일만 번역하고 동적 숫자 44타일을 그대로 보존, ASCII MISSION 조회 키 복원. 제목 전용 32×32 글리프를 Galmuri11로 복원(본문22px, advance24/공백12).
- 관측한 Max 도입10/수송 헬기3 조각의 의미 누락·공백을 복원. 최종 후보 `mission_titles_reviewed_candidate.gba`, SHA `58522d2d299315851e07e5e47ab60cb83ae41413571390b0f54fa646b9d970d1`. 71 tests/17,902 payload/1,946 repoint/91 full-fidelity/13 prologue/70 관측 행 PASS. 최종 writer 뒤 동결 소스·테이블·글리프 비교로 재오염 거부.
- `mission_titles_final_production_cold` 일반 저장 콜드 실행의 17/19/26/28/36/37/44/54/62 화면 육안 확인. reviewed 후보와 SHA 동일. 미션3/싸움의 개막, 보병과 바주카병, 바다 위에 있을 때는 공백 확인.
- Claude 실제 후속 정적 리뷰 `mission_titles_claude_followup.md`: 확정/차단 버그 없음. 원본 테이블 실제144항목·advance전부26, legacy blank fallback은 HEAD에도 존재함을 추가 확인. 29개 legacy 추출 코드 및 각 주소를 빌드 report에 기록. 미방문 전체 제목은 승인하지 않음.
- 연속 버튼 입력이 메뉴에 잘못 적용되어 1편 DAY6에 의도치 않은 항복 발생(기존 run 633..656). 실수 구간은 보존, 검증된 동일 ROM 632 체크포인트에서 `fog_day6_recovery_live`로 재개. 게임 RAM 수정/강제 승리 없음. 이후 메뉴/전투 종료마다 화면 확인.
- 2편 실제 MISSION3 DAY2 진행 중. 양편 엔딩/전체 캠페인/분기 검수는 미완료.

### 2026-09-22 합류 설명 추가 6행
실제 Mission3 DAY2 합류 설명에서 감탄사/공항 안내/하지만/합류해서/메뉴에서 조각 사이 공백, 질문 어미 누락을 확인. 새 관측6행을 guarded repair로 추가. 첫 빌드는 보호된 B팀 감탄사에 새 쉼표까지 추가해 재배치 불가 게이트가 차단했다. 기존 어휘 `젠장`은 그대로 두고 경계 공백만 추가하는 수정으로 정리, 재빌드 중. 실패 산출물은 검증 후보로 사용하지 않는다. Claude 리뷰는 확정 차단 결함 없음이나 실제 공백 화면 확인 요구, 콜드 검증 대기.

### 2026-09-22 1편 마지막 훈련 승리
동일 ROM 정상 입력으로 DAY8 도시(12,6) 점령을 마치자 승리 대사 진입. `fog_day6_recovery_live` 125..130: 적의 철수, 캐서린의 완료 인사 확인. 적 수송선 등 생존 상태에서도 점령으로 승리 조건 달성, 전멸은 필수 아님. 앞서 해당 도시를 HQ라고 추측한 기록은 잘못이며 화면 지형 표시는 도시였다. 캠페인 진입/일반 저장은 아직 다음 단계.

### 2026-09-22 합류 설명 최종 화면 검증
`air_merge_final` 후보는 실제 콜드에서 공항 설명 우측 잘림/합류 앞 경계 누락이 있어 불합격으로 기록. 의미 유지하며 `회복하는 곳은`으로 표현 정리, `같은 유닛끼리라면、　` 경계 추가. 최종 `air_merge_layout_candidate.gba` SHA `e757d83fd055d5785b26fdca2377ad943fb71c7e985905095fbec1fd0a5ae082`: 71tests/17,902payload/1,947repoint/77관측행 PASS. 일반 저장 콜드 152/154/155/156/157/162 실제 화면에서 모든 관측 수정 확인. Claude 명확한 변경/이웃 조각 자료를 보낸 후속 리뷰 차단 결함 없음. 전체 캠페인 미완료.


### 2026-09-22 캠페인 진입 / 2편 미션 3 승리
- 1편: 훈련 완료 일반 저장을 export 후 e757d83f 후보를 새로 실행, campaign_cold_live 첫 전투 DAY1 도입 대사 진행. 지도 VS 상대 호이프 및 아군 료, 전투 HUD 료 이름 일본어 잔존을 실화면에서 확인.
- 2편: menu_font_held_input_live 503 / 142002프레임에서 미션 3 잔여 보병 격파, DAY6 승리 대사 진입. 정상 입력이며 엔딩은 아님.
- rank_labels 68e6ae8f 후보 정상 저장 cold replay 147/149/151/153/155 검토: 브론즈 래트/주변 초상/카드/저장화면 정상.
- campaign_labels_final 38dd68e5 후보: 호이프 지도 이름 cold 8 확인. 자주포 설명 추가 4구간 수정 후 cold 399/401/402/405/407 확인. 81개 수정행, 17902 payload, 1948 재배치, 91 충실도 및 13 프롤로그 제어 PASS. 료 두 자산과 접근자 최종 보호를 추가한 후속 후보는 별도 빌드 중.

### 2026-09-22 진행: 일반 저장 재부팅과 블랙 캐논
- 1편 첫 캠페인 DAY4: `campaign_cold_live` segment394 게임 내 정상 저장, `part1_campaign_day4_save/game_save.json` 전체 계보 검증. 기존 기록 exit0. `campaign_day4_cold_live` 새 부팅으로 계속하기 성공, corrected756b ROM의 DAY 지휘관 료 표시 정상.
- 2편 MISSION4 DAY2: 보병/정찰차/전차 정상 생산, 정찰차 설명, 수송헬기 하차 메뉴 검수. DAY3 첫 블랙 캐논 발사로 수송헬기HP50, 약점(4,2) 안내 대사 진입. 입력 좌표 오차로 CO 정보 화면이 열린 분기는 보존, 게임 결함으로 분류하지 않음.
- 신규 공백 수정 1건 검증: `temp/full_audit_2026-09-15/cannon_boundary_verification.json`. 두 편 모두 엔딩 미도달.

- 관찰 정정(2026-09-22): 2편 중앙 시설(10,7)을 공항이라고 중간 설명한 것은 잘못된 판독. 실제 메인 segment569 R 지형정보의 명칭은 **공장**. 빈 시설에서 A가 생산창 대신 맵메뉴를 열었으므로 점령 완료/항공 생산을 주장하지 않음. 카메라/입력 좌표 재확인 필요, 패치 결함 아님.

- 중앙 공장 최종 확인: 메인2편 segment766 실제 생산창, segment771 중전차16000 생산/자금49000→33000. 이 증거로 공장 점령·생산 경로를 확인함. 이전 공항 관련 설명은 폐기.
- 1편 DAY10 하이퍼수리2회째 segment658/659: MD40→60, 상단 포병23→50, 하단 포병80→100. DAY11 적 중전차 제거, DAY12 북동 로켓포 1대만 남음. 두 편 엔딩 미도달.

### 2026-09-22 첫 캠페인 승리와 코인 설명 수정
- 1편 `campaign_day4_cold_live` segment820에서 첫 캠페인 DAY14 전멸 승리, 835 결과 B, 836 브론즈 래트/코인8, 843 일반 저장 완료. 엔딩은 아직 미도달.
- segment837에서 “워즈 숍” 다음 조사 “에서” 누락 관측. DFAED6/DFAF03을 “「워즈 코인」은 「워즈 숍」에서” / “쓸 수 있는 돈이야！”로 복원. 첫 행34B, 둘째22B는 원본18B 슬롯을 침범하지 않고 기존 필수 재배치로 전체메시지 DFAE9C→A77ED4(292→298B) 이동. 원본/새 제어열 동일.
- 후보 SHA `2bdc0c3cc34c54d1f9631ee2baa3163eeb38414f61e00b9e1b4eb12c0739ca70`: 89행 full-fidelity, 74 tests, integrity17902/repoint1949/91fidelity/13controls PASS. 정상DAY4저장 cold replay1..839, 835..839 실화면 정상. Claude 후속 결론 확정결함 없음. 증거 `temp/full_audit_2026-09-15/coin_explanation_verification.json`, `coin_explanation_byte_proof.json`, `coin_explanation_result_cold/`.
- 2편 M4는 segment1017 DAY15 중전차로 블랙 캐논 파괴 후 승리대사 진입. segment1022에서 “몇 번몇 번을,”/“와도내가” 중복·경계오류 발견하여 후속 수정중. 아직 결과/저장 검수중이며 엔딩 미도달.

- 2편 M4 결과 segment1036 A255(속도92/화력76/기술87), 1037 료 결과대사 정상. 이후 일반저장 확인중. 기존 Bteam drift42는 이번 수정 전후 동일함을 `cannon_victory_preexisting_bteam_drift.json`에 별도기록; 전체 drift 게이트 PASS로 주장하지 않는다.

### 2026-09-22 M4 승리 대사 3조각 복원
- 원본 A0BC9C「何度、」(6B)/pause77/A0BCA3「来たって」(8B)/newline72/A0BCAC「ぼくがいる限りムダだぞ！」(24B)/wait6B. 기존 override가 「몇 번을,」/「와도내가…」로 한 조각씩 밀려 앞 수기행 「몇 번」과 중복.
- 사용자 플레이중 오류수정 지시에 따라 각각 「몇 번이나　」/「와도」/「내가 있는 한 헛수고라고！」. A0BCA3 Bteam 기준과override도 같은키만 명시적 수정. 42개 기존drift는 전후동일이며 release PASS 아님.
- 후보9fd030506a3e7a2e1ef7c6e3373e12ba2a16277708a059beb649f0970d986871, 92guarded/74tests/integrity17902/repoint1949/91fidelity/13controls PASS. A0BC9C메시지→A43F54(44→54B), control[77,72,6B]동일. 정상Max완료저장cold1..1024, 1022중복소실/공백/줄바꿈 정상, 1017/1021/1023/1024전후화면확인. Claude확정결함없음, 요청한소스치환/바이트/런타임검증완료. `temp/full_audit_2026-09-15/cannon_victory_verification.json`.
- 1편 다음도입 오른쪽빌리 이름표 일본어ビリー 관측. bankBF2BCC slot5 BF2E4C raw128B가 해당그림임을 원본decode로확인. 기존이름표모듈에slot5추가후빌드/리뷰중.

### 2026-09-22 빌리 캠페인 이름표 복원
- 최초관측 `campaign_first_cleared_cold_live` 7..23 오른쪽초상하단ビリー. 원본BF2BCC bank slot5 BF2E4C128B SHA a81b739bb903b4dc8a4a44c7c148b8e1eb69bcd9ac4c2629ed07b30a9d557386(64자,실측일치). 기존 part1_campaign_co_labels.LABELS에빌리추가, 동일32×8 Galmuri7/팔레트1,3,5/포인터·접근기가드·최종freeze유지.
- 후보882bc231c057d75887dcef2bdfcc9d89bd0147d6bf1497054c496f91ef4e6bc9. 이름표4tests/92textguards/integrity17902/repoint1949/91fidelity/13controls PASS. 정상첫캠페인완료저장cold7/8/13/15에서빌리표시정상. Claude Opus 확정결함없음; 전투진입화면추가확인은진행중. `temp/full_audit_2026-09-15/campaign_billy_verification.json`.

### 2026-09-22 1편 공장 안내 호칭 경계
- 둘째전투 도입27 `아님료` 관측. DC33AF..DC33BD 원문さん、リョウ！/앞69이름삽입/뒤720A09. legacyTSV님료가쉼표를소실시킴. 실제operand를「님, 료！」로복원해플레이어아+님, 료！로표시. Bteam동일키baseline/override도실제fragment와일치시킴.
- 후보239ef4a3e34c578d4218ca397120cc2334f59606420c046b8aa209ca76856b35,93guarded/74tests/integrity17902/repoint1949/91fidelity/13controls PASS. 10B≤14B,앞69/뒤720A09원본동일. 첫캠페인완료일반저장cold26..30 시각검수PASS, 빌리이름표도26정상. ClaudeOpus최종제품리뷰확정결함없음. `temp/full_audit_2026-09-15/factory_call_verification.json`.

### 2026-09-22 2편 해상 미션 계속
MISSION5 main34 긴제목잘림 수정후보78c6ddc4 정상M4완료저장cold34/35와 짧은M4전후22/23/24픽셀동일. 실제titleaccessor검증범위를130→179개로넓혔고ROM동일. 7단위시험PASS; Claude후속리뷰 대기(앞선후속은도구호출모양텍스트만출력해리뷰실패).
main79/81/85 인용부호가?로출력: comprehensive원문「」가공통normalizer→ASCIIquote→8168이되어A3miss. 원본A3는8168없음,8175node80C040/8176node80C160존재. 관측3행(A094B9,A09516,A0962E) nativequote보존과연결구문수정진행. 새후보채택전메인ROM고정유지.
1편 둘째전투DAY2 city8,8 점령, Tank10,9 vs enemy11,9 교전후각4HP. Inf9,8→11,8 이동/공격메뉴149. 2편 Tcop12,4→cruiser12,10 탑재73, Sub12,11→13,7 이동/공격메뉴93. 양편엔딩미도달.

### 2026-09-22 저장 인계
P1 campaign_second_day1_cold_live255/frame40867 일반저장·exit0. P2 cannon_cleared_cold_live180/frame50538 일반저장·exit0. 출처검증export part1_second_day3_save/part2_naval_day1_save완료. 최신후보17dff0c0에서second_day3_cold_live/naval_day1_cold_live로각cold재시작중, savestate직접이식없음. 두편엔딩미도달.


### 2026-09-22 사용량 절약 중단
사용자 요청에 따라 두 레코더 정상종료(exit0). P1 second_day3_cold_live106/frame19029, P2 naval_day1_cold_live101/frame22020 일반 저장을 출처검증하여 각각part1_pause_day4_save/part2_pause_naval_day1_save에보존. 진행1편둘째DAY4/2편M5DAY1,엔딩미도달. 최신후보remaining_days_guarded73e6de3c는4tests/99수정행/integrity17902/repoint1949/fidelity91/controls13/basic PASS,정상저장cold양쪽HUD확인시제품과전체ROM동일. 최종리뷰보강의견은보류,메인미도입. 세부재개/잔여는 SESSION_HANDOFF_2026-09-22.md.
