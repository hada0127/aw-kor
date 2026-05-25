#!/usr/bin/env python3
"""hex_token 손상 행 복구 — Game Wars 한글화용.

추출/병합 단계에서 포인터 주소가 korean 필드에 새어든 손상 행
(예: "에 대해 기0x00D9AD98", length 칸에 일본어)을 복구한다.
lint_translation.py 의 hex_token error 250행을 0으로 만드는 게 목표.

손상 특징
- korean 에 `0x[0-9A-F]+` 토큰 누출(번역 truncate + 주소 append)
- length 가 비숫자(원래 숫자여야 함) — 거의 전부
- 일부 address 가 중복/이중(`00x..`, `0x000x..`)

복구 결정트리 (행은 삭제하지 않고 in-place 수정 — git diff 검토 쉬움)
1) 같은 진짜주소의 정상행이 이미 있음  → korean="" (중복 제거)
2) 노이즈(일본어에 가나 없음=무작위 한자)   → korean="" (추출 쓰레기)
3) 진짜 텍스트 + 같은 일본어의 정상 번역 존재 → 그 번역 복사 + length 복원
4) 진짜 텍스트 + 정상번역 없음               → hex/병합junk 제거한 부분번역만 남기고
                                              `--retrans-list` 로 재번역 대상 출력
모든 행: address 이중화 정리, length 를 SJIS 바이트수로 복원.

사용:
  python tools/repair_hex_corruption.py                          # 미리보기
  python tools/repair_hex_corruption.py --retrans-list temp/retrans.csv
  python tools/repair_hex_corruption.py --apply
"""
import csv
import os
import re
import argparse
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')

HEXTOK = re.compile(r'0x[0-9A-Fa-f]{2,}')
KANA = re.compile('[぀-ヿ]')
ADDR8 = re.compile(r'0x[0-9A-Fa-f]{6,8}')


def addr_ok(a):
    return bool(re.fullmatch(r'0x[0-9A-Fa-f]{6,8}', a or ''))


def true_addr(a):
    ms = ADDR8.findall(a or '')
    return ms[-1] if ms else (a or '')


def sjis_len(ja):
    try:
        return len(ja.encode('shift_jis', errors='ignore'))
    except Exception:
        return 0


def strip_korean(ko):
    """korean 에서 hex 토큰과 그 뒤 병합 junk(쉼표로 붙은 일본어/추가내용) 제거.

    'A0x..,B,C' → 첫 hex 토큰 앞까지만 남긴다. 부분 번역 보존용."""
    m = HEXTOK.search(ko)
    if m:
        ko = ko[:m.start()]
    return ko.rstrip(' ,、，')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--retrans-list', default=None,
                    help='재번역 대상 CSV 출력 경로 (address,japanese,partial_ko,length)')
    ap.add_argument('--limit', type=int, default=12)
    a = ap.parse_args()

    with open(a.csv, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # 삽입가능 정상행 인덱스
    clean_addrs = set()
    ja_clean = {}
    for r in rows:
        a_, ja, ko, ln = r['address'], r['japanese'], r['korean'], (r['length'] or '')
        if addr_ok(a_) and ln.strip().isdigit() and ko.strip() \
                and not HEXTOK.search(ko) and not KANA.search(ko):
            clean_addrs.add(a_)
            ja_clean.setdefault(ja, (ko, ln.strip()))

    stat = Counter()
    samples = []
    retrans = []
    for r in rows:
        ko = r['korean'] or ''
        if not HEXTOK.search(ko):
            continue
        ja = r['japanese'] or ''
        old_addr = r['address']
        ta = true_addr(old_addr)
        old = (old_addr, ko, r['length'])
        # 주소는 건드리지 않는다. malformed 주소는 어차피 삽입 안 되며,
        # de-double 추정이 틀려 falsely-valid 주소를 만들 위험이 있다.
        # length 복원(SJIS 바이트수)
        budget = sjis_len(ja)
        if budget > 0:
            r['length'] = str(budget)
        # korean 결정
        ja_only_kana = bool(ja) and not re.search(r'[一-鿿㐀-䶿]', ja) and KANA.search(ja)
        if ta in clean_addrs:
            r['korean'] = ''
            cat = 'clear_dup'
        elif not KANA.search(ja):
            r['korean'] = ''
            cat = 'clear_noise'
        elif HEXTOK.search(ja):
            r['korean'] = ''          # 원문 자체가 손상(hex 포함) → 번역 불가
            cat = 'clear_corrupt_src'
        elif ja_only_kana and len(ja) > 20:
            r['korean'] = ''          # 카타카나 고주온 그리드 표(번역 대상 아님)
            cat = 'clear_grid'
        elif ja in ja_clean:
            r['korean'] = ja_clean[ja][0]
            r['length'] = ja_clean[ja][1]
            cat = 'copy_clean'
        else:
            r['korean'] = strip_korean(ko)
            cat = 'retrans'
            retrans.append({'address': r['address'], 'japanese': ja,
                            'partial_ko': r['korean'], 'length': r['length']})
        stat[cat] += 1
        if len(samples) < a.limit:
            samples.append((cat, old[0], r['address'], ja[:26], old[1][:30], r['korean'][:30]))

    total = sum(stat.values())
    print(f'hex 손상 {total}행 복구:')
    for k, v in stat.most_common():
        print(f'  {k:12} {v}')
    print('\n샘플:')
    for cat, oa, na, ja, oko, nko in samples:
        print(f"  [{cat}] addr {oa}→{na} ja={ja!r}")
        print(f"      - {oko!r}\n      + {nko!r}")

    if a.retrans_list and retrans:
        with open(a.retrans_list, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['address', 'japanese', 'partial_ko', 'length'])
            w.writeheader(); w.writerows(retrans)
        print(f'\n재번역 대상 {len(retrans)}행 → {a.retrans_list}')

    if a.apply:
        with open(a.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader(); w.writerows(rows)
        print(f'\n[APPLIED] {a.csv}')
    else:
        print('\n[DRY-RUN] --apply 로 실제 적용')


if __name__ == '__main__':
    main()
