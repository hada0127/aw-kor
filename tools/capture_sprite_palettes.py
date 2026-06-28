#!/usr/bin/env python3
"""실기 팔레트 RAM(PRAM) 캡처 → 스프라이트 에디터용 대표 팔레트 라이브러리 생성.

스프라이트 타일 데이터엔 색 정보가 없다(게임이 런타임에 팔레트 RAM 0x05000000에 따로 로드).
이 도구는 대표 화면(타이틀/선택/메뉴)으로 헤드리스 네비 후 팔레트 RAM(512색=BG 16뱅크 +
OBJ 16뱅크)을 덤프하고, 비자명한 16색 뱅크를 추출해 data/sprite_palettes.json 으로 저장한다.
전투 중 유닛/CO 초상처럼 별도 진행 route에서 로드되는 팔레트는 후속 캡처 대상이다.
스프라이트 에디터(:8781)가 이 뱅크들을 색 지정 드롭다운으로 제공한다.

실행: python3 tools/capture_sprite_palettes.py
"""
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import MGBADriver  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path(os.environ.get("MGBAH", "/tmp/mgbah"))
OUT = ROOT / "temp" / "pal_capture"
LIB = ROOT / "data" / "sprite_palettes.json"

# 대표 화면 fresh-boot 네비(palette RAM이 실시간 로드된 상태에서 덤프)
SCREENS = {
    "title": [["frames", 600]],
    "part1_select": [["frames", 480], ["press", "A", 200], ["press", "START", 240], ["frames", 120]],
    "part2_title": [["frames", 480], ["press", "A", 200], ["press", "START", 200],
                    ["press", "DOWN", 120], ["press", "A", 240], ["frames", 120]],
    "part2_menu": [["frames", 480], ["press", "A", 200], ["press", "START", 200], ["press", "DOWN", 120],
                   ["press", "A", 240], ["press", "START", 240], ["press", "A", 240], ["press", "A", 240]],
}


def bgr555_to_rgb(v):
    return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def capture(tag, nav):
    OUT.mkdir(parents=True, exist_ok=True)
    drv = MGBADriver(ROM, OUT, HARNESS)
    try:
        drv.frames(1)
        for s in nav:
            if s[0] == "frames":
                drv.frames(int(s[1]))
            elif s[0] == "press":
                drv.press(s[1], 6, int(s[2]) if len(s) > 2 else 120)
        drv.shot(f"{tag}_screen")
        drv.cmd(f"dumpmem 5000000 1024 {OUT / (tag + '.pal')}")  # 0x400 = 512색 BGR555
    finally:
        drv.close()


def main():
    for tag, nav in SCREENS.items():
        capture(tag, nav)
        print("captured", tag)
    lib, seen, raw_dumps = [], set(), []
    for tag in SCREENS:
        path = OUT / (tag + ".pal")
        raw = path.read_bytes()
        screen_png = OUT / f"{tag}_screen.png"
        raw_dumps.append({
            "screen": tag,
            "path": str(path.relative_to(ROOT)),
            "size": len(raw),
            "sha256": sha256(path),
            "screenshot": str(screen_png.relative_to(ROOT)) if screen_png.exists() else None,
            "screenshot_sha256": sha256(screen_png) if screen_png.exists() else None,
        })
        cols = [struct.unpack("<H", raw[i * 2:i * 2 + 2])[0] for i in range(512)]
        for region, base in (("BG", 0), ("OBJ", 256)):
            for b in range(16):
                bank = cols[base + b * 16: base + b * 16 + 16]
                rgb = [bgr555_to_rgb(v) for v in bank]
                if len({tuple(c) for c in rgb}) < 4:  # 비자명 뱅크만
                    continue
                key = tuple(bank)
                if key in seen:
                    continue
                seen.add(key)
                lib.append({"name": f"{tag}_{region}{b}", "screen": tag, "region": region, "bank": b, "colors": rgb})
    out = {
        "_doc": "실기 팔레트 RAM(PRAM) 0x05000000..0x050003ff(1024B, BG 0x05000000 + OBJ 0x05000200) "
                "대표 화면 캡처에서 추출한 16색 뱅크. 스프라이트 에디터 색 지정용 스타터셋. "
                "전투/CO 초상 팔레트는 별도 route 캡처가 필요하다. 재생성: tools/capture_sprite_palettes.py",
        "source_rom": str(ROM.relative_to(ROOT)),
        "source_rom_sha256": sha256(ROM),
        "harness": str(HARNESS),
        "capture": {
            "address": "0x05000000",
            "bytes": 1024,
            "bg_palette_address": "0x05000000",
            "obj_palette_address": "0x05000200",
            "raw_dumps": raw_dumps,
        },
        "summary": {
            "count_semantics": "global exact-match dedupe; route counts are first-seen new unique banks, not per-route total banks",
            "unique_palettes": len(lib),
            "unique_BG": sum(1 for e in lib if e["region"] == "BG"),
            "unique_OBJ": sum(1 for e in lib if e["region"] == "OBJ"),
            "first_seen_new_banks_by_route": {tag: sum(1 for e in lib if e["screen"] == tag) for tag in SCREENS},
        },
        "palettes": lib,
    }
    LIB.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {LIB} — {len(lib)} banks (OBJ {sum(1 for e in lib if e['region']=='OBJ')})")


if __name__ == "__main__":
    main()
