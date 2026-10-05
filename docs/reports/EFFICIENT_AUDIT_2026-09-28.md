# 효율 검수 재개 — 2026-09-28

사용자 요청에 따라 Codex **주간 누적 사용률 30%**에서 정상 저장·인계 후 중단한다. 09/23의 40% 중단은 과거 기록이며 09/28 재개는 승인됐다. 두 편 엔딩은 미도달이고 배포는 보류한다.

## 사용량 검사 수정

기존 `temp/part2_2026-09-23/check_codex_usage.py`의 날짜 고정 때문에 과거 40%가 현재 값으로 표시됐다. 최신 이벤트 기준 실제 재개 사용량은 9%였고, 17:51 UTC에는 11%였다. 파일명의 날짜 대신 UTC 이벤트 시각과 초기화 시각을 확인한다.

검사기는 모든 세션 날짜의 최근 파일에서 각 마지막 2MiB를 읽고, 주간 10080분 창·15분 신선도·초기화 유효성·미래시각 허용 60초를 검사한다. 유효한 최근 기록 중 30% 이상이 하나라도 있으면 중단한다. 불명확한 기록도 진행을 허용하지 않는다. 제한된 tail 조사이므로 전체 로그 탐색 보장은 주장하지 않는다.

회귀 시험 9개 통과. Claude 엄격 읽기 리뷰와 후속 리뷰에 확정 차단 결함 없음. 증거: `temp/usage_checker_2026-09-28/completion.json`, `tests.log`, `claude_followup.log`. 종료코드 0만 계속, 30은 한도 도달, 2는 확인 불가이다.

## 플레이와 검수

- 기준 후보: `temp/part2_2026-09-23/round16/candidate.gba`, SHA256 `83305154eefa6ed82e4046cbb827ad33252d2bd35805b51947e0eede5bff3be2`. 재개 전 빌드 receipt와 현재 생산 입력 일치 확인.
- 1편: 정상 SRAM에서 cold boot 후 아군11·자금46800·자군 슬롯 전체 일치 확인. DAY32/아군12/자금47800까지 정상 진행. 체크포인트 `output/qa/part1_2026-09-28/mission3_day31_cold_live/0100_A_0021779.checkpoint.json`.
- 2편: M8 DAY2의 정상 SRAM에서 재개 준비. 다른 ROM의 savestate는 사용하지 않는다.
- lossless 잔여7건: 재검토해도 안전한 소비 진입점/제어·바이트 소유 범위가 확정되지 않았다. 단순 용량 계산이 맞는다는 이유로 강제 확장하지 않았다. `temp/sprite_2026-09-28/lossless_remaining/REPORT.md`.
- M8 소개와 완결 메시지53건을 기존 후보의 실제 조립 payload로 개별 검수. 기존74선별 대상과 겹치는 A0D75C 제외. M9~12는 임무 번호 대응 미확정으로 범위를 확장하지 않았다. 3건의 같은 줄 문장부호 누락 발견: A0D370, A0D9F0, A0DEF9. 주소 한정 수정 작업 중이며 새 후보·실화면 검증은 아직 완료되지 않았다. `temp/sprite_2026-09-28/m8_context/messages.json`.

저부하 원칙: 전체 빌드/대량 재생은 하나씩, main 하네스는 편당 하나·최대 둘, nice15, 디스크 15GiB 하한. 기존 증거는 삭제하지 않는다.

## M8 문구 4건 수정과 검증

A0D370/A0D9F0의 `그래`에 마침표, A0DEF9의 `어이`에 쉼표를 복원했다. 각 원본 6B 슬롯에 정확히 들어가며 공통 사전은 변경하지 않았다. A0DF00의 `얘긴 아직 안끝나`는 `얘긴 아직 안 끝났어!`로 복원했다. 새 문구24B가 원본18B를 넘으므로 원본 슬롯과 뒤 `77 72`를 보존하고 필수 메시지 재배치를 사용한다.

생산 변경은 `tools/build_korean_full.py`, `data/address_text_overrides.tsv`, `tools/test_observed_translation_repairs.py`이다. 관측 회귀17개와 스크립트 안전성92개 통과. 편집기4행의 표시/칸 크기/수정 가능 상태를 확인했다.

round17 빌드 및 자동검사 종료0, SHA256 `51b10dcf48204be4762c3c262c6a9de0de87fb014d7e0043742e7db02fff7d98`. 전체 수정행/제어·42목표·84소개·121strict제목·18094활성/1996재배치 payload 부호/글리프 검사 통과. 별도 범위검사는 변경3메시지 전체 expected와 2248개 다른 재배치 payload 동일성, 다중참조의 원본/old/new source 동일성, 원래 목적지의 빈 공간을 검사해 설명 못한 바이트 차이0을 확인했다. 재배치 주소 이동에 따른 물리 변화205418B를 내용 변화205418B로 집계하지 않는다.

