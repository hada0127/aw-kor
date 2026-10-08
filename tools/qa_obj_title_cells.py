#!/usr/bin/env python3
"""Final-ROM check: no glyph ink of the drawn titles is cut at an OBJ cell edge.

For every converted multi-OBJ title (2026-10-08 font conversion) the cells are
composed as displayed and checked with aw_fonts.check_cells: ink must not touch
the outer canvas edge, and may continue across an internal OBJ edge only where
the native Japanese art of that consumer already did (static proof that the
cells are drawn edge to edge). Per-glyph cells (power-title glyphs, banner
cells, mission-title glyph table) must keep their ink off the cell border.
usage: qa_obj_title_cells.py --rom ROM   (exit 1 on any issue)
"""
import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import aw_fonts  # noqa: E402
from lz77_scan import lz77_decompress  # noqa: E402

ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
# (label, LZ77 offset, cells, cell_w, cell_h, first tile, native contiguity allowed, check edges)
TITLES = [
    ('Part 2 air supremacy 하늘 제패!', 0xC1205C, 2, 8, 4, 0, False, True),
    ('Part 2 battle start 전투 개시!', 0xC10B34, 2, 8, 4, 0, False, True),
    ('Part 2 air mission 하늘의 적', 0xC11D9C, 2, 8, 4, 0, True, True),
    ('Part 1 M19', 0xC15A68, 2, 8, 4, 0, 'consumer', True),
    ('Part 1 M20', 0xC15C5C, 2, 8, 4, 0, 'consumer', True),
    ('Part 2 result 작전 성공', 0xBFB45C, 4, 4, 4, 0, False, True),
    ('Part 2 link logo 멀티팩', 0x54E538, 2, 8, 4, 64, True, False),
] + [(f'Part 2 mode logo {off:06X}', off, 2, 8, 4, 0, True, False)
     for off in (0x5B7930, 0x5B7CB0, 0x5B7F38, 0x5B82B4, 0x5B8564, 0x5B8850, 0x5B8B20)]
# (label, LZ77 offset, first tile, count, cell_w, cell_h)
CELLS = [
    ('Part 1 power title glyph', 0xBC9D0C, 0, 26, 2, 4),
    ('Part 1 campaign clear cell', 0xC43400, 32, 9, 4, 4),
    ('Part 1 versus settle cell', 0xBFC270, 0, 2, 4, 4),
]


def check(rom, original):
    import part1_mission_titles as mt
    issues = []
    at64, at128 = mt._contiguity(bytes(original))
    for label, off, cells, cw, ch, first, native_ok, edges in TITLES:
        dec = lz77_decompress(rom, off)
        if dec is None:
            issues.append(f'{label}: invalid LZ77 at {off:06X}')
            continue
        canvas = aw_fonts.obj_canvas(dec[0], cells, cw, ch, first)
        if native_ok == 'consumer':
            native = bool(at64)
        elif native_ok:
            native = aw_fonts.obj_canvas(lz77_decompress(original, off)[0], cells, cw, ch, first)
        else:
            native = None
        try:
            aw_fonts.check_cells(canvas, [cw * 8 * i for i in range(1, cells)], label, native=native, edges=edges)
        except AssertionError as exc:
            issues.append(str(exc))
    import build_title_hangul as T
    for name, off, text, _ in [*T.PART1_MAIN_HEADER_BLOCKS, *T.PART1_SUBMENU_LOGO_BLOCKS]:
        def logo(data):
            return [a + b for a, b in zip(aw_fonts.obj_canvas(data, 1, 8, 4, 0),
                                          aw_fonts.obj_canvas(data, 1, 2, 4, 32))]
        try:
            aw_fonts.check_cells(logo(lz77_decompress(rom, off)[0]), (64,), f'Part 1 header {text} {off:06X}',
                                 native=logo(lz77_decompress(original, off)[0]), edges=False)
        except AssertionError as exc:
            issues.append(str(exc))
    try:
        mt.check_cells(original)   # generated sheets; compare with ROM below
    except AssertionError as exc:
        issues.append(str(exc))
    for owner, *_ in mt.TITLES:
        main = lz77_decompress(rom, owner)[0]
        ext = lz77_decompress(rom, mt.EXTENSION[0])[0] if owner == mt.EXTENSION_OWNER else None
        bounds = (64, 128) if ext is not None else (64,)
        try:
            aw_fonts.check_cells(mt._canvas(main, ext), bounds, f'Part 1 mission title {owner:06X}',
                                 native=bool(at64 and at128))
        except AssertionError as exc:
            issues.append(str(exc))
    for label, off, first, count, cw, ch in CELLS:
        data = lz77_decompress(rom, off)[0]
        for i in range(count):
            grid = aw_fonts.obj_canvas(data, 1, cw, ch, first + i * cw * ch)
            if any(grid[0]) or any(grid[-1]) or any(r[0] or r[-1] for r in grid):
                issues.append(f'{label} {i}: ink on the cell border')
    pos = 0xF40000
    while True:
        code, _, ptr, adv = struct.unpack_from('<HHII', rom, pos)
        if not 0x08000000 <= ptr < 0x09000000:
            break
        if ptr >= 0x08F42000:
            dec = lz77_decompress(rom, ptr - 0x08000000)
            grid = aw_fonts.obj_canvas(dec[0], 1, 4, 4) if dec else None
            if grid is None or any(v for row in grid for v in row[min(adv, 32):]) or any(grid[-1]):
                issues.append(f'mission-title glyph {code:04X}: ink beyond its {adv}px advance or cell')
        pos += 12
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    args = ap.parse_args()
    issues = check(Path(args.rom).read_bytes(), ORIGINAL.read_bytes())
    for issue in issues:
        print('FAIL', issue)
    print('RESULT:', 'PASS' if not issues else f'FAIL ({len(issues)})')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
