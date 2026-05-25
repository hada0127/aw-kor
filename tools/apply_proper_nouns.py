#!/usr/bin/env python3
"""data/proper_nouns.json의 사용자 편집을 translation_for_import.csv에 역적용.

무라마사 한글화의 `tools/apply_proper_nouns.py`를 aw-kor 평면 CSV에 맞춰 적응 이식.

적용 규칙
- inconsistencies[].edit  : 비어있지 않으면, 그 ja와 정확히 일치하는 모든 행의 ko를 edit로 통일.
- recurring_terms[].edit  : 비어있지 않으면, (a) ja 정확 일치 행 ko를 edit로, (b) 기존 ko를
                            전역 부분문자열로 edit로 치환(대사 내 참조 일관화).
- common_terms[]          : {current, edit} 쌍을 전역 find-replace. (슬래시로 여러 쌍 가능)

기본은 미리보기(dry-run). 실제 적용은 --apply.

사용:
  python tools/apply_proper_nouns.py            # 미리보기
  python tools/apply_proper_nouns.py --apply    # CSV에 적용
"""
import csv
import json
import os
import argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')
PN_PATH = os.path.join(BASE, 'data', 'proper_nouns.json')


def norm(s):
    return (s or '').strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--pn', default=PN_PATH)
    ap.add_argument('--apply', action='store_true', help='실제 CSV 적용 (없으면 dry-run)')
    a = ap.parse_args()

    pn = json.load(open(a.pn, encoding='utf-8'))

    # ja 정확 일치 override 맵: ja -> new_ko
    ja_override = {}
    # 전역 부분문자열 치환 쌍: (old, new)
    sub_pairs = []

    for e in pn.get('inconsistencies', []):
        ed = norm(e.get('edit'))
        if ed:
            ja_override[e['ja']] = ed

    for e in pn.get('recurring_terms', []):
        ed = norm(e.get('edit'))
        if ed:
            ja_override[e['ja']] = ed
            old_ko = norm(e.get('ko'))
            if old_ko and old_ko != ed:
                sub_pairs.append((old_ko, ed))

    for e in pn.get('common_terms', []):
        cur = norm(e.get('current'))
        ed = norm(e.get('edit'))
        if not cur or not ed or cur == ed:
            continue
        cs = [t.strip() for t in cur.split('/') if t.strip()]
        es = [t.strip() for t in ed.split('/') if t.strip()]
        if len(cs) == len(es):
            sub_pairs.extend(zip(cs, es))
        else:
            sub_pairs.append((cur, ed))

    if not ja_override and not sub_pairs:
        print('적용할 편집이 없습니다. proper_nouns.json의 edit 칸을 채우세요.')
        return

    with open(a.csv, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    stats = {'ja_override': 0, 'substring': 0}
    samples = []
    for r in rows:
        ja = norm(r.get('japanese'))
        ko = r.get('korean') or ''
        new_ko = ko
        # 1) ja 정확 일치 override (우선)
        if ja in ja_override and norm(ko) != ja_override[ja]:
            new_ko = ja_override[ja]
            stats['ja_override'] += 1
        else:
            # 2) 부분문자열 치환
            changed = False
            for old, new in sub_pairs:
                if old and old in new_ko:
                    new_ko = new_ko.replace(old, new); changed = True
            if changed:
                stats['substring'] += 1
        if new_ko != ko:
            if len(samples) < 15:
                samples.append((r.get('address', ''), ko[:40], new_ko[:40]))
            r['korean'] = new_ko

    print(f"ja 정확치환 {stats['ja_override']}행 / 부분문자열치환 {stats['substring']}행")
    print('\n샘플:')
    for addr, old, new in samples:
        print(f"  {addr}\n    - {old!r}\n    + {new!r}")

    if a.apply:
        with open(a.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f'\n[APPLIED] {a.csv}')
    else:
        print('\n[DRY-RUN] --apply 로 실제 적용')


if __name__ == '__main__':
    main()
