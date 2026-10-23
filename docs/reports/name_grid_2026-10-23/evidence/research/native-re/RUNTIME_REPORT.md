BLOCKED: Link 통신 이후 이름 목록/renderer와 안전한 조합 state 소유권은 미확정이다. 아래 정상 입력·새 저장·cold reload 결과는 이 제한과 별개로 실측했다.

# Phase B T0 / 원본 런타임 선행조사

2026-10-23 · track: spike · 실행: 이 harness-codex code 워커 / Mac arm64
대상 revision: `90908180938c2bf40ee38dea43c4c1304b09df8a` (`sweep3-p2-20261023c`).
범위: `temp/name-grid-phaseB/native-re/`만 생성·수정. production/원본 ROM 변경, 추가 워커, commit/push, GUI 제어 없음. 실제 기능 ROM hook은 구현하지 않았다.

## 1. 우선 결론과 완료 기준 대조

- **기존 사용자 세이브 없이 정상 진입 가능.** 원본 cold boot → Part 2 → EDIT MODE/MAP → 처음 안내 → SELECT → ファイル → 名前入力. 키/프레임 원장·직접 확인한 PNG를 보존했다.
- **8자 새 저장과 cold reload 재현.** `ア` 8자 입력, 확인, 첫 슬롯 저장을 정상 키만으로 처음부터 다시 실행했다. 별도 새 프로세스가 이 cartridge save만 읽고 cold boot하여 불러오기 목록 및 이름 재진입 RAM에서 같은 8자를 확인했다. 과거 savestate/route가 없어 불가능하다는 가정은 이 경로에서 반증됐다.
- 선택표/표시표 분리, 입력/삭제/특수 셀, 객체 allocation/free, 실제 IWRAM renderer 및 예약 code fallback을 추적했다. 안전한 새 state byte나 최종 hook 설계 승인을 뜻하지 않는다.
- 저장/불러오기 목록과 저장 화면 상단 이름은 원본 renderer trace를 확보했다. Versus 일반 목록은 진입했으나 custom name 목록은 찾지 못했다. Link 세 모드는 목록 전에 통신 준비에 들어갔다. 미검증을 성공으로 집계하지 않았다.

## 2. T0와 실행 환경

### 원본/저장 정체성

| 대상 | 크기 | SHA-256 |
|---|---:|---|
| `original/Game Boy Wars Advance 1+2 (Japan).gba` | 16,777,216 | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |
| `replay-normal/new-eight.sav` | 131,072 | `d6e2651201c497139a4235034ed5d922816e1c2d2dd3c487ebf87d553ceeb481` |
| `savefix/confirmed-custom-eight.sav` | 131,072 | 위와 동일 |
| `mgbah` | 실행 파일 | `dfcd4c76b2d60940383e34d2027860763f4139a82819c484d37afab74dfac614` |
| `mgba-build/libmgba.0.11.0.dylib` | 동적 라이브러리 | `eccdd98390afbe198259bde4550f4a7dc54b706edb0172a562b03de3c521fff1` |

첫 저장 파일 `fresh3/new-custom-eight.sav`는 저장 확인의 기본값 **いいえ**를 눌러 저장되지 않은 실패 증거다. 최종 저장으로 사용하지 않았다. 이후 はい를 선택한 `savefix`와 완전 정상 키 재생 `replay-normal`만 성공 저장이다.

b44/candidate가 없으므로 해당 SHA·후보와의 동등성·코드 공간 소유권은 **(unverified)**. 원본 하나의 사실을 후보 ROM의 동작으로 일반화하지 않는다.

### 문서 → 설치 확인 → 레포 사용례

