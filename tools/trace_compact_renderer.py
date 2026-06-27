#!/usr/bin/env python3
"""Trace compact display renderer entrypoints in mGBA.

E12 needs runtime evidence, not just static byte/editor coverage. This helper
sets hardware breakpoints on the currently documented compact renderer
candidates, drives existing screen/freshrender routes, and records registers
from each hit. A target becomes direct evidence only when a general register
contains an exact known compact display target address.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_comparison_sheet import run_nav  # noqa: E402
from capture_freshrender import run_refresh  # noqa: E402
from qa_visual_regions import MGBADriver  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path("/tmp/mgbah")
SCREEN_CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
FRESHRENDER_CHECKPOINTS = ROOT / "data" / "freshrender_checkpoints.json"
DISPLAY_OVERRIDES = ROOT / "data" / "display_overrides.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DIALOGUE_GROUPS = ROOT / "data" / "dialogue_groups.json"
CODE_CONTEXT = ROOT / "data" / "compact_display_code_context.json"
OUT_JSON = ROOT / "data" / "compact_display_renderer_trace.json"

DEFAULT_SCREEN_CHECKPOINTS = [
    "07_part2_main_menu",
    "scene_23a_part2_wars_shop",
    "scene_86_common_compact_menu_tables",
    "scene_87_common_rule_settings",
    "30_battle_attack",
    "scene_27_part2_battle_objlabels",
    "scene_26a_part2_battle_start_overlay_f060",
    "41_part1_operation_room",
]
DEFAULT_FRESHRENDER = [
    "co_profile_maxg",
    "co_profile_domino",
]

BASE_BREAKPOINTS = [
    {"addr": 0x08380564, "label": "a2_compact_renderer"},
    {"addr": 0x083806A8, "label": "a2_compact_callsite_1"},
    {"addr": 0x08381294, "label": "a2_compact_callsite_2"},
    {"addr": 0x08B3C184, "label": "b842_compact_renderer"},
    {"addr": 0x08B3C2D0, "label": "b84_pointer_table_user_candidate_1"},
    {"addr": 0x08B3C300, "label": "b84_pointer_table_user_candidate_2"},
    {"addr": 0x08B3C320, "label": "b84_pointer_table_user_candidate_3"},
    {"addr": 0x08B3C4D6, "label": "b84_pointer_table_user_candidate_4"},
    {"addr": 0x08B3C550, "label": "b84_pointer_table_user_candidate_5"},
    {"addr": 0x08B3C5A0, "label": "b84_pointer_table_user_candidate_6"},
    {"addr": 0x08B12A82, "label": "b8_operation_reader_observed_1"},
    {"addr": 0x08B12ABC, "label": "b8_operation_reader_observed_2"},
    {"addr": 0x08B12B14, "label": "b8_operation_reader_observed_3"},
    {"addr": 0x0300660C, "label": "b8_operation_iwram_reader_observed_1"},
    {"addr": 0x0300660E, "label": "b8_operation_iwram_reader_observed_2"},
]

GROUP_SPECS = [
    {
        "id": "a2_co_power_profile_display_overrides",
        "ranges": [(0xA2955C, 0xA29830)],
        "source": "display_overrides",
    },
    {
        "id": "b84_compact_power_display_overrides",
        "ranges": [(0xB84E50, 0xB84F18)],
        "source": "display_overrides",
    },
    {
        "id": "b8_compact_display_table_all",
        "ranges": [(0xB81800, 0xB85000)],
        "source": "dialogue_groups",
    },
]

BP_RE = re.compile(
    r"^(?P<order>\d+) BP "
    r"r0=(?P<r0>[0-9A-F]{8}) r1=(?P<r1>[0-9A-F]{8}) "
    r"r2=(?P<r2>[0-9A-F]{8}) r3=(?P<r3>[0-9A-F]{8}) "
    r"r4=(?P<r4>[0-9A-F]{8}) r5=(?P<r5>[0-9A-F]{8}) "
    r"r6=(?P<r6>[0-9A-F]{8}) r7=(?P<r7>[0-9A-F]{8}) "
    r"sp=(?P<sp>[0-9A-F]{8}) lr=(?P<lr>[0-9A-F]{8}) pc=(?P<pc>[0-9A-F]{8})$"
)
GENERAL_REGS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7")
ALL_LOGGED_REGS = GENERAL_REGS + ("sp", "lr", "pc")


def load(path: Path) -> dict:
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


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def in_ranges(addr: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= addr < end for start, end in ranges)


def parse_addr(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def build_target_index() -> dict[int, dict]:
    display_overrides = load(DISPLAY_OVERRIDES)
    dialogue_map = load(DIALOGUE_MAP)
    groups_doc = load(DIALOGUE_GROUPS)

    line_by_addr: dict[int, dict] = {}
    for row in dialogue_map.get("lines", []):
        addr = parse_addr(row.get("address"))
        if addr is not None:
            line_by_addr[addr] = row

    targets: dict[int, dict] = {}
    for spec in GROUP_SPECS:
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
            for group in groups_doc.get("groups", []):
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
    return targets


def classify_addr(addr: int, targets: dict[int, dict]) -> dict:
    exact = targets.get(addr)
    if exact:
        return {"target_match": True, **exact}
    for spec in GROUP_SPECS:
        if in_ranges(addr, spec["ranges"]):
            return {
                "target_match": False,
                "group_id": spec["id"],
                "address": f"0x{addr:08X}",
                "reason": "inside_group_range_but_not_exact_target",
            }
    return {"target_match": False, "group_id": None, "address": f"0x{addr:08X}"}


def parse_bp_log(path: Path, targets: dict[int, dict]) -> list[dict]:
    if not path.exists():
        return []
    hits = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = BP_RE.match(line.strip())
        if not match:
            continue
        row = {
            key: int(value, 16) if key != "order" else int(value)
            for key, value in match.groupdict().items()
        }
        row["source"] = classify_addr(row["r0"], targets)
        row["dict"] = classify_addr(row["r1"], targets)
        row["register_matches"] = []
        for reg in ALL_LOGGED_REGS:
            classified = classify_addr(row[reg], targets)
            if classified.get("target_match") or classified.get("group_id"):
                row["register_matches"].append({"register": reg, **classified})
        row["direct_register_hits"] = [
            match for match in row["register_matches"]
            if match["register"] in GENERAL_REGS and match.get("target_match")
        ]
        row["range_register_hits"] = [
            match for match in row["register_matches"]
            if match["register"] in GENERAL_REGS and match.get("group_id") and not match.get("target_match")
        ]
        row["raw"] = line
        hits.append(row)
    return hits


def parse_int_addr(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def code_context_breakpoints(path: Path) -> list[dict]:
    if not path.exists():
        return []
    doc = load(path)
    breakpoints: list[dict] = []
    for row in doc.get("summary", {}).get("breakpoint_candidates", []):
        pc = parse_int_addr(row.get("pc"))
        if pc is not None:
            breakpoints.append({
                "addr": pc,
                "label": f"code_context_ldr_{pc:08X}",
                "source": "compact_display_code_context",
                "source_count": row.get("source_count"),
            })
        fn = parse_int_addr(row.get("function_start"))
        if fn is not None:
            breakpoints.append({
                "addr": fn,
                "label": f"code_context_fn_{fn:08X}",
                "source": "compact_display_code_context",
                "source_count": row.get("source_count"),
            })
    return breakpoints


def build_breakpoints(include_code_context: bool, code_context_path: Path) -> list[dict]:
    out: list[dict] = []
    by_addr: dict[int, dict] = {}
    for bp in BASE_BREAKPOINTS + (code_context_breakpoints(code_context_path) if include_code_context else []):
        addr = bp["addr"]
        if addr in by_addr:
            by_addr[addr].setdefault("aliases", []).append(bp["label"])
            continue
        row = {**bp, "aliases": []}
        by_addr[addr] = row
        out.append(row)
    return out


def setup_breakpoints(driver: MGBADriver, log_path: Path, breakpoints: list[dict]) -> list[dict]:
    responses = []
    for idx, bp in enumerate(breakpoints):
        target = str(log_path) if idx == 0 else "KEEP"
        response = driver.cmd(f"break {bp['addr']:08X} {target}")
        responses.append({**bp, "response": response})
    return responses


def run_screen_checkpoint(name: str, checkpoint: dict, rom: Path, harness: Path, out_dir: Path,
                          breakpoints: list[dict],
                          targets: dict[int, dict]) -> dict:
    case_dir = out_dir / f"screen_{name}"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "breakpoints.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    prov = {
        "case_type": "screen_checkpoint",
        "name": name,
        "mode": checkpoint.get("mode"),
        "scene_id": checkpoint.get("scene_id"),
        "breakpoint_log": rel(log_path),
    }
    try:
        driver.frames(1)
        prov["breakpoints"] = setup_breakpoints(driver, log_path, breakpoints)
        if checkpoint["mode"] == "fresh":
            run_nav(driver, checkpoint["nav"])
            prov["nav"] = checkpoint["nav"]
        elif checkpoint["mode"] == "savestate":
            state_path = resolve(checkpoint["state"])
            driver.loadstate(state_path)
            prov["state"] = rel(state_path)
            prov["state_sha256"] = sha256(state_path)
            refresh = checkpoint.get("refresh", [["frames", 20]])
            run_nav(driver, refresh)
            prov["refresh"] = refresh
        else:
            raise ValueError(f"unknown checkpoint mode: {checkpoint['mode']!r}")
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()
    hits = parse_bp_log(log_path, targets)
    return {
        **prov,
        "frame": rel(case_dir / "frame.png"),
        "hit_count": len(hits),
        "direct_target_hits": [hit for hit in hits if hit["direct_register_hits"]],
        "hits": hits[:200],
        "truncated_hits": max(0, len(hits) - 200),
    }


def run_freshrender_case(name: str, checkpoint: dict, rom: Path, harness: Path, out_dir: Path,
                         breakpoints: list[dict],
                         targets: dict[int, dict]) -> dict:
    case_dir = out_dir / f"freshrender_{name}"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "breakpoints.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    state_path = resolve(checkpoint["state"])
    prov = {
        "case_type": "freshrender",
        "name": name,
        "state": rel(state_path),
        "state_sha256": sha256(state_path),
        "breakpoint_log": rel(log_path),
    }
    try:
        driver.frames(1)
        prov["breakpoints"] = setup_breakpoints(driver, log_path, breakpoints)
        driver.loadstate(state_path)
        driver.frames(int(checkpoint.get("settle", 20)))
        refresh = checkpoint.get("refresh", [])
        run_refresh(driver, refresh)
        prov["refresh"] = refresh
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()
    hits = parse_bp_log(log_path, targets)
    return {
        **prov,
        "frame": rel(case_dir / "frame.png"),
        "hit_count": len(hits),
        "direct_target_hits": [hit for hit in hits if hit["direct_register_hits"]],
        "hits": hits[:200],
        "truncated_hits": max(0, len(hits) - 200),
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--temp-out", default=str(ROOT / "temp" / "compact_renderer_trace_20260627"))
    ap.add_argument("--code-context-json", default=str(CODE_CONTEXT))
    ap.add_argument("--no-code-context-breakpoints", action="store_true",
                    help="Do not include candidates from compact_display_code_context.json.")
    ap.add_argument("--screen-checkpoint", action="append", default=[],
                    help="screen_checkpoints.json name. Defaults to a small E12 probe set.")
    ap.add_argument("--freshrender-name", action="append", default=[],
                    help="freshrender_checkpoints.json name. Defaults to CO profile refresh probes.")
    args = ap.parse_args()

    rom = resolve(args.rom)
    harness = resolve(args.harness)
    out_json = resolve(args.out_json)
    temp_out = resolve(args.temp_out)
    code_context_path = resolve(args.code_context_json)
    if not rom.exists():
        raise SystemExit(f"ROM 없음: {rom}")
    if not harness.exists():
        raise SystemExit(f"mGBA harness 없음: {harness}")
    temp_out.mkdir(parents=True, exist_ok=True)

    targets = build_target_index()
    breakpoints = build_breakpoints(not args.no_code_context_breakpoints, code_context_path)
    screen_by_name = {row["name"]: row for row in load(SCREEN_CHECKPOINTS).get("checkpoints", [])}
    fresh_by_name = {row["name"]: row for row in load(FRESHRENDER_CHECKPOINTS).get("checkpoints", [])}
    screen_names = args.screen_checkpoint or DEFAULT_SCREEN_CHECKPOINTS
    freshrender_names = args.freshrender_name or DEFAULT_FRESHRENDER

    cases = []
    for name in screen_names:
        if name not in screen_by_name:
            raise SystemExit(f"screen checkpoint 없음: {name}")
        print(f"[trace] screen {name}")
        cases.append(run_screen_checkpoint(name, screen_by_name[name], rom, harness, temp_out, breakpoints, targets))
    for name in freshrender_names:
        if name not in fresh_by_name:
            raise SystemExit(f"freshrender checkpoint 없음: {name}")
        print(f"[trace] freshrender {name}")
        cases.append(run_freshrender_case(name, fresh_by_name[name], rom, harness, temp_out, breakpoints, targets))

    direct_hits = []
    for case in cases:
        for hit in case["direct_target_hits"]:
            direct_hits.append({
                "case": case["name"],
                "case_type": case["case_type"],
                "frame": case["frame"],
                "breakpoint_log": case["breakpoint_log"],
                "hit": hit,
            })

    report = {
        "tool": "tools/trace_compact_renderer.py",
        "rom": rel(rom),
        "rom_sha256": sha256(rom),
        "git_commit": git_commit(),
        "breakpoints": breakpoints,
        "code_context_json": rel(code_context_path) if code_context_path.exists() else None,
        "code_context_breakpoints_enabled": not args.no_code_context_breakpoints,
        "target_count": len(targets),
        "case_count": len(cases),
        "hit_count": sum(case["hit_count"] for case in cases),
        "direct_target_hit_count": len(direct_hits),
        "direct_hits": direct_hits,
        "cases": cases,
        "strict_note": (
            "Only direct_target_hits count as E12 visual provenance. A zero-hit case "
            "is a route/function-candidate negative result, not proof that the table "
            "is globally unused. direct_target_hits require an exact compact target "
            "address in r0-r7; range_register_hits are investigation leads only."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "out_json": rel(out_json),
        "case_count": report["case_count"],
        "hit_count": report["hit_count"],
        "direct_target_hit_count": report["direct_target_hit_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
