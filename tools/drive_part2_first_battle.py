#!/usr/bin/env python3
"""Drive Part 2 first battle from a savestate using real controller input.

This is a reproducible helper for scene-entrypoint capture. It never mutates
game memory; memory reads are used only to locate the cursor and live units so
that the same route can be replayed after ROM rebuilds.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_visual_regions import KEYS, MGBADriver  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
CURSOR_ADDR = 0x030034F4
UNIT_TABLE_ADDR = 0x02022584
UNIT_RECORD_SIZE = 12
PLAYER_RECORDS = 3


def label_font(size: int = 12) -> ImageFont.ImageFont:
    for font_path in (
        "/Library/Fonts/NanumGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ):
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def montage(shots: list[tuple[str, Image.Image]], out_path: Path, cols: int = 5) -> None:
    if not shots:
        return
    cw, ch, hd, pad = 240, 160, 18, 4
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + hd + pad) + pad), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    font = label_font()
    for idx, (label, image) in enumerate(shots):
        row, col = divmod(idx, cols)
        x = pad + col * (cw + pad)
        y = pad + row * (ch + hd + pad)
        draw.text((x, y), label[:36], font=font, fill=(235, 235, 235))
        sheet.paste(image, (x, y + hd))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


class BattleDriver:
    def __init__(self, rom: Path, out_dir: Path, harness: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.driver = MGBADriver(rom, out_dir, harness)
        self.shots: list[tuple[str, Image.Image]] = []
        self.events: list[dict[str, object]] = []
        self.shot_index = 0

    def close(self) -> None:
        self.driver.close()

    def dumpmem(self, addr: int, size: int, name: str) -> bytes:
        path = self.out_dir / name
        self.driver.cmd(f"dumpmem {addr:x} {size} {path}")
        return path.read_bytes()

    def cursor(self) -> tuple[int, int]:
        data = self.dumpmem(CURSOR_ADDR, 4, "cursor.bin")
        return data[0] | (data[1] << 8), data[2] | (data[3] << 8)

    def units(self) -> list[dict[str, int]]:
        data = self.dumpmem(UNIT_TABLE_ADDR, UNIT_RECORD_SIZE * 20, "units.bin")
        units: list[dict[str, int]] = []
        for idx in range(PLAYER_RECORDS):
            rec = data[idx * UNIT_RECORD_SIZE : (idx + 1) * UNIT_RECORD_SIZE]
            hp = rec[0]
            unit_type = rec[8]
            x, y = rec[10], rec[11]
            if hp and unit_type:
                units.append({"index": idx, "hp": hp, "type": unit_type, "x": x, "y": y})
        return units

    def press(self, key: str, *, hold: int = 6, after: int = 80) -> None:
        self.driver.cmd(f"keys {KEYS[key]}")
        self.driver.frames(hold)
        self.driver.cmd("keys 0")
        self.driver.frames(after)

    def press_many(self, keys: list[str], *, after: int = 80) -> None:
        for key in keys:
            self.press(key, after=after)

    def shot(self, label: str, *, save_state: bool = False) -> None:
        image = self.driver.shot(f"step_{self.shot_index:04d}")
        state_path = None
        if save_state:
            state_path = self.out_dir / f"state_{self.shot_index:04d}.ss0"
            self.driver.cmd(f"savestate {state_path}")
        cursor = self.cursor()
        units = self.units()
        self.shots.append((f"{self.shot_index:04d}:{label}", image.copy()))
        self.events.append(
            {
                "index": self.shot_index,
                "label": label,
                "png": str(self.out_dir / f"step_{self.shot_index:04d}.png"),
                "state": str(state_path) if state_path else None,
                "cursor": cursor,
                "units": units,
            }
        )
        self.shot_index += 1

    def move_cursor_to(self, x: int, y: int) -> None:
        cx, cy = self.cursor()
        horizontal = "RIGHT" if x > cx else "LEFT"
        for _ in range(abs(x - cx)):
            self.press(horizontal, after=24)
        vertical = "DOWN" if y > cy else "UP"
        for _ in range(abs(y - cy)):
            self.press(vertical, after=24)

    def wait_unit(self, unit: dict[str, int], *, advance: bool) -> None:
        self.move_cursor_to(unit["x"], unit["y"])
        self.shot(f"unit{unit['index']}_select", save_state=True)
        self.press("A", after=80)
        if advance and unit["type"] in {1}:
            # Infantry in this tutorial can usually move a few tiles east. If
            # the target is invalid the game simply keeps the movement cursor,
            # and the following confirm sequence will be visible in the trace.
            self.press_many(["RIGHT", "RIGHT"], after=30)
        self.press_many(["A", "A"], after=90)
        self.shot(f"unit{unit['index']}_done", save_state=True)

    def end_turn(self) -> None:
        # From map: A opens command menu on an empty tile. If a menu is already
        # open, B returns to map and the sequence retries cleanly enough for
        # this first-battle route.
        self.press("B", after=60)
        self.press("A", after=70)
        self.press_many(["DOWN", "DOWN", "DOWN", "DOWN", "A"], after=90)
        self.shot("after_end_turn", save_state=True)
        # Clear day overlays, CO popups, and R-button info tutorial if present.
        self.press_many(["A", "A", "R", "B", "A", "A"], after=130)
        self.shot("after_dialog_clear", save_state=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--advance", action="store_true", help="try simple eastward infantry movement before wait")
    parser.add_argument("--rom", default=str(ROOT / "output" / "game_wars_korean_full.gba"))
    parser.add_argument("--out", default=str(ROOT / "temp" / "scene_entrypoints" / "part2_first_battle_drive"))
    parser.add_argument("--harness", default="/tmp/mgbah")
    args = parser.parse_args()

    rom = Path(args.rom)
    if not rom.is_absolute():
        rom = ROOT / rom
    state = Path(args.state)
    if not state.is_absolute():
        state = ROOT / state
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    battle = BattleDriver(rom, out_dir, Path(args.harness))
    try:
        battle.driver.frames(1)
        battle.driver.loadstate(state)
        battle.driver.frames(40)
        battle.shot("start", save_state=True)
        for turn in range(args.turns):
            units = battle.units()
            battle.events.append({"turn": turn + 1, "phase": "units", "units": units})
            for unit in units:
                battle.wait_unit(unit, advance=args.advance)
            battle.end_turn()
        battle.driver.cmd(f"savestate {out_dir / 'final.ss0'}")
    finally:
        battle.close()

    montage(battle.shots, out_dir / "filmstrip.png")
    (out_dir / "events.json").write_text(json.dumps(battle.events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_dir}")
    print(f"shots={len(battle.shots)}")


if __name__ == "__main__":
    main()
