#!/usr/bin/env python3
"""Audit ADDRESS_TEXT_OVERRIDES governance.

This protects the build-safe hand overrides from the two failure modes that
already caused fresh-screen corruption:

1. Duplicate source keys in tools/build_korean_full.py.
2. UI/editor data drifting away from the effective ROM text.

dialogue_overrides collisions are reported, not failed, because legacy editor
overrides may intentionally remain in the file while the build ignores them for
protected addresses. The hard invariant is that source duplicates are zero and
dialogue_map displays the effective protected text.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_korean_full.py"
DIALOGUE_OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DIALOGUE_GROUPS = ROOT / "data" / "dialogue_groups.json"
ADDRESS_TEXT_OVERRIDES_TSV = ROOT / "data" / "address_text_overrides.tsv"
DEFAULT_REPORT = ROOT / "temp" / "address_text_overrides_audit.json"

# The 21 direct-writer discrepancies recorded in the 2026-10-12 address
# override investigation. Twenty were dead in-place slots after relocation.
# Keep this regression cohort explicit; other script rows have independent
# reviewed source/display policies and are not judged by this comparison.
SEMANTIC_REGRESSION_ADDRESSES = frozenset({
    0xA03EB8, 0xA05855, 0xD8FE8A, 0xD9831A, 0xD9E04C,
    0xDC3038, 0xDC6331, 0xDC655F, 0xDC690D, 0xDC6FC8,
    0xDC86F9, 0xDC8A0F, 0xDCADA5, 0xDCAFE7, 0xDCB666,
    0xDCC2F8, 0xDCD329, 0xDCD64D, 0xDCE5CF, 0xDCFAD2,
    0xDD17D1,
})


def audit_rom_semantics(rom_path: Path, manifest_path: Path,
                        protected: dict[int, str]) -> dict[str, Any]:
    """Check direct script owners at their live repointed line spans."""
    from qa_integrity_map import decode_enc, load_syl
    from qa_bteam_drift import display_equivalent
    import qa_text_fit
    import hashlib
    import struct
    from bisect import bisect_right
    import build_korean_poc as P

    rom = rom_path.read_bytes()
    original = Path(P.ROM).read_bytes()
    receipt = json.loads(Path(str(rom_path) + ".build.json").read_text(encoding="utf-8"))
    if (receipt.get("rom_sha256") != hashlib.sha256(rom).hexdigest()
            or receipt.get("source_sha256") != hashlib.sha256(original).hexdigest()
            or receipt.get("build_metadata", {}).get("temp/repoint_manifest.json")
            != hashlib.sha256(manifest_path.read_bytes()).hexdigest()):
        raise ValueError("build receipt ROM/source/manifest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Original pointer targets define message ownership independently of the
    # supplied relocation records, including when one record is omitted.
    original_sites: dict[int, list[int]] = defaultdict(list)
    for site, (pointer,) in enumerate(struct.iter_unpack("<I", original), start=0):
        target = pointer - 0x08000000
        if 0 <= target < len(original):
            original_sites[target].append(site * 4)
    starts = sorted(original_sites)
    def owner_of(addr: int) -> int | None:
        index = bisect_right(starts, addr) - 1
        return starts[index] if index >= 0 else None

    relocated: dict[int, tuple[int, int, int]] = {}
    for message in manifest:
        if message.get("status") != "relocated":
            continue
        target = int(message["new_addr"], 16)
        length = int(message["new_len"])
        source = int(message["msg"], 16)
        old_length = int(message["old_len"])
        sites = message.get("ptr_sites")
        if (not sites or old_length <= 0 or source < 0
                or source + old_length > len(original)
                or target < 0 or target + length > len(rom)):
            raise ValueError(f"invalid repoint manifest entry: {message['msg']}")
        for site_hex in sites:
            site = int(site_hex, 16)
            if site < 0 or site + 4 > len(rom) or site + 4 > len(original):
                raise ValueError(f"repoint site outside ROM: {site_hex}")
            if int.from_bytes(original[site:site + 4], "little") != 0x08000000 + source:
                raise ValueError(f"original pointer ownership mismatch: {message['msg']} {site_hex}")
            live_target = int.from_bytes(rom[site:site + 4], "little") - 0x08000000
            if live_target != target:
                raise ValueError(f"repoint manifest does not match ROM: {message['msg']} {site_hex}")
        for key, span in message.get("line_spans", {}).items():
            offset, size = span
            if offset < 0 or size <= 0 or offset + size > length:
                raise ValueError(f"invalid repoint line span: {message['msg']} {key}")
            addr = int(key, 16)
            if (addr in SEMANTIC_REGRESSION_ADDRESSES
                    and (not source <= addr < source + old_length or owner_of(addr) != source)):
                raise ValueError(f"repoint source ownership mismatch: {message['msg']} {key}")
            if addr in relocated:
                raise ValueError(f"duplicate repoint line: {key}")
            relocated[addr] = (target + offset, size, target)

    codes = load_syl()
    mismatches = []
    checked = 0
    followed = 0
    direct = qa_text_fit.load_direct_patch_texts(include_writer=True)
    for addr in sorted(SEMANTIC_REGRESSION_ADDRESSES):
        if addr not in protected or addr not in direct or direct[addr][2] != "patch_script_row":
            raise ValueError(f"semantic regression authority missing: 0x{addr:08X}")
        _end, _text, writer = direct[addr]
        if writer != "patch_script_row":
            continue
        checked += 1
        if addr in relocated:
            pos, size, _target = relocated[addr]
            followed += 1
        else:
            owner = owner_of(addr)
            if owner is not None and any(
                    original[site:site + 4] != rom[site:site + 4]
                    for site in original_sites[owner]):
                raise ValueError(f"missing relocated line span or relocation record: 0x{addr:08X}")
            pos = addr
            size = _end - addr
        if pos < 0 or size <= 0 or pos + size > len(rom):
            raise ValueError(f"invalid protected ROM span: 0x{addr:08X}")
        payload = rom[pos:pos + size].rstrip(b" \x00")
        actual = decode_enc(payload.replace(b"\x72\x0a\x09", b"\x81\x40"), codes).rstrip(" \u3000")
        wanted = display_equivalent(protected[addr], addr).rstrip(" \u3000")
        if actual != wanted:
            mismatches.append({"address": f"0x{addr:08X}", "live_addr": f"0x{pos:08X}",
                               "expected": short(wanted), "actual": short(actual)})
    return {"semantic_checked_count": checked, "semantic_relocated_count": followed,
            "semantic_mismatch_count": len(mismatches), "semantic_mismatches": mismatches[:120]}


def norm_addr(value: Any) -> str | None:
    try:
        return "0x%08X" % int(value, 16 if isinstance(value, str) else 10)
    except (TypeError, ValueError):
        return None


def short(value: Any, limit: int = 80) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def literal(node: ast.AST) -> Any:
    return ast.literal_eval(node)


def iter_source_entries(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    entries: list[dict[str, Any]] = []
    source_order = 0
    for node in tree.body:
        dict_node: ast.Dict | None = None
        source_kind = ""
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "ADDRESS_TEXT_OVERRIDES" for t in node.targets):
                if isinstance(node.value, ast.Dict):
                    dict_node = node.value
                    source_kind = "assign"
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "update"
                and isinstance(func.value, ast.Name)
                and func.value.id == "ADDRESS_TEXT_OVERRIDES"
                and node.value.args
                and isinstance(node.value.args[0], ast.Dict)
            ):
                dict_node = node.value.args[0]
                source_kind = "update"
        if dict_node is None:
            continue
        for key_node, value_node in zip(dict_node.keys, dict_node.values):
            if key_node is None:
                continue
            try:
                key = literal(key_node)
                value = literal(value_node)
            except Exception:
                continue
            if not isinstance(key, int):
                continue
            source_order += 1
            entries.append(
                {
                    "address": "0x%08X" % key,
                    "addr_int": key,
                    "value": value,
                    "lineno": getattr(key_node, "lineno", getattr(node, "lineno", None)),
                    "source": source_kind,
                    "order": source_order,
                }
            )
    return entries


def load_build_overrides() -> dict[int, str]:
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_korean_full as B  # noqa: WPS433

    if hasattr(B, "refresh_compact_glyph_dictionary_overrides"):
        B.refresh_compact_glyph_dictionary_overrides(B.load_display_overrides(), strict=True)
    return {int(k): str(v or "") for k, v in B.ADDRESS_TEXT_OVERRIDES.items()}


def generated_override_addrs() -> set[int]:
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_korean_full as B  # noqa: WPS433

    return set(getattr(B, "GLYPH_DICTIONARY_TEXT_ADDRS", set()))


def load_effective_protected_texts(raw: dict[int, str]) -> tuple[dict[int, str], dict[str, int]]:
    """Return protected-address final display text, matching build write order.

    ADDRESS_TEXT_OVERRIDES is the import-stage authority, but a few later
    direct script patches overwrite the same addresses. Pair-renderer regions
    also normalize ASCII spaces/digits before encoding. The editor/audit must
    compare against that final build-visible text, not the raw dict value.
    """
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_korean_full as B  # noqa: WPS433
    import qa_text_fit  # noqa: WPS433

    # build_report passes a snapshot of the active builder dictionary. The
    # resolver below reads that dictionary too: reject stale/foreign snapshots.
    if any(addr not in B.ADDRESS_TEXT_OVERRIDES or text != str(B.ADDRESS_TEXT_OVERRIDES[addr] or '')
           for addr, text in raw.items()):
        raise ValueError('protected text snapshot differs from active builder authority')
    effective = dict(raw)
    display_overrides = B.load_display_overrides()
    display_override_count = 0
    for addr, text in list(effective.items()):
        if addr in display_overrides:
            effective[addr] = display_overrides[addr]
            display_override_count += 1
    slots = B.load_slots()
    pair_normalized = 0
    for addr, text in list(effective.items()):
        slot = slots.get(addr, 1)
        if B.in_region(B.PAIR_RENDERER_REGIONS, addr, addr + max(slot, 1)):
            normalized = B.normalize_pair_renderer_text(text)
            if normalized != text:
                pair_normalized += 1
            effective[addr] = normalized
    direct_collisions = 0
    direct_divergent = 0
    _, script_members = B.load_direct_script_metadata()
    dialogue_overrides = B.load_dialogue_overrides(DIALOGUE_OVERRIDES)
    # Actual call provenance, not declaration membership, selects the policy.
    # Fixed labels and the independent prologue writer retain their own path.
    for addr, (end, text, writer) in qa_text_fit.load_direct_patch_texts(include_writer=True).items():
        if addr not in effective:
            continue
        if writer == 'patch_script_row':
            selected = B.direct_script_override_text(addr, end, script_members,
                                                     dialogue_overrides)
            if selected is not None:  # An explicit empty string is a clear.
                text = selected
        direct_collisions += 1
        if effective[addr] != str(text or ""):
            direct_divergent += 1
        effective[addr] = str(text or "")
    return effective, {
        "display_override_count": display_override_count,
        "pair_normalized_count": pair_normalized,
        "direct_patch_collision_count": direct_collisions,
        "direct_patch_divergent_count": direct_divergent,
    }


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def load_tsv_entries(path: Path) -> tuple[dict[int, str], list[str]]:
    if not path.exists():
        return {}, [f"missing TSV authority: {path.relative_to(ROOT)}"]
    errors: list[str] = []
    rows: dict[int, str] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames != ["address", "text"]:
            return {}, [f"{path.relative_to(ROOT)}: expected header address<TAB>text"]
        for line_no, row in enumerate(reader, start=2):
            raw_addr = (row.get("address") or "").strip()
            if not raw_addr:
                errors.append(f"{path.relative_to(ROOT)}:{line_no}: empty address")
                continue
            try:
                addr = int(raw_addr, 16)
            except ValueError:
                errors.append(f"{path.relative_to(ROOT)}:{line_no}: bad address {raw_addr!r}")
                continue
            if addr in rows:
                errors.append(f"{path.relative_to(ROOT)}:{line_no}: duplicate 0x{addr:08X}")
                continue
            rows[addr] = str(row.get("text") or "")
    return rows, errors


def load_required_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, f"missing required generated data: {path.relative_to(ROOT)}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON {path.relative_to(ROOT)}: {exc}"


def relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def build_report(rom_path: Path | None = None,
                 manifest_path: Path | None = None) -> dict[str, Any]:
    entries = iter_source_entries(BUILD)
    by_addr: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_addr[entry["addr_int"]].append(entry)

    duplicates = []
    for addr, items in sorted(by_addr.items()):
        if len(items) <= 1:
            continue
        values = [str(item["value"] or "") for item in items]
        duplicates.append(
            {
                "address": "0x%08X" % addr,
                "count": len(items),
                "same_value": len(set(values)) == 1,
                "entries": [
                    {
                        "lineno": item["lineno"],
                        "source": item["source"],
                        "value": short(item["value"]),
                    }
                    for item in items
                ],
            }
        )

    runtime = load_build_overrides()
    generated_addrs = generated_override_addrs()
    static_effective: dict[int, str] = {}
    for entry in entries:
        static_effective[entry["addr_int"]] = str(entry["value"] or "")
    inline_mismatches = []
    for addr in sorted(set(runtime) | set(static_effective)):
        if addr in generated_addrs and addr not in static_effective:
            continue
        rv = runtime.get(addr)
        sv = static_effective.get(addr)
        if rv != sv:
            inline_mismatches.append(
                {
                    "address": "0x%08X" % addr,
                    "runtime": short(rv),
                    "static_last": short(sv),
                }
            )

    source_forbidden_terms = ("쇼군", "휘프")
    source_forbidden = []
    for entry in entries:
        value = str(entry["value"] or "")
        terms = [term for term in source_forbidden_terms if term in value]
        if terms:
            source_forbidden.append(
                {
                    "address": entry["address"],
                    "lineno": entry["lineno"],
                    "terms": terms,
                    "value": short(value),
                }
            )

    tsv_entries, tsv_errors = load_tsv_entries(ADDRESS_TEXT_OVERRIDES_TSV)
    runtime_static_only = {addr: text for addr, text in runtime.items() if addr not in generated_addrs}
    # The builder clears the inline fallback when the TSV is present. Comparing
    # that dead snapshot with runtime reports valid TSV edits as source drift.
    static_mismatches = [] if ADDRESS_TEXT_OVERRIDES_TSV.exists() else inline_mismatches
    tsv_mismatches = []
    # Generated glyph-dictionary sources have a separate authority and may
    # remain in the TSV as human-readable source text.
    for addr in sorted((set(tsv_entries) | set(runtime_static_only)) - generated_addrs):
        tv = tsv_entries.get(addr)
        rv = runtime_static_only.get(addr)
        if tv != rv:
            tsv_mismatches.append(
                {
                    "address": "0x%08X" % addr,
                    "tsv": short(tv),
                    "runtime": short(rv),
                }
            )

    protected_raw = {addr: str(value or "") for addr, value in runtime.items()}
    protected, effective_stats = load_effective_protected_texts(protected_raw)
    dialogue_overrides = load_json(DIALOGUE_OVERRIDES, {})
    overlay_collisions = []
    overlay_diff_count = 0
    overlay_same_count = 0
    for key, value in sorted(dialogue_overrides.items()):
        n = norm_addr(key)
        if not n:
            continue
        addr = int(n, 16)
        if addr not in protected:
            continue
        cur = str(value or "")
        want = protected[addr]
        same = cur == want
        overlay_same_count += 1 if same else 0
        overlay_diff_count += 0 if same else 1
        if len(overlay_collisions) < 120:
            overlay_collisions.append(
                {
                    "address": n,
                    "same_as_effective": same,
                    "effective": short(want),
                    "dialogue_override": short(cur),
                }
            )

    required_errors = []
    dialogue_map, error = load_required_json(DIALOGUE_MAP)
    if error:
        required_errors.append(error)
        dialogue_map = {"lines": []}
    map_mismatches = []
    protected_map_count = 0
    for line in dialogue_map.get("lines", []):
        n = norm_addr(line.get("address"))
        if not n:
            continue
        addr = int(n, 16)
        if addr not in protected:
            continue
        protected_map_count += 1
        cur = str(line.get("ko") or "")
        want = protected[addr]
        if cur != want:
            map_mismatches.append(
                {
                    "address": n,
                    "id": line.get("id"),
                    "effective": short(want),
                    "dialogue_map": short(cur),
                }
            )

    dialogue_groups, error = load_required_json(DIALOGUE_GROUPS)
    if error:
        required_errors.append(error)
        dialogue_groups = {"groups": []}
    group_mismatches = []
    protected_group_count = 0
    for group in dialogue_groups.get("groups", []):
        gid = group.get("group_id")
        for member in group.get("members", []):
            n = norm_addr(member.get("address"))
            if not n:
                continue
            addr = int(n, 16)
            if addr not in protected:
                continue
            protected_group_count += 1
            cur = str(member.get("ko") or "")
            want = protected[addr]
            if cur != want:
                group_mismatches.append(
                    {
                        "address": n,
                        "group_id": gid,
                        "id": member.get("id"),
                        "effective": short(want),
                        "dialogue_group": short(cur),
                    }
                )

    semantic = (audit_rom_semantics(rom_path, manifest_path or ROOT / "temp" / "repoint_manifest.json", protected)
                if rom_path is not None else {})
    return {
        "source": str(BUILD.relative_to(ROOT)),
        "source_entry_count": len(entries),
        "raw_effective_count": len(runtime),
        "effective_count": len(protected),
        "generated_runtime_address_count": len([addr for addr in generated_addrs if addr in runtime and addr not in static_effective]),
        **effective_stats,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates[:120],
        "source_forbidden_term_count": len(source_forbidden),
        "source_forbidden_terms": source_forbidden[:120],
        "tsv_authority": str(ADDRESS_TEXT_OVERRIDES_TSV.relative_to(ROOT)),
        "tsv_entry_count": len(tsv_entries),
        "tsv_error_count": len(tsv_errors),
        "tsv_errors": tsv_errors[:120],
        "tsv_runtime_mismatch_count": len(tsv_mismatches),
        "tsv_runtime_mismatches": tsv_mismatches[:120],
        "runtime_static_mismatch_count": len(static_mismatches),
        "runtime_static_mismatches": static_mismatches[:120],
        "inactive_inline_mismatch_count": len(inline_mismatches) if ADDRESS_TEXT_OVERRIDES_TSV.exists() else 0,
        "inactive_inline_mismatches": inline_mismatches[:120] if ADDRESS_TEXT_OVERRIDES_TSV.exists() else [],
        "required_data_errors": required_errors,
        "dialogue_override_collision_count": overlay_same_count + overlay_diff_count,
        "dialogue_override_same_count": overlay_same_count,
        "dialogue_override_divergent_count": overlay_diff_count,
        "dialogue_override_collision_examples": overlay_collisions,
        "dialogue_map_protected_count": protected_map_count,
        "dialogue_map_mismatch_count": len(map_mismatches),
        "dialogue_map_mismatches": map_mismatches[:120],
        "dialogue_groups_protected_count": protected_group_count,
        "dialogue_groups_mismatch_count": len(group_mismatches),
        "dialogue_groups_mismatches": group_mismatches[:120],
        **semantic,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--rom", type=Path, help="candidate ROM for live semantic comparison")
    parser.add_argument("--repoint-manifest", type=Path,
                        default=ROOT / "temp" / "repoint_manifest.json")
    args = parser.parse_args()

    try:
        report = build_report(args.rom, args.repoint_manifest)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"[FAIL] ADDRESS_TEXT_OVERRIDES evidence mismatch: {exc}", file=sys.stderr)
        return 1
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("ADDRESS_TEXT_OVERRIDES audit")
    print(f"- source entries: {report['source_entry_count']} effective: {report['effective_count']}")
    print(f"- duplicate source keys: {report['duplicate_count']}")
    print(f"- source forbidden terms: {report['source_forbidden_term_count']}")
    print(
        "- TSV authority: "
        f"{report['tsv_authority']} entries {report['tsv_entry_count']}, "
        f"errors {report['tsv_error_count']}, "
        f"runtime mismatches {report['tsv_runtime_mismatch_count']}"
    )
    print(f"- runtime/static mismatches: {report['runtime_static_mismatch_count']}")
    print(f"- inactive inline fallback differences: {report['inactive_inline_mismatch_count']}")
    print(
        "- final effective transforms: "
        f"pair-normalized {report['pair_normalized_count']}, "
        f"direct-patch collisions {report['direct_patch_collision_count']} "
        f"(divergent {report['direct_patch_divergent_count']})"
    )
    for error in report["required_data_errors"]:
        print(f"- data error: {error}")
    print(
        "- dialogue_overrides collisions: "
        f"{report['dialogue_override_collision_count']} "
        f"(divergent {report['dialogue_override_divergent_count']}, same {report['dialogue_override_same_count']})"
    )
    print(
        "- dialogue_map protected rows: "
        f"{report['dialogue_map_protected_count']} mismatches: {report['dialogue_map_mismatch_count']}"
    )
    print(
        "- dialogue_groups protected rows: "
        f"{report['dialogue_groups_protected_count']} mismatches: {report['dialogue_groups_mismatch_count']}"
    )
    if args.rom is not None:
        print(f"- ROM semantic rows: {report['semantic_checked_count']} "
              f"(relocated {report['semantic_relocated_count']}) "
              f"mismatches: {report['semantic_mismatch_count']}")
    print(f"- report: {relpath(report_path)}")

    hard_fail = (
        report["duplicate_count"] > 0
        or report["source_forbidden_term_count"] > 0
        or report["tsv_error_count"] > 0
        or report["tsv_runtime_mismatch_count"] > 0
        or report["runtime_static_mismatch_count"] > 0
        or bool(report["required_data_errors"])
        or report["dialogue_map_mismatch_count"] > 0
        or report["dialogue_groups_mismatch_count"] > 0
        or report.get("semantic_mismatch_count", 0) > 0
    )
    if args.strict and hard_fail:
        print("[FAIL] ADDRESS_TEXT_OVERRIDES governance violation", file=sys.stderr)
        return 1
    print("[OK] ADDRESS_TEXT_OVERRIDES governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
