#!/usr/bin/env python3
"""Runtime read-watch probe for Part 1 compact help text.

This is an evidence helper, not a release gate.  It drives the current ROM in
mGBA, watches the Part 1 DFAxxx help-text area, and records which help groups
are read while menu selections change.  A positive hit is useful route evidence
because the screenshot is captured immediately after the watched input step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import qa_text_fit as QTF  # noqa: E402
from build_comparison_sheet import run_nav  # noqa: E402
from build_korean_full import ADDRESS_TEXT_OVERRIDES  # noqa: E402
from qa_visual_regions import MGBADriver, drive_part1_menu_from_coldboot  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path(os.environ.get("MGBA_HARNESS", "/tmp/mgbah"))
OUT_JSON = ROOT / "temp" / "part1_compact_help_read_watch.json"

HELP_START = 0x00DFA64A
HELP_END = 0x00DFA9E9
WATCH_START = 0x00DFA5E0
WATCH_END = 0x00DFAB40
POINTER_TABLE_START = 0x00DFAAB8
POINTER_TABLE_END = 0x00DFAB3C

KEYS = {"A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L"}
WATCH_RE = re.compile(
    r"^(?P<order>\d+) addr=(?P<addr>[0-9A-Fa-f]{8}) "
    r"pc=(?P<pc>[0-9A-Fa-f]{8}) lr=(?P<lr>[0-9A-Fa-f]{8}) "
    r"r0=(?P<r0>[0-9A-Fa-f]{8}) r1=(?P<r1>[0-9A-Fa-f]{8}) "
    r"old=(?P<old>[0-9A-Fa-f]{8}) new=(?P<new>[0-9A-Fa-f]{8})$"
)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gba_addr(offset: int) -> int:
    return 0x08000000 | offset


def rom_offset(addr: int) -> int:
    if 0x08000000 <= addr < 0x0A000000:
        return addr - 0x08000000
    return addr


def parse_steps(values: list[str]) -> list[list]:
    steps: list[list] = []
    for value in values:
        parts = value.split(":")
        op = parts[0]
        if op == "frames" and len(parts) == 2:
            steps.append(["frames", int(parts[1])])
        elif op == "press" and len(parts) in (2, 3, 4):
            key = parts[1].upper()
            if key not in KEYS:
                raise SystemExit(f"unknown key in step {value!r}")
            step: list = ["press", key]
            if len(parts) >= 3:
                step.append(int(parts[2]))
            if len(parts) == 4:
                step.append(int(parts[3]))
            steps.append(step)
        elif op == "part1_menu" and len(parts) == 1:
            steps.append(["part1_menu"])
        else:
            raise SystemExit(f"bad step {value!r}; use frames:N, press:KEY[:after[:hold]], or part1_menu")
    return steps


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_")[:140] or "case"


def load_groups() -> list[dict]:
    slots, _found = QTF.load_found()
    groups_json = json.loads((ROOT / "data" / "dialogue_groups.json").read_text(encoding="utf-8"))
    override_targets = {
        addr
        for addr in ADDRESS_TEXT_OVERRIDES
        if HELP_START <= addr <= HELP_END
    }
    groups: list[dict] = []
    for group in groups_json.get("groups", []):
        gid = group.get("group_id", "")
        if not gid.startswith("g_00DFA"):
            continue
        members = []
        for member in group.get("members", []):
            addr = int(member["address"], 16)
            if WATCH_START <= addr < WATCH_END:
                members.append({
                    "address": addr,
                    "slot": slots.get(addr, 0),
                    "text": member.get("ship_ko") or member.get("ko") or "",
                    "override_target": addr in override_targets,
                })
        if not members:
            continue
        target_members = [m for m in members if m["override_target"]]
        if not target_members:
            continue
        first = min(m["address"] for m in members)
        end = max(m["address"] + int(m.get("slot") or 0) for m in members)
        groups.append({
            "group_id": gid,
            "prefix_start": max(WATCH_START, first - 16),
            "start": first,
            "end": end,
            "members": members,
            "target_addresses": [m["address"] for m in target_members],
            "assembled_ko": group.get("assembled_ko", ""),
        })
    groups.sort(key=lambda g: g["start"])
    return groups


def classify_addr(addr: int, groups: list[dict]) -> dict:
    off = rom_offset(addr)
    if POINTER_TABLE_START <= off < POINTER_TABLE_END:
        return {
            "kind": "pointer_table",
            "offset": f"0x{off:08X}",
            "target_group": None,
        }
    for group in groups:
        if group["prefix_start"] <= off < group["end"]:
            target_addresses = [
                f"0x{addr:08X}"
                for addr in group["target_addresses"]
                if HELP_START <= addr <= HELP_END
            ]
            return {
                "kind": "help_group",
                "offset": f"0x{off:08X}",
                "target_group": group["group_id"],
                "target_addresses": target_addresses,
                "assembled_ko": group["assembled_ko"],
            }
    if WATCH_START <= off < WATCH_END:
        return {
            "kind": "watch_range_other",
            "offset": f"0x{off:08X}",
            "target_group": None,
        }
    return {"kind": "outside", "offset": f"0x{off:08X}", "target_group": None}


def parse_watch_log(path: Path, groups: list[dict], start_pos: int = 0) -> list[dict]:
    if not path.exists():
        return []
    data = path.read_text(encoding="utf-8", errors="replace")
    chunk = data[start_pos:]
    hits: list[dict] = []
    for line in chunk.splitlines():
        match = WATCH_RE.match(line.strip())
        if not match:
            continue
        row = {
            key: int(value, 16) if key != "order" else int(value)
            for key, value in match.groupdict().items()
        }
        row["source"] = classify_addr(row["addr"], groups)
        row["raw"] = line
        hits.append(row)
    return hits


def summarize_hits(hits: list[dict]) -> dict:
    direct_groups: dict[str, dict] = {}
    pointer_hits = 0
    other_hits = 0
    for hit in hits:
        src = hit["source"]
        if src["kind"] == "help_group":
            gid = src["target_group"]
            entry = direct_groups.setdefault(gid, {
                "group_id": gid,
                "hit_count": 0,
                "target_addresses": src.get("target_addresses", []),
                "assembled_ko": src.get("assembled_ko", ""),
            })
            entry["hit_count"] += 1
        elif src["kind"] == "pointer_table":
            pointer_hits += 1
        else:
            other_hits += 1
    direct_targets = sorted({
        addr
        for entry in direct_groups.values()
        for addr in entry.get("target_addresses", [])
    })
    return {
        "hit_count": len(hits),
        "direct_group_count": len(direct_groups),
        "direct_target_count": len(direct_targets),
        "direct_targets": direct_targets,
        "direct_groups": sorted(direct_groups.values(), key=lambda row: row["group_id"]),
        "pointer_table_hits": pointer_hits,
        "other_watch_range_hits": other_hits,
    }


def label_font(size: int) -> ImageFont.ImageFont:
    for path in ("/Library/Fonts/NanumGothic.ttf", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_contact(rows: list[dict], out_path: Path) -> None:
    panels = []
    font = label_font(12)
    for row in rows:
        frame = ROOT / row["frame"]
        if not frame.exists():
            continue
        img = Image.open(frame).convert("RGB").resize((480, 320), Image.NEAREST)
        header = Image.new("RGB", (480, 34), (24, 24, 28))
        draw = ImageDraw.Draw(header)
        summary = row["summary"]
        targets = ",".join(a[-4:] for a in summary["direct_targets"][:6])
        if len(summary["direct_targets"]) > 6:
            targets += ",..."
        draw.text((6, 4), f"{row['case_id']}  groups={summary['direct_group_count']} targets={targets}", font=font, fill=(235, 235, 235))
        panel = Image.new("RGB", (480, 354), (24, 24, 28))
        panel.paste(header, (0, 0))
        panel.paste(img, (0, 34))
        panels.append(panel)
    if not panels:
        return
    cols = 2
    pad = 8
    rows_count = (len(panels) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 480 + pad * (cols + 1), rows_count * 354 + pad * (rows_count + 1)), (12, 12, 14))
    for idx, panel in enumerate(panels):
        y, x = divmod(idx, cols)
        sheet.paste(panel, (pad + x * (480 + pad), pad + y * (354 + pad)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def setup_watch(driver: MGBADriver, log_path: Path) -> str:
    if log_path.exists():
        log_path.unlink()
    return driver.cmd(f"watchaddr {gba_addr(WATCH_START):08X} {WATCH_END - WATCH_START} r {log_path}")


def run_case(
    *,
    case_id: str,
    rom: Path,
    harness: Path,
    out_dir: Path,
    groups: list[dict],
    start: str,
    state: Path | None,
    tempsav: Path | None,
    steps: list[list],
) -> dict:
    case_dir = out_dir / safe_name(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "watch.log"
    driver = MGBADriver(rom, case_dir, harness)
    prov: dict = {
        "case_id": case_id,
        "start": start,
        "steps": steps,
        "watch_log": rel(log_path),
    }
    try:
        driver.frames(1)
        if start == "fresh_part1_menu":
            drive_part1_menu_from_coldboot(driver)
        elif start == "state":
            if state is None:
                raise ValueError("state start without state")
            driver.loadstate(state)
            driver.frames(1)
            prov["state"] = rel(state)
            prov["state_sha256"] = sha256(state)
            prov["watchpoint_caveat"] = "savestate route; positive text read after input is useful, static BG may still be stale"
        elif start == "tempsav_part1_menu":
            if tempsav is None:
                raise ValueError("tempsav start without tempsav")
            response = driver.cmd(f"loadtempsav {tempsav}")
            if not response.endswith("ok=1"):
                raise AssertionError(response)
            driver.cmd("reset")
            drive_part1_menu_from_coldboot(driver)
            prov["tempsav"] = rel(tempsav)
            prov["tempsav_sha256"] = sha256(tempsav)
            prov["loadtempsav_response"] = response
            prov["watchpoint_caveat"] = (
                "loadtempsav+reset route; menu is re-rendered by the current ROM, "
                "but only final-frame-visible hits should be promoted to visual evidence"
            )
        else:
            raise ValueError(start)
        watch_response = setup_watch(driver, log_path)
        prov["watch_response"] = watch_response
        run_nav(driver, steps)
        frame = driver.shot("frame")
        frame_path = case_dir / "frame.png"
        frame.save(frame_path)
    finally:
        driver.close()
    hits = parse_watch_log(log_path, groups)
    summary = summarize_hits(hits)
    return {
        **prov,
        "frame": rel(frame_path),
        "summary": summary,
        "hits": hits[:200],
        "truncated_hits": max(0, len(hits) - 200),
    }


def default_cases() -> list[tuple[str, list[list]]]:
    cases: list[tuple[str, list[list]]] = []
    for key in ("DOWN", "UP", "RIGHT", "LEFT"):
        for count in range(1, 10):
            cases.append((f"fresh_mode_{key.lower()}_{count:02d}", [["press", key, 120]] * count))
    cases.append(("fresh_operation_entry", [["press", "A", 200]]))
    for count in range(1, 9):
        cases.append((f"fresh_operation_down_{count:02d}", [["press", "A", 200]] + [["press", "DOWN", 120]] * count))
    cases.append(("fresh_single_entry", [["press", "DOWN", 120], ["press", "A", 180]]))
    for count in range(1, 9):
        cases.append((f"fresh_single_down_{count:02d}", [["press", "DOWN", 120], ["press", "A", 180]] + [["press", "DOWN", 120]] * count))
    cases.append(("fresh_link_entry", [["press", "DOWN", 120], ["press", "DOWN", 120], ["press", "A", 180]]))
    for count in range(1, 8):
        cases.append((f"fresh_link_down_{count:02d}", [["press", "DOWN", 120], ["press", "DOWN", 120], ["press", "A", 180]] + [["press", "DOWN", 120]] * count))
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--temp-out", default=str(ROOT / "temp" / "part1_compact_help_read_watch"))
    ap.add_argument("--no-default-cases", action="store_true")
    ap.add_argument("--state", action="append", default=[])
    ap.add_argument("--tempsav", action="append", default=[],
                    help="Combined 128KiB mGBA save to load with loadtempsav, reset, then drive to Part1 menu.")
    ap.add_argument("--tempsav-default-cases", action="store_true",
                    help="Run the full fresh Part1 menu sweep for each tempsav instead of the short state-step set.")
    ap.add_argument("--state-step", action="append", default=[],
                    help="State/tempsav step to run after installing watches; repeatable. Defaults to DOWN/UP/RIGHT/LEFT/A/B.")
    args = ap.parse_args()

    rom = Path(args.rom)
    harness = Path(args.harness)
    out_json = Path(args.out_json)
    temp_out = Path(args.temp_out)
    if not rom.exists():
        raise SystemExit(f"ROM 없음: {rom}")
    if not harness.exists():
        raise SystemExit(f"mGBA harness 없음: {harness}")
    temp_out.mkdir(parents=True, exist_ok=True)

    groups = load_groups()
    cases: list[dict] = []
    if not args.no_default_cases:
        for case_id, steps in default_cases():
            print(f"[probe] {case_id}")
            cases.append(run_case(
                case_id=case_id,
                rom=rom,
                harness=harness,
                out_dir=temp_out,
                groups=groups,
                start="fresh_part1_menu",
                state=None,
                tempsav=None,
                steps=steps,
            ))
    state_steps = parse_steps(args.state_step) if args.state_step else []
    default_state_step_sets = [
        [["frames", 20]],
        [["press", "DOWN", 120]],
        [["press", "UP", 120]],
        [["press", "RIGHT", 120]],
        [["press", "LEFT", 120]],
        [["press", "A", 180]],
        [["press", "B", 180]],
    ]
    for raw_state in args.state:
        state = Path(raw_state)
        if not state.is_absolute():
            state = ROOT / state
        if not state.exists():
            raise SystemExit(f"state 없음: {state}")
        step_sets = [state_steps] if state_steps else default_state_step_sets
        for idx, steps in enumerate(step_sets):
            case_id = f"state_{safe_name(rel(state))}_{idx:02d}"
            print(f"[probe] {case_id}")
            cases.append(run_case(
                case_id=case_id,
                rom=rom,
                harness=harness,
                out_dir=temp_out,
                groups=groups,
                start="state",
                state=state,
                tempsav=None,
                steps=steps,
            ))
    for raw_tempsav in args.tempsav:
        tempsav = Path(raw_tempsav)
        if not tempsav.is_absolute():
            tempsav = ROOT / tempsav
        if not tempsav.exists():
            raise SystemExit(f"tempsav 없음: {tempsav}")
        if args.tempsav_default_cases:
            step_sets = default_cases()
        else:
            step_sets = [("custom", state_steps)] if state_steps else [
                (f"{idx:02d}", steps) for idx, steps in enumerate(default_state_step_sets)
            ]
        for case_label, steps in step_sets:
            case_id = f"tempsav_{safe_name(rel(tempsav))}_{case_label}"
            print(f"[probe] {case_id}")
            cases.append(run_case(
                case_id=case_id,
                rom=rom,
                harness=harness,
                out_dir=temp_out,
                groups=groups,
                start="tempsav_part1_menu",
                state=None,
                tempsav=tempsav,
                steps=steps,
            ))

    direct_targets = sorted({
        target
        for case in cases
        for target in case["summary"]["direct_targets"]
    })
    direct_groups = sorted({
        group["group_id"]
        for case in cases
        for group in case["summary"]["direct_groups"]
    })
    hit_cases = [case for case in cases if case["summary"]["direct_group_count"] > 0]
    contact = temp_out / "contact.png"
    build_contact(hit_cases, contact)
    report = {
        "rom": rel(rom),
        "rom_sha256": sha256(rom),
        "watch_range": [f"0x{WATCH_START:08X}", f"0x{WATCH_END:08X}"],
        "group_count": len(groups),
        "case_count": len(cases),
        "hit_case_count": len(hit_cases),
        "direct_group_count": len(direct_groups),
        "direct_target_count": len(direct_targets),
        "direct_groups": direct_groups,
        "direct_targets": direct_targets,
        "contact": rel(contact) if contact.exists() else None,
        "cases": cases,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case_count": report["case_count"],
        "hit_case_count": report["hit_case_count"],
        "direct_group_count": report["direct_group_count"],
        "direct_target_count": report["direct_target_count"],
        "report": rel(out_json),
        "contact": report["contact"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
