#!/usr/bin/env python3
"""Part 1 compact help text gate.

The Part 1 world/single/link help boxes are a narrow renderer family. Generic
byte-fit and pixel-width checks are too broad: they do not prove that this
specific DFAxxx help table is encoded without unsafe one-byte text and within a
conservative help-box width. This gate audits the shipped ROM bytes for that
table directly.
"""
from __future__ import annotations

import json
import hashlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import qa_text_fit as QTF  # noqa: E402
from build_korean_full import ADDRESS_TEXT_OVERRIDES, SYLCODE, encode_fit  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT = ROOT / "temp" / "part1_compact_help_qa.json"

HELP_START = 0x00DFA64A
HELP_END_INCLUSIVE = 0x00DFA9E9
EXPECTED_COUNT = 34
EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT = 23
EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT = 11
EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT = 11

# Conservative per-line ceiling for the help box. Values are encoded
# half-cells: two-byte SJIS/reserved codes count as 2, single-byte ASCII as 1.
# Current maximum is 22. Keeping the gate at 24 leaves a small buffer while
# still catching casual text growth.
MAX_ENCODED_HALF_CELLS = 24

# Fresh current-SHA visual evidence exists for these through the 2026-06-27
# mode/operation/single/link sweep plus unlocked-save battle-record/map-design/
# shop routes. The remaining rows can be slot-safe but still need route-specific
# capture when unlock/progress states are found.
CURRENT_VISUAL_EVIDENCE = {
    0x00DFA68C,
    0x00DFA6AA,
    0x00DFA6CD,
    0x00DFA6E2,
    0x00DFA6FB,
    0x00DFA71B,
    0x00DFA72E,
    0x00DFA752,
    0x00DFA775,
    0x00DFA79A,
    0x00DFA7BE,
    0x00DFA7E2,
    0x00DFA7FD,
    0x00DFA80E,
    0x00DFA829,
    0x00DFA942,
    0x00DFA95B,
    0x00DFA972,
    0x00DFA989,
    0x00DFA9AE,
    0x00DFA9C7,
    0x00DFA9DA,
    0x00DFA9E9,
}

# 2026-06-28: direct unlock/progress routes for these rows are still missing,
# but renderer smoke evidence covers them.  The pointer-table probe forced the
# same Part1 compact help renderer to draw each row, and the live-code injection
# probe kept the real code->pointer lookup while changing only menu item codes.
# Keep these separate from direct visual evidence so route debt remains visible.
SYNTHETIC_RENDER_EVIDENCE = {
    0x00DFA64A,
    0x00DFA66B,
    0x00DFA83A,
    0x00DFA84D,
    0x00DFA872,
    0x00DFA885,
    0x00DFA8AA,
    0x00DFA8CB,
    0x00DFA8EA,
    0x00DFA90A,
    0x00DFA926,
}

LIVE_CODE_INJECTION_EVIDENCE = {
    0x00DFA64A,
    0x00DFA66B,
    0x00DFA83A,
    0x00DFA84D,
    0x00DFA872,
    0x00DFA885,
    0x00DFA8AA,
    0x00DFA8CB,
    0x00DFA8EA,
    0x00DFA90A,
    0x00DFA926,
}

ALLOWED_NEXT_CONTROL_BYTES = {0x00, 0x0A, 0x6B, 0x70, 0x71, 0x72, 0x77}

EVIDENCE_FILES = [
    ROOT / "docs" / "screenshots" / "part1_menu_help_spacing_2026-06-27" / "contact.png",
    ROOT / "docs" / "screenshots" / "part1_menu_help_spacing_2026-06-27" / "help_crops_4x.png",
    ROOT / "docs" / "screenshots" / "part1_menu_help_spacing_2026-06-27" / "full_sweep_contact.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "contact.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "battle_record_help_4x.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "map_design_help_4x.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "read_watch_report.json",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "shop_contact.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "shop_help.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "shop_help_4x.png",
    ROOT / "docs" / "screenshots" / "part1_unlocked_menu_help_2026-06-27" / "shop_read_watch_report.json",
    ROOT / "docs" / "screenshots" / "part1_campaign_help_2026-06-27" / "contact.png",
    ROOT / "docs" / "screenshots" / "part1_campaign_help_2026-06-27" / "help_crops_4x.png",
    ROOT / "docs" / "screenshots" / "part1_campaign_help_2026-06-27" / "read_watch_continue.json",
    ROOT / "docs" / "screenshots" / "part1_campaign_help_2026-06-27" / "read_watch_new_down.json",
    ROOT / "docs" / "screenshots" / "part1_campaign_help_2026-06-27" / "read_watch_new_up.json",
    ROOT / "docs" / "screenshots" / "part1_vs_continue_help_2026-06-28" / "contact.png",
    ROOT / "docs" / "screenshots" / "part1_vs_continue_help_2026-06-28" / "read_watch_report.json",
    ROOT / "docs" / "screenshots" / "part1_compact_help_forced_render_2026-06-28" / "contact.png",
    ROOT / "docs" / "screenshots" / "part1_compact_help_forced_render_2026-06-28" / "report.json",
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "contact_primary.png",
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "report_primary.json",
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "contact_player19.png",
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "report_player19.json",
]

