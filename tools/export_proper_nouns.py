#!/usr/bin/env python3
"""고유명사/용어 사전 추출기 — Game Wars 한글화용.

무라마사 한글화의 `tools/export_proper_nouns.py`를 aw-kor의 플랫 CSV
(`data/translation_for_import.csv`)에 맞춰 적응 이식.

무라마사는 섹션(scename/_itemdata)별로 뽑았지만 aw-kor는 평면 CSV라
전략을 바꿔, **용어 일관성**을 핵심으로 두 종류를 추출한다:

1. inconsistencies — 같은 일본어 원문(ja)이 2가지 이상의 한국어(ko)로 번역된 항목.
   (Wars 게임의 유닛/지형/CO명·UI 라벨은 일관돼야 함)
2. recurring_terms — 짧고 자주 나오는 ja(고유명사 후보). 현재 다수표기 ko + edit 칸.

출력: `data/proper_nouns.json`
각 항목의 `edit` 칸을 채우고 `tools/apply_proper_nouns.py`를 실행하면
CSV의 korean 필드에 일괄 반영된다.

사용:
  python tools/export_proper_nouns.py
  python tools/export_proper_nouns.py --min-count 3 --max-len 10
"""
import csv
import json
import os
import re
import argparse
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')
OUT_PATH = os.path.join(BASE, 'data', 'proper_nouns.json')

HEXTOK = re.compile(r'0x[0-9A-Fa-f]{2,}')
# 노이즈/플레이스홀더 후보 제외
NOISE = re.compile(r'(.)\1\1')


def norm(s):
    return (s or '').strip()


def looks_clean(ja, ko):
    """추출 노이즈·손상 행 제외."""
    if not ja or not ko:
        return False
    if HEXTOK.search(ko):
        return False
    if NOISE.search(ja):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--out', default=OUT_PATH)
    ap.add_argument('--min-count', type=int, default=3,
                    help='recurring_terms 최소 등장 횟수')
    ap.add_argument('--max-len', type=int, default=10,
                    help='고유명사 후보 ja 최대 길이(글자)')
    a = ap.parse_args()

    # ja -> Counter(ko)
    ja_to_ko = defaultdict(Counter)
    ja_count = Counter()
    with open(a.csv, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ja, ko = norm(r.get('japanese')), norm(r.get('korean'))
            if not looks_clean(ja, ko):
                continue
            ja_to_ko[ja][ko] += 1
            ja_count[ja] += 1

    # 1) 불일치: 같은 ja → 2개 이상 ko
    inconsistencies = []
    for ja, kos in ja_to_ko.items():
        if len(kos) >= 2:
            variants = [{'ko': k, 'n': n} for k, n in kos.most_common()]
            inconsistencies.append({
                'ja': ja,
                'variants': variants,
                'total': sum(kos.values()),
                'edit': '',   # 통일할 한국어를 적으면 모든 변형을 이걸로
            })
    # 변형 많고 자주 나오는 순
    inconsistencies.sort(key=lambda e: (-len(e['variants']), -e['total']))

    # 2) 반복 용어(고유명사 후보): 짧은 ja가 자주 등장 + 번역 일관(ko 1종)
    recurring = []
    for ja, n in ja_count.most_common():
        if n < a.min_count:
            continue
        if len(ja) > a.max_len:
            continue
        kos = ja_to_ko[ja]
        if len(kos) != 1:
            continue   # 불일치는 위 섹션에서 다룸
        ko = kos.most_common(1)[0][0]
        recurring.append({'ja': ja, 'ko': ko, 'n': n, 'edit': ''})

    # 3) 공용 용어(전역 치환): 사람이 직접 채워 쓰는 칸. 시드 비움.
    common_terms = []

    out = {
        '_readme': (
            '용어/고유명사 검토 파일. '
            'inconsistencies: 같은 일본어가 여러 한국어로 번역된 것 — edit에 통일안 입력. '
            'recurring_terms: 자주 나오는 고유명사 후보 — edit에 새 표기 입력. '
            'common_terms: 전역 find-replace — current/edit 쌍을 직접 추가. '
            '편집 후 tools/apply_proper_nouns.py 실행.'
        ),
        'counts': {
            'inconsistencies': len(inconsistencies),
            'recurring_terms': len(recurring),
            'common_terms': len(common_terms),
        },
        'inconsistencies': inconsistencies,
        'recurring_terms': recurring,
        'common_terms': common_terms,
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Wrote {a.out}')
    for k, v in out['counts'].items():
        print(f'  {k}: {v}')
    # 미리보기: 변형 많은 불일치 상위
    print('\n=== 불일치 상위 10 ===')
    for e in inconsistencies[:10]:
        vs = ' / '.join(f"{v['ko']}({v['n']})" for v in e['variants'])
        print(f"  {e['ja']!r} → {vs}")


if __name__ == '__main__':
    main()
