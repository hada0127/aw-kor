#!/usr/bin/env python3
"""Audit residual scene-container scan evidence.

Container scenes are address buckets, not independently capturable screens.
This audit makes that claim checkable: every container in scene_catalog.json
must have a residual-scan manifest entry, and every referenced scan result must
match its expected case/hit counts. Any hit in a residual scan is critical
unless the manifest maps it to an existing split screen scene.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "scene_catalog.json"
MANIFEST = ROOT / "data" / "scene_residual_scans.json"
ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT_DIR = ROOT / "temp" / "scene_residual_scan_audit"


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hex(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    raise ValueError(f"unsupported integer value: {value!r}")


def normalize_range(item) -> list[int]:
    if isinstance(item, str):
        start, end = item.split(":", 1)
        return [parse_hex(start), parse_hex(end)]
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return [parse_hex(item[0]), parse_hex(item[1])]
    raise ValueError(f"unsupported range: {item!r}")


def normalize_ranges(items) -> list[list[int]]:
    return [normalize_range(item) for item in (items or [])]


def hit_payload(row: dict) -> dict | None:
    hit = row.get("hit")
    if not hit:
        return None
    if isinstance(hit, dict):
        return hit
    return {"offset": str(hit)}


def hit_offset(row: dict) -> str | None:
    hit = hit_payload(row)
    if not hit:
        return None
    offset = hit.get("offset") or hit.get("addr")
    return str(offset) if offset else None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    catalog = load(CATALOG, {"scenes": []})
    manifest = load(MANIFEST, {"containers": []})
    scenes = catalog.get("scenes") or []
    scene_by_id = {scene.get("id"): scene for scene in scenes if scene.get("id")}
    current_rom_sha = sha256(ROM) if ROM.exists() else ""
    containers = [scene for scene in scenes if scene.get("scene_role") == "container"]
    screen_scene_ids = {
        scene.get("id")
        for scene in scenes
        if scene.get("scene_role") != "container" and scene.get("id")
    }
    entries = manifest.get("containers") or []
    entry_by_id = {entry.get("container_scene_id"): entry for entry in entries}

    issues: list[dict] = []
    rows: list[dict] = []

    for scene in containers:
        sid = scene.get("id")
        entry = entry_by_id.get(sid)
        if not entry:
            issues.append({
                "severity": "critical",
                "container_scene_id": sid,
                "issue": "residual scan manifest 없음",
            })
            continue

        catalog_ranges = normalize_ranges((scene.get("dialogue_filter") or {}).get("addr_ranges"))
        manifest_ranges = normalize_ranges(entry.get("container_ranges"))
        if catalog_ranges != manifest_ranges:
            issues.append({
                "severity": "critical",
                "container_scene_id": sid,
                "issue": "manifest range가 scene_catalog dialogue_filter와 다름",
                "catalog_ranges": catalog_ranges,
                "manifest_ranges": manifest_ranges,
            })

        related = entry.get("related_screen_scene_ids") or []
        missing_related = [rid for rid in related if rid not in screen_scene_ids]
        if missing_related:
            issues.append({
                "severity": "critical",
                "container_scene_id": sid,
                "issue": "related split scene이 screen scene으로 존재하지 않음",
                "missing_related": missing_related,
            })

        row = {
            "container_scene_id": sid,
            "dialogue_count": len(scene.get("dialogue_ids") or []),
            "evidence_count": len(entry.get("evidence") or []),
            "case_count": 0,
            "hit_count": 0,
            "known_hit_count": 0,
            "paths": [],
        }
        for evidence in entry.get("evidence") or []:
            result_path = ROOT / evidence.get("result_path", "")
            row["paths"].append(rel(result_path))
            expected_cases = evidence.get("expected_cases")
            expected_hits = evidence.get("expected_hit_count")
            expected_rom_sha = evidence.get("rom_sha256")
            expected_result_sha = evidence.get("result_sha256")
            if not evidence.get("method"):
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "evidence method 없음",
                })
            if expected_rom_sha and expected_rom_sha != current_rom_sha:
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "scan ROM SHA 불일치",
                    "expected": expected_rom_sha,
                    "actual": current_rom_sha,
                })
            if not result_path.exists():
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "scan results.json 없음",
                })
                continue
            if expected_result_sha:
                actual_result_sha = sha256(result_path)
                if expected_result_sha != actual_result_sha:
                    issues.append({
                        "severity": "critical",
                        "container_scene_id": sid,
                        "path": rel(result_path),
                        "issue": "scan results SHA 불일치",
                        "expected": expected_result_sha,
                        "actual": actual_result_sha,
                    })
            try:
                results = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": f"scan results JSON 오류: {exc}",
                })
                continue
            if not isinstance(results, list):
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "scan results가 list가 아님",
                })
                continue
            hits = [item for item in results if hit_payload(item)]
            row["case_count"] += len(results)
            row["hit_count"] += len(hits)
            if expected_cases is not None and len(results) != int(expected_cases):
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "scan case 수 불일치",
                    "expected": int(expected_cases),
                    "actual": len(results),
                })
            if expected_hits is not None and len(hits) != int(expected_hits):
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "scan hit 수 불일치",
                    "expected": int(expected_hits),
                    "actual": len(hits),
                })

            known_hits = evidence.get("known_hits") or []
            known_by_offset = {item.get("offset"): item for item in known_hits}
            row["known_hit_count"] += len(known_hits)
            if hits and not known_hits:
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "설명되지 않은 residual hit",
                    "hit_offsets": [hit_offset(item) for item in hits],
                })
            for item in hits:
                offset = hit_offset(item)
                known = known_by_offset.get(offset)
                if not known:
                    issues.append({
                        "severity": "critical",
                        "container_scene_id": sid,
                        "path": rel(result_path),
                        "issue": "known_hits에 없는 residual hit",
                        "hit_offset": offset,
                    })
                    continue
                target = known.get("target_scene_id")
                if target not in screen_scene_ids:
                    issues.append({
                        "severity": "critical",
                        "container_scene_id": sid,
                        "path": rel(result_path),
                        "issue": "known hit target이 screen scene이 아님",
                        "hit_offset": offset,
                        "target_scene_id": target,
                    })
                payload = hit_payload(item) or {}
                expected_group = known.get("group")
                if expected_group and payload.get("group") != expected_group:
                    issues.append({
                        "severity": "critical",
                        "container_scene_id": sid,
                        "path": rel(result_path),
                        "issue": "known hit group 불일치",
                        "hit_offset": offset,
                        "expected_group": expected_group,
                        "actual_group": payload.get("group"),
                    })
        rows.append(row)

    container_ids = {scene.get("id") for scene in containers}
    for entry in entries:
        sid = entry.get("container_scene_id")
        if sid not in container_ids:
            issues.append({
                "severity": "critical",
                "container_scene_id": sid,
                "issue": "manifest entry가 catalog container가 아님",
            })
        if sid and sid not in scene_by_id:
            issues.append({
                "severity": "critical",
                "container_scene_id": sid,
                "issue": "manifest entry scene_id가 catalog에 없음",
            })

    summary = {
        "container_count": len(containers),
        "manifest_count": len(entries),
        "audited_container_count": len(rows),
        "dialogue_count": sum(row["dialogue_count"] for row in rows),
        "case_count": sum(row["case_count"] for row in rows),
        "hit_count": sum(row["hit_count"] for row in rows),
        "known_hit_count": sum(row["known_hit_count"] for row in rows),
        "critical_count": sum(1 for issue in issues if issue.get("severity") == "critical"),
    }

    report = {"summary": summary, "issues": issues, "containers": rows}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Scene Residual Scan Audit",
        "",
        f"- containers: {summary['audited_container_count']}/{summary['container_count']}",
        f"- manifest entries: {summary['manifest_count']}",
        f"- dialogue in audited containers: {summary['dialogue_count']}",
        f"- scan cases: {summary['case_count']}",
        f"- hits: {summary['hit_count']} (known {summary['known_hit_count']})",
        f"- critical: {summary['critical_count']}",
        "",
    ]
    if issues:
        lines.append("## Issues")
        for issue in issues:
            lines.append(
                f"- {issue.get('severity')} {issue.get('container_scene_id')}: {issue.get('issue')}"
            )
        lines.append("")
    lines.append("## Containers")
    for row in rows:
        lines.append(
            f"- {row['container_scene_id']}: d{row['dialogue_count']} "
            f"e{row['evidence_count']} cases={row['case_count']} hits={row['hit_count']}"
        )
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"scene residual scan audit: {OUT_DIR / 'report.md'}")
    print(json.dumps(summary, ensure_ascii=False))
    if args.strict and summary["critical_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
