"""Korean graphics in one-pak MultiBoot bootstrap images and client payloads.

The host passes the complete, 4-byte-aligned image to BIOS MultiBoot.  Keep
its header, entry code and transfer length intact; only rebuild the nested
graphic streams in stage two and its outer LZ77 stream.  Campaign client
payloads also carry four copies of the result failure graphic.
"""
import hashlib
import struct
from functools import lru_cache

from bdf import glyph_grid, load_bdf
from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress
from link_error_bitmaps import STRIP_TEXT
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'reference/fonts/Galmuri11-Condensed.bdf'
ERROR_LINES = ('데이터 전송 실패', '다시 시도해 주세요.')
BUBBLE_LINES = ('잠시만', '기다려줘!')
BUBBLE_NATIVE_SHA = '89f99e6f4e3f502e43e40eda72dc815f776f4c18bdaf27c827c607d5c603857e'

# name, ROM image start/end, stage-two load base, warning stream/tile range,
# error sheet/map streams, their consumers' literal offsets in stage two.
IMAGES = (
    ('p2', 0x8FED9C, 0x902A8C, 0x0203C000, 0xEFC, 0x116, 52,
     0x33FC, 0x3618, (0x590, 0x598, 0x51C, 0x524)),
    ('p1', 0xEC3EE0, 0xEC6374, 0x0203C800, 0x13DC, 0, 52,
     0x1D2C, 0x1FFC, (0x70C, 0x714, 0x4EC, 0x4F4)),
)
NATIVE_STAGE2_SHA = {
    'p2': '07e10c17c52341535f17d0b6c2ae88398494d835e2ebae8c93904434d11d885b',
    'p1': '0f86e2238945a88ad0fa148854fc254b476a6ba342041f56e0f8b9e065d10853',
}
NATIVE_IMAGE_SHA = {
    'p2': 'b4959ce3b6a9c1c3d28b36d7827c1aec11a1aa65a311b87260fe2d9991481013',
    'p1': '517b5de3615b7625e13da0c329db55a1d9a9227b65d232044f3e06a8f95034c0',
}
PAYLOAD_FAILURE_COPIES = (0x92EE50, 0x967AD8, 0x9A037C, 0x9D8C20)
PAYLOAD_FAILURE_NATIVE_SHA = 'b5d1b72fbd22c88e386d16c869fbf210964d211daa8e6f5f768209579ca9240b'
FAILURE_CELL_SHA = (
    'cd6f57141133dac98c582b4aaf3a4c71bbe2d8077aaf9dc50e5f8c05b880b6e7',
    '6e97a2896574d2e672136d24db081001bc423c9c9d9227209c6c018cd0c7d6b1',
)


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(FONT))[0]


def _pixels(text):
    ink, cursor = set(), 0
    for ch in text:
        if ch == ' ':
            cursor += 4
            continue
        grid, width, height, xoff, yoff = glyph_grid(_font()[ord(ch)])
        top = 11 - (yoff + height)
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add((cursor + xoff + x, 3 + top + y))
        cursor += xoff + width + 1
    return ink, cursor - 1


