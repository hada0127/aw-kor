# Game Wars 한글화 (Korean Localization)

## 프로젝트 개요

Game Boy Advance 전술 게임 **Game Wars 1+2** (원제: Game Boy Wars Advance 1+2, 일본판) 완전 한글화 프로젝트입니다.

**현재 상태**: 기술 기반 구축 완료 → **번역 다듬기 + 검수(QA) 단계 진행 중**

> 자세한 진행 상황과 현재 우선순위는 루트 [`todo.md`](todo.md), 작업 지침은 [`CLAUDE.md`](CLAUDE.md)를 참고하세요.

---

## 📖 비개발자용 도구 사용 가이드

> 이 큰 섹션(0~5번)은 **새로 합류하신 번역 전문가분**을 위한 안내입니다.
> 그 아래 "프로젝트 구조 / 로드맵"은 기존 개발 문서이니 참고만 하셔도 됩니다.

### 0. 이 가이드는 누구를 위한 것인가

이 가이드는 **터미널이나 Python에 익숙하지 않은 일본어 번역 전문가**가 이 프로젝트의 도구(대사 편집기, 스프라이트 편집기, 한글 ROM 빌드, 화면 비교 시트, 품질 검사)를 직접 켜고 쓸 수 있도록, **그대로 따라 하면 실행되는 단계**로 정리한 것입니다. 명령은 모두 복사해서 붙여넣을 수 있게 적었고, 각 단계마다 "이렇게 나오면 성공" 예시도 넣었습니다. 처음엔 낯설어도 한 번만 환경을 준비해 두면, 이후엔 표(2번)에서 명령 한 줄만 골라 붙여넣으면 됩니다.

> ⚠️ **공통 전제**: 아래 모든 명령은 **프로젝트 폴더(루트) 안에서** 실행한다고 가정합니다. 터미널을 새로 열 때마다 먼저 아래 한 줄을 붙여넣어 프로젝트 폴더로 이동하세요.
>
> ```bash
> cd /Users/tarucy/project/aw-kor
> ```
>
> (성공하면 아무 메시지도 안 나오고 그냥 다음 줄로 넘어갑니다. 그게 정상입니다.)

---

### 1. 처음 한 번만: 환경 준비 (macOS 기준)

이 1번 단계는 **딱 한 번만** 하면 됩니다. 다 끝내면 2번부터는 명령만 붙여넣으면 됩니다.

#### 1-1. 터미널(Terminal) 여는 법

1. 화면 오른쪽 위 돋보기(Spotlight) 아이콘을 누르거나 `⌘(커맨드) + 스페이스`를 누릅니다.
2. `터미널` 또는 `Terminal` 이라고 입력하고 Enter.
3. 까만(또는 흰) 글씨 창이 뜨면 그게 터미널입니다. 여기에 명령을 붙여넣고 Enter를 칩니다.

> 💡 붙여넣기는 `⌘ + V`, 실행은 항상 마지막에 **Enter**.

#### 1-2. Python 3 설치 확인

먼저 프로젝트 폴더로 이동한 뒤 Python 버전을 확인합니다.

```bash
cd /Users/tarucy/project/aw-kor
python3 --version
```

**이렇게 나오면 성공** (숫자는 조금 달라도 `3.9` 이상이면 OK):

```
Python 3.12.4
```

만약 `command not found: python3` 라고 나오면 Python이 없는 것입니다. 이럴 때는 1-4의 Homebrew를 먼저 설치한 뒤 `brew install python` 을 실행하거나, 개발자에게 도움을 요청하세요.

#### 1-3. 필요한 부가 기능(의존성) 설치

이 프로젝트의 도구는 대부분 Python 기본 기능만 쓰지만, **스프라이트(그림) 편집기와 화면 비교 시트**는 이미지 처리 라이브러리(Pillow, 코드에서는 `PIL`)가 필요합니다.

```bash
pip3 install -r requirements.txt
pip3 install Pillow
```

**이렇게 나오면 성공** (이미 깔려 있으면 `already satisfied` 라고 나옵니다. 그것도 정상):

