# 공식 mGBA 0.10.5 컴파일 전용 환경 복구 보고

트랙: bounded. 기준 revision: `90908180938c2bf40ee38dea43c4c1304b09df8a`.
완료 기준은 공식 소스 보존, headless shared lib 및 기존 하네스 2개 컴파일, ABI/링크 정적 증거 확보다. GBA 실행·ROM 로드·프레임 진행·하네스 실행은 하지 않았다. live 기능은 `(unverified)`다.

## 소스 출처와 무결성

- 부모 제공 공식 archive URL: https://github.com/mgba-emu/mgba/archive/refs/tags/0.10.5.tar.gz
- 태그: `0.10.5`. 태그 commit: `26b7884bc25a5933960f3cdcd98bac1ae14d42e2` — 부모가 gh API로 확인했다고 브리프에 기록한 값이다. 이 워커는 네트워크 재확인을 하지 않았다.
- archive SHA-256은 아래 SHA256SUMS 참조. 브리프 기대값과 직접 대조했다.
- archive 내 regular file/디렉터리만 허용하고 절대경로·상위경로·링크를 배제해 추출했다. 최종 `source-verification.log`: `archive regular files byte-identical: 2580`.
- 공식 `version.cmake`는 major/minor/patch=0/10/5, ABI=0.10이다. `SKIP_GIT=ON`으로 바깥 프로젝트 git 정보가 release 버전으로 혼입되지 않게 했다.

## 산출물과 변경 범위

모든 생성물은 이 보고서와 같은 `temp/name-grid-phaseB/official-mgba/` 안에만 있다.

- `mgba-0.10.5/`: 원문 소스(수정 없음)
- `build/libmgba.dylib` → `libmgba.0.10.5.dylib`, `libmgba.0.10.dylib` symlink
- `mgbah`, `mgba_link_harness`: tracked 원문 C 파일에서 직접 빌드. 임시 호환 패치조차 필요 없었다. 0.11 어댑터 미사용, SIO driver 변경 없음.
- `build.py`, `verify.py`, `abi_probe.c`, `abi-*.s`, `abi-values.json`, `commands.jsonl`, 개별 `*.log`, `SHA256SUMS`: 재현 및 증거
- `run-single.sh`, `run-link.sh`: 후속 실행용 wrapper. `sh -n`만 실행했고 wrapper 자체는 실행하지 않았다.

tracked 코드/문서 변경, commit, push, 새 워커 생성은 없다. 외부 런타임 워커 디렉터리에는 쓰지 않았다.

## 컴파일/정적 검증 결과

`python3 temp/name-grid-phaseB/official-mgba/build.py` exit 0:

```text
[100%] Built target mgba
EXIT 0  (build)
EXIT 0  (compile-mgbah, 출력 없음)
EXIT 0  (compile-mgba_link_harness, 출력 없음)
```

Apple clang 21.0.0 / CMake 4.4.3 / arm64 Mach-O. CMake 4와 소스의 minimum 3.1 조합에는 `CMAKE_POLICY_VERSION_MINIMUM=3.5`를 외부 옵션으로 전달했다. 컴파일은 `nice -n 10`, 병렬 2개, `TMPDIR=<이 디렉터리>/tmp`로 수행했다. `memory.log`에 종료 시 vm_stat 원문을 보존했다.

Qt/SDL/GL/GLES/FFmpeg/Lua/외부 ZIP/SQLite/ELF/GDB frontend를 비활성화했다. 디버거 구조체와 PNG savestate 지원은 유지했다. CMake `USE_MINIZIP=OFF`는 외부 minizip 탐색을 끄며, 실제 lib C_DEFINES에는 bundled minizip의 `USE_MINIZIP`이 들어간다. 이것도 하네스에 동일하게 전달했다. libpng는 기존 Homebrew 1.6.58, zlib는 SDK/system 것을 사용했고 설치는 하지 않았다. Foundation/CoreFoundation은 공식 macOS backend의 링크 의존성이다.

공식 소스 경고(부호 비교·문자열 배열·const qualifier 등), 중복 -lm, libpng의 newer macOS deployment 경고가 존재한다(`build.log`). 하네스 컴파일 로그는 비어 있고 exit 0이다. 이 산출물은 현재 Mac용이며 구형 macOS 호환성은 `(unverified)`다. 하네스 Mach-O minos는 27.0이다.

