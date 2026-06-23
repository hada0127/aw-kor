#!/usr/bin/env python3
"""scene editor용 실제 화면 스크린샷 캡처.

data/scene_catalog.json의 scene.screenshot.checkpoint를 읽고, 각 checkpoint를
헤드리스 mGBA harness로 캡처해 temp/scene_screenshots/<checkpoint>_patched/frame.png에 둔다.
각 캡처는 build_comparison_sheet.capture()가 provenance.json을 함께 남긴다.

재생성:
  python3 tools/build_scene_catalog.py
  python3 tools/capture_scene_screenshots.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_comparison_sheet import capture  # noqa: E402

CATALOG = ROOT / "data" / "scene_catalog.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
PATCHED_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT_DIR = ROOT / "temp" / "scene_screenshots"
HARNESS = Path(os.environ.get("MGBA_HARNESS", "/tmp/mgbah"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def scene_checkpoint_names(catalog_path: Path) -> list[str]:
    data = _load(catalog_path)
    names: list[str] = []
    for sc in data.get("scenes", []):
        shot = sc.get("screenshot") or {}
        name = shot.get("checkpoint")
        if name and name not in names:
            names.append(name)
        for extra in ((sc.get("entrypoint") or {}).get("extra_screenshots") or []):
            extra_name = extra.get("checkpoint") if isinstance(extra, dict) else extra
            if extra_name and extra_name not in names:
                names.append(extra_name)
    return names


def scene_id_by_checkpoint(catalog_path: Path) -> dict[str, str]:
    data = _load(catalog_path)
    by_checkpoint: dict[str, str] = {}
    for sc in data.get("scenes", []):
        shot = sc.get("screenshot") or {}
        name = shot.get("checkpoint")
        scene_id = sc.get("id")
        if name and scene_id and name not in by_checkpoint:
            by_checkpoint[name] = scene_id
    return by_checkpoint


def checkpoint_names_for_scenes(catalog_path: Path, scene_ids: list[str]) -> list[str]:
    data = _load(catalog_path)
    wanted = set(scene_ids)
    names: list[str] = []
    missing: list[str] = []
    for sid in scene_ids:
        if not any(sc.get("id") == sid for sc in data.get("scenes", [])):
            missing.append(sid)
    if missing:
        raise SystemExit("scene_catalog에 없는 scene id: " + ", ".join(missing))
    for sc in data.get("scenes", []):
        if sc.get("id") not in wanted:
            continue
        shot = sc.get("screenshot") or {}
        name = shot.get("checkpoint")
        if not name:
            raise SystemExit(f"{sc.get('id')}: screenshot checkpoint 없음")
        if name not in names:
            names.append(name)
        for extra in ((sc.get("entrypoint") or {}).get("extra_screenshots") or []):
            extra_name = extra.get("checkpoint") if isinstance(extra, dict) else extra
            if extra_name and extra_name not in names:
                names.append(extra_name)
    return names


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_capture(frame: Path, checkpoint: dict, rom_sha: str) -> tuple[bool, str]:
    if not frame.exists() or frame.stat().st_size <= 0:
        return False, "frame 없음"
    prov = frame.parent / "provenance.json"
    if not prov.exists() or prov.stat().st_size <= 0:
        return False, "provenance 없음"
    try:
        data = json.loads(prov.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "provenance JSON 오류"
    if data.get("rom_sha256") != rom_sha:
        return False, "ROM SHA 불일치"
    expected_scene = checkpoint.get("scene_id")
    if expected_scene and data.get("scene_id") != expected_scene:
        return False, "scene_id provenance 불일치"
    if checkpoint.get("mode") == "savestate":
        state = checkpoint.get("state")
        if not state:
            return False, "checkpoint state 없음"
        state_path = Path(state)
        if not state_path.is_absolute():
            state_path = ROOT / state_path
        if not state_path.exists():
            return False, "checkpoint state 파일 없음"
        if data.get("state_sha256") != sha256(state_path):
            return False, "state SHA 불일치"
    return True, "current"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(CATALOG))
    ap.add_argument("--manifest", default=str(CHECKPOINTS))
    ap.add_argument("--rom", default=str(PATCHED_ROM))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--all-checkpoints", action="store_true",
                    help="scene에서 참조하지 않는 checkpoint까지 모두 캡처")
    ap.add_argument("--scene-id", action="append", default=[],
                    help="특정 scene id의 screenshot checkpoint만 캡처(여러 번 지정 가능)")
    ap.add_argument("--checkpoint", action="append", default=[],
                    help="특정 checkpoint만 캡처(여러 번 지정 가능)")
    ap.add_argument("--force", action="store_true", help="기존 frame.png가 있어도 재캡처")
    args = ap.parse_args()

    catalog_path = Path(args.catalog)
    manifest = _load(Path(args.manifest))
    by_name = {c["name"]: c for c in manifest.get("checkpoints", [])}
    scene_by_checkpoint = scene_id_by_checkpoint(catalog_path)
    if args.checkpoint:
        names = list(dict.fromkeys(args.checkpoint))
    elif args.scene_id:
        names = checkpoint_names_for_scenes(catalog_path, args.scene_id)
    else:
        names = list(by_name) if args.all_checkpoints else scene_checkpoint_names(catalog_path)
    missing = [name for name in names if name not in by_name]
    if missing:
        raise SystemExit("screen_checkpoints에 없는 scene screenshot checkpoint: " + ", ".join(missing))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rom = Path(args.rom)
    harness = Path(args.harness)
    if not rom.exists():
        raise SystemExit("ROM 없음: " + str(rom))
    if not harness.exists():
        raise SystemExit("mGBA harness 없음: " + str(harness))
    rom_sha = sha256(rom)
    summary = {"rom": str(rom), "harness": str(harness), "captured": [], "skipped": []}

    for name in names:
        checkpoint = dict(by_name[name])
        if not checkpoint.get("scene_id") and scene_by_checkpoint.get(name):
            checkpoint["scene_id"] = scene_by_checkpoint[name]
        frame = out_dir / f"{name}_patched" / "frame.png"
        if frame.exists() and not args.force:
            ok, reason = current_capture(frame, checkpoint, rom_sha)
            if ok:
                print(f"[skip] {name} -> {frame}")
                summary["skipped"].append(name)
                continue
            print(f"[recapture] {name}: {reason}")
        print(f"[capture] {name}")
        capture(rom, checkpoint, out_dir, harness, "patched")
        if not frame.exists() or frame.stat().st_size <= 0:
            raise SystemExit(f"{name}: frame.png 생성 실패")
        prov = frame.parent / "provenance.json"
        if not prov.exists() or prov.stat().st_size <= 0:
            raise SystemExit(f"{name}: provenance.json 생성 실패")
        summary["captured"].append(name)

    (out_dir / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nscene screenshots: {out_dir}  captured={len(summary['captured'])} skipped={len(summary['skipped'])}")


if __name__ == "__main__":
    main()
