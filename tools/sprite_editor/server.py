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

_LOCK = threading.Lock()
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".png": "image/png", ".json": "application/json; charset=utf-8"}


def load_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sprite_list():
    d = load_json(INDEX_PATH, {"sprites": []})
    return d.get("sprites", []) if isinstance(d, dict) else d


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


def decode_from_rom(rom, sp):
    """주어진 ROM 바이트에서 sprite 디코드 → (grid,w,h,cols). 실패 시 None."""
    off = sp.get("offset_int")
    if off is None:
        off = int(sp.get("offset", "0x0"), 16)
    typ = sp.get("type")
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
    """원본 ROM에서 디코드(편집기 기본)."""
    return decode_from_rom(rom_bytes(), sp)


def render_compare_png(sid, which):
    """원본(orig)/패치빌드(patched)/편집(edit) 스프라이트를 PNG 바이트로 렌더.
    스프라이트는 타일+팔레트에서 1:1 표시되므로 이 디코드 렌더 = 인게임 픽셀과 동일."""
    sp = sprite_by_id(sid)
    if sp is None:
        return None
    pal = [tuple(c) for c in palette_for(sp)]
    grid = w = h = None
    if which == "edit":
        ov = load_json(OVERRIDES_PATH, {}) or {}
        rec = ov.get(sid)
        if rec and rec.get("indices"):
            grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
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


def current_tiles(sp):
    """스프라이트의 현재 타일 바이트(편집본 우선→패치 ROM 디코드). 4bpp, 32B/타일."""
    ov = load_json(OVERRIDES_PATH, {}) or {}
    rec = ov.get(sp.get("id"))
    if rec and rec.get("indices"):
        grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
        return encode_indices(grid, w, h)
    dec = decode_from_rom(patched_bytes(), sp)
    if dec is None:
        return b""
    grid, w, h, _ = dec
    return encode_indices(grid, w, h)


def render_onscreen_png(sid):
    """레이아웃(OAM 셀)+현재 타일+캡처 팔레트로 실제 화면 형태 재조립 PNG. 없으면 None."""
    import struct as _s
    lay = load_layouts().get("layouts", {}).get(sid)
    sp = sprite_by_id(sid)
    if not lay or sp is None:
        return None
    tiles = current_tiles(sp)
    if not tiles:
        return None
    palp = lay.get("pal_file") or load_layouts().get("pal_by_screen", {}).get(lay.get("screen"))
    palb = (ROOT / palp).read_bytes() if palp and (ROOT / palp).exists() else b"\x00" * 1024
    def col(i):
        v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
        return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)
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
                            r, g, b = col(c.get("palbase", 256) + c["bank"] * 16 + idx)
                            px[sx, sy] = (r, g, b, 255)
    import io as _io
    buf = _io.BytesIO()
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(buf, "PNG")
    return buf.getvalue()


def palette_library():
    d = load_json(PALLIB_PATH, {}) or {}
    return d.get("palettes", [])


def default_palette_for(sp):
    """source 화면 추정 → 그 화면의 실기 OBJ 팔레트(첫 뱅크)를 기본값으로. 없으면 grayscale.
    (정확한 뱅크는 사용자가 팔레트 드롭다운으로 선택; OAM 정보 없이 자동은 화면까지만 추정)"""
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
    rec = ov.get(sp.get("id"))
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
    "battle_start_day_overlay_obj": "전투 시작 ‘N일째’ 오버레이",
    "result_success_overlay_obj": "결과: 성공 오버레이", "result_failure_overlay_obj": "결과: 실패 오버레이",
    "result_summary_obj": "결과 요약", "result_congratulations_obj": "결과: 축하",
    "domino_co_name_obj": "도미노 CO 이름", "campaign_header_obj": "캠페인 헤더",
    "level_label_obj": "레벨 라벨", "redstar_region_obj": "레드스타 영역 라벨",
    "mission_number_obj": "미션 번호", "lets_go_obj": "‘출격’ 라벨", "check_label_obj": "체크 라벨",
    "splash_logo_bg": "2편 스플래시 로고", "prologue_logo_obj": "프롤로그 로고",
    "mission_start_obj": "미션 시작", "air_mission_title_obj": "에어 미션 타이틀",
    "air_supremacy_title_obj": "제공권 타이틀", "damage_forecast_label_obj": "데미지 예측 라벨",
    "menu_newspaper_bg": "메뉴 신문 배경(텍스트 포함)", "intro_campaign_residual_graphics": "인트로 캠페인 잔여 그래픽",
    "world_map_label_tiles": "월드맵 지명 라벨", "info_screen_bg_labels": "정보 화면 라벨",
    "full_info_spec_obj_label": "상세정보 스펙 라벨", "check_label": "체크 라벨", "battle_day_banner": "전투 N일째 배너",
}


