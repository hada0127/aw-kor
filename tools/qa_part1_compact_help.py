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
import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import qa_text_fit as QTF  # noqa: E402
from build_korean_full import (  # noqa: E402
    ADDRESS_TEXT_OVERRIDES, SYLCODE, encode_fit, encode_required_full_fidelity,
)

ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT = ROOT / "temp" / "part1_compact_help_qa.json"

HELP_START = 0x00DFA64A
HELP_END_INCLUSIVE = 0x00DFA9E9
EXPECTED_COUNT = 34
EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT = 23
EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT = 11
EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT = 11

# Values are encoded half-cells: two-byte SJIS/reserved codes count as 2,
# single-byte ASCII as 1. The current measured frame proves that a
# 32-half-cell line fits; it does not justify further growth.
MAX_ENCODED_HALF_CELLS = 32

# The complete 32-half-cell 0xDFA7BE line and final punctuation are visible
# in this b43 cold-boot cartridge-save frame. 0xDFA79A uses two 16-cell
# rows; the b39 34-cell single-row observation remains historical.
WIDTH_EVIDENCE_ROM_SHA256 = "1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02"
CURRENT_VISUAL_FRAME_DIR = ROOT / "data/evidence/part1_help_b44"
WIDTH_EVIDENCE_FRAME = CURRENT_VISUAL_FRAME_DIR / "DFA7BE_0014_NONE_0001625.png"
EVIDENCE_SHA256 = {
    "registration.json": "13049ce78263505374e5f0c9bc58e4395ee597ac514a2c8cd475fc77f573eca5",
    "0059_NONE_0003305.png": "fc71a34481f80dd08ab54abef5aeeb0b65aeb0420106fc59ede2e88038961cc2",
    "0016_DOWN_0001519.png": "ca31724fc8cd4cca983e98a8937e1a636187e5eae3e34b22bbb4a25131dd33d6",
    "0015_DOWN_0001498.png": "409146aefb5ad39185a8f4d710a5210b0b6111fb8202d4bcb40cdf0298849095",
    "0049_NONE_0002819.png": "ed1d251a171c5d63f195c284c5259e89c222dde094a3195115bf333a219a2ed3",
    "0014_DOWN_0001477.png": "eb033d3e9b04a58fbf46020e5ae8c9aa152d14dd16467b6b40e17351699f3318",
    "exit.json": "37858833e93dd96bac07dbc8268054ca06b35aaea3c6fad81fbe175a61202112",
    "window_measurement.json": "06b7f8d3012829e365e3122f6490fba62f7246b0a50eb8a77c284f9e0bc0036e",
    "0013_DOWN_0001456.png": "17fcc00c2ed45f446169300168309146f0ac47a1b1b83648cead076e127df985",
    "0060_DOWN_0003336.png": "9357952cfb23f28b422269ca3e2130c777fa6a45ec6a9e413654ed8ebbb5e1a5",
    "0012_DOWN_0001435.png": "51ec46e0b6e00bcf0f7eea6c93e0c9a54e9286e3b11948eb70ba6d148162b852",
    "DFA7BE_0014_NONE_0001625.png": "699e4b470a8ad321241c0ba29630c84388755e62a1050872d76009f0bdc5de94",
    "findings.tsv": "bd6dbaa02f2e89c29462b96b8e03209eb88b00fb1d14fa471b77bf9cef9c2bff",
    "0061_DOWN_0003367.png": "c7934e58bcb780b8c40e2378615f0fd2a832500c90735f07a9f597a42c3bbbe1",
    "DFA68C_0077_NONE_0003956.png": "caa1ae886878afd8f93afb188a1f05e025ea0c1e2ece4aeef35d1801106eebf7",
    "0051_NONE_0002880.png": "5484f669251b1c9c2f9faec066a355786599a33603e4abdb43f88cb2de4cdaad",
    "0033_NONE_0002121.png": "98e2481935e768dfe79998d8b12173bbe5440d6594ada255b8992137e5aaa60e",
    "baseline.json": "b0597ea1df2634b7009ce050fa3b5d7fa60f0066cf2a482acd4d671cdadcd2ad"
}


