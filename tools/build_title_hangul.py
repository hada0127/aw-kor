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
TITLE_COPYRIGHT_LZ77_OFFS = (0x000228AC, 0x0003895C, 0x0052F974, 0x00C43FB8)
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
PART1_SUBMENU_LOGO_BLOCKS = [
    ("campaign", 0x00C1A2BC, "캠페인", 20),
    ("map_design", 0x00C1A81C, "맵 디자인", 18),
    ("single_battle", 0x00C1A9DC, "싱글 대전", 17),
    ("connect", 0x00C1AC60, "통신", 20),
    ("map_record", 0x00C1AE74, "맵 기록", 18),
    ("player_rank", 0x00C1B0E4, "플레이어 랭크", 15),
    ("single_card", 0x00C1B3A8, "1카드 통신", 14),
    ("multi_card", 0x00C1B610, "멀티카드 통신", 12),
    ("cable_battle", 0x00C1A564, "케이블 대전", 16),
    ("map_trade", 0x00C1B830, "맵 교환", 18),
]
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
PART1_LOGO_BLOCK_CAPACITY = {
    PART1_OPERATION_LOGO_LZ77_OFF: 660,
    PART1_MAP_SELECT_LZ77_OFF: 662,
    PART1_SHOP_SELECT_LZ77_OFF: 758,
    PART1_HARD_SHOP_LZ77_OFF: 698,
    PART1_CAMPAIGN_LZ77_OFF: 774,
    PART1_MODE_SELECT_LZ77_OFF: 630,
    PART1_RULE_SELECT_LZ77_OFF: 730,
    PART1_TEAM_SETTING_LZ77_OFF: 716,
}
PART1_MODE_OPTION_BLOCK_CAPACITY = {
    0x00C0310C: 1028,
    0x00C03510: 878,
    0x00C03880: 622,
    0x00C03AF0: 1144,
    0x00C03F68: 1141,
    0x00C043E0: 1210,
    0x00C0489C: 1194,
    0x00C04D48: 1169,
    0x00C051DC: 1145,
    0x00C05658: 828,
    0x00C05994: 996,
    0x00C05D78: 1183,
    0x00C06218: 1140,
    0x00C0668C: 1260,
    0x00C06B78: 994,
}
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

