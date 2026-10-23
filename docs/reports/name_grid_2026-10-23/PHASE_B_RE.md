# Phase B 런타임 RE — 2편 맵 에디터 이름 입력

작성 2026-10-23 · 대상 ROM: 원본 `original/Game Boy Wars Advance 1+2 (Japan).gba` SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` · 기준 HEAD `90908180938c2bf40ee38dea43c4c1304b09df8a`.

이 문서는 Phase B 설계의 근거가 된 런타임·정적 조사 사실이다. 원시 보고서 7개와 mode-scope 조사 산출물은 [`evidence/research/`](evidence/research/)에 바이트 그대로 복사했다. 출처 temp 경로와 SHA는 [`evidence/INDEX.md`](evidence/INDEX.md)에 있다. 주소는 GBA 버스 주소다. 파일 오프셋은 버스 주소에서 `0x08000000`을 뺀 값이다.

## 0. 역사와 현재

- **Phase A(이전)**: ROM 없이 참조 조합기만 만들었다([`PHASE_A_STATUS.md`](PHASE_A_STATUS.md)). 당시 원본 ROM·b44·세이브·route가 없어서 ROM 통합은 BLOCKED였다. 그 기록은 그대로 둔다.
- **Phase B(이번)**: 2026-10-23에 company 경유로 원본 ROM을 받았고 SHA를 대조했다. 폰트도 공식 출처에서 복구해 SHA를 맞췄다. 옛 사용자 세이브와 nyarch 자료는 여전히 접근할 수 없다. 대신 원본에서 정상 키만 써서 새 세이브를 만들었다(§2). b44는 `dist/` BPS로 다시 만들었다(`1ac68443…6f02`, [`b44-reference/RECOVERY_REPORT.md`](evidence/research/b44-reference/RECOVERY_REPORT.md)). 현재 소스 baseline 후보는 `ebbca0ba…3a8a`다([`baseline-build/RETRY1_BUILD_REPORT.md`](evidence/research/baseline-build/RETRY1_BUILD_REPORT.md)).
- 연구 단계의 「RAM에 넣은 완성 한글 8자 저장」 실험과 이번 기능의 「실제 그리드 키 8자 저장」 검증은 서로 다른 증거다. 앞의 것은 기존 A3가 완성 한글 이름을 그린다는 근거일 뿐이고, 자모 입력의 증거가 아니다. 뒤의 것은 [`PHASE_B_QA.md`](PHASE_B_QA.md)에 있다.

## 1. 원시 보고서 (판정 요약)

| 조사 | 판정 요약 | 복사본 |
|---|---|---|
| native-re (원본 런타임) | 정상 진입·ア×8 새 저장·cold reload 성공. 선택표/표시표 분리, 9번째 입력은 8번째 덮어쓰기, 끝 공백 trim, IWRAM 렌더러 복사 확인. 안전한 state 위치·Link는 미확정. 하네스는 로컬 vendor 0.11 소스 사본이며 upstream 동일성은 (unverified) | [`RUNTIME_REPORT.md`](evidence/research/native-re/RUNTIME_REPORT.md), [`verification.log`](evidence/research/native-re/verification.log) |
| candidate-re (baseline·b44) | 기존 A3가 `가/한/글`을 그림(VRAM 3×64B == ROM 타일). RAM 주입 8자를 native 경로로 저장하고 baseline·b44 cold reload 성공. 0x70→0x80 확장 입력 확보, A3 표 2,886 엔트리, zero-run 지도 | [`RUNTIME_REPORT.md`](evidence/research/candidate-re/RUNTIME_REPORT.md), [`verification.log`](evidence/research/candidate-re/verification.log) |
| list-link-re | 정상 키로 유효 맵(2색 HQ + 각 공장) 저장 → Versus 「デザインマップ」 목록·TEAM SETTING 도달, 한글 이름 A3 렌더 실측. Link는 BLOCKED(§9) | [`RUNTIME_REPORT.md`](evidence/research/list-link-re/RUNTIME_REPORT.md), [`verification.txt`](evidence/research/list-link-re/verification.txt) |
| mode-scope-re | dispatch는 셀 첫 바이트만 본다. 표·리터럴을 안 바꾸면 mode0/mode1 navigation이 그대로다(90셀). native 확인→No 복귀 실측. 모델 기대값 실측 | [`verification.log`](evidence/research/mode-scope-re/verification.log), [`model-results.json`](evidence/research/mode-scope-re/model-results.json), [`grid-map.json`](evidence/research/mode-scope-re/grid-map.json) |
| baseline-build RETRY1 | HEAD 소스 snapshot 빌드 1회 + 5관문 exit 0. 잔여 B팀 114·overflow 273·wider 507은 기존값 | [`RETRY1_BUILD_REPORT.md`](evidence/research/baseline-build/RETRY1_BUILD_REPORT.md) |
| b44-reference | 원본 + `dist/game_wars_korean_full_2026-10-21.bps` → manifest SHA·CRC·BPS trailer 일치 | [`RECOVERY_REPORT.md`](evidence/research/b44-reference/RECOVERY_REPORT.md) |
| official-mgba | 공식 0.10.5 archive(`91d6fbd3…cf14`, 태그 commit `26b7884b…`) 원문 빌드, ABI 상수 14개 일치. 이 단계에서는 실행 안 함 | [`BUILD_REPORT.md`](evidence/research/official-mgba/BUILD_REPORT.md) |
| arm-link-proof | clang Thumb-1 → GNU ld → objcopy raw: relocation 0·undefined 0·ELF==raw (독립 샘플) | [`PROOF_REPORT.md`](evidence/research/arm-link-proof/PROOF_REPORT.md) |

mode-scope-re에는 `REPORT.md`가 없다. 워커가 용량 한도로 보고서 작성 전에 종료했다(exit 1). 그래서 아래 사실은 그 폴더의 원시 산출물(`verification.log`·`model-results.json`·`grid-map.json`·`hook-contract-inputs.json`·`additional-contracts.json`·`execution-summary.json`·`runtime-cases.log`·`constructor-modes.log`)에서 직접 가져왔다.

## 2. 정상 새 게임 → 이름 입력 경로

- 원본: cold boot → 1+2 선택 → Part 2 → EDIT MODE/MAP → 처음 안내 A → SELECT(START는 미니맵) → ファイル → 名前入力. 이름 입력 자체의 안내도 A로 넘겨야 그리드가 움직인다. 저장·덮어쓰기 확인의 기본값은 いいえ라서 LEFT 후 A를 눌러야 한다. route: [`replay-normal/route.txt`](evidence/research/native-re/replay-normal/route.txt), cold 재로드 [`replay-cold/route.txt`](evidence/research/native-re/replay-cold/route.txt). 두 route에는 `loadstate`·`w8`·`w16`가 없다.
- 원본 새 저장 `new-eight.sav`(ア×8) SHA `d6e2651201c497139a4235034ed5d922816e1c2d2dd3c487ebf87d553ceeb481`. 세이브 파일 자체는 커밋하지 않는다.
- 후보 ROM은 MODE SELECT 항목이 더 많아서, 같은 키열에서 DOWN 2회 뒤 대기만 24→60프레임으로 늘렸다([`t5/routes/candidate-fresh-to-name.route`](evidence/t5/routes/candidate-fresh-to-name.route)). 원본 키를 그대로 쓰면 후보에서는 자유전으로 빠진다.

## 3. native 표와 90셀 분류

- 선택표 `0x0883FAF6`: 15×6 셀 × 2B. index = `2*(15*y+x)`. 커서는 obj `+0x1E`(x)·`+0x20`(y), signed 16비트.
- 표시표 `0x0883FE40`: 6행. 각 행은 `09` + 쌍 + `00` 형식이고 쌍 수는 17/17/17/11/11/11이다. 행 포인터 리터럴은 `0x0834AC24..AC38`. 선택 x 0..14 → 표시 쌍 `[0,1,2,3,4,6,7,8,9,10,12,13,14,15,16]`.
- 입력 루프 `0x0834AFA0`의 dispatch(`AFAE`, expect `0d4b1c680d4a16683568`)는 `[0x084873F4]`→선택표에서 셀의 **첫 바이트만** 읽는다. `62` 뒤로(B1E4), `63` 취소(B1C6), `65` 확인(B084), `31`/`32` 탁점·반탁점(B0E6/B146), 그 외는 전부 일반 셀(B0BC).
- 커서 이동 `B2C8`/`B338`(`134b`), mode0 취소 건너뛰기 `B3C0`(`1d4a`), 커서 그리기 `B470`(`234a`)은 리터럴로 선택표를 읽어 wide 버튼 여부만 본다.
- 그래서 선택표·표시표·행 포인터·좌표 표를 바꾸지 않으면 mode0·mode1 모두 navigation과 wide 버튼이 원본과 같다. 이것이 `WIDE_BUTTON_CLASS_INVARIANT 90 cells`다. 계약 바이트 9개는 [`hook-contract-inputs.json`](evidence/research/mode-scope-re/hook-contract-inputs.json), 추가 4개는 [`additional-contracts.json`](evidence/research/mode-scope-re/additional-contracts.json)에 있다.
- 결론: **native 공유 표는 원형 그대로 둔다.** mode1 전용 사설 선택표·표시행만 이미지 안에 두고, S1(일반 셀)과 D1(6행 그리기) 두 곳에서만 갈라진다.

## 4. 이름 객체 수명과 0x80 확장

- 할당 콜백 포인터 `0x0883FD58`(값 `71b93408` = `0x0834B971`) → `0x0834B970`: `mov r0,#0x70` → `0x08315300` → allocator `0x08315288`. 크기는 `(size+15)&~15`, 헤더 16B, **payload zeroing 없음**. 반환값은 `[0x03004650]`에 저장된다. 실행 사례 주소 `0x02003010`은 고정 주소가 아니다.
- 생성자 콜백 `0x0883FD78`(`fda93408`) → `0x0834A9FC`. 소멸자 `0x0883FE30` → `0x0834BA00` → free `0x08315390`. free는 헤더의 크기만 읽는다. 따라서 0x80으로 할당해도 free는 바꿀 필요가 없다.
- entry `0x0834B9C4`(BL 출처 `0x08304922`): r0=destination(`0x0200B09C`), r1=8. `+0x5C`=destination, `+0x60`=1(mode1), `+0x62`=8, `+0x63`=16. 다른 entry `0x0834B988`은 `+0x60`=0(mode0)이며 실제 사용처는 찾지 못했다.
- 기존 필드: `+0x2C` live 16B, `+0x44` 이전 사본, `+0x61` len, `+0x65/+0x66/+0x67/+0x68/+0x6A` UI 상태. `0x00..0x6F`는 전부 원형 보존한다.
- 관측 순서: free → entry → allocator → constructor → (편집) → free.
- **채택 ABI(tail +0x70..+0x7F)**: `+70 active(0/1)`, `+71 L(0xFF=없음)`, `+72 V(0xFF=없음)`, `+73 T(0..27)`, `+74..+7F 0`. committed 개수 C = `len − active`. 초기화는 할당 직후 `nc_alloc`이 한다. 0x80 확장으로 다음 힙 블록이 16B 밀린다(`0x02003080→0x02003090`).