1. 공식 [mGBA README](https://github.com/mgba-emu/mgba/blob/0.10.5/README.md)의 CMake 빌드/플랫폼 안내를 확인했다. `https://mgba.io/docs.html`은 web 도구에서 접근 실패했다. 셸의 GitHub/mgba.io 다운로드는 `curl: (6) Could not resolve host`였다.
2. `/opt/homebrew/lib/libmgba.dylib` 없음. `pkg-config --modversion mgba` exit 1. clang 21.0.0, CMake 4.4, capstone 5.0.9 (`cstool`), Pillow 11.3.0 사용. Python capstone 모듈은 없어서 설치 대신 기존 C 라이브러리/헤더로 disassembler를 빌드했다.
3. `tools/mgba_harness.c`, `tools/mgba_drive.py` 사용례를 읽었다. `/tmp` 기본 경로는 사용하지 않았다.
4. 로컬 `/Users/konest/project/spatialemu/ThirdParty/mgba` vendor source를 **복사**하여 이 영역 안에서 headless shared library를 빌드했다. source의 `version.cmake`는 0.11.0/ABI 0.11이다. `4fbb92d2316239cbe13a49f2b07aefef38ed6269`는 **SpatialEMU 상위 저장소 커밋**이며 upstream mGBA 커밋이 아니다. 해당 subtree의 git status는 clean. upstream과 byte-identical한 공식 release source인지는 **(unverified)**. 공식 0.10.5 패키지 설치에 성공했다고 주장하지 않는다. `source_identity.json`, 복사한 `mgba-src/`를 보존한다.

설치/시스템 변경 없이 `mgba-build/`에서 CMake configure/build exit 0. Qt/SDL/GL/FFmpeg/네트워크 추가 의존성을 껐다. 실행 관련 조건은 `configure.log`, `build.log`, `mgba-build/CMakeCache.txt`, `mgba-build/CMakeFiles/mgba.dir/flags.make`에 있다. 공유 라이브러리만 사용하며 전체 빌드/하네스는 동시에 하나씩 실행했다.

### 하네스 호환성 수정과 실패 원인

`tools/mgba_harness.c` 원문을 바로 빌드하면 exit 1: `color_t`, `desiredVideoDimensions`, 0.10 debugger 필드가 0.11에 없다. `adapt_harness.py`가 temp 사본 `mgba_harness_011.c`에만 헤더에 따른 변경을 한다.

- `mColor`, `baseVideoSize`, `mDebuggerModule`, range watchpoint API로 대응.
- dyld의 `no LC_RPATH's found` 오류는 실행 파일 상대 rpath로 해결.
- 생성된 `flags.h`에는 `ENABLE_DIRECTORIES`가 빠져 있지만 라이브러리의 실제 C_DEFINES에는 들어 있다. 생성 헤더만 따른 하네스는 struct mCore layout이 달라 null 함수 포인터 호출/SIGSEGV가 났다. 직접 실행 검사에서 `harness exit -11`. `compile.py`가 라이브러리의 실제 C_DEFINES를 읽어 일치시킨 뒤 부팅했다. 원인을 모르고 null guard를 추가하지 않았다.
- `fresh3/stderr.log`: `READY w=240 h=160 sizeof(mColor)=4`. `fresh3/boot.png`의 NINTENDO PRESENTS, `select2.png`의 1+2 선택, `p2mode2.png`의 MODE SELECT를 직접 확인했다.
- `nice -n 15`를 사용했으나 샌드박스가 `setpriority: Operation not permitted`를 출력했다. 낮은 priority 적용은 **실패**다. 한 번에 하네스 하나, 소량 프레임으로 운영했다. `vm_stat`/`df -h .`를 확인했으며 프로세스별 RSS 측정은 하지 못했다. 최종 ps 기반 검사는 EPERM으로 불가했다.
- 모든 실행은 `AW_KOR_TEMP_DIR`/`TMPDIR`을 본 temp 절대 경로로 명시하고 로그 argv도 명시했다. `drive.py`의 각 `launch.json`에 실행 argv/env가 있다.

## 3. 정상 진입/저장/cold reload 재생

키 마스크: A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512. `tap`은 기본 누름 1 frame, 해제 후 24 frames이며 추가 대기는 원장에 명시된다.

| 목적 | 원장/재생 | 직접 본 증거 |
|---|---|---|
| 최초 무세이브 진입 | `fresh3/commands.jsonl` | `fresh3/name-ready.png`, `typed-one.png` |
| 새 게임부터 최종 저장까지 키만 재생 | `replay_normal.py`, `replay-normal/route.txt`, `commands.jsonl` | `replay-normal/saved.png`, `new-eight.sav` |
| 새 프로세스 + 새 cartridge save로 cold boot | `replay_cold.py`, `replay-cold/route.txt`, `launch.json`, `commands.jsonl` | `replay-cold/cold-list.png`, `reentry.png`, `name.bin` |
| 최초 관찰 때의 cold load | `cold-confirmed/commands.jsonl` | `cold-list-actual.png`, `cold-loaded.png`, `cold-reentry.png` |

정상 최초 경로의 안내 문구를 A로 넘긴 뒤 이름 입력 자체의 안내도 넘겨야 grid가 활성화된다. START는 맵 편집기에서는 미니맵이며 메뉴는 SELECT다. 저장 확인/덮어쓰기 확인의 기본값은 いいえ라 LEFT 후 A가 필요했다. 성공 route는 이 실제 관찰을 모두 포함한다.

`replay-normal`과 `replay-cold`의 명령에는 `loadstate`, `w8`, `w16`가 없다. 정상 새 저장 증거와 아래 분기/메모리 변이 실험을 분리했다. 분기 실험은 모두 이 워커가 정상 진입으로 만든 savestate만 사용했다.

최종 정상 저장의 `0x1E504..0x1E513`은 `83 41` ×8이다. 별도 cold 재생 RAM의 base=`0x02003010`, name=`+0x2C`에 같은 16 bytes, length=`+0x61`에 8이 있다. **실측은 첫 슬롯 하나**이며 다른 슬롯 주소/체크섬/저장 트랜잭션 전체는 (unverified).

## 4. 입력/특수 셀 재확인

`input-probes.log`와 각 `probe-*/route.txt`, `result.bin`, `result.png`, `exit.json`을 참조한다. `input-contact.png`의 11개 입력 실험 화면과 lifecycle 취소 화면을 직접 확인했다.

| 조작 | 실측 |
|---|---|
| 일반 A | 選択 SJIS 2 bytes를 이름에 복사. `ア=8341` |
| 8자 상태의 다음 A | **거부가 아니라 8번째 덮어쓰기.** `ア`×8에서 RIGHT/A → `ア`×7+`イ=8343`, length는 8 |
| B | 마지막 pair 삭제, length 감소. length 0에서 B는 화면 이탈 없음 |
| BACK 셀 `(10,4)` | B와 같은 마지막 pair 삭제. 선택값 `6262` |
| Cancel 셀 `(10,3)` | 선택값 `6363`, 취소 확인 질문. はい 후 편집기로 복귀. `cancel-discard`에서 임시 `ア`가 destination에 복사되지 않음 확인 |
| START | cursor `(14,5)`로 이동하고 확인 질문. OK 셀 `(10,5)` 선택값 `6565`도 같은 확인 mode=2 |
| R | `カ=834A`를 `ガ=834B`로 교체. `ア`에는 변화 없음. 모든 문자에 대한 cycle 범위는 미검증 |
| `(10,2)` `3131` | `カ→ガ` 탁점 전환 |
| `(11,2)` `3232` | `ハ→パ=8370` 반탁점 전환 |
| 빈 셀 `(6,1)` | 입력 거부 셀이 아니라 전각 공백 `8140`을 한 슬롯에 입력 |

### 공백은 위치에 따라 저장 동작이 다름

- `space-save/before.bin`: `8341 8140 ...` (ア + trailing space).
- 확인 후 `destination.bin`: `8341 0040 ...` — 네이티브 trim이 trailing space의 첫 byte를 0으로 끝낸다.
- `space-save/new-space.sav` 첫 슬롯: `8341` 뒤 14 zero bytes. trailing `8140`은 보존되지 않는다.
- `space-internal/new-internal-space.sav`: `8341 8140 8341` 뒤 zero bytes. **중간 공백은 보존된다.**

정적 `disasm-space-trim.log`: `0x08313048`에서 2-byte 단위로 뒤로 가며 `81 40`을 검사하고 `0x0831307C`에서 종단 첫 byte에 0을 쓴다. 호출은 확인 복사 직전 `0x0834B012`. 기존 Phase A의 공백 계약을 변경하지는 않았다. ROM 통합 계획은 이 native trailing trim을 유지/변경할지 계약과 대조해야 한다. 공백만 있는 이름의 전체 UX와 모든 공간 정규화는 (unverified).

## 5. 테이블/입력 hook 후보의 근거

주소는 GBA bus 주소. 값 확정/코드 배정이 아니라 **후속 설계 입력**이다. 실제 ROM bytes는 `hook-bytes.json`, Thumb disassembly는 `disasm-native.log`, `disasm-state.log`에 있다. 선형 disassembly의 literal pool을 명령으로 해석한 줄은 근거로 사용하지 않는다.

- 선택표 `0x0883FAF6`: 15×6×2 bytes. signed cursor x=`+0x1E`, y=`+0x20`, index=`2*(15*y+x)`. `fresh3/append-watch.log`에서 선택표 읽기 PC `0x0834AFCE`/`0x0834B488` 관찰. `selection-cells.json`에 90셀 원문/좌표/특수값 보존.
- 표시표 `0x0883FE40`의 첫 row는 `09 83 41 ...`. `lifecycle/runtime.log`에서 파서 `0x0831425A`, 문자 경로 `0x08314336`, IWRAM `0x03006088`이 이 표시 문자열을 읽었다. 다른 테이블로 runtime 재확인. 행 제출 호출은 `0x0834AB4E` 등 → `0x08314EB0`.
- 입력 메인 `0x0834AFA0`: `f0b557464e464546e0b40020`; prologue는 r4-r7/LR, r8-r10을 보존한다.
- 일반 문자 처리 `0x0834B0BC`: `6520f0f7b9fcfff79dfefff745fc`. sound 호출 뒤 `0x0834B0C2` BL→`0x0834AE00`, 복귀는 `0x0834B0C6`(다음 BL은 preview redraw), 그 뒤 length 갱신. 런타임 append 진입 시 r5=`02003010`, r4=`0883FAF6`, LR=`0834B0C7`.
- `0x0834AE00` append 함수의 prologue는 `f0b5`(r4-r7/LR save), r12도 사용한다. 선택 pair의 store는 `0x0834AE44`; watchpoint의 pipeline PC는 `0x0834AE48`. 정상 호출은 r0-r3/r12/flags를 보존한다고 가정하면 안 된다. 함수 반환은 저장 LR을 pop하여 BX한다. 새 trampoline의 보존 집합/모든 분기 복귀는 **미설계·미검증**.
- B/BACK 삭제 `0x0834B20E` 이후: `01381070fff725fefff79dfb6620f0f70afc02e1`. R 처리 시작 `0x0834B222` 및 START/특수 셀은 일반 append와 별도다. 일반 A 하나만 hook하면 전체 조작 의미를 포괄하지 못한다.

Debugger 표기: breakpoint callback의 Thumb PC는 설정 주소+2, 메모리 watch의 PC는 해당 load/store 이후 pipeline 위치(+4)가 관찰됐다. `dumpmem` 자체의 host busRead도 watchpoint를 발생시킬 수 있다. dump 명령 이후 동일 정지 PC에서 나온 읽기를 게임 renderer/writer 증거로 세지 않았다. watchpoint set 출력의 개수는 등록 시도 수이며 실 hit를 근거로 판단했다.

## 6. state 크기·수명·scratch 안전성

정적·런타임을 함께 대조했다 (`trace-fresh/runtime.log`, `lifecycle/runtime.log`).

- 전역 state pointer 저장 위치 `0x03004650`.
- 생성 `0x0834B970`: `mov r0,#0x70; BL 0x08315300`. allocator 반환 runtime r0=`0x02003010`, 다음 heap 위치 r2=`0x02003080`; `0x0834B97A`에서 전역에 보관.
- allocator `0x08315288`은 16-byte 정렬과 헤더를 관리하며, 이 경로에는 객체 전체 zero-clear가 없다 (`disasm-allocator.log`). 0 dump를 소유권 증거로 삼지 않는다.
- entry setup `0x0834B9C4`: runtime r0=`0x0200B09C`, r1=8. `+0x5C`에 destination 포인터, `+0x60`=1, `+0x62`=8, `+0x63`=16을 설정. 별도 entry `0x0834B988`은 `+0x60`=0 경로.
- UI constructor `0x0834A9FC`에서 cursor/animation/상태 필드를 개별 초기화한다. `+0x65/+0x66/+0x67/+0x68/+0x6A`도 기존 코드가 사용한다. 이름 관련 두 버퍼 `+0x2C`, `+0x44`도 존재하므로 보이는 이름 16 bytes 외부를 빈 공간으로 보지 않는다.
- 확인 시 `+0x5C` destination으로 `+0x63` bytes를 복사. 취소 시에는 복사하지 않는다.
- 취소 복귀 뒤 destructor `0x0834BA00` hit, `0x08315390` free 호출이 정적으로 존재한다. 객체는 이름 화면의 동적 수명이다. `0x02003010`은 이번 allocator 반환 주소이며 영구 scratch 주소가 아니다.

**안전한 조합 state 위치: 입증 못 함.** 객체 크기/생성/해제는 확인했지만 전체 reader/writer·일반 입력 이외 모드·모든 객체 재사용을 전수 증명하지 않았다. tail의 0/잔존값만으로 몇 bytes를 골라서는 안 된다. 후속 계획에서 별도 할당 또는 검증된 객체 확장의 소유권/초기화/해제 계약을 정한 뒤 리뷰받아야 한다. 이번 조사는 기존 allocator 크기나 ROM을 바꾸지 않았다.

## 7. preview 실제 renderer와 `?` 원인

- 미리보기 갱신 `0x0834A954`는 이름 pair를 stack 임시 문자열(`0x03007D38` 관찰)에 복사하여 8회 `0x08314EB0`로 제출한다. `renderer-probe/render.log`의 LR=`0834A9D5`.
- 실제 glyph 실행은 `0x0300605C` 함수, 기존 hook 위치에 해당하는 내부 PC는 `0x03006080`. `iwram-probe/iwram.bin`과 ROM `0x08A3C7C0`부터 **0x174 bytes가 byte-identical** (`hook-bytes.json`). 따라서 `0x08A3C7E4`가 대응 소스인 것은 맞지만 이번 이름 출력은 그 ROM 주소 breakpoint에 hit하지 않았다.
- `ア` 노드 header=`0x08807C30`, 그림=`+6=0x08807C36`. runtime의 실제 그림 read는 PC=`030060E8`, LR=`0831BBED`. global 가나 그림을 수정하지 않았다.
- **RAM 변이 실험**: `fallback-trace/route.txt`에서 정상 도달 savestate의 live name 첫 pair만 `w8 0200303c 8840`으로 바꿔 redraw했다. ROM/원본 save 수정 없음. `reserved.png`는 직접 확인한 `?`다.
- `fallback-trace/runtime.log`: IWRAM fallback 위치 설정 `030060BC` hit에서 r4=`88`, r3=0(해당 lookup 실패). 다음 설정 `030060C8` hit에서는 r4=`81`, r3=`08808578`이다. 정적 `030060BC..C0`가 `81 48`로 바꾸어 재검색하는 코드라, **원본 lookup에 8840 노드가 없어 8148(？)로 fallback**하는 경로가 실증됐다. `disasm-iwram.log` 참조.

원본에서 예약 코드를 넣으면 `?`라는 사실은 후보 renderer가 지원하지 않는다는 독립 증명이 아니다. b44/candidate의 ROM→IWRAM 복사 시점과 hook 반영은 (unverified). 다음 설계는 ROM 소스 위치만 고칠지, 실행되는 IWRAM 복사/포인터 dispatch를 어떻게 처리할지 분명히 해야 한다.

## 8. 이름 소비자와 정확한 경계

| 소비자 | 도달/증거 | renderer / 한계 |
|---|---|---|
| 이름 입력 preview | 정상 키 typed-one/8자, 재진입, RAM 변이 `?` | 위 IWRAM glyph 경로 실측 |
| Design Maps 불러오기 목록 + 맵 preview | `replay-cold/cold-list.png`, `list-trace/list.png` | 문자열 source=`0200B204..B212`; `0x08314EB0` → IWRAM `03006080`; `list-trace/runtime.log`에서 8 glyph 읽기 확인 |
| 저장 화면 상단 이름 + 슬롯 목록 | `save-heading-trace/heading.png`, `runtime.log` | 상단 destination=`0200B09C`의 실제 읽기/문자 dispatch 확인. 일반 맵 편집 HUD에 독립 이름 타이틀이 항상 표시되는지는 확인 못 함 |
| 저장 맵을 load한 편집기 | `cold-confirmed/cold-loaded.png`, name 재진입 RAM | map load 후 이름 유지 확인. 별도 HUD title renderer는 (unverified) |
| Versus(フリーバトル NEW) MAP SELECT | `consumers/versus-list.png` 및 카테고리 2~8 PNG | 일반 목록은 통신 없이 접근. 좌우로 6종 카테고리 순환; custom 이름은 찾지 못 함. 정상 키로 청군 HQ를 추가·새 저장한 `valid-map/two-hq.sav`로도 custom 목록 도달은 입증 못 함. '원래 지원 안 함'이나 'HQ 부족이 원인'으로 단정하지 않음 |
| Link TRADE MAPS | `consumers/link-trade.png`, `link-trade2.png`, `link-wait.png` | 진입 뒤 목록 전에 `通信準備中…` 관찰. cable/두 번째 core handshake 이후 목록은 BLOCKED |
| Link SINGLE-PAK | `valid-map/single-pak*.png` | SINGLE-PAK plate 다음 `通信準備中…`, custom 목록 미도달 |
| Link MULTI-PAK | `multipak/communication-boundary.png` | MULTI-PAK 진입 뒤 `通信準備中…`, custom 목록 미도달 |

Link에서 기기/케이블이 물리적으로 반드시 필요한지는 이 한-core 실험만으로 단정할 수 없다. **현재 하네스의 한-core 구성으로 handshake를 완료하지 못한 경계**라는 의미의 BLOCKED다. 두 번째 core/케이블 환경 확장은 이번 spike에서 하지 않았다. 이름 소비자 전체가 동일 renderer라는 주장은 하지 않는다.

## 9. 명령/exit/재현 자료

프로젝트 root에서 실행한다. `audit.py`는 `commands.jsonl`에 argv/cwd/exit/log를 저장하며 각 에뮬 실행은 자체 `launch.json`, `commands.jsonl`, `stderr.log`, `exit.json`을 남긴다.

| 실제 실행 명령/작업 | exit | 출력/증거 |
|---|---:|---|
| CMake configure/build (`mgba-build/`) | 0 / 0 | `configure.log`: Configuring/Generating done; `build.log`: `[100%] Built target mgba` |
| 최초 기존 하네스 clang | 1 | `compile-original.log`, 0.11 API 차이 오류 |
| 호환 하네스 clang | 0 | `compile-adapted.log`, `compile-rpath.log`; 이후 launch ABI 실패는 별개 |
| ABI define 일치 clang (`python3 .../compile.py`) | 0 | `compile-matched-defines.log` |
| `python3 .../replay_normal.py` | 0 | `replay-normal.log`: driver exit 0, save size 131072, equal to earlier True |
| `python3 .../replay_cold.py` | 0 | `replay-cold.log`: `COLD_RELOAD_NATIVE8_VERIFIED` |
| `python3 .../probes.py` | 0 | `input-probes.log`, 각 11 case exit 0 |
| `python3 .../trace_fresh.py` | 0 | `runtime-trace.log`, 생성/append 실제 register trace |
| `python3 .../trace_more.py`, `trace_final.py` | 각 0 | `more-traces.log`, `final-traces.log`, lookup/free/표시표 trace |
| `python3 .../space_cancel.py` | 0 | `space-cancel.log`, trailing trim/취소 |
| `drive.py space-internal < .../space-internal/route.txt` | 0 | `space-internal/driver.log`, `exit.json`, middle-space save |
| `python3 .../consumer_final.py` | 0 | `consumer-final.log`, MULTI-PAK/저장 상단 trace |
| `cstool thumb ...` 초기 선형 시도 | 252 | `disasm-name-code.log`: invalid assembly code. C capstone skipdata 도구로 전환 |
| C disassembler 빌드/실행 | 0 | `compile-disasm*.log`, `disasm-native.log`, `disasm-state.log`, `disasm-allocator.log`, `disasm-iwram.log`, `disasm-space-trim.log` |
| `python3 .../verify_evidence.py` | 0 | `verification.log` 아래 원문 |

검증 출력(검사 범위 제한 포함):

```text
VERIFIED: 원본 SHA/크기, 정상 키 새저장, cold reload 8자, 9번째 덮어쓰기, 중간 공백 보존/끝 공백 제거, 취소, IWRAM 복사 일치
ROM_SHA256 a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c
NEW_SAVE_SHA256 d6e2651201c497139a4235034ed5d922816e1c2d2dd3c487ebf87d553ceeb481
HARNESS_SHA256 dfcd4c76b2d60940383e34d2027860763f4139a82819c484d37afab74dfac614
LIBMGBA_SHA256 eccdd98390afbe198259bde4550f4a7dc54b706edb0172a562b03de3c521fff1
TRACKED_STATUS: clean
NOT_VERIFIED: 한글 ROM hook, safe scratch, 모든 소비자, Link handshake, b44 동등성, upstream source commit
```

재생은 `python3 temp/name-grid-phaseB/native-re/replay_normal.py`, `python3 temp/name-grid-phaseB/native-re/replay_cold.py`. 저장 export는 O_EXCL이므로 기존 산출물을 덮어쓰지 않는다. 재실행하려면 이 워커 소유 출력 폴더만 별도 이름으로 보관하거나 script의 실행 이름/출력명을 바꿔야 한다. 원본/최종 정상 새 저장을 지우라는 뜻이 아니다. SHA inventory는 `evidence-sha256.json`.

## 10. 승인 계획 대비 차이와 다음 조사

사용자 승인 조사 범위를 넘지 않았다. 환경 부재/DNS 차단 때문에 Homebrew 0.10.5 대신 로컬 vendor 0.11 소스 복사 + temp 하네스 API/ABI 대응이 필요했다. upstream source commit 인증은 남았다. 새로운 게임 기능 패치나 후보 빌드는 하지 않았다.

후속 계획/검증에서 남은 것:

1. b44/candidate 정본을 복구하고 별도 SHA 대조. 원본에서 얻은 함수 bytes/복사 경로가 후보에 그대로 적용되는지 확인.
2. state의 안전한 소유권/수명/초기화/해제를 확정. 0x70 객체에 공간이 남는다는 가정 금지. 필요하면 승인 계획에서 확장/별도 allocation을 선택.
3. 모든 입력 분기와 renderer 실행 위치를 반영한 Fable 계획 + Astra 승인. 이번 예상 bytes는 승인/구현이 아니다.
4. Phase A 공백·완전 8자·active 편집 계약을 native trailing trim/8번째 overwrite와 대조. 참조 모델 2350/2345 결과를 ROM 결과로 바꾸지 않음.
5. Versus custom category의 실제 도달 조건 조사. 두 HQ 추가만으로 도달한다고 단정하지 말 것.
6. Link handshake를 수행할 환경/범위를 정한 뒤 목록/이름 renderer trace. 통신 전 목록을 보았다고 보고하지 않음.
7. 후보 예약 한글·자모 atlas·다른 consumer renderer·메모리 충돌/공유 A3 가나 무손상·실기 동작은 전부 (unverified). 이번 원본 RAM 실험으로 대신하지 않음.

후속 반영: tracked 문서에는 없음 — 명시된 worker 소유권이 temp 영역으로 제한되어 있다. 총괄이 위 새 사실(특히 IWRAM 실제 경로, native trailing trim, 8번째 overwrite, 0x70 allocation)을 승인 계획 및 영구 RE 문서에 반영해야 한다.

## 11. 종료 정리

이 워커가 실행한 에뮬/빌드/스크립트는 모두 종료했다. 추가 워커/claim/워크트리/stash/브라우저/서버 작업은 만들지 않았다. 조사·재현 증거인 본 temp 디렉터리는 인계 산출물로 보존한다. 최종 `git status --short` 출력 없음.

`harness-session-check status`는 D1 0건/보고 2건. 보고된 Downloads의 택시 길찾기 API 요금비교 HTML/PDF는 이 워커가 만든 것이 아니며 R3/info·ambiguous라 수정/삭제하지 않았다. 다만 샌드박스로 wt_seq/windows 공유 락 실패 및 ps EPERM을 보고했으므로 이 자동 검사 전체를 정상 완료라고 부르지 않는다. `cleanup.log`에 마지막 출력/exit를 보존한다.

RECEIPT: model=unknown effort=unknown role=code
