# T2 코어·이미지 — 결과 보고 (PLAN-v5 T2)

- 계획 `PLAN-v5.md` sha256 `60a7574a957e5277ac8bbb826ad3bee54c39362907fd30864cc26c47809521b4`(재계산 일치), `PLAN-REVIEW-v5.md` `CONTEXT: match` · `AUTHOR: fable` · `VERDICT: APPROVE` 확인 후 시작.
- 수행 주체: `ROUTING_UPDATE.md`(사용자 「이 pc 하네스대로」) → 라우터 code=claude, 로컬 Claude(Orca task_129c6529096c / ctx_89214c5c345c).
- 기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`, branch `sweep3-p2-20261023c`. 커밋·스테이지·push 안 함. tracked 변경 0(`git diff --stat` 빈 출력).
- **이 단계는 ROM 삽입·실게임 통합이 아니다.** 트램펄린은 정적 검사(objdump·심볼·리터럴)만 했고 실ROM 동작은 T3~T5 범위 (unverified).

## 변경 파일 (전부 신규, untracked)

| 파일 | SHA-256 |
|---|---|
| `tools/name_compose/core.c` | `aa99b4cad212c3c9c59b231b757d35cf677efe9ecb4b050957514238bfae9a01` |
| `tools/name_compose/tramp.s` | `6c30f45143042e221184a46a6bcac127acaa7e0f471de633ab2f216b32a32f9d` |
| `tools/name_compose/image.ld` | `40ce99f46732befde9e15e76e18d67f3a89a042d37602604bd362aedbdcb2a5e` |
| `tools/name_compose/gen_tables.py` | `112dcdaa75e5c724bd589a23d1da7ce2f292e48d582b585519acae6fc0ac78a4` |
| `tools/name_compose/build_image.py` | `bec403f8d3d9afd0bb5af0a5c7a427771ddc0b906905ff0a2f1bba03c110a1c9` |
| `tools/part2_name_compose_blob.py` (생성물) | `3313d3d8672e5868b1af95f0ebfbaeb2cb6a1f88b43f0febabc3b5eb368a3c16` |
| `tools/test_name_compose_core.py` | `bbe99bbce16dd04f8c2c67cfbefb2b78e330e8a85e321a306a69851b6fd7a137` |

T1 파일(`data/jamo_*`, `tools/gen_jamo_assets.py`, `tools/test_jamo_assets.py`)은 읽기만 했다.

## 결정 사항

- **생성 include 위치**: `tables.h`(C 표)·`grid.inc`(사설 선택/표시 바이트)는 추적하지 않는 작업 폴더에 생성한다(`build_image.py --work`, 기본 `temp/name_compose_build/`; 이번 증거는 `t2-core/build/`). 정본은 ① `gen_tables.PRIVATE_GRID`(레이아웃 1곳) ② `data/jamo_to_code_40.json`(T1 `load_jamo_codes()`로 검증 후 읽음) ③ `hangul_compose.py` 상수(L/V/T·복합모음·겹받침·종성→초성). 이중 정본 없음.
- **SOURCE_SHA**(blob): `core.c, tramp.s, image.ld, gen_tables.py, build_image.py, hangul_compose.py, data/jamo_to_code_40.json` + `generated/tables.h`, `generated/grid.inc`. 계획 §3의 4개(core.c·tramp.s·image.ld·tables.h)보다 넓다 — 실제 생성 입력 누락 방지. 툴체인 버전은 `TOOLCHAIN`에 별도 기록.
- 사설 표 데이터(`nc_sel_priv`·`nc_row_priv`)는 tramp.s 가 `.include "grid.inc"`로 넣는다(`.rodata.nc_grid`). 행 6개는 native 와 같은 길이(36/36/36/24/24/24)로 연속 배치, 각 행 라벨 `nc_row_priv_0..5`(`nc_row_priv` = 0행).

## blob 모듈 계약 (`tools/part2_name_compose_blob.py`)

`CODE`(2,739B), `CODE_SHA = 8dd9460864ad3b0f9703ce12c80667323935b8055f9c8966e6aa023fae6c3b2f`, `IMAGE_RT = 0x08F75800`, `IMAGE_MAX = 0x2000`, `DENSE_RT = 0x08F70000`(이미지 밖 절대 심볼, `DENSE_BYTES = 22344`), `SYMBOLS`(CODE 안 바이트 오프셋, Thumb bit 없음, 모두 4정렬), `FUNC_SYMBOLS`, `DATA_SYMBOLS`, `ROW_LENGTHS`, `SOURCE_SHA`, `TOOLCHAIN`.

| 심볼 | 오프셋 | 버스(파일 = −0x08000000) |
|---|---|---|
| nc_tramp_press | 0x0000 | 0x08F75800 |
| nc_tramp_confirm | 0x00D4 | 0x08F758D4 |
| nc_tramp_backspace | 0x014C | 0x08F7594C |
| nc_tramp_display | 0x01B0 | 0x08F759B0 |
| nc_alloc | 0x0280 | 0x08F75A80 |
| nc_press | 0x02B8 | 0x08F75AB8 |
| nc_confirm | 0x06DC | 0x08F75EDC |
| nc_backspace | 0x0768 | 0x08F75F68 |
| nc_sel_priv | 0x0888 | 0x08F76088 (데이터) |
| nc_row_priv | 0x093C | 0x08F7613C (데이터) |

**T3가 컴파일 없이 쓰는 함수**: `verify_code()`(해시·크기·심볼 범위/4정렬), `entry(name)` = `IMAGE_RT + SYMBOLS[name] | 1`(함수만, 데이터 이름은 KeyError — 사이트 리터럴용), `sel_priv()`(90셀 180B), `row_priv()`(6행), `check_sources()`(추적 소스·생성 include 현재 해시 ↔ SOURCE_SHA, 다른 키 목록). Thumb bit 는 `entry()`에서만 붙는다 — 파일 오프셋 계산엔 `SYMBOLS` 값을 그대로 쓴다. `nc_dense` 주소는 `DENSE_RT`(이미지 오프셋 아님).

재생성: `python3 tools/name_compose/build_image.py` (검증만: `--check`).

## 구현 요약

- `core.c`: 순수 C, 전역 쓰기·나눗셈·구조체 복사·게임 호출 없음. `commit()`이 새 상태(추가 확정 0..2개 + 새 active)를 슬롯 수·표 조회로 검사한 뒤 한 번에 기록(원자적 종성 이동). 셀 분류: 자모 33 코드 → 조합, `8140` → 공백, 그 외 → 리터럴(공백과 같은 규칙). 조회 `nc_dense[(L*21+V)*28+T]`. 반환 0 수락/1 거부(버퍼 불변). tail ABI +70..+73, +74..+7F 미기록, `len<8`이면 `slot[len]=00 00`.
- `nc_backspace` 는 모델과 같이 거부(1)를 낼 수 있다(빈 이름 등). 계획 §1.6 「항상 0」과 표기가 다르지만, S3 진입은 len≥1 지점이고 도달 가능한 상태에서 거부는 없다(랜덤·전수 테스트에서 C==모델). 트램펄린은 반환값과 무관하게 redraw→B21A 로 간다(계획 S3 경로와 동일).
- `tramp.s`: §1.5 표 그대로. 공통 `ENTER`(push r4-r7,lr → r8-r11 을 r4-r7 로 push → r4=sp → sp 8정렬, r3 만 사용해 S3 의 live r2 보존) / `LEAVE_TO`(sp·r8-r11·r4-r7·lr 복원 → `ldr r0,=ret|1; bx r0`). 원거리 호출 `ldr r3,=fn|1; bl nc_call_r3`. D1 은 C 없이 순수 asm: mode0 은 `r2=[r4]; r3=0x0883FE40; r6=0x8000` → AB44, mode1 은 `push {r7,lr}; sub sp,#8` 후 6회 `[sp]=0x8000,[sp+4]=0, r0=6, r1=6+2i, r2=[r4], r3=nc_row_priv_i, r7=0x08314EB1; bl nc_call_r7` → `add sp,#8` → r7·lr 복원 → r5=0, r6=0x8000 → ABA2. r3 에 함수 주소를 넣지 않음(objdump 확인).
- `nc_alloc`: B970 과 같은 프레임(`push {r4,lr}` … `pop {r4}; pop {r0}; bx r0`), r0=0x80 → 0x08315300, `[0x03004650]` 저장(0 이어도), 0 이 아니면 tail 16B = `00 FF FF 00` + 0×12.
- mode 판정은 `[obj+0x60] == 1`만 mode1, 그 외 값은 native 경로.

