BLOCKED: 기존 2core 하네스는 client full ROM을 cartridge로 load하지 않는다. 원본·후보 모두 client cold boot에 실패하여 Link 양쪽 모드 선택/READY/실제 전송 이후 이름 소비자는 (unverified)다. serialdriver/하네스는 수정하지 않았다.

# List / Link 선행조사

2026-10-23, track: spike. 기준 HEAD 90908180938c2bf40ee38dea43c4c1304b09df8a. Mac 실행. 완료 기준은 정상 편집키로 규칙 충족 맵 저장, Versus 사용자 목록/선택 및 한글 renderer 실측, 기존 두 코어 하네스의 원본/후보 경계 구분이다. 전체 성공을 주장하지 않는다.

## 변경 범위와 실행 환경

생성 파일은 이 `list-link-re/`에만 있다. tracked/기존 원본/후보/b44/도구/기존 조사 경로 수정, 추가 워커, commit/push 없음. probe.py는 stdin 명령/출력/시간/launch/exit와 RAW→PNG 변환만 담당하며 기존 하네스 바이너리/serialdriver를 변경하지 않는다. ROM·SRAM 직접 쓰기, RAM 변이, 다른 ROM savestate 이식 없음. 기존 candidate 한글 저장의 이름은 이전 RAM 변이 후 native 저장된 자료이며 이번에 정상 자모 키로 입력한 한글이 아니다.

공식 0.10.5 archive와 미수정 source를 빌드한 official-mgba/mgbah, mgba_link_harness, build/libmgba.0.10.5.dylib만 실행했다. 0.11 어댑터 미사용. 버전은 기존 BUILD_REPORT/version.cmake/otool 증거와 연결하며 실행 증거는 각 stderr.log의 READY 및 정상 프레임/캡처다. 소스/실행파일/라이브러리 SHA는 runtime-identities.json. 원문 C SHA는 protected-before/after.json. 공식 source tree 전체의 archive 대조는 official-mgba/source-verification.log의 기존 증거이며 이번에 재실행하지 않았다.

probe.py의 launch.json마다 argv/cwd/env를 기록했다. DYLD_LIBRARY_PATH는 official-mgba/build, TMPDIR/AW_KOR_TEMP_DIR와 cwd는 각 새 실험 디렉터리다. 링크의 고정 private save 상대경로도 본인 디렉터리에 위치한다. input.sav는 새 사본이며 링크 하네스가 다시 private copy를 만든다. client save는 기존 코드가 전혀 load하지 않는다. nice -n 10은 stderr에서 Operation not permitted로 거부되므로 낮은 priority 적용은 실패다. 초기 df는 330GiB 여유, vm_stat은 free 12104 pages(16KiB), inactive 338831 pages였다. 프레임 명령은 짧게 분리했고 각 명령 20초 제한과 종료 3초/terminate 5초 제한을 두었다. 모든 실행은 정상 quit/exit 0이며 timeout/프로토콜 전송 실패를 혼동하지 않는다.

## 공식 설명서 원문

부모 제공 Nintendo 공식 PDF와 page8~11 PNG를 직접 읽었다. 출처:
https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_AdvanceWars2BlackHoleRising_EN_DE_FR_ES_IT.pdf

인쇄 17쪽 Rules for Creating Maps 원문:
> The map must have at least two HQs of different colours and contain at least one deployed unit or one production base for each army’s HQ.

이는 영어 AW2 설명서의 조건이다. 일본 1+2와 같다고 가정하는 대신 아래 정상 선택 결과로 해당 사례를 확인했다. 인쇄 14~15쪽은 좌우/L/R로 7유형(DESIGN MAPS 포함)을 고른다고 설명한다. 19~21쪽 MULTI-PAK/TRADE는 각 플레이어가 같은 모드를 선택하고 1P START 후, TRADE는 sender→송신맵→수신슬롯 순이다. SINGLE-PAK는 고정 5맵이라고 설명한다. 설명서의 절차를 UI 도달 증거로 대신하지 않았다.

