# Game Boy Wars Advance 1+2 — 한글화 PREVIEW (2026-05-26)

> **위상**: 데이터-only **기술검증 빌드(preview)**. 대화/메뉴/이름입력에서 한글 렌더 확인.
> **풀게임 완성판이 아님** — 아래 한계/잔여 QA 참조.

## 적용 방법
1. 원본 ROM 준비: `Game Boy Wars Advance 1+2 (Japan).gba`
   - sha1 `0e805762d02df41a7c1f840569d17efb2fb92b1c`, crc32 `49ee1fdd`, 16,777,216 bytes
2. [Floating IPS(flips)](https://www.romhacking.net/utilities/1040/) 또는 beat 등 BPS 패처로
   `game_wars_korean_full_preview_2026-05-26.bps` 를 원본에 적용.
3. 결과 패치본: sha1 `66f031a03d53da51ea00f976fe58452dc9a8bdd7` (16MB).
4. mGBA/실기에서 실행.

## 구현 요약 (데이터-only, ASM 무수정)
- per-char 텍스트 변환루틴(ROM 0x08EFE788)의 FONT_BASE를 0x08F00000으로 repoint, 원본 폰트 48KB 복사.
- 한글 800 dedup 글리프(Galmuri11-Condensed, ink10) 주입 + 한자 테이블 536→1566엔트리 확장.
- 번역문을 예약 SJIS 코드로 인코딩(한글=2B, ASCII=1B, 일본어 잔여=원본 SJIS).
- 헤더 무변경(체크섬 0xBD 유효), 16MB 유지 → 실기 부팅 안전.

## 현재 커버리지
- **한글 인코딩 적용: 13,280행** / 슬롯초과로 원문(일본어) 유지: **2,322행** / 코드영역·미추출: 약 2,700행.
- 검증된 화면: 타이틀→게임선택→인트로 대화→이름입력 UI(한글 정상, 색·간격·받침 OK, 글리프매핑 오류 없음).

## 알려진 한계 / 잔여 QA (중요)
1. **잔존 일본어 2,322행**: 한국어가 원본 슬롯보다 길어 안전하게 원문 유지(인접손상 방지). 주로 타이트한
   메뉴/스탯/튜토리얼. 우선순위 목록: `dist/overflow_priority_report.csv`. 반복 문자열(예 "할 수 있다."×33)을
   짧게 고치면 다수 행 일괄 해소. **번역 축약은 품질 판단이 필요해 수동 권장.**
2. **공백이 좁게(ASCII) 렌더** — 한글 단어 간격이 빽빽. polish 여지(가독성엔 무리 없음).
3. **🔴 깊은 게임플레이 미검증(최우선 실기 확인)**: 첫 **전투/맵 UI**(유닛 상태창·이동/공격 예측창·맵 명령창)가
   대화와 동일 렌더 경로인지 미확인. **권장 smoke test**: 새 게임 → 이름입력 통과 → 첫 맵 진입 → 유닛 선택 →
   이동/공격 예측창 → 턴 종료. 여기서 한글이 정상이면 풀게임 신뢰도 크게 상승.
   (별도 bulk-DMA 폰트 업로드 경로가 있어, 그 경로로 렌더되는 화면은 일본어로 남을 수 있음.)
4. **제어코드 의미보존**: 슬롯 바이트 내 기록이라 인접손상은 없으나, 페이지넘김/선택지/변수삽입 등 흐름은 미전수검증.

## 재현 (개발자)
```bash
python tools/build_korean_full.py            # output/game_wars_korean_full.gba
python tools/make_bps.py "<원본>" output/game_wars_korean_full.gba <out.bps>
python tools/qa_text_fit.py                   # byte budget/박스폭 QA
```
