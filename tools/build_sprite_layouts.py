#!/usr/bin/env python3
"""스프라이트 온스크린 레이아웃 추출(전체 화면 캡처 집계) — WYSIWYG 편집 토대.

여러 화면 캡처(VRAM/OAM/팔레트/IO 덤프)를 모아, 각 스프라이트가 **실제 화면에 출력되는 형태**를
재조립할 레이아웃을 만든다. OBJ(OAM) + BG(타일맵) 둘 다 추출. 같은 로드(같은 base tile)에서 나온
여러 상태 캡처의 셀을 병합해 멀티라벨 블록도 모은다.

캡처 소스(모두 패치 ROM 기준):
  - temp/screen_state/*.{vram,oam,pal,io}  (큐레이트 화면: sprite_onscreen.capture_screen)
  - temp/cap_*/scr_*.{vram,oam,pal,io}      (auto_playthrough --dump-state 게임 진행 화면)

셀 스키마: {x,y(화면px), tw,th, fh,fv, tile_off, bank, palbase(0=BG,256=OBJ)}
출력: data/sprite_layouts.json {sprite_id:{screen,pal_file,obj1d,tile_cols,ntiles,x0,y0,w,h,cells}}
실행: python3 tools/build_sprite_layouts.py
"""
import glob
import json
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
import export_sprites as ES  # noqa: E402

PATCHED = os.path.join(BASE, "output", "game_wars_korean_full.gba")
INDEX = os.path.join(BASE, "data", "sprites_index.json")
OUT = os.path.join(BASE, "data", "sprite_layouts.json")
SHAPES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8),
          (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4),
          (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}


def tb(d, t):
    return bytes(d[t * 32:t * 32 + 32])


def probe_tiles(tiles, ntiles, k=4):
    """가장 distinctive(바이트 다양)한 비공백 타일 인덱스 k개 — 매칭 충돌 최소화."""
    scored = sorted((t for t in range(ntiles) if len(set(tb(tiles, t))) >= 6),
                    key=lambda t: -len(set(tb(tiles, t))))
    return scored[:k]


def verify_base(tiles, ntiles, region, base):
    """base에서 sprite 타일이 region과 얼마나 일치하는지 (match, checked)."""
    n = len(region) // 32
    match = checked = 0
    for t in range(ntiles):
        b = tb(tiles, t)
        if not any(b):
            continue
        checked += 1
        vt = base + t
        if 0 <= vt < n and tb(region, vt) == b:
            match += 1
    return match, checked


