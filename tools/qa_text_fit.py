#!/usr/bin/env python3
"""Session 3 QA: 예약코드 인코딩의 byte budget + 시각폭(박스) 적합성 리포트.

- byte budget: encoded_len(한글2B/ASCII1B/전각2B) vs 슬롯길이(found_texts 권위).
  초과 행은 빌드에서 skip(원문 유지)되므로, 그 목록을 보고 번역 축약 대상 선정.
- 시각폭: 한글 라인이 원본 일본어 라인보다 시각적으로 넓은지(전각2/ASCII1 근사).
  바이트 예산을 지키면 전각↔전각은 폭도 충족되나, ASCII→전각(숫자/메뉴) 행은 예외.

사용: python tools/qa_text_fit.py
"""
import ast, collections, csv, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
SAFE_MIN_ADDR = 0x800000

sys.path.insert(0, os.path.join(BASE, 'tools'))
from build_korean_full import (
    ADDRESS_TEXT_OVERRIDES,
    COMPREHENSIVE_TRANS,
    SOURCE_TEXT_OVERRIDES,
    TEXT_OVERRIDES,
    SAFE_MIN_ADDR,
    SYLCODE,
    encode_fit,
    in_deny,
)


def load_found():
    slots = {}
    texts = {}
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                slots[a] = int(r.get('length') or 0)
                texts[a] = (r.get('text') or '').strip()
            except (ValueError, TypeError):
                pass
    return slots, texts


def load_found_rows():
    rows = []
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                length = int(r.get('length') or 0)
            except (ValueError, TypeError):
                continue
            try:
                raw = bytes.fromhex(r.get('hex_bytes') or '')
            except ValueError:
                raw = b''
            rows.append((a, a + length, (r.get('text') or '').strip(), raw))
    return sorted(rows)


def source_text_for_span(start, end, found_rows, fallback):
    parts = []
    for a, row_end, text, raw in found_rows:
        if row_end <= start:
            continue
        if a >= end:
            break
        overlap_start = max(start, a) - a
        overlap_end = min(end, row_end) - a
        if overlap_start <= 0 and overlap_end >= row_end - a and text:
            parts.append(text)
            continue
        chunk = raw[overlap_start:overlap_end] if raw else b''
        piece = chunk.decode('shift_jis', errors='ignore').strip() if chunk else ''
        if piece:
            parts.append(piece)
    return ''.join(parts) if parts else fallback


