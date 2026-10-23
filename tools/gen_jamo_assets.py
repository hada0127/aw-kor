#!/usr/bin/env python3
"""2편 이름 입력 조합용 자모 40자 자산(코드표·글리프)과 조회표 생성기.

산출물(PLAN-v5 §1.7, T1):
  - data/jamo_to_code_40.json : 자모→SJIS 예약 코드 40개. 순서 = hangul_compose.PREVIEW_JAMO
                                (19초성 + 21모음). 코드 = extend_pool(원본) − 2350 코드의 정렬 첫 40개.
  - data/jamo_glyphs_40.bin   : 40 × (top 32B + bot 32B) = 2,560B, render_galmuri_8x16.render_char.
                                ROM 타일 1275+2i(top)·1276+2i(bot)에 순서대로 놓인다.

빌더용 API:
  load_jamo_codes() -> dict[str, int]            40개, 검증 후 반환
  jamo_tiles() -> bytes                          2,560B, 검증 후 반환
  dense_table(syl_to_code) -> bytes              (L*21+V)*28+T → u16 LE 코드, 없음 0 (22,344B)
  jamo_table_entries(sylmap, codes) -> bytes     A3 표 tail 40 엔트리(240B)

재현:  python3 tools/gen_jamo_assets.py
검증:  python3 tools/gen_jamo_assets.py --check   (재생성 바이트가 저장본과 같은지만 확인, 쓰지 않음)
"""
import argparse
import hashlib
import json
import os
import struct
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from hangul_compose import PREVIEW_JAMO  # noqa: E402

