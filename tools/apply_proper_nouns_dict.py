#!/usr/bin/env python3
"""data/proper_nouns.json (카테고리형) 의 편집을 translation_for_import.csv 에 적용.

tools/export_proper_nouns_dict.py 가 만든 카테고리형 사전을 입력으로 받는다.
muramasa-kor `tools/apply_proper_nouns.py` 의 적용 전략(정확치환 + 부분문자열
캐스케이드 + 공통어 전역치환)을 aw-kor 평면 CSV 에 맞춰 미러.

적용 규칙
  - characters / nations / places / discovered_candidates
      각 행의 `edit` 가 비어있지 않으면:
        (a) japanese == ja 인 행의 korean 을 edit 로 통일,
        (b) 기존 ko(또는 variants 의 한글 표기)를 대사 전역 부분문자열로 edit 로
            치환(대사 내 참조 일관화).
  - common_terms
      {current, edit} 쌍을 한국어 전역 find-replace. (슬래시로 다중 쌍 가능)

기본은 미리보기(dry-run). 실제 반영은 --apply.

사용:
  python3 tools/apply_proper_nouns_dict.py            # dry-run
  python3 tools/apply_proper_nouns_dict.py --apply    # CSV 반영
"""
import argparse
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')
PN_PATH = os.path.join(BASE, 'data', 'proper_nouns.json')

HANGUL_RE = re.compile(r'[가-힣]')


def norm(s):
    return (s or '').strip()


def collect_edits(pn):
    """반환: (ja_override{ja:new_ko}, sub_pairs[(old,new)])."""
    ja_override = {}
    sub_pairs = []
    seen_pairs = set()

    def add_pair(old, new):
        if old and new and old != new and (old, new) not in seen_pairs:
            seen_pairs.add((old, new))
            sub_pairs.append((old, new))

    for cat in ('characters', 'nations', 'places', 'discovered_candidates'):
        for e in pn.get(cat, []):
            ed = norm(e.get('edit'))
            if not ed:
                continue
            ja = norm(e.get('ja'))
            if ja:
                ja_override[ja] = ed
            old_ko = norm(e.get('ko'))
            if old_ko:
                add_pair(old_ko, ed)
            # variants 에 등장한 한글 표기들도 통일 대상으로 캐스케이드
            for v in (e.get('variants') or {}):
                if HANGUL_RE.search(v):
                    add_pair(norm(v), ed)

    for e in pn.get('common_terms', []):
        cur = norm(e.get('current'))
        ed = norm(e.get('edit'))
        if not cur or not ed or cur == ed:
            continue
        cs = [t.strip() for t in cur.split('/') if t.strip()]
        es = [t.strip() for t in ed.split('/') if t.strip()]
        if len(cs) == len(es):
            for o, n in zip(cs, es):
                add_pair(o, n)
        else:
            add_pair(cur, ed)

    # 긴 old 를 먼저 치환(부분 겹침으로 인한 오치환 방지)
    sub_pairs.sort(key=lambda p: -len(p[0]))
    return ja_override, sub_pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--pn', default=PN_PATH)
    ap.add_argument('--apply', action='store_true', help='실제 CSV 반영 (없으면 dry-run)')
    a = ap.parse_args()

    with open(a.pn, encoding='utf-8') as f:
        pn = json.load(f)

    ja_override, sub_pairs = collect_edits(pn)
    if not ja_override and not sub_pairs:
        print('적용할 편집이 없습니다. proper_nouns.json 의 edit 칸을 채우세요.')
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
        if ja in ja_override and norm(ko) != ja_override[ja]:
            new_ko = ja_override[ja]
            stats['ja_override'] += 1
        else:
            changed = False
            for old, new in sub_pairs:
                if old in new_ko:
                    new_ko = new_ko.replace(old, new)
                    changed = True
            if changed:
                stats['substring'] += 1
        if new_ko != ko:
            if len(samples) < 15:
                samples.append((r.get('address', ''), ko[:40], new_ko[:40]))
            r['korean'] = new_ko

    print(f"ja 정확치환 {stats['ja_override']}행 / 부분문자열치환 {stats['substring']}행")
    if samples:
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
        print('\n[DRY-RUN] --apply 로 실제 반영')


if __name__ == '__main__':
    main()
