# GBA 한글화 프로젝트 - 종합 연구 자료

## 1. 프로젝트 개요

Game Boy Advance(GBA) 게임 "Game Wars" 1+2 일본어판의 전체 한글화 프로젝트입니다.
이 문서는 WebSearch를 통해 수집한 모든 정보를 통합 정리한 자료입니다.

### 참조 문서
- `claude_research.md`: 커뮤니티 정보 및 리소스
- `codex_research.md`: 기술 도구 및 개발 방법론
- `gemini_research.md`: 종합 가이드 및 체크리스트

## [2026-06-07] Low-address UI `未設定` 문자열

- `0x005A3768`의 `未設定`은 `SAFE_MIN_ADDR=0x800000` 아래라 일반 CSV import pass에서
  자동 덮어쓰지 않는다. `data/game_wars_found_texts.csv`에는 6바이트/3글자 행으로 잡히지만,
  `translation_comprehensive.csv`에는 placeholder `미상`으로 남아 있었다.
- 주변 `0x5A375F`에는 이미 `코멘트` low-address 직접 패치가 있고, `0x5A3768` 역시 같은 UI 테이블
  문자열로 판단된다. `미설정`은 한글 3음절=예약코드 6바이트라 원 슬롯에 정확히 들어간다.
- low-address 범위 `0x5A3000:0x5A4000` 재스캔 기준 `未設定`은 제거됐고, 남은 후보
  `旧克署繊`, `灯助沫`, `劒屆撼`, `褂鉅鳰`은 주변 패턴상 깨진 데이터/추출 노이즈로 유지한다.

## [2026-06-07] Part 2 점령/상태창 현재 미노출 대사와 메뉴 라벨 재분류

- `0xA03C9C-0xA03CEC`의 점령/상태창 설명 슬롯은 current ROM에서 `네 보병이`,
  `점령 시작했어`, `상태창을 봐`로 정확히 들어간다. 그러나 EWRAM/IWRAM 후보 93개,
  day10 점령 후보 16개, city-defense/capture read-watch 후보 55개 모두 해당 주소 호출을
  재현하지 못했다. visible 점령 명령, 상태창 유닛명/지형명, DAY 2 점령 설명은 current ROM에서
  한글로 확인됐다. 호출 경로가 없다고 증명한 것은 아니므로, 현 시점에서는 실제 한글화 잔여가
  아닌 current evidence 기준 미노출 대사로 분류하고 이후 실제 화면에서 노출되면 별도 회귀 항목으로
  다시 연다.
- Part 2 행동/작전/보급 라벨 원본 타일은 output ROM 직접 렌더 기준 `공격`, `대기`, `부대`,
  `저장`, `설정`, `종료`, `보급`으로 들어가 있다. 중전차 day4의 작전 메뉴를 current ROM에서
  새로 열어도 visible 메뉴는 아이콘형 항목으로 보이며, 즉시 보이는 일본어/영어 문자열은 없다.
  따라서 `0xBE7F3C` 계열 raw 라벨이 특정 화면에 그대로 보이지 않는 현상은 새 패치 대상이 아니라
  메뉴 UI 형식 차이 또는 기존 savestate 캐시로 취급한다. 단, 이것은 콜드부트 fresh-run 전체
  커버리지가 아니므로 이후 실제 진행에서 행동/작전/보급 메뉴에 visible 일본어/영어 라벨이 보이면
  별도 그래픽 경로로 다시 추적한다.

## [2026-06-07] Part 1 full unit info `SPEC` 압축 OBJ 원본

- fresh-run full 정보창의 상단 `SPEC`는 OAM entry 27, x=4 y=0, shape=horizontal size=1,
  OBJ tile 537, palette 6으로 표시된다.
- 화면 VRAM의 OBJ tile 537~540(`SPEC` 32x8)은 current ROM raw에는 직접 존재하지 않고, LZ77 블록
  `0xBC7C00` 해제 결과 offset `0x0`/tile 0~3과 일치한다. 블록 크기는 해제 2624B, 원본 occupied
  1366B이며 패치 후 decoder consumed는 1309B다. 빌드는 남은 57B를 0으로 채워 원래 영역 안에 유지한다.
- compact/full 정보창의 `WEAPON` BG 라벨은 별도 LZ77 5개 변형
  `0x4310D4`, `0x92F0F4`, `0x967D7C`, `0x9A0620`, `0x9D8EC4`의 decompressed offset `0x220`
  48x8 payload다.

---

## 2. Game Boy Advance 플랫폼 이해

### 하드웨어 사양
- **CPU**: ARM7TDMI (16.78 MHz)
- **ROM**: 최대 32MB
- **메모리**: WRAM(32KB), VRAM(96KB), SRAM(32KB)
- **디스플레이**: 240×160 픽셀, 32,768색

### 텍스트 저장 공간의 제약
GBA의 가장 큰 제약은 ROM 크기입니다:
- 원본 롬 크기가 32MB를 초과할 수 없음
- 한글 폰트 데이터가 상당한 공간 차지
- 텍스트 길이 증가로 인한 포인터 재배치 필요
- **결론**: 효율적인 인코딩과 압축 필수

---

## 3. GBA 한글화 핵심 기술

### 3.1 텍스트 추출 및 분석

#### .tbl (Text Table) 파일 이해
`.tbl` 파일은 ROM의 바이너리 텍스트를 읽을 수 있는 형식으로 변환합니다.

**파일 형식:**
```
# 주석
00=A
01=B
7C=ㄱ
7D=ㄴ
...
```

**생성 방법:**
1. Hex 스캔으로 게임의 문자 위치 파악
2. RSEARCH 또는 Monkey-Moore 도구로 패턴 추출
3. 수동으로 .tbl 파일 작성
4. Hex 편집기(WindHex, HxD)에서 검증

#### 텍스트 추출 도구
| 도구 | 용도 | 난도 |
|-----|-----|-----|
| RSEARCH | 상대적 검색을 통한 테이블 자동 생성 | 중 |
| Monkey-Moore | 텍스트 패턴 분석 | 중 |
| WindHex | TBL 로드 및 시각화 | 하 |
| VisualBoyAdvance | 메모리 디버깅 | 중 |

### 3.2 Hex 편집기 및 도구

#### 주요 Hex 편집기
- **HxD** (무료): ROM 해킹 표준 도구
- **HexManiacAdvance** (오픈소스): 포켓몬 GBA 최적화
- **Crystal Tile 2.5** (오픈소스): GBA/NDS 종합 편집
  - 폰트 편집 가능
  - 문자열 테이블 직접 편집
  - 스프라이트 추출

### 3.3 문자열 포인터 시스템

#### 포인터의 역할
GBA 게임의 텍스트는 ROM의 고정 위치가 아니라 **포인터**로 참조됩니다.

**포인터 구조:**
```
메인 메모리: "대사를 여기서 불러옴"
            ↑
            32비트 주소 (4바이트)
```

#### 포인터 업데이트의 필요성
- 원본: 영어 "Hello" (5 바이트)
- 번역: 한글 "안녕하세요" (10 바이트, EUC-KR 기준)
- 텍스트 길이 변화 → 전체 포인터 재배치 필요

#### 자동화 방법
```python
# 예: Python을 이용한 포인터 업데이트 자동화
def update_pointers(rom_data, new_text_positions):
    for address, new_pos in new_text_positions.items():
        # 32비트 리틀엔디안으로 변환
        pointer = new_pos.to_bytes(4, 'little')
        rom_data[address:address+4] = pointer
```

---

## 4. 한글 인코딩 선택 기준

### 인코딩 비교

| 인코딩 | 바이트 | 한글자 수 | 추천 상황 |
|------|------|---------|---------|
| EUC-KR | 2 (고정) | 8,836자 | 공간 제약 심할 때 |
| CP949 | 2 (고정) | 11,172자 | EUC-KR 부족할 때 |
| UTF-8 | 3 (가변) | 무제한 | 최신 프로젝트 |

### Game Wars에 권장하는 인코딩
**EUC-KR 권장 이유:**
- 고정 길이(2바이트): 포인터 계산이 간단
- 일반적 한글 2,350자 모두 포함
- 기존 GBA 한글화 프로젝트와 호환성

---

## 5. ROM 해킹 워크플로우

### Phase 1: 준비 단계 (1-2주)

**필요 도구:**
```bash
필수:
- VisualBoyAdvance M v2.1.4 (에뮬레이터)
- HxD (Hex 편집기)
- 원본 ROM 파일

권장:
- Crystal Tile 2.5 (GBA 종합 편집)
- Python 3.x (자동화 스크립트)
- Git (버전 관리)
```

**초기 작업:**
```
1. ROM 분석
   - 파일 크기 확인
   - 헤더 정보 읽기
   - 텍스트 위치 대략 파악

2. 게임 플레이
   - 에뮬레이터에서 모든 신 확인
   - 텍스트량 추정
   - UI 구조 파악
```

### Phase 2: 텍스트 추출 (2-4주)

```
1. 문자 위치 특정
   - Hex 에디터에서 문자 검색
   - 패턴 인식
   
2. .tbl 파일 생성
   - RSEARCH로 패턴 추출
   - 수동 검증 및 수정
   
3. 전체 텍스트 추출
   - ROM 스캔
   - 스프레드시트로 정렬 (주소, 원문, 컨텍스트)
```

### Phase 3: 번역 작업 (6-12개월)

```
1. 번역팀 구성
   - 게임 분야 경험자
   - 게임 톤앤매너 이해자
   - 기술적 피드백 담당자

2. 번역 진행
   - 게임 스토리 읽기
   - 컨텍스트 기반 번역
   - 용어 일관성 관리
   
3. 검수
   - 네이티브 한글 화자 검토
   - 게임 느낌 검증
```

### Phase 4: 기술적 삽입 (4-8주)

```
1. 자동화 빌드 시스템 구축
   - 번역 CSV → 바이너리 변환 스크립트
   - 포인터 업데이트 자동화
   - ROM 생성 자동화
   
2. 폰트 준비
   - 한글 폰트 글리프 추출/생성
   - 폰트 데이터 ROM에 삽입
   
3. 텍스트 삽입
   - 포인터 업데이트
   - 텍스트 바이너리 변환 후 삽입
```

**자동 빌드 스크립트 예시:**
```batch
@echo off
REM build.bat - Game Wars 한글 패치 자동화

python extract_text.py
python translate_insert.py
python update_pointers.py
python generate_rom.py output.gba

echo Build complete!
pause
```

### Phase 5: QA 및 테스트 (4-12주)

```
1. 에뮬레이터 검증
   - 전체 게임 플레이
   - 모든 대사 확인
   - 메뉴 동작 검증
   
2. 버그 추적
   - 텍스트 오버플로우
   - 포인터 오류
   - 인코딩 문제
   
3. 수정 및 재테스트
   - 버그 목록 우선순위 지정
   - 수정 후 재테스트
```

---

## 6. Game Wars 한글화 특수 고려사항

### 전략 게임의 특성
Game Wars는 턴 기반 전략 게임으로:
- **유닛 이름**: Unit, Magic, Item 문자열
- **대사량**: 중간 규모 (RPG보다 적음)
- **메뉴 복잡도**: 높음 (메뉴 포인터 많음)
- **UI 제약**: 턴 시스템, 상태창 등

### 예상 텍스트량
- 일본어 원문: 약 300-500KB (텍스트 기준)
- 한글 번역: 약 350-550KB (길이 변수)
- 추가 폰트 데이터: 100-200KB
- **최종 ROM**: 32MB 이내 가능

### 추천 진행 순서
1. **UI/메뉴 번역 우선** (게임플레이에 필수)
2. **스토리 모드 번역** (주 콘텐츠)
3. **추가 모드 번역** (서브 콘텐츠)
4. **세부 조정** (오류, 폰트 등)

---

## 7. 커뮤니티 리소스 및 도움

### 주요 커뮤니티

