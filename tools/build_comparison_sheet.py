#!/usr/bin/env python3
"""전체 화면 비교 시트 생성기 (screen comparison sheet).

진행별 체크포인트(콜드부트 네비 또는 세이브스테이트)에서 ROM 화면을 캡처해
라벨이 붙은 몽타주 시트로 합친다. claude/codex/agy 시각 리뷰의 입력물.

체크포인트 모드
  fresh     : 콜드부트 후 키 네비로 화면에 도달 → **현재 ROM 그대로 렌더(ground truth)**.
              느리지만 stale VRAM 문제가 없어 BG/스프라이트 잔존 판정에 신뢰 가능.
  savestate : 세이브스테이트 로드 후 refresh 스텝 진행 → 빠르지만 정적 BG는
              캡처 시점 VRAM이라 **stale일 수 있음**(시트에 [STALE-BG]로 표기).

원본 대비(`--compare`)
  fresh 체크포인트는 동일 네비를 원본 ROM에도 적용해 좌(원본)/우(패치) 나란히 배치.
  savestate 체크포인트는 `orig_state`가 있으면 그 상태로 원본을 렌더.

사용 예
  python3 tools/build_comparison_sheet.py                 # 패치 ROM만, 기본 매니페스트
  python3 tools/build_comparison_sheet.py --compare       # 원본 vs 패치
  python3 tools/build_comparison_sheet.py --only fresh    # fresh 체크포인트만(신뢰 시트)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_visual_regions import MGBADriver, drive_part1_menu_from_coldboot, raw_to_png  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "screen_checkpoints.json"
DEFAULT_PATCHED = ROOT / "output" / "game_wars_korean_full.gba"
DEFAULT_ORIGINAL = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
DEFAULT_ORIG_CACHE = ROOT / "temp" / "orig_capture_cache"
GBA_W, GBA_H = 240, 160
PART1_MAIN_SWEEP_PRENAV = ["A", "START", "A", "START"]
PART1_MAIN_SWEEP_POLICY = [
    "A", "A", "RIGHT", "A", "A", "DOWN", "A", "A", "START", "A",
    "A", "LEFT", "A", "A", "UP", "A", "A", "START", "A", "B",
]

_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}
_FONT_PATHS = [
    "/Library/Fonts/NanumGothic.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def label_font(size: int) -> ImageFont.ImageFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for path in _FONT_PATHS:
        if Path(path).exists():
            font = ImageFont.truetype(path, size)
            _FONT_CACHE[size] = font
            return font
    return ImageFont.load_default()


def drive_part1_main_sweep(driver: MGBADriver, target_step: int, per_step_frames: int = 60) -> None:
    """Replay the documented Part 1 main sweep route to a specific policy step.

    This replaces stale savestates for high-risk editor screenshots while
    keeping screen_checkpoints.json readable.
    """
    driver.frames(480)
    for key in PART1_MAIN_SWEEP_PRENAV:
        driver.press(key)
    for step_idx in range(target_step + 1):
        driver.press(PART1_MAIN_SWEEP_POLICY[step_idx % len(PART1_MAIN_SWEEP_POLICY)], after=per_step_frames)


def run_nav(driver: MGBADriver, steps: list) -> None:
    """매니페스트 nav/refresh 스텝을 순서대로 실행."""
    for step in steps:
        op = step[0]
        if op == "frames":
            driver.frames(int(step[1]))
        elif op == "press":
            key = step[1]
            after = int(step[2]) if len(step) > 2 else 120
            hold = int(step[3]) if len(step) > 3 else 6
            driver.press(key, hold=hold, after=after)
        elif op == "keys":
            driver.cmd(f"keys {int(step[1])}")
        elif op == "loadstate":
            driver.loadstate(_resolve(step[1]))
        elif op == "part1_menu":
            drive_part1_menu_from_coldboot(driver)
        elif op == "part1_main_sweep":
            target_step = int(step[1])
            per_step_frames = int(step[2]) if len(step) > 2 else 60
            drive_part1_main_sweep(driver, target_step, per_step_frames)
        else:
            raise ValueError(f"unknown nav op: {op!r}")


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (ROOT / path)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _capture_cache_key(rom: Path, checkpoint: dict, side: str) -> str:
    payload: dict = {
        "version": 1,
        "side": side,
        "name": checkpoint["name"],
        "mode": checkpoint["mode"],
        "rom_sha256": _sha256(rom),
        "nav": checkpoint.get("nav"),
        "refresh": checkpoint.get("refresh"),
        "orig_state": checkpoint.get("orig_state"),
        "state": checkpoint.get("state") if side == "patched" else checkpoint.get("orig_state"),
    }
    state_ref = payload.get("state")
    if state_ref:
        state_path = _resolve(str(state_ref))
        payload["state_sha256"] = _sha256(state_path)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:24]


def _copy_cached_capture(cache_entry: Path, shot_dir: Path) -> Image.Image | None:
    frame = cache_entry / "frame.png"
    prov = cache_entry / "provenance.json"
    if not frame.exists() or not prov.exists():
        return None
    shutil.copy2(frame, shot_dir / "frame.png")
    shutil.copy2(prov, shot_dir / "provenance.json")
    return Image.open(frame).copy()


def _store_cached_capture(cache_entry: Path, shot_dir: Path) -> None:
    frame = shot_dir / "frame.png"
    prov = shot_dir / "provenance.json"
    if not frame.exists() or not prov.exists():
        return
    cache_entry.mkdir(parents=True, exist_ok=True)
    shutil.copy2(frame, cache_entry / "frame.png")
    shutil.copy2(prov, cache_entry / "provenance.json")


def capture(
    rom: Path,
    checkpoint: dict,
    out_dir: Path,
    harness: Path,
    side: str,
    *,
    orig_cache: Path | None = None,
) -> Image.Image:
    """단일 체크포인트의 단일 ROM 화면을 캡처 + provenance sidecar 기록.

    codex 리뷰 수정: savestate orig_state fallback 금지(없으면 명시 에러).
    각 캡처 옆에 ROM/state SHA·nav·git commit·harness를 sidecar JSON으로 남겨
    "어떤 ROM/상태에서 나온 화면인지" 추적 가능하게 한다.
    """
    name = checkpoint["name"]
    shot_dir = out_dir / f"{name}_{side}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    cache_entry: Path | None = None
    if side == "orig" and orig_cache is not None:
        cache_entry = orig_cache / _capture_cache_key(rom, checkpoint, side)
        cached = _copy_cached_capture(cache_entry, shot_dir)
        if cached is not None:
            print(f"  [orig-cache hit] {name}")
            return cached
    prov: dict = {
        "name": name,
        "scene_id": checkpoint.get("scene_id"),
        "side": side,
        "mode": checkpoint["mode"],
        "rom": str(rom),
        "rom_sha256": _sha256(rom),
        "git_commit": _git_commit(),
        "harness": str(harness),
        "grade": checkpoint.get("grade", "stale_state" if checkpoint.get("stale_bg") else "ground_truth"),
        "note": checkpoint.get("note"),
    }
    driver = MGBADriver(rom, shot_dir, harness)
    try:
        if checkpoint["mode"] == "fresh":
            run_nav(driver, checkpoint["nav"])
            prov["nav"] = checkpoint["nav"]
        elif checkpoint["mode"] == "savestate":
            if side == "patched":
                state = checkpoint["state"]
            else:
                state = checkpoint.get("orig_state")
                if not state:
                    raise ValueError(f"{name}: savestate orig 캡처는 orig_state 필수(patched state를 원본 ROM에 로드 금지)")
            state_path = _resolve(state)
            prov["state"] = str(state_path)
            prov["state_sha256"] = _sha256(state_path)
            driver.frames(1)
            driver.loadstate(state_path)
            run_nav(driver, checkpoint.get("refresh", [["frames", 20]]))
            prov["refresh"] = checkpoint.get("refresh", [["frames", 20]])
        else:
            raise ValueError(f"unknown mode: {checkpoint['mode']!r}")
        img = driver.shot("frame")
        (shot_dir / "provenance.json").write_text(
            json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if cache_entry is not None:
            _store_cached_capture(cache_entry, shot_dir)
        return img
    finally:
        driver.close()


def panel(image: Image.Image, title: str, scale: int = 2) -> Image.Image:
    """화면 1장을 라벨 헤더가 붙은 패널로 변환.

    codex 리뷰 수정: 고정 240폭 resize는 --compare pair(484폭)를 왜곡한다.
    실제 이미지 폭/높이를 기준으로 확대해 종횡비를 보존한다.
    """
    body = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    header = 22
    canvas = Image.new("RGB", (body.width, body.height + header), (28, 28, 32))
    canvas.paste(body, (0, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 4), title, font=label_font(14), fill=(235, 235, 235))
    return canvas


def build_sheet(panels: list[Image.Image], cols: int, out_path: Path) -> None:
    if not panels:
        raise SystemExit("no panels captured")
    cw = max(p.width for p in panels)
    ch = max(p.height for p in panels)
    pad = 10
    rows = (len(panels) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + pad * (cols + 1), rows * ch + pad * (rows + 1)), (16, 16, 18))
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        sheet.paste(p, (pad + c * (cw + pad), pad + r * (ch + pad)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--rom", default=str(DEFAULT_PATCHED))
    ap.add_argument("--original", default=str(DEFAULT_ORIGINAL))
    ap.add_argument("--compare", action="store_true", help="원본 vs 패치 나란히")
    ap.add_argument("--only", choices=["fresh", "savestate"], help="해당 모드만 캡처")
    ap.add_argument("--include-stale", action="store_true",
                    help="savestate(stale-BG) 체크포인트 포함(기본은 fresh ground truth만)")
    ap.add_argument("--out", default=str(ROOT / "temp" / "comparison_sheets"))
    ap.add_argument("--harness", default="/tmp/mgbah")
    ap.add_argument("--orig-cache", default=str(DEFAULT_ORIG_CACHE),
                    help="--compare 원본 캡처 캐시 디렉터리")
    ap.add_argument("--no-orig-cache", action="store_true",
                    help="원본 캡처 캐시 사용 안 함")
    ap.add_argument("--cols", type=int, default=0, help="0=자동")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    checkpoints = manifest["checkpoints"]
    if args.only:
        checkpoints = [c for c in checkpoints if c["mode"] == args.only]
    elif not args.include_stale:
        # codex 리뷰: 기본은 신뢰 가능한 fresh ground truth만. stale은 명시 opt-in.
        checkpoints = [c for c in checkpoints if not (c["mode"] == "savestate" and c.get("stale_bg"))]
    if not checkpoints:
        raise SystemExit("선택된 체크포인트 없음 (--include-stale 또는 --only savestate 확인)")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    harness = Path(args.harness)
    patched = Path(args.rom)
    original = Path(args.original)
    orig_cache = None if args.no_orig_cache else Path(args.orig_cache)

    panels: list[Image.Image] = []
    for ck in checkpoints:
        name = ck["name"]
        stale = " [STALE-BG]" if ck["mode"] == "savestate" and ck.get("stale_bg") else ""
        note = ck.get("note", "")
        print(f"[capture] {name} ({ck['mode']}) {note}")
        patched_img = capture(patched, ck, out_dir, harness, "patched")
        if args.compare:
            if ck["mode"] == "fresh" or ck.get("orig_state"):
                orig_img = capture(original, ck, out_dir, harness, "orig", orig_cache=orig_cache)
                pair = Image.new("RGB", (GBA_W * 2 + 4, GBA_H), (60, 60, 60))
                pair.paste(orig_img, (0, 0))
                pair.paste(patched_img, (GBA_W + 4, 0))
                panels.append(panel(pair, f"{name}  [원본|패치]{stale}  {note}", scale=2))
            else:
                panels.append(panel(patched_img, f"{name}  [패치]{stale}  {note}", scale=3))
        else:
            panels.append(panel(patched_img, f"{name}{stale}  {note}", scale=3))

    cols = args.cols or (2 if args.compare else 3)
    sheet_path = out_dir / ("sheet_compare.png" if args.compare else "sheet.png")
    build_sheet(panels, cols, sheet_path)
    print(f"\n[sheet] {sheet_path}  ({len(panels)} panels)")


if __name__ == "__main__":
    main()
