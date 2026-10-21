#!/usr/bin/env python3
"""Create patch-only distribution artifacts and verify round-trips."""

import argparse
import json
import re
import sys
import zlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_bps import apply_bps, make_bps
from make_ips import apply_ips, make_ips
from localization_evidence import snapshot_inputs, verify_prepackage_report


BASE = Path(__file__).resolve().parents[1]
SOURCE_ROM = BASE / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
TARGET_ROM = BASE / 'output' / 'game_wars_korean_full.gba'
DIST = BASE / 'dist'
B42_ROM_SHA256 = '1c23b09160a9f7e491c8d2de8782e80200a13fb4238aec92999728b0282b1fbf'
B42_RELEASE_HIGHLIGHT = (
    'b40 uses the wide 예/아뇨 row for every Part 1 prompt; b41 reflows dialogue '
    'windows without losing text; b42 restores natural word spacing and applies '
    'consistent spacing to names and titles.'
)
B42_USER_HIGHLIGHT_KO = (
    '1편의 모든 예/아뇨 질문을 넓은 칸으로 표시하고, 대사 창 줄바꿈을 글자 손실 없이 다시 맞췄으며, '
    '대사 띄어쓰기를 자연스럽게 되살리고 이름·칭호 띄어쓰기를 통일했습니다.'
)
B43_ROM_SHA256 = '488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34'
B43_RELEASE_HIGHLIGHT = (
    'b40 uses the wide 예/아뇨 row for every Part 1 prompt; b41 reflows dialogue '
    'windows without losing text; b42 restores natural word spacing and applies '
    'consistent spacing to names and titles; b43 corrects the Link status-line '
    'spacing. Remaining dialogue items retain their recorded verification limits.'
)
B43_USER_HIGHLIGHT_KO = (
    '1편의 모든 예/아뇨 질문을 넓은 칸으로 표시하고, 대사 창 줄바꿈을 글자 손실 없이 다시 맞췄으며, '
    '대사 띄어쓰기를 자연스럽게 되살리고 이름·칭호 띄어쓰기를 통일했습니다. '
    '이번 판은 Link 상태 문구의 띄어쓰기를 고쳤습니다. 남은 대사 항목의 검증 범위는 릴리스 노트를 확인하세요.'
)
B44_ROM_SHA256 = '1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02'
B44_RELEASE_HIGHLIGHT = (
    B42_RELEASE_HIGHLIGHT.rstrip('.') + '; b43 corrects the Link status-line spacing; '
    'b44 moves the dialogue end ▼ cursor one pixel farther from the final '
    'character. Remaining dialogue items retain their recorded verification limits.'
)
B44_USER_HIGHLIGHT_KO = (
    B42_USER_HIGHLIGHT_KO + ' 앞선 판의 Link 상태 문구 띄어쓰기 수정도 포함합니다. '
    '이번 판은 대화 끝 ▼ 커서를 마지막 글자에서 오른쪽으로 1픽셀 띄웠습니다. '
    '남은 대사 항목의 검증 범위는 릴리스 노트를 확인하세요.'
)


def digest(data):
    import hashlib

    return {
        'size': len(data),
        'crc32': f'{zlib.crc32(data) & 0xffffffff:08x}',
        'sha1': hashlib.sha1(data).hexdigest(),
        'sha256': hashlib.sha256(data).hexdigest(),
    }


def write_readme(path, release_date, patch_stem, source_info, target_info, user_highlight):
    """User-facing Korean patch README. Developer/reviewer notes: docs/REVIEWER_GUIDE.md."""
    highlight_block = f'\n이번 판에서 바뀐 점: {user_highlight}\n' if user_highlight else ''
    path.write_text(
        f"""# 어드밴스 워즈 1+2 한글 패치 — 적용 안내

일본판 GBA 게임 **Game Boy Wars Advance 1+2** ROM을 한글판으로 바꾸는 패치입니다.
저작권 문제로 **게임 ROM은 들어 있지 않습니다.** 본인이 정당하게 가진 일본판 ROM을 준비하세요.

- **버전:** {release_date} 판
- **받을 파일:** `{patch_stem}.bps` (권장) 또는 `{patch_stem}.ips` (호환용)
{highlight_block}
이 폴더에서 날짜가 가장 최근인 패치를 쓰세요. 날짜가 이른 패치는 예전 판 기록입니다.
BPS는 원본과 결과를 스스로 검사하므로 IPS보다 BPS를 권장합니다.

---

## 1. 원본 ROM 확인

`Game Boy Wars Advance 1+2 (Japan).gba` (일본판) 전용입니다. 다른 지역판·다른 덤프에는 적용되지 않습니다.

| 항목 | 값 |
|---|---|
| 크기 | {source_info['size']} 바이트 |
| CRC32 | `{source_info['crc32'].upper()}` |
| SHA-256 | `{source_info['sha256']}` |

## 2. 패치 적용

### 가장 쉬운 방법 — `apply_patch.py` (해시 자동 검사)

준비물: **Python 3** (<https://www.python.org/downloads/>). 추가 설치는 필요 없습니다.

1. 이 폴더의 `apply_patch.py`, `manifest.json`, `{patch_stem}.bps` 를 한 폴더에 둡니다.
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
| 크기 | {target_info['size']} 바이트 |
| CRC32 | `{target_info['crc32'].upper()}` |
| SHA-256 | `{target_info['sha256']}` |

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
""",
        encoding='utf-8',
    )