## 실행한 명령과 결과 (원문 로그: 이 폴더)

| 명령 | 결과 | 로그 |
|---|---|---|
| `python3 -I tools/test_name_compose_core.py` | `Ran 12 tests … OK`, EXIT 0 | `test.log` |
| `python3 -I tools/name_compose/build_image.py --check --work temp/name-grid-phaseB/t2-core/build` | `OK blob byte-identical`, EXIT 0 | `blob_check.log` |
| `python3 -I tools/test_jamo_assets.py` (T1 회귀) | OK, EXIT 0 | `t1_regress.log` |
| `python3 -I tools/gen_jamo_assets.py --check` | `OK jamo assets byte-identical`, EXIT 0 | `t1_check.log` |
| `python3 -I tools/test_hangul_compose.py` (모델 회귀) | EXIT 0 | `hangul_regress.log` |
| grid-map.json ↔ 원본 ROM 행 6개·선택표 90셀 | 모두 일치, EXIT 0 | `gridmap_vs_rom.log` |
| readelf/nm/objdump 원문 | — | `elf_inspect.log`, `objdump.txt` |

`test.log` 요약 출력:
```
exhaustive=11172 reached=2345 rejected=8827 supported_unreachable=5 뢨썅쏀쓩쭁
random_operations=20000 seed=20261023 applied=19193 rejected=12349
selector_cells=90 display_rows=6 match
image_bytes=2739 insns=968 code_sha=8dd9460864ad3b0f9703ce12c80667323935b8055f9c8966e6aa023fae6c3b2f
```
ELF: `.image` VMA 0x08F75800, size 0xAB3(2,739 ≤ 8,192), 유일한 할당 섹션 · `There are no relocations in this file.` · `nm -u` 빈 출력 · `Tag_CPU_arch: v4T`, `Tag_THUMB_ISA_use: Thumb-1` · 32bit 명령은 bl 뿐, `$a` 없음 · raw == ELF .image · `nc_dense` ABS 0x08F70000.
산출물 SHA: `build/image.bin` `8dd94608…6c3b2f`, `build/image.elf` `af9e67a5…7e7734`, `build/tables.h` `26ceeeb9…0e9f6c`, `build/grid.inc` `d3cbcf60…c4bbee9`.

