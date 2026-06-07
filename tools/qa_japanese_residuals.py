#!/usr/bin/env python3
"""Audit likely Japanese text that still survives in the built ROM.

This checker is intentionally conservative:
- found_texts.csv is the extraction authority.
- translation_for_import.csv and build_korean_full overrides count as covered.
- the strongest residual signal is the original SJIS byte run still being present
  at the same ROM address in the built ROM.
"""
import argparse
import ast
import csv
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_ROM = BASE / 'output' / 'game_wars_korean_full.gba'
DEFAULT_FOUND = BASE / 'data' / 'game_wars_found_texts.csv'
DEFAULT_TRANS = BASE / 'data' / 'translation_for_import.csv'
DEFAULT_SUPP_TRANS = BASE / 'data' / 'translation_comprehensive.csv'
DEFAULT_REPORT = BASE / 'temp' / 'japanese_residuals_report.tsv'

sys.path.insert(0, str(BASE / 'tools'))
from build_korean_full import (  # noqa: E402
    ADDRESS_TEXT_OVERRIDES,
    SAFE_MIN_ADDR,
    SOURCE_TEXT_OVERRIDES,
    in_deny,
)

KANA_RE = re.compile(r'[ぁ-ゖァ-ヺー]')
HIRAGANA_RE = re.compile(r'[ぁ-ゖ]')
CJK_RE = re.compile(r'[一-龯㐀-䶿]')
PARTICLE_RE = re.compile(r'[のはをにがでとへもやか]')
PUNCT_RE = re.compile(r'[、。！？ー・…「」（）]')
JP_LETTER_RE = re.compile(r'[ぁ-ゖァ-ヺー一-龯㐀-䶿]')
HANGUL_RE = re.compile(r'[가-힣]')
BLANKISH_BYTES = frozenset((0x00, 0x09, 0x0A, 0x0D, 0x20, 0xFF))


def parse_range(value):
    if not value:
        return SAFE_MIN_ADDR, 0xF00000
    if ':' not in value:
        raise argparse.ArgumentTypeError('range must be START:END, e.g. A00000:F00000')
    start, end = value.split(':', 1)
    return int(start, 16), int(end, 16)