#### 한글 패치 커뮤니티
- **한글로게임** (https://www.hangulogame.com/)
  - GBA 한글 패치 리스트
  - 기존 한글화 예시
  - 패치 다운로드

#### 기술 지원
- **RomHacking.net** (https://www.romhacking.net/)
  - 도구 리포지토리
  - 튜토리얼
  - 포럼 (English)

- **GBAtemp Forum** (https://gbatemp.net/)
  - GBA 기술 지원
  - 에뮬레이터 정보
  - ROM 해킹 커뮤니티

#### 정보 데이터베이스
- **Data Crystal** (https://datacrystal.tcrf.net/)
  - 게임 구조 정보
  - 주소 매핑
  - 포인터 위치

- **나무위키** (게임보이 어드밴스)
  - 게임 기본 정보
  - 한글 패치 소식

#### 한글 커뮤니티
- **네이버 카페: 한글화하는 사람들**
  - 실시간 번역 진행 현황
  - 기술 질문 및 답변

- **DC Inside 갤러리**
  - 닌텐도 갤러리
  - 게임보이 갤러리
  - 한글 패치 정보 공유

---

## 8. 필수 도구 정리

### 무료 도구 (권장)

```
┌─ ROM 분석/편집
│  ├─ VisualBoyAdvance M (에뮬레이터+디버거)
│  ├─ HxD (Hex 편집기)
│  ├─ Crystal Tile 2.5 (GBA/NDS 편집)
│  └─ GBA Explorer (구조 탐색)
│
├─ 텍스트 추출/테이블
│  ├─ RSEARCH (상대적 검색)
│  ├─ Monkey-Moore (패턴 분석)
│  └─ WindHex (TBL 지원 Hex 편집)
│
├─ 자동화 스크립트
│  ├─ Python 3.x
│  ├─ Git (버전 관리)
│  └─ VS Code (편집기)
│
└─ 번역 관리 (선택)
   ├─ Google Sheets (협업)
   ├─ OmegaT (번역 메모리)
   └─ Memsource (고급 번역)
```

### 필수 기술 스택

```python
# ROM 분석 및 처리
import struct      # 바이너리 데이터
import json        # 설정 관리
from pathlib import Path

# 포인터 계산 예시
def read_pointer(rom, address):
    """ROM에서 포인터 읽기 (리틀엔디안)"""
    return struct.unpack('<I', rom[address:address+4])[0]

def write_pointer(rom, address, pointer):
    """ROM에 포인터 쓰기 (리틀엔디안)"""
    rom[address:address+4] = struct.pack('<I', pointer)
```

---

## 9. 단계별 체크리스트

### ✓ 준비 단계
- [ ] 원본 ROM 확보 (일본어판 1, 2)
- [ ] 에뮬레이터 설치 및 테스트
- [ ] 모든 도구 다운로드 및 설정
- [ ] GitHub 리포지토리 생성
- [ ] 커뮤니티 조사 및 연락

### ✓ 분석 단계
- [ ] 게임 전체 플레이
- [ ] ROM 구조 분석
- [ ] 텍스트 위치 매핑
- [ ] .tbl 파일 생성
- [ ] 전체 텍스트 추출 및 정렬

### ✓ 번역 단계
- [ ] 번역팀 모집
- [ ] UI/메뉴 번역 (우선)
- [ ] 메인 스토리 번역
- [ ] 추가 콘텐츠 번역
- [ ] 검수 및 수정

### ✓ 개발 단계
- [ ] 폰트 데이터 준비
- [ ] 자동 빌드 시스템 구축
- [ ] 텍스트 삽입 자동화
- [ ] 포인터 업데이트 자동화
- [ ] 기본 ROM 생성 및 테스트

### ✓ QA 단계
- [ ] 전체 게임 플레이
- [ ] 버그 추적 및 기록
- [ ] 우선순위별 수정
- [ ] 최종 검수
- [ ] 패치 배포

---

## 10. 트러블슈팅 가이드

### 문제: 포인터 오류로 게임 크래시
**원인**: 포인터 업데이트 누락 또는 오류  
**해결**:
```python
# 모든 포인터 검증
def validate_pointers(rom, pointer_list):
    for addr in pointer_list:
        ptr = read_pointer(rom, addr)
        if ptr >= len(rom):
            print(f"Invalid pointer at 0x{addr:X}: 0x{ptr:X}")
```

### 문제: 텍스트가 화면에 안 보임
**원인**: 포인터 오류, 인코딩 오류, 폰트 부족  
**해결**:
1. Hex 에디터에서 실제 데이터 확인
2. 인코딩 검증 (EUC-KR 확인)
3. 폰트 데이터 재확인

### 문제: ROM 체크섬 오류
**원인**: ROM 수정 후 체크섬 미업데이트  
**해결**:
```bash
# GBA ROM 헤더 체크섬 재계산
# 도구: Game Boy ROM Analyzer
# 또는 Python으로 직접 계산
```

---

## 11. 참고 자료 및 링크

### 기술 문서
- [RomHacking.net - How To Make Table Files](https://www.romhacking.net/documents/54/)
- [Text Table Format](https://datacrystal.tcrf.net/wiki/Text_Table)
- [Emulation General Wiki - ROM hacking resources](https://emulation.gametechwiki.com/index.php/ROM_hacking_resources)

### 도구
- [Crystal Tile 2.5](https://github.com/Crisp2013/CrystalTile25)
- [VisualBoyAdvance](https://www.visualboyadvance.org/)
- [HxD Hex Editor](https://mh-nexus.de/en/hxd/)

### 커뮤니티
- [한글로게임](https://www.hangulogame.com/lists/gba/)
- [RomHacking.net](https://www.romhacking.net/)
- [GBAtemp.net](https://gbatemp.net/)
- [Data Crystal](https://datacrystal.tcrf.net/)

---

## 12. 결론 및 조언

### 프로젝트 성공을 위한 핵심 요소

1. **체계적 준비**: 분석 → 설계 → 구현 순서 준수
2. **자동화**: 반복 작업은 스크립트로 자동화
3. **커뮤니티 활용**: 기존 프로젝트 참고, 도움 요청
4. **품질 관리**: QA는 마지막이 아니라 처음부터
5. **버전 관리**: Git으로 모든 변경 추적

### Game Wars 한글화 예상 타임라인

| 단계 | 기간 | 비고 |
|-----|-----|-----|
| 준비 & 분석 | 2-4주 | 도구 설정, ROM 구조 파악 |
| 텍스트 추출 | 2-4주 | .tbl 파일, 전체 스캔 |
| 번역 | 6-12개월 | 팀 규모에 따라 매우 변수 |
| 개발 & 삽입 | 4-8주 | 자동화 스크립트 개발 |
| QA & 수정 | 4-12주 | 철저한 테스트 필수 |

**총 예상 기간**: 7개월~18개월 (팀 규모 및 경험에 따라)

### 최종 조언
- **작게 시작하기**: Game Wars 1부터 시작
- **문서화**: 모든 과정을 기록하면 2편이 빨라짐
- **버전 공개**: 베타 버전부터 공개하여 피드백 받기
- **커뮤니티 공유**: 완성 후 커뮤니티와 공유 (다른 프로젝트 영감)

---

**마지막 업데이트**: 2026년 5월  
**정보 출처**: RomHacking.net, 한글로게임, 나무위키, 기타 커뮤니티

---

## 2026-05-23 RE 발견 — Welcome Dialog 시스템

### 핵심 주소
| 항목 | 주소 | 비고 |
|------|------|------|
| Dialog init 함수 entry | 0x8B12984 | 모든 dialog open 시 호출 |
| Dialog text ptr store | 0x8B1299C | `str r4, [r6, #0x20]` — text addr 저장 |
| Dialog hook point (init) | 0x8B129D4 | BL trampoline 삽입 위치 (str r0, [r6, #0x3c]) |
| Text loop body | 0x8B12758 | 매 글자 렌더 호출 |
| Text loop exit | 0x8B12798 | `pop {r4, r5, r6}` — hook B 위치 |
| Engine clear function | 0x8B175BA | dialog 영역 BG 데이터 clear (BL 0x8B10E34) |
| Engine ▼ marker tile | 0xA1B9 (tile 441 + palette 0xA) | BG0 tilemap row 2 col 23 default location |

### Code Cave
- 0x08A3CF14: hook 코드 권장 위치 (large free space ~798KB)
- 0x08A3D000+: data 영역
- 17MB ROM 빈 영역: 0xA3CF14 시작 가용

### Dialog 데이터 구조 (r4 base = 0x03000F80)
| 오프셋 | 의미 |
|--------|------|
| r4+0x20 | text pointer (engine stores addr-2) |
| r4+0x32 | char counter (1 byte) |
| r4+0x34 | h-position (advance 2 per char) |
| r4+0x2E | v-position (not advanced = single line) |
| r4+0x3C | misc state |

### SJIS → Font Slot 매핑 (Grid 카타카나)
**검증 공식**: `slot_addr = 0xB984D0 + (sjis_low - 0x41) * 0x10`

| SJIS | char | ROM offset |
|------|------|------|
| 0x8341 | ア | 0xB984D0 |
| 0x8343 | イ | 0xB984F0 |
| 0x8345 | ウ | 0xB98510 |
| 0x8347 | エ | 0xB98530 |
| 0x8349 | オ | 0xB98550 |

- **슬롯 stride**: 0x10 bytes per SJIS code increment
- **슬롯 크기**: 32 bytes (= 1 8x8 4bpp tile) — 인접 슬롯과 16 bytes overlap
- **글리프 데이터**: 4-row katakana (bottom half of tile)
- **dakuten/small variants**: 사이 슬롯 (+0x10) 위치, overlap memory

### Blitter 정보 (Font Copy to VRAM)
- IWRAM blitter entry: 0x03006744 (Thumb)
- 호출자 LR: 0x08B1BF0D (welcome dialog text 렌더)
- 인자: r6 = VRAM dest, r7 = ROM source
- 호출당 32 bytes (= 1 tile) 복사
- Welcome dialog: 16 katakana = 16 호출
- Name input grid: ~165 호출 (50 katakana + 10 digits + cursor/UI 등)

### Hook B 패턴 (Single Line 한글)
```
HOOK_B at 0x08A3D000:
- 인자: flag in EWRAM 0x0203FFF0 (set by HOOK_A)
- 동작:
  1. flag != 0 검사
  2. tilemap row 1 (col 7) 22 entries 복사 (= 내 line 1 top tile refs)
  3. tilemap row 2 (col 7) 22 entries 복사 (= 내 line 1 bot + marker)
  4. glyph data (704 halfwords) 복사 to VRAM 0x06002780+
- 마지막에 원본 ABI 복원: pop {r4, r5, r6}; pop {r0}; bx r0
```

### Tilemap Marker (▼)
- 시스템 ▼ tile entry: 0xA1B9 (tile 441 + palette 0xA)
- 원래 위치: BG0 tilemap row 2 col 23 (engine이 typewriter 끝 자리에 자동 배치)
- 동적 정렬: hook B에서 row 2의 `marker_cell` 위치에 0xA1B9 직접 배치하면 원하는 위치에 ▼ 표시 (engine 기본 위치 무관)

---

## SJIS Lookup Table (2026-05-23 검증)

### 위치
- **SJIS_TABLE_ADDR**: `0x08BE717A` (ROM 파일 오프셋 0xBE717A)
- 각 엔트리: 2 byte big-endian SJIS 코드

### 엔트리 (앞부분)
| idx | sjis | char |
|-----|------|------|
| 0-8 | 0x8250..0x8258 | 全角숫자 １-９ |
| 9   | 0x8341 | ア |
| 10  | 0x8343 | イ |
| 11  | 0x8345 | ウ |
| 12  | 0x8347 | エ |
| 13  | 0x8349 | オ |
| 14  | 0x834A | カ |
| 15-18 | 0x834C..0x8352 | キ ク ケ コ |
| 19-23 | 0x8354..0x835C | サ シ ス セ ソ |
| 24  | 0x835E | タ |
| 25  | 0x8360 | チ |
| **26** | **0x8363** | ツ (표준 SJIS는 0x8362 — 게임은 0x8363 사용) |
| **27** | **0x8365** | テ (표준 0x8364) |
| **28** | **0x8367** | ト (표준 0x8366) |
| 29-33 | 0x8369..0x836D | ナ ニ ヌ ネ ノ |
| 34  | 0x836E | ハ |
| 35-38 | 0x8371,0x8374,0x8377,0x837A | ヒ フ ヘ ホ (변종 SJIS) |
| 39-40 | 0x0000 | NULL |
| 41+ | 0x837D... | マ 이후 |

### 슬롯 변환 (cell_to_slots.py)
```python
idx = (table lookup of sjis_code)
rel_idx = idx - 9
page = rel_idx // 16; chip = rel_idx % 16
top_extra = 128 + (page+5)*32 + 3 + chip   # 그리드 셀 상단 8x8
top       = 128 + page*32 + chip            # 다이얼로그 상단
bottom    = 128 + page*32 + 16 + chip       # 다이얼로그 하단
bot_extra = 128 + (page+5)*32 + 19 + chip   # 그리드 셀 하단 8x8

rom_addr = 0x08B974D0 + slot * 32
```

### 검증된 슬롯 (idx 9-18 = A-J on grid)
| idx | sjis | top_extra | bot_extra | grid display |
|-----|------|-----------|-----------|--------------|
| 9 | 0x8341 ア | 291 | 307 | A |
| 10 | 0x8343 イ | 292 | 308 | B |
| 11 | 0x8345 ウ | 293 | 309 | C |
| 12 | 0x8347 エ | 294 | 310 | D |
| 13 | 0x8349 オ | 295 | 311 | E |
| 14 | 0x834A カ | 296 | 312 | F |
| 15 | 0x834C キ | 297 | 313 | G |
| 16 | 0x834E ク | 298 | 314 | H |
| 17 | 0x8350 ケ | 299 | 315 | I |
| 18 | 0x8352 コ | 300 | 316 | J |

### 핵심 교훈
- 표준 SJIS 코드로 cell_slots() 호출 시 일부 (ツ/テ/ト/ヂ/ヅ/...)는 다른 페이지로 점프 → 화면 깨짐
- **반드시 게임의 lookup table을 직접 읽어서 SJIS 코드 추출** 후 cell_slots에 전달


---

## Name Input Grid Tile 슬롯 (2026-05-23 검증)

### 그리드 두 영역 분리

GBA 모든 4 BG 레이어 사용 (BG0 cb=0 sb=12 pri=0, BG1 cb=0 sb=30, BG2 cb=2 sb=13 pri=0, BG3 cb=2 sb=31).

**좌측 메인 그리드** (4×5 카타카나 셀):
- 슬롯 128 + N (top half) + 144 + N (bottom half) for cell N
- cell_to_slots의 `top` + `bottom` 슬롯 사용
- 각 셀 = 8×16 픽셀 = 두 타일 stacked
- ROM tile data: 0x08B974D0 + slot * 32

**우측 작은 패널** (1-9 + ヤユヨ + ワヲン + 기호):
- 슬롯 (page+5)*32+3+chip (top_extra) + (page+5)*32+19+chip (bot_extra)
- cell_to_slots의 `top_extra` + `bot_extra` 슬롯
- 작은 8×8 셀 (one tile each)

### 매핑 검증 절차
이분탐색으로 발견:
1. 슬롯 0-287에 'O' marker → 좌측 그리드 전체 'O' → 좌측은 0-287
2. 슬롯 0-71에 alphabet → 좌측 안 변함 → 좌측은 71+
3. 슬롯 128-191에 'X' → 좌측 32 셀 모두 'X' → 좌측 메인 = 128-191

### 셀 번호 (idx) → 슬롯 매핑 (page 0 검증)
- cell N (idx 9+N): top=128+N, bottom=144+N
- 예: ア (N=0): top=128, bottom=144
- 예: タ (N=15): top=143, bottom=159
- page 1+ (idx 25+): top=160+chip, bottom=176+chip (chip 0-15)

---

## NAME 입력 동작 (2026-05-23 검증)

### 입력 흐름
1. 사용자가 그리드 셀에 커서 이동 (DPad)
2. A 버튼 → 해당 셀의 카타카나 SJIS 코드 (예: ア=0x8341)가 name buffer에 추가
3. NAME 박스에 입력된 카타카나가 표시됨
4. 같은 다이얼로그 폰트 슬롯 사용 → 우리가 카타카나 슬롯에 알파벳 글리프 주입했으므로 NAME 박스도 알파벳 표시

### 즉, 자동 변환 (Universal Substitution)
- name buffer 내부 데이터: SJIS katakana 코드 (0x8341 등)
- 표시: 슬롯 128+144 등에서 글리프 로드
- 우리가 슬롯 글리프를 알파벳으로 변경 → 모든 곳에서 알파벳 표시
- 다음 화면 (스토리/UI)에서도 같은 슬롯 → 자동 알파벳 표시

### 부작용
- 게임 내 모든 카타카나 표시가 알파벳으로 변경
- 전체 한글화 시에는 무관 (어차피 카타카나 글리프를 한글로 교체)
- 일본판 그대로 사용 시에는 다른 텍스트에서 알파벳이 보일 수 있음

---

## NAME Input 그리드 nav 도구 한계 (2026-05-23 iter 4)

mgbah harness의 단순 key 입력으로는 OK 버튼까지 정확히 도달 어려움. 시도된 nav 패턴들:

| nav | 결과 | 비고 |
|-----|------|------|
| keys 4 (SELECT) | 효과 없음 | 잘못 사용 — DOWN으로 오해 |
| keys 8 (START) | 그리드 reset | NAME 박스 비움, 초기 상태 |
| keys 256 (R) | 글자 삭제 | backspace 효과 |
| keys 512 (L) | 글자 삭제 | backspace 효과 (R와 동일?) |
| 9 DOWN + 8 RIGHT | cursor on "ヲ" | 그리드 cursor 이동 정확 |
| 8 DOWN + 10 RIGHT | 그리드 reset | 시퀀스가 길어지면 input 일부 무효? |

### EWRAM/IWRAM 차이
- EWRAM 0x02000000 첫 40KB: cursor 위치와 무관 (좌표 저장 안 됨)
- IWRAM 0x03000000: ~36 byte가 cursor 이동마다 변경 (시각 효과 관련 가능성)

### 결론 — mGBA Lua API 필요
mgbah CLI는 큰 RE 비용. mGBA Lua API로 emu:setKeys + 좌표 watchpoint 결합 권장.

### 그러나 핵심 기능은 검증됨
- 그리드 알파벳 표시 ✓
- 이름 입력 시 알파벳 NAME 박스 표시 ✓
- 동일 폰트 슬롯 공유 → 다음 화면도 자동 정상 (보장)

---

## [2026-05-25] hook 일반화 RE — codex+gemini 자문 + 글리프 경로 측정

### 외부 자문 수렴 (codex 0.132 + gemini 0.35, `temp/{codex,gemini}_hook_opinion.md`)
둘 다 **"범위 기반 글리프 fetch hook + 비압축 글리프 직행"** 아키텍처가 정석이라 합의.
- LZ77 우회(비압축 직행) — SWI 0x11 오버헤드/프레임드랍 회피.
- hook 위치: SJIS→글리프포인터 계산 직후, **r7만 한글 글리프 주소로 교체** 후 **기존 팔레트
  리맵/copy 경로로 합류**(LZ77만 스킵). gemini 경고: 리맵 건너뛰면 색/그림자 깨져 검은 네모.
- SJIS 코드는 게임이 일반 전각으로 취급하는 **안 쓰는 한자 대역** 선택 → 커서폭 보정 공짜.
- 렌더 컨텍스트 분리 가능성 높음 → **최소 2 hook**(대화 / UI). 판별: 글리프 fetch PC가 화면군별 동일한지.
- gemini 대안(무-ASM): 안 쓰는 한자의 ROM 글리프포인터 테이블 엔트리를 LZ77 압축 한글 글리프로
  repoint. 안전하나 SWI 오버헤드.

### 측정으로 확정한 사실 (mgbah BP/watch + 헤드리스 네비)
- **합성 키 입력이 작동한다.** (CLAUDE.md "키 안 먹힘"은 옛 정보) → `keys 8/1` + `frames`로
  타이틀→이름입력→대화까지 헤드리스 진행 가능. RE의 결정적 enabler.
- **이름입력 그리드 폰트 = FONT_BASE(0x08B974D0) 비압축**, IWRAM copy 루틴 `0x03006744`가
  `r1=FONT_BASE, r7=소스(FONT_BASE+off), r6=VRAM dst`로 복사. **단일 ROM 호출자 lr=0x08B1BF0D**
  (172히트 중 167). 소스 범위 FONT_BASE~0x08BA3150(약 48KB). → UI/메뉴/그리드 한글은 이 경로
  (FONT_BASE 직접 주입, build_grid 그리드와 동일)로 가능.
- **LZ77 thunk 0x08B7A878**: 부팅 그래픽 압축해제(소스 0x08C2xxxx)에 5회. 폰트 글리프 per-char 아님.
- **대화 타이프라이터는 0x03006744를 per-char로 타지 않는다.** (이름입력 직후 hajimemashite
  대화 진행 시 복사 0히트) → 대화는 컨텍스트 진입 시 폰트 VRAM 프리로드 후 **타일맵 인덱스**로
  렌더하거나 별도 글리프 경로 사용. **이것이 build_grid가 대화에만 hook을 쓴 이유.**

### 남은 측정 (다음)
- 대화 글리프 render 경로 정확 지점: hajimemashite 대화(이름입력 OK 후) 진입 시 BG 타일맵 VRAM
  write PC + 글리프 소스 watch. → 그 지점이 대화용 hook(또는 FONT_BASE 프리로드 주입+타일인덱스) 위치.
- 게임 흐름: 타이틀 →(START)→ … → 이름입력 그리드 →(OK)→ hajimemashite 대화.

## [2026-05-25] 대화 글리프 경로 확정 — UI와 공통 chokepoint, 단 매핑은 별개

헤드리스 네비(타이틀→이름입력→hajimemashite 대화)로 대화 렌더 중 측정.

### 글리프 copy chokepoint (UI+대화 공통)
- 대화 텍스트 글리프도 **IWRAM copy 0x03006744**로 복사됨. 호출 체인:
  veneer `0x08B1BF08 bl 0x08B7BD1C` → ARM/Thumb 인터워크 thunk → IWRAM 0x03006744 (lr=0x08B1BF0D).
- copy 인자: `r1=FONT_BASE(0x08B974D0)`, `r7=소스=FONT_BASE+offset`, `r6=VRAM dst`. 대화는 dst가
  대화창 영역 0x06002040~0x060022C0, 문자당 0x40(2타일=8x16). 한 대화 전이에 29 copy.
- **대화 글리프 소스가 전부 FONT_BASE(비압축)** → 그리드/메뉴와 동일 폰트·동일 copy 경로.
- 텍스트 파서 0x08B11E48, SJIS 2바이트 분기 0x08B1215A(r1=ROM 텍스트 포인터, 2바이트씩 전진),
  텍스트 디코드 루프 0x08B1BF0A(r0=ROM 텍스트, r5=EWRAM 버퍼), 타이프라이터 0x08B0FFF0.

### 핵심 함정: 대화 SJIS→오프셋 매핑 ≠ 0xBE717A 그리드 테이블
- `cell_to_slots`(0xBE717A 기반) 오프셋이 캡처한 대화 copy 오프셋과 **불일치**.
- 대화 히라가나(ま,ち,が,い,な,し,ら 등)는 **0xBE717A 테이블에 없음**.
- → 0xBE717A는 그리드/메뉴 전용. **대화 폰트는 별도의 SJIS→오프셋 매핑**을 사용(미도출).

### FONT_BASE 폰트 영역 용량
- 0x08B974D0 ~ 약 0x08BAE190 (~91KB), 8x16 글리프 셀 **~1431개** → 1028 음절 수용 가능.

### 결론·권장 접근
- 대화+UI가 **단일 copy chokepoint(0x03006744 / veneer 0x08B1BF08, 호출자 0x08B1BF0D)** 를
  공유하므로, codex 권장대로 **그 지점에서 copy 소스(r7)를 한글 글리프 영역으로 리다이렉트**하는
  hook 1개가 가장 견고(대화 SJIS→오프셋 매핑 역산 불필요).
- 또는 대화 매핑을 역산해 FONT_BASE 한자 셀을 한글로 덮는 무-hook 방식(매핑 도출 + 충돌 분석 필요).
- 합성 키 입력 작동 → 헤드리스 네비로 인게임 검증 가능(welcome/hajimemashite 도달 확인).

## [2026-05-25] codex+gemini 엄격 리뷰 + per-char 확정 + 대화 매핑 데이터

### codex+gemini 리뷰 수렴 (temp/{codex_review2,gemini_review}.md)
- **per-char vs 프리로드 미확정 → 측정 필요** (둘 다 지적). ✅ 아래에서 per-char 확정.
- **🔴 복사 지점(0x03006744)은 너무 늦다**: SJIS 코드가 이미 오프셋으로 소실, r7만으론 한글 판정 불가
  (UI 아이콘/숫자 오프셋과 충돌 위험). → **상류(SJIS 코드 살아있는 곳)에서 한글 감지 후 오프셋
  재계산**해 copy로 넘기는 게 견고. 0x03006744는 관측/최종 redirect용.
- 팔레트 리맵: 한글 글리프는 **원본 JP 글리프와 동일 픽셀 인덱스 집합**(4bpp, 0x40/char, 투명/획
  index 동일) 사용 필수. JP 글리프 히스토그램 떠서 맞출 것.
- 1431셀 vs 0xF00000: 별도영역 redirect면 셀수 무관. 진짜 관건은 **오프셋 인덱싱 한계(16bit
  마스크/래핑 여부)**. 0xF00000=파일오프셋 → 런타임 0x08F00000 (혼동 금지). 1028 glyph≈64KB.
- **풀게임 커버 미보장**: 전투 숫자·맵 지명은 별도 DMA/OBJ 가능. AW1/AW2 각각 표본 + 전 화면
  0x03006744 BP + VRAM write watch 전수 확인 필요.

### per-char 확정 (bp_tw2.log 인터리브 분석, 새 측정 불필요)
- 파서 0x08B1215A 히트(r1/r2=ROM 텍스트 포인터, 2바이트씩 전진) 직후 copy 0x03006744 발생.
- **같은 글자 재등장 시 같은 offset을 새 VRAM dst로 재복사** → 캐시/프리로드 아닌 **per-char 렌더 확정**.
  예: い 0x82A2→off 0x20 (dst 0x...2100, 0x...2180 두 번), ま 0x82DC→0x5C0 (두 번), し→0x160 (두 번).

### 대화 SJIS→FONT_BASE offset 매핑 (실측 14점, 그리드 0xBE717A와 별개)
| 글자 SJIS | off | idx(off/0x20) | 글자 SJIS | off | idx |
|---|---|---|---|---|---|
| い 0x82A2 | 0x20 | 1 | ま 0x82DC | 0x5C0 | 46 |
| か 0x82A9 | 0xA0 | 5 | め 0x82DF | 0x820 | 65 |
| し 0x82B5 | 0x160 | 11 | ら 0x82E7 | 0x8C0 | 70 |
| ち 0x82BF | 0x400 | 32 | が 0x82AA | 0xC00 | 96 |
| て 0x82C4 | 0x440 | 34 | じ 0x82B6 | 0xCC0 | 102 |
| な 0x82C8 | 0x480 | 36 | 　0x8140 | 0xBE0 | 95 |
| は 0x82CD | 0x520 | 41 | ？0x8148 | 0x19C0 | 206 |
- 무성 가나(い1,か5,し11)는 고주온 순서 유사, 탁음(が96,じ102)·기호는 별도 블록 → SJIS→인덱스
  변환 테이블/공식 존재. (역산 미완)

### 파서 구조 (0x08B1215A 디스어셈블)
```
0x08B1215A: ldrb r0,[r2]      ; r0=현재 문자 리드바이트 (r2=텍스트 포인터)
0x08B1215C: cmp  r0,#0x77
0x08B1215E: bls  0x08B12162   ; <=0x77: 단일바이트 점프테이블(@0x08B1216C)
0x08B12160: b    0x08B12634   ; >0x77(SJIS 리드 0x81+): 함수 return(2바이트는 caller가 처리)
```
→ 0x08B1215A는 파서. **SJIS→offset 계산+글리프 복사는 이 파서의 caller**(2바이트 리턴 후 copy)에 있음.
  그 caller(offset 계산 지점)가 두 리뷰가 지목한 **최적 hook 위치**.

### 다음 측정 (continuation)
- 0x08B1215A의 caller(lr) → 거기서 SJIS 코드→offset 계산(테이블 lookup ldr 또는 산술) 지점 특정.
  그게 hook 지점(한글 예약코드면 offset을 한글영역으로 재계산). 테이블이면 데이터-only 확장도 가능.
- 한글 글리프 포맷: 원본 가나 글리프(예 FONT_BASE+0x20) 덤프 → 픽셀 index 집합 확인 후 맞춤.
- 전 화면(AW1/AW2 캠페인·전투·메뉴) 0x03006744 BP 전수 확인.

## [2026-05-25] 🔑 대화 텍스트 렌더 파이프라인 완전 RE (매핑 메커니즘 + 테이블 + ROM 소스)

PoC(FONT_BASE 주입으로 대화 한글 렌더) 성공 후, SJIS→glyph 변환 전체를 디스어셈블로 해독.
2차 codex+gemini 리뷰 반영. **이것으로 풀게임 대화 한글화 구현이 가능해짐.**

### 렌더 호출 체인 (대화)
```
렌더러 루프 0x08B12758: r0=[r4+0x20](텍스트 char 포인터), r1=[r4+0x34], r2=[r4+0x2e]
  → bl 0x08B1BEFC (veneer)
veneer 0x08B1BEFC: r1/r2 16비트화, r3=리터럴[0x08B1BF10]=0x030065E1
  → bl 0x08B7BD1C (= `bx r3`)
  → IWRAM 변환 루틴 0x030065E0  (★ROM 소스 = 0x08EFE788, 부팅 시 IWRAM 복사)
     : SJIS 코드 → glyph index + width 계산, 그 후
  → IWRAM 타일복사 0x03006744 : r7=FONT_BASE+idx*0x20 → VRAM(r6), 32바이트(16 halfword)
     픽셀별 팔레트 리맵(nibble>임계 시 오프셋 가산) 적용.
```

### 변환 루틴 0x030065E0 (ROM 0x08EFE788) — SJIS→index+width
- `r3 = (lead<<8)|trail` = SJIS 코드. `r7 = byte-swap(SJIS)` (LE).
- 중간 index `r1 = ((SJIS-0x8140) & ~7)*2 + (SJIS&7)`. (리터럴 -0x8140=0xFFFF7EC0, mask 0xFFF8)
- 기본 width `ip = 8`.
- **SJIS 범위별 분기** (base ptr 테이블 0x08B80270):
  - ≤0x823F (기호/ASCII): base=[0x08B80270+0]=0x08B8027C
  - ≤0x833F (히라가나): base=[+4]=0x08B8057C, index -= 0x200
  - ≤0x8397 (가타카나): base=[+8]=0x08B8087C, index -= 0x200 한 번 더
  - >0x8397 (**한자**): **테이블 검색** 0x08B80B7C (r7=byteswap SJIS로 선형 탐색),
    width `ip=1` 분기(테이블에서 폭 결정 추정).
- 즉 가나/기호는 **선형 공식**, 한자는 **테이블 lookup**.

### 한자 테이블 0x08B80B7C
- **536 엔트리 × 6바이트** = `[SJIS_LE(2), top_tile_idx(2), bot_tile_idx(2)]`. 끝 0x08B8180C.
- 글리프: top 타일 = FONT_BASE(0x08B974D0) + top_idx*0x20, bot = FONT_BASE + bot_idx*0x20.
  → **top/bot 타일이 별도 인덱스**(연속 엔트리는 idx 연속: 0x540/0x550, 0x541/0x551...).
- 게임이 쓰는 한자 536자만 등록됨(< 1028 음절).

### 핵심 주소 요약 (재현/패치용)
| 항목 | 주소 |
|---|---|
| 렌더러 루프(char ptr→veneer) | 0x08B12758 |
| veneer | 0x08B1BEFC (리터럴 0x08B1BF10=0x030065E1) |
| 변환 루틴 IWRAM / **ROM 소스** | 0x030065E0 / **0x08EFE788** |
| 타일복사+팔레트리맵 IWRAM | 0x03006744 |
| base ptr 테이블(기호/히라/가타) | 0x08B80270 → 0x08B8027C/057C/087C |
| **한자 테이블** | 0x08B80B7C (536×6B), 끝 0x08B8180C |
| FONT_BASE (글리프) | 0x08B974D0, 타일=idx*0x20 |
| 기본 width | 8 (ip), 한자는 테이블 |

### 구현 접근 (2차 리뷰 수렴: gemini ASM hook)
원본 매핑 공식을 완전 역산할 필요 없이:
1. **안 쓰는 SJIS 코드 대역 예약**(JIS L2 0x989F+ 등, 원문 전수덤프로 미사용 확인). 1028 음절 1:1 + 여유분.
2. **변환 루틴 ROM 소스(0x08EFE788) 또는 한자 테이블 패치**:
   - (a) ASM hook: 예약 코드면 `idx=(code-KOR_BASE)*2` 식으로 한글 글리프 영역 인덱스 반환 + width=8 고정.
   - (b) 데이터: 한자 테이블(0x08B80B7C)에 한글 엔트리 추가(끝 0x08B8180C 리터럴도 확장) — top/bot idx를 한글 글리프 영역으로.
3. **한글 글리프 주입**: FONT_BASE 뒤(또는 빈 영역)에 1028 음절 top/bot 타일(각 0x20), ink 인덱스 10.
4. **번역문 인코딩**: 음절→예약 코드(2바이트)로 치환.
5. **width 균일화**(gemini #1): 예약 코드 width=8 고정(ip 기본 8 활용 또는 테이블 width 8).

### 남은 검증 (다음)
- 전 화면 FONT_BASE read watch로 대화 외(전투/맵/스탯) 같은 경로인지 커버리지 확인.
- 변환 루틴 ROM 소스(0x08EFE788) 패치 PoC: 예약 코드 1개 → 한글 글리프 렌더.
- 가나/기호 범위의 정확한 base→glyph index 2차 indirection 확정(현재 한자 테이블 경로가 더 명확).

## [2026-05-25] Phase A 커버리지 + 변환루틴 전체 디스어셈블 + 글리프 배치 경계 확정

SESSION 1 작업. 글리프 블롭(800 dedup 타일) 생성 + 배치 전략 결정을 위한 정밀 RE.
codex+gemini 리뷰 반영(codex OK, gemini는 메커니즘 오해 우려 → 디스어셈블로 반증).

### Phase A — 텍스트 렌더 경로 커버리지 (정적+동적)
- **per-char 텍스트 경로(번역 대상 텍스트 전부)는 단일 chokepoint**:
  - 변환루틴 0x030065E0(ROM 0x08EFE788)는 veneer **0x08B1BEFC**(리터럴 0x08B1BF10=0x030065E1)
    로만 도달. veneer 0x08B1BEFC의 ROM 호출자는 **정확히 2곳**: `0x08B1275E`(대화 렌더 루프),
    `0x08B12B1A`(2번째 텍스트 렌더러). 둘 다 동일 변환루틴·동일 FONT_BASE(리터럴 0xEFE97C) 사용.
  - 동적 확인: hajimemashite 대화 도달 시 copy 0x03006744 BP 167히트 **전부 lr=0x08B1BF0D 단일**.
- **별도 경로: 폰트 bulk DMA 업로드 2곳**(FONT_BASE 리터럴 중 나머지 2개):
  - `0x08B11B54~`: DMA3(0x040000D4) src=FONT_BASE, dst=VRAM 0x06000000, CNT=0x80002C00
    → **idx 0..0x2BF(704타일, 22KB)를 VRAM에 통째 업로드**. (이름입력 그리드 등 프리로드+타일맵 경로)
  - `0x08B6A86C~`: 동일 패턴, CNT=0x80000100 → idx 0..0xF(16타일) 소형 업로드.
  - 이 경로들은 **프리로드된 고정 글리프셋**을 타일맵으로 렌더 → per-char 변환루틴 안 거침.
- **결론**: 번역 텍스트(대화/메뉴/유닛명)는 per-char 단일 변환루틴이 담당 → 한글화는 이 루틴 1곳 처리로 커버.
  bulk-DMA 화면(가나 입력 그리드/소형 심볼)은 별개 글리프셋 — **잔여 리스크**(그 화면이 번역 텍스트를
  쓰는지 Session 3 QA에서 확인. 가나 캐릭터 피커면 무관).

### 변환루틴 0x08EFE788 전체 디스어셈블 (글리프 소스 계산 — bound check 없음)
```
0xEFE7B0: r3 = (lead<<8)|trail = SJIS;  r7 = byteswap(SJIS)
0xEFE7BE: r1 = ((SJIS+0xFFFF7EC0)&0xFFF8)<<1 + (SJIS&7)   ; 중간 index
0xEFE7D2: ip = 8 (기본 width)
0xEFE7D8: cmp SJIS,0x823F; bhi → 아니면 r5=baseptr[0](0x08B80270[0])   ; 기호/ASCII
0xEFE800: cmp SJIS,0x833F; bhi → 아니면 r5=baseptr[1], index-=0x200      ; 히라가나
0xEFE820: cmp SJIS,0x8397; bhi → 아니면 r5=baseptr[2], index-=0x200      ; 가타카나
0xEFE838: (한자) ip=1; r5=0x08B80B7C(table start, 리터럴 0xEFE970)
0xEFE844:        r1=0x08B8180C(table end, 리터럴 0xEFE974)
0xEFE848: 루프: r2=halfword[r5]; cmp r7,r2; beq found; r5+=6; cmp r5,end; blo 루프
          미발견 시 r5=[baseptr]+0x1e (fallback glyph)
0xEFE85A: r5+=2 (→ &top_idx)
0xEFE85E: r3 = 0x08B974D0 (FONT_BASE, 리터럴 @0xEFE97C)   ★repoint 대상
0xEFE866: r1 = (sel<<1) + r5     ; sel = 0(top)/1(bot)
0xEFE86A: r0 = halfword[r1 + ip<<1]   ; ★테이블에서 top/bot idx 읽음 (16-bit, 클램프 없음)
0xEFE86C: r0 = idx << 5            ; idx*0x20
0xEFE86E: r7 = FONT_BASE + idx*0x20  ; ★글리프 ROM 소스 포인터
0xEFE87E~: 픽셀 nibble별 팔레트 리맵(>임계 시 sp/sl/sb/리터럴 오프셋 가산)
```
- **핵심: idx에 상한 검사(CMP/clamp)가 없다.** 테이블이 주는 idx를 그대로 `FONT_BASE+idx*0x20`. → gemini가 우려한 "하드코딩 bound check"는 **존재하지 않음**(실측 반증). 유일한 경계는 테이블 검색 end 리터럴 0xEFE974(=0x08B8180C) — 확장 시 갱신.
- per-char 경로는 **ROM→VRAM 동적 글리프 복사**(r7=ROM 소스, 문자당 0x20을 VRAM dst로). 즉 idx는 **ROM 글리프 소스 인덱스**이지 VRAM 타일맵 타일번호가 아님 → gemini의 "10-bit 타일 인덱스/VRAM 오버플로우" 우려는 메커니즘 오해(73KB 블록은 **ROM** 0x08F00000에 위치, VRAM 아님).

### 글리프 배치 경계 확정 (per-char 경로 max idx)
- 가나/기호 baseptr 인덱스테이블 max idx: sym 0x5F2, hira 0x3F9, kata 0x5F4.
- 한자 테이블(536엔트리) top/bot max idx: **0x5FF**.
- **per-char 경로 전체 max glyph idx = 0x5FF** → 폰트 사용 영역 = FONT_BASE..FONT_BASE+0x600*0x20
  = 파일 0xB974D0..0xBA34D0 = **정확히 48KB**.
- 도달범위 [0xB974D0, 0xD974B0](16-bit idx) 내 안전 빈공간: 0xFF 12타일뿐(0x00 1148타일은 흩어진
  그래픽 빈타일 → 덮으면 손상). **연속 25KB 안전공간 없음.**
- ROM 끝 0xF00000~0xFE0000 = **896KB 빈공간(0x00)**, 단 현 FONT_BASE 기준 16-bit 도달 밖.

### FONT_BASE 리터럴 (0x08B974D0 LE) — ROM에 정확히 3곳
| 파일오프셋 | 용도 |
|---|---|
| 0xEFE97C | **per-char 변환루틴** 글리프 소스 base (repoint 대상) |
| 0xB11B74 | bulk DMA(704타일) src — 프리로드 경로 |
| 0xB6A894 | bulk DMA(16타일) src — 소형 프리로드 |

### 글리프 dedup (Phase C-1)
- 번역문 고유 한글 음절 **1030개**(사전렌더 JSON 1028보다 궈·깎 2개 많음, CSV 기준 재생성).
- 각 음절 top+bot 8x8 4bpp(ink 10). **타일 dedup → 고유 800타일(top 437+bot 363, 겹침 0) = 25,600B**.
- `tools/build_korean_glyph_blob.py` → `data/korean_glyph_blob.bin`(25600B) + `data/syllable_to_glyph.json`
  (음절→로컬 top/bot 타일 idx). blob sha1 2f345701…. empty render 0건.

## [2026-05-26] 영문 그리드 양립을 위한 ASM hook 설계 (대화 방식 전환 — 사용자 결정)

### 배경: repoint와 v56 영문 그리드 충돌 (해결책=ASM hook)
- v56 영문 그리드는 원본 FONT_BASE(0x08B974D0) 슬롯에 영문 글리프 주입(top/bottom 슬롯 128/144… = 대화
  가나 글리프와 동일 슬롯). 그리드는 변환루틴 FONT_BASE 리터럴(0xEFE97C)로 글리프 fetch.
- 내 대화 방식은 0xEFE97C를 0x08F00000으로 repoint → 그리드도 0xF00000(원본 가나 복사) 읽어 영문 무시.
- 도달범위[0xB974D0,0xD974B0]에 25KB 연속 빈공간 없음(최대 4.5KB@0xBAE15C). → repoint/offset-trick 불가.
- **해결: repoint 폐기. 원본 FONT_BASE 보존(그리드+대화 가나/한자). 예약 한글코드만 ASM hook으로 별도
  KOR_BASE(0x08F00000) 사용.**

### 구현 계획 (다음 세션 실행)
1. base = `output/v56_polished.gba`(영문 그리드+훅 포함). **0xEFE97C repoint 안 함**(FONT_BASE 원본 유지).
2. 한글 800 dedup 글리프 → 파일 0xF00000 (KOR_BASE=0x08F00000).
3. 한자 테이블 확장 → 0xF20000, 한글 엔트리 top/bot idx = `kor_local_idx | 0x8000`(bit15=한글 마커).
   start/end 리터럴(0xEFE970/0xEFE974)만 패치. **0xEFE97C 건드리지 말 것.**
4. **ASM hook (trampoline, IWRAM↔ROM)**: 변환루틴 글리프소스 계산부(0xEFE86A `ldrh r0,[r0]`=idx 직후,
   0xEFE86C `lsls r0,#5`/0xEFE86E `adds r7,r0,r3`)를 hook 호출로 교체:
   - `ldr rT,[pc,#lit]`(rT=hook ROM주소|1) + `blx rT`. (IWRAM→ROM은 BLX register로 range 무제한)
   - hook(ROM 빈영역, v56가 0xA3Cxxx 사용하므로 0xF24000+ 등): 입력 r0=idx, r3=FONT_BASE.
     `if (idx & 0x8000): r7 = 0x08F00000 + (idx&0x7FFF)*0x20; else: r7 = r3 + idx*0x20;` → `bx lr`.
   - ⚠️ 레지스터 보존 필수: 0xEFE870+ 가 r6 사용, 0xEFE87C가 r2 사용 — hook이 r2/r6 등 clobber 금지.
     hook 진입 전 라이브니스 분석(r0,r3 in / r7 out / r1,r2,r4,r5,r6,sp,sl,sb 보존) 후 scratch 선택.
5. 빌드: v56 훅 대화 3개(0xDF8E16/DB2/E3E)+네임플레이트+데이터테이블 제외(이미 구현). 나머지 대화 인코딩.
6. 검증: 대화 한글(hook 경유) + 영문 그리드(v56) 둘 다 인게임 확인. cold-boot.

### 리스크
- ASM 레지스터 clobber / Thumb 인코딩 / IWRAM(0x030065E0)↔ROM hook 인터워크(BLX reg).
- hook ROM 위치가 v56_polished에서 비어있는지 확인(0xA3Cxxx는 v56 사용).
- 실패 시 fallback = 현재 동작 빌드(repoint, 가나 그리드).

## [2026-05-26] 2편(Advance 2) 별도 텍스트 시스템 — Game 2 "?" 깨짐 원인 + 수정계획

GBWars 1+2 컴필레이션은 **게임별 독립 텍스트 렌더 시스템**. 1편 hook은 1편 루틴만 패치 → 2편 "?".

### 변환루틴 3개 (시그니처 -0x8140 = 0xFFFF7EC0)
| 루틴 | 위치 | 테이블 | FONT_BASE | 비고 |
|---|---|---|---|---|
| 1편 대화 | ROM 0x08EFE788 (IWRAM 0x030065E0) | 0x08B80B7C(start@0xEFE970) | 0x08B974D0(@0xEFE97C) | **패치완료**(hook) |
| 타일맵계열 | 0x08B11Cxx | 0x08B80B7C(@0xB11E24) | 0x08B974D0(@0xB11B74) | char→tile idx strh, BG타일맵 |
| **2편 대화** | 0x08313xxx | **0x083902E4**(start@0x313FFC, end 0x08390F74@0x314000) | ? (찾아야) | baseptr 0x0838F9D8(@0x313F38/60/88) |

### 2편 한자테이블 0x083902E4 (536엔트리×6B, 1편과 동일 포맷)
- [stored_SJIS_LE, top_idx, bot_idx]. 예: k0 stored=0x548C(SJIS 0x8C54) top=0x540 bot=0x550. → **글리프복사 방식**(1편과 동일).
- end 0x08390F74 → (0x08390F74-0x083902E4)/6 = 536엔트리.

### 2편 수정계획 (1편과 동일 패턴)
1. 2편 루틴(0x313xxx) 글리프소스 계산부(`FONT_BASE+idx*0x20`)와 FONT_BASE 리터럴 특정. IWRAM 복사여부 확인.
2. 2편 테이블(0x083902E4) → 빈 ROM으로 relocate + 한글 엔트리(같은 예약코드, idx bit15 마커) 추가.
   start/end 리터럴(0x313FFC/0x314000) 패치.
3. 2편 글리프소스에 hook(1편과 동일: bit15→KOR_BASE) 삽입. ARMv4T bx 기반.
4. 게임선택에서 "2"(Advance 2) 진입 → PROLOGUE 도달 → 인게임 검증. (네비: game-select 커서 이동 필요)
- 한글 글리프(0xF00000)·예약코드(syllable_to_code.json)는 1편과 공유 재사용.

### 잔여 미해결
- 0x08B11Cxx 타일맵 루틴: 어느 화면이 쓰는지(이름그리드? 2편 일부?) + 한글 지원여부 미정.
- 0x313xxx FONT_BASE·글리프소스·IWRAM 여부 미특정(다음 작업).

## [2026-05-26] 2편 = 타일맵 라이터 (1편과 근본적으로 다른 출력 — 동적 VRAM 타일 필요)

2편 변환루틴(0x313xxx) 디스어셈블 완료. SJIS→idx 부분은 1편(0xEFE788)과 동일 구조이나 **출력이 다름**.

### 2편 한자 글리프 출력 (0x313FB0-0x313FCE)
```
0x313F90: r0=table(0x083902E4); 0x313F9E: r1=end(0x08390F74)
0x313FA0: 선형검색(ldrh r2,[r0]; cmp r7,r2; beq; r0+=6; blo)  ← 1편과 동일
0x313FAC: r0+=2 (→&top_idx)
0x313FB0: r3 = sl + (idx_pos<<1)   ← BG 타일맵 목적지 주소
0x313FB8: r1 = ldrh[table+top_idx위치]   ← top_idx (테이블에서)
0x313FBA: r0 = top_idx | [sp,#0x18]       ← idx | 팔레트/속성 비트
0x313FBE: strh r0, [r3]                    ← ★BG 타일맵에 직접 기록 (idx=VRAM 타일번호)
0x313FC0: r3+=0x40; (bot_idx도 동일하게 strh)
```
### 함의 (1편과 근본 차이)
- 1편: `r7=FONT_BASE+idx*0x20` 글리프 픽셀을 VRAM에 **복사**(hook으로 KOR_BASE 리다이렉트 가능).
- **2편: 테이블의 idx를 BG 타일맵에 그대로 기록.** idx = **이미 VRAM에 프리로드된 타일 번호**.
  → 한글 렌더하려면 (a) 한글 글리프 타일을 2편 VRAM charblock에 적재 + (b) 테이블 한글엔트리 idx=그 VRAM 타일번호.
- **내 bit15 마커는 BG 타일맵 엔트리의 V-flip 비트(bit11)/팔레트(bit12-15)로 해석** → 그대로 쓰면 깨짐.
- 즉 2편은 **동적 VRAM 타일 캐시**(한글코드 만나면 글리프를 VRAM 빈 타일에 로드, 그 타일번호를 타일맵에 기록)
  방식이 필요 — 1편 hook과 전혀 다른 대규모 구현.

### 현재 2편 "?" 원인 확정
- 2편 테이블(0x083902E4, 536엔트리)에 내 예약 한글코드 없음 → 선형검색 실패 → fallback "?".
- 단순 테이블 repoint로는 안 됨(idx|0x8000 마커가 타일맵 비트로 깨짐 + 한글 타일이 VRAM에 없음).

### 옵션
1. **풀 한글(대규모)**: 2편 VRAM 폰트 적재경로 RE + 동적 한글 타일 캐시 hook + 테이블확장(마커X, VRAM타일번호).
2. **interim(일본어 유지)**: 2편 텍스트 주소범위를 인코딩 제외 → "?" 대신 원본 일본어(가독). 2편 텍스트 범위 RE 필요.
3. 현상 유지.

## [2026-05-26] 2편 렌더러 RE — 네비게이션/타이밍 벽 (세이브스테이트 필요)

2편 풀 한글화 착수. 2편 텍스트 시스템이 **다중 렌더러 + elusive**임을 확인.
- 후보 루틴 0x313xxx(테이블 0x083902E4) + IWRAM 0x030065E0 둘 다 **MODE SELECT/타이틀 진입 시 미발화**.
- 2편 테이블(0x083902E4) **read 워치포인트도 MODE SELECT/타이틀에서 0 hit** → 그 화면은 이 테이블/루틴 안 씀.
- 즉 2편은 화면별(메뉴/프롤로그/인게임) **렌더러가 여러 개**고, "?" 나는 MODE SELECT는 0x313xxx가 아님.
- prologue는 CAMPAIGN 메뉴 통과 후라 워치포인트 armed 상태로 도달이 어려움(텍스트가 화면전환 시 1회 렌더).
- IWRAM 0x030065E0는 2편 중 1편 변환루틴이 아닌 다른 코드(0068002824d0...) — 2편은 다른 IWRAM 배치.

### 다음 단계 (효율적 RE 위해)
- **사용자 세이브스테이트**(2편 프롤로그/깨진 화면)가 있으면: 로드→텍스트 read/VRAM-write 워치포인트로
  렌더러 PC 즉시 특정 가능. 네비게이션/타이밍 병목 제거.
- 또는: 2편 텍스트 주소범위 확정 → interim(2편 인코딩 제외, 일본어 유지로 "?" 제거).
- 2편 렌더러 특정 후: 글리프복사형이면 1편처럼 hook, 타일맵형이면 동적 VRAM 한글 타일 캐시.

### 확정 사실
- 2편 = Advance 2(게임선택 하단). boot 500f→Start→Start=게임선택, Down+A=Advance 2 진입.
- MODE SELECT 메뉴(キャンペーン 등)는 일본어 표시 + "?????" 행(내 예약코드). prologue(image#6) 전체 "?".

### 이름 그리드 렌더 시스템 (2026-05-26 완전 RE)
- **가나→슬롯 테이블**: base8 = *(0x08B80278) = 0x08B8087C. kidx=((SJIS-0x8140)&0xFFF8)*2+(SJIS&7)-0x400.
  top=base8[kidx], bottom=base8[kidx+8]. (변환루틴 0x08EFE788; 코드범위별 base[0]=0x08B8027C≤0x823F,
  base[4]=0x08B8057C≤0x833F, base[8]=가나≤0x8397; >0x8397 한자테이블 0x08B80B7C.)
  - 95 = 공유 블랭크 슬롯(작은가나 top 등). 패치하면 그리드+대화 공유 영향.
- **그리드 레이아웃(행 문자열)**: 0x08DF8C38/60/88/B0/CC/E8 (6행). 포맷 `0A 09` + SJIS(big-endian 2B/문자) + `0A 00 00 00`.
  렌더 루틴 0x08B48910~960 (6× bl 0x08B1311C, x/y=6,{6,8,10,12,14,16}, r3=행주소). 미리보기 렌더=0x08B48E50(객체 *(0x03004690), obj+0x2c).
  - ★SET1(0x083FAF6, 6참조)·SET2(0x083FE41)·charlist(0x80505c→EWRAM 0x02010CEC)는 dead data — 그리드 렌더에 안 쓰임.
- **검증 기법**: 슬롯-프로브(폰트슬롯 0~N에 니블1-9로 슬롯번호 인코딩 마커 주입 → 신규 부팅네비(frames200+A×28)로
  이름화면 도달 → BG0(screenblock14,charblock0) 타일맵의 셀 타일ID→타일내용 디코드 → 셀이 읽는 실제 슬롯 역산).

## 2026-06-16 — Part 2 모드선택 메뉴 CO 인사말 "?" 잔존 (A3 렌더러)

- **증상**: fresh-boot Part 2 메인 메뉴(캠페인/도전/자유전 + 여성 CO)의 하단 인사말이 `???? ??부? ?래??니다`로, 한글 음절 다수가 `?`(0x8148 fallback)로 렌더. 증거: `docs/screenshots/ISSUE_part2_menu_greeting_question_marks_2026-06-16.png`.
- **확정 원인**: A3 hook(`PART2_HOOK_A3`)의 relocated table end literal이 `0x08F224B4`로 하드코딩되어 있었지만, 실제 2350자 확장 테이블 끝은 `0x08F243A4`다. 원본 536엔트리 뒤 한글 2350엔트리를 붙인 전체 길이는 `0x43A4`이며, 구 literal은 정렬된 한글 엔트리 앞 1030자(`가`..`빚`)만 검색했다. 그래서 `부/래/니/다/만/기/려`는 처리되고 `어/서/오/시/십/입/잠/주`는 검색 실패 → 원본 `0x8148` fallback으로 빠졌다.
- **캐시 검증**: A3 원본의 `0x0852F960` linked glyph table miss가 fallback 출처지만, 한글 성공 경로는 이 캐시를 쓰지 않고 `KOR_BASE`에서 `r5`가 가리키는 VRAM 2타일로 직접 복사 후 epilogue(`0x030061C1`)로 복귀한다. 따라서 긴 문자열 캐시 초과/충돌이 아니라 A3 hook의 table-end literal 오류다.
- **수정**: `tools/build_korean_full.py`에서 A3 hook table-end literal을 placeholder로 두고, `new_tbl` 생성 직후 `P.NEW_TBL_RT + len(new_tbl)`를 `PART2_HOOK_A3_FILE + 0x8C`에 패치한다. 현재 산출 ROM 기준 `0xF3030C = A4 43 F2 08`(`0x08F243A4`). fresh capture `temp/a3_fix_visual_20260616/sheet.png`의 `07_part2_main_menu`에서 하단 문구 `캠페인을 처음부터 플레이합니다` 정상 표시 확인.

## 2026-06-16 — A3 전각공백 폭: 오진(이미 1칸 정상) — 픽셀 실측 교훈

- **결론: A3 전각공백은 이미 1칸(약 9px)으로 정상 렌더된다. "이중공백처럼 넓다"는 초기 진단은 NEAREST 3x 확대 + 무공백 일본어 원본과의 대비에서 온 시각 착시였다.**
- **픽셀 실측**(`07_part2_main_menu` `캠페인을 처음부터 플레이합니다` 하단 텍스트, y148~158, 흰픽셀 열 분석): 단어 간 gap = **9px (= 1칸 8px + 1)**. `?` 수정만 적용된 ROM과 codex 전각공백 hook 적용 ROM의 gap이 `[59,9,9,54]`로 **완전 동일** → hook은 no-op.
- 따라서 codex가 추가한 `PART2_HOOK_A3_ZENKAKU_SPACE`(0x08314332 trampoline)는 효과 0이고 비정렬 파서 패치 crash 표면만 늘려 **revert**했다. 출하 ROM은 `?` 테이블-end 수정만 유지(SHA `6a14a710...`).
- **교훈**: 띄어쓰기 폭 결함은 **확대 육안이 아니라 흰픽셀 열 gap 픽셀 실측**으로 판정한다. 렌더러 간 폭 일치 확인도 동일 방식.
- (참고 RE, 유효) A3 파서 `0x0831424C`: 첫 바이트 `0x09..0x33`만 1차 jump-table(`0x08314270`)로. `0x20`=엔트리 `0x0831431C`(기존 hook 1칸). `0x8140`의 `0x81`은 `0x08314332: cmp r0,#0x77; bhi 0x083147F4`로 일반 2바이트 문자 경로. 단, 그 경로의 실제 advance는 1칸(실측 9px)이라 별도 수정 불요.

## 2026-06-16 — 자동진행 fresh-boot로 발견: 영어 잔존 BG 2종 (실잔존, stale 아님)

`tools/auto_playthrough.py` 콜드부트 자동진행(BG 신뢰)으로 발견. 과거 savestate QA가 "stale"로 기각했으나 **fresh-boot 현재 ROM에서 실제 영어 잔존 확인**:
1. **전략/영토 지도**(작전 진입 오버맵): 필기체 영어 지명 `Red star Palace`/`Blue moon Palace`/`Cosmo earth Palace`/`Factory`가 지도 그래픽에 박힘. 증거 `docs/screenshots/ISSUE_strategic_map_english_palace_labels_2026-06-16.png`. (작전실 BG 0xBF66F0은 한글화됐으나 이 오버맵은 별개 미패치 블록.)
2. **작전/전투 선택 화면 BG**: `RED STAR`/`BLUE MOON` 영어 국가명 타일. 증거 `docs/screenshots/ISSUE_operation_select_bg_english_2026-06-16.png`. (대사 "내가 싸우는 법을 알려줄게"는 정상.)
- 캠페인 월드맵은 한글(블루문)로 패치됨 확인(별개). 위 2종만 미패치.
- 수정 경로: 해당 LZ77 BG 블록 식별 → 디코드 → 영어 지명 타일을 한글(레드스타/블루문/그린어스/코스모랜드 등)로 재작도 → 재압축(comp_size≤). 필기체 라벨은 한글 픽셀로 대체.
- **교훈**: savestate "stale" 기각이 실잔존을 가렸다. 콜드부트 자동진행이 ground truth.

## 2026-06-16 — 영어 잔존 BG 한글화 레시피 (codex 블록탐색 + 분석 확정)

**0xBF66F0 작전/전투선택 BG (4bpp tiles, 해제 10112B=316타일, consumed 2952B, 팔레트 0xBF7A7C, tilemap raw 0xBF727A 32x32)**
- 국가명 텍스트는 각 1타일행(8px), 측면 배너 장식 포함. 텍스트는 ~6px 작은 픽셀폰트, cream bg(idx3)+색문자.
- 교체 대상 텍스트행 타일ID(같은 ID가 상/하단 2곳에 배치 → 1번 교체로 양쪽 반영):
  - RED STAR: 0x50–0x5B (12타일, tilemap y=6·22 x=1..12)
  - BLUE MOON: 0x70–0x7C (13타일, y=2·18 x=17..29)
  - GREEN EARTH: 0x110–0x11C (13타일, y=14·30 x=9..21)
  - YELLOW COMET: 우측 블록(0xC0–0x114 계열, y=9~14 x=9+) — 정밀 타일ID 추가 확인 필요.
- 레시피: lz77_decompress→해당 텍스트행 타일에 galmuri 한글(레드스타/블루문/그린어스/옐로코멧) ~7px 렌더(측면 장식 타일은 보존, 중앙 텍스트만 cream로 지우고 문자색으로 그림)→4bpp 재인코드→lz77_compress_optimal, len≤2952 검증. patch_part2_menu_newspaper_bg(build:5838) 패턴 재사용.
**0xC2FD70 + 0xC30EE8 전략 오버맵 (Mode4 8bpp bitmap 반쪽 2개, 각 0x4B00B=240x80, consumed 4471/4161, 팔레트 0xC2FC90)**
- 필기체 영어 지명을 bitmap 좌표에 직접 덮어 한글 픽셀로 재작도(좌표는 codex_bgblocks.md). 각 반쪽 LZ77 재압축 len≤consumed.
- 주의: 필기체 스타일이라 한글은 일반 픽셀체로 대체(가독 우선).

## 2026-06-16 — 자동진행 깊은 화면 시각 검증 (current-ROM)

auto_playthrough(강화판)으로 캡처·검증(모두 한글 정상, 깨짐 없음):
- 전투 맵/유닛정보 HUD, 전투 애니메이션(탱크전+CO+HP), CO파워 효과, 부대목록 표(종류/체력/연료/탄약 헤더+데이터), 캠페인 월드맵(레드스타/내해/블루문 라벨), 튜토리얼 대사.
- **잔여(미세)**: 부대목록 탄약열의 무탄약(보병) 표시가 `닛`(무의미 글자)로 보임 — 하드코딩 라벨 추정, 텍스트 데이터엔 standalone 닛 없음. 소규모 후속 점검.
- 결과/엔딩 화면은 전투 종료까지 도달 필요(자동진행 정책으로 부분 진전, near-end 세이브 또는 더 긴 런 필요).

## 2026-06-16 — 자동진행 결과/엔딩 도달 한계 + 진행 세이브 생성

- 강화 auto_playthrough 장기 런(600스텝)으로 균형 9v9 전투에서 전투맵/애니메이션/CO파워/부대목록 등 깊은 화면 다수 캡처(전부 한글 정상). **결과(승/패) 화면 미도달**: 균형 전투는 blind 자동진행으로 결판이 안 남(강한 유닛 99/99, 승도 패도 느림).
- **진행 세이브 20개 생성**(temp/auto_results2/state_*.ss0) — 사용자 "없으면 생성" 충족, 더 깊은 지점 재개용.
- **실용적 결론**: 결과/엔딩 *그래픽* 캡처는 near-end 세이브(거의 끝난 전투)가 있어야 실현적. 결과/엔딩 *텍스트*는 ROM-디코드 게이트로 이미 전수 검증됨(의미/띄어쓰기/명사 0). 그 외 모든 도달가능 화면은 시각 검증 clean.
- 잔여 구체 fixable: 부대목록 무탄약 `닛` 표시, 전략 오버맵 8bpp 필기체 지명.

### 전략 지도 화면 2종 정리 (2026-06-16, codex 리뷰 반영 재정정) — 둘 다 표시됨

처음엔 `0xC2FD70`/`0xC30EE8` 한글화를 "전략 오버맵"이라 했고, 그 다음(잘못) "오버맵이 아니라 표시
미확인 블록이라 revert"라 적었으나 **둘 다 부정확**. codex 리뷰로 SWI/DMA 로그를 재분석해 확정한
정확한 그림은 아래와 같다. **전략 지도는 서로 다른 두 화면**이다.

**(A) Mode4 풀스크린 비트맵 = `0xC2FD70` + `0xC30EE8`** — **표시 확정**.
- fresh-run SWI 로그(`temp/auto_fresh_p2/mgbah.stderr.log:7800~7806`):
  `0B`로 팔레트 0xC2FC90→복사, `11`(LZ77)로 0xC2FD70→EWRAM 0x02000000, **DMA 0x02000000→VRAM 0x06000000**(Mode4 fb 상단), 이어 0xC30EE8→0x02000000, **DMA→0x06004B00**(0x4B00=240×80=fb 하단). 즉 두 반쪽이 240×160 8bpp Mode4 프레임버퍼로 들어가 **화면에 그대로 표시**.
- 따라서 오프라인 렌더(팔레트 0xC2FC90)는 타일 간접 없이 **인게임 픽셀과 동일**(`temp/smap_original.png`). 에뮬 네비 없이 오프라인 검증=인게임 검증.
- 라벨(원본): 좌상 회색 오벌 `Red star Palace`(2행), 중앙 적색 구조 상단 `Factory`(1행), 중앙하단 회색 오벌 `Cosmo earth Palace`(2행), + 상단중앙/우하단 희미한 소형 라벨. (필기체 청/암색)
- ⚠ codex_bgblocks.md의 박스 좌표는 **부분 오류**(원본 픽셀 재검증): `Blue moon Palace`(116-174,55-78)는 **원본에 실제 텍스트 없음**(빈 암색 오벌); half-B `Factory` 2건(176-212,21-40 / 53-105,59-78)도 **미존재**(지형/해안선뿐). 중앙 적색구조 `Factory`는 codex 미열거. 상단 작은 해양 라벨 1건(필기체 'Cayo/Cargo?')은 판독 불가. → codex 좌표 신뢰 불가, 원본 픽셀 zoom으로 직접 enumerate.
- **현 상태: 한글화 완료(`patch_part2_strategic_map_mode4_labels`, 사용자 승인 2026-06-16)**. 실측 라벨 3건만: 좌상 회색오벌 'Red star Palace'→**레드스타 궁전**(파랑 idx16), 중앙 적색구조 'Factory'→**공장**(암적 idx24), 중앙하단 회색오벌 'Cosmo earth Palace'→**그린어스 궁전**(암 idx4). 'Cosmo earth'=녹색국가라 배너/범례와 동일 **그린어스**로 통일(#3). phantom/미존재 라벨은 제외(빈 영역에 가짜 라벨 방지). 상단 해양 소형 라벨은 판독불가로 미번역 유지. 오프라인 렌더=인게임(`temp/smap_built_verify.png`). 재압축 A 4249/4471·B 3996/4161 OK.

**(B) Mode0 타일 오버맵 = step073/프레임049-050 대륙 지도** — (A)와 **다른 화면**.
- DISPCNT=0x1B40 Mode0. 대륙지도=BG3(charBase 0x8000, screenBase 0xE800), charBase0 타일 소스 ROM **0xC34E10**(LZ77 decomp 19200B). "작전" 한글 오버레이=BG1. (`temp/over_bg3.png`)
- 필기체 영어 지명(Red star Palace/Factory/Cosmo earth Palace/Yellow Comet/Cable·Battle Factory 등 ~10) = 손그림 지도에 박힌 6px 안티에일리어스 **장식 아트**. 깨짐 아님(원본 그대로 정상 출력). 좁아 강제 한글화 시 깨짐 유발 → scope exception.

**결론**: (A) Mode4 풀스크린 전략지도 = **한글화 완료**(레드스타 궁전/공장/그린어스 궁전). (B) Mode0 대륙 오버맵의 타일 기반 6px 필기체 지명 = 아직 미번역(타일 그래픽 0xC34E10에서 라벨 타일 식별→재페인트 필요, 더 어려움). 둘 다 원래 「비트맵 깨짐」(한글 글리프 손상)은 아니었음.

**0xBF66F0 배너(작전/통신 화면 국가명) 한글화 확정·KEEP**: 원본 0xBF66F0 비공백 타일 312/312(100%)가 인게임 배너 VRAM(step057_A)과 verbatim 일치 → 표시 블록 확정. `patch_part2_operation_select_country_bg`로 레드스타/블루문/그린어스/코멧/옐로 한글화. (이건 깔끔히 완료된 별개 화면)

### A3 렌더러 예약코드 범위 버그 + 수정 (2026-06-16) — 2350 확장분 깨짐

**발견 경위**: UI 에디터 실캡처 기능(canvas-hijack: 07_part2_main_menu의 캠페인 설명 슬롯
0xA2C098를 임의 문자열로 덮어 헤드리스 캡처)을 검증하다가, 캡(0x9fc1)이 인게임에서 '?'로
렌더됨을 포착.

**원인**: `PART2_HOOK_A3`(MODE SELECT/메뉴 A3 글리프캐시 렌더러 hook, 0x08A3C7E4 계열)이
예약-한글 코드를 **[0x8840, 0x9369]** 범위로 1차 판별. 0x9369는 **구 1030자 한정** 상한.
2350 확장분(1320음절)은 코드 **0x936A~0xE2A7**라 이 범위를 벗어나 A3 fallback(0x8148 '?')으로 떨어짐.
- 다른 경로는 영향 없음: Part1 per-char(HOOK_TOP/BOT)·Part2 313/B11 tilemap hook은 **테이블 idx의
  bit15 마커**로 한글 판별(범위 cap 없음) → 전 2350 정상. (grep상 0x9369 범위 cap은 A3 hook에만 존재)
- 출하 텍스트 영향: 코드>0x9369 사용 행은 **단 2건, 둘 다 part1**(0xDFCA93 '다뤘을'의 뤘=0x9868,
  0xDCADA5 '바뀔지'의 뀔=0x9542) → part1 경로(bit15)라 정상 렌더. **A3 화면은 코드>0x9369 미사용**
  → 출하 빌드 무영향(「비트맵 깨짐 0」 유지). 즉 **잠복 버그**(Part2 편집/프리뷰에서 표면화).

**수정**: PART2_HOOK_A3 max 리터럴 0x9369 → **0xE2A7**(2350 최대 코드). 표 lookup+bit15가 한·일 구분
하므로 범위 확장 안전(A3 화면엔 한자 없음). canvas-hijack 검증: 가/뤘/캡/뀔/힝/한 6음절 전부 정상
렌더(과거 뤘/캡/뀔/힝 '?'), 정상 인사말 무회귀(`temp/cap_validate/a3fix_*`).
**회귀 가드**: build에 `max(syl_to_code) > A3_hook_max → AssertionError` 추가(코드맵 변경 시 hook 동기화 강제).
**교훈**: code∩glyph 대칭(qa_glyph_coverage)은 매핑만 보증, **렌더 경로 범위 cap은 별개**(codex point#4 적중).

### 대사 조각 = 단일 ROM 문자열의 분절 (2026-06-16, codex/agy/claude 자문 종합)

**발견**: dialogue_map의 '조각'들은 별도 포인터 문자열이 아니라 **하나의 연속 ROM 문자열**을
추출이 제어코드/변수삽입 지점에서 자른 것. 엔진은 포인터 하나(r4+0x20)를 읽어 **0x00(종료)까지
2바이트씩 walk**하며 한 대사창에 출력(파서 0x08B1215A 계열). 추출이 버린 gap 바이트 = 제어/삽입:
- `0x00` 종료 / `0x0A` 줄바꿈 / `0x09`·`0x6b`·`0x72`·`0x77`·`0x57`·`0x69` 박스·라인 제어
- `0x33 <SJIS literal> 0x30`, `0x32 <literal> 0x30` = **변수삽입 토큰**(literal=런타임 치환 기본값, 예 攻撃→〈커맨드〉/〈유닛〉). (B-team kor.tbl 대조)

예: 0xD90050 'できるだけ' + [33 攻撃 30] + 0xD90060 'をしにいったほうがいいわ！' → 한 메시지
"できるだけ〈攻撃/command〉をしにいったほうがいいわ！". 0xA01970 5조각 → 프롤로그 한 문장.

**그룹화(권위·결정적, tools/build_dialogue_groups.py)**: 주소순 인접 동일 region 비노이즈 조각 중
**사이 ROM 구간에 0x00 없으면 같은 메시지**, 있으면 경계. 휴리스틱 문법추정(오탐: 제목+부제,
공격력/방어력 라벨)은 미사용. 결과 9500그룹(멀티조각 3972, 16+조각 플래그 52)/21569조각.
data/dialogue_groups.json(group→members+segments+assembled). 수동 보정 data/dialogue_group_overrides.json(split_before/join_before).

**편집/빌드 무영향**: 그룹은 표시·문맥용. 저장은 기존대로 주소별 dialogue_overrides.json 역기록
(조각마다 독립 슬롯·길이). 빌드는 [addr,addr+slot)만 쓰고 gap(제어/삽입)은 손대지 않아 자동 보존
→ 신규 빌드로직 0. ⚠ 한국어 조사(을/를·이/가)는 삽입 단어 받침 의존 → 번역 시 (을)를 표기 권장
(런타임 조사 훅은 별도 과제). ⚠ 어순차로 특정 조각 슬롯 초과 가능 → 조각별 byte counter 필수.

## PLACEHOLDER_KO skip-set 누락 → 비트맵 손상 (2026-06-17)

`build_korean_full.py`의 `PLACEHOLDER_KO`(미해결 번역 skip 집합)에 `깨진 문자열`/`[깨진 문자열]`이
빠져 있었다. 그 마커를 korean으로 가진 18행이 ≥0x800000·DENY 영역 밖 **그래픽/비텍스트 주소**
(0x8A298C, 0x8A47CC, 0x8A64D8, 0x8A82A8, 0x8AAF18/98/BC, 0x8AC8D0, 0x8AFA80, 0x8B31D0, 0x8ED57C,
0x8F0124, 0x9412A1, 0xE88C50, 0xE8A524, 0xE8A548, 0xE8BE00, 0xE8F550)에 위치해, 빌드가 마커
텍스트를 예약 한글코드로 인코딩해 **원본 그래픽 위에 16~18바이트 덮어써 비트맵을 손상**시켰다.
- 검출법: 노이즈 행 제거 전/후 빌드 sha 비교(61d51a2a↔1623481a, 289바이트/18영역 차이) +
  각 span에서 `원본 ROM == 노이즈제거 빌드`(손상 없음), `구 baseline`만 손상 보유.
- 교훈: `integrity_map` 교집합으로 "표시 여부"를 판정하면 안 됨(stale일 수 있음). 권위는 실제
  빌드 ROM 바이트. placeholder 정의는 빌드/QA 단일소스로 유지(중복 누락 방지).

## OBJ 직접기록 라벨 함수 4종 — 합성 스프라이트 매핑 (2026-06-17)

LZ77 단일블록이 아닌 흩어진 ROM 오프셋에 4bpp OBJ 라벨 타일을 직접 기록하는 함수:
- patch_part2_battle_obj_labels: status_terrain(0xB93CD0~, 각 24x16=6타일, OBJ분할 재배열
  (0,1,3,4,2,5)→편집기 perm[0,1,4,2,3,5]) + '육'(0xB93BD0,16x16) + compact_terrain(0x464D68~,32x16)
  + unit(0xB94810~,32x16,Galmuri7) + compact_unit(0x466568~) + 휘프(0xBD0230,32x8).
- patch_part2_status_header_labels: 종류/체력/연료/탄약, 각 16x8=2연속타일(0xBE80FC/0xBE77FC/0xBE777C/0xBE76FC).
- patch_part2_info_screen_obj_labels: 정보/정보/비용/설명, 각 32x8=4타일(0xBE945C/0xBE9A5C/0xBE989C/0xBE9BDC).
- patch_part2_action_menu_icon_labels: 공격/대기/부대/저장/설정/종료/보급, 각 16x8=2연속타일(0xBE793C~).
편집기는 base 오프셋에서 tw*th 연속타일을 perm 보정해 읽어 라벨 적층 렌더. 0x465468 '수도'는
status_terrain 블록 stray write(x=4)가 compact_terrain 루프(x=8)에 덮어써져 최종은 compact쪽
(데드코드, objlabel_sprites.json엔 compact 1곳만 기록 → 이중기록 없음).

## 스프라이트 편집→ROM 오버레이 메커니즘 (2026-06-17)

`data/sprites_overrides.json`{id:{indices,...}} → 빌드 `apply_sprite_overrides(rom)`가 체크섬 직전
최종 적용. 키 매칭: id가 OBJLABEL_SPRITES(메모리)면 synthetic, sprites_index면 lz77/raw.
- synthetic: `_grid_to_tiles(indices)`로 조립 타일스트림 복원 → 라벨별 tindex 누적, `rom[off+perm[vis]*32]=tiles[(tindex+vis)*32]` (decode의 정확한 역연산).
- lz77: 재압축(vram_safe)≤comp_size, 초과 skip. raw: ≤size.
무오버라이드=무동작(byte-identical). 편집은 라벨 자동그리기를 덮어쓰므로 우선. revert는 override 제거 후 재빌드(자동그리기 원복).

## 실캡처 canvas 확장(Phase 7) — part1 fresh-nav 대사 fragility (2026-06-17)

통합 에디터 실캡처(canvas-hijack)를 part1 대사로 확장 시도하며 발견(6회 실측 + codex/agy 자문):
- **canvas 레지스트리 외부화**: `data/preview_canvases.json`(key→{slot hex,len,render,nav,checkpoint}).
  `tools/preview_capture._load_registry()`가 병합(JSON이 하드코딩 덮음). `build_scene_catalog`은
  canvas.checkpoint로 scene↔canvas 매핑. 새 canvas 추가 = 코드 수정 0.
- **part1 인트로 대사 슬롯**(dialogue_map 실측): welcome=`0xDF8E16`(slot32 'ゲームボーイウォーズへようこそ！'),
  이름프롬프트=`0xDF8DB2`(slot26 'あなたの名前をおしえてね。'), 'はじめまして'=`0xDF8E3E`(slot14).
  (agy 추정 0xDF8E14/0xDF8DB0은 2바이트 빗나감 — 실주소는 위.)
- **fresh-nav 도달은 됨**: 콜드부트→1편선택→1편타이틀→A(처음부터)로 캐서린 환영 대사창 진입 확인
  (per-char dialog 렌더러, 한글 정상 렌더).
- **그러나 캡처 불안정**: 인트로 대사(welcome/이름프롬프트)는 **입력 대기 없이 자동 진행**(컷씬).
  하이재킹한 텍스트가 짧으면 빨리 타이핑→자동 advance→캡처 프레임이 인접 화면(이름 그리드)에 안착.
  동일 nav라도 하이재킹 텍스트 길이에 따라 결과 화면이 달라짐(welcome↔이름그리드). 입력 대기로
  안정적인 건 이름 입력 **그리드**(텍스트 슬롯 미렌더)뿐.
- **결론**: 신뢰성 없는 canvas는 출하 금지(codex "ready 금지 until verified"). part2_menu(A3, 입력
  대기 메뉴라 안정)만 정식 등록 유지. part1/battle 대사 canvas는 **frame-sweep(대사창 비공백
  프레임 자동 선택) 또는 대사창 직전 정밀 savestate**가 필요(후속). savestate는 VRAM stale이라
  단순 frames advance 무효 — 로드 직후 대사 재트리거(press A) 필요(agy/codex 공통 경고).
- **캐시 키 버그 수정**(codex): preview_capture 캐시 키가 base_rom.name+text뿐이라 nav/슬롯/ROM
  내용 변경 시 stale 재사용 → 키에 canvas sig(slot/len/nav)+base_rom(size:mtime) 포함.

---

## 2026-06-23: Part2 캠페인 대사 메시지 포인터 테이블 RE + 단어붙음 repoint 해소

> 외부 서양판 한글패치(락이다님, GPT 기반 영어베이스)와 완성도 비교 중 발견. **qa_text_fit가
> dialogue_overrides(쪼롱이님/B팀)를 walk에서 누락**해 단어붙음 504건을 못 보던 QA 사각지대를 확인.

### 발견된 사실 (재현 가능)
- **Part2 메시지 포인터 테이블 = `0x08A357B4` ~ `0x08A38B80`** (3,315 엔트리, 4바이트 LE 포인터,
  단조 증가, 타깃 0x08A01970~0x08A357A0). 각 엔트리 = 한 대사 메시지의 시작 주소.
- 메시지 = 라인(0x0A/제어로 구분) + 종단 제어(예 `6B 00 00 00`). **메시지 중간으로 들어오는
  포인터는 없음**(순차 읽기) → 메시지 전체를 다른 곳으로 옮기고 포인터만 갱신하면 안전.
- **여유공간 `0x00A3CF14 ~ 0x00B00000`**(약 799KB, 미사용 0xFF). 출력 ROM에서 non-0xFF 0B 확인.
  빌드는 별도로 `0x08F20000~`(폰트 relocated table)만 사용 → 0xA3D000 블록과 무충돌.
- found_texts의 라인 span이 메시지를 (라인 + 제어 gap)으로 **무손실 정확 분해**됨(171/171 ok, 후 190/190).

### 단어붙음의 두 출처 (중요)
1. **dialogue_overrides(쪼롱이님)**: 소스에 공백 온전 → 빌드 encode_fit이 슬롯-fit으로 공백 제거
   (level≥10). **repoint로 정확 복원 가능(안전).**
2. **translation_for_import.csv 병합 항목**(미션 목표 등): 여러 시각줄을 한 슬롯에 병합·선-단어붙음
   저장. per-line 재배치 시 중복 노출 → **건드리면 안 됨(가드로 skip).**

### 해결 (`tools/dialogue_repoint.py`, build_korean_full.py "2.9" 블록)
- 메시지를 0xA3D000~에 전체 재배치, **슬롯-fit으로 열화된 쪼롱이님 라인만** `encode_full_fidelity`
  (반각공백 완전충실)로 복원, 포인터 갱신. 비대상 라인·제어 스켈레톤·구주소는 byte-identical.
- 안전 가드 4중: ①포인터 ROM 내 정확히 1개(테이블) ②(라인+gap) 정확분해 ③메시지 내 라인 간
  텍스트 중첩(병합 override) 없음 ④여유공간 내 비중첩.
- 결과: **190 메시지 / 216 라인 단어붙음 해소**, merged-skip 4. 구조검증 errors=0(temp/compare/verify_repoint_struct.py).
- 잔여 단어붙음 242건은 Part1(0xD8~0xE0)·0xB8 영역 — **분산 포인터 구조**(단조 테이블 아님)라
  repoint 확장에 별도 RE 필요(후속). `qa_dialogue_jamming.py`로 추적.

### 2026-06-23 (續): Part1 대사 repoint 시도 — 메시지 테이블 식별 불가(struct 함정)

사용자 요청으로 Part1(0xD8~0xE0·0xB8) 잔여 단어붙음 244건의 repoint 확장을 시도, **안전하게 불가** 판정.

**RE 결과**:
- Part1 대사 라인은 **개별 포인터 없음**(메시지-중간 라인, Part2와 동형). 0xE0 대사는 순차 텍스트
  (0xE00166 'ほう？', 0xE00171 'こんなところに…' 등 found_texts 실재).
- 그러나 **진짜 대사 메시지 포인터 테이블을 분리 불가**. ROM 전수 스캔(0x08D9xxxx 등)은 **우연 매치
  대량 포함**(예 0x06E43C의 0x08D9BDC5는 주변이 그래픽/코드). 조밀 연속 테이블(≥20)은 103개나
  검출되나, 큰 것들이 **struct/이벤트 테이블**이다.
- **결정적 반례**: 테이블 0xE1075C(n=98)가 가리키는 '메시지' 시작 `0xE017B8` = `00 00 00 00 89 89
  b3 08 00 …`(zeros+int 필드 = struct), 대사 아님. found_texts 라인이 그 span 안에 있어 decompose는
  통과하지만 디코드하면 `····演ｳ····` 쓰레기. → **decompose 가드만으론 struct 오인식을 못 막음.**

**판별자 발견 + 엔진 하드닝**: 진짜 대사 메시지는 **헤더갭(메시지시작→첫 found_texts 라인)이 작다**
(Part2 실측 최대 12, 3247개 중 갭>16 = 0). struct 테이블은 갭 178~195. → `dialogue_repoint`에
`max_header_gap=16` 가드 추가(헤더갭>16이면 비-대사로 skip). Part2 출력 byte-identical(SHA 0725a175),
잘못된 테이블을 넘겨도 struct 재배치(게임 손상) 차단. **단, 진짜 Part1 대사 테이블은 여전히 미발견**이라
Part1 repoint는 0건(빌드 미적용).

**다음 경로(후속)**: 런타임 트레이싱 — mgba 헤드리스로 Part1 대사 1개를 화면에 띄우고 렌더러의
포인터 로드(PC/주소)를 watch해 **진짜 대사 테이블 위치를 역추적**. 그 테이블을 확보한 뒤에야
`table_offsets`에 추가 가능. 실기/플레이테스트 동반 권장(쪼롱이님 캠페인 대사 손상 방지).
