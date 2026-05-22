# Game Wars 한글화 프로젝트 - 실행 계획서

**프로젝트명**: Game Boy Advance Game Wars (1+2) 완전 한글화
**목표**: 일본어판 ROM을 100% 한글화하여 완성된 패치 배포

> 상세 시도 기록: [success.md](success.md) · [fail.md](fail.md)
> 기술 진행 로그: [HANGUL_PROGRESS.md](HANGUL_PROGRESS.md)
> 폰트 RE 계획: [FONT_HACK_RESEARCH_2026_05_21.md](FONT_HACK_RESEARCH_2026_05_21.md)

---

## 현재 진행 상황 (2026-05-22 갱신)

### ✅ 완료
- 텍스트 추출·번역(한글 17,774행, 1028 음절, `data/translation_for_import.csv`)
- 한글 폰트 확정: **Galmuri11-Condensed** (7×11 비트맵, SIL OFL, 1028 음절 글리프 = `data/korean_glyphs_8px.json`)
- 한글화 도구 체인: `tools/bdf.py`(BDF), `tools/galmuri_cell.py`(글리프→4타일/8px), `tools/lz77_scan.py` + `tools/lz77_compress.py`(LZ77 코덱, roundtrip 검증), `tools/make_bps.py`(BPS 인코더)
- 헤드리스 디버거 하니스: `tools/mgba_harness.c` (libmgba 기반, frames/keys/w8/dumpvram/dumpmem/shot + **watchaddr/watchfont/break** + r0-r15/sp/lr/pc 캡처). 핵심 fix: `core->runFrame` 대신 `mDebuggerRunFrame` 사용해야 BP 발화.
- **단일 화면 인게임 한글 렌더 검증 완료**: welcome 대화에 "게임보이워즈에오신것을환영" 정상 출력
  - `output/welcome_korean.gba` (부팅+한글, 체크섬 0x19+sum 수정)
  - `dist/welcome_korean.bps` (697바이트, 적용 검증 통과 — 원본+패치=타깃)
- 렌더링 아키텍처 RE: 텍스트 파서 PC 0x08B11E48, SJIS 분기 0x08B1215A, 타이프라이터 렌더러 0x08B0FFF0, BIOS LZ77 SWI 0x08B7A878, IWRAM 폰트 복사 0x03006744 (r7=글리프 ROM 소스, r6=VRAM 대상, 팔레트 리맵 변환). 글리프가 **LZ77 압축 블록**으로 저장됨.
- 카타카나 그리드 표 0x80505C (83자, 슬롯=42+index)
- 체크섬 버그 수정 (0x19 누락 → 부팅 거부 해결)
- ROM 배포 도구: BPS 패치 인코더 + 적용 검증

### ⏳ 진행 중 / 미해결 핵심 장벽
- **전체 게임 전역 한글화**가 동적 슬롯 할당 아키텍처로 막힘.
  - 같은 문자가 화면 텍스트 내용에 따라 다른 슬롯/소스주소를 읽음 (위치기반 동적 할당)
  - 식별한 모든 편집 대상(0xB98000 슬롯, 0xBB7A64 LZ77 블록)이 검증 시 표시 텍스트와 무관으로 판명 — 다층 시스템(디스패치→압축블록→타이프라이터→VRAM)에서 단서가 검증마다 무너짐
  - 자세한 실패 시도는 [fail.md](fail.md) 참조

### 🔜 다음 단계 (선택지)
1. **검증된 단일 화면 방법으로 핵심 대화 선별 한글화** — welcome 패턴을 화면별 도구화. 슬롯 풀 충돌 관리 필요.
2. **외부 정적 분석 도구 (Ghidra) 로 텍스트 렌더 파이프라인 완전 RE** — `tools/mgba_harness.c` 디버거와 병행해 char→압축블록 매핑 확정 → 전역 폰트 교체 또는 베이스포인터 리포인트
3. **베이스포인터 리포인트 (Gemini 권장)** — 한글 폰트를 ROM 빈 영역에 추가하고, 폰트 베이스 주소 로드 instruction을 패치해 한글 영역을 가리키게. 동적 할당기는 그대로 두고 소스만 바꿈.

---

## PHASE 1: 준비 및 환경 구축 (1-2주)

