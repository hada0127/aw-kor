"""Part 1 capture-card 占領! OBJ, observed live at OAM 18/19.

The 40x32, 4bpp raw strip is loaded from 0xBC3CEC to OBJ tiles 397..416.
Its 22-pixel high picture word uses the approved OkDanDan-Bold face.
"""
import hashlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import aw_fonts

OFFSET = 0xBC3CEC
WIDTH, HEIGHT = 40, 32
SIZE = WIDTH * HEIGHT // 2
ORIGINAL_SHA256 = '91e8d6c768da2ed32a46f8fd818e4c0375fc186cceacda19301b45708d8a0fdf'


def _pixels():
    scale = 4
    font = ImageFont.truetype(aw_fonts.okdandan_path(), 20 * scale)
    text = '점령!'
    bbox = font.getbbox(text)
    ink = Image.new('L', (bbox[2] - bbox[0], bbox[3] - bbox[1]), 0)
    ImageDraw.Draw(ink).text((-bbox[0], -bbox[1]), text, font=font, fill=255)
    crop = ink.getbbox()
    if crop is None:
        raise AssertionError('Part 1 capture word is empty')
    ink = ink.crop(crop).resize((36, 18), Image.Resampling.LANCZOS)
    mask = Image.new('L', (WIDTH, HEIGHT), 0)
    mask.paste(ink, (2, 7))
    core = mask.point(lambda value: 255 if value >= 96 else 0)
    rim = core.filter(ImageFilter.MaxFilter(3))
    outer = rim.filter(ImageFilter.MaxFilter(3))
    rows = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            if core.getpixel((x, y)):
                color = 1  # white core in the native capture-word OBJ palette
            elif rim.getpixel((x, y)):
                color = 12  # purple inner rim
            elif outer.getpixel((x, y)):
                color = 14  # dark navy outline
            else:
                color = 0
            row.append(color)
        rows.append(row)
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
            'text': '점령!', 'font': 'OkDanDan-Bold'}


def verify(rom, original):
    if bytes(rom[OFFSET:OFFSET + SIZE]) != generated(original):
        raise AssertionError('Part 1 capture word overwritten')
