"""Observed Part 1 '두 명의 료' title, two native 64x32 OBJ cells."""
import hashlib
import struct
from pathlib import Path

from functools import lru_cache

import aw_fonts
from sprite_text_aa import palette_blend_index
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
SOURCE, POINTER, FOLLOWING = 0xC15A68, 0xE12CDC, 0xC15C5C
CAPACITY = 498
SOURCE_SHA = '98eb0a93f24a3443c84bc89d58750270d57ad6e8dd4b98a359196f38e2b1b41c'
TEXT = '두 명의 료'


def source_guard(original):
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != 2048 or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA
            or original.count(struct.pack('<I', SOURCE + 0x08000000)) != 1
            or struct.unpack_from('<II', original, POINTER) !=
            (SOURCE + 0x08000000, FOLLOWING + 0x08000000)):
        raise AssertionError('Part 1 M19 title source/allocation changed')


MAX_SIZE = 24
RELOCATION = 0xFDB000
RELOCATION_LIMIT = 0xFDB400

# Native mission-entry OAM22/23 bank 6, captured in
# temp/continuation_2026-10-02/p1_m19_title/public_oam_evidence.json
# states 0019..0021. No PRAM write is made.
MISSION_OBJ6_BGR555 = (237, 32733, 32634, 32534, 32467, 32368, 32268, 32169,
                       32037, 237, 32767, 25369, 19026, 11628, 11429, 2182)
