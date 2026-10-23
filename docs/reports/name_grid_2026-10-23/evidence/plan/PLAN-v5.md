# PLAN v5 — 2편 맵 에디터 이름 입력 두벌식 조합 (Phase B 실행 명세)

기준: cwd `/Users/konest/project/aw-kor`, HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`(clean), branch `sweep3-p2-20261023c`. 트랙: **structural**(저장 객체 크기·A3 범위·빌더 쓰기 영역·훅 ABI). 변경 이력: v1 최초(sha `a222a5e5…`) → **v2: Astra full 지적 F1~F8·N1~N4 반영, mode-scope-re 실측 반영, 「native 표 원형 유지 + mode1 사설 표」로 설계 교체.**

## 0. 원 요청과 추가 범위

**원 요청(요지, 제약 포함 — 원문 `temp/name-grid-phaseB/PHASE_B_BRIEF.md`):** 2편 맵 에디터 이름 입력을 완전 두벌식 조합으로 변경. 최대 8글자·글자당 2바이트. 2350 밖 중간 후보는 원자 거부(대체 금지). 지우기는 조합 중 자모부터. 공유 A3 가나 그림 변경 금지. 구현·테스트·Astra 리뷰는 harness-codex, Fable은 계획만. 사용자 개입 없이 수행하고 결과·필수 결정만 company 전달. 원본·default full/final/title_test·dist·b44·baseline 보호, 새 후보는 `--out --no-sync-outputs`. Python 모델 계약(`docs/reports/name_grid_2026-10-23/COMPOSITION_SPEC.md`) 준수(개+ㄷ 거부, 간+ㅒ 원자 거부, 8번째 active 편집, 5음절 도달 불가 정직 보고). **8자 저장·콜드 로드 필수, 4자 대체 금지.** 완료 시 RE/계획/QA를 `docs/reports/name_grid_2026-10-23/`에 보존, AGENTS/CLAUDE/todo 최신화, scoped secret-scan 후 한국어 Conventional commit/push, 승인·검증된 최종 feature는 main 병합까지. b44/dist/정본 ROM 재배포는 범위 밖. 동일 수정 3회 한계, rollback은 commit 후 revert, 보호 파일 덮어쓰기 금지. 수정 브리프 `PHASE_B_REVISION_BRIEF.md`의 F1~F8·N1~N4·총괄 보완을 모두 반영한다.

**원 요청 대비 추가 범위: 없음.** 아래 객체 확장·자모 자산·mode1 사설 표는 원요청의 실행에 필요한 부분이다. 새 프레임워크·시리얼 하네스·소비자별 훅·navigation 훅 복제는 하지 않는다.

## 1. 설계 결정

### 1.1 mode 범위 — native 표는 원형, mode1 만 사설 표 (F1·N2, 총괄 최소안 채택)
근거(raw, `mode-scope-re/baseline-name-module.log`·`grid-map.json`·`verification.log`):
- 입력 루프 `0x0834AFA0`의 dispatch(`AFAE`, expect `0d4b1c680d4a16683568`)는 `[0x084873F4]`→선택표 `0x0883FAF6`(런타임 BP r3=084873F4 r4=0883FAF6 실측)에서 셀 **첫 바이트만** 읽어 분기한다: `0x62` 뒤로(B1E4) · `0x63` 취소(B1C6) · `0x65` 확인(B084) · `0x31`/`0x32` 탁점·반탁점(B0E6/B146) · **그 외 전부 일반 셀 B0BC**.
- 커서 이동 `B2C8`/`B338`(expect `134b`), mode0 취소 건너뛰기 `B3C0`(`1d4a`), 커서 그리기 `B470`(`234a`)은 리터럴로 `0x0883FAF6`을 직접 읽어 클래스(62/63/65 → wide 버튼, 그 외 0)만 본다.
- 따라서 **선택표·표시표·row pointer 리터럴(AC24..AC38)·좌표 표를 전혀 바꾸지 않으면** mode0·mode1의 navigation·wide 버튼·커서·취소 건너뛰기는 원본과 동일하다(WIDE_BUTTON_CLASS_INVARIANT 90 cells). navigation 훅 복제는 불필요하다 — **하지 않는다**.
- mode1 사설 선택은 **S1(일반 셀 경로)에서만** 좌표로 읽고, mode1 사설 표시는 constructor의 6행 그리기 블록 한 곳(D1)에서만 분기한다. mode0는 두 곳 모두 원 명령을 재생한다.

사설 선택표 `nc_sel_priv[6][15]`(u16 BE, 이미지 내 const)의 **분류 동일성 제약**(T3 빌드 테스트가 90셀 전수 assert): 원본 첫 바이트 ∈ {31,32,62,63,65} 인 좌표(row2 x10·x11, row3~5 x10..14)는 **원본 코드 그대로**, 나머지 좌표의 코드는 첫 바이트 ∉ {31,32,62,63,65}(자모 코드 lead ≥ 0x88, 리터럴 81xx/82xx 만족). 탁점·반탁점 2셀은 legacy 유지: mode1에서 한글/자모가 마지막 쌍이면 native 핸들러(B118..B144 / B174..B1C2)가 kana 표 `[0x08487400]`/`[0x08487404]`에서 불일치 → `B1F4` sound 0x68 거부·상태 불변(런타임 QA 케이스 13으로 확인), legacy 가나 이름에만 기존 변환. 표시도 원본 `814a/814b` 유지(셀이 보이는 대로 동작).

### 1.2 그리드 레이아웃 (`symbolic-layout.json` 기준, legacy 2셀만 다름)
| row | x0..x4 | x5..x9 | x10..x14 |
|---|---|---|---|
| 0 | ㄱ ㄲ ㄴ ㄷ ㄸ | ㄹ ㅁ ㅂ ㅃ ㅅ | ０１２３４ (824f..8253 원본) |
| 1 | ㅆ ㅇ ㅈ ㅉ ㅊ | ㅋ ㅌ ㅍ ㅎ ␣ | ５６７８９ (8254..8258) |
| 2 | ㅏ ㅐ ㅑ ㅒ ㅓ | ㅔ ㅕ ㅖ ㅗ ㅛ | 3131 3232(legacy 유지) ・！？ (8145 8149 8148) |
| 3 | ㅜ ㅠ ㅡ ㅣ ␣ | ␣×5 | 6363×5 취소(wide) |
| 4 | ␣×10 | | 6262×5 뒤로(wide) |
| 5 | ␣×10 | | 6565×5 확인(wide) |
빈 셀은 native 원본(row1 x6·x8, row3 x6·x8)과 같은 전각 공백 `8140`(선례 있음, 새 마커 없음). 표시표 매핑: 선택 x 0..14 → 표시 pair index `[0,1,2,3,4,6,7,8,9,10,12,13,14,15,16]`(pair 5·11은 간격 `8140`); row0~2는 17쌍, row3~5는 11쌍(x0..9 → pair 0..4,6..10; wide 버튼은 native가 별도 타일로 그림). START 키는 native가 커서를 (14,5)=확인으로 옮긴다(B072..B082) — 불변. 사설 표시행 `nc_row_priv[6]`는 원본과 **같은 길이·같은 형식**(`09` + 쌍 + `00`, 17/11쌍)이고 §1.2의 사설 선택 레이아웃과 좌표 매핑에서 표시쌍을 생성한다. 자모 셀은 자모 코드, 새 공백 셀도 8140, 숫자·문장부호·간격은 지정값을 유지하고 row2 x10/11 표시는 원래 814A/814B를 유지한다. 원본 공유 표는 전혀 쓰지 않는다.

### 1.3 조합 상태 — 객체 0x80 확장(채택, v1 유지)
- `0x0834B974 mov r0,#0x70` 단일 상수, allocator `0x08315300→0x08315288` (size+15)&~15·헤더 16B·zeroing 없음, free `0x08315390`는 헤더 크기만 읽음(candidate-re §103~105). 0x80 요청이면 free 무변경. 별도 할당 대안은 정리 경로가 늘어 기각.
- **tail ABI(+0x70..+0x7F)**: `+70 active(u8 0/1)`, `+71 L(u8, 0xFF=없음)`, `+72 V(u8, 0xFF=없음)`, `+73 T(u8 0..27)`, `+74..+7F 0`. committed 개수 `C = len(+0x61) − active`.
- 초기화: 할당 콜백 포인터 **P1 `0x0883FD58`**(expect `71b93408` = `0x0834B971`) → `nc_alloc|1`. `nc_alloc`은 B970과 같은 프레임(`push {r4,lr}` … `pop {r4}; pop {r0}; bx r0`)으로 r0=0x80 → `0x08315300` 호출 → `[0x03004650]`에 저장(0이어도 저장) → r0≠0이면 tail 16B를 `01? 아니오: active=0, L=V=0xFF, T=0, 나머지 0`으로 쓴다. 할당 직후가 생명주기상 유일하게 순서가 안전하다(constructor B9C4가 allocator 앞에서 관측됨). `B970` 원본 바이트는 dead로 둔다. cancel/confirm → free → 재진입 → 재할당 → 재초기화. constructor 콜백 `FD78`(`fda93408`)·입력 루프 포인터 `FDE0`(`41b43408`)·커서 루프 `FD28`(`55b43408`)은 **불변**(빌드 테스트 expect).
- `0x00..0x6F` 원형 보존. mode0도 0x80을 받지만 tail을 쓰지 않는다.

