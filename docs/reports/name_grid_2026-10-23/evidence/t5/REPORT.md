# T5 런타임 QA — 실제 그리드 키·저장·콜드 재로드·레지스터 계약 (PLAN-v5 §2 T5)

상태: **15개 케이스 전부 PASS**(12 포함). 최종 집계 `python3 verify.py` → `T5_RESULT PASS`, exit 0. 생산 코드·자산·ROM·세이브·기존 도구는 수정하지 않았고 커밋도 하지 않았다. 실기기는 미검증, Link는 BLOCKED이며 이번 범위 밖이다.

- 수행: 로컬 Claude(Orca task_050ba844ee2e / ctx_24a758c40328), role=code, risk high, effort high. 기준은 `ROUTING_UPDATE.md`(「이 pc 하네스대로」).
- 계획: `PLAN-v5.md` sha256 `60a7574a…21b4`(재계산 일치)와 `PLAN-REVIEW-v5.md` `VERDICT: APPROVE`. 브리프: `T5_BRIEF.md`. 소유 범위는 이 폴더 `temp/name-grid-phaseB/t5-runtime/`뿐이다. 계획에 있던 `tools/qa_part2_name_compose.py`(tracked)는 브리프 지시에 따라 만들지 않았다.
- 후보 ROM: `output/game_wars_korean_namecompose_20261023.gba`. 실행 전후 SHA는 모두 **`1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb`**로 T4 보고와 같다. 이 SHA는 Emu 시작 때마다 assert한다.
- 대조 ROM: 원본 `a8ad7c7d…831c`, baseline(조합기 없는 같은 빌드) `ebbca0ba…3a8a`. 둘 다 읽기만 했다.

## 실행 환경 (공식 mGBA 0.10.5 + r8–r11 BP 로그 최소 사본)

- `harness/mgba_harness_t5.c`는 `tools/mgba_harness.c`(`1894c25c…`)의 사본이다. 원문과의 diff(`harness/harness.diff`)는 BP `fprintf` 한 줄의 r8–r11 필드 4개와 인자 4개뿐이다. 소스 SHA는 `86378640…1b65`이다.
- 컴파일 `python3 harness/build.py`(exit 0)는 공식 `official-mgba/commands.jsonl`의 `compile-mgbah` argv를 그대로 썼다. 다른 점은 소스·출력 경로뿐이다. `-D` 29개는 `build/CMakeFiles/mgba.dir/flags.make`의 C_DEFINES 29개와 같다(`harness/flags_make_defines.txt`). 헤더와 라이브러리도 공식 빌드와 같다. 바이너리 `harness/mgbah-t5`의 SHA는 `0427fc40…2fd2`, 라이브러리 `libmgba.dylib`의 SHA는 `83744c60…960da`(공식과 같은 파일)이다. 기록은 `harness/build.json`에 있다. 첫 시도는 내 build.py의 키 오류(`argv`→`command`)로 exit 1이었다.
- 라이브러리 로딩: `nice`(SIP 보호 바이너리)를 거치면 `DYLD_LIBRARY_PATH`가 제거된다. 그래서 첫 실행(pid 81685)은 dyld 실패로 즉시 종료됐다(`runs-failed/prep-fresh-attempt1`). 공식 바이너리와 같은 rpath `@executable_path/build`가 공식 build 폴더를 가리키도록 `harness/build`에 symlink를 두었다.
- 드라이버는 `t5lib.py`다. 실행마다 `runs/<tag>/`를 만들고 cwd·`TMPDIR`·`AW_KOR_TEMP_DIR`·emulator log를 모두 그 안에 둔다. 세이브는 `O_EXCL`로 사본을 만들고, 하네스는 `--read-only-save`로 그 사본의 mkstemp 사본을 쓴다(종료 시 삭제). PID 시작·종료는 `processes.jsonl`에 남겼다. 같은 tag로 다시 실행하면 이전 폴더를 `runs-superseded/`로 옮기고 지우지 않는다.
- 커서 이동: 입력마다 `[0x03004650]`에서 obj를 읽고 `obj+0x1E/+0x20`(signed)을 읽는다. D-pad를 한 번 누를 때마다 좌표를 다시 읽어 목표 셀까지 간 뒤 A를 누른다. (0,0)에서 시작한다고 가정하지 않았다. wide 버튼은 같은 코드면 x10..14를 같은 셀로 본다. START 뒤에는 (14,5)를 RAM에서 다시 읽었다.
- 오라클: 스텝마다 `hangul_compose.Composer`와 계획 §1.4 live adapter로 대조한다. 대조 항목은 `slot[0:2n]`, `n<8`이면 `slot[n]==0000`, `len`, tail `+70..+73`, `+74..+7F==0`이다. 뒤쪽 garbage는 강제하지 않는다. stored adapter는 trim prefix와 첫 0만 보고, 8자면 16B 전체를 본다. 소리 ID는 sound 함수 `0x0833BA34` BP의 r0로 확인한다(수락 65, 거부 68, 삭제 66).
- host C와의 연결: T2 `t2-core/test.log`(같은 `core.c`를 host로 컴파일, 랜덤 20,000회·전수 11,172회를 Composer와 대조)가 ROM 이전 단계의 근거다. T5는 ROM 실행 결과를 같은 Composer와 대조한다.

