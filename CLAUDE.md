# Game Wars 한글화 프로젝트 — Claude 작업 지침

> 대상 게임: **Game Boy Wars Advance 1+2 (GBA, 일본판)** 한글화
> **최종 목표(현재)**: 원본 ROM을 패치해 **실기(real GBA hardware) 및 에뮬레이터에서 한글이 정상 출력**되게 한다. (배포는 BPS 패치)

## 언어 설정
모든 응답은 **한국어**로 작성합니다.

---

## 단계별 기록 (2026-05-27 기준·후속 추가 포함)

> 최신 진행·미해결 오류는 `todo.md`를 따른다. 아래의 완료 표시는 개별 기능의 구현·검증 기록이며, 두 편 엔딩 도달·전 장면 검수·배포 승인을 뜻하지 않는다.

| 항목 | 상태 |
|------|------|
| 텍스트 번역 | ✅ 사실상 완료 — `data/translation_for_import.csv`에 한글 18,262행. QA(lint) error 0. 용어 5종 통일. |
| 대화 렌더 메커니즘 | ✅ **완전 RE + 인게임 PoC 3건 검증**(FONT_BASE 주입 / 멀티음절 / **예약코드→테이블→한글**). 해당 대화 출력 경로 입증. |
| 한글 폰트 풀빌드 | ✅ **완료** — `tools/build_korean_full.py`(base=**원본 ROM**, 기본값 `P.ROM`; `output/v56_polished.gba`는 부재/구버전이라 `--base`로만 지정) → `output/game_wars_korean_full.gba`. 음절 글리프 주입 + 한자테이블 확장 + 예약코드 인코딩. **2026-06-16: 폰트 1030→2350자(KS X 1001 완성형) additive 확장** (`data/syllable_to_code_2350.json`/`kor_glyphs_2350.bin`/`syllable_to_glyph_2350.json`, `tools/build_korean2350.py`). 기존 byte-identical 호환. |
| 한글화 도구체인 (2026-06-16, muramasa-kor 참조) | ✅ **통일사전** `data/proper_nouns.json`(`tools/export/apply_proper_nouns_dict.py`, 카테고리형 정본 — 구 generic `export/apply_proper_nouns.py`는 deprecated→`proper_nouns_inconsistencies.json`). **대사맵** `data/dialogue_map.json`(`tools/build_dialogue_map.py`). **대사 편집기** `tools/dialogue_editor/server.py`(:8780, JA→KO+사전 CRUD+사전검사). **스프라이트 픽셀에디터** `tools/sprite_editor/server.py`(:8781, 4bpp 인덱스+팔레트 페인트). **스프라이트 인덱스** `tools/export_sprites.py`→`data/sprites_index.json`. ✅ PRAM 팔레트 캡처 완료(2026-06-28, 대표 title/select/menu + 전투/CO/유닛 current-state route, `data/sprite_palettes.json` 176 unique/BG92/OBJ84 + route/state/raw dump SHA). ⚠ 잔여: 실화면 시각회귀 QA, LZ77 ROM 역기록, 미번역 1097종 triage. |
| 1편 이름 그리드 | ✅ **완료** — 좌 A-Z / 중 a-z(빈칸 없음, 대문자와 매칭) / 우 0-9(기호행 제거). 선택·미리보기 정상. 실배치 ROM 0x08DF8C38 계열 패치. |
| 2편(Advance 2) 한글 | ✅ **완료** — 타일맵 렌더 3경로(0x313F8C / 0xB11BB0 / 0xA3C7E4) hook으로 한글 렌더. **반각 공백** + **1편과 동일 11×11 galmuri**. 낱한자/감탄사 발견분 정리. |
| ROM 빌드/부팅 | ✅ 체크섬·삽입 안전, 부팅 OK(흰 화면 해소). |
| 에뮬레이터 검증 | ✅ **brew `mgba 0.10.5` + mgbah 헤드리스 디버거**(`loadstate` 추가). **합성 키 입력 작동**(헤드리스 네비 가능). |
| 잔여 | ⏳ 텍스트 overflow 0. 대사 단어붙음 **362라인 해소**(Part2 메시지테이블 + Part1 커맨드스트림 0x19 repoint, 2026-06-23 런타임 트레이싱). 잔여 117(0xB8/0xEC 비-0x19 + 다중참조/merged/wide skip). · 실기(real GBA) 테스트 |

**다음 작업 기준(필독 순서)**:
1. [`todo.md`](todo.md) — **현재 유일한 진행 기준**. 완료/대기/우선순위는 여기만 갱신한다.
2. [`docs/DIALOGUE_KOREAN_IMPLEMENTATION_PLAN.md`](docs/DIALOGUE_KOREAN_IMPLEMENTATION_PLAN.md) — 구체 구현 로드맵 참고.
3. [`docs/research.md`](docs/research.md) 맨 끝 — 대화 렌더 파이프라인 완전 RE(주소·테이블·공식).

