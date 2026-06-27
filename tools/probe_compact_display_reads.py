#!/usr/bin/env python3
"""Probe compact display table reads with mGBA watchaddr.

This is intentionally separate from trace_compact_renderer.py. Breakpoint traces
test candidate renderer PCs; this helper tests whether selected compact display
source ranges are actually read while driving known routes. Watchpoint results
are runtime provenance leads, not final visual proof by themselves.
"""
from __future__ import annotations

import argparse
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
from trace_compact_renderer import (  # noqa: E402
    DISPLAY_OVERRIDES,
    DIALOGUE_GROUPS,
    FRESHRENDER_CHECKPOINTS,
    GROUP_SPECS,
    HARNESS,
    OUT_JSON as TRACE_JSON,
    ROM,
    SCREEN_CHECKPOINTS,
    build_target_index,
    load,
    rel,
    resolve,
    sha256,
)

OUT_JSON = ROOT / "data" / "compact_display_read_watch_probe.json"
WATCH_RE = re.compile(
    r"^(?P<order>\d+) addr=(?P<addr>[0-9A-Fa-f]{8}) "
    r"pc=(?P<pc>[0-9A-Fa-f]{8}) lr=(?P<lr>[0-9A-Fa-f]{8}) "
    r"r0=(?P<r0>[0-9A-Fa-f]{8}) r1=(?P<r1>[0-9A-Fa-f]{8}) "
    r"old=(?P<old>[0-9A-Fa-f]{8}) new=(?P<new>[0-9A-Fa-f]{8})$"
)

GROUP_ALIASES = {
    "a2": "a2_co_power_profile_display_overrides",
    "b84": "b84_compact_power_display_overrides",
    "b8": "b8_compact_display_table_all",
}


def gba_rom_addr(offset: int) -> int:
    return 0x08000000 | offset


def rom_offset(addr: int) -> int:
    if 0x08000000 <= addr < 0x0A000000:
        return addr - 0x08000000
    return addr


def parse_offset(value: str) -> int:
    raw = value.strip()
    if raw.lower().startswith("0x"):
        addr = int(raw, 16)
    else:
        addr = int(raw, 16)
    return rom_offset(addr)


def group_specs_by_id() -> dict[str, dict]:
    return {spec["id"]: spec for spec in GROUP_SPECS}


def normalize_group_ids(values: list[str]) -> list[str]:
    specs = group_specs_by_id()
    out: list[str] = []
    for value in values:
        gid = GROUP_ALIASES.get(value, value)
        if gid not in specs:
            known = ", ".join(sorted(GROUP_ALIASES) + sorted(specs))
            raise SystemExit(f"unknown group {value!r}; known: {known}")
        if gid not in out:
            out.append(gid)
    return out


def build_target_spans(targets: dict[int, dict]) -> dict[str, list[dict]]:
    spans: dict[str, list[dict]] = {}
    for spec in GROUP_SPECS:
        gid = spec["id"]
        group_targets = sorted(addr for addr, row in targets.items() if row.get("group_id") == gid)
        group_spans: list[dict] = []
        for start_range, end_range in spec["ranges"]:
            starts = [addr for addr in group_targets if start_range <= addr < end_range]
            for idx, start in enumerate(starts):
                next_start = starts[idx + 1] if idx + 1 < len(starts) else end_range
                group_spans.append({
                    "group_id": gid,
                    "start": start,
                    "end": next_start,
                    "target": targets[start],
                })
        spans[gid] = group_spans
    return spans


def classify_watch_addr(addr: int, targets: dict[int, dict], spans: dict[str, list[dict]]) -> dict:
    off = rom_offset(addr)
    if off in targets:
        return {
            "kind": "target_start",
            "target_span_match": True,
            "read_address": f"0x{addr:08X}",
            "read_offset": f"0x{off:08X}",
            "target_start": f"0x{off:08X}",
            **targets[off],
        }
    for group_spans in spans.values():
        for span in group_spans:
            if span["start"] <= off < span["end"]:
                return {
                    "kind": "target_span",
                    "target_span_match": True,
                    "read_address": f"0x{addr:08X}",
                    "read_offset": f"0x{off:08X}",
                    "target_start": f"0x{span['start']:08X}",
                    "span_end": f"0x{span['end']:08X}",
                    **span["target"],
                }
    for spec in GROUP_SPECS:
        for start, end in spec["ranges"]:
            if start <= off < end:
                return {
                    "kind": "group_range_only",
                    "target_span_match": False,
                    "read_address": f"0x{addr:08X}",
                    "read_offset": f"0x{off:08X}",
                    "group_id": spec["id"],
                    "range": [f"0x{start:08X}", f"0x{end:08X}"],
                }
    return {
        "kind": "outside_groups",
        "target_span_match": False,
        "read_address": f"0x{addr:08X}",
        "read_offset": f"0x{off:08X}",
        "group_id": None,
    }