LIVE_CODE_REPORTS = [
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "report_primary.json",
    ROOT / "docs" / "screenshots" / "part1_compact_help_live_code_injection_2026-06-28" / "report_player19.json",
]


def encoded_half_cells(raw: bytes) -> int:
    i = 0
    cur = 0
    best = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x00, 0x0A):
            best = max(best, cur)
            cur = 0
            i += 1
        elif 0x81 <= b <= 0xE2 and i + 1 < len(raw):
            cur += 2
            i += 2
        elif 0x20 <= b <= 0x7E:
            cur += 1
            i += 1
        else:
            i += 1
    return max(best, cur)


def has_single_byte_printable(raw: bytes) -> bool:
    i = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x00, 0x0A):
            i += 1
        elif 0x81 <= b <= 0xE2 and i + 1 < len(raw):
            i += 2
        elif 0x20 <= b <= 0x7E:
            return True
        else:
            i += 1
    return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_range_addr(value) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def live_code_report_applies_to_current(
    report: dict,
    path: Path,
    expected_rom_sha: str,
    current_rom: bytes,
    issues: list[dict],
    carry_forwarded: list[dict],
) -> bool:
    report_sha = report.get("rom_sha256")
    if report_sha == expected_rom_sha:
        return True

    applicability = report.get("carry_forward_applicability") or {}
    ranges = applicability.get("ranges") or report.get("applicability_ranges") or []
    if not ranges:
        issues.append({
            "type": "stale_live_code_injection_report",
            "path": str(path.relative_to(ROOT)),
            "expected_rom_sha256": expected_rom_sha,
            "actual_rom_sha256": report_sha,
        })
        return False

    mismatches = []
    checked = []
    for row in ranges:
        try:
            start = parse_range_addr(row["start"])
            end = parse_range_addr(row["end"])
            expected = row["sha256"]
        except Exception as exc:
            issues.append({
                "type": "bad_live_code_injection_applicability_range",
                "path": str(path.relative_to(ROOT)),
                "range": row,
                "error": str(exc),
            })
            return False
        actual = hashlib.sha256(current_rom[start:end]).hexdigest()
        item = {
            "name": row.get("name"),
            "start": f"0x{start:08X}",
            "end": f"0x{end:08X}",
            "sha256": expected,
            "current_sha256": actual,
        }
        checked.append(item)
        if actual != expected:
            mismatches.append(item)
    if mismatches:
        issues.append({
            "type": "stale_live_code_injection_report_range_mismatch",
            "path": str(path.relative_to(ROOT)),
            "expected_rom_sha256": expected_rom_sha,
            "actual_rom_sha256": report_sha,
            "mismatches": mismatches,
        })
        return False
    carry_forwarded.append({
        "path": str(path.relative_to(ROOT)),
        "capture_rom_sha256": report_sha,
        "current_rom_sha256": expected_rom_sha,
        "range_count": len(checked),
        "ranges": checked,
        "note": (
            "Accepted stale live-code injection evidence only because the "
            "pinned Part1 compact-help renderer/data ranges are byte-identical "
            "in the current ROM."
        ),
    })
    return True


def load_live_code_report_targets(
    path: Path,
    expected_rom_sha: str,
    current_rom: bytes,
    issues: list[dict],
    carry_forwarded: list[dict],
) -> set[int]:
    if not path.exists():
        return set()
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append({
            "type": "bad_live_code_injection_report_json",
            "path": str(path.relative_to(ROOT)),
            "error": str(exc),
        })
        return set()
    if not live_code_report_applies_to_current(report, path, expected_rom_sha, current_rom, issues, carry_forwarded):
        return set()
    targets: set[int] = set()
    for row in report.get("rows", []):
        summary = row.get("summary") or {}
        for raw_addr in summary.get("direct_targets") or []:
            try:
                targets.add(int(str(raw_addr), 16))
            except ValueError:
                issues.append({
                    "type": "bad_live_code_injection_target",
                    "path": str(path.relative_to(ROOT)),
                    "target": raw_addr,
                })
    return targets


