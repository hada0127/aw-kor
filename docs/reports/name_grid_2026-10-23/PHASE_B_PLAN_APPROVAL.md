# Phase B 계획 승인 기록

작성 2026-10-23. 승인된 실행 명세 원문은 [`evidence/plan/PLAN-v5.md`](evidence/plan/PLAN-v5.md)(바이트 동일 복사), 원 요청 브리프는 [`evidence/plan/PHASE_B_BRIEF.md`](evidence/plan/PHASE_B_BRIEF.md)다. 리뷰 원문과 하네스 영수증 파일은 로컬 전역 상태라서 복사하지 않았다. 판정에 필요한 필드만 아래에 옮겼다.

## 1. 승인 대상

| 항목 | 값 |
|---|---|
| 계획 | `PLAN-v5.md` sha256 **`60a7574a957e5277ac8bbb826ad3bee54c39362907fd30864cc26c47809521b4`** (복사본 sha 동일, [`evidence/INDEX.md`](evidence/INDEX.md)) |
| 작성 | Fable 헤드리스 `harness-plan-write recheck` — 영수증 `kind=plan-recheck`, `recheck=ACCEPT`, `outcome=published`, `effectiveModel=claude-fable-5-1`, `effort=high`(argv+settings), `sessionId=472c8898-b32c-4c1d-a02f-d5eccf3b3d19`, base `be049c13…90ae`, ts `2026-10-23T07:49:33Z` |
| 계획 머리 서명 | `PLANNED-BY: claude-fable-5-1 effort=high session=472c8898-… recheck=ACCEPT base=be049c13` |
| 검토 | Astra(`gpt-6-astra`, read-only) `harness-plan-review --risk high`, `REVIEW-MODE: consensus` |
| 검토 결과 | `CONTEXT: match` · `AUTHOR: fable session=472c8898-…` · `VERDICT: APPROVE sha256=60a7574a…21b4` · 판정 영수증 `approved=true`, `authorOk=true`, **`implementationAllowed=true`**, manifest `17a93d10e188bd23…`, ts `2026-10-23T07:53:03Z` |

## 2. 계획 회차

| 회차 | 계획 sha | 리뷰 모드 | 결과 |
|---|---|---|---|
| v1 | `a222a5e5…ceaa` | full | REQUEST_CHANGES — 필수 F1~F8, Nit N1~N4 (mode0 보존, 쓰기 범위, host 테스트 경로, 기대값 모순 등) |
| v2 | `f4c61461…afc8` | (리뷰 안 함) | 총괄이 대조 중 잔여 결함을 찾아 v3 후보로 정정 → Fable 재검수 |
| v3 | `5838db25…3522` | delta | REQUEST_CHANGES — D1 Critical(rowdraw 인자 r3 덮어씀) + D2~D5 |
| v4 | `be049c13…90ae` | delta | REQUEST_CHANGES — D5 잔여(증거 보존 순서)만 필수 |
| v5 | `60a7574a…21b4` | consensus | **APPROVE** — D5 fixed, 설계·검증 조건 변경 없음 |

full → delta → delta 뒤 미승인이라 레포 규칙대로 합의(consensus) 회차로 넘어갔다. 3회차 v3의 첫 재검수는 출력 형식 오류(exit 7)로 무효였고, 같은 후보로 다시 돌려 published 됐다.

## 3. 이 승인이 뜻하지 않는 것

- 이 승인은 **계획**에 대한 것이다. 구현 코드의 최종 Astra 리뷰(PLAN §4.5 T7, `REVIEW-MODE: full`)는 별도이며 이 문서를 쓰는 시점에 **아직 진행하지 않았다(pending)**.
- secret-scan·커밋·push·main 병합도 pending이다. 총괄이 T7 뒤 이 절을 정정한다.

## 4. 수행 주체 — 「이 pc 하네스대로」

- 승인 계획 원문은 구현·테스트를 `harness-codex code`로 위임한다고 적었다(원 요청 당시의 주말 Codex 전용 지시를 반영).
- 2026-10-23 사용자가 company 경유로 「이 pc 하네스대로」라고 결정했다([`evidence/plan/ROUTING_UPDATE.md`](evidence/plan/ROUTING_UPDATE.md)). 이 맥 `harness-route` 판정이 이전 Codex 전용 지시보다 우선한다. 설계·검증·범위는 그대로이고, 리뷰는 고정 Astra read-only로 유지한다.
- 실제 효과: T1 첫 위임은 라우터가 code=claude로 판정해 `harness-codex`가 provider 전에 거부했다(exit 2, 생산 변경 0). 이후 T1~T6은 `harness-route code --risk high` 판정 **claude / `claude-opus-5-5` / effort high / local**대로 Orca 워커로 실행했다.

## 5. 워커 실행 영수증 (요청값 vs 실제값)

출처는 총괄 운영 기록(`temp/name-grid-phaseB/STATE.md`, 커밋 안 함)의 Orca task/dispatch 기록과 launch 확인이다. 전역 영수증 파일은 다른 프로젝트 실행도 섞여 있어 시각·역할만으로 이 작업에 귀속하지 않았다.

| 작업 | Orca task / dispatch | launch effective | 워커 보고서 RECEIPT |
|---|---|---|---|
| T1 자산 | `task_9d4d0dbfbb11` / `ctx_cb33685ff1e3` | claude-opus-5-5 / high / local | `effort=unknown` |
| T1 fix1 | `task_d22ab7f46d0f` / `ctx_ce4794e86921` | claude-opus-5-5 / high / local | `effort=high` |
| T2 코어 | `task_129c6529096c` / `ctx_89214c5c345c` | claude-opus-5-5 / high / local | `effort=unknown` |
| T3 빌더 | `task_d591699ea0d7` / `ctx_7b741ad5ee17` | claude-opus-5-5 / high / local | `effort=high` |
| T4 빌드 | `task_e7e283a4f2fe` / `ctx_19328acb517b` | claude-opus-5-5 / high / local | `effort=high` |
| T5 런타임 | `task_050ba844ee2e` / `ctx_24a758c40328` | claude-opus-5-5 / high / local | `effort=high` |
| T6 문서 | `task_899202347a37` / `ctx_3b9e975055c1` | claude-opus-5-5 / high / local | 이 작업 보고서 참조 |

워커가 쓴 `effort=unknown`은 워커가 자기 effort를 확인할 수단이 없었다는 뜻이다. launch가 확인한 실제값(high)과 다르게 해석하지 않는다. 연구 단계(native-re·candidate-re·list-link-re·mode-scope-re 등)는 이 결정 전이라 `harness-codex code`로 돌았다(이 작업 cwd로 확인된 영수증은 `gpt-6.1-sol`). 이들 보고서의 `RECEIPT: model=unknown`도 같은 이유다.
