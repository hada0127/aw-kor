#!/usr/bin/env python3
"""Prepare a batch of untranslated texts split into N agent input files.

Usage: python tools/loop_prepare_batch.py [BATCH_SIZE] [NUM_AGENTS]
Defaults: BATCH_SIZE=450, NUM_AGENTS=3

Writes data/_work/in_1.csv .. in_N.csv with columns: address,japanese,char_count
Untranslated texts are sorted by char_count ascending (shortest first).
"""
import csv
import re
import sys
from pathlib import Path

BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 450
NUM_AGENTS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

DATA = Path('data')
WORK = DATA / '_work'
WORK.mkdir(exist_ok=True)

# --- real-text filter -------------------------------------------------
# The source extraction contains many false positives (random kanji mixed
# with Cyrillic, math symbols, iteration marks). Only translate coherent
# Japanese: dialogue/system messages (hiragana + particles) or clean
# katakana unit/menu names. Garbage is skipped to avoid polluting the ROM.
_CYR = re.compile(r'[Ѐ-ӿ]')
_WEIRD = re.compile(r'[÷×∇∂∪∩β∮…‥仝]')
_ITER = re.compile(r'[ゝゞ〃々]')
_PARTICLE = re.compile(r'(は|を|が|の|に|へ|と|で|です|ます|した|する|ない|だ|よ|ね|わ|！|？)')


def _real_hira(t):
    return len(re.findall(r'[ぁ-ゖ]', t))


def _kata(t):
    return len(re.findall(r'[ァ-ヴー]', t))


def is_real(t):
    if not t:
        return False
    if _CYR.search(t) or _WEIRD.search(t) or _ITER.search(t):
        return False
    if _real_hira(t) >= 3 and _PARTICLE.search(t):
        return True
    letters = [c for c in t if not c.isspace()]
    if letters and _kata(t) >= 3 and _kata(t) / len(letters) >= 0.6:
        return True
    return False


def load_translated():
    translated = set()
    f = DATA / 'translation_for_import.csv'
    if f.exists():
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for row in csv.DictReader(fh):
                a = (row.get('address') or '').strip()
                k = (row.get('korean') or '').strip()
                if a and k:
                    translated.add(a)
    return translated


def load_source():
    texts = []
    with open(DATA / 'game_wars_found_texts.csv', encoding='utf-8', errors='ignore') as fh:
        for row in csv.DictReader(fh):
            texts.append(row)
    return texts


def main():
    translated = load_translated()
    src = load_source()
    unt = [t for t in src
           if (t.get('address') or '').strip()
           and (t.get('address') or '').strip() not in translated
           and is_real((t.get('text') or '').strip())]

    def cc(t):
        try:
            return int(t.get('char_count') or 0)
        except ValueError:
            return 0
    unt.sort(key=lambda t: (cc(t), t.get('address')))

    batch = unt[:BATCH_SIZE]
    total_unt = len(unt)

    # clear old work files
    for p in WORK.glob('in_*.csv'):
        p.unlink()
    for p in WORK.glob('out_*.txt'):
        p.unlink()

    # split round-robin so each agent gets a mix of lengths
    parts = [[] for _ in range(NUM_AGENTS)]
    for i, item in enumerate(batch):
        parts[i % NUM_AGENTS].append(item)

    for idx, part in enumerate(parts, start=1):
        with open(WORK / f'in_{idx}.csv', 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['address', 'japanese', 'char_count'])
            for t in part:
                w.writerow([t.get('address', ''), t.get('text', ''), t.get('char_count', '')])

    print(f"untranslated_remaining={total_unt}")
    print(f"batch_size={len(batch)}")
    for idx, part in enumerate(parts, start=1):
        print(f"in_{idx}.csv={len(part)} rows")


if __name__ == '__main__':
    main()
