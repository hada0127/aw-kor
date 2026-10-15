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
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_comparison_sheet import capture  # noqa: E402

CATALOG = ROOT / "data" / "scene_catalog.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
PATCHED_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT_DIR = ROOT / "temp" / "scene_screenshots"
HARNESS = Path(os.environ.get("MGBA_HARNESS", str(ROOT / "temp" / "mgbah")))
def is_withdrawn_checkpoint(checkpoint: dict) -> bool:
    grade = checkpoint.get("grade", "")
    return isinstance(grade, str) and grade.lower().startswith(("blocked", "withdrawn"))


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


def source_taint(state: dict, baseline: dict, run: Path | None = None) -> bool | None:
    """Resolve taint monotonically across checkpoint, inherited, and local evidence."""
    save = baseline.get("initial_game_save")
    receipt_taint = False
    if save is not None:
        receipt_sha = save.get("receipt_sha256")
        registry = _load(ROOT / "data/game_save_cheat_provenance.json")
        entry = registry.get("receipts", {}).get(receipt_sha, {})
        receipt_taint = entry.get("cheat_tainted")
        if run is not None:
            from game_save_evidence import UNVERIFIED_SRAM_KIND, receipt_cheat_status
            receipt_path = run / save.get("receipt", "game_save.json")
            if receipt_path.is_file() and sha256(receipt_path) == receipt_sha:
                receipt = _load(receipt_path)
                if receipt.get("kind") == UNVERIFIED_SRAM_KIND:
                    if save.get("provenance_class") != UNVERIFIED_SRAM_KIND:
                        raise ValueError("legacy SRAM provenance class missing")
                    receipt_taint = receipt_cheat_status(receipt, receipt_sha)["tainted"]
                elif save.get("provenance_class") == UNVERIFIED_SRAM_KIND:
                    raise ValueError("legacy SRAM provenance class mismatches receipt")
    if "cheat_inherited" in baseline and not isinstance(baseline["cheat_inherited"], bool):
        raise ValueError("baseline cheat_inherited must be Boolean")
    inherited = baseline.get("cheat_inherited") is True or receipt_taint is True
    local_taint = False
    if run is not None:
        from playthrough_capture import evidence_tainted, run_cheat_evidence
        evidence = run_cheat_evidence(run, state)
        if not evidence["ledger_verified"]:
            raise ValueError("checkpoint ledger digest is invalid")
        local_taint = evidence_tainted(evidence)
    declared = state.get("cheat_tainted")
    if "cheat_tainted" in state and not isinstance(declared, bool):
        raise ValueError("checkpoint cheat_tainted must be Boolean")
    if declared is False and (inherited or local_taint):
        raise ValueError("explicit clean taint contradicts inherited, receipt, or local evidence")
    if declared is True or inherited or local_taint:
        return True
    if not isinstance(receipt_taint, bool):
        return None
    return False


def initial_save_valid(run: Path, baseline: dict) -> bool:
    save = baseline.get("initial_game_save")
    if save is None:
        return True
    try:
        if any(Path(save[key]).is_absolute() or ".." in Path(save[key]).parts
               for key in ("save", "receipt")):
            return False
        return (sha256(run / save["save"]) == save["save_sha256"] and
                sha256(run / save["receipt"]) == save["receipt_sha256"])
    except (KeyError, OSError):
        return False