## 시작 상태 (후보 cold boot + 정상 키, 후보 전용 savestate만 재사용)

| 상태 | 만든 방법 | 증거 |
|---|---|---|
| `runs/prep-fresh/name-entry.ss0` | 빈 카트리지 후보 cold boot, 그다음 `routes/candidate-fresh-to-name.route`. 이 경로는 원본 fresh3 키 그대로이고, 후보 MODE SELECT에 항목(상점·도전)이 더 있어 DOWN 2회의 대기만 24→60프레임으로 늘렸다. 이어 편집→지도→안내 A×8→SELECT→파일→이름 입력 | `name-entry.png`, `bp.log`(nc_alloc 1회, tail `00ffff00`+0×12) |
| `runs/prep-legacy/legacy-name.ss0` | `native-re/replay-normal/new-eight.sav`(ア×8, 원본에서 정상 키로 만든 저장, SHA `d6e26512…b481`)의 사본으로 후보 cold boot, 그다음 `replay-cold` 키 → 맵 불러오기 → 이름 재진입 | len 8, active 0, 마지막 A(ㄱ)는 no_slot으로 거부, 내용 불변 |

탐색 실행 `runs/explore-fresh*`에서는 원본 경로를 그대로 쓰면 후보에서 자유전으로 빠진다는 것을 확인했다(`runs-failed/prep-fresh-attempt2`, 실패 증거로 보존).

## 케이스별 결과 (기대값은 실행 전에 `expectations.json`에 고정했다)

