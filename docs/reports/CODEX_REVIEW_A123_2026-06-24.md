**결론**

A2 hook의 Thumb 정렬, 복귀주소, `r4=space-1` 보정 자체는 맞습니다. 실제 ROM 기준 `0x8140` 리터럴은 `0x08F3042C`, ret1은 `0x08F30430`, ret2는 `0x08F30434`에 정렬돼 있고, 비공백은 `0x0831BD04`, 공백은 원본 `bl 0x831bbdc` 위치인 `0x0831BD10|1`로 복귀합니다. 연속 공백, 후미 공백, NUL 직전 공백도 이 루프에서는 깨지지 않습니다.

**실제 지적**

1. **A2 hook 전제가 불완전합니다.**
   같은 A2 맵명 테이블에 `"4Ｐ 맵"`이 있고 [data/dialogue_overrides.json](/Users/tarucy/project/aw-kor/data/dialogue_overrides.json:2716), 현재 인코더는 ASCII를 1바이트로 냅니다 [tools/build_korean_full.py](/Users/tarucy/project/aw-kor/tools/build_korean_full.py:9353). 실제 출하 ROM도 `0xA2CC0C = 34 82 6f ...`입니다. 즉 `0x20`만 문제가 아니라 “1바이트 코드가 2바이트 소비 루프에 들어감”이 문제입니다. 이 행이 0x831Bxxx 경로에 타면 여전히 misalignment 후보입니다. 원본은 `４Ｐ...`로 2바이트였습니다 [data/game_wars_found_texts.csv](/Users/tarucy/project/aw-kor/data/game_wars_found_texts.csv:16235). 최소 수정은 `"４Ｐ 맵"`으로 바꾸거나, A2 hook을 모든 ASCII 1바이트 처리로 일반화하는 겁니다.

2. **“B팀 drift 0”은 B팀 보호 증거로 부족합니다.**
   `qa_bteam_drift.py`는 `dialogue_overrides.json` 값만 baseline과 비교합니다 [tools/qa_bteam_drift.py](/Users/tarucy/project/aw-kor/tools/qa_bteam_drift.py:64). 렌더러가 공백을 `?`로 깨뜨리거나, 인코딩 단계가 반각/전각/패딩을 바꿔도 소스 JSON이 같으면 통과합니다. 이번 A2 공백 hook은 B팀 문구를 고친 게 아니라 표시를 의도대로 복구한 것이므로 위반은 아닙니다. 다만 “drift 0이라 안전”이라는 수락 논리는 틀렸습니다.

3. **A3 raw OBJ overwrite는 원본 시그니처 assert가 없습니다.**
   A1 CO OBJ는 LZ77 decompress size와 overflow를 검사합니다 [tools/build_korean_full.py](/Users/tarucy/project/aw-kor/tools/build_korean_full.py:8742). 반면 A3 라벨/값은 고정 offset에 바로 씁니다 [tools/build_korean_full.py](/Users/tarucy/project/aw-kor/tools/build_korean_full.py:8787), [tools/build_korean_full.py](/Users/tarucy/project/aw-kor/tools/build_korean_full.py:8853). 현재 원본 ROM 기준으론 맞아 보이지만, `--base`가 다른 ROM이면 조용히 다른 raw tile 영역을 오염시킬 수 있습니다. hook site처럼 expected bytes/hash를 두세요.

4. **전역 QA green 주장은 현재 사실이 아닙니다.**
   `python3 tools/qa_spacing_from_rom.py --show 20` 결과가 FAIL입니다: jammed 433, abbrev 74, grammar 17. 이건 A2 hook 단독 결함은 아니지만, “전 QA PASS”를 이번 변경의 안전 근거로 쓰면 안 됩니다.

`0x8140` 가정은 이 지점에서는 타당합니다. 한글 예약범위 `0x8840~0xE2A7` 밖이고, 원본 A2 테이블도 전각공백 `0x8140`을 실제 공백으로 쓰고 있습니다. A1 LZ77 in-place overflow도 현재 코드는 길이 초과 시 빌드 실패라 즉시 위험은 낮습니다.
