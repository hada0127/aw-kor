#!/usr/bin/env python3
"""Verify live preview_capture canvases.

This is a canvas-hijack regression guard: a canvas is only trustworthy when
different payload text changes the rendered emulator frame. A mere nonblank
capture can be a false positive if the configured slot is not the runtime
source for that screen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import preview_capture  # noqa: E402

OUT = ROOT / "temp" / "preview_canvas_verify.json"


def pixel_diff(a: Image.Image, b: Image.Image, box: list[int]) -> int:
    ac = a.crop(tuple(box)).convert("RGB")
    bc = b.crop(tuple(box)).convert("RGB")
    if ac.size != bc.size:
        raise AssertionError(f"crop size mismatch: {ac.size} != {bc.size}")
    return sum(1 for pa, pb in zip(ac.getdata(), bc.getdata()) if pa != pb)


def nonblank_score(img: Image.Image) -> int:
    rgb = img.convert("RGB")
    colors = rgb.getcolors(maxcolors=1_000_000)
    if not colors:
        return 0
    dominant = max(colors)[1]
    return sum(
        1 for px in rgb.getdata()
        if sum((px[i] - dominant[i]) ** 2 for i in range(3)) > 1200
    )


def verify_canvas(name: str, cv: dict) -> dict:
    texts = cv.get("verify_texts") or ["캡처테스트입니다", "다른문장입니다"]
    if len(texts) < 2:
        raise AssertionError(f"{name}: verify_texts must contain at least two samples")
    results = [
        preview_capture.capture(text, "ko", name, use_cache=False)
        for text in texts[:2]
    ]
    images = [Image.open(r["png"]).convert("RGB") for r in results]
    for text, result, image in zip(texts[:2], results, images):
        if result.get("truncated"):
            raise AssertionError(f"{name}: sample truncated: {text!r}")
        if image.size != (240, 160):
            raise AssertionError(f"{name}: unexpected image size {image.size}")
        if nonblank_score(image) <= 0:
            raise AssertionError(f"{name}: blank capture")
        sweep = result.get("sweep")
        if cv.get("sweep"):
            if not sweep:
                raise AssertionError(f"{name}: sweep metadata missing")
            min_score = int(cv["sweep"].get("min_score", 1))
            if int(sweep.get("selected_score") or 0) < min_score:
                raise AssertionError(f"{name}: sweep score below min: {sweep}")
    box = (cv.get("sweep") or {}).get("score_box") or [0, 0, 240, 160]
    diff = pixel_diff(images[0], images[1], box)
    if diff < int(cv.get("min_payload_diff", 20)):
        raise AssertionError(f"{name}: payload did not visibly affect capture (diff={diff}, box={box})")
    return {
        "ok": True,
        "canvas": name,
        "slot": cv.get("slot"),
        "len": cv.get("len"),
        "diff_pixels": diff,
        "box": box,
        "captures": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canvas", action="append", default=[], help="canvas key to verify")
    args = ap.parse_args()

    names = args.canvas or sorted(preview_capture.CANVASES)
    missing = [name for name in names if name not in preview_capture.CANVASES]
    if missing:
        raise SystemExit("unknown canvas: " + ", ".join(missing))
    report = {"canvases": [], "failures": []}
    for name in names:
        try:
            report["canvases"].append(verify_canvas(name, preview_capture.CANVASES[name]))
        except Exception as exc:
            report["failures"].append({"canvas": name, "error": str(exc)})
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "canvas_count": len(names),
        "failure_count": len(report["failures"]),
        "report": str(OUT),
        "failures": report["failures"],
    }, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
