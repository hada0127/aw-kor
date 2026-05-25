# Game Wars 한글화 프로젝트 — Claude 작업 지침

> 대상 게임: **Game Boy Wars Advance 1+2 (GBA, 일본판)** 한글화
> **최종 목표(현재)**: 원본 ROM을 패치해 **실기(real GBA hardware) 및 에뮬레이터에서 한글이 정상 출력**되게 한다. (배포는 BPS 패치)

## 언어 설정
모든 응답은 **한국어**로 작성합니다.

---

## 현재 상태 (2026-05-21)

| 항목 | 상태 |
|------|------|
| 텍스트 번역 | ✅ 사실상 완료 — `data/translation_for_import.csv`에 한글 18,262행. (원본 28,347행 중 ~10,254행은 추출 노이즈라 번역 대상 아님) |
| 한글 폰트 ROM 삽입 | ❌ 미완료 — **이게 현재 핵심 과제** |
| ROM 빌드 | ✅ `tools/execute_phase5_4→5_5` 파이프라인이 **부팅하는 ROM 생성**(흰 화면 해소, 2026-05-25 검증). 단 본문 대화는 폰트 미해결로 아직 한글 렌더 안 됨(아래) |
| 에뮬레이터 검증 | ✅ 경로 확보 — **brew `mgba 0.10.5` + `screencapture`** (VBA-M은 GPU 캡처 안 됨) |

**다음 작업 계획서**: [`docs/FONT_HACK_RESEARCH_2026_05_21.md`](docs/FONT_HACK_RESEARCH_2026_05_21.md) — 실기 패치 요건, 폰트 해킹 방법, 단계별 로드맵.

### 알려진 핵심 이슈 (반드시 인지)
- ✅ **체크섬 버그 — 해결됨**: `tools/execute_phase5_5.py:21`이 올바른 식 `(-(0x19 + sum(0xA0..0xBC))) & 0xFF` 사용. 텍스트 삽입은 헤더(0xA0–0xBC)를 안 건드리므로 0xBD 그대로 유효(검증 2026-05-25: 0xBD=0x72 식 일치).
- ✅ **삽입 손상 — 해결됨**: `execute_phase5_4.py`는 EUC-KR 길이가 원본 슬롯(`orig_len`)을 넘으면 skip, 정확히 `orig_len`만 clear/write, `SAFE_MIN_ADDR=0x800000` 미만(코드 영역)은 skip. 검증: 한글 ROM의 코드영역(<0x800000) 변경 **0바이트** → 원본과 동일하게 부팅.
- ⚠️ **본문 대화 폰트 렌더 — 미해결(현재 핵심 과제)**: `execute_phase5_4`는 **EUC-KR** 바이트를 삽입하는데, (a) 게임 대화 폰트는 SJIS-타일이고 (b) 흔한 한자(攻/撃 등)는 SJIS→슬롯 테이블(0xBE717A, 5498엔트리)에 없으며 (c) 대화 글리프는 LZ77 압축→VRAM 경로라 FONT_BASE 직접 주입이 안 통함 → EUC-KR이든 SJIS든 **대화는 한글로 안 보임**. 현재 작동하는 유일한 방법은 `build_grid_v*.py`의 **ARM hook**(특정 대화 주소를 0xA3E000 커스텀 글리프로 리다이렉트) — **per-screen**(welcome/이름입력/hajimemashite만). **풀게임 = 이 hook의 일반화**가 남은 큰 RE 과제.
  - 참고: **그리드/메뉴 폰트(이름입력)** 는 `FONT_BASE(0xB974D0)+slot*32`에 **직접 주입** 가능(비압축, A-Z/0-9 렌더 검증됨). 대화 폰트만 hook 필요.
- **추출 노이즈**: `game_wars_found_texts.csv`의 상당수는 깨진 문자(무작위 한자+키릴+기호) — 번역/삽입 대상 아님.

---

