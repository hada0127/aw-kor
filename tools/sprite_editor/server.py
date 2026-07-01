#!/usr/bin/env python3
"""스프라이트 픽셀아트 에디터 — 경량 웹도구 (stdlib http.server + PIL).

GBA 저해상도(8×8 4bpp 타일)에 맞춘 픽셀 단위 편집기. muramasa ui_editor의
서버 스캐폴드를 따르되 프론트엔드는 확대 캔버스 + 팔레트 스와치 픽셀 페인트.

실행:
  python3 tools/sprite_editor/server.py            # http://127.0.0.1:8781

데이터:
  data/sprites_index.json   {sprites:[{id,offset,type,width,height,palette_guess,png,source,...}]}
  temp/sprites_png/<id>.png  원본 렌더(인덱스 생성 시 export_sprites.py가 생성)
  data/sprite_edits/<id>.png 편집본(저장 시)
  data/sprites_overrides.json {id:{offset,type,width,height,edited_png}}  빌드 역기록용 기록

API
  GET  /api/sprites?type=&source=&q=&curated=     인덱스(필터)
  GET  /api/png?id=<id>                           원본(or 편집본) PNG
  GET  /api/png?id=<id>&orig=1                     항상 원본 PNG
  POST /api/save  {id, png_b64}                    편집 PNG 저장 + overrides 기록
  POST /api/revert {id}                            편집 되돌리기(편집본 삭제)
"""
import argparse
import base64
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
INDEX_PATH = ROOT / "data" / "sprites_index.json"
ORIG_PNG_DIR = ROOT / "temp" / "sprites_png"
EDIT_DIR = ROOT / "data" / "sprite_edits"
OVERRIDES_PATH = ROOT / "data" / "sprites_overrides.json"

SELECT_OBJ_ID = "lz77_00024A34"
SELECT_TOP_TITLE_ID = SELECT_OBJ_ID + "#select_top_title"
SELECT_BOTTOM_TITLE_ID = SELECT_OBJ_ID + "#select_bottom_title"
SELECT_VIRTUAL_SPRITES = {
    SELECT_TOP_TITLE_ID: {
        "base_id": SELECT_OBJ_ID,
        "layout_variant": "select_top_title",
        "source_suffix": "select_top_title",
        "desc": "1/2편 선택 화면 상단 제목",
    },
    SELECT_BOTTOM_TITLE_ID: {
        "base_id": SELECT_OBJ_ID,
        "layout_variant": "select_bottom_title",
        "source_suffix": "select_bottom_title",
        "desc": "1/2편 선택 화면 하단 제목",
    },
}

_LOCK = threading.Lock()
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".png": "image/png", ".json": "application/json; charset=utf-8"}


def load_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


OBJLABEL_PATH = ROOT / "data" / "objlabel_sprites.json"
_OBJLABELS = None


def load_objlabel_sprites():
    """빌드가 방출한 OBJ 직접기록 라벨군 합성 스프라이트(흩어진 4bpp 타일). type='synthetic'."""
    global _OBJLABELS
    if _OBJLABELS is None:
        _OBJLABELS = (load_json(OBJLABEL_PATH, {}) or {}).get("sprites", []) or []
    return _OBJLABELS


def sprite_list():
    d = load_json(INDEX_PATH, {"sprites": []})
    base = d.get("sprites", []) if isinstance(d, dict) else d
    sprites = list(base) + load_objlabel_sprites()
    select_base = next((s for s in sprites if s.get("id") == SELECT_OBJ_ID), None)
    if select_base:
        for sid, meta in SELECT_VIRTUAL_SPRITES.items():
            sp = dict(select_base)
            sp.update({
                "id": sid,
                "base_id": meta["base_id"],
                "layout_variant": meta["layout_variant"],
                "desc_override": meta["desc"],
                "source": f"{select_base.get('source') or ''}:{meta['source_suffix']}",
            })
            sprites.append(sp)
    return sprites


def png_for(sid, orig=False):
    """편집본 우선(없거나 orig=True면 원본). (data, found)."""
    if not orig:
        ep = EDIT_DIR / f"{sid}.png"
        if ep.exists():
            return ep.read_bytes(), True
    # index의 png 경로 우선, 없으면 temp/sprites_png/<id>.png
    sp = next((s for s in sprite_list() if s.get("id") == sid), None)
    if sp and sp.get("png"):
        p = ROOT / sp["png"]
        if p.exists():
            return p.read_bytes(), True
    p = ORIG_PNG_DIR / f"{sid}.png"
    if p.exists():
        return p.read_bytes(), True
    return b"", False


# --- 인덱스(4bpp) 기반 편집: ROM 바이트 → 팔레트 인덱스 그리드 ---
import sys as _sys
import struct as _struct
if str(ROOT / "tools") not in _sys.path:
    _sys.path.insert(0, str(ROOT / "tools"))
import export_sprites as ES  # noqa: E402  lz77_decompress, tiles_to_indices, GRAYSCALE, read_palette, guess_cols, TILE_BYTES

ROM_PATH = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
PATCHED_ROM_PATH = ROOT / "output" / "game_wars_korean_full.gba"
CMP_DIR = ROOT / "temp" / "sprite_cmp"
_ROM = None
_PATCHED = None
MODE4_STRATEGIC_MAP_OFFSETS = {0x00C2FD70, 0x00C30EE8}
MODE4_STRATEGIC_MAP_PALETTE_OFF = 0x00C2FC90
MODE4_STRATEGIC_MAP_W = 240


def rom_bytes():
    global _ROM
    if _ROM is None:
        _ROM = ROM_PATH.read_bytes() if ROM_PATH.exists() else b""
    return _ROM


def patched_bytes():
    global _PATCHED
    if _PATCHED is None:
        _PATCHED = PATCHED_ROM_PATH.read_bytes() if PATCHED_ROM_PATH.exists() else b""
    return _PATCHED


def sprite_by_id(sid):
    return next((s for s in sprite_list() if s.get("id") == sid), None)


def sprite_offset_int(sp):
    off = sp.get("offset_int")
    if off is None:
        off = int(sp.get("offset", "0x0"), 16)
    return off


def is_mode4_bitmap(sp):
    """Mode4 8bpp framebuffer halves. These are screen bitmaps, not 4bpp tiles."""
    src = (sp.get("source") or "").lower()
    return "mode4" in src or sprite_offset_int(sp) in MODE4_STRATEGIC_MAP_OFFSETS


def override_id(sp_or_sid):
    """저장/빌드 적용 키. 가상 화면 항목은 같은 base LZ77 블록에 합쳐 저장한다."""
    if isinstance(sp_or_sid, dict):
        return sp_or_sid.get("base_id") or sp_or_sid.get("id")
    sp = sprite_by_id(sp_or_sid)
    return (sp.get("base_id") or sp.get("id")) if sp else sp_or_sid


def decode_from_rom(rom, sp):
    """주어진 ROM 바이트에서 sprite 디코드 → (grid,w,h,cols). 실패 시 None."""
    if is_mode4_bitmap(sp):
        return None
    off = sprite_offset_int(sp)
    typ = sp.get("type")
    if typ == "synthetic":
        # 흩어진 ROM 오프셋의 라벨군을 시각순(perm 보정)으로 조립 → 단일 타일스트림.
        td = bytearray()
        for lab in (sp.get("labels") or []):
            loff = lab.get("offset_int")
            if loff is None:
                loff = int(lab["offset"], 16)
            tw, th = lab["tw"], lab["th"]
            perm = lab.get("perm") or list(range(tw * th))
            for vis in range(tw * th):
                ri = perm[vis]
                td += rom[loff + ri * 32: loff + ri * 32 + 32]
        tile_data = bytes(td)
        n = len(tile_data) // ES.TILE_BYTES
        if n == 0:
            return None
        cols = sp.get("tile_cols") or ES.guess_cols(n)
        pad = (-n) % cols  # 편집캔버스 그리드용 직사각 패딩(셀은 0..n-1만 참조 → onscreen 무영향)
        if pad:
            tile_data = tile_data + bytes(pad * 32)
        grid, w, h = ES.tiles_to_indices(tile_data, cols)
        return grid, w, h, cols
    if typ == "lz77":
        res = ES.lz77_decompress(rom, off)
        if not res:
            return None
        tile_data = res[0]
    else:
        tile_data = rom[off: off + (sp.get("size") or 0)]
    n = len(tile_data) // ES.TILE_BYTES
    if n == 0:
        return None
    cols = sp.get("tile_cols") or ES.guess_cols(n)
    grid, w, h = ES.tiles_to_indices(tile_data, cols)
    return grid, w, h, cols