`python3 temp/name-grid-phaseB/official-mgba/verify.py` exit 0:

```text
ABI compile-only constants MATCH ['4', '2408', '8', '2296', '2336', '152', '32', '7344', '32', '6288', '6496', '200', '48', '40']
Mach-O 64-bit dynamically linked shared library arm64
Mach-O 64-bit executable arm64   (mgbah)
Mach-O 64-bit executable arm64   (mgba_link_harness)
@rpath/libmgba.0.10.dylib (compatibility version 0.10.0, current version 0.10.5)
```

ABI: 생성 flags.h만 의존하지 않고 `build/CMakeFiles/mgba.dir/flags.make`의 전체 `C_DEFINES`를 양쪽 하네스에 적용했다. `abi_probe.c`를 라이브러리의 C_INCLUDES/C_FLAGS 조건(assembly 출력을 위해 LTO만 해제)과 하네스 조건으로 각각 assembly 컴파일하고 상수 14개를 대조했다. 순서/필드는 `abi-values.json` 참조. 핵심값은 color_t=4, mCore=2408, mCore.attachDebugger=2296, mCore.savedataClone=2336, GBA=7344, GBA.sio=6288, GBASIODriver=48이다. 비교용 프로그램도 실행하지 않았다. 전체 런타임 ABI와 기능 동작을 보장하는 검증은 아니다.

`otool -L`로 두 바이너리의 current 0.10.5 링크와 lib 의존성을 확인했다. `rpath.log`에는 `@executable_path/build`가 있다. `nm -gU` 심볼 목록은 `symbols.log`에 보존했다. 실제 dyld 로딩은 `(unverified)`다.

## 후속 실행용 wrapper 계약 — 이번 작업에서 미실행

두 wrapper는 자신의 디렉터리에서 root 경로를 구하고 다음 환경을 설정한다.

```text
TMPDIR=<official-mgba>/tmp/
AW_KOR_TEMP_DIR=<official-mgba>/runtime
DYLD_LIBRARY_PATH=<official-mgba>/build
cwd=<official-mgba>/runtime
```

이후 `<runtime>/temp/release_C/verify4b`를 생성한다. 링크 하네스의 고정 상대 private save 경로가 여기로 들어간다. 단일 하네스는 ROM 인자만 주면 `<runtime>/single.log`를 명시적으로 추가하여 `/tmp/mgba_swi.log` 기본값을 피한다. 인자가 두 개 이상이면 명시한 log를 그대로 사용한다. 단일 save는 `--write-save` 없이 기본 복사 경로를 사용해야 원본이 유지된다. 링크 save는 자체 private 복사 경로를 사용한다.

ROM/BIOS/save/log 인자는 반드시 절대경로로 지정해야 한다(cwd가 달라짐). stdin dump/shot/state/watch 로그 경로는 runtime 기준 상대경로 또는 이 소유 디렉터리 아래 절대경로로 지정한다. 링크 log는 원문 CLI대로 필수다. 기존 저장 파일을 인자로 전달할 뿐 wrapper가 새 저장 데이터를 발명하지 않는다. 실제 저장·정리·실행은 후속 런타임 워커 검증 대상이다.

## PLAN 대비 차이 / 남은 위험 / 정리

기능적 이탈 없음. 추출 초기 검사는 archive root entry의 trailing slash 가정으로 중단됐고, 두 번째는 기본 Python의 tarfile filter 미지원으로 중단됐다. 실제 추출 전 중단이었으며 regular file/디렉터리만 직접 복사하는 검증 후 추출로 해결했다. 소스 내용 수정은 없다.

라이브러리/하네스 build 작업 39439와 정적 검증 작업 9527은 모두 exit 0으로 종료했다. 새 에뮬 프로세스는 시작하지 않았다. 남긴 파일은 요청된 부모 인계 산출물이다. `harness-session-check status`는 D1 0건·보고 0건이지만 wt_seq/windows.log lock 증거 읽기 실패와 ps sandbox 거부를 보고했다. 따라서 이 검사로 전역 프로세스 상태를 확정하지 않는다. 다른 세션 프로세스를 종료하거나 파일을 수정하지 않았다.

