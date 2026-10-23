# 복구 후보·b44 이름 렌더러 및 state 확장 선행조사

2026-10-23 · 트랙: spike · Mac arm64 · 역할: code
기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`, 브랜치 `sweep3-p2-20261023c`.
범위는 `temp/name-grid-phaseB/candidate-re/`뿐이다. 생산 코드/ROM 훅 구현, tracked 문서 수정, 새 워커, commit/push, 원본 savestate 재사용은 하지 않았다. **Fable 계획과 Astra 승인 이전의 조사 자료이며 구현 승인이나 이름 조합 완성이 아니다.**

## 결론과 완료 기준

1. **후보 기존 A3 렌더러는 대표 예약 음절 `가/한/글`을 그린다.** 이름 preview에서 7자 `가한글가한글가`를 표시하고 VRAM의 3개 글리프 192바이트가 후보 ROM의 해당 타일과 같음을 대조했다. 원본의 `?` 결과를 후보 기능 부재로 일반화하면 안 된다.
2. **후보에서 RAM에 넣은 완성 한글 8자 `가한글가한글가한`을 게임의 확인·저장 경로로 새 cartridge save에 기록했다.** 별도 프로세스의 후보 및 b44 cold boot가 같은 16바이트/length=8을 읽었고 불러오기 목록·맵 preview·이름 재입장 화면을 확인했다. 저장 체크섬은 게임이 생성했다. 조합 키 입력 구현의 증거는 아니다.
3. **추가 consumer 훅이 필요하다는 근거는 이번 대표 사례에서 나오지 않았다.** 조사한 consumer의 기존 glyph kernel을 재사용할 수 있다. 자모 40개·2350자 전체·Versus/Link 사용자 이름은 (unverified)이며 추가 훅 불필요를 전역 결론으로 삼지 않는다.
4. **기존 allocator로 `0x70→0x80` 객체를 확장하는 계획의 구체 입력을 확보했다.** 새 tail의 소유권·초기화·해제를 명시하면 고정 scratch나 기존 tail 재사용보다 단순하다. 이번에 크기 상수나 객체를 변경하지 않았으며 안전 승인도 하지 않았다.
5. ARM7TDMI Thumb freestanding C `.o` 생성과 역어셈블은 exit 0. linker/objcopy는 PATH에서 발견하지 못했다. 최종 링크·재배치 파이프라인은 (unverified).

## 자산·실행 정체성

| 대상 | SHA-256 |
|---|---|
| 원본 ROM | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |
| 후보 `output/game_wars_korean_namegrid_baseline_20261023.gba` | `ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a` |
| b44 `output/game_wars_korean_b44_reference_20261023.gba` | `1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02` |
| 기존 조사 `native-re/mgbah` | `dfcd4c76b2d60940383e34d2027860763f4139a82819c484d37afab74dfac614` |
| 기존 조사 `native-re/mgba-build/libmgba.0.11.0.dylib` | `eccdd98390afbe198259bde4550f4a7dc54b706edb0172a562b03de3c521fff1` |
| 해당 실행 파일 source `native-re/mgba_harness_011.c` | `64ea970bef021646a08ba86e8d09189af778051ad0000017285e818c393370b8` |
| 파생 `drive.py` | `3e28fbb58ef8d9260f28ed20e932af913bfbdd1fe5cb1d341a00ae6cb2f7705e` |
| 새 최종 저장 `eight-save/hangul.sav` | `9e3ab43b99f3ded2c868674adab727c7a0fe651e99e7441ab7a89fab681c86d0` |

원본/후보/b44 각각 16,777,216바이트, 새 저장 131,072바이트. 기존 하네스와 ABI 일치 라이브러리를 그대로 읽기 전용 재사용했고 다시 빌드하지 않았다. upstream mGBA release와의 동일성은 이전 조사와 마찬가지로 (unverified).

`drive.py`는 기존 driver의 ROM argv와 출력 root만 파생 변경하고, 동일 바이너리·라이브러리를 명시한다. 모든 emulator argv/env는 각 실행 `launch.json`, 키/프레임/명령 응답은 `commands.jsonl`, 종료는 `exit.json`, 상위 호출은 `runs.jsonl`에 있다. `AW_KOR_TEMP_DIR`·`TMPDIR`는 소유 temp 경로다. `nice -n 15`는 실제로 `setpriority: Operation not permitted`여서 우선순위 적용에 실패했다. 새 전체 빌드는 하지 않았다. `vm_stat`에서 page size=16,384, free=48,831 pages, `df -h .`에서 available=334GiB를 관찰했다. 프로세스별 RSS는 (unverified).

## A. 후보 cold boot·IWRAM 복사·정확한 renderer

시작은 원본 조사에서 **정상 키만으로 새로 만든** `native-re/replay-normal/new-eight.sav`를 cartridge save로 넘겼다. 후보 첫 프로세스는 cold boot하고 `candidate-cold/route.txt`의 정상 키로 이름 화면에 도달했다. **다른 ROM savestate는 읽지 않았다.** 이후 분기는 여기서 처음 만든 후보 전용 `candidate-cold/name.ss0`만 읽는다. b44는 후보 savestate를 읽지 않고 새 cartridge save로 cold boot했다.

주소를 바로잡는다. `0x08A3C7E4 → 0x03006080` 대응은 함수 내부의 기존 명령 위치이며, **현재 source의 실제 8바이트 트램펄린 site는 `0x08A3C7E8 → 0x03006084`**다. `candidate-cold/iwram.bin`은 ROM `0x08A3C7C0..0x08A3C934`의 0x174바이트와 같다.

```text
03006080: 09 0c 00 91
03006084: 00 4a 10 47 81 02 f3 08
                       target = 0x08F30281 (Thumb)