def load_translations(path):
    by_addr = {}
    ranges = []
    with path.open(newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            try:
                addr = int(row.get('address', ''), 16)
            except (TypeError, ValueError):
                continue
            try:
                length = int(row.get('length') or 0)
            except (TypeError, ValueError):
                length = 0
            japanese = (row.get('japanese') or '').strip()
            korean = (row.get('korean') or '').strip()
            by_addr[addr] = (japanese, korean)
            if korean and length > 0:
                ranges.append((addr, addr + length))
    ranges.sort()
    return by_addr, ranges


def load_supplemental_translations(path):
    """Load supplemental rows that build_korean_full imports from A0-A3."""
    by_addr = {}
    if not path.exists():
        return by_addr
    with path.open(newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            if row.get('status') != 'Translated':
                continue
            try:
                addr = int(row.get('address', ''), 16)
            except (TypeError, ValueError):
                continue
            if not (0xA00000 <= addr < 0xA40000):
                continue
            korean = (row.get('korean') or '').strip()
            if not korean or korean == '미상' or not HANGUL_RE.search(korean):
                continue
            by_addr[addr] = ((row.get('japanese') or '').strip(), korean)
    return by_addr


def load_direct_patch_texts():
    """Extract literal direct script patches from build_korean_full.py.

    The builder has many patch-script tuple lists of the form
    (0xSTART, 0xEND, 'Korean text', 'label') and fixed-width label tuples of
    the form (0xSTART, length, 'Korean text'). Some one-off rows are patched
    through helper calls or INTRO_DIRECT_TEXT. These rows bypass the import CSV
    but are still authoritative final-ROM translations, so the residual audit
    should count them as covered.
    """
    path = BASE / 'tools' / 'build_korean_full.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    patches = []

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
        if isinstance(start, int) and isinstance(end, int) and end > start and text and HANGUL_RE.search(text):
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


def covered_by_translation_range(addr, length, ranges):
    if length <= 0:
        return False
    end = addr + length
    for start, stop in ranges:
        if start > addr:
            return False
        if start <= addr and end <= stop:
            return True
    return False


def likely_symbol_noise(text):
    compact = ''.join(ch for ch in text.strip() if ch not in ' 　')
    if len(compact) < 6 or HIRAGANA_RE.search(compact):
        return False
    letter_count = len(JP_LETTER_RE.findall(compact))
    non_letter_count = len(compact) - letter_count
    return 0 < letter_count <= 2 and non_letter_count >= letter_count * 3


def score_candidate(text, char_count, same_original):
    score = 0
    if KANA_RE.search(text):
        score += 5
    if CJK_RE.search(text):
        score += 1
    if PARTICLE_RE.search(text):
        score += 3
    if PUNCT_RE.search(text):
        score += 2
    if char_count >= 6:
        score += 2
    if char_count >= 12:
        score += 2
    if same_original:
        score += 4
    if char_count <= 4 and not PARTICLE_RE.search(text) and not PUNCT_RE.search(text):
        score -= 3
    if likely_symbol_noise(text):
        score -= 8
    return score


def has_korean_reserved_pair(data):
    """Best-effort signal that the original SJIS row was overwritten by Hangul.

    The project maps Hangul syllables into reserved two-byte codes from
    0x8840..0x9369. Interpreting those bytes as Shift-JIS often looks like
    random kanji, so this is a stronger signal than decoded text.
    """
    for i in range(0, max(len(data) - 1, 0)):
        code = (data[i] << 8) | data[i + 1]
        if 0x8840 <= code <= 0x9369:
            return True
    return False


def classify_current(data):
    if has_korean_reserved_pair(data):
        return 'changed_hangul'
    if not data or all(b in BLANKISH_BYTES for b in data):
        return 'changed_blank'
    if all(b in BLANKISH_BYTES or 0x21 <= b <= 0x7E for b in data):
        return 'changed_ascii'
    try:
        decoded = data.decode('shift_jis', errors='ignore')
    except LookupError:
        decoded = ''
    if decoded and not (KANA_RE.search(decoded) or CJK_RE.search(decoded)):
        return 'changed_symbol'
    return 'changed_other'


def classify_row(row, translations, translation_ranges, direct_patches, rom, start_addr, end_addr):
    try:
        addr = int(row['address'], 16)
        length = int(row.get('length') or 0)
        char_count = int(row.get('char_count') or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if addr < start_addr or addr >= end_addr or length <= 0 or addr + length > len(rom):
        return None
    if in_deny(addr, addr + length):
        return None

    text = (row.get('text') or '').strip()
    if not (KANA_RE.search(text) or CJK_RE.search(text)):
        return None

    if addr in ADDRESS_TEXT_OVERRIDES:
        return ('covered', addr, length, char_count, text, 'address_override', 0, False)
    if addr in direct_patches:
        return ('covered', addr, length, char_count, text, 'direct_patch', 0, False)
    if addr in translations and translations[addr][1]:
        return ('covered', addr, length, char_count, text, 'translation_csv', 0, False)
    if text in SOURCE_TEXT_OVERRIDES:
        return ('covered', addr, length, char_count, text, 'source_override', 0, False)

    try:
        original = bytes.fromhex(row.get('hex_bytes') or '')
    except ValueError:
        original = b''
    current = rom[addr:addr + len(original)] if original else b''
    same_original = bool(original) and current == original
    current_kind = 'same_original'
    if not same_original:
        if covered_by_translation_range(addr, length, translation_ranges):
            return ('covered', addr, length, char_count, text, 'translation_overlap', 0, False)
        current_kind = classify_current(current)
    score = score_candidate(text, char_count, same_original)
    return ('missing', addr, length, char_count, text, '-', score, same_original, current_kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', type=Path, default=DEFAULT_ROM)
    ap.add_argument('--found', type=Path, default=DEFAULT_FOUND)
    ap.add_argument('--translations', type=Path, default=DEFAULT_TRANS)
    ap.add_argument('--supp-translations', type=Path, default=DEFAULT_SUPP_TRANS)
    ap.add_argument('--out', type=Path, default=DEFAULT_REPORT)
    ap.add_argument('--range', dest='scan_range', type=parse_range, default=parse_range(None))
    ap.add_argument('--min-score', type=int, default=7)
    ap.add_argument('--limit', type=int, default=120)
    ap.add_argument(
        '--include-changed',
        action='store_true',
        help='include uncovered rows whose original bytes are already changed',
    )
    ap.add_argument(
        '--same-only',
        action='store_true',
        help='deprecated alias for the default residual-only candidate view',
    )
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    translations, translation_ranges = load_translations(args.translations)
    translations.update(load_supplemental_translations(args.supp_translations))
    direct_patches = load_direct_patch_texts()
    start_addr, end_addr = args.scan_range

    covered = []
    missing = []
    with args.found.open(newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            item = classify_row(row, translations, translation_ranges, direct_patches, rom, start_addr, end_addr)
            if not item:
                continue
            if item[0] == 'covered':
                covered.append(item)
            else:
                missing.append(item)

    candidates = [
        item for item in missing
        if item[6] >= args.min_score and (args.include_changed or item[7])
    ]
    candidates.sort(key=lambda x: (x[6], x[7], x[1]), reverse=True)

    same_count = sum(1 for item in missing if item[7])
    kind_counts = {}
    for item in missing:
        if len(item) > 8:
            kind_counts[item[8]] = kind_counts.get(item[8], 0) + 1
    print(f'range=0x{start_addr:06X}:0x{end_addr:06X}')
    print(
        f'covered={len(covered)} uncovered={len(missing)} '
        f'same_original={same_count} '
        + ' '.join(
            f'{kind}={count}'
            for kind, count in sorted(kind_counts.items())
            if kind != 'same_original'
        )
    )
    print(
        f'candidates(score>={args.min_score}, '
        f'include_changed={args.include_changed})={len(candidates)}'
    )
    for item in candidates[:args.limit]:
        _, addr, length, char_count, text, _reason, score, same_original, current_kind = item
        print(
            f'score={score:02d} same={int(same_original)} {current_kind:15s} '
            f'0x{addr:06X} len={length:03d} chars={char_count:03d} '
            f'txt={text[:100]!r}'
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8', newline='') as f:
        f.write('status\taddr\tlength\tchars\treason\tscore\tsame_original\tcurrent_kind\ttext\n')
        for item in covered:
            _, addr, length, char_count, text, reason, score, same_original = item
            f.write(
                f'covered\t0x{addr:06X}\t{length}\t{char_count}\t'
                f'{reason}\t{score}\t{int(same_original)}\tcovered\t{text}\n'
            )
        for item in sorted(missing, key=lambda x: (x[6], x[7], x[1]), reverse=True):
            _, addr, length, char_count, text, reason, score, same_original, current_kind = item
            status = 'residual' if same_original else 'changed_uncovered'
            f.write(
                f'{status}\t0x{addr:06X}\t{length}\t{char_count}\t'
                f'{reason}\t{score}\t{int(same_original)}\t{current_kind}\t{text}\n'
            )
    print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
