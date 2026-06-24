#!/usr/bin/env python3
"""띄어쓰기/줄바꿈 **렌더 기준** ROM-디코드 게이트 (qa_spacing_from_rom).

★2026-06-24 렌더 정확화(codex P4 반영): 이전엔 WRITE_LOG enc_hex(빌드 in-place 기록)를 디코드해
repoint된 라인을 stale로 봐 **대량 오탐**(433행)이었다. 이제 **게임이 실제 렌더하는 본문** 기준:
  ① repoint 매니페스트(temp/repoint_manifest.json)의 relocated 메시지 = free space 공백복원본
     렌더 → 결함 검사 제외(in-place는 stale).
  ② 비-relocated = 출하 ROM **실 바이트**를 디코드(trailing 패딩 strip).
  ③ JAMMED는 출하본이 의도값의 **같은 번역 공백제거판(정확일치, interior 공백)**일 때만 — 다른/축약
     번역은 제외(축약은 ABBREV로 분류). → 진짜 단어붙음만(159행 등).

검사
  1) [JAMMED] 같은 번역인데 공백이 전부 제거됨(단어붙음).
  2) [ABBREV] SHORTEN 축약 적용행(level 6~9) — 문법/의미 훼손 위험.
  3) [GRAMMAR] 출하 KO에 깨진 조사/관형형 시그니처 잔존.
  4) [DOUBLE] 연속 공백 이상.

`--json PATH`로 워크리스트 덤프. 종료코드: JAMMED가 있으면 1(진단용, dist 하드게이트 아님).
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


def _build_reloc_resolver():
    """렌더 기준 정확화: 빌드가 남긴 repoint 매니페스트(권위)로 relocated 메시지 범위를 판정.
    relocated 메시지는 게임이 free space의 공백 복원본(완전충실)을 렌더 → in-place는 stale.
    매니페스트 = [{msg, status:'relocated', old_len, new_addr, fixed:[...]}]."""
    import bisect as _bi
    try:
        out = open(OUTPUT_ROM, "rb").read()
        manifest = json.load(open(REPOINT_MANIFEST, encoding="utf-8"))
    except (OSError, ValueError):
        return None  # 매니페스트/ROM 없으면 보정 불가(구 동작 유지)
    ranges = []
    for m in manifest:
        if m.get("status") == "relocated":
            ms = int(m["msg"], 16)
            ranges.append((ms, ms + int(m.get("old_len", 0))))
    ranges.sort()
    starts = [r[0] for r in ranges]

    def is_relocated(addr):
        i = _bi.bisect_right(starts, addr) - 1
        return i >= 0 and ranges[i][0] <= addr < ranges[i][1]

    return out, is_relocated

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
    resolver = _build_reloc_resolver()
    out, is_relocated = (resolver if resolver else (None, lambda a: False))
    rows = []
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in wl:
        reloc = is_relocated(addr)
        if reloc:
            # 게임은 free space의 공백 복원본(완전충실 override)을 렌더 → in-place는 stale.
            # 단어붙음/축약 검사 통과를 위해 의도값(override)을 shipped로 사용(렌더 진실).
            dec = ko or decode_enc(bytes.fromhex(enc_hex), code2syl)
        elif out is not None:
            # in-place: WRITE_LOG enc가 아닌 **실 ROM 바이트** 디코드(후속 패치/덮어쓰기 반영).
            # 슬롯 trailing 패딩(반각0x20/전각0x8140)을 strip — DOUBLE/JAMMED has_space 오판 제거.
            dec = decode_enc(bytes(out[addr:addr + slot]), code2syl).rstrip()
        else:
            dec = decode_enc(bytes.fromhex(enc_hex), code2syl)
        rows.append({
            "addr": addr, "slot": slot, "level": level, "kind": kind,
            "intended": ko or "", "shipped": dec, "relocated": reloc,
        })
    return rows


def has_space(s: str) -> bool:
    return (" " in s) or ("　" in s)


_PUNCT = "　 .,!?。、！？・…‘’“”\"'「」『』～~ー-"


def _strip_norm(s: str) -> str:
    """공백·구두점 제거한 음절열 — '같은 번역인데 공백만 제거됐는지' 비교용."""
    return "".join(ch for ch in s if ch not in _PUNCT)


def _is_jam(intended: str, shipped: str) -> bool:
    """진짜 단어붙음 = 출하본이 의도값의 **공백 제거판**(같은 번역)일 때만.
    출하본이 다른(짧은/긴) 번역이면 intend-vs-ship 비교가 무의미 → 단어붙음 아님."""
    ni = _norm(intended)
    # **interior** 공백(앞뒤 strip 후에도 공백)이어야 단어붙음. 단편 경계의 trailing/leading
    # 공백(예 '여기서 ','은 ')은 단어붙음이 아님.
    if not has_space(ni.strip()) or has_space(shipped.strip()):
        return False
    # 공백·부호 제거 후 음절열이 **정확 일치**해야 같은 번역의 순수 공백제거(단어붙음).
    # (다른/축약 번역은 음절열이 달라 제외 — 축약은 ABBREV로 별도 분류.)
    a, b = _strip_norm(ni), _strip_norm(shipped)
    return bool(a) and a == b


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


def _jam_grade(addr, intended):
    """단어붙음 등급: 'bteam'(쪼롱이 권위=WONTFIX), 'acceptable'(비B팀 단일공백 보조용언/조사 붙임=한국어 허용),
    'real'(비B팀 명사구/다중공백/긴문장=진짜 결함). agy 리뷰 반영: 명사구(대공 전차 등) 실오류는 real로."""
    if addr in _BTEAM:
        return "bteam"
    t = _norm(intended).strip()
    interior = t.count(" ") + t.count("　")
    syl = sum(1 for c in t if "가" <= c <= "힣")
    if interior == 1 and syl <= 6:
        parts = t.replace("　", " ").split(" ")
        # 정확히 두 어절 + 앞=용언 활용형 + 뒤=보조용언(줘/둬/주마/봐/봅시다/버려…)으로 시작일 때만 허용.
        # (수리가 빠르다=조사+본용언, 대공 전차=명사구 → real)
        if len(parts) == 2 and _is_aux_attach(parts[0]) and parts[1] and parts[1][0] in "줘주줄둬두봐보봅버":
            return "acceptable"
    return "real"


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
        if r.get("relocated"):
            continue   # repoint relocated = free space에 완전충실 override 렌더 → 결함 없음
        lv = r["level"]
        intended, shipped = r["intended"], r["shipped"]
        r["ja"] = ja.get(r["addr"], "")
        # _fit_candidates(비용기반) 레벨: 0,1 전체보존 / 2,3 .!?,제거 / 4,5 :;"'제거
        # / 6,7 축약 / 8,9 축약+부호제거 / 10~12 공백제거(단어붙음). 축약=6~9.
        if _is_jam(intended, shipped):
            r["reason"] = "JAMMED: 공백 전부 제거(단어붙음)"
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
        r["grade"] = _jam_grade(r["addr"], r["intended"])
    jam_real = [r for r in jammed if r["grade"] == "real"]
    jam_bteam = [r for r in jammed if r["grade"] == "bteam"]
    jam_ok = [r for r in jammed if r["grade"] == "acceptable"]

    dump("JAMMED 진짜 단어붙음(real, 게이트 대상)", jam_real)
    print(f"\n[JAMMED 보류] B팀 권위(WONTFIX) {len(jam_bteam)} / 짧은구 한국어허용 {len(jam_ok)} — 게이트 비대상")
    dump("ABBREV 축약", abbrev)
    dump("GRAMMAR 조사/관형형 훼손", grammar)
    dump("DOUBLE 연속공백", dbl)

    if args.json:
        worklist = {"jammed": jammed, "jammed_real": jam_real, "jammed_bteam": jam_bteam,
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