```
Requirement already satisfied: Pillow in ...
Successfully installed Pillow-10.4.0
```

> 참고: `requirements.txt` 자체에는 Pillow가 적혀 있지 않아 위처럼 따로 한 줄 더 깔아 줍니다. 텍스트(대사) 편집과 QA 도구만 쓸 거면 Pillow 없이도 됩니다.

#### 1-4. mGBA(에뮬레이터) 설치 — 만든 ROM을 눈으로 확인할 때 필요

mGBA는 GBA 게임을 컴퓨터에서 돌려 보는 프로그램입니다. 먼저 설치 도구인 Homebrew가 있는지 확인합니다.

```bash
brew --version
```

`command not found: brew` 가 나오면 [https://brew.sh](https://brew.sh) 의 안내대로 Homebrew를 먼저 설치하세요(또는 개발자에게 요청). Homebrew가 있으면 mGBA를 설치합니다.

```bash
brew install mgba
```

설치 후 경로를 확인합니다.

```bash
ls /opt/homebrew/bin/mgba
```

**이렇게 나오면 성공:**

```
/opt/homebrew/bin/mgba
```

> 실제 실행 명령은 아래 **4번**에 있습니다.

#### 1-5. 한글 폰트 위치 (보통 신경 안 써도 됨)

화면 비교 시트는 라벨을 그릴 때 한글 폰트(나눔고딕 `NanumGothic`)를 씁니다. 보통 이미 깔려 있습니다. 확인만 하려면:

```bash
ls /Library/Fonts/NanumGothic.ttf
```

**이렇게 나오면 성공:**

```
/Library/Fonts/NanumGothic.ttf
```

없어도 도구는 시스템 기본 글꼴(AppleGothic 등)로 대체해 동작하니 크게 걱정하지 않아도 됩니다.

✅ 여기까지 했으면 환경 준비 끝! 이제 2번 표에서 하고 싶은 일을 골라 명령만 붙여넣으면 됩니다.

---

### 2. 자주 쓰는 작업 빠른 표

> 모든 명령은 **프로젝트 폴더 안에서** 실행한다고 가정합니다 (터미널을 새로 열었으면 `cd /Users/tarucy/project/aw-kor` 먼저).

| 하고 싶은 일 | 입력할 명령 | 결과가 나오는 위치 |
|---|---|---|
| **대사 번역 보고 고치기** (JA→KO, 용어 사전 포함) | `python3 tools/dialogue_editor/server.py` | 웹브라우저에서 `http://localhost:8780` 열기 |
| **그림(스프라이트) 픽셀 편집** | `python3 tools/sprite_editor/server.py` | 웹브라우저에서 `http://localhost:8781` 열기 |
| **한글 ROM 만들기(빌드)** ※시간이 좀 걸림 | `python3 tools/build_korean_full.py` | `output/game_wars_korean_full.gba` 파일 |
| **만든 ROM을 게임으로 켜 보기** | `DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/mgba -3 output/game_wars_korean_full.gba` | mGBA 창에서 게임 실행 |
| **화면 비교 시트 보기** (원본 vs 한글) | `python3 tools/build_comparison_sheet.py --compare` | `temp/comparison_sheets/sheet_compare.png` 이미지 |
| **빌드 무결성 검사** (가장 기본 게이트) | `python3 tools/qa_integrity_map.py` | 터미널에 PASS/FAIL |
| **용어 통일 검사** | `python3 tools/qa_terms_from_rom.py` | 터미널에 결과 + 종료코드 |
| **띄어쓰기/줄바꿈 검사** | `python3 tools/qa_spacing_from_rom.py` | 터미널에 결과 + 종료코드 |
| **글자 칸(슬롯) 넘침 검사** | `python3 tools/qa_text_fit.py` | 터미널에 넘침 목록 |
| **사전대로 번역 통일 적용** (미리보기) | `python3 tools/apply_proper_nouns_dict.py` | 터미널 미리보기 (`--apply` 붙이면 실제 반영) |

> 표의 자세한 사용법(끝내는 법, 자주 묻는 문제 포함)은 아래 **3번**에 있습니다.

---

### 3. 도구별 상세 사용법

#### 3-1. 대사 편집기 (대사 번역 + 용어 사전) — 가장 자주 쓰는 도구

**무엇을 하나요?** 게임 안 대사의 일본어 원문(JA)과 한국어 번역(KO)을 나란히 보고, 번역을 고쳐 저장하는 웹 화면입니다. 인물·국가·지명 같은 **통일 용어 사전**도 같이 보고 추가/수정할 수 있고, "이 대사가 사전대로 번역됐는지" 검사도 해 줍니다. 별도 설치 없이 컴퓨터 안에서만 도는 작은 웹페이지라 안전합니다.

**실행:**

```bash
python3 tools/dialogue_editor/server.py
```

다른 포트로 열고 싶으면 (보통은 안 그래도 됩니다):

```bash
python3 tools/dialogue_editor/server.py --port 9100
```

실행하면 터미널에 이렇게 뜹니다:

```
대사 편집기: http://127.0.0.1:8780  (Ctrl+C 종료)
  dialogue: .../data/dialogue_map.json  dict: .../data/proper_nouns.json
```

**사용 흐름:**

1. 명령을 실행하면 터미널은 그 상태로 멈춰 있습니다(서버가 켜져 있는 것이니 정상입니다. 창을 닫지 마세요).
2. 웹브라우저(사파리/크롬)를 열고 주소창에 **`http://localhost:8780`** 를 입력해 들어갑니다.
3. 대사 목록에서 원문/번역을 보고, 한국어를 고친 뒤 저장합니다.
4. 저장하면 번역이 `data/dialogue_map.json`과 `data/dialogue_overrides.json`에 기록됩니다(나중에 빌드에 반영됨).

**끝내는 법:** 서버를 켜 둔 **터미널 창을 클릭한 뒤 `Ctrl + C`** (컨트롤키와 C를 같이)를 누릅니다. `대사 편집기` 줄이 사라지고 명령 입력칸이 돌아오면 종료된 것입니다.

**자주 묻는 문제**
- *브라우저에 아무것도 안 떠요 / 연결할 수 없다고 나와요* → 서버를 켠 터미널이 그대로 켜져 있는지 확인하세요. 실수로 `Ctrl+C`로 껐다면 다시 위 명령을 실행하세요.
- *`Address already in use`(주소가 이미 사용 중) 라고 나와요* → 이미 8780 포트로 편집기가 켜져 있다는 뜻입니다. 그냥 브라우저로 `http://localhost:8780` 에 들어가 쓰거나, 다른 포트(`--port 9100`)로 켜세요.
- *목록이 비어 있어요* → `data/dialogue_map.json` 파일이 있어야 합니다. 개발자에게 "대사맵 생성"을 요청하거나, 데이터 재생성 명령(`python3 tools/build_dialogue_map.py`)을 한 번 돌리세요(3-6 참고).

#### 3-2. 스프라이트(그림) 픽셀 편집기

**무엇을 하나요?** 게임 안 작은 그림(로고·아이콘 등)을 **점(픽셀) 단위로 색칠해 고치는** 웹 화면입니다. 그림을 확대해 보여 주고, 정해진 색(팔레트) 중에서 골라 칠합니다. (이 도구는 1-3에서 깐 이미지 라이브러리 `Pillow`가 필요합니다.)

**실행:**

```bash
python3 tools/sprite_editor/server.py
```

실행하면 터미널에 이렇게 뜹니다:

```
스프라이트 픽셀 에디터: http://127.0.0.1:8781  (Ctrl+C 종료)
  index: .../data/sprites_index.json  edits: .../data/sprite_edits
```

**사용 흐름:**

1. 명령 실행 후 터미널은 켜진 채로 둡니다.
2. 브라우저에서 **`http://localhost:8781`** 로 들어갑니다.
3. 편집할 그림을 고르고, 팔레트에서 색을 골라 칸을 클릭해 칠합니다.
4. 저장하면 편집 결과가 `data/sprite_edits/`(그림)와 `data/sprites_overrides.json`(기록)에 저장됩니다.

> 참고: 저장은 "편집 기록"까지입니다. **실제 ROM에 그림을 다시 써 넣는 작업은 개발자가 별도 도구로** 진행합니다(저장 시 안내 문구가 나옵니다).

**끝내는 법:** 켜 둔 터미널에서 `Ctrl + C`.

**자주 묻는 문제**
- *`No module named 'PIL'` 오류* → 1-3의 `pip3 install Pillow` 를 실행하세요.
- *그림 목록이 비어 있어요* → 그림 인덱스(`data/sprites_index.json`)가 있어야 합니다. 없으면 데이터 재생성(`python3 tools/export_sprites.py`)을 한 번 돌리세요(3-6 참고). 시간이 좀 걸립니다.
- *포트 사용 중* → 3-1과 동일하게 이미 8781로 켜져 있는 것입니다.

#### 3-3. 한글 ROM 만들기 (메인 빌드)

**무엇을 하나요?** 지금까지의 번역과 한글 폰트를 원본 게임에 합쳐 **실제로 플레이할 수 있는 한글 ROM 파일**을 만들어 냅니다. 결과물은 `output/game_wars_korean_full.gba` 입니다.

> ⏳ **주의**: 이 빌드는 **시간이 좀 걸리고 무겁습니다.** 다른 사람이 빌드 중이거나 작업 중일 때 동시에 돌리면 충돌할 수 있으니, 혼자 작업할 때만 실행하세요. (번역만 다듬는 단계라면 빌드는 보통 개발자가 합니다.)

**실행:**

```bash
python3 tools/build_korean_full.py
```

(결과 파일 이름을 바꾸고 싶을 때만) `--out` 으로 지정할 수 있습니다:

```bash
python3 tools/build_korean_full.py --out output/내가만든_테스트.gba
```

**사용 흐름:**

1. 명령을 실행하면 진행 메시지가 쭉 올라옵니다. 끝까지 기다립니다.
2. 끝나면 `output/game_wars_korean_full.gba` 파일이 생기거나 갱신됩니다.
3. 이 파일을 **4번**의 mGBA 명령으로 열어 직접 확인하면 됩니다.

**끝내는 법:** 빌드는 끝나면 알아서 멈춥니다(웹 서버가 아니라 일회성 작업입니다). 중간에 멈추고 싶으면 `Ctrl + C`.

**자주 묻는 문제**
- *원본 ROM이 없다는 오류* → 빌드는 원본 게임 ROM(`original/` 폴더 안)이 있어야 합니다. 저작권 자산이라 저장소에 포함되지 않으니, 원본이 제자리에 있는지 개발자에게 확인하세요.
- *폰트 관련 오류* → 빌드가 특정 폰트를 요구할 수 있습니다. 오류 메시지에 적힌 폰트 경로를 개발자에게 전달하세요.

#### 3-4. 화면 비교 시트 (원본 vs 한글 한눈에 보기)

**무엇을 하나요?** 게임 여러 화면을 캡처해 **원본(일본어)과 한글판을 나란히 붙인 한 장의 비교 이미지**를 만들어 줍니다. 번역이 화면에서 어떻게 보이는지 검수할 때 좋습니다.

**실행:**

```bash
python3 tools/build_comparison_sheet.py --compare
```

패치본(한글)만 보고 싶으면:

```bash
python3 tools/build_comparison_sheet.py
```

**결과 위치:** `temp/comparison_sheets/sheet_compare.png` (`--compare` 없이 돌리면 `sheet.png`). 파인더(Finder)에서 그 파일을 더블클릭하면 미리보기로 열립니다.

**자주 묻는 문제**
- *`/tmp/mgbah` 가 없다는 오류* → 이 도구는 개발자가 미리 만들어 둔 헤드리스 실행기(`/tmp/mgbah`)가 필요합니다. 없으면 개발자에게 "mgba 하니스 빌드"를 요청하세요.
- *이미지가 비거나 깨져 보여요* → 검수용 참고 이미지이니, 이상하면 캡처해서 개발자에게 보여 주세요.

#### 3-5. 품질 검사(QA) 도구 — 빌드 결과가 멀쩡한지 점검

아래 도구들은 **방금 만든 ROM이 규칙에 맞는지 자동으로 점검**합니다. 끝에 PASS/FAIL 또는 결과 목록을 터미널에 보여 줍니다(보통 빌드 후에 돌립니다).

| 도구 | 무엇을 검사하나 | 명령 |
|---|---|---|
| 무결성맵 게이트 | 빌드가 ROM을 정확히 기술하는지 + 문장부호 소실 (가장 기본 검사) | `python3 tools/qa_integrity_map.py` |
| 용어 통일 | 출하 ROM 속 한글이 사전 정본 표기와 어긋나는지 | `python3 tools/qa_terms_from_rom.py` |
| 띄어쓰기/줄바꿈 | 단어 붙음·잘못된 축약·이중 공백 등 | `python3 tools/qa_spacing_from_rom.py` |
| 글자칸 넘침 | 한글이 정해진 칸(슬롯)보다 길어 넘치는지 | `python3 tools/qa_text_fit.py` |

**읽는 법:** 끝줄에 `PASS` 가 나오면 통과, `FAIL` 이나 문제 목록이 나오면 손볼 곳이 있다는 뜻입니다. 무슨 뜻인지 모르겠으면 그 화면을 캡처해 개발자에게 물어보세요. (`qa_terms_from_rom.py` 는 `--show 20` 을 붙이면 예시를 더 보여 줍니다.)

> 💡 QA 도구 대부분은 빌드가 남긴 `temp/integrity_map.json` 을 읽습니다. 따라서 **먼저 3-3 빌드를 한 번 돌린 뒤** QA를 실행해야 최신 결과를 점검합니다.

#### 3-6. (참고) 편집기용 데이터 다시 만들기

대사 편집기·스프라이트 편집기가 쓰는 데이터 파일은 자동 생성물입니다. 목록이 비어 있을 때만 한 번씩 돌리면 됩니다.

```bash
python3 tools/build_dialogue_map.py     # 대사 편집기용 data/dialogue_map.json 생성
python3 tools/export_sprites.py         # 스프라이트 편집기용 data/sprites_index.json + 그림 생성
```

**번역 용어 사전 관련 (선택):**

```bash
python3 tools/export_proper_nouns_dict.py    # data/proper_nouns.json (통일 사전) 생성/갱신
python3 tools/apply_proper_nouns_dict.py     # 사전 'edit' 값을 번역 CSV에 적용 (미리보기)
python3 tools/apply_proper_nouns_dict.py --apply   # 실제로 CSV에 반영
```

> `apply_proper_nouns_dict.py` 는 `--apply` 가 없으면 **미리보기(실제로 안 바꿈)** 이고, 붙여야 진짜로 `data/translation_for_import.csv` 에 반영됩니다.

---

### 4. ROM을 직접 눈으로 확인하기

빌드(3-3)로 만든 `output/game_wars_korean_full.gba` 를 mGBA로 켜서 게임을 직접 해 봅니다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/mgba -3 output/game_wars_korean_full.gba
```

- 앞부분(`DYLD_LIBRARY_PATH=...`)은 mGBA가 필요한 라이브러리를 찾게 해 주는 설정이니 **명령 전체를 통째로** 붙여넣으세요.
- `-3` 은 화면을 3배로 크게 보여 주는 옵션입니다.
- 창이 뜨고 게임이 시작되면 성공입니다. 끄려면 mGBA 창을 닫거나 터미널에서 `Ctrl + C`.

> 다른 ROM(예: 직접 이름 붙여 만든 파일)을 보려면 마지막 경로만 그 파일로 바꾸면 됩니다.

---

### 5. 막혔을 때

#### 흔한 오류와 해결

- **`command not found: python3` / `command not found: brew` / `command not found: mgba`**
  해당 프로그램이 설치되지 않았거나 경로가 안 잡힌 것입니다. 1번 "환경 준비"의 해당 단계를 다시 보세요. 그래도 안 되면 개발자에게 요청하세요.

- **`Address already in use` (주소가 이미 사용 중)**
  편집기 서버(8780/8781)가 **이미 켜져 있다**는 뜻입니다. 그냥 브라우저로 그 주소에 들어가 쓰거나, `--port 9100` 처럼 다른 번호로 켜세요. 정말 끄고 싶으면 그 서버를 켜 둔 터미널에서 `Ctrl + C`.

- **`No module named 'PIL'`**
  이미지 라이브러리가 없는 것입니다. `pip3 install Pillow` 를 실행하세요(1-3).

- **`Permission denied` (권한 없음)**
  파일을 쓸 권한이 없을 때 납니다. 명령을 **프로젝트 폴더 안에서** 실행했는지(`cd /Users/tarucy/project/aw-kor` 먼저) 확인하세요. 그래도 나면 캡처해서 개발자에게 보여 주세요.

- **원본 ROM / `/tmp/mgbah` 같은 파일이 없다는 오류**
  저작권 자산이거나 개발자가 미리 만들어 두는 도구라 저장소에 없을 수 있습니다. 개발자에게 "원본 ROM 위치 / mgba 하니스" 를 요청하세요.

- **편집기 목록이 비어 있음**
  데이터 파일이 아직 없는 것입니다. 3-6의 재생성 명령을 한 번 돌리세요.

#### 개발자에게 물어볼 때 같이 보내면 좋은 것

1. **무엇을 하려고 했는지** (예: "대사 편집기를 켜려고 했어요")
2. **붙여넣은 명령 한 줄** (그대로 복사)
3. **터미널에 빨갛게/길게 나온 오류 메시지 전체** (스크린샷 또는 텍스트 복사 — 마지막 몇 줄이 특히 중요)
4. (화면 문제라면) **mGBA나 브라우저 화면 캡처**

이 네 가지만 있으면 개발자가 훨씬 빨리 도와드릴 수 있습니다. 😊

---

## 프로젝트 구조

```
aw-kor/
├── .project-config.json          ← AI/프로젝트 설정 (참고)
├── CLAUDE.md                     ← 작업 지침 + 도구/환경 메모
├── todo.md                       ← 현재 진행 기준
├── README.md                     ← 이 파일
├── original/                     ← 원본 ROM (저작권 자산, 저장소 미포함)
├── docs/                         ← 문서 (번역 가이드, 리서치 등)
├── tools/                        ← ROM 해킹 / 번역 / 빌드 / QA / 편집기 도구
├── data/                         ← 번역·게임 데이터 (CSV, JSON 등)
├── output/                       ← 생성된 한글화 ROM (재생성 가능, 저장소 미포함)
├── temp/                         ← 임시 작업물 (비교 시트, 덤프 등)
└── dist/                         ← 배포본 (패치/릴리스 노트)
```

## 진행 상황 / 로드맵

자세한 진행 상황과 현재 우선순위는 루트 [`todo.md`](todo.md)만 참고합니다.

1. **PHASE 1**: 환경 구축 및 리포지토리 초기화
2. **PHASE 2**: ROM 구조 분석 및 문서화
3. **PHASE 3**: 텍스트 추출 및 포인터 매핑
4. **PHASE 4**: 번역 진행
5. **PHASE 5**: 자동화 시스템 구축 및 ROM 생성
6. **PHASE 6**: QA 및 테스트
7. **PHASE 7**: 배포 및 커뮤니티 공유

## 기여하기

이 프로젝트는 커뮤니티 기반 한글화 프로젝트입니다. 번역가, 검수자, 기술 지원자를 환영합니다.

## 참고 자료

- 진행 기준: [`todo.md`](todo.md)
- 작업 지침/도구 목록: [`CLAUDE.md`](CLAUDE.md)
- ROM 분석/대화 렌더 RE: `docs/research.md`
- 번역 톤/용어: `docs/TRANSLATION_GUIDE.md`, `docs/TRANSLATION_TONE_AND_STORY_GUIDE.md`

## 라이선스

정책 결정 예정 (사용 폰트 Galmuri 등은 OFL 라이선스)
