#!/usr/bin/env python3
"""Audit real translation completion separately from placeholder coverage."""

import csv
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPREHENSIVE = ROOT / "data" / "translation_comprehensive.csv"
NEEDS_WORK = ROOT / "data" / "translation_needs_rework.csv"
REPORT = ROOT / "docs" / "TRANSLATION_REAUDIT_2026_05_18.md"

HANGUL = re.compile(r"[\uac00-\ud7a3]")
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
SYMBOL_TRANSLATIONS = {"···"}


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def classify(row):
    korean = (row.get("korean") or "").strip()
    notes = row.get("notes", "")

    if korean in PLACEHOLDERS:
        return "needs_translation", "placeholder_or_unknown"
    if "fallback" in notes:
        return "needs_translation", "auto_fallback"
    if not HANGUL.search(korean) and korean not in SYMBOL_TRANSLATIONS:
        return "needs_review", "no_hangul_in_korean"
    return "meaningful", "has_korean_translation"


def main():
    rows = read_rows(COMPREHENSIVE)
    audited = []
    counts = Counter()
    reasons = Counter()
    by_note = Counter()
    needs_source_counter = Counter()

    for row in rows:
        status, reason = classify(row)
        counts[status] += 1
        reasons[reason] += 1
        by_note[row.get("notes", "")] += 1

        if status != "meaningful":
            needs_source_counter[row.get("japanese", "")] += 1
            audited.append({
                "address": row.get("address", ""),
                "japanese": row.get("japanese", ""),
                "current_korean": row.get("korean", ""),
                "char_count": row.get("char_count", ""),
                "frequency": row.get("frequency", ""),
                "audit_status": status,
                "audit_reason": reason,
                "previous_notes": row.get("notes", ""),
            })

    with NEEDS_WORK.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "address",
            "japanese",
            "current_korean",
            "char_count",
            "frequency",
            "audit_status",
            "audit_reason",
            "previous_notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audited)

    total = len(rows)
    meaningful = counts["meaningful"]
    needs_translation = counts["needs_translation"]
    needs_review = counts["needs_review"]
    remaining = needs_translation + needs_review
    unique_remaining = len({row["japanese"] for row in audited})
    progress = meaningful / total * 100 if total else 0

    top_remaining = needs_source_counter.most_common(30)
    report = [
        "# Translation Re-Audit - 2026-05-18",
        "",
        "## Corrected Status",
        f"- Total extracted text rows: {total:,}",
        f"- Meaningful Korean translations: {meaningful:,} ({progress:.2f}%)",
        f"- Needs real translation: {needs_translation:,}",
        f"- Needs manual review: {needs_review:,}",
        f"- Remaining rows total: {remaining:,}",
        f"- Remaining unique source strings: {unique_remaining:,}",
        "",
        "## Why Previous 100% Was Wrong",
        "- Placeholder coverage was counted as completion.",
        "- `미상` was used for many rows that still contain readable Japanese source text.",
        "- The current import CSV is complete only in the technical sense that every address has a value; it is not semantically translated.",
        "",
        "## Audit Reason Counts",
    ]
    for reason, count in reasons.most_common():
        report.append(f"- {reason}: {count:,}")

    report.extend([
        "",
        "## Previous Note Counts",
    ])
    for note, count in by_note.most_common():
        report.append(f"- {note or '(blank)'}: {count:,}")

    report.extend([
        "",
        "## Top Remaining Repeated Source Strings",
    ])
    for source, count in top_remaining:
        report.append(f"- {count}x: {source}")

    report.extend([
        "",
        "## Generated Files",
        f"- Rework list: `{NEEDS_WORK.relative_to(ROOT).as_posix()}`",
    ])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"total={total}")
    print(f"meaningful={meaningful}")
    print(f"needs_translation={needs_translation}")
    print(f"needs_review={needs_review}")
    print(f"remaining={remaining}")
    print(f"unique_remaining={unique_remaining}")
    print(f"progress={progress:.2f}%")


if __name__ == "__main__":
    main()
