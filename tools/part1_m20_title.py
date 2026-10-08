"""Observed Part 1 '흑막' title, two native 64x32 OBJ cells."""
import hashlib
import struct
from pathlib import Path

from functools import lru_cache

import aw_fonts
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal
from part1_m19_title import verify_vram_stream

ROOT = Path(__file__).resolve().parent.parent
SOURCE, POINTER, FOLLOWING = 0xC15C5C, 0xE12CE0, 0xC15E00
CAPACITY = 418
SOURCE_SHA = 'baad8f03eb0b9403c49aa05f3da18652590ba58a91f03c004e3466ab0225bf22'
TEXT = '흑막'


def source_guard(original):
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != 2048 or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA
            or original.count(struct.pack('<I', SOURCE + 0x08000000)) != 1
            or struct.unpack_from('<II', original, POINTER) !=
            (SOURCE + 0x08000000, FOLLOWING + 0x08000000)):
        raise AssertionError('Part 1 M20 title source/allocation changed')


MAX_SIZE, MIN_SIZE = 20, 12


def _ink(size):
    ink, _ = aw_fonts.okdandan_ink(TEXT, (2, 2, 126, 30), 0, size=size)
    if not ink or any(not (1 <= x < 127 and 1 <= y < 31) for x, y in ink):
        raise AssertionError('Part 1 M20 title exceeds native OBJ cells')
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
    raise AssertionError('Part 1 M20 title compressed allocation overflow')


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
        raise AssertionError('Part 1 M20 title source already modified by another writer')
    raw = render()
    compressed = lz77_compress_optimal(raw, vram_safe=True)
    if len(compressed) > CAPACITY:
        raise AssertionError('Part 1 M20 title compressed allocation overflow')
    rom[SOURCE:SOURCE + CAPACITY] = compressed + bytes(CAPACITY - len(compressed))
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != raw:
        raise AssertionError('Part 1 M20 title round trip failed')
    return 1


def capture(rom, original):
    source_guard(original)
    decoded = lz77_decompress(rom, SOURCE)
    if (decoded is None or len(decoded[0]) != 2048 or decoded[1] > CAPACITY
            or bytes(rom[POINTER:POINTER + 8]) != original[POINTER:POINTER + 8]
            or bytes(rom[SOURCE + CAPACITY:FOLLOWING]) != original[SOURCE + CAPACITY:FOLLOWING]):
        raise AssertionError('Part 1 M20 title final allocation changed')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]))
    # Approved editor pixel changes remain supported; freeze their final bytes.
    return ((SOURCE, bytes(rom[SOURCE:FOLLOWING])),
            (POINTER, bytes(rom[POINTER:POINTER + 8])))


def verify(rom, regions):
    if len(regions) != 2 or tuple(p for p, _ in regions) != (SOURCE, POINTER):
        raise AssertionError('Part 1 M20 title snapshot missing')
    if any(bytes(rom[p:p + len(raw)]) != raw for p, raw in regions):
        raise AssertionError('Part 1 M20 title overwritten after editor')


def generated_matches(rom):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == render()

