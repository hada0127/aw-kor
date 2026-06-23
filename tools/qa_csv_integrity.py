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

심각도(ROM 진실 기반 — 2026-06-24 정교화):
  rom_japanese   ROM 실제 디코드가 일본어(가나/한자)이고 DENY 테이블/가나표가 아님 → 진짜 잔존 결함
  benign         ROM이 한글/혼합/노이즈/의도적 테이블 → CSV는 손상돼도 빌드 inline 리터럴이 권위라 ROM 정상

핵심: translation_for_import.csv의 length/korean이 손상돼도, 빌드는 inline 리터럴+override를 권위로
쓰므로 ROM은 정상일 수 있다. 이 도구는 CSV가 아니라 **출하 ROM을 디코드**해 진짜 잔존만 본다.

사용:
  python3 tools/qa_csv_integrity.py            # 요약 + temp/csv_integrity_report.tsv
  python3 tools/qa_csv_integrity.py --fail-on-rom-japanese   # ROM 일본어 잔존 있으면 비0 종료
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
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code_2350.json')
ROM = os.path.join(BASE, 'output', 'game_wars_korean_full.gba')
OUT = os.path.join(BASE, 'temp', 'csv_integrity_report.tsv')

ADDR_RE = re.compile(r'0x[0-9A-Fa-f]{6,8}')
INT_RE = re.compile(r'\d+')

# 의도적으로 일본어/심볼 데이터를 담는 영역(가나표·기호테이블·컴팩트UI 사전·sjis 슬롯표).
# 여기 일본어는 텍스트 잔존이 아니라 폰트/테이블 데이터 → 잔존 결함에서 제외.
INTENTIONAL_TABLE_RANGES = [
    (0x008059C4, 0x008059C5),   # 이름입력 가나 음절표
    (0x00BE717A, 0x00BE9C6E),   # sjis 슬롯 테이블
    (0x00805100, 0x00805A24),   # part1 컴팩트 UI 사전
    (0x00D82740, 0x00D83100),   # part2 컴팩트 UI 사전
    (0x00D60000, 0x00D80000),   # 대사 스트림 이전(대사=0xD80000~) 심볼/구두점/포맷 테이블(noise 버킷 region='other')
]


def _in_table(addr_int: int) -> bool:
    return any(lo <= addr_int < hi for lo, hi in INTENTIONAL_TABLE_RANGES)


def _load_rom_decoder():
    """출하 ROM 디코더: addr → 'korean'|'japanese'|'mixed'|'noise'. 빌드 권위(inline 리터럴 포함)."""
    if not os.path.exists(ROM):
        return None
    rom = open(ROM, 'rb').read()
    syl = json.load(open(SYLCODE, encoding='utf-8'))
    c2s = {int(v, 16): k for k, v in syl.items()}

    def kind(addr_int: int, n: int = 40) -> str:
        b = rom[addr_int:addr_int + n]
        i = kor = jp = 0
        while i < len(b) and b[i] != 0:
            if b[i] in (0x20, 0x0A):
                i += 1
                continue
            if i + 1 < len(b) and ((b[i] << 8) | b[i + 1]) in c2s:
                kor += 1
                i += 2
                continue
            c = b[i]
            # 가나(0x82-0x83)·한자(0x88-0x9F,0xE0-0xEF)만 '일본어 텍스트'로 본다.
            # 0x81(전각 기호/구두점 ±−】【。，．·)은 심볼 테이블 데이터 → 잔존 결함 아님.
            if 0x82 <= c <= 0x9F or 0xE0 <= c <= 0xEF:
                jp += 1
                i += 2
                continue
            if c == 0x81:           # 심볼 블록: 2바이트 소비하되 일본어 카운트 안 함
                i += 2
                continue
            i += 1
        if kor and not jp:
            return 'korean'
        if jp and not kor:
            return 'japanese'
        if kor and jp:
            return 'mixed'
        return 'noise'
    return kind


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
    ap.add_argument('--fail-on-rom-japanese', action='store_true')
    args = ap.parse_args()

    rom_kind = _load_rom_decoder()
    rows = list(csv.DictReader(open(TRANS, encoding='utf-8')))
    findings = []
    for r in rows:
        c = classify(r)
        if not c:
            continue
        a = r.get('address', '')
        try:
            ai = int(a, 16)
        except (ValueError, TypeError):
            ai = -1
        # ROM 진실: 출하 ROM이 실제로 무엇을 렌더하는가
        if ai < 0x800000:
            rk = 'code/noise'
        elif rom_kind is None:
            rk = 'unknown(no-rom)'
        else:
            rk = rom_kind(ai)
        # 진짜 잔존 결함 = ROM 일본어 AND 의도적 테이블 아님
        if rk == 'japanese' and not _in_table(ai):
            sev = 'rom_japanese'
        else:
            sev = 'benign'
        findings.append((a, c, region(a), rk, sev, (r.get('korean') or '')[:50]))

    by_kind = Counter(f[1] for f in findings)
    by_romkind = Counter(f[3] for f in findings)
    by_sev = Counter(f[4] for f in findings)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('address\tkind\tregion\trom_render\tseverity\tkorean_excerpt\n')
        for a, k, rg, rk, sev, ko in findings:
            f.write(f'{a}\t{k}\t{rg}\t{rk}\t{sev}\t{ko}\n')

    print(f'총 CSV 손상행: {len(findings)} (length/korean 손상; 빌드는 inline 리터럴 권위라 ROM은 별개)')
    print(f'  손상 종류: {dict(by_kind)}')
    print(f'  ROM 실제 렌더: {dict(by_romkind)}')
    print(f'  심각도: {dict(by_sev)}')
    rj = [f for f in findings if f[4] == 'rom_japanese']
    print(f'  ★ 진짜 ROM 일본어 잔존(의도적 테이블 제외): {len(rj)}')
    for a, k, rg, rk, sev, ko in rj[:20]:
        print(f'    {a} [{rg}] csv_ko={ko!r}')
    print(f'리포트: {OUT}')

    if args.fail_on_rom_japanese and rj:
        print(f'FAIL: ROM 일본어 잔존 {len(rj)}건', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