### 알려진 핵심 사실 (반드시 인지 — 2026-05-25 갱신)
- ✅ **체크섬·삽입 버그 — 해결됨**: `execute_phase5_5.py:21` 올바른 식, `execute_phase5_4.py`는 슬롯 길이 제한 + 코드영역 skip. 부팅 검증(코드영역 변경 0바이트).
- ✅ **대화 한글 렌더 — 메커니즘 검증됨 (이전 "hook 필요/FONT_BASE 안 통함" 결론은 틀렸음)**:
  - 대화 글리프는 **FONT_BASE(0x08B974D0)+idx*0x20 비압축 타일을 per-char 복사**(IWRAM 0x03006744, 팔레트 리맵). 그 자리에 galmuri 글리프(ink 인덱스 10) 주입 → **대화 한글 렌더 인게임 확인**. ASM hook 불요.
  - SJIS→글리프 변환: IWRAM 0x030065E0(**ROM 소스 0x08EFE788**). 한자(>0x8397)는 **테이블 0x08B80B7C**(530엔트리×6B=[SJIS_LE,top_idx,bot_idx], 끝 0x08B8180C) 검색. **안 쓰는 한자코드 예약→테이블→한글 글리프** 렌더 PoC 성공(0x8AEF→"테").
  - 풀게임 구현 = 예약코드(미사용 SJIS 3326풀, `data/reserved_codes.json`) + 글리프 주입 + 테이블 확장 + 인코딩. (build_grid의 per-screen hook은 구식 — 이제 데이터만으로 가능)
- ✅ **1편 이름 그리드 — 실배치는 ROM 0x08DF8C38 계열**(행 SJIS 문자열, `0A 09` prefix + `0A 00 00 00` terminator). 렌더 루틴 0x08B48910~60, 미리보기 0x08B48E50. ⚠ SET1(0x83FAF6)/SET2(0x83FE41)/charlist(0x80505c)는 **死 데이터**(편집 무시됨). 슬롯: 대문자 A-Z=128~143/160~169, 소문자도 동일 패턴. n/p 바닥슬롯 충돌 → KANA_REMAP로 회피.
- ✅ **2편(Advance 2) — 타일맵 렌더러**(idx→BG 타일맵 strh, per-char 글리프 복사 아님): 0x08313F8C(Advance2) / 0x08B11BB0(공통) / 0x08A3C7E4·IWRAM 0x03006080(MODE SELECT/PROLOGUE 글리프캐시 = "?" 출처). A3는 0x08314270 char 디스패치 점프테이블(0x20 엔트리=0x083142CC). bit15 한글코드(0x8840~0x9369)를 KOR_BASE(0x08F00000)에서 VRAM 복사하도록 hook. 2026-09-23 소비자 구분: 313/B11 타일맵 경로의 0x20은 1타일(8px) 전진하지만, 31424C 스크립트 파서는 31431C에서 위치 이동 없이 소비한다. A3 글리프 호출만으로 스크립트 파서까지 확인됐다고 판단하지 않는다.
- **추출 노이즈**: `game_wars_found_texts.csv`의 상당수는 깨진 문자(무작위 한자+키릴+기호) — 번역/삽입 대상 아님.

---

## 번역 작업 방식

### JEV 보조 분류 (2026-09-30)

- 사용자 요청으로 `tools/jev_triage.py`와 `config/jev.json`을 추가했다. 사용법/실험 한계는 [`docs/JEV.md`](docs/JEV.md).
- `JEV_API_KEY`는 환경변수로만 사용하고 출력·커밋하지 않는다. 기본은 dry-run이며 명시적 `--live`일 때 선별한 완결 대사 최대8개만 전송한다. 키/ROM/전체 저장소를 업로드하지 않는다.
- 게임 파일럿은 [`docs/JEV.md`](docs/JEV.md)의 체크포인트 결합 `jev` 선택 경로를 사용한다. 상태 추출과 합법 후보 생성은 아직 수동이며, 제한된 로컬 매크로만 실행한다. Codex 토큰 절약 효과는 수치 검증 전까지 주장하지 않는다.
- 의미 누락·왜곡의 검토 우선순위 보조만 맡긴다. 애매한 결과도 검토 대상으로 유지하며, 낮은 확률을 승인으로 삼거나 번역/보호 기준을 자동 수정하지 않는다. 빌드·배포·기존 QA에는 자동 연결하지 않는다.
- API 설정 요청 자체는 게임 진행 재개 권한으로 해석하지 않았다. 이후 사용자가 게임 자동 진행 파일럿을 명시적으로 재개했고, (당시 지시: Codex 주간 사용량 중단선 미적용 — 2026-10-05 아래 「주간 사용률 상한」 30% 기준으로 대체됨.) RAM·디스크 여유도 계속 확인한다.

### 주간 사용률 상한 (2026-10-05 사용자 지시, 최신)

- Claude 로 인계된 이후 **Claude·Codex 각 계정의 주간 사용률이 30% 이상이면 새 입력/새 작업을 시작하지 않는다.** 이 기준은 사용한 비율이 30%라는 뜻이다. 30%를 추가로 쓰거나 30%가 남을 때까지 쓴다는 뜻이 아니다. 이전의 20%·40% 기준과 2026-09-30의 「사용량 무시」 지시는 이 기준으로 대체됐다.
- 확인은 `harness-usage` 의 신선한 관측(`observed` 15분 이내)으로 한다. 관측값이 없거나 오래됐으면 한도에 도달한 것으로 보고 무제한으로 실행하지 않는다. Codex 는 `temp/part2_2026-09-23/check_codex_usage.py` 를 `THRESHOLD=30` 으로 읽기 전용 실행해 확인할 수도 있다. 디스크에 기본값 70이 남아 있으므로 main 으로 실행하지 않는다.
- 2026-10-06 사용자 추가: Claude·Codex 중 주간 사용률이 더 낮은 쪽을 우선 사용해 부하를 조절한다(각 30% 상한은 유지).
- 한도에 도달하면 체크포인트·로그를 정상 저장하고 종료한 뒤 보고한다. 계정 사용률을 RTK 절감률이나 컨텍스트 토큰과 혼동하지 않는다.

