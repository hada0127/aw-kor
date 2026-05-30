#!/usr/bin/env python3
"""Session 3 QA: 예약코드 인코딩의 byte budget + 시각폭(박스) 적합성 리포트.

- byte budget: encoded_len(한글2B/ASCII1B/전각2B) vs 슬롯길이(found_texts 권위).
  초과 행은 빌드에서 skip(원문 유지)되므로, 그 목록을 보고 번역 축약 대상 선정.
- 시각폭: 한글 라인이 원본 일본어 라인보다 시각적으로 넓은지(전각2/ASCII1 근사).
  바이트 예산을 지키면 전각↔전각은 폭도 충족되나, ASCII→전각(숫자/메뉴) 행은 예외.

사용: python tools/qa_text_fit.py
"""
import collections, csv, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
SAFE_MIN_ADDR = 0x800000

sys.path.insert(0, os.path.join(BASE, 'tools'))
from build_korean_full import (
    ADDRESS_TEXT_OVERRIDES,
    SOURCE_TEXT_OVERRIDES,
    TEXT_OVERRIDES,
    SAFE_MIN_ADDR,
    SYLCODE,
    encode_fit,
    in_deny,
)


def load_slots():
    s = {}
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                s[a] = int(r.get('length') or 0)
            except (ValueError, TypeError):
                pass
    return s


def enc_len(ko):
    n = 0
    for ch in ko:
        if '가' <= ch <= '힣':
            n += 2
        elif 0x20 <= ord(ch) <= 0x7E:
            n += 1
        else:
            n += 2
    return n


def vwidth(s):
    w = 0
    for ch in s:
        w += 1 if (ch == ' ' or 0x20 <= ord(ch) <= 0x7E) else 2
    return w


def main():
    slots = load_slots()
    import json
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}
    written = overflow = wider = compact_shortened = deny = no_ko = code_region = no_slot = 0
    levels = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    unmapped = collections.Counter()
    seen_import_addrs = set()
    written_addrs = set()

    def check_text(a, ko, ja):
        nonlocal written, overflow, wider, compact_shortened
        enc, level = encode_fit(ko, slots[a], syl_to_code, unmapped)
        if enc is None:
            overflow += 1
            return
        written += 1
        written_addrs.add(a)
        levels[level] += 1
        if level == 5:
            compact_shortened += 1
        if vwidth(ko) > vwidth(ja):
            wider += 1

    with open(TRANS, newline='') as f:
        for row in csv.DictReader(f):
            ko = (row.get('korean') or '').strip()
            ja = (row.get('japanese') or '').strip()
            try:
                a = int(row['address'], 16)
            except (ValueError, TypeError):
                continue
            seen_import_addrs.add(a)
            if a in ADDRESS_TEXT_OVERRIDES:
                ko = ADDRESS_TEXT_OVERRIDES[a]
            elif ja in SOURCE_TEXT_OVERRIDES and not any('가' <= ch <= '힣' for ch in ko):
                ko = SOURCE_TEXT_OVERRIDES[ja]
            if a < SAFE_MIN_ADDR:
                code_region += 1
                continue
            if slots.get(a, 0) <= 0:
                no_slot += 1
                continue
            if in_deny(a, a + slots[a]):
                deny += 1
                continue
            if not ko:
                no_ko += 1
                continue
            ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
            check_text(a, ko, ja)

    for a, ko in sorted(ADDRESS_TEXT_OVERRIDES.items()):
        if a in seen_import_addrs or a < SAFE_MIN_ADDR or slots.get(a, 0) <= 0:
            continue
        if in_deny(a, a + slots[a]):
            continue
        check_text(a, ko, '')

    with open(FOUND, newline='', encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            try:
                a = int((row.get('address') or '').strip(), 16)
                slot = int(row.get('length') or 0)
            except (ValueError, TypeError):
                continue
            if a in written_addrs or a in seen_import_addrs:
                continue
            ko = SOURCE_TEXT_OVERRIDES.get((row.get('text') or '').strip())
            if not ko or a < SAFE_MIN_ADDR or slot <= 0:
                continue
            if in_deny(a, a + slot):
                continue
            check_text(a, ko, row.get('text') or '')

    print(f'written(한글 인코딩): {written}')
    print('fit levels: ' + ', '.join(f'level{k}={levels[k]}' for k in sorted(levels)))
    print(f'compact-shortened fallback: {compact_shortened}')
    print(f'overflow(슬롯초과 skip→원문): {overflow}')
    print(f'no_ko: {no_ko}, code_region: {code_region}, no_slot: {no_slot}, deny/data-skip: {deny}')
    print(f'visual-wider than JA: {wider} ({100*wider/max(written,1):.1f}%) — 박스폭 잠재리스크(대부분 ≤1글자/노이즈)')


if __name__ == '__main__':
    main()
