#!/usr/bin/env python3
"""Final-ROM check: no glyph ink of the drawn titles is cut at an OBJ cell edge.

For every converted multi-OBJ title (2026-10-08 font conversion) the cells are
composed as displayed and checked with aw_fonts.check_cells: ink must not touch
the outer canvas edge, and may continue across an internal OBJ edge only where
the native Japanese art of that consumer already did (static proof that the
cells are drawn edge to edge) or a screen capture proved it
(data/obj_cell_contiguity.json, tools/qa_screen_obj_contiguity.py). Per-glyph cells (power-title glyphs, banner
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
# Final candidate QA requires screen proofs captured on the candidate itself
# (--historical-proofs accepts guarded older frames for interim builds only).
FRESH = True
# (label, LZ77 offset, cells, cell_w, cell_h, first tile, native contiguity allowed, check edges)
TITLES = [
    ('Part 1 battle start 전투 개시!', 0xC10B34, 2, 8, 4, 0, True),
    ('Part 1 air mission 하늘의 적', 0xC11D9C, 2, 8, 4, 0, True),
    ('Part 1 air supremacy 하늘 제패!', 0xC1205C, 2, 8, 4, 0, True),
    ('Part 1 M19', 0xC15A68, 2, 8, 4, 0, True),
    ('Part 1 M20', 0xC15C5C, 2, 8, 4, 0, True),
    ('Part 1 result 작전 성공', 0xBFB45C, 4, 4, 4, 0, True),
    ('Part 2 link logo 멀티팩', 0x54E538, 2, 8, 4, 64, False),
    ('Part 2 recap 작전 일수', 0x5072AC, 2, 4, 2, 0, True),
] + [(f'Part 2 mode logo {off:06X}', off, 2, 8, 4, 0, False)
     for off in (0x5B7930, 0x5B7CB0, 0x5B7F38, 0x5B82B4, 0x5B8564, 0x5B8850, 0x5B8B20)]
# last field: check the outer canvas edge (boxed logos touch it by design)


def evidence(rom_original, rom, off, cells, cw, ch, first):
    """Proof the cells are drawn edge to edge: a registered screen capture
    (data/obj_cell_contiguity.json) first, else native art crossing the edge."""
    proof = aw_fonts.screen_contiguity(off, rom, final=True, fresh=FRESH)
    if proof:
        return proof, proof
    native = aw_fonts.obj_canvas(lz77_decompress(rom_original, off)[0], cells, cw, ch, first)
    rows = [aw_fonts.straddling_rows(native, cw * 8 * i) for i in range(1, cells)]
    return native, f'native:{rows}'


# (label, LZ77 offset, first tile, count, cell_w, cell_h)
CELLS = [
    ('Part 1 power title glyph', None, 0, 45, 2, 4),
    ('Part 1 campaign clear cell', 0xC43400, 32, 9, 4, 4),
    ('Part 1 versus settle cell', 0xBFC270, 0, 2, 4, 4),
]


def power_title_source(rom, count=45, cell_w=2, cell_h=4):
    """Resolve the glyph sheet used by the Part 1 power-title consumer."""
    pointer_off = 0xB3C1F4
    if pointer_off + 4 > len(rom):
        raise ValueError('Part 1 power title glyph: source pointer is outside ROM')
    pointer = struct.unpack_from('<I', rom, pointer_off)[0]
    off = pointer - 0x08000000
    if pointer < 0x08000000 or off >= len(rom):
        raise ValueError(f'Part 1 power title glyph: invalid source pointer {pointer:08X}')
    decoded = lz77_decompress(rom, off)
    cell_bytes = cell_w * cell_h * 32
    if (decoded is None or len(decoded[0]) < count * cell_bytes
            or len(decoded[0]) % cell_bytes):
        raise ValueError(f'Part 1 power title glyph: invalid source LZ77 at {off:06X}')
    return off, decoded[0], len(decoded[0]) // cell_bytes


def check(rom, original):
    import part1_mission_titles as mt
    issues, report = [], []
    at64, at128 = mt._contiguity(bytes(original))
    for label, off, cells, cw, ch, first, edges in TITLES:
        dec = lz77_decompress(rom, off)
        if dec is None:
            issues.append(f'{label}: invalid LZ77 at {off:06X}')
            continue
        canvas = aw_fonts.obj_canvas(dec[0], cells, cw, ch, first)
        crossing = [aw_fonts.straddling_rows(canvas, cw * 8 * i) for i in range(1, cells)]
        try:
            native, note = evidence(original, rom, off, cells, cw, ch, first)
            aw_fonts.check_cells(canvas, [cw * 8 * i for i in range(1, cells)], label, native=native, edges=edges)
            report.append(f'OK {label} {off:06X} crossing={crossing} evidence={note}')
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
            screen_proof = aw_fonts.screen_contiguity(owner, rom, final=True, fresh=FRESH)
            native_proof = bool(at64 and at128)
            proof = (native_proof if owner == mt.EXTENSION_OWNER else screen_proof or native_proof)
            aw_fonts.check_cells(mt._canvas(main, ext), bounds, f'Part 1 mission title {owner:06X}', native=proof)
            note = (f'{screen_proof}+native-consumer:{at64}/{at128}' if owner == mt.EXTENSION_OWNER
                    else screen_proof or f'native-consumer:{at64}/{at128}')
            report.append(f'OK Part 1 mission title {owner:06X} evidence={note}')
        except AssertionError as exc:
            issues.append(str(exc))
    for label, off, first, count, cw, ch in CELLS:
        if off is None:
            try:
                off, data, count = power_title_source(rom, count, cw, ch)
                report.append(f'OK {label} source={off:06X} cells={count}')
            except ValueError as exc:
                issues.append(str(exc))
                continue
        else:
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
    return issues, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--historical-proofs', action='store_true',
                    help='interim only: accept guarded frames from an earlier ROM (not a final pass)')
    args = ap.parse_args()
    global FRESH
    FRESH = not args.historical_proofs
    issues, report = check(Path(args.rom).read_bytes(), ORIGINAL.read_bytes())
    for line in report:
        print(line)
    for issue in issues:
        print('FAIL', issue)
    print('RESULT:', 'PASS' if not issues else f'FAIL ({len(issues)})')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
