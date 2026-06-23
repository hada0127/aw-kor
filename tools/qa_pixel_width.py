#!/usr/bin/env python3
"""렌더러 advance 기반 픽셀폭 검증(QA).

분석가 지적("픽셀폭 검증 미완")을 닫기 위한 정식 도구. 바이트 예산 하드게이트
(encoded_len ≤ slot)는 슬롯 용량만 보장하고 화면 박스 폭은 보장하지 않는다.
이 도구는 대화/UI 렌더러의 실제 글리프 advance를 모델링해 "한글 번역이 원문
일본어보다 픽셀 폭이 넓어 박스를 넘칠 위험"을 전수 검출한다.

렌더러 모델(docs/research.md: 변환 루틴 0x08EFE788, 기본 width ip=8, ASCII는 ip=1 분기):
  - 한글 완성형 / 전각 가나·한자 / 전각기호 = 8px (1 타일 셀)
  - ASCII printable / 반각공백 = 4px (반각, ip=1 분기 근사)
  - 제어/세그먼트 마커(0x0A 등)는 advance 0 으로 본다(줄 분리).

판정: 같은 슬롯(같은 박스)에서 width(KO) > width(JA) 이면 픽셀폭 초과 위험.
바이트 게이트를 통과한(=실제 빌드되는) 행만 본다. 코드영역/DENY/슬롯미상 제외.

사용:
  python3 tools/qa_pixel_width.py            # 요약 + temp/pixel_width_report.tsv
  python3 tools/qa_pixel_width.py --top 40   # 위험 상위 N 출력
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))

from build_korean_full import SYLCODE, encode_fit  # noqa: E402

TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
OUT = os.path.join(BASE, 'temp', 'pixel_width_report.tsv')

SAFE_MIN_ADDR = 0x800000


def glyph_px(ch: str) -> int:
    o = ord(ch)
    if ch in ('\n', '\r'):
        return 0
    if ch == '　':          # 전각 공백
        return 8
    if ch == ' ':               # 반각 공백
        return 4
    if 0x20 <= o <= 0x7E:       # ASCII printable (반각)
        return 4
    return 8                    # 한글/전각 가나·한자·기호


def pixel_width(s: str) -> int:
    return sum(glyph_px(c) for c in s)


def load_slots() -> dict:
    slots = {}
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
            except (ValueError, TypeError):
                continue
            try:
                slots[a] = int(r.get('length') or 0)
            except ValueError:
                slots[a] = 0
    return slots


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=25)
    args = ap.parse_args()

    slots = load_slots()
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}
    overrides = json.load(open(OVERRIDES, encoding='utf-8')) if os.path.exists(OVERRIDES) else {}
    unmapped: dict = {}

    checked = wider = built = 0
    rows = []
    seen = set()

    def consider(addr_int: int, ja: str, ko: str):
        nonlocal checked, wider, built
        if not ko or not ja:
            return
        if addr_int < SAFE_MIN_ADDR:
            return
        slot = slots.get(addr_int)
        if not slot or slot <= 0:
            return
        enc, level = encode_fit(ko, slot, syl_to_code, unmapped)
        if enc is None:           # 바이트 게이트 탈락(빌드 안 됨) → 제외
            return
        built += 1
        checked += 1
        wj, wk = pixel_width(ja), pixel_width(ko)
        if wk > wj:
            wider += 1
            rows.append((addr_int, wk - wj, wj, wk, level, ja, ko))

    # dialogue_overrides 우선, 없으면 translation_for_import
    with open(TRANS, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                a = int(r['address'], 16)
            except (ValueError, KeyError, TypeError):
                continue
            seen.add(a)
            ja = (r.get('japanese') or '').strip()
            akey = '0x%08X' % a
            ko = overrides.get(akey, overrides.get(r['address'], (r.get('korean') or '').strip()))
            consider(a, ja, ko)

    rows.sort(key=lambda x: x[1], reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('addr\tdelta_px\tja_px\tko_px\tfit_level\tja\tko\n')
        for a, d, wj, wk, lv, ja, ko in rows:
            f.write(f'0x{a:08X}\t{d}\t{wj}\t{wk}\t{lv}\t{ja}\t{ko}\n')

    print(f'built(바이트게이트 통과) 행: {built}')
    print(f'픽셀폭 KO>JA(박스폭 잠재초과): {wider}  ({100*wider/max(checked,1):.2f}%)')
    print(f'리포트: {OUT}')
    print(f'\n=== 위험 상위 {args.top} (delta_px desc) ===')
    for a, d, wj, wk, lv, ja, ko in rows[:args.top]:
        print(f'0x{a:08X}  +{d}px  JA[{wj}]={ja[:24]!r}  KO[{wk}]={ko[:24]!r}')


if __name__ == '__main__':
    main()
