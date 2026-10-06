"""Link-cable (communication) error bitmaps, Part 1 and Part 2.

Static RE (2026-10-06, fixG):
* Part 1 0xB30564 decompresses glyph sheet 0xC2A040 (LZ77, 3072 B = 96 BG
  tiles) to 0x06000000 and tilemap 0xC2A3A4 (LZ77, 2048 B = 32x32 entries) to
  0x06007000; palette 0xC2A54C.  The sheet is a de-duplicated 8x16 glyph pool
  (通信エラーです本体の電源とケブル / 接続を確かめてください、やりなお / し切。)
  and the tilemap composes three centred lines (rows 6-7, 9-10, 11-12):
    通信エラーです / 本体電源を切り、通信ケーブルの / 接続を確かめて やりなおしてください。
  Fill entry 0x04F (blank tile).  Pointerless byte-identical archive copies of
  the sheet+tilemap pair: 0x930B30/0x930E94, 0x9697B8/0x969B1C,
  0x9A205C/0x9A23C0, 0x9DA900/0x9DAC64, 0xEE9730/0xEE9A94.
* Part 2 asset table 0x816E04/0x816E08: sheet 0x4CA41C (2176 B = 68 tiles,
  tile 0 blank = fill) + tilemap 0x4CA718 (1280 B = 32x20), same message.
* Part 2 0x5481E4 (ptr 0x332A88): plain 216x16 strip (27x2 tiles, 2D rows)
  スイッチを切ったり、ケーブルを抜いたりしないでください。

Rebuild: each line is rendered with Galmuri11-Condensed (8 px cells, 11 px
tall, like the native 8x16 kana/kanji at rows 3..13), ink index 10 (native ink;
native AA 4/14 is not used), centred on the native line centre (pixel 124);
tiles are de-duplicated into the pool (blank -> native fill tile) and the
tilemap is regenerated.  Everything is recompressed in place.
Korean wording: 통신 오류 = existing 接続エラー -> 접속 오류 (0x00A34F2C);
케이블 / 전원을 끄- = existing 0x00A35258, 0x00A34BEA.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
INK = 10
FONT = ROOT / 'reference/fonts/Galmuri11-Condensed.bdf'

# Shortest natural wording that fits Part 2's 68-tile pool (66 tiles + blank); used
# for both parts for consistency (本体/です are dropped).
ERROR_LINES = ('통신 오류', '전원을 끄고 케이블 연결을', '확인한 뒤 다시 시도해 주세요.')
LINE_ROWS = (6, 9, 11)          # native first tile row of each 16 px line
LINE_CENTRE = 124               # native lines are centred on pixel 124
TEXT_TOP = 3                    # native glyph ink starts at row 3 of the cell

STRIP_TEXT = '스위치를 끄거나 케이블을 뽑지 마세요.'

# name, sheet, sheet capacity, sheet size, sheet sha, map, map capacity, map size, map sha,
# map rows, blank tile, pointers, pointerless (sheet, map) copies
SCREENS = (
    ('part1', 0xC2A040, 866, 3072,
     None,  # native SHA guards: NATIVE_SHA256
     0xC2A3A4, 390, 2048, None, 32, 0x4F, (0xB305E4, 0xB305E8),
     ((0x930B30, 0x930E94), (0x9697B8, 0x969B1C), (0x9A205C, 0x9A23C0),
      (0x9DA900, 0x9DAC64), (0xEE9730, 0xEE9A94))),
    ('part2', 0x4CA41C, 761, 2176, None,
     0x4CA718, 296, 1280, None, 20, 0x00, (0x816E04, 0x816E08), ()),
)
STRIP = (0x5481E4, 561, 1728, None, 0x332A88, 27)  # source, capacity, size, sha, pointer, columns


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(FONT))
    return font


def line_mask(text):
    """[(x, y)] ink pixels with top-of-cell y, plus total width."""
    font = _font()
    ink, cursor = [], 0
    for char in text:
        if char == ' ':
            cursor += 4
            continue
        grid, width, height, xoffset, yoffset = glyph_grid(font[ord(char)])
        top = 11 - (yoffset + height)
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.append((cursor + xoffset + x, TEXT_TOP + top + y))
        cursor += xoffset + width + 1
    return ink, cursor - 1


def _put(tile, x, y, value):
    tile[y * 4 + x // 2] |= value << (4 * (x % 2))


def build_screen(screen):
    """(sheet bytes, tilemap bytes) for a pool+tilemap error screen."""
    _, _, _, sheet_size, _, _, _, map_size, _, rows, blank, _, _ = screen
    tiles = sheet_size // 32
    pool = [bytes(32)] * tiles
    index = {bytes(32): blank}
    free = [i for i in range(tiles) if i != blank]
    entries = [blank] * (map_size // 2)
    for text, row in zip(ERROR_LINES, LINE_ROWS):
        ink, width = line_mask(text)
        x0 = LINE_CENTRE - (width + 1) // 2
        cells = {}
        for x, y in ink:
            px = x0 + x
            if not 0 <= px < 240:
                raise AssertionError(f'link error line exceeds screen: {text}')
            key = (px // 8, y // 8)
            cells.setdefault(key, bytearray(32))
            _put(cells[key], px % 8, y % 8, INK)
        for (col, half), raw in sorted(cells.items()):
            raw = bytes(raw)
            if raw not in index:
                if not free:
                    raise AssertionError('link error glyph pool overflow')
                index[raw] = free.pop(0)
                pool[index[raw]] = raw
            if row + half >= rows:
                raise AssertionError('link error line exceeds tilemap')
            entries[(row + half) * 32 + col] = index[raw]
    return b''.join(pool), struct.pack(f'<{len(entries)}H', *entries)


def build_strip():
    _, _, size, _, _, columns = STRIP
    raw = bytearray(size)
    ink, width = line_mask(STRIP_TEXT)
    x0 = (columns * 8 - width) // 2
    for x, y in ink:
        px = x0 + x
        if not 0 <= px < columns * 8:
            raise AssertionError('link warning strip overflow')
        tile = (y // 8) * columns + px // 8
        raw[tile * 32 + (y % 8) * 4 + (px % 8) // 2] |= INK << (4 * (px % 2))
    return bytes(raw)


def _blocks():
    """[(offset, capacity, decoded size, pointer or None, builder key)]."""
    out = []
    for screen in SCREENS:
        name, sheet, sheet_cap, sheet_size, _, tmap, map_cap, map_size = screen[:8]
        pointers, copies = screen[11], screen[12]
        out.append((sheet, sheet_cap, sheet_size, pointers[0], (name, 0)))
        out.append((tmap, map_cap, map_size, pointers[1], (name, 1)))
        for copy_sheet, copy_map in copies:
            out.append((copy_sheet, sheet_cap, sheet_size, None, (name, 0)))
            out.append((copy_map, map_cap, map_size, None, (name, 1)))
    out.append((STRIP[0], STRIP[1], STRIP[2], STRIP[4], ('strip', 0)))
    return tuple(out)


@lru_cache(maxsize=1)
def generated():
    result = {('strip', 0): build_strip()}
    for screen in SCREENS:
        sheet, tmap = build_screen(screen)
        result[(screen[0], 0)] = sheet
        result[(screen[0], 1)] = tmap
    return result


def source_guard(original):
    natives = {}
    for offset, capacity, size, pointer, key in _blocks():
        decoded = lz77_decompress(original, offset)
        if decoded is None or decoded[1] != capacity or len(decoded[0]) != size:
            raise AssertionError(f'link error source/allocation changed {offset:06X}')
        if natives.setdefault(key, decoded[0]) != decoded[0]:
            raise AssertionError(f'link error copy differs {offset:06X}')
        if bytes(original[offset + capacity:(offset + capacity + 3) & ~3]).strip(b'\0'):
            raise AssertionError(f'link error allocation padding changed {offset:06X}')
        refs = original.count(struct.pack('<I', offset + ROM_BASE))
        if refs != (1 if pointer is not None else 0):
            raise AssertionError(f'link error foreign reference {offset:06X}')
        if pointer is not None and struct.unpack_from('<I', original, pointer)[0] != offset + ROM_BASE:
            raise AssertionError(f'link error pointer changed {pointer:06X}')
    for key, digest in NATIVE_SHA256.items():
        if hashlib.sha256(natives[key]).hexdigest() != digest:
            raise AssertionError(f'link error native data changed {key}')


NATIVE_SHA256 = {
    ('part1', 0): '77320400807bde1da800b72f7dd16d10bb9701087bcced16b980b126e3a66d41',
    ('part1', 1): '4fbcb0ddd7d83145ab2a07f8e56d2f593d7b37536724b2ff5132812b9c461ed3',
    ('part2', 0): '73e710aeb77d568f414352d9a48b4d07c93c6306662a5d5d853d30bdeef8565b',
    ('part2', 1): '4952222c799e6fee9adc91b237140925a4fcfcf12f959881228c45164853376e',
    ('strip', 0): '594a518e1e3950d33a0c1935904e5579c4b9e94f3d57be355c51d09df19e1eba',
}


@lru_cache(maxsize=None)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions():
    regions = []
    data = generated()
    for offset, capacity, _, _, key in _blocks():
        stream = _stream(data[key])
        if len(stream) > capacity:
            raise AssertionError(f'link error LZ77 overflow {offset:06X}: {len(stream)} > {capacity}')
        regions.append((offset, stream + bytes(capacity - len(stream))))
    return regions


def patch(rom, original):
    source_guard(original)
    regions = expected_regions()
    for offset, new in regions:
        if bytes(rom[offset:offset + len(new)]) != bytes(original[offset:offset + len(new)]):
            raise AssertionError(f'link error {offset:06X} already modified by another writer')
    for *_, pointer, _ in _blocks():
        if pointer is not None and bytes(rom[pointer:pointer + 4]) != bytes(original[pointer:pointer + 4]):
            raise AssertionError(f'link error pointer repointed {pointer:06X}')
    for offset, new in regions:
        rom[offset:offset + len(new)] = new
    data = generated()
    for offset, _, _, _, key in _blocks():
        decoded = lz77_decompress(rom, offset)
        if decoded is None or decoded[0] != data[key]:
            raise AssertionError(f'link error round trip failed {offset:06X}')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    regions = []
    for offset, capacity, size, pointer, _ in _blocks():
        decoded = lz77_decompress(rom, offset)
        if decoded is None or len(decoded[0]) != size or decoded[1] > capacity:
            raise AssertionError(f'link error final allocation changed {offset:06X}')
        verify_vram_stream(bytes(rom[offset:offset + capacity]), size, 'link error bitmap')
        regions.append((offset, bytes(rom[offset:offset + capacity])))
        if pointer is not None:
            if bytes(rom[pointer:pointer + 4]) != bytes(original[pointer:pointer + 4]):
                raise AssertionError(f'link error final pointer changed {pointer:06X}')
            regions.append((pointer, bytes(rom[pointer:pointer + 4])))
    return tuple(regions)


def expected_region_addresses():
    out = []
    for offset, _, _, pointer, _ in _blocks():
        out.append(offset)
        if pointer is not None:
            out.append(pointer)
    return tuple(out)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('link error snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'link error bitmap overwritten after editor at {address:06X}')


def generated_matches(rom):
    data = generated()
    for offset, _, _, _, key in _blocks():
        decoded = lz77_decompress(rom, offset)
        if decoded is None or decoded[0] != data[key]:
            return False
    return True