### 1.4 버퍼 의미 — live adapter와 stored adapter 분리 (N3)
- **live**(편집 중 RAM, QA 스텝 대조): `+0x2C` 슬롯 16B·`+0x61 len`·tail. `slot[0..C) = committed 코드(BE)`, active 있으면 `slot[C] = 현재 표시 코드`(완성이면 2350 코드, 미완성이면 자모 코드), `len = C + active`, `len<8`이면 `slot[len] = 00 00`(AE60/AE90 규약). `live_expected(composer) → (bytes16, len, tail4)`.
- **stored**(확인 Yes 뒤 destination `[obj+0x5C]` 16B·세이브·콜드 로드): native가 `0x08313048`로 끝 공백 trim 후 16B 복사(B00C..B03E). `stored_expected(committed) → prefix`: 끝 `8140` 제거한 committed BE 연결. 판정은 「prefix 일치 + committed 8개면 정확히 16B 전체 일치 + 8개 미만이면 prefix 다음 첫 byte 0」만. 16 zero 강요 금지(brief). 모델 `serialize()`는 참조 표현일 뿐 native 계약이 아니다.
- 미완성 active는 confirm 거부로 destination에 절대 복사되지 않는다. cancel은 원래 복사하지 않는다.
- 명시 확정 경계(예 `가카`: 가+ㅋ=갘 표 밖 → 원자 거부): **native 확인 → No 로 편집 복귀**(runtime-cases 실측: 이름·len·dest 유지, RIGHT 뒤 A가 No)하는 기존 절차를 쓴다. nc_confirm이 active를 확정(active=0)한 뒤 AED8이 질문을 열므로 No 로 돌아와도 확정이 남는다. 새 키 정책·L 기능은 만들지 않는다. **가한은 ㄱㅏㅎㅏㄴ 자동 조합(갛=0x884D 2350 포함, model-results 실측) — 별도 확정 절차 없음.**

### 1.5 훅 사이트 — 바이트 기반 4곳 + 포인터 1곳 (F1·F5·F6, N1 심볼 단일화)
mode 판정은 `[obj+0x60]`(0=mode0, 1=mode1), obj=`[0x03004650]`. 파일 오프셋 = 버스 주소 − 0x08000000.

| 사이트 | 파일 오프셋 · 길이 | 원본 expect | 교체 | mode1 | mode0 |
|---|---|---|---|---|---|
| S1 일반 셀 | `0x34B0BC` 10B | `6520 f0f7b9fc fff79dfe` | `ldr r0,[pc,#0]; bx r0; .word nc_tramp_press\|1; nop(c046)` | x=`[obj+0x1E]`s16, y=`[obj+0x20]`s16, 범위 밖이면 거부; `cell=nc_sel_priv[y*15+x]`; `nc_press(obj,cell)`=0 → sound 0x65 → `0x0834A954` → `0x0834B428` / 1 → sound 0x68 → B428 | sound 0x65 → `0x0834AE00` → `0x0834B0C6` 복귀(원 len++ 경로) |
| S2 확인(START/OK) | `0x34B084` 8B | `fff728ff cee1 0000` | `ldr r0,[pc,#0]; bx r0; .word nc_tramp_confirm\|1` | `nc_confirm(obj)`=1(미완성) → sound 0x68 → B428 / 0 → `0x0834AED8` → B428 | `0x0834AED8` → B428 |
| S3 지우기 | `0x34B20E` 10B | `0138 1070 fff725fe fff7` | `ldr r0,[pc,#4]; bx r0; nop; .word nc_tramp_backspace\|1` | `nc_backspace(obj)` → `0x0834A954` → `0x0834B21A`(sound 0x66·B428) | `ldrb r0,[r2]; subs r0,#1; strb r0,[r2]` → `0x0834AE60` → `0x0834A954` → B21A |
| D1 표시 6행 | `0x34AB3C` 8B | `2268 394b 8026 3602` | `ldr r3,[pc,#0]; bx r3; .word nc_tramp_display\|1` | `sub sp,#8; [sp]=0x8000,[sp+4]=0`; i=0..5: `0x08314EB0(r0=6, r1=6+2i, r2=[r4], r3=nc_row_priv[i])`; `add sp,#8`; r5=0, r6=0x8000 → `0x0834ABA2` | `r2=[r4]; r3=0x0883FE40; r6=0x8000` → `0x0834AB44` |
| P1 할당 콜백 | `0x83FD58` 4B | `71b93408` | `nc_alloc\|1` | §1.3 | 동일 |

