#!/usr/bin/env python3
"""Audit where build-time authorities intentionally shadow import CSV text."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TRANS = ROOT / "data" / "translation_for_import.csv"
DIALOGUE_OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
INTEGRITY_MAP = ROOT / "temp" / "integrity_map.json"
REPOINT_MANIFEST = ROOT / "temp" / "repoint_manifest.json"
DEFAULT_REPORT = ROOT / "temp" / "csv_override_shadow_audit.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_korean_full as B  # noqa: E402
import qa_text_fit  # noqa: E402


def norm_addr(value: Any) -> str | None:
    try:
        return "0x%08X" % int(value, 16 if isinstance(value, str) else 10)
    except (TypeError, ValueError):
        return None


def has_hangul(text: str) -> bool:
    return any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in text or "")


def short(text: Any, limit: int = 96) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[: limit - 1] + "..."


def compact_norm(text: str) -> str:
    drop = set(" \u3000\r\n\t.,!?;:。、！？・…'\"`~～-ー「」『』（）()[]")
    return "".join(ch for ch in (text or "") if ch not in drop)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def load_dialogue_overrides() -> dict[int, str]:
    out: dict[int, str] = {}
    raw = load_json(DIALOGUE_OVERRIDES, {})
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        canonical = B.canonical_override_addr(key)
        if canonical:
            out[int(canonical, 16)] = str(value or "")
    return out


def load_integrity_map() -> dict[int, dict[str, Any]]:
    final: dict[int, dict[str, Any]] = {}
    for entry in load_json(INTEGRITY_MAP, []):
        if not isinstance(entry, list) or len(entry) < 8:
            continue
        try:
            addr = int(entry[0])
        except (TypeError, ValueError):
            continue
        final[addr] = {
            "slot": entry[1],
            "encoded_len": entry[2],
            "korean": str(entry[5] or ""),
            "level": entry[6],
            "kind": str(entry[7] or ""),
        }
    return final


def load_repoint_fixed_addrs() -> set[int]:
    fixed: set[int] = set()
    for item in load_json(REPOINT_MANIFEST, []):
        if not isinstance(item, dict):
            continue
        for value in item.get("fixed", []) or []:
            n = norm_addr(value)
            if n:
                fixed.add(int(n, 16))
    return fixed


def load_direct_patches() -> dict[int, str]:
    out: dict[int, str] = {}
    for addr, (_end, text) in qa_text_fit.load_direct_patch_texts().items():
        out[int(addr)] = str(text or "")
    return out


def effective_model(
    *,
    addr: int,
    ja: str,
    csv_ko: str,
    slots: dict[int, int],
    addr_overrides: dict[int, str],
    source_overrides: dict[str, str],
    text_overrides: dict[str, str],
    display_overrides: dict[int, str],
    dialogue_overrides: dict[int, str],
    direct_patches: dict[int, str],
    repointed_fixed: set[int],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    ko = csv_ko
    if addr in addr_overrides:
        ko = addr_overrides[addr]
        reasons.append("address_override")
    else:
        if ja in source_overrides and not has_hangul(ko):
            ko = source_overrides[ja]
            reasons.append("source_text_override")
        if ko in text_overrides:
            ko = text_overrides[ko]
            reasons.append("text_override")
    if addr in direct_patches:
        ko = direct_patches[addr]
        reasons.append("direct_patch")
    if addr in dialogue_overrides and addr not in addr_overrides:
        ko = dialogue_overrides[addr]
        reasons.append("dialogue_override")
    if addr in display_overrides:
        ko = display_overrides[addr]
        reasons.append("display_override")
    slot = slots.get(addr, 0)
    if slot > 0 and B.in_region(B.PAIR_RENDERER_REGIONS, addr, addr + slot):
        normalized = B.normalize_pair_renderer_text(ko)
        if normalized != ko:
            ko = normalized
            reasons.append("pair_renderer_normalize")
    if addr in repointed_fixed:
        reasons.append("repoint_payload")
    return str(ko or ""), reasons


def build_report() -> dict[str, Any]:
    if hasattr(B, "refresh_compact_glyph_dictionary_overrides"):
        B.refresh_compact_glyph_dictionary_overrides(B.load_display_overrides(), strict=True)

    slots = B.load_slots()
    addr_overrides = {int(k): str(v or "") for k, v in B.ADDRESS_TEXT_OVERRIDES.items()}
    source_overrides = {str(k or ""): str(v or "") for k, v in B.SOURCE_TEXT_OVERRIDES.items()}
    text_overrides = {str(k or ""): str(v or "") for k, v in B.TEXT_OVERRIDES.items()}
    display_overrides = {int(k): str(v or "") for k, v in B.load_display_overrides().items()}
    dialogue_overrides = load_dialogue_overrides()
    direct_patches = load_direct_patches()
    final_writes = load_integrity_map()
    repointed_fixed = load_repoint_fixed_addrs()

    rows = 0
    valid_rows = 0
    shadowed: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    model_actual_divergences: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    actual_kind_counts: Counter[str] = Counter()

    with TRANS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            n = norm_addr(row.get("address"))
            if not n:
                continue
            addr = int(n, 16)
            valid_rows += 1
            ja = str(row.get("japanese") or "").strip()
            csv_ko = str(row.get("korean") or "").strip()
            model_ko, reasons = effective_model(
                addr=addr,
                ja=ja,
                csv_ko=csv_ko,
                slots=slots,
                addr_overrides=addr_overrides,
                source_overrides=source_overrides,
                text_overrides=text_overrides,
                display_overrides=display_overrides,
                dialogue_overrides=dialogue_overrides,
                direct_patches=direct_patches,
                repointed_fixed=repointed_fixed,
            )
            actual = final_writes.get(addr)
            actual_ko = str((actual or {}).get("korean") or "")
            actual_kind = str((actual or {}).get("kind") or "")
            if actual_kind:
                actual_kind_counts[actual_kind] += 1

            differs_from_csv = compact_norm(model_ko) != compact_norm(csv_ko)
            actual_differs_from_csv = bool(actual_ko) and compact_norm(actual_ko) != compact_norm(csv_ko)
            if not reasons and actual_kind and not actual_kind.startswith("import-csv"):
                reasons.append(f"write_kind:{actual_kind}")
            if reasons:
                for reason in reasons:
                    reason_counts[reason] += 1
            if differs_from_csv or actual_differs_from_csv or reasons:
                rec = {
                    "address": n,
                    "reasons": reasons,
                    "csv_ko": short(csv_ko),
                    "model_ko": short(model_ko),
                    "actual_ko": short(actual_ko),
                    "actual_kind": actual_kind,
                }
                shadowed.append(rec)
                if actual_differs_from_csv and not reasons:
                    unexplained.append(rec)
                if actual_ko and model_ko and compact_norm(actual_ko) != compact_norm(model_ko):
                    # Repoint payload rows can carry full message spacing/punctuation,
                    # so keep them visible but do not make them a hard failure.
                    if "repoint_payload" not in reasons:
                        model_actual_divergences.append(rec)

    return {
        "csv_rows": rows,
        "csv_valid_rows": valid_rows,
        "shadowed_count": len(shadowed),
        "reason_counts": dict(sorted(reason_counts.items())),
        "actual_kind_counts": dict(sorted(actual_kind_counts.items())),
        "unexplained_shadow_count": len(unexplained),
        "unexplained_shadow_examples": unexplained[:80],
        "model_actual_divergence_count": len(model_actual_divergences),
        "model_actual_divergence_examples": model_actual_divergences[:80],
        "shadow_examples": shadowed[:200],
        "input_files": {
            "translation_csv": str(TRANS.relative_to(ROOT)),
            "integrity_map": str(INTEGRITY_MAP.relative_to(ROOT)) if INTEGRITY_MAP.exists() else None,
            "repoint_manifest": str(REPOINT_MANIFEST.relative_to(ROOT)) if REPOINT_MANIFEST.exists() else None,
            "dialogue_overrides": str(DIALOGUE_OVERRIDES.relative_to(ROOT)) if DIALOGUE_OVERRIDES.exists() else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_report()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("CSV override shadow audit")
    print(f"- csv rows: {report['csv_rows']} valid: {report['csv_valid_rows']}")
    print(f"- shadowed/explained rows: {report['shadowed_count']}")
    print(f"- unexplained output shadows: {report['unexplained_shadow_count']}")
    print(f"- model/actual divergences (informational): {report['model_actual_divergence_count']}")
    print("- reasons:")
    for key, value in report["reason_counts"].items():
        print(f"  {key}: {value}")
    print(f"- report: {report_path.relative_to(ROOT)}")

    hard_fail = report["unexplained_shadow_count"] > 0
    if args.strict and hard_fail:
        print("[FAIL] CSV override shadow audit", file=sys.stderr)
        return 1
    print("[OK] CSV override shadow audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