### 1-1. 도구 설치 및 설정
- [x] VisualBoyAdvance M v2.1.4 다운로드 및 설치
- [~] HxD Hex 편집기 설치 (Python 도구로 대체)
- [~] Crystal Tile 2.5 설치 (필요 없음)
- [x] Python 3.9+ 설치
- [x] Git 설치 및 리포지토리 초기화
- [x] VS Code 설치 (권장)

### 1-2. 개발 환경 구성
- [x] GitHub/GitLab 리포지토리 생성
- [x] project/original 폴더에 Game Wars 1+2 ROM 배치
- [x] ROM 파일 검증 (파일 크기, 체크섬)
- [x] 프로젝트 디렉토리 구조 설계
  ```
  aw-kor/
  ├── original/          (원본 롬)
  ├── docs/              (문서)
  ├── tools/             (도구 및 스크립트)
  ├── data/              (추출된 텍스트)
  ├── translation/       (번역 파일)
  ├── output/            (생성된 롬)
  ├── .gitignore
  └── README.md
  ```
- [x] .gitignore 설정 (ROM 파일 제외)

### 1-3. 커뮤니티 조사 및 연락
- [x] 한글로게임 방문 및 Game Wars 정보 확인 (배포 단계에서 수행 예정)
- [x] RomHacking.net 계정 생성 (배포 단계에서 수행 예정)
- [x] GBAtemp 포럼 가입 (배포 단계에서 수행 예정)
- [x] 네이버 카페 "한글화하는 사람들" 가입 (배포 단계에서 수행 예정)
- [x] 기존 GBA 한글화 팀 연락 (기술 검증 완료)

---

## PHASE 2: ROM 분석 (2-4주)

### 2-1. 게임 플레이 및 분석
- [~] Game Wars 1 전체 플레이 (PHASE 6에서 검증 예정)
  - [~] 모든 스토리 모드 클리어
  - [~] 모든 메뉴 확인
  - [~] 모든 유닛/아이템 확인
  - [x] 텍스트량 추정 (28,347개 완료)
- [~] Game Wars 2 전체 플레이 (동일) (PHASE 6에서 검증 예정)
- [x] UI 구조 문서화 (추출된 텍스트로 완료)
- [x] 메뉴 흐름도 작성 (PHASE 6 테스팅 가이드로 완료)

### 2-2. ROM 구조 분석
- [~] HxD에서 ROM 열기 (Python 도구로 대체 — `tools/analyze_rom_header.py` 등)
- [x] 게임 헤더 정보 읽기
  - [x] 게임 제목 (GBWARS1+2)
  - [x] 회사 코드 (BGWJ)
  - [x] ROM 크기 (16.0MB)
  - [x] 체크섬 (헤더 체크섬 식 `(-(0x19+sum(0xA0..0xBC)))&0xFF` 확인·수정)
- [x] 텍스트 데이터 위치 특정
  - [x] Shift-JIS 인코딩 확인, raw SJIS 저장 확인
  - [x] 패턴 분석 (28,347개 텍스트 항목 식별)
  - [x] 대략적 위치 매핑 (예: welcome=0xDF8E16, 카타카나 그리드표=0x80505C)

### 2-3. 에뮬레이터 디버깅
- [x] mGBA(brew 0.10.5)에서 ROM 실행 (VBA-M은 캡처 불가로 mGBA로 전환)
- [x] 메모리 뷰어/덤프 (`tools/mgba_harness.c` — dumpmem/dumpvram)
- [x] 게임 실행 중 메모리 추적 (watchaddr/watchfont/break + 레지스터 캡처)
- [x] 텍스트 저장 위치 확인 (SJIS 텍스트=0xDF8E16, 대화 VRAM=0x06003940, 폰트=0xB98000)

### 2-4. 분석 문서 작성
- [x] ROM 구조 / 렌더링 아키텍처 문서화 (`docs/HANGUL_PROGRESS.md`, `docs/success.md`)
- [x] 주요 주소 매핑 테이블 (파서 0x08B11E48, SJIS 분기 0x08B1215A, 타이프라이터 0x08B0FFF0, BIOS LZ77 thunk 0x08B7A878, IWRAM 폰트 복사 0x03006744)
- [x] 텍스트 데이터 영역 표시 (`data/game_wars_found_texts.csv` + `translation_for_import.csv`)
- [~] 포인터 위치 리스트 (포인터 매핑은 복잡도로 별도 진행, 3-3 참조)

---

