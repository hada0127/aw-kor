#!/usr/bin/env python3
"""Patch the title screen OBJ logo tiles with an OkDanDan Korean draft.

This targets the first title screen only. The title screen uses BG0 for the
camo background and OBJ tiles for the foreground logo, "1+2", PRESS START, and
copyright text. The compressed OBJ tile block at 0x22B2C is copied verbatim to
OBJ VRAM 0x06010000, so this script edits the decompressed tile block and
recompresses it in place.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lz77_compress import lz77_compress
from lz77_scan import lz77_decompress
from bdf import glyph_grid, load_bdf


TITLE_OBJ_LZ77_OFF = 0x00022B2C
SELECT_OBJ_LZ77_OFF = 0x00024A34
PART1_TITLE_OBJ_LZ77_OFF = 0x00C38BF8
PART2_TITLE_OBJ_LZ77_OFF = 0x004EAF6C
PART1_CATHERINE_NAME_LZ77_OFF = 0x00C102A8
PART1_MISSION_LOGO_LZ77_OFF = 0x00C18738
PART1_OPERATION_LOGO_LZ77_OFF = 0x00C18CB4
PART1_MAP_SELECT_LZ77_OFF = 0x00C18F48
PART1_SHOP_SELECT_LZ77_OFF = 0x00C191E0
PART1_HARD_SHOP_LZ77_OFF = 0x00C194D8
PART1_CAMPAIGN_LZ77_OFF = 0x00C19794
PART1_MODE_SELECT_LZ77_OFF = 0x00C19A9C
PART1_RULE_SELECT_LZ77_OFF = 0x00C19D14
PART1_TEAM_SETTING_LZ77_OFF = 0x00C19FF0
PART1_MODE_OPTION_BLOCKS = [
    ("campaign", 0x00C0310C, "캠페인", 30),
    ("trial", 0x00C03510, "트라이얼", 24),
    ("record", 0x00C03880, "기록", 28),
    ("operation_room", 0x00C03AF0, "작전룸", 28),
    ("wars_shop", 0x00C03F68, "상점", 28),
    ("map_design", 0x00C043E0, "맵 디자인", 30),
    ("single_battle", 0x00C0489C, "대전", 30),
    ("new_game", 0x00C04D48, "처음부터", 30),
    ("continue", 0x00C051DC, "계속하기", 30),
    ("link", 0x00C05658, "통신", 28),
    ("map_record", 0x00C05994, "맵 기록", 28),
    ("player_rank", 0x00C05D78, "플레이어 랭크", 22),
    ("single_card", 0x00C06218, "1카드 통신", 28),
    ("multi_card", 0x00C0668C, "멀티카드 통신", 24),
    ("map_trade", 0x00C06B78, "맵 교환", 26),
]
FONT_PATH = Path.home() / "Library/Fonts/OkDanDan-Bold.otf"
BODY_FONT_PATH = Path("reference/fonts/Galmuri11-Condensed.ttf")
BODY_BOLD_FONT_PATH = Path("reference/fonts/Galmuri11-Bold.ttf")
SMALL_BDF_FONT_PATH = Path("reference/fonts/Galmuri7.bdf")

# Runtime OAM layout captured on the title screen. Lower OAM index draws above
# higher index for same priority, so these are the Japanese logo text overlays.
TEXT_SPRITES = (
    # idx, x, y, w, h, tile, obj_palette
    (27, 20, 20, 64, 32, 0x028, 1),
    (28, 84, 20, 64, 32, 0x048, 1),
    (29, 148, 20, 64, 32, 0x068, 1),
)

PROMPT_SPRITES = (
    (16, 56, 100, 32, 16, 0x168, 3),
    (17, 88, 100, 32, 16, 0x170, 3),
    (18, 120, 100, 32, 16, 0x178, 3),
    (19, 152, 100, 32, 16, 0x180, 3),
)

SELECT_TOP_TEXT_SPRITES = (
    (36, 12, 4, 64, 32, 0x000, 0),
    (37, 12, 36, 32, 16, 0x020, 0),
    (38, 44, 36, 32, 16, 0x028, 0),
    (39, 76, 4, 64, 32, 0x030, 0),
    (40, 140, 4, 64, 32, 0x050, 0),
    (41, 76, 36, 32, 16, 0x070, 0),
    (42, 108, 36, 32, 16, 0x078, 0),
    (43, 140, 36, 32, 16, 0x080, 0),
    (44, 172, 36, 32, 16, 0x088, 0),
)

SELECT_BOTTOM_TEXT_SPRITES = (
    (23, 24, 92, 64, 32, 0x172, 1),
    (24, 88, 92, 64, 32, 0x192, 1),
    (25, 152, 92, 64, 32, 0x1B2, 1),
)

SELECT_PROMPT_SPRITES = (
    (18, 19, 144, 32, 16, 0x2DC, 6),
    (19, 51, 144, 32, 16, 0x2E4, 6),
    (20, 83, 144, 32, 16, 0x2EC, 6),
    (21, 115, 144, 32, 16, 0x2F4, 6),
)

PART1_TITLE_TEXT_SPRITES = (
    (32, 16, 12, 64, 32, 0x318, 1),
    (33, 80, 12, 64, 32, 0x338, 1),
    (34, 144, 12, 64, 32, 0x358, 1),
    (35, 208, 12, 16, 32, 0x378, 1),
    (36, 16, 44, 32, 16, 0x380, 1),
    (37, 48, 44, 32, 16, 0x388, 1),
    (38, 80, 44, 32, 16, 0x390, 1),
    (39, 112, 44, 32, 16, 0x398, 1),
    (40, 144, 44, 32, 16, 0x3A0, 1),
    (41, 176, 44, 32, 16, 0x3A8, 1),
    (42, 208, 44, 8, 16, 0x3B0, 1),
)

PART1_PROMPT_SPRITES = (
    (21, 75, 107, 32, 16, 0x200, 2),
    (22, 107, 107, 32, 16, 0x208, 2),
    (23, 139, 107, 32, 16, 0x210, 2),
)

PART2_TITLE_TEXT_SPRITES = (
    (26, 16, 20, 64, 32, 0x0E8, 1),
    (27, 80, 20, 64, 32, 0x108, 1),
    (28, 144, 20, 64, 32, 0x128, 1),
)

PART2_PROMPT_SPRITES = (
    (21, 56, 100, 32, 16, 0x170, 3),
    (22, 88, 100, 32, 16, 0x178, 3),
    (23, 120, 100, 32, 16, 0x180, 3),
    (24, 152, 100, 32, 16, 0x188, 3),
)


def bgr555_to_rgb(value: int) -> tuple[int, int, int]:
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
    )


def load_obj_palettes_from(pal_path: Path) -> list[list[tuple[int, int, int]]]:
    """Use the known title PRAM captured by mGBA if available.

    The ROM block stores only tile pixels; palette data is loaded separately.
    For draft conversion we use a runtime PRAM dump from the title screen so
    pixel indices match what the game already displays.
    """
    if not pal_path.exists():
        raise FileNotFoundError(f"missing {pal_path}; run the runtime capture step first")
    pal_data = pal_path.read_bytes()
    palettes: list[list[tuple[int, int, int]]] = []
    for pal_no in range(16):
        base = 0x200 + pal_no * 32
        colors = [
            bgr555_to_rgb(struct.unpack_from("<H", pal_data, base + i * 2)[0])
            for i in range(16)
        ]
        palettes.append(colors)
    return palettes


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, stroke: int) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return box[2] - box[0], box[3] - box[1]


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int) -> ImageFont.FreeTypeFont:
    for size in range(33, 16, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 3)
        if w <= max_w and h <= max_h:
            return font
    return ImageFont.truetype(str(FONT_PATH), 17)


def make_logo_layer() -> Image.Image:
    """Render only the text overlay that fits the original OBJ rectangles."""
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"OkDanDan font not found: {FONT_PATH}")

    layer = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = "게임보이 워즈 어드밴스"
    font = fit_font(draw, text, 190, 36)
    w, h = text_bbox(draw, text, font, 3)
    x = 116 - w // 2
    y = 26

    draw_original_style_text(draw, (x, y), text, font)
    return layer


def draw_original_style_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    x, y = xy
    dark = (38, 58, 122, 255)
    deep = (26, 35, 100, 255)
    white = (255, 251, 226, 255)
    orange = (236, 122, 24, 255)
    yellow = (255, 207, 34, 255)
    draw.text((x + 1, y + 1), text, font=font, fill=deep, stroke_width=1, stroke_fill=deep)
    draw.text((x, y), text, font=font, fill=orange, stroke_width=1, stroke_fill=dark)
    draw.text((x, y - 1), text, font=font, fill=yellow, stroke_width=0)


def make_prompt_layer() -> Image.Image:
    layer = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = "시작하기!"
    for size in range(17, 10, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 1)
        if w <= 120 and h <= 14:
            break
    box = (68, 100, 172, 116)
    draw.rectangle(box, fill=(247, 255, 238, 255))
    draw.rectangle(box, outline=(83, 132, 120, 255), width=2)
    x = (box[0] + box[2]) // 2 - w // 2
    y = 101
    draw.text((x, y), text, font=font, fill=(45, 91, 137, 255), stroke_width=1, stroke_fill=(247, 255, 238, 255))
    return layer


def draw_fitted_logo_text(
    layer: Image.Image,
    text: str,
    center_x: int,
    y: int,
    max_w: int,
    max_h: int,
    start_size: int,
) -> None:
    draw = ImageDraw.Draw(layer)
    for size in range(start_size, 13, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 3)
        if w <= max_w and h <= max_h:
            break
    x = center_x - w // 2
    draw_original_style_text(draw, (x, y), text, font)


def make_select_layer() -> Image.Image:
    layer = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    draw_fitted_logo_text(layer, "게임보이 워즈 어드밴스", 116, 20, 188, 28, 24)
    draw_fitted_logo_text(layer, "게임보이 워즈 어드밴스", 120, 101, 188, 24, 22)

    draw = ImageDraw.Draw(layer)
    prompt = "게임 선택"
    for size in range(15, 9, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, prompt, font, 1)
        if w <= 118 and h <= 14:
            break
    x = 80 - w // 2
    y = 145
    draw.text((x, y), prompt, font=font, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
    return layer


def make_part1_title_layer() -> Image.Image:
    layer = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = "게임보이 워즈 어드밴스"
    for size in range(28, 14, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 1)
        if w <= 200 and h <= 34:
            break
    x = 116 - w // 2
    # Part 1 title uses a separate OBJ highlight layer; its palette does not
    # contain the orange body colors. Keep this layer highlight-like so the
    # title fade palette does not turn the replacement text black.
    draw.text((x + 1, 24 + 1), text, font=font, fill=(255, 238, 150, 255), stroke_width=0)
    draw.text((x, 24), text, font=font, fill=(255, 255, 245, 255), stroke_width=0)
    return layer


def make_part2_title_layer() -> Image.Image:
    layer = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    draw_fitted_logo_text(layer, "게임보이 워즈 어드밴스", 116, 25, 188, 28, 25)
    return layer


def nearest_palette_index(color: tuple[int, int, int, int], palette: list[tuple[int, int, int]]) -> int:
    if color[3] < 64:
        return 0
    r, g, b = color[:3]
    best_i = 1
    best_d = 1 << 60
    for i in range(1, 16):
        pr, pg, pb = palette[i]
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_i = i
            best_d = d
    return best_i


def encode_tile(indices: list[int]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = indices[y * 8 + x] & 0xF
            bi = y * 4 + x // 2
            if x & 1:
                out[bi] = (out[bi] & 0x0F) | (v << 4)
            else:
                out[bi] = (out[bi] & 0xF0) | v
    return bytes(out)


def draw_index_text(
    layer: Image.Image,
    text: str,
    center_x: int,
    y: int,
    max_w: int,
    max_h: int,
    start_size: int,
    outline_idx: int,
    shadow_idx: int,
    body_idx: int,
    hi_idx: int,
    aa_idx: int | None = None,
    stroke: int = 1,
) -> None:
    draw = ImageDraw.Draw(layer)
    for size in range(start_size, 12, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, stroke)
        if w <= max_w and h <= max_h:
            break
    x = center_x - w // 2
    paint_index_text_aa(layer, (x + 1, y + 1), text, font, shadow_idx, shadow_idx, stroke, aa_idx=shadow_idx)
    paint_index_text_aa(layer, (x, y), text, font, body_idx, outline_idx, stroke, aa_idx=aa_idx)
    if hi_idx != body_idx:
        paint_index_text_aa(layer, (x, y - 1), text, font, hi_idx, body_idx, 0, aa_idx=body_idx)


def index_for_alpha(alpha: int, fill_idx: int, edge_idx: int, aa_idx: int) -> int:
    if alpha >= 192:
        return fill_idx
    if alpha >= 96:
        return aa_idx
    if alpha >= 32:
        return edge_idx
    return 0


def paint_index_text_aa(
    layer: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_idx: int,
    stroke_idx: int,
    stroke_width: int,
    aa_idx: int | None = None,
) -> None:
    outline = Image.new("L", layer.size, 0)
    od = ImageDraw.Draw(outline)
    od.text(xy, text, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
    body = Image.new("L", layer.size, 0)
    bd = ImageDraw.Draw(body)
    bd.text(xy, text, font=font, fill=255)
    op = outline.load()
    bp = body.load()
    lp = layer.load()
    if aa_idx is None:
        aa_idx = fill_idx
    for yy in range(layer.height):
        for xx in range(layer.width):
            o = op[xx, yy]
            b = bp[xx, yy]
            if o:
                idx = index_for_alpha(o, stroke_idx, stroke_idx, stroke_idx)
                if idx:
                    lp[xx, yy] = idx
            if b:
                idx = index_for_alpha(b, fill_idx, stroke_idx, aa_idx)
                if idx:
                    lp[xx, yy] = idx


def paint_index_text(
    layer: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_idx: int,
    stroke_idx: int,
    stroke_width: int,
) -> None:
    # Render anti-aliased masks, then quantize to exact palette indices. Drawing
    # directly into an L image would treat intermediate alpha values as palette
    # indices, producing unintended colors.
    outline = Image.new("L", layer.size, 0)
    od = ImageDraw.Draw(outline)
    od.text(xy, text, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255)
    body = Image.new("L", layer.size, 0)
    bd = ImageDraw.Draw(body)
    bd.text(xy, text, font=font, fill=255, stroke_width=0)
    op = outline.load()
    bp = body.load()
    lp = layer.load()
    for yy in range(layer.height):
        for xx in range(layer.width):
            if op[xx, yy] >= 96:
                lp[xx, yy] = stroke_idx
            if bp[xx, yy] >= 96:
                lp[xx, yy] = fill_idx


def paint_index_text_crisp(
    layer: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_idx: int,
    outline_idx: int,
    inner_idx: int,
) -> None:
    """Draw text with exact-index, 1px outline and internal crease lines."""
    body = Image.new("L", layer.size, 0)
    bd = ImageDraw.Draw(body)
    bd.text(xy, text, font=font, fill=255)
    body = body.point(lambda v: 255 if v >= 96 else 0)
    dilated = body.filter(ImageFilter.MaxFilter(3))
    outline = ImageChops.subtract(dilated, body)
    # Thin top-left emphasis restores the original logo's crisp upper edge.
    upper = ImageChops.offset(body, -1, -1)
    upper = ImageChops.subtract(upper, body)
    # Internal vertical creases help letters like 보/워 read less blob-like.
    left_gap = ImageChops.offset(body, -1, 0)
    right_gap = ImageChops.offset(body, 1, 0)
    inner = ImageChops.multiply(left_gap, right_gap)
    inner = ImageChops.subtract(inner, body)
    inner = inner.point(lambda v: 255 if v >= 255 else 0)

    lp = layer.load()
    op = outline.load()
    up = upper.load()
    bp = body.load()
    ip = inner.load()
    for yy in range(layer.height):
        for xx in range(layer.width):
            if op[xx, yy] or up[xx, yy]:
                lp[xx, yy] = outline_idx
            if bp[xx, yy]:
                lp[xx, yy] = fill_idx
            if ip[xx, yy]:
                lp[xx, yy] = inner_idx


def make_title_index_layer() -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    draw_index_text(layer, "게임보이 워즈 어드밴스", 116, 26, 190, 30, 25, 1, 11, 4, 4, aa_idx=10, stroke=1)
    draw_boxed_start_index(layer, "시작하기!", (68, 100, 172, 116))
    return layer


def make_select_index_layer() -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    # Top logo uses palette 0, whose bright body colors are indices 2..12.
    draw_index_text(layer, "게임보이 워즈 어드밴스", 116, 20, 188, 28, 24, 15, 14, 8, 8, aa_idx=10, stroke=1)
    # Bottom logo uses palette 1 and keeps the original "2" sprite.
    draw_index_text(layer, "게임보이 워즈 어드밴스", 120, 99, 188, 24, 22, 1, 11, 4, 4, aa_idx=10, stroke=1)
    draw_prompt_plain_index(layer, "게임 선택", (20, 144, 144, 160), 6, 1, 10, aa_idx=15)
    return layer


def make_part1_index_layer() -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    # Part 1 uses a different OBJ palette from 1+2/Part 2. Stable title-frame
    # sampling shows: dark outline=15, gray shade=14, orange body=8..12,
    # yellow highlight=2..3.
    draw_index_text(layer, "게임보이 워즈 어드밴스", 116, 24, 200, 34, 27, 15, 14, 8, 2, aa_idx=10, stroke=1)
    draw_part1_start_index(layer, "시작하기!", (75, 107, 171, 123))
    return layer


def make_part2_index_layer() -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    draw_index_text(layer, "게임보이 워즈 어드밴스", 116, 25, 188, 28, 24, 1, 11, 4, 4, aa_idx=10, stroke=1)
    draw_boxed_start_index(layer, "시작하기!", (68, 100, 172, 116))
    return layer


def draw_prompt_index(layer: Image.Image, text: str, box: tuple[int, int, int, int], _pal_no: int) -> None:
    draw_boxed_start_index(layer, text, box)


def draw_boxed_start_index(layer: Image.Image, text: str, box: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(layer)
    # 1+2 title and Part 2 title: pale fill, blue border, white text with blue edge.
    draw.rectangle(box, fill=12)
    draw.rectangle(box, outline=14, width=2)
    draw_blocky_prompt_index(layer, text, box, fill_idx=1, stroke_idx=14, aa_idx=10)


def draw_blocky_prompt_index(
    layer: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    fill_idx: int,
    stroke_idx: int,
    aa_idx: int,
) -> None:
    draw = ImageDraw.Draw(layer)
    for size in range(13, 8, -1):
        font = ImageFont.truetype(str(BODY_BOLD_FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 1)
        # Drawn twice horizontally to mimic the original block lettering.
        if w + 1 <= (box[2] - box[0] - 6) and h <= (box[3] - box[1] - 2):
            break
    x = (box[0] + box[2]) // 2 - (w + 1) // 2
    y = box[1] + ((box[3] - box[1]) - h) // 2 + 1
    paint_index_text_aa(layer, (x, y), text, font, fill_idx, stroke_idx, 1, aa_idx=aa_idx)
    paint_index_text_aa(layer, (x + 1, y), text, font, fill_idx, stroke_idx, 1, aa_idx=aa_idx)


def draw_part1_start_index(layer: Image.Image, text: str, box: tuple[int, int, int, int]) -> None:
    # Part 1 title: no box. White text, dark outline, brown/orange drop shadow.
    draw = ImageDraw.Draw(layer)
    font = fit_prompt_font(draw, text, box, bold=True)
    w, h = text_bbox(draw, text, font, 1)
    x = (box[0] + box[2]) // 2 - w // 2
    y = box[1] + ((box[3] - box[1]) - h) // 2 - 1
    paint_index_text_aa(layer, (x + 1, y + 1), text, font, 9, 9, 1, aa_idx=9)
    paint_index_text_aa(layer, (x, y), text, font, 1, 14, 1, aa_idx=3)


def fit_prompt_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    bold: bool = False,
) -> ImageFont.FreeTypeFont:
    font_path = BODY_BOLD_FONT_PATH if bold else BODY_FONT_PATH
    for size in range(13, 7, -1):
        font = ImageFont.truetype(str(font_path), size)
        w, h = text_bbox(draw, text, font, 1)
        if w <= (box[2] - box[0] - 6) and h <= (box[3] - box[1] - 2):
            return font
    return ImageFont.truetype(str(font_path), 8)


def draw_prompt_plain_index(
    layer: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    _pal_no: int,
    stroke_idx: int,
    fill_idx: int,
    aa_idx: int | None = None,
    bold: bool = False,
) -> None:
    draw = ImageDraw.Draw(layer)
    font = fit_prompt_font(draw, text, box, bold=bold)
    w, h = text_bbox(draw, text, font, 1)
    x = (box[0] + box[2]) // 2 - w // 2
    y = box[1] + ((box[3] - box[1]) - h) // 2 - 1
    paint_index_text_aa(layer, (x, y), text, font, fill_idx, stroke_idx, 1, aa_idx=aa_idx or fill_idx)


def patch_sprite_index_layer(
    tile_data: bytearray,
    layer: Image.Image,
    sprites: tuple[tuple[int, int, int, int, int, int, int], ...],
    tile_subtract: int = 0,
) -> None:
    px = layer.load()
    for _idx, sx, sy, w, h, base_tile, _pal_no in sprites:
        cols = w // 8
        rows = h // 8
        for ty in range(rows):
            for tx in range(cols):
                indices: list[int] = []
                for py in range(8):
                    for px_x in range(8):
                        indices.append(int(px[sx + tx * 8 + px_x, sy + ty * 8 + py]) & 0xF)
                tile_no = base_tile - tile_subtract + ty * cols + tx
                if tile_no < 0:
                    continue
                tile_data[tile_no * 32 : tile_no * 32 + 32] = encode_tile(indices)


def patch_sprite_tiles(
    tile_data: bytearray,
    layer: Image.Image,
    palettes: list[list[tuple[int, int, int]]],
    sprites: tuple[tuple[int, int, int, int, int, int, int], ...],
    tile_subtract: int = 0,
) -> None:
    px = layer.load()
    for _idx, sx, sy, w, h, base_tile, pal_no in sprites:
        cols = w // 8
        rows = h // 8
        palette = palettes[pal_no]
        for ty in range(rows):
            for tx in range(cols):
                indices: list[int] = []
                for py in range(8):
                    for px_x in range(8):
                        color = px[sx + tx * 8 + px_x, sy + ty * 8 + py]
                        indices.append(nearest_palette_index(color, palette))
                tile_no = base_tile - tile_subtract + ty * cols + tx
                if tile_no < 0:
                    continue
                tile_data[tile_no * 32 : tile_no * 32 + 32] = encode_tile(indices)


def block_to_tiles(layer: Image.Image) -> bytes:
    out = bytearray()
    px = layer.load()
    for ty in range(layer.height // 8):
        for tx in range(layer.width // 8):
            indices: list[int] = []
            for py in range(8):
                for px_x in range(8):
                    indices.append(int(px[tx * 8 + px_x, ty * 8 + py]) & 0xF)
            out += encode_tile(indices)
    return bytes(out)


def draw_centered_block_text(
    layer: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    max_size: int,
    fill_idx: int,
    stroke_idx: int,
    aa_idx: int,
    bold: bool = True,
) -> None:
    draw = ImageDraw.Draw(layer)
    font_path = BODY_BOLD_FONT_PATH if bold and BODY_BOLD_FONT_PATH.exists() else BODY_FONT_PATH
    for size in range(max_size, 6, -1):
        font = ImageFont.truetype(str(font_path), size)
        w, h = text_bbox(draw, text, font, 1)
        if w <= box[2] - box[0] and h <= box[3] - box[1]:
            break
    x = (box[0] + box[2] - w) // 2
    y = (box[1] + box[3] - h) // 2 - 1
    paint_index_text_aa(layer, (x, y), text, font, fill_idx, stroke_idx, 1, aa_idx=aa_idx)


def draw_centered_bdf_text(layer: Image.Image, text: str, fill_idx: int, spacing: int = 1) -> None:
    font, _ = load_bdf(str(SMALL_BDF_FONT_PATH))
    glyphs = []
    total_w = 0
    for ch in text:
        grid, w, h, xo, yo = glyph_grid(font[ord(ch)])
        glyphs.append((grid, w, h, xo, yo))
        total_w += w + spacing
    total_w -= spacing

    x = (layer.width - total_w) // 2
    y = 0
    px = layer.load()
    for grid, w, h, xo, _yo in glyphs:
        for row in range(h):
            for col in range(w):
                if not grid[row][col]:
                    continue
                dx = x + col + xo
                dy = y + row
                if 0 <= dx < layer.width and 0 <= dy < layer.height:
                    px[dx, dy] = fill_idx
        x += w + spacing


def make_part1_label_block(korean: str, _english: str, max_size: int = 20) -> Image.Image:
    layer = Image.new("L", (80, 32), 0)
    draw_centered_block_text(layer, korean, (0, 2, 80, 30), max_size + 2, 2, 15, 7)
    return layer


def make_part1_operation_block() -> Image.Image:
    layer = make_part1_label_block("작전룸", "OPERATION", 20)
    return layer


def make_part1_mode_block() -> Image.Image:
    return make_part1_label_block("모드 선택", "MODE SELECT", 18)


def make_part1_option_block(text: str, max_size: int) -> Image.Image:
    layer = Image.new("L", (128, 32), 0)
    draw = ImageDraw.Draw(layer)
    for size in range(max_size, 13, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        w, h = text_bbox(draw, text, font, 2)
        if w <= 116 and h <= 28:
            break
    x = (128 - w) // 2
    y = (32 - h) // 2 - 1
    # Original option sprites use palette-index steps for outline/body/shadow.
    # Stay inside those indices so each runtime palette keeps its own color.
    draw.text((x + 1, y + 1), text, font=font, fill=4, stroke_width=2, stroke_fill=4)
    draw.text((x, y), text, font=font, fill=15, stroke_width=2, stroke_fill=7)
    return layer


def make_part1_catherine_block() -> Image.Image:
    layer = Image.new("L", (96, 8), 0)
    draw_centered_bdf_text(layer, "캐서린", 15)
    return layer


def make_part1_mission_block() -> Image.Image:
    layer = Image.new("L", (128, 32), 0)
    draw_centered_block_text(layer, "작전", (0, 0, 128, 32), 28, 4, 1, 3)
    return layer


def patch_lz77_whole_block(rom: bytearray, off: int, layer: Image.Image, label: str) -> tuple[int, int]:
    dec = lz77_decompress(rom, off)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block for {label} at 0x{off:X}")
    old_data, consumed = dec
    new_data = block_to_tiles(layer)
    if len(new_data) != len(old_data):
        raise RuntimeError(f"{label} tile data size mismatch: {len(new_data)} != {len(old_data)}")
    comp = lz77_compress(new_data, vram_safe=True)
    if len(comp) > consumed:
        raise RuntimeError(f"compressed {label} block grew: {len(comp)} > {consumed}")
    rom[off : off + consumed] = comp + b"\x00" * (consumed - len(comp))
    return len(comp), consumed


def patch_part1_mission_block(rom: bytearray) -> tuple[int, int]:
    label = "part1 mission logo"
    dec = lz77_decompress(rom, PART1_MISSION_LOGO_LZ77_OFF)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block for {label} at 0x{PART1_MISSION_LOGO_LZ77_OFF:X}")
    old_data, consumed = dec
    layer = make_part1_mission_block()
    new_data = block_to_tiles(layer) + bytes(len(old_data) - layer.width * layer.height // 2)
    if len(new_data) != len(old_data):
        raise RuntimeError(f"{label} tile data size mismatch: {len(new_data)} != {len(old_data)}")
    comp = lz77_compress(new_data, vram_safe=True)
    if len(comp) > consumed:
        raise RuntimeError(f"compressed {label} block grew: {len(comp)} > {consumed}")
    rom[PART1_MISSION_LOGO_LZ77_OFF : PART1_MISSION_LOGO_LZ77_OFF + consumed] = (
        comp + b"\x00" * (consumed - len(comp))
    )
    return len(comp), consumed


def option_layer_to_tiles(layer: Image.Image) -> bytes:
    if layer.size != (128, 32):
        raise RuntimeError(f"option layer size mismatch: {layer.size}")
    tiles = bytearray()
    px = layer.load()
    for half in range(2):
        x_base = half * 64
        for ty in range(4):
            for tx in range(8):
                for y in range(8):
                    for x_pair in range(4):
                        lo = int(px[x_base + tx * 8 + x_pair * 2, ty * 8 + y]) & 0xF
                        hi = int(px[x_base + tx * 8 + x_pair * 2 + 1, ty * 8 + y]) & 0xF
                        tiles.append(lo | (hi << 4))
    return bytes(tiles)


def patch_part1_option_block(rom: bytearray, off: int, layer: Image.Image, label: str) -> tuple[int, int]:
    dec = lz77_decompress(rom, off)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block for {label} at 0x{off:X}")
    old_data, consumed = dec
    new_data = option_layer_to_tiles(layer)
    if len(new_data) != len(old_data):
        raise RuntimeError(f"{label} tile data size mismatch: {len(new_data)} != {len(old_data)}")
    comp = lz77_compress(new_data, vram_safe=True)
    if len(comp) > consumed:
        raise RuntimeError(f"compressed {label} block grew: {len(comp)} > {consumed}")
    rom[off : off + consumed] = comp + b"\x00" * (consumed - len(comp))
    return len(comp), consumed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="output/game_wars_korean_final.gba")
    parser.add_argument("--output", default="output/game_wars_korean_title_test.gba")
    parser.add_argument("--preview", default="docs/title_hangul/drafts/title_obj_okdandan_insert_layer_3x.png")
    parser.add_argument("--select-preview", default="docs/title_hangul/drafts/select_obj_okdandan_insert_layer_3x.png")
    parser.add_argument("--part1-preview", default="docs/title_hangul/drafts/part1_title_okdandan_insert_layer_3x.png")
    parser.add_argument("--part2-preview", default="docs/title_hangul/drafts/part2_title_okdandan_insert_layer_3x.png")
    args = parser.parse_args()

    rom = bytearray(Path(args.input).read_bytes())
    dec = lz77_decompress(rom, TITLE_OBJ_LZ77_OFF)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block at 0x{TITLE_OBJ_LZ77_OFF:X}")
    tile_data, consumed = dec
    tile_data = bytearray(tile_data)
    layer_idx = make_title_index_layer()
    patch_sprite_index_layer(tile_data, layer_idx, TEXT_SPRITES)
    patch_sprite_index_layer(tile_data, layer_idx, PROMPT_SPRITES)

    comp = lz77_compress(bytes(tile_data), vram_safe=True)
    if len(comp) > consumed:
        raise RuntimeError(f"compressed title OBJ block grew: {len(comp)} > {consumed}")
    rom[TITLE_OBJ_LZ77_OFF : TITLE_OBJ_LZ77_OFF + consumed] = comp + b"\x00" * (consumed - len(comp))

    select_dec = lz77_decompress(rom, SELECT_OBJ_LZ77_OFF)
    if select_dec is None:
        raise RuntimeError(f"invalid LZ77 block at 0x{SELECT_OBJ_LZ77_OFF:X}")
    select_tile_data, select_consumed = select_dec
    select_tile_data = bytearray(select_tile_data)
    select_idx = make_select_index_layer()
    patch_sprite_index_layer(select_tile_data, select_idx, SELECT_TOP_TEXT_SPRITES)
    patch_sprite_index_layer(select_tile_data, select_idx, SELECT_BOTTOM_TEXT_SPRITES)
    patch_sprite_index_layer(select_tile_data, select_idx, SELECT_PROMPT_SPRITES)
    select_comp = lz77_compress(bytes(select_tile_data), vram_safe=True)
    if len(select_comp) > select_consumed:
        raise RuntimeError(f"compressed select OBJ block grew: {len(select_comp)} > {select_consumed}")
    rom[SELECT_OBJ_LZ77_OFF : SELECT_OBJ_LZ77_OFF + select_consumed] = select_comp + b"\x00" * (
        select_consumed - len(select_comp)
    )

    part1_dec = lz77_decompress(rom, PART1_TITLE_OBJ_LZ77_OFF)
    if part1_dec is None:
        raise RuntimeError(f"invalid LZ77 block at 0x{PART1_TITLE_OBJ_LZ77_OFF:X}")
    part1_tile_data, part1_consumed = part1_dec
    part1_tile_data = bytearray(part1_tile_data)
    part1_idx = make_part1_index_layer()
    patch_sprite_index_layer(part1_tile_data, part1_idx, PART1_TITLE_TEXT_SPRITES, tile_subtract=0x200)
    patch_sprite_index_layer(part1_tile_data, part1_idx, PART1_PROMPT_SPRITES, tile_subtract=0x200)
    part1_comp = lz77_compress(bytes(part1_tile_data), vram_safe=True)
    if len(part1_comp) > part1_consumed:
        raise RuntimeError(f"compressed part1 title OBJ block grew: {len(part1_comp)} > {part1_consumed}")
    rom[PART1_TITLE_OBJ_LZ77_OFF : PART1_TITLE_OBJ_LZ77_OFF + part1_consumed] = part1_comp + b"\x00" * (
        part1_consumed - len(part1_comp)
    )

    part2_dec = lz77_decompress(rom, PART2_TITLE_OBJ_LZ77_OFF)
    if part2_dec is None:
        raise RuntimeError(f"invalid LZ77 block at 0x{PART2_TITLE_OBJ_LZ77_OFF:X}")
    part2_tile_data, part2_consumed = part2_dec
    part2_tile_data = bytearray(part2_tile_data)
    part2_idx = make_part2_index_layer()
    patch_sprite_index_layer(part2_tile_data, part2_idx, PART2_TITLE_TEXT_SPRITES)
    patch_sprite_index_layer(part2_tile_data, part2_idx, PART2_PROMPT_SPRITES)
    part2_comp = lz77_compress(bytes(part2_tile_data), vram_safe=True)
    if len(part2_comp) > part2_consumed:
        raise RuntimeError(f"compressed part2 title OBJ block grew: {len(part2_comp)} > {part2_consumed}")
    rom[PART2_TITLE_OBJ_LZ77_OFF : PART2_TITLE_OBJ_LZ77_OFF + part2_consumed] = part2_comp + b"\x00" * (
        part2_consumed - len(part2_comp)
    )

    p1_label_blocks = [
        ("part1 operation logo", PART1_OPERATION_LOGO_LZ77_OFF, make_part1_operation_block()),
        ("part1 map select logo", PART1_MAP_SELECT_LZ77_OFF, make_part1_label_block("맵 선택", "MAP SELECT", 20)),
        ("part1 shop select logo", PART1_SHOP_SELECT_LZ77_OFF, make_part1_label_block("숍 선택", "SHOP SELECT", 20)),
        ("part1 hard shop logo", PART1_HARD_SHOP_LZ77_OFF, make_part1_label_block("하드 숍", "HARD SHOP", 18)),
        ("part1 campaign logo", PART1_CAMPAIGN_LZ77_OFF, make_part1_label_block("캠페인", "CAMPAIGN", 20)),
        ("part1 mode select logo", PART1_MODE_SELECT_LZ77_OFF, make_part1_mode_block()),
        ("part1 rule select logo", PART1_RULE_SELECT_LZ77_OFF, make_part1_label_block("룰 선택", "RULE SELECT", 20)),
        ("part1 team setting logo", PART1_TEAM_SETTING_LZ77_OFF, make_part1_label_block("팀 설정", "TEAM SETTING", 20)),
    ]
    p1_option_blocks = [
        (name, off, make_part1_option_block(text, max_size))
        for name, off, text, max_size in PART1_MODE_OPTION_BLOCKS
    ]
    p1_catherine_idx = make_part1_catherine_block()
    p1_label_results = []
    for label, off, layer in p1_label_blocks:
        p1_label_results.append((label, *patch_lz77_whole_block(rom, off, layer, label)))
    p1_option_results = []
    for label, off, layer in p1_option_blocks:
        p1_option_results.append((label, *patch_part1_option_block(rom, off, layer, f"part1 option {label}")))
    p1_catherine_comp, p1_catherine_consumed = patch_lz77_whole_block(
        rom, PART1_CATHERINE_NAME_LZ77_OFF, p1_catherine_idx, "part1 Catherine name"
    )
    p1_mission_comp, p1_mission_consumed = patch_part1_mission_block(rom)

    rom[0xBD] = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(rom)
    preview = layer_idx.convert("RGB").resize((720, 480), Image.Resampling.NEAREST)
    Path(args.preview).parent.mkdir(parents=True, exist_ok=True)
    preview.save(args.preview)
    select_preview = select_idx.convert("RGB").resize((720, 480), Image.Resampling.NEAREST)
    Path(args.select_preview).parent.mkdir(parents=True, exist_ok=True)
    select_preview.save(args.select_preview)
    part1_preview = part1_idx.convert("RGB").resize((720, 480), Image.Resampling.NEAREST)
    Path(args.part1_preview).parent.mkdir(parents=True, exist_ok=True)
    part1_preview.save(args.part1_preview)
    part2_preview = part2_idx.convert("RGB").resize((720, 480), Image.Resampling.NEAREST)
    Path(args.part2_preview).parent.mkdir(parents=True, exist_ok=True)
    part2_preview.save(args.part2_preview)
    for label, _off, layer in p1_label_blocks:
        safe_label = label.replace(" ", "_")
        layer.convert("RGB").resize((240, 96), Image.Resampling.NEAREST).save(
            f"docs/title_hangul/drafts/{safe_label}_insert_layer_3x.png"
        )
    for label, _off, layer in p1_option_blocks:
        layer.convert("RGB").resize((384, 96), Image.Resampling.NEAREST).save(
            f"docs/title_hangul/drafts/part1_option_{label}_insert_layer_3x.png"
        )
    p1_catherine_idx.convert("RGB").resize((288, 24), Image.Resampling.NEAREST).save(
        "docs/title_hangul/drafts/part1_catherine_name_insert_layer_3x.png"
    )
    make_part1_mission_block().convert("RGB").resize((384, 96), Image.Resampling.NEAREST).save(
        "docs/title_hangul/drafts/part1_mission_logo_insert_layer_3x.png"
    )
    print(f"wrote {args.output}")
    print(f"compressed {len(comp)} / {consumed} bytes")
    print(f"select compressed {len(select_comp)} / {select_consumed} bytes")
    print(f"part1 compressed {len(part1_comp)} / {part1_consumed} bytes")
    print(f"part2 compressed {len(part2_comp)} / {part2_consumed} bytes")
    for label, comp_size, consumed_size in p1_label_results:
        print(f"{label} compressed {comp_size} / {consumed_size} bytes")
    for label, comp_size, consumed_size in p1_option_results:
        print(f"part1 option {label} compressed {comp_size} / {consumed_size} bytes")
    print(f"part1 catherine compressed {p1_catherine_comp} / {p1_catherine_consumed} bytes")
    print(f"part1 mission logo compressed {p1_mission_comp} / {p1_mission_consumed} bytes")
    print(f"preview {args.preview}")
    print(f"select preview {args.select_preview}")
    print(f"part1 preview {args.part1_preview}")
    print(f"part2 preview {args.part2_preview}")


if __name__ == "__main__":
    main()
