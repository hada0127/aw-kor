# PS Vita 한글패치 대안 방법 연구 (2026-04-10)

## 현재 문제점
- FTX 내부 폰트 아틀라스의 SJIS→셀 인덱스 매핑이 비선형적
- 가(0x88,0x40)=cell 224 확인했으나, b2>=0x80 구간은 cell >1023으로 점프
- 공식/테이블 기반 매핑을 알 수 없어 정확한 글리프 교체 불가
- DXT5 인코딩 + Morton 스위즐 자체는 해결됨

## 방법 1: Vita3K 에뮬레이터 텍스처 교체 (가장 유망)

### 원리
Vita3K는 게임 실행 중 GPU에서 사용하는 텍스처를 **해시 기반으로 덤프/교체**하는 기능 내장.
게임이 폰트 텍스처를 GPU에 로드할 때 해시값으로 식별 → 교체 PNG를 자동 로드.

### 작동 방식
1. **Export**: Settings → GPU → "Export Textures" 활성화 → 게임 실행
   - `textures/export/PCSE00240/` 폴더에 모든 텍스처 PNG/DDS로 덤프
   - 파일명 = 텍스처 해시값
2. **Import**: `textures/import/PCSE00240/` 폴더에 수정된 PNG 배치
   - Settings → GPU → "Import Textures" 활성화
   - 게임이 해당 텍스처 로드 시 자동 교체

### 장점
- **FTX/GXT 포맷 이해 불필요** - 에뮬레이터가 이미 디코딩한 상태의 텍스처를 다룸
- **스위즐/압축 처리 불필요** - PNG로 직접 작업
- **셀 인덱스 매핑 우회** - 원본 폰트 텍스처를 시각적으로 분석 → 글리프 위치 직접 확인
- DXT5 인코딩/Morton 스위즐/CRILAYLA 압축 전부 불필요

### 단점
- Vita3K 전용 (실기 비호환)
- 텍스처 해시가 업데이트마다 바뀔 가능성
- 성능 약간 저하 가능

### 적용 절차 (제안)
1. Vita3K에서 텍스처 Export 활성화 → 게임 실행 → 폰트 텍스처 덤프
2. 덤프된 폰트 텍스처에서 각 글리프 위치 시각적 분석
3. 한글 글리프로 교체한 PNG 생성
4. `textures/import/PCSE00240/` 에 배치
5. Import Textures 활성화 → 게임 실행

## 방법 2: rufaswan/psxtools FTX 추출기 활용

### 도구
- GitHub: `rufaswan/Web2D_Games/tools/psxtools/`
- **`psvita_mura_FTEX.php`** - Muramasa Rebirth Vita 전용 FTX 추출기
- **`psvita_mura_CPK.php`** - CPK 처리기

### 작동 방식
```bash
php psxtools/psvita_mura_FTEX.php font.ftx
# → GXT 파일 출력
php psxtools/img_clut2png.php output.gxt
# → PNG 변환
```

### 장점
- Vanillaware 게임 전문 역엔지니어가 만든 도구
- FTX 내부 구조를 이미 파악한 코드
- 추출 후 글리프 매핑 분석 가능

### 단점
- PHP 기반 도구 (PHP 설치 필요)
- 리패킹(GXT→FTX) 지원 여부 불명
- 역방향(수정 후 재패킹) 가능 여부 확인 필요

## 방법 3: 원본 폰트 분석으로 매핑 테이블 추출

### 원리
원본 font.ftx의 각 셀을 이미지로 추출 → OCR 또는 시각적 분석으로 원래 글자 식별 → SJIS 코드 ↔ 셀 인덱스 매핑 테이블 완성

### 절차
1. font.ftx에서 모든 셀(글리프) 이미지 추출 (DXT5 디코딩 + Morton 디스위즐)
2. 각 셀의 이미지를 OCR 또는 수동으로 일본어 문자와 매칭
3. JIS/SJIS 코드와 셀 인덱스의 매핑 테이블 생성
4. 해당 테이블 기반으로 한글 글리프 교체

### 장점
- 완전한 매핑 이해 가능
- CPK 직접 패치 가능 (실기 호환)

### 단점
- 수천 개 글리프 분석 필요 (시간 소요)
- OCR 정확도 한계 (저해상도 DXT5 글리프)

## 방법 4: 시스템 폰트 리다이렉트 (PGF 방식)

### 원리
PS Vita 시스템 폰트(PGF)를 한글 포함 폰트로 교체

### 도구
- FontInstaller Vita (homebrew)
- fontRedirect 플러그인

### 한계
- 게임이 **시스템 폰트를 사용하지 않음** (자체 FTX 폰트)
- Muramasa에는 적용 불가

## 방법 5: Wii 한글패치 참고 (muramasa.xdelta)

### 현황
- `muramasa.xdelta` (622.5MB) - Wii용 오보로 무라마사 한글패치
- 제작: 알랑방구(총괄), 슬램백호, 마르시안, 시이오 (2022-12-30)
- xdelta 패치로 전체 ROM을 수정하는 방식

### 참고 가능한 점
- **번역 텍스트**: 같은 게임이므로 번역 내용 참고 가능 (본편 스토리 동일)
- **한글 글리프 세트**: 어떤 한글 문자가 사용되었는지 참고
- **Wii와 Vita는 다른 엔진**: Wii용 FCMP/FTX vs Vita용 CPK/FTX - 포맷은 다르지만 Vanillaware 엔진 구조는 유사

### 한계
- 622MB xdelta는 전체 ROM 바이너리 패치 → 개별 파일 추출 불가
- Wii와 Vita의 텍스처/폰트 포맷 상이

## 방법 6: Wii UHD 텍스처팩 참고 (RSFE7U.zip)

### 현황
- Dolphin 에뮬레이터용 HD 텍스처팩 (1465 파일)
- 디렉토리: Alphas, BigShots, Kisuke, Momohime, NPC, Objects, StageBig/Low/Med/Small, Swords, **UI** (98개)
- 파일명 형식: `tex1_WxH_HASH_HASH_FMT.png` (Dolphin 텍스처 덤프 규칙)

### 참고 가능한 점
- **Vita3K도 유사한 텍스처 교체 방식** 사용 → 같은 접근법 적용 가능
- UI 텍스처에 폰트 관련 텍스처가 포함되어 있을 가능성
- HD 텍스처 제작 워크플로우 참고

## 추천 접근 순서

### 1순위: Vita3K 텍스처 교체 (방법 1)
- 가장 빠르고 확실한 방법
- FTX 내부 구조 이해 불필요
- 이미 Odin Sphere 등 다른 Vanillaware 게임에서 성공 사례

### 2순위: psxtools로 FTX 분석 (방법 2 + 3)
- psvita_mura_FTEX.php로 정확한 글리프 추출
- 매핑 테이블 완성 후 직접 패치

### 3순위: xdelta 패치에서 번역 텍스트 추출 참고
- 번역 품질 향상용으로 활용