- 정합성: `0x34B08C`는 B060의 리터럴(0x084873FC)이라 S2는 8B에서 끝난다. S3의 `0x34B218` 고아 `9dfb`는 실행 경로에 없다(B21A 복귀). B0C6 이후 len++는 mode0 복귀에만 쓰인다. AB3C..AB44로 들어오는 분기 없음(함수 내 분기 목표 AACC/AB10/AB22). D1에서 r4=`[0x0834AC1C]`=`0x08814FB0`(AB26 로드)·r7·r8·sb는 ABA2 이후 live → 보존. ABA2 이후 r5/r6는 ABA8/ABAA에서 재대입되지만 fidelity를 위해 r5=0, r6=0x8000로 맞춘다.
- 모든 복귀점에서 r0는 dead(B0C6 `bl`, B428 `pop`, B21A `movs r0`, AB44 `str r6,[sp]`, ABA2 `mov r0,r8`)이고 **플래그를 읽는 명령이 없다**(raw 확인) — 복귀는 `ldr r0,=ret|1; bx r0`. S3 mode0 재생은 r2(obj+0x61)가 live이므로 트램펄린은 진입 시 r0만 쓴다.
- 보존 규약(트램펄린 공통): `push {r4-r7,lr}` → r8-r11을 r4-r7에 복사해 `push {r4-r7}` → `mov r4,sp` 보관 → sp를 8정렬로 내림 → C 호출(r0=obj, r1=cell) → `mov sp,r4` → 역순 pop → 고정 복귀. C는 r4-r7·sp 보존(컴파일러), 트램펄린이 r8-r11·lr·sp를 보존. 관측 sp `0x03007D54`(4정렬, 8정렬 아님)라 정렬이 실제로 필요하다. D1은 C를 부르지 않는 순수 asm(게임 함수 호출은 8정렬 불요).
- 원거리 호출 idiom(ARMv4T, bl 도달 거리 >4MB): `ldr r3,=fn|1; bl nc_call_r3` (`nc_call_r3: bx r3`) — lr 자동 설정. 대상: sound `0x0833BA34`, redraw `0x0834A954`, `AED8`, `AE00`, `AE60`, allocator `0x08315300`. 단, row draw 0x08314EB0는 r3가 문자열 인자이므로 이 idiom을 쓰지 않는다. D1은 r7을 자기 프레임에 저장한 뒤 함수 주소 0x08314EB1을 r7에 두고 `bl nc_call_r7` (`nc_call_r7: bx r7`)으로 호출한다. r0-r3 인자가 모두 유지된다. D1은 자기 프레임/8B 스택 인자를 복원하고 원래 r4/r7/lr와 high register를 보존하며 r5=0/r6=0x8000 계약을 맞춰 ABA2로 복귀한다.
- 무변경: R 키 `B222`(kana 표 불일치 → 0x68), 탁점·반탁점(§1.1), 취소 `B1C6`, 커서 이동, AED8 검증, B00C trim·복사, constructor 로드(AE90 전체 zero → +0x44 사본 → 첫 00까지 복사).

### 1.6 조합 코어 — freestanding C + Thumb 트램펄린 + 생성 hex 모듈 (F4, N1)
- 소스: `tools/name_compose/core.c`(순수 로직, 게임 함수 호출·전역 쓰기·나눗셈·memcpy/memset 유발 구조체 복사 금지, 상태는 obj tail+버퍼뿐), `tools/name_compose/tramp.s`(§1.5 트램펄린·`nc_alloc`·`nc_call_r3`·`nc_call_r7`·`nc_sel_priv`·`nc_row_priv`·리터럴), `tools/name_compose/image.ld`(VMA `0x08F75800`, 단일 `.image`, `.ARM.exidx`/`.comment`/`.note.GNU-stack` DISCARD, **`nc_dense = 0x08F70000;` 절대 심볼**), `tools/name_compose/gen_tables.py`(JSON→`tables.h`: `L_CODE[19]`, `V_CODE[21]`(복합 7 포함), `SEL_TO_V[14]`, `CELL_CLASS`), `tools/name_compose/build_image.py`(clang `-target armv4t-none-eabi -mcpu=arm7tdmi -mthumb -ffreestanding -fno-builtin -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -Os -Wall -Wextra -Werror` → `arm-none-eabi-ld -T image.ld --no-undefined --fatal-warnings` → `objcopy -O binary --only-section=.image` → `readelf -r`=0 · `nm -u` 빈 출력 · attributes `v4T`/`Thumb-1` · raw == ELF 섹션 → `tools/part2_name_compose_blob.py` 생성).
- **심볼 이름(단일 정본, N1)**: C `nc_press`, `nc_confirm`, `nc_backspace`; asm `nc_tramp_press`, `nc_tramp_confirm`, `nc_tramp_backspace`, `nc_tramp_display`, `nc_alloc`; 데이터 `nc_sel_priv`, `nc_row_priv`, `nc_dense`(외부 절대). blob 모듈 `SYMBOLS`·빌더·테스트·문서가 이 이름만 쓴다.
- 코어 API(AAPCS Thumb): `int nc_press(uint8_t *obj, uint16_t cell)` 0 수락/1 거부 · `int nc_confirm(uint8_t *obj)` 0(활성 없음 또는 완성 확정)/1 미완성 · `int nc_backspace(uint8_t *obj)` 항상 0(len≥1 보장 지점). 셀 분류: 자모 33 코드 → 조합, `8140` → space 규칙, 그 외 2바이트 → 리터럴(space와 동일 규칙: 미완성 거부·완성이면 확정 후 슬롯·슬롯 없으면 원자 취소). 전이는 `COMPOSITION_SPEC.md` 표 그대로(L-only/V-only/L+V/L+V+T, 복합모음 7, 겹받침 11, 종성 이동은 앞·뒤 모두 조회·두 슬롯 확보 후 원자 적용, 표 밖 원자 거부, 9번째 필요 시 `no_slot`, 8번째 active 편집 허용). 조회는 `nc_dense[(L*21+V)*28+T]`(u16 LE, 0=없음, 22,344B). **host 테스트는 같은 `core.c`를 네이티브 컴파일하고 `nc_dense`를 JSON에서 만든 실제 배열로 링크**한다 — ROM과 host의 조합 알고리즘·조회 경로가 동일 소스다.
- 일반 빌드는 `part2_name_compose_blob.py`만 import(Python-only). toolchain이 있으면 테스트가 재생성 바이트 일치를 검사하고, 없으면 skip하되 SHA 가드는 항상 돈다(`test_part2_terrain_movement_labels` 패턴).

