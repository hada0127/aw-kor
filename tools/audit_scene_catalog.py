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
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data" / "scene_catalog.json"
SPR = ROOT / "data" / "sprites_index.json"
DGRP = ROOT / "data" / "dialogue_groups.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="critical issue가 있으면 exit 1")
    args = ap.parse_args()

    catalog = load(CAT, {"scenes": [], "coverage": {}})
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

    rom_sha = sha256(ROM) if ROM.exists() else ""
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

    dialogue_unassigned = int(coverage.get("dialogue_unassigned") or 0)
    pending_review_total = int(coverage.get("review_pending_total") or 0)
    sprite_text_candidate = int(coverage.get("sprites_unassigned_text_candidate") or 0)
    unassigned_review_scene = scene_by_id.get("99_unassigned_review") or {}
    unassigned_review_dialogue = len(unassigned_review_scene.get("dialogue_ids") or [])
    unassigned_dialogue_issue = []
    if dialogue_unassigned:
        unassigned_dialogue_issue.append({
            "coverage_dialogue_unassigned": dialogue_unassigned,
            "review_scene_dialogue": unassigned_review_dialogue,
            "issue": "실제 scene/review 사유에 수렴하지 않은 대사가 남음",
        })
    if pending_review_total or sprite_text_candidate:
        unassigned_dialogue_issue.append({
            "coverage_dialogue_unassigned": dialogue_unassigned,
            "review_scene_dialogue": unassigned_review_dialogue,
            "pending_review_total": pending_review_total,
            "sprite_text_candidate": sprite_text_candidate,
            "issue": "UI 에디터 검토 필요 항목이 0이 아님",
        })

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
        "warning_count": len(screenshot_issues) + len(broad_dialogue) + len(reused_screenshots) + len(container_rows),
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
            lines.append(
                f"- coverage dialogue_unassigned={x['coverage_dialogue_unassigned']} "
                f"99_unassigned_review dialogue={x['review_scene_dialogue']}: {x['issue']}"
            )
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
