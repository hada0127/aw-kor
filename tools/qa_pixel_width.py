#!/usr/bin/env python3
"""렌더러 advance 기반 픽셀폭 검증(QA).

분석가 지적("픽셀폭 검증 미완")을 좁히기 위한 정적 보조 도구. 바이트 예산 하드게이트
(encoded_len ≤ slot)는 슬롯 용량만 보장하고 화면 박스 폭은 보장하지 않는다.
이 도구는 대화/UI 렌더러의 실제 글리프 advance를 모델링해 "한글 번역이 원문
일본어보다 픽셀 폭이 넓어 박스를 넘칠 위험"을 전수 검출한다.

렌더러 모델(docs/research.md: 변환 루틴 0x08EFE788, 기본 width ip=8, ASCII는 ip=1 분기):
  - 한글 완성형 / 전각 가나·한자 / 전각기호 = 8px (1 타일 셀)
  - ASCII printable / 반각공백 = 4px (반각, ip=1 분기 근사)
  - 제어/세그먼트 마커(0x0A 등)는 advance 0 으로 본다(줄 분리).

판정:
  - 같은 슬롯(같은 박스)에서 width(KO) > width(JA)이면 픽셀폭 초과 위험.
  - 실제 encode_fit 결과의 줄 폭이 --max-cells를 넘으면 별도 후보로 기록.
바이트 게이트를 통과한(=실제 빌드되는) 행만 본다. dialogue_overrides와 직접
패치 텍스트를 반영하고, 코드영역/DENY/슬롯미상/placeholder는 제외한다.
주의: --max-cells 기본값 50은 대사 박스용 전역 기준이다. 메뉴/도움말/CO 파워명
같은 UI 테이블은 더 좁을 수 있으므로, 초과/근접 후보는 fresh capture와 UI별
허용폭 산정 전까지 안전 판정으로 쓰면 안 된다.

사용:
  python3 tools/qa_pixel_width.py            # 요약 + temp/pixel_width_report.tsv
  python3 tools/qa_pixel_width.py --top 40   # 위험 상위 N 출력
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))

from build_korean_full import (  # noqa: E402
    ADDRESS_TEXT_OVERRIDES,
    COMPREHENSIVE_TRANS,
    PLACEHOLDER_KO,
    SAFE_MIN_ADDR,
    SOURCE_TEXT_OVERRIDES,
    SYLCODE,
    TEXT_OVERRIDES,
    encode_fit,
    in_deny,
)
import qa_text_fit as QTF  # noqa: E402

TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
OUT = os.path.join(BASE, 'temp', 'pixel_width_report.tsv')
SCENE_CATALOG = os.path.join(BASE, 'data', 'scene_catalog.json')

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


def encoded_cells(raw: bytes) -> int:
    """Final encoded byte stream width in half-cell units.

    This follows the runtime renderer model used by text_metrics.visual_cells:
    SJIS/reserved two-byte codes occupy one 8px cell (=2 half-cells), ASCII
    occupies one 4px half-cell, and line/control terminators do not advance.
    """
    i = 0
    cur = 0
    best = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x00, 0x0A):
            best = max(best, cur)
            cur = 0
            i += 1
        elif 0x81 <= b <= 0xE2 and i + 1 < len(raw):
            cur += 2
            i += 2
        elif 0x20 <= b <= 0x7E:
            cur += 1
            i += 1
        else:
            i += 1
    return max(best, cur)


def load_scene_ranges() -> list[tuple[int, int, str, str]]:
    if not os.path.exists(SCENE_CATALOG):
        return []
    data = json.load(open(SCENE_CATALOG, encoding='utf-8'))
    ranges = []
    for scene in data.get('scenes', []):
        dialogue_filter = scene.get('dialogue_filter') or {}
        regions = ','.join(dialogue_filter.get('regions') or [])
        scene_id = scene.get('id') or ''
        for start, end in dialogue_filter.get('addr_ranges') or []:
            if isinstance(start, int) and isinstance(end, int) and end > start:
                ranges.append((start, end, scene_id, regions))
    return ranges


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--max-cells', type=int, default=50,
                    help='대사 박스 한 줄 half-cell 한계(기본 50 = 200px). 초과 행을 별도 집계한다.')
    ap.add_argument('--fail-over-max-cells', action='store_true',
                    help='최종 encode_fit 결과가 --max-cells를 초과하면 종료코드 1.')
    args = ap.parse_args()

    slots, found_texts = QTF.load_found()
    scene_ranges = load_scene_ranges()
    found_rows = QTF.load_found_rows()
    direct_patches = QTF.load_direct_patch_texts()
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}
    overrides = json.load(open(OVERRIDES, encoding='utf-8')) if os.path.exists(OVERRIDES) else {}
    unmapped = collections.Counter()

    checked = wider = built = over_max = 0
    rows = []
    max_rows = []
    seen_import_addrs = set()
    written_addrs = set()

    def scene_hint(addr_int: int) -> str:
        hits = [
            f'{scene_id}({regions or "-"})'
            for start, end, scene_id, regions in scene_ranges
            if start <= addr_int < end
        ]
        return ';'.join(hits)

    def has_hangul(text: str) -> bool:
        return any('가' <= ch <= '힣' for ch in text)

    def consider(addr_int: int, ja: str, ko: str, slot_override: int | None = None):
        nonlocal checked, wider, built, over_max
        if not ko or not ja:
            return
        if addr_int < SAFE_MIN_ADDR:
            return
        slot = slot_override or slots.get(addr_int)
        if not slot or slot <= 0:
            return
        enc, level = encode_fit(ko, slot, syl_to_code, unmapped, addr_int)
        if enc is None:           # 바이트 게이트 탈락(빌드 안 됨) → 제외
            return
        built += 1
        checked += 1
        wj, wk = pixel_width(ja), pixel_width(ko)
        cells = encoded_cells(enc)
        hint = scene_hint(addr_int)
        if cells > args.max_cells:
            over_max += 1
            max_rows.append((addr_int, cells, args.max_cells, level, hint, ja, ko))
        if wk > wj:
            wider += 1
            rows.append((addr_int, wk - wj, wj, wk, cells, level, hint, ja, ko))

    def submit(addr_int: int, ja: str, ko: str, slot_override: int | None = None):
        slot_for_filter = slot_override or slots.get(addr_int, 0)
        if addr_int < SAFE_MIN_ADDR or not slot_for_filter or slot_for_filter <= 0:
            return
        if in_deny(addr_int, addr_int + slot_for_filter):
            return
        if ko.strip() in PLACEHOLDER_KO:
            return
        if not has_hangul(ko):
            return
        before = built
        consider(addr_int, ja, ko, slot_override=slot_override)
        if built > before:
            written_addrs.add(addr_int)

    def apply_direct_patch(addr_int: int, ja: str, ko: str, slot: int) -> tuple[str, str, int | None]:
        if addr_int not in direct_patches:
            return ja, ko, None
        end, direct_ko = direct_patches[addr_int]
        slot_override = max(slot, end - addr_int)
        direct_ja = QTF.source_text_for_span(addr_int, end, found_rows, found_texts.get(addr_int, ja))
        return direct_ja, direct_ko, slot_override

    # dialogue_overrides 우선, 없으면 translation_for_import
    with open(TRANS, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                a = int(r['address'], 16)
            except (ValueError, KeyError, TypeError):
                continue
            seen_import_addrs.add(a)
            ja = (r.get('japanese') or '').strip()
            akey = '0x%08X' % a
            ko = overrides.get(akey, overrides.get(r['address'], (r.get('korean') or '').strip()))
            if a in ADDRESS_TEXT_OVERRIDES:
                ko = ADDRESS_TEXT_OVERRIDES[a]
            elif ja in SOURCE_TEXT_OVERRIDES and not any('가' <= ch <= '힣' for ch in ko):
                ko = SOURCE_TEXT_OVERRIDES[ja]
            ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
            slot = slots.get(a, 0)
            ja, ko, slot_override = apply_direct_patch(a, ja, ko, slot)
            submit(a, ja, ko, slot_override=slot_override)

    for a, ko in sorted(ADDRESS_TEXT_OVERRIDES.items()):
        if a in seen_import_addrs:
            continue
        slot = slots.get(a, 0)
        ja = found_texts.get(a, '')
        ja, ko, slot_override = apply_direct_patch(a, ja, ko, slot)
        submit(a, ja, ko, slot_override=slot_override)

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
            if not ko:
                continue
            ja = row.get('text') or ''
            ja, ko, slot_override = apply_direct_patch(a, ja, ko, slot)
            submit(a, ja, ko, slot_override=slot_override)

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
                if not ko or ko == '미상':
                    continue
                ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
                ja = found_texts.get(a, '')
                ja, ko, slot_override = apply_direct_patch(a, ja, ko, slots.get(a, 0))
                submit(a, ja, ko, slot_override=slot_override)

    for a, (end, ko) in sorted(direct_patches.items()):
        if a in written_addrs or a in seen_import_addrs:
            continue
        ja = QTF.source_text_for_span(a, end, found_rows, found_texts.get(a, ''))
        submit(a, ja, ko, slot_override=max(slots.get(a, 0), end - a))

    rows.sort(key=lambda x: x[1], reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('addr\tdelta_px\tja_px\tko_px\tencoded_cells\tfit_level\tscenes\tja\tko\n')
        for a, d, wj, wk, cells, lv, hint, ja, ko in rows:
            f.write(f'0x{a:08X}\t{d}\t{wj}\t{wk}\t{cells}\t{lv}\t{hint}\t{ja}\t{ko}\n')

    max_out = os.path.join(BASE, 'temp', 'dialogue_box_width_over_max.tsv')
    with open(max_out, 'w', encoding='utf-8') as f:
        f.write('addr\tencoded_cells\tmax_cells\tfit_level\tscenes\tja\tko\n')
        for a, cells, mx, lv, hint, ja, ko in sorted(max_rows, key=lambda x: x[1], reverse=True):
            f.write(f'0x{a:08X}\t{cells}\t{mx}\t{lv}\t{hint}\t{ja}\t{ko}\n')

    print(f'built(바이트게이트 통과) 행: {built}')
    print(f'픽셀폭 KO>JA(박스폭 잠재초과): {wider}  ({100*wider/max(checked,1):.2f}%)')
    print(f'리포트: {OUT}')
    print(f'final encoded cells > {args.max_cells} 후보: {over_max}')
    print(f'초과 리포트: {max_out}')
    print(f'\n=== 위험 상위 {args.top} (delta_px desc) ===')
    for a, d, wj, wk, cells, lv, hint, ja, ko in rows[:args.top]:
        print(f'0x{a:08X}  +{d}px  cells={cells}  scenes={hint or "-"}  JA[{wj}]={ja[:24]!r}  KO[{wk}]={ko[:24]!r}')
    if max_rows:
        print(f'\n=== encoded_cells > {args.max_cells} 후보 상위 {min(args.top, len(max_rows))} ===')
        for a, cells, mx, lv, hint, ja, ko in sorted(max_rows, key=lambda x: x[1], reverse=True)[:args.top]:
            print(f'0x{a:08X}  cells={cells}>{mx}  level={lv}  scenes={hint or "-"}  KO={ko[:40]!r}')
    if args.fail_over_max_cells and over_max:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