Claude 첫 읽기 검토는 생산코드 확정 결함을 찾지 못했고 범위검증 누락을 지적했다. 해당 검사와 PASS 출력 순서를 보강한 뒤 후속 읽기 검토에서 확정 오류 없음. `temp/part2_2026-09-28/round17/claude_review.log`, `claude_followup.log`, `scope_diff.json`.

`dialogue_map.json`/`dialogue_groups.json`을 재생성해 4행의 ko/ship_ko/group을 일치시켰다. 생성 메타데이터도 빌드 입력에 포함되므로 round18 최종 빌드 중이다. 전역 `audit_address_text_overrides.py --strict`는 기존 D90250/D902DC 및 다수 governance 부채로 여전히FAIL이며, 이번4행 검사로 전역 통과를 주장하지 않는다. 실제 새 ROM 3장면 표시 검증은 대기 중이다.

최종 round18 전체 빌드/QA/scope 종료0. round17과 16MiB 전체가 byte-identical이며 SHA51b10dcf…7d98이다. 메타데이터 생성 전후를 포함한 최종 입력 receipt가 있고 생성 후 map/group SHA도 유지된다. 보정행은258개, 편집기4행의 map/ship/group/실제 API 일치. 실제화면 재현은 별도 담당자가 기존 M7 승리 정상SRAM과 입력16개를 이용해 진행한다.

### 실제 도입 화면

M7 승리 정상 SRAM에서 16입력/10000연속프레임으로 A0D370 도입을 재현했다. round18 화면 `output/qa/part2_2026-09-28/round18_m8_intro_probe/0016_A_0010000.png`에서 `그래.`와 이어지는 문장의 간격, 줄바꿈을 확인했다(root/담당자 육안 확인). native포인터A35FE0→A45298, prefix88878aec8142/원본7777 제어 보존. 진단 에뮬 정상 종료0. `intro_screen_verification.json`에 SHA와 출처·종료기록 보존. 다른 두 장면은 앞으로의 M8 설명/승리 진행에서 확인한다.

D90250/D902DC의 map/group 불일치는 최종ROM과정본·실제서버를대조한결과 audit가옛directliteral을최종값으로취급한오탐이었다. 해당audit호스트도구만수정중이며 번역/ROM을되돌리지않는다. 다른runtime/TSV mismatch는이번두주소범위밖이며여전히미판정이다.

### 보호 문구 검사기 오탐 수정

`audit_address_text_overrides.py`와 `qa_text_fit.py`의 정적 추출에 writer 출처를 연결하고, 빌더와 같은 override 정규화/거부 규칙을 사용했다. 기존 2-tuple 호출 API는 유지한다. 새 `test_audit_address_text_overrides.py` 9시험과 기존 관측17시험 통과. Claude 후속 읽기 검토는 차단 결함 없음. 증거는 `temp/sprite_2026-09-28/address_audit_fix/`.

한계: 이는 추출 가능한 한글 상수/인식된 list loop의 **빌드 의도 텍스트 비교**다. 빈 literal·동적 payload·모든 writer·최종 ROM/실화면 전부의 증거가 아니다. 기존 코드의 넓은 docstring을 전수 검증 주장으로 사용하지 않는다. 두 확정오탐은 해소됐지만 새 metadata 차이155건이 드러났고, 미분류 override차이1008건 등이 남는다. 대표 D9028B/A03EB8은 새 계산값과 round18 writer/ship_ko가 일치함을 확인했으며, 155건 전체를 생산오류로 단정하거나 자동수정하지 않았다.

이번 변경은 호스트 검사기3파일뿐이다. round18 ROM은 불변이고 빌드 receipt는 당시 입력을 보존한다. 현재 입력과의 일치를 다시 확보하기 위해 round19 빌드 진행 중이며, 그 전 현재입력 기반 배포 검사는 통과한 것으로 취급하지 않는다.

round19 전체 빌드/QA/scope 종료0, 현재 전체 입력 receipt 일치. round18과 ROM 전체 byte-identical(SHA51b10dcf…7d98)이라 같은 ROM의 기존 도입 및 본선 화면 증거를 재사용한다. `round19/previous_identity.json`.