### 1.7 자모 코드·글리프·A3 확장 (F3 주소 정정)
- 자모 코드표 `data/jamo_to_code_40.json`(신규 tracked): `build_korean2350.extend_pool(original)` − 2350 매핑 값의 **정렬 첫 40개**(pool.json 실측 E2A8, E2AB, E2AD, E2AE, …; 전체 40개는 T1 생성 시 확정·고정)를 실제 `hangul_compose.PREVIEW_JAMO = L_LIST + V_LIST` 순(19초성+21모음, 복합모음은 V_LIST 내 순서)으로 매핑. 빌더는 「풀 소속·2350 미중복·40개·lead∈[0x88,0xEA]·trail≥0x40」 매 빌드 assert. 재선정은 별도 결정.
- 글리프: `render_galmuri_8x16.render_char`로 40자 top/bot → `data/jamo_glyphs_40.bin`(2,560B, 재배포 가능한 자체 폰트 산출물) + 「40자 모두 ink>0」 assert. 기록 `0xF09F60..0xF0A960`(tile 1275+2i top, 1276+2i bot; 1273 blank·1274 private 자 보존), 쓰기 전 zero assert.
- A3 표: 기존 `new_tbl`(2,886 entries × 6B = `0xF20000..0xF243A4`) 뒤에 40 entries(`code BE, top|0x8000 LE, bot|0x8000 LE`) append → **`0xF243A4..0xF24494`**. 삽입 위치는 `build_korean_full.py:14416`(`_assert_relocated_korean_indices`) 뒤·`:14417`(rom 기록) 앞 — 그러면 end 리터럴 4곳 **`0xEFE974`(P.LIT_TBL_END)·`0xF3030C`(A3 hook +0x8C)·`0x314000`·`0xB11E28`**(PART2_PATCHES)이 기존 코드로 자모 포함 길이로 찍힌다.
- A3 max 리터럴: **파일 `0xF30304`**(= `PART2_HOOK_A3_FILE + 0x84`, 현재 `a7e20000`; `0xF30300`은 min `0x8840`, `0xF30308/0xF3030C`는 표 start/end, **`0xF30310`은 mask `ff7f0000` — 보호**). `:14356`이 hook을 쓴 뒤 `max(2350 코드 ∪ 자모 40)`으로 pack하고, `:14400` 회귀 가드는 PART2_HOOK_A3 상수를 읽는 기존 방식 대신 실제 기록된 rom[F30304:F30308]을 little-endian u32로 읽고, 비교 집합에 자모를 포함한다. T3는 정상 max 확장 성공과 기록된 max의 1바이트 변조 거부를 둘 다 검사한다. bit15 마커·`KOR_BASE` 경로 불변.
- 표시표 끝 `0x83FEF4`(FEDC+24)·선택표 `0x83FAF6..0x83FBAA`·`NAME_GRID_RANGES(0x83FAF0..0x83FF00)`는 **이번에 쓰지 않는다**(v1과 다름).

### 1.8 ROM 영역·소유권·쓰기 가드 (F3)
| 영역(파일) | 용도 | 가드 |
|---|---|---|
| `F09F60..F0A960` | 자모 타일 80 | zero assert |
| `F70000..F75748` | `nc_dense` | zero assert |
| `F75800..F77800` | 코드 이미지, **상한 8,192B** | zero assert · 초과 시 생성기 실패 |
| `F243A4..F24494` | A3 표 tail 40 | 기존 append 경로 |
| `F30304` 4B | A3 max 리터럴 | expect `a7e20000` |
| `34B0BC`10·`34B084`8·`34B20E`10·`34AB3C`8·`83FD58`4 | 훅 사이트 | §1.5 expect |
| `EFE974`·`F3030C`·`314000`·`B11E28` | 표 end 리터럴 | 기존 경로, 테스트가 4곳 == `NEW_TBL_RT+len` 대조 |
8KB 상한 근거: zero-run `F6E587..FD0000`(399,993B, candidate-re) 안에서 mission-title 예약 `F66000..F70000` 뒤·다음 점유 `FD0000` 앞이며 `F70000..F77800`은 직접 writer·manifest 어디에도 없다(T4의 일회성 충돌 검사가 `direct-writers.json`·`writer-addresses.json`·`integrity-ranges.json`과 교차 0 assert). 넘으면 생성기가 실제 크기와 함께 실패하고 총괄이 설계 허가 범위 내에서 정정한다. `DENY_REGIONS`에 좁은 항목 `('part2_name_compose', 0xF70000, 0xF77800)` 추가(텍스트 import 차단). 모듈 상수 `NAME_COMPOSE_WRITES`(위 표, 파일 오프셋)가 단일 정본. **가드 입력 분리**: S1/S2/S3/D1/P1의 원본 사이트는 orig에 §1.5 expect를 대조하고 현재 rom도 동일한지 확인한다. 새 주입 영역은 현재 rom의 쓰기 전 zero를 대조한다. 기존 빌더가 생성한 A3 max/표/종료 리터럴은 orig와 비교하지 않고 해당 단계의 기존 payload(2350+원본536, max E2A7 및 그 단계의 실제 table end)와 대조한 뒤 확장한다. 모든 사전조건은 기록 전에 검사하며 실패 시 ValueError와 입력 rom 불변을 보장한다. 후보 diff 검증은 「후보−baseline diff ⊆ `NAME_COMPOSE_WRITES` ∪ end 리터럴 4곳」(부분집합) **+ payload별 필수 대조**(각 영역이 생성 payload와 바이트 일치·빠진 영역 없음).

