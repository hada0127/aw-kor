"""Korean-style 、(0x8141) / 。(0x8142) glyph images shared by the builder and QA.

Only the glyph images change (temp/fix_20261104/punct_glyph_research.md option a);
the text bytes stay 0x8141/0x8142. P1 per-char path: symbol-table top is the
shared blank slot 95 (never touched), bottom is a private FONT_BASE slot. P2 A3
glyph cache: a private node whose 64 pixel bytes start at node+6.
"""

FONT_BASE = 0xB974D0
TOP_BLANK_SLOT = 95
P1_BOTTOM_SLOT = {0x8141: 286, 0x8142: 285}
A3_NODE = {0x8141: 0x807BE8, 0x8142: 0x807D50}
INK = 10  # same nibble as the native marks and the A3 keyword colour remap
# Hangul baseline is cell row 13; marks sit at x=1..2 next to the previous glyph.
PIXELS = {
    0x8141: ((2, 12), (1, 13)),                    # Galmuri ',' (.x / x.)
    0x8142: ((1, 12), (2, 12), (1, 13), (2, 13)),  # 2x2 period (1x1 vanishes)
}


def bottom_tile(code):
    """4bpp 8x8 bottom tile (cell rows 8-15) for 0x8141/0x8142."""
    tile = bytearray(32)
    for x, y in PIXELS[code]:
        tile[(y - 8) * 4 + x // 2] |= INK << (4 * (x % 2))
    return bytes(tile)


def expected_symbol_tile(code, delta, original_tile):
    """Tile a symbol-table entry (delta 0 = top, 8 = bottom) should show."""
    if code in PIXELS and delta == 8:
        return bottom_tile(code)
    if code == ELLIPSIS and delta == 8:
        return ellipsis_bottom_tile()
    return bytes(original_tile)


def symbol_tile_ok(code, delta, tile, original_tile):
    """QA: the native tile, or the Korean redraw for 0x8141/0x8142 bottoms."""
    tile = bytes(tile)
    return tile == bytes(original_tile) or tile == expected_symbol_tile(code, delta, original_tile)


# ---------------------------------------------------------------------------
# One-cell ellipsis 「…」 (fixB J, plan_C §1 J option E3, spike S6).
# Code 0x8163 had no visible glyph: P1 symbol table idx 67/75 -> 95/95 (blank)
# in both the per-char/B11 table 0xB8027C and the 313 tilemap copy 0x38F9E4,
# and the P2 A3 bucket 0x63 had no 0x81 node. The top stays the shared blank
# slot 95; the bottom (idx 75) points at the private slot below. The A3 node
# is new (same layout as the 0xFD0000/0xFD0050 nodes).
# Pixels: Galmuri U+2026 = three 1px dots x=2,4,6 at the centre height
# (5 px above the Hangul baseline row 13 -> row 8, the 0x8145 dot row).
ELLIPSIS = 0x8163
ELLIPSIS_SYMBOL_INDEX = 67                      # top idx; bottom = idx + 8
ELLIPSIS_SYMBOL_TABLES = (0xB8027C, 0x38F9E4)   # per-char/B11 table, 313 copy
ELLIPSIS_P1_BOTTOM_SLOT = 255                   # no owner in original/fixA (S6)
ELLIPSIS_A3_NODE = 0xFD00A0                     # free 0xFD00A0..0xFD00FF (S6)
ELLIPSIS_A3_BUCKET = 0x807680 + 0x63 * 4
ELLIPSIS_PIXELS = ((2, 8), (4, 8), (6, 8))
MIDDLE_DOT = b'\x81\x45'


def ellipsis_bottom_tile():
    """4bpp 8x8 bottom tile (cell rows 8-15) for 0x8163."""
    tile = bytearray(32)
    for x, y in ELLIPSIS_PIXELS:
        tile[(y - 8) * 4 + x // 2] |= INK << (4 * (x % 2))
    return bytes(tile)


def ellipsis_cells(run):
    """「・」 run length -> number of 「…」 cells (0 = keep the run as is).

    1-2 dots are real middle dots (해상·공중, １・５, name grid) and stay.
    3-5 dots are one ellipsis cell; 6 or more are two (「……」).
    """
    if run < 3:
        return 0
    return 1 if run <= 5 else 2


def compact_ellipsis_text(text):
    """Text form of the byte rule: runs of 3-5 「・」 -> 「…」, 6+ -> 「……」."""
    import re
    return re.sub('・{3,}', lambda m: '…' * ellipsis_cells(len(m.group(0))), text)


def _two_byte_lead(byte):
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xEF


def compact_ellipsis_bytes(payload):
    """Same-length rewrite of one text payload tokenized from its start.

    A segment is a maximal run of two-byte glyphs and 0x20 spaces between
    single-byte controls (or the payload ends). Inside a segment every run of
    3+ 0x8145 tokens becomes 1 or 2 0x8163 tokens; the freed bytes become 0x20
    slot padding at the end of that segment (just before its control), which
    the P1 per-char and P2 31424C dialogue consumers do not draw. Control
    offsets, row starts and the payload length never move.
    Returns (new_bytes, [(segment_offset, segment_length), ...]).
    """
    data = bytes(payload)
    tokens = []  # (offset, raw)
    i = 0
    while i < len(data):
        if _two_byte_lead(data[i]) and i + 1 < len(data):
            tokens.append((i, data[i:i + 2]))
            i += 2
        else:
            tokens.append((i, data[i:i + 1]))
            i += 1
    out = bytearray(data)
    changed = []
    k = 0
    while k < len(tokens):
        if len(tokens[k][1]) == 1 and tokens[k][1] != b'\x20':
            k += 1
            continue
        start = k
        while k < len(tokens) and (len(tokens[k][1]) == 2 or tokens[k][1] == b'\x20'):
            k += 1
        seg = tokens[start:k]
        seg_off = seg[0][0]
        seg_len = sum(len(raw) for _, raw in seg)
        new = bytearray()
        j = 0
        hit = False
        while j < len(seg):
            if seg[j][1] == MIDDLE_DOT:
                n = j
                while n < len(seg) and seg[n][1] == MIDDLE_DOT:
                    n += 1
                cells = ellipsis_cells(n - j)
                if cells:
                    new += ELLIPSIS.to_bytes(2, 'big') * cells
                    hit = True
                else:
                    new += MIDDLE_DOT * (n - j)
                j = n
                continue
            new += seg[j][1]
            j += 1
        if hit:
            new += b'\x20' * (seg_len - len(new))
            out[seg_off:seg_off + seg_len] = new
            changed.append((seg_off, seg_len))
    return bytes(out), changed


# ---------------------------------------------------------------------------
# plan_C J vs byte pins, decision (a): the compaction pass logs each rewritten
# segment with its exact pre-compaction bytes. Verifiers that pin bytes or
# compare authored spacing check the pre-compaction form and this exact
# transform instead of folding the shipped 「…」.
COMPACT_WRITER = 'ellipsis-compact'


def restore_precompaction(rom, writes):
    """(pre-compaction ROM bytes, writes without compaction entries).

    Every compaction entry must hold ``before_hex``; ``compact_ellipsis_bytes``
    of those bytes must give exactly the logged bytes as one whole segment; the
    ROM must still show them; entries may not overlap. Raises ValueError.
    """
    out = bytearray(rom)
    kept, spans = [], []
    for entry in writes:
        if entry[7] != COMPACT_WRITER:
            kept.append(entry)
            continue
        if len(entry) < 9 or not isinstance(entry[8], dict) or 'before_hex' not in entry[8]:
            raise ValueError('ellipsis compaction write lacks its pre-compaction bytes')
        address, size = int(entry[0]), int(entry[1])
        before, after = bytes.fromhex(entry[8]['before_hex']), bytes.fromhex(entry[3])
        if int(entry[2]) != size or len(before) != size or len(after) != size or size <= 0:
            raise ValueError(f'ellipsis compaction write size invalid at 0x{address:X}')
        new, segments = compact_ellipsis_bytes(before)
        if new != after or segments != [(0, size)]:
            raise ValueError(f'ellipsis compaction transform mismatch at 0x{address:X}')
        if bytes(rom[address:address + size]) != after:
            raise ValueError(f'final ROM lost the compacted segment at 0x{address:X}')
        if any(lo < address + size and address < hi for lo, hi in spans):
            raise ValueError(f'overlapping ellipsis compaction writes at 0x{address:X}')
        spans.append((address, address + size))
        out[address:address + size] = before
    return bytes(out), kept