| # | 결과 | 핵심 근거 (모두 `runs/` 아래) |
|---|---|---|
| 1 | PASS | `case1-한글/강철/붉은달`: 스텝마다 live==Composer, 최종 `92af888a` / `884990d3` / `8d5c8f7e89e7`. 자모 preview는 A3 copy BP(r6=ROM src, r7=VRAM)로 확인. VRAM 64B가 ROM 타일(1275+2i/1276+2i) 및 `data/jamo_glyphs_40.bin`과 일치: ㄱ(`case1-강철/vram-ㄱ.bin`), ㅏ(`case1-vowel`), ㅘ(`case2-wa-vonly`). PNG `preview.png` |
| 2 | PASS | `한가`=`92af8840` · `닭`(`9648`)+ㅏ→`달가`=`89e78840` · V-only ㅗ+ㅏ→ㅘ `e346` · 새 상태에서 ㅇㅗㅏ→`와` `8f4c` · ㄱㅏㅎ에서 `갛`(`884d`)을 거쳐 ㅏㄴ→`가한` `884092af` |
| 3 | PASS | ㄱ 상태에서 START: 커서 (14,5)(RAM 재조회), `+0x67`=0, BP 순서 S2→tramp_confirm→nc_confirm→ret→sound 68, AED8(질문) 없음. OK 셀에서도 결과 같음. live·destination 불변 |
| 4 | PASS | 개+ㄷ · 간+ㅒ · 가+ㅋ: 모델 `not_in_2350`, sound 68, live·len·tail 불변 |
| 5 | PASS | ㄱ 상태의 공백·숫자 입력은 거부. `가␣1！`=`8840814082508149`. `가␣나`를 확인하면 destination `8840814088e9`+00. `가␣`를 확인하면 `8840 0040…`: 끝 공백의 첫 바이트가 0이 되는 native trim(원본 RE와 같은 동작) |
| 6 | PASS | 실제 키 17개 전부 수락(sound 65). 8번째 `아`→`안` 편집(active). 9번째 ㄱ은 no_slot·68이고 8번째는 덮어쓰지 않음. stored 16B는 `884088e989e28adf8bc38ca68da98ea2`. 11a와 11b에서 두 번 독립 수행 |
| 7 | PASS | `강`에서 B→`가`→`ㄱ`→빈 상태(tail `00ffff00`). committed `가`+active `나`에서 B, B 뒤 B 1회로 `가` 음절 전체 삭제 |
| 8 | PASS | 취소 셀 → 「어머, 역시 그만두시나요?」 → 예 → 편집기 복귀(`after-cancel-yes.png`). destination 불변. SELECT→파일→이름 입력 재진입 시 nc_alloc 재실행, tail `00ffff00`+0×12, live == destination |
| 9 | PASS | legacy ア×8 재진입: len 8, active 0 → B → ア×7 → ㄱ: `8341×7 e2a8`, tail `0100ff00` |
| 10 | PASS | ㄱㅏ → OK 셀(질문 x67=2, AED8 호출) → RIGHT(아뇨) → A: `가` committed, active 0, destination 불변 → ㅋㅏ → `가카` `88409163` |
| 11 | PASS | **전원 투입부터 정상 키만**(loadstate·w8 없음). 11a: 빈 카트리지 → full8 → 확인 → 저장(빈 슬롯, 「저장하시겠습니까」 예) → `dumpsave case11a.sav`(SHA `8bf74323…692f`, 패턴 `0x1E504`) → 별도 프로세스 cold. 11b: ア×8 저장 사본 → 맵 불러오기 → 재진입 → B×8 → full8 → 저장 → 「덮어쓰시겠습니까?」 예 → `case11b.sav`(`43ae680e…7606`, 패턴 `0x1F504`) → 별도 cold. 두 cold 모두 불러오기 목록 문자열 `0200B204` 16B, 맵 preview 화면, 이름 재진입 live 16B·len 8·active 0, destination `0200B09C` 16B가 일치. SRAM bank는 고정하지 않고 패턴 검색으로 찾았다 |
| 12 | PASS | 11b 저장 사본에 기존 `list-link-re/candidate-map.route`(HQ·공장 배치, native 저장)를 그대로 재생 → `valid-map.png` 「플레이 OK!」, 빨강/노랑 HQ·공장 → `case12-valid.sav`(`b70ea22e…c692`, 이름 유지) → 별도 cold로 `candidate-cold-fixed.route` 재생 → Versus 「디자인 맵」 목록(category5)에 `가나다라마바사안` 표시, 8음절 모두 A3 copy 확인 → A → TEAM SETTING(2진영) `selected.png` |
| 13 | PASS | 한글 active(`가`)와 미완성 자모 active(`ㄱ`) 상태에서 탁점·반탁점 셀과 R: 모두 sound 68, live 불변. **T7-FIX1 정정**: 처음 채택한 실행은 「자모 active」 단계에서 `ㄱ`을 눌러 `각`(완성 음절, `8841`·tail `01000001`)을 만들어 미완성 자모를 검사하지 못했다(Astra full-v1 F1). `B`로 `가→ㄱ`을 만든 뒤 세 조작 직전·직후마다 live `E2A8`·len 1·tail `0100ff00`+0×12를 명시 검사하도록 고쳐 케이스 13만 다시 실행했다(아래 「T7-FIX1 정정」). 13b(legacy 가나 보존): 원본에서 정상 키로 만든 ア×7カ 저장을 후보에서 불러와 탁점→`ガ`(834B), R→`カ`, 반탁점→거부(68). 결과·소리가 **원본 ROM의 같은 조작과 일치** |
| 14 | PASS | 원본 ROM, 같은 하네스, 원본 fresh 경로: A 1회 → `ア`(8341). BP 경로 S1→sound→AE00→RET_B0C6(트램펄린 없음). 이어 ア×7カ를 입력해 저장(`original-kana.sav` `602471df…371e`)했고 13b의 대조군으로 썼다 |
| 15 | PASS | 아래 절 참조. 계약 위반 0건 |