2편 본선 DAY3 설명 중 A0D9F0 `그래. 그건 말이야,`를 source56/frame14574에서 확인했다. root도 직접 화면을 확인했으며 마침표/간격/줄 경계 정상. 도입과 팩토리 두 장면을 `docs/screenshots/continuation_2026-09-28/`에 SHA와 함께 보존했다. A0DEF9/A0DF00 승리 문구 실화면은 아직 대기.

## 추가 주소 범위60개 문맥 검수와 보호 기준 충돌

A0E370~A10000의 native 적격101개 중60개(A0E398~A0F3C8)를 개별 검수, 다음 미검수A0F420. 임무번호는 추정하지 않았다. 소유 표현 A0F189, 금지 명령 조립 A0F333/F340, 사과 조각 A0F268/F26D/F27A의 확정 의미 오류3메시지를 찾았다. 원문/실제ROM/owner 증거 `temp/sprite_2026-09-28/e370_context/REPORT.md`.

첫 round20 후보는 구조·최종payload 비교는 통과했지만, F26D를CSV값으로되돌린것이 보호된 `bteam_baseline.json`의 `미,`와충돌했다. Claude 엄격검토에서발견했고실제qa_bteam_drift로확인했다. 후보를기각하고본선에적용하지않았다. 원래CSV일치만으로B팀기준일치라고판단한것은잘못이었다.

전역 drift는43건(이번F26D1+기존42). 기존42는이번범위밖의미분류상태이며자동수락/복원하지않는다. 후속안은F26D기준값불변, F268을더듬는첫조각으로복구, F27A의단한번사과와'하지만'전체문구를필수재배치경로로보존한다. baseline갱신없이새drift0을요구한다. 실제새3메시지화면경로는아직확인하지못했다.


### 보호 기준 보존 후속안

F26D는 B팀 기준 `미,`를 그대로 유지한다. F268은 고정4B 더듬는 조각, F27A는 `미안해. 하지만・・・`22B를 필수 재배치하며 원래12B 슬롯은 원문 staging으로 보존한다. 검증6행 중 실제변경5행이다. 관측18시험·스크립트92시험 통과. Claude 후속 읽기 검토는 추가 확정 차단 없음(`round21/claude_review.log`). 전역 B팀42건 FAIL은 계속 유지하며 이번 변경으로 추가 drift가 없어야 한다. round21 최종 ROM 빌드/검증 진행 중이고 새3장면 실화면은 미확인이다.

19:09 UTC 주간 사용률23%. 1편은 임무3 DAY40 정상저장 source292/frame48455. 2편 시도1은 M8 DAY8 source194/frame44720 정상저장 후 main 종료0, `temp/part2_2026-09-28/m8_attempt1_day8_save/game_save.json`에 보존했다. 시도2는 기존 정상 DAY2 SRAM으로 round19 cold 부팅, own3 전체/자금9000 일치(source8/frame6012) 검증 후 중앙 공항 우선 경로로 진행한다. 시도1을 승리로 집계하지 않는다.


round21 빌드/QA/scope 종료0, SHA `a2d2d8275db54d3ae62da5490954bdc1b84265b2f63271ce1d9490f1922264ca`. 3메시지 전체 조립/제어 보존, 나머지2249개 재배치 payload 불변, 범위 밖 바이트 차이0, 새 B팀 drift0/기존42 확인. 전역 로그 DRIFT42/MISSING0도 직접 확인했다. 6행 편집 메타데이터 ko/ship_ko 일치를 확인했고 갱신된 메타데이터의 최종 재빌드가 남았다. 새3장면 실화면과 양편 엔딩은 미확인이다.

기존42건 분류에서 D8FAEE 지역명과 DFD082 비밀이라는 서두 누락을 확인했다. D8FAEE는 기준전체42B가 원래36B보다 길어 필수 재배치 복원을 준비한다. DFD082는54half-cell로현재50 한도를 넘어 단순복원하지않는다. 보고서 `temp/sprite_2026-09-28/e370_context/BTEAM_DRIFT_CLASSIFICATION.md`; 말투 등 다른40건을 자동승인/복원하지 않았다.


### 지역명 누락 단일 복원

D8FAEE의 기준문구 `뭐라고?! 아라라 지방에 레드스타 군이`42B를 ADDRESS/TSV/override에 일치시키고 원래36B는 staging으로 보존, 필수 재배치로 등록했다. 실제 원본0x19 포인터 DA554C→D8FAEC와 단일메시지 메모리 검증에서128→134B·제어·이웃 보존을 확인했다. 관측19+스크립트92시험 통과. override정확1건만 변경하며 기준/CSV/registry/intent 불변, B팀 drift42→41/MISSING0으로 전역FAIL 유지. round22 빌드/Claude검토 중이다.

