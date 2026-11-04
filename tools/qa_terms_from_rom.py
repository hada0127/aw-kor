#!/usr/bin/env python3
"""명사 통일 ROM-디코드 게이트 (qa_terms_from_rom).

출하 ROM에 **실제로 표시되는 한글**을 기준으로 `data/proper_nouns.json`의 정본(ko)
대비 금지된 표기 흔들림(variant)이 한 건이라도 남아 있으면 FAIL.

대상은 활성 텍스트만이다(2026-11-04 Astra B5): 재배치 메시지는 repoint manifest의
현재 할당(모든 포인터가 new_addr를 가리키는지 확인)을 토큰 단위로 읽고, 제자리 행은
integrity map의 마지막 소유 바이트를 ROM에서 읽는다. 원래 자리·옛 할당
(*-retired-allocation, 대사 풀의 비활성 영역)·superseded 의도 행은 제외한다.
스크립트 렌더러의 네이티브 제어(r/w/k, 1편 i=이름, 2…0 강조 등)는 글자가 아니다.
한 음절 변형(예 몹)은 이름으로 쓰인 경우만 센다(몹시·몹쓸 같은 일반어 제외).

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
MANIFEST = os.path.join(BASE, "temp", "repoint_manifest.json")
ROM = os.path.join(BASE, "output", "game_wars_korean_full.gba")
ORIGINAL = os.path.join(BASE, "original", "Game Boy Wars Advance 1+2 (Japan).gba")
GBA = 0x08000000
# dialogue_rewrite_apply.ARENA_START/END: relocated dialogue pool. A text write
# there that is not inside a current relocated payload is an old allocation.
ARENA = (0xA3D000, 0xAFF000)
RETIRED_TAGS = ("dialogue-rewrite-retired-allocation", "spacing-retired-allocation",
                "dialogue-spacing-final-intent-superseded")
# Particles/titles that may follow a one-syllable name. Anything else (몹시,
# 몹쓸) is an ordinary word that merely starts with the same syllable.
NAME_FOLLOWERS = ("님", "씨", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과",
                  "도", "만", "야", "아", "여", "랑", "한테", "께", "로", "으로", "나리", "군",
                  "사령관", "장군", "쇼군")
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
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind, *_metadata in wl:
        dec = decode_enc(bytes.fromhex(enc_hex), code2syl)
        final[addr] = {"ko": dec, "intended": ko, "level": level, "kind": kind}
    return final


def _token_text(payload, game, code2syl):
    """Visible text of a script payload; native controls never become letters."""
    from dialogue_pixel_layout import tokenize
    if not payload.rstrip(b"\xff").endswith(b"\0"):
        payload = payload + b"\0"
    out = []
    for t in tokenize(payload, game):
        kind = t["kind"]
        if kind in ("glyph", "space"):
            out.append(decode_enc(t["raw"], code2syl) if len(t["raw"]) == 2 else " ")
        elif kind in ("newline", "page"):
            out.append(" ")  # row/page break separates words
        elif kind == "unknown":
            b = t["raw"][0]
            out.append(chr(b) if 0x21 <= b <= 0x7E else "▯")
        elif kind == "end":
            break
        # wait/format/style/speed/choice/name/icon/padding draw no letters here
    return "".join(out)


def _intervals_hit(intervals, lo, hi):
    import bisect
    i = bisect.bisect_right(intervals, (lo, float("inf"))) - 1
    for a, b in intervals[max(i, 0):]:
        if a >= hi:
            break
        if a < hi and lo < b:
            return True
    return False


def load_active(code2syl, rom_path=None, map_path=None, manifest_path=None):
    """Active shipped text keyed by start address, plus coverage stats.

    Relocated messages: the manifest's current allocation, only when every
    pointer site points there (else ValueError), read token-aware. In-place
    rows: the live (last-writer) bytes of each integrity-map text write, read
    from the ROM. Original slots of relocated messages, retired allocations,
    superseded intents and the inactive arena are excluded.
    """
    from renderer_text import renderer_for_address, P1_SCRIPT, P2_SCRIPT
    with open(rom_path or ROM, "rb") as f:
        rom = f.read()
    with open(map_path or MAP, encoding="utf-8") as f:
        writes = json.load(f)
    with open(manifest_path or MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    active: dict[int, dict] = {}
    stats = {"relocated": 0, "inplace": 0, "retired_rows": 0, "token_fallback": 0}
    covered, dead = [], []
    for m in manifest:
        if m.get("status") != "relocated":
            continue
        source, target, size = int(m["msg"], 16), int(m["new_addr"], 16), int(m["new_len"])
        for site in m.get("ptr_sites") or []:
            site = int(site, 16)
            if int.from_bytes(rom[site:site + 4], "little") != GBA + target:
                raise ValueError(f"0x{source:06X}: pointer 0x{site:06X} does not reach 0x{target:06X}")
        if not m.get("ptr_sites"):
            raise ValueError(f"0x{source:06X}: relocated message lacks ptr_sites")
        game = "p1" if source >= 0xB00000 else "p2"
        payload = rom[target:target + size]
        try:
            text = _token_text(payload, game, code2syl)
        except ValueError:
            stats["token_fallback"] += 1
            text = decode_enc(payload, code2syl)
        active[target] = {"ko": text, "source": source, "kind": "relocated"}
        covered.append((target, target + size))
        dead.append((source, source + int(m["old_len"])))
        stats["relocated"] += 1
    covered.sort()
    dead.sort()
    occupied = bytearray(len(rom))
    for entry in reversed(writes):
        addr, slot, enc_len, enc_hex, _fill, ko, level, kind = entry[:8]
        size = max(int(slot), len(bytes.fromhex(enc_hex))) if enc_hex else int(slot)
        if size <= 0 or addr < 0 or addr + size > len(rom):
            continue
        live = [not occupied[addr + k] for k in range(size)]
        occupied[addr:addr + size] = b"\1" * size
        if kind in RETIRED_TAGS:
            stats["retired_rows"] += 1
            continue
        if not enc_hex or "pointer" in str(kind) or str(kind).startswith("repoint:"):
            continue
        enc_end = addr + len(bytes.fromhex(enc_hex))
        start = None
        for k in range(enc_end - addr + 1):
            alive = k < enc_end - addr and live[k]
            if alive and start is None:
                start = k
            elif not alive and start is not None:
                lo, hi = addr + start, addr + k
                start = None
                if (_intervals_hit(covered, lo, hi) or _intervals_hit(dead, lo, hi)
                        or (ARENA[0] <= lo < ARENA[1])):
                    continue
                payload = rom[lo:hi]
                renderer = renderer_for_address(lo)
                text = None
                if renderer in (P1_SCRIPT, P2_SCRIPT):
                    try:
                        text = _token_text(payload, "p1" if renderer == P1_SCRIPT else "p2", code2syl)
                    except ValueError:
                        stats["token_fallback"] += 1
                if text is None:
                    text = decode_enc(payload, code2syl)
                active[lo] = {"ko": text, "intended": ko, "level": level, "kind": kind}
                stats["inplace"] += 1
    return active, stats


_HANGUL = re.compile(r"[가-힣]")


def name_occurrences(text, variant):
    """Occurrences of a forbidden variant. One-syllable variants count only as
    a standalone name: not glued to a preceding syllable, and followed by a
    non-Hangul character or a particle/title (몹님 yes, 몹시 no)."""
    if len(variant) != 1 or not _HANGUL.fullmatch(variant):
        return text.count(variant)
    count = 0
    for i, ch in enumerate(text):
        if ch != variant or (i and _HANGUL.match(text[i - 1])):
            continue
        rest = text[i + 1:]
        if not rest or not _HANGUL.match(rest[0]) or rest.startswith(NAME_FOLLOWERS):
            count += 1
    return count


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
    ap.add_argument("--rom", default=ROM)
    ap.add_argument("--map", default=MAP)
    ap.add_argument("--repoint-manifest", default=MANIFEST)
    args = ap.parse_args()

    for label, path in (("ROM", args.rom), ("무결성맵", args.map), ("repoint manifest", args.repoint_manifest)):
        if not os.path.exists(path):
            print(f"[FAIL] {label} 없음: {path} (빌드를 먼저 실행)")
            return 1

    code2syl = load_code2syl()
    try:
        shipped, stats = load_active(code2syl, args.rom, args.map, args.repoint_manifest)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"[HARD-FAIL] 활성 텍스트 판정 실패: {exc}")
        return 1
    # Relocated rows carry the native source address for the JA lookup.
    ja_all = load_ja()
    ja = {addr: ja_all.get(v.get("source", addr), "") for addr, v in shipped.items()}
    rules = build_forbidden()

    print(f"=== 명사 통일 ROM 게이트: 활성 {len(shipped)}행 (재배치 {stats['relocated']} / "
          f"제자리 {stats['inplace']}; 제외 retired {stats['retired_rows']}, "
          f"토큰 fallback {stats['token_fallback']}) / 규칙 {len(rules)}건 ===")

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
            if name_occurrences(v["ko"], forbidden):
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