`git status --short --untracked-files=no` exit 0, 출력 없음. 최종 HEAD는 위 기준값이다. 후속 반영: tracked 문서 수정 없음 — 이번 지시의 tracked 변경 금지에 따라 temp 보고서로만 인계한다. 실제 기능 검증은 총괄의 후속 배정이 필요하다.

## SHA-256 원문

```text
91d6fbd32abcbdf030d58d3f562de25ebbc9d56040d513ff8e5c19bee9dacf14  /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5.tar.gz
83744c60e737a114c54447e84c5b50fd173cbdf135bdc4dd2b7b0839e4c960da  /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/libmgba.dylib
05e1f8f12dede208a3b06ebc37236325ad8ba8bb109d6be0a7ffb718a32ad21c  /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgbah
ee8131ca41a338dbe793072f01096922e8326ce20d6c12fd343d0aed6e5a812d  /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba_link_harness
1894c25c5621492312ec663ae241703f0e8ed6615293555a118cb88eb06ca96f  /Users/konest/project/aw-kor/tools/mgba_harness.c
0ff3e19c00f7a21a7541d98b99a8b08db0189017d81c07a05aa5c2896cf61690  /Users/konest/project/aw-kor/tools/mgba_link_harness.c
```

## 실행 명령 / 종료코드 원문 기록

전체 로그는 각 name.log, 기계 판독용 원문은 commands.jsonl이다.

```sh
cmake -S /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5 -B /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=Release -DSKIP_GIT=ON -DBUILD_SHARED=ON -DUSE_DEBUGGERS=ON -DUSE_PNG=ON -DUSE_ZLIB=ON -DBUILD_QT=OFF -DBUILD_SDL=OFF -DBUILD_GL=OFF -DBUILD_GLES2=OFF -DBUILD_GLES3=OFF -DBUILD_STATIC=OFF -DBUILD_LIBRETRO=OFF -DBUILD_OPENEMU=OFF -DBUILD_PERF=OFF -DBUILD_TEST=OFF -DBUILD_SUITE=OFF -DBUILD_CINEMA=OFF -DBUILD_ROM_TEST=OFF -DBUILD_EXAMPLE=OFF -DBUILD_PYTHON=OFF -DBUILD_DOCGEN=OFF -DUSE_FFMPEG=OFF -DUSE_MINIZIP=OFF -DUSE_LIBZIP=OFF -DUSE_SQLITE3=OFF -DUSE_ELF=OFF -DUSE_LUA=OFF -DUSE_LZMA=OFF -DUSE_DISCORD_RPC=OFF -DUSE_EPOXY=OFF -DUSE_EDITLINE=OFF -DUSE_GDB_STUB=OFF
```

`configure`: exit 0

```sh
nice -n 10 cmake --build /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build --target mgba --parallel 2
```

`build`: exit 0

```sh
clang -g -DENABLE_SCRIPTING -DHAVE_CRC32 -DHAVE_FREELOCALE -DHAVE_FUTIMENS -DHAVE_FUTIMES -DHAVE_LOCALE -DHAVE_LOCALTIME_R -DHAVE_NEWLOCALE -DHAVE_PTHREAD_CREATE -DHAVE_PTHREAD_SETNAME_NP -DHAVE_SETLOCALE -DHAVE_SNPRINTF_L -DHAVE_STRDUP -DHAVE_STRLCPY -DHAVE_STRNDUP -DHAVE_STRTOF_L -DHAVE_USELOCALE -DHAVE_VASPRINTF -DHAVE_XLOCALE -DMGBA_DLL -DM_CORE_GB -DM_CORE_GBA -DUSE_DEBUGGERS -DUSE_MINIZIP -DUSE_PNG -DUSE_PTHREADS -DUSE_ZLIB -D_DARWIN_C_SOURCE -Dmgba_EXPORTS -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/include /Users/konest/project/aw-kor/tools/mgba_harness.c -L/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build -lmgba -Wl,-rpath,@executable_path/build -o /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgbah
```

`compile-mgbah`: exit 0