### 토큰·컴퓨터 자원 절약 원칙 (2026-09-23 사용자 지시)

- **임무 시작 조건을 먼저 확정한다(2026-10-02 재발 방지).** 지휘관별 경로의 게임 내 승리·패배 조건, 제한 일수, 보호 대상, 생산 가능 여부를 실제 화면으로 확인하고 기록한 뒤 턴을 종료한다. 공략의 랭크 권장 일수와 강제 제한을 혼동하지 않는다. 제한을 확인하지 못했으면 무제한으로 간주하지 않는다. 적의 숨은 위치·병종을 추측으로 확정하지 않고, 엔딩 진행이 목적일 때 불필요한 전멸·고득점보다 실제 승리 조건을 우선한다.
- **입력 전송과 행동 성공을 구분한다(2026-10-02 재발 방지).** 단순 방향 이동만 묶고, 메뉴·이동 확정·공격·생산처럼 분기가 있는 경계를 여러 유닛에 걸쳐 한 번에 넘기지 않는다. 유닛별 이동·생산 후 실제 화면과 허용된 아군 상태를 대조한 뒤 다음 행동으로 넘어간다. 명령이 전송됐다는 이유로 방어 배치·생산·점령 완료를 보고하거나 턴을 종료하지 않는다. 육상 사거리 밖이라는 사실을 적 잠수함 등 다른 병종에도 안전하다는 결론으로 확대하지 않는다.
- **관측된 공격 범위를 이동 전에 계산한다.** 미사일·로켓포·전함 등 확인한 위협의 좌표/사거리와 목적지 거리를 대조한다. 과거 위치와 현재 확인을 구분하고, 안개 속 빈칸이나 적의 제거를 추정으로 확정하지 않는다. `temp/continuation_2026-10-02/threat_check/README.txt`의 읽기 전용 계산기는 기하학적 보조 검사일 뿐이며 경고 없음도 안전을 뜻하지 않는다.
- **지휘관 선택·저장·임무 전환을 넘는 A 입력은 묶지 않는다.** 전환 화면마다 확인하고, 첫 턴 전에 실제 선택 지휘관과 승리 조건을 기록한다. 검증된 반복 입력도 실제 배치/체력/AI 행동이 달라지면 중단하고 현재 상태에 맞춰 다시 계획한다.

외부 파이프라인 대조와 게임별 분야·도구 적용 범위는 [`docs/LOCALIZATION_GATES.md`](docs/LOCALIZATION_GATES.md)의 「외부 게임 한글화 파이프라인 대조」를 따른다. 같은 검증이 이미 있으면 반복 도구를 만들지 말고 기존 증거를 재사용한다.

**검수 순서(2026-09-23 사용자 추가 지시):** 최종 ROM 전수 검사 → 문맥 단위 번역 검수 → 화면별 짧은 재현 → 남은 전체 플레이·엔딩 검증 순으로 진행한다. 전투를 진행해야만 오류를 찾는 방식의 비중을 줄인다. 기존 정상 저장과 입력 기록은 보존하며, 정적/진단 검사를 엔딩 도달 증거로 대신하지 않는다.

- 전수 검사는 native 포인터·검증된 span·실제 소비 렌더러에 묶인 최종 ROM payload를 검사한다. 짧은 제목/재배치 제목도 포함하며 인코딩, 제어, 등록 글리프, 실제 합성줄 폭, 이름표 매핑을 구분한다.
- 검사 대상 수와 미지원·미검증 경로를 함께 보고한다. 추출 노이즈나 일반 맵명의 별도 폰트에 다른 렌더러의 규칙을 적용하지 않는다. 알 수 없는 제어를 무시한 green check를 만들지 않는다.
- 스프라이트는 native 자산 목록과 기존 기록의 VRAM/OAM/팔레트 소비 근거를 우선 대조한다. 가능하면 이미 저장된 같은 ROM의 상태에서 읽기 전용 추출하고 새 에뮬레이터를 띄우지 않는다.
- 문맥 검수는 조립된 문장과 원문의 조건·부정·주체·조사·중복을 개별 확인한다. 확인된 수정은 기존 도구로 반영하고 해당 화면만 짧게 재현한다.
- **2026-09-30 사용자 갱신:** Codex 사용률 한도는 적용하지 않는다. 사용자는 계속 진행을 요청했으며 RAM·디스크 사용량만 주의한다. `playthrough_capture.py`는 디스크 최소 보존 여유를 자동 검사한다. RAM/swap은 실행 전후 `vm_stat`/`sysctl vm.swapusage` 및 프로세스 RSS로 수동 확인하고, 압박이 커지면 체크포인트 후 안전하게 멈춘다.

