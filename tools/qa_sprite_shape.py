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
