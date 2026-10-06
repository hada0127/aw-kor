"""Part 1 campaign CO name plate for Catherine (CO struct 0, 0xDF3B54 + 4).

0xC102A8 decodes to 384 bytes = the same 48x16 plate layout as the other CO
names in part1_campaign_co_name_lz77 (32x16 cell tiles 0..7 + 16x16 cell tiles
8..11; original reads キャサリン in that layout).  The legacy build writer
(build_title_hangul.make_part1_catherine_block, a 96x8 strip) lands as small
7px text in the bottom-left 32x8 of that plate
(temp/claude_2026-10-06/fixA/work/co_names_cand.png).  This module replaces it
with part1_campaign_co_name_lz77.render_name('캐서린') (native 8x16 glyphs,
ink 10, centred), recompressed in place inside the original allocation.

patch() accepts the block as original or as the legacy 96x8 output, so it can
run after the legacy call; the build owner may also drop the legacy call.
"""
import hashlib
import struct

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal
from part1_campaign_co_name_lz77 import render_name, SIZE

ROM_BASE = 0x08000000
SOURCE = 0xC102A8
POINTER = 0xDF3B58          # CO struct table 0xDF3B54, struct 0, field +4
FOLLOWING = 0xC10380        # next CO name sheet (リョウ)
CAPACITY = 215              # original compressed length (0xC1037F pad byte kept)
TEXT = '캐서린'
ORIGINAL_SHA256 = '354029f3c3caf5effcf74d6ba1528bef8751cdb6a12fbba581d64ce680cf0030'
LEGACY_SHA256 = '0032d37c06e4644f04f7f59b79ea90e2827e92931d1245983800e5ac64e559b6'


def source_guard(original):
    if struct.unpack_from('<I', original, POINTER)[0] != SOURCE + ROM_BASE:
        raise AssertionError('Part 1 Catherine name pointer changed')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1:
        raise AssertionError('Part 1 Catherine name has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != ORIGINAL_SHA256
            or not 0 <= FOLLOWING - SOURCE - CAPACITY < 4):
        raise AssertionError('Part 1 Catherine name source/allocation changed')


def render():
    return render_name(TEXT)


def patch(rom, original):
    source_guard(original)
    if bytes(rom[POINTER:POINTER + 4]) != bytes(original[POINTER:POINTER + 4]):
        raise AssertionError('Part 1 Catherine name repointed by another writer')
    if bytes(rom[SOURCE + CAPACITY:FOLLOWING]) != bytes(original[SOURCE + CAPACITY:FOLLOWING]):
        raise AssertionError('Part 1 Catherine name padding changed')
    current = lz77_decompress(rom, SOURCE)
    allowed = (ORIGINAL_SHA256, LEGACY_SHA256, hashlib.sha256(render()).hexdigest())
    if current is None or current[1] > CAPACITY or hashlib.sha256(current[0]).hexdigest() not in allowed:
        raise AssertionError('Part 1 Catherine name already modified by another writer')
    stream = lz77_compress_optimal(render(), vram_safe=True)
    if len(stream) > CAPACITY:
        raise AssertionError(f'Part 1 Catherine name overflow: {len(stream)} > {CAPACITY}')
    rom[SOURCE:SOURCE + CAPACITY] = stream + bytes(CAPACITY - len(stream))
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != render():
        raise AssertionError('Part 1 Catherine name round trip failed')
    return 1


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    decoded = lz77_decompress(rom, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY
            or bytes(rom[POINTER:POINTER + 4]) != bytes(original[POINTER:POINTER + 4])
            or bytes(rom[SOURCE + CAPACITY:FOLLOWING]) != bytes(original[SOURCE + CAPACITY:FOLLOWING])):
        raise AssertionError('Part 1 Catherine name final allocation changed')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'Part 1 Catherine name')
    return ((SOURCE, bytes(rom[SOURCE:FOLLOWING])), (POINTER, bytes(rom[POINTER:POINTER + 4])))


def verify(rom, regions):
    if tuple(address for address, _ in regions) != (SOURCE, POINTER):
        raise AssertionError('Part 1 Catherine name snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'Part 1 Catherine name overwritten after editor at {address:06X}')


def generated_matches(rom):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == render()