## A. 정상 키 맵 저장 / cold reload

원본은 native-re/replay-normal/new-eight.sav의 새 사본을 cold boot했다. editor.route는 기존 정상 키 경로만 재사용한다. 이후 자기 원본 savestate만 같은 ROM에서 분기했다. 조작은 R로 지형 메뉴, 좌우로 HQ/공장 선택, 상하로 진영 선택, A로 확정/배치, SELECT→파일→저장→덮어쓰기 확인이다. 최종 원본 맵은 빨강 HQ(7,5)/빨강 공장(7,6), 노랑 HQ(9,5)/노랑 공장(9,6)이다. `original-finalmap/valid-map.png` 직접 확인. 색 선택 중 중립 공장을 놓았던 중간 시행은 실패 자료로 남겼고 최종본과 구분했다. original-valid/redfix는 최종 유효맵으로 사용하지 않는다.

원본의 정확한 재생 연결: original-editor → original-buildmap → original-place → original-valid → original-redfix → original-color → original-finalmap. 각 commands.jsonl에 loadstate 및 모든 정상 키/프레임이 남아 있다. 기존 0.11 savestate는 사용하지 않았다.

후보는 candidate-re/eight-save/hangul.sav의 사본만 cold boot하고, 위 경로의 정상 keys/frames를 합친 candidate-map.route를 처음부터 재생했다. candidate-valid/valid-map.png에서 같은 HQ/공장을 확인했다. 이름 변경 없이 게임의 native 저장 메뉴로 저장했다. SRAM checksum 직접 수정 없음.

| 최종 새 저장 | SHA-256 |
|---|---|
| original-finalmap/valid.sav | f3a6198ea5340952e28a596dc2c39c343fd9a71b2d4a54a6d9d21e008a9a0b8a |
| candidate-valid/valid-hangul.sav | 15cfd55a8b24ec456c675e9c6cc22da189333166b080d03718c9230ad0232b1a |

각각 131072 bytes. 후보 한글 16bytes는 `884092af888a884092af888a884092af`이며 새 저장 0x1F504에도 존재한다. SRAM 안에는 여러 bank의 과거/현재 사본이 있으므로 단일 고정 offset만 읽어 현재 이름을 단정하지 않는다. 별도 cold boot가 이를 읽는 화면/실제 렌더 버퍼를 함께 확인했다.

## B. Versus confirmed / 제한

원본 original-cold-versus는 최종 valid.sav만으로 cold boot했다. 일곱 카테고리 순환 전체는 contact.png. category5.png의 デザインマップ에 ア 8자 이름 한 행이 있다. initial 두-HQ-only 시도에서 안 보였던 것은 이번 조건 충족 후 재현되지 않았다. 조건 부족의 정확한 native 판정 함수 주소는 추적하지 않았다(목록 도달했으므로 미도달 filter 정적 추적 조건은 해당 없음).

후보 candidate-cold-fixed/category5.png는 별도 cold boot한 최종 한글 save의 디자인 맵 목록으로 `가한글가한글가한` 8자가 보인다. 원본과 같은 짧은 A 연속 입력으로는 후보가 NEW submenu에 남았던 시행(candidate-cold-versus)을 보존했다. A를 한 번 더 정상 입력하여 진행한 candidate-cold-fixed.route가 실제 도달 증거다. 후보 전환 지연의 정확한 코드 원인은 (unverified)이며 메뉴 기능 결함으로 단정하지 않는다.

원본 original-select/selected.png와 후보 candidate-design/preview.png, candidate-versus-trace/selected.png에서 A 선택 후 빨강/노랑 2진영 TEAM SETTING 도달을 직접 확인했다. 목록 오른쪽은 원본도 실제 지형 미니맵 대신 DESIGN MAP 그림이며 후보도 디자인 맵 그림이다. 사용자맵의 실제 지형 preview가 목록에서 제공됐다고 보고하지 않는다. 선택된 맵의 전투 시작/모든 지형 round-trip은 (unverified).

