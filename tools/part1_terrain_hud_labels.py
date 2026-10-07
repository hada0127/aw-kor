"""Part 1 terrain HUD stat labels (raw 16x16 OBJ blocks, 4 tiles TL TR BL BR).

0xB93BD0 is the defense label 防 and 0xB93C50 the capture-durability label 耐,
drawn next to the terrain stars / capture points (Part 1 HUD OAM 41/42, palette 2).
A 2026-05-30 Part 2 overlay pass wrote '육' over 防 by mistake. Both are redrawn
as one-syllable Korean labels in the original style: white ink (1) with a 1px
dark outline (15), glyph rows 4..10 / outline rows 3..11 like the source kanji.
방 = 방어 (defense), 내 = 내구 (durability).
"""
import hashlib
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (offset, Korean label, sha256 of the original 128-byte 防 / 耐 block)
LABELS = ((0xB93BD0, '방', 'e71ad7839f45850ff6096806e4759fb036b351f4771145a68e0918e062164407'),
          (0xB93C50, '내', 'a154db90daf47be12c5f60318b704f3626ae5c5536f5f2ca534f4540cb97af70'))


def render_outlined_16(ch, font):
    from bdf import glyph_grid
    grid, w, h, xo, yo = glyph_grid(font[ord(ch)])
    x0 = (16 - w) // 2
    glyph = {(x0 + c + xo, 4 + r + yo) for r in range(h) for c in range(w) if grid[r][c]}
    outline = {(x + dx, y + dy) for x, y in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (x + dx, y + dy) not in glyph}
    if any(not (0 <= x < 16 and 1 <= y < 14) for x, y in glyph | outline):
        raise AssertionError(f'terrain HUD label {ch} leaves its cell')
    tiles = [bytearray(32) for _ in range(4)]
    for (x, y), value in [(p, 15) for p in outline] + [(p, 1) for p in glyph]:
        t = (y // 8) * 2 + x // 8
        i = (y % 8) * 4 + (x % 8) // 2
        if x & 1:
            tiles[t][i] = (tiles[t][i] & 0x0F) | (value << 4)
        else:
            tiles[t][i] = (tiles[t][i] & 0xF0) | value
    return b''.join(tiles)


def source_hashes(original):
    return {hex(off): hashlib.sha256(original[off:off + 128]).hexdigest() for off, _, _ in LABELS}


def patch(rom, original):
    from bdf import load_bdf
    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri7.bdf'))
    for off, ch, source in LABELS:
        if hashlib.sha256(original[off:off + 128]).hexdigest() != source:
            raise AssertionError(f'terrain HUD label source changed at 0x{off:X}')
        rom[off:off + 128] = render_outlined_16(ch, font)
    return len(LABELS)