```sh
clang -g -DENABLE_SCRIPTING -DHAVE_CRC32 -DHAVE_FREELOCALE -DHAVE_FUTIMENS -DHAVE_FUTIMES -DHAVE_LOCALE -DHAVE_LOCALTIME_R -DHAVE_NEWLOCALE -DHAVE_PTHREAD_CREATE -DHAVE_PTHREAD_SETNAME_NP -DHAVE_SETLOCALE -DHAVE_SNPRINTF_L -DHAVE_STRDUP -DHAVE_STRLCPY -DHAVE_STRNDUP -DHAVE_STRTOF_L -DHAVE_USELOCALE -DHAVE_VASPRINTF -DHAVE_XLOCALE -DMGBA_DLL -DM_CORE_GB -DM_CORE_GBA -DUSE_DEBUGGERS -DUSE_MINIZIP -DUSE_PNG -DUSE_PTHREADS -DUSE_ZLIB -D_DARWIN_C_SOURCE -Dmgba_EXPORTS -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/include /Users/konest/project/aw-kor/tools/mgba_link_harness.c -L/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build -lmgba -Wl,-rpath,@executable_path/build -o /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba_link_harness
```

`compile-mgba_link_harness`: exit 0

```sh
clang -DENABLE_SCRIPTING -DHAVE_CRC32 -DHAVE_FREELOCALE -DHAVE_FUTIMENS -DHAVE_FUTIMES -DHAVE_LOCALE -DHAVE_LOCALTIME_R -DHAVE_NEWLOCALE -DHAVE_PTHREAD_CREATE -DHAVE_PTHREAD_SETNAME_NP -DHAVE_SETLOCALE -DHAVE_SNPRINTF_L -DHAVE_STRDUP -DHAVE_STRLCPY -DHAVE_STRNDUP -DHAVE_STRTOF_L -DHAVE_USELOCALE -DHAVE_VASPRINTF -DHAVE_XLOCALE -DMGBA_DLL -DM_CORE_GB -DM_CORE_GBA -DUSE_DEBUGGERS -DUSE_MINIZIP -DUSE_PNG -DUSE_PTHREADS -DUSE_ZLIB -D_DARWIN_C_SOURCE -Dmgba_EXPORTS -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/src -I/opt/homebrew/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/src/third-party/zlib/contrib -Wall -Wextra -Wno-missing-field-initializers -Werror=implicit-function-declaration -O3 -DNDEBUG -flto -std=c11 -isysroot /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk -mmacosx-version-min=10.6 -fPIC -fno-lto -S /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/abi_probe.c -o /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/abi-library.s
```

`abi-library`: exit 0

```sh
clang -DENABLE_SCRIPTING -DHAVE_CRC32 -DHAVE_FREELOCALE -DHAVE_FUTIMENS -DHAVE_FUTIMES -DHAVE_LOCALE -DHAVE_LOCALTIME_R -DHAVE_NEWLOCALE -DHAVE_PTHREAD_CREATE -DHAVE_PTHREAD_SETNAME_NP -DHAVE_SETLOCALE -DHAVE_SNPRINTF_L -DHAVE_STRDUP -DHAVE_STRLCPY -DHAVE_STRNDUP -DHAVE_STRTOF_L -DHAVE_USELOCALE -DHAVE_VASPRINTF -DHAVE_XLOCALE -DMGBA_DLL -DM_CORE_GB -DM_CORE_GBA -DUSE_DEBUGGERS -DUSE_MINIZIP -DUSE_PNG -DUSE_PTHREADS -DUSE_ZLIB -D_DARWIN_C_SOURCE -Dmgba_EXPORTS -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/include -I/Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba-0.10.5/include -S /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/abi_probe.c -o /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/abi-harness.s
```

`abi-harness`: exit 0

```sh
file /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/libmgba.dylib /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgbah /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba_link_harness
```

`file`: exit 0

```sh
otool -L /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/libmgba.dylib
```

`link-library`: exit 0

```sh
otool -L /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgbah
```

`link-single`: exit 0

```sh
otool -L /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgba_link_harness
```

`link-dual`: exit 0

```sh
otool -l /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/mgbah
```

`rpath`: exit 0

```sh
nm -gU /Users/konest/project/aw-kor/temp/name-grid-phaseB/official-mgba/build/libmgba.dylib
```

`symbols`: exit 0

```sh
git status --short --untracked-files=no
```

`tracked-clean`: exit 0

```sh
vm_stat
```

`memory`: exit 0

RECEIPT: model=unknown effort=unknown role=code
