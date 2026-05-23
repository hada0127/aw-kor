# GBA 한글화 프로젝트 - 종합 연구 자료

## 1. 프로젝트 개요

Game Boy Advance(GBA) 게임 "Game Wars" 1+2 일본어판의 전체 한글화 프로젝트입니다.
이 문서는 WebSearch를 통해 수집한 모든 정보를 통합 정리한 자료입니다.

### 참조 문서
- `claude_research.md`: 커뮤니티 정보 및 리소스
- `codex_research.md`: 기술 도구 및 개발 방법론
- `gemini_research.md`: 종합 가이드 및 체크리스트

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