def decode_indices(sp):
    """원본 ROM에서 디코드. 비교/검증에서 원본 기준이 필요할 때만 쓴다.

    합성(synthetic) 스프라이트도 원본 ROM의 같은 직접 오프셋에서 조립할 수
    있으므로 좌측 비교 패널에서는 원본 바이트를 그대로 보여준다.
    """
    return decode_from_rom(rom_bytes(), sp)


def decode_current_indices(sp):
    """편집기 기본값: 최종 빌드 ROM 우선, 없을 때만 원본 ROM fallback."""
    rom = patched_bytes() or rom_bytes()
    return decode_from_rom(rom, sp)


def render_compare_png(sid, which):
    """원본(orig)/패치빌드(patched)/편집(edit) 스프라이트를 PNG 바이트로 렌더.
    스프라이트는 타일+팔레트에서 1:1 표시되므로 이 디코드 렌더 = 인게임 픽셀과 동일."""
    sp = sprite_by_id(sid)
    if sp is None:
        return None
    if is_mode4_bitmap(sp):
        return render_mode4_bitmap_png(sid, which)
    pal = [tuple(c) for c in palette_for(sp)]
    grid = w = h = None
    if which == "edit":
        ov = load_json(OVERRIDES_PATH, {}) or {}
        rec = ov.get(override_id(sp))
        if rec and rec.get("indices"):
            grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
        else:
            return None
    if grid is None:
        rom = patched_bytes() if which == "patched" else rom_bytes()
        if not rom:
            return None
        dec = decode_from_rom(rom, sp)
        if dec is None:
            return None
        grid, w, h, _ = dec
    CMP_DIR.mkdir(parents=True, exist_ok=True)
    out = CMP_DIR / f"{sid}_{which}.png"
    ES.render_png(grid, w, h, pal, str(out), scale=3)
    return out.read_bytes()


def _gba_palette256(rom):
    import struct as _s
    colors = []
    for i in range(256):
        o = MODE4_STRATEGIC_MAP_PALETTE_OFF + i * 2
        if o + 2 > len(rom):
            colors.append((0, 0, 0))
            continue
        v = _s.unpack("<H", rom[o:o + 2])[0]
        colors.append(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31))
    return colors