## 케이스 15 — 실ROM BP 계약 (`case15-contracts.json`, `case15-rowseq.json`)

- 대상: 이 폴더의 모든 후보 실행 `bp.log`. BP 28개(S1/S2/S3/D1/P1 진입, 트램펄린 4개, C 진입·복귀 3쌍, 고정 복귀 PC 5개, allocator·nc_alloc 내부, rowdraw, sound, AED8, AE00, A3 copy, P1 호출자 복귀 `083162A2`). 로그 PC는 BP 주소+2로 실측했다.
- 집계(T7-FIX1 케이스 13 재실행 뒤): S1 mode1 수락 116 / 거부 11, S2 mode1 수락 6 / 거부 2, S3 mode1 17, P1 9, D1 mode1 9, mode0의 D1/S1/S2/S3 각 1. **위반 0.**
- 검사 항목:
  - 사이트 진입→트램펄린 레지스터 동일.
  - C 진입 `sp%8==0`, `r0==obj(02003010)`, C 복귀 sp 동일, 반환값 ∈{0,1}.
  - S2 수락 시 AED8 호출.
  - 고정 복귀 PC: B428 / B0C6 / B21A / AB44 / ABA2.
  - 복귀 시 r4–r11·SP·LR이 진입과 같음. D1 mode1은 r4/r7–r11·SP·LR만 같고 **r5=0, r6=0x8000**.
- D1 mode1 rowdraw `08314EB0` 6회: r0=6, r1=6+2i, r2=[원래 r4=08814FB0]=`0201BB40`, r3=`nc_row_priv_i`(`08F7613C/…160/…184/…1A8/…1C0/…1D8`), r7=`08314EB1`(함수 주소는 r7에만 있고 r3에는 없다), rowdraw 진입 sp=`03007D28`=D1 진입 sp−16. **스택 인자**: 같은 pending 상태에서 `watchaddr 03007D28 8 a`로 확인했다. D1이 각 호출 전에 `[sp]=00008000`, `[sp+4]=0`을 쓰고(pc `08F759D6/D8` 등), rowdraw가 `08314EC6/EC8`에서 그 값을 6회 읽는다.
- P1: nc_alloc 진입 → allocator r0=0x80, lr=`08F75A8D`, sp=진입−8 → 반환 `02003010` → 에필로그 → 호출자 `083162A2` 복귀. sp·r4–r11이 진입과 같고, r0=복귀 주소로 원본 B970 프레임(`pop {r0}; bx r0`)과 같다. 전역 `[03004650]`=반환 포인터, tail 초기값 `00ffff00`+0×12.
- **mode0는 합성이다**(`runs/case15-mode0-SYNTHETIC`):
  - pending 상태를 만들었다(`case15-pending`). 정상 키로 이름 입력을 누른 뒤 프레임 단위로 진행해, nc_alloc는 끝났고 D1은 아직인 프레임 17에 savestate를 남겼다. 이때 `+0x60`=1.
  - 그 상태에서 `w8 02003070 00`만 쓰고 생성자를 실행했다.
  - 결과: D1 mode0 → AB44(r2=`0201BB40`, r3=`0883FE40`, r6=0x8000), native rowdraw 6회 → 가나 그리드. A(0,0)=`ア` 추가(S1 mode0→tramp→sound→AE00→B0C6), B 삭제(S3 mode0→B21A), START→AED8 질문.
  - native 대조: baseline ROM의 정상 이름 화면(`case15-baseline-native`)과 D1 구간 rowdraw (r0..r3) 6회가 **완전히 같다**. A 결과 `8341`과 BP 경로(트램펄린 한 단계 외)도 같다.
  - 같은 실행의 `result.json` `pass:false`는 전체 화면 픽셀 비교 결과다. 배경 스크롤과 1px 가로 오프셋(타이밍 차이로 추정, unverified) 때문에 판정 근거로 쓰지 않았고, rowdraw 인자 대조로 대체했다.
- baseline과 후보의 raw register 동일성은 요구하지 않았다(힙 +16B).

## 실행 명령과 종료코드 (cwd = 이 폴더, 원문 로그 `logs/`)