def validate_recorder_endpoint(checkpoint: dict, rom_sha: str) -> dict:
    """Validate the same immutable recorder chain for import and cached acceptance."""
    from PIL import Image

    endpoint = checkpoint["recorder_endpoint"]
    source = ROOT / endpoint["frame"]
    state_path = ROOT / endpoint["checkpoint"]
    run = state_path.parent
    state = _load(state_path)
    baseline_path = run / "baseline.json"
    baseline = _load(baseline_path)
    taint = source_taint(state, baseline, run)
    if (state["rom_sha256"] != rom_sha or baseline["rom_sha256"] != rom_sha or
            state["baseline_sha256"] != sha256(baseline_path) or
            not initial_save_valid(run, baseline) or
            taint is None or taint != checkpoint["cheat_tainted"] or
            sha256(source) != endpoint["frame_sha256"]):
        raise ValueError("recorder endpoint ROM, save, frame, or taint mismatch")
    ledger_path = run / "frames.jsonl"
    ledger_bytes = ledger_path.read_bytes()
    prefix_size = state["ledger_bytes"]
    if not isinstance(prefix_size, int) or prefix_size <= 0 or prefix_size > len(ledger_bytes):
        raise ValueError("recorder endpoint ledger prefix missing")
    ledger = ledger_bytes[:prefix_size]
    if hashlib.sha256(ledger).hexdigest() != state["ledger_sha256"]:
        raise ValueError("recorder endpoint ledger hash mismatch")
    rows = [json.loads(line) for line in ledger.splitlines()]
    core_frame = endpoint.get("core_frame", state["core_frame"])
    matches = [row for row in rows if row.get("core_frame") == core_frame]
    if len(matches) != 1:
        raise ValueError("recorder endpoint absent or duplicated in ledger")
    if run / matches[0]["image"] != source:
        actions = run / "actions.jsonl"
        if not actions.exists() or not any(
            row.get("status") == "captured" and
            Path(row.get("png", "")).name == source.name and
            Path(row.get("checkpoint", "")).name == state_path.name and
            row.get("end_core_frame") == core_frame
            for row in map(json.loads, actions.read_text().splitlines())
        ):
            raise ValueError("recorder endpoint absent from capture actions")
    with Image.open(source) as image:
        if (image.size != (240, 160) or
                hashlib.sha256(image.convert("RGB").tobytes()).hexdigest() != matches[0]["rgb_sha256"]):
            raise ValueError("recorder endpoint PNG/RGB mismatch")
    return {"state_path": state_path, "source": source, "core_frame": core_frame,
            "taint": taint,
            "provenance_class": (baseline.get("initial_game_save") or {}).get("provenance_class")}


def current_capture(frame: Path, checkpoint: dict, rom_sha: str) -> tuple[bool, str]:
    if is_withdrawn_checkpoint(checkpoint):
        return False, "withdrawn or blocked checkpoint grade"
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
    if checkpoint.get("mode") == "recorder_endpoint":
        endpoint = checkpoint["recorder_endpoint"]
        try:
            validated = validate_recorder_endpoint(checkpoint, rom_sha)
            valid = (data.get("source_frame_sha256") == endpoint["frame_sha256"] and
                     data.get("source_checkpoint_sha256") == sha256(ROOT / endpoint["checkpoint"]) and
                     data.get("source_core_frame") == validated["core_frame"] and
                     data.get("source_frame") == endpoint["frame"] and
                     data.get("source_checkpoint") == endpoint["checkpoint"] and
                     data.get("cheat_tainted") == checkpoint["cheat_tainted"] and
                     data.get("provenance_class") == validated["provenance_class"] and
                     sha256(frame) == endpoint["frame_sha256"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            valid = False
        if not valid:
            return False, "recorder endpoint 불일치"
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


def import_recorder_endpoint(checkpoint: dict, frame: Path, rom_sha: str) -> None:
    """Import a recorded PNG only after checking its ROM and ledger chain."""
    endpoint = checkpoint["recorder_endpoint"]
    validated = validate_recorder_endpoint(checkpoint, rom_sha)
    source = validated["source"]
    state_path = validated["state_path"]
    core_frame = validated["core_frame"]
    frame.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, frame)
    provenance = {
        "rom_sha256": rom_sha, "scene_id": checkpoint.get("scene_id"),
        "source_frame": endpoint["frame"], "source_frame_sha256": endpoint["frame_sha256"],
        "source_checkpoint": endpoint["checkpoint"],
        "source_checkpoint_sha256": sha256(state_path), "source_core_frame": core_frame,
        "cheat_tainted": checkpoint["cheat_tainted"],
    }
    if validated["provenance_class"] is not None:
        provenance["provenance_class"] = validated["provenance_class"]
    (frame.parent / "provenance.json").write_text(json.dumps(
        provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    if not harness.exists() and any(by_name[name].get("mode") != "recorder_endpoint" for name in names):
        raise SystemExit("mGBA harness 없음: " + str(harness))
    rom_sha = sha256(rom)
    summary = {"rom": str(rom), "harness": str(harness), "captured": [], "skipped": []}

    for name in names:
        checkpoint = dict(by_name[name])
        if is_withdrawn_checkpoint(checkpoint):
            raise SystemExit(f"{name}: withdrawn or blocked checkpoint grade")
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
        if checkpoint.get("mode") == "recorder_endpoint":
            import_recorder_endpoint(checkpoint, frame, rom_sha)
        else:
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
