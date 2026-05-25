#!/usr/bin/env python3
"""한글용 예약 SJIS 코드 finder — 대화 한글화 구현 빌딩블록.

대화 렌더 파이프라인 RE(docs/research.md) 기반. 한글 음절을 매핑할 "안 쓰는" SJIS 코드
대역을 찾는다. codex+gemini 2차 리뷰의 충돌 회피 요구 반영.

원리:
- 한자 코드(>0x8397)는 변환 루틴이 테이블(0x08B80B7C, 536엔트리 [SJIS_LE,top_idx,bot_idx])에서
  검색해 글리프 인덱스를 얻는다.
- 한글화 방법: (A) 안 쓰는 한자 테이블 엔트리의 글리프 idx를 한글 글리프로 repoint, 또는
  (B) 테이블을 확장해 새 예약코드 추가.
- 예약 코드는 "최종 ROM에서 원래 의미로 등장하지 않을" 코드여야 한다.

이 스크립트가 분류:
1) 한자 테이블 536 코드 중 원문 텍스트에 안 나오는 것 → (A) repoint 후보(즉시 사용 가능, 테이블 확장 불요)
2) 유효 SJIS 한자 대역(0x889F~0xEAA4)에서 원문·테이블 어디에도 없는 코드 → (B) 테이블 확장용 예약 후보

출력: data/reserved_codes.json (repoint_pool, extend_pool, 통계)

사용:
  python tools/find_reserved_codes.py
"""
import csv
import json
import os
import struct

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
OUT = os.path.join(BASE, 'data', 'reserved_codes.json')

KANJI_TABLE = 0x08B80B7C
KANJI_TABLE_END = 0x08B8180C


def valid_sjis(code):
    """유효한 2바이트 SJIS lead/trail인지."""
    lead = code >> 8
    trail = code & 0xFF
    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
        return False
    if not (0x40 <= trail <= 0x7E or 0x80 <= trail <= 0xFC):
        return False
    return True


def used_codes_in_text():
    """원문(japanese)에 등장하는 모든 SJIS 코드 집합."""
    used = set()
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            ja = r.get('japanese') or r.get('text') or ''
            try:
                b = ja.encode('shift_jis', errors='ignore')
            except Exception:
                continue
            i = 0
            while i < len(b) - 1:
                lead = b[i]
                if 0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC:
                    used.add((lead << 8) | b[i + 1]); i += 2
                else:
                    i += 1
    return used


def kanji_table_codes(rom):
    """한자 테이블의 SJIS 코드(빅엔디안 복원) 집합."""
    codes = {}
    for a in range(KANJI_TABLE, KANJI_TABLE_END, 6):
        o = a - 0x08000000
        sjis_le = struct.unpack('<H', rom[o:o + 2])[0]   # 테이블은 byteswap(LE) 저장
        big = ((sjis_le & 0xFF) << 8) | (sjis_le >> 8)   # 원래 SJIS(빅엔디안)
        top_idx = struct.unpack('<H', rom[o + 2:o + 4])[0]
        bot_idx = struct.unpack('<H', rom[o + 4:o + 6])[0]
        codes[big] = (top_idx, bot_idx)
    return codes


def main():
    rom = open(ROM, 'rb').read()
    used = used_codes_in_text()
    table = kanji_table_codes(rom)
    print(f'원문 사용 SJIS 코드: {len(used)}')
    print(f'한자 테이블 엔트리: {len(table)}')

    # (A) repoint 후보: 테이블에 있으나 원문에 안 나오는 한자
    repoint = sorted(c for c in table if c not in used)
    # (B) 확장 후보: 유효 SJIS 한자 대역에서 원문·테이블 어디에도 없는 코드
    extend = []
    for lead in range(0x88, 0xEB):           # JIS 한자 대역
        for trail in range(0x40, 0xFD):
            code = (lead << 8) | trail
            if not valid_sjis(code):
                continue
            if code in used or code in table:
                continue
            extend.append(code)
    print(f'(A) repoint 후보(테이블O·원문X): {len(repoint)}')
    print(f'(B) 확장 후보(테이블X·원문X 유효SJIS): {len(extend)}')
    need = 1028
    print(f'필요 음절: {need}  →  repoint {len(repoint)} + 확장 {min(len(extend), need)} 로 충분: {len(repoint)+len(extend) >= need}')

    out = {
        '_readme': '한글용 예약 SJIS 코드 풀. repoint_pool=테이블 repoint 즉시가능, '
                   'extend_pool=테이블 확장 필요. docs/research.md 파이프라인 참조.',
        'stats': {
            'used_in_text': len(used), 'kanji_table': len(table),
            'repoint_pool': len(repoint), 'extend_pool': len(extend),
            'need_syllables': need,
        },
        'repoint_pool': [f'0x{c:04X}' for c in repoint],
        'extend_pool_sample': [f'0x{c:04X}' for c in extend[:200]],
        'extend_pool_count': len(extend),
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n→ {OUT}')
    print(f'repoint 샘플(테이블O 원문X 한자): {[f"0x{c:04X}" for c in repoint[:10]]}')
    print(f'확장 샘플: {[f"0x{c:04X}" for c in extend[:10]]}')


if __name__ == '__main__':
    main()