| 명령 | exit | 비고 |
|---|---|---|
| `python3 harness/build.py` | 1 → 0 | 1차는 스크립트 키 오류 |
| `python3 protect.py before` / `after` | 0 / 0 | 469개 보호 파일 해시·HEAD·`git status`·`git diff` SHA 전후 동일: `PROTECTED_UNCHANGED []` |
| `nice -n 15 python3 prep_fresh.py` | 0 | 1차 dyld 실패, 2차 원본 경로로 자유전에 빠짐(둘 다 `runs-failed/`) |
| `nice -n 15 python3 explore.py …` ×3 | 0 | 후보 메뉴 경로 탐색 |
| `nice -n 15 python3 prep_legacy.py` | 0 | 1차는 obj 읽기 시점 assert(`runs-failed/`) |
| `python3 cases.py 1 2` | 0 | 첫 1회는 case1-강철 VRAM 덤프 시점 오류(이후 글자가 같은 캐시 슬롯을 덮음)로 FAIL. 스텝 직후 덤프로 고친 뒤 PASS |
| `python3 cases.py 3 4 5 7 8 9 10 13` | 1 | case5×2·case8·case10이 질문 창 대기 부족(START/질문 후 24–60프레임에 누른 A가 무시됨)으로 FAIL/예외 |
| `python3 cases.py 5 8 10 13` | 0 | 질문 대기를 120/180으로 고친 뒤 PASS(원본 RE 경로도 120–180 사용) |
| `python3 case11.py a` / `b` | 0 / 0 | |
| `python3 case14.py` | 0 | 14 + 13b |
| `python3 case15.py pending` / `modes` / `analyze` | 0 / 0 / 1→0 | modes 1차는 mode0 안내문 2페이지 처리 누락과 내 mode1 판정식 오류로 다시 실행. analyze 1차는 import 누락 |
| `python3 case15_mode0_vs_baseline.py` · `case15_rowseq.py` | 0 · 0 | |
| `python3 case12.py` · `case12.py cold-only` | 0 · 0 | 두 번째는 선택(TEAM SETTING) 단계를 추가해 cold만 다시 실행 |
| `python3 verify.py` | **0** | `T5_RESULT PASS`, hygiene OK |
| (T7-FIX1) `python3 -B temp/name-grid-phaseB/t5-runtime/cases.py 13` | 0 | 케이스 13만 재실행(F1). 옛 실행은 `runs-superseded/case13-1792750756/`로 자동 이동. 원문 `logs/case13-t7fix1.*` |
| (T7-FIX1) `python3 -B temp/name-grid-phaseB/t5-runtime/case15.py analyze` | 0 | 에뮬레이터 없음. S1 mode1 c_ret0 117→116, S3 mode1 16→17(케이스 13의 `ㄱ` 입력 1회가 `B` 1회로 바뀜), 위반 0. 원문 `logs/case15-analyze-t7fix1.*` |
| (T7-FIX1) `python3 -B temp/name-grid-phaseB/t5-runtime/verify.py` | 0 | `T5_RESULT PASS`, hygiene OK. 원문 `logs/verify-t7fix1.*` |

이전 실행은 `runs-superseded/`, 실패 실행은 `runs-failed/`에 지우지 않고 보존했다. 같은 수정을 세 번 실패한 경우는 없다.

## 보호·정리

- 보호 파일 469개(원본·output ROM/세이브·dist·연구 폴더의 sav/ss0/json/py/md·조합 소스/자산·공식 mGBA): 전후 SHA 동일. HEAD `90908180…`, `git status`·`git diff` 전후 동일.
- 프로세스: `processes.jsonl`에서 시작한 프로세스는 모두 종료가 기록됐다. dyld 실패 1건(pid 81685)은 즉시 종료라 exit 미기록이다. `pgrep -f mgbah-t5` 결과 없음. 하네스 mkstemp 세이브 사본은 남아 있지 않다.
- 다른 ROM의 savestate는 쓰지 않았다. `loadstate` 출처는 전부 이 폴더의 후보 전용 ss0이다. RAM 쓰기는 mode0 합성 1건뿐이다(`verify.py`가 assert).
- 정리하지 않고 남긴 것: 이 폴더(약 115MB, T6 증거 원본). 워크트리·claim·브라우저·추가 워커는 없다.

## 계획 대비 어긋난 점