## 번역 작업 방식

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
python tools/execute_phase5_4.py   # 텍스트 삽입 (※길이 제한 버그 수정 필요)
python tools/execute_phase5_5.py   # 체크섬/최종화 (※0x19 체크섬 버그 수정 필요)
python tools/phase6_basic_test.py  # 기본 검증
# 에뮬레이터 실행(검증):
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/mgba -3 output/game_wars_korean_final.gba
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
│   └── 분석:   analyze_rom_header.py, find_pointers.py, analyze_translation_patterns.py
│
├── output/                # 빌드 산출물 (git-ignored *.gba) — Claude는 청소하지 않음
│   ├── game_wars_korean_final.gba     # 최종 ROM (현재 흰 화면 = 손상)
│   ├── game_wars_korean_v1.gba        # 삽입 직후 중간본
│   └── game_wars_korean_final.sav     # 세이브
│
├── temp/                  # ★임시 작업 공간 (git-ignored) — 디버그 ROM/스크린샷/덤프
│
├── dist/                  # 배포본
│   ├── game_wars_korean_final.gba, manifest.json, RELEASE_NOTES.md, README.md
│
├── docs/                  # 문서 (상세 아래)
│   └── reports/           # 진행/세션 리포트 (이전 루트의 상태 MD들)
│
├── reference/             # 참고 데이터
│   ├── Unihan_full.zip, unihan_tmp/   # 한자 분해/참조 데이터
│
└── archive/               # 정리된 임시/구버전 파일 (삭제 대신 보관)
    ├── logs/              # codex/translation 실행 로그
    └── scratch/           # 임시 txt/py/png, codex 테스트 스크립트, 글리프 시험본
```

### docs/ 주요 문서
- **계획/리서치**: `FONT_HACK_RESEARCH_2026_05_21.md`(★현재 계획), `plan.md`, `research.md`, `rom_analysis_guide.md`, `tbl_format_guide.md`, `translation_process.md`
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
| `dist/` | **배포본** — 릴리스 ROM/패치, manifest, 릴리스 노트 | git-tracked. |
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

### 0. codex + gemini 엄격 리뷰 (필수 — 작업 완료 또는 막힘 시 항상)
> 사용자 지시(2026-05-25): **작업 도중 막히거나 작업을 마칠 때는 항상 codex와 gemini에게 엄격한
> 리뷰를 받는다.** commit 전에 수행. `.claude/settings.json`의 Stop 훅이 매 턴 리마인드한다.

- **언제**: ① 의미 있는 작업 완료 직전(commit 전), ② 진행 중 막혔을 때(접근법 검증), ③ 중요한 RE 결론·설계 결정 직후.
- **어떻게** (둘 다, 가능한 한 엄격하게 — "비판적으로 검토하고 결함·누락·대안을 지적하라"는 톤):
  ```bash
  # 프롬프트를 파일로 작성 후 (temp/review_prompt.md 등)
  codex exec "$(cat temp/review_prompt.md)" > temp/codex_review.md 2>/dev/null
  # ⚠ gemini는 깨진 vscode MCP 확장 때문에 -e none 필수 (없으면 "MCP issues" 후 실패)
  gemini -e none --approval-mode yolo -p "$(cat temp/review_prompt.md)" > temp/gemini_review.md 2>/dev/null
  ```
  - 둘 다 느릴 수 있으니 `run_in_background`로 병렬 실행 후 결과 종합.
  - 두 의견의 **수렴/상충**을 정리하고, 타당한 지적은 반영, 반영 안 한 건 사유 명시.

### 1. 문서 업데이트 (4개 핵심 문서)
| 문서 | 언제 업데이트 | 무엇을 추가 |
|------|----------|-----------|
| `docs/plan.md` | 다음 계획·로드맵 변경 시 | 완료된 항목 ✅ 체크, 새 단계 추가 |
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
- 에뮬레이터: `mgba 0.10.5` (brew, `/opt/homebrew/bin/mgba`, `libmgba.dylib`, 헤더 `/opt/homebrew/include/mgba`). 합성 키 입력은 게임에 전달 안 되므로 자동 진행은 **mGBA Lua 스크립팅** 사용.
- 이미지/글리프: `PIL`. 시스템 한글 폰트: `/Library/Fonts/NanumGothic.ttf` 등.
- 글리프→GBA 타일 변환 후보: Optiroc **SuperFamiconv**.
