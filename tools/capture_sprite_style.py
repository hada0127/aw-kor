#!/usr/bin/env python3
"""Capture Part 1 menu sprite states from a fresh boot of each supplied ROM."""
import argparse
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

from qa_visual_regions import MGBADriver, drive_part1_menu_from_coldboot
import build_title_hangul as th
from sprite_relocations import resolve_sprite_offset

ROOT = Path(__file__).resolve().parents[1]


def observed_sprites(rom, oam, obj, dispcnt):
    if dispcnt & 0x80 or not dispcnt & 0x1000:
        return []
    offsets = set(th.PART1_LOGO_BLOCK_CAPACITY) | set(th.PART1_MODE_OPTION_BLOCK_CAPACITY)
    offsets.update(row[1] for row in th.PART1_SUBMENU_LOGO_BLOCKS)
    shapes = (((8, 8), (16, 16), (32, 32), (64, 64)),
              ((16, 8), (32, 8), (32, 16), (64, 32)),
              ((8, 16), (8, 32), (16, 32), (32, 64)))
    if not dispcnt & 0x40:
        raise ValueError('capture expects the verified Part 1 1D OBJ mapping')
    objects = []
    for index in range(128):
        a0, a1, a2 = struct.unpack_from('<3H', oam, index * 8)
        if ((a0 >> 10) & 3) >= 2:
            continue
        if (not a0 & 0x100 and a0 & 0x200) or a0 & 0x2000 or a0 >> 14 == 3:
            continue
        width, height = shapes[a0 >> 14][a1 >> 14]
        x, y = a1 & 511, a0 & 255
        x = x - 512 if x >= 256 else x
        y = y - 256 if y >= 160 else y
        if x >= 240 or y >= 160 or x + width <= 0 or y + height <= 0:
            continue
        start, size = (a2 & 1023) * 32, width * height // 2
        pixels = obj[start:start + size]
        if pixels and any(pixels):
            objects.append((index, a2 >> 12, pixels))
    result = []
    for offset in sorted(offsets):
        raw, _ = th.lz77_decompress(rom, resolve_sprite_offset(rom, offset))
        required = {i // 32 for i in range(0, len(raw), 32) if any(raw[i:i + 32])}
        matched, indices, banks = set(), set(), set()
        for index, bank, pixels in objects:
            for start in range(0, len(raw) - len(pixels) + 1, 32):
                if raw[start:start + len(pixels)] == pixels:
                    matched.update(range(start // 32, (start + len(pixels)) // 32))
                    indices.add(index)
                    banks.add(bank)
        if matched:
            result.append({'source': hex(offset), 'oam': sorted(indices), 'banks': sorted(banks),
                           'nonblank_tiles': len(required), 'matched_nonblank_tiles': len(required & matched),
                           'all_nonblank_tiles_resident_in_visible_objects': required <= matched})
    return result


def capture(rom, out, harness):
    out.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom.resolve(), out.resolve(), harness.resolve())
    records = []
    rom_bytes = rom.read_bytes()

    def shot(name, route):
        driver.shot(name)
        artifacts = {}
        for region, addr, size in (("pal", 0x05000000, 1024), ("oam", 0x07000000, 1024),
                                  ("obj", 0x06010000, 32768), ("dispcnt", 0x04000000, 2)):
            path = (out / f"{name}.{region}").resolve()
            response = driver.cmd(f"dumpmem {addr:x} {size} {path}")
            if response != f"OK dumpmem {size}" or path.stat().st_size != size:
                raise RuntimeError(response)
        for suffix in ('png', 'pal', 'oam', 'obj', 'dispcnt'):
            artifacts[suffix] = hashlib.sha256((out / f'{name}.{suffix}').read_bytes()).hexdigest()
        consumers = observed_sprites(rom_bytes, (out / f'{name}.oam').read_bytes(),
                                    (out / f'{name}.obj').read_bytes(),
                                    int.from_bytes((out / f'{name}.dispcnt').read_bytes(), 'little'))
        records.append({"name": name, "route": route, "artifacts_sha256": artifacts,
                        "observed_sprites": consumers})

    try:
        drive_part1_menu_from_coldboot(driver)
        root = (out / "fresh_root.ss0").resolve()
        response = driver.cmd(f"savestate {root}")
        if not response.endswith("ok=1"):
            raise RuntimeError(response)
        for branch in range(3):
            # Same-run state only. No state or VRAM crosses between ROMs.
            driver.loadstate(root)
            route = ["part1_menu", *(["DOWN"] * branch)]
            for _ in range(branch):
                driver.press("DOWN", after=120)
            shot(f"main_{branch}", list(route))
            driver.press("A", after=200)
            route.append("A")
            for item in range(8):
                shot(f"branch_{branch}_item_{item}", list(route))
                driver.press("DOWN", after=120)
                route.append("DOWN")
        manifest = {"rom": str(rom), "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
                    "entry": "fresh_boot", "captured_at": datetime.now(timezone.utc).isoformat(),
                    "states": records}
        (out / "capture.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=ROOT / "temp/mgbah")
    args = parser.parse_args()
    capture(args.rom, args.out, args.harness)
    print(args.out / "capture.json")


if __name__ == "__main__":
    main()