def decode_mode4_bitmap(rom, sp):
    """Return (indices,w,h) for 8bpp Mode4 framebuffer half."""
    off = sprite_offset_int(sp)
    res = ES.lz77_decompress(rom, off)
    if not res:
        return None
    data = res[0]
    w = MODE4_STRATEGIC_MAP_W
    h = max(1, len(data) // w)
    return data[:w * h], w, h


def render_mode4_bitmap_png(sid, which):
    """원본/한글 빌드 Mode4 전략지도 반쪽을 실제 팔레트로 렌더. 편집 저장은 지원하지 않는다."""
    sp = sprite_by_id(sid)
    if sp is None:
        return None
    if which == "edit":
        return None
    rom = patched_bytes() if which == "patched" else rom_bytes()
    if not rom:
        return None
    dec = decode_mode4_bitmap(rom, sp)
    if dec is None:
        return None
    data, w, h = dec
    pal = _gba_palette256(rom)
    from PIL import Image
    im = Image.new("RGB", (w, h), (0, 0, 0))
    px = im.load()
    for y in range(h):
        row = y * w
        for x in range(w):
            px[x, y] = pal[data[row + x]]
    CMP_DIR.mkdir(parents=True, exist_ok=True)
    out = CMP_DIR / f"{sid}_{which}.png"
    im.resize((w * 3, h * 3), Image.NEAREST).save(out, "PNG")
    return out.read_bytes()


def encode_indices(grid, w, h):
    """index grid(h×w, 0..15) → 4bpp 타일 바이트(8×8 타일, cols=w//8)."""
    cols = w // 8
    rows = h // 8
    out = bytearray()
    for t in range(cols * rows):
        gx = (t % cols) * 8
        gy = (t // cols) * 8
        for row in range(8):
            for c2 in range(4):
                lo = grid[gy + row][gx + c2 * 2] & 0xF
                hi = grid[gy + row][gx + c2 * 2 + 1] & 0xF
                out.append(lo | (hi << 4))
    return bytes(out)


PALLIB_PATH = ROOT / "data" / "sprite_palettes.json"
LAYOUTS_PATH = ROOT / "data" / "sprite_layouts.json"
_LAYOUTS = None


def load_layouts():
    global _LAYOUTS
    if _LAYOUTS is None:
        _LAYOUTS = load_json(LAYOUTS_PATH, {"layouts": {}, "pal_by_screen": {}}) or {"layouts": {}, "pal_by_screen": {}}
    return _LAYOUTS


BUILD_LAYOUTS_PATH = ROOT / "data" / "sprite_build_layouts.json"
_BUILD_LAYOUTS = None

PART1_LOGO_80X32_OFFSETS = {
    0x00C18CB4, 0x00C18F48, 0x00C191E0, 0x00C194D8,
    0x00C19794, 0x00C19A9C, 0x00C19D14, 0x00C19FF0,
    0x00C1A2BC, 0x00C1A564, 0x00C1A81C, 0x00C1A9DC,
    0x00C1AC60, 0x00C1AE74, 0x00C1B0E4, 0x00C1B3A8,
    0x00C1B610, 0x00C1B830,
}

PART1_OPTION_128X32_OFFSETS = {
    0x00C0310C, 0x00C03510, 0x00C03880, 0x00C03AF0,
    0x00C03F68, 0x00C043E0, 0x00C0489C, 0x00C04D48,
    0x00C051DC, 0x00C05658, 0x00C05994, 0x00C05D78,
    0x00C06218, 0x00C0668C, 0x00C06B78,
}
PART1_FALLBACK_PALETTE_HINTS = {
    # Representative current-ROM captures for Part1 option/menu-label blocks
    # whose clean build layout is better than the raw captured OAM bbox.
    0x00C0668C: ("temp/cap_battle/scr_005.pal", 256, 8),  # 멀티카드 통신
    0x00C1AC60: ("temp/cap_part1/scr_009.pal", 256, 4),   # 접속
}

PART1_MISSION_128X32_OFFSETS = {0x00C18738}
PART1_CATHERINE_96X8_OFFSETS = {0x00C102A8}
PART1_TITLE_OBJ_OFFSETS = {0x00C38BF8}
PART1_BATTLE_DAY_BANNER_OFFSETS = {0x00EE5E14}
PART1_CHECK_LABEL_OFFSETS = {0x00BA4490}
COMMON_NINTENDO_PRESENTS_BG_OFFSETS = {0x00021CE8}
COMMON_SELECT_OBJ_OFFSETS = {0x00024A34}

PART1_TITLE_TEXT_SPECS = (
    (16, 12, 8, 4, 0x118, 1),
    (80, 12, 8, 4, 0x138, 1),
    (144, 12, 8, 4, 0x158, 1),
    (208, 12, 2, 4, 0x178, 1),
    (16, 44, 4, 2, 0x180, 1),
    (48, 44, 4, 2, 0x188, 1),
    (80, 44, 4, 2, 0x190, 1),
    (112, 44, 4, 2, 0x198, 1),
    (144, 44, 4, 2, 0x1A0, 1),
    (176, 44, 4, 2, 0x1A8, 1),
    (208, 44, 1, 2, 0x1B0, 1),
)
PART1_TITLE_PROMPT_SPECS = (
    (75, 107, 4, 2, 0x000, 2),
    (107, 107, 4, 2, 0x008, 2),
    (139, 107, 4, 2, 0x010, 2),
)

SELECT_TOP_TEXT_SPECS = (
    (12, 4, 8, 4, 0x000, 0),
    (12, 36, 4, 2, 0x020, 0),
    (44, 36, 4, 2, 0x028, 0),
    (76, 4, 8, 4, 0x030, 0),
    (140, 4, 8, 4, 0x050, 0),
    (76, 36, 4, 2, 0x070, 0),
    (108, 36, 4, 2, 0x078, 0),
    (140, 36, 4, 2, 0x080, 0),
    (172, 36, 4, 2, 0x088, 0),
)
SELECT_BOTTOM_TEXT_SPECS = (
    (24, 92, 8, 4, 0x172, 1),
    (88, 92, 8, 4, 0x192, 1),
    (152, 92, 8, 4, 0x1B2, 1),
)
SELECT_PROMPT_SPECS = (
    (19, 144, 4, 2, 0x2DC, 6),
    (51, 144, 4, 2, 0x2E4, 6),
    (83, 144, 4, 2, 0x2EC, 6),
    (115, 144, 4, 2, 0x2F4, 6),
)
SELECT_RESIDUAL_SPECS = (
    (-4, 1, 8, 8, 0x090, 3),
    (60, 1, 8, 8, 0x0D0, 3),
    (124, 1, 8, 8, 0x110, 3),
    (188, 1, 4, 8, 0x150, 3),
    (16, 80, 8, 8, 0x1FC, 4),
    (80, 80, 8, 8, 0x23C, 4),
    (144, 80, 8, 8, 0x27C, 4),
    (208, 80, 4, 8, 0x2BC, 4),
    (194, 122, 2, 1, 0x170, 1),
    (192, 80, 4, 4, 0x1D2, 2),
    (224, 80, 2, 4, 0x1E2, 2),
    (192, 112, 4, 2, 0x1EA, 2),
    (224, 112, 2, 2, 0x1F2, 2),
    (192, 128, 4, 1, 0x1F6, 2),
    (224, 128, 2, 1, 0x1FA, 2),
)
SELECT_CURSOR_SPECS = (
    (104, 48, 2, 2, 0x2FC, 5),
    (104, 68, 2, 2, 0x2FC, 5),
)

PART2_MISSION_TITLE_128X32_OFFSETS = {
    0x00C10B34, 0x00C11D9C, 0x00C1205C,
}
PART2_TITLE_OBJ_OFFSETS = {0x004EAF6C}
PART2_SPLASH_LOGO_BG_OFFSETS = {0x004D8AF8}
PART2_DOMINO_CO_NAME_OFFSETS = {0x0045274C}
PART2_INTRO_BG_FULLSHEET_OFFSETS = {0x004E0478, 0x004E17C0, 0x004ECD60}
PART2_PROLOGUE_LOGO_OFFSETS = {0x005BBB3C}
PART2_CAMPAIGN_HEADER_OFFSETS = {0x00541BB8}
PART2_REDSTAR_REGION_OFFSETS = {0x005488A0}
PART2_MISSION_NUMBER_OFFSETS = {0x005A38D4}
PART2_LETS_GO_OFFSETS = {0x005AF674}
PART2_MODE_MENU_BIG_LOGO_OFFSETS = {
    0x005B7930, 0x005B7CB0, 0x005B7F38, 0x005B82B4,
    0x005B8564, 0x005B8850, 0x005B8B20,
}
PART2_MODE_MENU_OPTION_OFFSETS = {
    0x005B8E44, 0x005B8F48, 0x005B9050,
    0x005B917C, 0x005B9280, 0x005B9378,
}
PART2_BATTLE_START_LARGE_OFFSETS = {0x0045EC74}
PART2_BATTLE_START_MEDIUM_OFFSETS = {
    0x0092DF84, 0x00966C0C, 0x0099F4B0, 0x009D7D54,
}
PART2_BATTLE_START_SMALL_OFFSETS = {
    0x0092EB5C, 0x009677E4, 0x009A0088, 0x009D892C,
}
PART2_CHECK_LABEL_OFFSETS = {0x0045FCC8}
PART2_DAMAGE_FORECAST_OFFSETS = {0x00BD4FBC}
PART2_RESULT_SUCCESS_OVERLAY_OFFSETS = {
    0x00930520, 0x009691A8, 0x009A1A4C, 0x009DA2F0, 0x00EE8A64,
}
PART2_RESULT_FAILURE_OVERLAY_OFFSETS = {0x00BFBB54, 0x00EE8F68}
PART2_RESULT_CONGRATS_OFFSETS = {0x00BFB45C}
PART2_RESULT_SUMMARY_OFFSETS = {0x0059DA5C}


def load_build_layouts():
    global _BUILD_LAYOUTS
    if _BUILD_LAYOUTS is None:
        _BUILD_LAYOUTS = (load_json(BUILD_LAYOUTS_PATH, {}) or {}).get("blocks", {})
    return _BUILD_LAYOUTS


def sprite_offset_int(sp):
    off = sp.get("offset_int")
    if off is None:
        off = int(sp.get("offset", "0x0"), 16)
    return off


def _layout_cells_from_specs(specs, palbase=256):
    return [
        {"x": x, "y": y, "tw": tw, "th": th, "fh": 0, "fv": 0,
         "tile_off": tile_off, "bank": bank, "palbase": palbase}
        for x, y, tw, th, tile_off, bank in specs
    ]


def part1_palette_hint(sp, off, default=None):
    """Reuse captured Part1 OBJ palette banks while keeping clean build geometry."""
    captured = load_layouts().get("layouts", {}).get(sp.get("id"), {})
    if captured.get("pal_file"):
        for cell in captured.get("cells") or []:
            if int(cell.get("tw", 1)) * int(cell.get("th", 1)) <= 1:
                continue
            palbase = int(cell.get("palbase", 256))
            bank = int(cell.get("bank", 0))
            return captured["pal_file"], palbase, bank
    if off in PART1_FALLBACK_PALETTE_HINTS:
        return PART1_FALLBACK_PALETTE_HINTS[off]
    return default


def apply_part1_palette_hint(sp, off, cells, default=None):
    hint = part1_palette_hint(sp, off, default)
    if not hint:
        return cells, None
    pal_file, palbase, bank = hint
    for cell in cells:
        cell["palbase"] = palbase
        cell["bank"] = bank
    return cells, pal_file


def part1_tiled_layer_layout(sp, off):
    """1편 타이틀 라벨 LZ77은 화면 레이어와 저장 타일 순서가 다르다.
    편집면은 빌드 인코더(part1_logo_layer_to_tiles/option_layer_to_tiles)의 역배치로 제공한다."""
    if off in PART1_TITLE_OBJ_OFFSETS:
        captured = load_layouts().get("layouts", {}).get(sp.get("id"), {})
        pal_file = "temp/screen_state/part1_title.pal"
        if not (ROOT / pal_file).exists():
            pal_file = captured.get("pal_file")
        cells = _layout_cells_from_specs(PART1_TITLE_TEXT_SPECS)
        cells.extend(_layout_cells_from_specs(PART1_TITLE_PROMPT_SPECS))
        return {
            "cells": cells,
            "x0": 16, "y0": 12, "w": 208, "h": 111, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
            "pal_file": pal_file,
            "fallback": "part1_title_text_prompt",
        }
    if off in PART1_LOGO_80X32_OFFSETS:
        cells = [
            {"x": 0, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
            {"x": 64, "y": 0, "tw": 2, "th": 4, "fh": 0, "fv": 0, "tile_off": 32, "bank": 0, "palbase": 0},
        ]
        cells, pal_file = apply_part1_palette_hint(
            sp, off, cells, ("temp/cap_battle/scr_005.pal", 256, 4)
        )
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 80, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
            "pal_file": pal_file, "fallback": "part1_80x32",
        }
    if off in PART1_OPTION_128X32_OFFSETS:
        cells = [
            {"x": 0, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
            {"x": 64, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0, "tile_off": 32, "bank": 0, "palbase": 0},
        ]
        cells, pal_file = apply_part1_palette_hint(
            sp, off, cells, ("temp/cap_battle/scr_005.pal", 256, 8)
        )
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
            "pal_file": pal_file, "fallback": "part1_128x32",
        }
    if off in PART1_MISSION_128X32_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 16, "th": 4, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part1_mission_128x32",
        }
    if off in PART1_CATHERINE_96X8_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 12, "th": 1, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 96, "h": 8, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part1_catherine_96x8",
        }
    if off in PART1_CHECK_LABEL_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 2, "th": 2, "fh": 0, "fv": 0, "tile_off": 76, "bank": 0, "palbase": 0},
                {"x": 16, "y": 0, "tw": 2, "th": 2, "fh": 0, "fv": 0, "tile_off": 72, "bank": 0, "palbase": 0},
                {"x": 32, "y": 0, "tw": 2, "th": 2, "fh": 0, "fv": 0, "tile_off": 68, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 48, "h": 16, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part1_check_label_bubble",
        }
    if off in PART1_BATTLE_DAY_BANNER_OFFSETS:
        captured = load_layouts().get("layouts", {}).get(sp.get("id"), {})
        cells = []
        for i, tile_off in enumerate((0, 16, 32, 48)):
            cells.append({"x": i * 32, "y": 0, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                          "tile_off": tile_off, "bank": 3, "palbase": 256})
        for i, tile_off in enumerate((224, 240)):
            cells.append({"x": 32 + i * 32, "y": 42, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                          "tile_off": tile_off, "bank": 3, "palbase": 256})
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 128, "h": 74, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
            "pal_file": captured.get("pal_file"),
            "fallback": "part1_battle_day_banner_chunks",
        }
    return None


