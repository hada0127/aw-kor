"""Observed Part 1 '두 명의 료' title, two native 64x32 OBJ cells."""
import hashlib
import struct
from pathlib import Path

from functools import lru_cache

import aw_fonts
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


MAX_SIZE, MIN_SIZE = 20, 12


def _ink(size):
    ink, _ = aw_fonts.okdandan_ink(TEXT, (2, 2, 126, 30), 0, size=size)
    if not ink or any(not (1 <= x < 127 and 1 <= y < 31) for x, y in ink):
        raise AssertionError('Part 1 M19 title exceeds native OBJ cells')
    return ink


@lru_cache(maxsize=1)
def render():
    # 2026-10-08 font rule: large title -> OkDanDan (was Galmuri7 at 2x). Largest
    # size <= 20 (native title ink is ~21 rows) whose sheet fits the allocation.
    # Public native OAM22/23: 64x32, tile0/32, palette6, identity affine matrix.
    for size in range(MAX_SIZE, MIN_SIZE - 1, -1):
        try:
            raw = _sheet(_ink(size))
        except AssertionError:
            continue
        if len(lz77_compress_optimal(raw, vram_safe=True)) <= CAPACITY:
            return raw
    raise AssertionError('Part 1 M19 title compressed allocation overflow')


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
    raw = bytearray(2048)
    for y in range(32):
        for x in range(128):
            tile = (x // 64) * 32 + (y // 8) * 8 + (x % 64) // 8
            offset = tile * 32 + (y % 8) * 4 + (x % 8) // 2
            raw[offset] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def patch(rom, original):
    source_guard(original)
    if (bytes(rom[POINTER:POINTER + 8]) != original[POINTER:POINTER + 8]
            or bytes(rom[SOURCE:FOLLOWING]) != original[SOURCE:FOLLOWING]):
        raise AssertionError('Part 1 M19 title source already modified by another writer')
    raw = render()
    compressed = lz77_compress_optimal(raw, vram_safe=True)
    if len(compressed) > CAPACITY:
        raise AssertionError('Part 1 M19 title compressed allocation overflow')
    rom[SOURCE:SOURCE + CAPACITY] = compressed + bytes(CAPACITY - len(compressed))
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != raw:
        raise AssertionError('Part 1 M19 title round trip failed')
    return 1


def capture(rom, original):
    source_guard(original)
    decoded = lz77_decompress(rom, SOURCE)
    if (decoded is None or len(decoded[0]) != 2048 or decoded[1] > CAPACITY
            or bytes(rom[POINTER:POINTER + 8]) != original[POINTER:POINTER + 8]
            or bytes(rom[SOURCE + CAPACITY:FOLLOWING]) != original[SOURCE + CAPACITY:FOLLOWING]):
        raise AssertionError('Part 1 M19 title final allocation changed')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]))
    # Approved editor pixel changes remain supported; freeze their final bytes.
    return ((SOURCE, bytes(rom[SOURCE:FOLLOWING])),
            (POINTER, bytes(rom[POINTER:POINTER + 8])))


def verify(rom, regions):
    if len(regions) != 2 or tuple(p for p, _ in regions) != (SOURCE, POINTER):
        raise AssertionError('Part 1 M19 title snapshot missing')
    if any(bytes(rom[p:p + len(raw)]) != raw for p, raw in regions):
        raise AssertionError('Part 1 M19 title overwritten after editor')


def generated_matches(rom):
    decoded = lz77_decompress(rom, SOURCE)
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