## 5. 길이·trim·stored 계약

- 확인 경로 `B00C..B03E`: `0x0834B012`에서 `0x08313048`을 불러 끝 공백을 정리한 뒤 `+0x63` 바이트만 destination으로 복사한다. 0x70 전체 복사는 없다. 취소는 복사하지 않는다.
- trim은 2B씩 뒤에서 `81 40`을 찾고, `0x0831307C`에서 종단 첫 바이트를 0으로 쓴다. 예: `8341 8140` → `8341 0040`. 중간 공백은 유지된다.
- 짧은 이름은 종료 첫 바이트만 0이고 뒤에 옛 바이트가 남을 수 있다(7자 예: `…88400041`). 그래서 stored 판정은 「trim된 committed prefix 일치 + 8개 미만이면 바로 다음 바이트 0, 8개면 16B 전체 일치」만 본다. 16B 전부 0을 요구하지 않는다. 모델 `serialize()`의 zero-fill은 참조 표현이다.

## 6. 8번째 입력 덮어쓰기

- 원본: 8자 상태에서 A를 누르면 거부가 아니라 **8번째 칸을 덮어쓴다**(ア×8 → ア×7+イ, len 8).
- 새 계약: 9번째 슬롯이 필요한 입력은 `no_slot`으로 원자 거부한다. 8번째 active 편집은 허용한다. S1 mode1은 native append `0x0834AE00`을 부르지 않으므로 덮어쓰기가 다시 생기지 않는다.

