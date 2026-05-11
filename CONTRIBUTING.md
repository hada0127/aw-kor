# Game Wars GBA 한글화 프로젝트 기여 가이드

이 프로젝트에 기여하고 싶으신가요? 환영합니다! 아래 가이드를 따라 참여하실 수 있습니다.

## 기여 방법

### 1. 프로젝트 포크 및 클론

```bash
# 이 리포지토리를 포크합니다
# (GitHub의 Fork 버튼 사용)

# 포크한 리포지토리를 클론합니다
git clone https://github.com/your-username/aw-kor.git
cd aw-kor
```

### 2. 작업 브랜치 생성

```bash
# main 브랜치에서 새 브랜치 생성
git checkout -b feature/your-feature-name

# 또는 버그 수정의 경우
git checkout -b fix/bug-description
```

### 3. 작업 진행

- 코드 또는 번역 작업 진행
- 정기적으로 커밋 (명확한 커밋 메시지)
- 테스트 (가능한 경우)

### 4. 커밋 메시지 규칙

```
<type>: <subject>

<description>

<footer>
```

**Type:**
- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 스타일 (포맷팅 등)
- `refactor`: 코드 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드, 의존성 등

**예:**
```
feat: ROM 텍스트 추출 스크립트 추가

- extract_text.py 구현
- .tbl 파일 로드 및 문자 변환
- CSV 형식으로 결과 저장

Closes #1
```

### 5. Pull Request 생성

```bash
# 변경사항 커밋 및 푸시
git push origin feature/your-feature-name
```

GitHub에서 Pull Request를 생성하고 다음을 포함합니다:
- 변경 내용 설명
- 관련 Issue 링크 (있는 경우)
- 스크린샷 (시각적 변경의 경우)

## 역할별 기여 방법

### 1. 번역가

**역할:** Game Wars의 일본어 텍스트를 한글로 번역

**시작 방법:**
1. `docs/plan.md`의 PHASE 4 참고
2. `docs/translation_process.md` 읽기
3. 프로젝트 리더에 연락 → 번역 배정

**제출:**
- Google Sheets 또는 CSV 파일 업로드
- 번역된 텍스트 항목별 검수 완료

### 2. 검수자

**역할:** 번역 품질 검증, 오타 확인, 톤앤매너 일관성

**체크리스트:**
- [ ] 원문 의미를 정확히 전달
- [ ] 게임 톤앤매너 일치
- [ ] 한글이 자연스러운가
- [ ] 오타/문법 오류 확인
- [ ] 텍스트 길이 적절성
- [ ] 용어 일관성

**제출:**
- 검수 의견을 CSV 파일의 notes 칸에 작성
- 완료 후 프로젝트 리더에 보고

### 3. 기술 개발자

**역할:** ROM 분석, 스크립트 작성, 빌드 시스템 관리

**기여 가능한 영역:**
- ROM 분석 도구 개선
- Python 스크립트 최적화
- 자동화 시스템 확장
- 포인터 계산 알고리즘
- 에러 처리 및 로깅

**예시:**
```python
# tools/extract_text.py 개선 제안
def extract_text_from_rom(rom_path, tbl_mapping, min_length=2):
    # 더 빠른 텍스트 추출
    # 추가 검증 로직
    # 향상된 오류 처리
```

**체크리스트:**
- [ ] Python 3.9+ 호환성 확인
- [ ] 주석 추가 (필요한 경우)
- [ ] 테스트 코드 작성 (가능하면)
- [ ] 문서화 (새 기능)

### 4. ROM 분석가

**역할:** Game Wars의 ROM 구조 분석

**필요한 도구:**
- VisualBoyAdvance M
- HxD Hex Editor
- Crystal Tile 2.5

**작업:**
1. ROM 구조 파악
2. 텍스트 데이터 위치 찾기
3. 포인터 위치 매핑
4. .tbl 파일 작성
5. 결과 문서화