### 테스트 범위 (계획 T2 대비)

① 고정 기대표: model-results.json(sha `f93b8c01…6b7d`) 5사례(full8 17 수락+9번째 ㄱ 거부·confirm 16B `884088e9…8ea2`, 한글 `92af888a`, 강철 `884990d3`, 붉은달 `8d5c8f7e89e7`, 가한 자동 조합 갛 `0x884D`)를 상수로 고정하고 연구 파일이 있으면 상수와 대조. 추가: 가+ㅋ 거부·가카(명시 확정)·한가·달가·갑시·하나·개+ㄷ 거부·간+ㅒ 보존·복합 7(V-only/L+V, 역삭제)·겹받침 11(역삭제)·강→가→ㄱ→빈·확정 가 음절 삭제·8번째 active 받침 편집/역삭제·미완성 confirm/space/리터럴 거부·리터럴/공백 셀(`884082508140`)·legacy ア×8(가득 참 거부→B→자모)·legacy `0x1234/0xFFFF` 역삭제. 매 스텝 C 반환 == 모델 수락, 거부 시 128B 버퍼 불변, 수락 시 live adapter(16B·len·tail 16B) 일치, 그 외 바이트 감시 패턴 불변.
② 시드 20261023 랜덤 20,000(자모·지우기·확정·공백·리터럴·재진입·초기화) 매 스텝 일치. ③ 11,172 전수: 도달 2,345, 지원 미도달 5(뢨썅쏀쓩쭁) 그대로, 첫 거부 지점 버퍼 불변. ④ 이미지: blob 가드(항상), 소스 재생성 blob 바이트 일치(툴체인 있을 때), 사설 선택 90셀이 §1.2와 일치, 원본 ROM 대비 분류 동일성(동작 코드 17셀 원본 그대로·나머지 첫 바이트 ∉ {31,32,62,63,65}), 표시행 길이·형식·간격·숫자/문장부호/legacy 814A·814B 원본 유지, 자모·공백 표시가 사설 선택표와 일치.

