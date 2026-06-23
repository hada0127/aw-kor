# Failure Log — 시도했으나 실패한 방법과 사유

> 같은 벽에 다시 부딪히지 않기 위한 기록. 작동한 방법은 [success.md](success.md) 참조.

---

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