- **검증된 구조를 먼저 재사용한다.** 폰트 코드→글리프, 제어문자, 포인터, 압축·팔레트·스프라이트 배치와 소비 렌더러를 기존 코드·RE 기록에서 확인한다. 새 사실은 근거 ROM SHA/주소/재현 명령과 함께 기록하며, 이미 확정한 구조를 매번 AI로 재분석하지 않는다.
- **반복 작업은 로컬 도구로 처리한다.** 글리프 생성·굵기/자간/AA 비교, 인코딩·문자 누락·행폭·슬롯·제어 바이트 검사, 추출/재삽입, 빌드, 입력 재생, 해시·화면 차이 수집을 결정적인 스크립트로 수행한다. 기존 도구를 먼저 찾고 확장하며, AI는 새로운 원인 분석·번역 의미·시각 판단에 집중한다.
- **표시 경로별 제약을 구분한다.** 1·2편 대화/메뉴/시스템 문구의 슬롯 크기, 줄·페이지 폭, 확장·재배치 가능 여부를 각각 확인한다. 다른 렌더러의 규칙을 복사하거나 폭에 맞추려고 의미를 삭제하지 않는다. 인코딩/배치 실패는 빌드 오류로 남긴다.
- **번역 데이터와 도구를 분리한다.** 원문·주소·제어 토큰을 보존한 CSV/JSON/TSV를 기존 빌드로 반영한다. 저비용 번역 모델은 명시적으로 선택된 경우 초안에 활용하되, 모델 변경·번역 API 호출을 자동 추가하지 않는다. 기존 번역 및 B팀 보호 범위를 유지한다. 자동 검사는 의미·말투 검수와 실화면 확인을 대체하지 않는다.
- **필요한 문맥과 결과만 읽는다.** `rg`로 주소/함수/실패 항목을 찾은 뒤 해당 범위만 읽는다. 큰 로그·ROM 덤프·전체 번역표를 대화에 반복 출력하지 않는다. 상세 증거는 파일에 남기고 변경점·실패 요약·재현 명령을 공유한다. 동일 입력/도구/ROM SHA의 검증 결과는 재사용하되 변경된 소비 경로의 검증은 다시 수행한다.
- **저부하 병렬 실행을 기본으로 한다.** 파일 소유권을 나눠 충돌을 피한다. 전체 ROM 빌드와 대량 재생/영상 변환은 한 번에 하나씩, 정상 플레이 하네스는 편당 하나·최대 둘로 제한한다. 별도 진단 하네스가 필요하면 해당 플레이를 멈춘 상태에서 짧게 실행한다. 무거운 작업은 가능하면 `nice -n 15`로 실행하고 메모리·CPU·디스크 여유를 확인한다. 입력 없는 에뮬레이터는 정지시키고 무한 폴링/동일 리뷰 재호출을 피한다.
- **절약과 완료 판정을 분리한다.** 정상 입력 플레이·전 프레임 증거·ROM 식별·회귀 검사·필수 적대 리뷰를 생략하지 않는다. 캡처/정적 QA 통과를 전 장면 육안 검수나 엔딩 도달로 집계하지 않는다. 사용자 개입 없이 계속하라는 현재 요청에 따라 이미 승인된 수정·검증은 자율 진행한다.

#### 2026-10-02 실행 로그·정상 저장 전환

**2026-10-02 사용자 캡처 정리 지시:** 문제가 없는 캡처를 정리하면서 임무를 계속 진행한다. 기존의 일괄 캡처 보존 규칙보다 이 지시가 우선한다. 우선 종료된 실행의 재생성 가능한 contact sheet를 정리하고, 오류·수정 전후·승리 화면과 개별 endpoint, 원본 frames, 원장, 체크포인트, 정상 저장은 유지한다. 미검수 화면을 정상 검수 완료로 취급하지 않는다. `tools/prune_capture_sheets.py`는 원본 프레임으로 시트 전체 RGB가 동일하게 재구성되는지 확인하고 복원 영수증을 fsync한 뒤 시트만 삭제한다. `--restore RECEIPTS_JSONL`로 같은 RGB를 복원할 수 있으며 PNG 압축 바이트는 다를 수 있다. 기록된 Pillow/FreeType/폰트 환경이 필요하다. 기존 actions의 시트 경로는 이 영수증을 통해 복구하며 visual_review 상태는 바꾸지 않는다. 정리 중 해당 실행의 새 증거 참조를 다른 작업자가 추가하지 않는다.

