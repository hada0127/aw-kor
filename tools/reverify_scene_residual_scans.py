#!/usr/bin/env python3
"""Regenerate residual evidence for container scenes.

Container scenes are address buckets, not directly capturable screens.  The
strict audit pins each evidence file to the current ROM SHA and to its own file
SHA.  This command rebuilds those evidence files from the current output ROM and
updates data/scene_residual_scans.json.

The important detail: do not judge arbitrary ROM bytes as Shift-JIS text.  The
Korean renderer deliberately uses custom two-byte codes, and byte-unaligned SJIS
decoding produces many false Japanese-looking runs.  The residual decision is
therefore based on extracted text rows from game_wars_found_texts.csv, reusing
qa_japanese_residuals.py's coverage and same-original checks.  A separate raw
kana observation list is retained as audit evidence only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "scene_catalog.json"
MANIFEST = ROOT / "data" / "scene_residual_scans.json"
ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT_DIR = ROOT / "data" / "scene_residual_reverify"
FOUND = ROOT / "data" / "game_wars_found_texts.csv"

sys.path.insert(0, str(ROOT / "tools"))
import qa_japanese_residuals as J  # noqa: E402

KATAKANA_CHAR_RE = re.compile(r"[ァ-ヺー]")

RAW_KANA_ALLOWLIST = {
    0x00DA4342: (
        "name-grid charset continuation after 0x00DA432C/0x00DA4337; "
        "raw grid data must stay SJIS for selection layout"
    ),
    0x00EE22AC: (
        "common comm numeric/control table single kana; same as original. "
        "Historical menu/focus residual scan found no visible hit; keep visual follow-up in todo."
    ),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


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


def normalize_range(item) -> tuple[int, int, str]:
    if isinstance(item, str):
        start_s, end_s = item.split(":", 1)
        start, end = parse_hex(start_s), parse_hex(end_s)
    elif isinstance(item, (list, tuple)) and len(item) == 2:
        start, end = parse_hex(item[0]), parse_hex(item[1])
    else:
        raise ValueError(f"unsupported range: {item!r}")
    return start, end, f"0x{start:08X}:0x{end:08X}"


def load_found_rows() -> list[dict]:
    rows = []
    with FOUND.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            try:
                row["_addr"] = int((row.get("address") or "").strip(), 16)
                row["_length"] = int(row.get("length") or 0)
            except (TypeError, ValueError):
                continue
            rows.append(row)
    rows.sort(key=lambda row: row["_addr"])
    return rows


def row_payload(item: tuple) -> dict:
    _, addr, length, char_count, text, _reason, score, same_original, current_kind = item
    return {
        "offset": f"0x{addr:08X}",
        "length": length,
        "chars": char_count,
        "score": score,
        "same_original": bool(same_original),
        "current_kind": current_kind,
        "text": text,
    }


def classify_extracted_rows(
    found_rows: list[dict],
    translations: dict,
    translation_ranges: list[tuple[int, int]],
    direct_patches: dict,
    rom: bytes,
    start: int,
    end: int,
    min_score: int,
) -> dict:
    covered = 0
    missing = []
    for row in found_rows:
        addr = row["_addr"]
        if addr < start:
            continue
        if addr >= end:
            break
        item = J.classify_row(row, translations, translation_ranges, direct_patches, rom, start, end)
        if not item:
            continue
        if item[0] == "covered":
            row["_covered"] = True
            covered += 1
        else:
            row["_covered"] = False
            missing.append(item)

    residuals = [
        row_payload(item)
        for item in missing
        if item[6] >= min_score and item[7]
    ]
    low_score_same_original = [
        row_payload(item)
        for item in missing
        if item[7] and item[6] < min_score
    ]
    kind_counts: dict[str, int] = {}
    for item in missing:
        kind = item[8] if len(item) > 8 else "unknown"
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    return {
        "covered_count": covered,
        "uncovered_count": len(missing),
        "same_original_uncovered_count": sum(1 for item in missing if item[7]),
        "current_kind_counts": kind_counts,
        "residual_candidates": residuals,
        "low_score_same_original": low_score_same_original[:8],
    }


def decode_sjis_at(rom: bytes, pos: int, end: int) -> tuple[str | None, int]:
    b0 = rom[pos]
    if b0 < 0x80:
        try:
            return bytes([b0]).decode("shift_jis"), 1
        except UnicodeDecodeError:
            return None, 1
    if pos + 1 < end:
        try:
            return rom[pos:pos + 2].decode("shift_jis"), 2
        except UnicodeDecodeError:
            pass
    return None, 1


def find_containing_row(found_rows: list[dict], offset: int) -> dict | None:
    # Container ranges are small and this runs only during evidence generation.
    for row in found_rows:
        start = row["_addr"]
        stop = start + max(row["_length"], 1)
        if start <= offset < stop:
            return row
        if start > offset:
            return None
    return None


def raw_kana_reason(offset: int, raw_end: int, text: str, containing: dict | None) -> tuple[bool, str]:
    deny = J.in_deny(offset, raw_end)
    if deny:
        return True, f"deny_region:{deny}"
    if containing and (containing.get("korean") or containing.get("_covered")):
        return True, "inside_covered_extracted_row_or_custom_encoding_boundary"
    if offset in RAW_KANA_ALLOWLIST:
        return True, RAW_KANA_ALLOWLIST[offset]
    if len(text) == 1 and containing:
        return True, "single-kana byte-boundary observation inside extracted row"
    return False, "unexplained_raw_kana"


def scan_raw_kana(rom: bytes, found_rows: list[dict], start: int, end: int) -> dict:
    observations = []
    pos = start
    run_start = None
    run_text = ""
    run_end = None

    def flush() -> None:
        nonlocal run_start, run_text, run_end
        if run_start is None or run_end is None:
            return
        containing = find_containing_row(found_rows, run_start)
        allowed, reason = raw_kana_reason(run_start, run_end, run_text, containing)
        observations.append({
            "offset": f"0x{run_start:08X}",
            "length": run_end - run_start,
            "text": run_text,
            "allowed": allowed,
            "reason": reason,
            "containing_extracted_addr": (
                f"0x{containing['_addr']:08X}" if containing else None
            ),
        })
        run_start = None
        run_text = ""
        run_end = None

    while pos < end:
        ch, size = decode_sjis_at(rom, pos, end)
        if ch and KATAKANA_CHAR_RE.fullmatch(ch):
            if run_start is None:
                run_start = pos
                run_text = ""
            run_text += ch
            run_end = pos + size
        else:
            flush()
        pos += size
    flush()

    unexplained = [row for row in observations if not row["allowed"]]
    return {
        "raw_kana_count": len(observations),
        "raw_kana_unexplained_count": len(unexplained),
        "raw_kana_observations": observations[:16],
        "raw_kana_unexplained": unexplained[:16],
    }


def scan_range(
    rom: bytes,
    range_text: str,
    found_rows: list[dict],
    translations: dict,
    translation_ranges: list[tuple[int, int]],
    direct_patches: dict,
    min_score: int,
) -> dict:
    start, end, normalized = normalize_range(range_text)
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"range outside ROM: {range_text}")
    extracted = classify_extracted_rows(
        found_rows, translations, translation_ranges, direct_patches, rom, start, end, min_score
    )
    raw_kana = scan_raw_kana(rom, found_rows, start, end)
    return {
        "range": normalized,
        "extracted": extracted,
        "raw_kana": raw_kana,
    }


def classify(range_rows: list[dict]) -> str:
    residuals = sum(
        len(row["extracted"]["residual_candidates"])
        for row in range_rows
    )
    raw_unexplained = sum(
        row["raw_kana"]["raw_kana_unexplained_count"]
        for row in range_rows
    )
    low_score = sum(
        row["extracted"]["same_original_uncovered_count"]
        for row in range_rows
    )
    if residuals:
        return "residual_candidate"
    if raw_unexplained:
        return "unexplained_raw_kana"
    if low_score:
        return "low_score_same_original_only"
    return "clean"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write evidence files and manifest")
    parser.add_argument("--min-score", type=int, default=7, help="qa_japanese_residuals candidate score gate")
    args = parser.parse_args()

    catalog = load_json(CATALOG)
    manifest = load_json(MANIFEST)
    scenes = {scene.get("id"): scene for scene in catalog.get("scenes", []) if scene.get("id")}
    rom = ROM.read_bytes()
    rom_sha = hashlib.sha256(rom).hexdigest()
    found_rows = load_found_rows()
    translations, translation_ranges = J.load_translations(J.DEFAULT_TRANS)
    translations.update(J.load_supplemental_translations(J.DEFAULT_SUPP_TRANS))
    direct_patches = J.load_direct_patch_texts()
    changed = []

    for entry in manifest.get("containers", []):
        sid = entry.get("container_scene_id")
        scene = scenes.get(sid, {})
        catalog_ranges = ((scene.get("dialogue_filter") or {}).get("addr_ranges") or [])
        ranges = entry.get("container_ranges") or catalog_ranges
        range_rows = [
            scan_range(rom, item, found_rows, translations, translation_ranges, direct_patches, args.min_score)
            for item in ranges
        ]
        residuals = [
            candidate
            for row in range_rows
            for candidate in row["extracted"]["residual_candidates"]
        ]
        raw_unexplained = [
            candidate
            for row in range_rows
            for candidate in row["raw_kana"]["raw_kana_unexplained"]
        ]
        result = [{
            "label": f"static_residual_reverify::{sid}",
            "method": "extracted_text_residual_reverification",
            "rom_sha256": rom_sha,
            "min_score": args.min_score,
            "ranges": range_rows,
            "extracted_covered_count": sum(row["extracted"]["covered_count"] for row in range_rows),
            "extracted_uncovered_count": sum(row["extracted"]["uncovered_count"] for row in range_rows),
            "same_original_uncovered_count": sum(
                row["extracted"]["same_original_uncovered_count"] for row in range_rows
            ),
            "raw_kana_count": sum(row["raw_kana"]["raw_kana_count"] for row in range_rows),
            "raw_kana_unexplained_count": len(raw_unexplained),
            "classification": classify(range_rows),
            "hit": residuals[0] if residuals else None,
            "residuals": residuals,
            "translation_residual": len(residuals),
        }]

        evidence = (entry.get("evidence") or [{}])[0]
        result_path = OUT_DIR / f"{sid}.json"
        if args.write:
            write_json(result_path, result)
            evidence["result_path"] = str(result_path.relative_to(ROOT))
            evidence["result_sha256"] = sha256(result_path)
            evidence["rom_sha256"] = rom_sha
            evidence["expected_cases"] = 1
            evidence["expected_hit_count"] = len(evidence.get("known_hits") or [])
            evidence["method"] = "extracted_text_residual_reverification"
            evidence["note"] = (
                f"{date.today().isoformat()} current ROM extracted-text residual reverify "
                f"(min_score={args.min_score}; raw kana observations retained)"
            )
            entry["evidence"] = [evidence]
        changed.append((sid, len(residuals), len(raw_unexplained), result_path))

    stamp = f"reverified_{date.today().isoformat().replace('-', '_')}"
    manifest[stamp] = {
        "rom_sha256": rom_sha,
        "method": "extracted_text_residual_reverification",
        "note": f"tools/reverify_scene_residual_scans.py --write --min-score {args.min_score}",
    }

    if args.write:
        write_json(MANIFEST, manifest)

    print(f"ROM {rom_sha}")
    for sid, residual_count, raw_unexplained_count, path in changed:
        print(
            f"{sid}: residual={residual_count} raw_unexplained={raw_unexplained_count} "
            f"-> {path.relative_to(ROOT)}"
        )
    print("wrote manifest/evidence" if args.write else "dry-run only")


if __name__ == "__main__":
    main()