def part2_tiled_layer_layout(sp, off):
    """2편 빌드 산출 OBJ 타일시트를 런타임 출력 배치로 재조립한다.

    캡처 OAM이 없는 전투 시작/결과 타이틀 계열은 원본 tile_cols=32 raw sheet로
    보면 의미가 깨진다. 빌드 패커의 역배치를 여기서 제공해 편집 canvas가
    실제 OBJ 묶음 크기와 상대 위치를 따르도록 한다.
    """
    if off in PART2_MISSION_TITLE_128X32_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
                {"x": 64, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0, "tile_off": 32, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_128x32_title",
        }
    if off in PART2_TITLE_OBJ_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 0x0E8, "bank": 0, "palbase": 0},
                {"x": 64, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 0x108, "bank": 0, "palbase": 0},
                {"x": 128, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 0x128, "bank": 0, "palbase": 0},
                {"x": 40, "y": 80, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 0x170, "bank": 0, "palbase": 0},
                {"x": 72, "y": 80, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 0x178, "bank": 0, "palbase": 0},
                {"x": 104, "y": 80, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 0x180, "bank": 0, "palbase": 0},
                {"x": 136, "y": 80, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 0x188, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 192, "h": 96, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_title_obj_text",
        }
    if off in PART2_SPLASH_LOGO_BG_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 22, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 1, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 176, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_splash_logo_bg",
        }
    if off in PART2_DOMINO_CO_NAME_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 12, "th": 1, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 96, "h": 8, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_domino_co_name",
        }
    if off in PART2_INTRO_BG_FULLSHEET_OFFSETS:
        tw = max(1, int(sp.get("tile_cols") or 1))
        th = max(1, int((sp.get("n_tiles") or tw) + tw - 1) // tw)
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": tw, "th": th, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": tw * 8, "h": th * 8, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_intro_bg_fullsheet",
        }
    if off in PART2_PROLOGUE_LOGO_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 12, "th": 1, "fh": 0, "fv": 0,
                 "tile_off": 0x08, "bank": 0, "palbase": 0},
                {"x": 0, "y": 8, "tw": 12, "th": 1, "fh": 0, "fv": 0,
                 "tile_off": 0x28, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 96, "h": 16, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_prologue_logo",
        }
    if off in PART2_CAMPAIGN_HEADER_OFFSETS:
        cells = []
        for tile_off, x in (
            (0x008, 4),
            (0x048, 30),
            (0x060, 45),
            (0x030, 71),
            (0x020, 81),
            (0x050, 93),
        ):
            cells.append({"x": x, "y": 0, "tw": 2, "th": 4, "fh": 0, "fv": 0,
                          "tile_off": tile_off, "bank": 0, "palbase": 0})
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_campaign_header_oam",
        }
    if off in PART2_REDSTAR_REGION_OFFSETS:
        return {
            "cells": [
                {"x": i * 32, "y": 0, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": i * 16, "bank": 0, "palbase": 0}
                for i in range(3)
            ],
            "x0": 0, "y0": 0, "w": 96, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_redstar_region_96x32",
        }
    if off in PART2_MISSION_NUMBER_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 16, "th": 1, "fh": 0, "fv": 0,
                 "tile_off": 0x000, "bank": 0, "palbase": 0},
                {"x": 0, "y": 8, "tw": 16, "th": 1, "fh": 0, "fv": 0,
                 "tile_off": 0x020, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 16, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_mission_number_128x16",
        }
    if off in PART2_LETS_GO_OFFSETS:
        cells = []
        for ty in range(8):
            cells.append({"x": 0, "y": ty * 8, "tw": 16, "th": 1, "fh": 0, "fv": 0,
                          "tile_off": ty * 0x20, "bank": 0, "palbase": 0})
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 128, "h": 64, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_lets_go_visible_128x64",
        }
    if off in PART2_MODE_MENU_BIG_LOGO_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
                {"x": 64, "y": 0, "tw": 8, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 32, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_mode_menu_big_logo",
        }
    if off in PART2_MODE_MENU_OPTION_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
                {"x": 32, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 8, "bank": 0, "palbase": 0},
                {"x": 64, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 16, "bank": 0, "palbase": 0},
                {"x": 96, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 24, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 16, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_mode_menu_option",
        }
    if off in PART2_BATTLE_START_LARGE_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 16, "th": 1, "fh": 0, "fv": 0, "tile_off": 16, "bank": 0, "palbase": 0},
                {"x": 0, "y": 8, "tw": 32, "th": 4, "fh": 0, "fv": 0, "tile_off": 160, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 256, "h": 40, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_battle_start_removed_large",
        }
    if off in PART2_BATTLE_START_MEDIUM_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 16, "th": 1, "fh": 0, "fv": 0, "tile_off": 16, "bank": 0, "palbase": 0},
                {"x": 0, "y": 8, "tw": 32, "th": 2, "fh": 0, "fv": 0, "tile_off": 160, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 256, "h": 24, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_battle_start_removed_medium",
        }
    if off in PART2_BATTLE_START_SMALL_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 32, "th": 1, "fh": 0, "fv": 0, "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 256, "h": 8, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_battle_start_removed_small",
        }
    if off in PART2_CHECK_LABEL_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 45, "bank": 0, "palbase": 0},
                {"x": 32, "y": 0, "tw": 1, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 53, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 40, "h": 16, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True,
            "fallback": "part2_check_label_40x16",
        }
    if off in PART2_DAMAGE_FORECAST_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 22, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 32, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True,
            "fallback": "part2_damage_forecast_bubble_32x32",
        }
    if off in PART2_RESULT_SUCCESS_OVERLAY_OFFSETS or off in PART2_RESULT_FAILURE_OVERLAY_OFFSETS:
        return {
            "cells": [
                {"x": i * 32, "y": 0, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": i * 16, "bank": 0, "palbase": 0}
                for i in range(4)
            ],
            "x0": 0, "y0": 0, "w": 128, "h": 32, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True,
            "fallback": "part2_result_status_128x32",
        }
    if off in PART2_RESULT_CONGRATS_OFFSETS:
        cells = []
        for sprite in range(4):
            cells.append({"x": sprite * 32, "y": 0, "tw": 4, "th": 2, "fh": 0, "fv": 0,
                          "tile_off": 64 + sprite * 8, "bank": 0, "palbase": 0})
        for sprite in range(4):
            cells.append({"x": sprite * 32, "y": 19, "tw": 4, "th": 4, "fh": 0, "fv": 0,
                          "tile_off": sprite * 16, "bank": 0, "palbase": 0})
        return {
            "cells": cells,
            "x0": 0, "y0": 0, "w": 128, "h": 51, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_result_congrats",
        }
    if off in PART2_RESULT_SUMMARY_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 7, "th": 6, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
                {"x": 40, "y": 0, "tw": 8, "th": 6, "fh": 0, "fv": 0,
                 "tile_off": 8, "bank": 0, "palbase": 0},
                {"x": 89, "y": 0, "tw": 8, "th": 6, "fh": 0, "fv": 0,
                 "tile_off": 17, "bank": 0, "palbase": 0},
                {"x": 133, "y": 0, "tw": 6, "th": 6, "fh": 0, "fv": 0,
                 "tile_off": 26, "bank": 0, "palbase": 0},
                {"x": 32, "y": 46, "tw": 24, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 7 * 32 + 6, "bank": 0, "palbase": 0},
                {"x": 0, "y": 66, "tw": 8, "th": 3, "fh": 0, "fv": 0,
                 "tile_off": 9 * 32, "bank": 0, "palbase": 0},
                {"x": 72, "y": 66, "tw": 7, "th": 3, "fh": 0, "fv": 0,
                 "tile_off": 9 * 32 + 9, "bank": 0, "palbase": 0},
                {"x": 136, "y": 66, "tw": 10, "th": 3, "fh": 0, "fv": 0,
                 "tile_off": 9 * 32 + 17, "bank": 0, "palbase": 0},
                {"x": 0, "y": 92, "tw": 8, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 12 * 32, "bank": 0, "palbase": 0},
                {"x": 64, "y": 92, "tw": 6, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 12 * 32 + 8, "bank": 0, "palbase": 0},
                {"x": 128, "y": 92, "tw": 9, "th": 2, "fh": 0, "fv": 0,
                 "tile_off": 12 * 32 + 16, "bank": 0, "palbase": 0},
                {"x": 0, "y": 112, "tw": 16, "th": 3, "fh": 0, "fv": 0,
                 "tile_off": 13 * 32, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 224, "h": 136, "obj1d": 0,
            "tile_cols": sp.get("tile_cols"), "build": True, "fallback": "part2_result_summary_label_groups",
        }
    return None


def tiled_layer_layout(sp, off):
    if off in COMMON_NINTENDO_PRESENTS_BG_OFFSETS:
        return {
            "cells": [
                {"x": 0, "y": 0, "tw": 25, "th": 4, "fh": 0, "fv": 0,
                 "tile_off": 0, "bank": 0, "palbase": 0},
            ],
            "x0": 0, "y0": 0, "w": 200, "h": 32, "obj1d": 0,
            "tile_cols": sp.get("tile_cols"), "build": True,
            "fallback": "common_nintendo_presents_text_region",
        }
    if off in COMMON_SELECT_OBJ_OFFSETS:
        captured = load_layouts().get("layouts", {}).get(sp.get("id"), {})
        cells = []
        variant = sp.get("layout_variant")
        if variant == "select_top_title":
            cells.extend(_layout_cells_from_specs(SELECT_TOP_TEXT_SPECS))
            return {
                "cells": cells,
                "x0": 12, "y0": 4, "w": 192, "h": 48, "obj1d": 1,
                "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
                "pal_file": captured.get("pal_file") or load_layouts().get("layouts", {}).get(SELECT_OBJ_ID, {}).get("pal_file"),
                "fallback": "common_select_obj_top_title",
            }
        if variant == "select_bottom_title":
            cells.extend(_layout_cells_from_specs(SELECT_BOTTOM_TEXT_SPECS))
            return {
                "cells": cells,
                "x0": 24, "y0": 92, "w": 192, "h": 32, "obj1d": 1,
                "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
                "pal_file": captured.get("pal_file") or load_layouts().get("layouts", {}).get(SELECT_OBJ_ID, {}).get("pal_file"),
                "fallback": "common_select_obj_bottom_title",
            }
        # This catalogue item is the 1/2 select title/logo.  The same LZ77 OBJ
        # block also contains cursor/prompt/residual tiles, but including them
        # here makes the editor look like a full-screen composite instead of the
        # editable title sprite group.
        cells.extend(_layout_cells_from_specs(SELECT_TOP_TEXT_SPECS))
        cells.extend(_layout_cells_from_specs(SELECT_BOTTOM_TEXT_SPECS))
        return {
            "cells": cells,
            "x0": 12, "y0": 4, "w": 204, "h": 120, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "screen": "obj",
            "pal_file": captured.get("pal_file"),
            "fallback": "common_select_obj_title_text",
        }
    return part1_tiled_layer_layout(sp, off) or part2_tiled_layer_layout(sp, off)


def build_layout_cells(sp):
    """빌드 권위 라벨 타일스트립 → cells(캡처 레이아웃과 동일 스키마). 라벨을 세로로 적층.
    pal_file 없음 → 렌더는 sprite palette_for 사용(인덱스 직접)."""
    off = sprite_offset_int(sp)
    fallback_layout = tiled_layer_layout(sp, off)
    if fallback_layout:
        return fallback_layout
    blk = load_build_layouts().get("0x%X" % off)
    if not blk:
        return None
    cells = []
    y = 0
    maxw = 0
    for lab in blk["labels"]:
        for i, tid in enumerate(lab["tile_ids"]):
            cells.append({"x": i * 8, "y": y, "tw": 1, "th": 1, "fh": 0, "fv": 0,
                          "tile_off": tid, "bank": 0, "palbase": 0})
        maxw = max(maxw, len(lab["tile_ids"]) * 8)
        y += 10  # 8px + 2 gap
    if not cells:
        return None
    return {"cells": cells, "x0": 0, "y0": 0, "w": maxw, "h": y, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True}


def synthetic_layout_cells(sp):
    """합성 OBJ 라벨군 → cells. 라벨을 세로로 적층, 각 라벨은 tw×th 격자.
    tile_off = 조립 타일스트림(decode_from_rom synthetic과 동일 순서)의 순번."""
    labels = sp.get("labels") or []
    cells = []
    y = 0
    tindex = 0
    maxw = 0
    for lab in labels:
        tw, th = lab["tw"], lab["th"]
        for ty in range(th):
            for tx in range(tw):
                cells.append({"x": tx * 8, "y": y + ty * 8, "tw": 1, "th": 1, "fh": 0, "fv": 0,
                              "tile_off": tindex + ty * tw + tx, "bank": 0, "palbase": 0})
        tindex += tw * th
        maxw = max(maxw, tw * 8)
        y += th * 8 + 2  # 라벨 간 2px 간격
    if not cells:
        return None
    return {"cells": cells, "x0": 0, "y0": 0, "w": maxw, "h": y, "obj1d": 1,
            "tile_cols": sp.get("tile_cols"), "build": True, "synthetic": True}


def get_layout(sid):
    """빌드 레이어 역배치 → 캡처 레이아웃 → 합성 → 빌드 권위 레이아웃.

    라벨 계열은 캡처 OAM이 없거나 여러 화면 상태의 큰 bbox로 잡히는 경우가 있어
    편집면 권위는 빌드 인코더의 layer size/타일 순서 역배치다.
    """
    sp = sprite_by_id(sid)
    if sp is None:
        return None
    try:
        fallback_layout = tiled_layer_layout(sp, sprite_offset_int(sp))
    except Exception:
        fallback_layout = None
    if fallback_layout:
        return fallback_layout
    lay = load_layouts().get("layouts", {}).get(sid)
    if lay:
        return lay
    if sp.get("type") == "synthetic":
        return synthetic_layout_cells(sp)
    return build_layout_cells(sp)


def current_tiles(sp):
    """스프라이트의 현재 타일 바이트(편집본 우선→패치 ROM 디코드). 4bpp, 32B/타일."""
    ov = load_json(OVERRIDES_PATH, {}) or {}
    rec = ov.get(override_id(sp))
    if rec and rec.get("indices"):
        grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
        return encode_indices(grid, w, h)
    dec = decode_from_rom(patched_bytes() or rom_bytes(), sp)
    if dec is None:
        return b""
    grid, w, h, _ = dec
    return encode_indices(grid, w, h)


def render_onscreen_png(sid):
    """레이아웃(OAM 셀)+현재 타일+캡처 팔레트로 실제 화면 형태 재조립 PNG. 없으면 None."""
    import struct as _s
    sp = sprite_by_id(sid)
    if sp is None:
        return None
    lay = get_layout(sid)
    if not lay:
        return None
    tiles = current_tiles(sp)
    if not tiles:
        return None
    palp = lay.get("pal_file")
    if palp and (ROOT / palp).exists():
        palb = (ROOT / palp).read_bytes()
        def col(palbase, bank, idx):
            i = palbase + bank * 16 + idx
            v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
            return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)
    else:
        pal16 = [tuple(c) for c in palette_for(sp)]  # 빌드 레이아웃: 인덱스 직접
        def col(palbase, bank, idx):
            return pal16[idx & 15]
    def spx(t, x, y):
        o = t * 32 + y * 4 + x // 2
        if o >= len(tiles):
            return 0
        b = tiles[o]
        return (b & 0xF) if x % 2 == 0 else (b >> 4) & 0xF
    from PIL import Image
    obj1d = lay.get("obj1d", 1)
    im = Image.new("RGBA", (max(1, lay["w"]), max(1, lay["h"])), (0, 0, 0, 0))
    px = im.load()
    for c in lay["cells"]:
        for ty in range(c["th"]):
            for tx in range(c["tw"]):
                t = c["tile_off"] + (ty * c["tw"] + tx if obj1d else ty * 32 + tx)
                for yy in range(8):
                    for xx in range(8):
                        idx = spx(t, 7 - xx if c["fh"] else xx, 7 - yy if c["fv"] else yy)
                        if idx == 0:
                            continue
                        sx = c["x"] - lay["x0"] + (c["tw"] - 1 - tx if c["fh"] else tx) * 8 + xx
                        sy = c["y"] - lay["y0"] + (c["th"] - 1 - ty if c["fv"] else ty) * 8 + yy
                        if 0 <= sx < im.width and 0 <= sy < im.height:
                            r, g, b = col(c.get("palbase", 256), c["bank"], idx)
                            px[sx, sy] = (r, g, b, 255)
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    import io as _io
    buf = _io.BytesIO()
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(buf, "PNG")
    return buf.getvalue()


