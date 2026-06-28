#!/usr/bin/env python3
"""Probe all A2 CO profile power-name reads via the live CO-id field.

The Part 2 CO profile renderer at 0x08385E30 selects power names with:

  record = *(0x08814FD0) + object[0x66] * 60
  co_id = record[0x1d]
  index1 = *(0x089FC418 + co_id * 260 + 0x7c)
  index2 = *(0x089FC418 + co_id * 260 + 0xc0)
  text = *(0x08A357B4 + index * 4)

This probe does not claim a natural route through every CO. It proves that the
current visible A2 CO profile screen reads each Korean power-name target when
the live co_id byte in the selected profile record is patched before redraw.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from probe_compact_display_reads import (  # noqa: E402
    build_target_index,
    build_target_spans,
    parse_watch_log,
    rel,
    setup_exact_watches,
    sha256,
    summarize_hits,
)
from qa_visual_regions import MGBADriver  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path("/tmp/mgbah")
STATE = ROOT / "temp" / "scene_entrypoints" / "part2_menu_sweep" / "state_036.ss0"
TEMP_OUT = ROOT / "temp" / "e12_a2_profile_coid_read_watch_current"
OUT_JSON = ROOT / "data" / "compact_display_read_watch_a2_profile_coid_current.json"
CONTACT = ROOT / "docs" / "screenshots" / "e12_a2_profile_coid_read_watch_2026-06-28" / "contact.png"

GROUP_ID = "a2_co_power_profile_display_overrides"
RENDER_BREAK = 0x08385E9E
CO_DATA_TABLE = 0x089FC418
TEXT_POINTER_TABLE = 0x08A357B4
CO_RECORD_SIZE = 60
CO_ID_OFFSET = 0x1D
CORE_RENDER_PCS = {0x0838BD18, 0x0838BCE4}
MIN_TARGET_HITS = 8
MIN_CORE_RENDER_HITS = 4
CO_ID_VALUES = [
    0x00,
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x08,
    0x09,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
]

BP_RE = re.compile(
    r"BP r0=(?P<r0>[0-9A-Fa-f]{8}) r1=(?P<r1>[0-9A-Fa-f]{8}) "
    r"r2=(?P<r2>[0-9A-Fa-f]{8}) r3=(?P<r3>[0-9A-Fa-f]{8}) "
    r"r4=(?P<r4>[0-9A-Fa-f]{8}) r5=(?P<r5>[0-9A-Fa-f]{8}) "
    r"r6=(?P<r6>[0-9A-Fa-f]{8}) r7=(?P<r7>[0-9A-Fa-f]{8}).*"
    r"lr=(?P<lr>[0-9A-Fa-f]{8}) pc=(?P<pc>[0-9A-Fa-f]{8})"
)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def target_offsets() -> list[int]:
    targets = build_target_index()
    return sorted(addr for addr, row in targets.items() if row.get("group_id") == GROUP_ID)


def verify_selected_record(rom: Path, harness: Path, state: Path, out_dir: Path) -> dict:
    case_dir = out_dir / "_record_break"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "break.log"
    if log_path.exists():
        log_path.unlink()
    driver = MGBADriver(rom, case_dir, harness)
    try:
        driver.loadstate(state)
        driver.cmd(f"break {RENDER_BREAK:08X} {log_path}")
        driver.press("DOWN", after=60)
        driver.press("DOWN", after=60)
        driver.frames(20)
        driver.shot("frame").save(case_dir / "frame.png")
    finally:
        driver.close()

    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = BP_RE.search(text)
    if not match:
        raise RuntimeError(f"record breakpoint did not hit: {log_path}")
    regs = {key: int(value, 16) for key, value in match.groupdict().items()}
    record_addr = regs["r0"]
    selected_record = regs["r1"]
    record_table = regs["r4"]
    expected_record = record_table + selected_record * CO_RECORD_SIZE
    if record_addr != expected_record:
        raise RuntimeError(
            f"unexpected record address: r0=0x{record_addr:08X}, "
            f"r4+r1*60=0x{expected_record:08X}"
        )
    if regs["r3"] != CO_DATA_TABLE:
        raise RuntimeError(f"unexpected CO data table: r3=0x{regs['r3']:08X}")
    if regs["r5"] != TEXT_POINTER_TABLE:
        raise RuntimeError(f"unexpected text pointer table: r5=0x{regs['r5']:08X}")
    return {
        "breakpoint_address": f"0x{RENDER_BREAK:08X}",
        "breakpoint_log": rel(log_path),
        "breakpoint_frame": rel(case_dir / "frame.png"),
        "selected_record": selected_record,
        "record_table": f"0x{record_table:08X}",
        "record_address": f"0x{record_addr:08X}",
        "co_id_patch_address": f"0x{record_addr + CO_ID_OFFSET:08X}",
        "profile_object": f"0x{regs['r6']:08X}",
        "status_pointer": f"0x{regs['r7']:08X}",
        "co_data_table": f"0x{regs['r3']:08X}",
        "text_pointer_table": f"0x{regs['r5']:08X}",
        "lr": f"0x{regs['lr']:08X}",
        "pc_after_break": f"0x{regs['pc']:08X}",
    }


def run_case(
    co_id: int,
    co_id_addr: int,
    rom: Path,
    harness: Path,
    state: Path,
    out_dir: Path,
    targets: dict[int, dict],
    spans: dict[str, list[dict]],
    offsets: list[int],
) -> dict:
    case_dir = out_dir / f"co{co_id:02X}_p2"
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "watch.log"
    if log_path.exists():
        log_path.unlink()

    state_steps = [["press", "DOWN", 60], ["press", "DOWN", 60], ["press", "DOWN", 60]]
    driver = MGBADriver(rom, case_dir, harness)
    try:
        driver.loadstate(state)
        patch_response = driver.cmd(f"w8 {co_id_addr:08X} {co_id:02x}")
        watch_responses = setup_exact_watches(driver, offsets, log_path, 4)
        for _ in range(3):
            driver.press("DOWN", after=60)
        driver.frames(20)
        image = driver.shot("frame")
        image.save(case_dir / "frame.png")
    finally:
        driver.close()

    hits = parse_watch_log(log_path, targets, spans)
    return {
        "name": f"co{co_id:02X}_p2",
        "case_type": "state_ram_patch",
        "mode": "a2_profile_selected_record_co_id_power_rows",
        "state": rel(state),
        "state_sha256": sha256(state),
        "ram_patch": {
            "address": f"0x{co_id_addr:08X}",
            "field": "selected_profile_record.co_id",
            "value": f"0x{co_id:02X}",
            "response": patch_response,
        },
        "state_steps": state_steps,
        "watch_mode": "exact_targets",
        "watches": watch_responses,
        "watch_log": rel(log_path),
        "frame": rel(case_dir / "frame.png"),
        "watchpoint_caveat": (
            "RAM co_id field proof: the selected profile record's co_id byte is patched "
            "before redraw. This is target source provenance, not natural all-CO route "
            "coverage or final pixel QA."
        ),
        "summary": summarize_hits(hits),
        "hits": hits[:80],
        "truncated_hits": max(0, len(hits) - 80),
    }


def aggregate_summary(cases: list[dict]) -> dict:
    counts: dict[str, int] = {}
    hit_count = 0
    direct_count = 0
    for case in cases:
        summary = case["summary"]
        hit_count += summary["hit_count"]
        direct_count += summary["direct_target_read_count"]
        for row in summary["direct_targets"]:
            target = row["target_start"]
            counts[target] = counts.get(target, 0) + row["count"]
    return {
        "hit_count": hit_count,
        "direct_target_read_count": direct_count,
        "direct_target_count": len(counts),
        "direct_targets": [
            {"target_start": target, "count": counts[target]} for target in sorted(counts)
        ],
    }


def target_hit_validation(cases: list[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for case in cases:
        for hit in case["hits"]:
            source = hit.get("source") or {}
            if not source.get("target_span_match"):
                continue
            target = source.get("target_start")
            if not target:
                continue
            row = stats.setdefault(target, {
                "target_start": target,
                "hit_count": 0,
                "core_render_pc_hit_count": 0,
                "pcs": {},
                "cases": set(),
            })
            row["hit_count"] += 1
            if hit.get("pc") in CORE_RENDER_PCS:
                row["core_render_pc_hit_count"] += 1
            pc = f"0x{hit.get('pc', 0):08X}"
            row["pcs"][pc] = row["pcs"].get(pc, 0) + 1
            row["cases"].add(case["name"])

    out = {}
    for target, row in stats.items():
        out[target] = {
            "target_start": target,
            "hit_count": row["hit_count"],
            "core_render_pc_hit_count": row["core_render_pc_hit_count"],
            "cases": sorted(row["cases"]),
            "top_pcs": [
                {"pc": pc, "count": count}
                for pc, count in sorted(row["pcs"].items(), key=lambda item: (-item[1], item[0]))[:8]
            ],
            "passed": (
                row["hit_count"] >= MIN_TARGET_HITS
                and row["core_render_pc_hit_count"] >= MIN_CORE_RENDER_HITS
            ),
        }
    return out


def representative_direct_hits(cases: list[dict], validation: dict[str, dict]) -> list[dict]:
    reps: dict[str, dict] = {}
    for case in cases:
        for hit in case["hits"]:
            source = hit.get("source") or {}
            if not source.get("target_span_match"):
                continue
            target = source.get("target_start")
            if not target or not validation.get(target, {}).get("passed"):
                continue
            prefer = hit.get("pc") in CORE_RENDER_PCS
            if target in reps and not prefer:
                continue
            reps[target] = {
                "case": case["name"],
                "case_type": case["case_type"],
                "frame": case["frame"],
                "watch_log": case["watch_log"],
                "hit": hit,
                "validation": validation[target],
            }
    return [reps[target] for target in sorted(reps)]


def write_contact_sheet(cases: list[dict], contact: Path) -> None:
    images: list[tuple[str, Image.Image]] = []
    for case in cases:
        frame = ROOT / case["frame"]
        if frame.exists():
            labels = ",".join(row["target_start"][-6:] for row in case["summary"]["direct_targets"])
            images.append((f"{case['name']} {labels}", Image.open(frame).convert("RGB")))
    if not images:
        return
    w, h = images[0][1].size
    cols = 3
    rows = (len(images) + cols - 1) // cols
    label_h = 16
    pad = 6
    sheet = Image.new("RGB", (cols * (w + pad) + pad, rows * (h + label_h + pad) + pad), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(images):
        x = pad + (idx % cols) * (w + pad)
        y = pad + (idx // cols) * (h + label_h + pad)
        draw.text((x, y), label, fill=(255, 255, 160))
        sheet.paste(image, (x, y + label_h))
    contact.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--state", default=str(STATE))
    ap.add_argument("--temp-out", default=str(TEMP_OUT))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--contact", default=str(CONTACT))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    rom = Path(args.rom).resolve()
    harness = Path(args.harness).resolve()
    state = Path(args.state).resolve()
    temp_out = Path(args.temp_out).resolve()
    out_json = Path(args.out_json).resolve()
    contact = Path(args.contact).resolve()
    if not rom.exists():
        raise SystemExit(f"ROM not found: {rom}")
    if not harness.exists():
        raise SystemExit(f"mGBA harness not found: {harness}")
    if not state.exists():
        raise SystemExit(f"state not found: {state}")
    temp_out.mkdir(parents=True, exist_ok=True)

    targets = build_target_index()
    spans = build_target_spans(targets)
    offsets = target_offsets()
    selector = verify_selected_record(rom, harness, state, temp_out)
    co_id_addr = int(selector["co_id_patch_address"], 16)

    cases = []
    for co_id in CO_ID_VALUES:
        print(f"[a2-coid] co_id=0x{co_id:02X}")
        cases.append(run_case(co_id, co_id_addr, rom, harness, state, temp_out, targets, spans, offsets))

    summary = aggregate_summary(cases)
    validation = target_hit_validation(cases)
    direct_hits = representative_direct_hits(cases, validation)
    expected = {f"0x{addr:08X}" for addr in offsets}
    observed = {row["hit"]["source"]["target_start"] for row in direct_hits}
    missing = sorted(expected - observed)
    invalid = sorted(
        target for target in expected
        if target in validation and not validation[target]["passed"]
    )
    write_contact_sheet(cases, contact)

    report = {
        "tool": "tools/probe_a2_profile_coid_power_reads.py",
        "proof_mode": "synthetic_ram_field_read_watch",
        "synthetic_ram_field_source_proof": True,
        "rom": rel(rom),
        "rom_sha256": sha256(rom),
        "git_commit": git_commit(),
        "selected_groups": [GROUP_ID],
        "selected_target_addresses": [f"0x{addr:08X}" for addr in offsets],
        "selector_probe": {
            **selector,
            "state": rel(state),
            "formula": (
                "record=*(0x08814FD0)+object[0x66]*60; co_id=record[0x1d]; "
                "index1=*(0x089FC418+co_id*260+0x7c); "
                "index2=*(0x089FC418+co_id*260+0xc0); "
                "text=*(0x08A357B4+index*4)"
            ),
            "co_id_values": [f"0x{value:02X}" for value in CO_ID_VALUES],
        },
        "case_count": len(cases),
        "hit_count": summary["hit_count"],
        "direct_target_read_count": summary["direct_target_read_count"],
        "summary": summary,
        "validation_policy": {
            "min_target_hits": MIN_TARGET_HITS,
            "min_core_render_pc_hits": MIN_CORE_RENDER_HITS,
            "core_render_pcs": [f"0x{pc:08X}" for pc in sorted(CORE_RENDER_PCS)],
            "note": (
                "Representative direct_hits are emitted only when a target has repeated "
                "reads and core string-loop PC hits, reducing stray read/read-ahead "
                "false positives."
            ),
        },
        "target_hit_validation": [validation[target] for target in sorted(validation)],
        "direct_hits": direct_hits,
        "missing_direct_targets": missing,
        "invalid_direct_targets": invalid,
        "contact_sheet": rel(contact),
        "cases": cases,
        "strict_note": (
            "A2 CO profile selected-record co_id proof. This is synthetic RAM-field "
            "source provenance: the probe dynamically identifies the selected record "
            "for state_036, patches its co_id byte before redraw, and verifies repeated "
            "core-renderer reads of all 36 A2 compact power-name targets. It is stronger "
            "than a static xref but not natural all-CO route coverage or final pixel-level "
            "visual QA."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "out_json": rel(out_json),
        "case_count": report["case_count"],
        "direct_target_count": summary["direct_target_count"],
        "missing_direct_targets": missing,
        "invalid_direct_targets": invalid,
        "contact_sheet": rel(contact),
    }, ensure_ascii=False, indent=2))
    return 1 if missing or invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
