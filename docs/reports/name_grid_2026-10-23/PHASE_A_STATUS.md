# 이름 입력 한글 조합 Phase A 종료 상태 — 2026-10-23

**전체 기능 BLOCKED:** 이 Mac에서는 nyarch 연결 경로·원본 ROM·b44·사용자 세이브·route/evidence가 복구되지 않았다. company로 요청 전달 완료이며 회신 대기 중이다. **ROM-free 참조 모델만 부분완료**다. 이 Mac에서 ROM 통합을 완료한 것이 아니며 실화면·실기·저장 후 cold reload는 `(unverified)`다.

## 구현·검토·push 식별

- 승인 PLAN v3: `temp/name-grid-resume/PLAN-v3.md`, SHA-256 `8e0d10339ec45664bf15b3cd970e2335d3dbdcdfdbf8df6cb851f63e009bf69c`. `PLAN-REVIEW-v3.md`의 `CONTEXT: match`, `AUTHOR: fable`, `VERDICT: APPROVE`에 연결된다.
- 테스트 당시 기준 HEAD: `a692987bd2313150631b5f02ba16d9e82a3d11bf`. 당시 구현 파일 해시·시험 명령·실제 출력·종료코드는 [COMPOSITION_SPEC.md](COMPOSITION_SPEC.md#실행-증거)에 보존했다. 13개 테스트, exhaustive 11,172 / reached 2,345 / random 20,000 / migration rejection 1,712이며 두 명령 모두 기존 로그에 `EXIT 0`이다. 이번 문서 정리에서는 테스트를 재실행하지 않았다.
- 구현 commit: `ad2ec49ca3e9b9ce8028ac751102bed0118dbb4d`, 브랜치 `sweep3-p2-20261023c`. 총괄 인계상 push 완료이며 로컬 `origin/sweep3-p2-20261023c`도 같은 SHA다. 이번 원격 재조회는 `Could not resolve host: github.com`으로 실패해 원격 현재 상태는 독립 재확인하지 못했다 `(unverified)`.
- 총괄이 기록한 검토 staged tree: `fcf486b9dd4c0166f734c3c3ea961811a5ebf970`. 로컬 구현 commit의 tree와 일치한다. 리뷰어는 tree를 직접 생성하지 않고 아래 staged blob 6개에 판정을 묶었다.

| 검토 파일 | Git blob |
|---|---|
| `AGENTS.md` | `097c03a5fdb4801595863d583633a8cf3506f430` |
| `CLAUDE.md` | `f82bc8113a7958f7cb1d5603ae0f140b0fcde193` |
| `docs/reports/name_grid_2026-10-23/COMPOSITION_SPEC.md` | `7b8bf1124bfbd66dcd93010f0e2b21645f665939` |
| `todo.md` | `8b906a17602bd5c0748428e33e08502053f64f07` |
| `tools/hangul_compose.py` | `7426352973f769db78bfc48aa7b7461544b5e7dd` |
| `tools/test_hangul_compose.py` | `834c9389a481058b008b952b319386bc8cae9153` |

Astra `REVIEW-MODE: full` 판정은 **승인**, Critical·필수·Nit 0 / FYI `[receipt]` 1이다. 원문은 `/Users/konest/.agent-harness/state/out/aw-kor-namegrid-phaseA-review-full-20261023.md`다. FYI는 prose 영수증의 `unknown`으로 실제 지정 모델을 판별할 수 없다는 내용이며, 아래 실행 메타데이터로 연결한다. 리뷰어는 테스트·빌드를 직접 실행하지 않았다. 이 판정은 구현 commit의 검토 파일에 적용되며 이후 문서 종료 변경까지 승인한 것으로 확대하지 않는다.

## 실제 실행 메타데이터와 prose 영수증 구분

출처: `temp/name-grid-resume/EXECUTION_METADATA.json`. 아래는 해당 실행 기록의 `effectiveModel`, `effectiveEffort`, `exit`, `ts`를 영구 보존한 것이다. `ts`는 기록 시각(UTC)이며 시작/종료 시각으로 재해석하지 않는다. 구현·plan-review·review prose의 `RECEIPT: model=unknown effort=unknown`과는 별도 근거다. 원문 영수증을 소급해서 수정하지 않는다.

| 역할·산출물 | effectiveModel | effectiveEffort | exit | ts (UTC) |
|---|---|---|---|---|
| plan-review v1 | gpt-6-astra | high | 0 | 2026-10-23T04:28:12Z |
| plan-review v2 | gpt-6-astra | high | 0 | 2026-10-23T04:39:29Z |
| plan-review v3 | gpt-6-astra | high | 0 | 2026-10-23T04:44:31Z |
| code Phase A | gpt-6.1-sol | medium | 0 | 2026-10-23T04:47:21Z |
| review Phase A full | gpt-6-astra | medium | 0 | 2026-10-23T04:55:18Z |

위 순서의 원문 산출물은 `/Users/konest/.agent-harness/state/out/` 아래 `aw-kor-namegrid-plan-review-v1-20261023.md`, `aw-kor-namegrid-plan-review-v2-20261023.md`, `aw-kor-namegrid-plan-review-v3-20261023.md`, `aw-kor-namegrid-phaseA-code-20261023.md`, `aw-kor-namegrid-phaseA-review-full-20261023.md`다. 실행 exit 0은 ROM 동작이나 전체 기능 완료를 뜻하지 않는다.

## 복구 목록·재개 조건

출처: `temp/name-grid-resume/ASSETS.md`. 아래 상태는 해당 원장을 옮긴 것으로 자산 재탐색·복구를 수행한 결과가 아니다.

| 자산 | 원장 상태·복구 후 조건 |
|---|---|
| 원본 ROM | 이 체크아웃에 없음. 복구 후 프로젝트 기록의 전체 SHA와 대조(prefix `a8ad7c7d`) |
| b44 정본 ROM | 이 Mac에 없음. 복구 후 SHA-256 `1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02` 대조 |
| 사용자 세이브·route | nyarch 원시 자료 없음. 출처·파일 SHA 기록, 사용자 원본 보존 후 `temp/` 사본만 사용 |
| 이전 sweep 캡처·RE trace | 인계 문서만 git에 보존. 원시 복구와 이번 재실행 증거 구분 |
| mGBA 라이브러리·헤드리스 실행파일 | 기존 로컬 경로에서 발견 못 함. ROM 복구 후 설치 버전·공식 빌드 경로 확인, 레포 `tools/mgba_harness.c` 사용 |
| Galmuri 원천 폰트 | `reference/fonts`에 추적됨. 현재 파일 유지 |
| OkDanDan-Bold.otf | 기본 로컬 폰트 경로에 없음. 정식 폰트 복구 후 `tools/aw_fonts.py` pinned SHA 대조 |
| Hada Sans Bold/Black | 별도 hada-font 레포에 존재. pinned SHA 대조 후 명시 env 경로 사용, 다른 세션 파일 변경 금지 |

company에서 nyarch 연결 경로 또는 접근 가능한 자산 경로를 받으면 **T0 자산 복구·SHA 검증 → 런타임 선행 조사 → 별도 Fable 계획·Astra 승인 → ROM 통합** 순서로 재개한다. 인터넷 ROM 입수는 하지 않는다. 참조 모델의 테스트 결과로 이 조건을 대체하지 않는다.

다음 단계의 조사·검증은 실제 입력 경로와 안전한 조합 상태 메모리, 16바이트 저장의 네이티브 계약, 공유 A3 가나 보존, 편집기 제목·저장/불러오기 목록·Versus·Link 네 소비자, 동일 상태 화면·실기·cold reload다. 상세 질문은 [COMPOSITION_SPEC.md](COMPOSITION_SPEC.md#phase-b-진입-전-연구-질문남은-위험)에 있다. 매핑 2350과 도달 2345를 구분하며, 공백 `0x8140`의 네이티브 의미는 계속 `(unverified)`다.

main **미병합·미배포**다. 이번 종료 정리는 `todo.md`, `COMPOSITION_SPEC.md`, 이 파일만 변경하며 커밋·push·후속 검토는 총괄 담당이다. 코드·테스트·빌더·ROM·규칙서 변경은 없다. 후속 지식 반영은 이 세 문서에 한정한다(사용자 지정 A4 범위).