def palette_library():
    d = load_json(PALLIB_PATH, {}) or {}
    return d.get("palettes", [])


# OBJ 라벨 합성 스프라이트 편집용 고대비 기본 팔레트(잉크 1/5=짙음, 그림자 15/3=회색, 배경=밝음).
# 실기 팔레트는 화면별로 다르나 편집 도구는 가독성이 우선(런타임에 실제 팔레트 적용).
def _objlabel_pal():
    p = [[232, 232, 236] for _ in range(16)]
    p[0] = [250, 250, 250]
    p[1] = [28, 28, 34]    # 잉크(terrain/unit/header/menu/info)
    p[5] = [32, 44, 96]    # 잉크(header/action_menu/info, 짙은 남색)
    p[15] = [70, 70, 82]   # 잉크/그림자(co_banner '휘프'는 ink=15 → 짙게)
    p[3] = [158, 158, 168]  # 그림자(밝은 회색, 15와 분리)
    return p


def default_palette_for(sp):
    """source 화면 추정 → 그 화면의 실기 OBJ 팔레트(첫 뱅크)를 기본값으로. 없으면 grayscale.
    (정확한 뱅크는 사용자가 팔레트 드롭다운으로 선택; OAM 정보 없이 자동은 화면까지만 추정)"""
    if "objlabel" in (sp.get("source") or "").lower() or sp.get("type") == "synthetic":
        return _objlabel_pal()
    lib = palette_library()
    if not lib:
        return [list(c) for c in ES.GRAYSCALE]
    src = (sp.get("source") or "").lower()
    if "select" in src:
        screen = "part1_select"
    elif "part2" in src or "mode" in src or "menu" in src:
        screen = "part2_menu"
    else:
        screen = "title"
    objs = [p for p in lib if p["screen"] == screen and p["region"] == "OBJ"]
    if not objs:
        objs = [p for p in lib if p["region"] == "OBJ"] or lib
    return objs[0]["colors"] if objs else [list(c) for c in ES.GRAYSCALE]


