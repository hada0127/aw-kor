"""Part 1 CO profile / comment OBJ captions in the raw atlas 0xBE743C.

Atlas metadata 0xD8D504 (8 bytes/entry: u16 tile, u8 w, u8 h, palette...) is
consumed by 0xB304A8 (copy BE743C + tile*32, w*h*32 bytes to OBJ VRAM; 1D).
Entries and direct immediate loaders (original ROM):
  89 リク / 90 ソラ / 91 ウミ (16x16 terrain badges) + 92/93 stars, loaded at
     0xB46446..0xB4647A together with entry 65 COMMENT  -> CO comment screen
  94 スキ / 95 キライ / 96 ノウリョク / 97 ブレイク (32x16), loaded at
     0xB413E0..0xB41414 together with entry 62 SHOGUN PROFILE -> CO profile
VRAM evidence: entries 89..91 sit at OBJ tile 451/455/459 in Part 1 battle
states (e.g. output/qa/part1_2026-10-01/round32_recovery/0371_RIGHT_0078506.ss0)
but no sampled OAM shows them; the profile screen itself was not captured
(display unverified).

Korean (Galmuri7, the native 7px class): 陸/空/海 -> 육 / 공 / 해 (one
syllable: the 16x16 badge has a 12px caption; same terms as
part1_unit_type_labels 육상/공중/해상), スキ/キライ -> 좋아 / 싫어,
ノウリョク -> 능력, ブレイク -> 브레이크 (project term, translation_for_import
"ブレイク => 브레이크").  브레이크 is 30px wide, so its black caption band
is widened from 25px to the full 32px OBJ width.  Raw bytes, in place.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'reference/fonts/Galmuri7.bdf'
ATLAS, META = 0xBE743C, 0xD8D504
META_SPAN = (0xD8D7CC, bytes.fromhex(
    'ee01020203000000f201020203000000f601020203000000fa01010104000000'
    'fb01010104000000fc0104020300000004020402030000000c02040204000000'))
WHITE, BLACK, SHADE = 1, 5, 3
# (entry, w, h, original sha256, Korean, style)
LABELS = (
    (89, 2, 2, '77c143e994c821d6e993660975827b98399f91647e4d7b26decfaefbb67c866c', '육', 'badge'),
    (90, 2, 2, '2d32519b246020acdf504cbb5f3a47c989578999663cfd868459a2bb61809dd4', '공', 'badge'),
    (91, 2, 2, '981c38004bc85bf1ee2af5c55bc702f523925690ee2ca51e506d7c372b17060b', '해', 'badge'),
    (94, 4, 2, 'd4b344adb6728d11bc89fd024fd1e6686867cee0a3a69aaa80f224902dfd43b3', '좋아', 'plate'),
    (95, 4, 2, '5f4018d7ab0a35d7d73a38184294642a704cf625f4806db068f27a5f459699e7', '싫어', 'plate'),
    (96, 4, 2, '6ab634e22e0f1e36eaf43ed37a32a8af83a33b24338f567b344f323e89ce1481', '능력', 'band'),
    (97, 4, 2, '4254d9bd4cd8fb8928a565730a0aa9f7d521c136f2ed683e7294ce330725e24f', '브레이크', 'band'),
)


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(FONT))[0]


def _ink(text):
    ink, cursor = set(), 0
    for char in text:
        grid, width, height, xoffset, yoffset = glyph_grid(_font()[ord(char)])
        top = 7 - height - yoffset
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add((cursor + x + xoffset, top + y))
        cursor += width + 1
    return ink, cursor - 1


def entry_span(original, entry):
    tile, w, h = struct.unpack_from('<HBB', original, META + entry * 8)
    return ATLAS + tile * 32, w, h


def source_guard(original):
    start, raw = META_SPAN
    if bytes(original[start:start + len(raw)]) != raw:
        raise AssertionError('Part 1 CO profile atlas metadata changed')
    for entry, w, h, digest, _, _ in LABELS:
        offset, ew, eh = entry_span(original, entry)
        if (ew, eh) != (w, h) or hashlib.sha256(original[offset:offset + w * h * 32]).hexdigest() != digest:
            raise AssertionError(f'Part 1 CO profile label {entry} source changed')


def render(original, entry):
    _, w, h, _, text, style = next(row for row in LABELS if row[0] == entry)
    offset, _, _ = entry_span(original, entry)
    data = bytearray(original[offset:offset + w * h * 32])
    width = w * 8

    def index(x, y):
        return ((y // 8) * w + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2

    def put(x, y, value):
        i = index(x, y)
        shift = 4 * (x % 2)
        data[i] = (data[i] & ~(15 << shift)) | (value << shift)

    ink, text_width = _ink(text)
    if style == 'plate':
        # White plate, black ink; native text box x12..29, rows 3..12.
        x0, y0, x1, y1 = 12, 3, 30, 13
        for y in range(y0, y1):
            for x in range(x0, x1):
                put(x, y, WHITE)
        left = x0 + (x1 - x0 - text_width) // 2
        for x, y in ink:
            put(left + x, 4 + y, BLACK)
        return bytes(data)
    if style == 'band':
        # Black caption band rows 8..14 with white letters, shade row 15.
        if text_width <= 23:
            x0, x1, shade_col = 1, 26, 26
        else:
            x0, x1, shade_col = 0, 32, None
        for y in range(8, 16):
            for x in range(width):
                if y == 15:
                    value = SHADE if x0 + 1 <= x < x1 + (1 if shade_col else 0) else 0
                elif x0 <= x < x1:
                    value = BLACK
                elif x == shade_col:
                    value = SHADE
                else:
                    value = 0
                put(x, y, value)
        left = x0 + (x1 - x0 - text_width) // 2
        for x, y in ink:
            if not (x0 <= left + x < x1):
                raise AssertionError(f'Part 1 CO profile band overflow: {text}')
            put(left + x, 8 + y, WHITE)
        return bytes(data)
    # 16x16 badge: keep the picture box rows 0..7, black band rows 8..15.
    for y in range(8, 16):
        for x in range(width):
            put(x, y, BLACK if 1 <= x <= 14 and not (y == 15 and x in (1, 14)) else 0)
    left = (width - text_width) // 2
    for x, y in ink:
        put(left + x, 8 + y, WHITE)
    return bytes(data)


def expected_regions(original):
    source_guard(original)
    return [(entry_span(original, entry)[0], render(original, entry)) for entry, *_ in LABELS]


def patch(rom, original):
    regions = expected_regions(original)
    start, raw = META_SPAN
    if bytes(rom[start:start + len(raw)]) != raw:
        raise AssertionError('Part 1 CO profile atlas metadata changed by another writer')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'Part 1 CO profile label {address:06X} conflicts with an earlier writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    return len(regions)


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original))


def capture(rom, original):
    source_guard(original)
    start, raw = META_SPAN
    regions = [(start, bytes(rom[start:start + len(raw)]))]
    for entry, w, h, *_ in LABELS:
        offset = entry_span(original, entry)[0]
        regions.append((offset, bytes(rom[offset:offset + w * h * 32])))
    return tuple(regions)


def verify(rom, regions):
    if len(regions) != len(LABELS) + 1 or regions[0][0] != META_SPAN[0]:
        raise AssertionError('Part 1 CO profile label snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'Part 1 CO profile label overwritten at {address:06X}')