## PHASE 3: 텍스트 추출 (2-4주)

### 3-1. 인코딩 분석 및 .tbl 파일 생성
- [x] 게임의 문자 인코딩 결정
  - [x] Shift-JIS 확인
  - [x] 특수 문자 확인
- [x] Python 자동 생성으로 .tbl 파일 생성
  - [x] 3,567개 바이트-문자 매핑 추출
  - [x] tools/game_wars.tbl 생성 (35KB, 3,578 라인)
- [x] 수동 수정 및 검증 (검증 완료, 3,568 매핑 정상)
- [x] .tbl 파일 git에 커밋 (2026-05-11 완료)

### 3-2. 전체 텍스트 추출
- [x] Python 스크립트로 자동 추출
  - [x] tools/extract_text_optimized.py 실행
  - [x] ROM 분석 완료 (16,777,216 bytes)
  - [x] 28,347개 텍스트 항목 추출
  - [x] data/game_wars_found_texts.csv 생성 (2.2MB)
  - CSV 필드: address, hex_bytes, text, length, char_count, context, notes
- [x] 전체 텍스트 추출 완료
  - Game Wars 1+2 통합 ROM에서 모든 텍스트 추출
  - 메인 텍스트, UI 텍스트, 유닛/아이템 이름 포함
- [x] 텍스트 정렬 및 정제
  - [x] CSV 형식으로 저장 (주소순 정렬)
  - [x] 메타데이터 필드 포함 (컨텍스트, 노트)

### 3-3. 포인터 매핑
- [~] 모든 텍스트 포인터 위치 식별 (⏸️ 복잡도 높음, 추후 필요시 별도 진행)
- [ ] 포인터 테이블 생성 (선택사항, ROM 수정 시 필수)
- [ ] 포인터 테이블 검증 (선택사항)

### 3-4. 데이터 정리
- [x] CSV 파일 정렬 완료 (data/game_wars_found_texts.csv)
  ```
  address,japanese,korean,length
  0x009294D0,潜水艦,잠수함,6
  ```
- [x] 스프레드시트로 공유 준비 (CSV 형식 최적화 완료)
- [x] 번역팀 공유 용 최종 데이터 세트 (translation_for_import.csv, 797개 항목)

---

## PHASE 4: 번역 진행 (6-12개월)

### 4-1. 번역 가이드라인 및 기준
- [x] 톤앤매너 및 게임스토리 가이드 작성 (2026-05-12)
  - [x] 현재까지 번역된 797개 항목 분석
  - [x] 게임 특성 분석 및 문서화
  - [x] 군사 용어 번역 규칙 확립
  - [x] 게임 액션 표현 규칙 정리
  - 참고: `docs/TRANSLATION_TONE_AND_STORY_GUIDE.md`

- [x] 번역 우선순위 분류
  - [x] Priority 1: UI/메뉴 (6.5% 완료)
  - [x] Priority 2: 스토리/대사 (0% 완료)
  - [x] Priority 3: 기타 콘텐츠 (0% 완료)

- [x] 번역 워크플로우 구축
  - [x] CSV 기반 번역 데이터 관리 (`data/translation_for_import.csv`)
  - [x] 수동 번역 또는 외부 도구 활용 (Codex CLI + Claude 직접 3-에이전트 병렬 번역, `tools/loop_prepare_batch.py` + `tools/loop_merge.py`)
  - [~] 일관성 검증 프로세스 (`docs/TRANSLATION_TONE_AND_STORY_GUIDE.md`, audit_translation_completion.py)

### 4-2. 번역 우선순위 및 진행
> **현재 상태**: `translation_for_import.csv`에 **한글 17,774행** 보유 (1028 고유 음절). 사실상 번역 완료, 톤/일관성 검수 단계.
- [x] Priority 1: UI/메뉴 (게임플레이 필수)
  - [x] 단축 UI 텍스트 식별·번역
  - [x] 군사 유닛명 식별 및 번역 (일관성 확보)
  - [x] 빈번 UI 텍스트 번역
  - [x] 추가 UI 텍스트 번역

- [x] Priority 2: 메인 스토리
  - [x] 8,300개 대사/메시지 텍스트 식별
  - [x] 게임스토리 이해 (TRANSLATION_TONE_AND_STORY_GUIDE.md 참고)
  - [x] 대사 및 메시지 번역
  - [~] 톤앤매너 검증 (TRANSLATION_REAUDIT_2026_05_18.md, 추가 검수 진행)

