"""Quantize text coverage using the original Part 1 menu palette families."""
from functools import lru_cache
from PIL import Image, ImageChops, ImageFilter

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
