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
- ✅ **2편(Advance 2) — 타일맵 렌더러**(idx→BG 타일맵 strh, per-char 글리프 복사 아님): 0x08313F8C(Advance2) / 0x08B11BB0(공통) / 0x08A3C7E4·IWRAM 0x03006080(MODE SELECT/PROLOGUE 글리프캐시 = "?" 출처). A3는 0x08314270 char 디스패치 점프테이블(0x20 엔트리=0x083142CC). bit15 한글코드(0x8840~0x9369)를 KOR_BASE(0x08F00000)에서 VRAM 복사하도록 hook. 공백 advance +1(반각).
- **추출 노이즈**: `game_wars_found_texts.csv`의 상당수는 깨진 문자(무작위 한자+키릴+기호) — 번역/삽입 대상 아님.

---

## 번역 작업 방식

### 토큰·컴퓨터 자원 절약 원칙 (2026-09-23 사용자 지시)

- **검증된 구조를 먼저 재사용한다.** 폰트 코드→글리프, 제어문자, 포인터, 압축·팔레트·스프라이트 배치와 소비 렌더러를 기존 코드·RE 기록에서 확인한다. 새 사실은 근거 ROM SHA/주소/재현 명령과 함께 기록하며, 이미 확정한 구조를 매번 AI로 재분석하지 않는다.
- **반복 작업은 로컬 도구로 처리한다.** 글리프 생성·굵기/자간/AA 비교, 인코딩·문자 누락·행폭·슬롯·제어 바이트 검사, 추출/재삽입, 빌드, 입력 재생, 해시·화면 차이 수집을 결정적인 스크립트로 수행한다. 기존 도구를 먼저 찾고 확장하며, AI는 새로운 원인 분석·번역 의미·시각 판단에 집중한다.
- **표시 경로별 제약을 구분한다.** 1·2편 대화/메뉴/시스템 문구의 슬롯 크기, 줄·페이지 폭, 확장·재배치 가능 여부를 각각 확인한다. 다른 렌더러의 규칙을 복사하거나 폭에 맞추려고 의미를 삭제하지 않는다. 인코딩/배치 실패는 빌드 오류로 남긴다.
- **번역 데이터와 도구를 분리한다.** 원문·주소·제어 토큰을 보존한 CSV/JSON/TSV를 기존 빌드로 반영한다. 저비용 번역 모델은 명시적으로 선택된 경우 초안에 활용하되, 모델 변경·번역 API 호출을 자동 추가하지 않는다. 기존 번역 및 B팀 보호 범위를 유지한다. 자동 검사는 의미·말투 검수와 실화면 확인을 대체하지 않는다.
- **필요한 문맥과 결과만 읽는다.** `rg`로 주소/함수/실패 항목을 찾은 뒤 해당 범위만 읽는다. 큰 로그·ROM 덤프·전체 번역표를 대화에 반복 출력하지 않는다. 상세 증거는 파일에 남기고 변경점·실패 요약·재현 명령을 공유한다. 동일 입력/도구/ROM SHA의 검증 결과는 재사용하되 변경된 소비 경로의 검증은 다시 수행한다.
- **저부하 병렬 실행을 기본으로 한다.** 파일 소유권을 나눠 충돌을 피한다. 전체 ROM 빌드와 대량 재생/영상 변환은 한 번에 하나씩, 정상 플레이 하네스는 편당 하나·최대 둘로 제한한다. 별도 진단 하네스가 필요하면 해당 플레이를 멈춘 상태에서 짧게 실행한다. 무거운 작업은 가능하면 `nice -n 15`로 실행하고 메모리·CPU·디스크 여유를 확인한다. 입력 없는 에뮬레이터는 정지시키고 무한 폴링/동일 리뷰 재호출을 피한다.
- **절약과 완료 판정을 분리한다.** 정상 입력 플레이·전 프레임 증거·ROM 식별·회귀 검사·필수 적대 리뷰를 생략하지 않는다. 캡처/정적 QA 통과를 전 장면 육안 검수나 엔딩 도달로 집계하지 않는다. 사용자 개입 없이 계속하라는 현재 요청에 따라 이미 승인된 수정·검증은 자율 진행한다.

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
├── .claude/               # settings.json(codex+gemini 리뷰 Stop 훅)
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
- 이미지/글리프: `PIL`. 시스템 한글 폰트: `/Library/Fonts/NanumGothic.ttf` 등.
- 글리프→GBA 타일 변환 후보: Optiroc **SuperFamiconv**.