## 2. 작업 분해 (작업 1건 = 담당 1명, 같은 파일 동시 writer 금지)

| T | 내용 | 소유 파일(N 신규/M 수정) | 선행 | 병렬 |
|---|---|---|---|---|
| T1 데이터 | `data/jamo_to_code_40.json`(N), `data/jamo_glyphs_40.bin`(N), `tools/gen_jamo_assets.py`(N: `load_jamo_codes()`·`jamo_tiles()`·`dense_table()`·`jamo_table_entries(sylmap)`), `tools/test_jamo_assets.py`(N) | — | T2와 병렬 |
| T2 코어·이미지 | `tools/name_compose/{core.c,tramp.s,image.ld,gen_tables.py,build_image.py}`(N), `tools/part2_name_compose_blob.py`(N 생성물), `tools/test_name_compose_core.py`(N) | **T1이 JSON 파일을 먼저 생성**(커밋 불요, 파일 존재만) | T1과 병렬 |
| T3 빌더 통합 | `tools/build_korean_full.py`(M: `DENY_REGIONS` 1항목·상수·`_part2_name_compose(rom, orig)` 1함수·A3 max·table append·호출 1줄), `tools/test_part2_name_compose_build.py`(N) | T1, T2 | 단독 |
| T4 후보 빌드·정적 게이트 | `temp/name-grid-phaseB/namecompose-build/`(snapshot·manifest·보고서·JSON), `output/game_wars_korean_namecompose_20261023.gba`(ignored) | T3 | 단독 |
| T5 런타임 QA | `tools/qa_part2_name_compose.py`(N), `temp/name-grid-phaseB/namecompose-qa/` | T4 | 단독 |
| T6 문서 | `docs/reports/name_grid_2026-10-23/{PHASE_B_RE.md,PHASE_B_PLAN_APPROVAL.md,PHASE_B_QA.md}`(N), `AGENTS.md`·`CLAUDE.md`·`todo.md`(M) | T5 | 단독 |
| T7 리뷰·병합·정리 | 총괄 진행(§4.5) | T6 | — |

**T1** — ① 코드 선정·JSON 기록(§1.7) ② 40자 렌더 → bin ③ `dense_table(syl_to_code) -> bytes(22,344)` ④ `jamo_table_entries(sylmap, codes) -> bytes(240)`. 테스트: 40개·중복 0·2350 미중복·풀 소속·lead/trail 범위; bin SHA 고정 + 40쌍 ink>0; dense에서 2350 코드 정확히 2,350개 비영·`갣`·`뢔 쌰 쎼 쓔 쬬` 자리 0; 재실행 byte-identical. 완료: `python3 -I tools/test_jamo_assets.py` exit 0.

**T2** — 테스트는 ① 고정 기대표: 한글(`ㅎㅏㄴㄱㅡㄹ`→92af 888a)·강철(884990d3)·붉은달(8d5c 8f7e 89e7)·full8 `ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏㅂㅏㅅㅏㅇㅏㄴ`→`가나다라마바사안`(17 수락, confirm 16B `884088e989e28adf8bc38ca68da98ea2`, 다음 ㄱ `no_slot` 원자)·가한 자동 조합(갛 884D 경유)·`가+ㅋ` 거부·`한+ㄱ+ㅏ→한가`·`닭+ㅏ→달가`·`값+ㅣ→갑시`·`개+ㄷ` 거부·`간+ㅒ` 거부 보존·복합 7·겹받침 11·역삭제·8번째 active 받침 편집·미완성 confirm/space 거부·리터럴 셀·legacy 코드 backspace — 기대값은 **`mode-scope-re/model-results.json` 실측값**만 ② 시드 20261023 랜덤 20,000 조작: host 컴파일 `core.c`(ctypes, 128B 상태 버퍼) vs `hangul_compose.Composer` + live adapter 매 스텝 일치 ③ 11,172 음절 표준 키열 전수: 도달 2,345·거부 지점·snapshot 불변 ④ 이미지: relocation 0·undefined 0·`v4T`/`Thumb-1`·`.image` ≤ 8,192·raw==ELF·`SYMBOLS` 오프셋 4정렬·`nc_sel_priv` 90셀이 §1.2와 일치·`nc_row_priv` 길이/형식이 `grid-map.json` 원본 행과 동일(자모·새 공백은 사설 선택표와 일치, 간격·legacy 표시는 지정값 유지). 완료: `python3 -I tools/test_name_compose_core.py` exit 0(toolchain 있는 맥에서 재생성 일치 포함).

**T3** — `_part2_name_compose(rom, orig)` 순서: ① 원본/빈 영역/생성 단계별 가드(§1.8) ② 자모 타일·dense·이미지 기록 ③ S1~S3·D1·P1 ④ `NAME_COMPOSE_WRITES` 기록(`WRITE_LOG`엔 넣지 않음). A3 표 append와 max 리터럴은 §1.7 위치. 테스트: 원본에 patch → diff ⊆ 화이트리스트 **and** payload별 필수 대조; expect 1바이트 변조 → `ValueError`·rom 불변; generated-stage 가드(A3 생성 payload 변조 시 실패, 원본 훅 사이트만 orig와 동일 요구); 이미지 8,192 초과·JSON 변조 거부; A3 max ≥ 모든 코드; end 리터럴 4곳 일치; 분류 동일성 90셀; tracked 테스트는 ignored 연구 JSON에 의존하지 않는다. 실제 baseline 연구 JSON과 F70000..F77800의 교차 충돌 검사는 T4 일회성으로 수행하고 입력 해시/판정 요약을 영구 보고서에 보존한다. 완료: 새 테스트 + `tools/test_part2_native_controls.py`(`:146`의 `0xF70000` 반전 fixture 영향 없음 확인)·`test_part1_yesno_row.py`·`test_dialogue_script_safety.py` exit 0.