MISSION_OBJ6_RGB = tuple(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31,
                          ((v >> 10) & 31) * 255 // 31) for v in MISSION_OBJ6_BGR555)


def soften_mission_body(pixels, max_adjacent=1):
    """Shade only two-sided body corners; keep the native outline and mask."""
    before = tuple(tuple(row) for row in pixels)
    for y in range(1, len(pixels) - 1):
        for x in range(1, len(pixels[0]) - 1):
            if before[y][x] != 10:
                continue
            adjacent = sum(before[y + dy][x + dx] == 10
                           for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            if adjacent <= max_adjacent:
                pixels[y][x] = palette_blend_index(13, 10, 192, (10, 11, 12, 13),
                                                   (MISSION_OBJ6_RGB,))
    if any((v == 10 or v == 11) != (before[y][x] == 10)
           for y, row in enumerate(pixels) for x, v in enumerate(row)):
        raise AssertionError('mission AA changed occupied body pixels')


def _ink(size):
    from part1_mission_titles import _ink_hada
    ink = _ink_hada(TEXT, 128, size)
    if not ink or any(not (1 <= x < 127 and 1 <= y < 31) for x, y in ink):
        raise AssertionError('Part 1 M19 title exceeds native OBJ cells')
    return ink


@lru_cache(maxsize=1)
def render():
    # Keep the approved 24px input size; AA must not shrink the native geometry.
    # Public native OAM22/23: 64x32, tile0/32, palette6, identity affine matrix.
    ink = _ink(MAX_SIZE)
    aw_fonts.require_large_line(ink, 1, 1)
    raw = _sheet(ink)
    return raw


def _sheet(ink):
    pixels = [[0] * 128 for _ in range(32)]
    for x, y in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                pixels[y + dy][x + dx] = 15
    for x, y in ink:
        pixels[y + 1][x + 1] = 13
    for x, y in ink:
        pixels[y][x] = 10
    soften_mission_body(pixels)
    raw = bytearray(2048)
    for y in range(32):
        for x in range(128):
            tile = (x // 64) * 32 + (y // 8) * 8 + (x % 64) // 8
            offset = tile * 32 + (y % 8) * 4 + (x % 8) // 2
            raw[offset] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def patch(rom, original):
    source_guard(original)
    if (bytes(rom[POINTER:POINTER + 4]) != original[POINTER:POINTER + 4]
            or bytes(rom[SOURCE:FOLLOWING]) != original[SOURCE:FOLLOWING]):
        raise AssertionError('Part 1 M19 title source already modified by another writer')
    raw = render()
    # Same mission-start consumer as part1_mission_titles: its native sheets
    # prove the two 64x32 OBJs are drawn edge to edge.
    import part1_mission_titles
    part1_mission_titles.check_cells(original, source=-1)
    aw_fonts.check_cells(aw_fonts.obj_canvas(raw, 2, 8, 4), (64,), 'Part 1 M19 title', native=True)
    compressed = lz77_compress_optimal(raw, vram_safe=True)
    address = SOURCE
    if len(compressed) > CAPACITY:
        if len(compressed) > RELOCATION_LIMIT - RELOCATION:
            raise AssertionError('Part 1 M19 title relocation overflow')
        if any(original[RELOCATION:RELOCATION_LIMIT]) or any(rom[RELOCATION:RELOCATION_LIMIT]):
            raise AssertionError('Part 1 M19 title relocation occupied')
        if any(RELOCATION + 0x08000000 <= value < RELOCATION_LIMIT + 0x08000000
               for value in memoryview(original).cast('I')):
            raise AssertionError('Part 1 M19 title relocation referenced')
        rom[RELOCATION:RELOCATION + len(compressed)] = compressed
        struct.pack_into('<I', rom, POINTER, RELOCATION + 0x08000000)
        address = RELOCATION
    else:
        rom[SOURCE:SOURCE + CAPACITY] = compressed + bytes(CAPACITY - len(compressed))
    decoded = lz77_decompress(rom, address)
    if decoded is None or decoded[0] != raw:
        raise AssertionError('Part 1 M19 title round trip failed')
    return 1


def capture(rom, original):
    source_guard(original)
    address = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    capacity = CAPACITY if address == SOURCE else RELOCATION_LIMIT - RELOCATION
    decoded = lz77_decompress(rom, address)
    old_span = slice(SOURCE, FOLLOWING) if address != SOURCE else slice(SOURCE + CAPACITY, FOLLOWING)
    if (address not in (SOURCE, RELOCATION) or decoded is None or len(decoded[0]) != 2048
            or decoded[1] > capacity
            or bytes(rom[old_span]) != original[old_span]):
        raise AssertionError('Part 1 M19 title final allocation changed')
    verify_vram_stream(bytes(rom[address:address + decoded[1]]))
    # Approved editor pixel changes remain supported; freeze their final bytes.
    return ((SOURCE, bytes(rom[SOURCE:FOLLOWING])),
            (POINTER, bytes(rom[POINTER:POINTER + 4])),
            (address, bytes(rom[address:address + decoded[1]])))


def verify(rom, regions):
    if len(regions) != 3 or tuple(p for p, _ in regions[:2]) != (SOURCE, POINTER):
        raise AssertionError('Part 1 M19 title snapshot missing')
    if any(bytes(rom[p:p + len(raw)]) != raw for p, raw in regions):
        raise AssertionError('Part 1 M19 title overwritten after editor')


def generated_matches(rom):
    address = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    decoded = lz77_decompress(rom, address)
    return decoded is not None and decoded[0] == render()


def verify_vram_stream(stream):
    """Validate final editor output for BIOS halfword VRAM decompression too."""
    if stream[:4] != b'\x10\x00\x08\x00':
        raise AssertionError('Part 1 M19 title LZ header changed')
    count, cursor = 0, 4
    try:
        while count < 2048:
            flags = stream[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if count >= 2048:
                    break
                if flags & (1 << bit):
                    a, b = stream[cursor], stream[cursor + 1]
                    cursor += 2
                    distance = ((a & 15) << 8 | b) + 1
                    if not 2 <= distance <= count:
                        raise AssertionError('Part 1 M19 title unsafe VRAM LZ distance')
                    count += (a >> 4) + 3
                else:
                    _ = stream[cursor]
                    cursor += 1
                    count += 1
                if count > 2048:
                    raise AssertionError('Part 1 M19 title LZ output overrun')
    except IndexError as exc:
        raise AssertionError('Part 1 M19 title truncated LZ stream') from exc
    return cursor