- 새 `playthrough_capture.py` 실행에는 검증된 `--gzip-emulator-log` 옵션을 사용한다. native 로그만 제한된 FIFO 버퍼로 gzip 저장하며 게임 입력·stdout 응답·프레임 증거는 기존 경로를 유지한다. 종료 때 원문 스트림과 복원 SHA/길이를 검증하고 receipt를 남긴다. 실패 receipt를 정상 종료로 취급하지 않는다. 실제 하네스의 짧은 시작/종료 시험은 통과했으며 장시간 처리 비용은 실제 실행에서 계속 측정한다.
- 새 프레임의 디스크 절약 선택 옵션은 `--lossless-palette-frames`다. 256색 이하이고 전체 RGB 픽셀이 일치하며 실제 PNG도 더 작을 때만 palette로 저장하고, 나머지는 RGB로 저장한다. 원장 RGB SHA·프레임 수·endpoint·sheet는 유지한다. 부모/자식 PNG 저장 모드가 달라도 RGB 검증은 동일하다. 인코딩 CPU 비용이 증가하므로 실제 처리 시간과 공간을 함께 측정한다. 이미 실행 중인 하네스에는 소급 적용되지 않는다.
- 정상 저장을 내보내고 곧바로 다른 후보 ROM을 부팅할 때는 `--export-game-save CHECKPOINT --export-game-save-out NEWDIR`로 동일 프로세스에서 진행할 수 있다. 다른 ROM으로 정상 SRAM을 이관할 때는 `--game-save-source-rom-sha256 SOURCE_SHA`도 명시한다. savestate를 다른 ROM에 이식하지 않는다.
- 위 선택 경로는 실제로 검증한 PNG 바이트 SHA/RGB 결과를 제한된 메모리에만 보관한다. 후속 검증에서 파일 전체 바이트 SHA가 같은 경우에만 디코딩을 생략하며, 변경되면 원래 RGB 검증을 수행한다. 원장·부모 연결·ROM·상태·SRAM 검사는 유지한다. 디스크 캐시를 임의로 신뢰하거나 진행 중인 검증을 중간에 건너뛰지 않는다.
- 전체 빌드·대량 재생·영상 변환의 직렬 제한을 모든 읽기 전용 해시 검증의 직렬 제한으로 확대하지 않는다. RAM·swap·디스크 여유를 확인한 뒤 읽기 전용 검증은 낮은 우선순위로 최대 두 개 병행할 수 있다. 메모리 압박이 생기면 하나를 일시 정지한다. 정상 플레이/진단 하네스의 총 두 개 제한은 그대로다.
- macOS에서 대량 검증/압축과 플레이 캡처가 디스크 I/O를 두고 경합하면 `nice`만으로 충분하다고 가정하지 않는다. 소유한 작업의 PID·명령을 확인한 후 `taskpolicy -b -p PID`로 배경 I/O 우선순위를 시험하고 같은 길이 입력의 wall time과 공간 회수 속도를 함께 기록한다. 필요하면 `taskpolicy -B -p PID`로 복원한다. 2026-10-02 A180 각5회 표본 평균8.576→3.643초는 화면·캐시가 다른 비통제 관측이며 전체 플레이 배속으로 일반화하지 않는다.
- 이미 열린 거대 로그를 `copytruncate`하지 않는다. 정상 종료/체크포인트 보존 후 열린 파일이 아님을 확인하고, gzip 복원 SHA와 원본 불변을 검증하고 receipt를 fsync한 다음 원본 로그만 제거한다. 프레임·세이브·원장은 삭제하지 않는다.

참고: 사용자가 제공한 시놀부의 「AI를 활용한 한글화 작업을 할 때 토큰을 절약하는 방법입니다」(2026-09-22). 특정 플랫폼의 구조는 그대로 적용하지 않고 이 프로젝트의 GBA 검증 사실을 따른다.

- **원칙(문서화된 방법)**: `python tools/phase4_codex_translate.py` (Codex CLI 배치 번역).
- **현실/대체**: codex가 rate-limit이거나 macOS에서 codex 경로가 안 맞을 때는 **Claude가 직접 3개 에이전트 병렬로 번역**한다. 파이프라인:
  ```bash
  python tools/loop_prepare_batch.py 600 3   # 실제 텍스트만 필터링해 in_1~3.csv 생성
  # (에이전트가 data/_work/out_N.txt 에 address|korean 기록)
  python tools/loop_merge.py                 # translation_for_import.csv 병합
  ```
- 번역 톤/용어: `docs/TRANSLATION_GUIDE.md`, `docs/TRANSLATION_TONE_AND_STORY_GUIDE.md` 준수.

## ROM 빌드 / 검증

```bash
python3 tools/build_korean_full.py   # ★현재 메인 빌드: base=원본 ROM(기본) → output/game_wars_korean_full.gba  (v56_polished는 부재/구버전, --base로만 사용)
                                     #   (음절 글리프 주입 + 한자테이블 확장 + 예약코드 인코딩 + 1편 그리드 + 2편 hook + 체크섬)
# (구식: execute_phase5_4/5.py — 이제 build_korean_full.py로 통합)
# 헤드리스 검증: tools/mgba_harness.c를 temp/ 아래에 빌드한다. 네비 스크립트도 temp/에 둔다.
# ROM 교체 시에는 정상 게임 저장을 cold boot로 읽고 save SHA를 검증한다. 다른 ROM의 savestate를 재사용하지 않는다.
# 에뮬레이터 실행(검증):
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/mgba -3 output/game_wars_korean_final.gba
```

### emucap MCP 보조 디버깅
- 설치 위치: `/Users/tarucy/.local/share/emucap` (`cargo build --release` 완료).
- GBA용 MesenCE 2.2.1 Apple Silicon 설치: `/Users/tarucy/.local/share/emucap/mesen/2.2.1/Mesen.app`.
- GBA BIOS는 커밋하지 않고 로컬 RetroArch BIOS를 참조한다: `EMUCAP_GBA_BIOS=/Users/tarucy/Documents/RetroArch/system/gba_bios.bin`.
- Codex MCP: `emucap-control`, `emucap-track` 글로벌 등록 완료.
- Claude MCP: 프로젝트 `.mcp.json`에 같은 `emucap-control`, `emucap-track` 등록 완료. Claude Code에서 처음 열 때 pending approval을 승인해야 한다.
- 런타임 홈/로그와 Tracking ledger는 프로젝트 루트가 아니라 `temp/emucap-emu-home`, `temp/emucap-ledger`를 사용한다.
- 용도: 사용자 제보 화면을 재현할 때 memory/screen/input/breakpoint를 에이전트가 직접 확인하는 보조 RE 도구.
- 한계: `emucap`은 v0.4 beta라 인터페이스/동작이 바뀔 수 있다. 기존 `tools/*` + `temp/mgbah` release QA를 대체하지 않는다. 배포 판정은 계속 `verify_dist_integrity.py`와 `run_release_qa.py`를 권위로 삼는다.