def validate_current_visual_registration(rom_sha: str) -> bool:
    """Bind each direct frame to a closed native C5 cold-boot capture."""
    from PIL import Image
    from capture_scene_screenshots import validate_recorder_endpoint
    try:
        receipt = json.loads((CURRENT_VISUAL_FRAME_DIR / "registration.json").read_text())
        if receipt["rom_sha256"] != rom_sha or len(receipt["frames"]) != 13:
            return False
        if {row["filename"] for row in receipt["frames"]} != {
                name for name in EVIDENCE_SHA256 if name.endswith(".png")}:
            return False
        for row in receipt["frames"]:
            frame = CURRENT_VISUAL_FRAME_DIR / row["filename"]
            native = ROOT / row["native_frame"]
            checkpoint = ROOT / row["native_checkpoint"]
            status = json.loads((ROOT / row["capture_exit"]).read_text())
            if (status["status"] != "closed" or status["emulator_exit_code"] != 0 or
                    sha256(frame) != row["sha256"] or sha256(native) != row["sha256"] or
                    sha256(checkpoint) != row["native_checkpoint_sha256"] or
                    json.loads(checkpoint.read_text())["rom_sha256"] != rom_sha):
                return False
            validate_recorder_endpoint({
                "recorder_endpoint": {
                    "checkpoint": row["native_checkpoint"],
                    "frame": row["native_frame"],
                    "frame_sha256": row["sha256"],
                    "core_frame": json.loads(checkpoint.read_text())["core_frame"],
                },
                "cheat_tainted": False,
            }, rom_sha)
            with Image.open(frame) as current, Image.open(native) as source:
                if current.convert("RGB").tobytes() != source.convert("RGB").tobytes():
                    return False
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return False
    return True

# The original line addresses remain source identifiers after dialogue repoint.
# Every pointer site is checked against the final ROM before reading the payload.
RELOCATED_HELP_POINTERS = {
    0x00DFA79A: (0x00DFAAD8, 0x00DFAAE4, 0x00DFAAF0, 0x00DFAB18),
    0x00DFA7BE: (0x00DFAADC, 0x00DFAAE8, 0x00DFAAF4, 0x00DFAB1C),
    0x00DFA8AA: (0x00DFAAF8,),
    0x00DFA8CB: (0x00DFAAF8,),
    0x00DFA8EA: (0x00DFAAFC,),
    0x00DFA90A: (0x00DFAB00,),
    0x00DFA926: (0x00DFAB04,),
}

# Direct cold-boot cartridge-save captures for WIDTH_EVIDENCE_ROM_SHA256.
# The 2026-06-27 captures belong to an older ROM and do not count here.
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

CURRENT_VISUAL_FRAMES = {
    0x00DFA68C: "DFA68C_0077_NONE_0003956.png",
    0x00DFA7BE: "DFA7BE_0014_NONE_0001625.png",
    **dict.fromkeys((0x00DFA6AA, 0x00DFA6CD), "0012_DOWN_0001435.png"),
    **dict.fromkeys((0x00DFA752, 0x00DFA775), "0013_DOWN_0001456.png"),
    **dict.fromkeys((0x00DFA942, 0x00DFA95B), "0014_DOWN_0001477.png"),
    **dict.fromkeys((0x00DFA71B, 0x00DFA72E), "0015_DOWN_0001498.png"),
    **dict.fromkeys((0x00DFA6E2, 0x00DFA6FB), "0016_DOWN_0001519.png"),
    0x00DFA79A: "0033_NONE_0002121.png",
    **dict.fromkeys((0x00DFA80E, 0x00DFA829), "0049_NONE_0002819.png"),
    **dict.fromkeys((0x00DFA7E2, 0x00DFA7FD), "0051_NONE_0002880.png"),
    **dict.fromkeys((0x00DFA9AE, 0x00DFA9C7), "0059_NONE_0003305.png"),
    **dict.fromkeys((0x00DFA972, 0x00DFA989), "0060_DOWN_0003336.png"),
    **dict.fromkeys((0x00DFA9DA, 0x00DFA9E9), "0061_DOWN_0003367.png"),
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
    ROOT / "data" / "evidence" / "part1_help_b44_synthetic" / "report.json",
]

B42_REFLOWED_HELP = 0x00DFA79A
B42_APPROVED_BTEAM_SPACING = {0x00DFA8EA, 0x00DFA90A, 0x00DFA926}


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


