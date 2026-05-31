# AW Korean Patch 통합 TODO

이 파일 하나를 현재 진행 기준으로 사용한다. 이전 진행 문서인
`.claude/todo.md`와 `docs/plan.md`는 이 파일로 통합했으며, 혼선을 막기
위해 `docs/plan.md`는 제거했다. 앞으로 작업 상태와 완료 기준은 이
파일만 갱신한다.

과거 장기 계획과 상세 조사 기록은 git history, `docs/success.md`,
`docs/fail.md`, `docs/research.md`에 남겨 둔다. 이 파일은 지금 해야 할
작업과 완료 판단에만 집중한다.

## 최종 목표

- [ ] 캠페인 전체 한글화 완료.
- [ ] 전투 화면, HUD, 메뉴, 팝업, 결과 화면 한글화 완료.
- [ ] 튜토리얼 구간을 먼저 끝까지 검수하고, 실제 화면 기준으로 깨짐을 제거.
- [ ] `full`, `final`, `title_test` 산출물이 같은 한글화 상태로 빌드되도록 정리.
- [ ] 잔여 일본어, 깨진 글자, 잘린 문장, 잘못된 색상/스프라이트를 제거.
- [ ] 최종 BPS/IPS 패치 생성 및 round-trip 검증.

## 현재 기준 산출물

- `output/game_wars_korean_full.gba`
- `output/game_wars_korean_final.gba`
- `output/game_wars_korean_title_test.gba`
- `tools/build_korean_full.py`
- `tools/build_title_hangul.py`

## 최근 완료

- [x] 전체 한글 예약코드/글리프 기반 빌드 파이프라인 구축.
- [x] Part 1 대화 ASM hook과 Part 2 tilemap/glyph-cache renderer hook 적용.
- [x] 이름 입력 그리드 A-Z/a-z/0-9 표시와 미리보기 흐름 안정화.
- [x] GBA 헤더 체크섬 QA를 `0xA0..0xBC` inclusive 기준으로 정리.
- [x] 타이틀/선택 화면 한글 로고 방향 정리 및 기본 색상/배치 조정.
- [x] Part 2 지도/미션/레벨/체크/캐서린 등 주요 OBJ 라벨 일부 한글화.
- [x] Part 2 튜토리얼 초반 커서/보병/수송차/이동/점령/지형/자주포/맥스/수송헬기 구간 문장 깨짐 교정.
- [x] Part 2 `0xA06B80-0xA14000` 구간의 일본식 말줄임표, 장음 기호, 미매핑 보조 번역을 정리.
  - ROM 디코드 감사 기준 `0xA06B80-0xA14000` bad=0, blank=0.
- [x] `docs/plan.md`를 제거하고 진행 기준을 루트 `todo.md` 하나로 통합.
- [x] Part 2 `0xA14000-0xA30000` 구간의 CSV 텍스트 슬롯 기준 잔여 일본어/깨짐 후보 정리.
  - CSV 슬롯 감사 기준 `0xA14000-0xA30000` bad=0.
  - `0xA2CAA4` blank 1개는 전각 공백 전용 슬롯이라 표시 문자열 대상에서 제외.
- [x] Part 2/캠페인 추가 슬롯 정리.
  - CSV 슬롯 감사 기준 `0xA30000-0xA80000` bad=0, blank=0.
  - CSV 슬롯 감사 기준 `0xE00000-0xE10000` bad=0, blank=0.
  - `D8Fxxx` 공격 튜토리얼의 복합 행은 행 단위 패치 기준으로 확인하고, CSV 슬롯 중간 읽기 false positive는 제외.
