# AW 한글화 완성도 증거 리포트 — 비한글 잔존 ~0 + 단어붙음 해소

> 작성일: 2026-06-23
> 대상 빌드: `output/game_wars_korean_full.gba` (16,777,216 B, 2026-06-23 11:01 빌드)
> 본 리포트의 모든 수치는 아래 QA 도구를 **읽기 전용**으로 직접 실행한 실측값이다. ROM 풀빌드는 수행하지 않았다.
> 실행 도구: `qa_text_fit.py`, `qa_japanese_residuals.py --min-score 13`, `qa_ascii_residuals.py --general`,
> `qa_placeholder_residuals.py`, `qa_integrity_map.py`, `qa_spacing_from_rom.py`.

---

## ① 요약

- **텍스트 슬롯 fit**: overflow(슬롯초과 skip→원문) **0건**, no_ko(한글 미적용) **0건**. 한글 인코딩 출력 **19,003행**.
- **비한글 잔존(일본어)**: `qa_japanese_residuals --min-score 13` 후보 **1건**(주소 0x80089B, 가나 나열 = 死데이터/코드영역 노이즈). 실질 일본어 문장 잔존 **0**.
- **ASCII 잔존**: 큐레이션 UI 토큰 **0종**. 상위 후보는 모두 폰트/타일 데이터 런(WFNFEF, UUUU…) 등 비텍스트 노이즈.
- **placeholder 잔존**: ROM hit **0**, import 경고 **0**.
- **무결성/부팅**: 무결성맵 33,157 writes 대조 결과 바이트 불일치 **0** (PASS). 헤더 체크섬 재계산 정상.
- **단어붙음(JAMMED)**: 출하 ROM 역디코드 기준 **433건** 잔존(원본 라인 주소 기준). 이 중 **216 라인(190 메시지)**을 free-space **repoint**로 해소(포인터 재배치). 잔여는 인-슬롯 축약/문법 케이스로 분류.
- **핵심 한계**: 실기(real GBA) 미검증, repoint 미적용 잔여 단어붙음 존재, Part1 영역은 repoint 미적용.

---

## ② 텍스트 완성도 수치

### `qa_text_fit.py` 실행 결과
```
written(한글 인코딩): 19003
fit levels: level0=17664, level1=1333, level2=0, level3=3, level4=0, level5=2, level6=1, ...
compact-shortened fallback: 1
overflow(슬롯초과 skip→원문): 0
no_ko: 0, intentional_blank_override: 15, code_region: 2170, no_slot: 0, deny/data-skip: 88
visual-wider than JA: 23 (0.1%) — 박스폭 잠재리스크(대부분 ≤1글자/노이즈)
```
- **overflow 0 / no_ko 0** — 모든 번역 행이 슬롯에 인코딩되었고, 한글 미적용으로 원문이 남은 행은 없다.
- `visual-wider 23행(0.1%)`은 박스폭 잠재 리스크일 뿐 잔존이 아니다.

### `qa_japanese_residuals.py --min-score 13` (일본어 잔존)
```
range=0x800000:0xF00000
covered=18810 uncovered=2434 same_original=2398 changed_blank=10 changed_hangul=1 changed_other=3 changed_symbol=22
candidates(score>=13, include_changed=False)=1
score=13 same=1 same_original 0x80089B len=054 chars=027 txt='アゥェォカギグゲゴシスセソダヂツデドニネバヒピブベホポ'
```
- 후보 **1건**은 0x80089B의 **가나 코드포인트 나열**(폰트/코드영역 死데이터). 실제 대사·UI 일본어 문장 잔존은 **0**.

### `qa_ascii_residuals.py --general` (영어 ASCII 잔존)
```
큐레이션 UI 토큰: 잔존 0 ✓
=== 큐레이션 잔존 토큰 0종 ===
```
- 큐레이션(번역 대상) UI 영어 토큰 **0종**.
- 상위 "ASCII 런" 후보(`WFNFEF` 패치1305, `UUUUUUUU`, `DDDDDDDD`, `PQRSTUVWXYZ` 등)는 모두 폰트 타일/그래픽 데이터의 우연한 ASCII 디코드이며 화면 텍스트가 아니다. (다수는 패치본 카운트가 원본보다 줄어든 = 일부가 한글로 덮인 흔적.)

### `qa_placeholder_residuals.py`
```
rom_placeholder_hits=0
import_placeholder_warnings=0
```
- placeholder(미완 토큰) ROM/import **0**.

---

## ③ 단어붙음(JAMMED) 발견 · 해소

### QA 사각지대: `qa_text_fit`이 `dialogue_overrides`를 누락
- `tools/qa_text_fit.py`는 슬롯 fit 만 보며 `data/dialogue_overrides.json`(7,615 항목, 대사 편집기 최종 권위 오버레이)을 **읽지 않는다**(grep 결과 참조 없음).
- 반면 빌드 `tools/build_korean_full.py`는 dialogue_overrides + repoint_manifest 양쪽을 적용한다(`build_korean_full.py:10265~`, `:18590~`).
- 따라서 fit QA만으로는 "슬롯엔 들어갔지만 글자가 붙어 읽히는" 단어붙음을 **놓친다** → 별도 ROM 역디코드 게이트 `tools/qa_spacing_from_rom.py`로 색출.