def resolved_target_bus(rom: bytes, raw_target: str) -> str:
    """Resolve the final ROM's help pointer instead of trusting report addresses."""
    target = int(raw_target, 16)
    if target not in RELOCATED_HELP_POINTERS:
        return f"0x{target + 0x08000000:08X}"
    pointer = struct.unpack_from("<I", rom, RELOCATED_HELP_POINTERS[target][0])[0]
    if target == 0x00DFA8CB:
        start = pointer - 0x08000000
        marker = rom.find(b"\x72\x0A\x09", start, start + 128)
        if marker < 0:
            raise ValueError("second relocated line marker missing")
        pointer = 0x08000000 + marker + 3
    else:
        pointer += 2
    return f"0x{pointer:08X}"


def displayed_rows(payload: bytes) -> list[int]:
    """Parse compact-help text through its 0A 00 terminator."""
    widths = [0]
    i = 0
    while i < len(payload):
        b = payload[i]
        if b == 0x0A:
            if i + 1 >= len(payload):
                raise ValueError("truncated 0A control")
            operand = payload[i + 1]
            if operand == 0x00:
                if i + 2 != len(payload):
                    raise ValueError("bytes after terminator")
                return widths
            if operand != 0x09:
                raise ValueError(f"unknown 0A control {operand:02X}")
            if i != 0:
                widths.append(0)
            i += 2
        elif b in (0x72, 0x6B, 0x70, 0x71):
            if i + 2 >= len(payload) or payload[i + 1:i + 3] not in (b"\x0A\x09", b"\x0A\x00"):
                raise ValueError(f"continuation {b:02X} lacks row header")
            i += 1
        elif b == 0x77:
            i += 1  # same-row wait
        elif 0x81 <= b <= 0xE2:
            if i + 1 >= len(payload) or payload[i + 1] < 0x40:
                raise ValueError("truncated text pair")
            widths[-1] += 2
            i += 2
        elif b == 0x20:
            widths[-1] += 1
            i += 1
        else:
            raise ValueError(f"unsupported text/control byte {b:02X}")
    raise ValueError("missing 0A 00 terminator")


