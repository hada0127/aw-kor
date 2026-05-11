# Game Wars (GBA) 한글화 프로젝트

Game Boy Advance Game Wars 1+2를 100% 한글화하는 프로젝트입니다.

## 프로젝트 구조

```
aw-kor/
├── original/          # 원본 ROM 파일 (Game Wars 1, 2)
├── docs/              # 문서 (계획, 분석, 리뷰)
├── tools/             # ROM 해킹 및 추출 도구
├── data/              # 추출된 게임 데이터 (텍스트, 포인터 등)
├── translation/       # 번역 파일 (CSV, 스프레드시트)
├── output/            # 생성된 한글화 ROM 파일
└── .gitignore         # Git 제외 설정
```

## 진행 상황

자세한 진행 상황은 `docs/plan.md` 참고

### 마일스톤 (2026-05-11)

| 항목 | 상태 | 진행률 |
|------|------|--------|
| M1: 환경 구축 | ◐ 진행 중 | 70% |
| M2: ROM 분석 | ☐ 도구 대기 | 0% |
| M3: 텍스트 추출 | ☐ 의존성 대기 | 0% |
| M4-M5: 번역 | ☐ 팀 구성 필요 | 0% |
| M6-M9: 구현/테스트/배포 | ◐ 스크립트 완료 | 50% |

### 완료된 작업

✅ **자동화 완료:**
- 프로젝트 구조 및 설정
- Python 자동화 스크립트 (4개 도구)
- 빌드 스크립트 (Windows/Linux/macOS)
- 기술 문서 (ROM 분석, 번역, .tbl 형식)
- 프로젝트 관리 문서 (CONTRIBUTING, GitHub 템플릿)
- GitHub Actions CI 설정

### 다음 단계

⏳ **필요한 수동 작업:**
1. ROM 분석 도구 설치 (VisualBoyAdvance M, HxD, Crystal Tile)
2. Game Wars 1+2 ROM 파일 준비
3. ROM 구조 분석 및 .tbl 파일 작성
4. 번역팀 구성 및 번역 진행

## 필수 도구

모든 도구는 **무료** 오픈소스입니다.

- **VisualBoyAdvance M**: GBA 에뮬레이터 및 디버거
- **HxD**: Hex 에디터
- **Crystal Tile 2.5**: 그래픽 편집 도구
- **Python 3.9+**: 텍스트 추출 및 자동화 스크립트
- **Git**: 버전 관리

## 로드맵

1. **PHASE 1**: 환경 구축 및 리포지토리 초기화
2. **PHASE 2**: ROM 구조 분석 및 문서화
3. **PHASE 3**: 텍스트 추출 및 포인터 매핑
4. **PHASE 4**: 번역 진행 (6-12개월)
5. **PHASE 5**: 자동화 시스템 구축 및 ROM 생성
6. **PHASE 6**: QA 및 테스트
7. **PHASE 7**: 배포 및 커뮤니티 공유

## 기여하기

이 프로젝트는 커뮤니티 기반 한글화 프로젝트입니다.
번역가, 검수자, 기술 지원자 모집 중입니다.

## 참고 자료

- 계획: `docs/plan.md`
- ROM 분석: `docs/research.md` (작성 예정)
- 번역 진행: Google Sheets (준비 예정)

## 라이선스

정책 결정 예정