def parse_watch_log(path: Path, targets: dict[int, dict], spans: dict[str, list[dict]]) -> list[dict]:
    if not path.exists():
        return []
    hits: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = WATCH_RE.match(line.strip())
        if not match:
            continue
        row = {
            key: int(value, 16) if key != "order" else int(value)
            for key, value in match.groupdict().items()
        }
        row["source"] = classify_watch_addr(row["addr"], targets, spans)
        row["raw"] = line
        hits.append(row)
    return hits


def setup_watch_ranges(driver: MGBADriver, group_ids: list[str], log_path: Path) -> list[dict]:
    responses: list[dict] = []
    first = True
    specs = group_specs_by_id()
    for gid in group_ids:
        for start, end in specs[gid]["ranges"]:
            response = driver.cmd(
                f"watchaddr {gba_rom_addr(start):08X} {end - start} r {log_path if first else 'KEEP'}"
            )
            responses.append({
                "group_id": gid,
                "start": f"0x{start:08X}",
                "end": f"0x{end:08X}",
                "gba_start": f"0x{gba_rom_addr(start):08X}",
                "size": end - start,
                "response": response,
            })
            first = False
    return responses


def setup_exact_watches(driver: MGBADriver, offsets: list[int], log_path: Path, size: int) -> list[dict]:
    responses: list[dict] = []
    for idx, offset in enumerate(offsets):
        response = driver.cmd(
            f"watchaddr {gba_rom_addr(offset):08X} {size} r {log_path if idx == 0 else 'KEEP'}"
        )
        responses.append({
            "offset": f"0x{offset:08X}",
            "gba_start": f"0x{gba_rom_addr(offset):08X}",
            "size": size,
            "response": response,
        })
    return responses


def setup_watches(
    driver: MGBADriver,
    group_ids: list[str],
    target_offsets: list[int],
    exact_size: int,
    log_path: Path,
) -> tuple[str, list[dict]]:
    if target_offsets:
        return "exact_targets", setup_exact_watches(driver, target_offsets, log_path, exact_size)
    return "ranges", setup_watch_ranges(driver, group_ids, log_path)


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_.-]+", "__", value).strip("_")[:180] or "state"


def parse_state_steps(values: list[str]) -> list[list]:
    steps: list[list] = []
    for value in values:
        parts = value.split(":")
        op = parts[0]
        if op == "frames" and len(parts) == 2:
            steps.append(["frames", int(parts[1])])
        elif op == "press" and len(parts) in (2, 3, 4):
            step: list = ["press", parts[1]]
            if len(parts) >= 3:
                step.append(int(parts[2]))
            if len(parts) == 4:
                step.append(int(parts[3]))
            steps.append(step)
        else:
            raise SystemExit(
                f"bad --state-step {value!r}; use frames:N or press:KEY[:after[:hold]]"
            )
    return steps