def palette_for(sp):
    """편집/표시용 16색 팔레트. override 우선 → source 기반 실기 팔레트 기본값 → grayscale."""
    ov = load_json(OVERRIDES_PATH, {}) or {}
    rec = ov.get(override_id(sp))
    if rec and rec.get("palette"):
        return rec["palette"]
    return default_palette_for(sp)


# ── 스프라이트 분류/설명 ──────────────────────────────────────────────────
# source 코드 → (텍스트 여부, 한글 설명). 텍스트=번역 필요 라벨/로고. 비텍스트는 기본 목록 제외.
MENU_LABEL_KO = {
    "campaign": "캠페인", "map_design": "지도 편집", "single_battle": "싱글 배틀",
    "map_record": "지도 기록", "player_rank": "플레이어 랭크", "single_card": "싱글 카드",
    "multi_card": "멀티 카드", "map_trade": "지도 교환", "trial": "트라이얼", "record": "기록",
    "operation_room": "작전실", "wars_shop": "워즈 숍", "new_game": "새 게임",
    "continue": "계속하기", "link": "통신", "cable_battle": "케이블 대전", "connect": "접속",
}
PART1_LOGO_KO = {
    "OPERATION": "작전", "MAP_SELECT": "지도 선택", "SHOP_SELECT": "상점 선택",
    "HARD_SHOP": "하드 상점", "CAMPAIGN": "캠페인", "MODE_SELECT": "모드 선택",
    "RULE_SELECT": "룰 선택", "TEAM_SETTING": "팀 설정", "MISSION_LOGO": "미션 로고",
    "TITLE_OBJ": "1편 타이틀 로고", "CATHERINE_NAME": "캐서린 이름",
}
PART2_PATCH_KO = {
    "mode_menu_obj_labels": "2편 모드 메뉴 라벨(상점/도전/캠페인 등)",
    "battle_start_day_overlay_obj": "전투 시작 회전 소스(일본어 제거 대상)",
    "result_success_overlay_obj": "결과: 성공 오버레이", "result_failure_overlay_obj": "결과: 실패 오버레이",
    "result_summary_obj": "결과 요약", "result_congratulations_obj": "결과: 축하",
    "domino_co_name_obj": "도미노 CO 이름(원본 그래픽 제거)", "campaign_header_obj": "캠페인 헤더",
    "level_label_obj": "레벨 라벨", "redstar_region_obj": "레드스타 영역 라벨",
    "mission_number_obj": "미션 번호", "lets_go_obj": "‘출격’ 라벨", "check_label_obj": "체크 라벨",
    "splash_logo_bg": "2편 스플래시 로고", "prologue_logo_obj": "프롤로그 로고",
    "mission_start_obj": "전투개시 배너", "air_mission_title_obj": "에어 미션 타이틀",
    "air_supremacy_title_obj": "제공권 타이틀", "damage_forecast_label_obj": "데미지 예측 라벨",
    "menu_newspaper_bg": "메뉴 신문 배경(텍스트 포함)", "intro_campaign_residual_graphics": "인트로 캠페인 잔여 그래픽",
    "operation_select_country_bg": "작전 선택 국가 배경",
    "strategic_map_mode4_labels": "전략지도 Mode4 지명 라벨",
    "world_map_label_tiles": "월드맵 지명 라벨", "info_screen_bg_labels": "정보 화면 라벨",
    "full_info_spec_obj_label": "상세정보 스펙 라벨", "check_label": "체크 라벨", "battle_day_banner": "전투 N일째 배너",
}


OBJLABEL_KO = {
    "terrain_status": "2편 상태팝업 지형명", "terrain_compact": "2편 커서팝업 지형명",
    "unit_status": "2편 상태팝업 유닛명", "unit_compact": "2편 커서팝업 유닛명",
    "co_banner": "2편 적턴 CO 배너 이름", "status_header": "2편 상태리스트 헤더(종류/체력/연료/탄약)",
    "info_screen": "2편 정보화면 라벨(정보/비용/설명)", "action_menu": "2편 행동메뉴 아이콘(공격/대기 등)",
}