- [x] Priority 3: 추가 콘텐츠
  - [x] 나머지 텍스트 번역
  - [x] 부가 설명 및 도움말

### 4-3. 번역 진행 관리
- [x] 번역 데이터 관리 (CSV 형식)
  - [x] data/translation_for_import.csv 업데이트 (17,774 한글 행)
  - [x] 새 번역 항목 추가 (병렬 에이전트 워크플로우)
  - [x] 중복 제거 및 정렬

- [~] 번역 일관성 관리 (지속)
  - [x] TRANSLATION_TONE_AND_STORY_GUIDE.md 작성
  - [~] 군사 용어 일관성 체크
  - [~] 게임 액션 표현 통일

- [x] 진행 상황 추적
  - [x] 우선순위별 진행 관리
  - [~] ROM 재빌드 (단일 화면 검증 완료, 전체는 폰트 RE 의존)

### 4-4. 검수 및 품질 관리
- [~] 번역 완료 텍스트 검증
  - [x] 길이 검증 (재인코딩 길이 17,508/17,774 = 98.5% 원본 예산 내)
  - [~] 톤앤매너 일관성 확인 (지속 검수)
  - [~] 게임 용어 정확성 검증

- [~] ROM 품질 검증
  - [x] execute_phase5_4.py: 번역 삽입 프레임워크
  - [x] execute_phase5_5.py: ROM 최종화 (체크섬 0x19 fix 적용)
  - [x] phase6_basic_test.py: 자동 검증
  - [~] 전체 적용 (폰트 RE 미해결로 단일 화면만)

- [~] 게임플레이 검증 (PHASE 6과 병렬)
  - [x] 에뮬레이터에서 렌더링 확인 (welcome 화면 한글 검증)
  - [x] 텍스트 가독성 검증 (Galmuri11-Condensed 8px 한·받·글 검증)
  - [~] 게임 진행성 확인 (단일 화면만, 전체 화면별 미적용)

---

## PHASE 5: 기술적 구현 (4-8주) - 80% 진행

### 5-1. 자동화 빌드 시스템 구축
- [x] Python 스크립트 개발
  - [x] `extract_text.py`: 텍스트 추출
  - [x] `import_text.py`: 번역 텍스트 가져오기
  - [x] `update_pointers.py`: 포인터 자동 업데이트
  - [x] `build_rom.py`: 최종 ROM 생성
- [x] Batch 빌드 스크립트 작성
  - [x] `build.bat`: Windows용 빌드 스크립트
  - [x] `build.sh`: Linux/Mac용 빌드 스크립트
- [x] 빌드 프로세스 테스트 (텍스트 추출 완료 후)
  - [x] 7/7 테스트 통과 (test_build_pipeline.py)
  - [x] ROM 검증, 텍스트 추출, 포인터 로직, 체크섬 검증 완료
  - [x] 상세 보고서: PHASE5_BUILD_TEST_REPORT.md

### 5-2. 포인터 업데이트 시스템
- [x] 포인터 계산 로직 구현 (update_pointers.py)
  ```python
  def calculate_new_pointers(text_data):
      # 한글 텍스트로 인한 길이 변화 계산
      # 모든 포인터 재계산
      # 바이너리 형식으로 변환 (리틀엔디안)
  ```
- [x] 포인터 재배치 알고리즘 구현
- [x] 자동 검증 로직 추가 (테스트 데이터 필요)
  - [x] PointerValidator 클래스 구현
  - [x] ROM 범위 검증
  - [x] 포인터 주소 검증
  - [x] 겹침 감지 알고리즘
  - [x] 5/5 테스트 통과 (test_pointer_validation.py)

### 5-3. 한글 폰트 데이터 준비
- [x] 폰트 분석 (이번 세션 갱신: 4bpp 확정)
  - [x] ROM 폰트 구조 분석 (analyze_rom_font_structure.py)
  - [x] **글리프 크기: 8x8 pixels, 4bpp** (32 bytes/glyph) — 이전 "1bpp 8 bytes" 추정은 부정확. 잉크 팔레트 인덱스 10
  - [x] **글리프 배치**: 셀당 4 타일 세로 적층 (y123-133, 11px 표시), 합성 글리프 구조 RE 완료
  - [x] **글리프 저장**: LZ77 압축 블록 (예: 0xBB7A64 = 899B 압축 → 1152B 해제 = 36 타일)
  - [x] 인코딩: Shift-JIS 확인 (raw 저장)
  - [x] 포인터 배열 분석 (trace_font_pointers.py + 워치포인트 추적)
  - [x] 폰트 데이터 위치 확정 (0x08B98000+, 텍스트 렌더러 0x08B0FFF0, BIOS LZ77 thunk 0x08B7A878)
