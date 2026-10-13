#!/usr/bin/env python3
"""Decode spacing from a provenance-bound ROM and its final owner/repoint spans.

Wording differences and unsupported coverage are reported separately. A relocated
row is decoded from the actual payload, never substituted with intended text.
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
OUTPUT_ROM = os.path.join(BASE, "output", "game_wars_korean_full.gba")
REPOINT_MANIFEST = os.path.join(BASE, "temp", "repoint_manifest.json")


from pathlib import Path
from qa_dialogue_jamming import rendered_rows, verify_provenance, is_jammed

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


def load_rows(rom_path, map_path, manifest_path):
    verify_provenance(rom_path, map_path, manifest_path)
    return rendered_rows(Path(rom_path).read_bytes(),
                         json.loads(Path(manifest_path).read_text()),
                         json.loads(Path(map_path).read_text()),
                         Path(BASE, 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())


def has_space(s: str) -> bool:
    return (" " in s) or ("　" in s)


_PUNCT = "　 .,!?。、！？・…‘’“”\"'「」『』～~ー-"


def _strip_norm(s: str) -> str:
    """공백·구두점 제거한 음절열 — '같은 번역인데 공백만 제거됐는지' 비교용."""
    return "".join(ch for ch in s if ch not in _PUNCT)


def _is_jam(intended: str, shipped: str) -> bool:
    return is_jammed(_norm(intended), shipped)


def _load_bteam_addrs():
    try:
        d = json.load(open(os.path.join(BASE, "data", "bteam_addresses.json"), encoding="utf-8"))
        lst = d.get("addresses", d) if isinstance(d, dict) else d
        return {int(x, 16) for x in lst}
    except Exception:
        return set()


_BTEAM = _load_bteam_addrs()

_CONJ_VOWELS = {0, 1, 4, 5, 6, 9, 10, 14, 15}  # ㅏㅐㅓㅔㅕㅘㅙㅝㅞ (용언 활용 연결어미)


def _is_aux_attach(before):
    """공백 앞 어절이 용언 활용형(보조용언 붙임 허용)인가 — 끝음절 모음이 ㅏ/ㅓ/ㅕ/ㅐ/ㅘ류 + 받침 없음.
    (놀아·맡겨·보여·들어·가·힘내·봐 → 허용 / 대공·전투·비밀·이름 명사 → 비허용)."""
    w = before.rstrip(" 　.,!?…\"'「」』『】")
    if not w or not ("가" <= w[-1] <= "힣"):
        return False
    x = ord(w[-1]) - 0xAC00
    vowel = (x // 28) % 21
    final = x % 28
    return final == 0 and vowel in _CONJ_VOWELS


def _jam_grade(addr, intended, shipped=""):
    """단어붙음 등급: 'bteam'(짜옹이 권위=WONTFIX), 'acceptable'(비B팀 단일공백 보조용언 붙임=한국어 허용),
    'real'(비B팀 명사구/다중공백/긴문장/구두점변형=진짜 결함). agy·codex 리뷰 반영."""
    if addr in _BTEAM:
        return "bteam"
    t = _norm(intended).strip()
    interior = t.count(" ") + t.count("　")
    syl = sum(1 for c in t if "가" <= c <= "힣")
    if interior == 1 and syl <= 6:
        parts = t.replace("　", " ").split(" ")
        de_spaced = t.replace(" ", "").replace("　", "")
        # 허용 조건(모두 충족): ①정확히 두 어절 ②앞=용언 활용형 ③뒤=보조용언(줘/둬/주마/봐/봅시다/버려…)
        # ④**순수 공백제거**(shipped == 공백뺀 intended, 구두점 변형 없음 — codex: 힘내봅시다,(.→,) 제외).
        if (len(parts) == 2 and _is_aux_attach(parts[0]) and parts[1] and parts[1][0] in "줘주줄둬두봐보봅버"
                and _norm(shipped).strip() == de_spaced):
            return "acceptable"
    return "real"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--show", type=int, default=12)
    ap.add_argument("--json", help="워크리스트 JSON 덤프 경로")
    args = ap.parse_args()
    try:
        rows, unsupported = load_rows(args.rom, args.map, args.manifest)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[FAIL] {exc}")
        return 2
    ja = load_ja()
    print(f"ROM: {args.rom.resolve()}; unsupported owner coverage: {len(unsupported)}")
    # 실제 대사/라벨만(code-region, 빈 텍스트 제외)
    real = [r for r in rows if r["shipped"].strip() and r["kind"] != "fixed_zero_text"]
    print(f"=== 띄어쓰기 ROM 게이트: {len(rows)}행(실텍스트 {len(real)}) ===")

    jammed, abbrev, grammar, dbl = [], [], [], []
    for r in real:
        lv = r["level"]
        intended, shipped = r["intended"], r["shipped"]
        r["ja"] = ja.get(r["addr"], "")
        # _fit_candidates(비용기반) 레벨: 0,1 전체보존 / 2,3 .!?,제거 / 4,5 :;"'제거
        # / 6,7 축약 / 8,9 축약+부호제거 / 10~12 공백제거(단어붙음). 축약=6~9.
        if _is_jam(intended, shipped):
            r["reason"] = "JAMMED: authored separator lost"
            jammed.append(r)
        elif lv in (6, 7, 8, 9):
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

    # 단어붙음 등급 분리: bteam(WONTFIX 권위) / acceptable(짧은구 한국어 허용) / real(진짜 결함)
    for r in jammed:
        r["grade"] = _jam_grade(r["addr"], r["intended"], r["shipped"])
    jam_real = [r for r in jammed if r["grade"] == "real"]
    jam_bteam = [r for r in jammed if r["grade"] == "bteam"]
    jam_ok = [r for r in jammed if r["grade"] == "acceptable"]

    dump("JAMMED 진짜 단어붙음(real, 게이트 대상)", jam_real)
    print(f"\n[JAMMED 보류] B팀 권위(WONTFIX) {len(jam_bteam)} / 짧은구 한국어허용 {len(jam_ok)} — 게이트 비대상")
    dump("ABBREV 축약", abbrev)
    dump("GRAMMAR 조사/관형형 훼손", grammar)
    dump("DOUBLE 연속공백", dbl)

    if args.json:
        worklist = {"unsupported": unsupported, "rom": str(args.rom.resolve()), "jammed": jammed, "jammed_real": jam_real, "jammed_bteam": jam_bteam,
                    "jammed_acceptable": jam_ok, "abbrev": abbrev, "grammar": grammar, "double": dbl}
        json.dump(worklist, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n[json] {args.json}")

    # 게이트는 **진짜 단어붙음(real)**에만 FAIL. B팀 권위/짧은구는 WONTFIX(보류).
    print(f"\n=== 결과: {'FAIL' if jam_real else 'PASS'} "
          f"(jammed real {len(jam_real)} / B팀WONTFIX {len(jam_bteam)} / 짧은구허용 {len(jam_ok)} "
          f"/ abbrev {len(abbrev)} / grammar {len(grammar)} / double {len(dbl)}) ===")
    return 1 if jam_real else 0


if __name__ == "__main__":
    raise SystemExit(main())
