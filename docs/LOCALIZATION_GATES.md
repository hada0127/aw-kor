# 번역 검증 증거와 외부 도구

## 외부 게임 한글화 파이프라인 대조 (2026-09-30)

참고 저장소: [arqhive/game-korean-localization-pipeline](https://github.com/arqhive/game-korean-localization-pipeline), 검토 revision [`fcfb415`](https://github.com/arqhive/game-korean-localization-pipeline/tree/fcfb4158409990490ea5ccd8596aa91c5f125dd5). 원칙을 GBA ROM 프로젝트에 맞춰 적용하며, Claude Code용 폴더 구조·사람 승인 게이트·다른 콘솔의 포맷 절차는 그대로 복사하지 않는다. 현재 프로젝트의 명시적 사용자 지시(사용자 개입 없이 진행)와 이 저장소의 GBA 구조·기존 승인 범위가 우선이다.

| 참고 원칙 | 이 프로젝트에서 쓰는 기준 / 남은 경계 |
|---|---|
| 게임에 있는 분야만 검사하고 없는 분야는 사유를 남김 | 적용 분야는 GBA 단일 ROM의 텍스트·폰트·BG/OBJ 스프라이트/UI 그래픽이다. 3D 모델·음성 더빙 파이프라인은 없다. 별도 영상/자막 자산은 현재 확인되지 않았지만 미발견을 부재로 단정하지 않고, ROM/실화면 조사에서 확인되면 `todo.md`와 자산 목록에 추가한다. 배포 대상은 실기 GBA와 mGBA이며 실기 미검증은 명시한다. |
| 포맷 분석·무변경 왕복을 번역/주입보다 먼저 | 원본 SHA, 소비 렌더러, 포인터·제어코드·글리프·압축 규칙을 `docs/research.md`, `docs/success.md`, `docs/fail.md`와 빌드 receipt에 보존한다. 현재 제작 흐름은 확정된 GBA 규칙을 재사용한다. 새 포맷 writer가 생기면 원본 payload 왕복/바이트 무결성을 별도 검사한다. |
| 추출 모집단과 대상 범위를 목록으로 확정 | 텍스트 모집단은 원본 ROM 포인터·payload와 `data/translation_for_import.csv`; 장면 및 이미지 작업은 `data/scene_catalog.json`, `data/scene_catalog_overrides.json`, `data/objlabel_sprites.json`, `data/sprites_overrides.json`, `data/sprite_build_layouts.json`을 활용한다. 추출 노이즈, 미확인 소비자, 화면 미관측 항목은 번역/검수 완료로 세지 않는다. |
| 안정 ID, 용어집·말투, 태그 및 줄 제한 | 주소·source/payload ID를 키로 유지하고 한국어 문구 자체로 행을 결합하지 않는다. 용어는 `data/proper_nouns.json`, 화자 근거는 `data/character_attribution.json`, 제어구조·실제 물리 폭은 기존 QA를 사용한다. 번역 수정은 원문·수정 전·수정 후와 실제 ROM/화면 증거를 연결한다. |
| 그래픽 기준본·비교 시트·변경 영역 밖 무변경 | 기존 sprite codec/editor, scene catalog, 팔레트 소비 캡처와 sprite override fit QA를 사용한다. 기준본을 고칠 때는 변경 영역을 구체화하고 비교 시트·픽셀 차이 검증으로 같은 시리즈의 자형/외곽선/팔레트를 확인한다. 원본 느낌 복원은 이전 폰트 자형 기준이며 최신 작업은 가독성 개선만 참조한다. |
| 빌드 결과의 readback, 회귀·배포 분리 | 현재 build receipt·physical row audit·release QA·패치 적용 비교를 유지한다. 정적 QA, 화면 증거, 엔딩 진행은 서로 다른 게이트다. 성공한 부분검사를 전체 게임 승인으로 확대하지 않는다. |

이 대조표는 upstream 절차를 새로 복제한 것이 아니라 기존 프로젝트의 대응 도구와 빈틈을 찾아 연결한 것이다. 구현 전 분석 보고서 형식, 픽셀 변경량 같은 일반 조언은 이 프로젝트의 기존 증거 방식이 더 구체적이면 기존 것을 사용한다.

## 적용 범위

- [hanpatch](https://github.com/yazzang-homelab/hanpatch), 검토 revision `14d6405e94882da37ff777d50474bc06830b001b`: 최종 입력과 결과의 해시 연결, 단계별 승인 분리, 오래된 증거 거부 원칙을 GBA 빌드에 맞게 구현했다. 3DS 포맷·폰트·부호 변환기는 사용하지 않는다. 특히 이 프로젝트의 GBA 대사에 ASCII 부호를 일괄 적용하면 깨질 수 있다.
- [hancharacter](https://github.com/yazzang-homelab/hancharacter), 사용 revision `c423131d9ae80f9466fb0f8c1bdfe5e78f4ab362`: 실제 upstream manifest join, 일본어/한국어 측정 플러그인과 conformance 검사를 연결했다. 원문과 번역의 누락·중복 결합을 거부하고, 편집기 대사 스냅샷의 말투 표지 후보를 읽기 전용으로 분석한다.

hanpatch와 hancharacter는 `data/localization_tools.lock.json`에 고정하며 둘 다 MIT 라이선스다. arqhive 저장소는 위 revision의 절차 원칙만 참고했으며 코드를 가져오거나 의존성으로 설치하지 않았다. 자체 증거 도구는 upstream 원칙을 참고한 GBA용 구현이며 hanpatch 전체 파이프라인의 통과를 주장하지 않는다.

## 빌드와 배포

```sh
python3 tools/build_korean_full.py
python3 tools/run_release_qa.py --dist-date YYYY-MM-DD
```

빌드는 `<ROM>.build.json`에 원본·결과 ROM SHA-256, `data/`, `reference/`, `tools/`, requirements, 명시 외부 폰트, Python/Pillow 버전을 기록한다. 빌드 도중 입력 변경을 거부한다. 빌더가 생성하는 두 파일(`objlabel_sprites.json`, `sprite_build_layouts.json`)은 전후 변경을 허용하되 최종 내용도 기록한다. 개발용 빌드 증거이며 `release_ready`는 false다.

QA는 이 증거가 현재 파일과 일치할 때만 진행한다. 전체 필수 검사 후 `temp/release_prepackage_qa.json`을 기록하고, 모두 통과해야 포장을 호출한다. 포장은 ROM·입력·빌드 증거·필수 검사 목록·실패·시간 초과를 다시 확인한다. 불일치하면 배포 파일을 쓰기 전에 중단한다. 패치 생성 후에도 재확인하고 BPS/IPS 적용 결과를 비교한다.

QA가 읽는 `temp/integrity_map.json`, `temp/repoint_manifest.json`도 빌드 증거에 연결한다. 다른 후보 빌드가 이 공유 파일을 덮어쓰면 이전 ROM의 증거는 무효가 된다. `--no-repoint-dialogue` 개발 빌드는 포장 승인에 사용할 수 없다.

```sh
python3 tools/prepare_patch_distribution.py --qa-report temp/release_prepackage_qa.json
```

위 직접 호출에도 같은 검사가 적용된다. 예전 빌드와 QA 보고서에는 연결 증거가 없어 재빌드·QA가 필요하다. 파일을 고치면 이전 증거는 무효가 된다. 해시는 오래된 증거의 오용을 막으며 로컬 JSON의 악의적 위조를 인증하는 서명은 아니다. 배포 파일 묶음의 다중 파일 쓰기는 하나의 원자적 트랜잭션이 아니다.

전체 캠페인·분기·애니메이션의 시각 검토, 말투 보존, 실기 검증은 별도 범위다. 배포 문구도 이 검사들만으로 전체 합격을 선언하지 않는다.

## 전체 플레이 전에 하는 정적 검사

현재 검수 순서는 최종 ROM 전수 검사 → 개별 문맥 검수 → 정상 저장에서 짧은 장면 재현 → 남은 전체 플레이·엔딩이다. `qa_part2_physical_rows.py`는 새 에뮬레이터나 AI 호출 없이 원본 native 3,315개 포인터에서 native 포인터와 주소 범위로 선택한 대화와 제목을 추린다. CSV의 조각별 폭과 달리 최종 ROM의 같은 줄 조각을 합산하며, 재배치 주소·길이를 해당 빌드 manifest와 대조한다.

```sh
python3 tools/qa_part2_physical_rows.py \
  --rom output/game_wars_korean_full.gba \
  --original 'original/Game Boy Wars Advance 1+2 (Japan).gba' \
  --manifest temp/repoint_manifest.json \
  --receipt output/game_wars_korean_full.gba.build.json \
  --output temp/physical_rows_audit
```

원본·후보·코드맵·manifest 해시가 build receipt와 맞아야 한다. 보관한 후보를 검사할 때는 그 후보의 ROM/receipt/manifest 경로를 함께 지정한다. `summary.json`에는 입력 SHA, native 코드·hook 검증 프로필, 메시지별 소비 증거 적용 수, 구조 오류, 조건부 폭 후보, 미해석 제어, 미확정 공백, 지원하지 않는 제목 경로가 기록된다. 상세 문장과 포인터는 `rows.json`, `messages.json`, `width_candidates.json`에서 찾는다.

- 종료 코드 0은 보고서 생성과 확인된 검사 통과만 뜻한다. 모든 글리프·표시 폭·번역 의미·게임 화면이 정상이라는 판정이 아니다.
- 종료 코드 1은 구조·인코딩 오류 또는 증거로 확정된 폭 초과, 2는 입력/증거 불일치다.
- 44 half-cell 한계는 **같은 메시지에 소비 증거와 초상 PNG 증거가 모두 있을 때** 적용한다. PNG만 있거나 소비 파서만 확인했으면 확정 폭 판정을 하지 않는다. 그 외 폭 44 초과는 문맥·화면 검수의 우선 후보다.
- `57/77` 대기, `4B/6B` 페이지, `72` 줄바꿈, `09/0A/20` 비이동 소비, `30..33` 스타일은 메시지의 `part2_31424c_script` 소비 증거와 실제 native 코드·hook 해시가 일치하는 범위에서만 확정한다. 범위표나 A3 글리프 호출 하나로 다른 메시지까지 승격하지 않는다. 소비 미검증 메시지의 행은 조건부이며, `57/4B/0A`와 중간 `20`도 미검증으로 남는다. native 제목 179개 중 상위 소비 경로를 확정하지 못한 58개는 별도로 기록한다. 최종 글리프 그림과 OBJ/메뉴는 검사 범위 밖이다.
- 명령·제어·어휘를 자동 수정하지 않는다. 원문의 부정·조건·주체·반복과 실제 쓰기 우선순위를 개별 확인한 뒤 기존 빌드로 수정한다.

### 선택 증거 파일

기본 명령에 `--consumer-evidence temp/consumer.json`과 `--layout-evidence temp/layout.json`을 필요에 따라 추가한다. 두 파일은 독립적인 schema 1이며, 서로 대체하지 않는다. 아래 SHA 자리에는 실제 64자리 SHA-256을 기록한다.

소비 증거는 현재 ROM/pointer/target/payload와 과거 원위치 메시지의 native 읽기를 연결한다. 과거와 현재의 파서·명령 표·줄바꿈/페이지/대기 handler·대기 callback·한글 hook을 고정된 코드 해시와 대조한다. `trace_rom`과 `trace` 경로는 **CLI를 실행한 작업 디렉터리 기준**이다(절대 경로도 허용).

```json
{
  "schema": 1,
  "rom_sha256": "<현재 ROM SHA-256>",
  "records": [{
    "source": "0x00A01D24",
    "pointer": "0x00A357F4",
    "target": "0x00A3D08C",
    "payload_sha256": "<검사 messages.json의 payload_sha256>",
    "consumer": "part2_31424c_script",
    "kind": "historical-inplace-native-read-v1",
    "trace_rom": "temp/previous/candidate.gba",
    "trace_rom_sha256": "<과거 ROM SHA-256>",
    "trace": "temp/previous/text_reads.log",
    "trace_sha256": "<실제 읽기 로그 SHA-256>"
  }]
}
```

로그에는 원본 종단 내 `addr`, 파서 읽기 `pc=0831425A` 또는 `08314336`, 호출자 `lr=083148F3`가 같은 행에 있어야 한다. `addr=08A01D24 pc=0831425A lr=083148F3` 형태다. 과거 ROM의 해당 포인터가 원본 위치를 유지한 경우만 지원한다. 글리프 함수 진입만 관측한 로그나 과거 재배치 메시지는 거부한다. 이 증거는 해당 메시지에서 관측된 소비 경로를 뒷받침하며, 모든 호출 문맥의 독점 소비자라는 뜻은 아니다. 로컬 로그 해시도 실행 사실을 인증하는 서명은 아니다.

초상 증거는 실제 확인한 240×160 PNG와 현재 payload를 연결한다. `screenshot` 상대 경로는 **layout JSON의 디렉터리 기준**이다. PNG 형식·크기·SHA는 자동 검사하지만, 해당 문장의 실제 초상 화면인지와 44 half-cell 한계의 시각 판단은 증거 작성자가 검토해야 한다.

```json
{
  "schema": 1,
  "records": [{
    "source": "0x00A024A0",
    "renderer": "part2_a3_portrait",
    "capacity_half_cells": 44,
    "rom_sha256": "<현재 ROM SHA-256>",
    "payload_sha256": "<검사 messages.json의 payload_sha256>",
    "screenshot": "portrait.png",
    "screenshot_sha256": "<PNG SHA-256>"
  }]
}
```

소개·목표·프롤로그에는 이 초상 규칙을 적용하지 않는다. `messages.json`의 `consumer_proof`, `consumer_status`, `capacity_unverified_reasons`가 각 메시지의 근거와 부족한 증거를 설명한다. `native_profile`이 null이면 확정된 native 소비 메시지가 없다는 뜻이다. `capacity_verified_messages`는 한계 적용 근거가 있는 메시지 수이며, 그 안의 미해석 명령이나 글리프까지 통과했다는 뜻은 아니다. 각 행의 `controls_understood`와 `confirmed_capacity_exceeded`를 함께 확인한다. `inputs`에는 제공한 두 JSON 해시를, `consumer_evidence_inputs`에는 실제 검증한 과거 ROM·로그 해시를 보존한다.

## 편집 의도 기록과 보호 문구

보호 주소를 대사 편집기에서 수정하면 `data/address_text_overrides.tsv`, `data/dialogue_overrides.json`, `data/editor_override_intents.json`을 함께 유지해야 한다. 화면용 대사/그룹 JSON도 같은 저장 작업으로 갱신되므로 편집기가 기록한 변경을 함께 검토·커밋한다. 일부 권위 파일만 옮기면 문구와 해시가 달라져 빌드가 중단될 수 있다.

문구가 이미 TSV와 대사 JSON 양쪽에 동일하게 저장되어 있고 의도 기록만 없어진 경우, 편집기의 현재 문구 확인 동작으로 기록을 다시 만들 수 있다. 서로 다른 보호 표시 문구와 원래 대사를 확인 동작만으로 합치지는 않는다. 일반 저장에서 변경이 없으면 새 기록을 만들지 않는다. 이 해시는 로컬 편집 의도를 연결하는 장치이며 사용자 인증이나 서명은 아니다.

## 말투 분석

최초 설치만 네트워크를 사용한다. 고정 revision의 checkout을 보관하며 기존 수정본을 덮어쓰지 않는다.

```sh
python3 tools/localization_dependencies.py --setup
python3 tools/audit_character_voice.py --out temp/voice_audit_새실행
```

분석은 로컬에서만 실행하며 모델/API 호출과 번역문 변경이 없다. 출력 디렉터리는 매번 새 이름을 사용한다.

- `manifest.json`, `host_rows.json`: 명시된 ja/ja/ko 언어 역할, 행별 최종 스냅샷, checksum과 양방향 join.
- `report.json`: 입력 해시, 제외된 추출 그룹, 화자 미확인 수, 일본어·한국어 측정기의 표지 후보.
- `data/character_attribution.json`: 검증된 화자만 등록한다. 각 항목은 원문·번역 SHA, 프로젝트 내부 증거 파일과 SHA, `review_status: reviewed`를 요구한다. 대사가 바뀌면 화자 증거도 재검토해야 한다.

현재 GBA 제어코드/화자 분할 어댑터와 검증된 캐릭터 말투 계약은 없다. 따라서 segmentation은 `NOT_RUN`, 최종 상태는 `report_only_no_sealed_contract`다. 일본어와 한국어의 측정 축은 다를 수 있으므로 단순 표지 수 차이를 말투 손실로 판정하지 않는다. 편집기 그룹은 최종 ROM readback이나 게임 전체 대사 모집단을 보증하지 않는다.

## 회귀 검증

```sh
python3 -m unittest discover -s tools -p test_localization_evidence.py
python3 -m unittest discover -s tools -p test_character_voice_adapter.py
```

정상 포장, 누락·실패·시간 초과된 검사, 입력·ROM 변경, upstream join 양방향 누락, 번역 변조, 화자 추측 방지를 확인한다. 반복 게임 재생은 기존 [로컬 재생 도구](REPLAY_QA.md)를 사용한다.

이 CLI의 재배치 중첩 검사는 manifest 레코드 상호 중첩과 원본 점유 바이트를 대상으로 한다. 다른 빌드 writer와의 충돌은 별도 빌드 무결성 검사 대상이다. historical trace와 당시 ROM의 연결은 조사자가 기록한 로컬 provenance이며, trace 자체의 서명이나 ROM SHA 헤더로 독립 입증된 자료가 아니다. 동일 source의 다른 소비자 부재도 입증하지 않는다.