## 7. A3 렌더러와 자모 확장

- 실행되는 렌더러는 IWRAM `0x0300605C` 함수다. ROM `0x08A3C7C0..`의 0x174B가 boot 때 BIOS로 복사된다. 후보의 트램펄린 자리는 `0x08A3C7E8→0x03006084`이고, `0x08F30281`(Thumb)로 점프한다.
- A3 표 `0x08F20000..0x08F243A4` = 2,886 엔트리(원본 536 + 한글 2,350, 6B). 조건: low byte > 0x3F, `0x8840 ≤ code ≤ max`, 표 안 엔트리 존재, top 인덱스 bit15. 타일 = `(idx & 0x7FFF)*32 + 0x08F00000`.
- 원본 ROM에서 `8840`을 넣으면 lookup이 실패하고 `8148`(？)로 fallback한다. 후보에서는 기존 A3가 처리한다. 그래서 원본의 `?`는 후보 기능 부재의 증거가 아니다.
- 자모 40개: `extend_pool(original)` 3,326 − 2350 매핑 = 976개 중 정렬 첫 40개(E2A8, E2AB, E2AD, …, E352). 첫 값 E2A8은 기존 max E2A7보다 크므로 max를 넓혀야 한다. 이번 빌드는 max `0xE352`, 표 끝 `0x08F24494`(2,926 엔트리)이고, end 리터럴 4곳 `0xEFE974`·`0xF3030C`·`0x314000`·`0xB11E28`가 같이 늘어난다. 타일 1273(빈칸)·1274(사설 자)는 보존하고 자모는 1275+2i/1276+2i다.
- **공유 A3 가나 그림은 바꾸지 않는다.** 이전 Sweep 3에서 그림을 바꾸면 2편 대사 대시(`0x815B`)가 오염되는 것이 확인됐다([`../../fail.md`](../../fail.md) 「2026-10-23 Part 2 이름 그림 공유 회귀」). 이번 후보는 72 코드 노드·그림 64B가 baseline과 같다([`PHASE_B_QA.md`](PHASE_B_QA.md) T4).

