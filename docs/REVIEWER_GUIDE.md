# 검수자 가이드 — 배포본 검증

> 배포본(BPS/IPS 패치)이 정본 빌드와 일치하는지, 어떤 검사를 통과했고 무엇이 아직 미검증인지
> 확인하는 방법입니다. 사용자용 안내는 루트 [`README.md`](../README.md)와 [`dist/README.md`](../dist/README.md),
> 개발 도구 안내는 [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md)에 있습니다.
>
> 이 문서는 예전 `dist/README.md`(영문, 생성물)의 개발자용 검증 메모를 옮겨 온 것도 포함합니다(2026-10-19).

---

## 1. 배포본 구성

`dist/` 에는 **패치만** 들어 있습니다. ROM 파일은 배포하지 않으며, 빌드 산출물은 `output/` 에 둡니다.

| 파일 | 내용 |
|---|---|
| `game_wars_korean_full_<날짜>.bps` | 정본 패치(원본·결과 CRC32 내장) |
| `game_wars_korean_full_<날짜>.ips` | 호환용 패치 |
| `manifest.json` / `manifest_preview.json` | 원본·결과 ROM과 패치의 크기·CRC32·SHA-1·SHA-256, 왕복 검사 결과, prepackage QA 증거 digest |
| `RELEASE_NOTES.md` / `RELEASE_NOTES_preview.md` | 릴리스 요약·미검증 범위(영문) |
| `README.md` | 사용자용 적용 안내(한국어). `tools/prepare_patch_distribution.py` 가 다시 만든다 |
| `README_KO.md` | `README.md` 로 옮겼다는 안내만 남긴 파일 |
| `apply_patch.py` | 사용자용 적용기(표준 라이브러리만, manifest 의 원본·결과 ROM SHA-256 검사; 패치 SHA-256은 manifest 가 있고 패치 파일 이름이 manifest 와 같을 때 검사) |

날짜가 더 이른 `.bps/.ips` 는 예전 판 기록입니다. 현재 정본은 `manifest.json` 의 `bps_patch.file` 입니다.

### 현재 정본 (2026-10-19 판)

| 항목 | 값 |
|---|---|
| 후보 | b43 |
| 원본 ROM | `Game Boy Wars Advance 1+2 (Japan).gba`, 16777216 B, CRC32 `49ee1fdd`, SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |
| 결과 ROM | 16777216 B, CRC32 `a53bfa40`, SHA-256 `488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34` |
| BPS | `game_wars_korean_full_2026-10-19.bps` |
| IPS | `game_wars_korean_full_2026-10-19.ips` |

b43 변경 요약(manifest `release_highlights`): b40 은 1편 모든 예/아뇨 질문에 넓은 행을 쓰고, b41 은 글자 손실 없이 대사 창 줄바꿈을 다시 맞추고, b42 는 자연스러운 띄어쓰기를 되살리고 이름·칭호 띄어쓰기를 통일한다. b43 은 사용자 승인 Link 상태 문구 9줄의 문장부호 뒤 공백을 고친다.

값은 이 문서보다 `dist/manifest.json` 이 정본입니다. 새 릴리스 뒤 이 표가 어긋나면 manifest 를 따르고 표를 고칩니다.

---

## 2. 배포 게이트

배포 판정의 권위는 아래 두 도구입니다(`CLAUDE.md` 「QA 도구」).

```bash
# 1) 배포 무결성: manifest.patched_rom.sha256 == sha256(output ROM)
#    == sha256(원본+BPS) == sha256(원본+IPS), 레거시 output 사본 일치, 일부 고정 시각 영역 검사
python3 tools/verify_dist_integrity.py          # exit 0=PASS, 1=FAIL

# 2) 릴리스 QA: 빌드 → prepackage 게이트 일괄 → (PASS 시) 패키징 → dist-integrity
AW_FONT_DIR=~/aw-fonts memcap -n aw-release -- nice -n 15 \
  python3 tools/run_release_qa.py --build --dist-date <YYYY-MM-DD>
```

- `run_release_qa.py` 는 `temp/release_prepackage_qa.json`(prepackage 증거)과 `temp/release_qa_report.json`(전체 결과)을 남깁니다.
- prepackage 게이트 목록은 `tools/run_release_qa.py` 의 `BASE_GATES`/`REQUIRED_PREPACKAGE_GATES` 가 정본입니다. 통과한 목록은 `manifest.json` 의 `validation.qa_evidence.gate_labels` 에 기록됩니다.
- QA 도중 `data/`·`reference/`·`tools/`·`requirements.txt`·외부 폰트가 바뀌면 `input-stability` 로 실패합니다. 다른 작업이 이 경로를 고치는 중에는 돌리지 않습니다.
- 빌드·릴리스 QA는 무거운 작업입니다. 한 번에 하나만 돌리고 CPU 온도(`sysmon --json`)를 먼저 봅니다.

### 패키징 (`tools/prepare_patch_distribution.py`)

```bash
python3 tools/prepare_patch_distribution.py --date <YYYY-MM-DD>
```