def summarize_hits(hits: list[dict]) -> dict:
    by_group: dict[str, int] = {}
    by_pc: dict[str, int] = {}
    direct_by_target: dict[str, int] = {}
    for hit in hits:
        source = hit["source"]
        gid = source.get("group_id") or "unknown"
        by_group[gid] = by_group.get(gid, 0) + 1
        pc = f"0x{hit['pc']:08X}"
        by_pc[pc] = by_pc.get(pc, 0) + 1
        if source.get("target_span_match"):
            target = source.get("target_start") or source.get("address") or source["read_offset"]
            direct_by_target[target] = direct_by_target.get(target, 0) + 1
    return {
        "hit_count": len(hits),
        "direct_target_read_count": sum(direct_by_target.values()),
        "direct_target_count": len(direct_by_target),
        "by_group": dict(sorted(by_group.items())),
        "top_pcs": [
            {"pc": pc, "count": count}
            for pc, count in sorted(by_pc.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
        "direct_targets": [
            {"target_start": target, "count": count}
            for target, count in sorted(direct_by_target.items())
        ],
    }


def run_state_case(
    state: Path,
    rom: Path,
    harness: Path,
    out_dir: Path,
    group_ids: list[str],
    target_offsets: list[int],
    exact_size: int,
    state_frames: int,
    state_steps: list[list],
    targets: dict[int, dict],
    spans: dict[str, list[dict]],
) -> dict:
    case_dir = out_dir / f"state_{safe_name(rel(state) or state.name)}"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "watch.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    prov = {
        "case_type": "state",
        "name": rel(state),
        "mode": "savestate",
        "state": rel(state),
        "state_sha256": sha256(state),
        "watch_log": rel(log_path),
        "watchpoint_caveat": (
            "savestate watchpoints are useful leads but can false-negative; prefer fresh routes for closure"
        ),
        "state_frames": state_frames,
        "state_steps": state_steps,
    }
    try:
        driver.frames(1)
        driver.loadstate(state)
        driver.frames(1)
        prov["watch_mode"], prov["watches"] = setup_watches(
            driver, group_ids, target_offsets, exact_size, log_path
        )
        if state_steps:
            run_nav(driver, state_steps)
        else:
            driver.frames(state_frames)
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()
    hits = parse_watch_log(log_path, targets, spans)
    return {
        **prov,
        "frame": rel(case_dir / "frame.png"),
        "summary": summarize_hits(hits),
        "hits": hits[:200],
        "truncated_hits": max(0, len(hits) - 200),
    }


def run_screen_case(
    name: str,
    checkpoint: dict,
    rom: Path,
    harness: Path,
    out_dir: Path,
    group_ids: list[str],
    target_offsets: list[int],
    exact_size: int,
    screen_steps: list[list],
    targets: dict[int, dict],
    spans: dict[str, list[dict]],
) -> dict:
    case_dir = out_dir / f"screen_{name}"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "watch.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    prov = {
        "case_type": "screen_checkpoint",
        "name": name,
        "mode": checkpoint.get("mode"),
        "scene_id": checkpoint.get("scene_id"),
        "watch_log": rel(log_path),
        "watchpoint_caveat": None,
        "screen_steps": screen_steps,
    }
    try:
        driver.frames(1)
        if checkpoint["mode"] == "fresh":
            prov["watch_mode"], prov["watches"] = setup_watches(
                driver, group_ids, target_offsets, exact_size, log_path
            )
            run_nav(driver, checkpoint["nav"])
            prov["nav"] = checkpoint["nav"]
            if screen_steps:
                run_nav(driver, screen_steps)
        elif checkpoint["mode"] == "savestate":
            state_path = resolve(checkpoint["state"])
            driver.loadstate(state_path)
            driver.frames(1)
            prov["watch_mode"], prov["watches"] = setup_watches(
                driver, group_ids, target_offsets, exact_size, log_path
            )
            prov["state"] = rel(state_path)
            prov["state_sha256"] = sha256(state_path)
            prov["watchpoint_caveat"] = (
                "savestate watchpoints are useful leads but can false-negative; prefer fresh routes for closure"
            )
            refresh = checkpoint.get("refresh", [["frames", 20]])
            run_nav(driver, refresh)
            prov["refresh"] = refresh
            if screen_steps:
                run_nav(driver, screen_steps)
        else:
            raise ValueError(f"unknown checkpoint mode: {checkpoint['mode']!r}")
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()
    hits = parse_watch_log(log_path, targets, spans)
    return {
        **prov,
        "frame": rel(case_dir / "frame.png"),
        "summary": summarize_hits(hits),
        "hits": hits[:200],
        "truncated_hits": max(0, len(hits) - 200),
    }


