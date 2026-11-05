"""Quantize text coverage using the original Part 1 menu palette families."""
from functools import lru_cache
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


@lru_cache(maxsize=8)
def _font_codepoints(font_path):
    from fontTools.ttLib import TTFont
    with TTFont(str(font_path), lazy=True) as font:
        return frozenset(font.getBestCmap() or ())

# Fresh-boot original ROM PRAM, OBJ banks 4/8/9/10. These are comparison
# profiles only; the renderer writes tile indices and never changes PRAM.
PART1_STYLE_PALETTES = (
    ((106,57,0),(238,246,255),(213,222,255),(180,197,255),(156,180,255),(131,156,255),(98,131,255),(74,106,255),(41,74,255),(106,57,0),(255,255,255),(205,197,197),(148,148,148),(98,90,90),(41,41,90),(49,32,16)),
    ((0,0,115),(230,255,238),(205,238,230),(172,222,222),(148,205,213),(123,189,197),(90,172,189),(65,156,180),(32,123,106),(106,57,0),(255,255,255),(205,197,197),(148,148,148),(98,90,90),(32,74,57),(49,32,16)),
    ((0,0,115),(238,255,246),(205,255,213),(164,255,180),(131,255,156),(90,255,123),(57,255,90),(16,255,57),(0,172,24),(106,57,0),(255,255,255),(205,197,197),(148,148,148),(98,90,90),(32,74,16),(49,32,16)),
    ((0,0,115),(255,246,238),(255,213,205),(255,180,172),(255,148,139),(255,115,106),(255,82,74),(255,49,41),(213,57,0),(106,57,0),(255,255,255),(205,197,197),(148,148,148),(98,90,90),(98,41,8),(49,32,16)),
)


@lru_cache(maxsize=8192)
def blend_index(under, over, alpha, candidates):
    """Choose one index across all shared palettes, never interpolate indices."""
    return min(candidates, key=lambda i: sum(
        sum((p[i][c] * 255 - p[under][c] * (255 - alpha) - p[over][c] * alpha) ** 2
            for c in range(3)) for p in PART1_STYLE_PALETTES
    ))


def palette_blend_index(under, over, alpha, candidates, palettes):
    """Nearest existing index to an RGB coverage blend in every supplied bank.

    A generator must supply the live palette bank(s), including animated/shared
    states. Index zero is never admitted as an AA color by the renderer.
    """
    if not palettes or not candidates or not 0 <= alpha <= 255:
        raise ValueError('palette profiles, candidates and 8-bit alpha required')
    for palette in palettes:
        if any(i < 0 or i >= len(palette) for i in (under, over, *candidates)):
            raise ValueError('palette index outside supplied bank')
    return min(candidates, key=lambda i: (sum(
        sum((palette[i][c] * 255 - palette[under][c] * (255 - alpha)
             - palette[over][c] * alpha) ** 2 for c in range(3))
        for palette in palettes), candidates.index(i)))


def supersampled_text(text, font_path, font_size, size, origin, *, scale=8):
    """Render an L fill mask at scale×; size and origin are target pixels.

    The font path is explicit so each generator can use its approved font.
    Clipped ink and missing glyphs fail instead of silently shortening text.
    """
    if scale < 2 or font_size < 1 or min(size) < 1:
        raise ValueError('invalid supersampling geometry')
    missing = [ch for ch in text if not ch.isspace() and ord(ch) not in _font_codepoints(str(font_path))]
    if missing:
        raise ValueError(f'font lacks glyphs: {missing!r}')
    font = ImageFont.truetype(str(font_path), font_size * scale)
    canvas = Image.new('L', (size[0] * scale, size[1] * scale), 0)
    draw = ImageDraw.Draw(canvas)
    draw.text((origin[0] * scale, origin[1] * scale), text, font=font, fill=255)
    box = draw.textbbox((origin[0] * scale, origin[1] * scale), text, font=font)
    if box[0] < 0 or box[1] < 0 or box[2] > canvas.width or box[3] > canvas.height:
        raise ValueError(f'text exceeds cell: {text!r}')
    if not canvas.getbbox():
        raise ValueError(f'empty text: {text!r}')
    return canvas


def size_for_ink_height(text, font_path, target_height, cell_size, *,
                        min_size=1, max_size=64, scale=8):
    """Choose the fitted font size nearest the requested final ink height.

    Returns (font_size, measured_height). Equal errors prefer the larger size.
    A generator still checks its own width, baseline and protected layout.
    """
    if target_height < 1:
        raise ValueError('target height must be positive')
    choices = []
    for font_size in range(min_size, max_size + 1):
        font = ImageFont.truetype(str(font_path), font_size * scale)
        box = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), text, font=font)
        width = (box[2] - box[0] + scale - 1) // scale
        height = (box[3] - box[1] + scale - 1) // scale
        if width and height and width <= cell_size[0] and height <= cell_size[1]:
            choices.append((abs(height - target_height), -font_size, font_size, height))
    if not choices:
        raise ValueError(f'text cannot fit cell: {text!r}')
    _, _, chosen, measured = min(choices)
    return chosen, measured