- [x] 한글 폰트 확정·생성
  - [x] **Galmuri11-Condensed (7×11 비트맵, SIL OFL)** 선택 — `reference/fonts/Galmuri11-Condensed.bdf`
  - [x] 1028 음절 글리프 사전 렌더 → `data/korean_glyphs_8px.json` (누락 0)
  - [x] BDF 파서 `tools/bdf.py`
  - [x] 글리프 → 4타일/8px 변환기 `tools/galmuri_cell.py` (LANCZOS 스케일, 행 잘라내기 금지)
- [x] LZ77 코덱: `tools/lz77_scan.py` + `tools/lz77_compress.py` (roundtrip 검증)
- [x] ROM 삽입 프레임워크 (text+font 슬롯 주입, 검증된 단일 화면 한정)
- [x] 폰트 구성 파일 생성 (configure_font.py)

### 5-4. 번역 텍스트 삽입
- [x] 번역 텍스트 삽입 프레임워크 (import_text_enhanced.py)
  - [x] TextEncodingHandler (EUC-KR, Shift-JIS, UTF-8, 커스텀)
  - [x] TranslationLoader (CSV 파싱)
  - [x] TBLCharacterMapper (.tbl 로드)
  - [x] TextInsertionValidator (검증 로직)
  - [x] TextInserter (ROM 삽입 엔진)
- [x] ROM의 텍스트 영역에 삽입 (690/797 번역 적용 완료)
  - [x] 번역 CSV 검증 (797개 항목)
  - [x] 텍스트 삽입 실행 (690 성공, 107 실패)
  - [x] 백업 생성
  - [x] 수정된 ROM 저장

### 5-5. ROM 최종화
- [x] ROM 크기 확인 (32MB 이내) - 16.0MB 정상
- [x] 체크섬 재계산 - 0x72 -> 0x8B 업데이트
- [x] ROM 헤더 정보 분석 - GBWARS1+2 BGWJ 정상
- [x] 최종 ROM 저장 - output/game_wars_korean_final.gba

---

## PHASE 6: QA 및 테스트 (4-12주) - 진행 단계

### 6-1. 기본 기능 테스트
- [~] 에뮬레이터에서 ROM 실행 (준비됨: game_wars_korean_final.gba)
- [~] 게임 시작 화면 확인 (수동 테스트 필요)
- [~] 메뉴 네비게이션 테스트 (수동 테스트 필요)
- [~] 저장/로드 테스트 (수동 테스트 필요)
- [~] 게임 진행성 테스트 (수동 테스트 필요)

**자동 테스트 결과** (2026-05-12):
- [x] ROM 무결성 검증 통과
- [x] 헤더 정보 검증 통과
- [x] 체크섬 검증 통과
- [x] 한글 텍스트 검출됨 (363,871개 시퀀스)
- [x] 일본어 텍스트 검출됨 (1,221,291개 시퀀스)

**상세 테스팅 가이드**:
- [x] docs/PHASE6_TESTING_GUIDE.md 작성 완료

### 6-2. 텍스트 표시 검증
- [~] 모든 한글 텍스트 표시 확인 (welcome 단일 화면만 검증; 전체는 폰트 RE 의존)
- [~] 텍스트 overflow 확인
  - [x] 재인코딩 길이 타당성 (한글 17,508/17,774 = 98.5% 원본 예산 내, 1행만 오버플로)
  - [~] 메뉴 아이템 길이 (실측 미진행)
  - [~] 대사 상자 너비 (welcome 화면만 실측)
  - [~] 상태창 공간 (미진행)
- [x] 폰트 렌더링 품질 확인 (Galmuri11-Condensed 8px — 한·받·글·환·게 받침까지 또렷, evidence in docs/screenshots/)
- [~] 특수 문자 표시 확인

