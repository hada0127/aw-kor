"""Korean place names on the Part 1 opening-demo strategy map (Mode 4 bitmap).

The two LZ77 halves 0xC2FD70 (rows 0..79) and 0xC30EE8 (rows 80..159) are
copied verbatim into the Mode 4 frame buffer (VRAM 0x06000000; R19b capture
smap_jp/smap_b.vram == decoded halves).  The BG palette on screen is the
256-colour ROM palette 0xC31F2C (R19b PRAM dump; only index 0 is faded), not
the OBJ palette 0xC2FC90 the first version used.

Each English cursive label is drawn with one ink index plus one lighter
anti-alias index on a flat fill.  R20 (2026-11-09): only those script pixels
are turned back into the fill -- and only between the first and last fill
pixel of each row, so the dithered oval rim and the land hatching stay -- and
Galmuri7 Korean is drawn in the script's ink index centred on the old script.
The small "+" location markers and the other labels (Yellow Comet, City, ...)
are not touched.
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from bdf import glyph_grid, load_bdf
from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
W = 240
HALVES = ((0xC2FD70, 4471), (0xC30EE8, 4161))   # (LZ77 offset, compressed size)
# (Korean lines, area (x0, y0, x1, y1) in frame pixels, fill, ink, AA, align)
LABELS = (
    (('레드스타', '궁전'), (30, 15, 100, 36), 2, 16, 9, 'center'),     # Red star Palace
    (('공장',), (119, 35, 156, 47), 17, 24, 22, 'left'),              # +Factory (after the marker)
    (('블루문', '궁전'), (104, 49, 172, 72), 13, 24, 22, 'center'),    # Blue moon Palace
    (('그린어스', '궁전'), (110, 100, 168, 124), 3, 23, 19, 'center'),  # Cosmo earth Palace
)
# Decoded native frame (both halves), checked before any edit.
FRAME_SHA256 = 'a8278b6fe92271bb639c6a3c255de072a1294f8197f6729fd48288c4ea804bca'


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))[0]


def _line(text):
    """Galmuri7 ink (x, y) on a 7-row cell and the line width."""
    ink, cursor = [], 0
    for char in text:
        grid, width, height, xoffset, yoffset = glyph_grid(_font()[ord(char)])
        top = 7 - height - yoffset
        ink += [(cursor + xoffset + x, top + y) for y in range(height) for x in range(width) if grid[y][x]]
        cursor += xoffset + width + 1
    return ink, cursor - 1


def erase_script(frame, area, fill, script):
    """Script pixels inside the fill span of each row -> fill; returns their bbox."""
    x0, y0, x1, y1 = area
    hit = []
    for y in range(y0, y1):
        row = frame[y * W + x0:y * W + x1]
        inside = [x0 + i for i, v in enumerate(row) if v == fill]
        if not inside:
            continue
        for x in range(inside[0], inside[-1] + 1):
            if frame[y * W + x] in script:
                frame[y * W + x] = fill
                hit.append((x, y))
    if not hit:
        raise AssertionError(f'no script pixels in strategy map area {area}')
    xs, ys = [x for x, _ in hit], [y for _, y in hit]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def draw_lines(frame, lines, bbox, fill, ink, align):
    left, top, right, bottom = bbox
    height = len(lines) * 8 - 1
    y = (top + bottom - height) // 2
    for text in lines:
        points, width = _line(text)
        x = (left + right - width) // 2 if align == 'center' else left
        for px, py in points:
            if frame[(y + py) * W + x + px] != fill:
                raise AssertionError(f'strategy map label {text} leaves its fill')
            frame[(y + py) * W + x + px] = ink
        y += 8


def frame_from(rom):
    return bytearray(b''.join(lz77_decompress(rom, offset)[0] for offset, _ in HALVES))


def localized_frame(original):
    for offset, size in HALVES:
        if lz77_decompress(original, offset)[1] != size:
            raise AssertionError(f'strategy map half {offset:06X} source changed')
    frame = frame_from(original)
    if hashlib.sha256(bytes(frame)).hexdigest() != FRAME_SHA256:
        raise AssertionError('strategy map frame source changed')
    for lines, area, fill, ink, aa, align in LABELS:
        bbox = erase_script(frame, area, fill, {ink, aa})
        draw_lines(frame, lines, bbox, fill, ink, align)
    return bytes(frame)


def expected_regions(original):
    frame = localized_frame(original)
    regions = []
    for index, (offset, capacity) in enumerate(HALVES):
        stream = lz77_compress_optimal(frame[index * W * 80:(index + 1) * W * 80], vram_safe=True)
        if len(stream) > capacity:
            raise AssertionError(f'strategy map half {offset:06X} overflow: {len(stream)} > {capacity}')
        regions.append((offset, stream + bytes(original[offset + len(stream):offset + capacity])))
    return regions


def patch(rom, original):
    for offset, new in expected_regions(original):
        if bytes(rom[offset:offset + len(new)]) != bytes(original[offset:offset + len(new)]):
            raise AssertionError(f'strategy map half {offset:06X} modified by another writer')
        rom[offset:offset + len(new)] = new
    return len(LABELS)