### QA 도구 (전체 점검)
```bash
python3 tools/qa_integrity_map.py        # 빌드 무결성맵(temp/integrity_map.json)↔ROM 1차 게이트 + 부호소실/中점 검사 (권위)
python3 tools/qa_text_fit.py             # 슬롯 fit/overflow/no_ko/visual-wider
python3 tools/qa_ascii_residuals.py --general   # 영어 UI 잔존 전수
python3 tools/qa_placeholder_residuals.py       # placeholder ROM hit
python3 tools/phase6_basic_test.py output/game_wars_korean_full.gba   # 부팅/체크섬/한글(예약코드) 검출
python3 tools/verify_dist_integrity.py   # 배포 manifest↔output↔BPS/IPS 3중 해시 게이트(배포 전 PASS 필수)
```

### 편집기 (웹, stdlib http.server, 외부 의존성 0)
```bash
python3 tools/dialogue_editor/server.py  # :8780 대사 JA→KO 편집 + 통일사전 CRUD + 사전검사
python3 tools/sprite_editor/server.py    # :8781 스프라이트 4bpp 픽셀 페인트(팔레트)
# 데이터 재생성(gitignored): python3 tools/build_dialogue_map.py / tools/export_sprites.py
```

---

## 폴더 / 문서 구조

```
aw-kor/
├── CLAUDE.md              # (이 파일) 작업 지침 + 구조 안내
├── README.md              # 프로젝트 개요
├── CONTRIBUTING.md        # 기여 가이드
├── requirements.txt       # Python 의존성
├── .project-config.json   # 프로젝트 설정
├── .claude/               # settings.json(Codex+Claude 리뷰 안내 훅)
│
├── original/              # 원본 자산 (git-ignored *.gba)
│   ├── Game Boy Wars Advance 1+2 (Japan).gba        # 원본 ROM (16MB)
│   ├── ...(Japan)_backup.gba                         # 원본 백업
│   └── visualboyadvance-m.app                        # (구) 에뮬레이터 — 캡처 안 됨, mgba 사용 권장
│
├── data/                  # 번역 데이터
│   ├── game_wars_found_texts.csv      # 추출된 원본 텍스트 (28,347행, 노이즈 포함)
│   ├── translation_for_import.csv     # ★메인 번역본 (address,japanese,korean,length)
│   ├── translation_*.csv / *.backup   # 각종 백업/리뷰/리워크 버전
│   ├── manual_translation_batch_*.csv # 수동 번역 배치
│   └── _work/                         # (생성) 에이전트 병렬 번역 작업 디렉터리
│
├── tools/                 # 모든 스크립트
│   ├── 추출:   extract_text*.py, find_japanese_text.py, quick_text_extract.py
│   ├── 번역:   phase4_codex_translate.py, loop_prepare_batch.py, loop_merge.py,
│   │           translate_*.py, claude_batch_translate.py
│   ├── 폰트:   font_dump.py(타일 렌더), analyze_rom_font_structure*.py,
│   │           locate_font_data.py, trace_font_pointers.py, configure_font.py,
│   │           font_preparation_framework.py, generate_tbl.py, game_wars.tbl
│   ├── ROM빌드: execute_phase5_4.py(삽입), execute_phase5_5.py(최종화),
│   │           import_text*.py, update_pointers.py, build_rom.py, build.sh/.bat
│   ├── 검증:   phase6_basic_test.py, test_*.py, audit_translation_completion.py
│   ├── QA(무라마사 이식): lint_translation.py(품질검수), export/apply_proper_nouns.py(용어통일),
│   │           fix_punctuation.py, reflow_dialogs.py, repair_hex_corruption.py(손상복구)
│   ├── 대화한글화: find_reserved_codes.py(예약코드풀), render_galmuri_8x16.py·galmuri_cell.py·bdf.py(글리프),
│   │           mgba_harness.c(/tmp/mgbah 헤드리스 BP/watch/네비)
│   └── 분석:   analyze_rom_header.py, find_pointers.py, analyze_translation_patterns.py
│
├── output/                # 재생성 가능한 빌드 산출물 (git-ignored *.gba)
│   ├── game_wars_korean_full.gba
│   ├── game_wars_korean_final.gba
│   └── game_wars_korean_title_test.gba
│
├── temp/                  # ★임시 작업 공간 (git-ignored) — 디버그 ROM/스크린샷/덤프
│
├── dist/                  # 배포본 (패치/manifest/릴리스 문서; ROM은 output/에서 재생성)
│   ├── *.bps, *.ips, manifest*.json, RELEASE_NOTES*.md, README.md
│
├── docs/                  # 문서 (상세 아래)
│   └── reports/           # 진행/세션 리포트 (이전 루트의 상태 MD들)
│
├── reference/             # 참고 데이터
│   └── fonts/             # 현재 빌드에 필요한 Galmuri 폰트 원본
│
└── archive/               # 정리된 임시/구버전 파일 (삭제 대신 보관)
    ├── logs/              # codex/translation 실행 로그
    └── scratch/           # 임시 txt/py/png, codex 테스트 스크립트, 글리프 시험본
```

