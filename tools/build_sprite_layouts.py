#!/usr/bin/env python3
"""스프라이트 온스크린 레이아웃 추출 — WYSIWYG(실제 화면 형태) 표시·편집 토대.

대표 화면을 헤드리스 캡처(sprite_onscreen.capture_screen)하고, 각 텍스트 스프라이트의
타일(패치 ROM 디코드)을 OBJ VRAM과 매칭해 base tile index를 찾은 뒤, 그 범위를 참조하는
OAM 셀(위치/크기/flip/팔레트뱅크)을 모아 **레이아웃**을 만든다. 레이아웃 + 현재 타일로
스프라이트의 실제 화면 형태를 재조립할 수 있다(편집기 /api/onscreen).

한계: 한 캡처는 그 순간 OAM에 올라온 셀만 본다. 멀티라벨 블록(예 모드메뉴 라벨)은
여러 메뉴 상태 캡처를 합쳐야 전부 모인다. 현재는 캡처된 상태의 가시 셀만 추출.

출력: data/sprite_layouts.json {sprite_id:{screen,base,obj1d,w,h,x0,y0,cells:[...]}}
실행: python3 tools/build_sprite_layouts.py
"""
import json
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
import export_sprites as ES  # noqa: E402
import sprite_onscreen as SO  # noqa: E402

PATCHED = os.path.join(BASE, "output", "game_wars_korean_full.gba")
INDEX = os.path.join(BASE, "data", "sprites_index.json")
OUT = os.path.join(BASE, "data", "sprite_layouts.json")
SCREENS = ["title", "part1_select", "part2_menu"]
SHAPES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8),
          (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4),
          (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}


def tb(d, t):
    return bytes(d[t * 32:t * 32 + 32])


def extract(sp, state, rom):
    """스프라이트의 OBJ VRAM base + OAM 셀 레이아웃. 못 찾으면 None."""
    off = sp.get("offset_int") or int(sp.get("offset", "0x0"), 16)
    if sp.get("type") == "lz77":
        dec = ES.lz77_decompress(rom, off)
        if not dec:
            return None
        tiles = dec[0]
    else:
        tiles = rom[off: off + (sp.get("size") or 0)]
    ntiles = len(tiles) // 32
    if ntiles == 0:
        return None
    objv = state["vram"][0x10000:]
    vmap = {}
    for vt in range(len(objv) // 32):
        b = tb(objv, vt)
        if any(b):
            vmap.setdefault(b, vt)
    base = None
    for t in range(ntiles):
        b = tb(tiles, t)
        if any(b) and b in vmap:
            base = vmap[b] - t
            break
    if base is None:
        return None
    obj1d = (struct.unpack("<H", state["io"][0:2])[0] >> 6) & 1
    oam = state["oam"]
    cells = []
    for i in range(128):
        a0, a1, a2 = struct.unpack("<HHH", oam[i * 8:i * 8 + 6])
        if (a0 >> 8) & 3 == 2:
            continue
        shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
        if (shape, size) not in SHAPES:
            continue
        tw, th = SHAPES[(shape, size)]
        tile = a2 & 0x3FF
        if not (base <= tile < base + ntiles):
            continue
        y = a0 & 0xFF; x = a1 & 0x1FF
        if x >= 240:
            x -= 512
        if y >= 160:
            y -= 256
        cells.append({"x": x, "y": y, "tw": tw, "th": th, "fh": (a1 >> 12) & 1,
                      "fv": (a1 >> 13) & 1, "tile_off": tile - base, "bank": (a2 >> 12) & 0xF})
    if not cells:
        return None
    xs = [c["x"] for c in cells] + [c["x"] + c["tw"] * 8 for c in cells]
    ys = [c["y"] for c in cells] + [c["y"] + c["th"] * 8 for c in cells]
    return {"base": base, "obj1d": obj1d, "ntiles": ntiles,
            "x0": min(xs), "y0": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys),
            "cells": cells}


def main():
    rom = open(PATCHED, "rb").read()
    sprites = json.load(open(INDEX, encoding="utf-8"))["sprites"]
    layouts = {}
    for screen in SCREENS:
        try:
            state = SO.capture_screen(screen)
        except Exception as e:
            print("capture fail", screen, e); continue
        n = 0
        for sp in sprites:
            if sp["id"] in layouts:
                continue
            lay = extract(sp, state, rom)
            if lay:
                lay["screen"] = screen
                layouts[sp["id"]] = lay
                n += 1
        print("screen %-14s → %d sprite layouts" % (screen, n))
    pal_by_screen = {s: ("temp/screen_state/%s.pal" % s) for s in SCREENS}
    out = {"_doc": "스프라이트 온스크린 레이아웃(OAM 셀). 레이아웃+현재 타일로 실제 화면 형태 재조립. "
                   "재생성: tools/build_sprite_layouts.py", "pal_by_screen": pal_by_screen, "layouts": layouts}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s — %d sprite layouts" % (OUT, len(layouts)))


if __name__ == "__main__":
    main()
