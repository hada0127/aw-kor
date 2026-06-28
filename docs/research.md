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
- **2026-06-26 D5 보강**: 위 skip은 더 이상 콘솔 로그만이 아니다. 빌드는 `temp/sprite_override_report.json`에
  override SHA, per-sprite applied/skipped/ignored, LZ77 `compressed_size`/`comp_size`를 기록한다.
  `tools/audit_sprite_override_report.py --strict`와 `verify_dist_integrity.py`의 `sprite override fit` 게이트가
  non-empty override의 stale report, 재압축 초과, size mismatch, skipped record를 critical 처리한다.

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
- **2026-06-26 갱신**: frame-sweep 구현 후 `part1_welcome`은 정식 승격. 단순 원본 슬롯
  `0xDF8E16` 패치는 화면에 반영되지 않았고, 실제 표시 command-stream 복사본 37B span을 NUL 없이
  패치해야 했다(뒤따르는 `0x6B/0x0A` 제어코드 보존 필수). 이후 repoint 배치가 바뀌며 초기
  `0xA7AB56`은 뒤쪽 안내문으로 밀렸고, 현재 정본은 `temp/repoint_manifest.json`의
  `0xDF8E14 -> new_addr` + fixed `0xDF8E16` delta로 계산한다(현재 fallback `0x00A7AA56`). nav 후
  frame 108/120/132/144를 sweep하고 `score_box=[20,124,220,148]`에서 ink score 최대 프레임을 선택한다.
  `tools/verify_preview_canvases.py`가 payload A/B 픽셀 차이를 검사해 잘못된 slot ready 회귀를 차단한다.
  battle 대사 canvas는 아직 **대사창 직전 정밀 savestate 또는 별도 frame-sweep 검증** 필요. savestate는 VRAM stale이라
  단순 frames advance 무효 — 로드 직후 대사 재트리거(press A) 필요(agy/codex 공통 경고).
- **2026-06-26 battle dialogue 후보 실측**:
  - `31_battle_dialog`은 이름과 달리 실제 대사 화면이 아니라 전투 정보/UI 화면(우측 료 초상+자금 1000)이며
    provenance도 구 SHA `4f6898d...` 기반 stale다. battle dialogue canvas 근거로 사용하면 안 된다.
  - 실제 대사 화면 후보는 `89a_common_battle_surrender_confirm`(항복 확인)와
    `89b_common_battle_defeat_comm_messages`(레드스타 군은 패배했습니다). 최종 표시 savestate에
    `0xEFDAA0`/`0xEFDAC1`/`0xA34D18`/`0xEFD8A4` payload를 바꿔 캡처해도 diff=0:
    이미 렌더된 VRAM을 캡처하는 상태라 canvas-hijack 신뢰 조건을 만족하지 않는다.
  - `0xA34D18` ROM 파일 패치는 loadstate 뒤 `dumpmem 0x08A34D18`에서 정상 반영됨을 확인했다. 따라서 문제는
    ROM 패치 불능이 아니라, 대사 생성 직전 state/nav가 아직 독립 재현되지 않은 것이다.
  - `part2_3p_surrender_confirm_fine/state_000_before_a.ss0`는 단독 loadstate 후 A hold/release replay에서
    저장된 `014_after_f20` 중간 메시지로 재진입하지 못하고 HUD 전환으로 빠진다. 이 state는 canvas 후보로
    승격 금지. fresh-nav 또는 재트리거 가능한 직전 state를 새로 확보해야 한다.
  - `89b` 캡처의 실제 런타임 read는 watch log상 `0x08A34D18`이다. scene_catalog는 기존에 공통
    `0xEFD8A4` 버킷만 연결하고 있었으므로 `g_00A34D18`~`g_00A34DB0`을 89b에 수동 보정했다.
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

### 2026-06-23 (續3): Part1 대사 = 커맨드 스트림(opcode 0x19) — 런타임 트레이싱으로 RE + repoint 완료

> 사용자 "옵션1: mGBA 소스 빌드해서 디버거 고쳐줘". mGBA 0.10.5 소스를 클론해 디버거 구동을 읽었더니
> **디버거는 원래 정상**이었음(이전 "breakpoint/watchpoint 사망" 결론은 **테스트 주소가 그 프레임 창에서
> 실행 안 된 false-negative**). execution breakpoint·loadstate 후 breakpoint 모두 작동 확인(0x08337382에서
> 7352히트). watchpoint만 loadstate가 메모리 shim을 제거해 미발화(breakpoint는 step-mode 경로라 무관).

**런타임 트레이싱(작동하는 디버거)**:
- 텍스트 ptr store `0x08B1299C str r4,[r6,#0x20]`에 breakpoint. 작전룸 savestate(base_a)에서 캐서린
  메뉴 이동(Down/Up) → store가 **r4=메시지 주소** 캡처: `0x08DF5D60`, `0x08DF612C`, `0x08DF6274`.
- 그 포인터들이 ROM 어디 있나 스캔 → `0xDF7A9C`, `0xDF7C6C`, `0xDF7D8C`. 그 앞 워드 = **`0x00000019`**.

**구조 = 커맨드 스트림**: Part1 대사는 Part2식 포인터 배열이 아니라, 0xD8~0xE0 영역의 **커맨드 인터프리터**
스크립트다. `0x19`(show-message) opcode 뒤 4바이트가 메시지 텍스트 포인터. (다른 opcode: 0x22/0x12/0x38/
0x39/0x04 + 핸들러 코드포인터 0x08B19355 등). 즉 메시지는 **0x19 뒤 포인터로 개별 참조** → repoint 가능.

**스캔 결과**: `0x19 + ptr(0x08B80000~0x08E10000)` = **1805 메시지**. 단어붙음 239건 중 **224건 커버**
(154 메시지), 150/154 단일포인터, 헤더갭≤16(struct아님)·decompose 154/154. 디코드 = 실제 캐서린 대사.

**구현/결과**: `dialogue_repoint.scan_command_messages` + `extra_messages` 파라미터(기존 가드 재사용 +
과확장 span 가드). Part1+2 합쳐 **357 메시지/403 라인 단어붙음 해소**(잔여 244→85). ROM 직접 무결성
게이트(qa_repoint_integrity, extra 포함) byte-identical PASS. 잔여 85 = 0xB8/0xEC 비-0x19 영역 +
merged/wide/multi-ptr/과확장 skip.

**하네스 사실**: tools/mgba_lua.c(Lua 임베딩)는 컴파일되나 스크립트 top-level 실행 트리거 미발견 → 보류.
디버거는 tools/mgba_harness.c(/tmp/mgbah_dbg = break에 hasBreakpoints 진단 추가본)로 충분.

### 2026-06-23 (續4): Part1 repoint 플레이테스트 — savestate 검증 한계 진단

신 빌드(08d50127) 플레이테스트를 codex 전체장면 시스템(screen_checkpoints.json)으로 시도.
**작동하는 디버거**(break 정상)로 검증:

- **메커니즘 확증**: 작전룸(base_a)에서 메뉴 이동(신규 트리거) → store(0x8B1299C)가 커맨드-스트림
  포인터 캡처(0xDF5D60/0xDF612C/0xDF6274/0xDF5E10/0xDF6418). **게임이 0x19 커맨드 포인터를 읽어
  메시지를 로드함**을 인게임 확인. 재배치 메시지면 갱신된 포인터(0xA4xxxx)를 읽게 됨(무결성 게이트로 보장).
- **savestate 검증 한계(중요)**: scene_19a2(메시지 0xD965DC=재배치)·battle savestate를 신 빌드에 로드해도
  대사가 **단어붙음으로 보임**. 원인 = pre-repoint savestate의 ① **캐시된 구 스크립트 상태**(RAM이 구
  포인터 0xD965DC=in-place 죽은 사본을 가리킴, advance해도 그걸 읽음) ② **구 폰트 VRAM 캐시**(신 텍스트
  렌더 시 □ 글리프 누락). 진단 근거: 0xD96607('여기까지 온 당신이라면 그 정도는', override 공백有)이
  메시지 0xD965DC(재배치)인데 savestate에선 단어붙음 → 캐시된 구 포인터 사용 확인.
  → **repoint 버그 아님. pre-repoint savestate는 repoint 콘텐츠를 시각검증 불가.** 향후 repoint 검증엔
  fresh-boot 네비 또는 post-repoint savestate 필요.
- **결론**: repoint 정확성은 ROM 직접 무결성 게이트(byte-identical, 권위) + 메커니즘 확증(store가
  커맨드포인터 읽음) + 디코드 검증(재배치=실제 un-jam 한글)으로 증명됨. 클린 시각 확인은 실기/에뮬
  **신규 플레이**에서 Part1 캠페인 미션 진입 시 가능(savestate 불가).

### 2026-06-23 (續5): Part1 repoint 인게임 검증 — fresh-boot 풀 네비 신규 트리거 (성공)

續4의 savestate 한계를 fresh-boot로 우회. **재현 가능한 네비**(harness press=keys K/frames6/keys0/frames N):
```
frames 480; A(200); START(200); A(240); START(240)   # Part1 타이틀
A(240); A(200); A(200)                                 # 새게임→이름 그리드
A(80)x3; START(120)                                    # 'AAA' 입력→확인
A(120) ...                                             # 캐서린 인트로 대사 진행
```
- **신규 0x19 트리거**: 인트로 대사 진행 중 store(0x8B1299C) r4=**0x08A446DC**(재배치 여유공간) 캡처.
  = 게임이 갱신된 커맨드-스트림 포인터를 따라 재배치본 로드(인게임 확증). 0xA446DC=메시지 0xDF8E6C 재배치.
- **디코드 대조**: 0xA446DC(읽힌 곳)="레드스타의 사령관,캐서린이에요"(un-jam) vs 0xDF8E6C(죽은 사본,
  안 읽힘)="레드스타의사령관캐서린이에요"(단어붙음). 시각: 이름그리드/인트로 대사 모두 깨끗한 공백 렌더.
- **교훈**: repoint 인게임 검증 = **fresh-boot 네비 + store 0x8B1299C로 r4 캡처**(재배치=0xA3D~0xB0).
  savestate는 캐시된 구 포인터라 불가. 이름입력은 그리드에서 A로 글자선택 후 START 확인.

---
## [2026-06-24] A2 맵선택 리스트 렌더러(4번째) RE + 공백 ASM hook

**렌더러 식별(watchaddr trace)**: 맵 이름(0x08A2CC3C "소라 마메 섬" 등)을 읽는 PC를
`watchaddr 08A2CC40 r`로 추적 → 파서 **0x0831Bxxx**, glyph는 공유 A3 hook(0x08F30284) 호출.
즉 313/B11/MODE SELECT(0x8314xxx) 외 **4번째 텍스트 렌더러는 0x831Bxxx**.

**파서 루프(0x0831BCFC~0x0831BD1C, Thumb)**:
- r4=문자열 포인터, r7=출력 셀 오프셋(+2/글리프), r8=베이스. 매 iter `ldrh`로 2바이트 코드 읽어
  0x831bbdc(→0x838c224 글리프캐시writer, r3=상태 0x03005D60)로 렌더, r4+=2, r7+=2, [r4]!=0 loop.
- 출력위치 r1 = [0x358+r8] + r7. 0x831BD10 = `bl 0x831bbdc`(렌더 호출 사이트).
- **공백 미처리**: 0x20(ASCII space)을 2바이트 코드의 일부로 오독 → 정렬 붕괴.

**공백 코드 형식**: 정상 맵명은 SJIS 전각공백 **0x8140**(bytes 81 40, high/low) 사용 → 렌더러가
2바이트 코드로 정상(빈칸). 0x8140은 한글예약범위(0x8840~0xE2A7) 밖 → A3 hook이 non-Korean
경로로 원본 0x8140 글리프(빈칸) 렌더.

**hook(PART2_HOOK_SPACE_A2CC, 0x08F30400)**: 루프top 0x0831BCFC 트램폴린. [r4]==0x20이면
코드 0x8140을 리터럴(hook 내 bytes 81 40)로 가리켜 렌더(r0=&literal via adr), r4-=1 후 0x831BD10
복귀(0x831BD14 +2로 space+1 정렬). 비공백이면 원본 4명령(movs/lsls/add r8/ldrh) 재현 후 0x831BD04 복귀.
far-call(0xF30400→0x831bbdc ~7MB>±4MB) 회피: 직접 bl 대신 원본 bl 사이트(0x831BD10)로 복귀.

---
## [2026-06-24] A1b 대사 화자명 박스(コシゲ) 정밀 조사 — 글리프 인덱스 렌더 확정

80c 인물 프로필 화면 좌상단 이름창에 가타카나 コシゲ(청록색) 렌더. 조사 결과:
- **OBJ 아님**: 명패 위치 스프라이트(spr20~29 @temp/koshige/oam.bin)는 아이콘(▼/★/✶)·값. コシゲ는 **BG 텍스트**.
- **CO 이름 OBJ 테이블 밖**: 0x81BE68(19 CO + 반복, A1 처리분)엔 コシゲ 없음(19 CO만).
- **SJIS/reserved 문자열 없음**: コシゲ(8358 8356 8052)·반각(BA BC B9 DE)·reserved-code 전부 ROM 미발견.
- **프로필 텍스트는 별개**: コシゲ 프로필 @0xA2B3FF("실력을 호크에게 인정받았다. 좋아함 고기 싫어함 채소...")는
  한글 번역됨(텍스트 블록). 이름은 이 블록에 없음 → **캐릭터ID별 글리프-인덱스 배열로 별도 렌더**.
- **결론**: コシゲ는 글리프 인덱스 렌더(프로필 struct의 name 필드 = 글리프 idx 배열 추정). 인덱스 테이블 위치
  확정엔 런타임 트레이스(BG 글리프캐시 write PC 역추적 또는 프로필 struct xref) 필요 — prior 세션도 동일 벽.