뮤테이션 확인(임시 사본, 정리 완료): 종결자 미기록·겹받침 실패 시 advance·tail T 미기록 → 랜덤 테스트가 검출. 종성 이동의 앞 음절 조회 제거는 검출 안 됨 — 도달 가능한 상태에선 앞 음절이 항상 이전 active 로 표에 있었으므로 동등 변형이다(모델과 같은 방어 검사로 유지).

## 계획 대비 어긋난 점

1. SOURCE_SHA 키가 계획 §3(4개)보다 넓다(실제 생성 입력 전부 + 생성 include 2개). 추가만, 기존 키 의미 불변.
2. 생성 include 가 `tables.h` 외 `grid.inc` 하나 더(사설 표 데이터를 tramp.s 에 넣기 위함, 같은 생성기·같은 입력).
3. `nc_backspace` 반환 표기(위 설명). 트램펄린 경로는 계획과 같다.
4. D1 mode1 은 복귀 직전에 native 프레임 `[sp]=0x8000, [sp+4]=0` 도 써 둔다(native 가 AB44..AB9E 에서 남기는 값과 같게 — fidelity 보강, 계획 r5/r6 계약에 덧붙임).
5. tramp.s 에 `.note.GNU-stack` 빈 섹션(ld `--fatal-warnings` 경고 방지, image.ld 가 DISCARD).
6. tramp.s 는 `arm-none-eabi-as -mcpu=arm7tdmi -mthumb --fatal-warnings`로 조립(계획 §1.6은 C 컴파일만 명시).
7. C 반환 0/1·obj 접근은 바이트 단위. 함수 4정렬은 clang `-Os` 기본 `.p2align 2` 출력에 의존하며 build_image 가 매번 검사(어기면 빌드 실패).

## 남은 위험 (unverified)

- 트램펄린·D1·nc_alloc 의 실ROM 동작(레지스터/스택 보존, 복귀 PC, 렌더러 인자)은 정적 검사만 했다 → T5 케이스 15.
- C 코어 스택 사용량(nc_press 프레임 52B + commit 인자 + 트램펄린 36B+정렬) 실측 안 함. IWRAM 스택 여유는 T5 에서 확인.
- AED8/A954/sound 를 트램펄린 프레임 아래(sp 가 native 보다 ~40B 낮음)에서 부른다 — 호출자 프레임을 읽지 않는 함수로 보이나 실행 확인은 T5.
- host 테스트는 같은 core.c 를 arm64 로 컴파일한 결과다. Thumb 코드의 의미 동일성은 컴파일러 신뢰에 기대고 있다(직접 Thumb 실행은 T5).
- 툴체인 버전이 다른 머신에선 CODE 가 같아도 blob 텍스트(TOOLCHAIN 줄)가 달라 `--check` 가 MISMATCH 일 수 있다.

## 후속 반영

문서(AGENTS/CLAUDE/todo, docs/reports)는 T6 소유라 안 건드림. T6 에 넘길 사실: blob 재생성 명령, SYMBOLS 표, SOURCE_SHA 범위, 생성 include 는 추적하지 않음.

정리: 테스트가 만든 `temp/name_compose_host_*`·`name_compose_img_*`·뮤테이션 임시 폴더는 삭제됨. `__pycache__` 없음(PYTHONDONTWRITEBYTECODE). 이 폴더(`t2-core/`)와 `build/`는 증거로 보존. 띄운 장기 프로세스·워크트리·claim·브라우저 없음.

RECEIPT: model=claude-opus-5-5 effort=unknown role=code
