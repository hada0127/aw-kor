#!/usr/bin/env python3
"""Export ADDRESS_TEXT_OVERRIDES fallback literals to the TSV build authority."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from audit_address_text_overrides import BUILD, ROOT, iter_source_entries

DEFAULT_OUT = ROOT / "data" / "address_text_overrides.tsv"


def build_rows() -> dict[int, str]:
    rows: dict[int, str] = {}
    for entry in iter_source_entries(BUILD):
        rows[entry["addr_int"]] = str(entry["value"] or "")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(["address", "text"])
        for addr, text in sorted(rows.items()):
            writer.writerow([f"0x{addr:08X}", text])
    print(f"wrote {len(rows)} rows -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
