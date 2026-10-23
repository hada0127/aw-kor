# aw-kor 안전 종료 인계 — 2026-10-24

사용자가 Codex 주간 한도 때문에 전체 안전 종료를 결정했다. 새 작업·워커·빌드·재생을 시작하지 않았다. 이 노트는 종료 전용 브랜치에만 올리며 main에 새로 병합하지 않는다.

## 목표와 현재 상태

2편 맵 에디터 이름 그리드의 두벌식 한글 조합 입력 구현은 완료됐다. 2바이트 × 최대 8자, 조합 중 자모부터 지우기, 2350 밖 중간 후보 원자 거부, 공유 가나 글리프 보존을 적용했다. 실제 그리드 입력·저장·별도 프로세스 cold reload·Versus 이름 소비자 등 15case와 원본 대비 5관문을 확인했고 Astra full→delta1→delta2 최종 승인을 받았다.

- 소스 commit: `4baba1f346c105d72a439f9af164f175a72544a0`.
- 문서 마감 / 종료 전 main·origin/main: `420e61657e5c9fad4307b5cf81940bd79d6a1eae`.
- 원격: `https://github.com/hada0127/aw-kor.git`.
- 이 인계노트의 브랜치: `shutdown-aw-kor-20261024`. 노트 commit은 이 브랜치의 `git log -1`로 확인한다(자기 commit SHA를 미리 적지 않음).
- 옛 작업 브랜치 `sweep3-p2-20261023c`는 완료 당시 main 병합·로컬/원격 tip 동일 확인 후 양쪽에서 삭제했다. 신규 작업트리는 만들지 않았다.
- 종료 시 미커밋 기능 변경 없음. 이번 종료에서 main 신규 병합·재배포 없음. 정본 b44와 dist는 그대로다.

## 재개

사용자가 재개를 지시한 뒤 첫 명령:

```bash
cd /Users/konest/project/aw-kor && git fetch origin && git status --short && git log -1 --oneline origin/shutdown-aw-kor-20261024
```

이 노트와 아래 원격 증거를 먼저 읽는다. 기능은 완료됐으므로 빌드·QA·워커를 자동 재실행하지 않는다. 후속 실기·Link·재배포는 재개 지시 범위에 맞게 별도 결정한다. 구현이 필요할 때만 새 작업 경계에서 `harness-route <role> --risk high --json`의 provider/location을 따른다. 이전 주말 Codex 전용 지시보다 사용자 결정 「이 pc 하네스대로」가 우선이다.

## 미검증·실패·남은 것

- GBA 실기 미검증. Link는 기존 하네스 full-ROM client 로더 한계로 BLOCKED이며 성공 처리하지 않았다.
- 중간 후보 원자 거부 계약 때문에 뢨·썅·쏀·쓩·쭁 5음절은 일반 키열 도달 불가다.
- 과거 비교 보조 로그의 실제 RC1과 후속 RC0 성공 주장 불일치는 성공 주장 철회로 해소했다. 후속 RC0는 미검증·판정 근거 제외다. 최초 실패·무효 case13 증거는 보존했다.
- 기존 잔여 B팀 114·overflow 273·wider 507·layout-loss 152는 baseline과 같은 집합이며 이번에 해결한 것으로 집계하지 않았다.
- 후보 SHA-256: `1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb`. ROM은 원격에 업로드하지 않았으므로 이 해시는 식별 기록이며 원격 바이너리 확보의 증거가 아니다. 원본 ROM도 사용자 제공 파일로만 유지한다.

## 원격에 보존된 유효 증거

아래는 모두 기존 push 완료 commit `420e61657e5c9fad4307b5cf81940bd79d6a1eae`에서 읽을 수 있다. 로컬 temp나 삭제된 서버 미러 링크는 유효한 원격 증거로 집계하지 않는다.

- [최종 코드 리뷰·승인 원문](https://github.com/hada0127/aw-kor/blob/420e61657e5c9fad4307b5cf81940bd79d6a1eae/docs/reports/name_grid_2026-10-23/PHASE_B_CODE_REVIEW.md)
- [QA 결과·명령·실제 출력](https://github.com/hada0127/aw-kor/blob/420e61657e5c9fad4307b5cf81940bd79d6a1eae/docs/reports/name_grid_2026-10-23/PHASE_B_QA.md)
- [증거 색인](https://github.com/hada0127/aw-kor/blob/420e61657e5c9fad4307b5cf81940bd79d6a1eae/docs/reports/name_grid_2026-10-23/evidence/INDEX.md) 및 같은 디렉터리 `index.json`의 324개 항목. SHA·크기 대조 완료. ROM·세이브·상태 저장·폰트 원본은 포함하지 않는다.
- [런타임 RE](https://github.com/hada0127/aw-kor/blob/420e61657e5c9fad4307b5cf81940bd79d6a1eae/docs/reports/name_grid_2026-10-23/PHASE_B_RE.md), 같은 디렉터리 `PHASE_B_PLAN_APPROVAL.md`와 `evidence/plan/PLAN-v5.md`.

## 종료 확인과 로컬 보존 예외

- 소유 Orca worker 8개 모두 terminal released. 종료 지시 뒤 다시 조회해 미해제 0 확인.
- 원격 run `aw-kor-phaseb-delta1-eb26ac81-20261023`, `aw-kor-phaseb-fix2-20261023`, `aw-kor-phaseb-delta2-b681903a-20261023`, `aw-kor-phaseb-closeout-4baba1f-20261023`: 모두 succeeded / provider_exit 0이며 이미 회수됐다. 진행 중 파이프라인·렌더·원격 run 없음. 이 세션이 만든 automation 없음.
- 소유 서버 미러는 완료 당시 OWNER와 종료 상태 확인 후 삭제됐다. 종료 지시에서 새 원격 작업을 만들지 않았다.
- **보존(미푸시 자료):** `/Users/konest/project/aw-kor/temp/name-grid-phaseB` 약 1.1GB. 재현용 ROM·세이브·원시 출력·빌드 스냅샷 등 원격 미보존 파일이 섞여 있어 사용자 지시의 “커밋/푸시 안 된 것은 지우지 말라”에 따라 전체 보존했다. 이 경로는 로컬 참고물이며 위 원격 유효 증거와 구분한다. 기존 B12 keep/track 등록도 보존 이유와 함께 남긴다. 따라서 소유 잔여는 이 보존 예외 1건이며 잔여 0이라고 주장하지 않는다.
- **보존(사용자 자료):** original/의 원본 ROM, output/의 후보·baseline·b44 참고 ROM, 사용자가 제공한 Downloads ZIP은 업로드·삭제하지 않았다.
- 주인 모를 iPhone Duo 시뮬레이터 및 타 세션 Downloads 항목은 건드리지 않았다. session-check의 기존 d1_incomplete·창 기록 락 실패는 검사 제한으로 보고만 하며 하네스 정책/원장을 편집하지 않았다.

최종 push 후 로컬 종료 브랜치 tip과 `git ls-remote`의 원격 tip을 대조한다. company에 노트 경로·실제 SHA·보존 예외를 한 번 보고한 뒤 작업을 끝낸다. 터미널 종료는 company 담당이다.
