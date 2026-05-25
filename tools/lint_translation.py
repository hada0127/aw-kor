#!/usr/bin/env python3
"""번역 품질 검수기 (lint) — Game Wars 한글화용.

무라마사 한글화 프로젝트의 `tools/lint_dialogs.py`를 aw-kor CSV 포맷
(`data/translation_for_import.csv`: address,japanese,korean,length)에 맞춰 적응 이식.

`korean` 필드를 규칙별로 검사해 error/warning/info로 리포트한다.
번역 회귀 추적 + 삽입 손상(바이트 예산 초과) 사전 차단 + 추출 노이즈 식별용.

검사 규칙
- hex_token (error)   : 추출 시 포인터 주소가 번역에 새어든 손상 (예: "유0x00D9991D")
- replacement (error) : U+FFFD 깨진 문자
- control (error)     : 개행/탭 외 제어문자
- byte_budget (error) : 재인코딩 바이트수 > length(원본 예산). 초과 시 인접 데이터 손상.
                        (인코딩 모델: 한글/비ASCII=2바이트, ASCII=1바이트 — execute_phase5_4와 동일)
- glyph (error)       : Galmuri11-Condensed BDF에 없는 한글 (현 폰트는 11,172 전체라 거의 0)
- jp_kana (warning)   : 가나 잔존 (미번역 또는 추출 노이즈)
- jp_kanji (warning)  : 한자 잔존
- jp_punct (warning)  : 일본 문장부호
- jp_quote (info)     : 일본 인용부호 (스타일)
- punct_space (warning): 줄임표/마침표 뒤 글자가 바로 붙음
- bad_punct (warning) : 비표준/연속 부호 의심
- empty_budget (info) : length가 비었거나 숫자가 아님 (예산 검사 불가)

추출 노이즈 구분: `japanese` 원문 자체가 가나/한자/기호 범벅이면 그 행은
번역 대상이 아닌 추출 노이즈일 확률이 높다. --hide-noise 로 그런 행을 숨길 수 있다.

사용:
  python tools/lint_translation.py                       # 전체 요약
  python tools/lint_translation.py --rule hex_token --limit 20
  python tools/lint_translation.py --severity error
  python tools/lint_translation.py --hide-noise          # 추출 노이즈 행 제외
  python tools/lint_translation.py --json temp/lint.json # 전체 결과 JSON
"""
import csv
import re
import os
import argparse
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')
BDF_PATH = os.path.join(BASE, 'reference', 'fonts', 'Galmuri11-Condensed.bdf')

# 유니코드 범위는 리터럴 한자/가나가 의도와 다른 코드포인트로 입력되는 함정을 피해
# 명시적 \u 이스케이프로 지정한다.
HANGUL = re.compile('[가-힣]')                       # 한글 음절
KANA = re.compile('[぀-ヿ]')                         # 히라가나 + 가타카나
CJK = re.compile('[㐀-鿿豈-﫿]')             # 한자(통합 A+통합+호환)
JP_PUNCT_HARD = re.compile('[。、]')                 # 。 、
JP_QUOTE = re.compile('[「」『』]')          # 「」『』
HEXTOK = re.compile(r'0x[0-9A-Fa-f]{2,}')                    # 누출된 포인터 주소
REPL = '�'


def enc_len(s):
    """재인코딩 바이트수. 한글/비ASCII=2, ASCII=1 (execute_phase5_4.py EUC-KR 모델)."""
    return sum(1 if ord(c) < 0x80 else 2 for c in s)


def load_glyphs():
    """Galmuri11-Condensed BDF에 존재하는 코드포인트 집합."""
    try:
        import sys
        sys.path.insert(0, os.path.join(BASE, 'tools'))
        from bdf import load_bdf
        gl, _ = load_bdf(BDF_PATH)
        return set(gl.keys())
    except Exception:
        return None  # BDF 못 읽으면 글리프 검사 생략


def is_noise(ja):
    """원문(ja)이 추출 노이즈(가나/한자/기호 범벅, 한글 무의미)인지 휴리스틱."""
    if not ja:
        return False
    # 같은 한자/기호 3회 이상 반복 (劔劔劔, 闊闊闊 류)
    if re.search(r'(.)\1\1', ja) and (CJK.search(ja) or KANA.search(ja)):
        return True
    return False


