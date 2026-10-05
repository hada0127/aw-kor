# 사용량 40% 중단 인계 — 2026-09-23 18:09 KST

사용자 지시에 따라 Codex 주간 used_percent 40%를 확인하고 새 작업·전투 입력을 중단했다. 재개 요청 전 자동 재개하지 않는다. 40% 확인: 2026-09-23 09:08:09.953 UTC, `check_codex_usage.py` exit40. 이후에는 정상 저장·종료·인계 정리만 수행했다. 두 편 엔딩은 미도달이며 배포하지 않았다.

## 검증 후보

- ROM: `temp/part2_2026-09-23/round16/candidate.gba`
- SHA256: `83305154eefa6ed82e4046cbb827ad33252d2bd35805b51947e0eede5bff3be2`
- receipt SHA256: `3760250e2d4b5cc71388e2e778a5370188bd5dd99f9d52f3a1383ce16664cfad`
- 전체 빌드·QA exit0. 254필수 수정행/메시지제어/42목표/84소개/121strict제목/18094활성·1996재배치payload 검사 통과.
- 지형 7종은 원래 Galmuri7과 아이콘을 보존해40px로 표시한다. 종료 직전 꼬리 소실을 수정했다. 정상SRAM cold 시제품과 전체ROM byte동일, 463캡처/63전환표본0회귀/128idle×3. 모든 프레임·날씨·항구7종동시 검수로 확대하지 않는다.
- 지형 모듈13시험, 편집기8시험 PASS. 구ROM 빈캔버스/비교API의잘못된링크, ARM ADR참조검사 오류를 수정했다. Claude 최종후속 정적리뷰에서 수정범위 확정회귀0 (`round16/claude_review.log`). agy는 이전 인증 실패로 사용 불가였다.
- 출력3종/배포BPS는 이 후보로 동기화하지 않았다. dirty/staged 변경을 보존했으며 일괄 커밋·리셋하지 않았다.

## 본선 저장

1편은 DAY31에 적 중전차 한 기 격파까지 진행했다. 40% 시점 source66/frame15891의 공격 목표 선택은 확정하지 않고 취소한 뒤, 일반 저장 checkpoint75/frame17469에서 세션51816을 정상 종료했다(exit0/정리오류0). 아군11개/자금46800/커서12,8. 정상SRAM receipt는 `temp/part1_2026-09-23/mission3_day31_quota40_save/game_save.json`, SRAM SHA256 `4c2ffcbc6b4dfd8d13036641b82b5609b7a324f985f1509c1553569d05018082`(131072B). 내보내기는 frame17469→17469로 게임 진행 없이 완료했고 임시core도 종료했다. 마지막 checkpoint는 `output/qa/part1_2026-09-23/mission3_day30_round14_cold_live/0075_A_0017469.checkpoint.json`, ROM8330으로 최종후보와 동일하다.

2편은 M8 DAY2, 자금9000/보병3개 상태를 보존하고 세션93758을 quit으로 exit0 종료했다. 마지막frame6012. `output/qa/part2_2026-09-23/round13_m8_cold_live/resume.checkpoint.json`, ROMfd0b2794. 정상SRAM은 `temp/part2_2026-09-23/m8_day2_round8_save/game_save.json`, save SHA031760a6c3345cbf5d25e06fb62fcea0d7e71ab05218168126bbc63b5650ba3a. 새8330에는 이 정상SRAM으로cold boot한다. 다른ROM의savestate를불러오지않는다.

## 재개 순서와 미검증 범위

사용량 조건을 사용자가 해제하거나 재개를 요청한 뒤에만 진행한다. 최신 정상 저장과 입력 기록을 이어 남은 캠페인·엔딩을 검수한다. 빌드/대량재생은 한 번에 하나, nice15. 원본/기존증거/로컬검사도구를 재사용하고 알려진동일ROM화면의중복재생을피한다. 아군 상태 보조 도구는 기존 체크포인트만 읽고 적 비공개 상태는 읽지 않는다.

소비 렌더러 근거1/2276, 긴줄조건부후보10, native제목58, lossless보류7, 미방문스프라이트/날씨/항구7종동시/실기/양편엔딩은 미검증으로 유지한다. 문맥74개 선별검수는 전체번역 의미검수가 아니다. 자세한 검증·제한은 `EFFICIENT_AUDIT_2026-09-23.md`와 `docs/research.md` 마지막 지형 항목을 따른다.
