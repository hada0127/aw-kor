# Failure Log — 시도했으나 실패한 방법과 사유

> 같은 벽에 다시 부딪히지 않기 위한 기록. 작동한 방법은 [success.md](success.md) 참조.

---

## [2026-06-28] E12 A2 `state_036` RIGHT 반복 all-CO route 실패

- **시도**: `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0`에서 `RIGHT`를 0..17회 누른 뒤
  `DOWN,DOWN`/`DOWN,DOWN,DOWN`으로 파워명 2행을 읽으면 A2 18 CO x 2 power = 36개를 순회할 것으로
  가정하고 read-watch/contact probe를 실행했다.
- **결과**: probe 자체는 current SHA `f95a8573...`에서 direct read 1836건을 만들었지만,
  unique target은 `0x00A295AC/0x00A295C0/0x00A295D8/0x00A295EC` 4개뿐이었다.
  contact sheet도 도미노/맥스 두 프로필만 반복해 보여 `RIGHT` 반복이 전 CO 순회 입력이 아님을 확인했다.
- **판정**: 이 산출물은 all-CO proof로 쓰지 않는다. 영구 evidence는 대표 4케이스만 slim 처리해
  `data/compact_display_read_watch_a2_profile_domino_max_current.json`에 넣고, matrix에는 A2 4/36으로만 반영했다.
  전체 반복 산출물은 `temp/e12_a2_profile_all_co_probe_20260628/`에 남긴다.
- **후속 기준**: 나머지 A2 32개는 전역 CO 도감/선택 화면, 다른 캠페인 CO profile state,
  target mutation diff, direct read-watch, 또는 WRAM/VRAM/DMA chain 중 새 differentiator가 있는 route에서만 재시도한다.

---

## [2026-06-28] E12 B84 all-COID proof 후속 리뷰 timeout 및 invalid-id boundary

- **시도**: B84 AW1 CO 파워명 11/11 read-watch + visual contact 증거를
  `temp/review_prompt_b84_all_coid_20260628.md`로 codex/agy/claude에 엄격 리뷰 요청했다.
- **리뷰 결과**: agy는 제한적 승인 가능하다고 보되, RAM-field near-fresh proof를 natural route 전수 증명으로
  과장하지 말 것과 `0x0201ADBD` invalid CO id bounds를 보강하라고 지적했다.
  codex는 180초 timeout(rc 124)이지만 중간 로그에 동일하게 “산식 근거는 충분, bounds 보강 필요” 취지의
  부분 리뷰가 남았다. claude는 180초 timeout(rc 124), 출력 0바이트였다.
- **bounds 보강**: `temp/b84_power_coid_bounds_probe_20260628`에서 `0x0201ADBD=0x0B/0x0C/0x10/0xFF`를
  짧게 probe했다. `0x0B`는 `0x08B1C194`의 명시 alias에 따라 `메테오` slot으로 읽혔고,
  `0x0C/0x10/0xFF`는 해당 activation window에서 B84 pointer/body hit 0이었다.
- **판정**: B84 positive proof는 valid selector 값 `0x00..0x0A` 11건으로만 카운트한다.
  invalid-id 동작은 target proof가 아니라 boundary note로 `docs/screenshots/b84_aw1_power_title_all_coid_2026-06-28/bounds_probe_summary.json`
  및 `data/compact_display_read_watch_b84_power_titles_coid_current.json`에 연결했다.

## [2026-06-28] E12 A2 profile nav 증거 보강 후 codex/claude 리뷰 timeout

- **시도**: A2 CO profile read-watch 증거를 1/36 -> 3/36으로 보강한 뒤
  `temp/review_prompt_e12_a2_nav_20260628.md`로 codex/agy/claude 엄격 리뷰를 병렬 요청했다.
  agy는 실질 리뷰를 반환했고, hit/direct read 총합 280에는 다단계 route의 이전 redraw read
  (`0xA295AC`)가 누적 포함된다는 caveat를 보고서에 넣으라는 지적을 반영했다.
- **timeout**: codex는 180초 timeout(rc 124)으로 stdout 0바이트, stderr에는 대형 diff 출력만 남았다.
  더 좁은 `temp/review_prompt_e12_a2_nav_codex_retry_20260628.md`로 120초 재시도했지만 다시 timeout(rc 124)됐다.
  claude도 180초 timeout(rc 124)으로 stdout/stderr 0바이트였다.
  agy 최종 재확인도 120초 timeout(rc 124)으로 "이전 find 명령 대기" 문구 외 리뷰 본문이 없었다.
- **후속**: 반영 가능한 실질 리뷰는 첫 agy 결과뿐이었다. `tools/build_compact_display_visual_matrix.py`와
  report에 event-count caveat를 추가했고, `py_compile`, `git diff --check`, `verify_dist_integrity.py` PASS 후 진행한다.

## [2026-06-28] Part1 작전실 제목 가독성 후속 claude/agy 리뷰 CLI timeout

- **시도**: 사용자 추가 스크린샷 후속 수정 범위(Part1 B8 compact title 32개 가독성 개선,
  `prove_compact_display_mutation.py` encode_fit 전환, E12/current SHA evidence/dist 재동기화)를
  claude CLI와 agy CLI에 한국어 엄격 리뷰로 병렬 요청했다.
- **명령**: `gtimeout 240 claude -p ...`, `gtimeout 240 agy -p ...`.
- **결과**: 두 CLI 모두 240초 안에 리뷰 본문을 반환하지 못했다. claude는 출력 없이 rc 124,
  agy는 `Error: timed out waiting for response` 후 rc 124.
- **후속**: 차단 이슈로 채택할 리뷰 결과가 없어 자체 QA 기준으로 진행했다.
  같은 변경 상태에서 `verify_dist_integrity.py`, `run_release_qa.py`,
  `run_release_qa.py --editor --cdp --timeout 300`은 PASS.

## [2026-06-28] E16 Part1 compact 도움말 top-mode BFS read-watch 390노드 음성

- **시도**: fresh Part1 mode menu에서 시작해 `A/B/UP/DOWN/LEFT/RIGHT/L/R/SELECT/START` BFS를 깊이 8,
  최대 650노드로 돌리되, 남은 help group(code0, code5/6, code16..19)의 ROM read만 watch했다.
- **결과**: 390개 frame까지 진행했지만 `watch.log`는 0바이트였다. title/Part2 선택 흐름을 포함해 화면은 많이
  확장됐지만 남은 Part1 compact help source는 전혀 읽히지 않았다.
- **판정**: 입력 brute-force로는 unlock/player-count 분기 조건을 만들지 못한다. 이후 같은 top-level BFS를
  반복하지 말고, `0x02000030` item-code writer RE 또는 real unlock/player-count state 확보로 전환한다.

## [2026-06-28] E16 campaign hidden 후보 단순 branch 반복 음성

- **시도**: AW1 external complete/hard save state(`2111_front`, `11186_front`, `8495_front`)에서 campaign submenu
  진입(`UP,A`) 후 `LEFT/RIGHT/L/R/UP/DOWN/SELECT/START/A` 변형을 read-watch했다.
- **결과**: 완료된 24개 branch에서 `0xDFA7E2/7FD/80E/829` normal campaign 도움말만 반복적으로 읽혔고,
  hidden campaign 후보 `0xDFA83A/84D/872/885` read는 0건이었다. 나머지 긴 batch는 같은 패턴이라 중단했다.
- **판정**: 해당 외부 save가 실제 GBWA1+2 hidden campaign flag를 세우지 못했거나, hidden campaign은 다른
  mode/state bit를 요구한다. 같은 `UP,A` submenu branch 반복은 중단하고 menu code writer 분기 조건을 RE한다.

## [2026-06-28] E16 title/Part2 화면의 RAM code0 후보는 stale/uninitialized 오탐

- **시도**: Part1 menu object 후보 RAM을 BFS로 훑으면서 active code에 잔여 code가 보이는 state를 찾았다.
- **결과**: 24건의 code0 후보가 나왔지만 공통 route는 `B B DOWN A/START` 계열이고, 화면은 Nintendo Presents/
  title/Game Boy Wars Advance 2 선택 흐름이었다. `0x02000030` 부근 active 값은 `[0,0]`처럼 보였지만
  Part1 compact help 화면이 아니며 target help read도 없었다.
- **판정**: title/Part2 상태에서 남은 `0` 값은 menu object가 아니라 stale/uninitialized RAM 오탐이다.
  direct visual evidence로 승격 금지.

---

## [2026-06-26] D4 battle dialogue preview canvas 후보 실패(최종 표시 state 금지)

- `31_battle_dialog`은 실제 전투 대사 화면이 아니다. 현재 캡처는 전투/정보 UI 화면이고 provenance도 구 SHA stale라
  battle dialogue canvas 근거로 쓰면 false green이 된다.
- `89a_common_battle_surrender_confirm`/`89b_common_battle_defeat_comm_messages` 최종 표시 savestate는 화면 자체는
  맞지만, ROM slot payload를 바꿔도 캡처 diff가 0이다. 이미 렌더된 VRAM 상태라 `preview_capture` canvas로
  승격하면 안 된다.
- `89b`의 `0xA34D18` ROM 패치는 loadstate 뒤 bus dump에는 정상 반영된다. 실패 원인은 ROM 패치가 아니라
  대사 생성 직전 state/nav 선택이었다. `state_011_confirm_yes.ss0`처럼 이미 확인 입력 뒤의 상태는
  저장된 중간 패배 메시지로 재진입하지 못해 payload diff가 0이다.
- 후속 해결: `89a` 항복 확인은 최종 표시 state가 아니라
  `part2_3p_surrender_defeat_probe_v4/state_008_sub_down_to_surrender.ss0`에서 A 입력으로 대사창을 재생성하고,
  실제 Part2 복제본 `0xA34CB0`을 패치해야 payload diff가 발생한다. 자세한 성공 근거는
  `docs/success.md`의 `D4 battle_surrender_confirm canvas 승격` 항목을 따른다.
- 후속 해결: `89b` 패배 메시지는
  `part2_3p_surrender_defeat_probe_v4/state_010_confirm_left_yes.ss0`에서 A 입력으로 대사창을 재생성하고,
  실제 Part2 복제본 `0xA34D18`을 패치해야 payload diff가 발생한다. 자세한 성공 근거는
  `docs/success.md`의 `D4 battle_defeat_message canvas 승격` 항목을 따른다.

## [2026-06-07] Part 1 정보창 savestate 기반 재캡처는 라벨 패치 검증에 부적합

- **시도**: `fresh_battle_after_wait_select.ss0` 및 `temp/fresh_part1_info_route_base_20260607/a140.ss0`
  기반으로 `B -> R` 재캡처를 수행해 `WEAPON`/`SPEC` 제거를 확인하려 했다.
- **결과**: ROM raw/LZ77 payload가 패치된 뒤에도 일부 저장상태는 이전 `WEAPON`/`SPEC` OBJ/BG tile을
  VRAM에 이미 캐시한 채라, 새 ROM 로드만으로 화면이 갱신되지 않았다.
- **결론**: 정보창 그래픽 라벨 검증은 콜드부트 실제 입력 라우트 또는 ROM LZ77 해제 payload 비교로 해야 한다.
  stale savestate 화면만 근거로 패치 실패를 판단하지 않는다.

## 카테고리 A — 매핑 도출 (글리프↔SJIS↔슬롯 자동 추출)

### A1. SJIS / 고주온 / JIS 마스터 테이블 ROM 검색
- **시도**: ROM에서 `アイウエオ…` SJIS 시퀀스 또는 JIS 카타카나 시퀀스를 직접 검색해 폰트 인덱스 테이블 발견 시도.
- **결과**: `0x80505C`에 카타카나 그리드 표(83자)는 있음 — 이름 입력 그리드용. 마스터 SJIS→슬롯 매핑 테이블은 ROM에 없음.
- **사유**: SJIS→glyph 변환이 데이터 테이블이 아니라 **렌더러 내부 로직**.

### A2. 선형 공식 (JIS/SJIS 인덱스 → 슬롯)
- **시도**: `slot = (Hi - off1) * 0x5E + (Lo - off2)` 등 선형 변환을 알려진 매핑(ア=42, カ=47)에 fit.
- **결과**: 비선형 — 폰트가 커스텀 순서. 한자는 빈도/첫등장과도 무상관(三 freq=0, slot=559).

### A3. 8x8 글리프 템플릿 매칭
- **시도**: VRAM 글리프 ↔ ROM 폰트 콘텐츠로 직접 매칭(VRAM tile 32B == ROM tile 32B 검색).
- **결과**: 매칭률 0/1024.
- **사유**: 폰트 복사 루틴(0x03006758)이 **팔레트 리맵 변환**(값>임계 시 오프셋 가산)을 적용 — VRAM 콘텐츠가 ROM과 다름.

### A4. VRAM 타일맵 차분 패턴 검색
- **시도**: 대화 윗줄 셀의 알려진 tile_index 차분([54, -161, 1] 등)을 VRAM 타일맵에서 검색.
- **결과**: 매칭 0건.
- **사유**: 대화 렌더가 표준 BG 타일맵이 아닌 특수 구조(4타일/y123-133 클리핑).

### A5. 마커 글리프 + VRAM 매칭
- **시도**: ROM 폰트 슬롯에 식별 가능한 마커를 삽입하고 VRAM에서 그 마커가 어디 나타나는지 찾아 slot→VRAM 위치 역추적.
- **결과**: 게임의 글리프 복사 변형(팔레트 리맵)으로 마커가 변형돼 매칭 실패.

### A6. 폰트 base 리터럴 ROM 검색
- **시도**: GBA 주소 `0x08B98000` 또는 `0x08B90000`를 가리키는 4정렬 포인터를 ROM에서 검색해 코드 앵커 확보.
- **결과**: 0건 (런타임 계산되거나 register-relative).
- **사유**: 베이스가 PC-relative LDR 또는 계산식. 정적 디스어셈블 시작점 없음.

### A7. RSP (GDB Remote Serial Protocol) 워치포인트
- **시도**: mGBA의 GDB 서버(`-g`)를 켜고 커스텀 Python RSP 클라이언트로 폰트 영역에 워치포인트 설정.
- **결과**: 워치포인트는 발화하나 RSP 동기화 불안정(빈 stop 패킷). PC가 KEYINPUT 폴링 루프(0x8B392xx)에 잡힘.
- **사유**: RSP는 VRAM write를 지원하지 않고 stub 동기가 깨짐. → 자체 하니스로 전환해 해결.