```

`candidate-cold/copy.log`의 순서는 boot 초기화 0..15 뒤 BIOS 복사 16..23이다. 복사 hit에서 `pc=00000288`, `r0=08A3C7E8 / 08A3C7EC`, `r1=03006080 / 03006084`가 관찰됐다. BIOS callback의 r0/r1은 진행 후 값이므로 이 값 하나로 소스 오프셋을 추정하지 않고 최종 전체 bytes 비교와 함께 판단했다. `candidate-cold/commands.jsonl`에서 cold boot 첫 `frames 600` 응답 이전에 이 복사가 발생했다. 정확한 cycle/frame 내부 시각은 (unverified).

### 대표 코드·테이블·marker

`table-audit.json`, `a3-disasm.log`:

| 음절 | 코드 | relocation entry | entry bytes |
|---|---|---|---|
| 가 | 8840 | 08F20C90 | `884000800180` |
| 한 | 92AF | 08F2405C | `92aff2820382` |
| 글 | 888A | 08F21020 | `888a4c800780` |

실제 table start/end는 `08F20000 / 08F243A4`: **17,316바이트, 2,886 entries**다. 원본 부분은 536 entries이고 한글이 2,350 entries다. 이전 문서의 530 entries 표현을 실제 table 길이로 쓰면 안 된다. `static.log`의 17,280바이트 SHA는 초기 부분 표본 hash이며 전체 테이블 길이의 근거가 아니다. 전체 경계의 근거는 실제 A3 literal 및 `table-audit.json`이다.

A3 조건은 low byte > 0x3F, `8840 ≤ code ≤ E2A7`, 해당 relocation entry 존재, top index의 bit15 marker다. bit15를 제거한 top/bottom index×32를 `08F00000`에 더해 VRAM glyph-cache로 복사한다. range 안이라는 이유만으로 모든 코드를 한글로 취급하지 않는다.

`focused-render/runtime.log`에서 `pc=08F302B6` callback은 code r3=`8840`, entry r6=`08F20C90`을 기록했다. 복사 진입 callback `pc=08F302DA`에서 가의 source r6=`08F00000`, destination r7=`06002620`; 한은 `08F05E40→06002660`, 글은 `08F00980→060026A0`다. watch는 실제 `06002620` store `pc=08F302DE`를 관찰했다. `focused-render/glyph-cache.bin`의 3×64바이트는 각 top/bottom ROM 타일과 정확히 같다.

### 원본 `?`와 후보의 차이

기존 원본 증거 `native-re/fallback-trace/runtime.log`는 8840 lookup 실패 뒤 `8148`로 fallback함을 보여 준다. 후보에서는 IWRAM trampoline→기존 A3 확장 table/marker 경로가 이 lookup을 처리한다. 이번 후보 대표 3음절에는 `?`가 재현되지 않았다. 원본 실패 원인은 원본 dictionary의 node 부재이며, 후보에 추가 consumer 훅이 없어서 실패한다는 가설은 이번 경로에서 반증됐다.

캐시는 같은 글자를 여러 번 요청해도 매번 glyph kernel을 호출하지 않는다. `candidate-render`의 7자에는 세 종류 코드에 대한 실제 A3 진입 세 번이 기록됐다. RAM 값만 변경하고 R을 눌렀던 `candidate-probe-small`은 redraw가 없어서 옛 가나가 남았다. 이를 parser 실패나 한글 미지원으로 해석하지 않았다. B키로 마지막 pair를 지워 네이티브 redraw를 발생시킨 `candidate-render`와 `focused-render`를 표시 근거로 사용한다.

## B. 새 native 저장·별도 cold reload

최종 대표 이름은 `가한글가한글가한`이다.

```text
16 bytes = 88 40 92 af 88 8a 88 40 92 af 88 8a 88 40 92 af
length=8, slot_limit=8, native_copy_length=16
```

`eight.py`는 후보 전용 savestate에서 **live name `0200303C`의 16바이트만 RAM 변이**한다. 기존 8슬롯 length를 유지하고 START→확인→편집기→저장 메뉴→덮어쓰기 확인은 게임 정상 키로 처리한다. 이름 자체를 native 자모/한글 키 입력으로 만든 것은 아니다. ROM·저장 파일을 직접 패치하거나 host에서 checksum을 생성하지 않았다.

`eight-save/destination.bin`은 위 16바이트와 같다. 새 SRAM의 이번 활성 기록은 `0x1F504..0x1F513`이며 같은 16바이트다. 기존 원본 저장의 `0x1E504` 레코드는 옛 `8341`×8을 유지한다. 따라서 고정 첫 주소 하나만 검사하면 새 저장에 실패했다고 오판할 수 있다. 두 레코드 전체의 bank 선택/checksum 포맷을 완전히 해석한 것은 (unverified).

| 소비자 | 실제 근거 | 입력·kernel·VRAM |
|---|---|---|
| 이름 preview | `focused-render/hangul.png`, `consumers-final/ready.png` | live `0200303C`→임시 문자열 `03007D38`; parser read `0831425A/08314336`, 제출 `08314EB0`, glyph caller LR=`0831BBED`, kernel `08F30280`; `focused-render/runtime.log`의 `06002620` watch와 192바이트 대조 |
| cold 불러오기 목록·동시 맵 preview | `candidate-eight-reload/cold-list.png`, `consumers-final/cold-list.png` | 문자열 `0200B204` 읽기 및 A3 copy 진입을 `consumers-final/runtime.log`에 기록; 제한 VRAM watch `06002620`도 같은 로그에 있음. 맵 preview는 목록과 같은 화면의 배경으로 확인했으며 별도 이름 HUD가 있다는 주장은 안 함 |
| 저장 화면 상단 이름 | `eight-save/heading.png`, `heading-final/heading.png` | `0200B09C` 읽기, `08314EB0`, A3 copy 진입과 `06002300/06002620` 제한 watch를 `heading-final/runtime.log`에 기록. VRAM 최종본 `heading-final/vram.bin` |
| map load 뒤 이름 재입장 | `candidate-eight-reload/reentry.png`, `consumers-final/ready.png`, `ready.bin` | live와 destination 모두 16바이트 일치, length=8. `consumers-final/runtime.log`에 entry/constructor·A3 trace. 재입장 안내를 A 한 번으로 닫은 뒤도 8자 그대로 확인 |
| b44 대표 비교 | `b44-eight-reload/cold-list.png`, `reentry.png`, `name.bin`, `destination.bin` | 별도 b44 cold boot + 새 cartridge save만 읽음. 동일 16바이트/length8과 화면. A3 진입 `consumers.log`, IWRAM dump 보존. b44 전 consumer별 VRAM 바이트 재대조는 (unverified) |

각 VRAM watch 로그에는 화면 전환/초기화와 다른 문구의 hit도 포함된다. watch 존재만으로 모든 hit를 이름 복사라고 집계하지 않는다. 대표 glyph 3개의 실제 ROM→VRAM 일치는 `focused-render`로 한정한다.

### 실패·수정된 검증 경로도 보존

- `candidate-probe`: VRAM 전체 98,304바이트에 watch를 하나씩 등록해 비효율적인 실행이 됐다. Ctrl-C로 wrapper exit 130, emulator exit -2, `exit.json`을 보존했다. `pkill`은 process-list 접근 실패(exit 3), 별도 셸 `kill`은 샌드박스 EPERM(exit 1)이었다. 같은 PTY 세션의 Ctrl-C로 종료했고 이후 `lsof`에서 해당 로그를 연 프로세스가 없었다. 네 바이트 watch로 줄인 후 성공했다. 기능/ROM 수정은 없었다.
- 초기 `candidate-reload`/`b44-cold`는 이전 원본 route 끝의 A 두 번 때문에 이름 화면 진입 뒤 한 글자가 추가됐다. 원본은 이미 8자 같은 가나라 눈에 띄지 않았던 route 부작용이다. `cold_exact.py`가 두 입력을 제거하고 `consumer_trace.py`가 안내 닫기 한 번만 분리했다. 초기 결과를 정확한 loaded name 근거로 쓰지 않는다.
- 7자 저장에서는 필드가 `884092af888a884092af888a88400041`이었다. native 문자열 끝의 첫 byte가 0이고, 그 다음 byte의 과거 `41`이 남는다. destination의 16바이트 전부가 항상 zero padding 그대로 SRAM에 저장된다고 보장할 수 없다. 최종 8자 사례는 종료자 없는 16바이트를 정확히 검증했다. 짧은 이름의 trailing 정규화와 Phase A serialize 계약의 접점은 후속 계획에서 명시해야 한다.

## C. allocator 기반 state 확장 계획 입력

근거: `native-re/disasm-allocator.log`, 이번 `name-module-disasm.log`, `constructor.log`, `confirm.log`, `call-sites.json`, `lifecycle/runtime.log`. 후보의 allocator `315288..3153B0`와 이름 코드 `34A954..34BA14`는 원본과 byte-identical이다.

### 할당/해제의 구체 계약

- `0834B974 mov r0,#0x70` → `08315300` → `08315288`. size를 `(size+15)&~15`로 올림하고 헤더 16바이트를 관리한다. 반환은 header+16, free-list 순회/분할이다. `r0=0` 반환 경로가 있다. **객체 payload 전체 zero 초기화는 없다.**
- 전역 소유 pointer `03004650`. 이번 반환 `02003010`, 다음 block header `02003080`은 실행 사례다. 절대 고정 주소로 쓰면 안 된다.
- free `08315390`→`08315324`: pointer-16 헤더에서 크기/다음 block/used를 읽고 인접 free block을 합친다. free가 caller의 `0x70` size 상수를 별도로 받지 않는다. 따라서 allocation header가 0x80을 소유한다면 원래 free 경로로 해제하는 구조다. 이 확장을 실제 실행 검증한 것은 아니다.
- `0834B9C4`는 destination=r0, max_slots=r1 하위 8비트, mode=1, +62=max_slots, +63=2*max_slots, +5C=destination을 설정한다. 편집기 실측은 r0=`0200B09C`, r1=8. 다른 entry `0834B988`은 mode=0 경로이며 직접 호출/등록 pointer는 이번 정적 스캔에서 발견하지 못했다. 임의 r1까지 안전하다는 뜻은 아니다.
- UI constructor `0834A9FC`는 cursor/animation/+67,+65,+66,+68,+6A 등을 개별 초기화한다. `+2C` live와 `+44` 이전 버퍼를 보존해야 한다. +61은 현재 길이, +62는 슬롯 상한, +63은 복사 바이트 수다.
- confirm `0834B00C`는 +5C destination, `0834B012`에서 trailing trim 후 +63을 상한으로 byte loop 복사한다. 전체 0x70 복사가 아니다. cancel은 destination에 복사하지 않는다.
- destructor `0834BA00`→free는 cancel과 confirm 뒤 모두 hit. 이번 `lifecycle/runtime.log`의 순서는 free(02003010) → entry(8 slots) → allocator(return02003010) → UI constructor → free(02003010)다. 재진입 주소가 같았다는 사실은 지속 소유권의 근거가 아니라 allocator 재사용의 증거다.

