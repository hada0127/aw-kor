# 외부판 비교 재분석 + 격차 클로징 (2026-06-24)

> 대상: 본 프로젝트(일본판 1+2 합본 한글, `output/game_wars_korean_full.gba`)
> vs 외부 배포 USA 독립판 한글패치 AW1 v0.38 / AW2 v0.31(다운로드).
> 방법: claude 주도 + codex·agy **적대적 엄격 리뷰**. 절대제약: 쪼롱이님/B팀 번역 불변.
> ROM: 세션 종료 SHA **a582a7cb**(시작 08d50127 → B팀 복원 반영).

## 1. 이번 세션 핵심 성과 (검증됨)

| # | 작업 | 결과 | 증거 |
|---|---|---|---|
| 1 | **전 63 game scene 재캡처** | 76 stale → **0**, entrypoint audit **critical=0**. "장면 진입기로 모든 장면 진입 확인" 요구 충족 | `tools/capture_scene_screenshots.py`, `temp/scene_entrypoint_audit/report.md` |
| 2 | **실화면 잔존 전수 시각검증**(13에이전트 병렬) | 63 scene 중 HIGH 3 / MED 4 / 나머지 정상. 정적 잔존스캔 21k행은 거의 노이즈임을 확증 | `temp/visual_verify_result.json`, `temp/residual_defects_2026-06-24.md` |
| 3 | **B팀 대사 변형 복원 (절대제약 보호)** | codex가 적발: 작업트리에서 `0x00DF5E12/35/56` B팀 대사가 **슬롯 여유 있음에도 축약·개작**됨 → HEAD 권위본으로 **복원** | git HEAD diff, 재빌드 검증 |
| 4 | **CSV 손상 위생 복구 + 영구 탐지기** | agy가 적발한 `0x00A2C2F4`(꼬리잘림)·`0x00A2C378`(length 필드 주소혼입) 복구 + `tools/qa_csv_integrity.py` 신설 | `tools/qa_csv_integrity.py`, `temp/csv_integrity_report.tsv` |
| 5 | **UI 에디터 스프라이트+대사 편집 완전성** | :8782 라이브 검증: 대사 save·슬롯 하드게이트(56B>16B 거부)·미수록음절·deny/pair 가드, 스프라이트 tile/render/save/revert 전부 동작 | `tools/scene_editor/server.py` |
| 6 | **픽셀폭 검증 도구화** | `tools/qa_pixel_width.py`(렌더러 advance 모델 8px/4px) 신설·실행. 시각검증과 교차: 실화면 박스 클리핑 0건 | `temp/pixel_width_report.tsv` |
| 7 | **배포 정합성** | B팀 복원 ROM에 맞춰 dist BPS/IPS/manifest 재생성, `verify_dist_integrity.py` **PASS** | `dist/*_2026-06-24.*` |

## 2. 외부판 3개 보정의 우리 대응 (벤치마크)

| 외부 보정(AW2 v0.31) | 우리 ROM 상태 | 판정 |
|---|---|---|
| versus/rules 도움말 강제개행 제거 → 1줄 | 우리 렌더러는 슬롯 fit 기반, 별도 강제개행 바이트 구조 아님 | 비해당(다른 렌더러) |
| 공장·항구·공항 4줄 지형설명 | 일본판은 원래 분리 구조 → repoint 꼼수 불요(agy 인정) | **아키텍처 우위** |
| 점령 라벨 별표 제거(대점령*→점령) | 우리 capture 명령은 이미 "점령"(0x008052A8). `0x00A04A63 「대점령」`은 CO 스킬명(大占領)=캠페인 대사라 **불변** | 무결함 |

## 3. 잔존 결함(추적) — 외부판 대비 위치

분석가 권고("남은 문제 없음보다 확인된 잔여 결함 목록이 더 신뢰된다") 이행.

- **HIGH ① CO/인물 이름 라벨 가타카나**(30f2 등): 이름은 SJIS 대화스트림 밖(OBJ/인덱스 렌더). Domino는 이미 OBJ blank+본문이관 처리(`patch_part2_domino_co_name_obj`)되나 타 CO 미처리. 외부판=USA 기반이라 이름이 원래 라틴(구조적 유리, 공정성 단서). → **이름 테이블 RE 후 per-CO 처리** 필요(추적).
- **MED ② 맵 선택 섬 이름 '??'**(87, 소라**마메**섬의 마/메): ROM 인코딩 정확(∈2350), **컴팩트 렌더러 글리프뱅크 누락**(fallback 0x8148='?'). 단 외부판은 맵 이름 **영문 유지(미번역)** → 우리가 이미 우위, '??' 2~3음절만 폴리시. → 컴팩트 글리프뱅크에 마/메 공급(추적).
- **MED ③ 영어 sprite UI**(PRESS A/ENEMY/R.MAP/SELECT/GALLERY/START): 그래픽 스프라이트. 외부판도 동류 영문 유지 → 동급. sprite editor로 추가 가능(선택).
- **OPEN ④ 24_part2_campaign_map 룰 라벨 일본어**: 라벨(収入/日数/能力)은 우리 데이터에 번역됨(수입/일수/능력) → savestate **stale-BG 의심**이나 codex는 실잔존 주장. → fresh-boot 재캡처로 확정 필요(추적).
- **LOW ⑤ part1 캠페인 단어붙음**(0x19 커맨드스트림): 부분해소·잔여 117 추적 중.
- **데이터 ⑥ CSV 손상**: `qa_csv_integrity.py` 기준 239행(length만 손상 다수 무해), 그 중 **109행이 진짜 ROM 위험**(korean이 일본어/빈칸/주소혼입+override無). 행별 맥락(쪼롱이 인접) 필요 → 신중 추적(일괄수정 금지).

