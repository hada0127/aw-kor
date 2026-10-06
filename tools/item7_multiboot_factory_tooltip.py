"""Factory tooltip plates (生産/処分) inside the link-play multiboot client images.

The sweep listed 0x92A9B0 (+ copies) as a "pointerless kanji banner".  It is
not pointerless: each copy lives inside a GBA multiboot client image embedded
in the cartridge and is referenced by an EWRAM-relative literal inside that
image (image base -> 0x02000000):

  copy      image (header / ROM pointer)              in-image literal
  0x92A9B0  0x90DC7C body (Part 2 ptr 0x391408)       0x91803C = 0x0201CD34
  0x964638  0x9463FC header (Part 2 ptr 0x39140C)     0x950AA4 = 0x0201E23C
  0x99CEDC  0x97ECA0 header (no cartridge pointer)    0x989348 = 0x0201E23C
  0x9D5780  0x9B7544 header (no cartridge pointer)    0x9C1BEC = 0x0201E23C
  0xEE532C  0xEC6374 header (Part 1 ptrs 0xB34B24/DA8) 0xED0C18 = 0x0201EFB8

(The project already patches sibling assets in the same images, e.g. the
battle-start overlays in patch_part2_battle_start_day_overlay_obj.)

Each copy decodes to 80 tiles = the main-cart block 0xBA4948 (88 tiles) minus
its tiles 60..67: client tiles 0..59 == main 0..59, 60..79 == main 68..87.
The 生産/処分 plates are main tiles 72..87 -> client tiles 64..79.  They are
replaced by part1_factory_tooltip_label's already reviewed Korean tiles
(생산 / 처분), so the client shows the same plates as the main cart.
Live client display is unverified (no link-play capture).
"""
import hashlib
import struct

from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress
import part1_factory_tooltip_label as tooltip

SIZE = 2560
CAPACITY = 1018
SOURCE_SHA256 = '0bf9215ce6e54f3c664a3375a65bc59effc54dc4d3c2fd5d25d5408db6f49411'
# (LZ77 offset, image base, in-image literal address)
COPIES = (
    (0x92A9B0, 0x90DC7C, 0x91803C),
    (0x964638, 0x9463FC, 0x950AA4),
    (0x99CEDC, 0x97ECA0, 0x989348),
    (0x9D5780, 0x9B7544, 0x9C1BEC),
    (0xEE532C, 0xEC6374, 0xED0C18),
)
CLIENT_TILES = range(64, 80)
MAIN_SHIFT = 8  # main-cart tile = client tile + 8 for client tiles >= 60


def _literal(base, offset):
    return 0x02000000 + offset - base


def source_guard(original):
    main = tooltip.source_block(original)
    for offset, base, literal in COPIES:
        decoded = lz77_decompress(original, offset)
        if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
                or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
            raise AssertionError(f'multiboot tooltip copy changed {offset:06X}')
        if struct.unpack_from('<I', original, literal)[0] != _literal(base, offset):
            raise AssertionError(f'multiboot tooltip in-image literal changed {literal:06X}')
        if any(original[offset + CAPACITY:offset + CAPACITY + 2]):
            raise AssertionError(f'multiboot tooltip padding changed {offset:06X}')
    data = lz77_decompress(original, COPIES[0][0])[0]
    if data[:60 * 32] != main[:60 * 32] or data[60 * 32:] != main[68 * 32:88 * 32]:
        raise AssertionError('multiboot tooltip copy no longer mirrors 0xBA4948')
    return data


def decoded_replacement(original):
    data = bytearray(source_guard(original))
    korean = tooltip.decoded_replacement(original)
    for tile in CLIENT_TILES:
        main = tile + MAIN_SHIFT
        data[tile * 32:tile * 32 + 32] = korean[main * 32:main * 32 + 32]
    return bytes(data)


def compressed_replacement(original):
    expected = decoded_replacement(original)
    stream = lz77_compress_optimal(expected, vram_safe=True)
    if len(stream) > CAPACITY:
        raise AssertionError(f'multiboot tooltip LZ77 grew: {len(stream)} > {CAPACITY}')
    check = lz77_decompress(stream, 0)
    if check is None or check[0] != expected:
        raise AssertionError('multiboot tooltip LZ77 round trip failed')
    return stream + bytes(CAPACITY - len(stream))


def patch(rom, original):
    payload = compressed_replacement(original)
    for offset, _, literal in COPIES:
        current = bytes(rom[offset:offset + CAPACITY])
        if current not in (bytes(original[offset:offset + CAPACITY]), payload):
            raise AssertionError(f'multiboot tooltip {offset:06X} conflicts with an earlier writer')
        if rom[literal:literal + 4] != original[literal:literal + 4]:
            raise AssertionError(f'multiboot tooltip literal {literal:06X} changed')
    for offset, _, _ in COPIES:
        rom[offset:offset + CAPACITY] = payload
    return len(COPIES)


def generated_matches(rom, original):
    payload = compressed_replacement(original)
    return all(bytes(rom[o:o + CAPACITY]) == payload for o, _, _ in COPIES)


def capture(rom, original):
    source_guard(original)
    regions = []
    for offset, _, literal in COPIES:
        decoded = lz77_decompress(rom, offset)
        if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
            raise AssertionError(f'multiboot tooltip final block invalid {offset:06X}')
        if rom[literal:literal + 4] != original[literal:literal + 4]:
            raise AssertionError(f'multiboot tooltip final literal changed {literal:06X}')
        regions.append((offset, bytes(rom[offset:offset + CAPACITY])))
        regions.append((literal, bytes(rom[literal:literal + 4])))
    return tuple(regions)


def verify(rom, regions):
    expected = tuple(a for o, _, l in COPIES for a in (o, l))
    if tuple(a for a, _ in regions) != expected:
        raise AssertionError('multiboot tooltip snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'multiboot tooltip overwritten at {address:06X}')
