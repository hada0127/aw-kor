"""Part 2 campaign-map army-name OBJ labels: BLUE MOON / GREEN EARTH / YELLOW COMET.

Static RE (original ROM, 2026-10-06 fixH):
- Table 0x08A3924C = 4 x (u32 LZ77 pointer, u32 value): RED STAR 0x5488A0,
  BLUE MOON 0x5489DC, GREEN EARTH 0x548B50, YELLOW COMET 0x548CD0.  Its only
  reference is the literal at 0x08376F54, used by 0x08376EDC: it loads the OBJ
  palette 0x08547E08 (colours 0x2A0.., i.e. OBJ banks 10/11), decompresses
  table[army].ptr into VRAM 0x06012000 (OBJ tile 256) and 0x08548E58 into
  0x06012600.  Each label is 1536 B = three 32x32 1D OBJ cells (96x32).
- RED STAR is already Korean (build_korean_full.patch_part2_redstar_region_obj:
  OkDanDan-Bold 16px in x 6..89, y 0..15 (2026-10-08 font rule; was Galmuri7 2x),
  ink 4, shadow 7 at (+1,0)/(+1,+1), no plate).
  The other three use their own ink index in the same palette: blue 13,
  green 15, yellow 14 (the plate/shadow index 7 is shared).
This module renders 블루문 / 그린어스 / 옐로코멧 (data/proper_nouns.json nations)
with exactly the red-star renderer and its ink index per army.
On-screen result unverified (only hidden y=160 OAM seen in savestates).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

import aw_fonts
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
TABLE = 0xA3924C
TABLE_POOL = 0x376F54
SIZE = 1536
WIDTH, HEIGHT, SCALE, CURSOR, SHADOW = 96, 32, 2, 13, 7
# One OkDanDan line over all four region names (red star is drawn by build_korean_full).
REGION_LINE_CHARS = '레드스타블루문그린어스옐로코멧'
# (source, pointer, capacity=original consumed, decoded sha256, Korean, ink, English)
LABELS = (
    (0x5489DC, 0xA39254, 372, 'f3ad36520203a12ce9a52ed119362b665ff85743f3ed09e476bd82af6e1b46d3',
     '블루문', 13, 'BLUE MOON'),
    (0x548B50, 0xA3925C, 381, '158b2a69069f5a7029c96274754f865dc58dce26a1ad2d9c25b875abcf9da8f8',
     '그린어스', 15, 'GREEN EARTH'),
    (0x548CD0, 0xA39264, 390, 'e8c955ab6e650887da335b302e140289eea6677752a16345d8183121c3b54ae0',
     '옐로코멧', 14, 'YELLOW COMET'),
)


def render_pixels(text, ink):
    """Same call as patch_part2_redstar_region_obj (ink index per army):
    OkDanDan-Bold on the common line (2026-10-08 font rule; was Galmuri7 2x)."""
    pixels = [[0] * WIDTH for _ in range(HEIGHT)]
    aw_fonts.draw_okdandan(pixels, text, (6, 0, 90, 16), 20, ink=ink, shadow=SHADOW,
                           shadow_offset=((1, 1), (1, 0)), valign='line', line_chars=REGION_LINE_CHARS)
    return pixels


def encode(pixels):
    out = bytearray(SIZE)
    for sprite in range(3):
        for ty in range(4):
            for tx in range(4):
                tile = sprite * 16 + ty * 4 + tx
                for row in range(8):
                    for col in range(8):
                        v = pixels[ty * 8 + row][sprite * 32 + tx * 8 + col] & 15
                        out[tile * 32 + row * 4 + col // 2] |= v << (4 * (col % 2))
    return bytes(out)


def decode(data):
    pixels = [[0] * WIDTH for _ in range(HEIGHT)]
    for sprite in range(3):
        for t in range(16):
            for row in range(8):
                for col in range(8):
                    v = (data[(sprite * 16 + t) * 32 + row * 4 + col // 2] >> (4 * (col % 2))) & 15
                    pixels[(t // 4) * 8 + row][sprite * 32 + (t % 4) * 8 + col] = v
    return pixels


def source_guard(original):
    if struct.unpack_from('<I', original, TABLE_POOL)[0] != TABLE + ROM_BASE:
        raise AssertionError('army name table literal changed')
    for source, pointer, capacity, digest, *_ in LABELS:
        if struct.unpack_from('<I', original, pointer)[0] != source + ROM_BASE:
            raise AssertionError(f'army name pointer changed {pointer:06X}')
        if original.count(struct.pack('<I', source + ROM_BASE)) != 1:
            raise AssertionError(f'army name block has foreign reference {source:06X}')
        decoded = lz77_decompress(original, source)
        if (decoded is None or decoded[1] != capacity or len(decoded[0]) != SIZE
                or hashlib.sha256(decoded[0]).hexdigest() != digest):
            raise AssertionError(f'army name source changed {source:06X}')


def sheet(text, ink):
    return encode(render_pixels(text, ink))


@lru_cache(maxsize=8)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    source_guard(original)
    out = []
    for source, _, capacity, _, text, ink, _ in LABELS:
        stream = _stream(sheet(text, ink))
        if len(stream) > capacity:
            raise AssertionError(f'army name overflow {source:06X}: {len(stream)} > {capacity}')
        out.append((source, stream + bytes(capacity - len(stream))))
    return tuple(out)


def _fixed(original):
    return tuple((p, bytes(original[p:p + 4])) for _, p, *_ in LABELS) + (
        (TABLE_POOL, bytes(original[TABLE_POOL:TABLE_POOL + 4])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError(f'army name pointer changed in ROM {address:06X}')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'army name {address:06X} already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    for source, _, _, _, text, ink, _ in LABELS:
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != sheet(text, ink):
            raise AssertionError(f'army name round trip failed {source:06X}')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError(f'army name final pointer changed {address:06X}')
    for (address, new), (_, _, capacity, *_) in zip(regions, LABELS):
        decoded = lz77_decompress(rom, address)
        if decoded is None or len(decoded[0]) != SIZE or decoded[1] > capacity:
            raise AssertionError(f'army name final block invalid {address:06X}')
        verify_vram_stream(bytes(rom[address:address + capacity]), SIZE, f'army name {address:06X}')
    return tuple((a, bytes(rom[a:a + len(n)])) for a, n in regions) + _fixed(original)


def expected_region_addresses():
    return tuple(row[0] for row in LABELS) + tuple(row[1] for row in LABELS) + (TABLE_POOL,)


def verify(rom, regions):
    if tuple(a for a, _ in regions) != expected_region_addresses():
        raise AssertionError('army name snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'army name overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    for source, _, _, _, text, ink, _ in LABELS:
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != sheet(text, ink):
            return False
    return True