1. 산출 위치: 계획 T5의 `tools/qa_part2_name_compose.py`와 `namecompose-qa/` 대신 브리프 소유 범위 `t5-runtime/`(temp 스크립트)를 썼다.
2. 후보 fresh 경로: 원본 fresh3 키에서 MODE SELECT의 DOWN 2회 대기만 60프레임으로 늘렸다(후보 메뉴 항목 차이). 다른 키는 그대로다.
3. 케이스 12의 유효 맵: 기존 route를 새 정상 입력 세이브(11b)에 적용했다. 같은 원본 맵이 기반이라 route가 그대로 맞았다. 이 route는 저장을 여러 번 하므로 패턴이 4곳(`0x11504/0x15504/0x17504/0x1F504`)에서 나온다. bank·슬롯 포맷 해석은 (unverified).
4. 케이스 13의 「legacy kana 변환 보존」은 원본에서 정상 키로 만든 カ 저장을 후보에서 불러와 검증했다(케이스 14와 같은 실행).
5. mode0 native 대조는 전체 화면 픽셀 대신 rowdraw 인자 시퀀스와 키 결과로 했다(위 설명).

## 남은 위험 (unverified)

- 실기기(GBA 하드웨어) 미검증. Link(Multiboot client full ROM)는 기존 BLOCKED이고 이번에 다시 조사하지 않았다.
- SRAM 레코드·bank 선택·체크섬 포맷 전체 해석(패턴 검색과 cold RAM만 근거).
- 힙 +16B 이웃 영향: 케이스 1·8·11에서 이상 징후는 없었다(cold 재로드·재진입 정상). 전수 증명은 아니다.
- 시각 관찰(판정 밖): 그리드 자모가 좁게 몰려 보인다(`case1-*/preview.png`). 계획의 표시 행 규칙대로 렌더된 결과다. 디자인 품질 판단은 T5 범위가 아니다.
- 자모 코드의 대화 렌더러(0x030065E0) 경로 표시는 이번에도 대상이 아니다.

## T7-FIX1 정정 (2026-10-23, Astra full-v1 F1)

- 결함: `cases.py` 케이스 13의 「자모 active」 단계는 `c.jamo('ㄱ')`이었다. 앞 단계의 active `가`에 `ㄱ`이 받침으로 붙어 `각`(완성 음절)이 되었고, `dakuten-incomplete`·`handakuten-incomplete`·`R-incomplete` 세 스텝은 모두 `preview="각"`·코드 `8841`·tail `01000001` 상태에서 돌았다. 그 실행의 PASS는 「한글 active」 검사로만 유효하고 미완성 자모 coverage의 근거가 아니다.
- 수정: 그 줄을 `c.backspace()`로 바꿔 `가→ㄱ`을 만들고(B 소리 66, S3→tramp_backspace→nc_backspace 경로), 세 native 조작 직전·직후마다 live slot0 `E2A8`·slot1 `0000`·len 1·tail `0100ff00`·`+74..+7F` 0을 `ㄱ state before/after …` 체크로 남겼다. 각 조작은 소리 68과 live·len·tail 불변을 함께 요구한다. `expectations.json`의 케이스 13 문구는 바꾸지 않았다.
- 결과: `runs/case13/result.json` PASS, 15개 체크 전부 ok. 세 조작 모두 소리 `68`, 직전·직후 `e2a8…`/len 1/`0100ff00…`, 불변.
- 옛 실행 원문은 `runs-superseded/case13-1792750756/`(자동 이동)에, 옛 `cases.py`·`summary.json`·`case15-contracts.json`·`evidence-manifest.json`·이 보고서의 정정 전 사본은 `../t7-fix1/pre-fix/`에 SHA 그대로 남겼다. 다른 14개 케이스는 다시 실행하지 않았다.

## T6에 넘길 최소 증거

`evidence-manifest.json`: 경로, sha256, 바이트 수. 스크립트, 기대값, summary, 계약 JSON, route, 하네스 diff·빌드 기록, 대표 PNG·bin·로그가 들어 있다. ROM과 카트리지 세이브는 제외했고, 세이브 SHA는 이 보고서와 `runs/*/result.json`에 있다. 최종 집계는 `summary.json`이다.

RECEIPT: model=claude-opus-5-5 effort=high role=code