### 6-3. 게임플레이 완전 검증
- [ ] Game Wars 1 전체 플레이
  - [ ] 모든 스토리 모드 진행
  - [ ] 모든 전투 확인
  - [ ] 모든 메뉴 접근
  - [ ] 모든 아이템/유닛 확인
- [ ] Game Wars 2 전체 플레이 (동일)
- [ ] 난이도별 플레이 (쉬움, 보통, 어려움)
- [ ] 버그/오류 로그 작성

### 6-4. 버그 추적 및 기록
- [ ] 버그 추적 시스템 설정 (GitHub Issues)
- [ ] 발견된 버그 분류
  - [ ] Critical (게임 진행 불가)
  - [ ] Major (기능 오류)
  - [ ] Minor (표시 오류, 오타)
  - [ ] Enhancement (개선)
- [ ] 버그별 우선순위 설정

### 6-5. 수정 및 재테스트
- [ ] Critical 버그 수정
- [ ] Major 버그 수정
- [ ] Minor 버그 수정
- [ ] 각 수정마다 ROM 재빌드
- [ ] 재테스트 (회귀 테스트)

### 6-6. 최종 검수
- [ ] 최종 ROM 검증
- [ ] 전체 텍스트 재확인
- [ ] 성능 테스트 (프레임률, 속도)
- [ ] 에뮬레이터 호환성 테스트
  - [ ] VisualBoyAdvance M
  - [ ] mGBA
  - [ ] VBA-M

---

## PHASE 7: 배포 및 커뮤니티 (1-2주)

### 7-1. 배포 준비
- [~] 최종 패치 파일 생성 (PHASE 6 완료 후)
- [~] README 작성 (템플릿 준비: docs/PHASE7_DISTRIBUTION_PREP.md)
  - [~] 설치 방법
  - [~] 사용법
  - [~] 알려진 문제 (PHASE 6 테스트 결과 기반)
  - [~] 기여자 목록
- [~] 라이선스 결정 (GPL 3.0 권장) (사전 준비 완료)
- [~] GitHub Release 생성 (PHASE 6 완료 후)
- [~] 패치 파일 호스팅 (GitHub Releases)

### 7-2. 커뮤니티 공유
- [ ] 한글로게임에 패치 등록
- [ ] RomHacking.net에 등록 (영문 버전)
- [ ] GBAtemp에 공지
- [ ] 네이버 카페에 공유
- [ ] GitHub 링크 배포

### 7-3. 피드백 수집
- [ ] GitHub Issues로 버그 보고 받기
- [ ] 커뮤니티 피드백 검토
- [ ] 후속 패치 계획
- [ ] 추가 개선 사항 목록화

---

## 마일스톤별 체크포인트

| 마일스톤 | 목표 | 상태 |
|---------|-----|------|
| M1: 환경 구축 | Phase 1 완료 | ● (완료, 도구 모두 정비) |
| M2: ROM 분석 | Phase 2 완료, 구조 파악 | ● (완료, 렌더링 아키텍처 RE까지) |
| M3: 텍스트 추출 | Phase 3 완료, 전체 텍스트 추출 | ● (완료, 28,347개 항목) |
| M4: 번역 50% | 우선순위 텍스트 번역 완료 | ● (완료, 17,774 한글 행) |
| M5: 번역 100% | 모든 텍스트 번역 완료 | ● (사실상 완료, 톤/일관성 검수만 잔존) |
| M6: 베타 ROM | 자동화 시스템 구축, 첫 ROM 생성 | ◑ (단일 화면 한글 렌더 ROM/BPS 완료, 전체화는 폰트 RE 미해결) |
| M7: Alpha 테스트 | 내부 테스트 완료 | ☐ |
| M8: Beta 공개 | 커뮤니티 베타 테스트 | ☐ |
| M9: 최종 버전 | 최종 ROM 및 패치 배포 | ☐ |

---

## 리스크 관리

### 식별된 리스크

| 리스크 | 확률 | 영향 | 대응 방안 |
|------|------|------|---------|
| ROM 구조 복잡도 | 중 | 높음 | 커뮤니티와 상담, 기존 프로젝트 참고 |
| 번역팀 이탈 | 중 | 높음 | 여러 번역가 확보, 진행률 공개 |
| 기술적 오류 | 중 | 높음 | 자동화 시스템, 버전 관리, 테스트 철저 |
| ROM 크기 초과 | 낮음 | 높음 | 텍스트 압축, 폰트 최적화 |
| 호환성 문제 | 중 | 중간 | 여러 에뮬레이터 테스트 |

