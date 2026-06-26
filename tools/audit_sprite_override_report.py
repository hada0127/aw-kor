#!/usr/bin/env python3
"""Audit build-time sprite override fit report.

The sprite editor can write pixel overrides for synthetic/raw/LZ77 sprites.
Build reinsertion must not silently skip an edited sprite: an ignored palette-only
record is acceptable, but any pixel override that fails size/recompression fit is
a hard error for release verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "data" / "sprites_overrides.json"
REPORT = ROOT / "temp" / "sprite_override_report.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overrides", default=str(OVERRIDES))
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    overrides_path = Path(args.overrides)
    if not overrides_path.is_absolute():
        overrides_path = ROOT / overrides_path
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path

    overrides = load_json(overrides_path, {})
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise SystemExit(f"sprites_overrides must be object: {overrides_path}")
    active_count = len(overrides)
    active_pixel_count = sum(1 for rec in overrides.values() if isinstance(rec, dict) and rec.get("indices"))

    issues: list[dict] = []
    report = None
    if report_path.exists():
        report = load_json(report_path, {})
        if not isinstance(report, dict):
            issues.append({"severity": "critical", "issue": "report json is not object", "path": str(report_path)})
            report = {}
    elif active_count:
        issues.append({"severity": "critical", "issue": "non-empty sprite overrides but no build report", "path": str(report_path)})

    if report:
        current_sha = sha256(overrides_path) if overrides_path.exists() else None
        if report.get("override_sha256") != current_sha:
            issues.append({
                "severity": "critical",
                "issue": "sprite override report is stale",
                "report_sha256": report.get("override_sha256"),
                "current_sha256": current_sha,
            })
        if int(report.get("override_count") or 0) != active_count:
            issues.append({
                "severity": "critical",
                "issue": "override_count mismatch",
                "report_count": report.get("override_count"),
                "current_count": active_count,
            })
        if not report.get("ok", True):
            issues.append({"severity": "critical", "issue": "report ok=false"})
        for rec in report.get("records") or []:
            status = rec.get("status")
            if status == "skipped":
                issues.append({
                    "severity": "critical",
                    "issue": "sprite override skipped",
                    "id": rec.get("id"),
                    "reason": rec.get("reason"),
                })
            if rec.get("kind") == "lz77" and status == "applied":
                comp = int(rec.get("compressed_size") or 0)
                cap = int(rec.get("comp_size") or 0)
                if not cap or comp > cap:
                    issues.append({
                        "severity": "critical",
                        "issue": "applied lz77 override exceeds comp_size",
                        "id": rec.get("id"),
                        "compressed_size": comp,
                        "comp_size": cap,
                    })

    critical_count = sum(1 for issue in issues if issue.get("severity") == "critical")
    summary = {
        "override_count": active_count,
        "pixel_override_count": active_pixel_count,
        "report": str(report_path),
        "report_exists": report_path.exists(),
        "reported_applied": (report or {}).get("applied", 0) if report else 0,
        "reported_skipped": (report or {}).get("skipped", 0) if report else 0,
        "reported_ignored": (report or {}).get("ignored", 0) if report else 0,
        "critical_count": critical_count,
        "issues": issues[:20],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if args.strict and critical_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
