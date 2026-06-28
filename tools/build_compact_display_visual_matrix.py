#!/usr/bin/env python3
"""Build the E12 compact display visual-evidence matrix.

This is not a pass/fail visual OCR. It makes the remaining evidence gap
explicit: compact display strings can be byte-correct and editor-visible while
still lacking direct per-target screen proof. The report separates those levels
so TODO E12 cannot be closed with a too-narrow static gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
DISPLAY_OVERRIDES = ROOT / "data" / "display_overrides.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DIALOGUE_GROUPS = ROOT / "data" / "dialogue_groups.json"
SCENE_CATALOG = ROOT / "data" / "scene_catalog.json"
GLYPH_QA = ROOT / "temp" / "glyph_dictionary_qa.json"
RENDERER_TRACE = ROOT / "data" / "compact_display_renderer_trace.json"
XREF_ANALYSIS = ROOT / "data" / "compact_display_xref_analysis.json"
CODE_CONTEXT_ANALYSIS = ROOT / "data" / "compact_display_code_context.json"
MANUAL_VISUAL_EVIDENCE = ROOT / "data" / "compact_display_manual_visual_evidence.json"
POSITIVE_CONTROL_PROBES = [
    ROOT / "data" / "compact_display_read_watch_positive_control_a01970.json",
]
POSITIVE_CONTROL_PROBE_SET = {path.resolve() for path in POSITIVE_CONTROL_PROBES}
READ_WATCH_PROBES = [
    path
    for path in sorted((ROOT / "data").glob("compact_display_read_watch*.json"))
    if path.resolve() not in POSITIVE_CONTROL_PROBE_SET
]
OUT_JSON = ROOT / "data" / "compact_display_visual_matrix.json"
OUT_MD = ROOT / "docs" / "reports" / "compact_display_visual_matrix_2026-06-27.md"
OUT_CONTACT = ROOT / "docs" / "screenshots" / "e12_compact_display_matrix_2026-06-27" / "current_representative_contact.png"

GROUP_SPECS = [
    {
        "id": "a2_co_power_profile_display_overrides",
        "title": "A2 CO power profile compact names",
        "ranges": [(0xA2955C, 0xA29830)],
        "expected_count": 36,
        "source": "data/display_overrides.json",
    },
    {
        "id": "b84_compact_power_display_overrides",
        "title": "B84 compact CO power names",
        "ranges": [(0xB84E50, 0xB84F18)],
        "expected_count": 11,
        "source": "data/display_overrides.json",
    },
    {
        "id": "b8_compact_display_table_all",
        "title": "B8 compact display table bucket",
        "ranges": [(0xB81800, 0xB85000)],
        "expected_count": 459,
        "source": "data/dialogue_groups.json",
    },
]

REPRESENTATIVE_SCENE_IDS = [
    "23_part2_main_menu",
    "23a_part2_wars_shop",
    "86_common_compact_menu_tables",
    "30f2_part2_co_profile_story",
    "26_part2_battle_labels",
    "24a_part2_operation_select",
    "85_ui_common",
    "87_common_rule_settings",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def in_ranges(addr: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= addr < end for start, end in ranges)


def parse_addr(value: str) -> int | None:
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def parse_hex_bytes(value) -> bytes | None:
    if not isinstance(value, str) or len(value) % 2:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def nonblack_pixel_count(path: Path) -> int:
    img = Image.open(path).convert("RGB")
    return sum(1 for px in img.getdata() if px != (0, 0, 0))


def scene_capture_current(scene: dict, rom_sha: str) -> dict:
    shot = scene.get("screenshot") or {}
    capture = shot.get("capture_path") or ((scene.get("entrypoint") or {}).get("capture_path"))
    if not capture:
        return {"current": False, "reason": "no_capture_path"}
    capture_path = ROOT / capture
    prov_path = capture_path.parent / "provenance.json"
    if not capture_path.exists():
        return {"current": False, "capture_path": rel(capture_path), "reason": "capture_missing"}
    if not prov_path.exists():
        return {"current": False, "capture_path": rel(capture_path), "reason": "provenance_missing"}
    try:
        prov = load(prov_path)
    except json.JSONDecodeError:
        return {"current": False, "capture_path": rel(capture_path), "reason": "provenance_invalid"}
    current = prov.get("rom_sha256") == rom_sha
    return {
        "current": current,
        "capture_path": rel(capture_path),
        "provenance_path": rel(prov_path),
        "provenance_rom_sha256": prov.get("rom_sha256"),
        "reason": "current" if current else "rom_sha_mismatch",
    }


def build_indices():
    dialogue_doc = load(DIALOGUE_MAP)
    groups_doc = load(DIALOGUE_GROUPS)
    catalog = load(SCENE_CATALOG)
    line_by_addr = {}
    for row in dialogue_doc.get("lines", []):
        addr = parse_addr(row.get("address"))
        if addr is not None:
            line_by_addr[addr] = row
    group_by_addr = {}
    group_by_id = {}
    for group in groups_doc.get("groups", []):
        gid = group.get("group_id")
        if gid:
            group_by_id[gid] = group
        for member in group.get("members", []):
            addr = parse_addr(member.get("address"))
            if addr is not None:
                group_by_addr[addr] = group
    scenes = catalog.get("scenes", [])
    scene_by_id = {scene.get("id"): scene for scene in scenes if scene.get("id")}
    scenes_by_gid = {}
    for scene in scenes:
        for gid in scene.get("dialogue_ids", []):
            scenes_by_gid.setdefault(gid, []).append(scene)
    return line_by_addr, group_by_addr, group_by_id, scene_by_id, scenes_by_gid


def display_override_targets(spec: dict, display_overrides: dict[str, str]) -> list[int]:
    out = []
    for key in display_overrides:
        if not isinstance(key, str) or not key.startswith("0x"):
            continue
        addr = int(key, 16)
        if in_ranges(addr, spec["ranges"]):
            out.append(addr)
    return sorted(out)


def group_targets(spec: dict, group_by_addr: dict[int, dict]) -> list[int]:
    return sorted(addr for addr in group_by_addr if in_ranges(addr, spec["ranges"]))


def target_row(addr: int, group_id: str, line_by_addr: dict[int, dict], group_by_addr: dict[int, dict],
               scenes_by_gid: dict[str, list[dict]], rom_sha: str, display_overrides: dict[str, str],
               direct_trace_by_addr: dict[int, list[dict]],
               read_watch_by_group_addr: dict[tuple[str, int], list[dict]],
               manual_visual_by_group_addr: dict[tuple[str, int], list[dict]],
               xref_by_group_addr: dict[tuple[str, int], dict]) -> dict:
    line = line_by_addr.get(addr) or {}
    group = group_by_addr.get(addr) or {}
    gid = group.get("group_id")
    scenes = scenes_by_gid.get(gid, []) if gid else []
    scene_rows = []
    for scene in scenes:
        capture = scene_capture_current(scene, rom_sha) if scene.get("scene_role") == "screen" else {"current": False, "reason": "container"}
        scene_rows.append({
            "id": scene.get("id"),
            "role": scene.get("scene_role"),
            "capture_required": bool(scene.get("capture_required")),
            "screenshot_status": (scene.get("screenshot") or {}).get("status"),
            "screenshot_grade": (scene.get("screenshot") or {}).get("grade"),
            "current_capture": capture,
        })
    screen_scenes = [scene for scene in scene_rows if scene["role"] == "screen"]
    current_screen_scenes = [scene for scene in screen_scenes if scene["current_capture"].get("current")]
    container_scenes = [scene for scene in scene_rows if scene["role"] == "container"]
    key = f"0x{addr:08X}"
    trace_evidence = direct_trace_by_addr.get(addr, [])
    read_watch_evidence = read_watch_by_group_addr.get((group_id, addr), [])
    manual_visual_evidence = manual_visual_by_group_addr.get((group_id, addr), [])
    static_xref = xref_by_group_addr.get((group_id, addr), {})
    direct_evidence = bool(trace_evidence or read_watch_evidence or manual_visual_evidence)
    proof_modes = sorted({
        evidence.get("proof_mode")
        for evidence in read_watch_evidence
        if evidence.get("proof_mode")
    })
    synthetic_runtime_source = any(
        evidence.get("synthetic_ram_field_source_proof")
        for evidence in read_watch_evidence
    )
    return {
        "address": key,
        "ja": line.get("ja") or "",
        "ko": display_overrides.get(key) or line.get("ko") or "",
        "kind": line.get("kind"),
        "region": line.get("region"),
        "slot": line.get("slot"),
        "group_id": gid,
        "editor_exposed": bool(scenes),
        "screen_scene_assigned": bool(screen_scenes),
        "current_screen_capture_assigned": bool(current_screen_scenes),
        "container_only": bool(container_scenes) and not bool(screen_scenes),
        "scene_evidence": scene_rows,
        "direct_target_visual_evidence": direct_evidence,
        "renderer_trace_evidence": trace_evidence,
        "read_watch_evidence": read_watch_evidence,
        "manual_visual_evidence": manual_visual_evidence,
        "runtime_source_proof_modes": proof_modes,
        "synthetic_runtime_source_proof": synthetic_runtime_source,
        "static_pointer_xrefs": {
            "pointer_ref_count": static_xref.get("pointer_ref_count", 0),
            "external_pointer_ref_count": static_xref.get("external_pointer_ref_count", 0),
            "second_level_ref_count": static_xref.get("second_level_ref_count", 0),
            "external_pointer_refs": static_xref.get("external_pointer_refs", [])[:8],
            "second_level_refs": static_xref.get("second_level_refs", [])[:8],
        },
        "evidence_level": (
            "renderer_trace_direct"
            if trace_evidence else
            "read_watch_direct"
            if read_watch_evidence else
            "manual_visual_mutation"
            if manual_visual_evidence else
            "current_screen_scene"
            if current_screen_scenes else
            "screen_scene_stale_or_missing"
            if screen_scenes else
            "container_only"
            if container_scenes else
            "no_scene"
        ),
    }


def summarize_targets(targets: list[dict], expected_count: int | None) -> dict:
    return {
        "expected_count": expected_count,
        "target_count": len(targets),
        "expected_count_match": expected_count is None or len(targets) == expected_count,
        "editor_exposed": sum(1 for row in targets if row["editor_exposed"]),
        "screen_scene_assigned": sum(1 for row in targets if row["screen_scene_assigned"]),
        "current_screen_capture_assigned": sum(1 for row in targets if row["current_screen_capture_assigned"]),
        "container_only": sum(1 for row in targets if row["container_only"]),
        "no_scene": sum(1 for row in targets if not row["editor_exposed"]),
        "direct_target_visual_evidence": sum(1 for row in targets if row["direct_target_visual_evidence"]),
        "static_pointer_refs": sum(1 for row in targets if row["static_pointer_xrefs"]["pointer_ref_count"] > 0),
        "static_external_pointer_refs": sum(1 for row in targets if row["static_pointer_xrefs"]["external_pointer_ref_count"] > 0),
    }


def representative_screens(scene_by_id: dict[str, dict], rom_sha: str) -> list[dict]:
    rows = []
    for sid in REPRESENTATIVE_SCENE_IDS:
        scene = scene_by_id.get(sid)
        if not scene:
            rows.append({"id": sid, "present": False})
            continue
        rows.append({
            "id": sid,
            "present": True,
            "title": scene.get("title"),
            "counts": scene.get("counts"),
            "capture": scene_capture_current(scene, rom_sha),
        })
    return rows


def renderer_trace_summary(trace: dict, rom_sha: str) -> dict:
    if not trace:
        return {
            "path": rel(RENDERER_TRACE),
            "present": False,
            "reason": "trace_file_missing",
        }
    current_rom = trace.get("rom_sha256") == rom_sha
    return {
        "path": rel(RENDERER_TRACE),
        "present": True,
        "current_rom": current_rom,
        "rom_sha256": trace.get("rom_sha256"),
        "case_count": trace.get("case_count"),
        "hit_count": trace.get("hit_count"),
        "direct_target_hit_count": trace.get("direct_target_hit_count"),
        "breakpoint_count": len(trace.get("breakpoints", [])),
        "code_context_breakpoints_enabled": trace.get("code_context_breakpoints_enabled"),
        "code_context_json": trace.get("code_context_json"),
        "strict_note": trace.get("strict_note"),
    }


def xref_analysis_summary(xref: dict, rom_sha: str) -> dict:
    if not xref:
        return {
            "path": rel(XREF_ANALYSIS),
            "present": False,
            "reason": "xref_file_missing",
        }
    current_rom = xref.get("rom_sha256") == rom_sha
    return {
        "path": rel(XREF_ANALYSIS),
        "present": True,
        "current_rom": current_rom,
        "rom_sha256": xref.get("rom_sha256"),
        "groups": [
            {
                "id": group.get("id"),
                **(group.get("summary") or {}),
            }
            for group in xref.get("groups", [])
        ],
        "strict_note": xref.get("strict_note"),
    }


def code_context_summary(doc: dict, rom_sha: str) -> dict:
    if not doc:
        return {
            "path": rel(CODE_CONTEXT_ANALYSIS),
            "present": False,
            "reason": "code_context_file_missing",
        }
    summary = doc.get("summary") or {}
    current_rom = doc.get("rom_sha256") == rom_sha
    return {
        "path": rel(CODE_CONTEXT_ANALYSIS),
        "present": True,
        "current_rom": current_rom,
        "rom_sha256": doc.get("rom_sha256"),
        "literal_entry_count": summary.get("literal_entry_count"),
        "derived_table_head_ref_count": summary.get("derived_table_head_ref_count"),
        "breakpoint_candidate_count": summary.get("breakpoint_candidate_count"),
        "function_candidate_count": len(summary.get("function_candidates", [])),
        "literal_entries_with_loads_by_group": summary.get("literal_entries_with_loads_by_group", {}),
        "strict_note": doc.get("strict_note"),
    }


def read_watch_summary(paths: list[Path], rom_sha: str | None = None) -> dict:
    probes = []
    for path in paths:
        if not path.exists():
            continue
        doc = load(path)
        current_rom = rom_sha is None or doc.get("rom_sha256") == rom_sha
        probes.append({
            "path": rel(path),
            "present": True,
            "current_rom": current_rom,
            "rom_sha256": doc.get("rom_sha256"),
            "selected_groups": doc.get("selected_groups", []),
            "selected_target_addresses": doc.get("selected_target_addresses", []),
            "case_count": doc.get("case_count", 0),
            "hit_count": doc.get("hit_count", 0),
            "direct_target_read_count": doc.get("direct_target_read_count", 0),
            "strict_note": doc.get("strict_note"),
            "proof_mode": doc.get("proof_mode"),
            "synthetic_ram_field_source_proof": bool(doc.get("synthetic_ram_field_source_proof")),
            "cases": [
                {
                    "name": case.get("name"),
                    "case_type": case.get("case_type"),
                    "mode": case.get("mode"),
                    "watch_mode": case.get("watch_mode"),
                    "watchpoint_caveat": case.get("watchpoint_caveat"),
                    "summary": case.get("summary", {}),
                    "watch_log": case.get("watch_log"),
                    "frame": case.get("frame"),
                }
                for case in doc.get("cases", [])
            ],
        })
    current_probes = [probe for probe in probes if probe.get("current_rom")]
    return {
        "present": bool(probes),
        "probe_count": len(probes),
        "current_probe_count": len(current_probes),
        "stale_probe_count": len(probes) - len(current_probes),
        "stale_paths": [probe["path"] for probe in probes if not probe.get("current_rom")],
        "case_count": sum(probe.get("case_count", 0) for probe in current_probes),
        "hit_count": sum(probe.get("hit_count", 0) for probe in current_probes),
        "direct_target_read_count": sum(probe.get("direct_target_read_count", 0) for probe in current_probes),
        "total_case_count": sum(probe.get("case_count", 0) for probe in probes),
        "total_hit_count": sum(probe.get("hit_count", 0) for probe in probes),
        "total_direct_target_read_count": sum(probe.get("direct_target_read_count", 0) for probe in probes),
        "probes": probes,
    }


def positive_control_summary(paths: list[Path], rom_sha: str | None = None) -> dict:
    probes = read_watch_summary(paths, rom_sha)
    probes["strict_note"] = (
        "Positive controls are not E12 target evidence. They prove the same "
        "fresh-route ROM read-watch mechanism can hit a known visible text."
    )
    return probes


def xref_by_group_addr(xref: dict, rom_sha: str) -> dict[tuple[str, int], dict]:
    if not xref or xref.get("rom_sha256") != rom_sha:
        return {}
    out: dict[tuple[str, int], dict] = {}
    for group in xref.get("groups", []):
        gid = group.get("id")
        for row in group.get("targets", []):
            addr = parse_addr(row.get("address"))
            if gid and addr is not None:
                out[(gid, addr)] = row
    return out


def direct_trace_by_addr(trace: dict, rom_sha: str) -> dict[int, list[dict]]:
    if not trace or trace.get("rom_sha256") != rom_sha:
        return {}
    out: dict[int, list[dict]] = {}
    for row in trace.get("direct_hits", []):
        hit = row.get("hit") or {}
        source = hit.get("source") or {}
        addr = parse_addr(source.get("address"))
        if addr is None:
            continue
        out.setdefault(addr, []).append({
            "case": row.get("case"),
            "case_type": row.get("case_type"),
            "frame": row.get("frame"),
            "breakpoint_log": row.get("breakpoint_log"),
            "pc": f"0x{hit.get('pc', 0):08X}" if isinstance(hit.get("pc"), int) else hit.get("pc"),
            "r0": f"0x{hit.get('r0', 0):08X}" if isinstance(hit.get("r0"), int) else hit.get("r0"),
            "r1": f"0x{hit.get('r1', 0):08X}" if isinstance(hit.get("r1"), int) else hit.get("r1"),
        })
    return out


def read_watch_by_group_addr(summary: dict, rom_sha: str) -> dict[tuple[str, int], list[dict]]:
    out: dict[tuple[str, int], list[dict]] = {}
    for probe in summary.get("probes", []):
        if not probe.get("current_rom"):
            continue
        path = probe.get("path")
        raw_path = ROOT / path if path else None
        if not raw_path or not raw_path.exists():
            continue
        doc = load(raw_path)
        if doc.get("rom_sha256") != rom_sha:
            continue
        proof_mode = doc.get("proof_mode")
        synthetic_ram_field = bool(doc.get("synthetic_ram_field_source_proof"))
        for row in doc.get("direct_hits", []):
            hit = row.get("hit") or {}
            source = hit.get("source") or {}
            gid = source.get("group_id")
            target = parse_addr(source.get("target_start"))
            if not gid or target is None:
                continue
            out.setdefault((gid, target), []).append({
                "probe": path,
                "case": row.get("case"),
                "case_type": row.get("case_type"),
                "frame": row.get("frame"),
                "watch_log": row.get("watch_log"),
                "read_address": source.get("read_address"),
                "target_start": source.get("target_start"),
                "pc": f"0x{hit.get('pc', 0):08X}" if isinstance(hit.get("pc"), int) else hit.get("pc"),
                "lr": f"0x{hit.get('lr', 0):08X}" if isinstance(hit.get("lr"), int) else hit.get("lr"),
                "r0": f"0x{hit.get('r0', 0):08X}" if isinstance(hit.get("r0"), int) else hit.get("r0"),
                "r1": f"0x{hit.get('r1', 0):08X}" if isinstance(hit.get("r1"), int) else hit.get("r1"),
                "proof_mode": proof_mode,
                "synthetic_ram_field_source_proof": synthetic_ram_field,
                "validation": row.get("validation"),
                "note": (
                    "Read-watch direct hit proves this target span was read on this route; "
                    "it is runtime/source provenance, not visual layout QA by itself."
                    + (
                        " This probe is synthetic RAM-field source proof, not natural route coverage."
                        if synthetic_ram_field else
                        ""
                    )
                ),
            })
    return out


def manual_evidence_errors(row: dict, rom_sha: str) -> list[str]:
    errors = []
    if row.get("rom_sha256") != rom_sha:
        errors.append("rom_sha256_mismatch")
    if not row.get("group"):
        errors.append("missing_group")
    if parse_addr(row.get("address")) is None:
        errors.append("bad_address")
    if int(row.get("pixel_diff_count") or 0) <= 0:
        errors.append("nonpositive_pixel_diff_count")
    contact = row.get("contact_sheet")
    if not contact or not (ROOT / contact).exists():
        errors.append("contact_sheet_missing")
    else:
        if not row.get("contact_sheet_sha256"):
            errors.append("missing_contact_sheet_sha256")
        elif sha256(ROOT / contact) != row.get("contact_sheet_sha256"):
            errors.append("contact_sheet_sha256_mismatch")
    if row.get("type") == "single_address_mutation_pixel_diff":
        for key in ("base_text", "mutation_text", "checkpoint", "scene_id"):
            if not row.get(key):
                errors.append(f"missing_{key}")
        try:
            slot = int(row.get("slot") or 0)
        except (TypeError, ValueError):
            slot = 0
        if slot <= 0:
            errors.append("bad_slot")
        old_hex = parse_hex_bytes(row.get("old_hex"))
        new_hex = parse_hex_bytes(row.get("new_hex"))
        encoded_hex = parse_hex_bytes(row.get("encoded_hex"))
        base_encoded_hex = parse_hex_bytes(row.get("base_encoded_hex"))
        if old_hex is None:
            errors.append("bad_old_hex")
        if new_hex is None:
            errors.append("bad_new_hex")
        if encoded_hex is None:
            errors.append("bad_encoded_hex")
        if base_encoded_hex is None:
            errors.append("bad_base_encoded_hex")
        if slot > 0 and old_hex is not None and len(old_hex) != slot:
            errors.append("old_hex_slot_mismatch")
        if slot > 0 and new_hex is not None and len(new_hex) != slot:
            errors.append("new_hex_slot_mismatch")
        if slot > 0 and encoded_hex is not None and len(encoded_hex) > slot:
            errors.append("encoded_hex_over_slot")
        if new_hex is not None and encoded_hex is not None and not new_hex.startswith(encoded_hex):
            errors.append("new_hex_does_not_start_with_encoded_hex")
        if old_hex is not None and base_encoded_hex is not None and not old_hex.startswith(base_encoded_hex):
            errors.append("old_hex_does_not_start_with_base_encoded_hex")
        diff_mask = row.get("diff_mask")
        if not diff_mask or not (ROOT / diff_mask).exists():
            errors.append("diff_mask_missing")
        else:
            if row.get("diff_mask_sha256") and sha256(ROOT / diff_mask) != row.get("diff_mask_sha256"):
                errors.append("diff_mask_sha256_mismatch")
            try:
                if nonblack_pixel_count(ROOT / diff_mask) != int(row.get("pixel_diff_count") or 0):
                    errors.append("diff_mask_pixel_count_mismatch")
            except Exception:
                errors.append("diff_mask_pixel_count_failed")
        null_control = row.get("null_control") or {}
        if null_control.get("enabled"):
            if not null_control.get("deterministic"):
                errors.append("null_control_not_deterministic")
            if int(null_control.get("pixel_diff_count") or 0) != 0:
                errors.append("null_control_nonzero_diff")
        expected_box = row.get("expected_diff_box")
        if expected_box is not None:
            if not isinstance(expected_box, list) or len(expected_box) != 4:
                errors.append("expected_diff_box_invalid")
            elif row.get("diff_bbox_within_expected_box") is not True:
                errors.append("diff_bbox_outside_expected_box")
    return errors


def manual_visual_summary(doc: dict, rom_sha: str,
                          valid_targets: set[tuple[str, int]] | None = None) -> dict:
    if not doc:
        return {
            "path": rel(MANUAL_VISUAL_EVIDENCE),
            "present": False,
            "reason": "manual_visual_evidence_file_missing",
            "current_count": 0,
            "stale_count": 0,
            "entries": [],
        }
    entries = []
    for row in doc.get("evidence", []):
        errors = manual_evidence_errors(row, rom_sha)
        addr = parse_addr(row.get("address"))
        group = row.get("group")
        if valid_targets is not None and group and addr is not None and (group, addr) not in valid_targets:
            errors.append("target_not_in_matrix")
        current = row.get("rom_sha256") == rom_sha
        entries.append({
            "address": row.get("address"),
            "group": row.get("group"),
            "type": row.get("type"),
            "current_rom": current,
            "rom_sha256": row.get("rom_sha256"),
            "checkpoint": row.get("checkpoint"),
            "scene_id": row.get("scene_id"),
            "base_text": row.get("base_text"),
            "mutation_text": row.get("mutation_text"),
            "slot": row.get("slot"),
            "encoded_hex": row.get("encoded_hex"),
            "base_encoded_hex": row.get("base_encoded_hex"),
            "old_hex": row.get("old_hex"),
            "new_hex": row.get("new_hex"),
            "contact_sheet_sha256": row.get("contact_sheet_sha256"),
            "pixel_diff_count": row.get("pixel_diff_count"),
            "diff_bbox": row.get("diff_bbox"),
            "expected_diff_box": row.get("expected_diff_box"),
            "diff_bbox_within_expected_box": row.get("diff_bbox_within_expected_box"),
            "null_control": row.get("null_control"),
            "diff_mask": row.get("diff_mask"),
            "diff_mask_sha256": row.get("diff_mask_sha256"),
            "contact_sheet": row.get("contact_sheet"),
            "note": row.get("note"),
            "accepted": not errors,
            "validation_errors": errors,
        })
    accepted_by_scene: dict[str, int] = {}
    accepted_by_checkpoint: dict[str, int] = {}
    accepted_by_group_scene: dict[str, int] = {}
    for row in entries:
        if not row.get("accepted"):
            continue
        scene = row.get("scene_id") or "unknown"
        checkpoint = row.get("checkpoint") or "unknown"
        group = row.get("group") or "unknown"
        accepted_by_scene[scene] = accepted_by_scene.get(scene, 0) + 1
        accepted_by_checkpoint[checkpoint] = accepted_by_checkpoint.get(checkpoint, 0) + 1
        key = f"{group}::{scene}"
        accepted_by_group_scene[key] = accepted_by_group_scene.get(key, 0) + 1
    return {
        "path": rel(MANUAL_VISUAL_EVIDENCE),
        "present": True,
        "source_sha256": sha256(MANUAL_VISUAL_EVIDENCE),
        "current_count": sum(1 for row in entries if row.get("current_rom")),
        "accepted_count": sum(1 for row in entries if row.get("accepted")),
        "invalid_count": sum(1 for row in entries if not row.get("accepted")),
        "stale_count": sum(1 for row in entries if not row.get("current_rom")),
        "unmatched_current_count": sum(
            1 for row in entries
            if row.get("current_rom") and "target_not_in_matrix" in row.get("validation_errors", [])
        ),
        "accepted_by_scene": dict(sorted(accepted_by_scene.items())),
        "accepted_by_checkpoint": dict(sorted(accepted_by_checkpoint.items())),
        "accepted_by_group_scene": dict(sorted(accepted_by_group_scene.items())),
        "entries": entries,
        "strict_note": (
            "Manual visual evidence is target-level only when the entry is for "
            "the current ROM SHA, has a positive pixel diff, has a durable contact "
            "sheet, and the group/address matches a matrix target. Mutation proof "
            "establishes live source provenance, not full visual-integrity coverage."
        ),
    }


def manual_visual_by_group_addr(summary: dict) -> dict[tuple[str, int], list[dict]]:
    out: dict[tuple[str, int], list[dict]] = {}
    for row in summary.get("entries", []):
        addr = parse_addr(row.get("address"))
        group = row.get("group")
        if not row.get("accepted") or not group or addr is None:
            continue
        out.setdefault((group, addr), []).append(row)
    return out


def compact_target_keys(display_overrides: dict, group_by_addr: dict[int, dict]) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for spec in GROUP_SPECS:
        addrs = (
            display_override_targets(spec, display_overrides)
            if spec["source"] == "data/display_overrides.json"
            else group_targets(spec, group_by_addr)
        )
        for addr in addrs:
            keys.add((spec["id"], addr))
    return keys


def write_markdown(report: dict) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Compact Display Visual Matrix",
        "",
        f"- ROM SHA: `{report['rom_sha256']}`",
        f"- Contact sheet: `{report['representative_contact_sheet']}`",
        "",
        "This report separates static byte/editor coverage from target-level runtime/source proof.",
        "A current screen scene proves the scene was captured on this ROM, but does not by itself prove every table target is visible.",
        "",
        "## Summary",
        "",
        "| Group | Targets | Editor | Screen scene | Current capture | Container-only | Static ext ptr | Target runtime/source proof |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in report["groups"]:
        s = group["summary"]
        lines.append(
            f"| {group['title']} | {s['target_count']} | {s['editor_exposed']} | "
            f"{s['screen_scene_assigned']} | {s['current_screen_capture_assigned']} | "
            f"{s['container_only']} | {s['static_external_pointer_refs']} | "
            f"{s['direct_target_visual_evidence']} |"
        )
    lines.extend([
        "",
        "## Current Representative Screens",
        "",
    ])
    for row in report["representative_screens"]:
        cap = row.get("capture") or {}
        lines.append(
            f"- `{row['id']}`: current={cap.get('current')} path=`{cap.get('capture_path')}` "
            f"reason={cap.get('reason')}"
        )
    lines.extend([
        "",
        "## Renderer Trace",
        "",
    ])
    rt = report.get("renderer_trace") or {}
    lines.append(
        f"- trace_present={rt.get('present')} current={rt.get('current_rom')} "
        f"rom_sha=`{rt.get('rom_sha256')}` cases={rt.get('case_count')} "
        f"hits={rt.get('hit_count')} direct={rt.get('direct_target_hit_count')} "
        f"breakpoints={rt.get('breakpoint_count')} "
        f"code_context={rt.get('code_context_breakpoints_enabled')} "
        f"path=`{rt.get('path')}`"
    )
    lines.extend([
        "",
        "## Static Code Context",
        "",
    ])
    cc = report.get("code_context_analysis") or {}
    lines.append(
        f"- code_context_present={cc.get('present')} current={cc.get('current_rom')} "
        f"rom_sha=`{cc.get('rom_sha256')}` path=`{cc.get('path')}` "
        f"literal_entries={cc.get('literal_entry_count')} "
        f"breakpoint_candidates={cc.get('breakpoint_candidate_count')} "
        f"function_candidates={cc.get('function_candidate_count')}"
    )
    lines.extend([
        "",
        "## Manual Visual Evidence",
        "",
    ])
    mv = report.get("manual_visual_evidence") or {}
    lines.append(
        f"- manual_present={mv.get('present')} path=`{mv.get('path')}` "
        f"current={mv.get('current_count')} accepted={mv.get('accepted_count')} "
        f"invalid={mv.get('invalid_count')} stale={mv.get('stale_count')} "
        f"note={mv.get('strict_note')}"
    )
    if mv.get("accepted_by_group_scene"):
        lines.append(f"- accepted_by_group_scene={mv.get('accepted_by_group_scene')}")
    if mv.get("accepted_by_checkpoint"):
        lines.append(f"- accepted_by_checkpoint={mv.get('accepted_by_checkpoint')}")
    for row in mv.get("entries", []):
        lines.append(
            f"- `{row.get('address')}` {row.get('group')}: current={row.get('current_rom')} "
            f"accepted={row.get('accepted')} errors={row.get('validation_errors')} "
            f"type={row.get('type')} checkpoint={row.get('checkpoint')} "
            f"diff_pixels={row.get('pixel_diff_count')} contact=`{row.get('contact_sheet')}`"
        )
    lines.extend([
        "",
        "## Static Pointer Xrefs",
        "",
    ])
    xa = report.get("xref_analysis") or {}
    lines.append(f"- xref_present={xa.get('present')} path=`{xa.get('path')}`")
    for row in xa.get("groups", []):
        lines.append(
            f"- `{row.get('id')}`: targets={row.get('target_count')} "
            f"ptr_targets={row.get('with_pointer_refs')} "
            f"external_ptr_targets={row.get('with_external_pointer_refs')} "
            f"second_level_targets={row.get('with_second_level_refs')}"
        )
    lines.extend([
        "",
        "## Read-Watch Probes",
        "",
    ])
    rw = report.get("read_watch_probes") or {}
    lines.append(
        f"- probes_present={rw.get('present')} probes={rw.get('probe_count')} "
        f"current={rw.get('current_probe_count')} stale={rw.get('stale_probe_count')} "
        f"cases={rw.get('case_count')} hits={rw.get('hit_count')} "
        f"direct_reads={rw.get('direct_target_read_count')}"
    )
    lines.append(
        "- hit/direct_read totals are event counts, not unique target counts; "
        "multi-step probes can include reads from earlier redraws on the same route."
    )
    for probe in rw.get("probes", []):
        targets = probe.get("selected_target_addresses") or []
        target_text = f" targets={len(targets)}" if targets else ""
        mode_text = f" proof_mode={probe.get('proof_mode')}" if probe.get("proof_mode") else ""
        lines.append(
            f"- `{probe.get('path')}`: current={probe.get('current_rom')} groups={probe.get('selected_groups')} "
            f"cases={probe.get('case_count')} hits={probe.get('hit_count')} "
            f"direct_reads={probe.get('direct_target_read_count')}{target_text}{mode_text}"
        )
    if rw.get("stale_paths"):
        lines.append(f"- stale probe files ignored in current summary: {', '.join(f'`{p}`' for p in rw['stale_paths'])}")
    lines.extend([
        "",
        "## Read-Watch Positive Controls",
        "",
    ])
    pc = report.get("read_watch_positive_controls") or {}
    lines.append(
        f"- controls_present={pc.get('present')} probes={pc.get('probe_count')} "
        f"cases={pc.get('case_count')} hits={pc.get('hit_count')} "
        f"note={pc.get('strict_note')}"
    )
    for probe in pc.get("probes", []):
        lines.append(
            f"- `{probe.get('path')}`: current={probe.get('current_rom')} targets={probe.get('selected_target_addresses')} "
            f"cases={probe.get('case_count')} hits={probe.get('hit_count')}"
        )
    direct_total = sum(
        (group.get("summary") or {}).get("direct_target_visual_evidence", 0)
        for group in report.get("groups", [])
    )
    direct_by_group = {
        group.get("id"): (group.get("summary") or {}).get("direct_target_visual_evidence", 0)
        for group in report.get("groups", [])
    }
    lines.extend([
        "",
        "## Remaining E12 Gap",
        "",
        f"- Target runtime/source proof count is currently {direct_total}; this includes provenance such as trace, read-watch, or mutation proof, and is still far from full target coverage.",
        "- Static pointer xrefs are provenance only: they show table reachability candidates, not screen rendering.",
        "- Current renderer-trace probes now include observed B8 operation-room reader breakpoints and therefore have breakpoint hits, but direct target register hits remain 0. The hits are a trace positive control for that Part1 path, not A2/B84/Part2-B8-HUD evidence.",
        "- A fresh-route general-text positive control (`0x00A01970`) produced ROM read-watch hits, and the Part1 operation-room B8 live-source probe also produced target reads. The remaining 0-hit routes are therefore not a blanket harness failure.",
        f"- A2 now has {direct_by_group.get('a2_co_power_profile_display_overrides', 0)} target runtime/source proof(s) from a selected-record CO-id RAM-field probe. This is synthetic source provenance, not natural all-CO route coverage or 36 per-power screen captures.",
        f"- B84 now has {direct_by_group.get('b84_compact_power_display_overrides', 0)} target runtime/source proof(s) from current-ROM read-watch probes. Stale older B84 selector proofs are listed above but are not counted until regenerated for this ROM SHA.",
        f"- B8 now has {direct_by_group.get('b8_compact_display_table_all', 0)} target runtime/source proof(s), currently from Part1 operation-title mutation source proofs, but this does not prove full visual layout quality, and most B8 targets still lack target-level provenance.",
        "- Current read-watch probes over the fresh main route, B8 battle/menu/shop/comm candidates, and external shop/profile state candidates still leave Part2-B8-HUD target reads unresolved; these are route/subset negatives, not global non-use proof.",
        "- The remaining 0-hit pattern also leaves source-address/dead-copy hypotheses unresolved for the unproven B8 targets; additional B8 runtime renders must be tied back through target reads, mutation diffs, or WRAM/VRAM/DMA write chains.",
        "- B8 entries are editor-visible through container scene `23d_part2_b8_compact_display_tables`, but need real screen entrypoints or corrected renderer PCs that exercise unit/weapon/shop/break labels.",
        f"- A2 CO power names now have {direct_by_group.get('a2_co_power_profile_display_overrides', 0)}/36 synthetic RAM-field source proof plus one current representative profile screen, but not natural-route 36 per-power screen captures.",
        "",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(report: dict) -> None:
    OUT_CONTACT.parent.mkdir(parents=True, exist_ok=True)
    images = []
    for row in report["representative_screens"]:
        cap_path = (row.get("capture") or {}).get("capture_path")
        if not cap_path:
            continue
        path = ROOT / cap_path
        if not path.exists():
            continue
        images.append((row["id"], Image.open(path).convert("RGB")))
    if not images:
        return
    scale = 2
    tile_w, tile_h = 240 * scale, 160 * scale
    label_h = 22
    cols = 2
    rows = (len(images) + cols - 1) // cols
    out = Image.new("RGB", (cols * tile_w, rows * (tile_h + label_h)), "white")
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    for idx, (label, img) in enumerate(images):
        x = (idx % cols) * tile_w
        y = (idx // cols) * (tile_h + label_h)
        out.paste(img.resize((tile_w, tile_h), Image.Resampling.NEAREST), (x, y + label_h))
        draw.text((x + 4, y + 4), label, fill=(0, 0, 0), font=font)
    out.save(OUT_CONTACT)


def main() -> int:
    global OUT_JSON, OUT_MD, OUT_CONTACT

    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    ap.add_argument("--contact", default=str(OUT_CONTACT))
    args = ap.parse_args()

    OUT_JSON = ROOT / args.out_json if not Path(args.out_json).is_absolute() else Path(args.out_json)
    OUT_MD = ROOT / args.out_md if not Path(args.out_md).is_absolute() else Path(args.out_md)
    OUT_CONTACT = ROOT / args.contact if not Path(args.contact).is_absolute() else Path(args.contact)

    rom_sha = sha256(ROM)
    display_overrides = load(DISPLAY_OVERRIDES)
    renderer_trace = load(RENDERER_TRACE) if RENDERER_TRACE.exists() else {}
    xref_analysis = load(XREF_ANALYSIS) if XREF_ANALYSIS.exists() else {}
    code_context_analysis = load(CODE_CONTEXT_ANALYSIS) if CODE_CONTEXT_ANALYSIS.exists() else {}
    manual_visual_doc = load(MANUAL_VISUAL_EVIDENCE) if MANUAL_VISUAL_EVIDENCE.exists() else {}
    read_watch_probes = read_watch_summary(READ_WATCH_PROBES, rom_sha)
    positive_controls = positive_control_summary(POSITIVE_CONTROL_PROBES, rom_sha)
    trace_by_addr = direct_trace_by_addr(renderer_trace, rom_sha)
    read_watch_by_addr = read_watch_by_group_addr(read_watch_probes, rom_sha)
    xrefs_by_addr = xref_by_group_addr(xref_analysis, rom_sha)
    line_by_addr, group_by_addr, _group_by_id, scene_by_id, scenes_by_gid = build_indices()
    glyph_qa = load(GLYPH_QA) if GLYPH_QA.exists() else {}
    valid_manual_targets = compact_target_keys(display_overrides, group_by_addr)
    manual_visual_evidence = manual_visual_summary(manual_visual_doc, rom_sha, valid_manual_targets)
    manual_by_addr = manual_visual_by_group_addr(manual_visual_evidence)

    groups = []
    for spec in GROUP_SPECS:
        addrs = (
            display_override_targets(spec, display_overrides)
            if spec["source"] == "data/display_overrides.json"
            else group_targets(spec, group_by_addr)
        )
        targets = [
            target_row(addr, spec["id"], line_by_addr, group_by_addr, scenes_by_gid,
                       rom_sha, display_overrides, trace_by_addr, read_watch_by_addr,
                       manual_by_addr, xrefs_by_addr)
            for addr in addrs
        ]
        groups.append({
            "id": spec["id"],
            "title": spec["title"],
            "ranges": [f"0x{start:08X}:0x{end:08X}" for start, end in spec["ranges"]],
            "source": spec["source"],
            "summary": summarize_targets(targets, spec.get("expected_count")),
            "targets": targets,
        })

    report = {
        "tool": "tools/build_compact_display_visual_matrix.py",
        "rom": rel(ROM),
        "rom_sha256": rom_sha,
        "glyph_dictionary_qa": {
            "path": rel(GLYPH_QA),
            "issue_count": glyph_qa.get("issue_count"),
            "rom_sha256": glyph_qa.get("rom_sha256"),
        },
        "renderer_trace": renderer_trace_summary(renderer_trace, rom_sha),
        "xref_analysis": xref_analysis_summary(xref_analysis, rom_sha),
        "code_context_analysis": code_context_summary(code_context_analysis, rom_sha),
        "manual_visual_evidence": manual_visual_evidence,
        "read_watch_probes": read_watch_probes,
        "read_watch_positive_controls": positive_controls,
        "groups": groups,
        "representative_screens": representative_screens(scene_by_id, rom_sha),
        "representative_contact_sheet": rel(OUT_CONTACT),
        "limitations": [
            "current_screen_capture_assigned means the owning screen scene has a current capture, not that this exact target is visible.",
            "direct_target_visual_evidence is a compatibility field for target-level runtime/source proof. It may be set by renderer trace, read-watch direct hit, or manual mutation proof; mutation proof establishes live source provenance, not full visual-integrity coverage.",
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_contact_sheet(report)
    write_markdown(report)
    print(json.dumps({
        "rom_sha256": rom_sha,
        "out_json": rel(OUT_JSON),
        "out_md": rel(OUT_MD),
        "contact": rel(OUT_CONTACT),
        "groups": [
            {"id": group["id"], **group["summary"]}
            for group in groups
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