def run_freshrender_case(
    name: str,
    checkpoint: dict,
    rom: Path,
    harness: Path,
    out_dir: Path,
    group_ids: list[str],
    target_offsets: list[int],
    exact_size: int,
    targets: dict[int, dict],
    spans: dict[str, list[dict]],
) -> dict:
    case_dir = out_dir / f"freshrender_{name}"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "watch.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    state_path = resolve(checkpoint["state"])
    prov = {
        "case_type": "freshrender",
        "name": name,
        "state": rel(state_path),
        "state_sha256": sha256(state_path),
        "watch_log": rel(log_path),
        "watchpoint_caveat": (
            "savestate watchpoints are useful leads but can false-negative; prefer fresh routes for closure"
        ),
    }
    try:
        driver.frames(1)
        driver.loadstate(state_path)
        driver.frames(int(checkpoint.get("settle", 20)))
        prov["watch_mode"], prov["watches"] = setup_watches(
            driver, group_ids, target_offsets, exact_size, log_path
        )
        refresh = checkpoint.get("refresh", [])
        run_refresh(driver, refresh)
        prov["refresh"] = refresh
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()
    hits = parse_watch_log(log_path, targets, spans)
    return {
        **prov,
        "frame": rel(case_dir / "frame.png"),
        "summary": summarize_hits(hits),
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
    ap.add_argument("--temp-out", default=str(ROOT / "temp" / "compact_display_read_watch_20260627"))
    ap.add_argument("--group", action="append", default=None,
                    help="Group alias or id to watch. Defaults to a2 and b84; add --group b8 explicitly.")
    ap.add_argument("--target-address", action="append", default=[],
                    help="Exact ROM/GBA address to watch instead of whole group ranges. Repeatable.")
    ap.add_argument("--exact-size", type=int, default=4,
                    help="Read-watch size for --target-address entries. Default: 4 bytes.")
    ap.add_argument("--screen-checkpoint", action="append", default=None,
                    help="screen_checkpoints.json name. Default is the fresh Part2 main menu route.")
    ap.add_argument("--no-default-screen", action="store_true",
                    help="Do not add the default fresh Part2 main menu route when no --screen-checkpoint is given.")
    ap.add_argument("--freshrender-name", action="append", default=[],
                    help="freshrender_checkpoints.json name. Empty by default because these start from savestate.")
    ap.add_argument("--state", action="append", default=[],
                    help="Raw savestate path to load and watch for --state-frames frames.")
    ap.add_argument("--state-frames", type=int, default=20,
                    help="Frames to run after installing watches for --state cases. Default: 20.")
    ap.add_argument("--state-step", action="append", default=[],
                    help="Refresh step for --state cases: frames:N or press:KEY[:after[:hold]]. Repeatable.")
    ap.add_argument("--screen-step", action="append", default=[],
                    help="Extra step after each --screen-checkpoint route: frames:N or press:KEY[:after[:hold]]. Repeatable.")
    args = ap.parse_args()

    rom = resolve(args.rom)
    harness = resolve(args.harness)
    out_json = resolve(args.out_json)
    temp_out = resolve(args.temp_out)
    if not rom.exists():
        raise SystemExit(f"ROM 없음: {rom}")
    if not harness.exists():
        raise SystemExit(f"mGBA harness 없음: {harness}")
    temp_out.mkdir(parents=True, exist_ok=True)

    group_ids = normalize_group_ids(args.group or ["a2", "b84"])
    target_offsets = sorted({parse_offset(value) for value in args.target_address})
    state_steps = parse_state_steps(args.state_step)
    screen_steps = parse_state_steps(args.screen_step)
    targets = build_target_index()
    spans = build_target_spans(targets)
    screen_by_name = {row["name"]: row for row in load(SCREEN_CHECKPOINTS).get("checkpoints", [])}
    fresh_by_name = {row["name"]: row for row in load(FRESHRENDER_CHECKPOINTS).get("checkpoints", [])}

    cases = []
    screen_names = args.screen_checkpoint or ([] if args.no_default_screen else ["07_part2_main_menu"])
    for name in screen_names:
        if name not in screen_by_name:
            raise SystemExit(f"screen checkpoint 없음: {name}")
        print(f"[read-watch] screen {name}")
        cases.append(run_screen_case(
            name, screen_by_name[name], rom, harness, temp_out,
            group_ids, target_offsets, args.exact_size, screen_steps, targets, spans,
        ))
    for name in args.freshrender_name:
        if name not in fresh_by_name:
            raise SystemExit(f"freshrender checkpoint 없음: {name}")
        print(f"[read-watch] freshrender {name}")
        cases.append(run_freshrender_case(
            name, fresh_by_name[name], rom, harness, temp_out,
            group_ids, target_offsets, args.exact_size, targets, spans,
        ))
    for state_arg in args.state:
        state = resolve(state_arg)
        if not state.exists():
            raise SystemExit(f"state 없음: {state}")
        print(f"[read-watch] state {rel(state)}")
        cases.append(run_state_case(
            state, rom, harness, temp_out, group_ids, target_offsets,
            args.exact_size, args.state_frames, state_steps, targets, spans,
        ))

    direct_hits = []
    for case in cases:
        for hit in case["hits"]:
            if hit["source"].get("target_span_match"):
                direct_hits.append({
                    "case": case["name"],
                    "case_type": case["case_type"],
                    "frame": case["frame"],
                    "watch_log": case["watch_log"],
                    "hit": hit,
                })

    report = {
        "tool": "tools/probe_compact_display_reads.py",
        "rom": rel(rom),
        "rom_sha256": sha256(rom),
        "git_commit": git_commit(),
        "selected_groups": group_ids,
        "selected_target_addresses": [f"0x{addr:08X}" for addr in target_offsets],
        "source_files": {
            "display_overrides": rel(DISPLAY_OVERRIDES),
            "dialogue_groups": rel(DIALOGUE_GROUPS),
            "renderer_trace": rel(TRACE_JSON),
        },
        "case_count": len(cases),
        "hit_count": sum(case["summary"]["hit_count"] for case in cases),
        "direct_target_read_count": len(direct_hits),
        "direct_hits": direct_hits[:200],
        "truncated_direct_hits": max(0, len(direct_hits) - 200),
        "cases": cases,
        "strict_note": (
            "Read-watch hits prove runtime reads of compact source spans on that route. "
            "They are stronger than static xrefs but still not a replacement for final "
            "pixel-level visual confirmation. Savestate watchpoint misses can be false negatives."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "out_json": rel(out_json),
        "selected_groups": group_ids,
        "selected_target_addresses": [f"0x{addr:08X}" for addr in target_offsets],
        "case_count": report["case_count"],
        "hit_count": report["hit_count"],
        "direct_target_read_count": report["direct_target_read_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
