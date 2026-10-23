# 이름 입력 한글 조합 — Phase A 참조 명세 (2026-10-23)

## 범위와 상태

이 문서는 **ROM 비의존 순수 Python 참조 모델**의 계약과 검증 결과다. 이름 입력 기능의 ROM 통합 완료를 뜻하지 않는다. `tools/hangul_compose.py`와 `tools/test_hangul_compose.py`만 구현했고, 빌더·ROM·ASM·글리프·코드 할당·dist·사용자 저장은 변경하지 않았다. 코드 표 내보내기나 ROM 레이아웃 파일도 만들지 않는다.

승인 원문은 `temp/name-grid-resume/PLAN-v3.md`, SHA-256 `8e0d10339ec45664bf15b3cd970e2335d3dbdcdfdbf8df6cb851f63e009bf69c`다. 보고서 `PLAN-REVIEW-v3.md`의 `CONTEXT: match`, `AUTHOR: fable`, `VERDICT: APPROVE`와 파일 해시를 대조했다. Astra full 구현 검토는 승인됐고(Critical·필수·Nit 0, FYI `[receipt]` 1), 총괄이 구현 commit `ad2ec49ca3e9b9ce8028ac751102bed0118dbb4d`를 작업 브랜치에 push 완료했다고 인계했다. main 미병합·미배포이며 이번 문서 종료 정리의 커밋·push·검토도 총괄 담당이다. 검토 대상과 실제 실행 메타데이터는 [PHASE_A_STATUS.md](PHASE_A_STATUS.md)에 영구 연결했다. T0 자산 복구는 company 경유 요청 후 대기 중이다. 이 문서는 자산 복구를 증명하지 않는다.

## 상태와 문자 집합

- `committed: list[int]`는 확정 코드, `active: Active(L,V,T) | None`는 조합 중 한 슬롯이다. `len(committed) + (active is not None) <= 8`을 유지한다.
- `Active`는 불변 객체이며 L·V는 없는 경우 `None`, T는 받침 없음 `0`이다. 인덱스는 Unicode §3.12의 L 19·V 21·T 28 순서다. 완성 문자는 `0xAC00 + (L*21+V)*28+T`로 구한다.
- 선택 자모 33개: `ㄱ ㄲ ㄴ ㄷ ㄸ ㄹ ㅁ ㅂ ㅃ ㅅ ㅆ ㅇ ㅈ ㅉ ㅊ ㅋ ㅌ ㅍ ㅎ`, `ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅗ ㅛ ㅜ ㅠ ㅡ ㅣ`. 된소리는 별도 선택한다.
- 미리보기 자모 40개는 위 33개와 `ㅘ ㅙ ㅚ ㅝ ㅞ ㅟ ㅢ`다. Unicode 호환 자모이며 ROM 사설 코드가 아니다. 겹받침은 완성 음절 안에서만 사용한다.
- 완성 후보는 읽기 전용 `data/syllable_to_code_2350.json`의 키를 조회한다. 후보가 없으면 `not_in_2350`으로 **키 전체를 거부**한다. 다른 음절로 대체하거나 확정 후 새 초성으로 바꾸지 않는다.

## 전이

아래에서 조회·슬롯 검사 실패는 committed와 active 모두 원자적으로 불변이다. 동시에 여러 조건이 실패하면 원인은 먼저 수행한 검사에 따라 반환되며, 여러 실패 원인 사이의 우선순위는 약속하지 않는다.

| 현재 active | 자음 c | 모음 v |
|---|---|---|
| 없음 | 새 L-only (슬롯 필요) | 새 V-only (슬롯 필요) |
| L-only | `incomplete` 거부 | L+v 조회 후 적용 |
| V-only | `incomplete` 거부 | 복합 가능하면 V-only 갱신, 불가하면 `invalid_transition` 거부 |
| L+V | 종성 가능한 c면 L+V+c 조회. 조회 실패 시 그대로 거부. 종성 불가 ㄸ·ㅃ·ㅉ만 현재 음절 확정 + 새 L-only (슬롯 필요) | 복합 가능하면 L+V' 조회. 불가하면 현재 음절 확정 + 새 V-only (슬롯 필요) |
| L+V+T | 겹받침 가능하면 새 완성 후보 조회. 불가하면 현재 확정 + 새 L-only (슬롯 필요) | 홑 T는 앞 L+V / 새 T→L+v. 겹 T=(t1,t2)는 앞 L+V+t1 / 새 t2→L+v. **앞·새 음절 모두** 조회하고 두 슬롯 확보 후 함께 적용 |