DFD082는 기준54half-cell이현재50guard를넘고 실제상점소비화면/안전한줄배치가미확정이므로생산수정하지않았다. 단순폭가드완화·축약·기준변경을해결로삼지않는다. `temp/sprite_2026-09-28/bteam_two/REPORT.md`에 후속실화면확인필요사항 기록.


round22 빌드/QA 종료0, SHA `18a1b5b5911cea317db15f1da1e498307cbe58dc17cc513f572b93effb209610`. 이번 변경 메시지 전체 정확일치와 다른2250개 재배치 payload/metadata 불변, 허용범위밖 차이0을 확인했다. Claude 읽기리뷰 확정차단없음. 전역 B팀41/MISSING0 FAIL 유지. 편집기 D8FAEE ko/ship_ko 일치로 갱신했고 원본slot36은 인접바이트쓰기방지를 위해 유지한다(재배치목적지payload42와구별). 메타데이터포함 round23 최종빌드중. 실제 새4메시지 화면은 미확인이다.


round23 최종빌드/QA/현재입력receipt 통과, round22와 ROM전체byte동일18a1b5b5…09610. 메타데이터해시불변도확인(`round23/previous_identity.json`). 본선교체는정상SRAM+cold로만진행한다.

2편 M8재시도 DAY7 공항구매에서 폭격기무기명 일본어 `爆弾` 잔류를 실제발견했다. source112/frame28718, 기존round19 SHA51b10. root가화면직접확인했고 `docs/screenshots/continuation_2026-09-28/p2_bomber_weapon_japanese.png`에보존했다. 바로앞전투기대공미사일은정상. 주소/원인확인과기존표시경로수정조사중이며미해결이다.


2편 M8 재시도 DAY9 목표파괴 source36/frame16350, 승리대사44/frame21166에서 수정문구 `어이, 얘긴 아직 안 끝났어!` 표시/간격/느낌표를 담당자와root가확인했다. 앞더듬는조각은별도유지. `docs/screenshots/continuation_2026-09-28/p2_m8_victory_punctuation.png` 보존. 이번M8문구4건의 도입/팩토리/승리3장면이 모두관측됐으며캠페인엔딩은아니다.

폭탄라벨은 A294C4 4B의일본어텍스트누락으로찾았고 ADDRESS/TSV/기존NULwriter에 `폭탄`4B를등록했다. 신규3시험통과·Claude후속체커차단해소. 그러나 round24 전체빌드후실제scope검사는실패했다. repoint가A37B10을A55324로바꾸고뒤pool을8B이동시켰으며총149694B차이다. exact4B외불변조건이이를검출했고후보는본선에적용하지않았다. 원인확인·수정후재빌드/실화면검증은미완료다. 19:47 UTC 주간29%.


폭탄 후속원인은 새fixed_zero WRITE_LOG는재배치입력에합쳐지지만 slots에는없어 encode_fit(slot=0) 실패99가되어재배치대상으로선택된것이다. A294C4만기존독립NUL라벨 skip_messages경로로제외하고 모든writer뒤 payload/NUL/nativeptr최종guard를추가했다. 실제slots없는fit99조건을포함한5시험 통과. 소스는 builder/TSV/test_part2_bomber_weapon_label.py. round25재빌드/Claude후속검토중이며최종4Bscope는계속필수다. 편집map의A294C4 ko/ship_ko=폭탄/slot4 확인. 아직수정실화면과최종후보검증은미완료다.

양편최신검증후보 round23=18a1b5b5…09610으로 정상SRAM cold변경: P1 DAY48 main87504 source7/frame4933에서army0전체/자금39600/커서10,10 일치(`temp/part1_2026-09-28/round23_cold_evidence.json`). P2 M8 DAY7 main52526 source8/frame6012 own5/자금13000 일치(`temp/part2_2026-09-28/round23_m8_retry_cold.json`). 이후 P2 DAY9 목표파괴/승리대사정상진행. 두편엔딩은여전히미도달이다.


주간30%에새작업중단. round25는빌드중SIGINT로종료(-2), QA/runtime미완료. Claude후속확정차단없음은통합검증을대체하지않는다. 양편main종료/저장자료export완료. P1 DAY50정상저장, P2 M8승리후상태는same-ROM checkpoint에만보존되고SRAM은DAY8과동일함을확인했다. [최종중단인계](SESSION_HANDOFF_2026-09-28_QUOTA30.md). 재개요청전자동재개금지.
