#!/usr/bin/env python3
"""B팀/짜옹이님 script.txt를 우리 주소체계로 대조·부분 병합한다.

병합 원칙(MERGE_PLAN_BTEAM_2026-06-16):
  - B ROM/코드테이블은 직접 병합하지 않는다.
  - B 확장 ROM의 0x08Fxxxxx 포인터를 원본 ROM 포인터와 대조해 원본 주소를 찾는다.
  - 기본 안전 모드는 "현재 UI/빌드 표시 번역이 비어 있고, B 텍스트가 슬롯에 안전하게
    들어가는" 조각만 data/dialogue_overrides.json에 추가한다.
  - 권위 덮어쓰기 모드는 B script의 r/k/w/㉠㉡ 제어표현을 제거·분할한 뒤,
    우리 dialogue_groups의 fragment 수와 정확히 맞고 각 슬롯에 들어가는 그룹만 덮는다.
    제어 흐름이 어긋나는 count mismatch 행은 리포트로 남기고 자동 적용하지 않는다.

기본 실행은 리포트만 생성:
  python3 tools/import_bteam_script.py

안전 후보를 dialogue_overrides.json에 반영:
  python3 tools/import_bteam_script.py --apply-missing

B팀 번역을 기존 번역 위에 덮어쓰기(정확 정렬+slot fit만):
  python3 tools/import_bteam_script.py --apply-authoritative
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
DIALOGUE_GROUPS = ROOT / "data" / "dialogue_groups.json"
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
_CONTROL_SPLIT_RE = re.compile(
    r"(?:㉠|㉡|㉢|Qn|Q|ps[0-9]+|s[0-9]+|"
    r"(?<![A-Za-z])[rkw]+(?![A-Za-z])|(?<![A-Za-z])[WK]+(?![A-Za-z]))"
)
_DROP_SEGMENTS = {"", "Y", "N", "n"}
_VAR_TOKEN_TERMS = [
    "대공미사일", "대공전차", "신형 전차", "전투헬기", "수송헬기",
    "경전차", "중전차", "수송차", "수송선", "호위함", "자주포",
    "로켓포", "정찰차", "전투기", "폭격기", "사령관", "보병",
    "전함", "전차", "공격", "점령", "종료", "대기",
]


def strip_bteam_variable_markers(text: str) -> str:
    """B script의 0x32/0x33 변수 기본값 표식(2보병0, 공격0 등)을 제거한다."""
    for term in sorted(_VAR_TOKEN_TERMS, key=len, reverse=True):
        text = re.sub(rf"(?<![0-9])(?:[23])?{re.escape(term)}0", term, text)
    return text


def strip_bteam_control_literals(text: str) -> str:
    """B script의 ASCII 제어 표식을 UI/ROM 문자열로 남기지 않도록 정리한다."""
    # Menu/help prefixes such as mi시스템, MH저장, p통신이 이상해.
    text = re.sub(r"^(?:m[a-z]|M[A-Z]|p)(?=[가-힣])", "", text)
    # Player-name variable marker. The original control byte is outside the
    # editable fragment, so leaving literal "i" is worse than a generic title.
    repls = [
        (r"i 씨의", "사령관님의"),
        (r"i 씨와", "사령관님과"),
        (r"i 씨에게", "사령관님에게"),
        (r"i 씨라면", "사령관님이라면"),
        (r"i 씨", "사령관님"),
        (r"i님의", "사령관님의"),
        (r"i님만", "사령관님만"),
        (r"i님", "사령관님"),
        (r"i 사령관", "사령관"),
        (r"i의", "사령관님의"),
        (r"i가", "사령관님이"),
        (r"i에게", "사령관님에게"),
        (r"i한테", "사령관님한테"),
        (r"i에,", "사령관님,"),
        (r"i와", "사령관님과"),
        (r"i라면", "사령관님이라면"),
    ]
    for src, dst in repls:
        text = re.sub(rf"(?<![A-Za-z]){src}(?![A-Za-z])", dst, text)
    text = re.sub(r"(?<![A-Za-z])i(?=[가-힣!?.,…・　 ]|$)", "사령관님", text)
    # Branch/wait markers that appear after punctuation in B script dumps:
    # ?r, ?rqn, ?rqy, ...WWr다음문장, ...wwwp, !rH, etc.
    text = re.sub(r"(?<=[가-힣.!?・,])(?:[wW]+p?|[W]*rH?|rq[ny]?|q[ny]?)(?=[가-힣0-9?!.])", "", text)
    text = re.sub(r"(?<=[가-힣.!?・,])(?:[wW]+p?|[W]*rH?|rq[ny]?|q[ny]?|R)$", "", text)
    return text


def normalize_bteam_text(text: str) -> str:
    text = text.translate(_FW_DIGITS)
    for src, dst in _PUNCT.items():
        text = text.replace(src, dst)
    text = (text.replace("Ａ", "A").replace("Ｂ", "B").replace("Ｒ", "R")
                .replace("Ｗ", "W").replace("Ｋ", "K").replace("ＨＰ", "HP"))
    # B팀 문체/명칭을 유지하되 명백한 조사 오타만 보정한다.
    text = (text.replace("호이프을", "호이프를")
                .replace("호이프이", "호이프가")
                .replace("안돼는", "안 되는")
                .replace("중인ㄴ", "중인"))
    text = strip_bteam_variable_markers(text)
    text = strip_bteam_control_literals(text)
    text = text.replace("공격해 줘요!", "공격해!")
    text = B.normalize_korean_terms(text)
    return text.strip()


def split_bteam_text(text: str) -> list[str]:
    """B script 제어표현을 제거하고 dialogue fragment 후보로 분해한다."""
    norm = normalize_bteam_text(text)
    out: list[str] = []
    for part in _CONTROL_SPLIT_RE.split(norm):
        part = part.strip(" 　")
        if part in _DROP_SEGMENTS:
            continue
        if part:
            out.append(part)
    return out


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


def load_group_index() -> dict[int, tuple[dict, int]]:
    if not DIALOGUE_GROUPS.exists():
        return {}
    data = json.loads(DIALOGUE_GROUPS.read_text(encoding="utf-8"))
    out = {}
    for group in data.get("groups", []):
        for idx, member in enumerate(group.get("members", [])):
            try:
                addr = int(member["address"], 16)
            except (KeyError, ValueError, TypeError):
                continue
            out[addr] = (group, idx)
    return out


def resolve_group_start(addr: int, group_index: dict[int, tuple[dict, int]]) -> tuple[int | None, dict | None, int | None]:
    """B 포인터가 원본 제어바이트를 가리키는 경우가 있어 +0..+8 범위에서 첫 text fragment를 찾는다."""
    for delta in range(0, 9):
        hit = group_index.get(addr + delta)
        if hit:
            group, idx = hit
            return addr + delta, group, idx
    return None, None, None


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
    ap.add_argument("--apply-authoritative", action="store_true",
                    help="B팀 번역을 기존 번역 위에 덮어쓰기(정확 fragment 정렬+slot fit만)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    rows = parse_script(BTEAM_SCRIPT)
    script_addrs = {r["bteam_addr"] for r in rows}
    pmap = pointer_map(ORIG_ROM.read_bytes(), BTEAM_ROM.read_bytes(), script_addrs)
    slots = B.load_slots()
    current = load_current_dialogue()
    group_index = load_group_index()

    candidates = []
    applied = 0
    overrides = load_overrides()
    seen_apply: set[int] = set()
    seen_group_apply: set[tuple[str, int, int]] = set()
    for row in rows:
        srcs = sorted(pmap.get(row["bteam_addr"], ()))
        norm = normalize_bteam_text(row["bteam_text"])
        reason = unsafe_reason(norm)
        segments = split_bteam_text(row["bteam_text"])
        for addr in srcs:
            slot = slots.get(addr) or 0
            cur = current.get(addr, {})
            cur_ko = (cur.get("ko") or "").strip()
            fit = False
            enc_len = None
            skip = reason
            group_action = None
            group_members = []
            resolved_addr = None
            if args.apply_authoritative and segments:
                resolved_addr, group, start_idx = resolve_group_start(addr, group_index)
                if group is not None and start_idx is not None and len(segments) == 1 and reason is None:
                    member = group.get("members", [])[start_idx]
                    member_addr = int(member["address"], 16)
                    member_slot = slots.get(member_addr) or int(member.get("slot") or 0)
                    ok, enc_len = encoded_fit(segments[0], member_slot)
                    if ok and member_addr not in seen_apply:
                        overrides[member["address"]] = segments[0]
                        seen_apply.add(member_addr)
                        applied += 1
                        group_action = "applied_authoritative_line"
                    elif ok:
                        group_action = "duplicate_line_target"
                    else:
                        group_action = "skip:line_slot_overflow"
                elif group is None or start_idx is None:
                    group_action = "skip:no_group"
                else:
                    tail = group.get("members", [])[start_idx:]
                    if len(tail) != len(segments):
                        group_action = f"skip:fragment_count_mismatch:{len(segments)}:{len(tail)}"
                    else:
                        group_members = tail
                        for seg, member in zip(segments, group_members):
                            member_addr = int(member["address"], 16)
                            member_slot = slots.get(member_addr) or int(member.get("slot") or 0)
                            ok, _n = encoded_fit(seg, member_slot)
                            if not ok:
                                group_action = "skip:group_slot_overflow"
                                break
                        if not group_action:
                            key = (group.get("group_id") or "", start_idx, len(segments))
                            if key in seen_group_apply:
                                group_action = "duplicate_group_target"
                            else:
                                seen_group_apply.add(key)
                                for seg, member in zip(segments, group_members):
                                    overrides[member["address"]] = seg
                                    seen_apply.add(int(member["address"], 16))
                                    applied += 1
                                group_action = "applied_authoritative_group"
            if not args.apply_authoritative:
                if not skip and not slot:
                    skip = "no_slot"
                if not skip:
                    fit, enc_len = encoded_fit(norm, slot)
                    if not fit:
                        skip = "slot_overflow"
            missing_now = not cur_ko or cur_ko == (cur.get("ja") or "")
            action = "candidate"
            if args.apply_authoritative:
                action = group_action or "skip:authoritative_no_action"
            else:
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
                "resolved_addr": addr_key(resolved_addr) if resolved_addr is not None else None,
                "slot": slot,
                "encoded_len": enc_len,
                "ja": cur.get("ja") or "",
                "current_ko": cur_ko,
                "bteam_ko": norm,
                "segments": segments,
                "action": action,
            })

    if (args.apply_missing or args.apply_authoritative) and applied:
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
