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
VISUAL_GRADES = {"fresh_savestate", "ground_truth", "stale_state"}
VISUAL_ROLES = {"primary_current_sha", "supplementary_stale_state"}


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


def residual_payloads(row: dict) -> list[dict]:
    out = []
    if isinstance(row.get("residuals"), list):
        out.extend(item for item in row["residuals"] if isinstance(item, dict))
    if row.get("translation_residual", 0) and hit_payload(row):
        payload = hit_payload(row)
        if payload and payload not in out:
            out.append(payload)
    return out


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def add_issue(
    issues: list[dict],
    sid: str | None,
    issue: str,
    *,
    severity: str = "critical",
    **extra,
) -> None:
    payload = {
        "severity": severity,
        "container_scene_id": sid,
        "issue": issue,
    }
    payload.update(extra)
    issues.append(payload)


def validate_result_reference(
    ref: dict,
    *,
    sid: str | None,
    label: str,
    issues: list[dict],
):
    path_value = ref.get("result_path")
    if not path_value:
        add_issue(issues, sid, f"{label} result_path 없음")
        return None
    path = ROOT / path_value
    if not path.exists():
        add_issue(issues, sid, f"{label} result_path 없음", path=rel(path))
        return None
    expected_sha = ref.get("result_sha256")
    if expected_sha:
        actual_sha = sha256(path)
        if expected_sha != actual_sha:
            add_issue(
                issues,
                sid,
                f"{label} result SHA 불일치",
                path=rel(path),
                expected=expected_sha,
                actual=actual_sha,
            )
    return path


