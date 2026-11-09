"""Part 1 capture-card 占領! OBJ, observed live at OAM 18/19.

The 40x32, 4bpp raw strip is loaded from 0xBC3CEC to OBJ tiles 397..416.

R15a (2026-11-09) live capture (CHEAT, 작전룸 training 2, JP and candidate,
OAM 18/19 affine, OBJ bank 3): the JP word is a squared gothic, 22 rows high,
with a 1px navy outline 14, white 1 highlight on the left edge of every stem,
a lilac 2..6 sheen that darkens down each stroke, 12 shading on the right
edge and 13 at diagonal outline corners.  Per the 2026-11-05 rule the Korean
word is Hada Sans ExtraBold drawn with that same index composition (was
OkDanDan-Bold with a 2px purple/navy rim).
"""
import hashlib

from PIL import Image, ImageDraw, ImageFont

import aw_fonts

OFFSET = 0xBC3CEC
WIDTH, HEIGHT = 40, 32
SIZE = WIDTH * HEIGHT // 2
ORIGINAL_SHA256 = '91e8d6c768da2ed32a46f8fd818e4c0375fc186cceacda19301b45708d8a0fdf'
TEXT = '점령!'
TOP, BODY_ROWS, BODY_WIDTH = 1, 20, 37   # JP ink rows 0..21 incl. the outline
HIGHLIGHT, SHADE, OUTLINE, OUTLINE_AA = 1, 12, 14, 13
SHEEN = (1, 3, 3, 4, 4, 5, 5, 6)   # by depth below the top of the stroke


def _coverage():
    """ExtraBold word, cropped to its ink and resampled into the JP word box
    (BODY_WIDTH x BODY_ROWS): the JP 占領 glyphs are taller than wide, so the
    word keeps the JP height instead of shrinking to the width limit."""
    scale = 4
    font = ImageFont.truetype(aw_fonts.hadasans_extrabold_path(), 24 * scale)
    probe = Image.new('L', (60 * 24 * scale // 10, 40 * scale), 0)
    ImageDraw.Draw(probe).text((4 * scale, 4 * scale), TEXT, font=font, fill=255)
    ink = probe.crop(probe.getbbox())
    width = min(BODY_WIDTH, round(ink.width * BODY_ROWS / ink.height))
    ink = ink.resize((width, BODY_ROWS), Image.Resampling.LANCZOS)
    image = Image.new('L', (WIDTH, HEIGHT), 0)
    image.paste(ink, ((WIDTH - width) // 2, TOP + 1))
    return image


def _pixels():
    cov = _coverage()
    body = {(x, y) for y in range(HEIGHT) for x in range(WIDTH) if cov.getpixel((x, y)) >= 128}
    near4 = lambda x, y: ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    ring = {(x + dx, y + dy) for x, y in body for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body
    rows = [[0] * WIDTH for _ in range(HEIGHT)]
    for x, y in ring:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise AssertionError('capture word clipped')
        rows[y][x] = OUTLINE if any(q in body for q in near4(x, y)) else OUTLINE_AA
    for x, y in body:
        depth = 0
        while (x, y - depth - 1) in body:
            depth += 1
        if (x - 1, y) not in body:
            value = HIGHLIGHT
        elif (x + 1, y) not in body:
            value = SHADE
        else:
            value = SHEEN[min(depth, len(SHEEN) - 1)]
        rows[y][x] = value
    occupied = [(x, y) for y, row in enumerate(rows) for x, color in enumerate(row) if color]
    bounds = (min(x for x, _ in occupied), min(y for _, y in occupied),
              max(x for x, _ in occupied) + 1, max(y for _, y in occupied) + 1)
    if bounds[3] - bounds[1] <= 16 or bounds[2] > WIDTH or bounds[3] > HEIGHT:
        raise AssertionError(f'capture word geometry invalid: {bounds}')
    return rows


def generated(original):
    source = bytes(original[OFFSET:OFFSET + SIZE])
    if len(source) != SIZE or hashlib.sha256(source).hexdigest() != ORIGINAL_SHA256:
        raise AssertionError('Part 1 capture word source changed')
    pixels = _pixels()
    raw = bytearray(SIZE)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            # OAM 18 is 32x32 (four tiles wide); OAM 19 is its 8x32 suffix.
            tile = ((y // 8) * 4 + x // 8) if x < 32 else (16 + y // 8)
            at = tile * 32 + (y % 8) * 4 + (x % 8) // 2
            if x & 1:
                raw[at] |= pixels[y][x] << 4
            else:
                raw[at] |= pixels[y][x]
    return bytes(raw)


def patch(rom, original):
    result = generated(original)
    if bytes(rom[OFFSET:OFFSET + SIZE]) not in (bytes(original[OFFSET:OFFSET + SIZE]), result):
        raise AssertionError('Part 1 capture word writer conflict')
    rom[OFFSET:OFFSET + SIZE] = result
    return {'offset': hex(OFFSET), 'size': SIZE, 'sha256': hashlib.sha256(result).hexdigest(),
            'text': TEXT, 'font': 'HadaSans-ExtraBold'}


def verify(rom, original):
    if bytes(rom[OFFSET:OFFSET + SIZE]) != generated(original):
        raise AssertionError('Part 1 capture word overwritten')
