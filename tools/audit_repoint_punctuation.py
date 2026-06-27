#!/usr/bin/env python3
"""Audit punctuation and source authority in relocated dialogue payloads."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT = ROOT / "output" / "game_wars_korean_full.gba"
TRANS = ROOT / "data" / "translation_for_import.csv"
DIALOGUE_OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
BTEAM_ADDRS = ROOT / "data" / "bteam_addresses.json"
INTEGRITY_MAP = ROOT / "temp" / "integrity_map.json"
REPOINT_MANIFEST = ROOT / "temp" / "repoint_manifest.json"
DEFAULT_REPORT = ROOT / "temp" / "repoint_punctuation_audit.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_korean_full as B  # noqa: E402


def norm_addr(value: Any) -> str | None:
    try:
        return "0x%08X" % int(value, 16 if isinstance(value, str) else 10)
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def load_csv_ko() -> dict[int, str]:
    out: dict[int, str] = {}
    with TRANS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            n = norm_addr(row.get("address"))
            if n:
                out[int(n, 16)] = str(row.get("korean") or "").strip()
    return out


def load_dialogue_overrides() -> dict[int, str]:
    out: dict[int, str] = {}
    raw = load_json(DIALOGUE_OVERRIDES, {})
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        canonical = B.canonical_override_addr(key)
        if canonical:
            out[int(canonical, 16)] = str(value or "").strip()
    return out


def load_bteam_addrs() -> set[int]:
    raw = load_json(BTEAM_ADDRS, {})
    values = raw.get("addresses", raw) if isinstance(raw, dict) else raw
    out: set[int] = set()
    for value in values or []:
        n = norm_addr(value)
        if n:
            out.add(int(n, 16))
    return out


def load_final_writes() -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for entry in load_json(INTEGRITY_MAP, []):
        if not isinstance(entry, list) or len(entry) < 8:
            continue
        try:
            addr = int(entry[0])
        except (TypeError, ValueError):
            continue
        out[addr] = {"korean": str(entry[5] or ""), "kind": str(entry[7] or "")}
    return out


def scan_payload(payload: bytes) -> dict[str, int]:
    counts = Counter()
    i = 0
    while i < len(payload):
        b = payload[i]
        if b == 0:
            break
        if 0x81 <= b <= 0xE2 and i + 1 < len(payload):
            code = (b << 8) | payload[i + 1]
            if code == 0x8140:
                counts["fullwidth_space"] += 1
            elif code == 0x8141:
                counts["fullwidth_comma"] += 1
            i += 2
            continue
        if b == 0x20:
            counts["ascii_space"] += 1
            nxt = payload[i + 1] if i + 1 < len(payload) else 0
            if 0x81 <= nxt <= 0xE2 or 0x21 <= nxt <= 0x7E:
                counts["interior_ascii_space"] += 1
        elif b == 0x2C:
            counts["ascii_comma"] += 1
        i += 1
    return dict(counts)


def choose_source(
    addr: int,
    *,
    csv_ko: dict[int, str],
    display: dict[int, str],
    address: dict[int, str],
    dialogue: dict[int, str],
    bteam: set[int],
    writes: dict[int, dict[str, Any]],
) -> tuple[str, str]:
    if addr in display:
        return "display_override", display[addr]
    if addr in address and str(address[addr] or "").strip():
        return "address_override", str(address[addr] or "").strip()
    if addr in bteam and addr in dialogue:
        return "bteam_dialogue_override", dialogue[addr]
    if addr in dialogue and str(dialogue[addr] or "").strip():
        return "dialogue_override", dialogue[addr]
    if addr in writes and str(writes[addr].get("korean") or "").strip():
        return "write_log", str(writes[addr].get("korean") or "").strip()
    if addr in csv_ko and csv_ko[addr]:
        return "csv", csv_ko[addr]
    return "unknown", ""


def build_report(rom_path: Path) -> dict[str, Any]:
    if hasattr(B, "refresh_compact_glyph_dictionary_overrides"):
        B.refresh_compact_glyph_dictionary_overrides(B.load_display_overrides(), strict=True)
    rom = rom_path.read_bytes()
    manifest = [m for m in load_json(REPOINT_MANIFEST, []) if isinstance(m, dict) and m.get("status") == "relocated"]
    csv_ko = load_csv_ko()
    display = {int(k): str(v or "") for k, v in B.load_display_overrides().items()}
    address = {int(k): str(v or "") for k, v in B.ADDRESS_TEXT_OVERRIDES.items()}
    dialogue = load_dialogue_overrides()
    bteam = load_bteam_addrs()
    writes = load_final_writes()

    payload_issue_examples: list[dict[str, Any]] = []
    source_examples: list[dict[str, Any]] = []
    payload_totals: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    fixed_line_count = 0
    source_ascii_commas = 0
    source_fullwidth_commas = 0

    for item in manifest:
        new_addr = int(item["new_addr"], 16)
        new_len = int(item.get("new_len", 0))
        payload = rom[new_addr:new_addr + new_len]
        counts = scan_payload(payload)
        payload_totals.update(counts)
        if counts.get("ascii_comma"):
            payload_issue_examples.append({
                "msg": item.get("msg"),
                "new_addr": item.get("new_addr"),
                "counts": counts,
            })
        for value in item.get("fixed", []) or []:
            n = norm_addr(value)
            if not n:
                continue
            addr = int(n, 16)
            source, text = choose_source(
                addr,
                csv_ko=csv_ko,
                display=display,
                address=address,
                dialogue=dialogue,
                bteam=bteam,
                writes=writes,
            )
            fixed_line_count += 1
            source_counts[source] += 1
            source_ascii_commas += text.count(",")
            source_fullwidth_commas += text.count("、")
            if len(source_examples) < 120:
                source_examples.append({
                    "address": n,
                    "source": source,
                    "text": text[:96],
                })

    return {
        "rom": str(rom_path.relative_to(ROOT)),
        "relocated_messages": len(manifest),
        "fixed_line_count": fixed_line_count,
        "payload_totals": dict(sorted(payload_totals.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "source_ascii_commas": source_ascii_commas,
        "source_fullwidth_commas": source_fullwidth_commas,
        "payload_issue_count": len(payload_issue_examples),
        "payload_issue_examples": payload_issue_examples[:80],
        "source_examples": source_examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", nargs="?", default=str(OUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.rom))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Repoint punctuation audit")
    print(f"- relocated messages: {report['relocated_messages']}")
    print(f"- fixed lines: {report['fixed_line_count']}")
    print(f"- source commas: ascii={report['source_ascii_commas']} fullwidth={report['source_fullwidth_commas']}")
    print(f"- payload totals: {report['payload_totals']}")
    print(f"- payload issue count: {report['payload_issue_count']}")
    print(f"- source counts: {report['source_counts']}")
    print(f"- report: {report_path.relative_to(ROOT)}")

    if args.strict and report["payload_issue_count"] > 0:
        print("[FAIL] Repoint punctuation audit", file=sys.stderr)
        return 1
    print("[OK] Repoint punctuation audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
