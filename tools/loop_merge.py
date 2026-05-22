#!/usr/bin/env python3
"""Merge agent output files (address|korean) into translation_for_import.csv.

Reads data/_work/out_*.txt where each line is: address|korean
Looks up japanese from source, computes length as utf-8 byte count of korean.
Only adds addresses that exist in source and are not already translated.

Usage: python tools/loop_merge.py
"""
import csv
from pathlib import Path

DATA = Path('data')
WORK = DATA / '_work'
OUT = DATA / 'translation_for_import.csv'
FIELDS = ['address', 'japanese', 'korean', 'length']


def load_source_japanese():
    jp = {}
    with open(DATA / 'game_wars_found_texts.csv', encoding='utf-8', errors='ignore') as fh:
        for row in csv.DictReader(fh):
            a = (row.get('address') or '').strip()
            if a:
                jp[a] = (row.get('text') or '').strip()
    return jp


def load_existing():
    existing = {}
    if OUT.exists():
        with open(OUT, encoding='utf-8', errors='ignore') as fh:
            for row in csv.DictReader(fh):
                a = (row.get('address') or '').strip()
                if a:
                    existing[a] = {
                        'address': a,
                        'japanese': (row.get('japanese') or '').strip(),
                        'korean': (row.get('korean') or '').strip(),
                        'length': (row.get('length') or '').strip(),
                    }
    return existing


def main():
    jp = load_source_japanese()
    existing = load_existing()
    already = {a for a, r in existing.items() if r['korean']}

    added = 0
    skipped_dup = 0
    skipped_unknown = 0
    for p in sorted(WORK.glob('out_*.txt')):
        with open(p, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.rstrip('\n').rstrip('\r')
                if '|' not in line:
                    continue
                addr, korean = line.split('|', 1)
                addr = addr.strip()
                korean = korean.strip()
                if not addr or not korean:
                    continue
                if addr not in jp:
                    skipped_unknown += 1
                    continue
                if addr in already:
                    skipped_dup += 1
                    continue
                existing[addr] = {
                    'address': addr,
                    'japanese': jp[addr],
                    'korean': korean,
                    'length': str(len(korean.encode('utf-8'))),
                }
                already.add(addr)
                added += 1

    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, restval='')
        w.writeheader()
        for a in sorted(existing.keys()):
            w.writerow(existing[a])

    translated_total = sum(1 for r in existing.values() if r['korean'])
    print(f"added={added}")
    print(f"skipped_duplicate={skipped_dup}")
    print(f"skipped_unknown_addr={skipped_unknown}")
    print(f"translated_total={translated_total}")


if __name__ == '__main__':
    main()
