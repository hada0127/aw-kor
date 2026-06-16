#!/usr/bin/env python3
"""띄어쓰기/줄바꿈 ROM-디코드 게이트 (qa_spacing_from_rom).

출하 ROM 역디코드(integrity_map enc_hex) 기준으로 띄어쓰기 결함을 색출한다.
codex 리뷰: CSV 시뮬레이션이 아니라 post-build ROM 권위.

검사
  1) [JAMMED] 의도 KO에는 공백이 있었으나 출하본은 공백이 0 (level≥4 압축) → 단어 붙음.
  2) [ABBREV] SHORTEN 축약 적용행(level 1/3) — 문법/의미 훼손 위험(에게→에, 있는→있 등).
  3) [GRAMMAR] 출하 KO에 깨진 조사/관형형 시그니처(' 있 ', ' 없 ', '에 ' 인칭 등) 잔존.
  4) [DOUBLE] 연속 공백/선두·후미 공백 이상.

`--json PATH`로 워크리스트(주소·JA·shipped·slot·level·kind·사유) 덤프 → 리뷰 워크플로 입력.
종료코드: JAMMED가 있으면 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from qa_terms_from_rom import load_code2syl, load_ja  # noqa: E402
from qa_integrity_map import decode_enc  # noqa: E402

MAP = os.path.join(BASE, "temp", "integrity_map.json")

# 빌드의 명사/띄어쓰기 통일을 의도값에도 적용해야 JAMMED 오탐(옐로 코멧→옐로코멧 등)을 제거.
try:
    from build_korean_full import normalize_korean_terms as _norm
except Exception:  # 빌드 모듈 임포트 실패 시 핵심 국가명만 보수적 정규화
    _NATION = [('레드 스타', '레드스타'), ('그린 어스', '그린어스'),
               ('옐로 코멧', '옐로코멧'), ('블루 문', '블루문'), ('블랙 홀', '블랙홀')]
    def _norm(t):
        for a, b in _NATION:
            t = t.replace(a, b)
        return t

# SHORTEN 중 문법/의미 훼손 위험이 큰 결과 시그니처(축약 후 출하본에 남는 형태)
GRAMMAR_RISK = [
    ("있 ", "관형형 '있는' 축약"),
    ("있　", "관형형 '있는' 축약"),
    ("없 ", "관형형 '없는' 축약"),
    ("없　", "관형형 '없는' 축약"),
]


def load_rows(code2syl):
    wl = json.load(open(MAP, encoding="utf-8"))
    rows = []
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in wl:
        dec = decode_enc(bytes.fromhex(enc_hex), code2syl)
        rows.append({
            "addr": addr, "slot": slot, "level": level, "kind": kind,
            "intended": ko or "", "shipped": dec,
        })
    return rows


def has_space(s: str) -> bool:
    return (" " in s) or ("　" in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=12)
    ap.add_argument("--json", help="워크리스트 JSON 덤프 경로")
    args = ap.parse_args()
    if not os.path.exists(MAP):
        print(f"[FAIL] 무결성맵 없음: {MAP} (빌드를 먼저 실행)")
        return 1

    code2syl = load_code2syl()
    ja = load_ja()
    rows = load_rows(code2syl)
    # 실제 대사/라벨만(code-region, 빈 텍스트 제외)
    real = [r for r in rows if r["shipped"].strip() and r["kind"] != "fixed_zero_text"]
    print(f"=== 띄어쓰기 ROM 게이트: {len(rows)}행(실텍스트 {len(real)}) ===")

    jammed, abbrev, grammar, dbl = [], [], [], []
    for r in real:
        lv = r["level"]
        intended, shipped = r["intended"], r["shipped"]
        r["ja"] = ja.get(r["addr"], "")
        # 2026-06-16 _fit_variants 재배열 후 레벨: 0=전각공백 1=반각공백 2=전각+축약
        # 3=반각+축약 4=공백제거 5=공백제거+축약, 6~11=부호제거 변형. 축약=2,3,8,9.
        if has_space(_norm(intended)) and not has_space(shipped):
            r["reason"] = "JAMMED: 공백 전부 제거(단어붙음)"
            jammed.append(r)
        elif lv in (2, 3, 8, 9):
            r["reason"] = f"ABBREV: SHORTEN 축약(level{lv})"
            abbrev.append(r)
        for sig, why in GRAMMAR_RISK:
            if sig in shipped:
                r2 = dict(r); r2["reason"] = f"GRAMMAR: {why}"
                grammar.append(r2); break
        if "  " in shipped or "　　" in shipped:
            # 의도적 더블(예/아니오 슬롯 등) 제외 휴리스틱: 라벨성 매우 짧은 건 패스
            if len(shipped.replace("　", " ").strip()) > 6:
                r3 = dict(r); r3["reason"] = "DOUBLE: 연속 공백"
                dbl.append(r3)

    def dump(title, lst):
        print(f"\n[{title}] {len(lst)}건")
        for r in lst[: args.show]:
            print(f"  0x{r['addr']:06X} L{r['level']} {r['kind']} | JA={r['ja'][:22]!r}")
            print(f"      intend={r['intended'][:38]!r}")
            print(f"      ship  ={r['shipped'][:38]!r}")

    dump("JAMMED 단어붙음", jammed)
    dump("ABBREV 축약", abbrev)
    dump("GRAMMAR 조사/관형형 훼손", grammar)
    dump("DOUBLE 연속공백", dbl)

    if args.json:
        worklist = {"jammed": jammed, "abbrev": abbrev, "grammar": grammar, "double": dbl}
        json.dump(worklist, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n[json] {args.json}")

    print(f"\n=== 결과: {'FAIL' if jammed else 'PASS'} (jammed {len(jammed)} / abbrev {len(abbrev)} / grammar {len(grammar)} / double {len(dbl)}) ===")
    return 1 if jammed else 0


if __name__ == "__main__":
    raise SystemExit(main())