**T4** — 부모 checkout의 `data/` 생성물 2개 쓰기를 피한다: **snapshot = tracked 파일 + 이번 신규/수정 파일(미커밋 포함)을 해시 manifest(`snapshot_manifest.json`: 경로·SHA)로 고정해 ignored `namecompose-build/source/`에 복사**(HEAD git archive만 쓰지 않는다). snapshot에 원본 읽기 사본·폰트 env(`AW_FONT_DIR=temp/name-grid-phaseB/fonts`, `AW_HADASANS_FONT`, BLACK)·`EDITOR_LOCK`을 주고 1회 빌드: `nice -n 15 python3 tools/build_korean_full.py --out output/game_wars_korean_namecompose_20261023.gba --no-sync-outputs --report temp/encode_report.csv`(nice 거부는 기록만). 같은 빌드의 `temp/integrity_map.json`·`repoint_manifest.json`·`encode_report.csv`를 보존하고 5관문(`phase6_basic_test`, `qa_integrity_map --byte-only`, `qa_text_fit`, `qa_bteam_drift --json <details>`, `qa_part2_name_grid_shared_glyph`) 실행. **F7 판정 출처 분리**: B팀은 `--json` 산출의 (주소·cause·decision) 집합을 `baseline-build/.../retry1_bteam_details.json`과 set 비교(신규만 회귀); overflow 273/width 507은 `qa_text_fit.main`의 local `check_text(a,ko,ja,slot_override=None)` 분류에서 나온다. T4 temp의 compare_text_fit.py가 baseline source와 candidate snapshot에서 각각 같은 main을 실행하며 check_text 진입/복귀의 local a/ko/ja/slot_override 및 overflow/wider 카운터 증분을 sys.settrace로 수집해 (주소, 유형) 집합을 보존·비교한다. 분류 알고리즘을 복제하지 않는다. 실제 local 함수명과 변수는 해당 소스에서 확인하여 추적 지점을 고정하고, 추적 산출 집합의 개수가 main의 실제 출력 합계와 일치하는지 검증한다. 집합 추출에 실패하면 T4 미완료로 남기며 count 동일성으로 대체하지 않는다. 보호 파일 SHA(원본·full/final/title_test·dist·b44·baseline) 전후 동일, 부모 checkout의 T4 전후 git diff/파일해시가 동일하고 status는 T1~T3 의도 변경 목록과 일치, snapshot의 tracked 유래 파일 중 빌더가 항상 쓰는 data/sprite_build_layouts.json·objlabel_sprites.json은 전후 해시를 기록하고, 나머지는 불변. 부모 checkout은 두 생성 파일을 포함해 불변. 후보 vs baseline 바이트 diff 화이트리스트+payload 대조(결과 JSON). **F2 공유 글리프**: `grid-map.json`의 선택∪표시 쌍 전부에서 action marker(3131/3232/6262/6363/6565)를 제외한 코드들을 baseline·후보의 실제 native A3 경로로 비교한다. tools/test_dialogue_script_safety.py의 native_glyph 탐색을 재사용: root=LE32(rom[0x52F960])-0x08000000; bucket=root+((code&255)-0x40)*4; 연결 node 포인터를 따라 off+4의 lead가 code>>8인지 비교; 일치 node의 off+6..off+70 그림64B를 읽는다. 양쪽의 노드 해석(존재 여부/offset/linked traversal)과 그림 bytes가 같아야 한다. 부재코드는 baseline과 후보 모두 부재인지 별도 목록에 기록하고 필요 시 기존 원래 fallback 경로를 대조한다. 공유 가나에 재배치 한글 top/bot 인덱스를 적용하지 않는다. 장음815B 기존 게이트를 별도로 유지한다. 완료: 5관문 exit 0 + diff PASS + 공유 글리프 PASS + 보호 SHA 동일 + 후보 SHA·빌드 map SHA 기록.

