"""Small Galmuri captions in all LINK MODE plate variants (54E538)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CAPTIONS = ('1팩 대전', '멀티팩 대전', '맵 교환')


def draw_hada_main(text, *, with_records=False):
    """Selected LINK caption with a solid Hada Sans body in the native band."""
    from aw_fonts import hadasans_path
    im = Image.new('L', (128, 32), 0)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 3, 127, 29), fill=4)
    draw.rectangle((0, 3, 127, 4), fill=1)
    draw.rectangle((0, 30, 127, 31), fill=3)
    # Render from the same high-resolution Hada outline as the approved mode
    # plates. Small hinted FreeType text broke the counters in 맵 교환.
    font = ImageFont.truetype(str(hadasans_path()), 384)
    glyphs = []
    for ch in text:
        if ch == ' ':
            glyphs.append(Image.new('L', (5, 23)))
            continue
        probe = Image.new('L', (768, 768))
        ImageDraw.Draw(probe).text((20, 0), ch, font=font, fill=255)
        box = probe.point(lambda v: 255 if v >= 128 else 0).getbbox()
        if box is None:
            raise AssertionError(f'empty LINK glyph: {ch!r}')
        cropped = probe.crop(box)
        width = max(1, round(cropped.width * 23 / cropped.height))
        glyphs.append(cropped.resize((width, 23), Image.Resampling.LANCZOS)
                      .point(lambda v: 255 if v >= 128 else 0))
    gap = 2
    width = sum(g.width for g in glyphs) + gap * (len(glyphs) - 1)
    if width > 120 or any(g.height > 23 for g in glyphs):
        raise AssertionError(f'LINK main caption exceeds native band: {text!r}')
    x = (128 - width) // 2
    records = []
    for ch, g in zip(text, glyphs):
        y = 6 + (23 - g.height) // 2
        im.paste(1, (x, y), g)
        if ch != ' ':
            records.append((ch, (x, y, x + g.width, y + g.height)))
        x += g.width + gap
    return (im, records) if with_records else im


def canvas(data, offset, segment_width, height):
    im = Image.new('L', (128, height))
    for y in range(height):
        for x in range(128):
            seg, sx = divmod(x, segment_width)
            i = offset + seg * segment_width * height // 2 + ((y // 8) * (segment_width // 8) + sx // 8) * 32 + y % 8 * 4 + sx % 8 // 2
            im.putpixel((x, y), data[i] >> (x % 2 * 4) & 15)
    return im


def pack(im, segment_width):
    out = bytearray()
    for seg in range(im.width // segment_width):
        for ty in range(im.height // 8):
            for tx in range(segment_width // 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        px = seg * segment_width + tx * 8 + x
                        py = ty * 8 + y
                        out.append(im.getpixel((px, py)) | im.getpixel((px + 1, py)) << 4)
    return bytes(out)


def draw_caption(im, text, y, height):
    draw = ImageDraw.Draw(im)
    for size in range(height, 6, -1):
        font = ImageFont.truetype(str(ROOT / 'reference/fonts/Galmuri11-Condensed.ttf'), size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[3] - box[1] <= height:
            break
    width, ink_height = box[2] - box[0], box[3] - box[1]
    if ink_height > height or ink_height > 16 or width > 120:
        raise AssertionError('LINK MODE caption exceeds its native strip')
    # Match the dark plate and white/blue antialiased caption palette.
    draw.rectangle((1, y, 126, y + height - 1), fill=4)
    mask = Image.new('L', im.size)
    ImageDraw.Draw(mask).text(((128 - width) // 2 - box[0], y + (height - ink_height) // 2 - box[1]), text, font=font, fill=255)
    for yy in range(y, y + height):
        for x in range(1, 127):
            v = mask.getpixel((x, yy))
            if v >= 64:
                im.putpixel((x, yy), 1 if v >= 160 else 2)


def repair_captions(data):
    out = bytearray(data)
    # Unselected variants are separate 128x16 plates, including MULTI-PAK.
    for i, text in enumerate(CAPTIONS):
        offset = 0x1800 + i * 0x400
        im = canvas(out, offset, 32, 16)
        draw_caption(im, text, 2, 12)
        out[offset:offset + 0x400] = pack(im, 32)
    return out
