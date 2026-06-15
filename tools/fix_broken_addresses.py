#!/usr/bin/env python3
"""translation_for_import.csv의 손상 주소(예: '00x00A1100A') 복구.

증상: 일부 행의 address가 '00x...' 처럼 잘못된 접두로 손상되어 build_korean_full.py의
int(addr,16)가 실패 → st['bad_addr']로 조용히 드롭됨. 그 결과 유효한 한국어 번역이
ROM에 안 실린다(누락). 'x' 뒤 16진을 복구해 다음으로 분류:

  - duplicate : 복구 주소에 이미 정상 행이 있음 → 손상 행 제거(무해, 정상 행이 출하).
  - recovered : 복구 주소가 신규 + 한국어 보유 → address를 '0x%08X'로 교정(드롭됐던 번역 복구).
  - junk      : 복구 불가(비16진/범위초과) 또는 한국어 없음 → 제거.

기본 dry-run. --apply 로 CSV에 반영(git이 백업).
"""
import argparse
import csv
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')
PLACEHOLDERS = {'미상', '불명', '판독 불가', '판독불가', '의미 불명', '의미불명', '해독 불가', '해독불가', '번역 불가', '번역불가'}


def has_korean(s):
    return any('가' <= c <= '힣' for c in (s or ''))


def recover(addr):
    a = (addr or '').strip()
    h = a.rsplit('x', 1)[1] if 'x' in a else a
    try:
        v = int(h, 16)
        return v if 0 <= v <= 0xFFFFFF else None
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(CSV_PATH, encoding='utf-8', errors='ignore', newline='') as f:
        r = csv.DictReader(f)
        fields = r.fieldnames
        rows = list(r)

    valid = {}
    for row in rows:
        try:
            v = int((row.get('address') or '').strip(), 16)
            if v <= 0xFFFFFF:
                valid.setdefault(v, True)
        except ValueError:
            pass

    out = []
    st = {'kept': 0, 'recovered': 0, 'duplicate_removed': 0, 'junk_removed': 0}
    recovered_rows = []
    for row in rows:
        a = (row.get('address') or '').strip()
        try:
            v = int(a, 16)
            if v <= 0xFFFFFF:
                out.append(row); st['kept'] += 1; continue
        except ValueError:
            pass
        # 손상 주소
        ko = (row.get('korean') or '').strip()
        v = recover(a)
        if v is None or not has_korean(ko) or ko in PLACEHOLDERS:
            st['junk_removed'] += 1; continue
        if v in valid:
            st['duplicate_removed'] += 1; continue
        row['address'] = '0x%08X' % v
        valid[v] = True
        out.append(row); st['recovered'] += 1
        recovered_rows.append((row['address'], ko[:36]))

    print('=== 손상 주소 복구 ===')
    for k, n in st.items():
        print(f'  {k}: {n}')
    print('\n복구된 번역(드롭됐던 것):')
    for ad, ko in recovered_rows:
        print(f'  {ad} | {ko!r}')

    if args.apply:
        with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(out)
        print(f'\n[APPLIED] {CSV_PATH} ({len(out)}행, 복구 {st["recovered"]}, 중복/junk 제거 {st["duplicate_removed"]+st["junk_removed"]})')
    else:
        print('\n(dry-run) --apply 로 반영')


if __name__ == '__main__':
    main()
