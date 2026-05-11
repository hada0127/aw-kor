# 번역 가이드 (PHASE 4)

**작성**: 2026-05-12  
**상태**: 진행 중 (2.8% 완료 - 797/28,347)  
**목표**: 28,347개 모든 텍스트 번역

---

## 번역 현황

### 진행률
```
완료: 797개 (2.8%)
남은 항목: 27,550개 (97.2%)

Priority 분류:
  1. UI/메뉴 (Priority 1): 797/12,242 완료 (6.5%)
  2. 스토리/대사 (Priority 2): 0/8,300 완료 (0%)
  3. 기타 텍스트 (Priority 3): 0/7,805 완료 (0%)
```

### 완료된 번역 (샘플)

**파일**: `data/translation_for_import.csv`

```
address,japanese,korean,length
0xA030B8,ゲーム ウォーズ,게임 워즈,8
0xA030C0,１ ＋ ２,1+2,3
0xA030C4,ニューゲーム,새 게임,8
0xA030CC,コンティニュー,계속,6
```

---

## 번역 환경 구성

### 1단계: 번역 도구 설정

#### Python 스크립트를 사용한 번역 추가

```bash
# 1. 번역 데이터 준비
python tools/prepare_translation.py

# 2. 번역 추가
python tools/add_translations.py --input data/new_translations.csv

# 3. ROM 재빌드
python tools/execute_phase5_4.py
python tools/execute_phase5_5.py
```

#### Google Sheets를 사용한 협업 번역

```
1. 링크: [Google Sheets 생성 예정]
2. 구조:
   - Column A: 주소 (Address)
   - Column B: 원본 일본어 (Japanese)
   - Column C: 번역 (Korean)
   - Column D: 상태 (Status: To Do / In Progress / Done / Review)
   - Column E: 번역자 (Translator)
   - Column F: 노트 (Notes)

3. 공유 링크: [준비 중]
```

---

## 번역 우선순위

### Priority 1: UI/메뉴 텍스트 (완료: 6.5%)

가장 중요하고 빈도가 높은 텍스트들:

```
일반 메뉴:
[ ] 새 게임 (New Game)
[ ] 계속 (Continue)
[ ] 설정 (Settings)
[ ] 종료 (Quit)

게임 메뉴:
[ ] Game Wars 1
[ ] Game Wars 2
[ ] 난이도 (Difficulty)
[ ] 쉬움 (Easy)
[ ] 보통 (Normal)
[ ] 어려움 (Hard)

게임 진행:
[ ] 공격 (Attack)
[ ] 방어 (Defense)
[ ] 이동 (Move)
[ ] 기술 (Skill)
[ ] 아이템 (Item)
[ ] 저장 (Save)
[ ] 로드 (Load)
[ ] 포기 (Abandon)
```

**특징**: 
- 짧은 텍스트 (3-10글자)
- 게임 진행에 필수
- 빈도가 높음

**당신의 작업**:
1. `data/game_wars_found_texts.csv`에서 Priority 1 항목 식별
2. 번역 입력 (Google Sheets 또는 CSV)
3. 번역 검수

### Priority 2: 스토리/대사 텍스트 (0%)

캐릭터 대사 및 게임 스토리:

```
예시:
- "전투를 시작합니다"
- "아군 유닛이 파괴되었습니다"
- "보스를 격파했습니다"
- "다음 미션으로 진행합니다"
```

**특징**:
- 중간 길이 텍스트 (10-100글자)
- 게임 스토리 이해에 중요
- 문맥 이해 필요

**당신의 작업**:
1. 게임플레이를 통해 문맥 파악
2. 자연스러운 한글 표현 번역
3. 게임의 톤앤매너 유지

### Priority 3: 기타 텍스트 (0%)

아이템 설명, 스테이터스, 등:

```
예시:
- 아이템 설명 (장중한 문체)
- 유닛 설명 (상세 정보)
- 기술 설명 (게임 용어 사용)
```

---

## 번역 스타일 가이드

### 기본 원칙

1. **자연스러움**
   - 어색한 직역 피하기
   - 한국식 게임 표현 사용
   
   ❌ "히트 포인트 감소" → ✓ "체력 감소"
   ❌ "마법점 사용" → ✓ "마나 소비"

2. **일관성**
   - 같은 단어는 항상 같게
   - 용어집 참고
   
   게임 전반에서:
   - HP = 체력
   - MP = 마나
   - Skill = 기술/스킬
   - Damage = 데미지

3. **길이 최소화** (옵션)
   - 할당 공간 내 맞추기
   - 긴 번역은 주의
   
   예: "공격력" (3글자) > "공격력 증가" (5글자)

4. **게임의 톤앤매너**
   - 전술/전략 게임의 정중한 표현
   - 게임 배경에 맞는 용어
   
   ✓ "유닛 전개"
   ✗ "캐릭터 배치"

### 용어집 (Glossary)

**군사/전략 용어**:
```
Unit = 유닛
Squad = 분대
Army = 군대
Battle = 전투
Attack = 공격
Defense = 방어
HP (Hit Points) = 체력
MP (Magic Points) = 마나
Experience = 경험치
Level Up = 레벨 업
```

**게임 시스템**:
```
Save = 저장
Load = 로드
New Game = 새 게임
Continue = 계속
Difficulty = 난이도
Settings = 설정
```

