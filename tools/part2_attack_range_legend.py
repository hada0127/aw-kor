"""Part 2 unit-stat legend popup, raw OBJ family 2 native ID 146 (128x64).

Consumer (static RE, original ROM, 2026-10-06 fixH):
- Family loader 0x0831F708 (r0 = native id) is called with r0 = 0x92 only at
  0x08385736/0x08385738, inside the screen init 0x08385550 that also loads
  IDs 0x93..0xA7 (move/range icons, -1..+3 modifiers, attack bars), 0x67
  (the "R:INFO" prompt), 0x43/0x44/0x50.
- Sprite placer 0x0831F820 is called with r0 = 0x92 only by the three task
  callbacks of script 0x08A3BD94: 0x08386570 (slide in from x=240 to 56,
  y=56), 0x08386614 (hold at 56,56 until A/B/R, keys mask 0x103) and
  0x083865C0 (slide out).  The script pointer is kept in the ROM slot
  0x0854EF14 (= 0x08A3BD8C), read by the same screen's input handler
  0x0838579C: at 0x08385A90 it checks the R key (0x100), field +0x4E == 0 and
  page variable [0x03005AC8] == 4, plays sound 0x76 and starts the script
  (0x0831CDC8).  So the panel is reachable: page 4 of that screen, press R.
  No savestate shows it in OAM (13,371 Part 2 states hold the tiles in VRAM,
  only as hidden OAM y=160), so the on-screen result is unverified.
- Layout: 16x8 tiles = two 64x64 1D OBJ halves (tiles 0..63 left, 64..127
  right).  Ink 15 (black, 7/14 AA) on white 1 with a gray underline band 8.

Japanese -> Korean (Galmuri11-Condensed 7x11, the dialogue font; ink 15):
  攻撃力がアップしています -> 공격력이 올라 있습니다  (攻撃力がアップ = 0x00DF345D
                              공격력이 올라가는)
  ふつうの攻撃力です       -> 보통 공격력입니다
  攻撃力がダウンしています -> 공격력이 떨어져 있습니다
  移動力 -> 이동력 (0x00A0306D)   射程 -> 사정거리 (0x00A0B655, 0x00A14D1E)
The second icon + dash of the last row move 4 px left so 사정거리 fits.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'reference/fonts/Galmuri11-Condensed.bdf'
FAMILY_TABLE, SIZE_TABLE, FAMILY, NATIVE_ID = 0x807178, 0x8071C0, 2, 146
OFFSET, TILES = 0x458BF4, 128
SOURCE_SHA256 = '160fd47370e874fb440f0e56a2a8475e659421f64d5d42f53344794179d48582'
WIDTH, HEIGHT = 128, 64
INK, OLD_INK = 15, (15, 7, 14)
TEXT_X0, TEXT_X1 = 33, 125            # clear span (inclusive / exclusive)
SPACE = 2
# (Korean, glyph top row, clear rows)
LINES = (('공격력이 올라 있습니다', 2, range(1, 15)),
         ('보통 공격력입니다', 17, range(16, 30)),
         ('공격력이 떨어져 있습니다', 32, range(31, 45)))
ROW4_TOP, ROW4_CLEAR = 48, range(47, 60)
ROW4_LEFT = ('이동력', 34)
ROW4_RIGHT = ('사정거리', 94)
MOVE_BLOCK, MOVE_BY = (70, 96), 4      # icon 2 + dash 2 columns, shifted left


def source_guard(original):
    base, _, start = struct.unpack_from('<III', original, FAMILY_TABLE + FAMILY * 12)
    end = struct.unpack_from('<III', original, FAMILY_TABLE + (FAMILY + 1) * 12)[2]
    if (base, start, end) != (0x08456114, 67, 170):
        raise AssertionError('Part 2 OBJ family 2 table changed')
    address = base - 0x08000000
    for native_id in range(start, NATIVE_ID):
        w, h = struct.unpack_from('<BB', original, SIZE_TABLE + native_id * 4)
        address += w * h * 32
    w, h = struct.unpack_from('<BB', original, SIZE_TABLE + NATIVE_ID * 4)
    if (address, w, h) != (OFFSET, 16, 8):
        raise AssertionError('attack legend extent changed')
    raw = bytes(original[OFFSET:OFFSET + TILES * 32])
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256 or original.count(raw) != 1:
        raise AssertionError('attack legend source changed')
    return raw


def _index(x, y):
    tile = (x // 64) * 64 + (y // 8) * 8 + (x % 64) // 8
    return tile * 32 + (y % 8) * 4 + (x % 8) // 2


def decode(raw):
    return [[(raw[_index(x, y)] >> (4 * (x % 2))) & 15 for x in range(WIDTH)] for y in range(HEIGHT)]


def encode(pixels):
    raw = bytearray(TILES * 32)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            raw[_index(x, y)] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(FONT))[0]


def _ink(text):
    points, cursor = set(), 0
    for char in text:
        if char == ' ':
            cursor += SPACE
            continue
        grid, w, h, xo, yo = glyph_grid(_font()[ord(char)])
        top = 11 - h - yo
        for gy in range(h):
            for gx in range(w):
                if grid[gy][gx]:
                    points.add((cursor + gx + xo, top + gy))
        cursor += w + 1
    return points, cursor - 1


def _clear(pixels, rows):
    for y in rows:
        span = [pixels[y][x] for x in range(TEXT_X0, TEXT_X1) if pixels[y][x] not in OLD_INK]
        background = max(set(span), key=span.count)
        for x in range(TEXT_X0, TEXT_X1):
            if pixels[y][x] in OLD_INK:
                pixels[y][x] = background


def _draw(pixels, text, left, top, x_limit=TEXT_X1):
    points, width = _ink(text)
    if left + width > x_limit:
        raise AssertionError(f'attack legend text too wide: {text}')
    for x, y in points:
        pixels[top + y][left + x] = INK


def render(original):
    pixels = decode(source_guard(original))
    for text, top, rows in LINES:
        _clear(pixels, rows)
        _draw(pixels, text, 34, top)
    # last row: keep icon 1 + dash 1 (left of the clear span), move icon 2 +
    # dash 2 left by MOVE_BY, redraw both texts
    x0, x1 = MOVE_BLOCK
    block = [row[x0:x1] for row in pixels[ROW4_CLEAR.start:ROW4_CLEAR.stop]]
    _clear(pixels, ROW4_CLEAR)
    for i, y in enumerate(ROW4_CLEAR):
        pixels[y][x0 - MOVE_BY:x1 - MOVE_BY] = block[i]
    _draw(pixels, ROW4_LEFT[0], ROW4_LEFT[1], ROW4_TOP, x0 - MOVE_BY)
    _draw(pixels, ROW4_RIGHT[0], ROW4_RIGHT[1], ROW4_TOP)
    return encode(pixels)


def expected_regions(original):
    return ((OFFSET, render(original)),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError('attack legend modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    return len(regions)


def capture(rom, original):
    source_guard(original)
    return ((OFFSET, bytes(rom[OFFSET:OFFSET + TILES * 32])),)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != (OFFSET,):
        raise AssertionError('attack legend snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError('attack legend overwritten after editor')


def generated_matches(rom, original):
    return bytes(rom[OFFSET:OFFSET + TILES * 32]) == render(original)


def preview(raw):
    from PIL import Image
    pal = {0: (90, 40, 40), 1: (248, 248, 248), 8: (176, 176, 176), 15: (0, 0, 0)}
    image = Image.new('RGB', (WIDTH, HEIGHT))
    for y, row in enumerate(decode(raw)):
        for x, v in enumerate(row):
            image.putpixel((x, y), pal.get(v, (255 - 14 * v, 160, 255 - 14 * v)))
    return image