def classify_sprite(source):
    """(is_text, desc_ko). 텍스트=번역 대상 라벨/로고. 비텍스트(배경/캐릭터/폰트/미분류) → 기본 제외."""
    s = (source or "")
    sl = s.lower()
    if "part2_objlabel/" in sl:
        key = sl.split("part2_objlabel/")[1]
        return (True, OBJLABEL_KO.get(key, "2편 OBJ 라벨"))
    if "dialogue glyph" in sl or "font_base" in sl:
        return (False, "대화 폰트 글리프(편집 대상 아님)")
    if "blackhole" in sl:
        return (False, "인트로 블랙홀 배경")
    if sl.startswith("scan_lz77"):
        return (False, "미분류 스캔 그래픽")
    if "menu_label/" in sl:
        key = sl.split("menu_label/")[1]
        return (True, "1편 메뉴 라벨: " + MENU_LABEL_KO.get(key, key))
    for k, v in PART2_PATCH_KO.items():
        if k in sl:
            return (True, v)
    if "common_nintendo_presents_bg" in sl or "nintendo_presents" in sl:
        return (True, "콜드부트 닌텐도 제공")
    if "part1_" in sl and "_lz77_off" in sl:
        for k, v in PART1_LOGO_KO.items():
            if "part1_" + k.lower() in sl or k.lower() in sl:
                return (True, "1편 화면 로고: " + v)
        return (True, "1편 화면 로고")
    if "copyright" in sl:
        return (True, "타이틀 카피라이트(© 표기)")
    if "select_obj" in sl:
        return (True, "1/2편 선택 화면 제목/로고")
    if "title_obj" in sl or "part2_title_obj" in sl:
        return (True, "타이틀 로고")
    if "patch_block" in sl or "patch_lz" in sl:
        return (True, "패치 블록(텍스트 포함 가능)")
    return (False, s or "미분류")


def sprite_section(source):
    """공통/1편/2편 구분. (타이틀·선택·카피라이트·폰트=공통)"""
    s = (source or "").lower()
    if "part2" in s or "pt2" in s:
        return "part2"
    if "part1" in s or "pt1" in s or "menu_label/" in s:
        return "part1"
    return "common"


