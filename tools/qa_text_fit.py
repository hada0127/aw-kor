#!/usr/bin/env python3
"""Session 3 QA: 예약코드 인코딩의 byte budget + 시각폭(박스) 적합성 리포트.

- byte budget: encoded_len(한글2B/ASCII1B/전각2B) vs 슬롯길이(found_texts 권위).
  초과 행은 빌드에서 skip(원문 유지)되므로, 그 목록을 보고 번역 축약 대상 선정.
- 시각폭: 한글 라인이 원본 일본어 라인보다 시각적으로 넓은지(전각2/ASCII1 근사).
  바이트 예산을 지키면 전각↔전각은 폭도 충족되나, ASCII→전각(숫자/메뉴) 행은 예외.

사용: python tools/qa_text_fit.py
"""
import csv, json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
SAFE_MIN_ADDR = 0x800000


def load_slots():
    s = {}
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                s[a] = int(r.get('length') or 0)
            except (ValueError, TypeError):
                pass
    return s


def enc_len(ko):
    n = 0
    for ch in ko:
        if '가' <= ch <= '힣':
            n += 2
        elif 0x20 <= ord(ch) <= 0x7E:
            n += 1
        else:
            n += 2
    return n


def vwidth(s):
    w = 0
    for ch in s:
        w += 1 if (ch == ' ' or 0x20 <= ord(ch) <= 0x7E) else 2
    return w


def main():
    slots = load_slots()
    written = overflow = wider = 0
    over_le2 = 0
    with open(TRANS, newline='') as f:
        for row in csv.DictReader(f):
            ko = (row.get('korean') or '').strip()
            ja = (row.get('japanese') or '').strip()
            try:
                a = int(row['address'], 16)
            except (ValueError, TypeError):
                continue
            if not ko or a < SAFE_MIN_ADDR or slots.get(a, 0) <= 0:
                continue
            el = enc_len(ko)
            slot = slots[a]
            if el > slot:
                overflow += 1
                if el - slot <= 2:
                    over_le2 += 1
                continue
            written += 1
            if vwidth(ko) > vwidth(ja):
                wider += 1
    print(f'written(한글 인코딩): {written}')
    print(f'overflow(슬롯초과 skip→원문): {overflow}  (그중 ≤2B: {over_le2}, 축약 용이)')
    print(f'visual-wider than JA: {wider} ({100*wider/max(written,1):.1f}%) — 박스폭 잠재리스크(대부분 ≤1글자/노이즈)')


if __name__ == '__main__':
    main()
