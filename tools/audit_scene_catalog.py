#!/usr/bin/env python3
"""통합 UI 에디터 scene 카탈로그 감사.

목표는 "게임에서 실제로 보이는 화면/그래픽/대사가 편집기 scene에 묶였는지"를
기계적으로 의심하는 것이다. 이 도구는 화면 의미를 완전히 판정하지 않는다. 대신
다음 결함을 계속 드러낸다.

* build 패치 함수가 만지는 curated 그래픽이 scene에 배정되지 않음
* 대사가 큰 광역 bucket에 남아 화면 연결이 흐림
* scene screenshot이 없거나 현재 ROM SHA와 맞지 않음
* 같은 screenshot checkpoint를 너무 많은 scene이 공유함
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data" / "scene_catalog.json"
SPR = ROOT / "data" / "sprites_index.json"
DGRP = ROOT / "data" / "dialogue_groups.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
OVERRIDES = ROOT / "data" / "scene_catalog_overrides.json"
ROM = ROOT / "output" / "game_wars_korean_full.gba"
SHOT_DIR = ROOT / "temp" / "scene_screenshots"
OUT_DIR = ROOT / "temp" / "scene_catalog_audit"

SELECT_OBJ_ID = "lz77_00024A34"
SELECT_TOP_TITLE_ID = SELECT_OBJ_ID + "#select_top_title"
SELECT_BOTTOM_TITLE_ID = SELECT_OBJ_ID + "#select_bottom_title"


def is_review_scene(scene: dict) -> bool:
    return (
        scene.get("id") in {"98_extraction_noise_review", "99_unassigned_review"}
        or scene.get("scope") == "review"
        or scene.get("scene_role") == "container"
        or scene.get("scene_role") == "excluded"
        or scene.get("scene_role") == "review_pending"
    )


def is_container_scene(scene: dict) -> bool:
    return scene.get("scene_role") == "container"


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_shot(checkpoint: dict, scene_id: str, rom_sha: str) -> tuple[bool, str]:
    checkpoint_name = checkpoint.get("name")
    if checkpoint.get("scene_id") and checkpoint.get("scene_id") != scene_id:
        return False, "checkpoint scene_id 불일치"
    frame = SHOT_DIR / f"{checkpoint_name}_patched" / "frame.png"
    if not frame.exists() or frame.stat().st_size <= 0:
        return False, "frame 없음"
    prov = frame.parent / "provenance.json"
    if not prov.exists() or prov.stat().st_size <= 0:
        return False, "provenance 없음"
    try:
        data = json.loads(prov.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "provenance JSON 오류"
    if data.get("rom_sha256") != rom_sha:
        return False, "ROM SHA 불일치"
    if data.get("scene_id") != scene_id:
        return False, "provenance scene_id 불일치"
    if checkpoint.get("mode") == "savestate":
        state = checkpoint.get("state")
        if not state:
            return False, "checkpoint state 없음"
        state_path = Path(state)
        if not state_path.is_absolute():
            state_path = ROOT / state_path
        if not state_path.exists():
            return False, "checkpoint state 파일 없음"
        if data.get("state_sha256") != sha256(state_path):
            return False, "state SHA 불일치"
    return True, "current"


def is_curated_patch_sprite(sp: dict) -> bool:
    src = sp.get("source") or ""
    if src.startswith("scan_lz77") or "dialogue glyph" in src.lower():
        return False
    removal_tokens = (
        "patch_part2_battle_start_day_overlay_obj",
        "patch_part2_domino_co_name_obj",
        "patch_part2_intro_campaign_residual_graphics",
    )
    if any(t in src for t in removal_tokens):
        return False
    if sp.get("id") == SELECT_OBJ_ID:
        # 편집기는 같은 블록의 화면상 상/하단 가상 항목을 배정한다.
        return False
    return src.startswith("full:patch_") or src.startswith("title:")


def classify_unassigned_coverage(coverage: dict, review_scene: dict) -> tuple[list[dict], list[dict]]:
    """Keep dialogue and pending sprite review blockers distinct in reports."""
    dialogue_unassigned = int(coverage.get("dialogue_unassigned") or 0)
    review_dialogue = len(review_scene.get("dialogue_ids") or [])
    pending_total = int(coverage.get("review_pending_total") or 0)
    sprite_candidates = int(coverage.get("sprites_unassigned_text_candidate") or 0)
    dialogue_issues = []
    if dialogue_unassigned:
        dialogue_issues.append({
            "coverage_dialogue_unassigned": dialogue_unassigned,
            "review_scene_dialogue": review_dialogue,
            "issue": "실제 scene/review 사유에 수렴하지 않은 대사가 남음",
        })
    sprite_issues = []
    if pending_total or sprite_candidates:
        sprite_issues.append({
            "pending_review_total": pending_total,
            "sprite_text_candidate": sprite_candidates,
            "issue": "UI 에디터 검토 필요 스프라이트가 남음",
        })
    return dialogue_issues, sprite_issues


def validate_unreached_probe(group_id: str, record: dict, rom_sha: str, root: Path) -> None:
    """Bind a negative observation to its ROM, source, installed watches and route."""
    def artifact(value: str) -> Path:
        if not isinstance(value, str) or not value:
            raise ValueError("artifact path missing")
        path = (root / value).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("artifact missing or outside repository")
        return path

    def hex_address(value: str) -> int:
        if not isinstance(value, str) or re.fullmatch(r"0x[0-9A-Fa-f]{8}", value) is None:
            raise ValueError("malformed watch address")
        return int(value, 16)

    if not rom_sha or re.fullmatch(r"[0-9a-f]{64}", rom_sha) is None:
        raise ValueError("audited ROM SHA missing")
    if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
        raise ValueError("reviewer missing")
    if not isinstance(record.get("rationale"), str) or not record["rationale"].strip():
        raise ValueError("rationale missing")
    routes = record.get("routes")
    logs = record.get("watch_logs")
    if not isinstance(routes, list) or len(routes) != 1 or not isinstance(routes[0], dict):
        raise ValueError("one route required")
    if not isinstance(logs, list) or len(logs) != 1 or not isinstance(logs[0], dict):
        raise ValueError("one watch log required")
    route, watch = routes[0], logs[0]
    receipt_path = artifact(watch.get("receipt"))
    if watch.get("receipt_sha256") != sha256(receipt_path):
        raise ValueError("probe receipt SHA mismatch")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != 1 or receipt.get("rom_sha256") != rom_sha:
        raise ValueError("probe ROM SHA mismatch")
    if not isinstance(route.get("route_id"), str) or not route["route_id"] or route["route_id"] != receipt.get("route_id"):
        raise ValueError("probe route identity mismatch")
    if route.get("step_keys") != [step.get("key") for step in receipt.get("steps", [])]:
        raise ValueError("probe route steps mismatch")
    for field, hash_field in (("source_state", "source_state_sha256"),
                              ("recorder_checkpoint", "recorder_checkpoint_sha256")):
        if route.get(field) != receipt.get(field):
            raise ValueError(f"probe {field} mismatch")
        source = artifact(receipt.get(field))
        if route.get(hash_field) != receipt.get(hash_field) or receipt.get(hash_field) != sha256(source):
            raise ValueError(f"probe {field} SHA mismatch")
    checkpoint = json.loads(artifact(receipt["recorder_checkpoint"]).read_text(encoding="utf-8"))
    if (checkpoint.get("rom_sha256") != rom_sha or checkpoint.get("state") != Path(receipt["source_state"]).name
            or checkpoint.get("state_sha256") != receipt["source_state_sha256"]):
        raise ValueError("recorder source identity mismatch")
    group = next((g for g in load(root / "data/dialogue_groups.json", {}).get("groups", [])
                  if g.get("group_id") == group_id), None)
    if not group or type(group.get("size")) is not int or group["size"] < 1:
        raise ValueError("dialogue group span missing")
    members = group.get("members")
    if not isinstance(members, list) or len(members) != group["size"]:
        raise ValueError("dialogue group members missing")
    member_spans = []
    for member in members:
        try:
            address = member["address"]
            slot = member["slot"]
            if not isinstance(address, str) or re.fullmatch(r"0x[0-9A-Fa-f]{8}", address) is None:
                raise ValueError
            if type(slot) is not int or slot < 1:
                raise ValueError
            start = 0x08000000 + int(address, 16)
            member_spans.append((start, start + slot))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("dialogue member address/slot missing") from exc
    member_spans.sort()
    target_start = 0x08000000 + int(group_id.removeprefix("g_"), 16)
    if target_start != member_spans[0][0]:
        raise ValueError("dialogue group address mismatch")
    target_span = [member_spans[0][0], max(end for _, end in member_spans)]
    control_span = [hex_address(watch.get("positive_control_address")),
                    hex_address(watch.get("positive_control_address")) + 2]
    if (hex_address(watch.get("target_address")) != target_start
            or control_span[0] == target_start or
            receipt.get("target_span") != [f"0x{x:08X}" for x in target_span] or
            receipt.get("control_span") != [f"0x{x:08X}" for x in control_span]):
        raise ValueError("target/control span mismatch")
    if any(start < control_span[1] and control_span[0] < end for start, end in member_spans):
        raise ValueError("positive control overlaps target")
    if watch.get("path") != receipt.get("watch_log") or watch.get("screen") != receipt.get("control_frame"):
        raise ValueError("watch log or control frame mismatch")
    log_path, screen_path = artifact(watch.get("path")), artifact(watch.get("screen"))
    if log_path.parent != screen_path.parent or receipt.get("watch_log_sha256") != sha256(log_path) or receipt.get("control_frame_sha256") != sha256(screen_path):
        raise ValueError("probe log/frame SHA or directory mismatch")
    event_path = artifact(receipt.get("frame_event_log"))
    if event_path.parent != log_path.parent or receipt.get("frame_event_log_sha256") != sha256(event_path):
        raise ValueError("frame-indexed probe log SHA or directory mismatch")
    setups = receipt.get("watch_setup")
    if not isinstance(setups, list) or len(setups) < 2:
        raise ValueError("watch setup missing")
    watch_spans = []
    for setup, destination in [(setup, str(log_path)) for setup in setups[:-1]] + [(setups[-1], "KEEP")]:
        if not isinstance(setup, dict):
            raise ValueError("complete watch setup missing")
        start = hex_address(setup.get("gba_start"))
        size = setup.get("size")
        if type(size) is not int or size < 1:
            raise ValueError("complete watch setup missing")
        if destination == "KEEP":
            if (start, start + size) != tuple(control_span):
                raise ValueError("complete watch setup missing")
        else:
            watch_spans.append((start, start + size))
        if (setup.get("gba_start") != f"0x{start:08X}" or setup.get("size") != size
                or setup.get("mode") != "r"
                or setup.get("command") != f"watchaddr {start:08X} {size} r {destination}"
                or setup.get("response") != f"OK watchaddr {start:08X} len={size} set={size}"):
            raise ValueError("complete watch setup missing")
    def slot_covered(start: int, end: int) -> bool:
        covered = start
        for wstart, wend in sorted(watch_spans):
            if wstart <= covered:
                covered = max(covered, wend)
            if covered >= end:
                return True
        return False

    if any(not slot_covered(start, end) for start, end in member_spans):
        raise ValueError("target member slot unwatched")
    first, last = receipt.get("first_watched_frame"), receipt.get("last_watched_frame")
    steps = receipt.get("steps")
    if (type(first) is not int or type(last) is not int or not isinstance(steps, list) or not steps
            or first != checkpoint.get("core_frame", -2) + 2 or last < first):
        raise ValueError("probe frame range mismatch")
    expected_frame = first
    for step in steps:
        if (not isinstance(step, dict) or step.get("key") not in {"A", "R", "L", "SELECT"}
                or step.get("start_frame") != expected_frame or type(step.get("end_frame")) is not int
                or step["end_frame"] < expected_frame):
            raise ValueError("probe route frame discontinuity")
        expected_frame = step["end_frame"] + 1
    if expected_frame != last + 1:
        raise ValueError("probe route does not cover watched frames")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    if (len(events) != len(lines) or any(
            not isinstance(event, dict) or event.get("log_line") != index
            or event.get("raw") != lines[index]
            or type(event.get("core_frame")) is not int
            or not first <= event["core_frame"] <= last
            for index, event in enumerate(events))):
        raise ValueError("frame-indexed probe log does not match raw watch log")
    addresses = []
    for line in lines:
        match = re.fullmatch(r"\d+ addr=([0-9A-Fa-f]{8}) pc=[0-9A-Fa-f]{8} lr=[0-9A-Fa-f]{8} r0=[0-9A-Fa-f]{8} r1=[0-9A-Fa-f]{8} old=[0-9A-Fa-f]{8} new=[0-9A-Fa-f]{8}", line)
        if match is None:
            raise ValueError("malformed probe watch log")
        addresses.append(int(match.group(1), 16))
    # The harness logs the watched address, but not access width. Four bytes is
    # conservative for wider reads that begin just before the target span.
    if any(addr < end and addr + 4 > start
           for addr in addresses for start, end in member_spans):
        raise ValueError("target member slot read on probe route")
    observed_control = {i for i, addr in enumerate(addresses)
                        if control_span[0] <= addr < control_span[1]}
    hits = receipt.get("control_hits")
    if not observed_control or not isinstance(hits, list) or len(hits) != len(observed_control):
        raise ValueError("positive control hit evidence missing")
    capture_frame = receipt.get("control_frame_core_frame")
    if type(capture_frame) is not int or not first <= capture_frame <= last:
        raise ValueError("control screenshot capture frame missing or outside route")
    seen = set()
    for hit in hits:
        if not isinstance(hit, dict):
            raise ValueError("malformed positive control hit")
        index, frame = hit.get("log_line"), hit.get("core_frame")
        if (type(index) is not int or index not in observed_control or index in seen
                or type(frame) is not int or not first <= frame <= last
                or frame != events[index]["core_frame"]
                or not any(step["start_frame"] <= frame <= step["end_frame"] for step in steps)
                or hit.get("route_id") != route["route_id"]):
            raise ValueError("positive control frame/route does not match probe log")
        seen.add(index)
    if capture_frame not in {events[index]["core_frame"] for index in observed_control}:
        raise ValueError("control screenshot frame does not match positive control hit")
    if watch.get("capture_core_frame") != capture_frame:
        raise ValueError("evidence screenshot frame does not match probe receipt")


def classify_unreached_dialogue(unassigned_ids: list[str], records: list[dict],
                                rom_sha: str, root: Path = ROOT) -> tuple[list[dict], list[dict]]:
    """Accept bounded negative reads only when the complete probe is validated."""
    warnings, critical = [], []
    by_group = defaultdict(list)
    for record in records:
        if isinstance(record, dict):
            by_group[record.get("group_id")].append(record)
    for group_id in unassigned_ids:
        candidates = by_group.get(group_id, [])
        problems = []
        if len(candidates) != 1:
            problems.append("exactly one evidence record required")
        else:
            record = candidates[0]
            try:
                validate_unreached_probe(group_id, record, rom_sha, root)
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                problems.append(str(exc))
        row = {"group_id": group_id, "issue": "unreached_dialogue",
               "problems": sorted(set(problems))}
        (critical if problems else warnings).append(row)
    for group_id in by_group.keys() - set(unassigned_ids):
        critical.append({"group_id": group_id, "issue": "unreached_dialogue record is not unassigned"})
    return warnings, critical


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="critical issue가 있으면 exit 1")
    ap.add_argument("--rom", type=Path, default=ROM, help="candidate ROM for screenshot provenance")
    args = ap.parse_args()

    catalog = load(CAT, {"scenes": [], "coverage": {}})
    overrides = load(OVERRIDES, {})
    sprites = load(SPR, {"sprites": []}).get("sprites", [])
    dialogue_groups = load(DGRP, {"groups": []}).get("groups", [])
    checkpoints = load(CHECKPOINTS, {"checkpoints": []}).get("checkpoints", [])
    scenes = catalog.get("scenes", [])
    scene_by_id = {s["id"]: s for s in scenes}
    coverage = catalog.get("coverage") or {}
    group_ids = {g.get("group_id") for g in dialogue_groups if g.get("group_id")}
    assigned = set()
    for sc in scenes:
        if is_review_scene(sc):
            continue
        assigned.update(sc.get("sprite_ids") or [])

    rom_sha = sha256(args.rom) if args.rom.exists() else ""
    checkpoint_by_id = {c["name"]: c for c in checkpoints}
    checkpoint_ids = set(checkpoint_by_id)
    checkpoint_modes = Counter(c.get("mode") for c in checkpoints)

    unassigned_curated = []
    for sp in sprites:
        sid = sp.get("id")
        if not sid or sid in assigned:
            continue
        if is_curated_patch_sprite(sp):
            unassigned_curated.append({
                "id": sid,
                "offset": sp.get("offset"),
                "source": sp.get("source"),
                "type": sp.get("type"),
                "width": sp.get("width"),
                "height": sp.get("height"),
            })

    missing_virtual_select = [
        sid for sid in (SELECT_TOP_TITLE_ID, SELECT_BOTTOM_TITLE_ID) if sid not in assigned
    ]

    count_mismatches = []
    dialogue_refs = defaultdict(list)
    missing_dialogue_ids = []
    for sc in scenes:
        dialogue_ids = sc.get("dialogue_ids") or []
        sprite_ids = sc.get("sprite_ids") or []
        counts = sc.get("counts") or {}
        if counts.get("dialogue") != len(dialogue_ids) or counts.get("sprite") != len(sprite_ids):
            count_mismatches.append({
                "scene": sc["id"],
                "counts": counts,
                "actual_dialogue": len(dialogue_ids),
                "actual_sprite": len(sprite_ids),
            })
        for gid in dialogue_ids:
            dialogue_refs[gid].append(sc["id"])
            if gid not in group_ids:
                missing_dialogue_ids.append({"scene": sc["id"], "group_id": gid})

    duplicate_dialogue_ids = [
        {"group_id": gid, "scenes": owners}
        for gid, owners in sorted(dialogue_refs.items()) if len(owners) > 1
    ]

    container_rows = []
    container_contract_issues = []
    for sc in scenes:
        if not is_container_scene(sc):
            continue
        shot = sc.get("screenshot") or {}
        row = {
            "scene": sc["id"],
            "title": sc.get("title"),
            "dialogue": len(sc.get("dialogue_ids") or []),
            "sprites": len(sc.get("sprite_ids") or []),
            "status": shot.get("status"),
            "grade": shot.get("grade"),
            "note": shot.get("note") or "",
            "related_dialogue_scene_ids": sc.get("related_dialogue_scene_ids") or [],
        }
        container_rows.append(row)
        if sc.get("capture_required") is not False:
            container_contract_issues.append({**row, "issue": "container capture_required가 false가 아님"})
        if sc.get("entrypoint"):
            container_contract_issues.append({**row, "issue": "container에 entrypoint가 붙어 있음"})
        if sc.get("checkpoint") or shot.get("checkpoint") or shot.get("url"):
            container_contract_issues.append({**row, "issue": "container에 checkpoint/url이 붙어 있음"})
        if shot.get("capture_path") or shot.get("provenance_path"):
            container_contract_issues.append({**row, "issue": "container에 capture/provenance path가 붙어 있음"})
        if shot.get("status") != "container" or shot.get("grade") != "not_a_scene":
            container_contract_issues.append({**row, "issue": "container screenshot status/grade 계약 위반"})
        if not row["note"]:
            container_contract_issues.append({**row, "issue": "container 제외 사유가 비어 있음"})

    pending_review_total = int(coverage.get("review_pending_total") or 0)
    unassigned_review_scene = scene_by_id.get("99_unassigned_review") or {}
    unassigned_ids = unassigned_review_scene.get("dialogue_ids") or []
    unreached_dialogue, unassigned_dialogue_issue = classify_unreached_dialogue(
        unassigned_ids, overrides.get("unreached_dialogue") or [], rom_sha)
    adjusted_coverage = {**coverage, "review_pending_total":
                         max(0, pending_review_total - len(unreached_dialogue))}
    _, pending_sprite_issue = classify_unassigned_coverage(adjusted_coverage, unassigned_review_scene)
    if int(coverage.get("dialogue_unassigned") or 0) != len(unassigned_ids):
        unassigned_dialogue_issue.append({"issue": "coverage dialogue_unassigned mismatch",
                                          "coverage_dialogue_unassigned": coverage.get("dialogue_unassigned"),
                                          "review_scene_dialogue": len(unassigned_ids)})

    screenshot_issues = []
    screenshot_use = Counter()
    for sc in scenes:
        if is_review_scene(sc):
            continue
        shot = sc.get("screenshot") or {}
        cp = shot.get("checkpoint")
        if not cp:
            screenshot_issues.append({"scene": sc["id"], "title": sc.get("title"), "issue": "checkpoint 없음"})
            continue
        screenshot_use[cp] += 1
        if cp not in checkpoint_ids:
            screenshot_issues.append({"scene": sc["id"], "title": sc.get("title"), "checkpoint": cp, "issue": "screen_checkpoints에 없음"})
            continue
        ok, reason = current_shot(checkpoint_by_id[cp], sc["id"], rom_sha) if rom_sha else (False, "ROM 없음")
        if not ok:
            screenshot_issues.append({"scene": sc["id"], "title": sc.get("title"), "checkpoint": cp, "issue": reason})

    broad_dialogue = []
    for sc in scenes:
        if is_review_scene(sc):
            continue
        n = len(sc.get("dialogue_ids") or [])
        title = sc.get("title") or ""
        filt = sc.get("dialogue_filter") or {}
        if n >= 500 or "전체" in title or "분류 전" in title:
            broad_dialogue.append({
                "scene": sc["id"],
                "title": title,
                "dialogue_count": n,
                "addr_ranges": filt.get("addr_ranges"),
                "reason": "광역 대사 bucket",
            })

    reused_screenshots = [
        {"checkpoint": cp, "scene_count": n,
         "scenes": [s["id"] for s in scenes if (s.get("screenshot") or {}).get("checkpoint") == cp]}
        for cp, n in sorted(screenshot_use.items()) if n >= 4
    ]

    scene_items = []
    for sc in scenes:
        if is_review_scene(sc):
            continue
        scene_items.append({
            "id": sc["id"],
            "title": sc.get("title"),
            "dialogue": len(sc.get("dialogue_ids") or []),
            "sprites": len(sc.get("sprite_ids") or []),
            "checkpoint": (sc.get("screenshot") or {}).get("checkpoint"),
            "screenshot_grade": (sc.get("screenshot") or {}).get("grade"),
        })

    issues = {
        "unassigned_curated_patch_sprites": unassigned_curated,
        "missing_virtual_select_sprites": missing_virtual_select,
        "unassigned_dialogue_groups": unassigned_dialogue_issue,
        "unreached_dialogue": unreached_dialogue,
        "pending_sprite_reviews": pending_sprite_issue,
        "missing_dialogue_ids": missing_dialogue_ids,
        "duplicate_dialogue_ids": duplicate_dialogue_ids,
        "count_mismatches": count_mismatches,
        "container_contract_issues": container_contract_issues,
        "tracked_container_scenes": container_rows,
        "screenshot_issues": screenshot_issues,
        "broad_dialogue_scenes": broad_dialogue,
        "reused_screenshot_checkpoints": reused_screenshots,
    }
    critical_count = (
        len(unassigned_curated)
        + len(missing_virtual_select)
        + len(unassigned_dialogue_issue)
        + len(pending_sprite_issue)
        + len(missing_dialogue_ids)
        + len(duplicate_dialogue_ids)
        + len(count_mismatches)
        + len(container_contract_issues)
    )
    summary = {
        "scene_count": len(scenes),
        "game_scene_count": len([s for s in scenes if not is_review_scene(s)]),
        "container_count": len(container_rows),
        "container_dialogue_count": sum(x["dialogue"] for x in container_rows),
        "checkpoint_count": len(checkpoints),
        "checkpoint_modes": dict(checkpoint_modes),
        "coverage": coverage,
        "review_pending_total": pending_review_total,
        "critical_count": critical_count,
        "warning_count": len(unreached_dialogue) + len(screenshot_issues) + len(broad_dialogue) + len(reused_screenshots) + len(container_rows),
    }
    report = {"summary": summary, "issues": issues, "scenes": scene_items}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Scene Catalog Audit",
        "",
        f"- scenes: {summary['scene_count']} (game {summary['game_scene_count']})",
        f"- tracked containers: {summary['container_count']} "
        f"(dialogue {summary['container_dialogue_count']})",
        f"- checkpoints: {summary['checkpoint_count']} {summary['checkpoint_modes']}",
        f"- sprites assigned: {summary['coverage'].get('sprites_assigned')}/{summary['coverage'].get('sprites_total')}",
        f"- dialogue game/review/unassigned: "
        f"{summary['coverage'].get('dialogue_game_scene_assigned')}/"
        f"{summary['coverage'].get('dialogue_review_only')}/"
        f"{summary['coverage'].get('dialogue_unassigned')} "
        f"(accounted {summary['coverage'].get('dialogue_assigned')}/"
        f"{summary['coverage'].get('dialogue_groups_total')})",
        f"- pending review: {summary['review_pending_total']}",
        f"- critical: {summary['critical_count']}",
        f"- warnings: {summary['warning_count']}",
        "",
    ]
    if unassigned_curated:
        lines.append("## Critical: Unassigned Curated Patch Sprites")
        for x in unassigned_curated:
            lines.append(f"- {x['id']} {x.get('offset')} {x.get('source')} {x.get('width')}x{x.get('height')}")
        lines.append("")
    if missing_virtual_select:
        lines.append("## Critical: Missing Virtual Select Sprites")
        for sid in missing_virtual_select:
            lines.append(f"- {sid}")
        lines.append("")
    if unassigned_dialogue_issue:
        lines.append("## Critical: Unassigned Dialogue Groups")
        for x in unassigned_dialogue_issue:
            lines.append(f"- {x.get('group_id', 'coverage')}: {x['issue']} {x.get('problems', '')}")
        lines.append("")
    if unreached_dialogue:
        lines.append("## Warning: Unreached Dialogue")
        for x in unreached_dialogue:
            lines.append(f"- {x['group_id']}: consumer remains unverified at runtime")
        lines.append("")
    if pending_sprite_issue:
        lines.append("## Critical: Pending Sprite Reviews")
        for x in pending_sprite_issue:
            lines.append(
                f"- review_pending_total={x['pending_review_total']} "
                f"sprites_unassigned_text_candidate={x['sprite_text_candidate']}: {x['issue']}")
        lines.append("")
    if missing_dialogue_ids:
        lines.append("## Critical: Missing Dialogue Group IDs")
        for x in missing_dialogue_ids[:80]:
            lines.append(f"- {x['scene']} references missing {x['group_id']}")
        if len(missing_dialogue_ids) > 80:
            lines.append(f"- ... {len(missing_dialogue_ids) - 80} more")
        lines.append("")
    if duplicate_dialogue_ids:
        lines.append("## Critical: Duplicate Dialogue Group IDs")
        for x in duplicate_dialogue_ids[:80]:
            lines.append(f"- {x['group_id']}: {', '.join(x['scenes'])}")
        if len(duplicate_dialogue_ids) > 80:
            lines.append(f"- ... {len(duplicate_dialogue_ids) - 80} more")
        lines.append("")
    if count_mismatches:
        lines.append("## Critical: Scene Count Mismatches")
        for x in count_mismatches:
            lines.append(
                f"- {x['scene']}: counts={x['counts']} "
                f"actual=d{x['actual_dialogue']}/sp{x['actual_sprite']}"
            )
        lines.append("")
    if container_contract_issues:
        lines.append("## Critical: Container Contract Issues")
        for x in container_contract_issues:
            lines.append(f"- {x['scene']}: {x['issue']}")
        lines.append("")
    if screenshot_issues:
        lines.append("## Screenshot Issues")
        for x in screenshot_issues:
            lines.append(f"- {x['scene']} {x.get('checkpoint')}: {x['issue']}")
        lines.append("")
    if broad_dialogue:
        lines.append("## Broad Dialogue Buckets")
        for x in broad_dialogue:
            lines.append(f"- {x['scene']} ({x['dialogue_count']}): {x['title']}")
        lines.append("")
    if reused_screenshots:
        lines.append("## Reused Screenshot Checkpoints")
        for x in reused_screenshots:
            lines.append(f"- {x['checkpoint']} x{x['scene_count']}: {', '.join(x['scenes'])}")
        lines.append("")
    if container_rows:
        lines.append("## Tracked Containers")
        for x in container_rows:
            related = ",".join(x["related_dialogue_scene_ids"]) or "none"
            lines.append(
                f"- {x['scene']} d{x['dialogue']} sp{x['sprites']} "
                f"related={related}: {x['note']}"
            )
        lines.append("")
    lines.append("## Scene Counts")
    for sc in scene_items:
        lines.append(f"- {sc['id']}: d{sc['dialogue']} sp{sc['sprites']} shot={sc['checkpoint']}")
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"scene audit: {OUT_DIR / 'report.md'}")
    print(json.dumps(summary, ensure_ascii=False))
    if args.strict and summary["critical_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
