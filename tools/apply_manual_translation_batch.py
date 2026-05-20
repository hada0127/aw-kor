#!/usr/bin/env python3
"""Apply reviewed manual translation batches to the project CSV files."""

import csv
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPREHENSIVE = ROOT / "data" / "translation_comprehensive.csv"
FOUND = ROOT / "data" / "game_wars_found_texts.csv"
IMPORT = ROOT / "data" / "translation_for_import.csv"
REVIEWED_IMPORT = ROOT / "data" / "translation_for_import_reviewed.csv"

HANGUL = re.compile(r"[\uac00-\ud7a3]")
SYMBOL_TRANSLATIONS = {"···", "...", "....", "......"}
PLACEHOLDERS = {
    "",
    "미상",
    "불명",
    "?",
    "[번역 필요]",
    "번역 필요",
    "원문 확인 필요",
    "판독 불가",
    "판독불가",
}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def euc_len(text):
    return len(text.encode("euc-kr", errors="ignore"))


def status_for(korean):
    korean = (korean or "").strip()
    if korean in PLACEHOLDERS:
        return "Needs Translation", "batch audit: placeholder"
    if HANGUL.search(korean) or korean in SYMBOL_TRANSLATIONS or re.search(r"[A-Za-z0-9]", korean):
        return "Translated", "batch audit: reviewed batch translation"
    return "Needs Review", "batch audit: no Hangul in Korean field"


def main():
    if len(sys.argv) != 2:
        print("usage: python tools/apply_manual_translation_batch.py data/manual_translation_batch_001.csv")
        return 2

    batch_path = ROOT / sys.argv[1]
    batch_rows = read_csv(batch_path)
    mapping = {row["japanese"]: row["korean"].strip() for row in batch_rows if row.get("japanese")}

    found_lengths = {}
    for row in read_csv(FOUND):
        found_lengths[row["address"]] = int(row.get("length") or 0)

    rows = read_csv(COMPREHENSIVE)
    applied = 0
    skipped_too_long = []

    for row in rows:
        japanese = row.get("japanese", "")
        if japanese not in mapping:
            continue

        korean = mapping[japanese]
        slot_len = found_lengths.get(row["address"], 0)
        if slot_len and euc_len(korean) > slot_len:
            skipped_too_long.append((row["address"], japanese, korean, euc_len(korean), slot_len))
            continue

        row["korean"] = korean
        row["status"], row["notes"] = status_for(korean)
        row["notes"] += f"; source={batch_path.name}"
        applied += 1

    write_csv(
        COMPREHENSIVE,
        rows,
        ["address", "japanese", "korean", "char_count", "frequency", "status", "notes"],
    )

    import_rows = []
    for row in rows:
        if row["status"] != "Translated":
            continue
        import_rows.append({
            "address": row["address"],
            "japanese": row["japanese"],
            "korean": row["korean"],
            "length": str(found_lengths.get(row["address"], 0)),
        })

    write_csv(IMPORT, import_rows, ["address", "japanese", "korean", "length"])
    write_csv(REVIEWED_IMPORT, import_rows, ["address", "japanese", "korean", "length"])

    print(f"batch={batch_path}")
    print(f"mapping_entries={len(mapping)}")
    print(f"applied_rows={applied}")
    print(f"translated_import_rows={len(import_rows)}")
    print(f"skipped_too_long={len(skipped_too_long)}")
    for item in skipped_too_long[:20]:
        print("too_long", item)
    return 1 if skipped_too_long else 0


if __name__ == "__main__":
    raise SystemExit(main())