### docs/ 주요 문서
- **진행 기준**: 루트 `todo.md` 하나만 사용한다. 구 `docs/plan.md`와 `.claude/todo.md`는 되살리지 않는다.
- **계획/리서치 참고**: `DIALOGUE_KOREAN_IMPLEMENTATION_PLAN.md`(구체 구현 로드맵), `research.md`(대화 렌더 파이프라인 완전 RE — 맨 끝), `muramasa_reference/`(무라마사 QA 도구 이식 출처), `FONT_HACK_RESEARCH_2026_05_21.md`(구 계획), `rom_analysis_guide.md`, `tbl_format_guide.md`, `translation_process.md`
- **번역 가이드**: `TRANSLATION_GUIDE.md`, `TRANSLATION_TONE_AND_STORY_GUIDE.md`, `AI_TRANSLATION_REFERENCE.md`, `TRANSLATION_REAUDIT_2026_05_18.md`
- **폰트(PHASE5-3)**: `PHASE5_3_FONT_ANALYSIS_COMPLETE.md`, `PHASE5_3_FONT_STATUS.md`, `PHASE5_3_ROM_FONT_ANALYSIS.md`
- **빌드/QA(PHASE5~7)**: `PHASE5_*` , `PHASE6_QA_FRAMEWORK.md`, `PHASE6_TESTING_GUIDE.md`, `PHASE7_DISTRIBUTION_PREP.md`
- **상태 스냅샷**: `PROJECT_STATUS_2026_05_12.md`, `PROJECT_COMPLETION_STATUS_2026_05_12_PHASE7.md`
- **AI 리서치**: `claude_research.md`, `codex_research.md`, `gemini_research.md`, `review_codex.md`, `review_gemini.md`
- **docs/reports/**: 세션/진행 리포트 (`SESSION_SUMMARY.md`, `PROJECT_PROGRESS.md`, `LOOP_*`, `PHASE3_SUMMARY.md`, `PHASE4_STATUS.md`, `SETUP_TRANSLATION.md`, `TRANSLATION_STATUS_2026_05_13.md`)

---

## 작업 디렉토리 규칙 (중요 — Claude 작업 시 반드시 준수)

> 모든 임시 작업물은 프로젝트 내 `temp/`에 모아 처리한다. `/tmp/` 사용 금지. 루트 디렉토리에 임시 파일을 흩뿌리지 말 것.

| 폴더 | 용도 | 비고 |
|------|------|------|
| `temp/` | **임시 작업 공간** — 디버그용 ROM 빌드, 테스트 .gba, 작업 중 스크린샷, 메모리 덤프(`*.bin`), 실험용 PNG, 일회성 분석 산출물 | git-ignored. `.gitkeep`만 트래킹. 자유롭게 쓰고 지움. |
| `output/` | **영구 빌드 산출물** — 최종/중간 한글 ROM, 세이브 파일 | git-ignored. **사용자 자산이므로 Claude가 임의로 비우지 않는다.** |
| `docs/screenshots/` | **영구 증거 스크린샷** — `SUCCESS_*`, 문서에 인용되는 그림 | git-tracked. 날짜·버전 태그 권장 (예: `SUCCESS_v25_…_2026-05-23.png`). |
| `dist/` | **배포본** — 릴리스 패치, manifest, 릴리스 노트 | git-tracked. ROM은 재생성 가능한 산출물이라 `output/`에 둔다. |
| `archive/` | **구버전 보관** — 삭제 대신 보관할 옛 로그/스크래치 | git-tracked. |

### Claude 행동 규칙
1. **새 디버그/테스트 산출물(.gba, .png, .bin, .raw 등)은 `/tmp/` 대신 `temp/` 아래에 저장한다.**
   - 예: `temp/welcome_probe.png`, `temp/test_engine_only.gba`, `temp/iwram_dump.bin`
2. **사용자에게 보여 줄 스크린샷도 `temp/` 경로를 사용**해도 된다. 사용자가 로컬 mGBA·미리보기로 바로 확인하기 좋다.
3. **검증·증거로 보존할 가치가 있는 스크린샷**은 그때 `docs/screenshots/`로 이동 + 의미 있는 이름·날짜 부여.
4. **최종 ROM이나 중간 빌드 산출물**은 `output/`에 둔다. (Claude가 `output/`을 청소하지 않는다.)
5. **루트 디렉토리에 임시 파일을 만들지 않는다.** (`shot*.png`, `*.bin`, `welcome_test.gba` 같은 패턴 금지)
6. **백업 파일(`*.bak`, `*.bak[0-9]*`)은 만들지 않는다.** git을 사용한다. 필요하면 `archive/`로 옮긴다.

### 정리 정책
- 루트에 `*.png` / `*.gba` / `*.bin` / `*.raw` 가 보이면 → 잘못 떨어진 임시물이므로 `temp/`로 옮기거나 지운다.
- `temp/`는 언제든 통째로 지워도 안전한 디렉터리. 영구 보존이 필요한 것은 즉시 `docs/screenshots/`, `output/`, `dist/`, `archive/` 중 적절한 곳으로 옮긴다.

---

## 작업 완료 시 자동 절차 (중요 — Claude 반드시 준수)

> **하나의 의미 있는 작업(검증된 ROM 빌드, 새 hook 작동, 영문 변환 완료, RE 발견 등)이 완료되면 다음을 항상 수행한다.**

### 0. Codex + Claude 엄격 리뷰 (필수 — 작업 완료 또는 막힘 시 항상)
> 2026-09-30 사용자 갱신: agy는 사용하지 않는다. 기존 agy 리뷰 의무는 폐기하고 Codex + Claude 리뷰를 사용한다.

- 의미 있는 작업 완료 직전, 막힘, 중요한 RE 결론 직후에 엄격히 검토한다.
- Codex 작업은 로그인된 Claude CLI에 읽기 전용 적대 검토를 요청한다. Claude 작업은 Codex에 요청한다.
- 리뷰는 버그·회귀·UX·보안·테스트 누락·배포 위험·경계 조건을 다룬다. 타당한 지적을 수정하고 필요한 검증 및 후속 리뷰를 수행한다.
- Claude는 일반 로그인 설정을 사용한다. `--bare`는 OAuth 로그인을 사용하지 않으므로 로그인 확인이나 리뷰에 쓰지 않는다.
- 리뷰 CLI가 실제로 사용 불가능하면 오류 증거를 기록하고 같은 항목을 자체 검토하며 외부 리뷰 통과로 집계하지 않는다.
- 프롬프트와 리뷰 결과는 `temp/`에 보존한다. 과거 리뷰 기록은 당시 이력으로 유지한다.

### 1. 문서 업데이트 (4개 핵심 문서)
| 문서 | 언제 업데이트 | 무엇을 추가 |
|------|----------|-----------|
| `todo.md` | 다음 계획·우선순위 변경 시 | 완료된 항목 체크, 새 단계 추가 |
| `docs/success.md` | 검증된 작동 결과 확인 시 | 작동한 정확한 방법·산출물·증거 (re-run 가능한 형식) |
| `docs/fail.md` | 시도 후 실패·dead-end 발견 시 | 사유, 다시 시도하지 않도록 조건 명시 |
| `docs/research.md` | 새 RE 사실·주소·공식 발견 시 | 주소·디스어셈블·테이블 등 reproducible 사실 |

### 2. 변경 사항 commit + push
1. `git status` / `git diff` 확인 후 핵심 산출물 + 문서 staging
2. 영구 산출물(`docs/screenshots/*.png`, `docs/*.md`, `tools/*.py`, `CLAUDE.md`) 위주로 add. `output/`, `temp/`, `original/` 는 git-ignored
3. 커밋 메시지: `<type>: <짧은 설명>` 형식 + 본문에 핵심 변경 요약 (한국어)
4. `git push` 까지 수행 (사용자 확인 없이 진행 OK — durable 기록 남기는 것이 중요)

### 3. 작업 완료 알림
- 사용자에게 1-2줄 요약 + 다음 단계 옵션 제시
- 다음 작업 진행 의사 확인 (또는 loop 모드면 다음 iteration으로)

### 트리거 예시
- ✅ 새 ROM 빌드가 검증 통과 (예: v25, v27)
- ✅ 새 기능 동작 (예: hook B 작동, alphabet glyph 주입)
- ✅ 새 RE 발견 (예: 폰트 슬롯 매핑 공식)
- ❌ 시도가 실패·dead-end (예: ASCII 직접 입력 crash)
- 단순 디버그·중간 실험은 트리거 아님 (작업이 의미있게 마무리될 때만)

---

## 환경 메모
- 에뮬레이터: `mgba 0.10.5` (brew, `/opt/homebrew/bin/mgba`, `libmgba.dylib`, 헤더 `/opt/homebrew/include/mgba`). 자동 진행은 `tools/mgba_harness.c`의 정상 키 입력 경로를 사용하고 입력·프레임·ROM SHA를 기록한다.
- 보조 MCP: `emucap`은 Codex/Claude 양쪽에 등록됐고 MesenCE + GBA BIOS 경로까지 설정됐다. 단, 실화면 회귀의 정식 증거는 여전히 `temp/mgbah` 기반 캡처와 `docs/screenshots/` 보존본이다.
- 이미지/글리프: `PIL`. 시스템 한글 폰트: `/Library/Fonts/NanumGothic.ttf` 등.
- 글리프→GBA 타일 변환 후보: Optiroc **SuperFamiconv**.

### 2026-10-02 연속 진행 디스크 운영값

QA 프로토콜의 기본 하한은10GiB이며 실행별 설정이 가능하다. 약15GiB에서 반복 중단된 원인은 이번 실행의 추가 보수값15GiB였고 사용자 고정 요구가 아니다. 후속 정상 플레이는 `--min-free-gib 12.0`으로 설정하고13GiB부터 증가량/외부사용을 점검한다. 500MiB 증가마다 자원 상태를 확인하며12GiB 하드 중단은 유지한다. 이전15GiB 가드 실패/미완료 증거는 그대로 보존하며 완료로 바꾸지 않는다. 코드나 체크포인트를 조작해 실행 중 가드를 우회하지 않고 정상 재시작 옵션으로 적용한다.
