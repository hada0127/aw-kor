"""Part 2 CO "SPECIAL BREAK" banner (BG) -> 스페셜 / 브레이크.

Static RE (original ROM, 2026-10-06 fixH):
- 0x08380D4C loads LZ77 0x5B00D8 (8192 B = 256 tiles, consumed 2266, single
  literal 0x380DC4) to BG char base + 0x20 (tile 1), LZ77 tilemap 0x5AFE60
  (32x32, literal 0x380DCC) to 0x0200FB40, then adds 0x9001 to every entry
  (0x08312B14: palette 9, tile + 1).  Palette 0x5B09B4 (16 colours) is copied
  to BG colour 144 (bank 9): 1 red, 3/4 light/mid AA, 5 dark red, 6 white.
- Map rows 0-1 / 14-15 = decoded tile 0x16 (solid red), rows 2-13 = tile 0x36
  (solid white band), rows 16-31 = tile 0x8E (transparent).  Line 1 SPECIAL
  sits at map rows 4-7, cols 2-24 (decoded tiles 0x00-0x15/0x20-0x35/0x40-0x56/
  0x60-0x76); line 2 BREAK at rows 8-11, cols 5-27 (0x17-0x1F + 0x80-0x8D per
  tile row).  Letters are hollow: interior index 0 (transparent), outline 5
  with 4/3 anti-aliasing, on the white plate 6.

The Korean term is 스페셜 브레이크 (translation_for_import 0x00A2DEB2 「스페셜
브레이크」, 0x00A2E619).  Each line is redrawn in the native hollow style:
Galmuri11-Bold at its native 12 px, scaled 2x (pixel crisp), body = index 0,
2 px outline 5 + one 4-neighbour AA ring 4, centred in its line rectangle.
Only tiles referenced exclusively by the line cells are rewritten; the shared
fill tiles 0x16/0x36/0x8E and the tilemap stay untouched.  On-screen result is
unverified (no savestate of the banner).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SOURCE, SOURCE_POINTER = 0x5B00D8, 0x380DC4
CAPACITY, FOLLOWING = 2266, 0x5B09B4   # 0x5B09B2..0x5B09B3 padding kept
SIZE = 8192
SOURCE_SHA256 = 'dd1c70329b94d57369f3d323c970f5bd986c99539ec783385650b8bf2f3511b7'
TILEMAP, TILEMAP_POINTER = 0x5AFE60, 0x380DCC
TILEMAP_SHA256 = '3a443722916cc464d42c3bdcaefa14140ae85ad4ff54dbdd39188a5b36c3e971'
SHARED_TILES = (0x16, 0x36, 0x8E)
PLATE, OUTLINE, AA = 6, 5, 4
# (Korean, map row0, map col0, map col1 exclusive)
LINES = (('스페셜', 4, 2, 25), ('브레이크', 8, 5, 28))
FONT = ROOT / 'reference/fonts/Galmuri11-Bold.ttf'
GAP = 4


def _u32(rom, address):
    return struct.unpack_from('<I', rom, address)[0]


def _tilemap(original):
    data = lz77_decompress(original, TILEMAP)
    if data is None or hashlib.sha256(data[0]).hexdigest() != TILEMAP_SHA256:
        raise AssertionError('special break tilemap changed')
    return [struct.unpack_from('<H', data[0], 2 * i)[0] for i in range(1024)]


def source_guard(original):
    for pointer, target in ((SOURCE_POINTER, SOURCE), (TILEMAP_POINTER, TILEMAP)):
        if _u32(original, pointer) != target + ROM_BASE:
            raise AssertionError(f'special break pointer changed {pointer:06X}')
        if original.count(struct.pack('<I', target + ROM_BASE)) != 1:
            raise AssertionError(f'special break block has foreign reference {target:06X}')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('special break sheet source changed')
    return decoded[0], _tilemap(original)


def line_cells(entries, row0, col0, col1):
    """{(cx, cy): tile} for the exclusive cells of a 4-row line rectangle."""
    use = {}
    for entry in entries:
        use[entry & 0x3FF] = use.get(entry & 0x3FF, 0) + 1
    cells = {}
    for cy in range(4):
        for cx in range(col1 - col0):
            entry = entries[(row0 + cy) * 32 + col0 + cx]
            tile = entry & 0x3FF
            if tile in SHARED_TILES:
                continue
            if entry & 0x0C00 or use[tile] != 1:
                raise AssertionError(f'special break cell not exclusive: tile {tile:#x}')
            cells[(cx, cy)] = tile
    return cells


@lru_cache(maxsize=None)
def glyph_mask(char):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT), 12)
    image = Image.new('L', (16, 16), 0)
    ImageDraw.Draw(image).text((0, 0), char, font=font, fill=255)
    box = image.getbbox()
    if box is None:
        raise AssertionError(f'special break glyph missing: {char}')
    x0, y0, x1, y1 = box
    small = {(x - x0, y - y0) for y in range(y0, y1) for x in range(x0, x1) if image.getpixel((x, y)) >= 128}
    return (frozenset((2 * x + dx, 2 * y + dy) for x, y in small for dx in (0, 1) for dy in (0, 1)),
            2 * (x1 - x0), 2 * (y1 - y0))


def render_line(text, width, allowed):
    """width x 32 pixel rows (None = keep native) for one hollow-letter line."""
    glyphs = [glyph_mask(c) for c in text]
    total = sum(w for _, w, _ in glyphs) + GAP * (len(glyphs) - 1)
    height = max(h for _, _, h in glyphs)
    left, top = (width - total) // 2, (32 - height) // 2
    body = set()
    for mask, w, h in glyphs:
        body |= {(x + left, y + top + (height - h)) for x, y in mask}
        left += w + GAP
    near8 = lambda p: [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    near4 = lambda p: [(p[0] + dx, p[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    ring1 = {q for p in body for q in near8(p)} - body
    ring2 = {q for p in ring1 for q in near8(p)} - body - ring1
    ring3 = {q for p in ring2 for q in near4(p)} - body - ring1 - ring2
    pixels = [[PLATE] * width for _ in range(32)]
    for points, value in ((ring3, AA), (ring2, OUTLINE), (ring1, OUTLINE), (body, 0)):
        for x, y in points:
            if not (0 <= x < width and 0 <= y < 32) or (x // 8, y // 8) not in allowed:
                raise AssertionError(f'special break glyph clipped: {text}')
            pixels[y][x] = value
    return pixels


def sheet(original):
    native, entries = source_guard(original)
    out = bytearray(native)
    for text, row0, col0, col1 in LINES:
        cells = line_cells(entries, row0, col0, col1)
        pixels = render_line(text, (col1 - col0) * 8, set(cells))
        for (cx, cy), tile in cells.items():
            raw = bytearray(32)
            for y in range(8):
                for x in range(8):
                    raw[y * 4 + x // 2] |= pixels[cy * 8 + y][cx * 8 + x] << (4 * (x % 2))
            out[tile * 32:tile * 32 + 32] = raw
    return bytes(out)


@lru_cache(maxsize=2)
def _stream(sheet_bytes):
    return lz77_compress_optimal(sheet_bytes, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'special break sheet overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((SOURCE_POINTER, bytes(original[SOURCE_POINTER:SOURCE_POINTER + 4])),
            (TILEMAP_POINTER, bytes(original[TILEMAP_POINTER:TILEMAP_POINTER + 4])),
            (SOURCE + CAPACITY, bytes(original[SOURCE + CAPACITY:FOLLOWING])))


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'special break pointer/padding changed {address:06X}')
    if lz77_decompress(rom, TILEMAP) != lz77_decompress(original, TILEMAP):
        raise AssertionError('special break tilemap modified by another writer')
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'special break {address:06X} already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('special break sheet round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'special break final pointer/padding changed {address:06X}')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('special break final sheet invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'special break sheet')
    return ((SOURCE, bytes(rom[SOURCE:SOURCE + CAPACITY])),) + _fixed(original)


def expected_region_addresses():
    return (SOURCE, SOURCE_POINTER, TILEMAP_POINTER, SOURCE + CAPACITY)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('special break snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'special break overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)


PALETTE = 0x5B09B4


def preview(rom, original):
    """Static BG composition (PIL RGB 256x128, map rows 0..15) from ROM data."""
    from PIL import Image
    data = lz77_decompress(rom, SOURCE)[0]
    entries = _tilemap(original)
    pal = []
    for i in range(16):
        c = struct.unpack_from('<H', rom, PALETTE + 2 * i)[0]
        pal.append(((c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8))
    image = Image.new('RGB', (256, 128), (40, 60, 120))  # stand-in for the layer below
    for cell in range(32 * 16):
        entry = entries[cell]
        tile, hflip, vflip = entry & 0x3FF, entry & 0x400, entry & 0x800
        for y in range(8):
            for x in range(8):
                sx, sy = (7 - x if hflip else x), (7 - y if vflip else y)
                v = (data[tile * 32 + sy * 4 + sx // 2] >> (4 * (sx % 2))) & 15
                if v:
                    image.putpixel(((cell % 32) * 8 + x, (cell // 32) * 8 + y), pal[v])
    return image