def _tile_bytes(pixels, cols, rows):
    raw = bytearray(cols * rows * 32)
    for (x, y), color in pixels.items():
        if not (0 <= x < cols * 8 and 0 <= y < rows * 8):
            raise AssertionError('stage-one text exceeds tile area')
        off = ((y // 8) * cols + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
        raw[off] |= color << (4 * (x % 2))
    return bytes(raw)


def warning_tiles(cols, obj_blocks=False):
    ink, width = _pixels(STRIP_TEXT)
    x0 = (cols * 8 - width) // 2
    if x0 < 1:
        raise AssertionError('warning text has no outline margin')
    white = {(x0 + x, y) for x, y in ink}
    neighbours = ((-1, 0), (1, 0), (0, -1), (0, 1))
    red = {(x + dx, y + dy) for x, y in white for dx, dy in neighbours} - white
    black = {(x + dx, y + dy) for x, y in white | red
             for dx, dy in neighbours} - white - red
    pixels = {p: 15 for p in black}
    pixels.update({p: 8 for p in red})
    pixels.update({p: 1 for p in white})
    linear = _tile_bytes(pixels, cols, 2)
    if not obj_blocks:
        return linear
    if cols != 26:
        raise AssertionError('Part 1 warning OBJ geometry changed')
    # Part 1 draws six 32x16 OBJ blocks followed by one 16x16 block.
    # Each block stores its top row before its bottom row.
    order = []
    for block in range(6):
        for row in range(2):
            order.extend(row*cols + block*4 + col for col in range(4))
    for row in range(2):
        order.extend(row*cols + 24 + col for col in range(2))
    return b''.join(linear[i*32:(i+1)*32] for i in order)


def bubble_tiles(native):
    """Replace the Part 1 loader bubble's lettering in its two 32x32 OBJ blocks."""
    if len(native) != 32 * 32 or hashlib.sha256(native).hexdigest() != BUBBLE_NATIVE_SHA:
        raise AssertionError('Part 1 loader bubble source changed')
    pixels = {}
    for y in range(32):
        for x in range(64):
            tile = (x // 32) * 16 + (y // 8) * 4 + (x % 32) // 8
            byte = native[tile*32 + (y % 8)*4 + (x % 8)//2]
            pixels[x, y] = (byte >> (4 * (x % 2))) & 15
    # The native white spans define each row of the irregular bubble interior.
    # Clear the full span, including JP antialiasing beyond the old text boxes;
    # the outline and its shadow remain outside these spans.
    for y in range(2, 28):
        white = [x for x in range(64) if pixels[x, y] == 1]
        if not white:
            raise AssertionError('Part 1 loader bubble interior changed')
        for x in range(white[0], white[-1] + 1):
            pixels[x, y] = 1
    for line, x0, dy in zip(BUBBLE_LINES, (16, 18), (-1, 13)):
        ink, width = _pixels(line)
        if x0 + width >= 57:
            raise AssertionError('Part 1 loader bubble text exceeds interior')
        # The native art uses dark brown ink with a light brown one-pixel edge.
        for x, y in ink:
            pixels[x0+x+1, y+dy+1] = 5
        for x, y in ink:
            pixels[x0+x, y+dy] = 13
    out = bytearray(len(native))
    for (x, y), value in pixels.items():
        tile = (x // 32) * 16 + (y // 8) * 4 + (x % 32) // 8
        off = tile*32 + (y % 8)*4 + (x % 8)//2
        out[off] |= value << (4 * (x % 2))
    return bytes(out)


def error_graphics(sheet, tmap, part):
    """Regenerate only text rows; preserve the native blank/decor tiles."""
    tile_count = len(sheet) // 32
    rows = len(tmap) // 64
    entries = list(struct.unpack(f'<{len(tmap)//2}H', tmap))
    text_rows = {8, 9, 11, 12}
    blank = 0 if part == 'p2' else 0x3F
    reserved = {blank} | {e & 1023 for i, e in enumerate(entries)
                          if i // 32 not in text_rows}
    pool = [sheet[i*32:(i+1)*32] if i in reserved else bytes(32)
            for i in range(tile_count)]
    free = [i for i in range(tile_count) if i not in reserved]
    lookup = {bytes(32): blank}
    for row in text_rows:
        for col in range(32):
            entries[row * 32 + col] = blank
    for line, top in zip(ERROR_LINES, (8, 11)):
        ink, width = _pixels(line)
        left = (256 - width) // 2
        cells = {}
        for x, y in ink:
            px = left + x
            key = (px // 8, y // 8)
            tile = cells.setdefault(key, bytearray(32))
            off = (y % 8) * 4 + (px % 8) // 2
            tile[off] |= 10 << (4 * (px % 2))
        for (col, half), raw in sorted(cells.items()):
            raw = bytes(raw)
            if raw not in lookup:
                if not free:
                    raise AssertionError(f'{part} error glyph pool overflow')
                lookup[raw] = free.pop(0)
                pool[lookup[raw]] = raw
            entries[(top + half) * 32 + col] = lookup[raw]
    return b''.join(pool), struct.pack(f'<{len(entries)}H', *entries)


def _source(original, spec):
    name, start, end, base, warn_off, first, count, err_off, map_off, refs = spec
    image = bytes(original[start:end])
    if (end - start) % 4 or image[:4] != bytes.fromhex('2e0000ea') or image[0xBD] != 0xF0:
        raise AssertionError(f'{name} MultiBoot bounds changed')
    if hashlib.sha256(image).hexdigest() != NATIVE_IMAGE_SHA[name]:
        raise AssertionError(f'{name} native MultiBoot source changed')
    outer, used = lz77_decompress(image, 0x2B0)
    if outer is None or used > len(image) - 0x2B0:
        raise AssertionError(f'{name} outer LZ77 invalid')
    expected = 0x3984 if name == 'p2' else 0x2508
    if len(outer) != expected:
        raise AssertionError(f'{name} stage-two size changed')
    if hashlib.sha256(outer).hexdigest() != NATIVE_STAGE2_SHA[name]:
        raise AssertionError(f'{name} native stage-two SHA changed')
    offsets = (warn_off, 0x308C if name == 'p2' else 0x10E0, err_off, map_off)
    # Literal order differs from stream order in Part 1.
    literals = ((offsets[1], refs[0]), (warn_off, refs[1]),
                (err_off, refs[2]), (map_off, refs[3]))
    if name == 'p2':
        literals = ((warn_off, refs[0]), (offsets[1], refs[1]),
                    (err_off, refs[2]), (map_off, refs[3]))
    for off, ref in literals:
        if struct.unpack_from('<I', outer, ref)[0] != base + off:
            raise AssertionError(f'{name} stage-two stream pointer changed {ref:x}')
    streams = {}
    for off in offsets:
        decoded, consumed = lz77_decompress(outer, off)
        if decoded is None:
            raise AssertionError(f'{name} nested stream invalid {off:x}')
        streams[off] = (decoded, consumed)
    return image, bytearray(outer), streams


def _patch_image(original, spec):
    name, start, end, _, warn_off, first, count, err_off, map_off, _ = spec
    image, stage, streams = _source(original, spec)
    warning, _ = streams[warn_off]
    warning = bytearray(warning)
    warning[first*32:(first+count)*32] = warning_tiles(count//2, name == 'p1')
    if name == 'p1':
        bubble = slice(0x58*32, 0x78*32)
        warning[bubble] = bubble_tiles(bytes(warning[bubble]))
    error_sheet, error_map = error_graphics(streams[err_off][0],
                                            streams[map_off][0], name)
    updated = {warn_off: bytes(warning), err_off: error_sheet,
               map_off: error_map}
    for off, decoded in updated.items():
        old, capacity = streams[off]
        if len(decoded) != len(old):
            raise AssertionError(f'{name} decoded stream size changed {off:x}')
        packed = lz77_compress_optimal(decoded, vram_safe=True)
        if len(packed) > capacity:
            raise AssertionError(f'{name} nested stream overflow {off:x}: {len(packed)} > {capacity}')
        stage[off:off+capacity] = packed + bytes(capacity-len(packed))
    outer = lz77_compress_optimal(bytes(stage), vram_safe=False)
    capacity = len(image)-0x2B0
    if len(outer) > capacity:
        raise AssertionError(f'{name} MultiBoot image overflow: {len(outer)} > {capacity}')
    out = bytearray(image)
    out[0x2B0:] = outer + bytes(capacity-len(outer))
    check, _ = lz77_decompress(out, 0x2B0)
    if check != bytes(stage):
        raise AssertionError(f'{name} outer round trip failed')
    return bytes(out)


def payload_failure_bytes(rom, original):
    """Use the already localized Part 2 result glyphs in campaign payloads."""
    from lz77_scan import lz77_decompress
    main = lz77_decompress(rom, 0x45EC74)
    if main is None or len(main[0]) != 9216:
        raise AssertionError('main Part 2 result overlay missing')
    korean = main[0][16*512:18*512]
    for index, digest in enumerate(FAILURE_CELL_SHA):
        if hashlib.sha256(korean[index*512:(index+1)*512]).hexdigest() != digest:
            raise AssertionError('main Part 2 failure glyph changed')
    for off in PAYLOAD_FAILURE_COPIES:
        native = lz77_decompress(original, off)
        if (native is None or len(native[0]) != 1024 or native[1] != 675 or
                hashlib.sha256(native[0]).hexdigest() != PAYLOAD_FAILURE_NATIVE_SHA):
            raise AssertionError(f'payload failure source changed {off:x}')
    packed = lz77_compress_optimal(korean, vram_safe=True)
    if len(packed) > 675:
        raise AssertionError(f'payload failure graphic overflow: {len(packed)} > 675')
    return packed + bytes(675-len(packed))


@lru_cache(maxsize=1)
def expected_images(original_bytes):
    return tuple(_patch_image(original_bytes, spec) for spec in IMAGES)


def patch(rom, original):
    expected = expected_images(bytes(original))
    failure = payload_failure_bytes(rom, original)
    for spec, data in zip(IMAGES, expected):
        name, start, end = spec[:3]
        if bytes(rom[start:end]) != bytes(original[start:end]):
            raise AssertionError(f'{name} bootstrap already modified')
        rom[start:end] = data
    for off in PAYLOAD_FAILURE_COPIES:
        if bytes(rom[off:off+675]) != bytes(original[off:off+675]):
            raise AssertionError(f'payload failure graphic already modified {off:x}')
        rom[off:off+675] = failure
    return {**{spec[0]: hashlib.sha256(data).hexdigest()
               for spec, data in zip(IMAGES, expected)},
            'payload_failure': hashlib.sha256(failure).hexdigest()}


def verify(rom, original):
    for spec, expected in zip(IMAGES, expected_images(bytes(original))):
        _, start, end = spec[:3]
        if bytes(rom[start:end]) != expected:
            raise AssertionError(f'{spec[0]} final bootstrap changed')
    failure = payload_failure_bytes(rom, original)
    for off in PAYLOAD_FAILURE_COPIES:
        if bytes(rom[off:off+675]) != failure:
            raise AssertionError(f'payload failure final graphic changed {off:x}')
