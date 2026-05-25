#!/usr/bin/env python3
"""문장부호 자동 보정 — Game Wars 한글화용.

무라마사 한글화의 `tools/fix_punctuation.py`(919줄)의 **한국어 종결어미 분류표**를
가져오되, aw-kor에 맞는 안전 전략으로 재구성했다.

aw-kor 특성: 전략 게임이라 UI 라벨/유닛명/지형명("아군", "방어", "기갑 방어")이 매우 많다.
무라마사식 "KO 종결어미만 보고 자동 부호 추가"는 이런 라벨에 마침표를 잘못 붙일 위험이 크다.

그래서 핵심 안전 게이트 두 개를 둔다:
  1) **일본어 원문(ja)이 종결부호(。！？…)로 끝날 때만** 부호를 붙인다.
     → 원문이 라벨이면 부호가 없으니 한국어에도 안 붙음. (가장 강한 신호)
  2) 한국어가 **문장형 종결어미**(classify_ko_ending)일 때만. → 명사/조사 끝 라벨 SKIP.
  부호는 일본어 원문을 미러링: 。→ "." / ！→ "!" / ？→ "?" / …→ "…" / ！？→ "!?"

기존에 부호가 있으면 건드리지 않는다. 노이즈 행(원문 한자/기호 반복)도 SKIP.

사용:
  python tools/fix_punctuation.py                 # 미리보기
  python tools/fix_punctuation.py --apply          # CSV 적용
  python tools/fix_punctuation.py --limit 30       # 샘플 개수
"""
import csv
import os
import re
import argparse
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'translation_for_import.csv')

# ===== 한국어 종결어미 분류표 (무라마사 fix_punctuation.py에서 이식) =====
AUTO_Q_KO_ENDINGS = [
    "더냐", "느냐", "는가", "는고", "런가", "인가", "인고",
    "을까", "을꼬", "는지", "런지", "리오", "이오",
    "리까", "리이까", "ㅂ니까", "습니까", "쏘냐", "이뇨", "느뇨",
    "이냐", "거냐", "것이냐", "겠나", "잖나", "라니",
    "이랴", "으랴", "랴", "까",
]
AUTO_DECL_KO_ENDINGS = [
    "이로다", "되었다", "하였다", "되었더라", "하였더라",
    "구나", "도다", "노라", "리라", "이라네", "이라오",
    "구먼", "구려", "ㅂ니다", "습니다", "니라", "이니라", "느니라",
    "합니다", "옵니다", "입니다", "답니다", "였답니다", "이옵니다",
    "이올시다", "올시다",
    "주마", "리다", "이리다", "겠지", "겠소", "겠어요",
    "이로군", "로군", "이로세", "로세",
    "지요", "이지요", "잖아", "지롱",
    "다오", "거다", "이거다",
    "는다", "었다",
    "마라", "해라",
    "었네", "였네", "다네",
    # aw-kor 보강(현대 구어체 — 번역 톤): 평서 종결
    "어요", "에요", "예요", "네요", "거든", "거야", "잖아요",
    "더라", "더라고", "던데", "는데", "을게", "ㄹ게", "을래",
]
AUTO_CMD_KO_ENDINGS = [
    "주거라", "거라", "어라", "아라", "오라",
    "오너라", "셔라", "옵소서", "하라", "가라",
    "있거라", "보거라", "들거라",
]
# 평서로 자동 적용 시 false-positive 위험 — 길이 가드(10자↑)에서만.
# 단 ja가 종결부호로 끝나면(문장임이 확실) 가드 완화.
RISKY_DECL_ENDINGS = {
    "이다", "한다", "있다", "없다", "같다", "겠다", "이라", "다",
}
# 명사/조사로 끝나면 SKIP
KO_PARTICLES_END = {"을", "를", "은", "는", "이", "가", "에", "의",
                    "도", "만", "와", "과", "로", "랑", "께", "께서"}
END_PUNCT = ".!?…」』）)\"'·~"


