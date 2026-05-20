# Game Wars 한글화 프로젝트 - Claude 작업 지침

## 언어 설정
모든 응답은 **한국어**로 작성합니다.

## 번역 작업 방식

### 필수 사항
**번역은 반드시 `codex cli`로 실행합니다.**

### 테스트 및 검증된 방법
```bash
python tools/phase4_codex_translate.py
```

**상태:** ✅ 테스트 완료, 성공 검증됨
- 배치 크기: 20개 텍스트
- 진행 상황: 2,442 / 28,347 (8.61%)
- 남은 텍스트: 25,905개

### 실행 단계

#### 1단계: Codex 번역 실행
```bash
python tools/phase4_codex_translate.py
```
- 자동으로 untranslated 텍스트 식별
- Codex CLI로 배치 처리
- 결과를 data/translation_for_import.csv에 저장

#### 2단계: 진행률 확인
```bash
wc -l data/translation_for_import.csv
```
- 목표: 28,348줄 (28,347 번역 + 1 헤더)

#### 3단계: 100% 완료 시
```bash
python tools/execute_phase5_4.py   # ROM 재구성
python tools/execute_phase5_5.py   # ROM 최종화
python tools/phase6_basic_test.py  # 검증
```

## 중요 설정값

| 항목 | 값 |
|------|-----|
| 번역 도구 | Codex CLI |
| 배치 크기 | 20 |
| 소스 파일 | data/game_wars_found_texts.csv |
| 출력 파일 | data/translation_for_import.csv |
| 목표 진행률 | 100% (28,347 / 28,347) |

## 주의사항

- ⚠️ Batch API나 다른 방식 사용 금지
- ✅ Codex CLI만 사용
- ✅ 항상 phase4_codex_translate.py 실행
- ✅ 진행률을 수시로 확인

## 불가능한 작업

다음은 이 프로젝트에서 수행하지 않습니다:
- Claude SDK 직접 호출 (Batch API 등)
- OpenAI API 사용
- 수동 번역
- 다른 도구 체인

---

**최종 목표:** `data/translation_for_import.csv` 파일이 28,348줄(헤더 포함)에 도달할 때까지 codex cli 번역 진행
