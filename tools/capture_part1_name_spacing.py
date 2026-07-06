#!/usr/bin/env python3
"""Capture original-vs-final Part 1 player-name spacing evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_visual_regions import MGBADriver, PART1_MENU_PRENAV  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_ROM = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
FINAL_ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = ROOT / "temp" / "mgbah"
TEMP_OUT = ROOT / "temp" / "part1_name_spacing_20260706"
DOC_OUT = ROOT / "docs" / "screenshots" / "part1_name_spacing_2026-07-06"
FRAMES = [
    ("00_name_grid_preview", "name preview"),
    ("01_name_confirm", "name confirm"),
    ("02_post_name_greeting", "post-name greeting"),
    ("03_catherine_intro", "next dialogue"),
    ("04_redstar_intro", "later dialogue"),
]
BOTTOM_CROP = (0, 104, 240, 156)
NAME_SUFFIX_SLOTS = {
    0xDF1F62: "name_control_suffix_copy_1",
    0xDF1FA2: "name_control_suffix_copy_2",
    0xDF230A: "name_control_suffix_copy_3",
    0xDF2390: "name_control_suffix_copy_4",
    0xDF26F2: "name_control_suffix_copy_5",
    0xDF2786: "name_control_suffix_copy_6",
    0xDF5DA9: "operation_room_suffix",
    0xDF8E4D: "post_name_greeting_suffix",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_syllable_codes() -> dict[str, int]:
    data = json.loads((ROOT / "data" / "syllable_to_code_2350.json").read_text(encoding="utf-8"))
    raw = data.get("map", data)
    out: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str) and len(key) == 1:
            out[key] = int(value, 16) if isinstance(value, str) else int(value)
    return out


def encode_name_suffix() -> bytes:
    code = load_syllable_codes()["님"]
    return bytes([code >> 8, code & 0xFF]) + b"\x20" * 4


def capture_sequence(rom: Path, tag: str, out_dir: Path, harness: Path) -> dict[str, str]:
    case_dir = out_dir / tag
    case_dir.mkdir(parents=True, exist_ok=True)
    shots: dict[str, str] = {}
    driver = MGBADriver(rom, case_dir, harness)
    try:
        driver.frames(480)
        for key in PART1_MENU_PRENAV:
            driver.press(key, after=120)
        driver.shot("00_name_grid_preview")
        driver.press("START", after=120)
        driver.shot("01_name_confirm")
        driver.press("A", after=120)
        driver.shot("02_post_name_greeting")
        driver.press("A", after=120)
        driver.shot("03_catherine_intro")
        driver.press("A", after=120)
        driver.shot("04_redstar_intro")
        driver.cmd(f"savestate {case_dir / 'final.ss0'}")
    finally:
        driver.close()

    for frame, _title in FRAMES:
        shots[frame] = str((case_dir / f"{frame}.png").relative_to(ROOT))
    return shots


def build_sheet(out_dir: Path, doc_dir: Path) -> Path:
    width, height = 240, 160
    zoom = 3
    crop_w = BOTTOM_CROP[2] - BOTTOM_CROP[0]
    crop_h = BOTTOM_CROP[3] - BOTTOM_CROP[1]
    row_h = 18 + height + 8 + crop_h * zoom + 12
    sheet = Image.new("RGB", (width * 2, row_h * len(FRAMES)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for row, (frame, title) in enumerate(FRAMES):
        y = row * row_h
        draw.text((4, y + 2), f"{title} / {frame}", fill=(255, 255, 255))
        for col, tag in enumerate(("original", "final")):
            x = col * width
            img = Image.open(out_dir / tag / f"{frame}.png").convert("RGB")
            color = (180, 220, 255) if tag == "original" else (180, 255, 180)
            draw.text((x + 4, y + 18), tag, fill=color)
            sheet.paste(img, (x, y + 34))
            crop = img.crop(BOTTOM_CROP).resize((crop_w * zoom, crop_h * zoom), Image.Resampling.NEAREST)
            sheet.paste(crop, (x, y + 34 + height + 8))
    doc_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = doc_dir / "original_vs_final_name_spacing.png"
    sheet.save(sheet_path)
    return sheet_path


def copy_frames_to_docs(shots: dict[str, dict[str, str]], doc_dir: Path) -> dict[str, dict[str, str]]:
    persistent: dict[str, dict[str, str]] = {}
    for tag, frames in shots.items():
        tag_dir = doc_dir / tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        persistent[tag] = {}
        for frame, rel_path in frames.items():
            src = ROOT / rel_path
            dst = tag_dir / f"{frame}.png"
            shutil.copyfile(src, dst)
            persistent[tag][frame] = str(dst.relative_to(ROOT))
    return persistent


def suffix_status(rom: Path) -> list[dict[str, object]]:
    data = rom.read_bytes()
    expected = encode_name_suffix()
    rows = []
    for addr, label in NAME_SUFFIX_SLOTS.items():
        current = data[addr:addr + 6]
        rows.append({
            "addr": f"0x{addr:08X}",
            "label": label,
            "expected_hex": expected.hex(),
            "current_hex": current.hex(),
            "matches": current == expected,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, default=ORIGINAL_ROM)
    parser.add_argument("--final", type=Path, default=FINAL_ROM)
    parser.add_argument("--harness", type=Path, default=HARNESS)
    parser.add_argument("--out-dir", type=Path, default=TEMP_OUT)
    parser.add_argument("--doc-dir", type=Path, default=DOC_OUT)
    args = parser.parse_args()

    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    shots = {
        "original": capture_sequence(args.original, "original", args.out_dir, args.harness),
        "final": capture_sequence(args.final, "final", args.out_dir, args.harness),
    }
    sheet = build_sheet(args.out_dir, args.doc_dir)
    persistent_shots = copy_frames_to_docs(shots, args.doc_dir)
    report = {
        "original_rom": str(args.original.relative_to(ROOT)),
        "original_sha256": sha256(args.original),
        "final_rom": str(args.final.relative_to(ROOT)),
        "final_sha256": sha256(args.final),
        "route": "coldboot -> Part1 new game -> accept generated/default name -> A",
        "comparison_note": (
            "This is a same-route suffix-spacing comparison. The original route yields "
            "a one-kana generated name, while the patched route yields a two-syllable "
            "Hangul generated name; the sheet is used to verify that the honorific "
            "attaches without a visible leading gap."
        ),
        "shots": persistent_shots,
        "temp_shots": shots,
        "sheet": str(sheet.relative_to(ROOT)),
        "suffix_slots": suffix_status(args.final),
        "visual_review_note": "The sheet is the visual spacing evidence; issue_count only gates suffix bytes.",
    }
    report["issue_count"] = sum(1 for row in report["suffix_slots"] if not row["matches"])
    report_path = args.doc_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "sheet": str(sheet.relative_to(ROOT)),
        "report": str(report_path.relative_to(ROOT)),
        "issue_count": report["issue_count"],
    }, ensure_ascii=False))
    return 1 if report["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