## 4. codex·agy 적대적 우열 판정 (수렴)

- **수렴(둘 다 인정)**: 범위·폰트(완성형 2350)·합본 단일패치·QA/도구 파이프라인·B팀 보호게이트·아키텍처는 본 프로젝트 **우위**. 외부 리포트는 개별 USA판 점진보정 중심으로 범위가 좁다.
- **수렴(둘 다 지적)**: "외부판보다 부족한 게 없다"는 **아직 완전 입증 전**. 실화면 일본어 잔존(이름 라벨)·맵 '??'·실기 미검증이 우위 주장의 blocker. codex가 적발한 **B팀 변형은 절대제약 위반 → 이번 세션에 복원 완료**.
- 전문: `temp/codex_review_2026-06-24.md`, `temp/agy_review_2026-06-24.md`.

## 5. 다음 우선순위 (우위 확보)
1. ~~B팀 권위문 복원~~ ✅ 완료(이번 세션).
2. CO/인물 이름 테이블 RE → per-CO OBJ blank+본문이관 확장(이름 라벨 일본어 0).
3. 컴팩트 렌더러 글리프뱅크에 마/메 공급 → 맵 '??' 제거 후 87/컴팩트 UI 재캡처.
4. CSV 109행 ROM 위험분 행별 검수·복구(쪼롱이 인접 보호) + `qa_csv_integrity --fail-on-rom-affecting` 게이트화.
5. container residual scan을 현재 SHA로 재생성 → `audit_scene_residual_scans --strict` PASS.
6. 24 rule-label fresh-boot 재캡처로 stale-BG vs 실잔존 확정.
7. 실기(real GBA) 검증.

---
## 후반 세션 (2026-06-24) — 정석 전수 진행 + codex·agy 2차 적대 재리뷰

### 닫은 것 (검증)
- **B팀 보호 3+층**: ①권위문 복원 ②`qa_bteam_drift.py`(3340주소 baseline, drift 0) ③:8782·:8780 `_save_line` save-time 차단(confirm_bteam)
  ④`--accept`=AW_BTEAM_ACCEPT=1 ⑤`verify_dist_integrity` 게이트 연동. → 0xDF5E식 우발 변형 5중 차단.
- **B1 CSV 손상 = ROM 결함 0 확정**: `qa_csv_integrity.py` ROM-디코드 권위화. 손상 239행이나 출하 ROM 일본어 텍스트 잔존 0.
- **C 편집 커버리지**: 실대사 99.0% 편집가능(차단 200=정당), 스프라이트 1979 전부 도달·편집. 쪼롱이 요구 충족.
- **A1 de-risk**: `korean_glyphs_8px.json`(8px 한글, agy 발견)으로 96×8 이름 OBJ 직접 렌더 가능. CO 테이블 0x081BE68/stride0x44/19 OBJ 식별.

### codex·agy 2차 verdict (수렴)
- **/goal "잔존 결함 0" 미달(약 70~80%)**: 현재 캡처에 A1(CO명 가타카나)·A2(맵 '??')·A3(룰라벨) **실잔존이 보임**.
  stale-BG 재판정은 **fresh-boot 입증 전 인정 불가**(둘 다). 데이터 정합/배포/B팀 보호는 크게 닫혔으나 적대 리뷰는 화면을 본다.
- **남은 진짜 결함(우선순위)**: P0 fresh-boot 재캡처+A1/A3 trace, P0 residual scan strict 재생성, P1 A2 4번째 렌더러 hook,
  P1 영어 sprite UI·단어붙음117·부호소실10, P1 B팀 보호 잔여(app.js confirm UI, 전수 디코더), F1 실기.
- **정직한 결론**: 외부판 대비 범위·완성형·QA·도구·B팀보호·아키텍처 우위는 유지. "외부판보다 부족함 0"의 화면 마감(이름/맵글리프)은
  미완 — 단 외부판도 이름은 라틴(기반게임差)·맵이름은 영문유지라 직접 열세는 제한적. A1/A2는 de-risked 경로 확보.
