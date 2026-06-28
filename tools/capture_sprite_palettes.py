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

# 대표 화면 fresh-boot 네비(PRAM이 실시간 로드된 상태에서 덤프)
FRESH_SCREENS = {
    "title": {"nav": [["frames", 600]], "scope": "starter", "note": "coldboot title"},
    "part1_select": {
        "nav": [["frames", 480], ["press", "A", 200], ["press", "START", 240], ["frames", 120]],
        "scope": "starter",
        "note": "coldboot part select with Part1 highlighted",
    },
    "part2_title": {
        "nav": [["frames", 480], ["press", "A", 200], ["press", "START", 200],
                ["press", "DOWN", 120], ["press", "A", 240], ["frames", 120]],
        "scope": "starter",
        "note": "coldboot Part2 title/splash",
    },
    "part2_menu": {
        "nav": [["frames", 480], ["press", "A", 200], ["press", "START", 200], ["press", "DOWN", 120],
                ["press", "A", 240], ["press", "START", 240], ["press", "A", 240], ["press", "A", 240]],
        "scope": "starter",
        "note": "coldboot Part2 main menu with CO portrait",
    },
}

# 깊은 전투/CO/유닛 화면은 이미 current scene evidence에서 쓰는 state를 로드해 PRAM만 보강한다.
STATE_SCREENS = {
    "part1_battle_day1": {
        "state": "temp/scene_entrypoints/part1_main_sweep_current/state_014.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Part1 battle day banner/map sprites",
    },
    "part1_info_list": {
        "state": "temp/auto_battle_end/state_007.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Part1 unit/army info list",
    },
    "part1_unit_detail": {
        "state": "temp/scene_entrypoints/first_battle_day2_after_info_probe/R_START.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Part1 unit detail/help with unit sprite panel",
    },
    "part2_co_profile": {
        "state": "temp/scene_entrypoints/part2_menu_sweep/state_036.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Part2 CO profile with portrait and power list",
    },
    "part2_unit_info": {
        "state": "temp/scene_entrypoints/part2_menu_sweep/state_031.ss0",
        "nav": [["press", "RIGHT", 120], ["press", "A", 240]],
        "scope": "e5b_battle_co_unit",
        "note": "Part2 production/unit info panel",
    },
    "common_battle_system": {
        "state": "temp/scene_entrypoints/part2_menu_sweep/state_040.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Common battle system menu",
    },
    "aw1_power_menu": {
        "state": "temp/b84_aw1_power_select_probe_20260628/rec1_meter_100k/menu_open.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "AW1 in-battle CO power menu",
    },
    "part2_battle_overlay": {
        "state": "temp/scene_entrypoints/part2_day_overlay_fine_frames/state_f060.ss0",
        "nav": [],
        "scope": "e5b_battle_co_unit",
        "note": "Part2 battle day overlay/map sprites",
    },
}


def bgr555_to_rgb(v):
    return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_nav(drv, nav):
    for s in nav:
        if s[0] == "frames":
            drv.frames(int(s[1]))
        elif s[0] == "press":
            drv.press(s[1], 6, int(s[2]) if len(s) > 2 else 120)


def capture(tag, spec, *, mode):
    OUT.mkdir(parents=True, exist_ok=True)
    drv = MGBADriver(ROM, OUT, HARNESS)
    try:
        drv.frames(1)
        if mode == "state":
            state = ROOT / spec["state"]
            if not state.exists():
                raise FileNotFoundError(state)
            drv.loadstate(state)
            drv.frames(30)
        apply_nav(drv, spec["nav"])
        drv.shot(f"{tag}_screen")
        drv.cmd(f"dumpmem 5000000 1024 {OUT / (tag + '.pal')}")  # 0x400 = 512색 BGR555
    finally:
        drv.close()


def main():
    capture_specs = []
    for tag, spec in FRESH_SCREENS.items():
        capture_specs.append((tag, spec, "fresh_nav"))
    for tag, spec in STATE_SCREENS.items():
        capture_specs.append((tag, spec, "state"))

    for tag, spec, mode in capture_specs:
        capture(tag, spec, mode=mode)
        print("captured", tag)
    lib, seen, raw_dumps = [], set(), []
    for tag, spec, mode in capture_specs:
        path = OUT / (tag + ".pal")
        raw = path.read_bytes()
        screen_png = OUT / f"{tag}_screen.png"
        rec = {
            "screen": tag,
            "scope": spec["scope"],
            "note": spec["note"],
            "capture_mode": mode,
            "path": str(path.relative_to(ROOT)),
            "size": len(raw),
            "sha256": sha256(path),
            "screenshot": str(screen_png.relative_to(ROOT)) if screen_png.exists() else None,
            "screenshot_sha256": sha256(screen_png) if screen_png.exists() else None,
        }
        if mode == "state":
            state = ROOT / spec["state"]
            rec["source_state"] = str(state.relative_to(ROOT))
            rec["source_state_sha256"] = sha256(state)
        raw_dumps.append(rec)
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
                lib.append({
                    "name": f"{tag}_{region}{b}",
                    "screen": tag,
                    "scope": spec["scope"],
                    "region": region,
                    "bank": b,
                    "colors": rgb,
                })
    out = {
        "_doc": "실기 팔레트 RAM(PRAM) 0x05000000..0x050003ff(1024B, BG 0x05000000 + OBJ 0x05000200) "
                "대표 화면과 current state 기반 전투/CO/유닛 화면 캡처에서 추출한 16색 뱅크. "
                "스프라이트 에디터 색 지정용. 재생성: tools/capture_sprite_palettes.py",
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
            "first_seen_new_banks_by_route": {tag: sum(1 for e in lib if e["screen"] == tag)
                                                for tag, _spec, _mode in capture_specs},
            "first_seen_new_banks_by_scope": {scope: sum(1 for e in lib if e["scope"] == scope)
                                               for scope in sorted({spec["scope"] for _tag, spec, _mode in capture_specs})},
        },
        "palettes": lib,
    }
    LIB.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {LIB} — {len(lib)} banks (OBJ {sum(1 for e in lib if e['region']=='OBJ')})")


if __name__ == "__main__":
    main()