종성 이동 예: `한+ㅏ → 하나`, `한+ㄱ+ㅏ → 한가`, `닭+ㅏ → 달가`, `값+ㅣ → 갑시`. `ㄴ+ㄱ`은 겹받침이 아니므로 `한+ㄱ`에서 한을 확정한다. 외부 리서치의 `한+ㄱ+ㅏ → 하나` 예시는 잘못된 것이며 채택하지 않았다.

`ㄱ,ㅐ,ㄷ`은 `개`에서 `갣`이 표 밖이므로 마지막 ㄷ을 거부한다. `개` 확정 + 새 ㄷ으로 진행하지 않는다. `간+ㅒ`도 새 `냬`가 표 밖이므로 `가`만 확정하지 않고 `간`을 그대로 보존한다.

| 작업 | 계약 |
|---|---|
| `confirm()` | 없음은 성공. 완성 active는 확정. L-only/V-only는 `incomplete` 거부하며 자모 유지 |
| `space()` | 미완성은 `incomplete` 거부. 완성은 확정 후 공백 한 슬롯. 없음은 공백 추가. 슬롯 부족이면 확정까지 취소 |
| `backspace()` | active 겹 T→t1, 홑 T→없음, 복합 V→앞 모음, L+V→L-only, 단독 L/V→없음. active 없으면 committed 마지막 코드 한 개 삭제. 모두 없으면 `empty` 거부 |
| `reset()` | committed와 active를 비움. 재진입은 reset 후 load, 참조 모델의 취소는 호출자가 reset |

8번째 슬롯이 active면 받침 추가·모음 조합·Backspace 같은 같은 슬롯 편집을 계속 허용한다. 새 L/V-only나 종성 이동 등 9번째 슬롯이 필요한 전이는 `no_slot` 거부한다. 저장된 `가`의 Backspace는 음절 삭제지만 입력 중 `가`의 Backspace는 `ㄱ` 미리보기로 돌아간다.

### 복합 모음·겹받침과 역분해

| 입력 두 자모 | 결과 | Backspace 후 |
|---|---|---|
| ㅗ+ㅏ | ㅘ | ㅗ |
| ㅗ+ㅐ | ㅙ | ㅗ |
| ㅗ+ㅣ | ㅚ | ㅗ |
| ㅜ+ㅓ | ㅝ | ㅜ |
| ㅜ+ㅔ | ㅞ | ㅜ |
| ㅜ+ㅣ | ㅟ | ㅜ |
| ㅡ+ㅣ | ㅢ | ㅡ |

| 입력 두 자모 | 결과 | Backspace 후 / 이동할 초성 |
|---|---|---|
| ㄱ+ㅅ | ㄳ | ㄱ / ㅅ |
| ㄴ+ㅈ | ㄵ | ㄴ / ㅈ |
| ㄴ+ㅎ | ㄶ | ㄴ / ㅎ |
| ㄹ+ㄱ | ㄺ | ㄹ / ㄱ |
| ㄹ+ㅁ | ㄻ | ㄹ / ㅁ |
| ㄹ+ㅂ | ㄼ | ㄹ / ㅂ |
| ㄹ+ㅅ | ㄽ | ㄹ / ㅅ |
| ㄹ+ㅌ | ㄾ | ㄹ / ㅌ |
| ㄹ+ㅍ | ㄿ | ㄹ / ㅍ |
| ㄹ+ㅎ | ㅀ | ㄹ / ㅎ |
| ㅂ+ㅅ | ㅄ | ㅂ / ㅅ |

홑 종성은 같은 호환 자음의 L 인덱스로 이동한다(`FINAL_TO_INITIAL`). ㄲ·ㅆ도 별도 선택된 홑 종성이므로 한 번에 제거·이동한다.

## API와 저장 계약

`Composer(table: dict[str,int])`는 표의 사본을 받아 메모리에서만 동작한다. 표는 `load_table(path=TABLE_PATH)`로 읽는다. 2350개 음절·16bit 비영 코드·코드 중복 없음을 확인하며 파일·JSON 오류는 예외로 전달한다. `code_for(table,L,V,T=0)`는 코드 또는 `None`을 반환한다. 두 함수와 `reachability_report(table=None)`는 파일을 쓰지 않는다.