**제출:**
- `docs/rom_analysis.md`: 분석 결과
- `tools/game_wars.tbl`: 문자 맵핑
- `data/pointers_1.csv`: 포인터 테이블

## 코드 스타일 가이드

### Python

```python
# 좋은 예
def extract_text_from_rom(rom_path, tbl_mapping, min_length=2):
    """ROM에서 텍스트를 추출합니다."""
    texts = []
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    # ...
    return texts

# 나쁜 예
def extractText(romPath,tblMapping):
    #ROM에서 텍스트 추출
    texts=[]
    ...
    return texts
```

**규칙:**
- PEP 8 준수
- 함수명: snake_case
- 변수명: snake_case
- 클래스명: PascalCase
- 4칸 들여쓰기
- 한 줄 최대 79자

### 문서

```markdown
# 좋은 제목
기술적 설명과 예시를 포함합니다.

## 섹션
상세한 내용

### 하위 섹션
세부사항
```

**규칙:**
- Markdown 문법 준수
- 명확하고 간결한 언어
- 예시 포함 (가능하면)
- 링크와 참고 자료

## 버그 보고

버그를 발견하셨나요?

1. GitHub Issues에서 검색 (중복 확인)
2. 새 Issue 생성
3. 다음 정보 포함:
   - 버그 설명
   - 재현 방법
   - 예상 결과
   - 실제 결과
   - 환경 (OS, Python 버전, 도구 버전 등)
   - 스크린샷 (해당하는 경우)

**예:**
```
제목: Game Wars 1 텍스트 추출 실패

설명: extract_text.py 실행 시 인코딩 오류

재현:
1. original/game_wars_1.gba 준비
2. python tools/extract_text.py original/game_wars_1.gba tools/game_wars.tbl data/test.csv 실행
3. 오류 발생

예상: data/test.csv 생성
실제: UnicodeDecodeError

환경:
- OS: Windows 11
- Python: 3.9.7
- .tbl 파일: tools/game_wars.tbl
```

## 기능 요청

새 기능을 제안하시나요?

1. GitHub Issues에서 "Feature Request" 제목으로 생성
2. 다음 포함:
   - 기능 설명
   - 사용 사례
   - 구현 방법 제안 (선택사항)

**예:**
```
제목: ROM 자동 검증 기능

설명: 생성된 ROM의 무결성을 자동으로 검증합니다.

사용 사례:
- 빌드 후 자동 검증
- 오류 조기 발견

제안: build_rom.py에서 ROM 체크섬 검증 추가
```

## 프로젝트 구조 이해

```
aw-kor/
├── original/              # 원본 ROM
├── docs/                  # 문서
│   ├── plan.md           # 프로젝트 계획
│   ├── rom_analysis_guide.md
│   └── translation_process.md
├── tools/                # 스크립트 및 도구
│   ├── extract_text.py
│   ├── import_text.py
│   ├── build.bat/build.sh
│   └── game_wars.tbl
├── data/                 # 추출된 데이터
│   ├── game_wars_1_text.csv
│   └── pointers_1.csv
├── translation/          # 번역 파일
├── output/               # 생성된 ROM
└── README.md
```

## 질문 및 지원

- **GitHub Issues**: 버그 보고, 기능 요청
- **GitHub Discussions**: 일반 질문, 아이디어 공유
- **프로젝트 리더**: 역할 배정, 진행상황 문의

## 행동 강령

이 프로젝트의 모든 참여자는:
- 서로 존중하고 친절할 것
- 건설적인 피드백 제공할 것
- 다양한 의견 존중할 것
- 스팸/욕설/차별 금지

## 라이선스

이 프로젝트에 기여함으로써, 당신의 기여물이 프로젝트의 라이선스 하에 배포되는 것에 동의합니다.

---

**감사합니다!** 🙏

Game Wars 한글화 프로젝트에 관심 가져주셔서 감사합니다.