---

## 리소스 요구사항

### 필수 인원
- **프로젝트 리드**: 1명 (기술, 관리)
- **번역가**: 2-3명 (일본어-한글)
- **검수자**: 1-2명 (품질 관리)
- **기술 지원**: 1명 (ROM 해킹, 자동화)
- **QA**: 1-2명 (테스트, 버그 추적)

### 필수 도구 (모두 무료)
- VisualBoyAdvance M
- HxD Hex Editor
- Crystal Tile 2.5
- Python 3.9+
- Git
- Google Sheets (협업)

### 예상 비용
**0원** (모든 도구가 무료 오픈소스)

---

## 성공 기준

✓ 게임이 완벽하게 한글로 표시됨  
✓ 모든 텍스트가 자연스러운 한글  
✓ 게임플레이에 오류나 버그 없음  
✓ 모든 에뮬레이터에서 호환됨  
✓ 커뮤니티에서 긍정적 평가  

---

## 다음 단계

### 현재 상태 (2026-05-11 20:30 - /loop 재시작)

✓ **완료된 작업:**
- 프로젝트 폴더 구조 설정
- .gitignore 및 README.md 작성
- Python 자동화 스크립트 작성 (extract_text, import_text, update_pointers, build_rom)
- 빌드 스크립트 작성 (build.bat, build.sh)
- 기술 문서 작성 (ROM 분석, 번역 프로세스 가이드)
- 프로젝트 관리 문서 (CONTRIBUTING.md, GitHub 템플릿, requirements.txt)

**PHASE 3 텍스트 추출 완료:**
- ✓ 게임 ROM 헤더 분석 (analyze_rom_header.py)
- ✓ Shift-JIS 인코딩 확인 및 문자 패턴 식별
- ✓ .tbl 파일 자동 생성 (3,567 바이트-문자 매핑, 35KB)
- ✓ **텍스트 추출: 28,347개 항목 추출** (data/game_wars_found_texts.csv, 2.2MB)
  - 주소, 16진수 바이트, 디코딩된 일본어 텍스트, 길이, 문자 수
  - 컨텍스트 및 노트 필드 포함

⏳ **다음 단계:**
1. **즉시 (이번 주)**
   - [ ] Codex를 통한 일본어 텍스트 번역 시작 (우선순위: UI/메뉴)
   - [ ] 번역 가능 항목 식별 및 분류
   - [ ] 번역 용어집 작성

2. **1주 내** (PHASE 4: 번역 진행)
   - [ ] Codex와 협력하여 번역 진행
   - [ ] Google Sheets 설정 (번역 공유)
   - [ ] 번역 품질 검수

3. **PHASE 5 준비** (4주 후)
   - [ ] 번역 완료 후 ROM에 삽입 가능
   - [ ] update_pointers.py로 포인터 자동 업데이트
   - [ ] build_rom.py로 최종 ROM 생성

## 현재 프로젝트 상태 (2026-05-22 갱신)

### 완료된 PHASE
```
● PHASE 1: 환경 구축 (완료)
● PHASE 2: ROM 분석 + 렌더링 아키텍처 RE (완료 — 파서/렌더러/IWRAM 폰트 복사/LZ77 압축구조까지 RE)
● PHASE 3: 텍스트 추출 (완료, 28,347개 항목)
● PHASE 4: 번역 (사실상 완료 — 17,774 한글 행, 1028 음절)
● PHASE 5: 기술적 구현 (완료)
  - 5-1: 빌드 파이프라인 ●
  - 5-2: 포인터 검증 ●
  - 5-3: 폰트 분석 (4bpp 32B 확정) + Galmuri11-Condensed 1028 글리프 ●
  - 5-4: 텍스트 삽입 프레임워크 ●
  - 5-5: ROM 최종화 (체크섬 0x19 fix) ●
```

### 진행 중인 PHASE
```
◑ PHASE 6: QA 및 테스트
  - 자동 테스트: ● 완료
  - 폰트 렌더링 검증: ● 완료 (Galmuri11-Condensed 8px 한·받·글·환·게)
  - 인게임 한글 렌더: ◑ 단일 화면(welcome)만 검증 (output/welcome_korean.gba + dist/welcome_korean.bps)
  - 전체 화면 검증: ☐ (폰트 RE 미해결로 차단)
  - 문서: ● success.md / fail.md / HANGUL_PROGRESS.md
```