- `press(jamo)`, `backspace()`, `space()`, `confirm()`은 성공·거부 모두 불변 `Result(accepted, reason)`을 반환한다. 성공 reason은 None. 거부 reason은 `not_in_2350`, `incomplete`, `no_slot`, `empty`, `invalid_transition` 중 하나다. 거부 전후 `snapshot()`은 같다.
- 선택 자모가 아닌 입력(복합 모음 직접 입력 포함)은 `ValueError`다. `press`에 공백 문자를 주는 대신 `space()`를 사용한다.
- `snapshot()`은 `(tuple(committed), active)` 불변 사본이며, `preview()`는 `('code', int)` / `('active', char)` 슬롯 목록이다. 미완성 자모는 preview에만 있다.
- `serialize()`는 **committed만** 빅엔디언 쌍으로 이어 정확히 16바이트를 반환한다. `가=0x8840 → 88 40`, 잔여는 0으로 채우며 8개면 종료자가 없다. 완성 active도 confirm 전에는 저장하지 않는다.
- `SPACE_CODE=0x8140`, `MAX_SLOTS=8`. 공백 상수는 리서치 인용 참조 모델 값이며 실제 네이티브 저장·렌더 의미는 **UNVERIFIED**다.
- `load(bytes16 | list[int])`는 정확히 16바이트 또는 최대 8개의 16bit 정수를 받는다. 구조 검증(정수 0..65535, bool 제외)은 전체 입력에 수행한다. 0/`00 00`은 종료자이며 그 뒤 유효한 값은 이름에 넣지 않는다. 성공하면 active는 비우고 committed를 교체한다. 잘못된 입력은 `ValueError`, 상태 불변이다.
- 불러온 비영 코드는 표 소속 여부를 검사하지 않는다. 예컨대 legacy `0x1234`, `0xFFFF`도 원래 두 바이트 그대로 왕복하며 Backspace로 한 코드씩 지운다. legacy 렌더 정책은 Phase B 조사 대상이다.

이 16바이트 계약은 **참조 모델**이다. 실제 RAM 객체 크기·종료자·저장 오프셋·체크섬·네이티브 빈 이름/취소 의미를 증명하지 않는다.

## 코드 매핑과 키열 도달 가능성

코드 매핑은 2350개다. 표준 키열의 모든 중간 완성 후보가 표에 있어야 해당 음절에 도달한다. 모음이 복합이면 첫 모음 단계와 복합 모음 단계, 종성이 겹받침이면 첫 종성 단계와 겹받침 단계까지 확인한다. 지원 2350개 전부 도달을 요구하지 않으며, 대체 입력이나 거부 완화로 수를 맞추지 않는다.

실제 계산 결과 **2345개 도달, 5개 도달 불가**다. 아래는 전 목록이다.

| 지원 음절 | 표준 키열 | 빠진 중간 후보 |
|---|---|---|
| 뢨 | ㄹㅗㅐㅆ | 뢔 |
| 썅 | ㅆㅑㅇ | 쌰 |
| 쏀 | ㅆㅖㄴ | 쎼 |
| 쓩 | ㅆㅠㅇ | 쓔 |
| 쭁 | ㅉㅛㅇ | 쬬 |

`reachability_report()`는 `{'mapped': 2350, 'reachable': 2345, 'unreachable': {음절: 누락후보 tuple}}` 구조를 반환한다. 이는 코드 매핑·키열 도달 분석이며 Python 소스의 분기 커버리지 수치가 아니다. 분기 커버리지 측정 도구는 실행하지 않았다.

## 실행 증거

당시 테스트 실행 기준 HEAD는 `a692987bd2313150631b5f02ba16d9e82a3d11bf`, 브랜치는 `sweep3-p2-20261023c`다. 당시 미커밋 구현 파일은 아래 SHA-256으로 식별하며, 이후 구현 commit `ad2ec49ca3e9b9ce8028ac751102bed0118dbb4d`에 보존됐다. Astra는 기준 HEAD에서 staged 6개 파일을 full 검토해 승인했다. 총괄이 기록한 검토 tree `fcf486b9dd4c0166f734c3c3ea961811a5ebf970`는 해당 구현 commit의 tree와 일치한다. 이번 종료 정리는 문서만 변경하며 테스트는 재실행하지 않았다. Python은 `Python 3.9.6`이다. 최초 타입 주석 평가 오류를 `from __future__ import annotations`로 해결한 뒤 아래 두 명령을 다시 실행했다.