def write_release_notes(path, release_date, patch_stem, source_info, target_info, release_highlight):
    highlight_details = (
        f'{release_highlight}\n'
        'The unlocked map-list and shared campaign-prompt captures used cheat-tainted '
        'saves: they verify those displays, not normal-play unlocking or progression.\n'
        'On iPhone RetroArch, the b42 ROM was read back and cold-booted through the '
        'Part 1 title, mode menu, and War Room list; the existing save was preserved '
        '(`docs/screenshots/b42_iphone_2026-10-19/receipt.json`). This device check '
        'does not cover all changed dialogue or every 예/아뇨 prompt. Real GBA hardware remains unverified.'
    ) if release_highlight else ''
    unverified_details = (
        'Alternate banner-sheet and `0x804FC8` consumer reachability, natural access '
        'to 11 Part 1 help windows, normal-play Sturm CO power, and hidden locked-map '
        'names remain unverified. For dialogue, 13 unknown consumers, 16 '
        'state-dependent messages, 18 horizontal-scroll help messages, and seven '
        'withheld relocations remain outside the fixed-window pass. Forced QA is '
        'not natural-route verification.'
    ) if release_highlight else ''
    path.write_text(
        f"""# Korean Patch Release Notes

## {release_date} Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `{source_info['sha256']}`
- Target ROM SHA-256: `{target_info['sha256']}`
- BPS patch: `{patch_stem}.bps`
- IPS patch: `{patch_stem}.ips`

{highlight_details}

The hash-bound prepackage QA checks listed in manifest.validation.qa_evidence
passed for this artifact. BPS/IPS round trips were checked during packaging.
These checks do not establish full-campaign, character-voice, or real-hardware
approval; those scopes remain tracked separately in `todo.md`.
{unverified_details}
""".rstrip() + '\n',
        encoding='utf-8',
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--stem', default=None)
    parser.add_argument('--qa-report', type=Path, default=BASE / 'temp/release_prepackage_qa.json')
    args = parser.parse_args()

    stem = args.stem or f'game_wars_korean_full_{args.date}'
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', stem):
        parser.error('Patch stem must be a plain filename')

    from run_release_qa import REQUIRED_PREPACKAGE_GATES
    try:
        qa_report = json.loads(args.qa_report.read_text())
        qa_evidence = verify_prepackage_report(qa_report, TARGET_ROM, SOURCE_ROM,
                                               REQUIRED_PREPACKAGE_GATES, snapshot_inputs())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f'Packaging refused before writing artifacts: {error}')

    source = SOURCE_ROM.read_bytes()
    target = TARGET_ROM.read_bytes()
    source_info = digest(source)
    target_info = digest(target)
    if target_info['sha256'] == B44_ROM_SHA256:
        release_highlight, user_highlight = B44_RELEASE_HIGHLIGHT, B44_USER_HIGHLIGHT_KO
    elif target_info['sha256'] == B43_ROM_SHA256:
        release_highlight, user_highlight = B43_RELEASE_HIGHLIGHT, B43_USER_HIGHLIGHT_KO
    elif target_info['sha256'] == B42_ROM_SHA256:
        release_highlight, user_highlight = B42_RELEASE_HIGHLIGHT, B42_USER_HIGHLIGHT_KO
    else:
        release_highlight, user_highlight = '', ''

    bps = make_bps(source, target)
    ips = make_ips(source, target)
    if apply_bps(source, bps) != target:
        raise SystemExit('BPS round-trip failed')
    if apply_ips(source, ips) != target:
        raise SystemExit('IPS round-trip failed')

    # Recheck after patch generation, before any distribution writes.
    verify_prepackage_report(qa_report, TARGET_ROM, SOURCE_ROM,
                             REQUIRED_PREPACKAGE_GATES, snapshot_inputs())
    if digest(SOURCE_ROM.read_bytes()) != source_info or digest(TARGET_ROM.read_bytes()) != target_info:
        raise SystemExit('ROM changed during patch generation')
    DIST.mkdir(exist_ok=True)

    bps_path = DIST / f'{stem}.bps'
    ips_path = DIST / f'{stem}.ips'
    bps_path.write_bytes(bps)
    ips_path.write_bytes(ips)
    bps_info = digest(bps)
    ips_info = digest(ips)

    manifest = {
        'name': 'Game Boy Wars Advance 1+2 — 한글화',
        'date': args.date,
        'status': 'hash-bound prepackage QA pass; full runtime/voice/hardware approval not implied',
        'release_highlights': [release_highlight] if release_highlight else [],
        'source_rom': {
            'name': SOURCE_ROM.name,
            **source_info,
        },
        'patched_rom': {
            'name': TARGET_ROM.name,
            **target_info,
        },
        'output_rom': {
            'canonical': TARGET_ROM.name,
            'sha256': target_info['sha256'],
            'legacy_variants': [],
        },
        'bps_patch': {
            'file': bps_path.name,
            **bps_info,
            'round_trip': 'OK',
        },
        'ips_patch': {
            'file': ips_path.name,
            **ips_info,
            'round_trip': 'OK',
            'note': 'BPS is preferred because it records source and target CRCs.',
        },
        'validation': {
            'qa_evidence': qa_evidence,
            'bps_round_trip': True,
            'ips_round_trip': True,
            'single_output_rom': True,
        },
    }
    for path in (DIST / 'manifest.json', DIST / 'manifest_preview.json'):
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_readme(DIST / 'README.md', args.date, stem, source_info, target_info, user_highlight)
    for path in (DIST / 'RELEASE_NOTES.md', DIST / 'RELEASE_NOTES_preview.md'):
        write_release_notes(path, args.date, stem, source_info, target_info, release_highlight)

    print(f'BPS: {bps_path} size={len(bps)} round-trip=OK')
    print(f'IPS: {ips_path} size={len(ips)} round-trip=OK')
    print(f'Manifest: {DIST / "manifest.json"}')


if __name__ == '__main__':
    main()