def source_message_row_count(rom: bytes, address: int) -> int:
    """Count row headers in the complete in-place message containing a target."""
    previous_end = rom.rfind(b"\x0A\x00", max(0, address - 256), address)
    start = rom.find(b"\x0A\x09", previous_end + 2, address + 2)
    end = rom.find(b"\x0A\x00", address, min(len(rom), address + 256))
    if start < 0 or end < 0 or not start <= address < end:
        raise ValueError("message header or terminator missing")
    message = rom[start:end + 2]
    headers = message.count(b"\x0A\x09")
    if headers == 0:
        raise ValueError("message has no row header")
    for i, byte in enumerate(message[:-2]):
        if byte in (0x6B, 0x70, 0x71, 0x72) and message[i + 1:i + 3] not in (b"\x0A\x09", b"\x0A\x00"):
            # Only inspect standalone control bytes; SJIS trails can match them.
            if not (i > 0 and 0x81 <= message[i - 1] <= 0xE2):
                raise ValueError(f"malformed continuation {byte:02X}")
    return headers


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
        try:
            trace = ROOT / row["trace"]
            frame = ROOT / row["frame"]
            state = ROOT / row["state"]
            checkpoint = ROOT / row["state_checkpoint"]
            state_record = json.loads(checkpoint.read_text())
            if (sha256(trace) != row["trace_sha256"] or
                    sha256(frame) != row["frame_sha256"] or
                    sha256(state) != row["state_sha256"] or
                    sha256(checkpoint) != row["state_checkpoint_sha256"] or
                    state_record["rom_sha256"] != expected_rom_sha or
                    state_record["state_sha256"] != row["state_sha256"] or
                    row["cheat_tainted"] is not True):
                raise ValueError("trace, frame, state, or taint mismatch")
            if any(sha256(ROOT / extra["frame"]) != extra["frame_sha256"]
                   for extra in row.get("additional_frames", [])):
                raise ValueError("additional frame hash mismatch")
            for target in row["target_reads"]:
                visuals = row.get("target_visual_evidence", {}).get(target)
                if not isinstance(visuals, list) or not visuals:
                    raise ValueError(f"target {target} has no visual evidence")
                if any(sha256(ROOT / visual["frame"]) != visual["frame_sha256"]
                       for visual in visuals):
                    raise ValueError(f"target {target} visual evidence hash mismatch")
            declared_visuals = {extra["frame"] for extra in row.get("additional_frames", [])}
            used_visuals = {v["frame"] for values in row["target_visual_evidence"].values() for v in values}
            if not used_visuals <= declared_visuals | {row["frame"]}:
                raise ValueError("target visual frame missing from declared additional_frames")
            if not declared_visuals <= used_visuals:
                raise ValueError("additional visual frame not bound to a target")
            if any(int(row["target_reads"][target], 16) != int(resolved_target_bus(current_rom, target), 16)
                   for target in row["target_reads"]):
                raise ValueError("target read does not match ROM-resolved mapping")
            observed = {token.split("=", 1)[1].upper()
                        for line in trace.read_text().splitlines()
                        for token in line.split() if token.startswith("addr=")}
            if any(str(bus)[2:].upper() not in observed for bus in row["target_reads"].values()):
                raise ValueError("target read missing from trace")
            if set(row["target_reads"]) != set((row.get("summary") or {}).get("direct_targets") or []):
                raise ValueError("target read set mismatch")
        except (OSError, KeyError, ValueError, TypeError, struct.error) as exc:
            issues.append({"type": "invalid_live_code_injection_evidence",
                           "path": str(path.relative_to(ROOT)), "case_id": row.get("case_id"), "error": str(exc)})
            continue
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROM)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    rom_path = args.rom.resolve()
    if not rom_path.exists():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"issue_count": 1, "issues": [{"type": "missing_rom", "path": str(rom_path)}]}, indent=2) + "\n")
        print(f"[FAIL] missing ROM: {rom_path}")
        return 1

    slots, found_texts = QTF.load_found()
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding="utf-8")).items()}
    syllable_leads = sorted({code >> 8 for code in syl_to_code.values()})
    rom = rom_path.read_bytes()
    rom_sha = sha256(rom_path)
    targets = {
        addr: text
        for addr, text in ADDRESS_TEXT_OVERRIDES.items()
        if HELP_START <= addr <= HELP_END_INCLUSIVE
    }

    issues: list[dict] = []
    rows: list[dict] = []
    b42_spacing = {}
    if rom_sha == WIDTH_EVIDENCE_ROM_SHA256:
        try:
            spacing = json.loads((ROOT / 'data/dialogue_spacing_repairs.json').read_text())
            b42_spacing = {int(item['address'], 16): item for item in spacing['bteam']
                           if item.get('address') and int(item['address'], 16) in B42_APPROVED_BTEAM_SPACING}
            if set(b42_spacing) != B42_APPROVED_BTEAM_SPACING:
                issues.append({'type': 'approved_b42_help_spacing_missing'})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            issues.append({'type': 'approved_b42_help_spacing_unreadable', 'error': str(exc)})

    valid_evidence = set()
    for name, expected_sha in EVIDENCE_SHA256.items():
        path = CURRENT_VISUAL_FRAME_DIR / name
        actual_sha = sha256(path) if path.is_file() else None
        if actual_sha == expected_sha:
            valid_evidence.add(name)
        else:
            issues.append({"type": "evidence_sha256_mismatch", "file": name,
                           "expected": expected_sha, "actual": actual_sha})
    try:
        capture_baseline = json.loads((CURRENT_VISUAL_FRAME_DIR / "baseline.json").read_text())
        capture_exit = json.loads((CURRENT_VISUAL_FRAME_DIR / "exit.json").read_text())
        measurement = json.loads((CURRENT_VISUAL_FRAME_DIR / "window_measurement.json").read_text())
        capture_valid = (capture_baseline.get("rom_sha256") == WIDTH_EVIDENCE_ROM_SHA256
                         and capture_exit.get("status") == "closed"
                         and capture_exit.get("emulator_exit_code") == 0
                         and measurement.get("rom_sha256") == WIDTH_EVIDENCE_ROM_SHA256
                         and measurement.get("safe_observed_capacity_half_cells") == MAX_ENCODED_HALF_CELLS
                         and measurement.get("visible_help_rows") == 2
                         and measurement.get("frame") == str(WIDTH_EVIDENCE_FRAME.relative_to(ROOT))
                         and {"baseline.json", "exit.json", "window_measurement.json", "findings.tsv",
                              "registration.json"} <= valid_evidence
                         and validate_current_visual_registration(rom_sha))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        capture_valid = False
        issues.append({"type": "current_visual_capture_receipt_unreadable", "error": str(exc)})
    if not capture_valid:
        issues.append({"type": "current_visual_capture_receipt_invalid",
                       "capture_dir": str(CURRENT_VISUAL_FRAME_DIR.relative_to(ROOT))})

    if rom_sha != WIDTH_EVIDENCE_ROM_SHA256 or not capture_valid or WIDTH_EVIDENCE_FRAME.name not in valid_evidence:
        issues.append({
            "type": "width_evidence_not_applicable",
            "expected_rom_sha256": WIDTH_EVIDENCE_ROM_SHA256,
            "actual_rom_sha256": rom_sha,
            "frame": str(WIDTH_EVIDENCE_FRAME.relative_to(ROOT)),
        })
    if set(CURRENT_VISUAL_FRAMES) != CURRENT_VISUAL_EVIDENCE:
        issues.append({"type": "current_visual_frame_map_mismatch"})
    for address, frame in CURRENT_VISUAL_FRAMES.items():
        if frame not in valid_evidence:
            issues.append({"type": "missing_current_visual_frame",
                           "address": f"0x{address:08X}", "frame": frame})

    if len(targets) != EXPECTED_COUNT:
        issues.append({"type": "target_count", "expected": EXPECTED_COUNT, "actual": len(targets)})

    if syllable_leads and syllable_leads[-1] > 0xE2:
        issues.append({
            "type": "unsupported_syllable_lead_range",
            "max_lead": f"0x{syllable_leads[-1]:02X}",
            "supported_max": "0xE2",
        })

    current_visual = ({addr for addr, frame in CURRENT_VISUAL_FRAMES.items() if frame in valid_evidence}
                      if rom_sha == WIDTH_EVIDENCE_ROM_SHA256 and capture_valid else set())
    visual_current_count = len(current_visual & set(targets))
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
            "visual_evidence_current": addr in current_visual,
            "visual_evidence_frame": str((CURRENT_VISUAL_FRAME_DIR / CURRENT_VISUAL_FRAMES[addr]).relative_to(ROOT))
            if addr in current_visual else None,
            "synthetic_render_evidence": addr in SYNTHETIC_RENDER_EVIDENCE and addr in live_report_targets,
            "live_code_injection_evidence": addr in LIVE_CODE_INJECTION_EVIDENCE and addr in live_report_targets,
            "source_japanese": found_texts.get(addr, ""),
        }
        if not slot:
            issues.append({"type": "missing_slot", "address": row["address"]})
            rows.append(row)
            continue
        relocated_sites = RELOCATED_HELP_POINTERS.get(addr)
        if relocated_sites:
            if any(site + 4 > len(rom) for site in relocated_sites):
                issues.append({"type": "truncated_rom_pointer", "address": row["address"]})
                rows.append(row)
                continue
            pointers = [struct.unpack_from("<I", rom, site)[0] for site in relocated_sites]
            if len(set(pointers)) != 1 or not 0x08000000 <= pointers[0] < 0x0A000000:
                issues.append({"type": "relocated_pointer_mismatch", "address": row["address"],
                               "pointer_sites": [f"0x{s:08X}" for s in relocated_sites],
                               "values": [f"0x{p:08X}" for p in pointers]})
                rows.append(row)
                continue
            message_addr = pointers[0] - 0x08000000
            if rom[message_addr:message_addr + 2] != b"\x0A\x09":
                issues.append({"type": "relocated_message_header", "address": row["address"],
                               "message_addr": f"0x{message_addr:08X}"})
                rows.append(row)
                continue
            enc = encode_required_full_fidelity(text, syl_to_code, Counter(), addr)
            if rom_sha == WIDTH_EVIDENCE_ROM_SHA256 and addr in B42_APPROVED_BTEAM_SPACING:
                repair = b42_spacing.get(addr)
                if (repair is None or repair.get('baseline') != text
                        or repair.get('classification') != 'restored'
                        or len(repair.get('final_fragment_hex', [])) != 1):
                    issues.append({'type': 'approved_b42_help_spacing_invalid', 'address': row['address']})
                    rows.append(row)
                    continue
                enc = bytes.fromhex(repair['final_fragment_hex'][0])
            level = 0
            active_addr = message_addr + 2
            if addr == 0xDFA8CB:
                first = encode_required_full_fidelity(targets[0xDFA8AA], syl_to_code, Counter(), 0xDFA8AA)
                active_addr += len(first) + 3
            row["relocated_message_addr"] = f"0x{message_addr:08X}"
            row["pointer_sites"] = [f"0x{s:08X}" for s in relocated_sites]
        else:
            enc, level = encode_fit(text, slot, syl_to_code, Counter(), addr)
            active_addr = addr
        row["fit_level"] = level
        if enc is None:
            issues.append({"type": "encode_fit_failed", "address": row["address"], "slot": slot, "text": text})
            rows.append(row)
            continue
        b42_reflow = rom_sha == WIDTH_EVIDENCE_ROM_SHA256 and addr == B42_REFLOWED_HELP
        if b42_reflow:
            if len(enc) != 34 or enc[16:18] != b'\x81\x40':
                issues.append({'type': 'b42_help_reflow_source_changed', 'address': row['address']})
                rows.append(row)
                continue
            active = enc[:16] + b'\x72' + enc[18:]
            row['approved_reflow_row_widths'] = [16, 16]
        else:
            active = enc
        actual = rom[active_addr : active_addr + (len(active) if relocated_sites else slot)]
        tail = actual[len(active) :]
        cells = encoded_half_cells(active)
        row["encoded_len"] = len(active)
        row["encoded_half_cells"] = cells
        row["actual_prefix_matches"] = actual.startswith(active)
        row["tail_padding_len"] = len(tail)
        row["tail_padding_ok"] = all(b in (0x00, 0x20) for b in tail)
        next_addr = active_addr + len(active) if relocated_sites else addr + slot
        row["next_byte_after_slot"] = f"0x{rom[next_addr]:02X}" if next_addr < len(rom) else None
        row["next_byte_after_slot_ok"] = (
            bool(relocated_sites) or bool(tail)
            or (next_addr < len(rom) and rom[next_addr] in ALLOWED_NEXT_CONTROL_BYTES)
        )
        row["single_byte_printable_in_active_payload"] = has_single_byte_printable(
            active.replace(b'\x72', b'') if b42_reflow else active)

        if not relocated_sites:
            try:
                row["displayed_row_count"] = source_message_row_count(rom, addr)
                if row["displayed_row_count"] > 2:
                    issues.append({"type": "displayed_row_limit", "address": row["address"],
                                   "rows": row["displayed_row_count"]})
            except ValueError as exc:
                issues.append({"type": "invalid_source_message_control_sequence", "address": row["address"],
                               "error": str(exc)})

        if relocated_sites:
            # 0xDFA8CB is the second member of the relocated 0xDFA8AA message.
            # Check both encoded fragments and the exact intervening controls.
            if b42_reflow:
                expected_message = b'\x0A\x09' + active + b'\x20\x20\x00'
            elif addr in (0xDFA8AA, 0xDFA8CB):
                first = encode_required_full_fidelity(targets[0xDFA8AA], syl_to_code, Counter(), 0xDFA8AA)
                second = encode_required_full_fidelity(targets[0xDFA8CB], syl_to_code, Counter(), 0xDFA8CB)
                expected_message = b"\x0A\x09" + first + b"\x72\x0A\x09" + second + b" " * 14 + b"\x0A\x00"
            else:
                suffix = b"\x72\x0A\x00" if addr == 0xDFA7BE else b"\x0A\x00"
                expected_message = b"\x0A\x09" + enc + suffix
            if b42_reflow:
                final_message = rom[message_addr:message_addr + len(expected_message)]
            else:
                terminator = rom.find(b"\x0A\x00", message_addr, min(len(rom), message_addr + 128))
                final_message = rom[message_addr:terminator + 2] if terminator >= 0 else rom[message_addr:message_addr + 128]
            if final_message != expected_message:
                issues.append({"type": "relocated_full_message_mismatch", "address": row["address"],
                               "message_addr": row["relocated_message_addr"],
                               "expected": expected_message.hex(), "actual": final_message.hex()})
            try:
                widths = [16, 16] if b42_reflow and final_message == expected_message else displayed_rows(final_message)
                row["displayed_row_widths"] = widths
                if len(widths) > 2:
                    issues.append({"type": "displayed_row_limit", "address": row["address"], "rows": len(widths)})
                if any(width > MAX_ENCODED_HALF_CELLS for width in widths):
                    issues.append({"type": "displayed_row_width_limit", "address": row["address"], "widths": widths})
            except ValueError as exc:
                issues.append({"type": "invalid_relocated_control_sequence", "address": row["address"], "error": str(exc)})

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
        width_to_check = max(row.get('displayed_row_widths', [cells])) if b42_reflow else cells
        if width_to_check > MAX_ENCODED_HALF_CELLS:
            issues.append({
                "type": "encoded_width_over_limit",
                "address": row["address"],
                "cells": width_to_check,
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
    if render_evidence_missing:
        issues.append({"type": "missing_render_evidence", "addresses": render_evidence_missing})
    synthetic_current_count = len(SYNTHETIC_RENDER_EVIDENCE & live_report_targets & set(targets))
    live_current_count = len(LIVE_CODE_INJECTION_EVIDENCE & live_report_targets & set(targets))
    report = {
        "rom": str(rom_path.relative_to(ROOT)) if rom_path.is_relative_to(ROOT) else str(rom_path),
        "rom_sha256": rom_sha,
        "target_range": [f"0x{HELP_START:08X}", f"0x{HELP_END_INCLUSIVE:08X}"],
        "target_count": len(targets),
        "expected_count": EXPECTED_COUNT,
        "max_encoded_half_cells": MAX_ENCODED_HALF_CELLS,
        "width_evidence_rom_sha256": WIDTH_EVIDENCE_ROM_SHA256,
        "width_evidence_frame": str(WIDTH_EVIDENCE_FRAME.relative_to(ROOT)),
        "expected_current_visual_evidence_count": EXPECTED_CURRENT_VISUAL_EVIDENCE_COUNT,
        "visual_evidence_current_count": visual_current_count,
        "visual_evidence_missing_count": len(visual_missing),
        "visual_evidence_missing_addresses": visual_missing,
        "expected_synthetic_render_evidence_count": EXPECTED_SYNTHETIC_RENDER_EVIDENCE_COUNT,
        "synthetic_render_evidence_count": synthetic_current_count,
        "synthetic_render_evidence_current_count": synthetic_current_count,
        "expected_live_code_injection_evidence_count": EXPECTED_LIVE_CODE_INJECTION_EVIDENCE_COUNT,
        "live_code_injection_evidence_count": live_current_count,
        "live_code_injection_report_target_count": live_current_count,
        "evidence_sha256": EVIDENCE_SHA256,
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
            "This gate checks final ROM bytes and the observed 32-half-cell width for Part1 help overrides. "
            "Rows in visual_evidence_missing_addresses still need current-ROM route captures. "
            "Older synthetic/live-code reports are counted only when their ROM SHA or pinned ranges match."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "target_count": len(targets),
        "issue_count": len(issues),
        "visual_evidence_current_count": report["visual_evidence_current_count"],
        "visual_evidence_missing_count": len(visual_missing),
        "synthetic_render_evidence_count": report["synthetic_render_evidence_count"],
        "live_code_injection_evidence_count": report["live_code_injection_evidence_count"],
        "render_evidence_missing_count": report["render_evidence_missing_count"],
        "report": str(args.out),
    }, ensure_ascii=False))
    if issues:
        for issue in issues[:20]:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Keep a fresh machine-readable FAIL report even for malformed input.
        failure_parser = argparse.ArgumentParser(add_help=False)
        failure_parser.add_argument("--out", type=Path, default=OUT)
        failure_parser.add_argument("--rom")
        failure_args, _ = failure_parser.parse_known_args()
        failure = {"issue_count": 1, "issues": [{"type": "gate_exception",
                                                  "error": f"{type(exc).__name__}: {exc}"}]}
        failure_args.out.parent.mkdir(parents=True, exist_ok=True)
        failure_args.out.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(f"[FAIL] {failure['issues'][0]}", file=sys.stderr)
        sys.exit(1)
