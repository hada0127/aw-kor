# 어드밴스 워즈 1+2 한글 패치 — 적용 안내

일본판 GBA 게임 **Game Boy Wars Advance 1+2** ROM을 한글판으로 바꾸는 패치입니다.
저작권 문제로 **게임 ROM은 들어 있지 않습니다.** 본인이 정당하게 가진 일본판 ROM을 준비하세요.

- **버전:** 2026-10-19 판
- **받을 파일:** `game_wars_korean_full_2026-10-19.bps` (권장) 또는 `game_wars_korean_full_2026-10-19.ips` (호환용)

이번 판에서 바뀐 점: 1편의 모든 예/아뇨 질문을 넓은 칸으로 표시하고, 대사 창 줄바꿈을 글자 손실 없이 다시 맞췄으며, 대사 띄어쓰기를 자연스럽게 되살리고 이름·칭호 띄어쓰기를 통일했습니다. 이번 판은 Link 상태 문구의 띄어쓰기를 고쳤습니다. 남은 대사 항목의 검증 범위는 릴리스 노트를 확인하세요.

이 폴더에서 날짜가 가장 최근인 패치를 쓰세요. 날짜가 이른 패치는 예전 판 기록입니다.
BPS는 원본과 결과를 스스로 검사하므로 IPS보다 BPS를 권장합니다.

---

## 1. 원본 ROM 확인

`Game Boy Wars Advance 1+2 (Japan).gba` (일본판) 전용입니다. 다른 지역판·다른 덤프에는 적용되지 않습니다.

| 항목 | 값 |
|---|---|
| 크기 | 16777216 바이트 |
| CRC32 | `49EE1FDD` |
| SHA-256 | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` |

## 2. 패치 적용

### 가장 쉬운 방법 — `apply_patch.py` (해시 자동 검사)

준비물: **Python 3** (<https://www.python.org/downloads/>). 추가 설치는 필요 없습니다.

1. 이 폴더의 `apply_patch.py`, `manifest.json`, `game_wars_korean_full_2026-10-19.bps` 를 한 폴더에 둡니다.
2. 같은 폴더에 일본판 ROM(`.gba`)을 넣습니다. 파일 이름은 달라도 됩니다.
3. 그 폴더에서 터미널(명령 프롬프트)을 열고 실행합니다.

   ```
   python3 apply_patch.py
   ```

   Windows에서 `python3` 가 없으면 `python apply_patch.py` 로 실행하세요.
   ROM을 못 찾으면 경로를 직접 지정합니다: `python3 apply_patch.py "원본.gba" "한글판.gba"`

4. 성공하면 `Game Boy Wars Advance 1+2 (Korean).gba` 가 생깁니다.

`manifest.json` 을 함께 제공하고 패치 파일 이름을 바꾸지 않았다면 적용기는 ① 패치 파일 ② 원본 ROM ③ 결과 ROM의 지문(SHA-256)을 차례로 비교하고,
하나라도 다르면 멈추고 어느 단계에서 어긋났는지 알려 줍니다. 패치 이름을 바꾸면 패치 파일의 SHA-256 검사는 건너뛰지만 원본·결과 ROM 검사는 계속합니다.

### 다른 패치 도구

`.bps` 는 표준 BPS 패치라서 어떤 BPS 적용기로도 쓸 수 있습니다.

- **Rom Patcher JS** (웹, 설치 없음): <https://www.marcrobledo.com/RomPatcher.js/>
- **Floating IPS (Flips)**: <https://github.com/Alcaro/Flips>

## 3. 결과 확인

| 항목 | 값 |
|---|---|
| 크기 | 16777216 바이트 |
| CRC32 | `A53BFA40` |
| SHA-256 | `488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34` |

직접 확인하는 법:

```
# macOS / Linux
shasum -a 256 "Game Boy Wars Advance 1+2 (Korean).gba"

# Windows (PowerShell)
Get-FileHash "Game Boy Wars Advance 1+2 (Korean).gba" -Algorithm SHA256
```

## 4. 플레이

- **에뮬레이터:** mGBA, RetroArch mGBA 코어 등에서 패치한 `.gba` 를 엽니다.
- **실기:** 플래시 카트(EZ-Flash 등)에 넣을 수 있게 만들었지만, **실제 GBA 본체에서는 아직 확인하지 않았습니다.**
- **세이브:** 플래시 1Mbit(128KB) 형식입니다. 플래시 카트에서는 세이브 종류를 Flash 128KB(1M)로 맞추세요.
  패치는 세이브 형식을 바꾸지 않지만, 판을 바꾸기 전에 `.sav` 를 백업하세요.
  에뮬레이터 상태 저장(세이브 스테이트)은 다른 판 ROM으로 옮겨 쓰지 마세요.

## 5. 알려진 한계

- 실제 GBA 본체에서는 아직 확인하지 않았습니다.
- 두 편 모두 일반 플레이로 엔딩까지 전부 확인하지는 못했습니다.
- 드물게 나오는 일부 메시지는 테스트용 진입으로만 화면을 확인했습니다.
- 일부 화면에 어색한 줄바꿈·배치나 일본어가 남아 있을 수 있습니다.

## 6. 주의

- 비공식 팬 번역입니다. 닌텐도·인텔리전트 시스템즈 및 원작 권리자와 관계가 없습니다.
- **ROM이나 패치를 적용한 ROM을 재배포하지 마세요.** 이 폴더에는 패치·적용기·문서만 들어 있습니다.
- 만든 사람들·글꼴 라이선스는 저장소 루트의 `README.md` 를 보세요.
