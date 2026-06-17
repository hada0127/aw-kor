#!/usr/bin/env python3
"""명사 통일 ROM-디코드 게이트 (qa_terms_from_rom).

출하 ROM에 **실제로 기록된 한글**(integrity_map의 enc_hex를 역디코드)을 기준으로
`data/proper_nouns.json`의 정본(ko) 대비 금지된 표기 흔들림(variant)이 한 건이라도
남아 있으면 FAIL. CSV 시뮬레이션이 아니라 post-build ROM 권위(codex 리뷰 반영).

검사
  1) [HARD] 금지 표기 잔존: 정본과 다른 변형(예 료우/레드 스타/옐로 코멧)이 출하 KO에 있으면 FAIL.
  2) [INFO] 명사 미반영 후보: JA 원문에 명사 JA형이 있는데 출하 KO에 정본도 변형도 없는 행.

사용
  python3 tools/qa_terms_from_rom.py                  # 기본 integrity_map + proper_nouns
  python3 tools/qa_terms_from_rom.py --show 20        # 샘플 더 보기
종료코드 0=통일 OK, 1=금지 표기 잔존.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from import_bteam_script import _VAR_TOKEN_TERMS  # noqa: E402
from qa_integrity_map import decode_enc  # noqa: E402

MAP = os.path.join(BASE, "temp", "integrity_map.json")
PROPER = os.path.join(BASE, "data", "proper_nouns.json")
FOUND = os.path.join(BASE, "data", "game_wars_found_texts.csv")
SYL_CANDIDATES = [
    os.path.join(BASE, "data", "syllable_to_code_2350.json"),
    os.path.join(BASE, "data", "syllable_to_code.json"),
]


def load_code2syl():
    """음절→코드 맵(2350 우선, 1030 병합)을 코드→음절로 역전."""
    code2syl: dict[int, str] = {}
    for path in reversed(SYL_CANDIDATES):  # 2350이 1030을 덮도록 마지막에 적용
        if not os.path.exists(path):
            continue
        syl = json.load(open(path, encoding="utf-8"))
        for h, c in syl.items():
            code = int(c) if isinstance(c, int) else int(c, 0)
            code2syl[code] = h
    if not code2syl:
        raise SystemExit("syllable_to_code(_2350).json 없음")
    return code2syl


def load_shipped(code2syl):
    """integrity_map → 주소별 최종 출하 KO(last-writer-wins)."""
    wl = json.load(open(MAP, encoding="utf-8"))
    final: dict[int, dict] = {}
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in wl:
        dec = decode_enc(bytes.fromhex(enc_hex), code2syl)
        final[addr] = {"ko": dec, "intended": ko, "level": level, "kind": kind}
    return final


def load_ja():
    ja: dict[int, str] = {}
    with open(FOUND, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                addr = int(parts[0], 16)
            except ValueError:
                continue
            ja[addr] = parts[2]
    return ja


def build_forbidden():
    """proper_nouns.json → [(forbidden_str, canonical_str, term_label)] (정본 미포함만)."""
    d = json.load(open(PROPER, encoding="utf-8"))
    rules: list[tuple[str, str, str]] = []
    for cat in ("characters", "nations", "places", "discovered_candidates"):
        for t in d.get(cat, []):
            canon = (t.get("ko") or "").strip()
            if not canon:
                continue
            allowed = {str(v).strip() for v in (t.get("allowed") or []) if str(v).strip()}
            label = f"{cat}:{t.get('ja','?')}→{canon}"
            for v in t.get("variants", {}):
                v = v.strip()
                if v in allowed:
                    continue
                if v and v != canon and v not in canon and canon not in v:
                    rules.append((v, canon, label))
                elif v and v != canon and (v in canon or canon in v):
                    # 부분문자열 모호 → 별도 보고(자동 스캔 제외)
                    rules.append((v, canon, label + " [SUBSTR-AMBIG]"))
    for it in d.get("issues", []):
        canon = (it.get("chosen_ko") or "").strip()
        allowed = {str(v).strip() for v in (it.get("allowed_ko") or {}) if str(v).strip()}
        for v in it.get("other_ko", {}):
            v = v.strip()
            if v in allowed:
                continue
            if v and v != canon:
                amb = " [SUBSTR-AMBIG]" if (v in canon or canon in v) else ""
                rules.append((v, canon, f"issue:{it.get('ja','?')}→{canon}{amb}"))
    # dedupe
    seen = set()
    uniq = []
    for r in rules:
        if r[:2] in seen:
            continue
        seen.add(r[:2])
        uniq.append(r)
    return uniq


def find_bteam_control_residuals(shipped, ja):
    """B팀 script dump의 ASCII 제어표식이 최종 출하 문자열에 남았는지 검사."""
    var_terms = "|".join(re.escape(t) for t in sorted(_VAR_TOKEN_TERMS, key=len, reverse=True))
    patterns = [
        ("player-name marker i", re.compile(r"(?<![A-Za-z])i(?=[가-힣!?.,…・　\s「」『』“”\"']|$)")),
        ("menu/control prefix", re.compile(r"(?<![A-Za-z0-9])(?:m[a-z]|M[A-Z]|p)(?=[가-힣])")),
        ("branch/wait marker", re.compile(r"(?<=[가-힣.!?・,　\s「」『』“”\"'])(?:[wW]{2,}p?|[wW]+r|rH?|rq[ny]?|q[ny]?|[Kk])(?=$|[가-힣0-9?!.　\s「」『』“”\"'])")),
        ("B팀 circled marker", re.compile(r"[㉠㉡㉢]")),
        ("B팀 variable zero marker", re.compile(rf"(?<![0-9])(?:{var_terms})0")),
    ]
    hits: dict[str, list] = {}
    for addr, v in shipped.items():
        ko = v["ko"]
        for label, pat in patterns:
            if pat.search(ko):
                hits.setdefault(label, []).append((addr, ja.get(addr, ""), ko))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    if not os.path.exists(MAP):
        print(f"[FAIL] 무결성맵 없음: {MAP} (빌드를 먼저 실행)")
        return 1

    code2syl = load_code2syl()
    shipped = load_shipped(code2syl)
    ja = load_ja()
    rules = build_forbidden()

    print(f"=== 명사 통일 ROM 게이트: shipped {len(shipped)}행 / 규칙 {len(rules)}건 ===")

    # 1) HARD: 금지 표기 잔존 (모호 규칙 제외)
    hits: dict[str, list] = {}
    ambiguous: dict[str, int] = {}
    for forbidden, canon, label in rules:
        if "[SUBSTR-AMBIG]" in label:
            cnt = sum(forbidden in v["ko"] for v in shipped.values())
            if cnt:
                ambiguous[f"{forbidden}→{canon} ({label})"] = cnt
            continue
        key = f"{forbidden} → {canon}  ({label})"
        for addr, v in shipped.items():
            if forbidden in v["ko"]:
                hits.setdefault(key, []).append((addr, ja.get(addr, ""), v["ko"]))

    total = sum(len(v) for v in hits.values())
    if hits:
        print(f"\n[HARD-FAIL] 금지 표기 잔존: {total}건 / {len(hits)}종")
        for key, rows in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            print(f"  ✗ {key}: {len(rows)}건")
            for addr, j, ko in rows[: args.show]:
                print(f"      0x{addr:06X} | JA={j[:24]!r} | KO={ko[:40]!r}")
    else:
        print("\n[HARD-OK] 금지 표기 잔존 0건 (자동 스캔 규칙 기준)")

    control_hits = find_bteam_control_residuals(shipped, ja)
    control_total = sum(len(v) for v in control_hits.values())
    if control_hits:
        print(f"\n[HARD-FAIL] B팀 제어표식 잔류: {control_total}건 / {len(control_hits)}종")
        for key, rows in sorted(control_hits.items(), key=lambda kv: -len(kv[1])):
            print(f"  ✗ {key}: {len(rows)}건")
            for addr, j, ko in rows[: args.show]:
                print(f"      0x{addr:06X} | JA={j[:24]!r} | KO={ko[:40]!r}")
    else:
        print("[HARD-OK] B팀 제어표식 잔류 0건")

    if ambiguous:
        print(f"\n[INFO] 부분문자열 모호 규칙(수동 확인 필요): {len(ambiguous)}종")
        for k, c in sorted(ambiguous.items(), key=lambda kv: -kv[1]):
            print(f"  ? {k}: 출하 KO에 {c}회 등장(정본 포함 가능)")

    hard_total = total + control_total
    print(f"\n=== 결과: {'FAIL' if hard_total else 'PASS'} (hard {hard_total}건) ===")
    return 1 if hard_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
