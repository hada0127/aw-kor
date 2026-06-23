# Game Boy Wars Advance 1+2 한글 패치 — 적용 안내 (비개발자용)

이 폴더의 패치를 사용하면 일본판 **Game Boy Wars Advance 1+2 (GBA)** 롬을
한글판으로 바꿀 수 있습니다. 저작권 문제로 **게임 ROM 자체는 포함되어 있지 않습니다.**
ROM은 본인이 합법적으로 소유한 카트리지에서 직접 준비하세요.

준비물:
- **Python 3** (Windows/macOS/Linux 모두 무료. <https://www.python.org/downloads/> 에서 설치)
  - 추가 라이브러리 설치는 **필요 없습니다.** 표준 기능만 사용합니다.
- 원본 일본판 ROM 파일 1개: `Game Boy Wars Advance 1+2 (Japan).gba`

---

## 3단계 적용

### 1단계 — 원본 ROM 준비
본인 소유의 일본판 ROM(`.gba`)을 이 폴더(`apply_patch.py`가 있는 폴더)에 넣습니다.
파일 이름은 달라도 괜찮습니다. 스크립트가 SHA-256 지문으로 올바른 ROM인지 자동 확인합니다.

### 2단계 — 적용기 실행
이 폴더에서 터미널(명령 프롬프트)을 열고 아래 한 줄을 실행합니다.

```
python3 apply_patch.py
```

(Windows에서 `python3`가 없다면 `python apply_patch.py` 로 시도하세요.)

ROM을 자동으로 못 찾으면 경로를 직접 지정할 수 있습니다.

```
python3 apply_patch.py "Game Boy Wars Advance 1+2 (Japan).gba"
```

출력 파일 이름을 직접 정하려면 두 번째 인자로 지정합니다.

```
python3 apply_patch.py "원본.gba" "한글판.gba"
```

### 3단계 — 결과 확인
성공하면 같은 폴더에 다음 파일이 생깁니다.

```
Game Boy Wars Advance 1+2 (Korean).gba
```

이 파일을 **mGBA** 같은 에뮬레이터나 실기 플래시카트(EZ-Flash 등)에서 실행하면
한글이 표시됩니다.

---

## 해시(지문) 검증에 대하여

적용기는 다음을 **자동으로** 검사합니다. 하나라도 어긋나면 멈추고 오류를 표시합니다.

1. **패치 파일 자체** — `manifest.json`의 SHA-256과 일치하는지 (배포본 손상 방지)
2. **원본 ROM** — `manifest.json`의 `source_rom.sha256`과 일치하는지 (잘못된 ROM 방지)
3. **패치 결과 ROM** — `manifest.json`의 `patched_rom.sha256`과 일치하는지 (적용 성공 보증)

직접 확인하고 싶다면 `manifest.json`에서 아래 값을 비교하세요.

- 원본 일본판 ROM SHA-256:
  `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- 한글판 결과 ROM SHA-256:
  `63d237712359debd9951ac1e2d7616c1e97c57218310c5ed0fecd8b767cd7a0f`

수동 확인 예 (macOS/Linux):

```
shasum -a 256 "Game Boy Wars Advance 1+2 (Japan).gba"
```

Windows (PowerShell):

```
Get-FileHash "Game Boy Wars Advance 1+2 (Japan).gba" -Algorithm SHA256
```

> 참고: BPS 패치는 내부적으로 원본/결과의 CRC32도 함께 검증하므로,
> 다른 리전·다른 덤프의 ROM에는 적용되지 않습니다.

---

## 다른 패치 도구를 써도 되나요?

네. 이 폴더의 `.bps` 파일은 표준 BPS 패치이므로
**Floating IPS(Flips)**, **beat**, **MultiPatch** 등 어떤 BPS 적용기로도 적용할 수 있습니다.
`.ips` 파일도 호환용으로 함께 들어 있지만, 원본/결과 CRC를 기록하는 **BPS를 권장**합니다.
`apply_patch.py`는 추가 프로그램 설치 없이 해시 검증까지 한 번에 해 주는 가장 안전한 방법입니다.

---

## 알려진 한계

- 이 패치는 **일본판** `Game Boy Wars Advance 1+2 (Japan).gba` 전용입니다.
  다른 리전/덤프에는 적용되지 않습니다(해시·CRC 불일치로 거부됨).
- 일부 UI 라벨은 한글이 슬롯보다 길어 **일본어가 남아 있을 수 있습니다**(오버플로 항목).
  진행에는 지장이 없습니다.
- 세이브 파일(`.sav`)은 일본판과 호환됩니다. 단, 에뮬레이터에 따라
  세이브 타입(플래시/SRAM) 자동 인식이 다를 수 있습니다.
- 본 패치는 팬 번역 결과물이며, 게임 ROM의 저작권은 원저작권자에게 있습니다.
  **ROM은 절대 재배포하지 마세요.** 이 폴더에는 패치/스크립트/문서만 들어 있습니다.

문제가 생기면 오류 메시지를 그대로 캡처해 문의해 주세요. 메시지에 어느 단계에서
어떤 해시가 어긋났는지 표시됩니다.
