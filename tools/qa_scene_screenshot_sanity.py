#!/usr/bin/env python3
"""Sanity-check current mGBA scene screenshots.

This is intentionally not OCR.  It catches stale provenance, wrong frame size,
near-blank captures, and unusually low-information frames in the current
capture manifest.  Known logo/transition frames are reported as observations so
they stay visible without failing the release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHOT_DIR = ROOT / "temp" / "scene_screenshots"
DEFAULT_MANIFEST = DEFAULT_SHOT_DIR / "manifest.json"
DEFAULT_OUT = ROOT / "temp" / "scene_screenshots_sanity"
ROM = ROOT / "output" / "game_wars_korean_full.gba"

KNOWN_LOW_INFO = {
    "01_coldboot_nintendo",
    "scene_20_part2_intro_newspaper",
    "scene_20a_part2_menu_newspaper_bg",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def frame_metrics(path: Path, rom_sha: str) -> tuple[dict, list[dict], list[dict]]:
    name = path.parent.name.removesuffix("_patched")
    img = Image.open(path).convert("RGB")
    w, h = img.size
    pixels = list(img.getdata())
    total = len(pixels)
    black = sum(1 for px in pixels if px == (0, 0, 0))
    bright = sum(1 for r, g, b in pixels if r + g + b >= 520)
    dark = sum(1 for r, g, b in pixels if r + g + b <= 90)
    colors = len(set(pixels))
    tile_hashes = set()
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            tile = img.crop((tx, ty, min(tx + 8, w), min(ty + 8, h))).tobytes()
            tile_hashes.add(hashlib.sha1(tile).digest())

    prov_path = path.parent / "provenance.json"
    provenance = load_json(prov_path) if prov_path.exists() else {}
    row = {
        "checkpoint": name,
        "frame": str(path.relative_to(ROOT)),
        "provenance": str(prov_path.relative_to(ROOT)),
        "provenance_rom_sha256": provenance.get("rom_sha256"),
        "size": [w, h],
        "unique_colors": colors,
        "unique_tiles": len(tile_hashes),
        "black_ratio": round(black / total, 4),
        "dark_ratio": round(dark / total, 4),
        "bright_ratio": round(bright / total, 4),
        "sha256": sha256_file(path),
    }

    issues: list[dict] = []
    observations: list[dict] = []
    low_reasons = []
    if colors < 16:
        low_reasons.append(f"low_color_count={colors}")
    if len(tile_hashes) < 80:
        low_reasons.append(f"low_unique_tiles={len(tile_hashes)}")
    if dark / total > 0.96 and bright < 400:
        low_reasons.append(f"mostly_dark={dark / total:.4f},bright={bright}")
    if low_reasons and name in KNOWN_LOW_INFO:
        observations.append({
            "checkpoint": name,
            "note": "known low-information transition/logo frame",
            "reasons": low_reasons,
        })
    else:
        issues.extend({"checkpoint": name, "issue": reason} for reason in low_reasons)
    if (w, h) != (240, 160):
        issues.append({"checkpoint": name, "issue": "bad_size", "value": [w, h]})
    if provenance.get("rom_sha256") != rom_sha:
        issues.append({
            "checkpoint": name,
            "issue": "stale_provenance",
            "value": provenance.get("rom_sha256"),
        })
    if total - black < 1000:
        issues.append({"checkpoint": name, "issue": "near_blank", "value": total - black})
    return row, issues, observations


def font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        Path("/Library/Fonts/NanumGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def write_contact_pages(frames: list[Path], out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    page_paths: list[str] = []
    fnt = font(11)
    for page_idx in range((len(frames) + 24) // 25):
        subset = frames[page_idx * 25:(page_idx + 1) * 25]
        scale = 2
        thumb_w, thumb_h = 240 * scale, 160 * scale
        header_h = 18
        pad = 6
        cols = 5
        rows = (len(subset) + cols - 1) // cols
        sheet = Image.new(
            "RGB",
            (cols * thumb_w + (cols + 1) * pad, rows * (thumb_h + header_h) + (rows + 1) * pad + 24),
            (12, 12, 14),
        )
        draw = ImageDraw.Draw(sheet)
        draw.text((pad, 4), f"Current ROM manifest scene review page {page_idx + 1}", font=fnt, fill=(240, 240, 240))
        for index, path in enumerate(subset):
            y, x = divmod(index, cols)
            px = pad + x * (thumb_w + pad)
            py = 24 + pad + y * (thumb_h + header_h + pad)
            name = path.parent.name.removesuffix("_patched")
            draw.rectangle((px, py, px + thumb_w - 1, py + header_h - 1), fill=(30, 30, 34))
            draw.text((px + 3, py + 2), name[:62], font=fnt, fill=(235, 235, 235))
            frame = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.NEAREST)
            sheet.paste(frame, (px, py + header_h))
        out_path = out_dir / f"contact_page_{page_idx + 1:02d}.png"
        sheet.save(out_path)
        page_paths.append(str(out_path.relative_to(ROOT)))
    return page_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--shot-dir", default=str(DEFAULT_SHOT_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    shot_dir = Path(args.shot_dir)
    if not shot_dir.is_absolute():
        shot_dir = ROOT / shot_dir
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    manifest = load_json(manifest_path)
    rom_sha = sha256_file(ROM)
    frames = [shot_dir / f"{name}_patched" / "frame.png" for name in manifest.get("captured", [])]
    missing = [str(path.relative_to(ROOT)) for path in frames if not path.exists()]
    rows: list[dict] = []
    issues: list[dict] = [{"checkpoint": path, "issue": "missing_frame"} for path in missing]
    observations: list[dict] = []
    for path in frames:
        if not path.exists():
            continue
        row, row_issues, row_observations = frame_metrics(path, rom_sha)
        rows.append(row)
        issues.extend(row_issues)
        observations.extend(row_observations)

    contact_pages = write_contact_pages([path for path in frames if path.exists()], out_dir)
    unique_tiles = [row["unique_tiles"] for row in rows]
    unique_colors = [row["unique_colors"] for row in rows]
    report = {
        "rom_sha256": rom_sha,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_frame_count": len(frames),
        "checked_frame_count": len(rows),
        "skipped": manifest.get("skipped", []),
        "issue_count": len(issues),
        "issues": issues,
        "observations": observations,
        "summary": {
            "min_unique_colors": min(unique_colors) if unique_colors else 0,
            "min_unique_tiles": min(unique_tiles) if unique_tiles else 0,
            "max_dark_ratio": max((row["dark_ratio"] for row in rows), default=0),
            "max_black_ratio": max((row["black_ratio"] for row in rows), default=0),
            "median_unique_tiles": statistics.median(unique_tiles) if unique_tiles else 0,
        },
        "contact_sheets": contact_pages,
        "frames": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rom_sha256": rom_sha,
        "manifest_frame_count": len(frames),
        "checked_frame_count": len(rows),
        "skipped": report["skipped"],
        "issue_count": len(issues),
        "observations": observations,
        "summary": report["summary"],
        "report": str((out_dir / "report.json").relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
