#!/usr/bin/env python3
"""대사 줄바꿈 재배치 (DP) — Game Wars 한글화용.

무라마사 한글화의 `tools/reflow_dialogs.py`(DP 기반 균형 줄바꿈)를 aw-kor CSV에
맞춰 적응 이식.

목적: 한국어 대사를 목표 줄 수 이하로, 줄당 최대 폭을 지키며 단어 경계로 재배치.
마침표·쉼표 뒤에서 우선 끊고(자연스러운 분리), 줄 폭을 균형 있게 분배(DP).

폭 계산: 한글/전각 = 1.0, ASCII = 0.5 (셀 기준).

⚠️ 현재 aw-kor 상태: `translation_for_import.csv`는 대부분 단일행이고 줄바꿈을
게임 타이프라이터 렌더러가 처리한다(welcome 화면 RE 참조). 즉 지금은 reflow 대상
멀티라인 행이 거의 없다. 이 도구는 **향후 대사 박스 폭에 맞춰 직접 줄바꿈을
넣어야 할 때**(예: 번역이 박스를 넘쳐 강제 개행 필요) 쓰도록 준비해 둔 것이다.
박스 폭(--max-width)은 게임 대사창의 실제 셀 수로 보정해야 한다(미보정 기본=15).

사용:
  python tools/reflow_dialogs.py --test "긴 문장 ..."        # 단일 문자열 줄바꿈 시연
  python tools/reflow_dialogs.py --max-width 15               # CSV 미리보기(멀티라인/초과행)
  python tools/reflow_dialogs.py --max-width 15 --apply        # CSV 적용
"""
import csv
import re
import os
import argparse
from functools import lru_cache

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')

PUNCT_STRONG = set("。.!?…」』）)")
PUNCT_WEAK = set(",、—–-")


def line_width(s):
    """한글/전각=1.0, ASCII=0.5."""
    return sum(0.5 if ord(c) < 0x80 else 1.0 for c in s)


def reflow(ko, target_n, max_width):
    """ko 를 target_n 줄 이하로 재배치. 불가하면 None. (무라마사 DP 충실 이식)"""
    full = " ".join(ko.replace("\r\n", "\n").split("\n")).strip()
    full = re.sub(r' +', ' ', full)
    if not full:
        return ko
    words = full.split(" ")
    n = len(words)
    if n == 0:
        return ""

    space_w = 0.5
    cum = [0.0]
    for w in words:
        cum.append(cum[-1] + line_width(w) + space_w)

    def slice_width(i, j):
        return cum[j] - cum[i] - space_w

    def break_penalty(j):
        if j <= 0 or j >= n:
            return 0
        last = words[j - 1]
        if not last:
            return 5
        c = last[-1]
        if c in PUNCT_STRONG:
            return 0
        if c in PUNCT_WEAK:
            return 2
        return 5

    @lru_cache(maxsize=None)
    def solve(start, lines_left):
        if lines_left == 1:
            sw = slice_width(start, n)
            if sw > max_width:
                return None
            return (sw, 0, (n,))
        best = None
        for j in range(start + 1, n):
            sw = slice_width(start, j)
            if sw > max_width:
                break
            sub = solve(j, lines_left - 1)
            if sub is None:
                continue
            sub_max, sub_pen, sub_breaks = sub
            max_w = max(sw, sub_max)
            pen = sub_pen + break_penalty(j)
            cost = (pen, max_w)
            if best is None or cost < (best[1], best[0]):
                best = (max_w, pen, (j,) + sub_breaks)
        return best

    r = solve(0, target_n)
    solve.cache_clear()
    if r is None:
        return None
    lines = []
    prev = 0
    for b in r[2]:
        lines.append(" ".join(words[prev:b]))
        prev = b
    return "\n".join(lines)


def count_lines(text):
    return text.replace("\r\n", "\n").count("\n") + 1 if text else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--max-width', type=float, default=15.0,
                    help='줄당 최대 폭(전각 셀 단위). 게임 대사창 폭으로 보정 필요')
    ap.add_argument('--max-lines', type=int, default=0,
                    help='목표 최대 줄 수(0=일본어 줄 수 따름)')
    ap.add_argument('--test', default=None, help='단일 문자열 줄바꿈 시연')
    ap.add_argument('--sample', type=int, default=10)
    a = ap.parse_args()

    if a.test is not None:
        tn = a.max_lines or 3
        for n in range(1, tn + 1):
            out = reflow(a.test, n, a.max_width)
            print(f'--- target {n}줄 (max_width {a.max_width}) ---')
            if out is None:
                print('  (불가: 폭 초과)')
            else:
                for l in out.split('\n'):
                    print(f'  | {l}  (w={line_width(l):g})')
        return

    with open(a.csv, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    stats = {'total': 0, 'need': 0, 'reflowed': 0, 'fail': 0}
    samples = []
    for r in rows:
        ko = r.get('korean') or ''
        ja = r.get('japanese') or ''
        if not ko.strip():
            continue
        stats['total'] += 1
        ko_n = count_lines(ko)
        target = a.max_lines or max(1, count_lines(ja))
        # 재배치 필요: 줄 수가 목표 초과 또는 어떤 줄이 max_width 초과
        over_width = any(line_width(l) > a.max_width for l in ko.split('\n'))
        if ko_n <= target and not over_width:
            continue
        stats['need'] += 1
        new_ko = reflow(ko, target, a.max_width)
        if new_ko is None:
            for tn in range(target + 1, ko_n + 3):
                new_ko = reflow(ko, tn, a.max_width)
                if new_ko is not None:
                    break
        if new_ko is None or new_ko == ko:
            stats['fail'] += 1
            continue
        stats['reflowed'] += 1
        if len(samples) < a.sample:
            samples.append((r.get('address', ''), ko, new_ko))
        if a.apply:
            r['korean'] = new_ko

    print(f"대사행 {stats['total']} / 재배치 필요 {stats['need']} / 성공 {stats['reflowed']} / 실패 {stats['fail']}")
    for addr, old, new in samples:
        print(f"\n[{addr}]")
        for l in old.split('\n'):
            print(f"  old| {l}  (w={line_width(l):g})")
        for l in new.split('\n'):
            print(f"  new| {l}  (w={line_width(l):g})")

    if a.apply and stats['reflowed']:
        with open(a.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader(); w.writerows(rows)
        print(f'\n[APPLIED] {a.csv}')
    elif not a.apply:
        print('\n[DRY-RUN] --apply 로 실제 적용')


if __name__ == '__main__':
    main()
