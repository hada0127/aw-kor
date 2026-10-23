# ARM7TDMI C → ELF → raw 선행조사 (2026-10-23)

트랙: spike. 완료 기준: 두 C 함수/const 배열 보존, ARMv4T Thumb-1 확인, 링크 재배치 해소·미해결 심볼 0, ELF section/raw 바이트 일치. 아래 증거는 독립 샘플만 대상으로 한다.

## 확인 순서와 도구

1. [Clang cross compilation](https://clang.llvm.org/docs/CrossCompilation.html), [GNU ld scripts](https://sourceware.org/binutils/docs/ld/Scripts.html), [objcopy](https://sourceware.org/binutils/docs/binutils/objcopy.html) 공식 문서에서 target/CPU 지정, `-T` section 배치, binary 추출을 확인했다. 추가 참고: [Clang flags](https://clang.llvm.org/docs/ClangCommandLineReference.html), [ld DISCARD](https://sourceware.org/binutils/docs/ld/Output-Section-Discarding.html).
2. 설치 `--version`/`--help` 확인: Apple clang 21.0.0 (clang-2100.3.34.2); `/opt/homebrew/bin/arm-none-eabi-{ld,objcopy,nm,readelf,objdump}` 모두 GNU Binutils 2.47.20260726. 실제 원문은 `stdout.log`에 있다.
3. 레포 `rg` 확인: `tools/test_part2_terrain_movement_labels.py:23` 및 `candidate-re/toolchain.py`에 clang ARM object 컴파일 예가 있다. 이 검색 범위에 C→GNU ld→raw 완성 예는 없었다. 기존 도구는 실행하지 않았다. 첫 탐색에서 없는 `scripts` 경로 때문에 rg exit 2가 있었고, 존재하는 tools/candidate-re 대상으로 재검색하여 exit 0을 얻었다(후자 stdout.log).

## 샘플과 실행 명령

산출물은 이 디렉터리만: `sample.c`, `sample.ld`, `sample.o`, `sample.elf`, `sample.bin`, `sample.map`, `verify.py`, `stdout.log`, `verification.log`, 본 보고서.
`sample.c`는 `proof_entry`가 noinline `proof_leaf`를 호출하고 4바이트 const 배열을 동적 인덱스로 읽는 독립 예다. 게임 조합 로직은 없다.

아래 컴파일·링크·추출 명령은 이 디렉터리를 cwd로 실행했고, 모두 stdout/stderr 빈 출력 및 **EXIT 0**이었다. readelf/nm/objdump도 모두 EXIT 0이며 전체 원문은 `stdout.log`다.

```sh
clang -target armv4t-none-eabi -mcpu=arm7tdmi -mthumb -ffreestanding -fno-builtin -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -Os -Wall -Wextra -Werror -c sample.c -o sample.o
/opt/homebrew/bin/arm-none-eabi-ld -T sample.ld --no-undefined --fatal-warnings -Map=sample.map -o sample.elf sample.o
/opt/homebrew/bin/arm-none-eabi-objcopy -O binary --only-section=.image sample.elf sample.bin
/opt/homebrew/bin/arm-none-eabi-readelf -h -A -S -r -s -W sample.elf
/opt/homebrew/bin/arm-none-eabi-nm -n -S sample.elf
/opt/homebrew/bin/arm-none-eabi-nm -u sample.elf
/opt/homebrew/bin/arm-none-eabi-objdump -d -s sample.elf
```

`-target/-mcpu/-mthumb`가 ARM7TDMI Thumb 프런트엔드를 지정한다. `-ffreestanding/-fno-builtin`으로 hosted/builtin 가정을 배제하고, stack protector/unwind 플래그를 명시했다. 이 샘플에는 나눗셈·부동소수·메모리 복사·외부 호출이 없고 ld에 object 하나만 전달하므로 libc/startup/runtime 라이브러리 링크가 없다. 이 플래그들이 임의의 C에서 helper를 막는다는 보장은 아니다.

실측상 unwind 비활성화 플래그에도 object에 cant-unwind `.ARM.exidx` 16바이트가 생겼다. 예외/스택 풀기를 하지 않는 이 독립 샘플에서만 linker script `/DISCARD/`로 제거했다. `.comment/.note.GNU-stack`도 제외하고 `.ARM.attributes`는 비할당 section으로 보존했다. `.text` 30바이트와 `.rodata` 4바이트를 단일 `.image`로 합쳤다. 게임용 linker 정책으로 승인된 것은 아니다.

## 실제 결과

- object `.rel.text`의 `R_ARM_ABS32 proof_values`, `R_ARM_THM_CALL proof_leaf`가 링크 후 해소됐다. readelf: `There are no relocations in this file.`
- `nm -u sample.elf`: 출력 없음, EXIT 0. ELF null symbol을 제외한 named undefined 0개를 독립 검사로도 확인했다.
- ELF `.image`: VMA 0x08F70000, file offset 0x1000, section size 0x22=34바이트, 유일한 SHF_ALLOC section. ELF 파일 전체는 4708바이트이며 raw는 34바이트다.
- `nm -n -S`: `08f70000 00000010 T proof_leaf`, `08f70010 0000000e T proof_entry`, `08f7001e 00000004 T proof_values`. 단일 실행 section에 합쳤으므로 nm은 const도 T로 표시한다.
- nm은 함수 주소 Thumb bit를 정규화한다. readelf 실제 FUNC 값은 leaf=0x08F70001, entry=0x08F70011이다. raw 함수 offset은 각각 0x0/0x10. ELF entry=0x08F70011, Thumb bit=1. raw 자체에는 entry 메타데이터가 없다.
- attributes: `Tag_CPU_name: "arm7tdmi"`, `Tag_CPU_arch: v4T`, `Tag_THUMB_ISA_use: Thumb-1`. `Tag_ARM_ISA_use: Yes`도 있으나 실제 두 함수는 Thumb mapping `$t`와 Thumb 명령으로 역어셈블된다.
- objdump: `8f70012: f7ff fff5 bl 8f70000 <proof_leaf>` (Thumb-1의 두 halfword BL), 나머지는 movs/ands/ldr/ldrb/adds/bx/push/pop. Thumb-2 명령은 없다. literal `0x08F7001E`와 배열은 `$d` 데이터이며 명령어로 세지 않는다.
- `python3 temp/name-grid-phaseB/arm-link-proof/verify.py`: ELF32 section header를 직접 파싱하여 `.image` file bytes와 objcopy raw를 비교했다. 실제 출력:

```text
ELF file size=4708; .image offset=0x1000; size=34; raw length=34
ELF .image bytes == objcopy raw: PASS; relocation sections=0; alloc sections=.image only
proof_entry: ELF symbol=0x08f70011; Thumbbit=1; raw offset=0x10; function size=14
proof_leaf: ELF symbol=0x08f70001; Thumbbit=1; raw offset=0x0; function size=16
ELF entry=0x08f70011; Thumbbit=1; named undefined symbols=0
SHA256 sample.c (361 bytes) af31f3ace9bdb3c96b34f018a8b85d74e94710236cbbc8c7ff2f83a8d1b458e7
SHA256 sample.ld (333 bytes) 6b925860a6eb1d62dbdab7fbfac82c45cc4a3df60cc01033841d8a8c815b6d55
SHA256 sample.o (1028 bytes) eecdac285e2b7b8e30458fd4849295d918562f8650bd2d1a964d85c274f553e2
SHA256 sample.elf (4708 bytes) 3af0a85d9205595dc29c2a9bc6838379688f9b3340146acdbfe4d6b62f204991
SHA256 sample.bin (34 bytes) 21abdf12525b4993b70dca3b5102f46ca50e3e89f23964ef4638bd25ab0f19dd
EXIT 0
```

## 한계·인계

PLAN 대비 어긋난 점: 없음. 승인된 구현 PLAN 대신 이번 선행조사 지시 범위만 수행했다. 위 주소는 **가짜 임시 링크 주소**이며 ROM free 공간 할당/삽입 승인이 아니다. literal 주소가 고정돼 있으므로 다른 주소에 배치하려면 재링크해야 한다.

게임 ROM/원본 실행 경로·에뮬레이터·생산 코드·데이터·추적 문서는 건드리거나 실행하지 않았다. commit/push/새 워커/라이브러리 설치 없음. 샘플의 런타임 동작·게임 ABI/스택/호출 거리·실제 빈 공간은 (unverified). Fable 계획에 넘길 도구 경로 증거이며 구현 승인이 아니다. 후속 반영: 없음 — temp 한정 실험이며 생산 규칙 변경은 금지된 범위다. 본 디렉터리 산출물은 총괄 인계용으로 보존한다. 세션이 새로 띄운 장기 프로세스/브라우저/워크트리/claim/stash는 없다.
