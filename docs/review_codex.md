# Plan.md 검토 - Codex(기술/개발 중심)

**검토자**: Claude (Codex 관점 - 개발 및 기술 검토)  
**검토일**: 2026년 5월 11일  
**대상**: docs/plan.md v1.0

---

## 종합 평가

**평점**: ⭐⭐⭐⭐ (4/5)  
**종합의견**: 기술적 구조는 견고하나, **자동화 스크립트 구현 난도가 과소평가**되었습니다.

---

## 1. 기술적 검토 - PHASE 5 (구현 단계)

### ✓ 잘된 점

1. **도구 선택이 적절함**
   - Crystal Tile 2.5: GBA 바이너리 편집에 최적화
   - HxD: 표준적인 Hex 편집기
   - VisualBoyAdvance M: 디버깅 기능 완비
   
2. **.tbl 파일 프로세스 상세함**
   - RSEARCH로 자동 추출 → 수동 검증이 올바른 순서
   - TBL 파일 검증 단계 포함

3. **포인터 매핑 체계화됨**
   - CSV 형식의 구조화된 데이터
   - 메타데이터 포함

### ⚠️ 우려 사항 및 개선 필요

#### 1. 자동화 스크립트 난도가 과소평가됨
```python
# 현재 plan.md의 예상:
# tools/update_pointers.py: 포인터 자동 업데이트
# "Python 스크립트로 간단히 해결"

# 실제 구현 복잡도:
# - 포인터 체인 추적 (pointer chain)
# - 동적 메모리 할당 처리
# - 압축된 텍스트 데이터 처리 여부 판단
# - 상대 포인터 vs 절대 포인터 구분
# - 엔디안(endian) 처리
# - ROM 오버플로우 방지
```

**권장사항**:
- PHASE 5-1에 "포인터 시스템 복잡도 분석" 추가 (1주)
- 포토타입 스크립트 작성 후 아키텍처 재검토

#### 2. 인코딩 구현 상세 필요
```python
# EUC-KR 선택은 좋지만, 다음을 고려해야 함:

# 문제 1: 가변 길이 제어 문자
def validate_encoding(text):
    # null terminator 처리
    if '\0' in text:  # 위험
        # 텍스트를 다시 구조화해야 함
    
# 문제 2: 포인터 계산 변경
# 영어: "Hello" = 5 bytes
# EUC-KR 한글: "안녕" = 4 bytes  
# 그런데 다른 위치의 "테스트" = 6 bytes
# → 모든 포인터가 다시 계산되어야 함
```

**권장사항**:
- 인코딩 검증 로직 추가 (비클린 bytes 처리)
- 포인터 재배치 알고리즘 미리 검증

#### 3. ROM 크기 관리 부족
```
PHASE 5-5에서 마지막에 "ROM 크기 확인"하는 것은 너무 늦음.

현재 상황:
- 원본: ~32MB (추정)
- 폰트 데이터: ~150KB (한글 2,350자)
- 텍스트 추가: ~50-100KB
- 총: 32MB 근처

위험: 빌드 후 32MB 초과 발견 → 모든 작업 재검토
```

**권장사항**:
- PHASE 5-2부터 ROM 크기 추적
- 자동화 빌드에 크기 체크 로직 포함
- 텍스트 압축 계획 (선택사항) 조기 검토

#### 4. 빌드 자동화 복잡도 상세화 필요
```batch
# 제안된 build.bat는 단순화되어 있음

@echo off
python tools/extract_text.py
python tools/import_text.py
python tools/update_pointers.py
python tools/generate_rom.py output.gba

# 실제 구현에 필요한 것:
# 1. 에러 처리
# 2. 롤백 메커니즘
# 3. 증분 빌드 (모든 것을 매번 재빌드하지 않음)
# 4. 검증 단계
# 5. 백업 자동화
# 6. 로깅
```

**개선된 배치 스크립트**:
```batch
@echo off
setlocal enabledelayedexpansion

echo [1/5] Extracting text...
python tools/extract_text.py || goto error

echo [2/5] Importing translation...
python tools/import_text.py || goto error

echo [3/5] Updating pointers...
python tools/update_pointers.py || goto error

echo [4/5] Validating ROM...
python tools/validate_rom.py || goto error

echo [5/5] Generating ROM...
python tools/build_rom.py output.gba || goto error

echo Build successful!
exit /b 0

:error
echo Build failed at step %errorlevel%
REM Rollback if needed
exit /b 1
```

---

## 2. 도구 및 라이브러리 검토

### ✓ 추천 추가 도구

1. **Python 라이브러리**
   ```python
   # 강력히 권장
   import struct         # 바이너리 처리 (이미 포함)
   import hashlib        # 체크섬 계산
   import logging        # 로깅 (추가 권장)
   
   # 옵션
   from PIL import Image  # 폰트 글리프 생성 시
   ```

2. **검증 도구**
   - **CRC32 계산기**: ROM 체크섬 자동 검증
   - **바이너리 비교 도구** (WinMerge): 전후 ROM 비교

### ⚠️ 문제점

**Ruby 또는 Go 기반 대안 검토 부족**
- Python은 느린 편 (ROM 처리에는 문제 아님)
- 하지만 포인터 재배치에서 1000+ 주소 처리 시 성능 고려
- 현재 프로젝트 규모면 Python으로 충분

---

## 3. 테스트 전략 검토 (PHASE 6)

### ✓ 잘된 점

1. **다단계 테스트 구조**
   - 기본 기능 → 텍스트 표시 → 전체 플레이
   - 순차적 검증이 논리적