| 파일 | SHA-256 |
|---|---|
| `tools/hangul_compose.py` | `7f442ca1ceb1cd6b98ca04135e9e0f6636747972dde63462fc95619fe65cb2d4` |
| `tools/test_hangul_compose.py` | `31676da9cda4dbe04a141512435b4e5613d6e818909978a7c643ce646e28cf7f` |
| `data/syllable_to_code_2350.json` (읽기 전용) | `7f4f32022d8af640cb628b418769dbf3e70e964a0740ba4b32c6ff017e26548f` |

명령과 실제 출력 요약(2026-10-23):

```text
$ python3 -I tools/test_hangul_compose.py
Ran 13 tests in 0.743s
OK
random_operations=20000 seed=20261023 rejections=17522
exhaustive=11172 reached=2345 rejected=8827 supported_unreachable=5
migration_rejection_cases=1712 example=('간', 'ㅒ', '가', '냬')
EXIT 0

$ python3 -I tools/hangul_compose.py --report
mapped=2350 reachable=2345 unreachable=5
뢨: missing 뢔
썅: missing 쌰
쏀: missing 쎼
쓩: missing 쓔
쭁: missing 쬬
EXIT 0
```

전체 stdout/stderr·명령·종료코드는 `temp/name-grid-resume/phase-a-tests.log`, `phase-a-report.log`에 있다. 요약은 이 문서에 영구 보존한다. 실행 시간은 이 실행의 관측값이며 성능 보장이 아니다.

테스트는 고정 키열과 기대 문자열(한글·강철·붉은달·4종 종성 이동), 7개 복합 모음과 11개 겹받침, 자모 역삭제, committed/active 구분, 8슬롯 경계, 원자적 공백/확인 거부, legacy 왕복과 정확한 저장 바이트를 확인한다. `가`의 `88 40`, 공백 `81 40`은 고정 바이트로 대조한다.

전수 검사는 모델의 분해 상수를 쓰지 않는 별도 키열 목록과 Unicode 산술로 11,172음절의 중간 후보를 계산한다. 모델을 import하지 않고 읽은 원본 JSON과 비교해 첫 실패 키에서 `not_in_2350`과 snapshot 불변을 검사한다. 지원 음절 누락 목록도 별도로 계산해 보고서와 대조한다. `갣`과 위 5개 누락 중간 후보는 원본 JSON 부재를 직접 확인한다. 모델의 자체 보고만을 정답으로 삼지 않는다. 추가로 1712개 실제 종성 이동 거부와 결정적 시드의 20,000개 조작에서 상태 불변식을 검사했다. 이는 무한 키열이나 ROM/ASM 동일성의 증거가 아니다.

## Phase B 진입 전 연구 질문·남은 위험

T0 원본 ROM·b44·사용자 세이브·route/evidence·mgbah 복구와 해시 대조는 총괄 담당이다. 인터넷에서 ROM을 입수하지 않는다. 런타임 조사 후 별도 Fable 계획 + Astra 승인 전에는 ROM 구현을 시작하지 않는다.

- 선택 표→그리기 표→자모 ID 전달 경로, 훅 PC·레지스터·보존 명령은 무엇인가?
- 조합 상태를 둘 안전한 메모리와 수명, 초기화·취소·재진입 경로는 무엇인가?
- START/OK/공백/B/R/특수 셀의 실제 의미와 8번째 active 편집·거부 시 append 차단 경로는 무엇인가?
- 라이브 버퍼와 16바이트 저장 필드의 용량·종료자·주변 필드·오프셋·체크섬은 무엇인가?
- 자모 40개를 둘 사설 글리프·예약 코드 풀과 A3 훅 범위, 조회표/코드 주입 구간의 실제 여유·점유는 무엇인가? 공유 A3 가나 그림은 보존해야 한다.
- 편집기 제목·저장/불러오기 목록·Versus·Link의 네 소비자가 새 예약 음절을 그리는가? legacy와 미리보기 폴백 정책은 무엇인가?
- 후보 ROM·같은 빌드 map/manifest·기준 ROM SHA·동일 상태 화면을 지정한 QA 및 Python↔ASM 전이 대조를 어떻게 재현할 것인가?

실화면·실기·저장 후 cold reload·소비자 회귀·공유 글리프 게이트는 **아직 안 돌렸다 (unverified)**. Phase A 준비를 전체 이름 입력 완료로 집계하지 않는다. 이번 문서와 AGENTS.md·CLAUDE.md·todo.md에 후속 계약을 반영했다. 새 ROM RE 사실이나 검증된 ROM 성공/실패는 없으므로 research/success/fail 이력은 변경하지 않았다.