def classify_sprite(source):
    """(is_text, desc_ko). 텍스트=번역 대상 라벨/로고. 비텍스트(배경/캐릭터/폰트/미분류) → 기본 제외."""
    s = (source or "")
    sl = s.lower()
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
    if "part1_" in sl and "_lz77_off" in sl:
        for k, v in PART1_LOGO_KO.items():
            if "part1_" + k.lower() in sl or k.lower() in sl:
                return (True, "1편 화면 로고: " + v)
        return (True, "1편 화면 로고")
    if "copyright" in sl:
        return (True, "타이틀 카피라이트(© 표기)")
    if "select_obj" in sl:
        return (False, "1/2편 선택 화면 캐릭터/그래픽")
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
        from collections import Counter
        sid = q.get("id", [""])[0]
        lay = load_layouts().get("layouts", {}).get(sid)
        sp = sprite_by_id(sid)
        if not lay or sp is None:
            return {"ok": False, "error": "no layout for %s" % sid}
        palp = lay.get("pal_file") or load_layouts().get("pal_by_screen", {}).get(lay.get("screen"))
        palb = (ROOT / palp).read_bytes() if palp and (ROOT / palp).exists() else b"\x00" * 1024
        # 지배적 셀의 (palbase,bank)로 편집 팔레트
        dom = Counter((c.get("palbase", 256), c["bank"]) for c in lay["cells"]).most_common(1)[0][0]
        palbase, bank = dom

        def col(i):
            v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
            return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]
        dec = decode_indices(sp)
        cols = dec[3] if dec else (sp.get("tile_cols") or 1)
        return {"ok": True, "w": lay["w"], "h": lay["h"], "x0": lay["x0"], "y0": lay["y0"],
                "obj1d": lay.get("obj1d", 1), "tile_cols": cols, "cells": lay["cells"],
                "palette": [col(palbase + bank * 16 + i) for i in range(16)], "bank": bank,
                "screen": lay.get("screen")}

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
        has_edit = sid in ov and bool(ov[sid].get("indices"))
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
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        # 편집본(인덱스) 우선
        ov = load_json(OVERRIDES_PATH, {}) or {}
        rec = ov.get(sid)
        desc = classify_sprite(sp.get("source"))[1]
        has_os = sid in load_layouts().get("layouts", {})
        if rec and rec.get("indices"):
            grid = rec["indices"]
            h = len(grid); w = len(grid[0]) if grid else 0
            return {"ok": True, "id": sid, "width": w, "height": h,
                    "tile_cols": w // 8, "type": sp.get("type"),
                    "palette": palette_for(sp), "indices": grid, "edited": True,
                    "offset": sp.get("offset"), "source": sp.get("source"), "desc": desc, "has_onscreen": has_os}
        dec = decode_indices(sp)
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
        return self._send(404, {"error": "not found"})

    def _setpalette(self, body):
        """픽셀 편집 없이 팔레트만 override에 고정(다음 조회/비교에 반영)."""
        sid = body.get("id")
        palette = body.get("palette")
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not palette or not isinstance(palette, list):
            return {"ok": False, "error": "palette(16×[r,g,b]) 필요"}
        with _LOCK:
            ov = load_json(OVERRIDES_PATH, {}) or {}
            rec = ov.get(sid, {})
            rec.update({"offset": sp.get("offset"), "type": sp.get("type"), "palette": palette})
            ov[sid] = rec
            save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid}

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
        with _LOCK:
            ov = load_json(OVERRIDES_PATH, {}) or {}
            ov[sid] = {"offset": sp.get("offset"), "type": sp.get("type"),
                       "width": w, "height": h, "indices": indices, "palette": palette,
                       "raw_len": len(enc), "orig_size": sp.get("size"),
                       "comp_size": sp.get("comp_size"), "fits_raw": fits}
            save_json(OVERRIDES_PATH, ov)
            try:
                EDIT_DIR.mkdir(parents=True, exist_ok=True)
                pal = [tuple(c) for c in (palette or [list(c) for c in ES.GRAYSCALE])]
                ES.render_png(indices, w, h, pal, str(EDIT_DIR / f"{sid}.png"), scale=2)
            except Exception:
                pass
        return {"ok": True, "id": sid, "raw_len": len(enc), "orig_size": sp.get("size"),
                "fits_raw": fits,
                "note": "편집 저장됨. ROM 역기록은 tools/apply_sprite_edits.py (타입 %s, lz77은 재압축 ≤comp_size 검증)." % sp.get("type")}

    def _revert(self, body):
        sid = body.get("id")
        with _LOCK:
            ep = EDIT_DIR / f"{sid}.png"
            if ep.exists():
                ep.unlink()
            ov = load_json(OVERRIDES_PATH, {})
            ov.pop(sid, None)
            save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid}


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