def classify_ko_ending(line, ja_has_terminal):
    """KO 줄 끝 종결어미 분류 → ('Q'|'DECL'|'CMD'|'RISKY_DECL'|None, end).

    ja_has_terminal=True면 원문이 문장임이 확실해 RISKY 길이가드를 완화한다.
    """
    s = line.rstrip()
    if not s:
        return (None, None)
    last_ch = s[-1]
    if last_ch in END_PUNCT:        # 이미 부호 있음
        return (None, None)
    if not ("가" <= last_ch <= "힣"):
        return (None, None)
    if len(s.replace(" ", "")) < 3:  # 너무 짧은 라벨/감탄사
        return (None, None)
    if last_ch in KO_PARTICLES_END:
        return (None, None)
    for end in sorted(AUTO_CMD_KO_ENDINGS, key=len, reverse=True):
        if s.endswith(end):
            return ("CMD", end)
    for end in sorted(AUTO_Q_KO_ENDINGS, key=len, reverse=True):
        if s.endswith(end):
            return ("Q", end)
    for end in sorted(AUTO_DECL_KO_ENDINGS, key=len, reverse=True):
        if s.endswith(end):
            return ("DECL", end)
    for end in sorted(RISKY_DECL_ENDINGS, key=len, reverse=True):
        if s.endswith(end):
            if ja_has_terminal or len(s.replace(" ", "")) >= 10:
                return ("RISKY_DECL", end)
            return (None, None)
    return (None, None)


def ja_terminal(ja):
    """일본어 원문의 종결부호 → 한국어 대응 부호 문자열. 없으면 ''."""
    s = (ja or '').rstrip().rstrip('」』）)】')  # 닫는 괄호 벗겨 안쪽 부호 확인
    s = s.rstrip()
    if not s:
        return ''
    # 끝의 부호 덩어리 추출
    m = re.search(r'[。．！？…\!\?\.]+$', s) or re.search(r'(・・・)$', s)
    if not m:
        return ''
    tail = m.group()
    has_q = ('？' in tail) or ('?' in tail)
    has_ex = ('！' in tail) or ('!' in tail)
    has_ell = ('…' in tail) or ('・・・' in tail)
    if has_ex and has_q:
        return '?!' if tail.rstrip()[-1] in '！!' else '!?'
    if has_q:
        return '?' * (tail.count('？') + tail.count('?'))
    if has_ex:
        return '!' * (tail.count('！') + tail.count('!'))
    if has_ell:
        return '…'
    # 。 . ．만 남음
    return '.'


def noise(ja):
    return bool(re.search(r'(.)\1\1', ja or ''))


def fix_one(ja, ko):
    """(new_ko, kind) 또는 (None, None). 마지막 줄에만 부호 추가."""
    if not ko or noise(ja):
        return (None, None)
    term = ja_terminal(ja)
    if not term:
        return (None, None)   # 게이트1: 원문이 문장 종결부호로 안 끝남
    lines = ko.split('\n')
    last = lines[-1].rstrip()
    kind, _ = classify_ko_ending(last, ja_has_terminal=True)
    if kind is None:
        return (None, None)   # 게이트2: 한국어가 문장형 종결어미 아님
    # 부호 결정: 한국어 종결어미가 의문이면 ? 우선, 아니면 원문 미러
    if kind == 'Q' and '?' not in term:
        mark = '?'
    elif kind in ('CMD', 'DECL', 'RISKY_DECL') and term == '?':
        mark = '.'    # 원문이 ?인데 한국어가 평서면 평서 따름(드묾)
    else:
        mark = term
    lines[-1] = last + mark
    return ('\n'.join(lines), kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_PATH)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--limit', type=int, default=20)
    a = ap.parse_args()

    with open(a.csv, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    stat = Counter()
    samples = []
    for r in rows:
        ja = r.get('japanese') or ''
        ko = r.get('korean') or ''
        new_ko, kind = fix_one(ja, ko)
        if new_ko is None or new_ko == ko:
            continue
        stat[kind] += 1
        if len(samples) < a.limit:
            samples.append((r.get('address', ''), kind, ja[:30], ko[:35], new_ko[:36]))
        r['korean'] = new_ko

    total = sum(stat.values())
    print(f'부호 추가 {total}행: ' + ', '.join(f'{k} {v}' for k, v in stat.most_common()))
    print('\n샘플:')
    for addr, kind, ja, ko, new in samples:
        print(f"  {addr} [{kind}] ja={ja!r}")
        print(f"    - {ko!r}\n    + {new!r}")

    if a.apply:
        with open(a.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f'\n[APPLIED] {a.csv}')
    else:
        print('\n[DRY-RUN] --apply 로 실제 적용')


if __name__ == '__main__':
    main()