실제 이름 렌더 근거:
- candidate-parser/runtime.log: parser PC=0831425C callback의 r1=02027F4E, LR=08314F1B.
- candidate-name-watch는 이름 02027F4E 16bytes 읽기 + VRAM 060006E0 4bytes 쓰기만 watch한다. 실제 게임 read PC=0831425A/08314336/0831BC90/0838BCE4, 한글 복사 store PC=08F302DE, LR=0831BBED. dumpmem 후 동일 idle PC의 host read는 근거에서 제외했다.
- name.bin은 정확히 `884092af888a884092af888a884092af`.
- candidate-versus-trace/runtime.log: 첫 이름 glyph source r6=08F00000, destination r5=060006E0, 다음 한=08F05E40→06000720, 글=08F00980→06000760, 나머지 반복도 확인. actual breakpoint=08F302D6, callback PC=08F302D8.
- candidate-name-watch/glyph.bin의 첫 가 64bytes == 후보 ROM 0xF00000..0xF0003F. 실제 검증 출력 `GLYPH_FIRST_GA_MATCH True`.
- 처음 후보 trace에서 0200B204(편집기 목록 버퍼)/06002620를 watch한 것은 이 consumer에 hit하지 않았다. candidate-list-memory의 RAM 스캔과 parser register로 올바른 렌더 source/destination을 찾았다. 전체 VRAM watch 없음.

대표 저장 한 슬롯/3음절의 이 소비자만 confirmed다. 전체 2350자·모든 슬롯·공백·실기는 (unverified).

## C. Link: 기존 하네스의 정확한 경계

원문 tools/mgba_link_harness.c setup_core:
- host(id0)만 core->loadROM과 loadSave를 호출한다.
- client(id1)는 cartridge vf를 닫고 두 번째 인자를 GBALoadMB로 읽는다.
- 공식 0.10.5 src/gba/gba.c:381의 GBALoadMB는 파일 처음 SIZE_WORKING_RAM(256KiB)을 EWRAM에 읽는다. full cartridge 16MiB를 client cartridge로 매핑하지 않는다. 반환 true는 client full ROM boot 성공이 아니다.

이 동작을 변경하지 않고 full 원본 ROM 두 개부터 실제 전달했다. original-dual에서 host/client 각각 120 frame은 진행했지만 host PC=08009A6C, client PC=0BF7F286, client PNG는 흰 화면이다. 이후 client PC는 비정상/미매핑 영역으로 계속 진행한다. 원본과 후보의 같은 link-trade.route 입력 대조 모두 client mode=8 node=-1, SIOCNT=0000 RCNT=8000, client 흰 화면이었다. 후보만의 한글 패치 통신 회귀라는 증거는 없다.

**중요: 실험 디렉터리 이름보다 캡처가 권위다.** original-link-trade는 실제 MULTI-PAK 선택/대기다. original-link-multipak은 잘못 EDIT 소개로 들어갔으므로 Link 성공 자료가 아니다. candidate-actual-trade는 실제 상점으로 이동한 잘못된 키 재생이며 통신 대기로 집계하지 않는다. candidate-trade-final/wait는 SINGLE-PAK 선택이다. 이 시행들을 삭제하거나 목적한 모드로 재분류하지 않았다.

| 실제 확인한 모드 | 증거 경로 | 최종 status/SIO |
|---|---|---|
| 원본 MULTI-PAK | original-link-trade/trade-0.png(선택), after-start-0.png(通信準備中), 양쪽 PNG/serial.log | host/client=1957/1957, multi=0 normal=0, host 6007, client 0000 |
| 원본 TRADE MAPS | original-actual-trade/trade-menu-0.png, after-start-0.png | 1982/1982, multi=0 normal=0, host 6007, client 0000 |
| 후보 동일 입력열 대조 | candidate-link-trade, link-trade.route 그대로 | 1957/1957, multi=0 normal=0, host 6007, client 0000. 캡처는 LINK 대기이나 세부 모드 확정 근거로 사용하지 않음 |
| 후보 TRADE MAPS(입력 보정) | candidate-trade-confirmed/trade-highlight-0.png(맵 교환), after-start-0.png, candidate-trade-confirmed.route | 2943/2943, multi=0 normal=0, host 6007, client 0000 |
| 원본 SINGLE-PAK | original-single/single-menu-0.png, after-start-0.png | 1982/1982, multi=0 normal=0, host 2007, client 0000 |

