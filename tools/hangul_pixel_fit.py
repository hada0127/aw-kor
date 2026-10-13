"""Natural-proportion OkDanDan rasterization with final ink/gap checks.

Legacy column fitting remains only for explicitly sized bitmap consumers.

Historical b13 method (retired for outline text):

The source is the pinned OkDanDan outline at 96px. Each destination column
samples its source column and fits alternating ink/gap runs by least squared
boundary displacement. Every internal run gets at least one pixel; outer
whitespace may disappear. Unlike thresholded downsampling, a thin counter
cannot silently close. Impossible targets fail rather than drop a stroke.
The returned reference witnesses allow a separate final-palette QA check.
"""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
import aw_fonts


def runs(values):
    result = []
    for i, value in enumerate(values):
        value = bool(value)
        if not result or result[-1][0] != value:
            result.append([value, i, i + 1])
        else:
            result[-1][2] = i + 1
    return result


@lru_cache(maxsize=1024)
def reference(char):
    font = ImageFont.truetype(aw_fonts.okdandan_path(), 96)
    image = Image.new('L', (192, 192))
    ImageDraw.Draw(image).text((12, 0), char, font=font, fill=255)
    image = image.point(lambda v: 255 if v >= 128 else 0)
    if not image.getbbox():
        raise aw_fonts.FontFitError(f'empty outline glyph: {char!r}')
    return image.crop(image.getbbox())


def fit_column(values, height):
    parts = runs(values)
    if not any(v for v, _, _ in parts):
        return [0] * height
    # Dynamic programming: optimal integer run boundaries, preserving topology.
    n = len(values)
    states = {0: (0.0, [])}
    for i, (ink, start, end) in enumerate(parts):
        minimum = 1 if ink or 0 < i < len(parts) - 1 else 0
        remaining = sum(1 for j, (v, _, _) in enumerate(parts[i + 1:], i + 1)
                        if v or 0 < j < len(parts) - 1)
        nxt = {}
        for left, (cost, bounds) in states.items():
            for right in range(left + minimum, height - remaining + 1):
                if i == len(parts) - 1 and right != height:
                    continue
                score = cost + (right - end * height / n) ** 2
                if right not in nxt or score < nxt[right][0]:
                    nxt[right] = (score, bounds + [right])
        states = nxt
    if height not in states:
        raise aw_fonts.FontFitError(f'{len(parts)} alternating runs cannot fit {height}px')
    output = []
    for (ink, _, _), end in zip(parts, states[height][1]):
        output.extend([255 if ink else 0] * (end - len(output)))
    return output


@lru_cache(maxsize=1024)
def outline_alpha(char):
    # Keep coverage until the final uniform downsample; never fit columns.
    font = ImageFont.truetype(aw_fonts.okdandan_path(), 384)
    image = Image.new('L', (768, 768))
    ImageDraw.Draw(image).text((20, 0), char, font=font, fill=255)
    box = image.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if box is None:
        raise aw_fonts.FontFitError(f'empty glyph: {char!r}')
    return image.crop(box)