**T5** — 하네스 `official-mgba/run-single.sh`(공식 0.10.5 `mgbah`, 명령 `frames`/`tap`/`dumpmem`/`savestate`/`loadstate`/`shot`/`break <addr> <log>`(BP 행: r0-r7·sp·lr·pc)) cold boot. 세이브: `native-re/replay-normal/new-eight.sav`(ア×8) 사본, `candidate-re/eight-save/hangul.sav` 사본. 키 그리드 변환: 각 입력 전 obj+0x1E/0x20의 현재 signed 좌표를 읽고 목표 셀까지 D-pad tap으로 이동한 뒤 A. 이동 후 실제 좌표를 다시 읽고, wide 버튼은 같은 동작 코드의 x10..14를 동등하게 취급한다. START 뒤 좌표(14,5)도 RAM에서 다시 읽는다. (0,0) 고정 시작을 가정하지 않는다. 스텝마다 obj 포인터(`dumpmem 03004650 4`) → `dumpmem obj 0x80`; oracle = `Composer` + live/stored adapter. 케이스(후보 ROM):
1. 그리드 입력 한글·강철·붉은달: 스텝별 live 일치, preview PNG, 자모 단계 VRAM glyph-cache 64B == 자모 타일(ㄱ·ㅏ·ㅘ).
2. 받침 이동 `한+ㄱ+ㅏ→한가`, `닭+ㅏ→달가`; V-only 복합 `ㅗ+ㅏ→ㅘ`와 reset 뒤 `ㅇ+ㅗ+ㅏ→와`를 별도 사례로 검사; 가한 자동 조합.
3. 미완성 확인 거부: `ㄱ` 상태 START·OK 셀 → `+0x67` 0 유지, 다이얼로그 없음, 상태 불변.
4. 2350 밖 거부 `개+ㄷ`, `간+ㅒ`, `가+ㅋ`: live 불변.
5. 공백·숫자·！ 리터럴, `가␣나` 저장 후 stored prefix(중간 공백 유지·끝 공백 trim).
6. **full8** `가나다라마바사안`(실제 키열 17) → 9번째 ㄱ 거부(len 8·8번째 미덮어쓰기) → 저장 → stored 16B == `884088e989e28adf8bc38ca68da98ea2`.
7. 지우기 `강→가→ㄱ→빈`; committed `가` B → 음절 삭제.
8. 취소 셀 → Yes → 편집기 복귀·destination 미변경; 재진입 tail `70..7F` 초기값.
9. legacy ア×8 재진입 → len 8·active 0 → B 1회 → 자모 입력.
10. **가카 경계**: `ㄱㅏ` → OK → RIGHT(No) → A → 편집 복귀(가 committed, active 0, dest 불변) → `ㅋㅏ` → 가카.
11. **정상 저장·콜드 로드(필수)**: 케이스 6의 8자 START→Yes→저장→덮어쓰기 Yes→`dumpsave`(O_EXCL) → 별도 프로세스 cold boot → 불러오기 목록·맵 preview·이름 재진입 live 16B 일치. SRAM offset 고정 단정 금지(1F504/1E504 둘 다 존재): 저장 파일에서 기대 패턴 검색 + cold reload RAM이 정본.
12. Versus: list-link-re 유효 맵 route로 저장 → cold boot → フリーバトル 이름 렌더(완성 음절만).
13. legacy 탁점 셀·R 키를 한글 active에서 누름 → 0x68·live 불변.
14. 원본 ROM 대조군 1건(ア 입력 route) — 하네스·route 유효성.
15. **F6 레지스터/스택 검증(실ROM break)**: 후보 자체의 각 훅 진입과 native 복귀 지점을 짝지어 SP와 live callee-saved r4-r11 보존을 대조한다(D1의 명시적 r5/r6 결과는 §1.5 계약 적용). LR/PC는 각 원거리 호출·복귀 계약에 맞는지 판정한다. baseline은 의미 대조군이며, 힙 확장으로 포인터/LR가 달라질 수 있으므로 baseline과 후보의 raw register 동일성을 요구하지 않는다. 기존 mgba_harness.c의 breakpoint callback은 r0-r15를 읽지만 출력은 r0-r7뿐이다. T5는 소유 temp에 그 소스 사본을 만들고 BP printf에 r8-r11 네 필드를 추가하는 최소 진단 수정만 허용한다. 원문과의 diff가 이 log 필드/인자뿐임을 기록하고 공식 0.10.5의 동일 compile definitions/library로 다시 컴파일, source/바이너리 SHA·명령·exit를 남긴다. 추적용 게임 코드나 serial 동작은 추가하지 않는다. nc_press/nc_confirm/nc_backspace 진입 BP에서 sp%8==0; nc_alloc 호출 전후 SP/r4와 반환 계약 및 global pointer/tail 초기값 검사. 수락·거부·삭제·할당·D1 mode0/mode1 각각 검사하며 mode0는 별도 synthetic RAM mode probe로 명시한다. 모든 고정 복귀 PC를 검사한다. D1의 6회 렌더러 진입(08314EB0)에 breakpoint를 추가해 r0=6,r1=6+2i,r2=[원래r4],r3=nc_row_priv[i] 및 스택 인자8000/0을 확인한다. nc_call_r7 때문에 r3가 함수 주소로 덮이지 않았음을 직접 대조한다.
Link: 기존 하네스가 client full ROM을 multiboot로 읽어 흰 화면 → **BLOCKED 정직 보고**, 게이트 아님. 실기: 미검증 명시. 완료: 1~11·13~15 PASS(증거 경로·exit·SHA), 12는 PASS 또는 구체 사유 BLOCKED, 종료 후 프로세스/claim 0.

**T6** — T7 리뷰·스캔·최종 커밋 전에, 문서가 인용하는 최소 QA 증거(PNG/RAM dump/BP log/정상키 route/명령·exit·SHA)와 연구 판정 요약을 docs/reports/name_grid_2026-10-23/evidence/에 영구 보존하고 모든 문서의 참조 경로를 그 위치로 갱신한다. 이 evidence/ 아래 필요한 파일은 T6 소유 신규 산출물이며 ROM/사용자 세이브는 제외한다. 이 작업과 문서 변경을 포함한 최종 tree를 T7 리뷰·secret-scan·commit·push·main 병합 대상으로 삼는다. `PHASE_B_RE.md`: 7개 원시 보고서 + mode-scope-re 핵심 사실(주소·바이트·dispatch 분류·lifecycle·trim·8번째 overwrite·IWRAM 복사·SRAM bank·native No 복귀)과 temp 경로·SHA. `PHASE_B_PLAN_APPROVAL.md`: 계획 sha·verdict·영수증. `PHASE_B_QA.md`: T4/T5 명령·exit·증거. AGENTS/CLAUDE/todo: Phase A 절 보존 + Phase B 절(자산 복구 완료·`NAME_COMPOSE_WRITES`·자모 JSON/bin 정본·blob 재생성 명령·0x80 ABI·S1~S3/D1/P1·native 표 원형 규칙·main 병합/재배포 범위·output 3종 SHA 불일치 사실). 시크릿·계정·IP 금지.

## 3. 모듈 간 약속
- tail ABI(§1.3)·live/stored adapter(§1.4)·심볼 이름(§1.6)은 T2·T3·T5·T6 공유. 변경 시 전부 고친다.
- `part2_name_compose_blob.py`: `CODE: bytes`, `CODE_SHA: str`, `IMAGE_RT = 0x08F75800`, `IMAGE_MAX = 0x2000`, `DENSE_RT = 0x08F70000`, `SYMBOLS: dict[str,int]`(§1.6 이름), `SOURCE_SHA: dict`(core.c, tramp.s, image.ld, tables.h). 빌더는 `IMAGE_RT + SYMBOLS[x] | 1`로 사이트 리터럴을 만든다.
- `gen_jamo_assets.py`: `load_jamo_codes() -> dict[str,int]`(40), `jamo_tiles() -> bytes`(2,560), `dense_table(syl_to_code) -> bytes`(22,344), `jamo_table_entries(sylmap, codes) -> bytes`(240). `tables.h`는 같은 JSON에서 생성(테스트가 `SOURCE_SHA[tables.h]`를 재생성 대조 — 이중 정본 금지).
- 트램펄린↔코어: r0=obj, r1=cell(u16 BE 값), 반환 r0∈{0,1}. 오류는 반환값으로만, 상태 불변.
- 빌더 가드 실패는 `AssertionError/ValueError`로 중단·rom 불변.