def main() -> int:
    if not ROM.exists():
        print(f"[FAIL] missing ROM: {ROM}")
        return 1

    slots, found_texts = QTF.load_found()
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding="utf-8")).items()}
    syllable_leads = sorted({code >> 8 for code in syl_to_code.values()})
    rom = ROM.read_bytes()
    rom_sha = sha256(ROM)
    targets = {
        addr: text
        for addr, text in ADDRESS_TEXT_OVERRIDES.items()
        if HELP_START <= addr <= HELP_END_INCLUSIVE
    }

    issues: list[dict] = []
    rows: list[dict] = []

    if len(targets) != EXPECTED_COUNT:
        issues.append({"type": "target_count", "expected": EXPECTED_COUNT, "actual": len(targets)})

    if syllable_leads and syllable_leads[-1] > 0xE2:
        issues.append({
            "type": "unsupported_syllable_lead_range",
            "max_lead": f"0x{syllable_leads[-1]:02X}",
            "supported_max": "0xE2",
        })

    visual_current_count = len(CURRENT_VISUAL_EVIDENCE & set(targets))
    if visual_current_count != EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT:
        issues.append({
            "type": "visual_evidence_count_changed",
            "expected": EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT,
            "actual": visual_current_count,
        })
    synthetic_render_count = len(SYNTHETIC_RENDER_EVIDENCE & set(targets))
    if synthetic_render_count != EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT:
        issues.append({
            "type": "synthetic_render_evidence_count_changed",
            "expected": EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT,
            "actual": synthetic_render_count,
        })
    live_code_injection_count = len(LIVE_CODE_INJECTION_EVIDENCE & set(targets))
    if live_code_injection_count != EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT:
        issues.append({
            "type": "live_code_injection_evidence_count_changed",
            "expected": EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT,
            "actual": live_code_injection_count,
        })
    overlap = CURRENT_VISUAL_EVIDENCE & SYNTHETIC_RENDER_EVIDENCE
    if overlap:
        issues.append({
            "type": "direct_and_synthetic_evidence_overlap",
            "addresses": [f"0x{addr:08X}" for addr in sorted(overlap)],
        })
    live_missing = SYNTHETIC_RENDER_EVIDENCE - LIVE_CODE_INJECTION_EVIDENCE
    if live_missing:
        issues.append({
            "type": "synthetic_without_live_code_injection_evidence",
            "addresses": [f"0x{addr:08X}" for addr in sorted(live_missing)],
        })

    for path in EVIDENCE_FILES:
        if not path.exists():
            issues.append({"type": "missing_evidence_file", "path": str(path.relative_to(ROOT))})
    live_report_targets: set[int] = set()
    carry_forwarded_live_code_reports: list[dict] = []
    for path in LIVE_CODE_REPORTS:
        live_report_targets |= load_live_code_report_targets(path, rom_sha, rom, issues, carry_forwarded_live_code_reports)
    live_report_missing = LIVE_CODE_INJECTION_EVIDENCE - live_report_targets
    if live_report_missing:
        issues.append({
            "type": "live_code_injection_report_missing_targets",
            "addresses": [f"0x{addr:08X}" for addr in sorted(live_report_missing)],
            "reports": [str(path.relative_to(ROOT)) for path in LIVE_CODE_REPORTS],
        })

    for addr in sorted(targets):
        text = targets[addr]
        slot = slots.get(addr)
        row: dict = {
            "address": f"0x{addr:08X}",
            "text": text,
            "slot": slot,
            "visual_evidence_current": addr in CURRENT_VISUAL_EVIDENCE,
            "synthetic_render_evidence": addr in SYNTHETIC_RENDER_EVIDENCE,
            "live_code_injection_evidence": addr in LIVE_CODE_INJECTION_EVIDENCE,
            "source_japanese": found_texts.get(addr, ""),
        }
        if not slot:
            issues.append({"type": "missing_slot", "address": row["address"]})
            rows.append(row)
            continue
        enc, level = encode_fit(text, slot, syl_to_code, Counter(), addr)
        row["fit_level"] = level
        if enc is None:
            issues.append({"type": "encode_fit_failed", "address": row["address"], "slot": slot, "text": text})
            rows.append(row)
            continue
        active = enc
        actual = rom[addr : addr + slot]
        tail = actual[len(active) :]
        cells = encoded_half_cells(active)
        row["encoded_len"] = len(active)
        row["encoded_half_cells"] = cells
        row["actual_prefix_matches"] = actual.startswith(active)
        row["tail_padding_len"] = len(tail)
        row["tail_padding_ok"] = all(b in (0x00, 0x20) for b in tail)
        row["next_byte_after_slot"] = f"0x{rom[addr + slot]:02X}" if addr + slot < len(rom) else None
        row["next_byte_after_slot_ok"] = (
            bool(tail)
            or (addr + slot < len(rom) and rom[addr + slot] in ALLOWED_NEXT_CONTROL_BYTES)
        )
        row["single_byte_printable_in_active_payload"] = has_single_byte_printable(active)

        if level != 0:
            issues.append({"type": "non_level0_fit", "address": row["address"], "level": level})
        if not actual.startswith(active):
            issues.append({
                "type": "rom_prefix_mismatch",
                "address": row["address"],
                "expected_prefix": active.hex(),
                "actual": actual.hex(),
            })
        if not row["tail_padding_ok"]:
            issues.append({"type": "bad_tail_padding", "address": row["address"], "tail": tail.hex()})
        if not row["next_byte_after_slot_ok"]:
            issues.append({
                "type": "bad_next_byte_after_full_slot",
                "address": row["address"],
                "next_byte": row["next_byte_after_slot"],
                "allowed": [f"0x{b:02X}" for b in sorted(ALLOWED_NEXT_CONTROL_BYTES)],
            })
        if row["single_byte_printable_in_active_payload"]:
            issues.append({
                "type": "single_byte_printable_in_active_payload",
                "address": row["address"],
                "encoded": active.hex(),
            })
        if cells > MAX_ENCODED_HALF_CELLS:
            issues.append({
                "type": "encoded_width_over_limit",
                "address": row["address"],
                "cells": cells,
                "limit": MAX_ENCODED_HALF_CELLS,
                "text": text,
            })
        rows.append(row)

    visual_missing = [
        row["address"]
        for row in rows
        if not row.get("visual_evidence_current")
    ]
    render_evidence_missing = [
        row["address"]
        for row in rows
        if not row.get("visual_evidence_current") and not row.get("synthetic_render_evidence")
    ]
    report = {
        "rom": str(ROM.relative_to(ROOT)),
        "rom_sha256": rom_sha,
        "target_range": [f"0x{HELP_START:08X}", f"0x{HELP_END_INCLUSIVE:08X}"],
        "target_count": len(targets),
        "expected_count": EXPECTED_COUNT,
        "max_encoded_half_cells": MAX_ENCODED_HALF_CELLS,
        "expected_current_visual_evidence_count": EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT,
        "visual_evidence_current_count": visual_current_count,
        "visual_evidence_missing_count": len(visual_missing),
        "visual_evidence_missing_addresses": visual_missing,
        "expected_synthetic_render_evidence_count": EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT,
        "synthetic_render_evidence_count": synthetic_render_count,
        "expected_live_code_injection_evidence_count": EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT,
        "live_code_injection_evidence_count": live_code_injection_count,
        "live_code_injection_report_target_count": len(LIVE_CODE_INJECTION_EVIDENCE & live_report_targets),
        "carry_forwarded_live_code_report_count": len(carry_forwarded_live_code_reports),
        "carry_forwarded_live_code_reports": carry_forwarded_live_code_reports,
        "live_code_injection_report_missing_addresses": [
            f"0x{addr:08X}" for addr in sorted(LIVE_CODE_INJECTION_EVIDENCE - live_report_targets)
        ],
        "render_evidence_missing_count": len(render_evidence_missing),
        "render_evidence_missing_addresses": render_evidence_missing,
        "syllable_lead_min": f"0x{syllable_leads[0]:02X}" if syllable_leads else None,
        "syllable_lead_max": f"0x{syllable_leads[-1]:02X}" if syllable_leads else None,
        "allowed_next_control_bytes": [f"0x{b:02X}" for b in sorted(ALLOWED_NEXT_CONTROL_BYTES)],
        "evidence_files": [str(path.relative_to(ROOT)) for path in EVIDENCE_FILES],
        "issue_count": len(issues),
        "issues": issues,
        "rows": rows,
        "strict_note": (
            "This gate proves ROM byte/source safety and conservative width for all Part1 DFAxxx help overrides. "
            "Rows listed in visual_evidence_missing_addresses still need real route captures; "
            "synthetic/live-code evidence only proves the current renderer and code->pointer lookup can draw them "
            "without text breakage."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "target_count": len(targets),
        "issue_count": len(issues),
        "visual_evidence_current_count": report["visual_evidence_current_count"],
        "visual_evidence_missing_count": len(visual_missing),
        "synthetic_render_evidence_count": report["synthetic_render_evidence_count"],
        "live_code_injection_evidence_count": report["live_code_injection_evidence_count"],
        "render_evidence_missing_count": report["render_evidence_missing_count"],
        "report": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))
    if issues:
        for issue in issues[:20]:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