TITLE_BACKDROP_SPRITES = (
    (30, 8, 8, 64, 64, 0x088, 2),
    (31, 72, 8, 64, 64, 0x0C8, 2),
    (32, 136, 8, 64, 64, 0x108, 2),
    (33, 200, 8, 32, 64, 0x148, 2),
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

SELECT_RESIDUAL_SPRITES = (
    (45, -4, 1, 64, 64, 0x090, 3),
    (46, 60, 1, 64, 64, 0x0D0, 3),
    (47, 124, 1, 64, 64, 0x110, 3),
    (48, 188, 1, 32, 64, 0x150, 3),
    (32, 16, 80, 64, 64, 0x1FC, 4),
    (33, 80, 80, 64, 64, 0x23C, 4),
    (34, 144, 80, 64, 64, 0x27C, 4),
    (35, 208, 80, 32, 64, 0x2BC, 4),
    (22, 194, 122, 16, 8, 0x170, 1),
    (26, 192, 80, 32, 32, 0x1D2, 2),
    (27, 224, 80, 16, 32, 0x1E2, 2),
    (28, 192, 112, 32, 16, 0x1EA, 2),
    (29, 224, 112, 16, 16, 0x1F2, 2),
    (30, 192, 128, 32, 8, 0x1F6, 2),
    (31, 224, 128, 16, 8, 0x1FA, 2),
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

PART2_ATTRACT_RESIDUAL_SPRITES = (
    (25, 186, 50, 16, 8, 0x190, 1),
    (34, 8, 48, 32, 16, 0x0B0, 2),
    (35, 40, 48, 32, 16, 0x0B8, 2),
    (36, 72, 48, 32, 16, 0x0C0, 2),
    (37, 104, 48, 32, 16, 0x0C8, 2),
    (38, 136, 48, 32, 16, 0x0D0, 2),
    (39, 168, 48, 32, 16, 0x0D8, 2),
    (40, 200, 48, 32, 16, 0x0E0, 2),
)

SHARED_TITLE_TM_SPRITES = (
    (46, 200, 8, 32, 64, 0x2F8, 3),
)

SHARED_TITLE_TILE_SUBTRACT = 0x200

TM_PIXEL_PATTERN = (
    "2222222222222",
    "2111112132312",
    "2221222113112",
    "..212.2121212",
    "..212.2122212",
    "..212.212.212",
    "..212.212.212",
    "..222.222.222",
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
    draw_fitted_logo_text(layer, "게임보이 워즈 어드밴스", 114, 20, 184, 28, 24)
    draw_fitted_logo_text(layer, "게임보이 워즈 어드밴스", 121, 101, 188, 24, 22)

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


def draw_select_logo_text(
    layer: Image.Image,
    text: str,
    center_x: int,
    y: int,
    max_w: int,
    max_h: int,
    start_size: int,
    outer_idx: int,
    inner_idx: int,
    inner_aa_idx: int,
    body_stops: tuple[int, ...],
    body_aa_idx: int,
) -> None:
    draw = ImageDraw.Draw(layer)
    for size in range(start_size, 12, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        w = box[2] - box[0]
        h = box[3] - box[1]
        if w <= max_w and h <= max_h:
            break
    x = center_x - w // 2 - box[0]
    yy = y - box[1]

    outer = text_mask_layer(layer.size, text, font, (x, yy), 2)
    inner = text_mask_layer(layer.size, text, font, (x, yy), 1)
    body = text_mask_layer(layer.size, text, font, (x, yy), 0)
    lp = layer.load()
    op = outer.load()
    ip = inner.load()
    bp = body.load()
    bbox = body.getbbox()
    if bbox is None:
        return
    x0, _y0, x1, _y1 = bbox
    width = max(1, x1 - x0 - 1)
    stops = (5, 4, 6, 7, 8)
    for py in range(layer.height):
        for px in range(layer.width):
            if op[px, py] >= 48:
                lp[px, py] = outer_idx
            if ip[px, py] >= 48:
                lp[px, py] = inner_idx if ip[px, py] >= 128 else inner_aa_idx
            alpha = bp[px, py]
            if alpha >= 32:
                t = max(0.0, min(1.0, (px - x0) / width))
                idx = body_stops[min(len(body_stops) - 1, int(t * len(body_stops)))]
                lp[px, py] = idx if alpha >= 128 else body_aa_idx


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
    draw_select_logo_text(
        layer,
        "게임보이 워즈 어드밴스",
        114,
        18,
        184,
        30,
        24,
        outer_idx=15,
        inner_idx=1,
        inner_aa_idx=13,
        body_stops=(10, 8, 6, 4, 2),
        body_aa_idx=9,
    )
    draw_select_logo_text(
        layer,
        "게임보이 워즈 어드밴스",
        121,
        96,
        188,
        31,
        24,
        outer_idx=1,
        inner_idx=15,
        inner_aa_idx=14,
        body_stops=(5, 4, 6, 7, 8),
        body_aa_idx=9,
    )
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
    draw_select_logo_text(
        layer,
        "게임보이 워즈 어드밴스",
        116,
        25,
        184,
        28,
        24,
        outer_idx=1,
        inner_idx=15,
        inner_aa_idx=14,
        body_stops=(5, 4, 6, 7, 8),
        body_aa_idx=9,
    )
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


def patch_sprite_overlay_pixels(
    tile_data: bytearray,
    layer: Image.Image,
    sprites: tuple[tuple[int, int, int, int, int, int, int], ...],
    tile_subtract: int = 0,
) -> None:
    px = layer.load()
    for _idx, sx, sy, w, h, base_tile, _pal_no in sprites:
        cols = w // 8
        for yy in range(sy, sy + h):
            if yy < 0 or yy >= layer.height:
                continue
            for xx in range(sx, sx + w):
                if xx < 0 or xx >= layer.width:
                    continue
                value = int(px[xx, yy]) & 0xF
                if value == 0:
                    continue
                lx = xx - sx
                ly = yy - sy
                tile_no = base_tile - tile_subtract + (ly // 8) * cols + (lx // 8)
                if tile_no < 0:
                    continue
                bi = tile_no * 32 + (ly % 8) * 4 + (lx % 8) // 2
                if bi >= len(tile_data):
                    continue
                if lx & 1:
                    tile_data[bi] = (tile_data[bi] & 0x0F) | (value << 4)
                else:
                    tile_data[bi] = (tile_data[bi] & 0xF0) | value


def patch_sprite_screen_rects(
    tile_data: bytearray,
    rects: tuple[tuple[int, int, int, int, int], ...],
    sprites: tuple[tuple[int, int, int, int, int, int, int], ...],
    tile_subtract: int = 0,
) -> None:
    for x0, y0, x1, y1, fill in rects:
        fill &= 0xF
        for _idx, sx, sy, w, h, base_tile, _pal_no in sprites:
            ox0 = max(x0, sx)
            oy0 = max(y0, sy)
            ox1 = min(x1, sx + w)
            oy1 = min(y1, sy + h)
            if ox0 >= ox1 or oy0 >= oy1:
                continue
            cols = w // 8
            for yy in range(oy0, oy1):
                for xx in range(ox0, ox1):
                    lx = xx - sx
                    ly = yy - sy
                    tile_no = base_tile - tile_subtract + (ly // 8) * cols + (lx // 8)
                    if tile_no < 0:
                        continue
                    bi = tile_no * 32 + (ly % 8) * 4 + (lx % 8) // 2
                    if bi >= len(tile_data):
                        continue
                    if lx & 1:
                        tile_data[bi] = (tile_data[bi] & 0x0F) | (fill << 4)
                    else:
                        tile_data[bi] = (tile_data[bi] & 0xF0) | fill


def patch_sprite_screen_mask_rows(
    tile_data: bytearray,
    rows: tuple[tuple[int, int, str, int], ...],
    sprites: tuple[tuple[int, int, int, int, int, int, int], ...],
    tile_subtract: int = 0,
) -> None:
    for x0, yy, mask, fill in rows:
        fill &= 0xF
        for dx, marker in enumerate(mask):
            if marker != "#":
                continue
            xx = x0 + dx
            for _idx, sx, sy, w, h, base_tile, _pal_no in sprites:
                if not (sx <= xx < sx + w and sy <= yy < sy + h):
                    continue
                cols = w // 8
                lx = xx - sx
                ly = yy - sy
                tile_no = base_tile - tile_subtract + (ly // 8) * cols + (lx // 8)
                if tile_no < 0:
                    continue
                bi = tile_no * 32 + (ly % 8) * 4 + (lx % 8) // 2
                if bi >= len(tile_data):
                    continue
                if lx & 1:
                    tile_data[bi] = (tile_data[bi] & 0x0F) | (fill << 4)
                else:
                    tile_data[bi] = (tile_data[bi] & 0xF0) | fill


def make_title_residual_overlay_layer() -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    draw = ImageDraw.Draw(layer)
    draw.rectangle((52, 9, 190, 27), fill=8)
    draw_centered_block_text(layer, "한글판", (52, 10, 190, 25), 12, 15, 10, 9)
    return layer


def patch_title_residual_tiles(tile_data: bytearray) -> None:
    patch_sprite_overlay_pixels(tile_data, make_title_residual_overlay_layer(), TITLE_BACKDROP_SPRITES)
    patch_sprite_screen_rects(tile_data, ((208, 40, 230, 55, 0),), TITLE_BACKDROP_SPRITES)


def patch_select_residual_tiles(tile_data: bytearray) -> None:
    patch_sprite_screen_rects(
        tile_data,
        (
            (200, 28, 221, 36, 0),
            (56, 124, 184, 141, 0),
        ),
        SELECT_RESIDUAL_SPRITES,
    )


def make_tm_pattern_layer(x: int, y: int) -> Image.Image:
    layer = Image.new("L", (240, 160), 0)
    px = layer.load()
    for dy, row in enumerate(TM_PIXEL_PATTERN):
        for dx, ch in enumerate(row):
            if ch == ".":
                continue
            px[x + dx, y + dy] = int(ch, 16)
    return layer


def patch_select_top_tm_tiles(tile_data: bytearray) -> None:
    patch_sprite_overlay_pixels(tile_data, make_tm_pattern_layer(204, 28), SELECT_RESIDUAL_SPRITES)


def patch_shared_title_tm_tiles(tile_data: bytearray) -> None:
    patch_sprite_screen_rects(
        tile_data,
        ((213, 35, 232, 44, 0),),
        SHARED_TITLE_TM_SPRITES,
        tile_subtract=SHARED_TITLE_TILE_SUBTRACT,
    )
    patch_sprite_overlay_pixels(
        tile_data,
        make_tm_pattern_layer(213, 35),
        SHARED_TITLE_TM_SPRITES,
        tile_subtract=SHARED_TITLE_TILE_SUBTRACT,
    )


def make_select_top_tm_overlay_layer() -> Image.Image:
    return make_tm_pattern_layer(204, 28)


def make_part1_tm_overlay_layer() -> Image.Image:
    return make_tm_pattern_layer(213, 35)


def patch_part2_attract_title_residual_tiles(tile_data: bytearray) -> None:
    patch_sprite_screen_rects(
        tile_data,
        (
            (48, 51, 205, 63, 0),
            (186, 50, 202, 58, 0),
        ),
        PART2_ATTRACT_RESIDUAL_SPRITES,
    )


def title_copyright_layer_to_tiles(layer: Image.Image) -> bytes:
    if layer.size != (160, 16):
        raise RuntimeError(f"title copyright layer size mismatch: {layer.size}")
    tiles = bytearray()
    px = layer.load()
    for sprite in range(5):
        x_base = sprite * 32
        for ty in range(2):
            for tx in range(4):
                for y in range(8):
                    for x_pair in range(4):
                        lo = int(px[x_base + tx * 8 + x_pair * 2, ty * 8 + y]) & 0xF
                        hi = int(px[x_base + tx * 8 + x_pair * 2 + 1, ty * 8 + y]) & 0xF
                        tiles.append(lo | (hi << 4))
    return bytes(tiles)


def make_title_copyright_block() -> bytes:
    layer = Image.new("L", (160, 16), 0)
    draw_centered_block_text(layer, "닌텐도  시스템즈", (0, 2, 160, 15), 10, 1, 15, 13)
    return title_copyright_layer_to_tiles(layer)


def patch_title_copyright_blocks(rom: bytearray) -> int:
    new_data = make_title_copyright_block()
    patched = 0
    for off in TITLE_COPYRIGHT_LZ77_OFFS:
        dec = lz77_decompress(rom, off)
        if dec is None:
            raise RuntimeError(f"invalid title copyright LZ77 block at 0x{off:X}")
        old_data, consumed = dec
        if len(old_data) != len(new_data):
            raise RuntimeError(f"title copyright block size mismatch at 0x{off:X}: {len(old_data)} != {len(new_data)}")
        comp = lz77_compress(new_data, vram_safe=True)
        if len(comp) > consumed:
            raise RuntimeError(f"compressed title copyright block grew at 0x{off:X}: {len(comp)} > {consumed}")
        rom[off : off + consumed] = comp + b"\x00" * (consumed - len(comp))
        patched += 1
    return patched


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


def part1_logo_layer_to_tiles(layer: Image.Image) -> bytes:
    if layer.size != (80, 32):
        raise RuntimeError(f"part1 logo layer size mismatch: {layer.size}")
    out = bytearray()
    px = layer.load()
    for x_base, cols in ((0, 8), (64, 2)):
        for ty in range(4):
            for tx in range(cols):
                indices: list[int] = []
                for py in range(8):
                    for px_x in range(8):
                        indices.append(int(px[x_base + tx * 8 + px_x, ty * 8 + py]) & 0xF)
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


def draw_centered_title_font_text(
    layer: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    max_size: int,
    fill_idx: int,
    stroke_idx: int,
    aa_idx: int,
    target_min_w: int | None = None,
) -> None:
    draw = ImageDraw.Draw(layer)
    font_path = FONT_PATH if FONT_PATH.exists() else BODY_BOLD_FONT_PATH
    for size in range(max_size, 8, -1):
        font = ImageFont.truetype(str(font_path), size)
        w, h = text_bbox(draw, text, font, 2)
        if w <= box[2] - box[0] and h <= box[3] - box[1]:
            break
    text_box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
    w = text_box[2] - text_box[0]
    h = text_box[3] - text_box[1]
    x = (box[0] + box[2] - w) // 2 - text_box[0]
    y = (box[1] + box[3] - h) // 2 - text_box[1] - 1
    glyph_y = (max(0, y + text_box[1]), min(layer.height - 1, y + text_box[3]))
    paste_mask_index(layer, text_mask_layer(layer.size, text, font, (x + 2, y + 2), 2), 15, 32)
    paste_mask_index(layer, text_mask_layer(layer.size, text, font, (x + 1, y + 1), 2), 9, 48)
    paste_mask_index(layer, text_mask_layer(layer.size, text, font, (x, y), 2), 10, 48)
    paste_mask_index(layer, text_mask_layer(layer.size, text, font, (x, y), 1), 14, 32)
    body = text_mask_layer(layer.size, text, font, (x, y), 0)
    paste_vertical_text_gradient(
        layer,
        body,
        glyph_y,
        center_idx=10,
        top_indices=(1, 2, 3),
        bottom_indices=(4, 5, 6, 7),
        aa_idx=aa_idx,
        center_band=0.16,
    )
    if target_min_w is None:
        return
    bbox = layer.getbbox()
    if bbox is None:
        return
    current_w = bbox[2] - bbox[0]
    target_w = min(target_min_w, box[2] - box[0])
    if current_w >= target_w:
        return
    patch = layer.crop(bbox).resize((target_w, bbox[3] - bbox[1]), Image.Resampling.NEAREST)
    draw.rectangle((bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1), fill=0)
    x = (box[0] + box[2] - target_w) // 2
    layer.paste(patch, (x, bbox[1]))


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


def paste_mask_index(layer: Image.Image, mask: Image.Image, idx: int, threshold: int = 24) -> None:
    mp = mask.load()
    lp = layer.load()
    for yy in range(layer.height):
        for xx in range(layer.width):
            if mp[xx, yy] >= threshold:
                lp[xx, yy] = idx & 0xF


def text_mask_layer(
    size: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    xy: tuple[int, int],
    stroke: int,
) -> Image.Image:
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.text(xy, text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    return mask


def paste_vertical_text_gradient(
    layer: Image.Image,
    body: Image.Image,
    bbox_y: tuple[int, int],
    *,
    center_idx: int = 10,
    top_indices: tuple[int, ...] = (1, 2, 3, 4),
    bottom_indices: tuple[int, ...] = (4, 5, 6, 7, 8),
    aa_idx: int = 3,
    center_band: float = 0.13,
) -> None:
    bp = body.load()
    lp = layer.load()
    y0, y1 = bbox_y
    height = max(1, y1 - y0)
    mid = y0 + height * 0.48
    for yy in range(layer.height):
        t = max(0.0, min(1.0, (yy - y0) / height))
        if abs(yy - mid) <= max(2.0, height * center_band):
            fill = center_idx
        elif yy < mid:
            fill = top_indices[min(len(top_indices) - 1, int(t / 0.48 * len(top_indices)))]
        else:
            bt = (t - 0.48) / 0.52
            fill = bottom_indices[min(len(bottom_indices) - 1, max(0, int(bt * len(bottom_indices))))]
        for xx in range(layer.width):
            alpha = bp[xx, yy]
            if alpha >= 96:
                lp[xx, yy] = fill
            elif alpha >= 24 and lp[xx, yy] == 0:
                lp[xx, yy] = aa_idx


BAYER_4X4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def paste_ordered_text_gradient(
    layer: Image.Image,
    body: Image.Image,
    bbox_y: tuple[int, int],
    stops: tuple[int, ...],
    *,
    aa_idx: int = 3,
    dither: bool = True,
) -> None:
    bp = body.load()
    lp = layer.load()
    y0, y1 = bbox_y
    height = max(1, y1 - y0)
    scale = max(1, len(stops) - 1)
    for yy in range(layer.height):
        t = max(0.0, min(1.0, (yy - y0) / height))
        pos = t * scale
        lo = min(scale, int(pos))
        hi = min(scale, lo + 1)
        frac = pos - lo
        for xx in range(layer.width):
            alpha = bp[xx, yy]
            if alpha >= 96:
                if dither:
                    threshold = (BAYER_4X4[yy & 3][xx & 3] + 0.5) / 16.0
                    lp[xx, yy] = stops[hi] if frac > threshold else stops[lo]
                else:
                    lp[xx, yy] = stops[hi] if frac >= 0.5 else stops[lo]
            elif alpha >= 24 and lp[xx, yy] == 0:
                lp[xx, yy] = aa_idx


def strengthen_operation_room_rieul(layer: Image.Image) -> None:
    px = layer.load()
    body_indices = {1, 2, 3, 4, 5, 6, 7, 8, 10}
    for y, x0, x1 in ((8, 79, 87), (10, 82, 91)):
        for x in range(x0, x1):
            if px[x, y] in body_indices:
                px[x, y] = 14


def strengthen_first_tong_tieut(layer: Image.Image) -> None:
    """Extend the right edge of the first '통' top strokes by two pixels."""
    bbox = layer.getbbox()
    if bbox is None:
        return
    x0, y0, x1, y1 = bbox
    px = layer.load()
    mid = x0 + max(1, (x1 - x0) // 2)
    body_indices = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    for y in range(y0, min(y1, y0 + 10)):
        xs = [x for x in range(x0, mid) if px[x, y] in body_indices]
        if len(xs) < 4:
            continue
        left = min(xs)
        right = max(xs)
        if right - left < 5:
            continue
        value = px[right, y] if px[right, y] else 14
        for x in (right + 1, right + 2):
            if x < mid + 2 and px[x, y] == 0:
                px[x, y] = value


def make_part1_label_block(korean: str, _english: str, max_size: int = 20) -> Image.Image:
    layer = Image.new("L", (80, 32), 0)
    draw_centered_title_font_text(layer, korean, (4, 3, 78, 29), min(max_size, 18), 2, 15, 7)
    return layer


def make_part1_submenu_label_block(korean: str, max_size: int = 20) -> Image.Image:
    layer = Image.new("L", (80, 32), 0)
    label = {
        "멀티카드 통신": "멀티 통신",
        "플레이어 랭크": "랭크",
    }.get(korean, korean)
    if label in {"싱글 대전", "통신"}:
        target_w = 72 if label == "싱글 대전" else 48
        draw_centered_title_font_text(
            layer, label, (4, 3, 78, 29), min(max_size, 18), 2, 15, 7, target_min_w=target_w
        )
    else:
        draw_centered_block_text(layer, label, (6, 6, 78, 28), min(max_size, 15), 2, 15, 7)
    return layer


def make_part1_operation_block() -> Image.Image:
    layer = make_part1_label_block("작전룸", "OPERATION", 20)
    return layer


def make_part1_mode_block() -> Image.Image:
    layer = Image.new("L", (80, 32), 0)
    draw = ImageDraw.Draw(layer)
    text = "모드 선택"
    font = ImageFont.truetype(str(FONT_PATH), 19)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
    w = box[2] - box[0]
    h = box[3] - box[1]
    x = (80 - w) // 2 - box[0]
    y = (32 - h) // 2 - box[1] - 1
    glyph_y = (max(0, y + box[1]), min(31, y + box[3]))
    paste_mask_index(layer, text_mask_layer((80, 32), text, font, (x + 2, y + 2), 2), 15, 32)
    paste_mask_index(layer, text_mask_layer((80, 32), text, font, (x + 1, y + 1), 2), 9, 48)
    paste_mask_index(layer, text_mask_layer((80, 32), text, font, (x, y), 2), 10, 48)
    paste_mask_index(layer, text_mask_layer((80, 32), text, font, (x, y), 1), 14, 32)
    body = text_mask_layer((80, 32), text, font, (x, y), 0)
    paste_vertical_text_gradient(
        layer,
        body,
        glyph_y,
        center_idx=10,
        top_indices=(1, 2, 3),
        bottom_indices=(4, 5, 6, 7),
        center_band=0.16,
    )
    return layer


def part1_option_display_text(text: str) -> str:
    return text


def make_part1_option_block(text: str, max_size: int) -> Image.Image:
    layer = Image.new("L", (128, 32), 0)
    label = part1_option_display_text(text)
    draw = ImageDraw.Draw(layer)
    font_path = BODY_BOLD_FONT_PATH if BODY_BOLD_FONT_PATH.exists() else BODY_FONT_PATH
    width_limit = 78 if len(label) >= 5 else 62
    start_size = max(8, min(max_size, 12))
    font = ImageFont.truetype(str(font_path), start_size)
    for size in range(start_size, 7, -1):
        font = ImageFont.truetype(str(font_path), size)
        w, h = text_bbox(draw, label, font, 0)
        if w <= width_limit and h <= 13:
            break

    box = draw.textbbox((0, 0), label, font=font, stroke_width=0)
    w = box[2] - box[0]
    x = (128 - w) // 2 - box[0]
    y = 5 - box[1]
    # These OBJ labels scroll behind the translucent Part1 help box. Keep them
    # low-profile: no drop shadow or outline. The original menu scrolls option
    # OBJs behind the translucent help box, so extra edge pixels hurt the help
    # text more than they improve the off-center carousel labels.
    paint_index_text_aa(layer, (x, y), label, font, 2, 2, 0, aa_idx=2)
    return layer


def make_part1_catherine_block() -> Image.Image:
    layer = Image.new("L", (96, 8), 0)
    draw_centered_bdf_text(layer, "캐서린", 15)
    return layer


def make_part1_mission_block() -> Image.Image:
    layer = Image.new("L", (128, 32), 0)
    draw_centered_block_text(layer, "작전", (0, 0, 128, 32), 28, 4, 1, 3)
    return layer


def patch_lz77_whole_block(
    rom: bytearray,
    off: int,
    layer: Image.Image,
    label: str,
    capacity: int | None = None,
) -> tuple[int, int]:
    dec = lz77_decompress(rom, off)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block for {label} at 0x{off:X}")
    old_data, consumed = dec
    new_data = part1_logo_layer_to_tiles(layer) if layer.size == (80, 32) else block_to_tiles(layer)
    if len(new_data) != len(old_data):
        raise RuntimeError(f"{label} tile data size mismatch: {len(new_data)} != {len(old_data)}")
    comp = lz77_compress(new_data, vram_safe=True)
    limit = capacity or consumed
    if len(comp) > limit:
        raise RuntimeError(f"compressed {label} block grew: {len(comp)} > {limit}")
    rom[off : off + limit] = comp + b"\x00" * (limit - len(comp))
    return len(comp), limit


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


def patch_part1_submenu_logo_blocks(rom: bytearray) -> list[tuple[str, int, int]]:
    results = []
    for label, off, text, max_size in PART1_SUBMENU_LOGO_BLOCKS:
        layer = make_part1_submenu_label_block(text, max_size)
        comp_size, consumed_size = patch_lz77_whole_block(rom, off, layer, f"part1 submenu logo {label}")
        results.append((label, comp_size, consumed_size))
    return results


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


def patch_part1_option_block(
    rom: bytearray,
    off: int,
    layer: Image.Image,
    label: str,
    capacity: int | None = None,
) -> tuple[int, int]:
    dec = lz77_decompress(rom, off)
    if dec is None:
        raise RuntimeError(f"invalid LZ77 block for {label} at 0x{off:X}")
    old_data, consumed = dec
    new_data = option_layer_to_tiles(layer)
    if len(new_data) != len(old_data):
        raise RuntimeError(f"{label} tile data size mismatch: {len(new_data)} != {len(old_data)}")
    comp = lz77_compress(new_data, vram_safe=True)
    limit = capacity or consumed
    if len(comp) > limit:
        raise RuntimeError(f"compressed {label} block grew: {len(comp)} > {limit}")
    rom[off : off + limit] = comp + b"\x00" * (limit - len(comp))
    return len(comp), limit


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
    patch_title_residual_tiles(tile_data)

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
    patch_select_residual_tiles(select_tile_data)
    patch_select_top_tm_tiles(select_tile_data)
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
    patch_shared_title_tm_tiles(part1_tile_data)
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
    patch_part2_attract_title_residual_tiles(part2_tile_data)
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
        p1_label_results.append(
            (label, *patch_lz77_whole_block(rom, off, layer, label, PART1_LOGO_BLOCK_CAPACITY.get(off)))
        )
    p1_submenu_results = patch_part1_submenu_logo_blocks(rom)
    p1_option_results = []
    for label, off, layer in p1_option_blocks:
        p1_option_results.append(
            (
                label,
                *patch_part1_option_block(
                    rom,
                    off,
                    layer,
                    f"part1 option {label}",
                    PART1_MODE_OPTION_BLOCK_CAPACITY.get(off),
                ),
            )
        )
    p1_catherine_comp, p1_catherine_consumed = patch_lz77_whole_block(
        rom, PART1_CATHERINE_NAME_LZ77_OFF, p1_catherine_idx, "part1 Catherine name"
    )
    p1_mission_comp, p1_mission_consumed = patch_part1_mission_block(rom)
    copyright_patched = patch_title_copyright_blocks(rom)

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
    for label, _off, text, max_size in PART1_SUBMENU_LOGO_BLOCKS:
        layer = make_part1_submenu_label_block(text, max_size)
        layer.convert("RGB").resize((240, 96), Image.Resampling.NEAREST).save(
            f"docs/title_hangul/drafts/part1_submenu_{label}_insert_layer_3x.png"
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
    for label, comp_size, consumed_size in p1_submenu_results:
        print(f"part1 submenu logo {label} compressed {comp_size} / {consumed_size} bytes")
    for label, comp_size, consumed_size in p1_option_results:
        print(f"part1 option {label} compressed {comp_size} / {consumed_size} bytes")
    print(f"part1 catherine compressed {p1_catherine_comp} / {p1_catherine_consumed} bytes")
    print(f"part1 mission logo compressed {p1_mission_comp} / {p1_mission_consumed} bytes")
    print(f"title copyright blocks patched {copyright_patched}")
    print(f"preview {args.preview}")
    print(f"select preview {args.select_preview}")
    print(f"part1 preview {args.part1_preview}")
    print(f"part2 preview {args.part2_preview}")


if __name__ == "__main__":
    main()
