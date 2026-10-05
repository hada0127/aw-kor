# 주간 사용량30% 중단 인계 — 2026-09-28

사용자 지시의 **주간 누적 사용률**(10080분)이 2026-09-27 19:51 UTC/09-28 04:51 KST에30%도달하여 새작업·게임입력을중단했다. 재개요청전자동재개금지. 저장/종료정리만수행한다. **양편엔딩미도달·배포보류.**

## 검증 후보와 미완료 수정

마지막 통합검증 후보는 `temp/part2_2026-09-28/round23/candidate.gba`, SHA256 `18a1b5b5911cea317db15f1da1e498307cbe58dc17cc513f572b93effb209610`. M8문구4건·추가3메시지의의미오류·D8FAEE지역명복원이포함된다. M8도입/팩토리/승리3장면실제확인. 추가3메시지와지역명복원실화면은미확인. 기존B팀drift41건은여전히전역FAIL이다.

폭격기구매창 무기명 `爆弾` 잔류는 A294C4의독립4B텍스트누락이다. `폭탄`4B추가한round24는최종repoint가슬롯없는문자열을재배치하여exact4BscopeFAIL, **본선미적용**. 후속소스는해당주소만기존skip_messages경로로제외+최종payload/NUL/nativeptr검증을추가했다. 관련5시험PASS/Claude후속확정차단없음. 그러나round25빌드중30%가되어SIGINT중단(build -2/wrapper254), QA와실화면은미완료다. **round24/25를검증후보로사용하지말것.**

관련파일: `tools/build_korean_full.py`, `data/address_text_overrides.tsv`, `tools/test_part2_bomber_weapon_label.py`. 후속자료 `temp/sprite_2026-09-28/bomber_label/`, 빌드/검사/리뷰 `temp/part2_2026-09-28/round25/`. 현재편집메타데이터는round24 integrity로생성됐으므로재개후최종성공빌드기준으로갱신/입력receipt를맞춰야한다. 전역배포산출물동기화는하지않았다.

## 본선 저장 상태

- 1편: 임무3 DAY50, round23. source147/frame22803에서공격대상선택만열린상태로30%검사에걸려공격확정미실행. 취소/정상저장/export/quit정리결과는아래에추가한다.
- 2편: M8재시도 DAY9 정상승리(B200,누계2236Pt), 블루문전환대사 source59/frame31996. main52526 정상quit/emulator exit0. 승리직후같은ROM checkpoint는보존됐으나승리후일반저장/cold복원은미확인이다. 마지막직접확인일반저장은DAY8 source24/25이다. 최종SRAM/해당DAY8 SRAM export결과는아래에추가한다.

교차ROM savestate금지. 검증ROM이바뀌면정상SRAM cold경로를사용하고아군raw/자금/위치를대조한다. 같은ROM승리후checkpoint재개는정상SRAM승리저장과구분한다.

## 재개 우선순위

1. 사용자의명시재개요청후에만작업재개. 새사용량의UTC시각/주간10080분창확인. `python3 temp/part2_2026-09-23/check_codex_usage.py`.
2. 폭탄수정round25빌드/receipt/최종4Bscope/기존검사완료. 새후보로정상DAY8구매창짧은cold재현, 폭격기폭탄표기확인. 이후편집메타데이터갱신/최종receipt.
3. P2승리이후저장경로확인과P1 DAY50정상진행. 새임무진행은사용량재개후.
4. 추가4메시지실화면, DFD082의54half-cell>50 표시경로, B팀41건, 기타기존미검증범위는별도유지. 긴문장축약/기준자동수락/검사가드완화금지.

상세: [효율검수기록](EFFICIENT_AUDIT_2026-09-28.md). 증거파일과기존stage/workingtree변경은보존했다.


## 종료 정리 확정

- **1편 정상저장 완료:** DAY50/아군10/자금34200, source156/frame23961. `temp/part1_2026-09-28/mission3_day50_quota30_save/game_save.json`, SRAM SHA256 `9ef938afb88495f6b29fd3afafe8ef3a5169a1b0066f1ab6535c17f917c9a91b`. export0/main87504 quit0. checkpoint `output/qa/part1_2026-09-28/mission3_day48_round23_cold_live/0156_A_0023961.checkpoint.json`. 담당상세 `temp/part1_2026-09-28/HANDOFF_QUOTA30.md`.
- **2편 종료 완료, 승리후일반저장 없음:** main52526/emulator exit0, frame31996. `temp/part2_2026-09-28/m8_retry_day8_purchase_save/game_save.json`과 `temp/part2_2026-09-28/m8_victory_quota30_save/game_save.json`의 SRAM SHA256은 모두 `29d329d7fa9339713a4c93eff6538d05decbbb8b1fadd903a67ebacae849829f`로 동일하다. 두export0. **정상SRAM cold는DAY8로돌아간다.** 승리후자동저장됐다는주장을하지않는다. 승리/블루문위치는 `output/qa/part2_2026-09-28/round23_m8_retry/0059_A_0031996.checkpoint.json` 및같은ROM resume로보존한다. 다른ROM에이state를적용하지않는다. 담당상세 `temp/part2_2026-09-28/p2_quota30_handoff.json`/`m8_progress.md`.
- round25 빌드프로세스 SIGINT종료확인(build -2/wrapper254). 추가QA/게임진행없음. 모든본선정상종료했다.