### call-site/크기 의존 조사 범위

전체 ROM의 halfword-aligned Thumb BL 및 word-aligned Thumb 함수 pointer를 스캔했다(`static_audit.py`). 데이터가 우연히 명령 패턴인 경우와 간접 계산 호출은 스캔만으로 판별할 수 없어 후보 목록으로 보존했다.

- entry B9C4 직접 BL은 `08304922` 한 곳. runtime LR=`08304927`과 부합한다.
- allocation callback B970 pointer=`0883FD58`, UI constructor A9FC pointer=`0883FD78`, destructor BA00 pointer=`0883FE30`. 주변 script 데이터와 runtime의 `083162A3` dispatch LR이 부합한다. 이 callback들을 놓치면 직접 BL이 없다는 이유로 dead code로 오판한다.
- 이름 모듈 `0834A954..0834BA14`의 선형 역어셈블에서 payload size 0x70을 설정하는 명령은 allocation B974다. 다른 `#0x70/#0x6C` 문자열 hit는 PC-relative literal load이며 payload copy 상수가 아니다. 확인한 코드에서 전체 0x70 memcpy/stride는 발견하지 못했다. 선형 disassembly literal 해석과 제한적 data-flow 조사이므로 전 ROM 모든 간접 reader의 완전 부재 증명은 아니다.
- 이번 조사 범위에서 객체 +70 이후를 쓰는 기존 field 접근은 발견하지 못했다. 이것을 기존 0x70 tail/neighbor 사용 허가로 바꾸지 않는다. 기존 payload 전체 0x00..0x6F는 원형 보존한다.

