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


# The seven LARGE mode plates share one 19px ink height and bottom baseline.
# The native white field ends at y=22; origin y=2 leaves rows 21 and 22 clear.
PLATE_HEIGHT = 19
PLATE_ORIGIN = (6, 2)
PLATE_LABELS = ('캠페인', '자유전', '상점', '편집', '통신', '트라이얼', '사운드룸')
# At this size the uniform outline closes the second counter of ㅌ/ㄹ.
# Open a single row without moving the strokes or scaling either axis.
# The middle bar is necessarily 1px in this seven-row initial; the outer
# bars and vertical stems retain 2px or more wherever the geometry allows.
PLATE_CLEAR_PIXELS = {
    '통': tuple((x, 4) for x in range(4, 9)),
    '룸': tuple((x, 4) for x in range(3, 8)),
}


def plate_glyph(char):
    source = outline_alpha(char)
    width = max(1, round(source.width * PLATE_HEIGHT / source.height))
    mask = glyph(char, width, PLATE_HEIGHT).copy()
    for xy in PLATE_CLEAR_PIXELS.get(char, ()):
        if not mask.getpixel(xy):
            raise aw_fonts.FontFitError(f'plate counter correction drift: {char!r} {xy}')
        mask.putpixel(xy, 0)
    return mask


def verify_plate_ink(layer, text):
    """Compare EVERY final syllable with a complete, unclipped glyph.

    The independent shape oracle additionally checks the unedited font raster.
    This guard checks bounds and whole-mask equality, including the bottom
    rows which a tight cropped/reference-height comparison cannot protect.
    """
    mask, records = plate_line(text)
    ox, oy = PLATE_ORIGIN
    expected = Image.new('L', layer.size)
    expected.paste(mask, (ox, oy))
    actual = layer.point(lambda v: 255 if v == 5 else 0)
    # Exclude the native colored caption strip, but no main-text row.
    actual = actual.crop((0, 0, 128, 23))
    if actual.tobytes() != expected.crop((0, 0, 128, 23)).tobytes():
        raise aw_fonts.FontFitError(f'clipped or changed plate ink: {text!r}')
    for char, (a, b, c, d) in records:
        ref = plate_glyph(char)
        box = ref.getbbox()
        if box is None or not (4 <= ox+a+box[0] < ox+a+box[2] <= 124 and
                               2 <= oy+b+box[1] < oy+b+box[3] <= 21):
            raise aw_fonts.FontFitError(f'plate glyph outside white field: {char!r}')
        if actual.crop((ox+a, oy+b, ox+c, oy+d)).tobytes() != ref.tobytes():
            raise aw_fonts.FontFitError(f'incomplete plate syllable: {char!r}')
    return records


def plate_line(text, width=116, height=PLATE_HEIGHT, spacing=3):
    """One shared height/baseline, natural aspect ratios, complete syllables."""
    if height != PLATE_HEIGHT or text not in PLATE_LABELS:
        raise aw_fonts.FontFitError(f'unsupported LARGE plate profile: {text!r} {height}')
    glyphs = [plate_glyph(ch) for ch in text]
    used = sum(g.width for g in glyphs) + spacing * (len(text) - 1)
    if used > width:
        raise aw_fonts.FontFitError(f'plate cannot fit natural glyphs: {text!r}')
    mask = Image.new('L', (width, height))
    x = (width - used) // 2
    records = []
    for ch, ink in zip(text, glyphs):
        mask.paste(ink, (x, 0))
        records.append((ch, (x, 0, x+ink.width, height)))
        x += ink.width + spacing
    return mask, records