def index_state(st):
    """상태 1회 전처리: OBJ vmap+OAM셀, 활성 BG별 charblock vmap+타일맵셀. (sprite 매칭 가속)"""
    vram, oam, io = st["vram"], st["oam"], st["io"]
    dispcnt = struct.unpack("<H", io[0:2])[0]
    obj1d = (dispcnt >> 6) & 1
    # OBJ
    objv = vram[0x10000:]
    obj_vmap = {}
    for vt in range(len(objv) // 32):
        b = tb(objv, vt)
        if any(b):
            obj_vmap.setdefault(b, vt)
    oam_cells = []
    for i in range(128):
        a0, a1, a2 = struct.unpack("<HHH", oam[i * 8:i * 8 + 6])
        if (a0 >> 8) & 3 == 2:
            continue
        shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
        if (shape, size) not in SHAPES:
            continue
        tw, th = SHAPES[(shape, size)]
        y = a0 & 0xFF; x = a1 & 0x1FF
        x = x - 512 if x >= 240 else x
        y = y - 256 if y >= 160 else y
        oam_cells.append((a2 & 0x3FF, x, y, tw, th, (a1 >> 12) & 1, (a1 >> 13) & 1, (a2 >> 12) & 0xF))
    # BG: 활성 BG별 (cbb vmap, 타일맵 셀)
    bgs = {}
    for bg in range(4):
        if not ((dispcnt >> (8 + bg)) & 1):
            continue
        bgcnt = struct.unpack("<H", io[8 + bg * 2:10 + bg * 2])[0]
        cbb = ((bgcnt >> 2) & 3) * 0x4000
        sbb = ((bgcnt >> 8) & 0x1F) * 0x800
        size = (bgcnt >> 14) & 3
        sw = 64 if size in (1, 3) else 32
        sh = 64 if size in (2, 3) else 32
        if cbb not in bgs:
            region = bytes(vram[cbb:cbb + 0x8000])
            vmap = {}
            for rvt in range(len(region) // 32):
                b = region[rvt * 32:rvt * 32 + 32]
                if any(b):
                    vmap.setdefault(b, rvt)
            bgs[cbb] = {"vmap": vmap, "cells": [], "region": region}
        cells = bgs[cbb]["cells"]
        blocks_w = sw // 32
        for blk in range((sw // 32) * (sh // 32)):
            b0 = sbb + blk * 0x800
            bx = (blk % blocks_w) * 32; by = (blk // blocks_w) * 32
            for ty in range(32):
                row = b0 + ty * 64
                for tx in range(32):
                    o = row + tx * 2
                    if o + 2 > len(vram):
                        continue
                    e = vram[o] | (vram[o + 1] << 8)
                    sx = (bx + tx) * 8; sy = (by + ty) * 8
                    if sx >= 256 or sy >= 256:
                        continue
                    cells.append((e & 0x3FF, sx, sy, (e >> 10) & 1, (e >> 11) & 1, (e >> 12) & 0xF))
    return {"obj1d": obj1d, "obj_vmap": obj_vmap, "objv": objv, "oam": oam_cells, "bgs": bgs, "pal": st["pal"]}


def _find_verified_base(tiles, ntiles, vmap, region, probes):
    """probe(distinctive) 타일로 base 후보를 잡고, 다른 probe들이 그 base에서 일치(불일치 0)하면 검증.
    부분 로드(라벨 일부만 VRAM)에도 견고 — 셀은 별도 content-check로 정밀 필터."""
    nv = len(region) // 32
    for t in probes:
        cand = vmap.get(tb(tiles, t))
        if cand is None:
            continue
        base = cand - t
        match = mism = 0
        for p in probes:
            vt = base + p
            if 0 <= vt < nv:
                rb = tb(region, vt)
                if rb == tb(tiles, p):
                    match += 1
                elif any(rb):
                    mism += 1
        # distinctive probe 1개 일치 + 모순 0이면 채택(셀은 content-check로 정밀 필터되므로 안전)
        if match >= 1 and mism == 0:
            return base
    return None


def match_obj(sidx, tiles, ntiles, probes):
    base = _find_verified_base(tiles, ntiles, sidx["obj_vmap"], sidx["objv"], probes)
    if base is None:
        return None, []
    objv, cells = sidx["objv"], []
    nv = len(objv) // 32
    for tile, x, y, tw, th, fh, fv, bank in sidx["oam"]:
        if not (base <= tile < base + ntiles):
            continue
        # 셀 첫 타일 내용이 sprite 타일과 일치할 때만(스퍼리어스 컷)
        st = tile - base
        if 0 <= tile < nv and tb(objv, tile) == tb(tiles, st):
            cells.append({"x": x, "y": y, "tw": tw, "th": th, "fh": fh, "fv": fv,
                          "tile_off": st, "bank": bank, "palbase": 256})
    return base, cells


def match_bg(sidx, tiles, ntiles, probes):
    best = (None, [])
    for cbb, bgd in sidx["bgs"].items():
        base = _find_verified_base(tiles, ntiles, bgd["vmap"], bgd["region"], probes)
        if base is None:
            continue
        region = bgd["region"]; nv = len(region) // 32
        cells = []
        for tid, sx, sy, fh, fv, bank in bgd["cells"]:
            if not (base <= tid < base + ntiles):
                continue
            st = tid - base
            if 0 <= tid < nv and region[tid * 32:tid * 32 + 32] == tb(tiles, st):
                cells.append({"x": sx, "y": sy, "tw": 1, "th": 1, "fh": fh, "fv": fv,
                              "tile_off": st, "bank": bank, "palbase": 0})
        if len(cells) > len(best[1]):
            best = (("bg%d" % base), cells)
    return best


def gather_states():
    """모든 캡처 상태 세트(.io 존재 기준) → [(tag, paths)]."""
    states = []
    for io in sorted(glob.glob(os.path.join(BASE, "temp", "screen_state", "*.io")) +
                     glob.glob(os.path.join(BASE, "temp", "cap_*", "scr_*.io"))):
        stem = io[:-3]
        if all(os.path.exists(stem + e) for e in (".vram", ".oam", ".pal")):
            states.append((os.path.relpath(stem, BASE),
                           {"vram": open(stem + ".vram", "rb").read(),
                            "oam": open(stem + ".oam", "rb").read(),
                            "pal": stem + ".pal", "io": open(stem + ".io", "rb").read()}))
    return states


def sprite_tiles(sp, rom):
    off = sp.get("offset_int") or int(sp.get("offset", "0x0"), 16)
    if sp.get("type") == "lz77":
        dec = ES.lz77_decompress(rom, off)
        return dec[0] if dec else b""
    return rom[off: off + (sp.get("size") or 0)]


def main():
    rom = open(PATCHED, "rb").read()
    sprites = json.load(open(INDEX, encoding="utf-8"))["sprites"]
    raw_states = gather_states()
    print("capture states:", len(raw_states))
    states = [(tag, index_state(st)) for tag, st in raw_states]
    layouts = {}
    from collections import defaultdict
    for sp in sprites:
        tiles = sprite_tiles(sp, rom)
        ntiles = len(tiles) // 32
        if ntiles == 0:
            continue
        probes = probe_tiles(tiles, ntiles)
        if not probes:
            continue  # distinctive 타일 없음(거의 빈/단색) → 신뢰 매칭 불가
        # 같은 (kind,base) 로드끼리 셀 병합 → 최다 셀 그룹 채택(멀티상태 병합, 크로스화면 오염 회피)
        groups = defaultdict(lambda: {"cells": {}, "pal": None, "obj1d": 1})
        for tag, sidx in states:
            ob, oc = match_obj(sidx, tiles, ntiles, probes)
            if oc:
                g = groups[("obj", ob)]; g["pal"] = g["pal"] or sidx["pal"]; g["obj1d"] = sidx["obj1d"]
                for c in oc:
                    g["cells"][(c["x"], c["y"], c["tw"], c["th"], c["tile_off"], c["fh"], c["fv"])] = c
            bk, bc = match_bg(sidx, tiles, ntiles, probes)
            if bc:
                g = groups[("bg", bk)]; g["pal"] = g["pal"] or sidx["pal"]
                for c in bc:
                    g["cells"][(c["x"], c["y"], c["tw"], c["th"], c["tile_off"], c["fh"], c["fv"])] = c
        if not groups:
            continue
        bestk = max(groups, key=lambda k: len(groups[k]["cells"]))
        g = groups[bestk]
        best = list(g["cells"].values())
        xs = [c["x"] for c in best] + [c["x"] + c["tw"] * 8 for c in best]
        ys = [c["y"] for c in best] + [c["y"] + c["th"] * 8 for c in best]
        cols = sp.get("tile_cols") or ES.guess_cols(ntiles)
        layouts[sp["id"]] = {"screen": bestk[0], "pal_file": os.path.relpath(g["pal"], BASE),
                             "obj1d": g["obj1d"], "tile_cols": cols, "ntiles": ntiles,
                             "x0": min(xs), "y0": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys),
                             "cells": best}
    json.dump({"_doc": "스프라이트 온스크린 레이아웃(OBJ+BG, 다화면 집계). 재생성: tools/build_sprite_layouts.py",
               "layouts": layouts}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s — %d sprite layouts" % (OUT, len(layouts)))


if __name__ == "__main__":
    main()