def load_direct_patch_texts():
    """Extract literal direct script and fixed-width label patches."""
    path = os.path.join(BASE, 'tools', 'build_korean_full.py')
    tree = ast.parse(open(path, encoding='utf-8').read())
    patches = []

    def has_hangul(text):
        return any('가' <= ch <= '힣' for ch in text)

    def const_text(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'encode_text'
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return node.args[0].value
        return None

    def add_patch(start, end, text, lineno):
        if isinstance(start, int) and isinstance(end, int) and end > start and text and has_hangul(text):
            patches.append((lineno, start, end, text))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'INTRO_DIRECT_TEXT'
            for target in node.targets
        ) and isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if not (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, int)
                    and isinstance(value, ast.Tuple)
                    and len(value.elts) == 2
                    and isinstance(value.elts[1], ast.Constant)
                    and isinstance(value.elts[1].value, int)
                ):
                    continue
                text = const_text(value.elts[0])
                add_patch(key.value, key.value + value.elts[1].value, text, node.lineno)
        elif isinstance(node, ast.Tuple) and len(node.elts) >= 3:
            start, end, text_node = node.elts[:3]
            text = const_text(text_node)
            if not (
                isinstance(start, ast.Constant)
                and isinstance(start.value, int)
                and isinstance(end, ast.Constant)
                and isinstance(end.value, int)
            ):
                continue
            if len(node.elts) >= 4 and end.value > start.value:
                add_patch(start.value, end.value, text, node.lineno)
            elif 0 < end.value <= 0x1000:
                add_patch(start.value, start.value + end.value, text, node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {'fixed_text_patch', 'fixed_zero_text_patch'} and len(node.args) >= 3:
                start, slot_len = node.args[:2]
                text = const_text(node.args[2])
                if (
                    isinstance(start, ast.Constant)
                    and isinstance(start.value, int)
                    and isinstance(slot_len, ast.Constant)
                    and isinstance(slot_len.value, int)
                ):
                    add_patch(start.value, start.value + slot_len.value, text, node.lineno)
            elif node.func.id == 'patch_script_row' and len(node.args) >= 3:
                start, end = node.args[:2]
                text = const_text(node.args[2])
                if (
                    isinstance(start, ast.Constant)
                    and isinstance(start.value, int)
                    and isinstance(end, ast.Constant)
                    and isinstance(end.value, int)
                ):
                    add_patch(start.value, end.value, text, node.lineno)
    direct = {}
    for _lineno, start, end, text in sorted(patches):
        direct[start] = (end, text)
    return direct


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
    slots, found_texts = load_found()
    found_rows = load_found_rows()
    direct_patches = load_direct_patch_texts()
    import json
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}
    written = overflow = wider = compact_shortened = deny = no_ko = code_region = no_slot = 0
    intentional_blank = 0
    # Phase B: encode_fit이 level 6~11(부호 제거 폴백)을 반환할 수 있음.
    levels = {k: 0 for k in range(12)}
    unmapped = collections.Counter()
    seen_import_addrs = set()
    written_addrs = set()

    def check_text(a, ko, ja, slot_override=None):
        nonlocal written, overflow, wider, compact_shortened
        enc, level = encode_fit(ko, slot_override or slots[a], syl_to_code, unmapped)
        if enc is None:
            overflow += 1
            return
        written += 1
        written_addrs.add(a)
        levels[level] += 1
        if level >= 6:
            # 부호 보존 후보가 모두 슬롯 초과 → ASCII 문장부호 제거 폴백 사용(가독성 손실).
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
            blank_override = a in ADDRESS_TEXT_OVERRIDES and ADDRESS_TEXT_OVERRIDES[a] == ''
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
            if blank_override:
                intentional_blank += 1
                written_addrs.add(a)
                continue
            if not ko:
                no_ko += 1
                continue
            ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
            slot_override = None
            if a in direct_patches:
                end, ko = direct_patches[a]
                slot_override = max(slots[a], end - a)
                ja = source_text_for_span(a, end, found_rows, found_texts.get(a, ja))
            check_text(a, ko, ja, slot_override=slot_override)

    for a, ko in sorted(ADDRESS_TEXT_OVERRIDES.items()):
        if a in seen_import_addrs or a < SAFE_MIN_ADDR or slots.get(a, 0) <= 0:
            continue
        if in_deny(a, a + slots[a]):
            continue
        slot_override = None
        if a in direct_patches:
            end, ko = direct_patches[a]
            slot_override = max(slots[a], end - a)
            ja = source_text_for_span(a, end, found_rows, found_texts.get(a, ''))
        else:
            ja = found_texts.get(a, '')
        check_text(a, ko, ja, slot_override=slot_override)

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
            slot_override = None
            if a in direct_patches:
                end, ko = direct_patches[a]
                slot_override = max(slot, end - a)
                ja = source_text_for_span(a, end, found_rows, row.get('text') or '')
            else:
                ja = row.get('text') or ''
            check_text(a, ko, ja, slot_override=slot_override)

    if os.path.exists(COMPREHENSIVE_TRANS):
        with open(COMPREHENSIVE_TRANS, newline='', encoding='utf-8', errors='replace') as f:
            for row in csv.DictReader(f):
                if row.get('status') != 'Translated':
                    continue
                try:
                    a = int(row.get('address', ''), 16)
                except (ValueError, TypeError):
                    continue
                if a in written_addrs or a in seen_import_addrs:
                    continue
                if not (0xA00000 <= a < 0xA40000):
                    continue
                ko = (row.get('korean') or '').strip()
                if not ko or ko == '미상' or not any('가' <= ch <= '힣' for ch in ko):
                    continue
                if a < SAFE_MIN_ADDR or slots.get(a, 0) <= 0:
                    continue
                if in_deny(a, a + slots[a]):
                    continue
                ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
                slot_override = None
                if a in direct_patches:
                    end, ko = direct_patches[a]
                    slot_override = max(slots[a], end - a)
                    ja = source_text_for_span(a, end, found_rows, found_texts.get(a, ''))
                else:
                    ja = found_texts.get(a, '')
                check_text(a, ko, ja, slot_override=slot_override)

    for a, (end, ko) in sorted(direct_patches.items()):
        if a in written_addrs or a in seen_import_addrs:
            continue
        if a < SAFE_MIN_ADDR or slots.get(a, 0) <= 0:
            continue
        if in_deny(a, a + slots[a]):
            continue
        ja = source_text_for_span(a, end, found_rows, found_texts.get(a, ''))
        check_text(a, ko, ja, slot_override=max(slots[a], end - a))

    print(f'written(한글 인코딩): {written}')
    print('fit levels: ' + ', '.join(f'level{k}={levels[k]}' for k in sorted(levels)))
    print(f'compact-shortened fallback: {compact_shortened}')
    print(f'overflow(슬롯초과 skip→원문): {overflow}')
    print(f'no_ko: {no_ko}, intentional_blank_override: {intentional_blank}, code_region: {code_region}, no_slot: {no_slot}, deny/data-skip: {deny}')
    print(f'visual-wider than JA: {wider} ({100*wider/max(written,1):.1f}%) — 박스폭 잠재리스크(대부분 ≤1글자/노이즈)')


if __name__ == '__main__':
    main()
