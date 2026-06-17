#!/usr/bin/env python3
"""scene_catalog 생성기 — 게임 흐름(scene) 기반 통합 UI 에디터의 정본 카탈로그.

입력(권위 데이터):
  data/screen_checkpoints.json   게임순 prefix + nav/savestate (canvas 후보)
  data/sprites_index.json        스프라이트 인덱스(source 토큰으로 화면 추정)
  data/objlabel_sprites.json     합성 OBJ 라벨 스프라이트
  data/dialogue_groups.json      조립 대사 그룹(region + address)

출력:
  data/scene_catalog.json        {version, scenes:[{id,order,scope,subtag,title,canvas,
                                   dialogue_filter,sprite_filter, counts:{dialogue,sprite}}],
                                   coverage:{...}}

설계(3자 합의, todo.md):
  - SCENES = 게임 흐름순 큐레이션 정의(아래). 자동 배정은 "후보"이며 수동 보정은
    data/scene_catalog_overrides.json(include/exclude id 목록)으로 덮어쓴다.
  - 미배정 스프라이트/대사는 숨기지 않고 `99_unassigned_review`로 100% 수렴 → 누락 0 검증.
  - scope: all(필터용)/shared_select/part1/part2. order=정의 순.
  - 배정 규칙: 스프라이트=source_contains 첫 매칭 scene. 대사=region∈scene.regions AND
    (addr_ranges 없으면 전체, 있으면 주소 포함) 첫 매칭. noise 제외.

재생성: python3 tools/build_scene_catalog.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHK = ROOT / "data" / "screen_checkpoints.json"
SPR = ROOT / "data" / "sprites_index.json"
OBJ = ROOT / "data" / "objlabel_sprites.json"
DGRP = ROOT / "data" / "dialogue_groups.json"
OVERRIDES = ROOT / "data" / "scene_catalog_overrides.json"
OUT = ROOT / "data" / "scene_catalog.json"

# preview_capture가 실제 지원하는 canvas 키(실캡처 hijack). screen_checkpoint id와 별개.
# scene의 checkpoint(게임순 진입용) → preview canvas 키 매핑(지원하는 화면만).
# ⚠ 현재 preview_capture.CANVASES는 part2_menu 1종 → 22_part2_main_menu만 실캡처 가능.
#   Phase 7에서 canvas 추가 시 이 매핑 확장.
PREVIEW_BY_CHECKPOINT = {"07_part2_main_menu": "part2_menu"}


def preview_canvas_keys():
    """preview_capture.CANVASES의 실제 지원 키 집합(단일 권위)."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("preview_capture", ROOT / "tools" / "preview_capture.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return set(m.CANVASES.keys())
    except Exception:
        return {"part2_menu"}


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ── 게임 흐름순 scene 정의(큐레이션) ────────────────────────────────────────
# 각 scene: id, scope, subtag, title, canvas(checkpoint id 또는 None),
#   sprite: source_contains 토큰 리스트(부분일치, 첫 매칭 scene에 배정),
#   dialogue: {regions:[...], addr_ranges:[[lo,hi],...]?}  (addr_ranges 있으면 그 안만)
# 순서가 곧 order. 구체 scene(addr_ranges 지정)을 먼저, 광역 버킷(범위 미지정)을 뒤에 둔다.
SCENES = [
    # ── 공통 / 1+2편 선택(shared_select) ──
    dict(id="00_coldboot_nintendo", scope="shared_select", subtag="인트로",
         title="콜드부트 닌텐도 제공", canvas="01_coldboot_nintendo",
         sprite=["nintendo_presents", "common_nintendo"], dialogue=dict(regions=[])),
    dict(id="01_common_title", scope="shared_select", subtag="시작화면",
         title="공통 타이틀(시작하기)", canvas="02_common_title",
         sprite=["title:TITLE_OBJ", "title:TITLE_COPYRIGHT", "common_title"], dialogue=dict(regions=[])),
    dict(id="02_select_part", scope="shared_select", subtag="1+2편 선택",
         title="1+2편 선택 화면", canvas="03_select_part1",
         sprite=["title:SELECT_OBJ", "select_obj"], dialogue=dict(regions=[])),

    # ── 1편(part1) ──
    dict(id="10_part1_title", scope="part1", subtag="시작화면",
         title="1편 타이틀", canvas="04_part1_title",
         sprite=["part1_title", "PART1_TITLE_OBJ"], dialogue=dict(regions=[])),
    dict(id="11_part1_mode_select", scope="part1", subtag="모드 선택",
         title="1편 모드/메뉴 선택", canvas=None,
         sprite=["menu_label/", "part1_mode_select", "MODE_SELECT", "RULE_SELECT",
                 "TEAM_SETTING", "part1_operation", "OPERATION", "MAP_SELECT",
                 "SHOP_SELECT", "HARD_SHOP"], dialogue=dict(regions=[])),
    dict(id="12_part1_name_input", scope="part1", subtag="이름 입력",
         title="1편 이름 입력", canvas="40_part1_name_menu",
         sprite=["CATHERINE_NAME"], dialogue=dict(regions=[])),
    dict(id="13_part1_info_screen", scope="part1", subtag="유닛 정보",
         title="1편 유닛/상세 정보 화면", canvas=None,
         sprite=["part1_info_screen", "part1_full_info_spec", "part1_check_label",
                 "info_screen_bg_labels", "full_info_spec"], dialogue=dict(regions=[])),
    dict(id="14_part1_campaign", scope="part1", subtag="캠페인",
         title="1편 캠페인/미션/전투", canvas=None,
         sprite=["part1_campaign", "CAMPAIGN", "MISSION_LOGO", "part1_battle"],
         dialogue=dict(regions=[])),
    dict(id="18_part1_story", scope="part1", subtag="대사",
         title="1편 스토리 대사(전체)", canvas=None,
         sprite=[], dialogue=dict(regions=["part1"])),

    # ── 2편(part2) ──
    dict(id="20_part2_intro", scope="part2", subtag="인트로",
         title="2편 오프닝/프롤로그(신문·블랙홀·도미노)", canvas=None,
         sprite=["part2_intro", "intro_blackhole", "intro_campaign", "splash_logo",
                 "prologue_logo", "domino_co_name", "menu_newspaper", "blackhole"],
         dialogue=dict(regions=[])),
    dict(id="21_part2_title", scope="part2", subtag="시작화면",
         title="2편 타이틀", canvas="06_part2_title",
         sprite=["PART2_TITLE_OBJ", "part2_title"], dialogue=dict(regions=[])),
    dict(id="22_part2_main_menu", scope="part2", subtag="메뉴 선택",
         title="2편 메인 메뉴(모드 선택)", canvas="07_part2_main_menu",
         sprite=["part2_mode_menu", "mode_menu_obj"],
         dialogue=dict(regions=["part2"], addr_ranges=[[0xA2C000, 0xA2D000]])),
    dict(id="23_part2_campaign", scope="part2", subtag="캠페인 선택",
         title="2편 캠페인/작전 선택(월드맵)", canvas="20_mode_select_menu",
         sprite=["campaign_header", "mission_number", "level_label", "lets_go",
                 "redstar_region", "world_map_label", "mission_start", "air_mission",
                 "air_supremacy"], dialogue=dict(regions=[])),
    dict(id="24_part2_battle", scope="part2", subtag="전투",
         title="2편 전투(데미지 예측·N일째·행동메뉴·상태)", canvas="30_battle_attack",
         sprite=["battle_start_day", "damage_forecast", "check_label", "battle_day_banner",
                 "part2_objlabel/action_menu", "part2_objlabel/terrain",
                 "part2_objlabel/unit", "part2_objlabel/co_banner",
                 "part2_objlabel/status_header", "part2_objlabel/info_screen"],
         dialogue=dict(regions=[])),
    dict(id="25_part2_result", scope="part2", subtag="결과",
         title="2편 결과(성공·실패·요약·축하)", canvas=None,
         sprite=["result_success", "result_failure", "result_summary",
                 "result_congratulations"], dialogue=dict(regions=[])),
    dict(id="28_part2_story", scope="part2", subtag="대사",
         title="2편 스토리 대사(전체)", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"])),

    # ── 캠페인/공통 대사 ──
    dict(id="80_campaign_story", scope="part2", subtag="대사",
         title="캠페인 대사(전체)", canvas=None,
         sprite=[], dialogue=dict(regions=["campaign"])),
    dict(id="85_ui_common", scope="all", subtag="UI/공통",
         title="공통 UI 라벨/대사", canvas=None,
         sprite=["patch_block", "check_label"], dialogue=dict(regions=["ui"])),
    dict(id="90_other_dialogue", scope="all", subtag="대사",
         title="기타/공통 대사(분류 전)", canvas=None,
         sprite=[], dialogue=dict(regions=["other"])),
]

# region → scope (기본). dialogue 배정 검증/필터용.
REGION_SCOPE = {"part1": "part1", "part2": "part2", "campaign": "part2",
                "ui": "all", "other": "all", "font": "all"}


def sprite_section(source):
    s = (source or "").lower()
    if "part2" in s or "pt2" in s:
        return "part2"
    if "part1" in s or "pt1" in s or "menu_label/" in s:
        return "part1"
    return "common"


def _scope_section_ok(scope, section):
    """scene scope ↔ 스프라이트 section 교차 가드(타편 도둑질 방지).
    part1/part2 scene엔 반대편(part2/part1) 스프라이트 배정 금지. 그 외(공통/선택)는 허용."""
    if scope == "part1" and section == "part2":
        return False
    if scope == "part2" and section == "part1":
        return False
    return True


def assign_sprites(scenes, sprites):
    """source_contains 첫 매칭 scene에 스프라이트 id 배정. scope/section 가드. 미매칭은 unassigned."""
    bucket = {sc["id"]: [] for sc in scenes}
    unassigned = []
    for sp in sprites:
        src = (sp.get("source") or "")
        sid = sp.get("id")
        section = sprite_section(src)
        hit = None
        for sc in scenes:
            if not _scope_section_ok(sc.get("scope"), section):
                continue
            for tok in sc.get("sprite", []):
                if tok and tok in src:
                    hit = sc["id"]
                    break
            if hit:
                break
        if hit:
            bucket[hit].append(sid)
        else:
            # scan_lz77(미분류 그래픽)은 비텍스트 → 별도 풀, 그 외 텍스트성은 review
            unassigned.append(sid)
    return bucket, unassigned


def assign_dialogue(scenes, groups):
    """region + addr_range 첫 매칭 scene에 group_id 배정. noise 제외. 미매칭은 unassigned."""
    bucket = {sc["id"]: [] for sc in scenes}
    unassigned = []
    # 구체(addr_ranges 지정) scene 먼저 평가하도록 정렬: 정의에서 이미 구체가 앞.
    for g in groups:
        if g.get("flagged") is None:
            pass
        members = g.get("members") or []
        if not members:
            continue
        try:
            addr = int(members[0]["address"], 16)
        except (ValueError, KeyError, TypeError):
            continue
        region = g.get("region")
        # noise: 모든 멤버가 noise면 제외(그룹엔 is_noise 없음 → region=font는 글리프라 제외)
        if region == "font":
            continue
        hit = None
        for sc in scenes:
            dl = sc.get("dialogue", {})
            regs = dl.get("regions", [])
            if not regs or region not in regs:
                continue
            ar = dl.get("addr_ranges")
            if ar:
                if not any(lo <= addr < hi for lo, hi in ar):
                    continue
            hit = sc["id"]
            break
        if hit:
            bucket[hit].append(g.get("group_id"))
        else:
            unassigned.append(g.get("group_id"))
    return bucket, unassigned


def main():
    chk = load(CHK, {"checkpoints": []})
    chk_ids = {c["name"] for c in chk.get("checkpoints", [])}
    spr = load(SPR, {"sprites": []}).get("sprites", [])
    obj = (load(OBJ, {}) or {}).get("sprites", []) or []
    sprites = list(spr) + list(obj)
    groups = load(DGRP, {"groups": []}).get("groups", [])
    ov = load(OVERRIDES, {}) or {}

    scenes = [dict(s) for s in SCENES]
    sp_bucket, sp_un = assign_sprites(scenes, sprites)
    dl_bucket, dl_un = assign_dialogue(scenes, groups)

    # 수동 보정(include/exclude) 적용 — 스프라이트
    for sid, rule in (ov.get("sprite", {}) or {}).items():
        for x in rule.get("add", []):
            if x not in sp_bucket.get(sid, []):
                sp_bucket.setdefault(sid, []).append(x)
                if x in sp_un:
                    sp_un.remove(x)
        for x in rule.get("remove", []):
            if x in sp_bucket.get(sid, []):
                sp_bucket[sid].remove(x)
                sp_un.append(x)
    # 수동 보정 — 대사(group_id 이동/제외; region/range 오배정 수렴 경로)
    for sid, rule in (ov.get("dialogue", {}) or {}).items():
        for x in rule.get("add", []):
            # 다른 scene에서 제거(중복 방지) 후 추가
            for b in dl_bucket.values():
                if x in b:
                    b.remove(x)
            if x in dl_un:
                dl_un.remove(x)
            dl_bucket.setdefault(sid, []).append(x)
        for x in rule.get("remove", []):
            if x in dl_bucket.get(sid, []):
                dl_bucket[sid].remove(x)
                dl_un.append(x)

    pv_keys = preview_canvas_keys()
    out_scenes = []
    for order, sc in enumerate(scenes):
        checkpoint = sc.get("canvas")  # SCENES의 canvas= 는 screen_checkpoint id(게임순 진입용)
        checkpoint_exists = bool(checkpoint and checkpoint in chk_ids)
        # 실캡처 canvas = preview_capture가 실제 지원하는 키만(없으면 None→미지원).
        preview = PREVIEW_BY_CHECKPOINT.get(checkpoint) or PREVIEW_BY_CHECKPOINT.get(sc["id"])
        if preview not in pv_keys:
            preview = None
        canvas_status = "ready" if preview else "none"
        out_scenes.append({
            "id": sc["id"], "order": order * 10, "scope": sc["scope"],
            "subtag": sc["subtag"], "title": sc["title"],
            # canvas = 실캡처 프리뷰 키(없으면 None). checkpoint = 게임순 진입(미래 fresh-nav).
            "canvas": preview, "canvas_status": canvas_status,
            "checkpoint": checkpoint, "checkpoint_exists": checkpoint_exists,
            "dialogue_filter": sc.get("dialogue", {}),
            "sprite_filter": {"source_contains": sc.get("sprite", [])},
            "dialogue_ids": dl_bucket[sc["id"]],
            "sprite_ids": sp_bucket[sc["id"]],
            "counts": {"dialogue": len(dl_bucket[sc["id"]]), "sprite": len(sp_bucket[sc["id"]])},
        })

    # 미배정 review scene(누락 0 보증)
    out_scenes.append({
        "id": "99_unassigned_review", "order": 9990, "scope": "all",
        "subtag": "미배정", "title": "미배정(검토 필요) — 규칙 미매칭",
        "canvas": None, "canvas_status": "none",
        "dialogue_filter": {}, "sprite_filter": {},
        "dialogue_ids": dl_un, "sprite_ids": sp_un,
        "counts": {"dialogue": len(dl_un), "sprite": len(sp_un)},
    })

    # 비텍스트 스캔 스프라이트는 review 안에서 별도 표시용 카운트
    scan_un = sum(1 for sp in sprites if sp.get("id") in set(sp_un)
                  and (sp.get("source") or "").startswith("scan_lz77"))

    assigned_dl = sum(len(v) for v in dl_bucket.values())
    assigned_sp = sum(len(v) for v in sp_bucket.values())
    total_dl_groups = sum(1 for g in groups if g.get("region") != "font" and g.get("members"))
    catalog = {
        "version": 1,
        "_doc": "게임 흐름순 scene 카탈로그(통합 UI 에디터 정본). tools/build_scene_catalog.py 생성. "
                "수동보정 data/scene_catalog_overrides.json. 미배정은 99_unassigned_review로 100% 수렴.",
        "generated_from": {"checkpoints": str(CHK.relative_to(ROOT)),
                            "sprites": str(SPR.relative_to(ROOT)),
                            "dialogue": str(DGRP.relative_to(ROOT))},
        "scopes": ["all", "shared_select", "part1", "part2"],
        "coverage": {
            "sprites_total": len(sprites), "sprites_assigned": assigned_sp,
            "sprites_unassigned": len(sp_un), "sprites_unassigned_scan_lz77": scan_un,
            "dialogue_groups_total": total_dl_groups, "dialogue_assigned": assigned_dl,
            "dialogue_unassigned": len(dl_un),
        },
        "scenes": out_scenes,
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"scene_catalog.json 생성: {len(out_scenes)} scenes → {OUT}")
    print(f"  스프라이트: {assigned_sp}/{len(sprites)} 배정, 미배정 {len(sp_un)}(scan_lz77 {scan_un})")
    print(f"  대사그룹:   {assigned_dl}/{total_dl_groups} 배정, 미배정 {len(dl_un)}")
    print("  scene별 count(게임순):")
    for sc in out_scenes:
        print(f"    {sc['id']:28s} [{sc['scope']:13s}|{sc['subtag']:8s}] "
              f"대사{sc['counts']['dialogue']:5d} 스프{sc['counts']['sprite']:4d} "
              f"canvas={sc['canvas_status']}")


if __name__ == "__main__":
    main()