### A8. 카타카나 블록 단일 슬롯 probe (0-300, 절대 임계)
- **시도**: 슬롯 32-260을 하나씩 `0xAA` 채우고 어느 대화 셀이 변하는지 확인 (>40 dark pixels 임계).
- **결과**: 16셀 중 7셀만 매핑됨(다쿠텐 합성 슬롯 절반 누락).
- **사유**: 임계값이 합성 절반(~32px)을 놓침. → delta-detection으로 일부 개선.

### A9. delta-detection 종합 probe (0-1100)
- **시도**: A8을 baseline 대비 +18 delta로 개선.
- **결과**: 일부 셀(13/16)이 매핑됐으나 cell1·5처럼 dedup으로 같은 슬롯 공유 발견. 절대 임계보다 나아짐.

### A10. ROM 슬롯 단일 fill probe (welcome 텍스트 유지)
- **시도**: text=`アイウエオカキク`에서 slot 42, 39 등을 단독 채워 어느 셀이 바뀌는지 확인.
- **결과**: text='アイウ…' 컨텍스트에서 slot 42→cell0, slot 39→무변경.
- **모순**: 같은 ア×16 baseline-diff에서는 slot 39가 ア 슬롯. 즉 같은 문자가 컨텍스트별 다른 슬롯.

### A11. 같은 문자 다른 위치 fill 검증
- **시도**: text=`アカアサアタアナ`에서 같은 ア가 위치별로 같은 슬롯인지(문자고정) 다른지 확인.
- **결과**: cell0 ア → slot 49, cell2 ア → slot 54, cell4 ア → slot 39 — **동일 문자가 위치마다 다른 슬롯**.
- **결론**: 슬롯 할당이 **문자고정이 아니라 위치기반 동적**.

### A12. 슬롯 42 마커 cross-screen 테스트
- **시도**: ROM 폰트 슬롯 42에 마커를 넣고 welcome → 다음 대화로 진행하며 마커가 일관된 문자 위치에 나타나는지 확인.
- **결과**: welcome cell0(ア)에만 마커 출현, 다음 대화 어느 셀에도 출현 안 함. cross-screen 문자고정 매핑 부재.

### A13. distinct 히라가나 probe (slot 0-600)
- **시도**: 16개 distinct 히라가나(`あいう…`)로 텍스트 재작성 후 slot 0-600 fill-probe.
- **결과**: 매핑 0건.
- **사유**: 히라가나 폰트가 그 슬롯 범위 밖. 폰트가 텍스트가 사용하는 글리프만 로드.

### A14. 빈도/첫등장 순서 가설
- **시도**: 슬롯 순서 = 일본어 텍스트 빈도순 또는 ROM 첫등장순.
- **결과**: 무상관. ア=42(freqrank=84), 三=559(freq=0). 둘 다 fit 안 됨.

---

## 카테고리 B — 정적 디스어셈블 RE

