#!/usr/bin/env python3
"""의미 드리프트 기계 검사 (qa_meaning_from_rom).

출하 ROM 역디코드 KO ↔ 원문 JA를 대조해 **기계적으로 잡히는** 의미 오류를 색출한다.
codex 리뷰: LLM 생성+LLM 검증은 자기합리화 위험 → 비-LLM 백스톱 필요.

검사
  1) [NUMBER] JA의 아라비아 숫자(반각/전각)가 KO에 누락/변경 → 수치 오역(예 2HP, 14일).
  2) [NEGATION] JA 부정(ない/ません/ぬ/ず/なきゃ…) ↔ KO 부정(안/못/없/말/지 마/지 않)
     극성이 어긋나면 의미 반전 후보(예 '알고 싶지 않아?'↔'알고 싶잖아?').

높은 정밀도를 위해 실대사(JA에 가나/한자 포함, KO에 한글 포함)만 검사. 부정은 노이즈가
있어 WARN(정렬 보고), 숫자는 정밀도가 높다. 종료코드: NUMBER 누락 있으면 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from qa_terms_from_rom import load_code2syl, load_shipped, load_ja  # noqa: E402

ZEN2HAN = {ord('０') + i: chr(ord('0') + i) for i in range(10)}
KANA = re.compile(r"[぀-ヿ一-鿿]")
HANGUL = re.compile(r"[가-힣]")

JA_NEG = ["ない", "ません", "なかった", "なきゃ", "なくちゃ", "ぬ。", "ず。", "ずに",
          "ないで", "ねえ", "まい", "るな！", "んな！"]
KO_NEG = ["안 ", "못 ", "없", "아니", "말고", "마.", "마,", "마!", "마?", "지 마",
          "지마", "지 않", "지않", "ㄹ 수 없", "지 못", "말아", "말라", "없이"]


# 한국어가 작은 수를 고유어/한자어로 옮기는 경우(이동력3→느리지만 같은 실드리프트와 구분).
NATIVE_NUM = {
    "0": ["영", "제로", "다 ", "다.", "모두", "바닥", "전부", "0"],
    "1": ["한", "하나", "일", "하루", "첫", "혼자", "홑"],
    "2": ["두", "둘", "이틀", "양", "둘째", "쌍"],
    "3": ["세", "셋", "삼", "사흘"],
    "4": ["네", "넷", "나흘"],
    "5": ["다섯", "닷새", "오"],
    "6": ["여섯", "엿새"],
    "7": ["일곱", "칠"],
    "8": ["여덟", "팔"],
    "9": ["아홉", "구"],
    "10": ["열", "십"],
}


def nums(s: str) -> set:
    s = s.translate(ZEN2HAN)
    return set(re.findall(r"\d+", s))


def has_native(d: str, ko: str) -> bool:
    return any(f in ko for f in NATIVE_NUM.get(d, []))


def neg(s: str, markers) -> bool:
    return any(m in s for m in markers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()
    code2syl = load_code2syl()
    shipped = load_shipped(code2syl)
    ja = load_ja()

    number_hits, neg_hits = [], []
    checked = 0
    for addr, v in shipped.items():
        ko = v["ko"]
        j = ja.get(addr, "")
        if not (KANA.search(j) and HANGUL.search(ko)):
            continue  # 실대사만
        checked += 1
        jn, kn = nums(j), nums(ko)
        # KO에 숫자도 없고 그 값의 고유어/한자어 표현도 없으면 '진짜 누락' 후보.
        missing = {d for d in (jn - kn) if not has_native(d, ko)}
        if missing:
            number_hits.append((addr, j, ko, missing))
        if neg(j, JA_NEG) != neg(ko, KO_NEG):
            neg_hits.append((addr, j, ko, neg(j, JA_NEG)))

    print(f"=== 의미 드리프트 검사: 실대사 {checked}행 ===")
    print(f"\n[NUMBER] JA 숫자 KO 누락/변경: {len(number_hits)}건")
    for addr, j, ko, miss in number_hits[: args.show]:
        print(f"  0x{addr:06X} miss={sorted(miss)} | JA={j[:30]!r} | KO={ko[:34]!r}")
    print(f"\n[NEGATION] 부정 극성 불일치(반전 후보): {len(neg_hits)}건")
    for addr, j, ko, janeg in neg_hits[: args.show]:
        print(f"  0x{addr:06X} JA부정={janeg} | JA={j[:28]!r} | KO={ko[:32]!r}")

    print(f"\n=== 결과: {'FAIL' if number_hits else 'PASS'} (number {len(number_hits)} / negation {len(neg_hits)} WARN) ===")
    return 1 if number_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
