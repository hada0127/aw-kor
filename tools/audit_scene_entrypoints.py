#!/usr/bin/env python3
"""Scene screenshot/entrypoint completeness audit.

This is stricter than tools/audit_scene_catalog.py for the current UI-editor
goal: every real game scene must have its own checkpoint, that checkpoint must
exist in data/screen_checkpoints.json, and the patched screenshot must have
current provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data" / "scene_catalog.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
ROM = ROOT / "output" / "game_wars_korean_full.gba"
SHOT_DIR = ROOT / "temp" / "scene_screenshots"
OUT_DIR = ROOT / "temp" / "scene_entrypoint_audit"

REVIEW_IDS = {"98_extraction_noise_review", "99_unassigned_review"}
BAD_GRADES = {"needs_real_entrypoint", "legacy_savestate", "placeholder"}
BAD_NOTE_TOKENS = ("placeholder", "미확보", "후보", "해금 전", "근접")


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_game_scene(scene: dict) -> bool:
    return (
        scene.get("id") not in REVIEW_IDS
        and scene.get("scope") != "review"
        and scene.get("scene_role") != "container"
    )


def is_container_scene(scene: dict) -> bool:
    return scene.get("scene_role") == "container"


def current_capture(checkpoint: dict, scene_id: str, rom_sha: str) -> tuple[bool, str, Path | None]:
    checkpoint_name = checkpoint.get("name")
    if checkpoint.get("scene_id") and checkpoint.get("scene_id") != scene_id:
        return False, "checkpoint scene_id 불일치", None
    frame = SHOT_DIR / f"{checkpoint_name}_patched" / "frame.png"
    if not frame.exists() or frame.stat().st_size <= 0:
        return False, "frame 없음", frame
    prov = frame.parent / "provenance.json"
    if not prov.exists() or prov.stat().st_size <= 0:
        return False, "provenance 없음", frame
    try:
        data = json.loads(prov.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "provenance JSON 오류", frame
    if data.get("rom_sha256") != rom_sha:
        return False, "ROM SHA 불일치", frame
    if data.get("scene_id") != scene_id:
        return False, "provenance scene_id 불일치", frame
    if checkpoint.get("mode") == "savestate":
        state = checkpoint.get("state")
        if not state:
            return False, "checkpoint state 없음", frame
        state_path = Path(state)
        if not state_path.is_absolute():
            state_path = ROOT / state_path
        if not state_path.exists():
            return False, "checkpoint state 파일 없음", frame
        if data.get("state_sha256") != sha256(state_path):
            return False, "state SHA 불일치", frame
    return True, "current", frame


def semantic_candidate_reason(scene: dict, checkpoint: dict) -> str | None:
    """Reject known placeholder/probe states even when provenance is current.

    The provenance audit only proves that a screenshot was reproducibly captured.
    For the editor goal, candidate-only states must remain red until a reviewer
    has replaced them with an actual target screen.
    """
    grade = str(checkpoint.get("grade") or (scene.get("screenshot") or {}).get("grade") or "")
    if grade in BAD_GRADES:
        return f"candidate grade: {grade}"
    note = " ".join(
        str(value or "")
        for value in (
            checkpoint.get("note"),
            (scene.get("screenshot") or {}).get("note"),
            (scene.get("entrypoint") or {}).get("note"),
        )
    )
    for token in BAD_NOTE_TOKENS:
        if token in note:
            return f"candidate note token: {token}"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    catalog = load(CAT, {"scenes": []})
    checkpoints = load(CHECKPOINTS, {"checkpoints": []}).get("checkpoints", [])
    checkpoint_by_id = {c.get("name"): c for c in checkpoints}
    rom_sha = sha256(ROM) if ROM.exists() else ""

    all_scenes = catalog.get("scenes", [])
    scenes = [s for s in all_scenes if is_game_scene(s)]
    containers = [s for s in all_scenes if is_container_scene(s)]
    by_checkpoint: dict[str | None, list[dict]] = defaultdict(list)
    primary_scene_by_checkpoint: dict[str, str] = {}
    issues: list[dict] = []
    rows: list[dict] = []

    for scene in scenes:
        shot = scene.get("screenshot") or {}
        checkpoint = shot.get("checkpoint")
        by_checkpoint[checkpoint].append(scene)
        if checkpoint and checkpoint not in primary_scene_by_checkpoint:
            primary_scene_by_checkpoint[checkpoint] = scene.get("id")

    def expected_scene_for_checkpoint(name: str | None, owner_scene: dict) -> str:
        if not name:
            return owner_scene.get("id")
        checkpoint = checkpoint_by_id.get(name) or {}
        return checkpoint.get("scene_id") or primary_scene_by_checkpoint.get(name) or owner_scene.get("id")

    def audit_one_capture(scene: dict, shot: dict, *, relation: str, label: str | None = None) -> None:
        checkpoint = shot.get("checkpoint")
        row = {
            "scene": scene.get("id"),
            "relation": relation,
            "label": label,
            "title": scene.get("title"),
            "checkpoint": checkpoint,
            "mode": shot.get("mode"),
            "grade": shot.get("grade"),
            "capture_path": shot.get("capture_path"),
            "provenance_path": shot.get("provenance_path"),
        }
        if not checkpoint:
            issues.append({**row, "severity": "critical", "issue": "checkpoint 없음"})
            rows.append({**row, "capture": "missing_checkpoint"})
            return
        if not shot.get("capture_path"):
            issues.append({**row, "severity": "critical", "issue": "capture_path 없음"})
        if not shot.get("provenance_path"):
            issues.append({**row, "severity": "critical", "issue": "provenance_path 없음"})
        if checkpoint not in checkpoint_by_id:
            issues.append({**row, "severity": "critical", "issue": "screen_checkpoints.json에 없음"})
            rows.append({**row, "capture": "missing_manifest"})
            return
        expected_scene = expected_scene_for_checkpoint(checkpoint, scene)
        ok, reason, frame = current_capture(checkpoint_by_id[checkpoint], expected_scene, rom_sha)
        candidate_reason = semantic_candidate_reason(scene, checkpoint_by_id[checkpoint])
        row.update({
            "entrypoint": checkpoint_by_id[checkpoint],
            "expected_scene": expected_scene,
            "capture": candidate_reason or reason,
            "frame": str(frame) if frame else None,
        })
        if not ok:
            issues.append({**row, "severity": "critical", "issue": reason})
        elif candidate_reason:
            issues.append({**row, "severity": "critical", "issue": candidate_reason})
        rows.append(row)

    for scene in scenes:
        shot = scene.get("screenshot") or {}
        audit_one_capture(scene, shot, relation="main")
        for extra in ((scene.get("entrypoint") or {}).get("extra_screenshots") or []):
            if not isinstance(extra, dict):
                extra = {"checkpoint": extra}
            checkpoint_name = extra.get("checkpoint")
            checkpoint = checkpoint_by_id.get(checkpoint_name, {})
            extra_shot = {
                "checkpoint": checkpoint_name,
                "mode": checkpoint.get("mode"),
                "grade": checkpoint.get("grade"),
                "capture_path": extra.get("capture_path") or checkpoint.get("capture_path"),
                "provenance_path": extra.get("provenance_path") or checkpoint.get("provenance_path"),
            }
            audit_one_capture(scene, extra_shot, relation="extra", label=extra.get("label"))

    container_rows = []
    for scene in containers:
        shot = scene.get("screenshot") or {}
        row = {
            "scene": scene.get("id"),
            "title": scene.get("title"),
            "dialogue": len(scene.get("dialogue_ids") or []),
            "status": shot.get("status"),
            "grade": shot.get("grade"),
            "note": shot.get("note") or "",
        }
        container_rows.append(row)
        if scene.get("capture_required") is not False:
            issues.append({**row, "severity": "critical", "issue": "container capture_required가 false가 아님"})
        if scene.get("entrypoint"):
            issues.append({**row, "severity": "critical", "issue": "container에 entrypoint가 붙어 있음"})
        if scene.get("checkpoint") or shot.get("checkpoint") or shot.get("url"):
            issues.append({**row, "severity": "critical", "issue": "container에 checkpoint/url이 붙어 있음"})
        if shot.get("capture_path") or shot.get("provenance_path"):
            issues.append({**row, "severity": "critical", "issue": "container에 capture/provenance path가 붙어 있음"})
        if shot.get("status") != "container" or shot.get("grade") != "not_a_scene":
            issues.append({**row, "severity": "critical", "issue": "container screenshot status/grade 계약 위반"})
        if not row["note"]:
            issues.append({**row, "severity": "critical", "issue": "container 제외 사유가 비어 있음"})

    duplicates = []
    for checkpoint, owners in sorted(by_checkpoint.items(), key=lambda kv: (str(kv[0]))):
        if checkpoint and len(owners) > 1:
            item = {
                "checkpoint": checkpoint,
                "scene_count": len(owners),
                "scenes": [s.get("id") for s in owners],
            }
            duplicates.append(item)
            issues.append({"severity": "critical", "issue": "checkpoint 재사용", **item})

    summary = {
        "game_scene_count": len(scenes),
        "container_count": len(container_rows),
        "container_dialogue_count": sum(row["dialogue"] for row in container_rows),
        "audited_capture_count": len(rows),
        "extra_capture_count": len([row for row in rows if row.get("relation") == "extra"]),
        "unique_checkpoint_count": len([cp for cp in by_checkpoint if cp]),
        "duplicate_checkpoint_count": len(duplicates),
        "missing_or_stale_capture_count": len([i for i in issues if i.get("issue") != "checkpoint 재사용"]),
        "critical_count": len(issues),
    }
    report = {"summary": summary, "issues": issues, "scenes": rows, "containers": container_rows}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Scene Entrypoint Audit",
        "",
        f"- game scenes: {summary['game_scene_count']}",
        f"- tracked containers: {summary['container_count']} "
        f"(dialogue {summary['container_dialogue_count']})",
        f"- audited captures: {summary['audited_capture_count']} (extra {summary['extra_capture_count']})",
        f"- unique checkpoints: {summary['unique_checkpoint_count']}",
        f"- duplicate checkpoints: {summary['duplicate_checkpoint_count']}",
        f"- missing/stale captures: {summary['missing_or_stale_capture_count']}",
        f"- critical: {summary['critical_count']}",
        "",
    ]
    if duplicates:
        lines.append("## Duplicate Checkpoints")
        for dup in duplicates:
            lines.append(f"- {dup['checkpoint']} x{dup['scene_count']}: {', '.join(dup['scenes'])}")
        lines.append("")
    other_issues = [i for i in issues if i.get("issue") != "checkpoint 재사용"]
    if other_issues:
        lines.append("## Missing/Stale Captures")
        for issue in other_issues:
            lines.append(f"- {issue.get('scene')} {issue.get('checkpoint')}: {issue.get('issue')}")
        lines.append("")
    if container_rows:
        lines.append("## Tracked Containers")
        for row in container_rows:
            lines.append(f"- {row['scene']} d{row['dialogue']}: {row['note']}")
        lines.append("")
    lines.append("## Scene Entrypoints")
    for row in rows:
        lines.append(f"- {row['scene']}: {row.get('checkpoint')} [{row.get('capture')}] {row.get('title')}")
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    print(f"entrypoint audit: {OUT_DIR / 'report.md'}")
    if args.strict and summary["critical_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