@lru_cache(maxsize=4096)
def glyph(char, width, height):
    """Uniformly scale the outline to fit; unused allocation stays empty."""
    if min(width, height) < 1:
        raise aw_fonts.FontFitError('empty glyph allocation')
    source = outline_alpha(char)
    h = height
    while h > 0 and max(1, round(source.width * h / source.height)) > width:
        h -= 1
    if not h:
        raise aw_fonts.FontFitError(f'glyph cannot fit: {char!r}')
    w = max(1, round(source.width * h / source.height))
    mask = source.resize((w, h), Image.Resampling.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    result = Image.new('L', (width, height))
    result.paste(mask, ((width - w) // 2, (height - h) // 2))
    return result


def verify_glyph(char, mask):
    """Final ink/gap columns against a uniformly scaled reference raster.

    Unlike the retired per-column fitting oracle, whitespace in the allocation
    does not change the expected glyph proportions. Shape QA independently
    checks aspect, overlap and connected components.
    """
    box = mask.getbbox()
    if box is None:
        return dict(character=char, gap_columns=0, failures=['empty glyph'])
    actual = mask.crop(box)
    source = outline_alpha(char)
    w = max(1, round(source.width * actual.height / source.height))
    expected = source.resize((w, actual.height), Image.Resampling.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    expected = expected.crop(expected.getbbox())
    failures=[]; checked=0
    for x in range(max(actual.width, expected.width)):
        want = [expected.getpixel((x,y)) if x < expected.width else 0 for y in range(expected.height)]
        got = [actual.getpixel((x,y)) if x < actual.width else 0 for y in range(actual.height)]
        nr = sum(v for v,_,_ in runs(want)); na = sum(v for v,_,_ in runs(got))
        checked += nr >= 2
        if nr != na:
            failures.append(dict(x=x, expected_strokes=nr, actual_strokes=na))
    return dict(character=char, gap_columns=checked, failures=failures)


def line(text, width, height, spacing=2):
    """Natural font metrics at one point size, centered inside an allocation."""
    for size in range(height * 2, 0, -1):
        font = ImageFont.truetype(aw_fonts.okdandan_path(), size)
        canvas = (round(font.getlength(text)) + (len(text)+4)*size, size*4)
        mask, records = native_mask(text, font, canvas, (size,size), spacing)
        box = mask.getbbox()
        if box and box[2]-box[0] <= width and box[3]-box[1] <= height:
            break
    else:
        raise aw_fonts.FontFitError(f'label cannot fit: {text!r}')
    result = Image.new('L', (width,height))
    dx = (width-(box[2]-box[0]))//2-box[0]
    dy = (height-(box[3]-box[1]))//2-box[1]
    result.paste(mask,(dx,dy))
    return result, [(ch,(a+dx,b+dy,c+dx,d+dy)) for ch,(a,b,c,d) in records]


def dense_syllable(char):
    if not '\uac00' <= char <= '\ud7a3':
        return False
    n = ord(char) - 0xac00
    initial = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'[n // 588]
    final = ('', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ',
             'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ')[n % 28]
    return initial in 'ㄸㄹㅂㅃㅆㅊㅌㅍㅎ' or any(c in final for c in 'ㄹㅂㅆㅌㅍㅎ')


def native_mask(text, font, canvas_size, origin=(0, 0), spacing=1):
    """Keep baseline/font metrics while fitting each outline on integer pixels."""
    image = Image.new('L', canvas_size)
    records = []
    x, y = map(round, origin)
    for char in text:
        if not char.isspace():
            probe = Image.new('L', (font.size * 3, font.size * 3))
            ImageDraw.Draw(probe).text((font.size, 0), char, font=font, fill=255)
            probe = probe.point(lambda v: 255 if v >= 128 else 0)
            box = probe.getbbox()
            if not box:
                raise aw_fonts.FontFitError(f'empty native glyph: {char!r}')
            left, top = x + box[0] - font.size, y + box[1]
            w, h = box[2] - box[0], box[3] - box[1]
            if left < 0 or top < 0 or left + w > image.width or top + h > image.height:
                raise aw_fonts.FontFitError(f'clipped glyph: {char!r}')
            image.paste(glyph(char, w, h), (left, top))
            records.append((char, (left, top, left + w, top + h)))
        x += round(font.getlength(char)) + spacing
    return image, records


def paint_native(layer, text, font, origin, fill, outline=None, shadow=None,
                 shadow_offset=(1, 1), spacing=1):
    """Paint exact palette indices and validate final dense-syllable counters."""
    from PIL import ImageFilter
    body, records = native_mask(text, font, layer.size, origin, spacing)
    contour = body.filter(ImageFilter.MaxFilter(3)) if outline is not None else body
    cast = Image.new('L', layer.size)
    cast.paste(contour, shadow_offset)
    for y in range(layer.height):
        for x in range(layer.width):
            if shadow is not None and cast.getpixel((x, y)):
                layer.putpixel((x, y), shadow)
            if outline is not None and contour.getpixel((x, y)):
                layer.putpixel((x, y), outline)
            if body.getpixel((x, y)):
                layer.putpixel((x, y), fill)
    for char, box in records:
        if dense_syllable(char):
            crop = layer.crop(box)
            final_mask = Image.new('L', crop.size)
            final_mask.putdata([255 if v == fill else 0 for v in crop.getdata()])
            result = verify_glyph(char, final_mask)
            if result['failures']:
                raise aw_fonts.FontFitError(f'closed final palette gap: {text!r} {result}')
    return records


def paint_bitmap(layer, text, font, origin, fill, outline=None, shadow=None,
                 shadow_offset=(2, 2)):
    """Native monochrome Galmuri ink with separately composed palette effects.

    FreeType's stroked monochrome glyph mask can add disconnected fill pixels.
    Keep the unstroked font mask authoritative and dilate only its outline.
    """
    from PIL import ImageFilter
    body = Image.new('L', layer.size)
    draw = ImageDraw.Draw(body)
    draw.fontmode = '1'
    draw.text(origin, text, font=font, fill=255)
    contour = body.filter(ImageFilter.MaxFilter(3)) if outline is not None else body
    if shadow is not None:
        cast = Image.new('L', layer.size); cast.paste(contour, shadow_offset)
        layer.paste(shadow, (0, 0), cast)
    if outline is not None:
        layer.paste(outline, (0, 0), contour)
    layer.paste(fill, (0, 0), body)
    x, y = origin
    records = []
    for i, char in enumerate(text):
        if char.isspace(): continue
        start = x + font.getlength(text[:i])
        box = draw.textbbox((start, y), char, font=font)
        records.append((char, (round(start), box[1],
                              round(x + font.getlength(text[:i + 1])), box[3])))
    return records


# Part 2 LARGE mode plates (2026-10-13 b19): JP lettering treatment with
# Hada Sans Bold. Measured on the original plates (0x5B7930..0x5B8B20): every
# JP word fills x=4..123 and y=2..21 (120x20 band). Letter bodies use palette
# indices 5..12 (one per JP letter, left to right; the menu animates them), and
# rounded edges use the two light shades 3 and 2 on the white field (index 1).
# Korean: one 20px cap band, the outline set wider before rasterization
# (horizontal scale <= PLATE_MAX_WIDTH_SCALE, declared per label so the shape
# oracle still rejects any other anisotropy), a topology-safe 1px emboldening
# from the same outline's coverage, x-band body indices 5..12 and AA 2/3.
PLATE_HEIGHT = 20
PLATE_ORIGIN = (4, 2)
PLATE_WIDTH = 120
PLATE_LABELS = ('캠페인', '자유전', '상점', '편집', '통신', '트라이얼', '사운드룸')
PLATE_MAX_WIDTH_SCALE = 1.9    # declared wide setting; shape oracle checks it
PLATE_MIN_GAP = 2
PLATE_MAX_GAP = 8
PLATE_AA_LEVELS = ((80, 3), (30, 2))   # guide coverage -> JP edge shade index
PLATE_BODY_INDICES = tuple(range(5, 13))


def plate_body_index(x):
    """JP x-band body index for an absolute plate column."""
    return 5 + min(7, max(0, x - PLATE_ORIGIN[0]) * 8 // PLATE_WIDTH)


def plate_syllable_indices(text):
    """JP gives each letter one body index 5..12 left to right (the menu
    animates them). Each Korean syllable gets the band index of its center
    column, so the sweep still runs left to right (b20: one index per glyph
    also keeps the LZ77 payload inside the native allocations)."""
    _, records = plate_line(text)
    return [plate_body_index(PLATE_ORIGIN[0] + (a + c) // 2) for _, (a, _, c, _) in records]


@lru_cache(maxsize=256)
def plate_outline_alpha(char):
    font = ImageFont.truetype(aw_fonts.hadasans_path(), 384)
    image = Image.new('L', (768, 768))
    ImageDraw.Draw(image).text((20, 0), char, font=font, fill=255)
    box = image.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if box is None:
        raise aw_fonts.FontFitError(f'empty Hada Sans glyph: {char!r}')
    return image.crop(box)


def _components(pixels):
    groups = 0
    pixels = set(pixels)
    while pixels:
        stack = [pixels.pop()]
        groups += 1
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    p = (x + dx, y + dy)
                    if p in pixels:
                        pixels.remove(p)
                        stack.append(p)
    return groups


def plate_topology(mask):
    """(8-connected ink components, enclosed counters) of a binary mask."""
    w, h = mask.size
    px = mask.load()
    ink = {(x, y) for y in range(h) for x in range(w) if px[x, y]}
    # Background is 4-connected (dual of 8-connected ink); pad one pixel.
    bg = {(x, y) for y in range(-1, h + 1) for x in range(-1, w + 1) if (x, y) not in ink}
    regions = 0
    while bg:
        stack = [bg.pop()]
        regions += 1
        while stack:
            x, y = stack.pop()
            for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if p in bg:
                    bg.remove(p)
                    stack.append(p)
    return _components(ink), regions - 1


@lru_cache(maxsize=256)
def plate_outline_topology(char):
    src = plate_outline_alpha(char)
    probe = src.resize((max(1, src.width // 4), max(1, src.height // 4)), Image.Resampling.BOX)
    return plate_topology(probe.point(lambda v: 255 if v >= 128 else 0))


@lru_cache(maxsize=256)
def _plate_outline_pair(char):
    """Bold and Black outlines drawn at the same origin, cropped to one box.

    Returns (bold, black, bold_box) where bold_box is the Bold ink bbox
    inside the shared union box.
    """
    images = []
    for path in (aw_fonts.hadasans_path(), aw_fonts.hadasans_black_path()):
        font = ImageFont.truetype(path, 384)
        image = Image.new('L', (900, 768))
        ImageDraw.Draw(image).text((60, 0), char, font=font, fill=255)
        images.append(image)
    boxes = [im.point(lambda v: 255 if v >= 128 else 0).getbbox() for im in images]
    if None in boxes:
        raise aw_fonts.FontFitError(f'empty Hada Sans glyph: {char!r}')
    bold_box = boxes[0]
    union = (min(boxes[0][0], boxes[1][0]), bold_box[1], max(boxes[0][2], boxes[1][2]), bold_box[3])
    inner = (bold_box[0] - union[0], 0, bold_box[2] - union[0], bold_box[3] - bold_box[1])
    return images[0].crop(union), images[1].crop(union), inner


def plate_glyph_width(char, scale):
    """Width (px) of the union box at the declared scale (upper bound of ink)."""
    bold, _, _ = _plate_outline_pair(char)
    return max(1, round(bold.width * PLATE_HEIGHT * scale / bold.height))


def _column_runs(cells, w, h):
    return [sum(v for v, _, _ in runs([(x, y) in cells for y in range(h)])) for x in range(w)]


def _row_runs(cells, w, h):
    return [sum(v for v, _, _ in runs([(x, y) in cells for x in range(w)])) for y in range(h)]


@lru_cache(maxsize=1024)
def _plate_raster(char, scale):
    """(body mask, weight-guide coverage), cropped to the body's columns.

    Body = Hada Sans Bold raster at the declared scale, grown toward the
    Hada Sans Black outline of the same glyph (b20 JP-weight treatment). A
    guide pixel joins only when it is 4-adjacent to the body, outside every
    enclosed Bold counter, keeps every column's and row's stroke count (no
    gap closes, so each gap stays >= 1px) and keeps the outline's 8-connected
    jamo components and counters. Bold jamo shapes and counters survive.
    """
    bold, black, inner = _plate_outline_pair(char)
    H = PLATE_HEIGHT
    W = plate_glyph_width(char, scale)
    strict = bold.resize((W, H), Image.Resampling.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    guide = black.resize((W, H), Image.Resampling.LANCZOS)
    sp, gp = strict.load(), guide.load()
    body = {(x, y) for y in range(H) for x in range(W) if sp[x, y]}

    def as_mask(cells):
        mask = Image.new('L', (W, H))
        for xy in cells:
            mask.putpixel(xy, 255)
        return mask

    want = plate_outline_topology(char)
    if plate_topology(as_mask(body)) != want:
        raise aw_fonts.FontFitError(f'plate raster merges jamo or counters: {char!r} {scale}')
    outside = set()
    stack = [(x, y) for x in range(W) for y in (0, H - 1)] + [(x, y) for y in range(H) for x in (0, W - 1)]
    stack = [p for p in stack if p not in body]
    outside.update(stack)
    while stack:
        x, y = stack.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= q[0] < W and 0 <= q[1] < H and q not in outside and q not in body:
                outside.add(q)
                stack.append(q)
    cols, rows = _column_runs(body, W, H), _row_runs(body, W, H)
    cands = sorted(((gp[x, y], -y, -x) for y in range(H) for x in range(W)
                    if (x, y) not in body and (x, y) in outside and gp[x, y] >= 128), reverse=True)
    changed = True
    while changed:
        changed = False
        for _, ny, nx in cands:
            x, y = -nx, -ny
            if (x, y) in body or not any(q in body for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
                continue
            trial = body | {(x, y)}
            if (sum(v for v, _, _ in runs([(x, yy) in trial for yy in range(H)])) != cols[x] or
                    sum(v for v, _, _ in runs([(xx, y) in trial for xx in range(W)])) != rows[y]):
                continue
            if plate_topology(as_mask(trial)) != want:
                continue
            body = trial
            changed = True
    mask = as_mask(body)
    x0, _, x1, _ = mask.getbbox()
    return mask.crop((x0, 0, x1, H)), guide.crop((x0, 0, x1, H))


def plate_glyph(char, scale=1.0):
    """Final binary body of one plate syllable (see _plate_raster)."""
    return _plate_raster(char, scale)[0]


def plate_coverage(char, scale):
    """Weight-guide (Hada Sans Black) coverage aligned with plate_glyph."""
    return _plate_raster(char, scale)[1]


@lru_cache(maxsize=64)
def plate_width_scale(text):
    """Widest declared outline scale (<= max) whose line fits 120px."""
    if text not in PLATE_LABELS:
        raise aw_fonts.FontFitError(f'unsupported LARGE plate profile: {text!r}')
    best = None
    for step in range(100, round(PLATE_MAX_WIDTH_SCALE * 100) + 1):
        scale = step / 100
        used = sum(plate_glyph_width(ch, scale) for ch in text) + PLATE_MIN_GAP * (len(text) - 1)
        if used <= PLATE_WIDTH:
            best = scale
    if best is None:
        raise aw_fonts.FontFitError(f'plate cannot fit natural glyphs: {text!r}')
    return best


def plate_line(text, width=PLATE_WIDTH, height=PLATE_HEIGHT):
    """Body mask and syllable boxes inside the 120x20 band (band coordinates)."""
    if height != PLATE_HEIGHT or width != PLATE_WIDTH or text not in PLATE_LABELS:
        raise aw_fonts.FontFitError(f'unsupported LARGE plate profile: {text!r} {height}')
    scale = plate_width_scale(text)
    glyphs = [plate_glyph(ch, scale) for ch in text]
    natural = sum(g.width for g in glyphs)
    gap = min(PLATE_MAX_GAP, (width - natural) // max(1, len(text) - 1)) if len(text) > 1 else 0
    if gap < PLATE_MIN_GAP:
        raise aw_fonts.FontFitError(f'plate cannot fit natural glyphs: {text!r}')
    used = natural + gap * (len(text) - 1)
    mask = Image.new('L', (width, height))
    x = (width - used) // 2
    records = []
    for ch, ink in zip(text, glyphs):
        mask.paste(ink, (x, 0))
        records.append((ch, (x, 0, x + ink.width, height)))
        x += ink.width + gap
    return mask, records


def plate_shades(text):
    """{(x, y): index} JP edge shades (band coordinates), never inside a 1px gap."""
    mask, records = plate_line(text)
    scale = plate_width_scale(text)
    body = mask.load()
    # Shade only the outer contour: a pixel inside an enclosed counter stays
    # white (JP shades rounded outer corners, never counter interiors).
    outside = set()
    stack = [(x, y) for x in range(mask.width) for y in (0, mask.height - 1)] + \
            [(x, y) for y in range(mask.height) for x in (0, mask.width - 1)]
    stack = [p for p in stack if not body[p]]
    outside.update(stack)
    while stack:
        x, y = stack.pop()
        for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= p[0] < mask.width and 0 <= p[1] < mask.height and p not in outside and not body[p]:
                outside.add(p)
                stack.append(p)
    shades = {}
    for ch, (a, b, c, d) in records:
        cov = plate_coverage(ch, scale).load()
        for y in range(b, d):
            for x in range(a, c):
                v = cov[x - a, y - b]
                if body[x, y] or v < PLATE_AA_LEVELS[-1][0] or (x, y) not in outside:
                    continue
                def ink(px, py):
                    return 0 <= px < mask.width and 0 <= py < mask.height and body[px, py]
                if (ink(x - 1, y) and ink(x + 1, y)) or (ink(x, y - 1) and ink(x, y + 1)):
                    continue
                shades[(x, y)] = next(i for level, i in PLATE_AA_LEVELS if v >= level)
    return shades


def paint_plate(layer, text):
    """Paint body (per-syllable JP index 5..12) and edge shades (3/2) into a 128x32 layer."""
    mask, records = plate_line(text)
    ox, oy = PLATE_ORIGIN
    px = layer.load()
    for (x, y), idx in plate_shades(text).items():
        px[ox + x, oy + y] = idx
    body = mask.load()
    for idx, (_, (a, b, c, d)) in zip(plate_syllable_indices(text), records):
        for y in range(b, d):
            for x in range(a, c):
                if body[x, y]:
                    px[ox + x, oy + y] = idx
    return records


def verify_plate_ink(layer, text):
    """Compare EVERY final syllable with a complete, unclipped glyph.

    Checks the whole 128x23 text field: body mask (indices 5..12) equals the
    renderer, each body pixel carries its syllable's JP index, and edge shades 2/3
    appear only where the renderer placed them.
    """
    mask, records = plate_line(text)
    ox, oy = PLATE_ORIGIN
    expected = Image.new('L', layer.size)
    expected.paste(mask, (ox, oy))
    actual = layer.point(lambda v: 255 if v in PLATE_BODY_INDICES else 0)
    # Exclude the native colored caption strip, but no main-text row.
    if actual.crop((0, 0, 128, 23)).tobytes() != expected.crop((0, 0, 128, 23)).tobytes():
        raise aw_fonts.FontFitError(f'clipped or changed plate ink: {text!r}')
    shades = {(ox + x, oy + y): i for (x, y), i in plate_shades(text).items()}
    band = {}
    for idx, (_, (a, b, c, d)) in zip(plate_syllable_indices(text), records):
        for x in range(a, c):
            band[ox + x] = idx
    for y in range(oy, oy + PLATE_HEIGHT):
        for x in range(ox, ox + PLATE_WIDTH):
            v = layer.getpixel((x, y))
            if v in PLATE_BODY_INDICES and v != band.get(x):
                raise aw_fonts.FontFitError(f'plate body index changed: {text!r} {(x, y)}')
            if v in (2, 3) and shades.get((x, y)) != v:
                raise aw_fonts.FontFitError(f'plate edge shade changed: {text!r} {(x, y)}')
            if (x, y) in shades and v != shades[(x, y)]:
                raise aw_fonts.FontFitError(f'plate edge shade missing: {text!r} {(x, y)}')
    scale = plate_width_scale(text)
    for char, (a, b, c, d) in records:
        ref = plate_glyph(char, scale)
        box = ref.getbbox()
        if box is None or not (4 <= ox+a+box[0] < ox+a+box[2] <= 124 and
                               2 <= oy+b+box[1] < oy+b+box[3] <= 22):
            raise aw_fonts.FontFitError(f'plate glyph outside white field: {char!r}')
        if actual.crop((ox+a, oy+b, ox+c, oy+d)).tobytes() != ref.tobytes():
            raise aw_fonts.FontFitError(f'incomplete plate syllable: {char!r}')
    return records
