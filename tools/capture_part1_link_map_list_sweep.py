#!/usr/bin/env python3
"""Re-capture the Part 1 link map-list full sweep evidence.

This recreates the documented route in
docs/screenshots/part1_link_map_list_full_sweep_2026-06-28/report.json:

  part1_menu_from_coldboot -> DOWN -> A -> DOWN -> A
  then capture 180 frames, pressing DOWN after each screenshot.

The output is a current-ROM report plus contact sheets used by
tools/verify_dist_integrity.py to reject stale Part1 map-label evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from qa_visual_regions import MGBADriver, drive_part1_menu_from_coldboot  # noqa: E402

DEFAULT_ROM = ROOT / "output" / "game_wars_korean_full.gba"
DEFAULT_HARNESS = ROOT / "temp" / "mgbah"
DEFAULT_WORK = ROOT / "temp" / "part1_link_map_list_full_sweep_20260706"
DEFAULT_DOCS = ROOT / "docs" / "screenshots" / "part1_link_map_list_full_sweep_2026-06-28"
GBA_W, GBA_H = 240, 160
LIST_CROP_BOX = (0, 0, GBA_W, GBA_H)
LOW_BRIGHT_THRESHOLD = 500


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def font(size: int) -> ImageFont.ImageFont:
    for path in [
        "/Library/Fonts/NanumGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def frame_metrics(crop: Image.Image, step: int) -> dict:
    rgb = crop.convert("RGB")
    data = list(rgb.getdata())
    bright = 0
    yellowish = 0
    dark = 0
    for r, g, b in data:
        if r + g + b >= 510:
            bright += 1
        if r > 160 and g > 130 and b < 90:
            yellowish += 1
        if r + g + b <= 90:
            dark += 1
    digest = hashlib.sha256(rgb.tobytes()).hexdigest()
    return {
        "bright_pixels": bright,
        "yellowish_pixels": yellowish,
        "dark_pixels": dark,
        "crop_sha256": digest,
        "step": step,
    }


def panel(img: Image.Image, title: str, scale: int = 2) -> Image.Image:
    body = img.convert("RGB").resize((img.width * scale, img.height * scale), Image.NEAREST)
    header = 22
    out = Image.new("RGB", (body.width, body.height + header), (24, 24, 26))
    out.paste(body, (0, header))
    draw = ImageDraw.Draw(out)
    draw.text((6, 4), title, fill=(238, 238, 238), font=font(13))
    return out


def build_sheet(panels: list[Image.Image], cols: int, out_path: Path) -> None:
    if not panels:
        raise ValueError("no panels")
    pad = 8
    cw = max(p.width for p in panels)
    ch = max(p.height for p in panels)
    rows = (len(panels) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + pad * (cols + 1), rows * ch + pad * (rows + 1)), (14, 14, 16))
    for i, p in enumerate(panels):
        y, x = divmod(i, cols)
        sheet.paste(p, (pad + x * (cw + pad), pad + y * (ch + pad)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def capture_sweep(rom: Path, harness: Path, work: Path, steps: int) -> tuple[list[dict], list[Path], list[Path]]:
    frames_dir = work / "frames"
    crops_dir = work / "crops"
    frames_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    metrics: list[dict] = []
    frame_paths: list[Path] = []
    crop_paths: list[Path] = []
    driver = MGBADriver(rom, work, harness)
    try:
        drive_part1_menu_from_coldboot(driver)
        driver.press("DOWN", after=120)
        driver.press("A", after=180)
        driver.press("DOWN", after=120)
        driver.press("A", after=180)
        driver.frames(30)

        for step in range(steps):
            img = driver.shot(f"sweep_{step:03d}")
            frame_path = frames_dir / f"step_{step:03d}.png"
            crop_path = crops_dir / f"step_{step:03d}.png"
            shutil.copy2(work / f"sweep_{step:03d}.png", frame_path)
            crop = img.crop(LIST_CROP_BOX)
            crop.save(crop_path)
            frame_paths.append(frame_path)
            crop_paths.append(crop_path)
            metrics.append(frame_metrics(crop, step))
            driver.press("DOWN", after=160)
    finally:
        driver.close()
    return metrics, frame_paths, crop_paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(DEFAULT_ROM))
    ap.add_argument("--harness", default=str(DEFAULT_HARNESS))
    ap.add_argument("--work", default=str(DEFAULT_WORK))
    ap.add_argument("--docs", default=str(DEFAULT_DOCS))
    ap.add_argument("--steps", type=int, default=180)
    args = ap.parse_args()

    source_rom = Path(args.rom)
    harness = Path(args.harness)
    work = Path(args.work)
    docs = Path(args.docs)
    if not source_rom.exists():
        raise SystemExit(f"ROM missing: {source_rom}")
    if not harness.exists():
        raise SystemExit(f"mGBA harness missing: {harness}")

    work.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    isolated_rom = work / "current_isolated.gba"
    shutil.copy2(source_rom, isolated_rom)

    metrics, frame_paths, crop_paths = capture_sweep(isolated_rom, harness, work, args.steps)
    unique = len({row["crop_sha256"] for row in metrics})
    low_bright_steps = [
        row["step"] for row in metrics if int(row["bright_pixels"]) < LOW_BRIGHT_THRESHOLD
    ]

    page_size = 60
    for page_idx in range(3):
        start = page_idx * page_size
        page_crops = crop_paths[start:start + page_size]
        panels = [panel(Image.open(path), f"{start + i:03d}") for i, path in enumerate(page_crops)]
        build_sheet(panels, 5, docs / f"list_sweep_page{page_idx + 1}.png")

    full_panels = [
        panel(Image.open(frame_paths[step]), f"{step:03d}", scale=2)
        for step in range(0, len(frame_paths), 10)
    ]
    build_sheet(full_panels, 3, docs / "full_frame_every10.png")

    docs_map = {
        "list_sweep_page1": rel(docs / "list_sweep_page1.png"),
        "list_sweep_page2": rel(docs / "list_sweep_page2.png"),
        "list_sweep_page3": rel(docs / "list_sweep_page3.png"),
        "full_frame_every10": rel(docs / "full_frame_every10.png"),
    }
    docs_sha256 = {
        label: sha256(ROOT / path)
        for label, path in docs_map.items()
    }

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rom": rel(isolated_rom),
        "rom_sha256": sha256(isolated_rom),
        "source_rom_sha256": sha256(source_rom),
        "route": [
            "part1_menu_from_coldboot",
            "DOWN",
            "A",
            "DOWN",
            "A",
            "then DOWN after each screenshot",
        ],
        "step_count": args.steps,
        "unique_list_crop_count": unique,
        "duplicate_list_crop_count": args.steps - unique,
        "list_crop_box": list(LIST_CROP_BOX),
        "list_crop_note": "The crop is the full visible frame; uniqueness proves 180 captured frame/crop states, not 180 distinct map-label strings.",
        "low_bright_threshold": LOW_BRIGHT_THRESHOLD,
        "low_bright_steps": low_bright_steps,
        "docs": docs_map,
        "docs_sha256": docs_sha256,
        "metrics": metrics,
    }
    (docs / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "report": rel(docs / "report.json"),
        "rom_sha256": report["rom_sha256"],
        "step_count": args.steps,
        "unique_list_crop_count": unique,
        "low_bright_steps": low_bright_steps,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
