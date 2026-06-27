#!/usr/bin/env python3
"""Analyze pointer xrefs for E12 compact display targets.

This is static provenance only. It proves that a target has ROM pointer
references, not that the target was rendered on screen. The output is used to
separate "no obvious pointer user" from "runtime entrypoint still missing".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
DISPLAY_OVERRIDES = ROOT / "data" / "display_overrides.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DIALOGUE_GROUPS = ROOT / "data" / "dialogue_groups.json"
OUT_JSON = ROOT / "data" / "compact_display_xref_analysis.json"

GROUP_SPECS = [
    {
        "id": "a2_co_power_profile_display_overrides",
        "title": "A2 CO power profile compact names",
        "ranges": [(0xA2955C, 0xA29830)],
        "source": "display_overrides",
    },
    {
        "id": "b84_compact_power_display_overrides",
        "title": "B84 compact CO power names",
        "ranges": [(0xB84E50, 0xB84F18)],
        "source": "display_overrides",
    },
    {
        "id": "b8_compact_display_table_all",
        "title": "B8 compact display table bucket",
        "ranges": [(0xB81800, 0xB85000)],
        "source": "dialogue_groups",
    },
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_addr(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def in_ranges(addr: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= addr < end for start, end in ranges)


def target_group(addr: int) -> str | None:
    for spec in GROUP_SPECS:
        if in_ranges(addr, spec["ranges"]):
            return spec["id"]
    return None


def find_refs(rom: bytes, file_addr: int) -> list[int]:
    ptr = (0x08000000 + file_addr).to_bytes(4, "little")
    refs = []
    pos = rom.find(ptr)
    while pos != -1:
        refs.append(pos)
        pos = rom.find(ptr, pos + 1)
    return refs


def ref_bucket(ref: int) -> str:
    if 0x080000 <= ref < 0xB80000:
        return "code_or_static"
    if 0xB81800 <= ref < 0xB85000:
        return "b8_internal"
    if 0xA2955C <= ref < 0xA29830:
        return "a2_internal"
    if 0xDE0000 <= ref < 0xE20000:
        return "part2_table"
    if 0xD80000 <= ref < 0xDE0000:
        return "part1_or_table"
    return f"0x{(ref // 0x10000) * 0x10000:06X}"


def build_line_index() -> dict[int, dict]:
    out = {}
    for row in load(DIALOGUE_MAP).get("lines", []):
        addr = parse_addr(row.get("address"))
        if addr is not None:
            out[addr] = row
    return out


def build_targets_by_group() -> dict[str, dict[int, dict]]:
    display_overrides = load(DISPLAY_OVERRIDES)
    line_by_addr = build_line_index()
    targets_by_group: dict[str, dict[int, dict]] = {spec["id"]: {} for spec in GROUP_SPECS}
    for spec in GROUP_SPECS:
        targets = targets_by_group[spec["id"]]
        if spec["source"] == "display_overrides":
            for key, ko in display_overrides.items():
                addr = parse_addr(key)
                if addr is None or not in_ranges(addr, spec["ranges"]):
                    continue
                line = line_by_addr.get(addr, {})
                targets[addr] = {
                    "address": f"0x{addr:08X}",
                    "group_id": spec["id"],
                    "ko": ko,
                    "ja": line.get("ja") or "",
                    "kind": line.get("kind"),
                }
        else:
            for group in load(DIALOGUE_GROUPS).get("groups", []):
                gid = group.get("group_id")
                for member in group.get("members", []):
                    addr = parse_addr(member.get("address"))
                    if addr is None or not in_ranges(addr, spec["ranges"]):
                        continue
                    line = line_by_addr.get(addr, {})
                    targets[addr] = {
                        "address": f"0x{addr:08X}",
                        "group_id": spec["id"],
                        "dialogue_group_id": gid,
                        "ko": line.get("ko") or "",
                        "ja": line.get("ja") or "",
                        "kind": line.get("kind"),
                    }
    return targets_by_group


def analyze_target(rom: bytes, addr: int, target: dict) -> dict:
    refs = find_refs(rom, addr)
    owning_group = target_group(addr)
    external_refs = [
        ref for ref in refs
        if target_group(ref) != owning_group
    ]
    second_level_refs = []
    # If an entry is referenced by a table slot, search for pointers to the
    # start of that observed slot. This often reveals the code/literal user of
    # the whole pointer table.
    for ref in refs[:16]:
        for ref2 in find_refs(rom, ref)[:16]:
            second_level_refs.append(ref2)
    return {
        **target,
        "pointer_ref_count": len(refs),
        "external_pointer_ref_count": len(external_refs),
        "pointer_refs": [f"0x{ref:08X}" for ref in refs[:64]],
        "external_pointer_refs": [f"0x{ref:08X}" for ref in external_refs[:64]],
        "pointer_ref_buckets": dict(Counter(ref_bucket(ref) for ref in refs)),
        "second_level_ref_count": len(second_level_refs),
        "second_level_refs": [f"0x{ref:08X}" for ref in sorted(set(second_level_refs))[:64]],
    }


def summarize(rows: list[dict]) -> dict:
    buckets = Counter()
    for row in rows:
        buckets.update(row.get("pointer_ref_buckets") or {})
    return {
        "target_count": len(rows),
        "with_pointer_refs": sum(1 for row in rows if row["pointer_ref_count"] > 0),
        "with_external_pointer_refs": sum(1 for row in rows if row["external_pointer_ref_count"] > 0),
        "with_second_level_refs": sum(1 for row in rows if row["second_level_ref_count"] > 0),
        "pointer_ref_total": sum(row["pointer_ref_count"] for row in rows),
        "external_pointer_ref_total": sum(row["external_pointer_ref_count"] for row in rows),
        "pointer_ref_buckets": dict(buckets),
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> int:
    global ROM, OUT_JSON
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    args = ap.parse_args()

    ROM = Path(args.rom)
    if not ROM.is_absolute():
        ROM = ROOT / ROM
    OUT_JSON = Path(args.out_json)
    if not OUT_JSON.is_absolute():
        OUT_JSON = ROOT / OUT_JSON
    if not ROM.exists():
        raise SystemExit(f"ROM 없음: {ROM}")

    rom = ROM.read_bytes()
    targets_by_group = build_targets_by_group()
    groups = []
    for spec in GROUP_SPECS:
        targets = targets_by_group[spec["id"]]
        rows = [
            analyze_target(rom, addr, target)
            for addr, target in sorted(targets.items())
        ]
        groups.append({
            "id": spec["id"],
            "title": spec["title"],
            "ranges": [f"0x{start:08X}:0x{end:08X}" for start, end in spec["ranges"]],
            "summary": summarize(rows),
            "targets": rows,
        })

    report = {
        "tool": "tools/analyze_compact_display_xrefs.py",
        "rom": rel(ROM),
        "rom_sha256": sha256(ROM),
        "git_commit": git_commit(),
        "groups": groups,
        "strict_note": (
            "Pointer xrefs are static provenance only. They do not prove a target "
            "was rendered; runtime direct evidence still requires screen or trace proof."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "out_json": rel(OUT_JSON),
        "rom_sha256": report["rom_sha256"],
        "groups": [{"id": group["id"], **group["summary"]} for group in groups],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
