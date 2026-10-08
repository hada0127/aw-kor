"""Font locations and the shared large-title renderer for ROM graphics.

2026-10-08 user font rule (CLAUDE.md): large drawn text (titles, banners,
headlines, big labels) uses OkDanDan-Bold; small text glyphs use Galmuri
(reference/fonts). No other font may produce ROM pixels.

OkDanDan is not redistributable here, so it is resolved from a font directory:
  AW_FONT_DIR (explicit) > ~/Library/Fonts (macOS, unchanged) > ~/aw-fonts (Linux).
"""
import hashlib
import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GALMURI_DIR = ROOT / 'reference' / 'fonts'
GALMURI11_BOLD = GALMURI_DIR / 'Galmuri11-Bold.ttf'
GALMURI11_CONDENSED = GALMURI_DIR / 'Galmuri11-Condensed.ttf'
# Official okticon OkDanDan-Bold.otf; the Linux ~/aw-fonts copy (2026-10-08)
# has this SHA-256, the same value the Mac builds pinned.
OKDANDAN_SHA256 = '3b48adae2f39018dfa8e3d8264363729f024af9c7eb289dcb0479e6d7ea67472'


def font_dir():
    env = os.environ.get('AW_FONT_DIR')
    if env:
        return Path(env).expanduser()
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Fonts'
    return Path.home() / 'aw-fonts'


OKDANDAN = font_dir() / 'OkDanDan-Bold.otf'


def okdandan_path(verify=True):
    """Path of OkDanDan-Bold; fails closed when missing or a different build."""
    path = OKDANDAN
    if not path.is_file():
        raise FileNotFoundError(f'OkDanDan-Bold font not found: {path} (set AW_FONT_DIR)')
    if verify:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != OKDANDAN_SHA256:
            raise AssertionError(f'unexpected OkDanDan-Bold SHA-256 {digest} at {path}')
    return str(path)


def fit_okdandan(text, max_w, max_h, max_size, min_size=6, stroke=0, spacing=0):
    """Largest OkDanDan size whose (stroked) ink box fits max_w x max_h."""
    from PIL import ImageFont
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(okdandan_path(), size)
        box = text_box(text, font, stroke, spacing)
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return font, box
    raise AssertionError(f'OkDanDan cannot fit {text!r} in {max_w}x{max_h} (min size {min_size})')


def text_box(text, font, stroke=0, spacing=0):
    from PIL import Image, ImageDraw
    if not spacing:
        return ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), text, font=font,
                                                                stroke_width=stroke)
    mask = text_mask(text, font, stroke=stroke, spacing=spacing)
    return mask.getbbox() or (0, 0, 0, 0)


def text_mask(text, font, size=None, origin=(0, 0), stroke=0, spacing=0, fill=True):
    """L mask of text (fill only, or fill+stroke when fill=False and stroke>0).
    With spacing the characters are placed one by one with extra advance."""
    from PIL import Image, ImageDraw
    if size is None:
        width = int(font.getlength(text)) + 4 * stroke + spacing * len(text) + font.size * 2
        size = (width, font.size * 2 + 4 * stroke)
    image = Image.new('L', size, 0)
    draw = ImageDraw.Draw(image)
    kwargs = {} if fill or not stroke else {'stroke_width': stroke, 'stroke_fill': 255}
    if not spacing:
        draw.text(origin, text, font=font, fill=255, **kwargs)
        return image
    x, y = origin
    for ch in text:
        draw.text((x, y), ch, font=font, fill=255, **kwargs)
        x += font.getlength(ch) + spacing
    return image


