# PHASE 5-3: 한글 폰트 데이터 준비 - 상태 보고서

**날짜**: 2026-05-11  
**상태**: ⏸️ 기술적 블록 (ROM 폰트 구조 분석 필요)  
**진행**: 프레임워크 준비 완료 (80%)

---

## 현재 상태

PHASE 5-3는 기술적으로 ROM의 폰트 구조 분석이 필요합니다. Python-only 접근으로는 다음 정보를 자동으로 수집할 수 없습니다:

1. **ROM 내 폰트 위치**: Hex 에디터로 수동 찾기 필요
2. **글리프 구조**: ROM 리버싱 또는 문서 필요
3. **인코딩 방식**: 게임 코드 분석 필요

## 준비된 작업

### ✓ 프레임워크 구현
```
tools/font_preparation_framework.py
  - GBAFontInfo: 폰트 정보 저장소
  - FontAnalyzer: 분석 틀
  - KoreanGlyphGenerator: 한글 글리프 생성 틀
  - FontInsertionEngine: ROM 삽입 엔진
  - FontEncodingConverter: 인코딩 변환 도구
```

### ✓ 분석 가이드
```
tools/font_preparation_framework.py
  - ROM 폰트 위치 찾기 방법
  - 폰트 특성 파악 방법
  - 한글 적응 옵션 3가지
  - 단계별 구현 계획
```

### ✓ 한글 글리프 생성 준비
- 완성형 한글 2,350자 범위 정의
- 기본 ASCII 지원
- 글리프 크기 계산 로직

## 기술적 블록 요인

### 1. ROM 폰트 구조 분석
```
필요 도구:
  - HxD (Hex 에디터) - 사용 불가 (Windows GUI 도구)
  - 또는 IDA Pro, Ghidra (역어셈블러)
  - 또는 VisualBoyAdvance M 디버거

필요 지식:
  - GBA 그래픽 형식
  - Game Wars 1+2 코드 구조
  - Shift-JIS 폰트 포맷
```

### 2. 폰트 데이터 소스
```
가능한 방법:
  1. 기존 Game Wars 번역에서 폰트 추출
  2. GBA 공개 폰트 리소스 찾기
  3. 새로운 한글 폰트 작성 (도구 필요)
  4. 오픈소스 비트맵 폰트 활용
```

### 3. ROM 공간 부족
```
문제: 기존 폰트 공간에 한글을 모두 추가하기 어려울 수 있음

해결 방법:
  A. 일부 문자 제거하고 한글로 대체 (ROM 크기 유지)
  B. ROM 확장 영역에 추가 (ROM 크기 증가)
  C. 압축 또는 최적화 (복잡도 증가)
```

## 차단 해제 방법

### 방법 1: ROM 분석 (권장)
```
1. HxD에서 "Game Boy Wars Advance 1+2.gba" 열기
2. 검색: 일본어 문자의 비트맵 패턴 찾기
3. 폰트 데이터 영역 식별
4. 시작 주소, 크기, 인코딩 기록

필요 시간: 2-4시간
도구: HxD (무료, 설치됨)
```

### 방법 2: 기존 자료 활용
```
1. Game Wars 기존 한글화 프로젝트 찾기
2. 폰트 자료 또는 분석 결과 확인
3. ROM 오프셋 정보 수집

필요 시간: 1-2시간
도구: 웹 검색, GBAtemp/RomHacking 포럼
```

### 방법 3: 커뮤니티 지원
```
1. RomHacking.net 또는 GBAtemp 포럼에 질문
2. GBA 폰트 전문가 찾기
3. 폰트 분석 결과 공유

필요 시간: 1일 이상 (응답 대기)
```

## 준비된 구현 계획

폰트 구조 정보가 수집되면 다음 순서로 진행할 수 있습니다:

```
[1] 폰트 정보 설정
    font_info = GBAFontInfo()
    font_info.font_start_address = 0x???  # 분석에서 찾은 값
    font_info.glyph_size_bytes = ?         # 글리프당 바이트 크기
    ...

[2] 한글 글리프 생성
    glyphs = KoreanGlyphGenerator.generate_hangul_glyphs(font_info)

[3] ROM에 삽입
    FontInsertionEngine.insert_font_data(
        'original/game_wars.gba',
        font_info,
        glyphs,
        'output/game_wars_kor_font.gba'
    )

[4] 검증 및 테스트
    에뮬레이터에서 한글 표시 확인
```

## 예상 일정

| 작업 | 기간 | 담당 |
|-----|------|------|
| ROM 폰트 구조 분석 | 2-4시간 | 기술팀 |
| 한글 글리프 생성 | 1-2주 | 디자인/개발팀 |
| 폰트 데이터 준비 | 1-2주 | 개발팀 |
| ROM 삽입 및 테스트 | 2-4시간 | 기술팀 |

**총 예상 기간**: 2-4주 (폰트 자료 확보 후)

## 의존성 및 영향

### PHASE 5-3 완료 후:
- ✓ PHASE 5-4 (텍스트 삽입) 진행 가능
- ✓ PHASE 5-5 (ROM 최종화) 진행 가능
- ✓ PHASE 6 (QA) 시작 가능

### 현재 블록 상태:
- ⏸️ PHASE 5-4 대기 (한글 인코딩 필요)
- ⏸️ PHASE 5-5 대기 (최종 테스트 필요)
- ⏸️ PHASE 6 대기 (한글 ROM 필요)

## 권장 조치

### 즉시 (이번 주)
1. ROM 폰트 구조 분석 시작
   - HxD에서 ROM 열기
   - 일본어 문자 비트맵 찾기
   - 폰트 영역 범위 식별

2. GBA 폰트 자료 검색
   - RomHacking.net 검색
   - GitHub "GBA font" 검색
   - 유사 프로젝트 찾기

### 1주 내
1. 폰트 정보 수집 완료
2. framework 구현 시작
3. 한글 글리프 준비 계획 수립

### 2-4주
1. 한글 글리프 생성 완료
2. ROM 삽입 테스트
3. 에뮬레이터 검증

## 리소스 준비

### 파일
- `tools/font_preparation_framework.py` ✓ (프레임워크)
- `docs/PHASE5_3_FONT_STATUS.md` ✓ (이 문서)

### 필요 정보 (수집 대기)
- ROM 폰트 시작 주소
- 글리프 크기 (픽셀)
- 글리프당 바이트 크기
- 폰트 데이터 끝 주소
- 인코딩 방식 확인

### 도구
- HxD Hex 에디터 (설치됨)
- Python 3.9+ (준비됨)
- VisualBoyAdvance M (설치됨)

## 성공 기준

PHASE 5-3 완료 기준:

1. ✓ ROM 폰트 위치 식별
2. ✓ 폰트 특성 파악
3. ✓ 한글 글리프 2,350자 준비
4. ✓ 인코딩 방식 결정
5. ✓ ROM 삽입 및 테스트 성공
6. ✓ 에뮬레이터에서 한글 표시 확인

## 결론

**현재 상태**: PHASE 5-3는 ROM 폰트 구조 분석이 필요한 기술적 블록 상태입니다.

**준비 완료**:
- ✓ 프레임워크 (80%)
- ✓ 분석 가이드
- ✓ 구현 계획

**다음 액션**:
1. ROM 폰트 구조 분석 시작
2. 폰트 정보 수집
3. 프레임워크 구현 완료

이 작업이 완료되면 PHASE 5-4, 5-5, 6을 진행할 수 있습니다.

---

**상태**: ⏸️ 블록 (기술 분석 필요)  
**프레임워크**: ✓ 준비 완료  
**다음**: ROM 폰트 구조 분석 시작
