# Ghidra 디컴파일 보조 (GBA ROM)

## 목적·한계
- 함수 구조·제어코드 분기·테이블 위치를 빨리 읽기 위한 **정적 보조 도구**다.
- 디컴파일 결과만으로 사실을 기록하지 않는다. `docs/research.md`에 올리기 전에 mgba 헤드리스 하네스(`tools/mgba_harness.c`) 런타임 추적(BP/watch/PC·LR)으로 확인한다. 미확인이면 "Ghidra 정적 근거, 런타임 미확인"이라고 적는다.

## 설치 (sudo 없음, `~/.local/opt`)
- Ghidra **12.1.4** PUBLIC zip (GitHub release `Ghidra_12.1.4_build`). 2026-10-13 내려받은 zip SHA-256: `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db` — release 페이지 공지값과 대조해 확인한다.
  `unzip ghidra.zip -d ~/.local/opt/` → `~/.local/opt/ghidra_12.1.4_PUBLIC`
- Temurin JDK **21.0.12.1+1** tar.gz → `~/.local/opt/jdk-21.0.12.1+1`
- GBA 로더 확장(1.1.0)은 Ghidra 12.0.2 전용이라 쓰지 않는다. raw `BinaryLoader`, 언어 `ARM:LE:32:v4t`, base `0x08000000`으로 가져온다.
- 경로가 다르면 `GHIDRA_HOME`, `JAVA_HOME` 환경변수로 지정한다. 없으면 스크립트가 오류 메시지를 내고 끝난다.

## 사용법
```bash
tools/ghidra/decomp.sh 0x08373D10            # Thumb(기본) → temp/decomp/ghidra/out/08373D10.c
tools/ghidra/decomp.sh 0x0831424C:t 0x080000C0:a   # :t Thumb / :a ARM, 여러 개 한 번에
tools/ghidra/decomp.sh xref=0x08B80B7C       # 32비트 상수를 리터럴 풀에서 찾고 포함 함수를 만들어 나열
tools/ghidra/decomp.sh --rom output/game_wars_korean_full.gba 0x08F30400   # 패치 후보 ROM(hook 영역 확인)
```
- 출력: C + 디스어셈블. 프로젝트 `temp/decomp/ghidra/proj`, 출력 `temp/decomp/ghidra/out` (`GHIDRA_PROJ`, `GHIDRA_OUT`로 변경). `temp/`가 지워져도 첫 실행 때 다시 import한다.
- `--rom`을 주면 ROM SHA-256 앞 12자로 프로젝트(`gbwa_<sha>`)와 출력 하위 폴더(`out/<sha>/`)를 분리한다. 0xF30400·0x08F00000 같은 hook 영역은 패치 ROM에서만 보인다.

## GbaDecomp.java가 하는 일 (`tools/ghidra/scripts/`)
- GBA 메모리 맵(EWRAM/IWRAM/IO/PRAM/VRAM/OAM) 블록을 미초기화로 만들어 참조가 풀리게 한다.
- 함수 시작마다 `TMode`(Thumb/ARM)를 지정한다.
- ARMv4T의 `pop {rX}; bx rX` 반환을 RETURN으로 표시한다(v4t는 `pop {pc}` 인터워킹이 없다).
- 점프 테이블을 찾아 switch로 복원하고, 호출 대상(callee) 함수를 만든다.

## 알려진 출력 특성
- 반환값이 `CONCAT44(...)`로 보이는 경우가 있다(r0:r1 쌍 해석). 실제 반환은 r0만인 경우가 많다.
- 인자는 `param_1..` 일반 이름과 `undefined4` 타입이다. 구조체는 직접 해석한다.
- 데이터 테이블·글자 테이블이 문자열 리터럴처럼 보일 수 있다. 바이트로 다시 확인한다.

## 자원·발열
- `memcap -n ghidra-decomp -m 8G` + `nice -n 15` + `MAXMEM=6G` + `-XX:ActiveProcessorCount=4`로 감싸 실행한다(스크립트에 내장). 실행 전 `memcap status`, 온도 확인. 피크 RSS는 `out/metrics.log`.
- 한 번에 하나만 돌린다. 같은 프로젝트를 두 프로세스가 동시에 열면 잠금 오류가 난다.

## 검증된 사용 예
- 헤더 드로어 `0x08373D10`, 로더 `0x08373DEC`, 2편 파서 `0x0831424C` — [`research.md` 「2026-10-13 2편 헤더 알파벳·파서 제어코드」](research.md#2026-10-13-2편-헤더-알파벳파서-제어코드-원본-rom-sha-256-a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c). 헤더 항목은 b19 런타임 추적으로 확인됐다.
- 2026-10-13 b22 스모크: `decomp.sh 0x08373D10` 결과가 이전 `temp/decomp/ghidra/out/08373D10.c`와 바이트 동일.
- 단어붙음 잔여 분석(`temp/jam_ghidra_20261013/plan.md`): b21 잔여 196행을 소비 렌더러별로 분류해 **실제 붙음은 5건**뿐임을 확인. 0x20을 위치 이동 없이 소비하는 31424C 파서를 쓰는 진짜 잔여는 없었다.

## rev.ng를 쓰지 않는 이유
- 전체 ROM lift 크래시, 리터럴 풀 오인, 점프 테이블 소실 등 — [`fail.md` 「2026-10-13 rev.ng PoC 부분 실패 — Ghidra 사용」](fail.md#2026-10-13-revng-poc-부분-실패--ghidra-사용).
