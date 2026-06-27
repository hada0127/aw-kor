#!/usr/bin/env python3
"""QA for compact CO power-name glyph dictionaries.

The dictionaries at 0xA3B880 and 0xB842E8 are not display strings. Runtime
renderers scan target power-name text as two-byte code pairs and look each pair
up in these compact glyph dictionaries. Static line-width QA intentionally skips
the dictionary rows, so this script is the corresponding hard gate.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DISPLAY_OVERRIDES = ROOT / "data" / "display_overrides.json"
DIALOGUE_OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
POWER_DISPLAY_WHITELIST = ROOT / "data" / "compact_power_display_whitelist.json"
REPORT = ROOT / "temp" / "glyph_dictionary_qa.json"

DICT_SPECS = [
    {
        "label": "part2_co_power_profile_dictionary",
        "dict_addr": 0xA3B880,
        "slot": 122,
        "target_ranges": [(0xA2955C, 0xA29830)],
        "expected_target_count": 36,
    },
    {
        "label": "part2_b8_compact_power_dictionary",
        "dict_addr": 0xB842E8,
        "slot": 84,
        "target_ranges": [(0xB84E50, 0xB84F18)],
        "expected_target_count": 11,
    },
]

FALLBACK_DROP_CHARS = set(" \u3000!！?？.,。、・·…:;\"'()[]{}")


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_korean_full", ROOT / "tools" / "build_korean_full.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_required(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"required QA input missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_display_overrides_required() -> dict[int, str]:
    raw = load_json_required(DISPLAY_OVERRIDES)
    if not isinstance(raw, dict):
        raise ValueError("display_overrides.json must be a JSON object")
    out = {}
    for key, value in raw.items():
        if key == "_doc":
            continue
        if not isinstance(key, str) or not key.startswith("0x") or not isinstance(value, str):
            raise ValueError(f"invalid display override entry: {key!r}")
        out[int(key, 16)] = value.strip()
    return out


def load_dialogue_overrides_required() -> dict[int, str]:
    raw = load_json_required(DIALOGUE_OVERRIDES)
    if not isinstance(raw, dict):
        raise ValueError("dialogue_overrides.json must be a JSON object")
    out = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.startswith("0x") or not isinstance(value, str):
            continue
        out[int(key, 16)] = value.strip()
    return out


def load_power_display_whitelist_required() -> dict[int, dict]:
    raw = load_json_required(POWER_DISPLAY_WHITELIST)
    if not isinstance(raw, dict) or not isinstance(raw.get("targets"), dict):
        raise ValueError("compact_power_display_whitelist.json must contain a targets object")
    out = {}
    for key, value in raw["targets"].items():
        if not isinstance(key, str) or not key.startswith("0x") or not isinstance(value, dict):
            raise ValueError(f"invalid compact power whitelist entry: {key!r}")
        addr = int(key, 16)
        display_ko = value.get("display_ko")
        full_ko = value.get("full_ko")
        reason = value.get("reason")
        if not all(isinstance(item, str) and item.strip() for item in (display_ko, full_ko, reason)):
            raise ValueError(f"compact power whitelist entry lacks display_ko/full_ko/reason: {key}")
        out[addr] = {
            "display_ko": display_ko.strip(),
            "full_ko": full_ko.strip(),
            "reason": reason.strip(),
        }
    return out


def pair_hex(data: bytes) -> list[str]:
    return [data[i:i + 2].hex() for i in range(0, len(data), 2)]


def compact_display_text(build, text: str) -> str:
    normalized = build.normalize_for_fit(text or "")
    drop_chars = getattr(build, "COMPACT_GLYPH_DROP_CHARS", FALLBACK_DROP_CHARS)
    return "".join(ch for ch in normalized if ch not in drop_chars)


def encode_compact(build, text: str, syl_to_code: dict[str, int]) -> bytes:
    unmapped = Counter()
    encoded = build.encode_text(compact_display_text(build, text), syl_to_code, unmapped)
    if unmapped:
        raise ValueError(f"unmapped chars: {dict(unmapped)}")
    return encoded


def range_contains(ranges, addr: int) -> bool:
    return any(start <= addr < end for start, end in ranges)


def require_zero_tail(issues: list[dict], *, label: str, address: int, slot_bytes: bytes, used_len: int, slot: int) -> None:
    if len(slot_bytes) != slot:
        issues.append({
            "address": f"0x{address:08X}",
            "issue": f"{label} slot truncated in output ROM",
            "expected_slot": slot,
            "actual_len": len(slot_bytes),
        })
        return
    if 0x20 in slot_bytes:
        issues.append({
            "address": f"0x{address:08X}",
            "issue": f"{label} slot contains ASCII space byte",
            "first_space_offset": slot_bytes.index(0x20),
        })
    tail = slot_bytes[used_len:]
    bad_offsets = [used_len + i for i, b in enumerate(tail) if b != 0]
    if bad_offsets:
        issues.append({
            "address": f"0x{address:08X}",
            "issue": f"{label} slot tail is not zero-filled",
            "first_bad_offsets": bad_offsets[:8],
            "tail_sample": tail[:32].hex(),
        })


def row_slot(row: dict | None) -> int:
    if not row:
        return 0
    try:
        return int(row.get("slot") or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    if not ROM.exists():
        raise FileNotFoundError(f"required QA input missing: {ROM.relative_to(ROOT)}")
    build = load_build_module()
    syl_to_code = {k: int(v, 16) for k, v in load_json_required(Path(build.SYLCODE)).items()}
    dialogue_doc = load_json_required(DIALOGUE_MAP)
    if not isinstance(dialogue_doc, dict) or not isinstance(dialogue_doc.get("lines"), list):
        raise ValueError("dialogue_map.json must contain a top-level lines list")
    dialogue = dialogue_doc["lines"]
    dialogue_by_addr = {}
    for row in dialogue:
        try:
            dialogue_by_addr[int(row.get("address", ""), 16)] = row
        except (TypeError, ValueError):
            continue
    display_overrides = load_display_overrides_required()
    dialogue_overrides = load_dialogue_overrides_required()
    compact_whitelist = load_power_display_whitelist_required()
    address_text_overrides = getattr(build, "ADDRESS_TEXT_OVERRIDES", {})
    derived_dictionaries = build.refresh_compact_glyph_dictionary_overrides(display_overrides, strict=True)
    specs = getattr(build, "COMPACT_GLYPH_DICTIONARY_SPECS", DICT_SPECS)
    allowed_whitelist_addrs = {
        addr
        for addr in compact_whitelist
        if any(range_contains(spec["target_ranges"], addr) for spec in specs)
    }
    if allowed_whitelist_addrs != set(compact_whitelist):
        issues = [{
            "issue": "compact power display whitelist contains address outside dictionary target ranges",
            "outside_addrs": [
                f"0x{addr:08X}"
                for addr in sorted(set(compact_whitelist) - allowed_whitelist_addrs)
            ],
        }]
    else:
        issues = []
    rom = ROM.read_bytes()
    results = []

    for spec in specs:
        daddr = spec["dict_addr"]
        slot = spec["slot"]
        dictionary_text = derived_dictionaries.get(daddr, "")
        encoded, level = build.encode_fit(dictionary_text, slot, syl_to_code, Counter(), daddr)
        if encoded is None:
            issues.append({"dict": f"0x{daddr:08X}", "issue": "dictionary overflow"})
            encoded = b""
        if len(encoded) % 2:
            issues.append({"dict": f"0x{daddr:08X}", "issue": "dictionary odd byte length", "length": len(encoded)})
        bad_leads = [i for i in range(0, len(encoded), 2) if encoded[i] < 0x80]
        if bad_leads:
            issues.append({"dict": f"0x{daddr:08X}", "issue": "dictionary single-byte/ASCII lead", "offsets": bad_leads[:8]})
        if rom[daddr:daddr + len(encoded)] != encoded:
            issues.append({"dict": f"0x{daddr:08X}", "issue": "output ROM dictionary bytes mismatch"})
        require_zero_tail(
            issues,
            label="dictionary",
            address=daddr,
            slot_bytes=rom[daddr:daddr + slot],
            used_len=len(encoded),
            slot=slot,
        )

        dictionary_pairs = {encoded[i:i + 2] for i in range(0, len(encoded), 2)}
        expected_count = spec["expected_target_count"]
        target_addrs = sorted(addr for addr in display_overrides if range_contains(spec["target_ranges"], addr))
        whitelist_addrs = sorted(addr for addr in compact_whitelist if range_contains(spec["target_ranges"], addr))
        if len(target_addrs) != expected_count:
            issues.append({
                "dict": f"0x{daddr:08X}",
                "issue": "target count mismatch",
                "expected": expected_count,
                "actual": len(target_addrs),
                "target_addrs": [f"0x{addr:08X}" for addr in target_addrs],
            })
        if whitelist_addrs != target_addrs:
            issues.append({
                "dict": f"0x{daddr:08X}",
                "issue": "compact power display whitelist mismatch",
                "target_addrs": [f"0x{addr:08X}" for addr in target_addrs],
                "whitelist_addrs": [f"0x{addr:08X}" for addr in whitelist_addrs],
            })
        targets = []
        for addr in target_addrs:
            row = dialogue_by_addr.get(addr)
            if row is None:
                issues.append({"address": f"0x{addr:08X}", "issue": "target missing from dialogue_map"})
            elif row.get("is_noise"):
                issues.append({"address": f"0x{addr:08X}", "issue": "target marked as noise in dialogue_map"})
            text = display_overrides[addr]
            whitelist = compact_whitelist.get(addr)
            if whitelist is None:
                issues.append({"address": f"0x{addr:08X}", "issue": "target missing from compact power display whitelist"})
            else:
                if whitelist["display_ko"] != text:
                    issues.append({
                        "address": f"0x{addr:08X}",
                        "issue": "display override diverges from compact power display whitelist",
                        "display_override": text,
                        "whitelist_display_ko": whitelist["display_ko"],
                    })
                address_override = address_text_overrides.get(addr)
                if address_override is not None and address_override != text:
                    issues.append({
                        "address": f"0x{addr:08X}",
                        "issue": "ADDRESS_TEXT_OVERRIDES compact target diverges from display override",
                        "address_text_override": address_override,
                        "display_override": text,
                    })
                authoritative_full = dialogue_overrides.get(addr)
                if not authoritative_full:
                    issues.append({
                        "address": f"0x{addr:08X}",
                        "issue": "compact power whitelist full_ko has no dialogue_overrides authority",
                        "whitelist_full_ko": whitelist["full_ko"],
                    })
                elif whitelist["full_ko"] != authoritative_full:
                    issues.append({
                        "address": f"0x{addr:08X}",
                        "issue": "compact power whitelist full_ko diverges from dialogue_overrides",
                        "dialogue_override": authoritative_full,
                        "whitelist_full_ko": whitelist["full_ko"],
                    })
            normalized_text = build.normalize_for_fit(text)
            compact_text = compact_display_text(build, text)
            if normalized_text != compact_text:
                issues.append({
                    "address": f"0x{addr:08X}",
                    "issue": "target contains dropped compact-renderer characters",
                    "text": text,
                    "normalized": normalized_text,
                    "compact": compact_text,
                })
            target_enc = encode_compact(build, text, syl_to_code)
            if len(target_enc) % 2:
                issues.append({"address": f"0x{addr:08X}", "issue": "target odd byte length", "text": text})
            missing = sorted({p.hex() for p in (target_enc[i:i + 2] for i in range(0, len(target_enc), 2)) if p not in dictionary_pairs})
            if missing:
                issues.append({
                    "dict": f"0x{daddr:08X}",
                    "address": f"0x{addr:08X}",
                    "issue": "target glyph missing from dictionary",
                    "text": text,
                    "missing_pairs": missing,
                })
            if rom[addr:addr + len(target_enc)] != target_enc:
                issues.append({
                    "address": f"0x{addr:08X}",
                    "issue": "output ROM target bytes mismatch",
                    "text": text,
                    "expected": target_enc.hex(),
                    "actual": rom[addr:addr + len(target_enc)].hex(),
                })
            slot_len = row_slot(row)
            if slot_len <= 0:
                issues.append({"address": f"0x{addr:08X}", "issue": "target slot missing from dialogue_map"})
            else:
                if len(target_enc) > slot_len:
                    issues.append({
                        "address": f"0x{addr:08X}",
                        "issue": "target encoded bytes overflow slot",
                        "text": text,
                        "encoded_len": len(target_enc),
                        "slot": slot_len,
                    })
                require_zero_tail(
                    issues,
                    label="target",
                    address=addr,
                    slot_bytes=rom[addr:addr + slot_len],
                    used_len=len(target_enc),
                    slot=slot_len,
                )
            targets.append({
                "address": f"0x{addr:08X}",
                "text": text,
                "full_ko": (whitelist or {}).get("full_ko"),
                "whitelist_reason": (whitelist or {}).get("reason"),
                "compact": compact_text,
                "slot": slot_len,
                "pairs": pair_hex(target_enc),
            })
        results.append({
            "label": spec["label"],
            "dict_addr": f"0x{daddr:08X}",
            "slot": slot,
            "level": level,
            "derived_text": dictionary_text,
            "encoded_len": len(encoded),
            "pair_count": len(encoded) // 2,
            "unique_pair_count": len(dictionary_pairs),
            "pairs": pair_hex(encoded),
            "target_count": len(targets),
            "expected_target_count": expected_count,
            "targets": targets,
        })

    report = {
        "rom": str(ROM.relative_to(ROOT)),
        "rom_sha256": sha256(ROM) if ROM.exists() else None,
        "dictionary_count": len(specs),
        "compact_power_display_whitelist": str(POWER_DISPLAY_WHITELIST.relative_to(ROOT)),
        "compact_power_display_whitelist_count": len(compact_whitelist),
        "issue_count": len(issues),
        "issues": issues,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dictionary_count": len(specs),
        "issue_count": len(issues),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
