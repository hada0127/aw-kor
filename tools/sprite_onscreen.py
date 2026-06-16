#!/usr/bin/env python3
"""온스크린(WYSIWYG) 스프라이트 조립 엔진 — 실제 화면 형태 복원 + 편집 매핑 토대.

스프라이트는 ROM에 타일 뱅크로 저장돼 타일시트가 화면 모습과 다르다. 이 모듈은 해당
스프라이트가 표시되는 실제 화면의 그래픽 상태(VRAM/OAM/팔레트/IO)를 헤드리스로 캡처하고,
OAM(OBJ)·타일맵(BG)으로 **실제 화면에 출력되는 형태**를 재조립한다. 더불어 화면 픽셀→
(소스 타일, flip) 매핑을 만들어 WYSIWYG 편집(화면 형태로 그리고 ROM 타일로 역기록)을 가능케 한다.

검증(2026-06-16): part2 메뉴에서 상점/도전/캠페인/자유전/편집 OBJ 라벨 + CO 조립 성공
(temp/screen_state/obj_layer.png).

CLI:
  python3 tools/sprite_onscreen.py --screen part2_menu          # 캡처+조립 렌더
  python3 tools/sprite_onscreen.py --screen part2_menu --bg 0   # BG0 레이어
"""
from __future__ import annotations
import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path("/tmp/mgbah")
STATE_DIR = ROOT / "temp" / "screen_state"

# 텍스트 스프라이트가 등장하는 화면 + fresh-boot 네비.
SCREENS = {
    "title": [["frames", 600]],
    "part1_select": [["frames", 480], ["press", "A", 200], ["press", "START", 240], ["frames", 120]],
    "part2_menu": [["frames", 480], ["press", "A", 200], ["press", "START", 200], ["press", "DOWN", 120],
                   ["press", "A", 240], ["press", "START", 240], ["press", "A", 240], ["press", "A", 240]],
}

# (shape,size) → (tiles_w, tiles_h)
OBJ_DIMS = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8),
            (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4),
            (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}


def capture_screen(screen, tag=None):
    """헤드리스 네비 후 VRAM/OAM/팔레트/IO 덤프. 상태 dict 반환."""
    from qa_visual_regions import MGBADriver
    nav = SCREENS[screen]
    tag = tag or screen
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    drv = MGBADriver(ROM, STATE_DIR, HARNESS)
    try:
        drv.frames(1)
        for s in nav:
            if s[0] == "frames":
                drv.frames(int(s[1]))
            elif s[0] == "press":
                drv.press(s[1], 6, int(s[2]) if len(s) > 2 else 120)
        drv.cmd(f"dumpvram {STATE_DIR / (tag + '.vram')}")
        drv.cmd(f"dumpmem 7000000 0x400 {STATE_DIR / (tag + '.oam')}")
        drv.cmd(f"dumpmem 5000000 0x400 {STATE_DIR / (tag + '.pal')}")
        drv.cmd(f"dumpmem 4000000 0x60 {STATE_DIR / (tag + '.io')}")
        drv.shot(tag)
    finally:
        drv.close()
    return load_state(tag)


def load_state(tag):
    d = STATE_DIR
    return {
        "vram": (d / (tag + ".vram")).read_bytes(),
        "oam": (d / (tag + ".oam")).read_bytes(),
        "pal": (d / (tag + ".pal")).read_bytes(),
        "io": (d / (tag + ".io")).read_bytes(),
        "tag": tag,
    }