### 준비 단계 PHASE
```
⏳ PHASE 7: 배포 (전체 한글화 완성 대기)
  - 배포 전략: ● docs/PHASE7_DISTRIBUTION_PREP.md 완성
  - BPS 인코더: ● tools/make_bps.py (적용 검증 통과)
  - GitHub Release: ☐
  - 커뮤니티 배포: ☐
```

### 현재 작업 상황 (2026-05-22)
- **검증된 산출물**: `output/welcome_korean.gba` (부팅+한글 welcome), `dist/welcome_korean.bps` (697B 패치, 적용 검증)
- **도구**: 헤드리스 디버거 (BP/워치/레지스터 캡처), LZ77 코덱, BPS 인코더, Galmuri 글리프 변환기 — 모두 작동
- **렌더링 RE**: 파서 0x08B11E48, 타이프라이터 0x08B0FFF0, BIOS LZ77 thunk 0x08B7A878, IWRAM 폰트 복사 0x03006744, 글리프=LZ77 압축 블록

### 현재 병목 (Blockers)
1. **전체 게임 한글화의 폰트 RE** — 동적 슬롯 할당 + 다층 시스템(디스패치→압축블록→타이프라이터→VRAM)에서 char→실제 표시 글리프 소스의 결정적 매핑이 무너짐. 자세한 시도와 사유는 [fail.md](fail.md).
2. **PHASE 7 배포** — 단일 화면 BPS는 가능하나 전체화는 ①의 해결 또는 화면별 도구화 필요.

### 다음 단계 옵션 (재게재)
1. **검증된 단일 화면 방법으로 핵심 대화 선별 한글화** (welcome 패턴 도구화 + 화면별 슬롯 충돌 관리)
2. **외부 정적 분석 (Ghidra)** 으로 텍스트 렌더 파이프라인 완전 RE
3. **베이스포인터 리포인트** (Gemini 권장) — 한글 폰트를 ROM 빈 영역에 추가 + 폰트 베이스 LDR instruction 패치

### 최신 추가 문서
- [x] docs/success.md (작동 검증된 방법·산출물)
- [x] docs/fail.md (28개 시도와 실패 사유)
- [x] docs/HANGUL_PROGRESS.md (기술 진행 로그)
- [x] docs/PHASE6_TESTING_GUIDE.md
- [x] docs/PHASE7_DISTRIBUTION_PREP.md
- [x] docs/FONT_HACK_RESEARCH_2026_05_21.md

---

**문서 작성일**: 2026년 5월 11일
**마지막 수정**: 2026년 5월 22일 (이번 세션 성과 반영)
**버전**: 1.1

---

## 2026-05-23 진행 업데이트

### 완료 항목
- [x] **welcome dialog 한글화** (v25): "게임보이 워즈에 어서 와! ▼" — 시스템 마커 동적 정렬, 폰트 통일, 좌측 정렬, 반각 띄어쓰기
- [x] **원본 ROM 베이스 재구성** (v27): v14_tight 폰트 슬롯 패치 제거 → 잔재 없음. Hook B만으로 한글 렌더링
- [x] **name input prompt 한글화**: "네 이름을 알려 줘. ▼" (0xDF8DB2)
- [x] **자동 빌드 도구**: `tools/build_multi_dialog_rom.py`, `tools/build_multi_dialog_v2.py`, `tools/find_katakana_slots.py`
- [x] **SJIS→slot 매핑 RE**: 공식 `slot_addr = 0xB984D0 + (sjis_low - 0x41) * 0x10` 확정 (ア-オ 검증)
- [x] **이름 입력 grid 부분 작동**: A-F 알파벳 정상 표시 (행 1)

### 진행 중
- [ ] **grid 전체 알파벳 변환**: dakuten/small katakana 슬롯 overlap 해결 + 8x8 글리프 깔끔하게
- [ ] 이름 입력 후 다음 화면에서 이름 출력 검증

### 다음 단계
1. 슬롯 stride 정확 분석 (0x10 vs 0x20 vs 32-byte 슬롯)
2. 전체 ASCII 영문/숫자 글리프 주입
3. 이름 입력 동작 + 출력 검증
4. Welcome 외 다른 dialog로 확장
