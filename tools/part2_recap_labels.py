"""Part 2 ending mission-recap card labels: 作戦日数 -> 작전 일수, 日 -> 일.

Static RE (2026-10-08, effc6ee8 savestate run19/0378 + original ROM):
LZ77 0x5072AC (1920 B, consumed 783, single pointer 0x36C2F8) is the OBJ sheet
of the recap card. 1D tiles 0-7 / 8-15 are two 32x16 OBJs drawn edge to edge
(OAM x=58 and x=90, y=54) holding 作戦日数; tiles 16-19 are the 16x16 日 unit
after the day count (OAM x=178); tiles 20-59 are the digits 0-9 (16x16 each)
and stay native. The labels are 12 px small text, so they use Galmuri11-Bold
(2026-10-08 font rule: <= 16 px drawn text is Galmuri): white fill 6 with a
gray 10 drop shadow, on OBJ palette 0 like the native art.
"""
import hashlib
import struct
from pathlib import Path

from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
SOURCE, POINTER, CAPACITY, SIZE = 0x5072AC, 0x36C2F8, 783, 1920
SOURCE_SHA256 = '1f8ebd65b1e03b0e9ee5019ed6895a9095f28dfcdfeab034ae95f60d6d225f62'
FONT = ROOT / 'reference/fonts/Galmuri11-Bold.ttf'
FILL, SHADOW = 6, 10
LABEL, UNIT = '작전 일수', '일'


def source_guard(original):
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256
            or struct.unpack_from('<I', original, POINTER)[0] != SOURCE + 0x08000000
            or original.count(struct.pack('<I', SOURCE + 0x08000000)) != 1):
        raise AssertionError('Part 2 recap label sheet source/pointer changed')
    return decoded[0]


def _grid(text, width, height):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT), 12)
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    box = probe.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0] + 1, box[3] - box[1] + 1    # +1 for the shadow
    if w > width - 2 or h > height - 2:
        raise AssertionError(f'recap label does not fit {width}x{height}: {text}')
    x, y = (width - w) // 2 - box[0], (height - h) // 2 - box[1]
    mask = Image.new('L', (width, height), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=font, fill=255)
    m = mask.load()
    grid = [[0] * width for _ in range(height)]
    for yy in range(height):
        for xx in range(width):
            if m[xx, yy] >= 128:
                if yy + 1 < height and xx + 1 < width:
                    grid[yy + 1][xx + 1] = grid[yy + 1][xx + 1] or SHADOW
    for yy in range(height):
        for xx in range(width):
            if m[xx, yy] >= 128:
                grid[yy][xx] = FILL
    return grid


def _pack(grid, cells, cell_w, cell_h):
    out = bytearray(cells * cell_w * cell_h * 32)
    for cell in range(cells):
        for t in range(cell_w * cell_h):
            for y in range(8):
                for x in range(8):
                    value = grid[(t // cell_w) * 8 + y][cell * cell_w * 8 + (t % cell_w) * 8 + x]
                    out[(cell * cell_w * cell_h + t) * 32 + y * 4 + x // 2] |= value << (4 * (x % 2))
    return bytes(out)


def render(original):
    import aw_fonts
    native = source_guard(original)
    data = bytearray(native)
    label = _grid(LABEL, 64, 16)
    # Native 作戦日数 crosses the x=32 OBJ edge: the two cells are drawn edge to edge.
    aw_fonts.check_cells(label, (32,), 'Part 2 recap label', native=aw_fonts.obj_canvas(native, 2, 4, 2, 0))
    data[0:16 * 32] = _pack(label, 2, 4, 2)
    data[16 * 32:20 * 32] = _pack(_grid(UNIT, 16, 16), 1, 2, 2)
    return bytes(data)


def expected_region(original):
    stream = lz77_compress_optimal(render(original), vram_safe=True)
    if len(stream) > CAPACITY:
        raise AssertionError(f'Part 2 recap label sheet overflow: {len(stream)} > {CAPACITY}')
    return stream + bytes(CAPACITY - len(stream))


def patch(rom, original):
    region = expected_region(original)
    if bytes(rom[SOURCE:SOURCE + CAPACITY]) != bytes(original[SOURCE:SOURCE + CAPACITY]):
        raise AssertionError('Part 2 recap label sheet already modified by another writer')
    rom[SOURCE:SOURCE + CAPACITY] = region
    if lz77_decompress(rom, SOURCE)[0] != render(original):
        raise AssertionError('Part 2 recap label sheet round trip failed')
    return 1


def verify(rom, original):
    if bytes(rom[SOURCE:SOURCE + CAPACITY]) != expected_region(original):
        raise AssertionError('Part 2 recap label sheet changed after its writer')
