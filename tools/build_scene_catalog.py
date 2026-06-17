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

# scene의 checkpoint(게임순 진입용) → preview canvas 키 매핑은 레지스트리(data/preview_canvases.json)의
# canvas.checkpoint 필드에서 자동 도출(코드 하드코딩 제거 — 새 canvas 추가만으로 확장).
def _load_preview_registry():
    """preview_capture.CANVASES(레지스트리 병합 반영) 로드 → (지원 키 집합, checkpoint→key 맵)."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("preview_capture", ROOT / "tools" / "preview_capture.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        keys = set(m.CANVASES.keys())
        by_chk = {cv.get("checkpoint"): k for k, cv in m.CANVASES.items() if cv.get("checkpoint")}
        return keys, by_chk
    except Exception:
        return {"part2_menu"}, {"07_part2_main_menu": "part2_menu"}


def preview_canvas_keys():
    return _load_preview_registry()[0]


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ── 게임 흐름순 scene 정의(큐레이션) ────────────────────────────────────────
# 각 scene: id, scope, subtag, title, canvas(checkpoint id 또는 None),
#   screenshot: scene 증거 스크린샷용 checkpoint id. 없으면 canvas/checkpoint를 사용.
#   sprite: source_contains 토큰 리스트(부분일치, 첫 매칭 scene에 배정),
#   sprite_ids: 정확한 sprite id 리스트(중복 source/오프셋 분리용, token보다 우선),
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
    dict(id="02_select_part1", scope="shared_select", subtag="1+2편 선택",
         title="1+2편 선택 화면(1편 선택)", canvas="03_select_part1",
         sprite=["title:SELECT_OBJ", "select_obj"], dialogue=dict(regions=[])),
    dict(id="03_select_part2", scope="shared_select", subtag="1+2편 선택",
         title="1+2편 선택 화면(2편 선택)", canvas="05_select_part2",
         sprite=[], dialogue=dict(regions=[])),

    # ── 1편(part1) ──
    dict(id="10_part1_title", scope="part1", subtag="시작화면",
         title="1편 타이틀", canvas="04_part1_title",
         sprite=["part1_title", "PART1_TITLE_OBJ"], dialogue=dict(regions=[])),
    dict(id="11_part1_world_menu", scope="part1", subtag="모드 선택",
         title="1편 월드 메뉴 라벨", canvas=None, screenshot="40_part1_name_menu",
         sprite_ids=["lz77_00C0310C", "lz77_00C03510", "lz77_00C03880", "lz77_00C03AF0",
                     "lz77_00C03F68", "lz77_00C043E0", "lz77_00C0489C", "lz77_00C04D48",
                     "lz77_00C051DC", "lz77_00C05658", "lz77_00C05994", "lz77_00C05D78",
                     "lz77_00C06218", "lz77_00C0668C", "lz77_00C06B78"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="12_part1_submenus", scope="part1", subtag="하위 메뉴",
         title="1편 하위 메뉴 라벨(싱글/통신/카드)", canvas=None, screenshot="42_part1_single_battle",
         sprite_ids=["lz77_00C1A2BC", "lz77_00C1A564", "lz77_00C1A81C", "lz77_00C1A9DC",
                     "lz77_00C1AC60", "lz77_00C1AE74", "lz77_00C1B0E4", "lz77_00C1B3A8",
                     "lz77_00C1B610", "lz77_00C1B830"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="13_part1_name_input", scope="part1", subtag="이름 입력",
         title="1편 이름 입력", canvas="40_part1_name_menu",
         sprite_ids=["lz77_00C102A8"], sprite=[], dialogue=dict(regions=[])),
    dict(id="14_part1_operation_logos", scope="part1", subtag="작전/설정",
         title="1편 작전/지도/상점/룰 화면 로고", canvas=None, screenshot="41_part1_operation_room",
         sprite_ids=["lz77_00C18CB4", "lz77_00C18F48", "lz77_00C191E0", "lz77_00C194D8",
                     "lz77_00C19A9C", "lz77_00C19D14", "lz77_00C19FF0"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="15_part1_info_screen", scope="part1", subtag="유닛 정보",
         title="1편 유닛/상세 정보 화면", canvas=None,
         screenshot="32_battle_continue",
         sprite=["part1_info_screen", "part1_full_info_spec", "part1_check_label",
                 "info_screen_bg_labels", "full_info_spec"], dialogue=dict(regions=[])),
    dict(id="16_part1_campaign", scope="part1", subtag="캠페인",
         title="1편 캠페인/미션 로고", canvas=None, screenshot="20_mode_select_menu",
         sprite_ids=["lz77_00C18738", "lz77_00C19794"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="17_part1_battle", scope="part1", subtag="전투",
         title="1편 전투 N일째 배너", canvas=None, screenshot="30_battle_attack",
         sprite_ids=["lz77_00EE5E14"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="18_part1_story", scope="part1", subtag="대사",
         title="1편 스토리 대사(전체)", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"])),

    # ── 2편(part2) ──
    dict(id="20_part2_intro_newspaper", scope="part2", subtag="인트로",
         title="2편 인트로 신문/스플래시", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_004D8AF8", "lz77_005B5D10"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="21_part2_intro_blackhole", scope="part2", subtag="인트로",
         title="2편 인트로 블랙홀/도미노/프롤로그", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_0045274C", "lz77_004E0478", "lz77_004E17C0", "lz77_004ECD60",
                     "lz77_005BBB3C"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="22_part2_title", scope="part2", subtag="시작화면",
         title="2편 타이틀", canvas="06_part2_title",
         sprite=["PART2_TITLE_OBJ", "part2_title"], dialogue=dict(regions=[])),
    dict(id="23_part2_main_menu", scope="part2", subtag="메뉴 선택",
         title="2편 메인 메뉴(모드 선택)", canvas="07_part2_main_menu",
         sprite=["part2_mode_menu", "mode_menu_obj"],
         dialogue=dict(regions=["part2"], addr_ranges=[[0xA2C000, 0xA2D000]])),
    dict(id="24_part2_campaign_map", scope="part2", subtag="캠페인 선택",
         title="2편 캠페인/작전 선택(월드맵)", canvas="20_mode_select_menu",
         sprite_ids=["lz77_00541BB8", "lz77_0054214C", "lz77_00547188", "lz77_005488A0",
                     "lz77_005A38D4", "lz77_005AAA68", "lz77_005AF674"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="25_part2_mission_titles", scope="part2", subtag="미션 진입",
         title="2편 미션 시작/에어 미션 타이틀", canvas=None, screenshot="32_battle_continue",
         sprite_ids=["lz77_00C10B34", "lz77_00C11D9C", "lz77_00C1205C"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="26_part2_battle_labels", scope="part2", subtag="전투",
         title="2편 전투 라벨(N일째·체크·데미지 예측)", canvas="30_battle_attack",
         sprite_ids=["lz77_0045EC74", "lz77_0045FCC8", "lz77_0092DF84", "lz77_0092EB5C",
                     "lz77_00966C0C", "lz77_009677E4", "lz77_0099F4B0", "lz77_009A0088",
                     "lz77_009D7D54", "lz77_009D892C", "lz77_00BD4FBC"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="27_part2_battle_objlabels", scope="part2", subtag="전투",
         title="2편 전투 OBJ 라벨(행동·유닛·지형·상태)", canvas=None, screenshot="31_battle_dialog",
         sprite_ids=["objlabel_p2_terrain_status", "objlabel_p2_terrain_compact",
                     "objlabel_p2_unit_status", "objlabel_p2_unit_compact",
                     "objlabel_p2_co_banner", "objlabel_p2_status_header",
                     "objlabel_p2_info_screen", "objlabel_p2_action_menu"],
         sprite=[],
         dialogue=dict(regions=[])),
    dict(id="28_part2_result_status", scope="part2", subtag="결과",
         title="2편 결과 성공/실패 오버레이", canvas=None, screenshot="33_battle_transport",
         sprite_ids=["lz77_00930520", "lz77_009691A8", "lz77_009A1A4C", "lz77_009DA2F0",
                     "lz77_00BFBB54", "lz77_00EE8A64", "lz77_00EE8F68"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="29_part2_result_summary", scope="part2", subtag="결과",
         title="2편 결과 요약/축하", canvas=None, screenshot="33_battle_transport",
         sprite_ids=["lz77_0059DA5C", "lz77_00BFB45C"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="30_part2_story", scope="part2", subtag="대사",
         title="2편 스토리 대사(전체)", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"])),

    # ── 캠페인/공통 대사 ──
    dict(id="80_campaign_story", scope="part2", subtag="대사",
         title="캠페인 대사(전체)", canvas=None, screenshot="20_mode_select_menu",
         sprite=[], dialogue=dict(regions=["campaign"])),
    dict(id="85_ui_common", scope="all", subtag="UI/공통",
         title="공통 UI 라벨/대사", canvas=None, screenshot="02_common_title",
         sprite=["patch_block", "check_label"], dialogue=dict(regions=["ui"])),
    dict(id="90_other_dialogue", scope="all", subtag="대사",
         title="기타/공통 대사(분류 전)", canvas=None, screenshot="31_battle_dialog",
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
    """정확한 sprite_ids 우선, 나머지는 source_contains 첫 매칭 scene에 배정."""
    bucket = {sc["id"]: [] for sc in scenes}
    explicit = {}
    duplicate_explicit = []
    for sc in scenes:
        for sid in sc.get("sprite_ids", []) or []:
            if sid in explicit and explicit[sid] != sc["id"]:
                duplicate_explicit.append((sid, explicit[sid], sc["id"]))
            explicit[sid] = sc["id"]
    if duplicate_explicit:
        detail = ", ".join("%s:%s/%s" % x for x in duplicate_explicit[:10])
        raise ValueError("중복 explicit sprite_ids: " + detail)
    known = {sp.get("id") for sp in sprites}
    missing = sorted(set(explicit) - known)
    if missing:
        raise ValueError("존재하지 않는 explicit sprite_ids: " + ", ".join(missing[:20]))
    seen_sprites = set()
    unassigned = []

    def add_unique(scene_id, sid):
        if sid not in bucket[scene_id]:
            bucket[scene_id].append(sid)

    for sp in sprites:
        src = (sp.get("source") or "")
        sid = sp.get("id")
        if not sid or sid in seen_sprites:
            continue
        seen_sprites.add(sid)
        section = sprite_section(src)
        if sid in explicit:
            add_unique(explicit[sid], sid)
            continue
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
            add_unique(hit, sid)
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
    chk_by_id = {c["name"]: c for c in chk.get("checkpoints", [])}
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

    pv_keys, pv_by_chk = _load_preview_registry()
    out_scenes = []
    for order, sc in enumerate(scenes):
        checkpoint = sc.get("canvas")  # SCENES의 canvas= 는 screen_checkpoint id(게임순 진입용)
        checkpoint_exists = bool(checkpoint and checkpoint in chk_ids)
        shot_checkpoint = sc.get("screenshot") or checkpoint
        shot = chk_by_id.get(shot_checkpoint)
        if shot:
            shot_grade = shot.get("grade") or ("stale_state" if shot.get("stale_bg") else "ground_truth")
            screenshot = {"checkpoint": shot_checkpoint,
                          "url": f"/scene_shots/{shot_checkpoint}.png",
                          "mode": shot.get("mode"), "grade": shot_grade,
                          "status": "capturable", "note": shot.get("note", "")}
        else:
            screenshot = {"checkpoint": shot_checkpoint, "url": None, "mode": None,
                          "grade": "missing_checkpoint", "status": "missing_checkpoint", "note": ""}
        # 실캡처 canvas = 레지스트리에서 checkpoint→canvas로 도출(지원 키만).
        preview = pv_by_chk.get(checkpoint) or pv_by_chk.get(sc["id"])
        if preview not in pv_keys:
            preview = None
        canvas_status = "ready" if preview else "none"
        out_scenes.append({
            "id": sc["id"], "order": order * 10, "scope": sc["scope"],
            "subtag": sc["subtag"], "title": sc["title"],
            # canvas = 실캡처 프리뷰 키(없으면 None). checkpoint = 게임순 진입(미래 fresh-nav).
            "canvas": preview, "canvas_status": canvas_status,
            "checkpoint": checkpoint, "checkpoint_exists": checkpoint_exists,
            "screenshot": screenshot,
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
        "checkpoint": None, "checkpoint_exists": False,
        "screenshot": {"checkpoint": None, "url": None, "mode": None, "grade": "not_a_scene",
                       "status": "not_a_scene", "note": "미배정 검토 bucket"},
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
