#!/usr/bin/env python3
"""영어 ASCII UI 잔존 전수 검사 (Phase C-full).

기존엔 잔존 영어를 수동 grep으로만 확인했다(audit 지적: 체계적 도구 전무).
이 도구는 (1) 큐레이션된 UI 토큰이 패치 ROM에 남았는지, (2) 원본 대비 제거 여부,
(3) 일반 대문자 ASCII 런 후보를 보고한다. 표시되는 영어 잔존을 잡기 위한 것.

false positive(코드/내부 문자열)를 줄이려 원본에도 있고 패치에도 그대로 남은 토큰을
'미제거 후보'로 강조한다. exit는 항상 0(리포트 도구). --fail-on-curated로 게이트화 가능.
"""
import argparse
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')

# 게임에서 표시되던 영어 UI 토큰(todo/릴리스 로그 기반). 한글화로 제거됐어야 하는 것들.
CURATED = [
    b'PRESS START', b'NEW GAME', b'CONTINUE', b'GAME OVER', b'GAME START',
    b'SINGLE BATTLE', b'VS BATTLE', b'CAMPAIGN', b'HARD CAMPAIGN', b'TUTORIAL',
    b'MISSION', b'HISTORY', b'RECORD', b'OPTION', b'SOUND ROOM', b'NOW LOADING',
    b'WEATHER', b'ENEMY', b'RESULT', b'TOTAL', b'CONGRATULATIONS', b'INFO',
    b'GREEN EARTH', b'BLUE MOON', b'RED STAR', b'YELLOW COMET', b'BLACK HOLE',
    b'NEUTRAL', b'WARS WORLD', b"LET'S GO", b'RELEASE', b'SHOP', b'MAP DESIGN',
    b'MAP TRADE', b'PLAYER', b'RANK', b'SAVE', b'LOAD', b'DELETE', b'YES', b'NO',
    b'A:OK', b'B:BACK', b'BACK', b'EXIT', b'NEXT', b'TURN', b'DAY', b'WIN', b'LOSE',
    b'ATTACK', b'MOVE', b'WAIT', b'SUPPLY', b'CAPTURE', b'POWER', b'DEFENSE',
]
# 잡음(코드/헤더/식별자) — 잔존이어도 무시.
IGNORE = {b'NINTENDO', b'GBA', b'ROM', b'SRAM', b'FLASH', b'EEPROM', b'AGB', b'SAVE'}


def find_all(data, needle, limit=6):
    out = []
    pos = 0
    while True:
        i = data.find(needle, pos)
        if i < 0:
            break
        out.append(i)
        pos = i + 1
        if len(out) >= limit:
            break
    # 총 개수도 따로
    total = data.count(needle)
    return out, total


def is_word_bounded(data, idx, length):
    """앞뒤가 영문/숫자가 아니면 단어 경계로 간주(부분문자열 오탐 감소)."""
    before = data[idx - 1] if idx > 0 else 0
    after = data[idx + length] if idx + length < len(data) else 0
    def alnum(b):
        return (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A) or (0x30 <= b <= 0x39)
    return not alnum(before) and not alnum(after)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--original', default=ORIGINAL)
    ap.add_argument('--general', action='store_true', help='일반 대문자 ASCII 런 후보도 보고')
    ap.add_argument('--fail-on-curated', action='store_true', help='큐레이션 토큰 잔존 시 exit 1')
    args = ap.parse_args()

    rom = open(args.rom, 'rb').read()
    orig = open(args.original, 'rb').read() if os.path.exists(args.original) else None

    print(f'=== 영어 ASCII 잔존 검사: {os.path.basename(args.rom)} ===')
    residual = 0
    for tok in CURATED:
        if tok in IGNORE:
            continue
        offs, total = find_all(rom, tok)
        # 단어 경계 적중만 셈
        bounded = [o for o in offs if is_word_bounded(rom, o, len(tok))]
        if not bounded:
            continue
        o_total = orig.count(tok) if orig else -1
        residual += 1
        print(f"  [잔존] {tok.decode():<16} 패치 {total}회 (원본 {o_total}회)  예: " +
              ', '.join(f'0x{o:06X}' for o in bounded[:4]))
    if residual == 0:
        print('  큐레이션 UI 토큰: 잔존 0 ✓')

    if args.general:
        print('\n=== 일반 대문자 ASCII 런(≥5, 영문+공백) 후보(상위 30, 코드/잡음 포함 가능) ===')
        runs = {}
        for m in re.finditer(rb'[A-Z][A-Z ]{4,}[A-Z]', rom):
            s = m.group()
            if any(ig in s for ig in IGNORE):
                continue
            runs[s] = runs.get(s, 0) + 1
        for s, n in sorted(runs.items(), key=lambda kv: -kv[1])[:30]:
            o = orig.count(s) if orig else -1
            print(f"  {s.decode():<28} 패치 {n} / 원본 {o}")

    print(f'\n=== 큐레이션 잔존 토큰 {residual}종 ===')
    return 1 if (args.fail_on_curated and residual) else 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
