#!/usr/bin/env python3
"""B팀/쪼롱이님 script.txt를 우리 주소체계로 대조·부분 병합한다.

병합 원칙(MERGE_PLAN_BTEAM_2026-06-16):
  - B ROM/코드테이블은 직접 병합하지 않는다.
  - B 확장 ROM의 0x08Fxxxxx 포인터를 원본 ROM 포인터와 대조해 원본 주소를 찾는다.
  - 제어코드가 섞인 전체 메시지는 자동 적용하지 않고 후보 리포트로 남긴다.
  - 자동 적용은 "현재 UI/빌드 표시 번역이 비어 있고, B 텍스트가 슬롯에 안전하게 들어가는"
    조각만 data/dialogue_overrides.json에 추가한다.

기본 실행은 리포트만 생성:
  python3 tools/import_bteam_script.py

안전 후보를 dialogue_overrides.json에 반영:
  python3 tools/import_bteam_script.py --apply-missing
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIG_ROM = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
BTEAM_ROM = ROOT / "temp" / "bteam" / "bteam_rom.gba"
BTEAM_SCRIPT = ROOT / "temp" / "bteam" / "script.txt"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DIALOGUE_OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
OUT = ROOT / "temp" / "bteam" / "import_candidates.json"

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import build_korean_full as B  # noqa: E402


def has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text or "")


def addr_key(addr: int) -> str:
    return "0x%08X" % addr


def parse_script(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-16le").lstrip("\ufeff")
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        try:
            off = int(parts[0], 16)
            length = int(parts[1])
        except ValueError:
            continue
        rows.append({"line": line_no, "bteam_addr": off, "bteam_len": length,
                     "bteam_text": parts[2].removesuffix("㉢")})
    return rows


def pointer_map(original: bytes, bteam: bytes, script_addrs: set[int]) -> dict[int, set[int]]:
    """B 확장 텍스트 주소 -> 원본 텍스트 주소 집합."""
    out: dict[int, set[int]] = {}
    limit = min(len(original), len(bteam)) - 3
    for pos in range(0, limit, 4):
        bv = struct.unpack_from("<I", bteam, pos)[0]
        if not (0x08F00000 <= bv < 0x09110000):
            continue
        target = bv - 0x08000000
        if target not in script_addrs:
            continue
        ov = struct.unpack_from("<I", original, pos)[0]
        if 0x08000000 <= ov < 0x09000000:
            out.setdefault(target, set()).add(ov - 0x08000000)
    return out


_FW_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_PUNCT = {
    "、": ",", "。": ".", "！": "!", "？": "?", "：": ":",
    "（": "(", "）": ")", "／": "/", "ー": "-",
}
_CONTROL_MARKERS = ("㉠", "㉡", "㉢")


def normalize_bteam_text(text: str) -> str:
    text = text.translate(_FW_DIGITS)
    for src, dst in _PUNCT.items():
        text = text.replace(src, dst)
    return text.strip()


def unsafe_reason(text: str) -> str | None:
    if any(mark in text for mark in _CONTROL_MARKERS):
        return "bteam_control_marker"
    # B script는 원본 제어 바이트를 r/k/w/Qn/s0/ps0 같은 ASCII 표식으로 보존한다.
    # 조각 단위 override에 그대로 쓰면 제어 흐름을 깨므로 자동 적용하지 않는다.
    if re.search(r"(^|[^A-Z])[rkw](Qn|[0-9]*|$)|(^|[^A-Z])p?s[0-9]", text):
        return "inline_control_token"
    if not has_hangul(text):
        return "no_hangul"
    return None


def encoded_fit(text: str, slot: int) -> tuple[bool, int | None]:
    unmapped = collections.Counter()
    enc, _level = B.encode_fit(text, slot, B.SYL_TO_CODE if hasattr(B, "SYL_TO_CODE") else _syl_map(), unmapped)
    return enc is not None, len(enc) if enc is not None else None


def _syl_map():
    return {s: int(c, 16) for s, c in json.loads((ROOT / "data" / "syllable_to_code_2350.json").read_text(encoding="utf-8")).items()}


def load_current_dialogue() -> dict[int, dict]:
    if not DIALOGUE_MAP.exists():
        return {}
    data = json.loads(DIALOGUE_MAP.read_text(encoding="utf-8"))
    cur = {}
    for line in data.get("lines", []):
        try:
            addr = int(line["address"], 16)
        except (KeyError, ValueError, TypeError):
            continue
        cur[addr] = line
    return cur


def load_overrides() -> dict:
    if not DIALOGUE_OVERRIDES.exists():
        return {}
    try:
        return json.loads(DIALOGUE_OVERRIDES.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-missing", action="store_true",
                    help="현재 번역이 빈 주소에 한해 안전 후보를 dialogue_overrides.json에 추가")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    rows = parse_script(BTEAM_SCRIPT)
    script_addrs = {r["bteam_addr"] for r in rows}
    pmap = pointer_map(ORIG_ROM.read_bytes(), BTEAM_ROM.read_bytes(), script_addrs)
    slots = B.load_slots()
    current = load_current_dialogue()

    candidates = []
    applied = 0
    overrides = load_overrides()
    seen_apply: set[int] = set()
    for row in rows:
        srcs = sorted(pmap.get(row["bteam_addr"], ()))
        norm = normalize_bteam_text(row["bteam_text"])
        reason = unsafe_reason(norm)
        for addr in srcs:
            slot = slots.get(addr) or 0
            cur = current.get(addr, {})
            cur_ko = (cur.get("ko") or "").strip()
            fit = False
            enc_len = None
            skip = reason
            if not skip and not slot:
                skip = "no_slot"
            if not skip:
                fit, enc_len = encoded_fit(norm, slot)
                if not fit:
                    skip = "slot_overflow"
            missing_now = not cur_ko or cur_ko == (cur.get("ja") or "")
            action = "candidate"
            if skip:
                action = "skip:" + skip
            elif not missing_now:
                action = "keep_existing"
            elif addr in seen_apply:
                action = "duplicate_target"
            elif args.apply_missing:
                overrides[addr_key(addr)] = norm
                seen_apply.add(addr)
                applied += 1
                action = "applied"
            candidates.append({
                "bteam_addr": addr_key(row["bteam_addr"]),
                "source_addr": addr_key(addr),
                "slot": slot,
                "encoded_len": enc_len,
                "ja": cur.get("ja") or "",
                "current_ko": cur_ko,
                "bteam_ko": norm,
                "action": action,
            })

    if args.apply_missing and applied:
        DIALOGUE_OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    summary = {
        "script_rows": len(rows),
        "mapped_rows": sum(1 for r in rows if r["bteam_addr"] in pmap),
        "candidate_rows": len(candidates),
        "safe_missing_candidates": sum(1 for c in candidates if c["action"] in {"candidate", "applied"}),
        "applied": applied,
        "actions": {},
    }
    for c in candidates:
        summary["actions"][c["action"]] = summary["actions"].get(c["action"], 0) + 1
    out = {"summary": summary, "candidates": candidates}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
