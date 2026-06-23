#!/usr/bin/env python3
"""translation_for_import.csv 무결성 검사(QA).

2026-06-24 적대적 리뷰(agy)가 발견한 CSV 손상(번역 꼬리잘림·length 필드에 다음
레코드 주소 혼입·행 병합)을 영구 가시화하기 위한 탐지기. 손상이 ROM에 반영되는지
판정하려고 dialogue_overrides.json(빌드 우선층)·game_wars_found_texts.csv(권위 슬롯)와
대조한다.

분류:
  bad_len        length 필드가 정수도 빈칸도 아님(예: '770x00A2C484')
  empty_len      length 필드 빈칸(+ korean 꼬리잘림 동반 다수)
  embedded_addr  korean 필드에 0x......가 끼어듦(행 병합 흔적)
  merged_newline korean 필드에 개행이 끼어듦(여러 레코드 병합)
  bad_addr       address 필드가 0x[6-8 hex] 형식 아님

심각도:
  rom_affecting  override 없음 → 손상 korean이 실제 빌드에 유입될 위험(원문/노이즈 잔존)
  masked         override 있음 → 빌드는 override 사용, CSV는 잠재 지뢰(위생 문제)

사용:
  python3 tools/qa_csv_integrity.py            # 요약 + temp/csv_integrity_report.tsv
  python3 tools/qa_csv_integrity.py --fail-on-rom-affecting   # ROM 영향분 있으면 비0 종료
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
OUT = os.path.join(BASE, 'temp', 'csv_integrity_report.tsv')

ADDR_RE = re.compile(r'0x[0-9A-Fa-f]{6,8}')
INT_RE = re.compile(r'\d+')


def norm_addr(a: str) -> str:
    try:
        return '0x%08X' % int(a, 16)
    except (ValueError, TypeError):
        return a


def classify(row: dict):
    a = (row.get('address') or '')
    ko = (row.get('korean') or '')
    L = (row.get('length') or '')
    if '\n' in ko or '\r' in ko:
        return 'merged_newline'
    if ADDR_RE.search(ko):
        return 'embedded_addr'
    if L and not INT_RE.fullmatch(L):
        return 'bad_len'
    if L == '':
        return 'empty_len'
    if not re.fullmatch(r'0x[0-9A-Fa-f]{6,8}', a):
        return 'bad_addr'
    return None


def region(a: str) -> str:
    try:
        x = int(a, 16)
    except (ValueError, TypeError):
        return 'bad_addr'
    if 0xA00000 <= x < 0xA40000:
        return 'part1_campaign'
    if 0xD80000 <= x < 0xE20000:
        return 'part_dialogue'
    if 0x800000 <= x < 0x810000:
        return 'compact_ui'
    return 'other'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--fail-on-rom-affecting', action='store_true')
    args = ap.parse_args()

    ov = json.load(open(OVERRIDES, encoding='utf-8')) if os.path.exists(OVERRIDES) else {}
    ovset = set(ov) | {norm_addr(k) for k in ov}

    rows = list(csv.DictReader(open(TRANS, encoding='utf-8')))
    findings = []
    for r in rows:
        c = classify(r)
        if not c:
            continue
        a = r.get('address', '')
        masked = (a in ovset) or (norm_addr(a) in ovset)
        findings.append((a, c, region(a), 'masked' if masked else 'rom_affecting',
                         (r.get('korean') or '')[:60]))

    by_kind = Counter(f[1] for f in findings)
    by_sev = Counter(f[3] for f in findings)
    by_region_rom = Counter(f[2] for f in findings if f[3] == 'rom_affecting')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('address\tkind\tregion\tseverity\tkorean_excerpt\n')
        for a, k, rg, sev, ko in findings:
            f.write(f'{a}\t{k}\t{rg}\t{sev}\t{ko}\n')

    print(f'총 손상행: {len(findings)}')
    print(f'  종류별: {dict(by_kind)}')
    print(f'  심각도: {dict(by_sev)}')
    print(f'  ROM 영향(override 없음) 지역별: {dict(by_region_rom)}')
    print(f'리포트: {OUT}')

    rom_aff = by_sev.get('rom_affecting', 0)
    if args.fail_on_rom_affecting and rom_aff:
        print(f'FAIL: ROM 영향 손상행 {rom_aff}건', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
