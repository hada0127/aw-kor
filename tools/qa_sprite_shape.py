"""Independent binary shape oracle; no production pixel-fitting imports.

Compare final palette ink with the pinned outline at a uniform scale, or an
unscaled BDF glyph. Translation is ignored; anisotropy, component topology and
pixel overlap are not. This necessary check does not replace visual review.
"""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import aw_fonts


def components(mask):
    pixels = {(x, y) for y in range(mask.height) for x in range(mask.width)
              if mask.getpixel((x, y))}
    groups = []
    while pixels:
        seed = pixels.pop(); stack = [seed]; group = {seed}
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    p = (x + dx, y + dy)
                    if p in pixels:
                        pixels.remove(p); group.add(p); stack.append(p)
        groups.append(group)
    return sorted(groups, key=lambda g: (-len(g), min(g)))


@lru_cache(maxsize=1024)
def outline(char):
    font = ImageFont.truetype(aw_fonts.okdandan_path(), 384)
    im = Image.new('L', (768, 768))
    ImageDraw.Draw(im).text((20, 0), char, font=font, fill=255)
    box = im.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if box is None:
        raise ValueError(f'missing glyph {char!r}')
    return im.crop(box)


@lru_cache(maxsize=1024)
def hada_outline(char):
    font = ImageFont.truetype(aw_fonts.hadasans_path(), 384)
    im = Image.new('L', (768, 768))
    ImageDraw.Draw(im).text((20, 0), char, font=font, fill=255)
    box = im.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if box is None:
        raise ValueError(f'missing Hada Sans glyph {char!r}')
    return im.crop(box)


@lru_cache(maxsize=4096)
def hada_uniform_reference(char, height, width_scale=1.0):
    """Hada Sans outline raster; width_scale is the plate's DECLARED wide setting.

    Any anisotropy other than the declared one still fails 'non-uniform scale'.
    """
    src = hada_outline(char)
    width = max(1, round(src.width * height * width_scale / src.height))
    return src.resize((width, height), Image.Resampling.LANCZOS).point(lambda v: 255 if v >= 128 else 0)


@lru_cache(maxsize=1024)
def hada_plate_references(char, height, width_scale):
    """(Bold raster, Black raster) in the declared plate geometry.

    Both outlines are drawn at one origin; the box is Bold's vertical extent
    and the union of both horizontal extents; x is scaled by the declared
    width_scale relative to the box height. Uniform otherwise.
    """
    images = []
    for path in (aw_fonts.hadasans_path(), aw_fonts.hadasans_black_path()):
        font = ImageFont.truetype(path, 384)
        im = Image.new('L', (900, 768))
        ImageDraw.Draw(im).text((60, 0), char, font=font, fill=255)
        images.append(im)
    bold_box = images[0].point(lambda v: 255 if v >= 128 else 0).getbbox()
    black_box = images[1].point(lambda v: 255 if v >= 128 else 0).getbbox()
    box = (min(bold_box[0], black_box[0]), bold_box[1], max(bold_box[2], black_box[2]), bold_box[3])
    width = max(1, round((box[2] - box[0]) * height * width_scale / (box[3] - box[1])))
    return tuple(im.crop(box).resize((width, height), Image.Resampling.LANCZOS)
                 .point(lambda v: 255 if v >= 128 else 0) for im in images)


def hada_black_reference(char, height, width_scale):
    return hada_plate_references(char, height, width_scale)[1]


def _cells(mask):
    return {(x, y) for y in range(mask.height) for x in range(mask.width) if mask.getpixel((x, y))}


