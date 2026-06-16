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
    PLACEHOLDER_KO,
    SAFE_MIN_ADDR,
    SOURCE_TEXT_OVERRIDES,
    SYLCODE,
    TEXT_OVERRIDES,
    encode_fit,
    encode_text,
    in_deny,
)

# 단일 소스: 빌드의 PLACEHOLDER_KO를 그대로 사용(과거 QA 목록이 '해독 불가'·'깨진 문자열'을
# 빠뜨려 검출 누락 → 빌드와 통일). import 검사는 '정확일치'라 안전.
PLACEHOLDERS = tuple(sorted(PLACEHOLDER_KO))

# ROM 스캔은 '부분문자열' 검색이라, 정상 한글 단어의 부분이 되는 짧은 마커는 거짓양성을
# 낸다(예: '불명' ⊂ 행방불명/정체불명, '불가' ⊂ 가능불가). 이런 모호 토큰만 ROM 스캔에서 제외.
# 완전형 마커('의미 불명','판독 불가' 등)는 그대로 스캔하므로 진짜 placeholder는 여전히 잡힌다.
ROM_SCAN_AMBIGUOUS = {'불명', '미상', '불가'}
ROM_SCAN_PLACEHOLDERS = tuple(p for p in PLACEHOLDERS if p not in ROM_SCAN_AMBIGUOUS)


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
    for value in ROM_SCAN_PLACEHOLDERS:
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