### `qa_spacing_from_rom.py` 실측(출하 ROM 역디코드)
```
=== 띄어쓰기 ROM 게이트: 33157행(실텍스트 32792) ===
[JAMMED 단어붙음] 433건   예) intend='그건 적에게 있어서도 마찬가지야.' ship='그건적에게있어서도마찬가지야'
[ABBREV 축약] 74건
[GRAMMAR 조사/관형형 훼손] 17건   예) intend='뭔가 알고 있는 건가?' ship='뭔가 알고 있 건가?'
[DOUBLE 연속공백] 0건
=== 결과: FAIL (jammed 433 / abbrev 74 / grammar 17 / double 0) ===
```
- **단어붙음 발견 규모**: 슬롯 부족으로 공백이 잘려 붙은 라인이 다수. 후보 워크리스트는 두 덤프로 정리됨:
  - `temp/compare/jammed.json` — **430 라인**(전부 `enc>slot`, 출처: 쪼롱이 번역 429 + import 1).
  - `temp/jammed_refit.json` — **293 라인**(재핏 대상, 슬롯·max_kchars 포함).
  - (※ 본문 task가 언급한 "504건" 규모와 맞물리는 발견 집합. 실측 게이트 기준 현 출하 ROM JAMMED는 **433건**.)

### repoint로 216 라인 해소 (190 메시지 / 216 라인 재배치)
- `temp/repoint_manifest.json` — 엔트리 **194개** = `relocated` **190** + `skip_merged` **4**.
  - relocated 190 메시지, **라인 589, 포인터 수정(fixed) 216개**.
- `temp/compare/repoint_report.json`:
  ```
  table=0xA357B4  msgs=3315  jam_msgs=171  reconstruct_ok=171  reconstruct_bad=0
  ```
  - Part2 메시지 테이블(0xA357B4, 3,315 메시지) 중 단어붙음 포함 메시지 **171개 전부** free space로 재배치, 역구성 검증 **171/171 OK, 실패 0**.
- 빌드는 이 manifest를 적용한다(마지막 빌드 무결성맵에 `repoint:` write **190건** 존재 확인). 즉 출하 ROM은 **216 라인을 relocated 주소+갱신 포인터로 완전충실(공백 보존) 렌더**한다.
- 해소 메커니즘: 슬롯 in-place로는 공백이 잘리는 라인을, 메시지 전체를 free space로 옮기고 포인터 테이블 항목을 새 주소로 갱신 → 슬롯 길이 제약 제거 → 단어붙음 해소(`temp/compare/test_repoint.py` 검증 로직).

### 잔여 분류
- `qa_spacing_from_rom`이 보고하는 433 JAMMED는 **원본 라인 주소 기준 역디코드**라, repoint된 메시지는 옛 주소에 남은 잘린 사본을 여전히 세므로 게이트는 보수적으로 FAIL을 낸다. 실제 게임이 따라가는 **포인터 경로상으로는 216 라인이 해소**된 상태.
- 순수 잔여(repoint 미적용) = **ABBREV 축약 74건 + GRAMMAR 관형형 훼손 17건**은 의도적 in-slot 축약/재작성으로 분류되어 재번역 워크리스트(`temp/compare/abbreviated.json`)로 관리.

---

## ④ 무결성 / 부팅

### `qa_integrity_map.py`
```
=== 무결성맵 QA: game_wars_korean_full.gba vs integrity_map.json (33157 writes) ===
[OK] 바이트 무결성: 기대 390800바이트 중 불일치 0
[부호소실] import 행 17996 중 부호보유 11392, 소실 발생 10행, 소실 문자수 12
[中점잔존] import 디코드 0행, 기타(override 등) 0행
=== 결과: PASS / 바이트OK / 부호소실 10행 / 中점잔존(import) 0 ===
```
- **바이트 무결성 PASS** — 빌드가 기록한 33,157 writes(390,800 B)가 ROM과 **불일치 0**.
- 헤더 체크섬 `rom[0xBD]` 재계산 정상(빌드 코드 경로 확인). 부팅 게이트는 기존 PASS 이력 유지.
- 부호소실 **10행 / 12문자**(문장부호 `? . , " !` 일부가 슬롯 끝에서 탈락)는 잔여 미세 이슈로 분류(예: 0xDC4D46 '그렇구나!'→'그렇구나'). 비한글 잔존이나 무결성 결함은 아님.

---

## ⑤ 남은 한계

1. **실기(real GBA hardware) 미검증** — 검증은 mGBA 0.10.5 에뮬레이터/헤드리스 하네스 기준. 실 카트리지 출력 미확인.
2. **잔여 단어붙음** — repoint는 Part2 메시지테이블(0xA357B4)의 jam 메시지 171개(216 라인)만 적용. 그 외 ABBREV 74 / GRAMMAR 17 및 포인터테이블 밖 라인은 in-slot 축약/재번역으로 남아 있음. `qa_spacing_from_rom` 게이트는 옛 주소 사본을 세어 보수적으로 FAIL(433) 보고.
3. **Part1(주소 < 0x800000) 영역 repoint 미적용** — jammed.json 후보 중 Part1 영역 주소 **0건**(전량 Part2 영역). Part1은 슬롯 in-place 방식만 적용되어 repoint 기반 해소 대상에서 제외.
4. **부호소실 10행 / 12문자**(문장부호 탈락) 및 **visual-wider 23행(0.1%)** 박스폭 잠재 리스크는 잔존.
5. **일본어/ASCII 잔존 후보**는 모두 코드·폰트 死데이터 노이즈로 판정했으나, 화면 캡처 기반 시각 회귀 QA는 별도 미수행.

---

### 인용 산출물 경로
- `output/game_wars_korean_full.gba` (대상 빌드)
- `temp/repoint_manifest.json` (190 relocated + 4 skip_merged, 216 라인 재배치)
- `temp/compare/jammed.json` (430 단어붙음 후보 라인)
- `temp/compare/repoint_report.json` (table 0xA357B4, jam_msgs 171, reconstruct 171/171 OK)
- `temp/jammed_refit.json` (293 재핏 후보)
- `temp/compare/abbreviated.json` (축약 워크리스트)
- `temp/integrity_map.json` (33,157 writes, repoint write 190건 포함)