세부 경계는 **client mode 진입 이전 → both MULTI 불성립 → READY=0 → master transfer start 없음 → ID 할당/완료 IRQ/송수신 목록 이전**이다. sio.h에서 Slave bit2, Ready bit3, ID bits4~5다. 6007은 Ready bit가 0, Busy bit7도 0이며 기존 driver가 peer 미진입 때문에 Slave bit를 세운다. node_write는 두 node가 MULTI일 때만 master start transfer를 스케줄한다. serial.log에는 host load/unload만 있고 client load/transfer start/done이 없다. 따라서 IRQ 전달 불량을 원인으로 지목할 수 없다. START 입력을 실제 양쪽에 넣었지만 client 게임이 실행되지 않았으므로 양쪽 게임 모드 선택에 성공한 것은 아니다. BIOS 부재는 현재 full-ROM client loader 경계의 해결 근거가 아니며 다운로드/추정 요구하지 않았다.

Link sender/receiver/customlist 한글 표시, 수신 이름16bytes, 실제 전송은 모두 (unverified). SINGLE-PAK 고정5맵은 공식 영어 manual 근거이며, 일본 ROM의 실제 전송 후 5맵 목록/정적 selector를 확인하지 못했으므로 일본판에서 사용자맵이 불가능하다고 결론내리지 않는다.

후속 질문: full-ROM 두 cartridge를 진짜 load하는 기존 환경이 있는가? 없다면 기존 single-pak 중심 하네스의 client load 경로 확장은 별도 승인 범위가 필요하다. 이 조사에서는 serial framework 개발이나 driver 수정으로 성공을 만들지 않았다.

## 원시 명령 / 결과 / 무결성 / 정리

주 실행 형태(root cwd):
```
python3 temp/name-grid-phaseB/list-link-re/probe.py <case> single <ROM> <save-source> < <route>
python3 temp/name-grid-phaseB/list-link-re/probe.py <case> link <ROM> <save-source> < <route>
```
각 launch.json에 실제 절대 argv/env/cwd, commands.jsonl에 실제 stdin/응답/소요 초, exit.json에 실제 exit가 있다. route 파일 없는 대화식 배치도 전체 stdin이 commands.jsonl에 보존됐다. RAW는 uint16 width/height + uint8 pixel-size + RGBA32이며 원문 하네스 shot 함수에서 확인했다.

최종 verification.txt와 evidence-sha256.json 참조. 검증 원문 핵심:
```
PROTECTED_UNCHANGED True
GLYPH_FIRST_GA_MATCH True
GIT_EXIT 0 STDOUT ''
LSOF_EXIT 1 STDOUT ''
```
전체 emulator exit.json은 exit 0. 본인 로그에 열린 프로세스는 lsof 출력 없음. 전체 시스템 프로세스 상태를 보장하지 않는다. harness-session-check status는 D1 0/보고0이지만 d1_incomplete·wt_seq/windows.log lock 실패 및 ps sandbox 거부를 보고했으므로 전체 정리 검사 정상이라고 주장하지 않는다. 별도 워커/claim/워크트리/stash/Downloads 생성 없음. 증거는 총괄 인계용으로 남긴다.

PLAN 대비: A/B 대표 사례는 실측했고, C는 기존 client loader의 full-ROM 불지원 경계로 차단됐다. 잘못된 모드 진입 시행을 위에 분리했다. tracked 문서 후속 반영 없음 — 명시된 tracked 변경 금지에 따라 이 보고서로만 인계한다. 코드 변경/커밋이 없어 커밋 전 게이트는 해당 없음. 리뷰는 총괄 담당이며 추가 리뷰 워커를 생성하지 않았다.

RECEIPT: model=unknown effort=unknown role=code