### Fable 계획에서 고정할 최소 사항 — 구현하지 않은 제안

| 선택 | 소유권/수명 | 필요한 변경·주의 |
|---|---|---|
| 객체 0x80 확장 | 원래 allocator가 원래 payload+새 16바이트를 한 번에 소유, 기존 destructor에서 해제 | B974 요청 size만 아니라 생성 후 새 영역 초기화, entry 재설정, load 뒤 committed 복구, 8슬롯/partial flag 계약을 함께 계획 |
| 별도 0x10 allocation | 별도 pointer의 명시 소유권 필요 | 추가 allocate 실패·pointer 저장·양쪽 free 순서·중복 해제 방지·부분 생성 정리까지 필요. 현재 요구에 비해 경로가 늘어남 |

선행조사상 첫 안이 더 작은 변경이다. 이를 승인으로 보지 않는다. 제안 layout은 +70 committed_count(u8), +71 active_present(u8), +72 L(u8), +73 V(u8), +74 T(u8), +75 padding, +76 current_candidate(u16), +78..+7F reserved다. **아직 확정 ABI가 아니며 현재 어느 byte도 사용하지 않는다.** L/V의 absent sentinel을 FF로 정하면 zero clear만으로 초기화 완료가 아니므로 active=0, L/V=FF, T=0, candidate=0, count=0 등을 명시해야 한다.