## 7.1 채택한 훅 자리 (바이트 기반 4곳 + 포인터 1곳)

mode 판정은 `[obj+0x60]`(1이면 mode1, 그 외는 native 경로)이다. 원본 expect는 원본·baseline에서 같았다. 정본 상수는 `tools/build_korean_full.py`의 `NAME_COMPOSE_SITES`·`NAME_COMPOSE_WRITES`다.

| 자리 | 파일 오프셋·길이 | 원본 expect | mode1 | mode0 |
|---|---|---|---|---|
| S1 일반 셀 | `0x34B0BC` 10B | `6520f0f7b9fcfff79dfe` | 사설 선택표 셀 → `nc_press` → 소리 65/68 → `0x0834A954` → `0x0834B428` | 소리 65 → `0x0834AE00` → `0x0834B0C6` |
| S2 확인 | `0x34B084` 8B | `fff728ffcee10000` | `nc_confirm`=1(미완성)이면 소리 68, 0이면 `0x0834AED8` | `0x0834AED8` |
| S3 지우기 | `0x34B20E` 10B | `01381070fff725fefff7` | `nc_backspace` → redraw → `0x0834B21A` | 원 명령 재생 → `0x0834AE60` → redraw → B21A |
| D1 표시 6행 | `0x34AB3C` 8B | `2268394b80263602` | 사설 행 6개를 `0x08314EB0`로 그림 → `0x0834ABA2` | `r2=[r4]; r3=0x0883FE40; r6=0x8000` → `0x0834AB44` |
| P1 할당 콜백 | `0x83FD58` 4B | `71b93408` | `nc_alloc`(0x80 할당 + tail 초기화) | 같음(tail은 mode0에서 안 씀) |