- `temp/release_prepackage_qa.json` 이 현재 ROM·원본·입력 스냅숏과 맞지 않으면 아무것도 쓰지 않고 거부합니다.
- BPS·IPS 를 다시 만들고 다음을 확인합니다.
  - BPS 왕복: 원본 ROM + BPS == 최신 한글 ROM
  - IPS 왕복: 원본 ROM + IPS == 최신 한글 ROM
  - 기존 정본 `output/game_wars_korean_full.gba` 를 사용한다
- `manifest*.json`, `README.md`, `RELEASE_NOTES*.md` 를 함께 다시 씁니다. `dist/README.md` 를 손으로 고치면 다음 패키징 때 덮어쓰이므로, 문구는 `write_readme()` 에서 고칩니다.
- 사용자용 변경 요약은 결과 ROM SHA 가 b42 또는 b43 정본일 때만 넣습니다(`B42_ROM_SHA256`, `B43_ROM_SHA256`). 다른 ROM 으로 패키징하면 요약 줄이 빠집니다.

---

## 3. 손으로 확인하기

```bash
sha256sum "original/Game Boy Wars Advance 1+2 (Japan).gba"   # == manifest.source_rom.sha256
sha256sum output/game_wars_korean_full.gba                   # == manifest.patched_rom.sha256
sha256sum dist/game_wars_korean_full_2026-10-19.bps           # == manifest.bps_patch.sha256

# 사용자 경로 그대로: 임시 폴더에서 적용기 실행
mkdir -p temp/apply_check && cp dist/apply_patch.py dist/manifest.json \
  dist/game_wars_korean_full_2026-10-19.bps temp/apply_check/
python3 temp/apply_check/apply_patch.py "original/Game Boy Wars Advance 1+2 (Japan).gba" \
  temp/apply_check/korean.gba
```

빌드 쪽 1차 게이트는 `python3 tools/qa_integrity_map.py`(무결성맵↔ROM)이고, 나머지 QA 도구 사용법은 [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) 3-4 에 있습니다.

---

## 4. 증거 위치

| 무엇 | 어디 |
|---|---|
| 화면 증거(보존) | `docs/screenshots/` — 후보·날짜 태그 폴더(예: `b42_dialogue_2026-10-19/`, `b42_yesno_2026-10-19/`, `b42_iphone_2026-10-19/receipt.json`) |
| 작동한 방법·재현 명령 | [`success.md`](success.md) |
| 실패·막다른 길 | [`fail.md`](fail.md) |
| RE 사실(주소·공식) | [`research.md`](research.md) |
| 장면 재현 경로 | `tools/scene_routes/*/README.md` |
| 정상 플레이 QA 규칙 | [`PLAYTHROUGH_QA_PROTOCOL.md`](PLAYTHROUGH_QA_PROTOCOL.md), [`REPLAY_QA.md`](REPLAY_QA.md) |
| 검사 범위·외부 파이프라인 대조 | [`LOCALIZATION_GATES.md`](LOCALIZATION_GATES.md) |
| 진행·미해결 목록 | 루트 [`todo.md`](../todo.md) |

`temp/` 의 리포트는 언제든 지워질 수 있는 작업물입니다. 오래 남길 증거는 `docs/screenshots/` 로 옮겨야 합니다.

---

## 5. 통과가 뜻하지 않는 것 (미검증 범위)

prepackage QA·왕복 검사 통과는 **나열된 검사만** 통과했다는 뜻입니다. 전체 캠페인, 캐릭터 말투, 실기 승인을 뜻하지 않습니다.
2026-10-19 판(b43) 기준 미검증 범위(`dist/RELEASE_NOTES.md` 와 같음):

- **실제 GBA 하드웨어:** 미검증. iPhone RetroArch 에서 b42 ROM 을 읽어 1편 타이틀 → 모드 메뉴 → War Room 목록까지 콜드부트했고 기존 세이브가 보존됐다(`docs/screenshots/b42_iphone_2026-10-19/receipt.json`). 이 기기 확인은 바뀐 대사 전부나 모든 예/아뇨 질문을 덮지 않는다.
- **치트 사용 증거:** 해금된 맵 목록·공통 캠페인 질문 캡처는 치트 저장으로 만들었다. 그 화면 표시만 확인하며 정상 플레이 해금·진행을 증명하지 않는다. 치트 구간은 정상 승리·엔딩 도달로 세지 않는다.
- **도달 미확인:** 다른 배너 시트와 `0x804FC8` 소비자 도달, 1편 도움말 창 11개의 자연 진입, 정상 플레이 Sturm CO 필살기, 잠긴 맵의 숨은 이름.
- **b43 대사 고정창 검사 밖:** 소비자 미상 13건, 상태 의존 메시지 16건, 가로 스크롤 도움말 18건, 보류된 재배치 7건.
- **강제 QA는 자연 경로 검증이 아니다.** 강제 렌더·RAM 조작으로 본 화면은 표시 확인일 뿐이다.
- 두 편 모두 정상 플레이로 엔딩까지의 전 장면 검수는 끝나지 않았다(`todo.md` 기준).

못 돌린 항목은 PASS 가 아니라 BLOCKED/미검증으로 적습니다. 판정에는 대상 ROM SHA·명령·종료코드·증거 경로를 함께 남깁니다.