필요한 실행 계약은 (1) allocation 성공 후에만 새 tail 접근, (2) constructor/entry에서 새 영역 초기화하고 native load 이후 committed_count 복구, (3) count+active≤실제 +62이고 map entry에서는 ≤8, (4) 미완성 active를 live 저장 field에 섞지 않음, (5) 8번째 active 편집 허용·9번째 필요 시 원자 거부, (6) 취소/확정 재진입에서 새 상태를 재사용하지 않음, (7) 기존 free 한 번과 새 영역 수명 일치다. 할당 실패 처리는 기존 코드의 실패 의미를 조사한 뒤 계획에서 정해야 하며 임의 null guard로 대체하지 않는다. 모든 기존 경로 전수증명이라는 무한 gate를 추가하지 않고 이 구체 계약과 변경 경로를 검증 대상으로 삼는다.

## D. 가벼운 toolchain·ROM 공간 조사

공식 Clang [CrossCompilation](https://clang.llvm.org/docs/CrossCompilation.html)과 [명령행 문서](https://clang.llvm.org/docs/ClangCommandLineReference.html)를 확인한 뒤 설치본과 레포 사용례 `tools/test_part2_terrain_movement_labels.py` 및 `tools/asm/`을 읽었다. 기존 방식은 Thumb ASM을 clang ELF로 컴파일하고 ELF `.text`를 읽어 embedded bytes와 대조하는 방식이다. `build_korean_full.py`의 A3는 현재 `bytes.fromhex`와 명시 literal patch다.

`toolchain.py` 실제 원문 출력은 `toolchain.log`/`toolchain.json`:

```text
Apple clang version 21.0.0 (clang-2100.3.34.2)
clang -target armv4t-none-eabi -mcpu=arm7tdmi -mthumb -ffreestanding -fno-builtin -Os -c <소유경로>/hello.c -o <소유경로>/hello.o
EXIT 0
llvm-objdump -d -r <소유경로>/hello.o
file format elf32-littlearm
00000000 <hello>:
  0: 1c40  adds r0,r0,#1
  2: 4770  bx lr
EXIT 0
ld.lld None
llvm-objcopy None
arm-none-eabi-ld None
arm-none-eabi-objcopy None
```

objdump는 Xcode toolchain의 절대 경로를 썼다. linker/objcopy가 컴퓨터 어디에도 없다는 전수 검색 결론이 아니라 PATH와 조회한 일반 LLVM 설치 경로에서 부재라는 뜻이다. hello는 조사 폴더에만 있고 ROM 삽입하지 않았다. 실제 조합 C/ASM, 외부 helper, ABI 보존, relocation 해소는 (unverified).

### 구체 점유·zero-run (파일 offset, end exclusive)

`zero-runs.json`은 최종 후보의 길이≥256인 모든 연속 zero 영역, `direct-writers.json`은 builder 직접 slice/pack_into 190문장의 원문·line, `writer-addresses.json`은 정적으로 해석한 FILE 상수 30개, `integrity-ranges.json`은 **같은 후보 빌드**의 manifest 40,055행 범위를 보존한다. manifest는 직접 writer/모듈 예약을 전부 포괄하지 않으므로 단독 allocator로 쓸 수 없다.

| 알려진 점유/예약 | 근거 |
|---|---|
| F00000..F09F20 한글 blob, F09F20..F09F60 주변 전용/보존 바이트 | builder blob 길이 assert/전용 index 처리 |
| F10000..F103C0 여러 1편 yes/no hook·표, F10400 legacy classifier 예약 | `writer-addresses.json`, builder assert. F103C0 이후 zero-run에 F10400 예약이 포함됨 |
| F20000..F243A4 relocation table | 실제 A3 start/end literal |
| F30000대 per-char/313/B11/A3 hook, F30280..F30324 A3 본체, F31F80 source gate, F32000 glyph block, F3F000 battle dictionary | 직접 writer·해석 상수. 세부 길이가 동적으로 정해지는 항목은 null 표시 |
| F40000..F42000 전까지 title table, F42000 이후 glyph blob | builder 경계 assert와 동적 길이. 미사용 바이트를 이 조사에서 양도하지 않음 |
| F51000..F5108E editor 도움말 dictionary 등 | 동일 build manifest |
| F66000..F70000 mission-title-fit 예약 (TABLE F66800, GLYPHS F68000) | `tools/part2_mission_title_fit.py` BASE/END. 마지막 비영 바이트 뒤도 예약에 포함 |
| FD0000..FD0098 decimal/comma node, FD0100..FD0148 fullwidth node, FD1000..FD105C dictionary, FD2000..FD2965 compressed glyph | 동일 build manifest |
| FFC000..FFD100 terrain movement 예약 | 해당 모듈 CAVE/CAPACITY 및 manifest |

주요 실제 zero-run:

```text
F6E587..FD0000 399,993 B   ← 앞부분은 mission-title-fit 예약 F70000까지와 겹침
FE3090..FFC000 102,256 B
F51238..F66000  85,448 B
F103C0..F20000  64,576 B   ← F10400 legacy 예약과 겹침
FD2965..FE0000  54,939 B
F31FEC..F3F000  53,268 B   ← F32000 명시 상수 구역 포함
F243A4..F30000  48,220 B
F09F60..F10000  24,736 B
```

후속의 Unicode 완성 lookup 11,172×2=22,344바이트, 자모 atlas 40×64=2,560바이트 합계는 **24,904(0x6148)바이트**다. 24,736바이트 zero-run 하나에는 둘 다 못 들어간다. 예를 들어 `F70000..F76148`은 이번 후보에서 모두 zero이며 위 mission 예약을 피하고 24,904바이트를 담을 수 있다. 이는 **계획 비교용 후보 범위**일 뿐 할당 허가·전체 builder ownership 증명이 아니다. 빌더 간접 모듈·미래 배치와 최종 assertion/등록을 Fable 계획에서 정해야 하며 이번에는 reserve/write하지 않았다.

### T1 실제 pool 잔여

`build_korean2350.extend_pool(original)`을 실제 호출했다. pool=3,326, 기존 mapping=2,350, 차집합=**976**. 첫 미할당 후보는 E2A8,E2AB,E2AD,E2AE,… (`pool.json` 전체). `data/reserved_codes.json` 표본 수로 추정하지 않았다. 이것은 텍스트/원본 한자 배제 규칙에 따른 pool 잔여이지 모든 consumer의 무충돌 승인 목록은 아니다. 첫 잔여 E2A8부터 현재 A3 max E2A7을 넘으므로, 자모 40개를 배정하기만 하면 그려진다는 결론은 틀리다. 승인 계획에서 기존 range/table/marker와 atlas 배치를 함께 정해야 한다.

## 실행 명령·exit·최종 검증

cwd는 프로젝트 root. 아래 경로 앞에 `temp/name-grid-phaseB/candidate-re/`를 붙인다. 모든 성공 emulator의 실제 stdout/stderr와 exit는 개별 디렉터리에 보존한다.

| 실제 명령 | exit | 원시 자료 |
|---|---:|---|
| `python3 .../run.py` | 0 | candidate-cold, cold boot/복사 trace |
| `python3 .../probe.py` 초기 전체 watch | 130 | candidate-probe/exit.json은 emulator -2 |
| `python3 .../probe.py` 작은 watch 및 B redraw 수정 실행 | 각 0 | candidate-probe-small, candidate-render |
| `python3 .../save_reload.py` | 0 | candidate-save, candidate-reload, b44-cold; 초기 route 부작용 위 설명 |
| `python3 .../cold_exact.py` | 0 | candidate/b44-reload-exact |
| `python3 .../eight.py` | 0 | eight-save, candidate/b44-eight-reload |
| `python3 .../consumer_trace.py` | 0 | consumers-final |
| `python3 .../lifecycle.py` | 0 | lifecycle/runtime.log |
| `python3 .../focused.py` | 0 | focused-render/runtime.log, glyph-cache.bin |
| `python3 .../heading_trace.py` | 0 | heading-final/runtime.log, vram.bin |
| `python3 .../static_audit.py > .../static.log` | 0 | call-sites/pool/zero-runs/direct-writers/integrity-ranges |
| `python3 .../ownership.py > .../ownership.log` | 0 | writer-addresses.json |
| `python3 .../toolchain.py > .../toolchain.log` | 0 | 내부 clang/objdump 각각 exit 0 |
| `native-re/disasm output/<후보>.gba 0xf30280 0x80` 및 34A9FC/34AFB0/34A954 구간 | 각각 0 | a3-disasm/constructor/confirm/name-module-disasm.log |
| `python3 .../verify.py > .../verification.log` | 0 | 아래 출력 |
| `git status --short`, `git diff --exit-code` | 0 / 0 | 빈 status, 검증 스크립트에서도 대조 |
| `harness-session-check status` | 0 | cleanup.log; 부분 검사 실패는 아래 설명 |

재실행은 기존 저장/증거를 덮어쓰지 않도록 `run.py` tag/output을 새 이름으로 지정해야 한다. 저장 export는 O_EXCL이다. 동명 폴더로 그대로 실행해 이전 증거를 혼합하지 않는다. 현재 `probe.py`는 B redraw의 작은 watch 버전이며 전체 watch 실패는 원래 `candidate-probe/route.txt`에 보존돼 있다.

최종 `verification.log`의 핵심 원문:

```text
PROTECTED_HASHES_UNCHANGED 45
NAME16 884092af888a884092af888a884092af
NATIVE_SAVE16 884092af888a884092af888a884092af OFFSET 0x1f504 SHA256 9e3ab43b99f3ded2c868674adab727c7a0fe651e99e7441ab7a89fab681c86d0
candidate-eight-reload COLD_NAME16_MATCH length=8 slots=8 bytes=16
b44-eight-reload COLD_NAME16_MATCH length=8 slots=8 bytes=16
IWRAM_COPY_0x174_MATCH TRAMP_03006084_TO_08F30281
VRAM_CACHE_GA_HAN_GEUL_3x64_MATCH_ROM_GLYPHS
TRACKED_STATUS_CLEAN
GIT_DIFF_EXIT0
```

원본/후보/b44·기존 하네스 source/executable/library·dist 전 파일 총 45개 해시를 전후 대조했다. 생산 파일 변경이 없으므로 전체 빌드/프로젝트 회귀 게이트는 재실행하지 않았다. 이전 후보 QA의 B팀114/overflow273/width507은 기존 기록이며 이번에 해결됐다고 주장하지 않는다.

## 남은 위험·계획 대비 차이·인계

- 완료된 조사 범위는 대표 3음절/한 저장 슬롯/한 이름8자다. 자모·2350 전수·legacy 전수·공백/빈 이름·실기·Versus 사용자 맵·Link 통신 이후 목록은 (unverified). 이전 한-core handshake 경계는 이번에 확장하지 않았다.
- state 확장 실구현, active 미완성 표시와 저장 금지, 부분 생성/실패·entry mode0의 실제 사용처, linker/relocation, 최종 ROM 공간 할당·consumer hook 결정은 Fable 계획+Astra 승인 전 미실시다.
- 7자 SRAM 종료자 이후 잔존 byte, 안내 뒤 A키의 추가 입력, 실제 trampoline 주소 +4 차이, 536개 원본 relocation entries는 후속 계획에 반영할 구체 사항이다.
- PLAN 이탈: 전체 VRAM watch 때문에 중단한 실험 1회가 있었고 제한 watch로 정정했다. nice 적용 실패를 기록했다. 기능/생산 범위 확대는 없다. 외부 교차 리뷰는 계약대로 총괄의 Astra 1명 담당이며 워커가 요청하지 않았다.
- 후속 반영: tracked 문서에는 없음 — 본인 temp만 쓰라는 명시 소유권 제한을 우선했다. 총괄이 이 보고서를 영구 문서/승인 계획에 반영해야 한다.
- 생성 파일은 이 디렉터리의 driver/run/probe/save_reload/cold_exact/eight/consumer_trace/lifecycle/focused/heading_trace/static_audit/ownership/toolchain/verify 스크립트, hello.c/.o, 보고서, JSON·로그·PNG·RAW·RAM·본인 savestate와 새 cartridge save뿐이다. `evidence-sha256.json`이 개별 파일을 식별한다. 이전 native-re 및 tracked 파일은 변경하지 않았다.

## 종료 정리

성공 emulator 전부 exit 0, 중단 emulator exit -2를 확인했다. 본 실행의 emulator.log들을 대상으로 `lsof -t <로그들>`은 stdout 빈 값/exit 1(열린 파일 없음)이었다(`owned-process-check.json`). 추가 워커·브라우저·claim·워크트리·stash·서버 작업·Downloads 파일을 만들지 않았다. 조사 증거는 총괄 인계를 위해 남긴다.

`harness-session-check status`: D1 0건/보고 0건, 그러나 B10 wt_seq lock 읽기와 windows.log 공유 락이 실패했다. ps EPERM은 프로세스 검사 불가로 분류됐다. 따라서 정리 검사 전체가 정상이라고 주장하지 않는다. 강제 종료 차단은 해당 세션 Ctrl-C로 해소했으며 남의 프로세스는 건드리지 않았다.

RECEIPT: model=unknown effort=unknown role=code