**상태 효과**:
```
Poison = 독
Stun = 기절
Sleep = 수면
Paralysis = 마비
Burn = 화상
```

---

## 번역 작업 프로세스

### 1단계: 번역 항목 선택

```bash
# 미번역 항목 확인
python tools/list_untranslated.py

# 특정 Priority 항목만 보기
python tools/list_untranslated.py --priority 2

# 특정 범위의 텍스트 보기
python tools/list_untranslated.py --start 0x000000 --end 0x100000
```

### 2단계: 번역 입력

**방법 A: CSV 파일 직접 수정**

1. `data/translation_for_import.csv` 열기
2. 누락된 `korean` 필드 입력
3. 파일 저장

**방법 B: Google Sheets (협업)**

1. Google Sheets 링크 접속
2. 번역 입력
3. 상태를 "Done"으로 표시
4. 정기적으로 CSV로 다운로드

### 3단계: 번역 검수

```bash
# 번역 데이터 검증
python tools/validate_translations.py

# 길이 검사
python tools/check_translation_lengths.py
```

### 4단계: ROM 재빌드

```bash
# 텍스트 삽입
python tools/execute_phase5_4.py

# ROM 최종화
python tools/execute_phase5_5.py

# 결과 확인
python tools/phase6_basic_test.py
```

---

## 번역 팁 및 주의사항

### 일반적인 실수 피하기

❌ **직역**
- "나는 전투를 시작한다" → ✓ "전투를 시작합니다"

❌ **과도한 길이**
- "이 유닛은 매우 강력한 공격력을 가지고 있습니다" 
- ✓ "강력한 공격력" (할당 공간이 제한적)

❌ **불일관한 용어**
- "체력" vs "생명력" vs "HP"
- ✓ 게임 전체에서 같은 용어 사용

### 문제 해결

**Q: 텍스트 길이가 할당 공간을 초과합니다**

A: 다음 중 하나를 선택:
1. 더 짧은 표현 찾기
2. 약자 사용 ("공격력" 대신 "공격")
3. Skip (다음 번역 진행)

**Q: 문맥을 모르겠습니다**

A:
1. 게임 화면에서 같은 부근의 다른 텍스트 참고
2. PHASE 6 테스트 결과 확인
3. 기존 번역 (797개) 참고

**Q: 번역 선택지가 여러 개입니다**

A: 
1. 게임의 톤앤매너 유지
2. 기존 번역과 일관성 확인
3. 가장 자연스러운 표현 선택

---

## 번역 속도 및 일정

### 목표 속도

```
Priority 1 (UI): 500개/주 목표
  - 짧고 반복적
  - 기존 797개 기준으로 계산

Priority 2 (스토리): 300개/주 목표
  - 길이가 다양함
  - 문맥 이해 필요

Priority 3 (기타): 200개/주 목표
  - 길이 및 복잡도 높음
```

### 일정 계획

```
현재: 2026-05-12
1주차: Priority 1 완료 (12,242개)
2주차: Priority 2 진행 (8,300개 중 일부)
3주차 이후: Priority 2 & 3 지속
```

**예상 완료**: 2026-06-09 (4주)

---

## 번역 후 다음 단계

### 1. 번역 데이터 통합

```bash
# 새 번역 확인
python tools/validate_translations.py

# 번역 기록 저장
git add data/translation_*.csv
git commit -m "PHASE 4: Update translations (+XXX items)"
```

### 2. ROM 재빌드

```bash
# 텍스트 삽입 실행
python tools/execute_phase5_4.py

# 최종화
python tools/execute_phase5_5.py

# 검증
python tools/phase6_basic_test.py
```

### 3. PHASE 6 테스트 재실행

```bash
# 에뮬레이터에서 새 ROM 로드
output/game_wars_korean_[version].gba

# 새로운 번역이 정상 표시되는지 확인
```

### 4. 진행 상황 업데이트

```bash
# plan.md 업데이트
# 진행률 기록
# 문제 사항 기록
```

---

## 리소스

### 파일 위치
- **번역 입력**: `data/translation_for_import.csv`
- **원본 텍스트**: `data/game_wars_found_texts.csv`
- **생성 도구**: `tools/execute_phase5_4.py`
- **검증 도구**: `tools/test_text_insertion.py`

### 기존 번역 참고
- **샘플 번역**: `data/translation_priority1.csv`
- **기술 문서**: `docs/PHASE5_COMPLETION_REPORT.md`

### 기술 지원
- **자동화 검증**: `tools/phase6_basic_test.py` 실행
- **디버깅**: 도구 스크립트 내 오류 메시지 확인
- **롤백**: `original/Game Boy Wars Advance 1+2 (Japan)_backup.gba`

---

## 체크리스트

번역 시작 전:
- [ ] Google Sheets 액세스 확인 (또는 CSV 편집)
- [ ] 용어집 검토
- [ ] 완료된 797개 번역 검토 (톤앤매너 이해)
- [ ] 게임 플레이 경험 (선택사항)

번역 진행 중:
- [ ] 매일 진행 상황 기록
- [ ] 주 1회 번역 검증
- [ ] 모르는 단어/표현 기록

완료 후:
- [ ] 전체 번역 재검수
- [ ] ROM 재빌드
- [ ] PHASE 6 재테스트

---

**작성**: 2026-05-12  
**담당**: 번역팀 (협업 진행)  
**최신 업데이트**: 2026-05-12