def _col(pal, i):
    v = struct.unpack("<H", pal[i * 2:i * 2 + 2])[0]
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def reconstruct_obj(state):
    """OAM+OBJ VRAM → (PIL 240x160 RGBA OBJ 레이어, cellmap).
    cellmap[(px,py)] = (obj_tile_index, local_x, local_y) — 편집 역매핑용(추후 ROM 타일 연결)."""
    from PIL import Image
    vram, oam, pal, io = state["vram"], state["oam"], state["pal"], state["io"]
    obj1d = (struct.unpack("<H", io[0:2])[0] >> 6) & 1
    im = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    px = im.load()
    cellmap = {}

    def objpx(tile, x, y):
        o = 0x10000 + tile * 32 + y * 4 + x // 2
        if o >= len(vram):
            return 0
        b = vram[o]
        return (b & 0xF) if x % 2 == 0 else (b >> 4) & 0xF

    # OAM은 뒤(높은 인덱스)일수록 아래 우선순위 → 앞에서부터 그리되 priority는 생략(라벨 단순)
    for i in range(128):
        a0, a1, a2 = struct.unpack("<HHH", oam[i * 8:i * 8 + 6])
        if (a0 >> 8) & 3 == 2:
            continue  # disabled
        if (a0 >> 13) & 1:
            continue  # 256-color (대상 라벨은 4bpp)
        shape, size = (a0 >> 14) & 3, (a1 >> 14) & 3
        if (shape, size) not in OBJ_DIMS:
            continue
        tw, th = OBJ_DIMS[(shape, size)]
        y = a0 & 0xFF; x = a1 & 0x1FF
        if x >= 240:
            x -= 512
        if y >= 160:
            y -= 256
        fh, fv = (a1 >> 12) & 1, (a1 >> 13) & 1
        tile0, bank = a2 & 0x3FF, (a2 >> 12) & 0xF
        for ty in range(th):
            for tx in range(tw):
                t = tile0 + (ty * tw + tx if obj1d else ty * 32 + tx)
                for yy in range(8):
                    for xx in range(8):
                        idx = objpx(t, 7 - xx if fh else xx, 7 - yy if fv else yy)
                        if idx == 0:
                            continue
                        c = _col(pal, 256 + bank * 16 + idx)
                        sx = x + (tw - 1 - tx if fh else tx) * 8 + xx
                        sy = y + (th - 1 - ty if fv else ty) * 8 + yy
                        if 0 <= sx < 240 and 0 <= sy < 160:
                            px[sx, sy] = (c[0], c[1], c[2], 255)
                            cellmap[(sx, sy)] = (t, (7 - xx if fh else xx), (7 - yy if fv else yy))
    return im, cellmap


def reconstruct_bg(state, bg):
    """BG 레이어 조립(charBase/screenBase는 BGcnt에서). text 라벨 BG용."""
    from PIL import Image
    vram, pal, io = state["vram"], state["pal"], state["io"]
    bgcnt = struct.unpack("<H", io[8 + bg * 2:10 + bg * 2])[0]
    cbb = ((bgcnt >> 2) & 3) * 0x4000
    sbb = ((bgcnt >> 8) & 0x1F) * 0x800
    size = (bgcnt >> 14) & 3
    sw = 512 if size in (1, 3) else 256
    sh = 512 if size in (2, 3) else 256
    im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    px = im.load()

    def bgpx(tile, x, y):
        o = cbb + tile * 32 + y * 4 + x // 2
        if o >= len(vram):
            return 0
        b = vram[o]
        return (b & 0xF) if x % 2 == 0 else (b >> 4) & 0xF

    blocks_w = sw // 256
    for blk in range((sw // 256) * (sh // 256)):
        base = sbb + blk * 0x800
        bx = (blk % blocks_w) * 32
        by = (blk // blocks_w) * 32
        for ty in range(32):
            for tx in range(32):
                e = struct.unpack("<H", vram[base + (ty * 32 + tx) * 2: base + (ty * 32 + tx) * 2 + 2])[0]
                tid = e & 0x3FF; fh = (e >> 10) & 1; fv = (e >> 11) & 1; pb = (e >> 12) & 0xF
                for yy in range(8):
                    for xx in range(8):
                        idx = bgpx(tid, 7 - xx if fh else xx, 7 - yy if fv else yy)
                        if idx == 0:
                            continue
                        c = _col(pal, pb * 16 + idx)
                        px[(bx + tx) * 8 + xx, (by + ty) * 8 + yy] = (c[0], c[1], c[2], 255)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", default="part2_menu", choices=list(SCREENS))
    ap.add_argument("--bg", type=int, default=None)
    ap.add_argument("--no-capture", action="store_true", help="기존 덤프 재사용")
    args = ap.parse_args()
    state = load_state(args.screen) if args.no_capture else capture_screen(args.screen)
    if args.bg is not None:
        im = reconstruct_bg(state, args.bg)
        out = STATE_DIR / f"{args.screen}_bg{args.bg}.png"
    else:
        im, _ = reconstruct_obj(state)
        out = STATE_DIR / f"{args.screen}_obj.png"
    im.resize((im.width * 2, im.height * 2)).save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