def validate_visual_reverification(
    *,
    sid: str | None,
    item: dict,
    index: int,
    current_rom_sha: str,
    screen_scene_ids: set[str],
    issues: list[dict],
) -> None:
    carry_forward = item.get("carry_forward_applicability") if isinstance(item.get("carry_forward_applicability"), dict) else {}
    carry_forward_ok = (
        carry_forward.get("method") == "validated_unrelated_rom_diff_carry_forward"
        and carry_forward.get("validated_current_rom_sha256") == current_rom_sha
        and carry_forward.get("capture_rom_sha256") == item.get("rom_sha256")
    )
    if item.get("method") != "current_sha_visual_reverification":
        add_issue(
            issues,
            sid,
            "visual reverify row method 불일치",
            row_index=index,
            actual=item.get("method"),
        )
    if item.get("rom_sha256") != current_rom_sha and not carry_forward_ok:
        add_issue(
            issues,
            sid,
            "visual reverify ROM SHA 불일치",
            row_index=index,
            expected=current_rom_sha,
            actual=item.get("rom_sha256"),
        )
    if item.get("container_scene_id") != sid:
        add_issue(
            issues,
            sid,
            "visual reverify container_scene_id 불일치",
            row_index=index,
            actual=item.get("container_scene_id"),
        )

    static_ref = item.get("static_residual_reverify")
    if not isinstance(static_ref, dict):
        add_issue(issues, sid, "visual reverify static_residual_reverify 없음", row_index=index)
    else:
        validate_result_reference(
            static_ref,
            sid=sid,
            label="visual static residual",
            issues=issues,
        )

    dynamic_ref = item.get("historical_dynamic_scan")
    if isinstance(dynamic_ref, dict):
        dynamic_path = validate_result_reference(
            dynamic_ref,
            sid=sid,
            label="visual historical dynamic scan",
            issues=issues,
        )
        if dynamic_path:
            try:
                dynamic_results = json.loads(dynamic_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                add_issue(
                    issues,
                    sid,
                    f"visual historical dynamic scan JSON 오류: {exc}",
                    path=rel(dynamic_path),
                )
                dynamic_results = None
            if isinstance(dynamic_results, list):
                dynamic_hits = [row for row in dynamic_results if hit_payload(row)]
                expected_cases = dynamic_ref.get("case_count")
                expected_hits = dynamic_ref.get("hit_count")
                if expected_cases is not None and len(dynamic_results) != int(expected_cases):
                    add_issue(
                        issues,
                        sid,
                        "visual historical dynamic scan case 수 불일치",
                        path=rel(dynamic_path),
                        expected=int(expected_cases),
                        actual=len(dynamic_results),
                    )
                if expected_hits is not None and len(dynamic_hits) != int(expected_hits):
                    add_issue(
                        issues,
                        sid,
                        "visual historical dynamic scan hit 수 불일치",
                        path=rel(dynamic_path),
                        expected=int(expected_hits),
                        actual=len(dynamic_hits),
                    )
            elif dynamic_results is not None:
                add_issue(
                    issues,
                    sid,
                    "visual historical dynamic scan 결과가 list가 아님",
                    path=rel(dynamic_path),
                )

    screenshots = item.get("current_sha_screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        add_issue(issues, sid, "visual reverify current_sha_screenshots 없음", row_index=index)
    else:
        primary_count = 0
        for shot_index, shot in enumerate(screenshots):
            if not isinstance(shot, dict):
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot 항목이 dict가 아님",
                    row_index=index,
                    shot_index=shot_index,
                )
                continue
            path_value = shot.get("path")
            if not path_value:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot path 없음",
                    row_index=index,
                    shot_index=shot_index,
                )
                continue
            shot_path = ROOT / path_value
            if not shot_path.exists():
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot 파일 없음",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                )
                continue
            expected_sha = shot.get("sha256")
            if not expected_sha:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot SHA 없음",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                )
            else:
                actual_sha = sha256(shot_path)
                if expected_sha != actual_sha:
                    add_issue(
                        issues,
                        sid,
                        "visual reverify screenshot SHA 불일치",
                        path=rel(shot_path),
                        row_index=index,
                        shot_index=shot_index,
                        expected=expected_sha,
                        actual=actual_sha,
                    )
            if shot.get("provenance_rom_sha256") != current_rom_sha and not (
                carry_forward_ok and shot.get("provenance_rom_sha256") == carry_forward.get("capture_rom_sha256")
            ):
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot ROM SHA 불일치",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    expected=current_rom_sha,
                    actual=shot.get("provenance_rom_sha256"),
                )
            scene_id = shot.get("scene_id")
            if scene_id not in screen_scene_ids:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot scene_id가 screen scene이 아님",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    scene_id=scene_id,
                )
            if "visual_result" not in shot:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot visual_result 없음",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                )
            grade = shot.get("grade")
            role = shot.get("evidence_role")
            if grade not in VISUAL_GRADES:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot grade 값이 유효하지 않음",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    grade=grade,
                )
            if role not in VISUAL_ROLES:
                add_issue(
                    issues,
                    sid,
                    "visual reverify screenshot evidence_role 값이 유효하지 않음",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    role=role,
                )
            if role == "primary_current_sha":
                primary_count += 1
            if grade == "stale_state" and role != "supplementary_stale_state":
                add_issue(
                    issues,
                    sid,
                    "stale_state screenshot이 primary 증거로 분류됨",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    role=role,
                )
            if grade != "stale_state" and role != "primary_current_sha":
                add_issue(
                    issues,
                    sid,
                    "fresh/ground-truth screenshot evidence_role 불일치",
                    path=rel(shot_path),
                    row_index=index,
                    shot_index=shot_index,
                    grade=grade,
                    role=role,
                )
        if primary_count <= 0:
            add_issue(
                issues,
                sid,
                "visual reverify primary_current_sha screenshot 없음",
                row_index=index,
            )

    for stale in item.get("excluded_stale_artifacts") or []:
        if isinstance(stale, dict) and stale.get("path"):
            add_issue(
                issues,
                sid,
                "excluded stale artifact가 파일 경로를 증거처럼 보존함",
                row_index=index,
                path=stale.get("path"),
            )


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
            if evidence.get("method") == "current_sha_visual_reverification":
                hits = [item for item in results if isinstance(item, dict) and hit_payload(item)]
                row["case_count"] += len(results)
                row["hit_count"] += len(hits)
                if expected_cases is not None and len(results) != int(expected_cases):
                    add_issue(
                        issues,
                        sid,
                        "visual reverify case 수 불일치",
                        path=rel(result_path),
                        expected=int(expected_cases),
                        actual=len(results),
                    )
                if expected_hits is not None and len(hits) != int(expected_hits):
                    add_issue(
                        issues,
                        sid,
                        "visual reverify hit 수 불일치",
                        path=rel(result_path),
                        expected=int(expected_hits),
                        actual=len(hits),
                    )
                for index, item in enumerate(results):
                    if isinstance(item, dict):
                        validate_visual_reverification(
                            sid=sid,
                            item=item,
                            index=index,
                            current_rom_sha=current_rom_sha,
                            screen_scene_ids=screen_scene_ids,
                            issues=issues,
                        )
                    else:
                        add_issue(
                            issues,
                            sid,
                            "visual reverify row가 dict가 아님",
                            path=rel(result_path),
                            row_index=index,
                        )
                continue
            hits = [item for item in results if hit_payload(item)]
            unexplained_residual_rows = [
                item for item in results
                if safe_int(item.get("translation_residual")) != len(residual_payloads(item))
            ]
            raw_unexplained_rows = [
                item for item in results
                if safe_int(item.get("raw_kana_unexplained_count")) > 0
            ]
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
            for item in unexplained_residual_rows:
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "translation_residual count와 residual payload 수 불일치",
                    "translation_residual": item.get("translation_residual"),
                    "payload_count": len(residual_payloads(item)),
                })
            for item in raw_unexplained_rows:
                issues.append({
                    "severity": "critical",
                    "container_scene_id": sid,
                    "path": rel(result_path),
                    "issue": "설명되지 않은 raw kana observation",
                    "raw_kana_unexplained_count": item.get("raw_kana_unexplained_count"),
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