불변으로 두는 포인터: `0x83FD78` `fda93408`, `0x83FDE0` `41b43408`, `0x83FD28` `55b43408`. R 키·탁점·반탁점·취소·커서 이동·AED8 검증·B00C trim도 바꾸지 않는다. 한글/자모가 마지막 쌍이면 native 탁점 처리기가 가나 표에서 못 찾아 소리 68로 거부한다.

## 8. 가한·가카 경계와 native No

- `가한`: ㄱㅏㅎㅏㄴ을 차례로 누르면 `갛`(0x884D, 2350 포함)을 거쳐 자동으로 `가한`이 된다. 따로 확정할 필요가 없다.
- `가카`: `가+ㅋ`=갘은 2350 밖이라 원자 거부된다. native 확인 → No로 편집 화면에 돌아오면 확정이 남는다. mode-scope 실측: 확인 질문의 기본값은 Yes라서 RIGHT 후 A가 No이고, 이름·len·destination이 바뀌지 않는다([`runtime-cases.log`](evidence/research/mode-scope-re/runtime-cases.log)). 새 키 정책은 만들지 않았다.

## 9. 소비자·SRAM·Link

| 항목 | 사실 | 한계 |
|---|---|---|
| 이름 preview | live `+0x2C` → stack 문자열 → `0x08314EB0` → IWRAM A3 | — |
| Design Maps 불러오기 목록 | `0x0200B204` → A3 | 별도 편집기 HUD 이름 렌더러는 (unverified) |
| 저장 화면 상단 | `0x0200B09C` → A3 | — |
| Versus 「デザインマップ」 | 유효 맵 조건(영문 AW2 설명서 17쪽: 서로 다른 색 HQ 2개 + HQ마다 유닛 또는 생산 거점) 충족 시 category5 목록·TEAM SETTING 도달. 이름 `0x02027F4E` → A3 | 전투 시작 이후는 (unverified) |
| SRAM | 이름 레코드가 `0x1E504`·`0x1F504` 두 곳에 생긴다(bank로 추정). 고정 offset 하나로 판정하지 않는다 | bank·checksum 포맷 해석은 (unverified) |
| Link | 기존 `tools/mgba_link_harness.c`는 client를 `GBALoadMB`로 읽는다(앞 256KiB만 EWRAM). full cartridge client가 흰 화면이 되고, READY 전 단계에서 멈춘다(원본·후보 동일) | **BLOCKED** — 이번 승인 범위 밖. 시리얼 하네스는 만들지 않았다 |
| 실기(GBA 하드웨어) | 이번에 돌리지 않았다 | 미검증 — 승인 범위 밖 |

## 10. 하네스·도구 정체성

- 연구 1단계(native-re, candidate-re)는 로컬 vendor mGBA 0.11 사본 + temp 어댑터 하네스(`dfcd4c76…c614`)를 썼다. upstream과의 동일성은 (unverified)다.
- list-link-re·T5는 공식 0.10.5 빌드(`libmgba` `83744c60…960da`)를 썼다. T5는 `tools/mgba_harness.c` 사본에 BP 출력 r8–r11 필드 4개만 더했다(diff [`t5/harness/harness.diff`](evidence/t5/harness/harness.diff)).
- ARM 도구: Apple clang 21.0.0 + Homebrew `arm-none-eabi-binutils` 2.47. 일반 빌드는 컴파일러 없이 생성된 `tools/part2_name_compose_blob.py`만 import한다.
