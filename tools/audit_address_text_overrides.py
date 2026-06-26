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
DEFAULT_REPORT = ROOT / "temp" / "address_text_overrides_audit.json"


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

    return {int(k): str(v or "") for k, v in B.ADDRESS_TEXT_OVERRIDES.items()}


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

    effective = dict(raw)
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
    for addr, (_end, text) in qa_text_fit.load_direct_patch_texts().items():
        if addr not in effective:
            continue
        direct_collisions += 1
        if effective[addr] != str(text or ""):
            direct_divergent += 1
        effective[addr] = str(text or "")
    return effective, {
        "pair_normalized_count": pair_normalized,
        "direct_patch_collision_count": direct_collisions,
        "direct_patch_divergent_count": direct_divergent,
    }


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


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


def build_report() -> dict[str, Any]:
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
    static_effective: dict[int, str] = {}
    for entry in entries:
        static_effective[entry["addr_int"]] = str(entry["value"] or "")
    static_mismatches = []
    for addr in sorted(set(runtime) | set(static_effective)):
        rv = runtime.get(addr)
        sv = static_effective.get(addr)
        if rv != sv:
            static_mismatches.append(
                {
                    "address": "0x%08X" % addr,
                    "runtime": short(rv),
                    "static_last": short(sv),
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

    return {
        "source": str(BUILD.relative_to(ROOT)),
        "source_entry_count": len(entries),
        "raw_effective_count": len(runtime),
        "effective_count": len(protected),
        **effective_stats,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates[:120],
        "runtime_static_mismatch_count": len(static_mismatches),
        "runtime_static_mismatches": static_mismatches[:120],
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

    print("ADDRESS_TEXT_OVERRIDES audit")
    print(f"- source entries: {report['source_entry_count']} effective: {report['effective_count']}")
    print(f"- duplicate source keys: {report['duplicate_count']}")
    print(f"- runtime/static mismatches: {report['runtime_static_mismatch_count']}")
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
    print(f"- report: {relpath(report_path)}")

    hard_fail = (
        report["duplicate_count"] > 0
        or report["runtime_static_mismatch_count"] > 0
        or bool(report["required_data_errors"])
        or report["dialogue_map_mismatch_count"] > 0
        or report["dialogue_groups_mismatch_count"] > 0
    )
    if args.strict and hard_fail:
        print("[FAIL] ADDRESS_TEXT_OVERRIDES governance violation", file=sys.stderr)
        return 1
    print("[OK] ADDRESS_TEXT_OVERRIDES governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