2. **버그 분류 체계**
   - Critical/Major/Minor 분류 명확
   - 우선순위 설정 체계적

### ⚠️ 개선 제안

#### 자동화된 테스트 부족
```python
# 제안: 자동화 검증 스크립트 추가

def test_pointer_validity():
    # 모든 포인터가 유효한 ROM 주소를 가리키는지 확인
    pass

def test_text_encoding():
    # 모든 한글 텍스트가 EUC-KR로 올바르게 인코딩되었는지
    pass

def test_rom_integrity():
    # ROM 체크섬 확인
    # 헤더 정보 확인
    pass

def test_memory_overlap():
    # 텍스트 데이터가 다른 리소스와 겹치지 않는지
    pass
```

**권장**: PHASE 6-3에 "자동화 검증 도구" 추가

---

## 4. Git 워크플로우 검토

### ✓ 지현 상태
- GitHub 리포지토리 생성 ✓
- .gitignore 설정 ✓

### ⚠️ 권장 추가사항

```
.gitignore에 다음 추가:

# ROM 파일 (저작권 때문에)
*.gba
original/

# 빌드 결과물
output/
*.rom

# 임시 파일
*.tmp
*.bak
*.log

# IDE
.vscode/
.idea/
*.pyc

# 데이터 파일 (크기 때문에)
data/*.bin
```

**커밋 전략**:
- 각 Phase 완료마다 메이저 태그 (v1.0, v1.1 등)
- 구현 단계별 상세 커밋 메시지
- 예시:
  ```
  git tag -a v1.0-analysis -m "ROM analysis complete"
  git tag -a v1.1-extraction -m "Text extraction complete"
  ```

---

## 5. 예상 기술적 리스크

### High Priority
1. **포인터 체인 오류** (Critical)
   - 포인터가 다른 포인터를 가리키는 경우
   - 영향: 게임 크래시
   - 대응: 포인터 검증 자동화

2. **ROM 오버플로우** (Critical)
   - 한글 텍스트가 ROM 한계 초과
   - 영향: ROM 생성 불가
   - 대응: 크기 추적 자동화, 조기 감지

### Medium Priority
3. **인코딩 호환성** (Major)
   - EUC-KR ↔ UTF-16 변환 오류
   - 영향: 깨진 텍스트
   - 대응: 인코딩 검증 테스트

4. **에뮬레이터 버전 호환성** (Major)
   - 다양한 에뮬레이터에서 다른 동작
   - 영향: 일부 유저만 문제 경험
   - 대응: 여러 에뮬레이터 테스트 필수

### Low Priority
5. **폰트 렌더링** (Minor)
   - 한글 글리프 깨짐
   - 영향: 시각적 문제
   - 대응: 폰트 데이터 검증

---

## 6. 우선순위 조정 권장

### 현재 계획 문제점

```
PHASE 5: 기술적 구현 (4-8주)
  └─ 많은 복잡한 작업을 한꺼번에 처리
```

### 권장 개선

```
PHASE 5A: 프로토타입 & 아키텍처 (2-3주)
  ├─ 포인터 시스템 프로토타입
  ├─ 인코딩 검증 로직
  ├─ ROM 크기 트래킹
  └─ 자동화 빌드 스켈레톤

PHASE 5B: 구현 & 최적화 (3-5주)
  ├─ 본격 빌드 시스템 구축
  ├─ 자동화 테스트 추가
  ├─ 성능 최적화
  └─ 에러 처리 강화
```

---

## 7. 기술 스택 최종 검토

| 컴포넌트 | 선택 | 평가 | 대안 |
|---------|-----|------|-----|
| 언어 | Python 3.9+ | ⭐⭐⭐⭐⭐ | Go, Rust (과다) |
| Hex 편집 | HxD | ⭐⭐⭐⭐ | Hex Workshop (상용) |
| ROM 분석 | Crystal Tile 2.5 | ⭐⭐⭐⭐ | 직접 개발 (불가) |
| 에뮬레이터 | VBA-M | ⭐⭐⭐⭐ | mGBA (권장 추가) |
| 버전관리 | Git | ⭐⭐⭐⭐⭐ | (필수) |

---

## 8. 최종 권장사항

### ✅ 수용 권장
1. PHASE 5를 5A + 5B로 분할 (복잡도 분산)
2. 자동화 테스트 추가 (검증 강화)
3. ROM 크기 모니터링 조기 시작
4. 에러 처리 및 롤백 메커니즘 추가
5. 포인터 검증 자동화

### ⚠️ 검토 권장
1. 포인터 시스템 복잡도 재평가
2. 인코딩 변환 로직 프로토타입 선행
3. 자동화 빌드 스크립트 사전 설계

### ❌ 거절 또는 무시해도 됨
1. Ruby/Go로의 언어 변경 (Python으로 충분)
2. 상용 도구 사용 (무료 도구로 충분)
3. 빌드 시스템을 극도로 복잡하게 구축 (단순 유지)

---

## 종합 평가

**수정 필요 정도**: 중간 (3/5)

- ✓ 전체 구조는 건전함
- ⚠️ 기술 구현 복잡도를 과소평가했음
- ✓ 테스트 전략은 좋음
- ⚠️ 자동화 및 검증 로직 상세화 필요

**다음 단계**:
1. PHASE 5 상세화 (포인터 시스템 프로토타입)
2. 자동화 스크립트 틀 작성
3. 첫 번째 테스트 ROM 생성 시도 (Game Wars 1의 작은 부분)
4. 예상 기간 재평가

---

**검토자**: Codex(기술 중심)  
**검토 완료**: 2026년 5월 11일