def compare_plate(char, actual, width_scale):
    """LARGE mode plate oracle (b20): Hada Sans Bold jamo at the declared
    width scale, grown no further than the declared Hada Sans Black weight.

    - aspect and one-to-one jamo components against the Bold raster;
    - recall: >= 90% of Bold ink is present (no stroke lost);
    - precision: >= 95% of final ink lies inside the Black raster grown by
      1px (no foreign blob). Best translation within +-2px; never stretched.
    """
    actual = actual.point(lambda v: 255 if v else 0)
    box = actual.getbbox()
    if box is None:
        return dict(character=char, failures=['empty glyph'], gap_columns=0)
    actual = actual.crop(box)
    h = actual.height
    bold_ref, black_ref = hada_plate_references(char, h, width_scale)
    result = compare(char, actual, bold_ref)
    failures = [f for f in result['failures'] if f != 'shape overlap below 0.85']
    a = _cells(actual)
    bold = _cells(bold_ref.crop((bold_ref.getbbox()[0], 0, bold_ref.width, h)))
    black = _cells(black_ref)
    black = {(x + dx, y + dy) for x, y in black for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    shifts = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)]
    best = max(shifts, key=lambda d: len({(x + d[0], y + d[1]) for x, y in bold} & a))
    recall = len({(x + best[0], y + best[1]) for x, y in bold} & a) / len(bold)
    # No closed counter/gap: every Bold column/row keeps its stroke count.
    def strokes(cells, xs=None, ys=None):
        line = [(xs, y) in cells for y in range(-3, h + 3)] if ys is None else \
               [(x, ys) in cells for x in range(-3, actual.width + 3)]
        return sum(1 for i, v in enumerate(line) if v and (i == 0 or not line[i - 1]))
    moved = {(x + best[0], y + best[1]) for x, y in bold}
    closed = [('x', x) for x in {x for x, _ in moved}
              if strokes(moved, xs=x) >= 2 and strokes(a, xs=x) < strokes(moved, xs=x)]
    closed += [('y', y) for y in {y for _, y in moved}
               if strokes(moved, ys=y) >= 2 and strokes(a, ys=y) < strokes(moved, ys=y)]
    precision = max(len({(x + dx, y + dy) for x, y in a} & black) / len(a)
                    for dx in range(-3, 4) for dy in range(-2, 3))
    if recall < .9:
        failures.append('Bold strokes missing')
    if closed:
        failures.append('stroke gap closed')
    if precision < .95:
        failures.append('ink outside declared weight guide')
    return dict(result, failures=failures, recall=round(recall, 4), precision=round(precision, 4),
                closed_lines=closed[:8])


@lru_cache(maxsize=4096)
def uniform_reference(char, height):
    src = outline(char)
    width = max(1, round(src.width * height / src.height))
    return src.resize((width, height), Image.Resampling.LANCZOS).point(lambda v: 255 if v >= 128 else 0)


def compare(char, actual, reference=None):
    actual = actual.point(lambda v: 255 if v else 0)
    box = actual.getbbox()
    if box is None:
        return dict(character=char, failures=['empty glyph'], gap_columns=0)
    actual = actual.crop(box)
    ref = uniform_reference(char, actual.height) if reference is None else reference
    ref = ref.crop(ref.getbbox())
    aspect = (actual.width / actual.height) / (ref.width / ref.height)
    # Align tight bounding boxes; never stretch either side to improve overlap.
    a = {(x,y) for y in range(actual.height) for x in range(actual.width) if actual.getpixel((x,y))}
    b = {(x,y) for y in range(ref.height) for x in range(ref.width) if ref.getpixel((x,y))}
    iou = len(a & b) / len(a | b)
    ca, cb = components(actual), components(ref)
    failures=[]
    if not .9 <= aspect <= 1.1: failures.append('non-uniform scale')
    if len(ca) != len(cb): failures.append('split/merged/stray components')
    # Count alone can miss one split plus one merge. Require one-to-one
    # spatial correspondence of every connected jamo component.
    links = [{j for j,g in enumerate(cb) if group & g} for group in ca]
    reverse = [{i for i,g in enumerate(ca) if group & g} for group in cb]
    if any(len(v) != 1 for v in links + reverse):
        failures.append('jamo component correspondence changed')
    if iou < .85: failures.append('shape overlap below 0.85')
    return dict(character=char, actual_size=actual.size, reference_size=ref.size,
                aspect_ratio=round(aspect,4), iou=round(iou,4),
                components=len(ca), reference_components=len(cb), failures=failures,
                gap_columns=0)