def render_graphic_aa(masks, size, *, palettes, allowed_indices, fills,
                      backgrounds, base=None, protected=None, text_region=None,
                      glyphs=(), scale=8):
    """Compose high-resolution L masks into a palette-indexed image.

    masks: ordered dict of layer name -> scale× L mask (shadow, outline,
    fill, crack order is caller-controlled). fills: layer -> index or one
    index per target row. backgrounds: layer -> opaque local index or 0.
    Each background may also be one index per row. A transparent background
    admits the solid core only, avoiding halos.
    glyphs: (character, target-pixel box) records checked with verify_glyph
    against the fill's binary core. Return (P image, measurements).
    """
    from hangul_pixel_fit import verify_glyph
    if scale < 2 or not masks or not palettes or not allowed_indices:
        raise ValueError('scale, masks, palettes and allowed indices required')
    allowed = tuple(dict.fromkeys(allowed_indices))
    if 0 in allowed:
        raise ValueError('transparent index cannot be an AA ramp color')
    if set(masks) != set(fills) or set(masks) != set(backgrounds):
        raise ValueError('every layer needs fill and background indices')
    if base is None:
        base = Image.new('P', size, 0)
    if base.size != size or base.mode != 'P':
        raise ValueError('base must be a matching indexed image')
    if protected is not None and (protected.size != size or protected.mode != '1'):
        raise ValueError('protected mask must be a matching 1-bit image')
    if text_region is not None and (text_region.size != size or text_region.mode != '1'):
        raise ValueError('text region must be a matching 1-bit image')
    result = base.copy()
    cores = {}
    for name, high in masks.items():
        if high.mode != 'L' or high.size != (size[0] * scale, size[1] * scale):
            raise ValueError(f'invalid high-resolution mask: {name}')
        coverage = high.resize(size, Image.Resampling.BOX)
        core = coverage.point(lambda v: 255 if v >= 128 else 0)
        cores[name] = core
        row_fill = fills[name]
        if isinstance(row_fill, int):
            row_fill = [row_fill] * size[1]
        if len(row_fill) != size[1]:
            raise ValueError(f'fill row count differs: {name}')
        row_under = backgrounds[name]
        if isinstance(row_under, int):
            row_under = [row_under] * size[1]
        if len(row_under) != size[1]:
            raise ValueError(f'background row count differs: {name}')
        for y in range(size[1]):
            fill = row_fill[y]
            under = row_under[y]
            if fill not in allowed or (under and under not in allowed):
                raise ValueError(f'illegal palette index: {name} row {y}')
            for x in range(size[0]):
                alpha = coverage.getpixel((x, y))
                if not alpha:
                    continue
                if text_region is not None and not text_region.getpixel((x, y)):
                    raise ValueError(f'ink outside text region: {name} {(x, y)}')
                if protected is not None and protected.getpixel((x, y)):
                    raise ValueError(f'protected pixel touched: {name} {(x, y)}')
                if core.getpixel((x, y)):
                    result.putpixel((x, y), fill)
                elif under:
                    result.putpixel((x, y), palette_blend_index(under, fill, alpha, allowed, palettes))
    if glyphs:
        if 'fill' not in cores:
            raise ValueError('glyph validation requires a fill layer')
        for char, box in glyphs:
            if not '\uac00' <= char <= '\ud7a3':
                continue
            check = verify_glyph(char, cores['fill'].crop(box))
            if check['failures']:
                raise ValueError(f'closed counter or altered glyph: {check}')
    ink_box = cores['fill'].getbbox() if 'fill' in cores else None
    return result, {'scale': scale, 'core_box': ink_box,
                    'core_height': 0 if ink_box is None else ink_box[3] - ink_box[1],
                    'layers': tuple(masks)}


def body_index(fill, alpha):
    if alpha >= 192:
        return fill
    if alpha >= 96:
        return blend_index(14, fill, min(255, alpha + 48), (14, *range(8, fill - 1, -1)))
    return None


def compose_part1_text(layer, inner, body, row_colors, *, compact=False):
    """Keep solid strokes; use the original edge colors only at coverage edges."""
    # The white envelope encloses both the dark contour and its cast shadow.
    shadow = Image.new('L', layer.size, 0)
    shadow.paste(inner, (1, 1))
    contour = inner.point(lambda value: 255 if value >= 48 else 0)
    cast = shadow.point(lambda value: 255 if value >= 96 else 0)
    outer = ImageChops.lighter(contour, cast).filter(ImageFilter.MaxFilter(3))
    lp = layer.load()
    sp, op, ip, bp = (mask.load() for mask in (shadow, outer, inner, body))
    for y in range(layer.height):
        for x in range(layer.width):
            if compact:
                value = 9 if sp[x, y] >= 80 else 0
                if ip[x, y] >= 96:
                    value = 14
                if bp[x, y] >= 160:
                    value = row_colors[y]
                elif bp[x, y] >= 96:
                    value = 12 if row_colors[y] == 10 else 8
                lp[x, y] = value
                continue
            value = 10 if op[x, y] >= 96 else 0
            if sp[x, y] >= 96:
                value = 9
            if ip[x, y] >= 48:
                value = 14
            fill = body_index(row_colors[y], bp[x, y])
            if fill is not None:
                value = fill
            lp[x, y] = value
