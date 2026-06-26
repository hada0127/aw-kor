#!/usr/bin/env python3
"""장면 의미 감사.

provenance 감사는 "현재 ROM/상태에서 재현되는 캡처인가"만 본다.
이 파일은 지금까지 수동 검수로 확인된 화면-장면 불일치와 너무 넓은
대사 bucket을 별도 실패로 남겨, 잘못된 실화면을 green 처리하지 않게 한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "data" / "scene_catalog.json"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
OUT_DIR = ROOT / "temp" / "scene_semantic_audit"

REVIEW_IDS = {"98_extraction_noise_review", "99_unassigned_review"}

KNOWN_BAD = {
    "19f_part1_extra_story": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/part1_main_sweep/state_017.ss0",
        "issue": "대사 scene인데 현재 캡처는 대사창 없는 전투 맵",
        "required": "해당 23개 대사가 실제 표시되는 대사창 프레임을 별도 확보",
    },
    "20_part2_intro_newspaper": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/part2_menu_sweep/state_001.ss0",
        "issue": "인트로 신문/스플래시가 아니라 신문 배경 위 메인 메뉴",
        "required": "메뉴가 뜨기 전 실제 신문/스플래시 프레임 또는 장면 재분류",
    },
    "23c_part2_sound_room": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/part2_soundroom_select_probe/state_001.ss0",
        "issue": "사운드룸 트랙 목록 scene인데 현재 캡처는 상점 선택/해금 전 화면",
        "required": "사운드룸 해금 후 SELECT 전환으로 실제 트랙 목록이 표시된 state",
    },
    "26a_part2_battle_start_overlays": {
        "severity": "major",
        "bad_state": "temp/scene_entrypoints/part2_first_battle_drive_wait/state_0031.ss0",
        "issue": "전투 시작 애니메이션 중 단일 일자/전환 프레임만 대표함",
        "required": "회전하며 나오는 작전개시/전투개시 스프라이트 프레임들을 별도 캡처",
    },
    "28_part2_result_status": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/surrender_confirm_scan/state_002.ss0",
        "issue": "결과 성공/실패 오버레이가 아니라 항복 확인 대사",
        "required": "작전성공/작전실패 오버레이가 실제로 표시된 state",
    },
    "29_part2_result_summary": {
        "severity": "critical",
        "bad_state": "temp/auto_results2/state_020.ss0",
        "issue": "결과 요약/축하가 아니라 전투 맵",
        "required": "교전/파워/테크닉/승리 요약이 표시된 state",
    },
    "30d_part2_story_green_earth": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/part2_main_sweep/state_008.ss0",
        "issue": "그린어스 스토리가 아니라 레드스타 작전 지도/대사",
        "required": "그린어스 전반 스토리의 실제 대사 프레임",
    },
    "30f_part2_story_final_and_co": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/part2_main_sweep/state_024.ss0",
        "issue": "최종전/CO 설명이 아니라 일반 전투 START 메뉴/안내 대사",
        "required": "최종전 또는 CO 설명 대사가 실제 표시된 프레임",
    },
    "89b_common_battle_defeat_comm_messages": {
        "severity": "critical",
        "bad_state": "temp/scene_entrypoints/system_surrender_scan_a/state_002.ss0",
        "issue": "패배/통신 오류 메시지 scene인데 현재는 시스템 메뉴 placeholder",
        "required": "각 군 패배 메시지 또는 통신 오류 메시지가 실제 표시된 state",
    },
}

MULTI_SCREEN_SCENES = {
    "86_common_compact_menu_tables": {
        "severity": "major",
        "issue": "공통 압축 메뉴 라벨 테이블을 단일 상점/통신 후보 화면으로 대표",
        "required": "튜토리얼/캠페인/트라이얼/프리배틀/상점/지도편집/통신 노출 화면 분리",
        "min_extra": 6,
    },
}

ANIMATION_FRAME_REQUIREMENTS = {
    "26a_part2_battle_start_overlays": {
        "severity": "major",
        "min_extra": 4,
        "issue": "전투 시작/일자 affine 애니메이션 보조 프레임 부족",
        "required": "회전 도입/중앙 표시/축소 퇴장/HUD 복귀 등 최소 4개 checkpoint를 extra_screenshots에 연결",
    },
}

RUNTIME_WATCH_REQUIREMENTS = {
    "89b_common_battle_defeat_comm_messages": {
        "severity": "critical",
        "watch_log": "temp/scene_entrypoints/part2_3p_surrender_confirm_fine/defeat_watch.log",
        "required_hits": {"g_00A34D18"},
        "issue": "실제 3P surrender defeat 캡처의 watch hit 주소가 scene dialogue_ids에 없음",
        "required": "watch log의 addr=08xxxxxx 런타임 hit 그룹을 scene_catalog_overrides.json으로 해당 scene에 연결",
    },
}


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def game_scenes(catalog: dict) -> list[dict]:
    out = []
    for scene in catalog.get("scenes", []):
        if (
            scene.get("scope") == "review"
            or scene.get("id") in REVIEW_IDS
            or scene.get("scene_role") == "container"
        ):
            continue
        out.append(scene)
    return out


def container_scenes(catalog: dict) -> list[dict]:
    return [scene for scene in catalog.get("scenes", []) if scene.get("scene_role") == "container"]


def state_matches(checkpoint: dict, expected: str) -> bool:
    state = checkpoint.get("state")
    if not state:
        return False
    return Path(state).as_posix() == Path(expected).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def watch_hit_group_ids(log_path: str) -> set[str]:
    path = ROOT / log_path
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for token in line.split():
            if not token.startswith("addr="):
                continue
            try:
                bus_addr = int(token.split("=", 1)[1], 16)
            except ValueError:
                continue
            if 0x08000000 <= bus_addr < 0x0A000000:
                ids.add(f"g_{bus_addr - 0x08000000:08X}")
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--broad-dialogue-threshold", type=int, default=200)
    args = ap.parse_args()

    catalog = load(CAT, {"scenes": []})
    checkpoints = load(CHECKPOINTS, {"checkpoints": []}).get("checkpoints", [])
    checkpoint_by_name = {c.get("name"): c for c in checkpoints}
    issues: list[dict] = []
    frame_hash_owners: dict[str, list[dict]] = defaultdict(list)

    semantic_scenes = game_scenes(catalog)
    containers = container_scenes(catalog)

    for scene in semantic_scenes:
        scene_id = scene.get("id")
        screenshot = scene.get("screenshot") or {}
        checkpoint_name = screenshot.get("checkpoint")
        checkpoint = checkpoint_by_name.get(checkpoint_name, {})
        capture_path = screenshot.get("capture_path")
        if capture_path:
            frame = Path(capture_path)
            if not frame.is_absolute():
                frame = ROOT / frame
            if frame.exists() and frame.stat().st_size > 0:
                frame_hash_owners[sha256(frame)].append({
                    "scene": scene_id,
                    "title": scene.get("title"),
                    "checkpoint": checkpoint_name,
                    "capture_path": capture_path,
                })
        known = KNOWN_BAD.get(scene_id)
        if known and state_matches(checkpoint, known["bad_state"]):
            issues.append({
                "scene": scene_id,
                "title": scene.get("title"),
                "checkpoint": checkpoint_name,
                "severity": known["severity"],
                "issue": known["issue"],
                "required": known["required"],
                "state": checkpoint.get("state"),
            })
        frame_req = ANIMATION_FRAME_REQUIREMENTS.get(scene_id)
        if frame_req:
            extras = (scene.get("entrypoint") or {}).get("extra_screenshots") or []
            extra_names = [
                extra.get("checkpoint") if isinstance(extra, dict) else extra
                for extra in extras
            ]
            extra_names = [name for name in extra_names if name]
            missing = [name for name in extra_names if name not in checkpoint_by_name]
            if len(extra_names) < frame_req["min_extra"] or missing:
                issues.append({
                    "scene": scene_id,
                    "title": scene.get("title"),
                    "checkpoint": checkpoint_name,
                    "severity": frame_req["severity"],
                    "issue": frame_req["issue"],
                    "required": frame_req["required"],
                    "extra_count": len(extra_names),
                    "missing_extra_checkpoints": missing,
                })
        multi = MULTI_SCREEN_SCENES.get(scene_id)
        if multi:
            extras = (scene.get("entrypoint") or {}).get("extra_screenshots") or []
            extra_names = [
                extra.get("checkpoint") if isinstance(extra, dict) else extra
                for extra in extras
            ]
            extra_names = [name for name in extra_names if name]
            missing = [name for name in extra_names if name not in checkpoint_by_name]
            if len(extra_names) < multi.get("min_extra", 1) or missing:
                issues.append({
                    "scene": scene_id,
                    "title": scene.get("title"),
                    "checkpoint": checkpoint_name,
                    "severity": multi["severity"],
                    "issue": multi["issue"],
                    "required": multi["required"],
                    "state": checkpoint.get("state"),
                    "extra_count": len(extra_names),
                    "missing_extra_checkpoints": missing,
                })
        dialogue_count = len(scene.get("dialogue_ids") or [])
        if dialogue_count >= args.broad_dialogue_threshold:
            issues.append({
                "scene": scene_id,
                "title": scene.get("title"),
                "checkpoint": checkpoint_name,
                "severity": "major",
                "issue": f"대사 {dialogue_count}개가 대표 화면 하나에 묶임",
                "required": "실제 진행 화면 단위로 대사 range와 캡처를 더 쪼개야 함",
                "dialogue_count": dialogue_count,
            })
        if checkpoint.get("mode") == "savestate" and not (scene.get("entrypoint") or {}).get("source_state"):
            issues.append({
                "scene": scene_id,
                "title": scene.get("title"),
                "checkpoint": checkpoint_name,
                "severity": "major",
                "issue": "savestate checkpoint인데 scene_entrypoints.json에 source_state가 없음",
                "required": "재현 가능한 source_state 또는 fresh nav를 scene entrypoint에 기록",
                "state": checkpoint.get("state"),
            })
        watch_req = RUNTIME_WATCH_REQUIREMENTS.get(scene_id)
        if watch_req:
            observed = watch_hit_group_ids(watch_req["watch_log"])
            missing_watch = sorted(watch_req["required_hits"] - observed)
            if missing_watch:
                issues.append({
                    "scene": scene_id,
                    "title": scene.get("title"),
                    "checkpoint": checkpoint_name,
                    "severity": watch_req["severity"],
                    "issue": "기록된 watch log에 필수 런타임 hit 주소가 없음",
                    "required": "watch log/provenance를 재확보하거나 audit 요구 주소를 갱신",
                    "missing_watch_hits": missing_watch,
                    "watch_log": watch_req["watch_log"],
                    "state": checkpoint.get("state"),
                })
            have = set(scene.get("dialogue_ids") or [])
            missing = sorted(watch_req["required_hits"] - have)
            if missing:
                issues.append({
                    "scene": scene_id,
                    "title": scene.get("title"),
                    "checkpoint": checkpoint_name,
                    "severity": watch_req["severity"],
                    "issue": watch_req["issue"],
                    "required": watch_req["required"],
                    "missing_dialogue_ids": missing,
                    "watch_log": watch_req["watch_log"],
                    "state": checkpoint.get("state"),
                })

    for digest, owners in sorted(frame_hash_owners.items(), key=lambda item: item[1][0]["scene"]):
        if len(owners) <= 1:
            continue
        issues.append({
            "scene": ", ".join(owner["scene"] for owner in owners),
            "title": " / ".join(owner["title"] for owner in owners),
            "checkpoint": ", ".join(owner["checkpoint"] for owner in owners),
            "severity": "major",
            "issue": f"서로 다른 scene {len(owners)}개가 동일 frame.png 해시를 공유함",
            "required": "각 scene의 실제 고유 화면을 확보하거나, 같은 화면이면 scene 구조를 재검토",
            "frame_sha256": digest,
            "owners": owners,
        })

    container_rows = []
    for scene in containers:
        shot = scene.get("screenshot") or {}
        row = {
            "scene": scene.get("id"),
            "title": scene.get("title"),
            "dialogue_count": len(scene.get("dialogue_ids") or []),
            "status": shot.get("status"),
            "grade": shot.get("grade"),
            "note": shot.get("note") or "",
        }
        container_rows.append(row)
        if scene.get("capture_required") is not False:
            issues.append({**row, "checkpoint": shot.get("checkpoint"), "severity": "critical",
                           "issue": "container capture_required가 false가 아님",
                           "required": "container는 실제 화면 캡처 대상에서 제외하되 별도 추적해야 함"})
        if scene.get("entrypoint"):
            issues.append({**row, "checkpoint": shot.get("checkpoint"), "severity": "critical",
                           "issue": "container에 entrypoint가 붙어 있음",
                           "required": "container는 대표 진입점 없이 not_a_scene bucket으로만 추적해야 함"})
        if scene.get("checkpoint") or shot.get("checkpoint") or shot.get("url"):
            issues.append({**row, "checkpoint": shot.get("checkpoint"), "severity": "critical",
                           "issue": "container에 checkpoint/url이 붙어 있음",
                           "required": "잔여 버킷에는 대표 스크린샷을 붙이지 말고 split 실제 화면에만 연결"})
        if shot.get("status") != "container" or shot.get("grade") != "not_a_scene" or not row["note"]:
            issues.append({**row, "checkpoint": shot.get("checkpoint"), "severity": "critical",
                           "issue": "container status/grade/note 계약 위반",
                           "required": "container 사유와 not_a_scene 상태를 명시"})

    summary = {
        "scene_count": len(semantic_scenes),
        "container_count": len(container_rows),
        "container_dialogue_count": sum(row["dialogue_count"] for row in container_rows),
        "issue_count": len(issues),
        "critical_count": sum(1 for i in issues if i["severity"] == "critical"),
        "major_count": sum(1 for i in issues if i["severity"] == "major"),
    }
    report = {"summary": summary, "issues": issues, "containers": container_rows}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Scene Semantic Audit",
        "",
        f"- game scenes: {summary['scene_count']}",
        f"- tracked containers: {summary['container_count']} "
        f"(dialogue {summary['container_dialogue_count']})",
        f"- issues: {summary['issue_count']}",
        f"- critical: {summary['critical_count']}",
        f"- major: {summary['major_count']}",
        "",
    ]
    for sev in ("critical", "major"):
        subset = [i for i in issues if i["severity"] == sev]
        if not subset:
            continue
        lines.append(f"## {sev.upper()}")
        for item in subset:
            lines.append(
                f"- {item['scene']} {item.get('checkpoint')}: {item['issue']} "
                f"=> {item['required']}"
            )
        lines.append("")
    if container_rows:
        lines.append("## Tracked Containers")
        for row in container_rows:
            lines.append(f"- {row['scene']} d{row['dialogue_count']}: {row['note']}")
        lines.append("")
    (OUT_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    print(f"semantic audit: {OUT_DIR / 'report.md'}")
    if args.strict and summary["critical_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
