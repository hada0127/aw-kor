#!/usr/bin/env python3
"""Check that placeholder translations are not present in the built ROM.

This complements Japanese residual QA. A row can be "Korean" syntactically but
still be a placeholder such as "미상" or "판독 불가"; those must not reach the
final ROM as user-visible text.
"""
import argparse
import collections
import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_ROM = BASE / 'output' / 'game_wars_korean_full.gba'
FOUND = BASE / 'data' / 'game_wars_found_texts.csv'
TRANS = BASE / 'data' / 'translation_for_import.csv'

sys.path.insert(0, str(BASE / 'tools'))
from build_korean_full import (  # noqa: E402
    ADDRESS_TEXT_OVERRIDES,
    SAFE_MIN_ADDR,
    SOURCE_TEXT_OVERRIDES,
    SYLCODE,
    TEXT_OVERRIDES,
    encode_fit,
    encode_text,
    in_deny,
)

PLACEHOLDERS = (
    '미상',
    '번역 필요',
    '번역필요',
    '원문 불명',
    '원문불명',
    '의미 불명',
    '의미불명',
    '판독 불가',
    '판독불가',
)


def load_slots():
    slots = {}
    with FOUND.open(newline='', encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            try:
                slots[int((row.get('address') or '').strip(), 16)] = int(row.get('length') or 0)
            except (TypeError, ValueError):
                continue
    return slots


def placeholder_kind(text):
    compact = text.strip()
    compact_no_space = compact.replace(' ', '')
    for value in PLACEHOLDERS:
        if compact == value or compact_no_space == value.replace(' ', ''):
            return value
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', default=str(DEFAULT_ROM))
    parser.add_argument('--limit', type=int, default=30)
    args = parser.parse_args()

    rom = Path(args.rom).read_bytes()
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}
    unmapped = collections.Counter()

    rom_hits = []
    for value in PLACEHOLDERS:
        try:
            payload = encode_text(value, syl_to_code, unmapped)
        except KeyError:
            continue
        start = 0
        while True:
            pos = rom.find(payload, start)
            if pos < 0:
                break
            rom_hits.append((pos, value))
            start = pos + 1

    slots = load_slots()
    import_hits = []
    with TRANS.open(newline='', encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            try:
                addr = int((row.get('address') or '').strip(), 16)
            except (TypeError, ValueError):
                continue
            ko = (row.get('korean') or '').strip()
            ja = (row.get('japanese') or '').strip()
            if addr in ADDRESS_TEXT_OVERRIDES:
                ko = ADDRESS_TEXT_OVERRIDES[addr]
            elif ja in SOURCE_TEXT_OVERRIDES and not any('가' <= ch <= '힣' for ch in ko):
                ko = SOURCE_TEXT_OVERRIDES[ja]
            ko = ADDRESS_TEXT_OVERRIDES.get(addr, TEXT_OVERRIDES.get(ko, ko))
            kind = placeholder_kind(ko)
            if not kind:
                continue
            slot = slots.get(addr, 0)
            if addr < SAFE_MIN_ADDR or slot <= 0 or in_deny(addr, addr + slot):
                continue
            enc, _level = encode_fit(ko, slot, syl_to_code, unmapped)
            if enc is None:
                continue
            import_hits.append((addr, kind, ja, ko))

    print(f'rom_placeholder_hits={len(rom_hits)}')
    print(f'import_placeholder_warnings={len(import_hits)}')
    for pos, value in rom_hits[:args.limit]:
        print(f'rom 0x{pos:X} {value}')
    for addr, kind, ja, ko in import_hits[:args.limit]:
        print(f'import 0x{addr:X} {kind} ja={ja!r} ko={ko!r}')

    # Import warnings are kept visible because many are data/symbol extraction
    # false positives; only final ROM placeholder bytes fail the gate.
    return 1 if rom_hits else 0


if __name__ == '__main__':
    raise SystemExit(main())