# 인게임 출력 순서 근사: 화면 등장 순서 랭크(작을수록 먼저)
def sprite_order_rank(source):
    s = (source or "").lower()
    table = [("copyright", 0), ("title_obj", 1), ("title", 1), ("select_obj", 2), ("select", 2),
             ("menu_label", 3), ("mode_menu", 3), ("menu", 3), ("newspaper", 3),
             ("splash", 4), ("blackhole", 4), ("prologue", 5), ("intro", 5), ("campaign", 6),
             ("mission", 7), ("redstar", 7), ("operation", 7), ("map_select", 7),
             ("objlabel", 8), ("terrain", 8), ("unit", 8), ("action_menu", 8),
             ("battle", 8), ("day", 8), ("damage", 8), ("level", 8), ("check", 8),
             ("result", 9), ("congratulations", 9), ("air_", 9)]
    for k, r in table:
        if k in s:
            return r
    return 10


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self._static("index.html")
        if u.path.startswith("/static/"):
            return self._static(u.path[len("/static/"):])
        if u.path == "/api/sprites":
            return self._send(200, self._sprites(q))
        if u.path == "/api/png":
            sid = q.get("id", [""])[0]
            data, ok = png_for(sid, orig=q.get("orig", ["0"])[0] == "1")
            if not ok:
                return self._send(404, {"error": "no png for " + sid})
            return self._send(200, data, "image/png")
        if u.path == "/api/tile":
            return self._send(200, self._tile(q))
        if u.path == "/api/render":
            sid = q.get("id", [""])[0]
            which = q.get("which", ["orig"])[0]
            if which not in ("orig", "patched", "edit"):
                return self._send(400, {"error": "which=orig|patched|edit"})
            try:
                data = render_compare_png(sid, which)
            except Exception as e:
                return self._send(500, {"error": "render: %r" % e})
            if not data:
                return self._send(404, {"error": "no render for %s/%s" % (sid, which)})
            return self._send(200, data, "image/png")
        if u.path == "/api/compare":
            return self._send(200, self._compare(q))
        if u.path == "/api/palettes":
            return self._send(200, {"palettes": palette_library()})
        if u.path == "/api/onscreen":
            sid = q.get("id", [""])[0]
            try:
                data = render_onscreen_png(sid)
            except Exception as e:
                return self._send(500, {"error": "onscreen: %r" % e})
            if not data:
                return self._send(404, {"error": "no onscreen layout for %s" % sid})
            return self._send(200, data, "image/png")
        if u.path == "/api/onscreen_data":
            return self._send(200, self._onscreen_data(q))
        return self._send(404, {"error": "not found"})

    def _onscreen_data(self, q):
        """WYSIWYG 편집용: 레이아웃 셀 + 그릴 팔레트(캡처 OBJ 뱅크) + tile_cols.
        프런트가 현재 indices로 조립 렌더 + 클릭→타일픽셀 역매핑 페인트."""
        import struct as _s
        sid = q.get("id", [""])[0]
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "no sprite %s" % sid}
        lay = get_layout(sid)
        if not lay:
            return {"ok": False, "error": "no layout for %s" % sid}
        dec = decode_current_indices(sp)
        cols = dec[3] if dec else (sp.get("tile_cols") or 1)
        palp = lay.get("pal_file")
        cells = []
        palettes = None
        for c in lay.get("cells") or []:
            cc = dict(c)
            if "palette_key" not in cc:
                cc["palette_key"] = "%s:%s" % (cc.get("palbase", 256), cc.get("bank", 0))
            cells.append(cc)
        if palp and (ROOT / palp).exists():
            palb = (ROOT / palp).read_bytes()

            def col(i):
                v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
                return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]
            palettes = {}
            for c in cells:
                key = c["palette_key"]
                if key in palettes:
                    continue
                palbase = int(c.get("palbase", 256))
                bank = int(c.get("bank", 0))
                palettes[key] = [col(palbase + bank * 16 + i) for i in range(16)]
            first_key = cells[0]["palette_key"] if cells else None
            palette = palettes.get(first_key) if first_key else None
            if palette is None:
                palette = [list(c) for c in palette_for(sp)]
        else:
            palette = [list(c) for c in palette_for(sp)]  # 빌드 레이아웃: 인덱스 직접
        out = {"ok": True, "w": lay["w"], "h": lay["h"], "x0": lay["x0"], "y0": lay["y0"],
               "obj1d": lay.get("obj1d", 1), "tile_cols": cols, "cells": cells,
               "palette": palette, "screen": lay.get("screen"), "build": lay.get("build", False)}
        if palettes:
            out["palettes"] = palettes
        return out

    def _compare(self, q):
        """원본↔적용(패치빌드) 픽셀 동일 여부 + 편집 존재 여부."""
        sid = q.get("id", [""])[0]
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        o = decode_from_rom(rom_bytes(), sp)
        p = decode_from_rom(patched_bytes(), sp) if patched_bytes() else None
        changed = (o and p and o[0] != p[0])
        ov = load_json(OVERRIDES_PATH, {}) or {}
        has_edit = override_id(sp) in ov and bool(ov[override_id(sp)].get("indices"))
        return {"ok": True, "id": sid, "offset": sp.get("offset"), "type": sp.get("type"),
                "source": sp.get("source"),
                "orig_url": "/api/render?id=%s&which=orig" % urllib.parse.quote(sid),
                "patched_url": ("/api/render?id=%s&which=patched" % urllib.parse.quote(sid)) if p else None,
                "edit_url": ("/api/render?id=%s&which=edit" % urllib.parse.quote(sid)) if has_edit else None,
                "build_changed": bool(changed), "has_edit": has_edit,
                "note": "스프라이트는 타일+팔레트에서 1:1 표시 → 이 디코드 렌더가 인게임 픽셀과 동일(에뮬 불필요)."}

    def _static(self, rel):
        path = (STATIC / rel)
        if not path.exists():
            return self._send(404, {"error": "missing " + rel})
        self._send(200, path.read_bytes(), MIME.get(path.suffix, "application/octet-stream"))

    def _sprites(self, q):
        sprites = sprite_list()
        typ = (q.get("type", [""])[0] or "").strip()
        src = (q.get("source", [""])[0] or "").strip()
        qs = (q.get("q", [""])[0] or "").strip()
        cur = (q.get("curated", [""])[0] or "").strip()
        # text 필터: 기본 1(번역 대상 텍스트 스프라이트만). text=0이면 전체.
        text_only = (q.get("text", ["1"])[0] or "1") != "0"
        section = (q.get("section", [""])[0] or "").strip()  # 허브: common/part1/part2/all
        edited = {p.stem for p in EDIT_DIR.glob("*.png")} if EDIT_DIR.exists() else set()
        out = []
        n_text = 0
        for s in sprites:
            is_text, desc = classify_sprite(s.get("source"))
            sec = sprite_section(s.get("source"))
            if is_text:
                n_text += 1
            if text_only and not is_text:
                continue
            if section in ("common", "part1", "part2") and sec != section:
                continue
            if typ and s.get("type") != typ:
                continue
            if cur == "1" and not s.get("curated"):
                continue
            if src and src not in (s.get("source") or ""):
                continue
            if qs and qs not in (s.get("id") or "") and qs not in (s.get("source") or "") and qs not in (desc or ""):
                continue
            out.append({**s, "edited": s.get("id") in edited, "desc": desc, "is_text": is_text, "section": sec})
        # 인게임 출력 순서: 화면 등장 랭크 → offset
        out.sort(key=lambda s: (sprite_order_rank(s.get("source")), int(s.get("offset_int") or int(s.get("offset", "0x0"), 16))))
        types = sorted({s.get("type", "") for s in sprites})
        return {"count": len(out), "total": len(sprites), "text_total": n_text, "text_only": text_only,
                "types": types, "edited_count": len(edited), "sprites": out[:3000]}

    def _tile(self, q):
        sid = q.get("id", [""])[0]
        which = (q.get("which", ["current"])[0] or "current").strip()
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if which not in ("current", "orig"):
            return {"ok": False, "error": "which=current|orig"}
        # 편집본(인덱스) 우선
        ov = load_json(OVERRIDES_PATH, {}) or {}
        rec = ov.get(override_id(sp))
        desc = sp.get("desc_override") or classify_sprite(sp.get("source"))[1]
        has_os = get_layout(sid) is not None
        if which == "orig":
            dec = decode_indices(sp)
            if dec is None:
                return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
            grid, w, h, cols = dec
            return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                    "type": sp.get("type"), "palette": default_palette_for(sp), "indices": grid,
                    "edited": False, "offset": sp.get("offset"), "source": sp.get("source"),
                    "desc": desc, "has_onscreen": has_os, "which": "orig"}
        if rec and rec.get("indices"):
            grid = rec["indices"]
            h = len(grid); w = len(grid[0]) if grid else 0
            return {"ok": True, "id": sid, "width": w, "height": h,
                    "tile_cols": w // 8, "type": sp.get("type"),
                    "palette": palette_for(sp), "indices": grid, "edited": True,
                    "offset": sp.get("offset"), "source": sp.get("source"), "desc": desc, "has_onscreen": has_os}
        dec = decode_current_indices(sp)
        if dec is None:
            return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
        grid, w, h, cols = dec
        return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                "type": sp.get("type"), "palette": palette_for(sp), "indices": grid,
                "edited": False, "offset": sp.get("offset"), "source": sp.get("source"), "desc": desc, "has_onscreen": has_os}

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"error": "bad json: %r" % e})
        if u.path == "/api/save":
            return self._send(200, self._save(body))
        if u.path == "/api/revert":
            return self._send(200, self._revert(body))
        if u.path == "/api/setpalette":
            return self._send(200, self._setpalette(body))
        if u.path == "/api/build":
            return self._send(200, self._build(body))
        return self._send(404, {"error": "not found"})

    def _build(self, body):
        """편집(sprites_overrides.json)을 ROM에 반영 = build_korean_full.py 전체 재빌드
        (overrides가 라벨 자동그리기 뒤 최종 오버레이로 적용). 완료 후 패치 ROM 캐시 무효화."""
        import subprocess
        global _PATCHED
        try:
            proc = subprocess.run([_sys.executable, str(ROOT / "tools" / "build_korean_full.py")],
                                  capture_output=True, text=True, cwd=str(ROOT), timeout=900)
        except Exception as e:
            return {"ok": False, "error": "빌드 실행 실패: %r" % e}
        _PATCHED = None  # 재빌드 ROM 재로딩
        applied = ""
        for line in (proc.stdout or "").splitlines():
            if "스프라이트 편집 적용" in line:
                applied = line.strip()
        return {"ok": proc.returncode == 0, "applied": applied,
                "log_tail": (proc.stdout or "")[-1200:],
                "error": (proc.stderr or "")[-800:] if proc.returncode != 0 else None}

    def _setpalette(self, body):
        """픽셀 편집 없이 팔레트만 override에 고정(다음 조회/비교에 반영)."""
        sid = body.get("id")
        palette = body.get("palette")
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not palette or not isinstance(palette, list):
            return {"ok": False, "error": "palette(16×[r,g,b]) 필요"}
        key = override_id(sp)
        with _LOCK:
            ov = load_json(OVERRIDES_PATH, {}) or {}
            rec = ov.get(key, {})
            rec.update({"offset": sp.get("offset"), "type": sp.get("type"), "palette": palette})
            ov[key] = rec
            save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid, "base_id": key}

    def _save(self, body):
        sid = body.get("id")
        indices = body.get("indices")
        palette = body.get("palette")
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not indices or not isinstance(indices, list) or not indices[0]:
            return {"ok": False, "error": "indices(2D 0..15) 필요"}
        h = len(indices)
        w = len(indices[0])
        try:
            enc = encode_indices(indices, w, h)
        except Exception as e:
            return {"ok": False, "error": "encode: %r" % e}
        if sp.get("type") == "lz77":
            fits = (len(enc) == sp.get("size"))  # 타일수 동일해야 함(압축적합은 apply에서)
        else:
            fits = (len(enc) <= (sp.get("size") or len(enc)))
        key = override_id(sp)
        with _LOCK:
            ov = load_json(OVERRIDES_PATH, {}) or {}
            ov[key] = {"offset": sp.get("offset"), "type": sp.get("type"),
                       "width": w, "height": h, "indices": indices, "palette": palette,
                       "raw_len": len(enc), "orig_size": sp.get("size"),
                       "comp_size": sp.get("comp_size"), "fits_raw": fits}
            save_json(OVERRIDES_PATH, ov)
            try:
                EDIT_DIR.mkdir(parents=True, exist_ok=True)
                pal = [tuple(c) for c in (palette or [list(c) for c in ES.GRAYSCALE])]
                ES.render_png(indices, w, h, pal, str(EDIT_DIR / f"{key}.png"), scale=2)
            except Exception:
                pass
        return {"ok": True, "id": sid, "base_id": key, "raw_len": len(enc), "orig_size": sp.get("size"),
                "fits_raw": fits,
                "note": "편집 저장됨(overrides). '적용'(/api/build)으로 재빌드하면 ROM에 반영 — "
                        "synthetic은 perm 역변환, lz77은 재압축≤comp_size, raw는 size 이내(타입 %s)." % sp.get("type")}

    def _revert(self, body):
        sid = body.get("id")
        key = override_id(sid)
        with _LOCK:
            ep = EDIT_DIR / f"{key}.png"
            if ep.exists():
                ep.unlink()
            ov = load_json(OVERRIDES_PATH, {})
            ov.pop(key, None)
            save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid, "base_id": key}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"스프라이트 픽셀 에디터: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print(f"  index: {INDEX_PATH}  edits: {EDIT_DIR}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