ROM = os.path.join(ROOT, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
ROM_SHA256 = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
SYLCODE = os.path.join(ROOT, 'data', 'syllable_to_code_2350.json')
OUT_CODES = os.path.join(ROOT, 'data', 'jamo_to_code_40.json')
OUT_GLYPHS = os.path.join(ROOT, 'data', 'jamo_glyphs_40.bin')

JAMO_COUNT = 40
TILE_BYTES = 32
GLYPH_BYTES = JAMO_COUNT * 2 * TILE_BYTES          # 2,560
DENSE_ENTRIES = 19 * 21 * 28                       # 11,172
DENSE_BYTES = DENSE_ENTRIES * 2                    # 22,344
ENTRY_BYTES = 6
FIRST_TILE = 1275  # 1273 = 기존 빈 타일, 1274 = 사설 자 top (build_korean_full)
KOREAN_MARKER = 0x8000


def _read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_syllable_codes(path=SYLCODE):
    return {s: int(c, 16) for s, c in _read_json(path).items()}


def select_jamo_codes(rom, syl_to_code):
    """extend_pool(원본 ROM) 중 2350 매핑에 안 쓰인 코드의 정렬 첫 40개를 PREVIEW_JAMO 순으로."""
    from build_korean2350 import extend_pool
    used = set(syl_to_code.values())
    unused = sorted(set(extend_pool(rom)) - used)
    if len(unused) < JAMO_COUNT:
        raise ValueError(f'free pool {len(unused)} < {JAMO_COUNT}')
    return dict(zip(PREVIEW_JAMO, unused[:JAMO_COUNT]))


def _validate_codes(codes, syl_to_code):
    if list(codes) != list(PREVIEW_JAMO):
        raise ValueError('jamo keys/order != PREVIEW_JAMO')
    values = list(codes.values())
    if len(set(values)) != JAMO_COUNT:
        raise ValueError('duplicate jamo codes')
    clash = set(values) & set(syl_to_code.values())
    if clash:
        raise ValueError(f'jamo codes overlap 2350 codes: {sorted(clash)}')
    for j, c in codes.items():
        if not (0x88 <= c >> 8 <= 0xEA and (c & 0xFF) >= 0x40):
            raise ValueError(f'{j} code 0x{c:04X} out of lead/trail range')


def load_jamo_codes(path=OUT_CODES, sylcode_path=SYLCODE):
    codes = {j: int(c, 16) for j, c in _read_json(path).items()}
    _validate_codes(codes, load_syllable_codes(sylcode_path))
    return codes


def render_jamo_tiles():
    from render_galmuri_8x16 import render_char
    cwd = os.getcwd()
    os.chdir(ROOT)  # render_galmuri_8x16 는 폰트를 ROOT 상대 경로로 연다
    try:
        out = bytearray()
        for j in PREVIEW_JAMO:
            top, bot = render_char(j)
            if not any(top) and not any(bot):
                raise ValueError(f'{j} rendered with no ink')
            out += top + bot
    finally:
        os.chdir(cwd)
    return bytes(out)


def jamo_tiles(path=OUT_GLYPHS):
    data = _read_bytes(path)
    if len(data) != GLYPH_BYTES:
        raise ValueError(f'jamo glyph bin {len(data)}B != {GLYPH_BYTES}')
    for i, j in enumerate(PREVIEW_JAMO):
        if not any(data[i * 64:(i + 1) * 64]):
            raise ValueError(f'{j} glyph has no ink')
    return data


def dense_table(syl_to_code):
    table = bytearray(DENSE_BYTES)
    for s, code in syl_to_code.items():
        n = ord(s) - 0xAC00
        if not 0 <= n < DENSE_ENTRIES:
            raise ValueError(f'{s!r} is not a precomposed syllable')
        if not code:
            raise ValueError(f'{s} has zero code')
        struct.pack_into('<H', table, n * 2, code)
    return bytes(table)


def jamo_table_entries(sylmap, codes):
    max_tile = max(max(g['top'], g['bot']) for g in sylmap.values())
    # 빌더는 자 top을 사설 1274로 바꾼 sylmap을 넘긴다(1273 빈 타일도 기존 영역) — 자모 영역만 막는다
    if max_tile >= FIRST_TILE:
        raise ValueError(f'syllable tile {max_tile} reaches jamo tiles (>= {FIRST_TILE})')
    out = bytearray()
    for i, j in enumerate(PREVIEW_JAMO):
        code = codes[j]
        top = (FIRST_TILE + 2 * i) | KOREAN_MARKER
        bot = (FIRST_TILE + 2 * i + 1) | KOREAN_MARKER
        out += bytes([code >> 8, code & 0xFF]) + struct.pack('<HH', top, bot)
    return bytes(out)


def _codes_json(codes):
    return json.dumps({j: f'0x{c:04X}' for j, c in codes.items()},
                      ensure_ascii=False, indent=0) + '\n'


def generate():
    rom = _read_bytes(ROM)
    if hashlib.sha256(rom).hexdigest() != ROM_SHA256:
        raise ValueError('original ROM SHA-256 mismatch')
    syl_to_code = load_syllable_codes()
    codes = select_jamo_codes(rom, syl_to_code)
    _validate_codes(codes, syl_to_code)
    return _codes_json(codes).encode('utf-8'), render_jamo_tiles()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='재생성 결과가 저장본과 같은지만 확인')
    args = ap.parse_args()
    codes_bytes, glyphs = generate()
    if args.check:
        bad = [p for p, b in ((OUT_CODES, codes_bytes), (OUT_GLYPHS, glyphs))
               if not os.path.exists(p) or _read_bytes(p) != b]
        for p in bad:
            print(f'MISMATCH {os.path.relpath(p, ROOT)}')
        if not bad:
            print('OK jamo assets byte-identical')
        raise SystemExit(1 if bad else 0)
    with open(OUT_CODES, 'wb') as f:
        f.write(codes_bytes)
    with open(OUT_GLYPHS, 'wb') as f:
        f.write(glyphs)
    print(f'wrote {os.path.relpath(OUT_CODES, ROOT)} ({len(codes_bytes)}B), '
          f'{os.path.relpath(OUT_GLYPHS, ROOT)} ({len(glyphs)}B)')


if __name__ == '__main__':
    main()