- **우선순위**: 기반게임差(외부 USA판=라틴이름이라 비대칭) + 다세션 깊은 RE → 보류(codex: "보류 사유이지 해결
  판정 사유 아님"). 다음 단계: state_21 로드 → 명패 BG tilemap 좌표/타일 덤프 → 그 타일 write watchpoint →
  렌더러 PC → 글리프 idx 배열(=name 테이블) 역추적 → Korean idx로 치환.

---
## [2026-06-24] A1b 화자명 박스 — 렌더 메커니즘 완전 RE (돌파, prior 세션 벽 통과)

80c 인물 프로필 이름창(コシゲ 등 가타카나) 렌더 메커니즘을 런타임 트레이스로 완전 해독.

**핵심 돌파 1 — 재렌더 경로**: 80c 프로필은 **RIGHT/LEFT로 캐릭터 사이클**(コシゲ↔ドミノ…) → 이름 재렌더.
savestate frozen-VRAM 우회 가능(MGBADriver press RIGHT, 이름창 crop diff 2537).

**핵심 돌파 2 — 렌더러 = A3 글리프 hook(0x08F30280)**: watchaddr(06000800 write)로 PC=0x08F302EC,
lr=0x0831BBED(A3 파서). 즉 **이름창은 대사와 동일한 A3 hook으로 렌더**. hook 디스어셈(capstone):
```
08F30280 ldrb r4,[r0]      ; 문자열ptr r0에서 high byte
08F30282 ldrb r1,[r0,#1]   ; low byte → code=(r4<<8)|r1
08F3028A cmp r1,#0x3f; bls fallback   ; 제어/단일바이트 → 원본 FONT
08F30290 ldr =0x8840; blo fallback    ; code<0x8840 → 원본 FONT(가타카나!)
08F30296 ldr =0xE2A7; bhi fallback    ; code>0xE2A7 → 원본 FONT
08F3029C 테이블 0x08F20000~0x08F243A4 6B엔트리 검색(code→top/bot glyph idx)
08F302C6 KOR_BASE=0x08F00000 + idx*0x20 → BG VRAM copy(0x302CC~0x302EC stm)
```
→ **예약코드 0x8840~0xE2A7 = 한글**(테이블→KOR_BASE), 그 외 = FONT_BASE 가타카나 폴백.
프로필 본문(한글)은 한글경로(0x302EC), 이름(가타카나)은 FONT 폴백.

**핵심 돌파 3 — 캐릭터 이름 테이블 = 0x80591C**(원본 ROM): SJIS 가타카나 이름 연접
'キャサリン ョウマ ホイップ ビーク クチヨ アスカ グルモ ボテト ドミノ ヘズ'(+0x805440 동일). A1의 CO OBJ
테이블(0x81BE68)과 **별개 메커니즘**(SJIS 문자열, A3 hook 렌더). ドミノ는 0x80516A/0x80591C 등 다수.

**A1b 수정 경로(확정)**: 이름 테이블(0x80591C 계열)의 가타카나 이름을 **한글 예약코드로 인코딩** →
A3 hook이 자동 한글 렌더(대사와 동일 인프라). build_korean_full의 예약코드+테이블+글리프 체계 재사용.
잔여: ①state_21 캐릭터(コシゲ, 0x80591C 미발견 — 별도 story 테이블 가능성) 정확 소스 = A3 파서
(0x0831BBDC) r0 추적 ②이름 테이블 전수 한글 readings 인코딩 + slot fit ③fresh-render 검증.
기반게임差(외부 USA판=라틴이름)지만 메커니즘 확보로 한글화 가능(보류→실행가능 격상).

---
## [2026-06-24] A1b 최종 결론 — 화자명은 이미 한글(A1 완료), コシゲ는 stale VRAM 오탐

런타임 트레이스 + 전수 디코드로 A1b "이름테이블 한글 인코딩"의 진실을 규명:

**핵심 정정(워크플로 src 추정 뒤집음)**: 이름창은 SJIS 문자열도, save/RAM 상주도 아니다.
**OBJ LZ77 그래픽**이다 — 이름 글리프는 프리베이크 타일(코드의 문자열 아님)이라 ROM에서 'コシゲ'
바이트검색이 0건이었던 것.

**렌더 메커니즘(확정)**:
- 이름창 = OBJ 스프라이트(panel rows5-6, y40, pal8, tiles 0x2ac~0x2b4=6자 8x16).
- 글리프 소스 = **CO 이름 OBJ 테이블 0x81BE68**(stride 0x44, 24엔트리=19 distinct 슬롯, A1 도메인).
  각 엔트리 첫워드 = LZ77 그래픽 포인터(0x08452650~0x0845357C).
- 캐릭터별 슬롯 디코드 = **BIOS SWI 0x11**(LZ77UnCompReadNormalWrite8bit, wrapper 0x0838B450) →
  OBJ VRAM. 호출자 0x08311D1D. watchaddr 확증: r0=슬롯ptr, r1=OBJ VRAM dest.
- 슬롯 인덱싱: 캐릭터 ID → 테이블 인덱스 → 슬롯ptr. コシゲ(state_21)=인덱스[11]=0x08453004.

**A1b = 오탐(stale VRAM)**:
- state_21 savestate는 **구 ROM(A1 번역 전) 캡처** → VRAM에 가타카나 コシゲ 잔상. 새 ROM 로드해도
  VRAM은 stale(재렌더 전까지 구 글리프).
- LEFT→RIGHT로 **재렌더** 시 새 ROM에서 디코드 → **'콩'(한글)** 표시 + 프로필도 완전 한글
  ("블랙홀군 최강...인정받았다", stale의 '인정받이????' 사라짐). temp/koshige/rerendered_3x.png 확증.
- 전수검증: 0x81BE68의 **19 distinct 슬롯 전부 출력≠원본(=A1 한글화됨)**, 미번역 가타카나 0개.
  렌더: 캐서린/도미노/맥스/호이프/빌리/키쿠치요/아스카/이글/모프/헬보우즈/콩/캣/스네이크/호크/하치/이반/한나/야마모토.

**결론**: 화자명 테이블은 **이미 A1(patch_part2_domino_co_name_obj)이 한글 인코딩 완료**. 추가 작업 불요.
교훈(재확인): savestate 캡처는 provenance OK여도 **VRAM stale 가능** → OBJ/BG 변경의 잔존 판정은
반드시 **fresh-render 재캡처**로 확증(capture_freshrender). state_21류 구 savestate를 결함증거로 쓰지 말 것.

---
## [2026-06-24] codex 세션리뷰 반영 — A4 ASCII 잔존 provenance + A1b 옛 가설 폐기

### A4 EXIT/NO/UNIT ASCII 잔존 주소별 비표시 근거(codex 요청)
- **EXIT** @0x17FF27, @0x70369F: 컨텍스트 `<19>?_9..EXIT5IM4..` = 비-텍스트 바이너리(압축/코드 블록 내 우연
  ASCII). 포인터 참조 0건 → 텍스트 렌더 경로 없음. 미표시.
- **NO** @0x1787F, @0xFC70F: `JNL..N[N1NO·G`, `%5$SK)NO/*` = 압축/코드 데이터 중간의 2글자 우연일치. 단어 아님.
- **UNIT** @0x4CA3B4: `UNIT  C0  C1····PSQ(%1d)····ASQ(%1d)` = **printf 디버그 포맷**(%1d 포맷지정자). 참조는
  있으나 디버그 오버레이용(정상 플레이 미표시). 플레이어 대면 UI 아님.
- 결론: 표시되는 영문 UI 잔존 0(qa_ascii 큐레이션 0 + scene audit critical 0과 정합). 위 3종은 코드/압축/디버그.

### A1b 옛 가설 폐기(DEPRECATED) 명시
- 이 문서 위쪽 A1b 서술 중 **(a) BG 글리프-인덱스 렌더 가설**, **(b) A3 hook(0x08F30280) 텍스트 렌더 가설**,
  **(c) 이름테이블 0x80591C / save·RAM 상주 가설**은 전부 **폐기(DEPRECATED)**.
- **최종 확정 결론(권위)**: 화자명 = **OBJ LZ77 그래픽**(CO 이름 OBJ 테이블 0x81BE68, SWI 0x11 디코드, 19 슬롯).
  A1(patch_part2_domino_co_name_obj)이 전부 한글화 완료. state_21 'コシゲ'는 구 ROM savestate VRAM 잔상(오탐).
  나머지 옛 서술은 추적 과정 기록일 뿐 결론 아님.

---
## [2026-06-25] A5c 단어붙음 대량 해소 — jam 102→19 (81% 감소, ROM 확장 불요)

사용자 제안(슬롯 강제확장)에서 출발했으나, 근본은 **free space 부족이 아니라 repoint coverage/granularity**였음.
5개 기법 결합으로 free space 내(795KB 중 48KB 사용) 해결:

1. **span_of terminator 세분화**(dialogue_repoint.py): 0x19 메시지는 sparse라 'next 메시지 시작'까지 span이
   다음 0x19 미참조 메시지들까지 grab → 527라인 거대블록·거짓 merged. SJIS 본문엔 0x00 없으므로 **첫 0x00=실제
   종단**. min(next, terminator)로 한정 → merged 오탐 제거(merged-skip 13→6).
2. **CSV-source 확장**(_rp_dlg): 비-B팀 라인은 빌드 의도값(WRITE_LOG ko 공백본)을 repoint 소스로(override가
   stale-jammed이거나 없을 때). B팀은 override 권위 유지.
3. **trusted_message_start 자동 coverage**: 포인터 인덱스(array)로 jammed 라인의 메시지시작(직전 0x00 뒤)이
   **단일 포인터**(포인터테이블 엔트리)면 _rp_extra 추가 → 0x19/0xA357B4 미커버 메시지(포인터테이블 참조분) 재배치.
4. **in-place-jam 감지**(_rp_inplace_jammed): script/override가 CSV 공백본을 잼으로 덮은 경우 source는 fit이라도
   in-place ROM 바이트가 공백제거판이면 _rp_fit_level=6 강제 → 재배치로 공백 복원. script row 다수 해소.
5. **비-B팀 잼-override skip**: dialogue-override가 import 공백본의 같은번역 공백제거판이면 skip(CSV 공백본 살림).
   import-* 전 종류 + 구두점 무시 비교.

결과: repoint 369→448 msgs, 504 lines. jam 102→19. drift 0, integrity PASS, scene critical 0, dist PASS.
재배치 인게임 확증(실 바이트 디코드): '매크로 랜드 침공 작전은,/특기인 해군으로.../지상 유닛에 대한 공격력' 등 공백 복원.
ROM f09d111f. B3 재스탬프·scene 70 재캡처·dist BPS/IPS 재생성.

**잔여 19**(genuine 한계): 메시지가 0x19 sub-start 포함(line이 sub-entry로 매핑, NOT_IN_MAN 10) / 무포인터
mid-fragment 5 / 다중포인터 3 / merged 실중복 1. 일부는 acceptable(bracket-space '그건, 「'→'그건「'). 게이트 정직 보고.

---
## [2026-06-25] A5c hardening — codex/agy 적대 리뷰 4개 우려 반영

A5c 단어붙음 해소(102→19) 직후 codex/agy 리뷰가 blocker급 우려 제기 → 전부 반영(ROM 84ec5fde):

1. **span_of truncation(codex#1, blocker)**: 라인 extent가 메시지 종단(0x00 run)까지 삼킨 patch_script_row류는
   fixed_bytes 교체 시 terminator 손실 → run-off corrupt. → dialogue_repoint.py에 **terminator 보존 검증**
   (원본 0x00 종단인데 new_msg가 아니면 skip_no_terminator). qa_repoint_integrity로 전수 0 corrupt 확증.
2. **override-skip 편집 되돌림(codex#2,agy#2)**: 비-B팀 잼 override skip이 acceptable 보조용언(놀아줘/가버렸네)을
   CSV로 되돌릴 위험 → **_ov_acceptable_aux**(앞=용언활용+뒤=보조용언)면 override 존중(skip 안 함).
3. **trusted 포인터 우연일치(codex#3,agy#1)**: ROM 전체 정렬워드를 포인터 후보로 → 코드영역 우연일치로 오염 위험.
   → 포인터 OFFSET을 **대사/스크립트 영역(0xA00000~0xE10000)으로 제한**(코드영역 제외).
4. **QA가 무회귀 증명 못함(codex#4)**: qa_spacing은 relocated를 intended로 간주(free-space 미follow). →
   **tools/qa_repoint_integrity.py 갱신**: manifest new_addr를 **포인터로 독립 확인** + free-space 블롭 실디코드
   (terminator/garbage/공백). 450 재배치 전수 PASS(문제 0).

최종 게이트: integrity·B팀drift0·csv0·scene entrypoint·residual critical0·**qa_repoint_integrity 0**·dist PASS.
jam 102→19 유지. repoint 450msgs/510lines. 70 scene 재캡처·B3 재스탬프·dist BPS/IPS 재생성.

---
## [2026-06-25] A5c hardening 2차 — 고아 포인터 + terminal 검증 (codex/agy 2차 리뷰)

1차 hardening 후 codex/agy가 **mid-span 고아 포인터** 동일 지적(둘 다 독립 발견, 5 후보):
메시지 시작 외 **중간주소를 참조하는 별도 포인터**가 있으면 재배치 시 start만 갱신돼 중간 포인터가 구주소에
남음(고아) → 특정 경로가 구 in-place 슬롯/깨진 중간문자열 렌더. 반영:

- **고아 가드**(dialogue_repoint.py): 대사/스크립트 영역(0xA0-0xE1) 정렬 포인터 타깃 집합 구축 →
  메시지 span (msg, me) 내 임의 중간주소가 참조되면 bisect로 검출해 **재배치 skip**(skip_mid_ref).
- **terminator 보수화**: 원본이 **0x00 종단인 메시지만** 재배치(orig[me-1]==0 && new_msg 0x00 종단).
  비-0x00 종단(다음메시지까지 span)은 소비범위 불명 → skip.
- **qa_repoint_integrity 강화**: manifest new_addr를 ① ptr_off 정합 ② **구 span 고아 미참조** ③ terminator
  ④ **terminal-zero**(첫 0x00 이후 new_len까지 모두 0x00=텍스트가 종단 전 끝남) ⑤ garbage 전수 검증.
- **override-skip 투명성**(codex#5): skip되는 비-B팀 override 84건 → docs/reports/a5c_override_skip_conflicts.json.
  다수가 진짜 noun-phrase 잼(대공 전차/전투 헬기 등 CSV 복원이 옳음). 보조용언(놀아줘류)은 _ov_acceptable_aux로 존중.

결과: repoint 445msgs/501lines. **고아 0·corrupt 0** 게이트 확증. jam 102→21(79%). 빌드 결정적(006b12cd, 2회 동일).
잔여 21=구조한계(0x19 sub-start/무·다중포인터/merged/고아skip/script). 70 scene 재캡처·B3 재스탬프·dist 재생성.
**follow-up(codex#4)**: trusted-start 재배치분 mGBA 실캡처는 잔여 검증(게이트가 바이트는 전수 확증).

---
## [2026-06-25] ★단어붙음의 진짜 원인 — 반각공백(0x20) 미렌더 (실캡처 검증으로 발견)

**발견 경위**: A5c 재배치를 fresh-render(key-advance, stale savestate 아님)로 5배 확대 검증 중,
같은 대사 박스에서 `0xDFF1CA "캐서린이[전각0x8140]없는…"`은 넓은 gap 렌더, `0xDFF1F1 "이[반각0x20]몸의…"`는
공백 완전 스킵(잼) 확인. 바이트 대조로 확정.

**메커니즘**: 대사 렌더러가 **글리프 폭 단위로 커서 전진** → 반각공백(0x20, ASCII)은 글리프가 없어 전진 0 = 화면 잼.
일본어 원본이 공백에 전각(0x8140)을 쓰므로 렌더러는 0x8140만 공백으로 인식(A2 맵선택 '??'와 동일).

**규모**: 출하 ROM 바이트 기준 **5976개 대사가 0x20 사용→화면 단어붙음**(qa_spacing은 바이트만 봐서, savestate
캡처는 구 ROM VRAM 보존이라 둘 다 못 잡음). **그동안 싸워온 단어붙음의 진짜 원인**.

**stale VRAM 확정(codex #4)**: savestate scene 캡처를 orig ROM(일본어)으로 로드해도 동일 한글 렌더 →
savestate VRAM이 만들어진 ROM의 화면을 보존, 1-frame refresh로 현 ROM 미반영. fresh-render(key-advance)만 신뢰.

**Phase 1 수정(구현)**:
- `_fit_candidates` 전각 우선 재정렬(0~5 전각 / 6~9 반각 / 10~12 공백제거)
- `encode_full_fidelity` 전각(0x8140)화
- 재배치 블롭의 **interior 0x20→0x8140 변환**(content 사이만; trailing 패딩·제어 앞은 유지; 2바이트 코드 lead 건너뜀)
- `min_level=1`(전각-full 미적합이면 재배치=부호+전각 완전충실)
- 결과: **재배치 1958개 완전 정상화(잼 0)**, 렌더잼 5976→4452, free 221KB/795KB, drift 0, qa_repoint PASS

**Phase 2 잔여(4452 비-재배치 in-place)**: 분석 결과 **무포인터 3105 / 단일 1224 / 다중 123**.
free space 574KB 여유 → **병목은 ROM 용량이 아니라 포인터**. 단일/다중(1347)은 재배치 커버리지 확장(fix_addrs
없어도 interior 변환이 잼 해소하므로 render-jam 메시지 relocate 허용)으로 기존 free space에 해결 가능.
무포인터 3105는 서브메시지(순차참조)/미참조 추정 → 부모 메시지 재배치 또는 포인터 RE 필요.

부작용: 부호소실 1733(비-재배치가 전각 fit 위해 부호 떨굼). 트레이드오프=가독 공백 > 부호(사용자 승인).

---
## [2026-06-25] Phase 2a — render-jam 단일포인터 coverage 확장: 5976→970 (84%)

Phase 1 후 잔여 측정이 **재배치 메시지의 stale in-place 라인을 오집계**(4402)함을 발견 → 재배치 범위
[msg, msg+old_len) 제외하면 정확 잔여는 **970**. 즉 Phase1만으로도 이미 대폭 해소.

Phase 2a: dialogue_repoint에 **render-jam 허용**(fixable 라인 없어도 content 사이 0x20 있으면 재배치 →
interior 변환이 해소) + build에 **단일포인터 render-jam 메시지 coverage**(repoint_renderjam_starts).
→ 재배치 2667개, 렌더잼 **5976→970**, free 283KB/795KB, drift0, qa_repoint PASS(2667 문제0).

잔여 970 포인터 분석: **무포인터 587 / 단일 246 / 다중 137**. free space 충분(병목=포인터):
- 다중 137: 다중포인터 재배치 지원(전 site 갱신)으로 해결 가능
- 단일 246: decompose/struct 가드로 skip 추정 — 케이스 조사
- 무포인터 587: 서브메시지(순차참조)/미참조 — 부모 메시지 재배치 또는 포인터 RE 필요
ROM 확장은 space가 아니라 무포인터 587의 포인터 문제라 직접 해결 안 됨(free 충분).

---
## [2026-06-25] Phase 2b 종합 — render-jam 5976→792 (87%), 하드 잔여 특성화

Phase 2a(단일포인터) 후 추가 해소:
- **다중포인터 재배치 지원**(dialogue_repoint): 1회 재배치+전 site 갱신(고아 방지) → 970→850
- **B팀 render-jam 전각화 허용**: 0x20→0x8140은 렌더링 수정(텍스트 불변)이라 B팀 제약상 허용,
  재배치 conversion이 공백만 전각화 → 850→792, **B팀 drift 0 유지**(텍스트 보존 검증)
- 재배치 2829개, free 295KB/795KB, qa_repoint PASS, integrity PASS

**시도했으나 채택 안 함**: 페이지 인식 span_of(연속 페이지 포함) → qa_repoint_integrity FAIL(17 문제)
+ 효과 미미(24개) → revert. 연속 페이지는 포함 시 merged/orphan 가드에 걸림.

**하드 잔여 792 특성화**(`tools/qa_render_jam.py` 게이트):
- **무포인터 576**: 멀티페이지 연속 페이지(0x00 경계 뒤, 부모 포인터만 존재). 페이지인식 span이 가드 충돌로
  안전 해소 불가. 부모 메시지 재배치 시 0x00 종단/고아 가드와 충돌.
- **guard-skip 206**: skip_merged 129(중복노출 방지)·skip_mid_ref 67(고아 방지)·기타 10. 회귀 방지 가드라
  완화는 회귀 위험.
- 미처리 10: coverage 엣지케이스.
→ 792는 **작동하는 87% 수정을 깨지 않는 안전 floor**. 추가 해소는 멀티페이지 구조 RE + 가드 정교화 필요.

부작용 부호소실 1733: 비재배치 메시지가 전각 fit 위해 부호 떨굼(가독>부호, 승인된 트레이드오프).

---
## [2026-06-25] Phase 2c — 멀티페이지 중간 0x00 가설 반증 + orphan 가드 정교화

**검증 결론**: `0xDFC248` 사례는 빌드가 중간에 spurious `0x00`을 넣은 것이 아니다.
원본/출하/재빌드 모두 `0xDFC248..0xDFC430` 구간의 `0x00`은 종단 `0xDFC430` 1개뿐이다.
`0xDFC274`는 출하 ROM에서 `0x7E`이며, 중간 truncation 증거 없음. `0x00`은 대사 종료,
`0x6B`는 페이지 전환/입력대기 제어로 보존해야 한다.

실제 원인: `skip_mid_ref`가 대사/스크립트 영역 정렬워드의 **모든 pointer-shaped 값**을 고아 포인터로
봤다. `0xDFC248`을 막은 값은 `0xC789BC -> 0xDFC2DA`였는데, `0xDFC2DA`는 라인 시작이 아니라 SJIS 본문
한가운데이며 `0xC7xxxx`는 추출 노이즈/데이터 영역이다. 즉 멀티페이지 부모 재배치가 맞지만, 고아 가드가
그래픽/압축 데이터의 우연 값을 과신해 막고 있었다.

**수정**:
- `dialogue_repoint.py`: 고아 포인터 가드를 `line_index` 라인 시작 또는 알려진 메시지 시작(`all_targets`)만
  차단하도록 정교화. 본문 중간 바이트를 가리키는 pointer-shaped 값은 고아 위험에서 제외.
- 동일 `(ptr_off,msg)`가 table/extra 양쪽에서 들어올 때 Python 3.12 정렬이 `_tbl=None/int` 비교로 실패하는
  빌드 블로커를 명시 key 정렬로 수정.
- `qa_repoint_integrity.py`: 빌드와 같은 entry-target 기준으로 orphan-mid-ref를 판정해, 실제 라인/메시지
  엔트리 고아만 FAIL 처리.

**결과(출하 빌드 SHA `71ab0d6a...`)**:
- `0xDFC248` 부모 메시지 재배치 성공: `new_addr=0xA82930`, old 492B → new 521B, 13라인,
  fixed `0xDFC28E/0xDFC2B9/0xDFC31E/0xDFC378/0xDFC3A1`.
- render-jam **792→718**. 재배치 **2829→2860**. `qa_repoint_integrity` PASS(2860, 문제 0),
  `qa_integrity_map` PASS, B팀 drift 0, `phase6_basic_test` PASS.
- 잔여 718 재분류: parent pointer continuation 241(`skip_merged` 206, `no_manifest` 23,
  `skip_ptr` 7, `skip_no_terminator` 4, `skip_decompose` 1), exact_ptr 1, no_parent_ptr 476.
  남은 주 병목은 중간 0x00이 아니라 **포인터 미식별 476 + merged/구조가드 241**이다.

---
## [2026-06-25] Part1 대사 파서 — 반각공백(0x20) 렌더 완전 RE + hook 주소

런타임 트레이스(mGBA 하네스 break/regs + capstone)로 Part1 대사 파서 완전 규명. state 베이스=0x03000E00.

**화면 위치 공식**: `위치(VRAM 타일맵) = [state+0x28](base) + [state+0x32](열)×2 + [state+0x33](행)×64`.
계산 함수 **0x08B11B80**(`adds r0,#0x32; ldrb; lsls #1; ldr [r2,#0x28]; adds r2,#0x33; ldrb; lsls #6`).
- **[state+0x32] = 열(화면 x)**. 글자당 0x8b12782에서 +1.
- **[state+0x33] = 행(화면 y)**. 줄바꿈 시 +1.
- **[state+0x34] = 글리프 타일인덱스**(저장위치, 글자당 +2=2타일). **위치 아님**(혼동 주의).
- [state+0x39] = render-one-char return 플래그(0=정상 1글자 후 return).

**render-one-char 함수(0x08B126F0~0x08B12798)**: 상위 루프가 글자당 1회 호출.
- 0x8b1271e `bl 0x8b11b80`→위치(**파서 실행 전** 계산, off-by-one 원인).
- 0x8b12728 `bl 0x8b12074`(파서 루프). 0x8b12758 render(0x8b1befc 글리프변환 + **0x8b12762** `adds r0,r4;
  adds r1,r5; bl 0x8b12640`(타일쓰기: tile=[state+0x34]|[state+0x2c], [r1]+[r1+0x40] 2타일)).
- 0x8b1277A~ 전진([state+0x20]+=2, [state+0x32]+=1, [state+0x34]+=2). 0x8b12792 return검사.

**파서 루프(0x08B12074)**: jump table 0x08B12098+(char-9)×4. 0x20엔트리=**0xB120F4**(원래 0x08B12144=
byte ptr만 +1=잼). content char(>0x77)는 0x8b12634에서 return 1.

**0x20 렌더 hook(완성, build_korean_full.py)**:
1. table 0xB120F4 → 0x08F30500: 다음=한글(0x88-0xE2)이면 [state+0x32]+1, 0x20 소비, 0x08B1207D 복귀.
2. render site **0x8b12764**(4정렬, _abs_tramp ldr[pc,#0] 요건) → 0x08F30540: 위치 [state+0x32] **재계산**
   (파서가 0x20 소비 후이므로 정확), 0x8b12640 호출, 0x8b1276A(adds r0,r4) replicate, 0x08B1276C 복귀.

---
## [2026-06-26] "무포인터 3건" 재조사 — 전부 포인터 존재(텍스트주소 검색의 함정)

이전에 "재배치할 포인터 0개=하드한계"로 본 3건은 **텍스트주소로 검색한 탓**이었다. 포인터는 **메시지 라인시작
(\n\t = 텍스트 -2/-4)**을 가리킨다:
- **0xEC312E**(라인 0xEC312C "지정일이..." VS설정도움말) → 도움말 포인터테이블 **0xEC2708**(18엔트리)@0xEC2714.
- **0xEC3246**(라인 0xEC3244 "같은 깃발을...") → **코드 인라인 LDR** @0xB71218 (0xB711C8 `ldr r6,[pc,#0x4c]`
  → 0xB12910 렌더호출, 단일 site라 literal 갱신 안전).
- **0xE0FF0C**(라인 0xE0FF08 "언제든지...") → **0x19 커맨드** @0xE1015C (scan_hi 0xE0→0xE2 확장으로 캐치).

**해소**: 0xE0FF08·0xEC3244는 extra_messages/scan으로 재배치(텍스트 보존=B팀 불변). 2/3 fixed.
**0xEC312E 잔존 사유**(잼): ① B팀 보호주소(텍스트 단축=제약위반, drift는 override 기준이라 미검출 — 단축 시도→
즉시 revert) ② visual_cells 51 > max_cells 50(전각 재배치 시 58 half-cell, 단일라인 도움말박스 폭 초과 → 잘림 위험).
즉 포인터는 있으나 **B팀+폭** 이중 제약으로 재배치 불가. 동류 0xA2C378/0xA2C484/0xDFD082도 B팀+폭(51-52셀).

---
## [2026-06-26] D1 text metrics/preview canvas 재검증 사실

- **text metrics 권위**: Python 쪽 byte 길이/visual cell/2350 미수록 음절 판정은 `tools/text_metrics.py`가 정본이다.
  JS `encLen`은 `tools/scene_editor/static/app.js`의 UI 표시용 mirror이며, `tools/test_text_metrics.py`가 CSV/override/
  dialogue group 코퍼스 전체로 py↔js parity를 검증한다.
- **lint budget 권위**: `tools/lint_translation.py`의 byte-budget 판정은 빌드와 같은 `build_korean_full.encode_fit`을
  호출해야 한다. direct `script:*`는 found_texts 첫 조각 길이가 아니라 build direct span을 써야 false positive가 없다.
  `dialogue_overrides.json` overlay가 최종 권위이므로 CSV만 보는 lint는 stale/over-budget 오판을 만든다.
- **B팀 byte-budget 예외**: B팀 baseline 문장은 편집/드리프트 보호 대상이지 일반 lint 단축 대상이 아니다.
  B팀 주소의 byte-budget 문제는 `qa_bteam_drift.py`, repoint/fit 게이트, build overflow report가 보호한다.
- **part1_welcome canvas drift**: repoint 블롭은 새 빌드마다 배치가 움직일 수 있다. SHA `7e79670c…`에서는 welcome
  runtime command-stream text span이 `0x00A7AA56..0x00A7AA7A`(37B, 뒤 `0x6B/0x0A` 보존)이다.
  이전 `0x00A7AB56`은 같은 블롭의 뒤쪽 `"1대 대전"` 안내문으로 이동해 payload diff 0이 된다. 그러므로 canvas는
  "캡처가 nonblank"가 아니라 `tools/verify_preview_canvases.py`의 A/B payload pixel diff로만 ready 판정한다.
  `tools/preview_capture.py`는 이 취약성을 줄이기 위해 `temp/repoint_manifest.json`에서 `msg=0xDF8E14`,
  `fixed=0xDF8E16`, `new_addr`를 찾아 `new_addr + 2`를 현재 slot으로 계산하고, manifest가 없을 때만
  레지스트리 fallback slot을 쓴다.
- **scene screenshot provenance**: `verify_scene_editor_cdp.py`의 stale_screenshot failure는 화면 렌더 오류가 아니라
  `temp/scene_screenshots/<checkpoint>_patched/provenance.json`의 `rom_sha256` 불일치다. ROM SHA 변경 후에는
  `tools/capture_scene_screenshots.py --force`로 카탈로그 참조 screenshot/extra를 재캡처하고
  `tools/audit_scene_entrypoints.py --strict` stale 0을 먼저 만든 뒤 CDP 검증을 돌린다.
- **review-only bucket 편집 정책**: `98_extraction_noise_review`는 화면에 연결하지 않는 저신뢰 추출 후보 보관소다.
  `scene_editor/server.py`는 이 scene 전체를 차단하지 않고, 현재 값이 build renderer에서 보존되지 않는
  unsupported/error member만 non-editable로 내린다. 따라서 B팀 실제 문장 `0x00DF3AFA`처럼 렌더 가능한 문장은
  review bucket 안에서도 `editable:true`와 B팀 경고를 유지한다. 노이즈 sentinel은 빌더에서 더 강하게 막는다:
  `문자 깨짐`/`[문자 깨짐]`/`해독·번역·판독 불가(문자 깨짐)`은 `PLACEHOLDER_KO` skip 대상이며,
  `0x009B2DFA` 포함 고주소 8행의 `：！｀￣ヾ〃仝々浦〆〇〇` 패턴은 원본 바이트를 보존한다.

---
## [2026-06-26] `ADDRESS_TEXT_OVERRIDES` vs `dialogue_overrides` 우선순위 fresh 깨짐

- **재현**: stale savestate가 아니라 cold boot 기반 fresh route가 필요하다.
  `auto_playthrough.py --fresh --prenav frames480,A,START,A,START,A,A,A,A,A,A,START ...` 계열로
  Part1 새 게임/이름 입력 후 작전룸에 들어가면 하단 대사창 첫 설명이 재생성된다.
- **증상**: 수정 전 ROM에서는 `0x00DF5E12` 계열 첫 설명 화면과, 같은 fresh route 후반 `0x00D8F3DE`
  전투 튜토리얼 화면 하단에 점/가비지 글리프가 섞였다. 같은 state에서 기다려도 사라지지 않아 typewriter
  지연이 아니며, command-stream 렌더 결과 자체가 감염된 것이다.
- **주소/데이터 경계**: `ADDRESS_TEXT_OVERRIDES`에는 이미 Part1 작전룸/튜토리얼용 hand-safe 짧은 fragment가
  들어 있었지만, 빌드 후반 `dialogue_overrides.json` 최종 overlay가 같은 주소를 다시 긴 편집기/B팀 권위문으로
  덮어썼다. CSV/정적 fit만 확인하면 이 우선순위 문제를 놓친다.
- **해결 원칙**: `ADDRESS_TEXT_OVERRIDES`는 빌드 안전 권위다. final editor overlay가 이 주소들을 덮으면
  과거에 화면 검증으로 만든 tight command-stream fragment가 무효화되므로, 빌드는 `a in ADDRESS_TEXT_OVERRIDES`
  인 경우 dialogue overlay를 skip한다. 누락됐던 `0xDF5E12`/`0xDF5E35`는 `코스모랜드 설명을`/`해 줄게.`로
  추가했다. `dialogue_overrides.json`/`bteam_baseline.json` 권위문은 변경하지 않는다.
- **주의**: `0xD81C24` 맵 디자인 도움말 조사 중 발견됐지만, 이 결함은 `0xD81C24`가 아니라 Part1 작전룸 intro row다.
  D81 watch hit 0 결과와 혼동하지 않는다.

---
## [2026-06-26] Part1 모드 메뉴 OBJ 라벨과 반투명 도움말 충돌

- **관찰**: Part1 모드 선택/대전/통신 메뉴의 스크롤식 대형 OBJ 라벨은 원본에서도 하단 반투명 도움말 박스 뒤를
  지나간다. 따라서 "라벨이 도움말 뒤에 일부 보인다" 자체는 엔진 구조상 버그가 아니다.
  원본 비교 contact는 `docs/screenshots/part1_menu_label_shrink_2026-06-26/original_overlap_reference_contact.png`.
- **실제 결함**: 한글 패치의 `make_part1_option_block()`은 짧은 라벨을 원본 일본어 폭에 맞추려 `target_min_w`로
  nearest 확대했고, 긴 통신 항목도 128x32 option OBJ 안에서 큰 OkDanDan 글자로 렌더했다. 이 때문에 도움말 문장 위에
  진한 외곽선/획이 남아 원본보다 가독성이 나빠졌다.
- **수정 원칙**: OAM 위치나 도움말 박스 불투명도는 건드리지 않는다. 같은 라벨 OBJ가 선택/비선택/스크롤 위치에
  재사용되므로 위치별 특수 처리는 취약하다. 대신 소스 그래픽 자체를 Galmuri11-Bold 12px 이하 본문-only compact로
  줄이고, drop shadow/outline을 제거한다. 리뷰 후 `1카드 통신`/`멀티카드 통신` 원 표기는 compact 폰트에서
  96x16 bbox 안에 들어감을 확인해 보존했다.
- **회귀 기준**: `qa_visual_regions.py`는 모든 Part1 option block을 직접 검사한다. bbox는 최대 96x16, y1<=24,
  palette는 `{2}` 단색만 허용하고 검은 edge(15)는 0px이어야 한다. mGBA screen check는 도움말 ROI의
  매우 어두운 침범 픽셀을 mode/single/link 각각 60px 이하로 제한한다. 2026-06-26 리뷰 반영 후 기본 입력은
  구 `final_menu.ss0`가 아니라 coldboot fresh route이며, `--menu-state`는 debug-only 옵션이다.
- **검증 경로**: fresh route `frames480,A,START,A,START,A,A,A,A,A,A,START`에서 Part1 이름 입력 후 메뉴 state를
  얻고, 그 state에서 `DOWN,A`, `DOWN,DOWN,A`, `DOWN,DOWN,A,RIGHT/DOWN/UP`을 눌러 사용자 보고 화면 7종을
  재캡처했다. 수정 후 증거는
  `docs/screenshots/part1_menu_label_shrink_2026-06-26/fresh_final_routes_contact.png`와
  `docs/screenshots/part1_menu_label_shrink_2026-06-26/fresh_final_filmstrip.png`.
- **stale state 주의**: `temp/final_original_vs_final_20260615/final_menu.ss0` 계열처럼 구 ROM에서 만든
  savestate를 새 ROM에 로드하면 VRAM/text cache가 남아 Part1 single/link 하단 문장이 깨진 것처럼 보일 수 있다.
  현재 SHA `8a34a570…` coldboot fresh route의 `state_003.ss0`에서 만든 7-route contact에서는 해당 노이즈가
  재현되지 않는다. Part1 메뉴의 확정 결함은 large option OBJ 라벨의 도움말 침범이며, stale-state 대사 깨짐은
  현 ROM 결함 증거로 쓰지 않는다.

---
## [2026-06-26] 대사 에디터 그룹 member id와 dialogue_map id 불일치

- **증상**: :8780 대사 에디터의 `/api/groups`는 `data/dialogue_groups.json`의 member `id`를 그대로 반환했지만,
  `/api/line` 저장은 `data/dialogue_map.json`에서 같은 `id`를 찾았다. 두 파일의 id는 항상 동치가 아니며,
  `g_00DF5E12`에서는 그룹 member id `29423`이 dialogue_map의 인접 주소 `0x00DF5DF3`를 가리켰다.
- **위험**: 그룹 화면에서 저장하면 표시 중인 주소가 아니라 인접 line이 override될 수 있다. 특히
  `ADDRESS_TEXT_OVERRIDES` 보호 주소를 검증하는 과정에서 `0x00DF5E12` 대신 `0x00DF5DF3` override가 생기는 것을
  확인했고 즉시 제거했다.
- **해결**: `/api/groups` 응답을 address 기준으로 `dialogue_map.json` canonical line에 재동기화해 실제 id/slot/kind를
  내려준다. `/api/line`은 payload에 address가 있으면 address를 우선해 저장 대상을 찾고, 프런트는 group/list 양쪽에서
  `{id,address,ko}`를 전송한다. dry-run 저장을 추가해 보호 주소 차단을 데이터 변경 없이 검증할 수 있게 했다.

---
## [2026-06-26] Part1 single map list `??????` 스크린샷 triage

- **관찰**: `docs/screenshots/part1_menu_label_shrink_2026-06-26/fresh_final_routes_contact.png`의
  `single_map` 패널에는 맵 리스트 3행이 `??????`로 보인다. 한글 fallback처럼 보일 수 있으므로 별도 확인했다.
- **런타임 확인**: current SHA `8a34a570…`에서 같은 coldboot route로 `watchaddr 08DF8C2A 12 r`를 걸고
  Part1 대전→맵 선택에 진입하면 `0x08DF8C2A`가 144회 read-hit한다.
- **바이트 확인**: 당시 원본 ROM과 패치 ROM 모두 `0x00DF8C2A..0x00DF8C35`가
  `814881488148814881488148`(`？？？？？？`)으로 byte-identical이다.
  2026-06-27 Codex 재검증에서도 당시 output SHA
  `a4e98a93daf1f545f6224814b0c55d8e981f98ec16ccc3872c2f30831ec0489e`의 같은 범위가
  원본과 byte-identical임을 확인했고, `data/part1_single_map_question_watch_20260626.json`에
  `current_byte_recheck`로 보존했다.
- **시각 확인**: `docs/screenshots/part1_menu_label_shrink_2026-06-26/single_map_question_rows_crop_4x.png` crop에서 물음표 6개는
  서로 분리되어 보이며 글리프 겹침/타일 깨짐은 관측되지 않는다.
- **판정**: 이 화면의 `??????`는 패치가 만든 한글 렌더 fallback이나 비트맵 손상이 아니라, 원본의 `？`
  placeholder 데이터를 그대로 표시한 것이다. 잠금/unknown 맵명이라는 의미 해석은 추정으로만 둔다. 증거 요약은
  `data/part1_single_map_question_watch_20260626.json`.
- **검증**: 새 서버에서 `코스모랜드 설명을` 검색 시 `0x00DF5E12` member id는 `29424`로 보정되고,
  stale 문장 `당신에게는,코스모 랜드에 대해` 검색 hit는 0이다. `/api/line` dry-run 저장은
  `빌드 안전 ADDRESS_TEXT_OVERRIDES 보호 주소` 오류로 차단된다.

---
## [2026-06-27] Part1 single map list placeholder UX fix

- **변경 이유**: 위 triage의 원인 판정은 맞지만, 사용자 스크린샷에서는 `??????`가 깨진 텍스트처럼 보인다.
  따라서 원본 placeholder 보존 대신 현재 ROM에서 unknown/locked 맵명 표시를 `미공개`로 바꿨다.
- **실패한 표시 경로**: `0x00DF8C2A`에 일반 예약 한글 코드로 `미공개`를 직접 넣거나,
  compact kanji glyph 경로로 `基工開`를 넣으면 이 리스트 renderer에서 blank가 된다.
  `ヮ/ヵ/ヶ` 같은 작은 가나 후보도 원하는 한글 glyph로 안정적으로 나오지 않았다.
- **폐기한 경로**: 한때 source bytes를 `834b834d834f814081408140`
  (`ガギグ` + 전각공백 3개)로 바꾸고 `ガ/ギ/グ` glyph table entry를 `미/공/개` 글리프로 remap하는
  우회를 만들었지만, claude/agy 리뷰에서 전역 가나 표시 오염과 name-grid `ヒ/フ/ヘ` 슬롯 충돌 위험이 지적되어 폐기했다.
- **성공 경로**: source bytes는 `814881488148814081408140`
  (`？` 3개 + 전각공백 3개)로 둔다. `0x08B1319C` compact render call 자리에 `0x08F30600` hook을 설치하고,
  hook entry의 `r2` source pointer가 `0x08DF8C2A/2C/2E`일 때만 원래 renderer 호출 뒤 tilemap entry를
  private tile id `0x3E0/0x3E2/0x3E4`로 바꾸며 KOR_BASE의 `미/공/개` 글리프를 VRAM에 복사한다.
  `ガ/ギ/グ` kana table 값은 원본과 동일하게 유지된다.
- **검증**: fresh mGBA route `Part1 메뉴 -> 싱글 대전 -> 맵 선택`에서 세 행이 `미공개`로 표시된다.
  증거는 `docs/screenshots/part1_single_map_unknown_label_fix_2026-06-27/contact.png`,
  `map_unknown_label_crop_4x.png`, `report.json`.
  최종 output/dist SHA는 `fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093`이며,
  `verify_dist_integrity.py`와
  `run_release_qa.py --timeout 300 --report temp/release_qa_report_20260627_single_map_unknown_label_safe_hook.json`가 PASS했다.
- **주의**: 이 hook은 해당 placeholder 표시를 위한 주소 국소 우회다.
  일반 한글 renderer나 compact table 전수 증거로 확대 해석하지 않는다.

---
## [2026-06-26] `ADDRESS_TEXT_OVERRIDES` 거버넌스 audit와 D2 미커버 watch

- **source duplicate 구조**: `ADDRESS_TEXT_OVERRIDES` 단일 dict 내부 중복은 0으로 보였지만, 후속
  `ADDRESS_TEXT_OVERRIDES.update({...})` 블록이 앞선 값을 덮는 중복이 142주소/145라인 남아 있었다.
  이 구조는 최종 ROM을 바꾸지 않더라도 새 override가 숨어 들어갈 수 있으므로, 최종 effective 값을 보존한 채
  앞선 중복 정의를 제거했다. audit 기준은 source entries=effective=4118, duplicate 0.
- **final effective 산정 정정**: 보호주소 final text는 raw `ADDRESS_TEXT_OVERRIDES[addr]`만이 아니다.
  import/override pass 뒤에 `patch_script_row` 등 direct patch가 같은 주소를 다시 쓰는 경우가 있고, pair-renderer
  영역은 `normalize_pair_renderer_text`로 전각 공백/숫자 변환 후 인코딩된다. audit 기준은
  `direct patch > pair normalize > raw ADDRESS_TEXT_OVERRIDES` 순서다. 현재 pair normalize 4건, direct patch collision
  970건(분기 502)이다.
- **overlay 분기**: `dialogue_overrides.json`에는 보호주소 collision 1111건이 남아 있고, final effective 기준 1072건은
  실제 출하 text와 다르다. 이는 편집기/legacy 권위문과 출하 안전문이 분기된 상태를 명시적으로 보여 주는 리포트
  대상이다. 빌드/에디터 표시/저장 게이트는 final effective text를 권위로 쓴다.
- **UI 표시 동기화**: `dialogue_map.json`과 `dialogue_groups.json`은 final effective text 기준으로 검사한다.
  리뷰에서 raw 보호값 기준 early-return이 direct patch 502건과 pair normalize 4건을 숨기는 결함임을 확인해 철회했다.
  현재 audit 기준 `dialogue_map` 보호주소 mismatch 0, `dialogue_groups` 보호주소 mismatch 0.
- **D2 미커버 watch**: 현재 SHA `8a34a570…`에서 `0xD81C24`, `0xA3B880`, `0xB842E8` 본문 head와 정적 포인터 위치를
  `temp/part1_menu_fresh_final_current/state_003.ss0`, `temp/part1_post_name_menu_branch_20260608/menu_base.ss0`,
  battle/Part2 sweep 계열 4개 state 주변 15케이스로 read-watch했다. 결과는 모두 hit 0이며 요약은
  `data/d2_width_uncovered_watch_probe_20260626.json`. 이 결과는 기존 checkpoint가 실제 노출 화면이 아님을 뜻할 뿐,
  해당 후보의 클리핑 안전성을 증명하지 않는다.

---
## [2026-06-26] Part2 `상점` 도움말 `?` 깨짐/우측 잘림과 표시 전용 override

- **재현**: coldboot Part2 모드 메뉴에서 `상점`을 highlight하면 `0x00A2C1B8`
  B팀 문장 `획득한 포인트로,여러 가지 쇼핑을 할 수 있습니다`가 하단 도움말 한 줄에 표시된다.
  수정 전 fresh 캡처는 `temp/part2_shop_help_repro_20260626/s005.png`이며,
  `획득한 포인트????????` 형태의 byte alignment 깨짐이 보였다.
- **메커니즘**: 이 compact renderer는 ASCII separator가 섞이면 2바이트 단위 소비 경로와 어긋나 fallback `?`가
  연쇄 노출된다. repoint/free-space 문장에 대해 `encode_full_fidelity()`가 ASCII space/comma를 전각 공백/`、`로
  바꾸면 `?`는 사라졌지만, 전각 공백까지 포함한 폭이 54 half-cell이 되어 우측이 잘렸다.
  `、`는 한국어 구두점 정책이 아니라 이 엔진에서 이미 안전하게 소비되는 2바이트 구두점으로 쓰는 회피값이다.
- **정책 충돌**: B팀 권위문 자체를 줄이면 `qa_bteam_drift.py` baseline 변경이 필요하다. 사용자 명시 승인 없이
  baseline을 갱신하지 않기 위해 원문 데이터는 유지하고, 화면에 실제로 들어가는 문구만
  `data/display_overrides.json`으로 분리했다.
- **수정**: `0x00A2C1B8` 표시 문구를 `포인트로 쇼핑을 할 수 있습니다`로 지정했다.
  빌드는 CSV/ADDRESS/SOURCE/TEXT 계산 뒤, pair/direct 후단 전 실제 표시 텍스트에 이 계층을 적용한다.
  `build_dialogue_map.py`, `qa_text_fit.py`, `qa_pixel_width.py`, `audit_address_text_overrides.py`도 같은 표시 계층을
  반영해 ROM/에디터/QA effective text가 갈라지지 않게 했다.
- **검증**: 현재 output 3종 SHA `19a2ea7102df707194ec2993b48a0cd0e5fe029cba6443bd76dffa4392e8c00d`.
  fresh 캡처 `docs/screenshots/part2_shop_help_fix_2026-06-26/fresh_shop_help.png` 및
  `fresh_shop_help_bottom_zoom.png`에서 `?`와 우측 잘림이 모두 사라졌다. `qa_bteam_drift.py` drift 0 유지.

---
## [2026-06-26] Part1 visual QA route A-count 보정

- **증상**: `qa_visual_regions.py`가 Part1 이름 입력 뒤 A 17회로 `fresh_menu.ss0`를 저장해
  `모드 선택`이 아니라 작전룸 내부 리스트를 `single/link` 기준점으로 검사했다. 이 때문에 원본 ROM에서도
  OPERATION 로고가 남는 화면을 한글 패치 회귀처럼 판정했다.
- **확정**: A-count probe `temp/part1_menu_a_count_probe_20260626/contact.png`에서 A 16회째가 `모드 선택`,
  A 17회째가 작전룸 진입임을 확인했다.
- **수정**: `PART1_MENU_ADVANCE_A_PRESSES`를 16으로 보정하고, mode/single/link 검사는 저장한 mode-select state에서
  각각 독립 분기하도록 정리했다. 현재 `qa_visual_regions.py`는 `visual_region_checks=39`로 PASS한다.

---
## [2026-06-26] 현재 SHA 기준 scene/UI editor 재검증

- **scene screenshot provenance**: Part2 상점 표시 override와 Part1 route 보정 뒤 현재 SHA
  `19a2ea7102df707194ec2993b48a0cd0e5fe029cba6443bd76dffa4392e8c00d`로 scene screenshot 70개를 재캡처했다.
  stale entrypoint 76건은 `tools/capture_scene_screenshots.py --force` 재실행 후 0건이 되었고,
  `audit_scene_entrypoints.py --strict`, `audit_scene_catalog.py --strict`, `audit_scene_semantics.py --strict`,
  `audit_scene_residual_scans.py --strict`가 모두 통과했다.
- **:8782 editor 상태**: `verify_scene_editor_apply_state.py`가 ROM/output SHA 일치와 `apply_needed=false`를 확인했다.
  Chrome CDP 검증은 63개 대표 scene과 107개 sprite를 열어 failure 0이었다.
- **저장/빌드 경로**: `data/scene_editor_roundtrip_verify.json` 기준 80 scene, 10,336 dialogue group, 1,990 sprite,
  17,975 editable member dry-run failure 0, B팀 2,805 member confirm failure 0/skip 0이다.
  일반/B팀 대표 실제 저장·복원 2건과 direct script 확장-span 샘플 `0x00D8FD26`의 임시 ROM 빌드 expected/actual byte 일치도 통과했다.

---
## [2026-06-26] 맵 디자인 도움말 renderer의 ASCII 숫자/구분자 정렬 깨짐

- **관찰**: Part2 모드 메뉴 → 편집 → 맵 디자인 → SELECT → 도움말 → `플레이 조건` fresh route에서
  도움말 본문 숫자/쉼표 이후가 `????`로 깨졌다. 같은 계열의 Part1/Part2 맵 디자인 도움말 행은
  `0x00A2C720..0x00A2C868`, `0x00D82134..0x00D822AC`에 분산되어 있다.
- **원인**: 해당 compact 도움말 renderer는 2바이트 셀 단위로 소비되는 경로이며, 본문에 ASCII `31/32`,
  `2c`, `2e` 같은 1바이트 숫자/구분자가 섞이면 다음 glyph 경계가 어긋난다. 결과적으로 유효 한글 코드가
  fallback `?` 연쇄로 보인다.
- **수정 경계**: B팀/편집기 권위문 자체를 줄이지 않고 `data/display_overrides.json`에 화면 전용 안전문을 둔다.
  안전문은 ASCII 숫자/쉼표/마침표를 제거하고, 필요한 공백은 전각 공백 또는 한글-only 문장으로 처리한다.
- **빌드 순서 결함**: 기존에는 `dialogue_overrides.json` 최종 overlay가 display override를 다시 덮을 수 있었다.
  `tools/build_korean_full.py`의 후단 overlay는 이제 `display_overrides` 주소를 건너뛰고, 해당 주소는 화면 전용
  문구를 최종 ROM 권위로 쓴다.
- **D81C24 분리**: `0x00D81C24`는 visible split 도움말 행이 아니라 직접 테이블/요약 후보로 보인다.
  정적 D2 width 후보를 줄이기 위해 42셀 요약 `조건수도둘이상각군병종거점필요대전통신가능`으로 축약했고,
  실제 `플레이 조건` 화면 깨짐은 `A2C/D821` split 행의 ASCII 제거로 닫았다.
- **검증 결과**: current SHA `7bf452715d5dc9da63b58cb45eb4e23e45e785b5cb699714760a23411455a680`에서
  fresh route 캡처와 D821 보조 cross-state 캡처 모두 `?`/클리핑이 없다.
  `qa_bteam_drift.py`는 drift 0이며, `qa_pixel_width.py`의 `>50` 후보에서 `0x00D81C24`는 제거됐다.
  당시 남은 D2 미확정은 `0x00A3B880/0x00B842E8` CO 파워명 노출 state뿐이었다(아래 2026-06-27 정정으로 종결).

---
## [2026-06-27] `0xA3B880/0xB842E8` CO 파워명 폭 후보 정정: 표시 문자열이 아니라 글리프 사전

- **정적 포인터 재해석**: `0x00A3B880`의 포인터는 `0x003806FC`, `0x00381300` 코드 리터럴 풀에,
  `0x00B842E8`의 포인터는 `0x00B3C1F8` 코드 리터럴 풀에 있다. 이들은 문자열 테이블 포인터가 아니라
  런타임 변환 함수가 받는 글리프 코드 사전이다.
- **A3 계열 루틴**: Thumb 함수 `0x08380564`는 입력 문자열의 2바이트 코드마다 사전 포인터(`r1`)를 2바이트씩
  전진하며 일치 인덱스를 찾고, 찾은 인덱스로 `0x060160E0` 쪽 타일 데이터를 복사한다. 호출자
  `0x083806A8`, `0x08381294`가 실제 CO 파워명 문자열 포인터를 `r0`, `0x08A3B880` 사전을 `r1`로 넘긴다.
- **B842 계열 루틴**: `0x08B3C184`도 입력 바이트열을 순회하며 `0x08B842E8` 사전에서 2바이트 코드쌍을 찾고,
  매칭된 인덱스의 0x100-byte 타일 블록을 복사한다.
- **결론**: 디코드상 `하이퍼리페어라세드...`처럼 이어 보이는 값은 CO 파워명들을 한 줄로 표시하는 문장이 아니라,
  개별 파워명 렌더에 필요한 2바이트 코드 집합이다. 따라서 화면 폭/클리핑 후보에서 제외하는 것이 맞다.
- **적용**: `tools/build_korean_full.py::GLYPH_DICTIONARY_TEXT_ADDRS`에 `0xA3B880`, `0xB842E8`을 등록했다.
  `tools/qa_pixel_width.py`는 이 주소를 line-width 후보에서 제외한다. `tools/build_dialogue_map.py`는
  감사 추적을 위해 두 행을 남기되 `is_noise=true`로 표시하고, `data/dialogue_groups.json` 및
  `data/scene_catalog.json`에는 배정하지 않는다.
- **리뷰 적발 보강**: codex 리뷰가 `0xA3B880` override 안의 ASCII `_`를 지적했다. 이 값은 사전 렌더러의
  2바이트 코드쌍 경계를 105바이트 홀수 payload로 밀 수 있으므로, 단순 width 후보 제외만으로는 안전하지 않았다.
  이후 A3/B842 사전 문자열을 실제 compact 표시명 unique glyph set으로 재작성하고, 화면 표시명은
  `data/display_overrides.json`의 compact CO 파워명 전용 override로 맞췄다.
- **B8 catalog 정정**: 리뷰에서 `0x00B84E7C`, `0x00B84F04` 등 실제 CO 파워명 그룹과
  `0x00B81874` 이후 유닛/무기명 그룹이 `region="font"`라서 `scene_catalog`에서 빠지는 결함도 확인했다.
  `0xB81800..0xB85000`은 순수 폰트가 아니라 유닛/무기/상점/CO/브레이크 라벨 compact 표시문 테이블이므로,
  `23d_part2_b8_compact_display_tables` container scene으로 459개 그룹을 배정했다. 짧은 CJK-only 라벨이
  노이즈로 숨겨지는 문제도 `build_dialogue_map.py`에서 build-authored text 판정으로 보강했다.
- **전용 QA/자동 생성**: `tools/qa_glyph_dictionary_tables.py`를 추가했다. 이 게이트는 두 사전 payload가 짝수 길이인지,
  1바이트 ASCII lead가 없는지, output ROM 사전 바이트와 일치하는지, A2/B84 compact 표시 대상의 모든 2바이트
  glyph pair가 해당 사전에 존재하는지 검사한다. 또한 display override 대상 count(36/11), dialogue_map 노출,
  사전/대상 slot tail 0 패딩, ASCII space 잔존 금지를 함께 검사한다. 후속 보강으로 `tools/build_korean_full.py`는
  `data/display_overrides.json`의 A2 36개/B84 11개 compact 표시명에서 ordered unique glyph set을 산출해
  `0xA3B880/0xB842E8` 사전 override를 자동 주입한다. 하드코딩 사전 문자열은 제거했고,
  `audit_address_text_overrides.py`는 이 runtime-generated 주소 2개를 static mismatch가 아닌 생성 주소로 집계한다.
  `verify_dist_integrity.py`에도 `CO glyph dictionary coverage` 게이트로 묶었다.
- **검증**: 최종 SHA `d1cebfde9764606dcc3b7b3017fcfc8c2cc0faf30afa4e69568b604f5ae12854`에서
  `qa_glyph_dictionary_tables.py` issue 0, `qa_pixel_width.py --top 40`의 `final encoded cells > 50` 후보 9개,
  `audit_scene_catalog.py --strict` dialogue_unassigned 0, `audit_scene_residual_scans.py --strict` critical 0,
  `audit_scene_entrypoints.py --strict` stale 0, `verify_dist_integrity.py` PASS. 배포 게이트에는 text fit,
  visual region, CO glyph dictionary coverage, sprite override fit이 포함된다.

---
## [2026-06-27] Part2 프롤로그 `0xA01A5C/0xA01A70` 보고문과 `77 72` gap

- **구조**: `0x00A01A5C`는 포인터 테이블 xref가 1건(`0x00A357C4`)이고,
  `0x00A01A70`은 직접 포인터 xref가 없다. 원본 메시지는
  `各ショーグンとも、` 뒤 gap `0x00A01A6E=77 72`를 거쳐
  `攻撃の準備を終わったところです。`로 이어지는 연속 메시지다.
- **추가 원인**: `0x00A01A2C` 첫 질문만 free-space(`0xA3D000`)로 repoint하면 ROM 바이트와 포인터는
  정합해도 실제 화면 첫 줄이 뒤쪽 `0xA01A5C` 보고문 내용으로 오염됐다. `0xA357C0` 포인터를 원래
  `0x08A01A2C`로 되돌리면 질문 화면이 즉시 정상화되어, 이 프롤로그 renderer가 인접 in-place span 또는
  glyph/cache 상태에 민감하다고 판정했다.
- **실패한 후보**: `0x0A` 삽입, `0xA01A70` blank, `0xA01A5C..0xA01A94` 통짜 span + `k`,
  통짜 span + `wr` 직접 삽입, `0xA01A70` leading fullwidth space는 route 캡처에서 잔상/중복 또는
  다른 대사 깨짐을 만들었다. 단순히 뒤쪽 조각만 blank하거나 줄바꿈을 넣는 방식은 renderer 상태를 안정화하지 못했다.
- **해석**: `0x77`/`0x72`는 이 프롤로그 대화 renderer의 wait/scroll/line 계열 1바이트 제어로 보인다.
  `0x0A`는 이 위치에서 원하는 줄분리를 만들지 못한다.
- **채택한 수정**: `tools/dialogue_repoint.py`에 forced skip을 추가하고, `build_korean_full.py`에서
  `0xA01A2C/0xA01A5C`를 repoint 대상에서 제외한다. 포인터 `0xA357C0/0xA357C4`는 각각
  `0x08A01A2C/0x08A01A5C`로 고정하고, 원본 span을 넘지 않는 두 직접 패치를 마지막에 적용한다.
  - `0xA01A2C..0xA01A5C`: `매크로　랜드　침공　작전은、\n어찌　되었나？`
  - `0xA01A5C..0xA01A94`: `각　사령관　모두、\n공격　준비를　끝낸　참입니다。`
- **검증**: 최종 SHA `11098045c8ee5d167d5b27f00087d0ed38d04f16384b3dcc66ccca2ef800a9a1`에서
  A-only route는 `매크로 랜드 침공 작전은, / 어찌 되었나?` →
  `각 사령관 모두, / 공격 준비를 끝낸 참입니다.` → `목적은 알고 있겠지` 순서로 정상 표시된다.
  focus route에서도 중복/잔상 없음, step_005 wait 1/30/120/300/600 프레임 안정.
  증거는 `docs/screenshots/part2_prologue_inline_renderer_fix_2026-06-27/`.

---
## [2026-06-27] E12 compact 표시문 visual evidence matrix

- **문제**: `qa_glyph_dictionary_tables.py`는 A2/B84 compact CO 파워명 사전과 대상 바이트를 검증하지만,
  실제 화면에서 모든 CO 파워명/유닛명/무기명/상점/브레이크 라벨이 렌더됐다는 증거는 아니다.
  `23d_part2_b8_compact_display_tables`는 UI 에디터 노출용 container이며 독립 화면이 아니다.
- **도구**: `tools/build_compact_display_visual_matrix.py` 추가. `data/display_overrides.json`,
  `data/dialogue_map.json`, `data/dialogue_groups.json`, `data/scene_catalog.json`, scene screenshot provenance를 합쳐
  target별 evidence level을 산출한다. 산출물은 `data/compact_display_visual_matrix.json`,
  `docs/reports/compact_display_visual_matrix_2026-06-27.md`,
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/current_representative_contact.png`.
- **초기 SHA `11098045…` 결과**:
  - A2 CO 파워명 36개: editor 36, current screen scene 1, container-only 35, direct target visual 0.
  - B84 CO 파워명 11개: editor 11, container-only 11, direct target visual 0.
  - B8 compact table 459개: editor 459, container-only 459, direct target visual 0.
- **판정**: E12는 진행 기반이 생겼지만 미완료다. “current screen scene”은 해당 scene이 현재 ROM으로 캡처됐다는 뜻이지
  특정 target이 화면에 보인다는 뜻이 아니다. 다음 직접 증거 우선순위는 B84 파워 발동 화면, B8 유닛/무기/상점 HUD,
  A2 CO 프로필 다중 CO 캡처 순서로 잡는다(agy 리뷰 동일).

---
## [2026-06-27] E12 compact renderer breakpoint trace 1차

- **리뷰 반영**: claude/agy 모두 source 주소를 추정해 read-watch하는 방식보다, 이미 문서화된 compact renderer
  진입점에서 break 후 `r0`/`r1`를 기록하는 방식이 더 정석이라고 지적했다. direct evidence는 “해당 프레임에
  renderer가 `r0=target address`를 받았다”로만 인정한다.
- **도구**: `tools/trace_compact_renderer.py` 추가. 현재 후보 PC는
  `0x08380564`, `0x083806A8`, `0x08381294`, `0x08B3C184`이며, 결과는
  `data/compact_display_renderer_trace.json`에 저장된다. `tools/build_compact_display_visual_matrix.py`는
  이 trace의 `direct_hits`만 target-level direct evidence로 병합한다.
- **초기 SHA `11098045…` 1차 결과**: Part2 메인 메뉴, 워즈숍, compact 메뉴, 룰 설정,
  전투 공격/전투 OBJ 라벨/전투 시작 overlay, CO 프로필 maxg/domino refresh 9경로 모두
  breakpoint hit 0/direct 0이다. 같은 CO 프로필 refresh에서
  `0x060160E0` write-watch도 0이었고, 프로필 스크롤 자체는 VRAM/OAM/PAL diff와 `0x06000000..0x06002000`
  write-watch로 확인되었다(대표 write PC `0x08313C4C`, `0x08F302DE..0x08F302F0`, LR `0x08385E27/0x0831BBED`).
- **해석**: 이 결과는 현재 대표 route와 문서화된 PC 조합이 direct evidence로 부적합하다는 뜻이다.
  B8/B84/A2 target이 전역 미사용이라는 결론은 아니다. 다음 조사는 corrected renderer PC 역추적 또는
  실제 CO 파워 발동, 유닛 상세, 전투 데미지예측 등 target이 강제로 다시 그려지는 state 확보가 필요하다.
- **2026-06-27 code-context 후보 포함 재시도**: `tools/analyze_compact_display_code_context.py`로
  static xref 주변 PC-relative literal load를 계산해 breakpoint 후보 24개/function 후보 18개를 뽑고,
  `tools/trace_compact_renderer.py`가 이 후보를 자동 포함하도록 보강했다. 최종 break set은 50개
  (`data/compact_display_renderer_trace.json`, `code_context_breakpoints_enabled=true`)가 되었지만 같은
  9경로에서 hit 0/direct 0이다. claude 리뷰 지적처럼 이 후보 중 일부는 데이터 영역을 Thumb로 오독한
  noise일 수 있으므로, 이 결과는 “후보 route/PC 음성”으로만 기록한다.

---
## [2026-06-27] E12 compact target static pointer xref

- **도구**: `tools/analyze_compact_display_xrefs.py` 추가. A2/B84/B8 compact target을 가리키는
  ROM pointer literal을 전수 검색하고, target 그룹 내부 참조와 외부 포인터 테이블 참조를 분리한다.
  산출물은 `data/compact_display_xref_analysis.json`이며, visual matrix의 Static Pointer Xrefs 섹션에 병합된다.
- **초기 SHA `11098045…` 결과**:
  - A2 CO 파워명 36개: pointer ref 36/36, external pointer ref 36/36. 포인터는 `0x00A37B3C..` 계열 static table.
  - B84 CO 파워명 11개: pointer ref 11/11, external pointer ref 11/11. 포인터는 `0x00DF2B54..` 계열 Part2 table.
  - B8 compact table 459개: pointer ref 371/459, external pointer ref 355/459. 참조 버킷은 D8/DE 계열 포인터 테이블과
    일부 code/static literal, B8 내부 포인터 슬롯으로 나뉜다.
- **B84 2차 참조**: `0x00B84F14`(기적)가 가리키는 B84 파워명 pointer table head `0x08DF2B54`는
  `0x00B3C318`, `0x00B3C540`에서 다시 참조된다. 주변 후보 블록
  `0x08B3C2D0/0x08B3C300/0x08B3C320/0x08B3C4D6/0x08B3C550/0x08B3C5A0`도
  `tools/trace_compact_renderer.py` breakpoint set에 추가했다.
- **판정**: static xref는 target reachability 후보를 좁히는 증거일 뿐, 화면 렌더를 증명하지 않는다.
  E12 direct evidence 조건은 여전히 “실제 화면 route에서 target 주소가 renderer/source로 사용됨을 trace 또는
  VRAM write chain으로 입증”이다.

---
## [2026-06-27] E12 compact static code-context 분석

- **도구**: `tools/analyze_compact_display_code_context.py` 추가. `data/compact_display_xref_analysis.json`의
  external/second-level ref와 기존 compact glyph dictionary literal(`0x003806FC/0x00381300/0x00B3C1F8`) 주변을
  Capstone Thumb/ARM로 디스어셈블하고, 해당 ROM word를 PC-relative literal로 적재하는 `ldr [pc,#imm]` 후보를 찾는다.
  산출물은 `data/compact_display_code_context.json`.
- **초기 SHA `11098045…` 결과**: literal entry 492, derived table-head ref 478,
  breakpoint candidate 24, function candidate 18. A2 36개는 literal load 0으로, `0x08A37B3C` 포인터 테이블이
  direct literal이 아니라 register/index 경로로 읽힐 가능성이 높다.
- **검토 결론**: agy는 `0x083806A8/0x08381234`, `0x08B3C254/0x08B3C4D8`, `0x08B20020`을 우선 후보로 보았고,
  claude는 더 보수적으로 `0x08B3C184` 사전 함수, `0x08B342A8`(`0xB83268` 직접 포인터) 정도만 상대적으로
  가치가 있다고 보았다. 두 리뷰 공통 결론은 “literal LDR 후보만으로는 direct evidence가 아니며,
  실제 화면 target read 또는 VRAM write 역추적이 필요”다.
- **주의**: 포인터 테이블/데이터 영역을 디스어셈블하면 가짜 `push {..,lr}`/`ldr [pc]`가 생길 수 있다.
  따라서 code-context 후보는 breakpoint 탐색 목록일 뿐, E12 완료 근거로 쓰지 않는다.

---
## [2026-06-27] E12 compact read-watch probe 1차

- **claude/agy 재리뷰**: 두 CLI 모두 `direct 0`은 “증거 부재”이지 미사용 증명이 아니며, 다음 우선순위는
  실제 target source read를 잡아 corrected renderer PC/LR을 확보하는 것이라고 지적했다. 또한 hit 0은
  화면 미진입, 후보 PC 오판, watchpoint false-negative를 분리해야 한다.
- **도구 보강**:
  - `tools/trace_compact_renderer.py`는 이제 `r0/r1`만 보지 않고 `r0..r7/sp/lr/pc`의 exact/range match를
    모두 로깅한다. 단, direct evidence는 `r0..r7`에 exact target address가 잡힌 경우만 인정한다.
  - `tools/probe_compact_display_reads.py`를 추가했다. mGBA `watchaddr`로 compact source range 또는
    representative exact target addresses를 read-watch하고 `pc/lr/r0/r1`을 JSON으로 기록한다.
- **초기 SHA `11098045…` 결과**:
  - A2/B84 range read-watch: fresh Part2 메인 메뉴 + CO profile maxg/domino refresh 3케이스 hit 0/direct read 0.
    산출물 `data/compact_display_read_watch_probe.json`.
  - B8 range read-watch: compact 메뉴/워즈숍 savestate 2케이스 hit 0/direct read 0.
    산출물 `data/compact_display_read_watch_probe_b8.json`.
  - B8 representative exact watch: `0xB81D40/0xB831BC/0xB8387C/0xB838BC/0xB839F0/0xB84CB8/0xB84F14`을
    fresh Part2 메인 메뉴 + compact 메뉴/워즈숍 후보 3케이스에서 감시했지만 hit 0/direct read 0.
    산출물 `data/compact_display_read_watch_probe_b8_subset.json`.
  - B8 battle 후보: 같은 exact subset을 전투 공격/OBJ 라벨/전투 시작 overlay 3케이스에서 감시했고,
    추가로 전투 공격 화면 1케이스는 B8 전체 range로 감시했지만 모두 hit 0/direct read 0.
    산출물 `data/compact_display_read_watch_probe_b8_battle_subset.json`,
    `data/compact_display_read_watch_probe_b8_battle_range.json`.
  - 임의 savestate 입력 모드: `tools/probe_compact_display_reads.py`에 `--state`, `--state-step`,
    `--no-default-screen`을 추가했다. `temp/external_saves/profile_plus_aw2_zophar_matrix/*/state_shop_enter.ss0`
    5개는 B8 range 20프레임 hit 0/direct read 0, `state_011_SELECT.ss0` 5개는 A2/B84 range 대기 및
    RIGHT refresh 모두 hit 0/direct read 0이었다. 프레임 확인상 이 후보들은 compact 파워명/상품목록이 아니라
    상점 대화 화면이었다. 산출물 `data/compact_display_read_watch_probe_b8_shop_states.json`,
    `data/compact_display_read_watch_probe_a2_b84_profile_states.json`,
    `data/compact_display_read_watch_probe_a2_b84_profile_refresh_states.json`.
- **2026-06-27 양성대조/추가 fresh sweep**:
  - fresh Part2 프롤로그 나레이션에서 화면에 보이는 `0x00A01970`을 exact 64바이트 watch했더니 59 hit가 발생했다
    (`0x0831425A/0x08314336/0x08F30284/0x08F30286`). 산출물
    `data/compact_display_read_watch_positive_control_a01970.json`. 즉 E12 0-hit는 하니스가 ROM read를 전혀
    못 잡는 문제가 아니라 route/target 가정 문제다.
  - code-context 상 상대적으로 높은 후보인 `0x00B83268`(잠시 기다려 주십시오.)을 Part2 통신 checkpoint에서
    exact watch했지만 hit 0이고, 프레임상 해당 state는 통신 대기문이 아니라 멀티 메뉴였다.
    산출물 `data/compact_display_read_watch_b83268_comm.json`.
  - `tools/probe_compact_display_reads.py`에 `--screen-step`을 추가해 fresh `06_part2_title` 이후
    `part2_menu_sweep` 정책을 재생하며 대표 B8 7개
    (`0xB81D40/0xB831BC/0xB83268/0xB8387C/0xB839F0/0xB84CB8/0xB84F14`)를 exact watch했지만 hit 0이다.
    최종 화면은 맵 설정/룰류 화면이었고, 산출물은 `data/compact_display_read_watch_b8_fresh_menu_sweep_subset.json`.
- **해석**: read-watch 0은 현재 route/subset이 direct evidence로 부적합하다는 추가 음성 결과다.
  B8 전체 range fresh watch는 60초 이상 정체되어 중단했으므로 실패 로그로만 취급한다.
  다음에는 B84 파워 발동 직전/직후, 유닛 상세/무기 상세/전투 데미지예측처럼 target read가 강제되는 fresh 또는
  near-fresh state를 확보해야 한다.

---
## [2026-06-27] 사용자 추가 스크린샷 후속: Part1 작전실 작전명/repoint 표시 경로 확정

- **관찰**: 사용자 추가 스크린샷 triage 뒤 Part1 작전실을 coldboot fresh route로 재캡처했다.
  미션 리스트가 `전투 개싸`, `전선 기지를 확보하라`, `적 부대를 해치워라`, `지상 최강????`처럼
  긴 문장·구두점·ellipsis 잔상으로 보였다. 현재 증거는
  `docs/screenshots/part1_operation_room_title_fix_2026-06-27/contact.png`.
- **주소 범위**: 해당 작전명은 `0x00B81D80..0x00B82018`의 Part1 compact title rows가 실제 화면에
  노출되는 경로다. 이 renderer에서는 `!`, `？`, `・・・`, 전각 공백과 긴 설명형 번역이 선택 하이라이트/폭 제한과
  충돌하므로 화면용 compact title이 필요하다.
- **원인 체인**: 단순 in-place `ADDRESS_TEXT_OVERRIDES`만 고치면 일부 행은 개선됐지만
  `0xB81FC4/0xB81FF4`는 계속 긴 문장으로 표시됐다. `temp/repoint_manifest.json` 확인 결과 두 행은
  free-space로 재배치되어 있었고, 재배치 문자열은 `data/dialogue_overrides.json`의 legacy 문장을 사용했다.
  즉 `ADDRESS_TEXT_OVERRIDES`와 실제 repoint payload의 권위가 갈라진 것이 원인이다.
- **수정 원칙**: `_rp_dlg()`의 표시 문자열 우선순위를 display override → `ADDRESS_TEXT_OVERRIDES`
  → `dialogue_overrides.json` 순으로 바꿨다. build-safe 보호 override가 legacy editor override보다 먼저 적용되어,
  protected compact row가 free-space에 오래된 긴 문장으로 복제되는 회귀를 막는다.
- **결과**: `0xB81D80..0xB82018` 작전명은 `전투개시`, `전선기지확보`, `적부대격파`, `지상최강중전차`,
  `드래곤플라이`, `하늘에서오는건` 등 compact title로 정리됐다. E9 도움말 `0xDFA6AA/0xDFA6CD`는
  1차로 `전투법알려줄게`/`와서들어봐`까지 줄였지만, 후속 실측에서 공백 있는
  `전투 방법 알려 줄게`/`와서 들어 봐`도 slot-fit임이 확인되어 최신 ROM은 공백 복원 문구를 사용한다.

---
## [2026-06-27] E9 Part1 compact 도움말 의미/안전성 refresh

- **범위**: Part1 mode/single/link compact 도움말 `0x00DFA64A..0x00DFA9E9`.
  이 렌더러는 ASCII 숫자와 일부 길고 구두점이 섞인 문구가 위험하지만, 한글 음절 사이 공백은 slot별로
  `encode_fit()`을 실측해 안전하면 보존할 수 있다.
- **적용**: `대결 법 가르 드려`류 임시 축약을 먼저 짧은 화면용 문구로 교체했고, 후속 공백 복원에서
  `전투 방법 알려 줄게`/`와서 들어 봐`, `둘부터 넷까지`/`대전 가능`,
  `통신 케이블로`/`대전하기`, `카트리지 하나로`/`모두와 대전`,
  `친구와 연결해`/`맵 교환 가능` 등으로 정리했다. 추가 감사 중 같은 compact 권역의
  `0xDFA68C`는 `전투 기록 보기 가능.`에서 `전투기록볼수있어`로 바꿔 마침표 리스크를 제거했다.
- **검증**: 1차 최종 SHA `d96a7e13db4ceed1694cad6a7f6d39334a97ff59a75c84dfddde261c4eb810e9`,
  공백 복원 후 SHA `b9eea881356404e4643fadd6ca4f6d9bb7dcc31a649c1a928a7777ff170418b7`.
  mGBA fresh route로 mode/single/link 및 작전룸 하위 메뉴 28프레임 contact를 재캡처했다.
  증거는 `docs/screenshots/e9_part1_compact_help_refresh_2026-06-27/contact.png`,
  `docs/screenshots/part1_menu_help_spacing_2026-06-27/contact.png`.
  E8 통신 라벨 visual evidence도 같은 SHA로 다시 동기화했다.

---
## [2026-06-27] B2 CSV 손상 239행 source hygiene 복구

- **관찰**: `qa_csv_integrity.py --fail-on-rom-japanese` 기준 `data/translation_for_import.csv`에는
  `empty_len 36`, `bad_len 203`의 손상행 239개가 남아 있었다. 유형은 length-only가 아니라
  CSV 행병합/필드밀림/주소 누출/일본어·한국어 필드 오염이었다. 단, 출하 ROM 실제 일본어 잔존은 0이었다.
- **복구 권위**: 구조 필드(`address`, `japanese`, `length`)는 `data/game_wars_found_texts.csv`를 우선했다.
  실제 출력문은 `temp/integrity_map.json`의 `ship_ko`를 우선했고, 안전하게 분리 가능한 현재 CSV 한글 필드는 보존했다.
  clean backup은 보조 근거로만 사용했다.
- **정리 결과**: CSV row는 17763→17758, 234행 변경, 신규 행 0이다.
  found/integrity 양쪽에 없는 malformed artifact 5행
  (`0x00A23`, `0x00A2D`, `0x00A32`, `0x00D`, `0x00E0952`)은 제거했다.
  복구 후 `qa_csv_integrity.py --fail-on-rom-japanese`는 손상행 0, ROM 일본어 잔존 0을 보고한다.
- **중요 검증**: `python3 tools/build_korean_full.py` rebuild 후
  `output/game_wars_korean_full.gba`, `game_wars_korean_final.gba`, `game_wars_korean_title_test.gba` SHA가 모두
  `d96a7e13db4ceed1694cad6a7f6d39334a97ff59a75c84dfddde261c4eb810e9`로 이전 빌드와 byte-identical이다.
  즉 이번 수정은 ROM 동작 변경이 아니라 CSV 정본 부채 제거다.
- **리뷰 메모**: agy 리뷰는 B2 완료 PASS로 판단했다. 남은 위험은 CSV가 정상이어도
  `ADDRESS_TEXT_OVERRIDES`/`TEXT_OVERRIDES`/`dialogue_overrides.json`/repoint payload 우선순위가 실제 출력 권위를
  shadow할 수 있다는 점이다. 이는 B4/E11/E14 후속으로 분리한다.

---
## [2026-06-27] B4 CSV/override shadow 감사 게이트

- **문제 정의**: B2로 CSV 필드 구조는 정리됐지만, 실제 빌드는 CSV만 권위로 쓰지 않는다.
  `ADDRESS_TEXT_OVERRIDES`, `SOURCE_TEXT_OVERRIDES`, `TEXT_OVERRIDES`, `display_overrides.json`,
  `dialogue_overrides.json`, direct script patch, repoint payload가 후단에서 CSV를 의도적으로 덮을 수 있다.
- **도구**: `tools/audit_csv_override_shadow.py --strict`를 추가했다.
  이 도구는 `translation_for_import.csv`, `temp/integrity_map.json`, `temp/repoint_manifest.json`,
  build module의 override dict와 `qa_text_fit` direct patch 목록을 읽어, CSV와 최종 출력이 다른 행마다
  설명 가능한 shadow reason이 있는지 집계한다. strict failure는 **최종 출력이 CSV와 다른데 어떤 권위로도
  설명되지 않는 경우**에만 발생한다.
- **현재 결과**: CSV 17,758행 중 shadow/explained 11,595행,
  unexplained output shadow 0. reason count는 address override 3,662, dialogue override 5,023,
  direct patch 4,761, display override 68, pair renderer normalize 109, repoint payload 2,196,
  source-text override 3, text override 66이다. model/actual divergence 95건은 후단 fixed/direct writer가
  정적 모델보다 더 구체적인 최종 문구를 쓰는 정보성 차이로 리포트에 남긴다.
- **게이트화**: `verify_dist_integrity.py`에 `CSV override shadow` 하위 게이트를 추가했다.
  현재 `verify_dist_integrity.py` 전체 PASS이며 output/dist SHA는 계속 `d96a7e13…`이다.
- **리뷰 메모**: Claude B4 리뷰는 timeout, agy B4 리뷰는 비리뷰 출력으로 종료되어 실질 지적은 없었다.
  E11의 통합 runner/CI 정리는 별도 미완료로 남는다.

---
## [2026-06-27] E14 repoint punctuation/priority 영향 감사

- **감사 도구**: `tools/audit_repoint_punctuation.py --strict`를 추가했다.
  `temp/repoint_manifest.json`의 relocated message를 신뢰하지 않고, `output/game_wars_korean_full.gba`의
  `new_addr/new_len` free-space payload를 직접 스캔한다. 단일바이트 comma(0x2C)가 남으면 hard fail하고,
  fixed line source authority도 `display_override` → `address_override` → B팀/dialogue → write log → CSV 순으로 집계한다.
- **초기 발견**: 기존 빌드의 repointed payload에는 ASCII comma 1,323개가 남아 있었다.
  이는 `encode_full_fidelity()`가 fixed line의 comma만 `、`로 바꾸고, 같은 relocated message 안의 보존 라인
  comma는 그대로 둔 결과였다. `fixed=[]` render-jam relocation에서도 ASCII comma가 발견되어 “fixed line 한정”
  설명으로 닫을 수 없었다.
- **수정**: `dialogue_repoint.py`의 재구성 후단 `_conv` 단계에서 2바이트 코드 lead는 건너뛰고,
  전체 `new_msg`의 단일바이트 comma(0x2C)를 `0x8141`(`、`)로 변환하도록 했다.
  기존 전각공백 변환과 같은 free-space 후처리라 원본 슬롯 크기에는 영향이 없다.
- **검증 결과**: 재빌드 후 `audit_repoint_punctuation.py --strict`는 relocated message 2,084개,
  fixed line 2,417개, payload ASCII comma 0, fullwidth comma 1,887, payload issue 0을 보고한다.
  source authority 분포는 address override 277, B팀 dialogue override 380, CSV 304, dialogue override 734,
  display override 2, write log 720이다. `qa_repoint_integrity.py`도 2,084 재배치, 문제 0 PASS.
- **배포 동기화**: output/dist SHA는
  `d8be8aaf9fd6ae82be9995b3aec6c0c717f735b20b407ac46573b56f758b2ba6`로 갱신됐다.
  `verify_dist_integrity.py`에 repoint punctuation/integrity 하위 게이트를 추가했고 전체 PASS.
  SHA 변경으로 stale가 된 E8 `88_common_comm_labels` visual evidence 7장과 contact sheet도 현재 SHA로 재캡처/갱신했다.

---
## [2026-06-27] E11 통합 release QA runner 정리

- **목적**: 기존 배포 전 검증은 개별 명령을 수동으로 나열하는 방식이라, B2/B4/E14처럼 새 strict gate가 늘 때
  누락 위험이 컸다. `tools/run_release_qa.py`를 추가해 기본 로컬/static QA와 scene editor/CDP profile을 분리했다.
- **기본 profile**: `py_compile`로 핵심 스크립트 import/runtime 문법을 먼저 확인하고,
  `qa_csv_integrity.py --fail-on-rom-japanese`, `lint_translation.py --severity error`, `qa_text_fit.py`,
  placeholder/Japanese residual, address override, CSV override shadow, repoint punctuation/integrity,
  glyph dictionary, scene catalog/semantics/residual, visual region, `phase6_basic_test.py`,
  `verify_dist_integrity.py`를 순차 실행한다.
- **editor profile**: `--editor`는 :8782 scene editor API가 열려 있을 때
  `verify_scene_editor_apply_state.py`와 `verify_scene_editor_roundtrip.py --no-actual-sample --no-build-sample`을 실행한다.
  `--only-editor --editor` 결과는 PASS였다. CDP 검증은 `--cdp` 옵션으로 분리했으며 이번 실행 시 Chrome remote
  debugging 9224 포트가 닫혀 있어 이번 완료 근거에는 포함하지 않았다.
- **현재 결과**: 기본 profile과 editor API profile 모두 PASS, 리포트는 `temp/release_qa_report.json`.
  `verify_dist_integrity.py`에는 B4 CSV shadow, E14 repoint punctuation, E14 repoint integrity가 하위 게이트로 포함됐다.

---
## [2026-06-27] `87_common_rule_settings` B8 맵명 공백 뒤 `??` 깨짐

- **관찰**: 사용자 추가 스크린샷 계열에서 공통 룰 설정 화면의 B팀 맵명이
  `소라?? 섬`, `타마?? 섬`처럼 깨졌다. 같은 frame을 확대 확인한 결과 `소/라/타/마`처럼 첫 ASCII space
  이전 한글은 정상이고, space 이후 2바이트 한글만 `?`로 오독됐다.
- **ROM 바이트**: 수정 전 B8 map-name copy는 `0x00B827AC = 소라 마메 섬`,
  `0x00B8277C = 타마 타마 섬`, `0x00B826A8 = 마른 잎 섬` 형태였다. 이는 B팀 권위문과 맞지만,
  이 화면 renderer는 Part2 A2 map-select에서 고친 0x20 hook 경로가 아니어서 ASCII space 뒤 한글 pair를 안전하게
  렌더하지 못한다. loadstate 캡처는 RAM 캐시 때문에 ROM 수정 후에도 구 문자열을 보여 줄 수 있음도 재확인했다.
- **수정 경계**: B팀 권위문(`data/dialogue_overrides.json`, `data/bteam_baseline.json`)은 유지하고,
  화면 전용 `data/display_overrides.json`에 B8 compact copy 3건을 붙임 표기로 추가했다:
  `0x00B826A8 마른잎섬`, `0x00B8277C 타마타마섬`, `0x00B827AC 소라마메섬`.
  이 주소들은 A2/B84 compact glyph dictionary strict count 범위가 아니므로 dictionary 파생 카운트에는 영향이 없다.
- **캡처 인프라 보정**: `scene_87_common_rule_settings`의 `screen_checkpoints.json` entry를
  `part2_menu_sweep/state_017.ss0` savestate에서 coldboot fresh nav로 승격했다. 표준 캡처와 one-off fresh route의
  PNG SHA가 일치했고, fresh frame에서는 `??` 없이 맵명이 표시된다.
- **증거/검증**: 증거는 `docs/screenshots/rule_settings_map_name_fix_2026-06-27/fresh_rule_settings.png`.
  output 3종 SHA는 `e6ca1081a14a193bea40bc08114a3c8657b35f230cd89b4b2a94fa7d03bf8f60`.
  `qa_bteam_drift.py`, `qa_text_fit.py`, `qa_glyph_dictionary_tables.py`, `audit_csv_override_shadow.py --strict`,
  `audit_address_text_overrides.py --strict`, `audit_repoint_punctuation.py`, `qa_visual_regions.py`,
  `verify_dist_integrity.py`, `run_release_qa.py`, `run_release_qa.py --only-editor --editor --timeout 300` PASS.

---
## [2026-06-27] E12 current SHA 재동기화와 read-watch 한계 재확인

- **리뷰 결론 반영**: Claude/agy 모두 E12의 read-watch hit는 visual proof가 아니며, 0-hit도 DMA/WRAM 캐시/
  route 미진입/4B exact watch 한계 때문에 미사용 증명이 아니라고 지적했다. 따라서 E12는 direct visual evidence 0이면
  완료 처리하지 않는다.
- **새 SHA 재동기화**: 최종 SHA `a4e98a93…` 기준 `analyze_compact_display_xrefs.py`,
  `qa_glyph_dictionary_tables.py`, `analyze_compact_display_code_context.py`, `trace_compact_renderer.py`,
  `probe_compact_display_reads.py` current-exact/B8 map-territory exact/positive-control,
  `build_compact_display_visual_matrix.py`를 다시 실행했다. 대표 scene 8개도 새 SHA로 재캡처했다.
- **현 수치**: matrix는 A2 editor 36/current screen capture 1/direct 0,
  B84 editor 11/direct 0, B8 editor 459/direct 0이다. static xref는 A2 36/36,
  B84 11/11, B8 402/459 target에 pointer ref가 있고, external pointer ref는 A2 36, B84 11, B8 386 target이다.
  code-context는 literal entry 523, derived table-head ref 509, breakpoint candidate 24,
  function candidate 18이다. renderer trace는 9경로 hit 0/direct 0,
  current-exact read-watch 11케이스는 hit 0/direct 0, B8 map-territory exact watch
  (`0x00B84F5C/0x00B84F6C`, `10_part2_region_map_redstar`)도 hit 0/direct 0이다.
  positive control `0x00A01970`은 hit 8이라 하니스가 fresh route ROM read를 잡는다는 점은 유지된다.
- **추가 state triage**: `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0` 기반 CO profile nav probe는
  Domino/Max 프로필 설명 페이지 전환과 map 복귀만 보여 주며 CO power-name page로 진입하지 못했다.
  `part2_30b_remaining_breakscan_v1` 후보 state와 외부 profile/shop state contact도 지도 라벨/상점 대화/메뉴 화면으로
  판정되어 A2/B84/B8 direct evidence가 아니다. 증거 contact는
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/co_profile_nav_probe_contact.png`,
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/candidate_state_triage_contact.png`.
- **claude/agy 리뷰 후 해석 보강**: 차단급 문제는 없고 E12 미완료 유지가 맞다는 판정이다. 다만 현재 0-hit는
  단순 route 미진입뿐 아니라 A2/B84/B8 override 주소가 실제 화면 source가 아닌 복사본/死 데이터일 가능성도
  남긴다. `23d_part2_b8_compact_display_tables`와 UI 에디터/CDP PASS는 catalog/data binding 증거일 뿐,
  실화면 렌더 증거가 아니다. 따라서 다음 조사는 새 메뉴 sweep을 넓히기보다, 단 1건이라도 target read 또는
  WRAM/VRAM/DMA write chain으로 override 주소가 화면 타일로 이어지는지 먼저 확정하는 쪽이 우선이다.
- **2026-06-27 source-address 가설 검증 추가**:
  - B84 지도 라벨 후보 `0x00B84F5C`/`0x00B84F6C`, `0x00A35758`, ROM 전체 encoded `레드스타` 261건을
    test label로 바꿔도 `10_part2_region_map_redstar` 픽셀 diff는 0이었다. 이 지도 라벨은 B8/B84 text table
    provenance가 아니라 baked graphic/VRAM cache/다른 source 후보로 본다.
  - `scene_86_common_compact_menu_tables`의 `0x00B837A4`(`통신`), `0x00B84488`(`편집`) mutation도 diff 0이고,
    fresh `07_part2_main_menu`의 전체 `상점` ROM 발생 위치 mutation도 diff 0이었다. menu label 화면은
    E12 B8 직접 증거로 쓰지 않는다.
  - 실제 `공격` action menu가 열린 `temp/first_battle_state31_action_a30/a30_action_menu.ss0`와,
    menu-open 전 `temp/first_battle_state31_a36_probe/after_a36.ss0`에서 `A` 반복으로 같은 menu까지 도달하는
    경로 모두 B8 exact 후보 7건 read-watch hit 0/direct 0이었다. 이 화면도 현 후보 주소의 runtime source
    증거가 아니다.
- **matrix 갱신**: `build_compact_display_visual_matrix.py`는 새 action-menu watch JSON까지 자동 수집한다.
  2026-06-27 후속 재동기화 뒤 현재 read-watch 집계는 probes 17/current 17/stale 0/cases 46/hits 69/direct 69,
  positive control 1케이스 hit 8이다. read-watch hit 69는 모두 `41_part1_operation_room` B8 작전명
  live-source 4주소에서 나온다. 비작전실 A2/B84/Part2-B8 후보 45 cases는 hit 0/direct 0이다.
  renderer trace/code-context/xref도 current SHA로 재생성했고,
  matrix/report와 `verify_dist_integrity.py`가 stale dependency를 hard fail한다.
  단, 이 positive control은 일반 텍스트 `0x00A01970`의 read-watch이며 compact renderer 자체가 watchpoint로
  잡힌다는 양성대조는 아직 아니다. E12의 0-hit는 계속 route/subset 음성 결과로만 해석한다.
- **2026-06-27 B8 작전명 live source 확정**: 사용자 작전실 화면에 직접 보이는
  `0x00B81FF4`(`전선기지확보`)를 temp ROM에서 `테스트확보`로 단일 주소 mutation하고,
  `41_part1_operation_room` coldboot fresh route를 base/mutation 모두 캡처했다. 픽셀 diff는 209px,
  bbox는 `[9,75,56,86]`이며 리스트의 해당 행만 바뀐다.
  증거는 `temp/e12_b8_operation_mutation_evidence_20260627/evidence.json` 및
  `docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_operation_title_b81ff4_mutation_contact.png`.
  이로써 B8 compact table 중 최소 1건은 dead copy가 아니라 실화면 source임이 확정됐다. 이 증거는 source provenance이지
  글자/레이아웃 전수 품질 보장이 아니다. `data/compact_display_manual_visual_evidence.json`과 matrix builder가
  current ROM SHA, 양수 픽셀 diff, contact sheet 존재, 그룹/주소 일치 조건으로 집계하며, 현재 direct 수치는
  A2 0, B84 0, B8 1이다. `verify_dist_integrity.py`는 matrix SHA가 current output SHA와 다르거나 manual evidence가
  stale/invalid/unmatched이거나 accepted evidence가 matrix target row에 붙지 않으면 실패한다.
- **2026-06-27 B8 작전명 live source 추가 3건**: `tools/prove_compact_display_mutation.py`로 같은
  `41_part1_operation_room` route를 반복 검증했다. `0x00B82018`(`전투개시`→`검증개시`)는 diff 54px/bbox
  `[10,43,24,54]`, `0x00B8200C`(`초반전`→`검증전`)는 diff 64px/bbox `[9,59,24,70]`,
  `0x00B81FDC`(`고물전차출격`→`검증출격`)는 diff 215px/bbox `[9,91,56,102]`로 각각 해당 작전실
  리스트 행만 바뀐다. contact는 `docs/screenshots/e12_compact_display_matrix_2026-06-27/`의
  `b8_operation_title_00B82018_mutation_contact.png`,
  `b8_operation_title_00B8200C_mutation_contact.png`,
  `b8_operation_title_00B81FDC_mutation_contact.png`. 이 시점의 matrix는 manual current/accepted 4,
  direct 수치 A2 0, B84 0, B8 4였다. 2026-06-27 agy 리뷰 지적 반영 후 matrix는 accepted mutation evidence의
  `contact_sheet_sha256`, `diff_mask`, `diff_mask_sha256`를 포함하며, `verify_dist_integrity.py`도 contact SHA,
  diff mask 파일 존재, SHA 일치, non-black pixel count 일치를 배포 게이트로 확인한다.
- **2026-06-27 B8 작전명 스크롤 행 추가 4건**: `tools/prove_compact_display_mutation.py`에
  `--append-nav-step`을 추가해 `41_part1_operation_room` 뒤 DOWN 입력을 붙인 fresh route를 만들 수 있게 했다.
  DOWN 4회 위치에서 `0x00B81FC4`(`적부대격파`→`검증격파`, diff 167px/bbox `[10,75,48,86]`),
  `0x00B81FAC`(`지상최강중전차`→`검증중전차`, diff 209px/bbox `[9,91,64,102]`)가 해당 행만 바뀌었다.
  DOWN 7회 위치에서는 `0x00B81F98`(`드래곤플라이`→`검증플라이`, diff 218px/bbox `[9,59,56,70]`),
  `0x00B81F70`(`창공제패`→`검증제패`, diff 40px/bbox `[9,91,23,102]`)가 해당 행만 바뀌었다.
  `0x00B81F80`(`하늘에서오는건`)은 selected row 설명/애니메이션 프레임 diff가 섞여 bbox가
  `[0,0,240,112]`까지 커졌으므로 accepted evidence에서 제외했다. 최신 matrix는 manual current/accepted 8,
  direct 수치 A2 0, B84 0, B8 8이다.
- **2026-06-27 B8 작전명 중반부 추가 4건**: 긴 append-nav 이름이 경로 길이 한계를 넘는 문제를 막기 위해
  `tools/prove_compact_display_mutation.py`가 140자를 넘는 checkpoint 이름을
  `<base>_plus_<N>steps_<sha1-10>` 형식으로 줄이게 했다. 같은 fresh 작전실 route에서 DOWN 10회 위치의
  `0x00B81F5C`(`도그파이트`→`검증파이트`, diff 70px/bbox `[9,59,24,70]`),
  `0x00B81F4C`(`바다너머`→`검증너머`, diff 77px/bbox `[9,75,23,86]`),
  `0x00B81F40`(`백은세계`→`검증세계`, diff 48px/bbox `[9,91,23,102]`)와
  DOWN 13회 위치의 `0x00B81F38`(`결전`→`검증`, diff 58px/bbox `[9,91,24,102]`)가 행 단위로 바뀌었다.
  DOWN 16회에서 `0x00B81F2C/24/10/04`는 diff 0이라 해당 route의 direct evidence로 채택하지 않았다.
  최신 matrix는 manual current/accepted 12, direct 수치 A2 0, B84 0, B8 12/459다.
- **2026-06-27 proof hardening**: Claude/agy 리뷰에서 mutation proof의 false-positive 가능성(cursor/animation diff)과
  bbox 인과 약점을 지적했다. `tools/prove_compact_display_mutation.py`에 같은 ROM/같은 checkpoint를 한 번 더 캡처하는
  null-control을 추가했고, 작전실 proof에는 expected diff box `0,32,80,104`를 지정했다. 12개 accepted proof 모두
  null-control pixel diff 0/deterministic true, mutation diff bbox within expected box true다.
  `build_compact_display_visual_matrix.py`와 `verify_dist_integrity.py`가 null-control nonzero 또는 bbox outside를
  hard fail한다. 따라서 12건의 provenance 인과는 강화됐지만, coverage 한계는 그대로다.
- **해석 한계(Claude/agy 리뷰 반영)**: mutation proof는 source provenance 증거다. 짧은 mutation이 화면 row를
  바꾸는 것은 그 주소가 live source임을 보이지만, 실제 `ship_ko` 전체의 visual-fit, A2/B84 direct 품질,
  B8 나머지 447개, compact renderer 전용 positive control을 증명하지 않는다. 현재 증거는 Part1 작전실 계열에
  편중되어 있으므로 E12 완료 근거로 확대하지 않는다.
- **2026-06-27 A2 CO profile mutation 음성**: `scene_30f2_part2_co_profile_story`에서
  `0x00A295D8`(`강타`)를 `검증`으로 단일 mutation했지만 pixel diff 0이었다.
  temp 증거는 `temp/e12_a2_co_profile_mutation_probe_20260627_r2/summary.json`. 이 savestate+1 frame checkpoint는
  A2 compact power-name direct evidence로 쓸 수 없다. 다만 stale/cache와 화면 미진입 confound가 남으므로,
  coldboot fresh power-name route의 전역 미사용 증명으로 해석하지 않는다.
- **다음 방향**: read-watch 반복보다 B84 파워 발동, B8 유닛 상세/무기 상세/데미지예측, 실제 통신 대기문처럼
  target이 화면에 뜨는 진입점을 먼저 확보해야 한다. 필요하면 VRAM write-watch/DMA3 source 추적으로 renderer provenance를
  역추적한다.

---
## [2026-06-27] 사용자 추가 스크린샷 current 재검증과 Part1 작전실 scene checkpoint fresh 전환

- **입력 재확인**: Downloads의 사용자 추가 스크린샷 7장은
  `docs/screenshots/user_report_triage_2026-06-27/download_contact.png` contact와 일치한다.
  `docs/screenshots/user_report_triage_2026-06-27/triage.md`에 이미지별 판정을 정리했다.
- **사용자 신고 화면 판정**:
  - Part1 모드/통신 하위 메뉴의 대형 라벨 도움말 침범은 compact OBJ 라벨 수정 뒤 current fresh route에서 재현되지 않는다.
    `qa_visual_regions.py` current 실행 결과 `mode_help_intrusive_dark=0`, `single_help_intrusive_dark=0`,
    `connect_help_intrusive_dark=0`, `visual_region_checks=39`다.
  - `single_map`의 `??????` 3행은 원본 `8148` placeholder로 byte-identical인 항목이며, 깨진 한글 fallback이 아니다.
  - Part1 작전실/작전명 free-space 복사본 결함은 `0xB81D80..0xB82018` compact title 정리와 repoint 우선순위 수정으로
    ROM 화면에서는 이미 닫혔다.
- **추가 발견**: 전체 scene screenshot을 `e6ca1081…`로 재캡처하자
  `audit_scene_entrypoints.py --strict`의 stale count는 0이 되었지만,
  수동 시각 확인에서 `temp/scene_screenshots/41_part1_operation_room_patched/frame.png`가
  `2026-06-08` savestate RAM 캐시를 거쳐 깨진 작전실 문자를 표시하는 것이 드러났다.
  즉, provenance SHA audit는 current ROM 여부는 보장하지만 stale savestate 내부 VRAM/text cache 깨짐까지는 보장하지 않는다.
- **수정**: `data/screen_checkpoints.json`의 `41_part1_operation_room`을 savestate에서 coldboot fresh nav로 전환했다.
  경로는 `qa_visual_regions.py::drive_part1_menu_from_coldboot()`와 같은 Part1 post-name mode menu route를 사용하고,
  마지막에 `A`로 작전실에 들어간다. `data/scene_entrypoints.json`의 `15_part1_operation_logos`도
  `source_state`를 제거하고 `data/screen_checkpoints.json` provenance로 맞췄다.
- **검증**: fresh probe와 표준 scene capture 모두 `전투개시/초반전/전선기지확보/고물전차출격`과
  하단 `캐서 조작부터 / 공격방법도 설명이야`를 정상 표시한다.
  `python3 tools/build_scene_catalog.py`,
  `python3 tools/audit_scene_entrypoints.py --strict`(missing/stale 0),
  `python3 tools/audit_scene_catalog.py --strict`(critical 0, warning 16),
  `python3 tools/run_release_qa.py`,
  :8782 서버 기동 후 `python3 tools/run_release_qa.py --only-editor --editor --timeout 300` PASS.

---
## [2026-06-27] stale savestate 캡처와 Part2 결과 요약 full-sheet 보존 규칙

- `scene_19e7_part1_hoip_co_weather_help`와 `scene_19f_part1_extra_story`는 ROM bytes가 정상이어도
  이미 구 텍스트가 VRAM/text cache에 그려진 savestate를 그대로 캡처하면 깨진 대사처럼 보인다.
  current ROM 검증용 checkpoint는 화면 직전 state에서 입력으로 대사창을 다시 생성해야 한다.
  - `19e7`: `temp/scene_entrypoints/part1_aw1_save_placement_probe_a5/2111_front/after_route.ss0`
    + `A,A`로 `0xDF7452/0xDF7482` current text를 재렌더한다.
  - `19f`: `temp/scene_entrypoints/part1_main_sweep_stepstates/step_016.ss0`
    + `A`로 `0xDF9516/0xDF953B` current text를 재렌더한다.
- Part2 결과 요약 `0x0059DA5C` LZ77 block은 1024 tiles/256x256 source이지만, 런타임 visible layout은
  12개 sparse cell을 224x136 화면으로 조립한다. source 좌표에 직접 한글을 그리면 contact sheet에서
  `작전 성공` 주변에 원본 조각/검은 stroke가 새는 것처럼 보일 수 있다.
  단, sparse cell만 blank output에 scatter하는 방식은 안전하지 않다. 점수 숫자/랭크 stamp가 label 주변의
  즉시 보이는 cell 밖 source tile을 재사용하므로, uncovered tile을 버리면 결과 화면의 핵심 정보가 사라진다.
- 안전한 패치 절차:
  1. 원본 decompressed `data` 전체 1024타일을 256x256 layer로 복원한다.
  2. title/축하/속도/화력/기술/합계/+전체 라벨 영역과 tail scratch 영역만 지우고 한글을 그린다.
  3. 전체 1024타일을 다시 직렬화해 숫자/랭크/장식 타일을 그대로 보존한다.
  4. `lz77_compress(..., vram_safe=True)` 계열로 in-place fit을 확인한다. 현재 consumed는 10153 <= 원본 11504.
- `scene_29_part2_result_summary`도 stale `state_016`을 쓰면 구 VRAM이 유지되므로,
  pre-result `state_012.ss0`에서 `A,A`로 결과 요약을 다시 로드한다.
- 이번 sweep의 final output/dist SHA는
  `a4e98a93daf1f545f6224814b0c55d8e981f98ec16ccc3872c2f30831ec0489e`.
  기본 release QA, editor API, Chrome CDP, scene/residual strict audit, dist integrity가 모두 PASS했다.

---
## [2026-06-27] 전투 항복/모드 선택 복귀 확인창 `??????` 메커니즘

- **관찰**: B84 power-menu route probe의 contact sheet에서
  `모드 선택으로 돌아갈까??????`가 실제 에뮬레이터 화면에 표시됐다. `before_question_marks.png`와
  `after_fixed.png`는 `docs/screenshots/battle_surrender_question_fix_2026-06-27/`에 보존했다.
- **대상 주소**: 문제 문장은 `0x00A34CE8`과 `0x00DF2A64`의 동일 일본어
  `モードセレクトに戻ります。よろしいかしら？` 계열이다. 수정 전 output에는 B팀 권위문
  `모드 선택으로 돌아갈게요.괜찮을까요?`가 고정 42바이트 visible slot 안에 들어가고,
  뒤에는 원래 제어 tail `72 71` 또는 `72 51`, `6e 00`이 이어졌다.
- **확정 원인**: byte slot overflow가 아니라 화면별 renderer 표시 한계 문제다. 긴 B팀 문장은 ROM slot에는 맞지만
  전투 항복 확인창은 대략 13음절 안팎까지만 안전하게 표시했고, 그 뒤 glyph/control 해석이 fallback `?`로 무너졌다.
  같은 문장을 더 짧게 바꾸면 동일 route에서 후행 `??????`가 사라졌다.
- **비교 실험**: temp ROM에서 `모드 선택으로 돌아갈까요?`, `모드 선택으로 갈까요?`,
  `모드로 돌아갈까요?`를 각각 캡처했고 모두 후행 `?` 없이 렌더됐다. Claude/agy 리뷰 결과, 말투 보존과 의미 보존의
  균형 때문에 최종 문구는 `모드 선택으로 돌아갈까요?`로 결정했다.
- **수정 경계**: 이는 renderer를 확장한 근본 수정이 아니라, 해당 fixed 확인창의 표시 한계에 맞춘 권위문 조정이다.
  따라서 `data/bteam_baseline.json`도 함께 갱신해 B팀 drift gate가 이 의도적 변경을 보호하게 했다.
  최종 SHA는 `3e3bae3363ce429df76505d1413906f82203dfaaea35b4df3d610bbd80e902d0`이고,
  release QA/editor/dist integrity가 모두 PASS했다.

---
## [2026-06-27] E12 read-watch current-SHA 재동기화와 scene screenshot freshness

- 배경: E12 null-control 보강 뒤 ROM SHA가 `3e3bae33…`로 고정됐지만, 이전 read-watch JSON 상당수는
  `a4e98a93…`/`11098045…`/`d8be8aaf…` 등 stale SHA를 가리켰다. stale 0-hit는 현재 빌드의 음성 결과로
  해석할 수 없으므로 전부 재실행했다.
- 재실행 대상:
  - positive control `0x00A01970` fresh prologue route.
  - B8 action-menu exact/range, `after_a36` 선설치 exact.
  - B8 대표 exact current set 27개, fresh menu sweep subset, comm label `0xB83268`, rule/map-name 후보,
    map-territory 후보, battle subset/range, shop state range.
  - A2/B84 fresh profile/freshrender/profile-state range probes.
- 결과: `data/compact_display_read_watch*.json` 16개 모두 current ROM SHA가 됐고, E12 probe 합계는
  당시 45 cases, hit 0/direct target read 0이었다. 후속으로 B8 작전실 live-source positive probe를 추가해
  현재 집계는 46 cases, hit 69/direct target read 69이며, 이 69 hit는 모두 Part1 작전명 4주소다.
  general positive control은 현재 단일 fresh `08_part2_prologue_map_text` route 기준 1 case hit 8을 유지한다.
  과거 59 hit 기록은 다른 probe/route 범위의
  양성 결과로, 현재 8-hit baseline과 직접 비교해 회귀로 해석하지 않는다.
- 해석: 이 결과는 하니스 불능이 아니라, 현재 route/subset과 감시 주소가 실제 target source read를 잡지 못했다는
  최신 음성 증거다. DMA/WRAM cache, 이미 렌더된 savestate, 다른 source copy, route 미진입 가능성 때문에
  A2/B84/B8 target 미사용 증명으로 확대하지 않는다.
- codex/agy 리뷰 반영: 일반 텍스트 positive control은 compact renderer 자체의 양성대조가 아니다.
  또한 ROM read-watch는 사전 WRAM/EWRAM 캐시나 DMA 복사를 경유하는 렌더 경로를 놓칠 수 있다.
  다음 증거 확보는 실제 compact 표시가 뜨는 state에서 exact watch뿐 아니라 WRAM/VRAM/DMA write chain까지
  추적해야 한다.
- 부수: 전체 UI 에디터 screenshot provenance도 SHA 변경으로 stale가 누적되어 있었다.
  `tools/capture_scene_screenshots.py`로 58개를 재캡처했고, `audit_scene_entrypoints.py --strict`는
  audited capture 76, missing/stale 0, critical 0을 보고했다.
- codex 리뷰가 matrix의 stale dependency를 지적해 `data/compact_display_xref_analysis.json`,
  `data/compact_display_code_context.json`, `data/compact_display_renderer_trace.json`도 같은 SHA로 재생성했다.
  matrix/report는 renderer trace/code-context/xref 각각의 `current_rom`과 `rom_sha256`을 출력하고,
  `verify_dist_integrity.py`는 present dependency가 stale이면 실패한다.
- Claude 리뷰가 B8 direct 12/459 숫자의 과대해석 위험을 지적했다. 이에 matrix/report는
  manual accepted evidence를 scene/checkpoint별로 분해한다. 현재 direct 12건은 모두
  `15_part1_operation_logos`/`41_part1_operation_room` 작전명 계열이며, Part2 B8 HUD/유닛·무기·상점·데미지예측
  direct evidence는 여전히 0이다.
- B8 operation read-watch positive는 이 작전명 계열에서 ROM read-watch가 실제 target source read를 잡는다는
  양성대조다. 하지만 Part2 HUD/A2/B84 compact renderer 경로의 양성대조는 아니다.
- 이 read-watch에서 관측된 reader PC를 trace breakpoint에 추가하자
  `41_part1_operation_room` 및 `scene_87_common_rule_settings`에서 breakpoint hit가 발생했다.
  current trace 전체는 10 cases, hit 1762, direct target register hit 0이다. 레지스터에는 exact target 주소가
  직접 남지 않아 matrix direct evidence는 늘지 않는다. 따라서 trace hit는 “하니스/PC 양성대조”이고,
  unproven A2/B84/Part2-B8 source provenance는 여전히 read-watch/mutation/WRAM-DMA chain으로 별도 확보해야 한다.
- matrix 현황: A2 target 36/editor 36/current screen capture 1/direct 0, B84 11/editor 11/direct 0,
  B8 459/editor 459/direct 12다. B8 direct 12는 Part1 작전실 mutation source provenance이며,
  A2/B84 또는 B8 전체 visual-fit 보장이 아니다.

---
## [2026-06-27] Part1 compact 도움말 공백 복원 원인과 검증 경계

- **원인**: 사용자 추가 스크린샷 후속 확인에서 보인 Part1 모드/대전/통신 하단 도움말 가독성 문제는
  renderer나 비트맵 손상이 아니라 `ADDRESS_TEXT_OVERRIDES` `0xDFA64A..0xDFA9E9`의 화면 전용 문구 선택 문제였다.
  이전 결함인 대형 OBJ 라벨의 강한 도움말 침범은 compact 라벨 자산 수정으로 닫혔지만,
  도움말 문자열은 `전투법알려줄게`, `와서들어봐`, `처음부터대전`, `친구와연결해`처럼 공백 없는 임시 축약으로 남아 있었다.
- **slot 사실**: 실제 빌드 인코더의 `encode_fit()`으로 후보 문구를 검사하면
  `전투 방법 알려 줄게`, `와서 들어 봐`, `둘부터 넷까지`, `대전 가능`, `처음부터 대전`,
  `친구와 연결해`, `카트리지 하나로` 등이 모두 level 0으로 원래 fixed slot 안에 들어간다.
  따라서 공백 제거는 기술적 필수가 아니었고, 의미/가독성 손상만 남긴 축약이었다.
- **수정 경계**: Part1 option OBJ 라벨은 원본 엔진 구조상 반투명 도움말 박스 뒤로 지나갈 수 있다.
  이번 수정의 판정 기준은 겹침 0이 아니라 도움말 텍스트가 라벨보다 읽히고, 문구 자체가 자연스러운가이다.
  `qa_visual_regions.py`의 `mode_help_intrusive_dark=0`, `single_help_intrusive_dark=0`,
  `connect_help_intrusive_dark=0`과 mGBA fresh capture로 이를 확인했다.
- **증거**: `docs/screenshots/part1_menu_help_spacing_2026-06-27/contact.png` 및
  `docs/screenshots/part1_menu_help_spacing_2026-06-27/help_crops_4x.png`.
  Claude/agy 리뷰 후 current fresh route 30프레임(mode 9, operation 8, single 7, link 6)을 추가 캡처했고,
  `docs/screenshots/part1_menu_help_spacing_2026-06-27/full_sweep_contact.png`에 보존했다.
  최신 output/dist SHA는 `b9eea881356404e4643fadd6ca4f6d9bb7dcc31a649c1a928a7777ff170418b7`.
- **검증 한계**: 이 30프레임 route는 operation/single/link 계열 도움말을 직접 확인하지만,
  fresh route에서 잠겨 있거나 진행도 조건이 필요한 campaign/hidden/player-count 계열 도움말은 아직 직접 진입 증거가 없다.
  또한 `qa_pixel_width.py`의 전역 ASCII/반각공백 4px 근사는 Part1 도움말 renderer의 실제 공백 advance와 다를 수 있다.
  이에 따라 `tools/qa_part1_compact_help.py`를 추가했다. 이 도구는 해당 범위 34개 override의
  current ROM prefix, tail padding, 1바이트 printable 부재, level 0 fit, 보수 상한 24 half-cell 이하를 hard gate로 검사한다.
  Claude 리뷰 후에는 한글 코드 lead max가 현재 분류기 상한 `0xE2`를 넘지 않는지,
  tail이 없는 full-slot row의 직후 바이트가 `00/0A/6B/70/71/72/77` 계열 제어바이트인지도 검사한다.
  현재 target 34/issue 0이며 `verify_dist_integrity.py`와 `run_release_qa.py`에 연결됐다.
  단, direct visual evidence 13개는 자동 OCR/주소 매핑 검증이 아니라 수기 capture metadata이며,
  21개는 계속 `todo.md` E16의 route 확보 대상으로 남긴다.
- **별도 판정**: `single_map`의 `??????` 3행은 원본 `0x00DF8C2A`의 `8148` x 6 placeholder와 byte-identical이며,
  한글 fallback 깨짐이 아니다. Part1 작전실 도움말 하단의 `커서 조작부터 / 공격방법도 설명이야`도 current fresh route에서
  정상 렌더되는 문구로 확인했다.
- **E12 동기화**: SHA 변경 때문에 E12 manual mutation evidence 12건, matrix, xref, code-context, renderer trace를
  current ROM으로 재생성했다. current trace는 10 cases, breakpoint hit 1775, direct target register hit 0이다.
  direct evidence는 여전히 A2 0, B84 0, B8 12/459이며, B8 12건은 모두 Part1 작전명 source provenance다.
  이 동기화는 stale evidence 제거이지 E12 완료 근거가 아니다.

---
## [2026-06-27] Part1 compact 도움말 unlocked save route와 증거 승격 기준

- **route**: 진행도 조건이 필요한 Part1 메뉴 도움말은 기존 savestate보다 외부 AW1 진행도 save를
  `loadtempsav` 후 reset/coldboot 메뉴로 진입하는 편이 stale VRAM/RAM 위험이 작다.
  이를 위해 `tools/probe_part1_compact_help_reads.py`에 `--tempsav`와 `tempsav_part1_menu` 시작 모드를 추가했다.
- **확인된 source**: AW1 unlocked save route에서 현재 ROM
  `dee641f76e9c450cbc7d73e8f1b4d7160faa432c2e4d85518f5b81ea94ea4484` 기준
  `0x00DFA68C`(전적), `0x00DFA71B`/`0x00DFA72E`(맵 디자인),
  `0x00DFA6E2`/`0x00DFA6FB`(shop)가 최종 화면 도움말과 직접 대응했다.
  증거는 `docs/screenshots/part1_unlocked_menu_help_2026-06-27/`의 contact/crop/read-watch report에 보존했다.
  shop은 AW1 8495-front tempsav에서 `DOWN` x8 후 최종 화면이 `워즈 코인으로`/`물건 살 수 있어`를
  표시하는 route만 승격했고, raw watch의 중간 메뉴 hit는 증거 count에 넣지 않았다.
- **승격 기준**: read-watch hit만으로는 direct visual evidence로 승격하지 않는다.
  최종 frame이 해당 문구를 실제로 보여 주고, crop/contact와 watch target이 같은 route에서 맞물릴 때만 승격한다.
  이전 campaign/shop 후보처럼 read-watch hit가 있어도 최종 frame이 다른 도움말을 보여 주면 evidence count에 넣지 않는다.
- **라벨 조정**: 사용자 스크린샷의 도움말 침범 계열을 줄이기 위해 Part1 submenu label 중
  `싱글 대전`/`통신`을 제외한 항목을 저프로파일 렌더로 바꿨다. 두 특수 라벨은 visual gate가 상단 가시성을
  직접 보는 기존 대표 항목이라 유지했다.
- **현재 경계**: `qa_part1_compact_help.py`는 current direct evidence 18/missing 16으로 갱신됐다.
  미확보 16개는 campaign/hidden/player-count 등 별도 진행도 route가 필요하며 `todo.md` E16에 남긴다.

---
## [2026-06-27] Part1 싱글 대전 룰 원형 라벨 LZ77 OBJ 수정

- **발견**: E16 잔여 route 탐색 중 AW1 8495-front `loadtempsav` 후 current ROM으로 메뉴를 다시 렌더해
  `싱글 대전 -> 맵 선택 -> CO/룰 설정` 흐름에 들어가자 원형 룰 버튼의 상단/내부 텍스트가 일본어로 남았다.
  확인된 잔존은 `サクテキ`, `テンキ`, `収入`, `日数`, `ユウセイ`, `能力`, `アニメ` 및
  `アリ`, `ランダム`, `ナシ`, `タイプA` 계열이다. agy/Claude 리뷰 모두 Part2 기존 룰 요약 패치가 아니라
  Part1 전용 리소스 결함으로 판정했다.
- **원인/위치**: OAM tile trace에서 라벨 tile은 80/88/96/104/112/120/290, 값 tile은
  128/136/144/152/160/168/386/390/394로 확인됐다. 해당 tile block은 ROM raw가 아니라
  LZ77 block `0x00C2C6EC`의 decompressed sheet에 있으며, 원본 decompressed SHA16은
  `131a4e7eac41a812`, slot consumed는 4792B다.
- **수정**: `tools/build_korean_full.py`에 `patch_part1_rule_circle_labels()`를 추가했다.
  `_render_rule_label_obj()`를 재사용해 `정찰/날씨/수입/일수/우세/능력/애니` 7개를 32x16 OBJ로,
  `_render_value_obj(..., 4)`로 `있음/랜덤/눈/없음/맑음/있음/타입A/B/C` 9개를 4타일 값 OBJ로 렌더한다.
  새 압축 크기는 3904B로 원 slot 4792B보다 작아 in-place LZ77 재압축이 가능했다.
- **검증**: 같은 mGBA route로 재캡처한 실제 화면에서 원형 라벨/값이 모두 한글로 표시된다.
  VRAM object base `0x10000` 기준 `tile*32` 위치 16개가 빌드 렌더 바이트와 일치했다.
  증거와 전후 이미지는 `docs/screenshots/part1_rule_circle_labels_fix_2026-06-27/`에 보존했다.
- **부수 동기화**: output SHA가 `c1d1b28909d318373a58603d08f2bdf55e9a774af960a8cbee61902a38957280`로 바뀌면서
  dist BPS/IPS, scene screenshot, E8 visual reverify, E12 matrix/xref/code-context/trace, scene residual evidence를
  current SHA로 재생성했다. E12 manual mutation evidence는 기본 `41_part1_operation_room` 4건과
  DOWN 4/7/10/13 스크롤 route 8건을 current ROM에서 다시 캡처해 12건 모두 유지한다.
  각 proof는 same-ROM null-control diff 0, expected box 내부 bbox true다.
- **현재 한계**: 이 수정은 Part1 룰 원형 bitmap/OBJ 잔존을 닫은 것이며,
  E12 compact target 전수 provenance나 E16 잔여 Part1 도움말 16개 route 확보를 완료하지 않는다.

---
## [2026-06-27] Part1 unlocked mode carousel 도움말 뒤 격자 artifact OAM 추적

- **관찰 route**: AW1 8495-front save
  `temp/scene_entrypoints/part1_aw1_save_placement_probe_a5/8495_front/game_wars_korean_full.sav`를
  `loadtempsav` 후 reset/coldboot 메뉴로 진입하고, current ROM SHA
  `fb760c651b0e036afb7e3b725291f13bfe489613f8c0b075110c2094ab2c5093`에서 `DOWN` 1회 또는 3회를 누르면
  도움말 박스 왼쪽 위에 작은 검은/노랑/초록 격자성 블록이 보인다.
- **OAM 사실**: `temp/e16_unlocked_artifact_oam_20260627/covering_oam.json` 기준 해당 ROI를 덮는 OBJ는
  idx 30 하나뿐이다. 속성은 x=-4, y=100, 64x32, tile 504, priority 3, OBJ palette 8, 4bpp다.
  `dumpvram` + OBJ palette render에서 1D tile 해석
  `temp/e16_unlocked_artifact_oam_20260627/oam30_tile504_pal8_1d.png`는 `트라` option label half로 보인다.
- **중요한 반증**: `make_part1_option_block()` 실험만으로는 이 artifact를 없애지 못했다.
  option text를 block 내부 y=-3으로 올린 temp ROM은 VRAM tile의 `트라` bbox를 위로 이동시켰지만,
  화면 crop의 격자성 블록은 유지됐다. `trial/campaign` option block의 왼쪽 64x32 half를 통째로 blank 처리한
  temp ROM에서도 같은 블록이 유지됐다. 증거는
  `temp/e16_shifted_option_compare_20260627/crops/base_shifted_artifact_crops.png`와
  `temp/e16_blankleft_option_compare_20260627/crops.png`.
- **추가 반증**: option label palette index를 11/12/13으로 바꾼 temp ROM
  `temp/e16_option_palette_tests_20260627/`에서도 ROI의 격자성 블록은 줄지 않았다. 또한
  `trial/campaign` option block 전체를 blank 처리한 `temp/e16_option_blank_tests_20260627/blank_trial_campaign.gba`는
  실제로 OAM idx30 tile504의 VRAM bytes를 0으로 바꿨다(`temp/e16_blank_oam_match_20260627/` 기준 1D/2D nonzero 0).
  그런데 최종 composited frame의 격자성 블록은 남았다. 따라서 `OBJ idx30/tile504` option glyph 단독 원인은 배제하지만,
  어느 레이어/타일맵이 실제 픽셀을 만드는지는 아직 확정하지 못했다.
- **중간 결론**: visible artifact는 단순 `PART1_MODE_OPTION_BLOCKS` 글자 위치/크기 문제가 아니다.
  option carousel OBJ와 겹치는 별도 BG/cache/tilemap 잔상, 원본 메뉴 배경 조각, 또는 tile provenance 식별 오류 가능성을 남긴다.
  따라서 option label을 더 작게 만들거나 특정 half를 지우는 패치는 취약하고, 원본 baseline 및 레이어별 관측 전에는
  채택하지 않는다.
- **원본 baseline**: 원본 일본판 ROM
  `original/Game Boy Wars Advance 1+2 (Japan).gba`에 같은 8495-front save를 로드하고, title -> 1편 -> mode select
  route의 원본 mode sweep을 캡처했다(`temp/e16_original_mode_sweep_20260627/contact.png`,
  영구 증거 `docs/screenshots/part1_unlocked_original_baseline_2026-06-27/original_mode_sweep_contact.png`).
  원본의 `down1/down3/up1/up5/up7` 등에서도 같은 빨간 ROI 위치에 주황/검은 격자성 조각이 도움말 박스 뒤로
  보인다. 따라서 이 증상은 한글 option label 패치가 만든 회귀가 아니라 원본 메뉴의 투명 도움말 뒤 배경/라벨 합성이다.
  한글판에서 자산을 강제로 지우는 패치는 원본 동작을 바꾸는 화면별 hack이므로 채택하지 않는다.
- **부수 route 결과**: 같은 save에서 `DOWN` 1..10 및 `DOWN` x6 -> 통신 하위 item 0..4 `A`를 current ROM으로
  probe했지만, E16 missing 16개 도움말 주소와 교차한 direct target은 0이었다. 확인된 것은 기존 visible evidence 계열
  `0xDFA68C/6AA/6CD/6E2/6FB/71B/72E/752/775/79A/942/95B/972/989/9AE/9C7/9DA/9E9`뿐이다.
- **추가 route 결과**: 8495-front `UP` 1..8도 missing 16과 교차 0이었다. 2111/2113/2954 front의
  `after_route.ss0` state route 기본 입력은 `0xDFA752/775/79A`만 재확인했고, 2111 campaign에서 `A` 후
  `DOWN/UP/A/B`를 눌러도 missing 16과 교차하지 않았다. 11186/2111/2112 front를 `loadtempsav+reset`으로
  coldboot route에 넣는 방식은 일부 save에서 전투맵으로 지나쳐 help watch 0을 만들므로, 이 save들의 메뉴 증거는
  stale caveat가 있더라도 `after_route.ss0`에서 입력 후 새 read가 발생한 경우만 사용한다.

---
## [2026-06-27] Part1 campaign compact 도움말 direct route 4건

- **route**: `temp/scene_entrypoints/part1_aw1_save_placement_probe_a5/2111_front/after_route.ss0`는
  Part1 mode menu에서 작전룸에 커서가 있는 state다. 여기서 `UP,A`를 누르면 campaign continue 선택 화면으로 들어가고,
  최종 프레임은 `이어서 캠페인 / 진행 가능`을 표시한다. `UP,A,DOWN` 또는 `UP,A,UP`은
  `처음부터 캠페인 / 시작해요`를 표시한다.
- **direct target**: read-watch 기준 `UP,A`는 `0xDFA80E/0xDFA829`,
  `UP,A,DOWN` 및 `UP,A,UP`은 `0xDFA7E2/0xDFA7FD`를 최종 프레임 visible 문구와 함께 확인한다.
  증거는 `docs/screenshots/part1_campaign_help_2026-06-27/contact.png`,
  `help_crops_4x.png`, `read_watch_continue.json`, `read_watch_new_down.json`,
  `read_watch_new_up.json`.
- **승격 경계**: 같은 read-watch에서 `0xDFA83A/0xDFA84D` hidden 후보도 hit하지만, 최종 프레임에
  `특별한 처음부터 / 숨겨진 모드`가 보이지 않는다. 따라서 이 둘은 direct visual evidence로 세지 않는다.
- **QA 반영**: `tools/qa_part1_compact_help.py`의 current visual evidence set은 18 -> 22로 증가했다.
  남은 direct visual route 미확보 주소는 `0xDFA64A/66B/7BE/83A/84D/872/885/8AA/8CB/8EA/90A/926`이다.

---
## [2026-06-28] E16 Part1 compact 도움말 renderer item-code 구조와 read-hit 경계

- **사용자 스크린샷 입력 재확인**: `~/Downloads`, Desktop, Pictures에서 최근 스크린샷을 다시 훑었고,
  새로 분리할 이미지는 `docs/screenshots/user_report_triage_2026-06-27/download_contact.png`의 7장과 같은 계열이었다.
  current ROM 증거 기준 작전실 작전명, `single_map` unknown label, Part1 메뉴 도움말 가독성, 룰 원형 라벨은
  기존 수정 증거로 닫혀 있다.
- **pointer-table xref**: Capstone으로 current ROM을 확인한 결과 Part1 compact 도움말 pointer table
  `0x08DFAAB8` literal은 파일 offset `0xB4AF48` 부근에서 참조된다. 주변 도움말 renderer는 현재 menu item code를
  읽고 `code & 0x7F`로 table index를 만든 뒤 해당 도움말 pointer를 고르는 구조로 보인다.
- **player-count 해석**: `0xDFA8AA/0xDFA8CB/0xDFA8EA/0xDFA90A/0xDFA926` 계열은 table상
  player-count item code가 실제로 활성화되어야 화면에 뜨는 후보로 해석한다. 단순 `DOWN×5,A,A`
  map/team setting, 통신 하위 메뉴, `SELECT/L/R` 도움말 트리거로는 이 item code가 최종 프레임에 유지되지 않았다.
- **`0xDFA7BE` 경계**: map/team 계열 probe에서 `0xDFA7BE` read-hit가 반복되지만, 최종 frame은 맵 선택,
  CO 선택, battle submenu 등이고 `이어서 대전` 문구가 보이지 않는다. 따라서 현재 증거로는 read-ahead,
  transient menu cache, 또는 표시되지 않는 후보 pointer read일 수 있으며 direct visual evidence로 승격하지 않는다.
- **다음 route 가설**: 실제 VS suspend/continue SRAM을 만든 뒤 `처음부터/이어서 대전` 선택 화면에 진입하거나,
  hard/hidden campaign unlock이 반영된 save로 hidden campaign item code를 열거나, AW2 free battle/진짜 player-count
  선택 화면을 확보해야 남은 12개 direct visual evidence를 닫을 가능성이 높다. 이 결론은 disassembly 기반 추론이며,
  target 미사용 증명이 아니다.

---
## [2026-06-28] E16 broad state scan 및 forced-render smoke 사실

- **메뉴 state dump 요약**: current Part1 compact 메뉴 object는 `0x02000000` 기준 `+0x2F` cursor,
  `+0x30+cursor` item code를 사용한다. current fresh route에서 확인된 active code 배열은
  mode menu `[10,13,20,10,13,20]`, single submenu `[14,14]`, link submenu `[22,21,23]` 계열이다.
  따라서 잔여 code `0/5/6/9/16/17/18/19`는 일반 fresh mode/single/link route에 없다.
- **광역 state scan**: `temp/e16_state_menu_code_scan_broad_20260628/report.json`은 Part1/AW1/E16/menu/single/link/
  campaign/freebattle 이름이 걸리는 `temp/**/*.ss0` 8,085개를 current ROM으로 로드해 `0x02000000..0x020000FF`
  메뉴 RAM을 덤프한 결과다. plausible active menu 후보 중 잔여 code 5/6/16/17/18/19는 발견되지 않았다.
  code17 후보 1건(`temp/final_original_vs_final_20260615/original_menu.ss0`)은 active length 뒤 tail 값으로,
  `temp/e16_original_menu_tail_direct_probe_20260628/report.json`의 입력 probe에서도 잔여 target read 0이었다.
- **RAM-only 주입 반증**: `w8 0200002F 00`와 `w8 02000030 <code>`로 item code만 바꾼 뒤 frame을 진행해도
  help source read가 발생하지 않았다. menu redraw/update path를 타지 않으면 help renderer가 다시 실행되지 않는다.
- **forced-render smoke 방법**: current ROM temp 복사본에서 help pointer table `0x08DFAAB8`의 visible code
  `10/13/20/14/21/22/23` entry를 잔여 pointer로 바꾼 뒤, current Part1 menu state에서 `DOWN/UP` 입력으로
  실제 redraw를 유도했다. 대상 pointer는 code0=`0x08DFA648`, code5=`0x08DFA838`, code6=`0x08DFA870`,
  code9=`0x08DFA7BC`, code16=`0x08DFA8A8`, code17=`0x08DFA8E8`, code18=`0x08DFA908`,
  code19=`0x08DFA924`다.
- **forced-render 결과**: `docs/screenshots/part1_compact_help_forced_render_2026-06-28/contact.png` 기준
  잔여 12개 문구는 실제 Part1 compact help renderer에서 모두 깨짐/클리핑 없이 표시된다. 단 이 방법은
  pointer table을 synthetic하게 바꾼 temp ROM smoke test이므로, route-specific direct visual evidence는 아니다.

---
## [2026-06-28] E16 VS suspend save route와 `이어서 대전`

- **route 정정**: Part1 top-level mode menu에서 current single battle은 `DOWN×1,A`다.
  이전 `DOWN×5,A,A` 계열은 link/통신 또는 다른 하위 화면으로 들어가므로 VS continue 생성 route로 쓰면 안 된다.
- **battle 저장 메뉴**: 싱글 대전 battle 진입 뒤 `START`는 미니맵 overlay를 켠다. 저장/상황 메뉴는 `SELECT`다.
  battle에서 `SELECT`를 누르면 우측 명령 메뉴가 나오고, `A,DOWN,DOWN,A`가
  `현재 상황 저장할까요 / 예 아니` 확인창으로 이어진다. 여기서 `A`는 `예` 저장이다.
- **SRAM 재진입**: 위 방법으로 만든 SRAM을 `loadtempsav+reset`한 뒤 title/select에서 1편으로 들어가면
  mode menu의 single battle 진입 후 submenu 첫 항목이 `이어서 대전`으로 바뀐다.
- **direct evidence**: `docs/screenshots/part1_vs_continue_help_2026-06-28/contact.png`의
  `06_single_continue_a` frame은 `이어서 대전`을 최종 표시하고, `read_watch_report.json`은
  `0x00DFA7BE` read-hit를 기록한다. 따라서 `0xDFA7BE`는 direct visual evidence로 승격한다.
  read-ahead로 같이 잡히는 campaign new 도움말 `0xDFA7E2/7FD`는 해당 frame의 visible 문구가 아니므로
  이 route의 direct evidence로 세지 않는다.

---
## [2026-06-28] E16 Part1 compact menu code writer 및 live-code injection 경계

- **리뷰 결론**: agy/Claude 모두 입력 brute-force보다 `0x02000030` item-code 배열 write-watch로 메뉴 builder를
  역추적하라고 지적했다. 단순 top-level sweep, 8,085개 ss0 active-code scan, unlock save campaign branch 반복은
  분기 조건을 모르면 음성 증거만 쌓인다.
- **write-watch 결과**: `0x0200002C..0x0200006B` write-watch 기준, Part1 compact menu object는
  `0x02000000+0x2F` cursor와 `+0x30+cursor` item code를 사용한다. 주요 writer/readback 후보는
  `0x08B4AF50`(slot/code source copy), `0x08B4AF08`(current code로 help pointer 선택),
  menu builder/update 쪽 `0x08B4B1F0`, `0x08B4B654`, `0x08B4BCBC` 계열이다.
- **현재 active code 관측**:
  fresh top mode는 `[10,13,20,10,13,20]`, single submenu는 `[14,14,14,14]`,
  link submenu는 `[22,21,23,22,21,23]`다. external AW1 unlocked campaign branch는 save별로
  `[4,3,4,3]` 또는 `[3,3,3,3]`을 만들며, code5/6 hidden campaign item은 아직 real route에서 관측되지 않았다.
  8495-front 일부 state의 `[1,26,7,13,20,29]`는 unlocked top-level carousel/상점/맵 디자인 계열로 보이며
  잔여 hidden/player-count code가 아니다.
- **source table 주의**: `0x08B4AF50`은 `0x08DFAB40` 주변 메뉴 정의 테이블을 참조하지만, 이 영역은 item code만의
  단순 배열이 아니다. 그래픽/좌표/포인터성 필드가 섞여 있고, 실제 표시 code list는 `0x0201FF85/96/97`
  RAM 보조 배열과 메뉴 builder의 복사/정렬 루프를 거쳐 `0x02000030...`에 형성된다.
- **live-code injection smoke**: pointer table을 고치지 않고 current menu object의 `+0x2D/+0x2E/+0x2F`와
  `+0x30...` item code만 `0`, `5/6`, `16..19`로 주입한 뒤 실제 cursor 이동을 눌렀다. 이 경우
  `0x08B4AF08`의 실제 `code & 0x7F -> 0x08DFAAB8` lookup과 help renderer를 그대로 사용한다.
  결과 code0, code5/6, code16..19의 남은 11개 문구가 모두 read-watch와 최종 화면에서 정상 표시됐다.
  증거는 `docs/screenshots/part1_compact_help_live_code_injection_2026-06-28/`.
  2026-06-28 후속 재실행으로 report 2종은 current SHA `f95a8573...` 직접 캡처가 됐고,
  `qa_part1_compact_help.py`의 carry-forward 인정은 더 이상 필요하지 않다.
- **경계**: live-code injection은 pointer-table forced-render보다 강한 smoke지만, 실제 게임 진행/해금 조건으로
  해당 item code가 active menu에 올라오는 route proof는 아니다. E16 direct debt는 code0 VS 헤더, code5/6 hidden
  campaign, code16..19 player-count 화면의 real route 확보까지 유지한다.

---
## [2026-06-28] E12 B8 작전명 `0xB81F80` live-source proof 및 rule-settings dead-copy 경계

- **B8 작전명 추가 live source**: `41_part1_operation_room` DOWN 6 route에서
  `0x00B81F80`(`하늘에서오는건`)이 화면 리스트 4번째 행에 보인다. 같은 주소를
  `하늘에서검증건`으로 단일 mutation하면 current ROM에서 row-local pixel diff 66px가 발생한다.
  null-control은 0px이므로 cursor/animation false-positive는 아니다.
- **길이 조건**: 같은 주소를 더 짧은 `검증오는건`으로 바꾸면 bbox가 `[0,0,240,112]`까지 퍼졌다.
  이 화면은 선택/배경/title cache와 작전명 문자열을 함께 쓰는 레이어가 있어, source proof용 mutation은
  원래 음절 수를 유지해야 row-local 증거가 된다.
  정확한 cascade 원인은 아직 미확정이다. 후보는 문자열 폭 변화로 인한 list redraw/tile reuse, 배경 title cache와
  selected-description cache의 동시 갱신, 또는 padding 영역 처리 차이다. 따라서 이 주소 계열의 mutation proof는
  같은 음절 수 또는 동일 encoded 길이를 유지하고, null-control 및 bbox 가드를 함께 둔 경우만 row-local evidence로 채택한다.
- **current read-watch**: `data/compact_display_read_watch_current_exact.json`을 현재 SHA
  `fb760c65...`로 재실행한 결과 4 route 중 `41_part1_operation_room`만 target read를 냈다.
  direct targets는 `0x00B81F80` 10회, `0x00B81FF4` 15회, `0x00B82018` 18회다.
  관측 PC는 `0x08B12A82`, `0x08B12ABC`, `0x08B12B14`, `0x08B12B2E` 및 IWRAM mirror 실행부
  `0x03006460/03006464/0300660C/0300660E` 계열이다.
- **rule-settings map-name 음성**: `scene_87_common_rule_settings`에 보이는 `소라 마메 섬` 화면에서
  `0x00B827AC`(`소라마메섬`)만 `검증마메섬`으로 mutation해도 pixel diff 0이었다.
  따라서 이 화면의 현재 맵명은 B8 `0xB827AC` row가 아니라 A2C 계열 복사본/별도 renderer/cache를 쓰는 것으로 본다.
  이 음성 결과는 target 미사용 전역 증명이 아니라 해당 route의 direct evidence 부적합 판정이다.

---
## [2026-06-28] E12 B84 AW1 CO 파워명 컷인 `0x00B84F04` route/fix 확정 및 hook 정정

- **실제 깨짐**: AW1 전투 중 CO 파워 row 2 발동 route에서 `0x00B84F04`가 `하이퍼수리` 대신
  가나 조각처럼 표시됐다. pre-fix 증거는
  `temp/b84_aw1_power_select_probe_20260628/rec1_meter_100k/row_2/contact.png`다.
- **route 조건**: player record base는 `0x0201AD38`, stride `0x68`, rec1 gauge/current charge는
  `0x0201ADC0`이다. rec1 `+0x20 = a0860100` 상태에서 메뉴 row 2를 선택하면
  B84 pointer table `0x08DF2B54`가 `0x08B84F04`를 가리키고, renderer `0x08B3C184`가
  `0x08B842E8` 2바이트 사전으로 glyph index를 찾는다.
- **중간 실패 1**: 첫 후크는 `0x08B3C1DE` copy site의 literal pool을 2바이트 밀어 배치했다.
  `ldr r0,[pc,#0x1c]`가 `0x06010000`이 아니라 `0x0000BF00`을 읽어 VRAM 목적지 계산이 틀렸고,
  화면에는 일부 잔여 조각만 남았다.
- **중간 실패 2**: literal 정렬을 고친 뒤에도 `0x08B3C1DE -> 0x08F30680` copy-site hook은
  `0x08B3C184` 공용 compact renderer 안의 shared copy path를 가로챘다. B84 파워명 외의 Part1 compact 메뉴/scene
  capture route에서도 이 renderer가 사용되어, stale live-code evidence 재생성 및 `qa_visual_regions.py` fresh route에서
  invalid address loop(`7DC93Bxx` 계열)가 발생할 수 있었다.
- **최종 수정**: `tools/build_korean_full.py`는 B84 글리프를 16x32 4bpp OBJ 타일로 생성하고
  원본 LZ77 glyph source `0x00BC9D0C`의 26개 사전 glyph를 한글로 교체한다.
  copy-site hook은 비활성화하며, `0x08B3C1DE` bytes는 원본 prefix `500800023818`로 복원했다.
  재압축은 roundtrip과 size check를 빌드 중 강제한다. `b84_power_title_glyphs.method`는
  `lz77_source_only`, `copy_site_hook`은 `disabled_shared_renderer`로 기록된다.
- **검증**: current SHA `e1919e48b283026bbb353a1fb2bd623229fd1893f6dfe13c6029f778d8ed0ac1`에서
  B84 body reads 157, pointer reads 2를 기록했다.
  `docs/screenshots/b84_aw1_power_title_fix_2026-06-28/contact.png`와
  `title_best_crop_4x.png`는 `하이퍼수리`가 컷인에서 정상 표시됨을 보인다.
  `qa_visual_regions.py`, `verify_dist_integrity.py`, `run_release_qa.py`도 PASS.
- **당시 범위**: 이 증거는 B84 11개 중 `0x00B84F04` 1건의 runtime source + visual proof였다.
  나머지 B84 파워명 10개는 후속 CO-id selector proof로 닫혔고, A2 profile 파워명과
  B8 Part2 HUD/상점/무기/데미지예측 계열은 계속 별도 증거가 필요하다.

---
## [2026-06-28] Part1 작전실 compact 제목 가독성 보강과 E12 freshness 재동기화

- **사용자 스크린샷 재대조**: 최근 `~/Downloads` 7장 contact와 current fresh route를 다시 비교했다.
  이전에 보이던 Part1 mode/single/link 라벨 덮침은 current ROM에서 재현되지 않았고,
  single-map unknown은 `미공개`로 정상 표시된다. 남은 체감 문제는 작전실 compact title이
  `전투개시`, `전선기지확보`, `키쿠치요실수`처럼 공백 없이 붙어 보여 깨진 제목처럼 보이는 점이었다.
- **수정 범위**: `tools/build_korean_full.py`의 Part1 B8 작전명 override 32개를 슬롯 안에서 짧고 읽히는 제목으로
  조정했다. 긴 제목은 피하고 fullwidth space까지 포함해 `전투 개시`, `전선 기지 확보`,
  `고물 전차 출격`, `특수부대 도미노`, `은빛 세계`, `호이프 해군` 같은 형태로 맞췄다.
- **검증 도구 주의**: `tools/prove_compact_display_mutation.py`는 기존 `encode_text()` 직접 호출 대신
  build `encode_fit(text, slot, addr=...)`을 사용한다. Part1 compact title은 공백을 fullwidth `0x8140`으로
  인코딩하고 slot별 폭/패딩 정책을 거치므로, mutation proof도 build와 같은 encoder를 써야
  `old_hex`/`base_encoded_hex` 비교가 맞는다.
- **current SHA 재동기화**: 새 output SHA는
  `f95a857354a84119452b69bdabb371c6f390e0ecd4faf13bc56d5208ec1bb292`다. 이 SHA 기준으로
  B8 작전명 mutation evidence 13건, B84 `0x00B84F04` read-watch, xref/code-context/renderer trace,
  scene screenshot 70개, scene residual evidence, BPS/IPS manifest를 모두 재생성했다.
  `data/compact_display_visual_matrix.json`의 direct 수치는 A2 0/36, B84 1/11, B8 13/459다.
- **경계**: 이번 변경은 사용자 화면 가독성 결함 수정과 evidence freshness 복구다.
  B8 direct evidence는 여전히 Part1 작전실 편중이며, A2/B84 나머지와 Part2-B8 HUD/상점/무기/데미지예측 계열은
  route-specific read-watch, mutation diff, 또는 WRAM/VRAM/DMA chain 증거가 필요하다.

---
## [2026-06-28] 사용자 추가 스크린샷 current triage 및 B8 DOWN16 음성

- **스크린샷 출처**: `temp/user_added_screenshots_20260628/manifest.json`은
  `~/Downloads/스크린샷 2026-06-26 오후 4.57.xx~4.58.xx.png` 7장을 가리킨다.
  보존본은 `docs/screenshots/user_report_triage_2026-06-28/`이다.
- **current 비교**: current SHA `f95a8573...`에서 같은 계열 fresh route를 재캡처하면
  Part1 mode/single/link 하단 도움말 침범, `single_map ??????`, 1카드/멀티카드/맵교환 깨짐은 재현되지 않는다.
  이는 기존 라벨 축소, 도움말 공백 복원, `미공개` hook, 작전실 compact title 정리 패치가 current ROM에서
  정상 작동함을 교차 확인한 것이다. 작전실도 `current_operation_room_contact.png` 기준 공백 있는 compact title이
  정상 표시된다.
- **B8 DOWN16 확인**: 과거 stale SHA probe가 힌트를 남겼던 `0x00B81F04/10/24/2C`
  (`하늘 용사`, `건 파이터`, `개전`, `과외수업`)은 current SHA에서 DOWN 16 route로 다시 mutation proof를 실행해도
  pixel diff 0이다. 영구 보존 요약은
  `docs/screenshots/user_report_triage_2026-06-28/e12_b8_down16_negative_summary.json`이다.
  이 route의 최종 프레임은 해당 주소를 화면 source로 쓰지 않는 것으로 본다.
- **해석 경계**: DOWN16 음성은 해당 route의 direct proof 부적합 판정이지, 네 주소의 전역 미사용 증명이 아니다.
  E12 추가 증거는 다른 작전실 state나 Part2 compact renderer route에서 target-level read/diff/VRAM chain을 따로 잡아야 한다.

---
## [2026-06-28] E12 read-watch current SHA 전량 재동기화

- **현상**: 이전 matrix는 current ROM SHA가 `f95a8573...`인데도 read-watch probe 19개 중 18개가 stale SHA를
  가리켜, read-watch evidence가 실제 current state를 충분히 뒷받침하지 못했다.
- **조치**: `tools/probe_compact_display_reads.py`로 기존 19개 `data/compact_display_read_watch*.json`을 모두
  current ROM 기준으로 재실행했다. `tools/build_compact_display_visual_matrix.py` 재생성 후 read-watch probes는
  current 19/stale 0, cases 41, hits/direct reads 144가 됐다.
- **A2 direct read**: `data/compact_display_read_watch_a2_profile_down_current.json`은
  `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0`에서 `DOWN,DOWN` redraw를 유도할 때
  A2 compact target `0x00A295AC`를 34회 읽는다. 관측 PC 상위는 `0x0838BD18` 15회,
  `0x0838BCE4` 5회이며, A2 group의 target-level runtime provenance로 matrix에 붙는다.
- **음성 current화**: action menu exact/range, after-a36, B8 comm label, Part2 title menu sweep,
  map territory, rule-setting map names, B8 battle range/subset, B8 shop external states,
  A2/B84 external profile states/freshrender 등은 current SHA에서 hit 0이다.
- **경계**: 0-hit는 해당 route/subset의 음성 결과다. 특히 B8 Part2 HUD/상점/무기/데미지예측과 B84 나머지
  파워명은 source-address/dead-copy 여부를 아직 전역 결론 낼 수 없다. A2 `0x00A295AC`도 read-watch provenance이지
  36개 전수 visual-layout proof가 아니다.

---
## [2026-06-28] E12 A2 CO profile nav read-watch 확장

- **상태/route**: `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0`는 CO 프로필 파워 정보창으로
  재진입 가능한 near-fresh state다. `DOWN,DOWN`은 기존 `0x00A295AC`(`승리`)를 읽고,
  `DOWN,DOWN,DOWN`은 `0x00A295C0`(`대승`), `DOWN,DOWN,RIGHT`는
  `0x00A295D8`(`강타`)을 추가로 읽는다.
- **관측**: 두 신규 probe 모두 current ROM SHA
  `f95a857354a84119452b69bdabb371c6f390e0ecd4faf13bc56d5208ec1bb292`에서
  A2 range watch hit 68/direct read 68을 기록했다. 각 probe의 신규 target은 34회 read이며,
  상위 PC는 기존 A2 hit와 동일하게 `0x0838BD18`, `0x0838BCE4`,
  `0x0831425A`, `0x08314336`, `0x0831BD1C`, `0x08F30284/286`, `0x08F30404`
  계열이다.
- **증거 파일**:
  `data/compact_display_read_watch_a2_profile_down3_current.json`,
  `data/compact_display_read_watch_a2_profile_right_current.json`.
  matrix 재생성 결과 A2 target runtime/source proof는 1/36 -> 3/36,
  전체 E12 target runtime/source proof count는 17이 됐다.
- **음성 후보**: 같은 state의 no-step, `RIGHT` 단독, 주변 `state_023/026/027/028/039/040`
  + `DOWN,DOWN,RIGHT,DOWN`은 A2/B84 target read 0이었다. 따라서 state_036 계열에서
  안정적으로 얻은 양성 범위는 현재 `0xA295AC/0xA295C0/0xA295D8` 3개다.
- **해석 경계**: 이 증거는 source-address/dead-copy 의심을 해당 3주소에 대해서만 반증한다.
  A2 잔여 33개와 B8 Part2 HUD/상점/무기/데미지예측 계열은 계속 별도 fresh route,
  target mutation diff, direct read-watch, 또는 WRAM/VRAM/DMA chain이 필요하다.

---
## [2026-06-28] E12 B84 AW1 CO 파워명 11/11 selector/read-watch 확정

- **selector 경로**: AW1 CO 파워 컷인 루틴 `0x08B3C254`는 object의 player index 1을 사용해
  `0x08D845A4 -> 0x0201AD38` player record base에서 `base + 0x68 + 0x1D = 0x0201ADBD`
  CO id byte를 읽는다. 이 값은 `0x08B1C194`에서 B84 pointer-table index가 되고,
  `0x08DF2B54 + index*4`가 target body pointer를 반환한다. 최종 문자열 렌더는 기존과 같은
  `0x08B3C184` shared compact renderer다.
- **실험 방식**: current ROM SHA
  `f95a857354a84119452b69bdabb371c6f390e0ecd4faf13bc56d5208ec1bb292`에서
  `temp/b84_aw1_power_select_probe_20260628/rec1_meter_100k/menu_open.ss0`를 로드하고,
  ROM/pointer table은 변경하지 않았다. route 직전 live RAM `0x0201ADBD`만 `0x00..0x0A`로 바꾼 뒤
  같은 `DOWN,DOWN,A` 파워 발동을 실행했다.
- **관측**: slot 0..10이 각각
  `0x00B84F14`(`기적`), `0x00B84F04`(`하이퍼수리`), `0x00B84EF0`(`강타`),
  `0x00B84EE0`(`설백`), `0x00B84ECC`(`승리`), `0x00B84EB8`(`저격`),
  `0x00B84EA4`(`일도`), `0x00B84E94`(`탐색`), `0x00B84E7C`(`번개강습`),
  `0x00B84E64`(`큰파도`), `0x00B84E50`(`메테오`)를 직접 읽었다. `0x0B`는 slot 10과 같은
  `메테오`로 clamp/alias된다.
- **invalid-id boundary**: `0x08B1C194`는 `0x0B -> 0x0A` alias만 명시한다.
  후속 짧은 probe에서 `0x0201ADBD=0x0C/0x10/0xFF`는 B84 pointer/body hit 0이었고,
  positive evidence로 세지 않는다. 결과는 `bounds_probe_summary.json`과 `docs/fail.md`에 남겼다.
- **증거 파일**:
  `data/compact_display_read_watch_b84_power_titles_coid_current.json`,
  `docs/screenshots/b84_aw1_power_title_all_coid_2026-06-28/contact.png`.
  contact sheet는 11개 컷인 제목이 모두 한글로 표시됨을 보인다.
- **matrix 반영**: `tools/build_compact_display_visual_matrix.py` 재실행 후 read-watch probes는
  current 22/stale 0, cases 54, hits/direct reads 291이고, B84 target runtime/source proof는
  11/11이다. 전체 E12 target runtime/source proof count는 A2 3 + B84 11 + B8 13 = 27이다.
- **해석 경계**: 이것은 natural route 전수 증명이 아니라 live RAM CO-id field를 바꾼 near-fresh proof다.
  다만 ROM bytes, B84 pointer table, `0x08B3C184` renderer, source-only LZ77 glyph 수정은 모두 current ROM 그대로라,
  B84 target body가 dead copy라는 의심은 11개 전부에 대해 반증한다. E12 전체는 A2/B8 잔여 때문에 미완료다.

---
## [2026-06-28] E12 Part2 생산/유닛 정보 화면은 B8 duplicate가 아니라 A2 source를 읽음

- **화면/route**: `temp/scene_entrypoints/part2_menu_sweep/state_031.ss0`에서 `RIGHT,A`로 생산/유닛 정보
  화면을 열면 `보병/정찰차/경전차/중전차/신형전차` 등이 보인다.
- **B8 음성**: 같은 route에서 B8 early unit/weapon 후보
  `0x00B81840/1854/1874/1970/1988/1A40/1A60/1A6C/1AC0/1ACC/1AD8/1B04/1B14`
  exact watch는 hit 0/direct 0이었다.
- **A2 양성**: 같은 route에서 A2 unit source 후보를 watch하면 493 hit가 발생한다. 주요 hit는
  `0x00A29390`(`보병`) 75회, `0x00A293A8`(`중전차`) 58회,
  `0x00A293B0`(`경전차`) 48회, `0x00A2939C`(`신형전차`) 19회다.
  상위 PC는 `0x0838BD18`, `0x0838BCE4`, `0x08F30404`, `0x0831BD1C`,
  `0x0838BCFA`, `0x08F30284/0x08F30286`, `0x0831425A`, `0x08314336` 계열이다.
  raw evidence는 `data/e12_a2_unit_info_source_redirect_current.json`.
- **해석**: 이 Part2 생산/유닛 정보 route의 visible unit labels는 B8 duplicate body가 아니라 A2 source에서
  공급된다. 따라서 이 route에 대한 B8 0-hit는 하니스 실패가 아니라 source mismatch로 해석할 수 있다.
  단, 이 사실은 B8 early unit/weapon 후보의 전역 dead-copy 증명이 아니며, 다른 화면에서 B8을 읽을 가능성은
  pointer-ref disasm, pointer/body mutation, 또는 WRAM/VRAM write-chain으로 별도 확인해야 한다.

---
## [2026-06-28] E12 A2 `state_036` CO 프로필은 도미노/맥스 pair source proof까지만 유효

- **입력 의미 재분류**: `temp/scene_entrypoints/part2_menu_sweep/state_036.ss0`에서 `RIGHT`는 전역 CO list를
  한 칸 넘기는 입력이 아니라 현재 캠페인 profile pair의 도미노/맥스 토글로 동작한다.
  `RIGHT` 0..17회 반복 contact는 두 화면만 번갈아 보였다.
- **확정 source**: 이 state에서 대표 4케이스만 뽑으면 A2 compact target
  `0x00A295AC`(`승리`), `0x00A295C0`(`대승`), `0x00A295D8`(`강타`),
  `0x00A295EC`(`직격`)을 직접 읽는다. 상위 PC 계열은 기존 A2 profile hits와 같은
  `0x0838BD18`, `0x0838BCE4`, `0x0831425A`, `0x08314336`, `0x0831BD1C`,
  `0x08F30284/286`, `0x08F30404`다.
- **증거/집계**: slim 영구 증거는 `data/compact_display_read_watch_a2_profile_domino_max_current.json`,
  전체 반복 contact는 `docs/screenshots/e12_a2_profile_domino_max_2026-06-28/contact.png`.
  matrix 재생성 결과 A2 target runtime/source proof는 4/36이다.
- **해석 경계**: 36개 all-CO coverage로 격상하지 않는다. 이 state는 A2 source-address/dead-copy 의심을
  도미노/맥스 4주소에 대해서만 반증한다. 나머지 A2 32개는 다른 route 또는 write-chain 증거가 필요하다.