### B1. SJIS 글리프 핸들러 디스어셈블 (0x08B1215A)
- **시도**: 파서가 SJIS(0x83~) 분기하는 0x08B1215A를 capstone으로 디스어셈블해 슬롯 계산 로직 추출.
- **결과**: 또 다른 nested jump table(첫바이트 cmp 0x77, lsls #2, ldr [tbl]). 다단계 상태기계, 슬롯 계산 식 직접 보이지 않음.
- **사유**: 텍스트 파서는 측정/검증 패스 — 실제 슬롯 계산은 IWRAM 렌더 파이프라인의 다른 함수에 있음.

### B2. IWRAM 폰트 복사 루틴 디스어셈블 (0x03006754~0x030067C4)
- **시도**: IWRAM 덤프 + capstone Thumb 디스어셈블.
- **결과**: 루틴은 `glyph_index = ldrh [table + idx]` (런타임 테이블 lookup) → `r7 = font_base + glyph_index*32`, 픽셀별 팔레트 리맵 후 VRAM 기록 — 구조는 명확.
- **장벽**: glyph_index 생성 코드(테이블 채우는 부분)는 별도 함수, 그 시작점 식별 못함.

### B3. 0x8b7bd18 디스어셈블 (압축해제 디스패처)
- **시도**: 텍스트 렌더러가 `bl 0x8b7bd18`로 호출하는 함수 분석.
- **결과**: `bx r2`~`bx lr` 12개 트램폴린 + 큰 정수 나누기 루틴. char→소스 계산은 여기 없음.

### B4. 디스패치 테이블 0x08D8263C 분석
- **시도**: 텍스트 렌더러(0x08B0FFF0)가 인덱싱하는 디스패치 테이블 8 엔트리.
- **결과**: 핸들러 8개가 모두 `0x08B7A87x` 영역의 BIOS SWI thunk(svc #0x11, svc #0x12 등 — LZ77/Huff/RLE 압축해제).
- **함의**: 글리프가 다양한 BIOS 압축 포맷으로 저장돼 있을 가능성.

---

## 카테고리 C — 동적 RE (디버거)

### C1. mGBA 실행 브레이크포인트 첫 시도
- **시도**: 하니스에 `setBreakpoint` 추가하고 0x03006758에 BP 설정.
- **결과**: 0건 발화.
- **사유**: `core->runFrame()` 직접 호출이 브레이크포인트 체크를 우회. → `mDebuggerRunFrame(&dbg)`로 수정 후 작동 (이 fix는 success.md 참조).

### C2. 워치포인트로 char→slot 직접 매핑 시도 (watchfont)
- **시도**: 폰트 영역 전체에 read 워치포인트(슬롯 시작마다)로 렌더 중 읽힌 슬롯 순서 캡처.
- **결과**: 캡처는 됨(185 고유 슬롯). 노이즈 큼 — UI글리프·대화글리프·타이프라이터가 같은 루틴 공유, r7만 다름. char→slot 분리 안 됨.

### C3. baseline-diff 슬롯 격리
- **시도**: text=`ア×16` vs `カ×16` 워치포인트 카운트 비교로 ア/カ 슬롯 격리.
- **결과**: ア→{39, 55}, カ→{44, 60} 깨끗하게 격리. ㅏ는 카타카나 영역에서 고주온 +5 차이.
- **모순**: 그런데 같은 ア가 text=`アイウ`에선 slot 42, text=`カア`에선 또 다른 슬롯. **같은 측정이 컨텍스트별로 다른 답을 줌**.
- **사유**: 텍스트 내용에 따라 동적 할당.

### C4. (r6, r7) 페어 캡처 — VRAM-dest ↔ ROM-source 상관
- **시도**: 복사 루틴 BP에서 (r6, r7)을 모두 캡처해 셀 위치 ↔ 글리프 소스 상관.
- **결과**: r6 셀 ↔ r7 소스가 **순서 무관(content-based)**으로 일관. text=`アイウ…` ↔ `カアエ…`에서 cell0→0x8b974d0 동일.
- **함정**: 알고 보니 이건 **상수 UI 레이아웃**(박스/초상화) 복사. 텍스트가 아님.

### C5. r7 ≥ 0xB98000 필터링 (대화영역)
- **시도**: C4에서 r7이 폰트 영역인 호출만 필터링.
- **결과**: text1과 text2의 (r6→r7) 매핑이 완전 동일 — **위치고정**.
- **사유**: 이 PC(0x03006744)도 상수 레이아웃. 대화 텍스트가 아니라 박스 장식 글리프.

### C6. ROM 0xB98540 (슬롯 42) read 워치포인트
- **시도**: 슬롯 42 ROM을 읽는 모든 PC 캡처해 대화 텍스트 렌더러 식별.
- **결과**: 0건 발화.
- **사유**: 대화는 슬롯 42를 직접 안 읽음. (fill-probe "42→cell0"는 부정확/spurious 상관.)

### C7. VRAM diff로 대화 텍스트 위치 식별
- **시도**: 타이프라이터 진행 중 두 시점에 VRAM 덤프 → diff로 텍스트 타일 위치 식별.
- **결과**: ✅ 대화 텍스트 VRAM = **0x06003940-0x06003b00**. (success.md에 기록)

### C8. VRAM 0x06003900+ write 워치포인트로 텍스트 렌더러 식별
- **시도**: 대화 텍스트 VRAM에 write 워치포인트.
- **결과**: ✅ PC `0x08B7A878` (BIOS SWI 0x11 thunk = LZ77 압축해제). 호출자 LR=`0x08B10020`, 렌더러=`0x08B0FFF0`. (success.md)

### C9. LZ77 압축 블록 편집 검증
- **시도**: 0x08B0FFF0 BP에서 r0(LZ77 소스)을 캡처 → 0xBB7A64 블록 디코딩(899→1152, 36타일) → 한 타일 교체 → 재압축 → 재삽입 → 대화 변경 확인.
- **결과**: 재압축은 roundtrip 정확(검증됨). 그러나 **블록 0xBB7A64 편집이 표시 대화를 안 바꿈**.
- **사유 (추정)**: 다층 시스템. 블록이 VRAM 0x06003780에 해제되지만, 타이프라이터가 표시하는 0x06003940은 별도 경로로 채워짐 — 동일 PC가 다른 호출 컨텍스트에서 다른 의미. 캡처가 spurious 상관일 가능성.

### C10. 슬롯 fill broad test (cross-screen)
- **시도**: 슬롯 0-900을 전부 `0xAA`로 채우고 welcome과 다음 대화에서 각각 마커가 어디 나타나는지.
- **결과**: 다음 대화의 한자(名前·。)가 블록으로 변함. 히라가나·일부는 유지.
- **모호함**: 다른 문자 사용으로 어차피 다른 슬롯이라 cross-screen 문자고정 확정에는 불충분.

---

## 카테고리 D — empirical 매핑 시도

### D1. 비트인코딩 probe (binary search)
- **시도**: 11 비트런(bit-encoded fill)으로 슬롯 인덱스를 binary-coded 추출.
- **결과**: 셀의 ~95%가 비트 0에서 cluster되며 이웃 슬롯 blead로 부정확. 합성 슬롯 환경에서 작동 안 함.

### D2. distinct katakana + 순차 슬롯 가정
- **시도**: text=`アイウエオカキクケコサシスセソタ` distinct 카타카나 → 슬롯 = 42+K (확정), 한글을 그 슬롯에 채움.
- **결과**: ✅ **welcome에서 작동** (success.md). 단 이는 이 화면의 동적 할당이 우연히 이 base를 사용한 결과 — 전역 char-fixed 매핑이 아님.

### D3. 슬롯 0-1200 종합 probe (delta) on distinct hiragana
- **시도**: distinct 히라가나(`あいう…`)로 텍스트 재작성 후 0-600 fill-probe.
- **결과**: 매핑 0건. 히라가나가 그 범위 밖.

---

## 카테고리 E — 외부 도구·환경

### E1. arm-none-eabi-gdb 설치 시도
- **시도**: `which arm-none-eabi-gdb` 등.
- **결과**: 미설치. brew에도 즉시 가용 패키지 없음.
- **해결**: 자체 하니스에 `break` + 레지스터 캡처 구현으로 대체 (성공).

### E2. mGBA Lua 스크립팅으로 자동 진행
- **시도**: AppleScript/keystroke로 게임 입력 자동화.
- **결과**: 합성 키 입력이 mGBA 게임에 전달 안 됨.
- **해결**: 자체 하니스의 `keys MASK` 명령(setKeys API 직접 호출)으로 대체.

### E3. VBA-M으로 검증
- **시도**: 사용자 제공 VBA-M으로 스크린샷 캡처.
- **결과**: GPU 캔버스가 macOS screencapture로 잡히지 않음.
- **해결**: brew mgba 0.10.5 + 자체 하니스 shot 명령으로 대체.

---

## 종합 결론

**근본 장벽**: Game Wars의 텍스트 렌더링은 다층 동적 시스템 — (1) SJIS 파서 → (2) 글리프 인덱스 동적 할당 → (3) LZ77 압축 블록에서 BIOS 압축해제 → (4) VRAM 타이프라이터 쓰기. 상수 UI 레이아웃과 텍스트 글리프가 같은 복사 루틴을 공유해 디버거 캡처가 문맥별로 어긋남.

**현재 환경의 한계**: 자체 디버거(BP+워치포인트+레지스터)가 작동하고 LZ77 코덱도 검증됐지만, **char→실제 표시 글리프 소스의 결정적 매핑**이 검증마다 무너짐. 식별한 모든 편집 후보(슬롯 0xB98000, 블록 0xBB7A64)가 표시 텍스트와 무관으로 판명됨.

**전체 한글화의 진짜 다음 단계**: Ghidra 등 외부 정적 분석 도구로 텍스트 렌더 파이프라인을 명령어 단위 완전 RE 또는 Gemini 권장의 베이스포인터 리포인트(폰트 베이스 주소 LDR 명령 patch). 이 자율 CLI 환경에서 empirical/동적 방법은 소진됨.

---

## 2026-05-23 추가 실패 시도

### F1. 풀폭 SJIS ASCII (Ａ-Ｚ 0x8260-0x8279) 직접 사용
- **시도**: 이름 입력 grid 텍스트 바이트를 풀폭 영문(SJIS Ａ-Ｚ)으로 교체
- **결과**: 숫자 0-9는 정상 표시, **영문 글리프는 게임 폰트에 없어서 빈 자리만 표시**
- **결론**: 풀폭 SJIS ASCII 글리프 없음. 카타카나 폰트 슬롯에 직접 영문 글리프 주입해야 함

### F2. ASCII half-width 문자 (0x41-0x5A) 직접 입력
- **시도**: dialog text 바이트로 ASCII letter 'A' (0x41) 직접 쓰기
- **결과**: 게임 즉시 흰 화면 크래시
- **결론**: 게임 SJIS 파서가 single-byte ASCII를 받아들이지 않음. 반드시 SJIS 2-byte 형식 필요.

### F3. 8x4 영문 글리프 (스파스 4-row)
- **시도**: 슬롯 stride 0x10이라 글리프를 8x4 (= 16 bytes) 로 만들어 overlap 회피
- **결과**: 글리프가 너무 sparse하여 가독성 낮음 — 알아보기 어려운 형태
- **결론**: 4-row 가로 글리프는 비실용적. 슬롯 overlap 다른 방식으로 해결 필요 (예: stride 0x20 만 사용 = 메이저 katakana 슬롯만 사용)

### F4. 100 dialog 다중 dispatch (v6)
- **시도**: 100개 dialog 자동 빌드 (build_multi_dialog_v2.py)
- **결과**: Game intro/title 화면에 영향 미쳐 navigation 중단
- **결론**: 100개 중 일부 dialog 주소가 system/menu 화면과 겹침. dialog 필터링 + binary search dispatch 필요.

### F5. v14_tight 폰트 슬롯 패치 의존
- **시도**: 처음 welcome 한글화에 v14_tight (font slot 0xB98000+ 한글 주입) 사용
- **결과**: name input grid에 한글 잔재 노출 (katakana 슬롯과 동일 주소 공유)
- **결론**: 글로벌 폰트 슬롯 패치는 다른 화면에 부작용. v27에서 원본 ROM + hook B만으로 재구성하여 해결.

### F6. 캐서린 dialog (0xDF8E54) flag=4 시도 (v54, 2026-05-23)
- **시도**: hook A를 4-way로 재작성 (welcome/name_prompt/hajimemashite/watashi) + hook B에 flag=4 핸들러 추가. addr4 = 0xDF8E54 (double 0a 09 prefix) + 0xDF8E56 (단일 0a 09) 두 가지 시도.
- **결과**: 두 주소 모두 flag=4 미발화. 다음 화면이 캐서린 dialog 표시 안 함.
- **분석**:
  1. 0xDF8E54-0xDF8E57의 "0a 09 0a 09" double prefix는 **이전 hajimemashite block (0xDF8E3C) 내부의 line continuation**일 가능성 (= "줄바꿈 + 새 줄"). hajimemashite block이 line 1 "はじめまして..." + line 2 "私はキャサリン..."를 모두 포함.
  2. 게임 dialog parser가 0xDF8E54/0xDF8E56을 **별도 block 시작이 아닌 같은 block 내부 줄 전환**으로 처리 → hook A의 `[r6+0x20]` 비교 안 됨.
  3. hook B 가 hajimemashite block 시작에서 한 번 fire하지만 line 2 전환 시 다시 fire되지 않음 — overlay가 line 1만 덮음.
- **해결책 (미구현)**: hook B를 multi-line block 인식하도록 확장 (line 전환 시 별도 overlay) 또는 line 2 영역 cells도 한 번에 overlay (단일 hook B 발화에서 line 1+2 모두 덮기, 22+22 cells).
- **결론**: v53 (hajimemashite 단일 line 한글 overlay) 이 현재 아키텍처의 최대 도달점. 캐서린 dialog 한글화는 hook B 멀티라인 지원이 필요한 별도 과제.

### F7. watchaddr 기반 dialog addr 탐색 (v53 검증, 2026-05-23)
- **시도**: harness watchaddr로 hook A의 flag write (0x0203FFF0)를 감시 → 게임 진행 중 7회 발화 캡처.
- **결과**: 시퀀스 = flag=1 (welcome), flag=2 (name prompt), **flag=0 (미매핑 dialog)**, flag=3 (hajimemashite OK), flag=0 (미매핑), flag=0 (미매핑).
- **분석**:
  1. hook A가 dialog마다 fires (게임은 정상 progression).
  2. hajimemashite 후 추가 2개 dialog가 flag=0으로 처리 → 정의된 addr1/2/3 와 다른 주소.
  3. 캐서린 dialog는 별도 block (multi-line이 아님!) 으로 보이나 addr이 우리 추측과 다름.
  4. 정확한 addr를 알려면 hook A 진입점에서 r0 (= [r6+0x20]) 캡처가 필요. BP가 발화 안 함 (mGBA-libmgba hardware BP 이슈로 추정).
- **해결책 (미구현)**: hook A를 디버그 로그 출력하도록 확장 (r0를 EWRAM ring buffer에 기록) → 게임 진행 후 buffer 덤프하여 actual addr 캡처.
- **결론**: v53 == 사용자 목표 만족 (이름 입력 → 다음 화면 "처음 뵙겠습니다" 한글). 추가 dialogs는 디버그 인프라 강화 (BP 작동 fix or 로그 inject) 후 진행 가능.

---

## [2026-05-25] EUC-KR 텍스트 삽입으로는 본문 대화 한글 렌더 불가 (재시도 금지)

`execute_phase5_4.py`의 EUC-KR 인코딩 삽입은 ROM을 **부팅**시키지만 대화에서 **한글로 렌더되지 않는다.**
인코딩만 SJIS-슬롯으로 바꿔도 마찬가지(아래 이유) — 단순 인코딩 교체는 의미 없으니 하지 말 것.

### 이유 (RE로 확정)
1. 게임 대화 폰트는 Shift-JIS **타일** 기반. EUC-KR 바이트(0xB0–0xC8 리드)는 SJIS 해석상 반각 가나/단일
   바이트로 깨져 보인다.
2. 흔한 대화 한자(攻 0x8D55, 撃 0x8C82)가 SJIS→슬롯 테이블(0xBE717A)에 **없다** → SJIS 코드를 써도
   슬롯 매핑이 안 됨.
3. 대화 글리프는 **LZ77 압축 → VRAM 해제** 경로(success.md: 0xBB7A64 등). FONT_BASE에 raw 타일을 직접
   주입해도 대화에는 안 반영(그리드/메뉴 폰트만 비압축 직접주입 가능).

### 결론 / 올바른 길
- 본문 대화 한글화는 `build_grid_v*.py`의 **ARM hook**(특정 대화 주소 → 0xA3E000 커스텀 글리프) 방식만
  작동하며 현재 **per-screen**(welcome/이름입력/hajimemashite). 
- **풀게임 = 이 hook의 일반화**(임의 대화에 대해 한글 글리프 공급 + 타이프라이터/LZ77 처리)가 남은 핵심 RE 과제.
  EUC-KR/SJIS 인코딩만 만지는 접근은 막다른 길.

> ⚠️ **[2026-05-25 정정]** 위 "LZ77→ARM hook만 작동, SJIS 인코딩은 막다른 길" 결론은 **틀렸음**.
> 대화 글리프는 LZ77이 아니라 **비압축 FONT_BASE per-char 복사**였고(research.md 2026-05-25),
> **예약 SJIS코드+한자테이블 확장+글리프주입+FONT_BASE repoint(데이터-only, ARM hook 불요)** 로
> 풀게임 한글 렌더가 작동함(success.md SESSION 2/3 인게임 검증). 단 **EUC-KR**은 여전히 막다른 길
> (게임이 EUC-KR 디코더 없음 — SJIS 예약코드라야 렌더됨).

## [2026-05-26] 영문 이름 그리드 ✗ FONT_BASE repoint와 아키텍처 충돌 (ASM hook 필요)

> ✅ **[2026-05-26 해결]** ASM hook 구현 완료. 원본 FONT_BASE 보존(그리드+대화), 예약 한글코드만
> 별도 KOR_BASE(0x08F00000) 사용. TOP/BOT 글리프소스 2곳 트램폴린(bx, ARMv4T BLX 미지원), bit15 마커.
> 대화 한글 + 영문 그리드 인게임 양립 확인. success.md(2026-05-26) 참조.

- v56_polished는 영문 그리드(ABCDE FGHIJ KLMNO PQRST) 정상 — 훅(0xB12798→0xA3D000, 0xB129D4→0xA3CF14)
  +FONT_BASE 슬롯에 영문 글리프 주입. **그리드는 변환루틴 FONT_BASE 리터럴(0xEFE97C)을 통해 글리프 fetch.**
- 내 풀게임 대화 방식은 **0xEFE97C를 0x08F00000으로 repoint**(원본폰트 복사+한글). → 그리드도 0x08F00000을
  읽어 **영문 글리프 무시·원본 가나 표시**. v56_polished를 base로 써도 동일(repoint가 덮어씀).
- v56_polished 폰트를 0xF00000에 복사하면? v56가 슬롯 0-1023 블랭크 → 대화 가나가 빈/영문 → 대화 깨짐.
- 결론: **repoint 방식과 v56 그리드는 글리프 슬롯을 공유해 양립 불가.** 둘 다 가지려면 codex/gemini가
  처음 추천한 **ASM hook**(예약 한글코드만 별도 KOR_BASE=0x08F00000 사용, 원본 FONT_BASE는 그리드/대화 보존)
  으로 대화 렌더를 재작업해야 함. 예약코드→idx 마커(예 idx≥0x8000)→hook에서 KOR_BASE 분기.
- 현재 동작 상태: 원본 base = 기능적 가나 그리드 + 풀 대화 한글(repoint) + #1/#4 수정. 영문 그리드는 미적용.

## [2026-05-25] SESSION 3 잔여 위험 (막다른 길 아님, 다음 세션 처리 — codex 리뷰)
풀게임 인코딩 빌드는 작동하나, 다음은 "슬롯에 들어감"과 별개로 깨질 수 있어 QA 필요:
- **슬롯-fit ≠ 제어코드 의미보존**: 슬롯 이내로 써도 문자열 내부 제어코드(페이지넘김/선택지분기/변수삽입/
  색상/종료) 의미가 틀리면 흐름이 깨짐. 인접손상은 없으나(clear후 ≤슬롯 기록) 의미보존은 미검증.
- **잔존 일본어 분류 미완**: overflow-skip(2,322) 외에 bulk-DMA/고정타일/압축그래픽 경로로 박힌 글자는
  CSV 채워도 일본어 유지. 화면별 렌더경로 매트릭스로 구분 필요.
- **박스폭/줄바꿈 미검증**: 한국어가 길어 박스밖/다음줄침범/선택지겹침 가능. 줄바꿈 기준(byte/glyph/pixel) RE 필요.

- **integrity_map 교집합으로 "미표시" 단정 금지(2026-06-17)**: 노이즈 행 345개가 integrity_map에
  0건이라 "전부 미기록"으로 판단했으나, stale 맵이었고 실제로는 `깨진 문자열` 18행이 그래픽 위에
  기록되어 비트맵 손상 중이었음. 표시/기록 여부는 **그때그때 빌드한 ROM 바이트**로 확인할 것.

## [2026-06-22] Part2 잔여 컨테이너 watch-range 장시간 정체

- **시도**: `temp/story_watchrange.py`로 2편 30a 잔여 범위 `0x00A04C64:0x00A08000`을 watch-range 방식으로 상태 7개×정책 2개부터 확인.
- **결과**: 20분 이상 경과해도 첫 8케이스도 완료되지 않았고 `mgbah` CPU만 지속 사용. 중단 후 잔여 프로세스 없음 확인.
- **결론**: 이 구간의 watch-range 방식은 완료 가능성이 낮고 검증 루프를 막는다. 동일 목적은 `temp/story_range_breakscan.py`의 render-breakpoint 방식으로 대체해야 한다.
- **대체 검증**: 같은 30a 범위를 render-breakpoint로 재실행해 14케이스 `NO_HIT`; 이후 30b/30c/30d-30g/30e/30f도 같은 방식으로 완료.

## [2026-06-23] Part1·0xB8 대사 단어붙음 repoint 미적용 (분산 포인터)

- **상황**: Part2 캠페인 대사는 `0x08A357B4`의 단조 메시지 포인터 테이블(3315엔트리)로 참조돼
  메시지 단위 free-space 재배치(repoint)로 단어붙음 214 라인 해소.
- **막힌 점**: Part1(0xD8~0xE0)·0xB8 영역의 잔여 단어붙음 244건은 동일 기법이 **바로는 안 됨**.
  잔여 240건 중 깨끗한 단조 포인터 테이블로 참조되는 건 1건뿐 — 나머지는 **분산/비단조 포인터**
  (예 0xB81F70←0xD8AB7C, 0xB820D8←0xD8A708, 0xB824F8←0xD89844: 참조 포인터가 흩어져 감소).
- **다시 시도하지 않을 조건**: 단일 0xA357B4식 테이블 스캔으로 Part1을 처리하려는 시도. Part1은
  영역별(미션별?) 포인터 구조를 먼저 RE해야 한다. dialogue_repoint 엔진은 `table_offsets`만 추가하면
  되지만, 그 전에 각 영역의 테이블 위치·단조성·중간참조 여부를 검증해야 안전.
- **참고**: 일부 0xA0xxxx override는 소스 자체가 선-단어붙음(예 0xA01ED0 '기지를공격하라')이라
  repoint해도 완전 해소 안 됨 → 데이터(쪼롱이님 문구) 측 교정 영역(자동 수정 금지).

## [2026-06-23 續] Part1 대사 repoint — struct 테이블 함정 (decompose 불충분)

- **시도**: Part1 대사 영역(0xE0/0xDF 등)의 조밀 포인터 테이블(0xE1075C n=98 등)을 dialogue_repoint
  `table_offsets`에 추가해 단어붙음 해소 시도.
- **막힌 점**: 그 테이블들은 **대사 테이블이 아니라 struct/이벤트 테이블**. 가리키는 '메시지' 시작이
  `00 00 00 00 89 89 b3 08…`(int 필드)라 디코드하면 쓰레기. found_texts 라인이 span에 우연히 들어가
  **decompose 가드는 통과**하지만 실제론 대사가 아님. 강행 시 struct를 free-space로 옮기고 struct
  포인터를 갱신해 **게임 이벤트/데이터 손상**.
- **다시 시도하지 않을 조건**: "조밀 단조 포인터 테이블 = 대사 테이블"이라는 가정. Part1은 struct
  테이블이 대사 영역을 가리키는 경우가 많다. 반드시 **디코드해서 실제 대사인지** 확인하거나, 런타임
  렌더러 포인터 로드를 트레이싱해 진짜 테이블을 찾을 것. 헤더갭>16 가드로 자동 차단은 해 뒀음.

## [2026-06-23 續2] Part1 대사 런타임 트레이싱 — 하네스 디버거 loadstate 후 미발화

- **목표**: Part1 대사 표시 중 렌더러의 메시지 포인터 로드를 watchpoint/breakpoint로 잡아 진짜
  대사 테이블 역추적(static 분리 불가 결론 이후의 정공법).
- **진행**: mgbah(tools/mgba_harness.c)로 first_battle savestate 로드 → Part1 캠페인 대사 화면 확인
  (캐서린 튜토리얼 "점령은…", CO 도감 "기계광 활기찬 소년…"). 텍스트 ptr store `0x8B1299C
  str r4,[r6,#0x20]`, copy chokepoint `0x8B1BF08`, 파서 `0x8B11E48`에 break/watch.
- **막힌 점**: **loadstate 후 watchpoint/breakpoint가 발화하지 않음**. 검증: fresh boot(loadstate 無)에선
  VRAM 쓰기 watchpoint 52히트·IWRAM rw 188히트로 **정상 작동**하나, `loadstate` 직후엔 동일 watchpoint가
  0히트. loadstate 핸들러에서 디버거 재attach(mDebuggerAttach+init) 패치해도 미발화 → mGBA가 loadstate 시
  CPU fast-path 메모리 접근으로 복원해 디버거 슬로우패스(watchpoint 체크)를 우회하는 라이브러리 내부 이슈.
- **static 분석 결과**: store `0x8B1299C`의 r4(텍스트 ptr)는 `[sp,#0x10]`(스택 인자)에서 옴 → 함수
  `0x8B12984`가 텍스트 ptr를 인자로 받음. 콜체인 위로 다단계 추적해야 테이블 로드(`ldr rX,[rBase,...]`)
  도달. 가능하나 레지스터 juggling 多.
- **다시 시도할 때**: ① mgbah를 loadstate 후 watchpoint가 살아나도록 고치거나(mGBA fast-path 무효화 +
  debugger 재설치 — 깊은 작업), ② **fresh-boot 네비**로 Part1 대사 도달 후 watchpoint(이 경로는 작동),
  ③ mGBA **Lua 스크립팅** 메모리 콜백(C 디버거와 별개 경로), ④ static 콜체인 디스어셈블 완주.
  어느 경우든 **실기/플레이테스트로 실제 대사 렌더 확인** 후에만 Part1 repoint 적용(쪼롱이님 캠페인 손상 방지).

- **static 추적 최종 결론**: 텍스트 ptr는 렌더러 함수들(`0x8B12910`→`0x8B12984`)의 인자로 위에서
  내려오며, caller가 참조하는 `0x08D826E4`는 **텍스트 커맨드 인터프리터의 핸들러 테이블**
  (`08B127A1`+flags 등 함수포인터 구조)이지 메시지 텍스트 테이블이 아니다. 즉 **Part1 대사는 Part2
  같은 깨끗한 메시지-포인터 배열이 아니라 커맨드-스트림 아키텍처**라, "테이블 1개 추가"로 repoint 확장이
  안 된다. 대사 선택은 게임 이벤트/스크립트 시스템(렌더러에서 5~10단계+ 위)에서 ID로 이뤄진다.
- **종합**: Part1 대사 repoint는 ① 하네스 디버거 loadstate 미발화 수정 또는 fresh-boot 네비로
  런타임 트레이싱, ② 커맨드-스트림/이벤트 시스템 RE, ③ 실기 플레이테스트가 모두 필요한 다세션 작업.
  현 시점 안전 적용 불가 → **Part2 214라인 해소로 마감, Part1은 미적용 유지**(게임/쪼롱이님 캠페인 보호).

## [2026-06-23 續3] Part1 런타임 트레이싱 — 하네스 디버거 근본 한계 확정(옵션1·2 모두 시도)

사용자 "1,2 go"로 ① fresh-boot 네비, ② 하네스 디버거 수정을 모두 시도. 결과:

- **execution breakpoint는 타입 무관 전혀 미발화**: `break`를 HARDWARE/SOFTWARE 둘 다, 확실 실행
  주소(부팅 VRAM 루프 `0x0800247E`)에 걸어도 0히트. fresh boot에서도 안 됨 → mDebuggerRunFrame가
  execution breakpoint 체크를 안 하는 하네스/libmgba 경로 문제.
- **watchpoint는 fresh boot에서만 작동**: fresh boot VRAM 쓰기 52히트·IWRAM 188히트. 그러나
  **loadstate 후엔 미발화**. 수정 시도 전부 실패: ⓐ mDebuggerAttach 재호출 ⓑ core->attachDebugger
  (USE_DEBUGGERS 매크로 필요, ABI 불일치로 크래시) ⓒ GBAAttachDebugger(core->board) 직접 재배선
  (크래시 없으나 미발화). loadstate가 CPU activeRegion/prefetch를 fast-path로 복원해 watchpoint
  slow-path를 우회하는 mGBA 내부 동작.
- **결론**: 가용 도구는 fresh-boot watchpoint 뿐. breakpoint/스테핑이 없어 "메시지 텍스트 read →
  포인터 로드(테이블) 역추적"이 불가. 정적 추적도 커맨드 인터프리터로 비수렴(續2).

**다음에 시도할 구체 방법(가용 primitive로 가능)**:
1. **쓰기 watchpoint 역인덱싱**: fresh-boot 네비로 Part1 대사 도달 → IWRAM/EWRAM 쓰기 watchpoint →
   new값이 Part1 대사 포인터(0x08D8xxxx~0x08E1xxxx)인 store(=0x8B1299C) 캡처 → **실제 메시지 주소
   시퀀스** 확보 → 그 주소들을 **연속으로 담은 ROM 테이블** 검색(우연매치 아닌 실주소라 정밀).
   테이블이 있으면 repoint 가능, 없으면 커맨드-스트림 확정. (struct 함정은 헤더갭 가드로 이미 차단.)
2. **mGBA Lua 스크립팅** 메모리 콜백(C 디버거와 별개 경로 — breakpoint가 될 수 있음).
3. **libmgba 디버거 수정**(execution breakpoint 발화 + loadstate 후 watchpoint 재설치) — 소스 빌드 필요.
어느 경우든 적용 전 **실기/플레이테스트로 실제 대사 렌더 확인** 필수.

## [2026-06-23 續4] Part1 — mGBA Lua 스크립팅 임베딩 시도(4번째 접근)

C 디버거(breakpoint 사망·loadstate watchpoint 사망)를 우회하려 mGBA Lua 경로 시도.
- **Lua 엔진은 libmgba에 있음**: 심볼 `_mSCRIPT_ENGINE_LUA`, liblua5.5 링크됨. `tools/mgba_lua.c`로
  헤드리스 임베딩(mScriptContextInit/RegisterEngines/AttachCore/AttachStdlib/LoadFile) 빌드 성공.
- **컴파일은 됨**: .lua 문법오류가 정확히 보고됨(Lua 엔진이 isScript+load로 컴파일).
- **그러나 top-level chunk가 실행되지 않음**: `emu:write32` 마커가 메모리에 안 박히고 `console:log`
  무출력, top-level 런타임 에러도 미보고. 시도한 조합: ⓐ LoadFile 후 mScriptContextTriggerCallback("frame")
  ⓑ 엔진 mScriptEngineContext->run() 직접 호출(출력 전체 소실) ⓒ attach 순서 변경(stdlib/core를 엔진 등록
  전). 전부 실패. 헤드리스 임베딩에서 **스크립트 실행 트리거를 못 찾음**(mGBA 프론트엔드 소스 미공개).
- **결론(4접근 종합)**: Part1 대사 repoint의 런타임 트레이싱은 ① C 디버거(broken) ② fresh-boot watchpoint
  (추적 불가) ③ 정적(커맨드 인터프리터, 비수렴) ④ Lua(실행 트리거 미발견) 모두 막힘. **현 도구셋으로
  자율 불가** 확정. 다음은 소스 빌드 mGBA(디버거 수정) 또는 GUI 디버거+수동 플레이테스트가 현실적.
  `tools/mgba_lua.c`는 임베딩 스캐폴드로 보존(run 트리거만 RE하면 재사용 가능).

## [2026-06-23 續5] 정정: 디버거는 정상이었음 + Part1 repoint 성공

**중대 정정**: 續2~4의 "execution breakpoint 사망 / loadstate 후 breakpoint 사망" 결론은 **틀렸음**.
mGBA 0.10.5 소스(temp/mgba-src)로 mDebuggerRun을 읽으니 hasBreakpoints()→step-mode→checkBreakpoints
경로가 정상. 실측 재검증: breakpoint at 0x08337382 → loadstate 후에도 **7352히트**. 이전 0히트는
**테스트 주소(0x0800247E 등)가 그 짧은 프레임 창에서 실행 안 된 false-negative**였다. watchpoint만
loadstate가 메모리 shim을 제거해 미발화(breakpoint는 shim 무관이라 생존).
→ 교훈: "breakpoint 미발화 = 도구 고장"으로 단정 말 것. **확실히 실행되는 주소**(현재 PC)로 먼저 검증.

**결과**: 작동하는 디버거로 Part1 대사 런타임 트레이싱 성공(0x19 커맨드 RE) → Part1 repoint 완료
(続3, success.md). SOFTWARE breakpoint는 mGBA에서 abort()하니 HARDWARE만 사용.

## [2026-06-24] 이름 라벨/맵 글리프 무위험 자율수정 — 이번 세션 보류(deep RE 필요)
- **이름 라벨 가타카나 잔존**(CO 프로필 30f2 등): 이름은 SJIS 대화스트림 밖. 반각 SJIS 직접검색 실패
  (`コシゲ`/`ﾄﾞﾐﾉ` 미발견) → OBJ 타일/인덱스 렌더 경로로 추정. Domino만 `patch_part2_domino_co_name_obj`로
  OBJ blank+본문이관 처리됨. 타 CO는 per-character 테이블 RE 필요 → 무위험 즉시수정 불가, 추적.
- **맵 선택 섬 이름 '??'**(87, 마=8BC3/메=8BED): ROM 인코딩은 정확(∈2350)인데 컴팩트 렌더러가 fallback
  0x8148='?'로 렌더 → 맵선택 컴팩트 글리프뱅크에 해당 음절 미주입. 글리프뱅크 주입점 RE 필요, 추적.
- **CSV 109행 ROM 위험분 일괄수정 금지**: korean이 일본어/빈칸인 행 다수가 part1_campaign/part_dialogue(쪼롱이
  인접)라 행별 맥락검수 없이 일괄 번역하면 쪼롱이 보호 위반/오역 위험. `qa_csv_integrity.py`로 추적, 신중 복구.

---
## [2026-06-25] 대사 렌더러 0x20-advance hook — off-by-one 회귀 (revert)

단어붙음(반각공백 0x20 미렌더)의 정석 근본해결로 **Part1 대사 파서 0x20 핸들러 hook**(0x20을 한 칸 advance)을
codex가 구현 시도. 결과는 **off-by-one 렌더 회귀**라 revert.

**메커니즘(확정)**: Part1 대사 파서 jump table 0x08B12098+(char-0x09)*4. 0x20 엔트리(0xB120F4)는 원래
0x08B12144(byte ptr만 +1, x advance 없음=잼). codex hook(0x08F30500): 0x20 다음 바이트가 content(한글
0x88-0xE2 / ASCII 0x21-7E 중 제어코드 제외)면 x([state+0x34]) +2, char count([state+0x32]) +1.

**실패 원인**: fresh-render 시 공백이 **한 음절씩 늦게** 렌더("캐서린이없 는레"=캐서린이 없는이어야). 파서가
0x20 다음 글리프를 **hook advance가 적용되기 전에 배치**(lookahead/pipeline). [state+0x34]가 글리프 tile
위치(0x08B12640 ldrh r2,[r0,#0x34])에 쓰이나, content 핸들러가 그 값을 0x20 처리 시점보다 먼저 읽음.

**재시도 조건**: 파서의 x 계산 타이밍을 **런타임 트레이스**(watchaddr [state+0x34], 한 글자씩)로 규명 후,
hook을 올바른 시점(다음 글리프 배치 전)에 걸어야 함. codex 37분 시도로도 미해결. 단순 advance값 조정 아님.

**대안(현 채택)**: 전각(0x8140)화+재배치로 5976→718(88%) 해소. 718 잔여(무포인터 sequential chunk 476 +
guard-skip)는 hook이 정석이나 위 파서 RE 선행 필요.

---
## [2026-06-25] 렌더러 0x20-advance hook — 런타임 트레이스 완전 진단(미완 구현)

단어붙음 잔여 718(0x20 메시지)을 렌더러 hook으로 근본해결하려 11시간+ 런타임 트레이스. **off-by-one을 완전
규명**했으나 최종 구현이 caller 루프를 깨 revert(작동하는 718 유지).

**파서 구조(트레이스+capstone 확정, state=0x03000E00)**:
- 화면 위치 = `[state+0x28](base) + [state+0x32](열)*2 + [state+0x33](행)*64`, 계산 함수 **0x08B11B80**.
- caller(0x08B126F0~): ①0x8b1271e `bl 0x8b11b80`→r5=위치(**파서 전** 계산) ②0x8b12728 `bl 0x8b12074`(파서) ③
  0x8b12758~ render(0x8b1befc 글리프변환 + **0x8b12762** `adds r0,r4; adds r1,r5; bl 0x8b12640`(타일쓰기))
  ④0x8b1277A~ [state+0x20]+=2, [state+0x32]+=1(열), [state+0x34]+=2(**타일인덱스**) ⑤0x8b12792 `ldrsb [r6]`
  부호검사로 루프 지속.
- 파서 jump table 0x08B12098+(char-9)*4. 0x20엔트리=0xB120F4(원래 0x08B12144=byte ptr만+1=잼).
- **[state+0x34]는 타일인덱스(글리프 저장위치), [state+0x32]가 열(화면 위치)**. codex/1차 hook이 0x34를 advance해 무효.

**off-by-one 근본**: 위치가 **파서 전**(0x8b1271e)에 [state+0x32]로 계산됨. 0x20은 파서 내부에서 소비(0x20 hook이
[state+0x32]+1)되나, 현재 글자의 위치는 이미 계산됨 → 공백이 **다음 글자**에 적용=한 음절 늦음. codex가 못 푼 이유.

**올바른 수정(미완)**: ①0x20 hook이 [state+0x32](열) advance ②**render 직전 위치 재계산**(0x8b11b80 공식 인라인).
4-정렬 site 필요(_abs_tramp는 ldr[pc,#0]라 4-정렬 필수; 0x8b12762는 2-정렬 → 0x8b12764로). 그러나 render hook이
**1글자 후 caller 루프(0x8b12792 [r6] 부호검사) 정지** — r6(루프 제어)와의 상호작용 미해결. 추가 단일스텝 트레이스 필요.

**대안(현 채택)**: 전각(0x8140)화+재배치로 5976→718(88%). 718은 0x20 메시지(슬롯 빠듯해 전각 미적합 + 무포인터
재배치불가). hook 완성 시 0x20이 슬롯맞고 렌더되어 718+부호소실 1733 근본해결 가능.

---
## [2026-06-26] D2 폭 후보 미커버 read-watch — 기존 checkpoint 주변 hit 0

`0xD81C24` 맵 디자인 도움말, `0xA3B880/0xB842E8` CO 파워명 후보를 기존 scene checkpoint 주변에서 다시
read-watch했다. 결과는 `data/d2_width_uncovered_watch_probe_20260626.json`에 보존했다.

- Part1 fresh 메뉴 state와 구 `menu_base.ss0`에서 `DOWN/A/START/SELECT/좌우` 조합 11케이스:
  `0x08D81C24` 본문 head와 `0x08B059F0` 포인터 read hit 0.
- Part2 전투/메인 sweep/freebattle state 4케이스:
  `0x08A3B880`, `0x08B842E8` 본문 head 및 `0x083806FC/0x08381300/0x08B3C1F8` 포인터 read hit 0.

이 실패 경로로 D2를 닫지 않는다. 결론은 "기존 checkpoint 주변은 실제 노출 화면이 아니다"이며,
다음 재시도는 맵 디자인 도움말 메뉴 직접 진입 state 또는 CO 파워 발동/상세 화면 state 확보가 먼저다.

---
## [2026-06-27] E12 compact renderer breakpoint trace 1차 — 대표 route hit 0

`tools/trace_compact_renderer.py`로 현재 문서화된 compact renderer 후보 PC
`0x08380564/0x083806A8/0x08381294/0x08B3C184`와, static xref로 찾은 B84 pointer-table user 후보
`0x08B3C2D0/0x08B3C300/0x08B3C320/0x08B3C4D6/0x08B3C550/0x08B3C5A0`에 hardware break를 걸고,
당시 SHA `11098045…`의 Part2 메인 메뉴, 워즈숍, compact 메뉴, 룰 설정,
전투 공격/전투 OBJ 라벨/전투 시작 overlay, CO 프로필 maxg/domino refresh를 실행했다.

- **결과**: 9 route 모두 breakpoint hit 0/direct target hit 0.
  산출물은 `data/compact_display_renderer_trace.json`,
  캡처/로그는 `temp/compact_renderer_trace_20260627/`.
- **후속 재시도**: `tools/analyze_compact_display_code_context.py`의 code-context 후보까지 자동 포함해
  break set을 50개로 늘렸지만, 같은 9 route에서 여전히 hit 0/direct 0.
  캡처/로그는 `temp/compact_renderer_trace_code_context_20260627/`.
- **보조 확인**: CO 프로필 refresh는 실제로 화면이 바뀌지만, 문서상 A2 목적지였던 `0x060160E0` write hit도 0.
  넓은 VRAM 초반 write-watch에서는 `0x08313C4C`, `0x08F302DE..0x08F302F0` 계열 write PC가 잡혀
  화면 갱신 자체는 일어남을 확인했다.
- **실패 판정**: 이 route/PC 조합은 E12 direct evidence로 사용할 수 없다. 단, 이것만으로 B8/B84/A2 테이블이
  전역 미사용이라고 결론내리면 안 된다. 다음 재시도는 corrected renderer PC 역추적 또는 실제 CO 파워 발동,
  유닛 상세, 전투 데미지예측 state를 확보해 `r0`가 target 주소에 떨어지는지 확인해야 한다.

## [2026-06-27] E12 compact read-watch 1차 — route/subset hit 0

claude/agy 재리뷰 지적에 따라 `tools/probe_compact_display_reads.py`를 추가하고 source range/exact target
read-watch를 시도했다.

- **A2/B84 range**: fresh Part2 메인 메뉴 + CO profile maxg/domino refresh 3케이스 hit 0/direct read 0.
  산출물 `data/compact_display_read_watch_probe.json`.
- **B8 range**: compact 메뉴/워즈숍 savestate 2케이스 hit 0/direct read 0.
  산출물 `data/compact_display_read_watch_probe_b8.json`.
- **B8 exact subset**: `0xB81D40/0xB831BC/0xB8387C/0xB838BC/0xB839F0/0xB84CB8/0xB84F14`을
  fresh Part2 메인 메뉴 + compact 메뉴/워즈숍 후보 3케이스에서 감시했지만 hit 0/direct read 0.
  산출물 `data/compact_display_read_watch_probe_b8_subset.json`.
- **B8 battle 후보**: 같은 exact subset을 전투 공격/OBJ 라벨/전투 시작 overlay 3케이스에서 감시했고,
  전투 공격 1케이스는 B8 전체 range로도 감시했지만 모두 hit 0/direct read 0.
  산출물 `data/compact_display_read_watch_probe_b8_battle_subset.json`,
  `data/compact_display_read_watch_probe_b8_battle_range.json`.
- **외부 상점/프로필 state 후보**: `profile_plus_aw2_zophar_matrix/*/state_shop_enter.ss0` 5개를 B8 range로,
  `state_011_SELECT.ss0` 5개를 A2/B84 range 대기 및 RIGHT refresh로 감시했지만 모두 hit 0/direct read 0.
  프레임 확인상 해당 후보들은 compact 파워명/상품목록이 아니라 상점 대화 화면이었다.
- **후속 양성대조/추가 메뉴 sweep**: fresh `0x00A01970` 나레이션 exact watch는 59 hit가 나와 하니스
  자체는 ROM read를 잡을 수 있음을 확인했다. 하지만 `0x00B83268` 통신 후보 exact watch와,
  fresh `06_part2_title` + `part2_menu_sweep` 정책에서 B8 대표 7개
  (`0xB81D40/0xB831BC/0xB83268/0xB8387C/0xB839F0/0xB84CB8/0xB84F14`) exact watch는
  모두 hit 0/direct read 0. 산출물은
  `data/compact_display_read_watch_positive_control_a01970.json`,
  `data/compact_display_read_watch_b83268_comm.json`,
  `data/compact_display_read_watch_b8_fresh_menu_sweep_subset.json`.
- **최신 SHA `a4e98a93…` 재시도**: current-exact 11케이스(A2/B84/B8 대표 27 target)와
  B8 map-territory exact 1케이스(`0x00B84F5C/0x00B84F6C`, `10_part2_region_map_redstar`)도
  hit 0/direct read 0이다. 같은 ROM에서 positive control `0x00A01970`은 hit 8이므로, 실패 원인은
  하니스 전체 불능이 아니라 목표 화면/target 가정 문제로 본다.
- **mutation source test 기각**: `10_part2_region_map_redstar`에 보이는 `레드스타` 라벨은
  `0x00B84F5C`/`0x00B84F6C`를 `테스트`로 바꿔도, `0x00A35758`(`레드스타 영토`)를 바꿔도,
  ROM 전체의 encoded `레드스타` 261건을 `테스트`로 바꿔도 픽셀 diff 0이었다.
  따라서 이 화면의 지도 라벨은 B8/B84 텍스트 source 증거가 아니라 baked map graphic, VRAM cache,
  또는 아직 분리하지 못한 다른 source로 취급한다.
- **메뉴 라벨 mutation 기각**: `scene_86_common_compact_menu_tables`에서 `0x00B837A4`(`통신`)와
  `0x00B84488`(`편집`)을 바꿔도 diff 0이었다. 해당 checkpoint는 savestate+1 frame이라 cache false-negative
  가능성이 크다. 별도 fresh `07_part2_main_menu`에서도 ROM 전체 `상점` 6건 mutation diff 0이므로,
  현재 보이는 메뉴 라벨을 E12 B8 target 직접 증거로 쓰지 않는다.
- **전투 action menu 후보 기각**: `temp/first_battle_state31_action_a30/a30_action_menu.ss0`는 작은
  `공격` action menu가 열린 실제 화면이지만 B8 exact 후보 7건
  (`0xB82DEE/0xB82DF6/0xB82DFE/0xB82E28/0xB82E32/0xB82E3A/0xB82E42`) read-watch가 hit 0이었다.
  메뉴가 열리기 전 `temp/first_battle_state31_a36_probe/after_a36.ss0`에서 watch를 먼저 설치하고
  `A` 반복으로 같은 `공격` 메뉴까지 도달해도 hit 0/direct 0이었다.
  산출물: `data/compact_display_read_watch_action_menu_a30_b8_exact.json`,
  `data/compact_display_read_watch_action_menu_from_after_a36_b8_exact.json`.
- **장시간 range watch 기각**: 최신 SHA에서 A2/B84/B8 whole-range를 fresh 대표 화면에 걸고 DOWN/RIGHT redraw를
  유도하는 방식은 `07_part2_main_menu`도 끝내기 전에 3분 이상 정체되어 중단했다. 출력 JSON을 남기지 못했으므로
  evidence가 아니라 “이 방식은 과도하게 느려 실전 조사에 부적합”한 실패 기록으로만 취급한다.
- **state 후보 기각**: CO profile nav probe는 Domino/Max 프로필 설명 전환과 map 복귀만 확인됐고
  CO power-name page로 들어가지 못했다. breakscan/profile/shop 후보 contact도 지도 라벨/상점 대화/메뉴 화면이라
  A2/B84/B8 direct evidence에 부적합하다. 증거 contact:
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/co_profile_nav_probe_contact.png`,
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/candidate_state_triage_contact.png`.
- **실패 판정**: 현재 route/subset은 direct evidence로 부적합하다. B8 전체 range fresh watch는
  60초 이상 정체되어 중단했으므로 장시간 sweep 방식은 피하고, 다음에는 실제 파워 발동/유닛 상세/무기 상세/데미지예측
  state를 확보해 좁은 exact watch 또는 corrected renderer breakpoint로 재시도한다.

---
## [2026-06-27] Part1 작전실 작전명 초기 수정 실패 — in-place override만으로는 부족

- **실패한 접근**: `0xB81D80..0xB82018` 작전명 행의 `ADDRESS_TEXT_OVERRIDES`를 compact title로 줄인 뒤
  재빌드했지만, fresh emulator 작전실 화면에서 `전선 기지를 확보하라`와 `적 부대를 해치워라`가 계속 표시됐다.
- **기각 이유**: ROM 원주소 검색에서는 compact 문장이 들어갔지만, `temp/repoint_manifest.json`에
  `0xB81FF4 -> 0xA5B248`, `0xB81FC4 -> 0xA5B264` 재배치가 남아 있었다. free-space payload는
  `data/dialogue_overrides.json`의 legacy 긴 문장을 사용했으므로 원주소만 고치는 방식은 증상 제거가 불가능했다.
- **교훈**: protected 표시 override가 있는 주소는 in-place 쓰기와 repoint payload 모두 같은 권위를 사용해야 한다.
  이후 `_rp_dlg()` 우선순위를 display override → `ADDRESS_TEXT_OVERRIDES` → legacy dialogue override로 고쳐 닫았다.

---
## [2026-06-27] E12 A2 CO 프로필 설명 checkpoint는 power-name direct evidence가 아님

- **실패한 접근**: `scene_30f2_part2_co_profile_story`에서 A2 compact power-name target
  `0x00A295D8`(`강타`)를 temp ROM에서 `검증`으로 단일 mutation하고 같은 savestate checkpoint를 캡처했다.
- **결과**: pixel diff 0, bbox 없음. temp 증거는
  `temp/e12_a2_co_profile_mutation_probe_20260627_r2/summary.json` 및 contact
  `temp/e12_a2_co_profile_mutation_probe_20260627_r2/contacts/a2_co_power_profile_display_overrides_00A295D8_mutation_contact.png`.
- **기각 이유**: 이 savestate+1 frame checkpoint의 diff 0은 A2 power-name 직접 증거가 되지 않는다.
  CO 설명/프로필 텍스트와 CO 전환은 보이지만, 해당 화면에 `강타` power-name이 실제로 표시되는지는
  이 실험만으로 확정되지 않았다. 따라서 이 캡처를 A2 power-name 직접 증거로 다시 사용하지 말고,
  필요하면 coldboot fresh power-name route에서 재검증한다.

---
## [2026-06-27] E12 B84 power/menu route probe — 55케이스 hit 0

- **시도**: `scene_89_common_battle_system_results` 계열 state에서 B84 CO 파워명/전투 메뉴 route를 찾기 위해
  `temp/e12_b84_power_menu_probe_20260627` 55케이스를 실행했다. 무 RAM 패치와 gauge/state variant를 섞고,
  `b_start`, `b_select`, `up_a` 등 power/menu 진입 가능성이 있는 입력을 시도했다.
- **감시 대상**: `0x08DF2B54` B84 power-name pointer table, `0x08B84E50` 계열 B84 body/read 후보,
  `0x08B3C184`, `0x08B3C254`, `0x08B3C4D8` compact renderer 후보 break를 감시했다.
- **결과**: read/break hit 0, direct evidence 0. contact sheet는 항복 확인창, 메뉴, 전투 대화 프레임을 포함했지만
  B84 파워명 target이 실제 화면 source로 읽히는 증거는 없었다.
- **부수 발견**: contact에서 별도 결함 `모드 선택으로 돌아갈까??????`를 발견했고, 이는
  `0x00A34CE8/0x00DF2A64` 문구를 `모드 선택으로 돌아갈까요?`로 줄여 성공적으로 수정했다.
- **실패 판정**: 이 probe는 B84 power-name direct evidence 확보 실패 기록이다. B84 target 전역 미사용 증명이 아니다.
  다음에는 실제 CO 파워 발동 직전/직후 state, 파워명이 보이는 animation frame, 또는 corrected renderer PC에서
  exact target read/WRAM-DMA write chain을 좁혀야 한다.

---
## [2026-06-27] E12 B8 작전실 DOWN 16 proof — 추가 행 diff 0

- **시도**: `tools/prove_compact_display_mutation.py`로 `41_part1_operation_room` fresh route 뒤 DOWN 16회를 붙이고
  `0x00B81F2C`(`과외수업`), `0x00B81F24`(`개전`), `0x00B81F10`(`건파이터`), `0x00B81F04`(`하늘용사`)를
  단일 mutation했다. 경로 길이 문제는 이 과정에서 발견해 hash suffix로 수정했다.
- **결과**: 4건 모두 pixel diff 0. base frame은 DOWN 13회와 같은 `도그파이트/바다너머/백은세계/결전` 화면에
  머물러 있었다. 산출물은 `temp/e12_b8_operation_more_down16_probe_20260627/summary.json`.
- **실패 판정**: 이 fresh route의 단순 DOWN 반복은 `결전` 아래 작전명으로 더 내려가지 못한다.
  `과외수업` 이하를 증명하려면 다른 unlock/progress state, page 이동 입력, 또는 campaign progress가 더 열린 savestate가 필요하다.

---
## [2026-06-27] E12 current-SHA read-watch refresh — 비작전실 기존 route 45케이스 direct hit 0

- **시도**: 최종 SHA `3e3bae33…` 기준으로 기존 `data/compact_display_read_watch*.json` 16개를 모두 재실행했다.
  대상은 A2/B84 profile range, B8 action-menu exact/range, B8 menu/shop/battle/map/rule 후보 exact/range,
  external profile/shop state, fresh menu sweep이다.
- **결과**: E12 target probe 합계 45 cases, hit 0, direct target read 0.
  반면 positive control `0x00A01970`은 같은 현재 ROM의 fresh prologue route에서 hit 8을 유지했다.
  이 8-hit는 현재 단일 `08_part2_prologue_map_text` route 기준 baseline이며, 과거 59-hit 기록과 직접 비교하지 않는다.
- **후속 보정**: 이후 `41_part1_operation_room` B8 작전명 4주소 read-watch는 69 hit/direct 69를 기록했다.
  따라서 이 실패 항목은 B8 작전실을 제외한 기존 A2/B84/Part2-B8 후보 route의 0-hit로 한정한다.
- **실패 판정**: 기존 route/subset으로는 A2/B84/B8 compact target의 direct provenance를 얻지 못한다.
  이 0-hit는 전역 미사용 증명이 아니며, 다음 시도는 실제 파워명/유닛·무기 상세/데미지예측/통신 대기문이
  표시되는 fresh 또는 near-fresh state를 먼저 확보한 뒤 exact watch/mutation/VRAM-DMA chain으로 좁혀야 한다.
  일반 대사 `0xA01970` 양성대조는 read-watch 하니스 검증일 뿐 compact renderer 전용 양성대조가 아니므로,
  이 route 세트를 다시 반복하는 대신 compact renderer가 반드시 실행되는 양성 route를 먼저 확보해야 한다.

---
## [2026-06-27] Part1 single-map unknown label 일반 한글/kanji 경로 실패

- **시도**: `0x00DF8C2A`의 원본 `8148`×6 placeholder를 일반 예약 한글 코드로 인코딩한 `미공개`로 직접 교체했다.
- **결과**: Part1 single-map list renderer에서 해당 행이 blank로 표시됐다. 이 주소의 renderer는 일반 대사/도움말용
  예약 한글 코드 경로를 쓰지 않는다.
- **시도**: compact kanji glyph 경로를 기대하고 `基工開`를 넣었다.
- **결과**: 동일하게 blank가 됐다. 따라서 Part2 UI context token/kanji-table 우회도 이 리스트에는 맞지 않는다.
- **시도**: `ヮ/ヵ/ヶ` 같은 작은 가나 후보를 placeholder source로 써서 glyph remap 가능성을 확인했다.
- **결과**: 원하는 한글 표시로 안정화되지 않았다.
- **채택하지 않은 이유**: 위 세 경로는 current mGBA 화면에서 `미공개`를 만들지 못한다.
- **시도 후 폐기**: `ガギグ` source를 쓰고 `ガ/ギ/グ` glyph table entry를 name-grid blank slot의
  `미/공/개` 글리프로 remap하는 우회는 화면상으로는 성공했지만, 전역 가나 표시 오염과 `ヒ/フ/ヘ`
  슬롯 충돌 위험이 있어 claude/agy 리뷰 후 폐기했다.
- **최종 대체**: `0x00DF8C2A` source는 `？` 3개+전각공백 3개로 유지하고, `0x08B1319C` compact call에
  source pointer gate가 있는 국소 hook을 설치해 이 label에만 `미/공/개` private tile을 복사한다. 성공 증거는
  `docs/screenshots/part1_single_map_unknown_label_fix_2026-06-27/contact.png`.

---
## [2026-06-27] Part1 unlocked mode carousel 격자 artifact — option label 자산 수정 실패

- **시도**: AW1 8495-front unlocked route의 `DOWN` 1/3 화면에서 도움말 박스 뒤에 보이는 작은 격자성 블록을
  `PART1_MODE_OPTION_BLOCKS`의 글자 침범으로 보고, `make_part1_option_block()`을 Galmuri regular/10px로 축소하는
  temp 변경을 빌드해 확인했다.
- **결과**: output SHA는 시험 중 `1882588d...`로 바뀌었지만, `temp/e16_unlocked_mode_option_shrink_after_20260627/contact.png`
  기준 격자 ROI dark pixel 수와 bbox가 기존과 같았다. source 변경은 원복했고 output SHA는
  `fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093`로 복구했다.
- **시도**: option text를 block 내부 y=-3으로 올린 temp ROM `temp/e16_shifted_option_test.gba`를 만들었다.
  VRAM tile의 `트라` label bbox는 실제로 위로 이동했지만, 화면 crop의 격자성 블록은 유지됐다.
- **시도**: `trial/campaign` option block의 왼쪽 64x32 half를 통째로 blank 처리한 temp ROM
  `temp/e16_blankleft_option_test.gba`를 만들었다.
- **결과**: `temp/e16_blankleft_option_compare_20260627/crops.png`에서 label 일부는 사라졌지만 격자성 블록은
  그대로 남았다.
- **시도**: option label palette index를 11/12/13으로 바꾼 temp ROM들을 만들었다
  (`temp/e16_option_palette_tests_20260627/`).
- **결과**: 최종 화면 ROI의 격자성 블록은 줄지 않았고, index 12/13은 오히려 dark/chroma 수치가 나빠졌다.
- **시도**: `trial/campaign` option block 전체를 blank 처리한 temp ROM
  `temp/e16_option_blank_tests_20260627/blank_trial_campaign.gba`를 만들었다.
- **결과**: `temp/e16_blank_oam_match_20260627/` 기준 OAM idx30 tile504의 VRAM bytes는 실제로 0이 됐지만,
  composited frame의 격자성 블록은 계속 남았다.
- **기각 이유**: 이 artifact는 단순 option label glyph 위치/크기/왼쪽 half 문제가 아니다. 실제 source를 더 찾기 전
  option label 축소, palette 변경, half/full blanking, 특정 좌표 raw tile 지우기 같은 패치는 취약한 화면별 hack이므로
  채택하지 않는다. 다음 재시도는 원본 같은 route 비교와 레이어별 관측이 먼저다. 현재 확정된 것은
  `OBJ idx30/tile504` option glyph 단독 원인 배제뿐이며, BG/tilemap 원인 단정은 아직 불가하다.

---
## [2026-06-27] E16 unlocked artifact 리뷰 CLI 시도 실패

- **시도**: `temp/review_prompt_e16_unlocked_artifact.md`를 작성해 agy와 claude에 엄격 리뷰를 요청했다.
- **결과**: 첫 백그라운드 호출은 agy/claude 모두 0바이트로 즉시 종료했다. 짧은 프롬프트 테스트는 정상이라 긴 프롬프트 전달 방식을
  바꿔 재시도했다.
- **결과**: agy foreground `--print-timeout 2m`는 `Error: timed out waiting for response`로 종료했다.
  claude foreground는 90초 이상 무응답이어서 중단했고 `Execution error`만 반환했다.
- **판정**: 이번 artifact 판단에는 실질 리뷰 결과를 얻지 못했다. 같은 긴 프롬프트/같은 CLI 방식 반복은 피하고,
  재시도 시에는 근거 이미지를 줄이거나 질문을 OAM #30 provenance 하나로 좁혀야 한다.

### 짧은 프롬프트 재시도
- **시도**: `temp/review_prompt_e16_short.md`(605B)로 질문을 `OBJ idx30/tile504 배제 결론` 하나로 좁혀
  agy/claude에 재리뷰를 요청했다.
- **결과**: agy는 120초 timeout(`temp/agy_review_e16_short.md`), claude는 응답 성공
  (`temp/claude_review_e16_short.md`).
- **반영**: claude는 option label을 패치하지 않는 판단은 타당하지만, `BG/tilemap` 귀속은 양성 증거 없이 성급하다고
  지적했다. 이에 `todo.md`, `docs/research.md`, `docs/fail.md`의 결론을
  "`OBJ idx30/tile504` option glyph 단독 원인 배제, 실제 레이어/원인 미확정"으로 낮췄다.

---
## [2026-06-27] E16 remaining route negative probes

- **대전 이어하기**: AW1 8495-front `DOWN×5,A` 대전 시작/이어하기 선택 화면에서
  `RIGHT/LEFT/DOWN/UP` 및 조합을 캡처했지만 화면은 계속 `처음부터 대전`만 표시했다.
  이 save에는 VS continue가 없어 `0xDFA7BE` direct evidence를 얻을 수 없다.
  증거: `temp/e16_battle_continue_direction_probe_20260628/contact.png`.
- **통신 1P~4P 화면**: AW1 8495-front `DOWN×6,A,item,A`의 케이블/1카드 계열 1P~4P 화면은
  하단이 `통신 준비 중이야`로 고정되며 `0xDFA8AA/8CB/8EA/90A/926` player-count 도움말을 표시하지 않는다.
  증거: `temp/e16_link_item_frames_2x_20260628.png`.
- **대전 맵/룰 설정 화면**: AW1 8495-front `DOWN×5,A,A` 맵 선택에서 여러 맵/페이지를 고른 뒤 A,
  그리고 `DOWN×5,A,A,A,A` 룰 설정 화면에서 방향키/버튼을 눌러도 player-count 도움말은 나오지 않았다.
  증거: `temp/e16_battle_map_player_select_probe_20260628/contact.png`,
  `temp/e16_battle_rule_player_probe_20260628/contact.png`.
- **탐색 방식 실패**: `temp/e16_missing_route_bfs_20260628`처럼 sequence마다 새 mGBA를 띄우는 넓은 BFS는
  너무 느려 중단했다. `temp/e16_missing_route_fast_20260628`처럼 한 세션에서 watch+loadstate를 반복하는 방식도
  첫 progress 전 장시간 정체되어 중단했다. 다음 탐색은 주소 묶음별 짧은 route probe로 제한한다.

---
## [2026-06-28] E16 remaining route 추가 음성 probe 및 CLI 리뷰 한계

- **사용자 추가 스크린샷 재확인**: `~/Downloads`, Desktop, Pictures의 최근 이미지를 다시 확인했지만
  새로 분리할 스크린샷은 없었다. 확인된 7장은
  `docs/screenshots/user_report_triage_2026-06-27/download_contact.png`와 같은 계열이며, current 증거에서는
  작전실 작전명 깨짐, `single_map ??????`, Part1 메뉴 라벨/도움말 침범, Part1 룰 원형 일본어 잔존이
  각각 기존 수정 증거로 닫혀 있다.
- **hidden/campaign 후보 실패**: `temp/e16_hidden_campaign_state_frames_20260628.json`의 27개 기존 hidden/campaign
  후보 state frames-only watch는 남은 target hit 0이었다. `2111/2113/2954/3285` 계열에서 `UP/SELECT/A`
  조합을 더한 후보도 hidden target을 화면에 내지 못했다.
- **전체 AW1 save top-level sweep 실패**: 변환된 AW1 save 8개
  (`11186`, `2111`, `2112`, `2113`, `2807`, `2954`, `3441`, `8495`)를 tempsav로 로드해
  current ROM top-level sweep을 실행했다. `temp/e16_aw1_all_saves_top_sweep_timeout_20260628.json` 기준
  frames 120, missing hits 0, failures 0이며 contact는
  `temp/e16_aw1_all_saves_top_sweep_timeout_20260628/contact.png`다.
- **3285 state 기본 route 실패**: `temp/e16_gamefaqs_3285_menu_default_steps_20260628` probe는 장시간 실행으로
  중단했고, partial 파싱 `temp/e16_gamefaqs_3285_menu_default_steps_20260628_partial.json` 기준
  33 cases, missing hits 0이다.
- **대전 continue 생성 실패**: `temp/e16_vs_continue_create_probe_20260628`에서 8495 save temp copy로
  VS battle start를 시도했지만 save SHA가 전후 동일했다. 최종 캡처는 아직 `팀 설정`/`통신 준비 중이야`
  화면이어서 실제 VS suspend/continue save를 만들지 못했다.
  후속 정정: 이 실패는 `DOWN×5`로 통신 계열에 들어간 route 오류였다. current single battle은 `DOWN×1,A`이며,
  전투 중 `SELECT -> A -> DOWN -> DOWN -> A -> A`로 suspend save를 만든 뒤 `0xDFA7BE` direct evidence를 확보했다.
  성공 절차는 `docs/success.md`의 2026-06-28 `이어서 대전` 항목을 따른다.
- **map/team/SELECT-LR 경로 실패**: `DOWN×5,A,A` 계열과 `SELECT/L/R/START/A` 조합 probe에서
  `0xDFA7BE` read-hit가 반복됐지만 최종 contact
  `temp/e16_team_setting_player_help_probe_20260628/contact.png` 및
  `temp/e16_player_count_select_lr_probe_20260628/contact.png`에는 `이어서 대전`이 보이지 않았다.
  따라서 read-hit만으로 direct visual evidence에 넣지 않는다. player-count
  `0xDFA8AA/8CB/8EA/90A/926` hit는 0이다.
- **CLI 리뷰**: agy는 잔여 route 후보로 실제 VS suspend/continue SRAM, hard/hidden campaign unlock save,
  true player-count 선택 화면 또는 AW2 free battle route를 제안했다. claude CLI는 2분 이상 무응답 후
  `Execution error`로 중단되어 실질 리뷰 결과를 얻지 못했다.
- **판정**: 이번 음성 probe는 current route set의 실패 기록일 뿐 target 미사용 증명이 아니다.
  다음 시도는 save/state 조건을 먼저 바꿔 실제 메뉴 item code가 잔여 target에 대응하는 화면을 만든 뒤
  watch와 최종 프레임을 함께 묶어야 한다.

## [2026-06-28] E16 broad savestate item-code scan false positive

- **시도**: Part1/AW1/E16/menu/single/link/campaign/freebattle 이름이 걸리는 `temp/**/*.ss0` 8,085개를 current ROM으로
  순차 로드하고 `0x02000000..0x020000FF`를 덤프해 Part1 compact menu object의 item code 배열
  (`+0x30` 계열)에 잔여 code `5/6/16/17/18/19`가 있는지 찾았다.
- **결과**: plausible active menu 후보 중 잔여 code는 없었다. 유일한 후보는
  `temp/final_original_vs_final_20260615/original_menu.ss0`의 code17이었지만, active length `0x2D/0x2E=6/6`
  뒤 7번째 tail 값이었다. current ROM에서 이 state를 직접 로드해 `DOWN/UP/A` read-watch를 붙여도
  기존 visible 도움말(`0xDFA752/775/79A`, `0xDFA942/95B/972/989`, `0xDFA6AA/6CD/6E2/6FB`)만 읽혔고
  잔여 `DFA8EA` 계열은 hit 0이었다.
- **추가 실패**: `w8 0200002F 00` + `w8 02000030 <item_code>`로 RAM item code만 바꾸는 방식은
  menu redraw가 발생하지 않아 help source read가 0이었다. renderer 검증은 temp ROM pointer-table mutation처럼
  실제 redraw를 일으키는 방식으로 해야 한다.
- **판정**: 기존 savestate 더미/tail 값만으로 direct route를 얻을 수 없다. 같은 방식의 광역 state scan을
  반복하기보다 실제 VS suspend/continue SRAM, hard/hidden campaign unlock SRAM, 또는 player-count 화면을 여는
  route를 새로 확보해야 한다.
- **CLI 리뷰 재시도 실패**: `temp/review_prompt_e16_20260628.md`로 `claude -p`와
  `agy --dangerously-skip-permissions -p`를 각각 180초 timeout wrapper에서 실행했지만 둘 다 stdout/stderr 0바이트로
  timeout됐다. 따라서 이번 forced-render/savestate-scan 판단에는 외부 CLI의 실질 리뷰 결과가 없다.

## [2026-06-28] E12 `scene_87_common_rule_settings` B8 map-name mutation direct proof 실패

- **시도**: `scene_87_common_rule_settings` current fresh checkpoint에서 화면에 보이는 `소라 마메 섬` 계열을
  B8 compact target `0x00B827AC`(`소라마메섬`)의 live source로 증명하려고,
  `tools/prove_compact_display_mutation.py --checkpoint scene_87_common_rule_settings --target 0x00B827AC=검증마메섬`
  를 실행했다.
- **결과**: current ROM SHA `fb760c65...`에서 null-control diff 0, mutation diff도 0이었다.
  contact는 `docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B827AC_mutation_contact.png`
  에 남아 있지만 direct evidence로 채택하지 않는다.
- **판정**: 이 rule-settings 화면은 B8 `0xB827AC` row를 직접 읽어 표시하지 않는다. 기존 `소라?? 섬`
  수정은 A2C/B8 표시 계층 차이를 분리한 display override로 닫혔고, E12 B8 provenance에는 사용할 수 없다.
  이는 단일 current fresh route의 음성 결과이며, `0xB827AC`가 다른 화면에서 쓰이지 않는다는 전역 증명은 아니다.
  다음 재시도는 A2C 계열 실제 source 또는 별도 renderer/read-watch 체인을 겨냥해야 한다.

## [2026-06-28] E12 Part2 맵 목록 `0x00B8279C` B8 duplicate mutation 실패

- **시도**: `temp/scene_entrypoints/part2_menu_sweep/state_016.ss0`에서 `A`로 여는 Part2 맵 목록의
  `도넛 섬`을 B8 map-name copy `0x00B8279C`의 live source로 증명하려고 같은 슬롯을 `검증섬`으로 바꿨다.
- **양성 대조**: 같은 route와 같은 문자열에서 A2 copy `0x00A2CC4C`를 바꾸면 pixel diff 10548이 발생했고,
  contact sheet에서 목록 라벨이 `검증섬`으로 바뀌었다. null-control은 diff 0이었다.
- **음성 결과**: B8 `0x00B8279C`를 동일하게 바꿔도 pixel diff 0이었다. 증거는
  `docs/screenshots/b8_map_list_source_redirect_2026-06-28/report.json`,
  `a2_live_source_contact.png`, `b8_duplicate_negative_contact.png`.
- **판정**: 이 route에서 보이는 `도넛 섬`은 B8 duplicate가 아니라 A2 source에서 온다.
  `0x00B8279C`를 같은 state+입력으로 다시 mutation/read-watch하는 것은 중단한다. 단, 이는 route-local
  음성 결과이며 B8 map-name copy 전체의 전역 dead-copy 증명은 아니다. `state_016.ss0`와 원시 frame은
  `temp/` 로컬 증거이므로 커밋만으로 완전 재현 가능한 proof package라고 보지는 않는다.

## [2026-06-28] E12 B8 맵 목록 source redirect CLI 리뷰 timeout

- **시도**: `temp/review_prompt_b8_map_list_source_redirect_20260628.md`로 codex/agy/claude에
  Part2 맵 목록 A2 양성/B8 음성 증거, 문서 표현 과장 여부, 커밋 가능 여부를 엄격 리뷰 요청했다.
- **결과**: 세 CLI 모두 180초 timeout으로 정상 최종 리뷰를 반환하지 못했다.
  agy stdout은 `Error: timed out waiting for response`, claude stdout/stderr는 0바이트였다.
  codex stdout은 0바이트였고 stderr 내부 로그만 남았다.
- **부분 반영**: codex stderr 로그 중 `state_016.ss0`와 raw frame이 `temp/` 로컬 증거라 커밋만으로
  완전 재현 가능한 패키지는 아니라는 지적을 확인했다. 이에 report, `todo.md`, `docs/research.md`,
  본 실패 기록에 영구 증거 범위가 report/contact 2장이라는 caveat를 추가했다.

## [2026-06-28] B84 AW1 power title 중간 실패: VRAM hook literal 정렬 오류

- **실패 증상**: `0x08B3C1DE` copy site에 후크를 붙인 뒤에도 AW1 CO 파워 컷인 제목이 대부분 비거나
  한 글자 조각만 보였다.
- **잘못된 가설**: 처음에는 32x16/16x32 타일 배치나 OBJ 팔레트 인덱스 문제로 보았지만,
  실제 원인은 후크 literal pool 정렬이었다.
- **원인 확정**: hook disasm에서 `ldr r0,[pc,#0x1c]`가 목표 literal `0x06010000`이 아니라
  `0x0000BF00`을 읽었다. `00bf00bf` 두 NOP가 literal을 `0x08F306A2`로 밀어 4바이트 정렬이 깨졌다.
- **해결**: NOP를 하나로 줄여 literal을 `0x08F306A0`에 맞췄다. 이후 `하이퍼수리` 정상 표시가 확인됐다.

## [2026-06-28] B84 AW1 power title copy-site hook 회귀: 공용 compact renderer 훅 금지

- **실패 증상**: literal 정렬을 고친 `0x08B3C1DE -> 0x08F30680` copy-site hook은 B84 컷인만 고치는 듯 보였지만,
  이후 Part1 compact 도움말 live-code evidence 재생성, `qa_visual_regions.py`, `capture_scene_screenshots.py`의 fresh
  route에서 invalid address loop(`7DC93Bxx` 계열)가 재현될 수 있었다.
- **원인 확정**: `0x08B3C1DE`는 B84 전용 copy site가 아니라 `0x08B3C184` 공용 compact renderer 내부 경로다.
  B84 파워명 외의 compact 메뉴 문자열도 이 renderer를 통과하므로, 이 지점에 원본 경로를 덮는 VRAM copy hook을
  두면 unrelated source/register 상태까지 hook이 가로챈다.
- **최종 대체**: copy-site hook을 비활성화하고 `0x08B3C1DE` bytes를 원본 prefix `500800023818`로 복원했다.
  B84 컷인은 `0x00BC9D0C` LZ77 source glyph 교체만으로 유지한다. current SHA
  `e1919e48b283026bbb353a1fb2bd623229fd1893f6dfe13c6029f778d8ed0ac1`에서 B84 body reads 157/pointer reads 2와
  `하이퍼수리` 화면 표시가 확인됐고, `qa_visual_regions.py`와 release QA가 PASS한다.
- **다시 하지 말 것**: B84 전용 조건이 레지스터/소스 포인터로 엄격히 증명되지 않는 한
  `0x08B3C184` 계열 공용 renderer copy site에 전역 hook을 붙이지 않는다. B84/B8/A2 추가 증거는
  route-specific read-watch, mutation proof, WRAM/VRAM/DMA chain으로 좁힌 뒤 처리한다.

## [2026-06-28] verify_dist_integrity current 실패: B84 수정 후 기존 증거/배포 manifest stale

- **상태**: B84 수정 후 current output SHA는 `8940784c33bf50081a1b143af34628c9f94ceebc721a7a331df9ba2df36251a9`다.
- **실패 원인**: 기존 `manifest.json`/`manifest_preview.json` 및 BPS/IPS 배포 패치가 이전 SHA
  `fb760c65...` 기준이라 stale이다. compact visual matrix의 renderer trace/xref 일부와
  Part1 compact help live-code injection report도 이전 SHA를 가리킨다.
- **확인된 OK**: 산출물 3종 full/final/title_test 바이트 동일, B팀 drift, CSV 일본어 잔존,
  text fit, override governance, repoint punctuation/integrity, CO glyph dictionary coverage는 OK로 지나갔다.
- **판정**: B84 기능 수정 실패가 아니라 release/evidence 재동기화 미완료다.
  배포 전 `prepare_patch_distribution` 및 stale evidence 재캡처/재분석을 다시 돌려야 한다.
- **후속 해결**: copy-site hook 제거 후 current SHA `e1919e48...` 기준으로 B84 read-watch, B8 manual mutation
  evidence 13건, compact matrix, scene residual, Part1 compact help evidence, dist BPS/IPS를 재동기화했다.
  `verify_dist_integrity.py`와 `run_release_qa.py`가 PASS한다. 이 실패 항목은 stale evidence/manifest를 방치하면
  배포 게이트가 실패한다는 기록으로 유지한다.

## [2026-06-28] B84 power title 후속 CLI 리뷰 timeout

- **시도**: `temp/review_prompt_b84_power_title_20260628.md`로 claude/agy에 B84 hook/LZ77/source evidence 리뷰를 요청했다.
- **결과**: claude는 180초 timeout으로 stdout/stderr 실질 결과가 없었다. agy도 180초 timeout됐고 wrapper의
  TimeoutExpired bytes 처리 오류로 substantive output이 없었다.
- **기록**: `temp/claude_review_b84_power_title_20260628.md`,
  `temp/agy_review_b84_power_title_20260628.md`.

## [2026-06-28] B84 source-only/release sync 후속 CLI 리뷰 timeout

- **시도**: copy-site hook 제거, B84 LZ77 source-only 최종 구현, current B8 manual mutation 13건 재생성,
  `verify_dist_integrity.py`/`run_release_qa.py` PASS 이후
  `temp/review_prompt_b84_source_only_release_20260628.md`로 claude/agy에 엄격 리뷰를 요청했다.
- **결과**: claude와 agy 모두 240초 timeout, stdout/stderr 0바이트였다.
- **기록**: `temp/claude_review_b84_source_only_release_20260628.md`,
  `temp/agy_review_b84_source_only_release_20260628.md`.
- **판정**: 실질 리뷰 결과가 없으므로 반영할 지적은 없다. 같은 긴 프롬프트 반복 대신, 다음 리뷰는
  “B84 source-only 결론” 또는 “E12 stale evidence 정책”처럼 질문을 더 좁혀 요청한다.

## [2026-06-28] E12 B8 작전실 DOWN16 current mutation proof 실패

- **시도**: stale SHA `3e3bae33...`의 예전 probe가 언급한 B8 작전명 후보
  `0x00B81F04`(`하늘 용사`), `0x00B81F10`(`건 파이터`), `0x00B81F24`(`개전`),
  `0x00B81F2C`(`과외수업`)을 current SHA `f95a8573...`에서 다시 확인했다.
  route는 `41_part1_operation_room` + `DOWN` 16회, expected diff box는 `0,32,80,104`다.
- **결과**: 4개 mutation 모두 null-control pixel diff 0, mutation pixel diff 0, bbox `null`이었다.
  결과 파일은 `docs/screenshots/user_report_triage_2026-06-28/e12_b8_down16_negative_summary.json`.
- **판정**: 이 route는 네 주소의 direct visual/source evidence가 아니다. 예전 stale probe는 current evidence로
  승격하지 않는다. 다만 이는 route 음성일 뿐 target 전역 미사용 증명이 아니므로, 다른 state/route에서 재시도 가능성은 남긴다.

## [2026-06-28] 사용자 스크린샷 재확인 후속 claude CLI timeout

- **시도**: `temp/review_prompt_user_screenshot_retriage_20260628.md`로 claude/agy에 좁은 리뷰를 요청했다.
- **결과**: agy는 실질 리뷰를 반환했고, "not-reproduced"보다 기존 패치가 current fresh route에서 fixed 상태로
  작동함을 명시하라는 지적과 temp 요약 영구 보존 권고를 반영했다. claude는 120초 timeout으로 stdout/stderr 0바이트였다.

## [2026-06-28] E12 current read-watch 0-hit route 재확인

- **시도**: stale였던 E12 read-watch probe를 current SHA `f95a8573...`로 모두 재실행했다.
- **음성 유지 route**: action-menu exact/range, `after_a36` action 후보, B8 `0xB83268` comm label,
  Part2 title menu sweep subset, Part2 map territory, rule-settings map-name 후보,
  B8 compact menu/war shop range, battle range/subset, external shop states,
  A2/B84 external profile states/freshrender 후보는 current SHA에서도 hit 0이다.
- **판정**: 이들은 route/subset 음성으로 유지한다. 전역 미사용 증명으로 해석하지 않으며, 실제 target-level provenance는
  fresh route, redraw가 보장되는 near-fresh state, mutation diff, 또는 WRAM/VRAM/DMA chain으로 다시 잡아야 한다.

## [2026-06-28] E12 B8 유닛/무기 duplicate route 음성 및 A2 source redirect 확인

- **시도**: Part2 map state `temp/scene_entrypoints/part2_menu_sweep/state_031.ss0`에서
  `RIGHT,A`/`DOWN,A`로 생산/유닛 정보 화면을 띄우고 B8 early unit/weapon 후보
  `0x00B81840/1854/1874/1970/1988/1A40/1A60/1A6C/1AC0/1ACC/1AD8/1B04/1B14`
  exact read-watch를 걸었다. 같은 화면은 `보병/정찰차/경전차/중전차/신형전차` 등이 실제로 보이는 화면이다.
- **B8 결과**: 위 B8 후보들은 current route에서 hit 0/direct 0이다. Part1 unit detail state
  `temp/scene_entrypoints/first_battle_day2_after_info_probe/R_START.ss0`에서도 `0x00B81B14` 등 B8 후보는
  hit 0/direct 0이었다.
- **mutation 음성**: `scene_16_part1_info_screen`에서 `0x00B81B14`(`장비 없음`)만 `검증 없음`으로 바꾼
  `tools/prove_compact_display_mutation.py` 실험은 null-control diff 0, mutation pixel diff 0이었다.
  temp summary는 `temp/e12_b8_part1_info_b81b14_mutation_20260628/summary.json`이다. 이 0-diff 결과는
  route 음성이므로 success-tier screenshot으로 승격하지 않는다.
- **대체 source 양성**: 같은 Part2 생산/유닛 route에 A2 unit source 후보
  `0x00A29390/939C/93A8/93B0/93B8/93C0/93E8/93F8/9414/9438/9458/9464/94E4`
  exact watch를 걸자 493 hit가 발생했다. target span 기준으로 `0x00A29390`(`보병`) 75회,
  `0x00A293A8`(`중전차`) 58회, `0x00A293B0`(`경전차`) 48회,
  `0x00A2939C`(`신형전차`) 19회가 읽혔다. raw evidence는
  `data/e12_a2_unit_info_source_redirect_current.json`에 보존했다.
- **판정**: 이 화면 계열에서 B8 early unit/weapon duplicate를 source로 보지 않는다. 현재 보이는 생산/유닛
  정보 화면은 A2 source를 읽는 redirect proof가 있으므로, 동일 state+입력+B8 exact watch 반복은 중단한다.
  단, 이는 B8 early unit/weapon의 전역 dead-copy 증명이 아니다. 전역 dead로 격상하려면 pointer-ref disasm,
  pointer poisoning/body mutation의 화면 무변화, 또는 WRAM/VRAM write-chain으로 실제 대체 source를 더 넓게 확정해야 한다.

## [2026-06-28] E12 B8 route/dead-copy 후속 CLI 리뷰

- **시도**: `temp/review_prompt_e12_b8_route_deadcopy_20260628.md`로 agy/claude/codex에 B8 비작전실 0-hit,
  dead-copy 판단 기준, 다음 route 우선순위를 좁혀 엄격 리뷰를 요청했다.
- **결과**: agy와 claude는 실질 리뷰를 반환했다. codex는 180초 timeout(rc 124)으로 최종 리뷰 본문이 없고
  stderr에는 도구 실행 로그만 남았다.
- **반영한 지적**: 두 리뷰 모두 static editor 노출 459건을 live source로 과장하지 말 것,
  0-hit route 반복보다 positive source identification/WRAM·VRAM write-chain을 우선할 것,
  `0xB81B14` 0-diff 이미지는 success-tier evidence로 커밋하지 말 것을 지적했다.
- **다음 기준**: 이미 0-hit가 난 생산/유닛/시스템/에디트 steady-state route는 새 differentiator
  (scene-load 전환 순간 watch, 다른 sub-panel 도달, pointer/body mutation, 대체 source positive ID)가 없으면
  반복하지 않는다. 다음 probe 우선순위는 전투 데미지 예측/무기 상세의 write-chain 또는 positive source ID다.

## [2026-06-28] E12 A2 profile selector scan 한계

- **시도**: `state_036.ss0`의 RAM diff에서 `RIGHT`/`RIGHT` 전환과 함께
  `0x0200D63E`가 `0x01 -> 0x02 -> 0x01`로 움직이는 것을 잡고, redraw 직전에 이 byte를
  `0x00..0x1F`로 바꿔 A2 CO profile power-name read-watch를 돌렸다.
- **성공 범위**: 값 `0x00/01/02/03/0C`와 power row 1/2 조합으로 10개 target
  (`0x00A2955C/70/88/98/AC/C0/D8/EC/9810/9824`)은 current ROM source read가 확인됐다.
- **실패/한계**: 여러 값이 `기적/별꿈`으로 alias되고 일부 값은 hit 0이었다. 따라서 이 scan은
  RAM-field selector source proof 10/36일 뿐, 자연 all-CO route나 A2 36개 visual-layout proof가 아니다.
  나머지 26개는 별도 selector 의미 해석, 다른 state, 또는 WRAM/VRAM write-chain 증거가 필요하다.
- **기록**: 영구 slim evidence는
  `data/compact_display_read_watch_a2_profile_selector_0200d63e_current.json`, 전체 임시 scan은
  `temp/e12_a2_profile_ram_selector_0200d63e_values_20260628/summary.json`.
- **후속 해결**: 이 한계는 `0x0200D63E`가 selected record index/alias 성격이라 생긴 것이었다.
  후속 RE에서 실제 power-name 선택 byte가 selected record의 `co_id`임을 확인했다.
  현 `state_036.ss0`에서는 `0x020231B0 + 0x1d = 0x020231CD`지만, 이는 breakpoint로 재도출해야 하는 state-local live address다.
  `tools/probe_a2_profile_coid_power_reads.py`가 A2 target 36/36 direct read proof를 확보했다.
  따라서 이 항목은 `0x0200D63E` scan 자체의 한계 기록으로만 유지한다.

## [2026-06-28] E12 B8 comm wait `state_011` 단순 입력 0-hit

- **시도**: `scene_23b_part2_comm_multiplayer` 계열 microprobe contact를 기준으로 B8 comm wait 후보
  `0x00B83268/322C/3160/2F7C/306C/310C`를 exact read-watch했다.
  입력은 `A`, `B`, `A,B`, `B,A`, `LEFT,B`, `RIGHT,B`, `DOWN,B` 7케이스다.
- **결과**: 모든 케이스 hit 0/direct 0이다. 결과 파일은
  `temp/e12_b8_comm_wait_state011_*_20260628.json`, contact는
  `temp/e12_comm_menu_state011_microprobe_20260628/contact.png`.
- **판정**: 이 state와 단순 전환 입력은 위 B8 comm wait 후보의 source 증거가 아니다. 단, route/subset
  음성이므로 B8 comm wait 문자열의 전역 dead-copy 증명은 아니다. 다음에는 화면 전환 직전 write-chain,
  다른 통신 대기 state, 또는 대체 source positive ID를 우선한다.

## [2026-06-28] E12 B8 작전실 추가 스크롤 및 전투 state broad scan 음성

- **작전실 DOWN 재확인**: 기존 DOWN16 음성이 스크롤 카운트 오차인지 확인하려고
  `41_part1_operation_room` fresh route 뒤 `DOWN` 14~18회에서
  `0x00B81F2C`(`과외수업`), `0x00B81F24`(`개전`),
  `0x00B81F10`(`건 파이터`), `0x00B81F04`(`하늘 용사`)을 각각 같은 슬롯 길이 mutation으로 바꿨다.
  모든 카운트/주소 조합이 pixel diff 0이었다.
- **작전실 UP 재확인**: 반대 방향 wrap/후반 미션 노출 가능성을 보려고 `UP` 1~6회에서
  `0x00B82024`(`라스트 미션`), `0x00B82038`(`파라파라 제도`),
  `0x00B8204C`(`비경의 숲`) mutation을 돌렸지만 모두 pixel diff 0이었다.
- **broad state read-watch**: freebattle after-attack/endturn, first-battle unit/info, system surrender,
  freebattle start, second-mission battle 계열 savestate 24개에 B8 whole range `0x00B81800..0x00B85000`
  read-watch를 30프레임씩 걸었다. 결과 hit 0/direct 0이다.
- **기록**: `temp/e12_b8_operation_scan_down*_20260628/summary.json`,
  `temp/e12_b8_operation_scan_up*_20260628/summary.json`,
  `temp/e12_b8_broad_state_scan_20260628.json`.
- **판정**: 위 route들은 B8 direct evidence 후보에서 제외한다. 전역 dead-copy 증명은 아니며,
  다음 B8 증거 확보는 같은 steady-state 반복이 아니라 scene-load 전환 순간 watch, 실제 target row가 노출되는
  진행도 save, 대체 source positive ID, 또는 WRAM/VRAM write-chain으로 해야 한다.

## [2026-06-28] E12 A2 co_id proof Claude 리뷰 timeout

- **시도**: `temp/review_prompt_e12_a2_coid_20260628.md`로 A2 selected-record `co_id` source proof 36/36,
  matrix 표현, RAM 주소 fragility, representative hit 방식에 대해 claude/agy 엄격 리뷰를 요청했다.
- **결과**: agy는 실질 리뷰를 반환했고 지적을 반영했다. Claude는 `gtimeout 180 claude -p ...`에서
  rc 124 timeout, stdout/stderr 0바이트였다.
- **기록**: `temp/claude_review_e12_a2_coid_20260628.md`,
  `temp/claude_review_e12_a2_coid_20260628.err`,
  `temp/agy_review_e12_a2_coid_20260628.md`.

## [2026-06-28] `scene_24` A3 룰 라벨 일본어 재출현을 ROM 회귀로 보는 판정

- **시도/오판 위험**: `scene_24_part2_campaign_map`의 UI 에디터 캡처에서
  `日数/攻め/収入/能力/アニメ`가 보여 A3 raw OBJ 패치가 회귀한 것처럼 보였다.
- **반증**: current ROM raw 영역은 이미 한글 라벨/값 데이터로 패치되어 있고, 같은 입력을
  coldboot fresh route로 재생하면 `정찰/날씨/수입/일수/우세/능력/애니`가 정상 표시된다.
- **판정**: 문제는 ROM 패치가 아니라 stale savestate checkpoint였다. provenance의 ROM SHA가 current여도
  savestate VRAM이 구 일본어 그래픽을 보존할 수 있으므로, 이 화면은 savestate 캡처만으로 결함 판정하지 않는다.
- **재시도 금지**: `scene_24`/`scene_24b`의 일본어 룰 라벨을 근거로 `0x45D334..0x45DC74` raw OBJ를
  다시 덮어쓰기 전에 반드시 `data/screen_checkpoints.json`의 fresh checkpoint 또는 coldboot 재생 캡처를 먼저 확인한다.
  정식 증거는 `docs/screenshots/scene24_fresh_checkpoint_fix_2026-06-28/contact.png`.
- **CLI 리뷰**: `agy`는 stale savestate 제거/커밋 가능 판정. `claude`는 180초 timeout(stdout/stderr 0B),
  `codex`도 180초 timeout(stdout 0B, stderr는 하니스/도구 로그 위주로 실질 finding 없음).

## [2026-06-28] E12 B8 `0x08D84830` table-head steady-state breakpoint 0-hit

- **시도**: B8 unit/weapon rows의 source를 찾기 위해 `0x08D84830` table-head literal loader 99개에
  exec breakpoint를 걸고, unit detail/battle/attack/object-label/day-overlay/system/shop/map/operation-room
  후보 13개 checkpoint를 실행했다.
- **결과**: 전 케이스 hit 0이다. 증거는
  `docs/screenshots/e12_b8_d84830_table_head_negative_2026-06-28/report.json`.
- **판정**: 캡처된 실행 구간에서는 `0x08D84830` loader PC가 실행되지 않았다. 단, B8 unit/weapon table의
  전역 dead-copy 증명이 아니고, 특히 `frames:1` savestate 케이스는 state 캡처 전 loader 실행 가능성을
  배제하지 못하므로 success 증거로 승격하지 않는다.
- **재시도 금지**: 새 화면 진입점, scene-load 순간 breakpoint, 실제 target row 노출 state, 또는 WRAM/VRAM write-chain
  없이 같은 13개 화면에서 같은 table-head loader breakpoint를 반복하지 않는다.
- **주의**: raw probe의 `scene_24/24b` 케이스는 fresh checkpoint 승격 전 candidate route다. 이 기록은
  반복 방지용 0-hit triage이며, fresh visual proof나 전역 dead-copy 판정으로 사용하지 않는다.
- **CLI 리뷰**: agy/claude는 커밋 차단 없음으로 판정했다. claude가 지적한 `frames:1` savestate 한계,
  per-case provenance 보존, 131 literal 수치의 근거 경계를 반영했다. codex는 180초 timeout(stdout 0B)으로
  실질 finding이 없었다.

## [2026-06-28] E12 B8 rule-label / AW1 power-route 추가 음성

- **fresh rule-settings mutation 0-diff**: `scene_87_common_rule_settings`에서
  `0x00B839A8/39E0/39F0/39D0`(`거점수입/날씨/룰/사령브레이크`)를
  `검증*` 문자열로 바꿔도 null-control diff 0, mutation diff 0이었다. 이 fresh rule-settings route는
  해당 B8 rows의 source 증거가 아니다.
- **AW1 power-route exact watch 0-hit**: B84 `0x00B84F04`가 157회 read되는 동일 AW1 `DOWN,DOWN,A`
  파워 발동 route에서 B8 power-dialogue 후보 `0x00B83A3C/3A64/3A98/408C/4154`는 슬롯 전체 exact watch가
  모두 hit 0이었다. 이 route는 B84 title proof이지 B8 power-dialogue proof가 아니다.
- **range-watch 오해 금지**: B8 전체 range watch는 475,509 hit가 나오지만 code/pointer 인접 read를 target span으로
  잘못 분류하는 노이즈가 크다. B8 성공 증거는 whole-range hit가 아니라 target-slot exact watch, mutation diff,
  또는 WRAM/VRAM write-chain으로만 인정한다.
- **증거**: `docs/screenshots/e12_b8_additional_route_negatives_2026-06-28/report.json`.
- **CLI 리뷰**: agy는 커밋 차단 없음으로 판정했다. codex/claude는 180초 timeout(stdout 0B)으로 실질 finding이 없었다.