def check(ja, ko, glyphs, budget):
    """한 행의 korean에 대한 (severity, rule, message) 리스트."""
    issues = []
    def add(sev, rule, msg): issues.append((sev, rule, msg))
    if not ko:
        return issues

    # --- 손상(데이터 무결성) ---
    m = HEXTOK.search(ko)
    if m:
        add('error', 'hex_token', f'포인터 주소 누출: {m.group()}')
    if REPL in ko:
        add('error', 'replacement', 'U+FFFD 깨진 문자')
    ctrl = sorted({c for c in ko if ord(c) < 0x20 and c not in '\n\t'})
    if ctrl:
        add('error', 'control', f'제어문자: {[hex(ord(c)) for c in ctrl]}')

    # --- 바이트 예산 (삽입 손상 방지) ---
    if budget is not None:
        e = enc_len(ko)
        if e > budget:
            add('error', 'byte_budget', f'재인코딩 {e}B > 예산 {budget}B (초과 {e-budget}B)')
    else:
        add('info', 'empty_budget', 'length 비었거나 비숫자')

    # --- 글리프 (폰트에 없는 한글) ---
    if glyphs is not None:
        bad = sorted({c for c in ko if HANGUL.match(c) and ord(c) not in glyphs})
        if bad:
            add('error', 'glyph', f'폰트에 없는 글자: {"".join(bad)}')

    # --- 일본어 잔존 ---
    if KANA.search(ko):
        add('warning', 'jp_kana', f'가나 잔존: {"".join(sorted(set(KANA.findall(ko))))[:8]}')
    cjk = sorted(set(CJK.findall(ko)))
    if cjk:
        add('warning', 'jp_kanji', f'한자 잔존: {"".join(cjk)[:12]}')
    if JP_PUNCT_HARD.search(ko):
        add('warning', 'jp_punct', f'일본 부호: {"".join(sorted(set(JP_PUNCT_HARD.findall(ko))))}')
    if JP_QUOTE.search(ko):
        add('info', 'jp_quote', f'일본 인용부호: {"".join(sorted(set(JP_QUOTE.findall(ko))))}')

    # --- 부호 ---
    # 줄임표·마침표 뒤에 글자가 바로 붙으면 공백 누락 (문장 시작 줄임표 제외)
    for mt in re.finditer('[….]', ko):
        ch = mt.group(); s = mt.start()
        nxt = ko[s+1:s+2]; prev = ko[s-1] if s > 0 else ''
        if not nxt or nxt.isspace():
            continue
        if not (nxt.isalnum() or HANGUL.match(nxt)):
            continue
        if s == 0 or prev.isspace():
            continue
        if ch == '.' and (nxt.isdigit() or nxt == '.' or prev.isdigit()):
            continue
        if ch == '…' and nxt in '….':
            continue
        add('warning', 'punct_space', f'"{ch}" 뒤 공백 없음')
        break
    if re.search(r'(?<!\.)\.\.(?!\.)|！！|？？|，|．', ko):
        add('warning', 'bad_punct', '비표준/연속 부호 의심')

    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--severity', choices=['error', 'warning', 'info', 'all'], default='all')
    ap.add_argument('--rule', default=None, help='특정 규칙만')
    ap.add_argument('--limit', type=int, default=0, help='샘플 출력 개수')
    ap.add_argument('--json', default=None, help='전체 결과 JSON 경로')
    ap.add_argument('--hide-noise', action='store_true', help='추출 노이즈 행 제외')
    a = ap.parse_args()

    glyphs = load_glyphs()
    if glyphs is None:
        print('[경고] Galmuri BDF를 못 읽어 glyph 검사 생략')

    rows = []
    n_total = n_noise = 0
    with open(a.csv, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ko = (r.get('korean') or '').strip()
            if not ko:
                continue
            ja = (r.get('japanese') or '')
            n_total += 1
            noise = is_noise(ja)
            if noise:
                n_noise += 1
            if a.hide_noise and noise:
                continue
            ln = (r.get('length') or '').strip()
            budget = int(ln) if ln.isdigit() else None
            for sev, rule, msg in check(ja, ko, glyphs, budget):
                if a.severity != 'all' and sev != a.severity:
                    continue
                if a.rule and rule != a.rule:
                    continue
                rows.append({'address': r.get('address', ''), 'severity': sev,
                             'rule': rule, 'message': msg, 'noise': noise,
                             'ja': ja[:40], 'ko': ko.replace('\n', '⏎')[:70]})

    by = Counter((x['severity'], x['rule']) for x in rows)
    cnt = Counter(x['severity'] for x in rows)
    flagged = len({x['address'] for x in rows})
    print(f"번역행 {n_total} (추출노이즈 추정 {n_noise}) / 지적된 행 {flagged}")
    print(f"총 {len(rows)}건 (error {cnt['error']} / warning {cnt['warning']} / info {cnt['info']})")
    order = {'error': 0, 'warning': 1, 'info': 2}
    for (sev, rule), n in sorted(by.items(), key=lambda x: (order.get(x[0][0], 9), -x[1])):
        print(f'  [{sev:7}] {rule:14} {n}')

    if a.json:
        import json
        json.dump(rows, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'→ {a.json} ({len(rows)}건)')
    if a.limit:
        print('\n샘플:')
        for x in rows[:a.limit]:
            tag = ' [noise]' if x['noise'] else ''
            print(f"  {x['address']} [{x['severity']}] {x['rule']}{tag}: {x['message']}")
            print(f"     ja={x['ja']!r}\n     ko={x['ko']!r}")


if __name__ == '__main__':
    main()