- [x] 최근 빌드 검증:
  - `python3 -m py_compile tools/build_korean_full.py`
  - `python3 tools/build_korean_full.py --out output/game_wars_korean_full.gba`
  - `python3 tools/build_title_hangul.py --input output/game_wars_korean_full.gba --output output/game_wars_korean_final.gba`
  - `cp output/game_wars_korean_final.gba output/game_wars_korean_title_test.gba`
  - `python3 tools/qa_text_fit.py`
  - `python3 tools/phase6_basic_test.py output/game_wars_korean_full.gba`
  - `python3 tools/phase6_basic_test.py output/game_wars_korean_final.gba`
  - `git diff --check`

## 현재 우선순위

1. [ ] Part 2 튜토리얼을 끝까지 실제 화면 기준으로 검수한다.
2. [ ] `D8Fxxx-DCxxxx` 튜토리얼/전투 설명과 `E10000` 이후 실제 대사 후보를 CSV 슬롯/실제 화면 기준으로 계속 확인한다.
3. [ ] 전투 진입/진행 중 충돌 여부를 재검증하고, 충돌이 남아 있으면 먼저 수정한다.
4. [ ] `예/아니오`, `vwxy`, 대사 끝 하얀 픽셀 깨짐, 회색 글자 변화 문제를 회귀 검증한다.
5. [ ] 튜토리얼을 통과한 뒤 Part 2 본편 캠페인/전투 화면 전체로 확장한다.
6. [ ] Part 1 본편 캠페인/전투 화면 전체로 확장한다.

## 작업 루프

각 한글화 변경은 아래 순서로 처리한다.

1. `data/game_wars_found_texts.csv`와 실제 ROM 디코드로 대상 주소를 확인한다.
2. 화면 상태 파일이나 mGBA 캡처로 실제 출력 경로를 확인한다.
3. `tools/build_korean_full.py`에 주소 고정 override, raw replacement, OBJ/BG 그래픽 패치를 추가한다.
4. `output/game_wars_korean_full.gba`를 재빌드한다.
5. `output/game_wars_korean_final.gba`와 `output/game_wars_korean_title_test.gba`도 같은 상태로 맞춘다.
6. 아래 검증을 통과시킨다.
   - `python3 -m py_compile tools/build_korean_full.py`
   - `python3 tools/qa_text_fit.py`
   - `python3 tools/phase6_basic_test.py output/game_wars_korean_full.gba`
   - `python3 tools/phase6_basic_test.py output/game_wars_korean_final.gba`
   - `git diff --check`
7. 필요한 경우 mGBA 상태 파일로 직접 화면을 확인하고 스크린샷을 남긴다.
8. 검증된 변경만 커밋한다.

## 남은 큰 항목

- [ ] Part 2 튜토리얼 잔여 대사 전체 검수 및 깨짐 수정.
- [ ] Part 2 튜토리얼 전투 화면 명령, 메뉴, 도움말, 팝업 검수.
- [ ] Part 2 본편 캠페인 대사 전체 플레이스루 검수.
- [ ] Part 2 본편 전투 HUD, OBJ 라벨, 결과 화면, 상점, CO 정보 검수.
- [ ] Part 2 컴패니언/작전실/오퍼레이션 선택 화면 잔여 그래픽 한글화.
- [ ] Part 1 본편 캠페인 대사 전체 플레이스루 검수.
- [ ] Part 1 본편 전투 HUD, OBJ 라벨, 결과 화면, 작전실, 상점, CO 정보 검수.
- [ ] 1+2 선택 화면, 1편 본편, 2편 본편의 타이틀/시작 텍스트 스타일 재검증.
- [ ] final/title_test/full 산출물 간 한글화 차이 제거.
- [ ] 배포 전 BPS/IPS 재생성, manifest 갱신, round-trip 검증.

## 문서 규칙

- 진행 상태는 이 파일만 수정한다.
- `docs/plan.md`는 되살리지 않고, `.claude/todo.md`에는 새 체크리스트를 추가하지 않는다.
- 오래된 상세 기록이 필요하면 git history에서 이전 `docs/plan.md`와 `.claude/todo.md`를 확인한다.