## 4. 검증·완료 조건·되돌리기 (F8)
4.1 작업별 완료 기준은 §2. 브라우저·기기 불필요, 하네스는 맥 공식 mGBA 0.10.5 단일 코어.
4.2 전체 완료 = T1~T5 명령 exit 0 + T6 문서 + Astra 승인 + 리뷰 대상 tree == T4/T5가 검증한 tree.
4.3 되돌리기: commit 단위, 실패 시 `git revert`. 후보 ROM은 ignored 산출물(삭제). 보호 파일은 쓰지 않는다. 동일 수정 3회 실패 → 중단·총괄 보고.
4.4 코드가 바뀌면 **바뀐 것에 걸린 검증만** 재실행: 코어/트램펄린 → T2·T3·T4·T5, 빌더만 → T3·T4·T5, 데이터만 → T1·T3·T4·T5(케이스 1·6·11), 문서만 → 없음.
4.5 순서: Astra `REVIEW-MODE: full` 1회(명세 준수 + 코드 품질, 지적마다 처방 + Change together) → 워커 1명이 반영 → `delta`(이전 리뷰 원문·revision 첨부) → 승인 → **최종 tree/ROM 검증**(승인 tree의 빌드 입력 manifest와 T4/T5 대상 소스/자산 및 후보SHA가 같음을 확인, T5 증거 revision 일치; 문서만 바뀌고 빌드 입력이 같으면 반복 풀빌드하지 않음) → scoped secret-scan → `feat(name-grid): 2편 이름 입력 두벌식 조합(Phase B)` 한국어 Conventional commit → push → handoff의 main 병합 → 병합 뒤 **소유권·조상·끝점·clean 확인**(`git fetch --prune`, L==R, `merge-base --is-ancestor`, 미커밋 0) 후 본 작업의 불필요한 임시물만 정리한다. 병합 후에는 T6에서 완료한 영구 증거 보존·참조 경로의 존재와 커밋 포함 여부를 확인한다. snapshot과 원시 연구/QA 디렉터리는 인용·재현에 필요하면 보존하며 harness-session-check keep에 사유를 기록한다. ROM/사용자 세이브는 커밋하지 않는다. 삭제는 인용되지 않는 자기 임시물과 조건 확인된 작업 브랜치/워크트리만 한다 → company 결과 전달(후보 SHA·빌드 map·BLOCKED 항목·output 3종 SHA 불일치·재배포 범위 밖). 수렴 점검은 `roles/final.md`.

## 5. 리스크 등급
`RISK: high` — 세이브 데이터 경로(destination 16B·SRAM 콜드 로드)·main 병합·런타임 ABI 패치가 걸린다. effort는 낮추지 않는다. 주의: 0x80 확장은 힙 다음 블록을 16B 민다(실행 사례 `0x02003080→0x02003090`) — 케이스 1·8·11에서 이웃 손상 징후 없음을 증거로 삼고 전수 증명 게이트는 두지 않는다.

## 6. 사전 부검
| 경로 | 방어 |
|---|---|
| 할당 실패(r0=0) | native와 같이 저장만, tail 미기록 — 「안 함」 |
| 사이트 바이트가 원본과 다름(b44 변형·다른 모듈 선행 쓰기) | 원본/생성 단계별 가드로 빌드 실패 |
| 자모 코드 풀 변동 | JSON 고정 + 풀 소속 assert → 빌드 실패 |
| 이미지 8KB 초과·헬퍼 심볼 유입 | 생성기 실패(`nm -u`·`--no-undefined`), 실제 크기 보고 |
| 좌표 범위 밖(x≥15·y≥6) | S1 거부(상태 불변) |
| 키 연타·중복 | 매 키 원자, 상태는 tail+버퍼뿐 |
| 중간 전원 차단 | 저장은 native 확인 경로만, 미완성 비저장 — 「안 함」 |
| 조용한 실패(거부음만) | native와 동일 UI, QA는 dump로 판정 — 「안 함」 |
| 9번째에서 native 덮어쓰기 재발 | S1이 mode1에서 AE00을 부르지 않음 + 케이스 6 |
| A3가 자모를 안 그림 | max 리터럴(F30304)·표 tail·end 리터럴 4곳 + 케이스 1 VRAM |
| mode0 회귀 | 표·리터럴 무변경 + D1/S1/S3 mode0 재생 + 분류 동일성 테스트 |
| Link/실기 | 미검증 보고, 게이트 아님 |

## 7. 검토·실행 안내
`harness-plan-review <이 파일> --risk high --context temp/name-grid-phaseB/PHASE_B_BRIEF.md --context temp/name-grid-phaseB/PHASE_B_REVISION_BRIEF.md --context docs/reports/name_grid_2026-10-23/COMPOSITION_SPEC.md --context temp/name-grid-phaseB/mode-scope-re/verification.log --context temp/name-grid-phaseB/mode-scope-re/grid-map.json --context temp/name-grid-phaseB/mode-scope-re/model-results.json --context temp/name-grid-phaseB/mode-scope-re/baseline-name-module.log --context temp/name-grid-phaseB/candidate-re/RUNTIME_REPORT.md --context temp/name-grid-phaseB/native-re/RUNTIME_REPORT.md`. exit 0 뒤 T1→T2(병렬)→T3→T4→T5→T6→T7 순서로 `harness-codex code` 위임, 5분 점검, 단일 Astra full→delta.

NEEDS RESEARCH: 없음 — 미확인 항목(kana 표 `[0x08487400]`에 lead≥0x88 쌍 부재, `qa_text_fit` 실제 local 추적 변수, Versus 도달)은 각각 T5 케이스 13·T4 trace 산출 검증·T5 케이스 12의 확인 항목으로 두었고 설계 확정에 필요하지 않다.




## v4 변경 대조(총괄 후보, Fable 재확인 전 구현 허가 아님)
- D1 Critical: rowdraw만 r7전용 call veneer로 r0-r3인자를보존,진입BP에서6행인자직접검사.
- D2: 표시행을사설선택레이아웃에서생성해공백까지동기화,간격/탁점display별도지정.
- D3: native A3 bucket/linked node 그림을비교하며한글재배치표타일검사와분리.
- D4: 기록된rom의A3max를읽는가드,정상확장/변조거부대조.
- D5: ignoredJSON은T4일회성검사,tracked테스트의존제거,필수증거영구보존후참조갱신/불필요임시물만정리.
- Nit: 추가범위표축소,빌드입력불변이면중복풀빌드안함.


## v5 변경 대조
D5 잔여에 동의한다. 증거 보존/참조 갱신을 T6의 리뷰·스캔·커밋 전 단계로 옮겼다. 병합 뒤에는 보존 완료와 커밋 포함 여부 확인 및 불필요 임시물 정리만 한다. 구현 설계와 검증 조건의 변경 없음.

PLANNED-BY: claude-fable-5-1 effort=high session=472c8898-b32c-4c1d-a02f-d5eccf3b3d19 receipt=state/plan-receipts/ recheck=ACCEPT base=be049c13