def draw_okdandan(pixels, text, box, max_size, ink, outline=None, shadow=None,
                  shadow_offset=(1, 1), stroke=1, min_size=6, fill_threshold=128,
                  outline_threshold=96, align='center', valign='center', stretch=None,
                  line_chars=None):
    """Draw large text with OkDanDan into a row-major index grid (list of lists).

    box = (x0, y0, x1, y1) exclusive; the whole ink (fill, outline and shadow)
    stays inside it. outline (stroke idx) and shadow (drop shadow idx) are
    optional; the shadow is only painted on pixels that stay 0. shadow_offset
    may be one (dx, dy) or a list of them. stretch=(w, h) renders the text
    big and resamples its ink box to exactly w x h (for cells whose aspect
    differs from the font). valign='line' centres the common OkDanDan line over
    line_chars instead of this text's own ink (one baseline across separately
    drawn labels).
    Returns the chosen font size and ink bounding box.
    """
    from PIL import Image, ImageDraw, ImageFont
    height, width = len(pixels), len(pixels[0])
    s = stroke if outline is not None else 0
    offsets = [] if shadow is None else (
        [shadow_offset] if isinstance(shadow_offset[0], int) else list(shadow_offset))
    sx = max([0] + [dx for dx, _ in offsets])
    sy = max([0] + [dy for _, dy in offsets])
    bw, bh = box[2] - box[0], box[3] - box[1]
    if stretch:
        w, h = stretch[0] + 2 * s + sx, stretch[1] + 2 * s + sy
        if w > bw or h > bh:
            raise AssertionError(f'stretched {text!r} {w}x{h} exceeds {bw}x{bh}')
        size = 96
        font = ImageFont.truetype(okdandan_path(), size)
        big = Image.new('L', (int(font.getlength(text)) + 2 * size, 3 * size), 0)
        ImageDraw.Draw(big).text((size // 2, size // 2), text, font=font, fill=255)
        big = big.crop(big.getbbox()).resize(stretch, Image.Resampling.LANCZOS)
        x = box[0] + {'center': (bw - w) // 2, 'left': 0, 'right': bw - w}[align] + s
        y = box[1] + {'center': (bh - h) // 2, 'top': 0, 'bottom': bh - h}[valign] + s
        fill_mask = Image.new('L', (width, height), 0)
        fill_mask.paste(big, (x, y))
        outer = fill_mask.copy()
        if s:
            from PIL import ImageFilter
            hard = fill_mask.point(lambda v: 255 if v >= fill_threshold else 0)
            outer = hard.filter(ImageFilter.MaxFilter(2 * s + 1))
        ink_box = (x - s, y - s, x - s + w, y - s + h)
    else:
        for size in range(max_size, min_size - 1, -1):
            font = ImageFont.truetype(okdandan_path(), size)
            tb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), text, font=font, stroke_width=s)
            if valign == 'line':
                # Vertical metrics from the common OkDanDan line, so labels drawn
                # separately share one baseline whatever their syllables.
                top, bottom = okdandan_line(size, line_chars)
                tb = (tb[0], top - s, tb[2], bottom + s)
            w, h = tb[2] - tb[0] + sx, tb[3] - tb[1] + sy
            if w <= bw and h <= bh:
                break
        else:
            raise AssertionError(f'OkDanDan cannot fit {text!r} in {bw}x{bh}')
        x = box[0] + {'center': (bw - w) // 2, 'left': 0, 'right': bw - w}[align] - tb[0]
        y = box[1] + {'center': (bh - h) // 2, 'line': (bh - h) // 2, 'top': 0,
                      'bottom': bh - h}[valign] - tb[1]
        fill_mask = Image.new('L', (width, height), 0)
        ImageDraw.Draw(fill_mask).text((x, y), text, font=font, fill=255)
        outer = Image.new('L', (width, height), 0)
        ImageDraw.Draw(outer).text((x, y), text, font=font, fill=255, stroke_width=s, stroke_fill=255)
        ink_box = (x + tb[0], y + tb[1], x + tb[0] + w, y + tb[1] + h)
    fp, op = fill_mask.load(), outer.load()
    edge = outline_threshold if s else fill_threshold
    for dx, dy in offsets:
        for yy in range(height):
            for xx in range(width):
                ox, oy = xx - dx, yy - dy
                if 0 <= ox < width and 0 <= oy < height and pixels[yy][xx] == 0 and op[ox, oy] >= edge:
                    pixels[yy][xx] = shadow
    for yy in range(height):
        for xx in range(width):
            if outline is not None and op[xx, yy] >= outline_threshold:
                pixels[yy][xx] = outline
            if fp[xx, yy] >= fill_threshold:
                pixels[yy][xx] = ink
    return size, ink_box


def okdandan_ink(text, box, max_size, min_size=6, threshold=128, align='center',
                 valign='center', size=None):
    """Set of (x, y) OkDanDan ink pixels for text fitted into box=(x0,y0,x1,y1).

    With size given the text is drawn at that size (fails if it does not fit).
    Callers keep their own outline/shadow composition around the ink.
    """
    from PIL import Image, ImageDraw, ImageFont
    bw, bh = box[2] - box[0], box[3] - box[1]
    sizes = [size] if size else range(max_size, min_size - 1, -1)
    for current in sizes:
        font = ImageFont.truetype(okdandan_path(), current)
        canvas = Image.new('L', (int(font.getlength(text)) + 4 * current, 4 * current), 0)
        ImageDraw.Draw(canvas).text((current, current), text, font=font, fill=255)
        hard = canvas.point(lambda v: 255 if v >= threshold else 0)
        ink_box = hard.getbbox()
        if ink_box is None:
            raise AssertionError(f'OkDanDan has no ink for {text!r}')
        w, h = ink_box[2] - ink_box[0], ink_box[3] - ink_box[1]
        if w <= bw and h <= bh:
            break
    else:
        raise AssertionError(f'OkDanDan cannot fit {text!r} in {bw}x{bh}')
    x0 = box[0] + {'center': (bw - w) // 2, 'left': 0, 'right': bw - w}[align]
    y0 = box[1] + {'center': (bh - h) // 2, 'top': 0, 'bottom': bh - h}[valign]
    px = hard.load()
    ink = {(x0 + x - ink_box[0], y0 + y - ink_box[1])
           for y in range(ink_box[1], ink_box[3]) for x in range(ink_box[0], ink_box[2]) if px[x, y]}
    return ink, current


@lru_cache(maxsize=None)
def okdandan_line(size, chars=None):
    """(top, bottom) ink rows, from the draw origin, of the given characters
    (default: all KS X 1001 Hangul + ASCII/fullwidth signs) at this size.
    OkDanDan glyph heights vary per syllable, so per-glyph renderers align on
    this common line, never on each glyph's own ink box (which would break the
    baseline). A fixed asset passes its own characters so the line is not
    stretched by rare tall syllables it never draws."""
    import json
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(okdandan_path(), size)
    if chars is None:
        with open(ROOT / 'data' / 'syllable_to_code_2350.json', encoding='utf-8') as stream:
            chars = ''.join(json.load(stream)) + '!?.,0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ！？'
    draw = ImageDraw.Draw(Image.new('L', (1, 1)))
    top = bottom = None
    for ch in chars:
        box = draw.textbbox((0, 0), ch, font=font)
        if box[3] <= box[1]:
            continue
        top = box[1] if top is None else min(top, box[1])
        bottom = box[3] if bottom is None else max(bottom, box[3])
    return top, bottom


@lru_cache(maxsize=None)
def okdandan_fit_line(height, chars, max_size=64):
    """Largest size whose common line over chars is at most height rows."""
    for size in range(max_size, 5, -1):
        top, bottom = okdandan_line(size, chars)
        if bottom - top <= height:
            return size
    raise AssertionError(f'OkDanDan line cannot fit {height} rows')


@lru_cache(maxsize=None)
def okdandan_glyph(char, size, size_y=None, threshold=128, chars=None):
    """One OkDanDan glyph: (frozenset((x, y)), width, line_height).

    x is cropped to the glyph's ink; y is relative to the common line top of
    okdandan_line(size, chars) so different syllables keep one baseline, and
    line_height is that common line height. size_y != size stretches the
    glyph vertically (cells the native art drew taller than wide).
    Replaces the old 'Galmuri11-Bold 12px x N' masks.
    """
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(okdandan_path(), size)
    top, bottom = okdandan_line(size, chars)
    image = Image.new('L', (3 * size, bottom - top), 0)
    ImageDraw.Draw(image).text((size // 2, -top), char, font=font, fill=255)
    if size_y and size_y != size:
        image = image.resize((image.width, max(1, round(image.height * size_y / size))),
                             Image.Resampling.LANCZOS)
    px = image.load()
    ink = [(x, y) for y in range(image.height) for x in range(image.width) if px[x, y] >= threshold]
    if not ink:
        raise AssertionError(f'OkDanDan glyph missing: {char!r}')
    x0 = min(x for x, _ in ink)
    x1 = max(x for x, _ in ink)
    return frozenset((x - x0, y) for x, y in ink), x1 - x0 + 1, image.height
