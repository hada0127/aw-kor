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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHK = ROOT / "data" / "screen_checkpoints.json"
SPR = ROOT / "data" / "sprites_index.json"
OBJ = ROOT / "data" / "objlabel_sprites.json"
DGRP = ROOT / "data" / "dialogue_groups.json"
OVERRIDES = ROOT / "data" / "scene_catalog_overrides.json"
OUT = ROOT / "data" / "scene_catalog.json"

SELECT_OBJ_ID = "lz77_00024A34"
SELECT_TOP_TITLE_ID = SELECT_OBJ_ID + "#select_top_title"
SELECT_BOTTOM_TITLE_ID = SELECT_OBJ_ID + "#select_bottom_title"
NOISE_REVIEW_SCENE_ID = "98_extraction_noise_review"
SELECT_VIRTUAL_META = {
    SELECT_TOP_TITLE_ID: ("select_top_title", "1/2편 선택 화면 상단 제목"),
    SELECT_BOTTOM_TITLE_ID: ("select_bottom_title", "1/2편 선택 화면 하단 제목"),
}

PLACEHOLDER_KO_MARKERS = (
    "미상", "번역 불가", "해독 불가", "원문 깨짐", "문자 깨짐", "문자 오류"
)
MOJIBAKE_MARKER_CHARS = set(
    "劔韋珥囮髯髷闊矣珮鴃粐聽粤珞蓙鉗鳬鳧韈鱚瞻跚"
    "轟訣麹惧沮泅棡撼鞴蒻鱇胝齏肬胙跖蓐鱠鱶"
)

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


def _load_build_guards():
    """빌드가 실제로 건드리는 슬롯/보호 영역을 카탈로그 분류에도 사용한다."""
    try:
        tools_dir = str(ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import build_korean_full as B  # noqa: WPS433
        return {
            "slots": B.load_slots(),
            "deny": list(getattr(B, "DENY_REGIONS", [])),
            "pair": list(getattr(B, "PAIR_RENDERER_REGIONS", [])),
        }
    except Exception:
        return {"slots": {}, "deny": [], "pair": []}


def _in_ranges(addr, ranges):
    return any(lo <= addr < hi for lo, hi in (ranges or []))


def _range_overlap(lo, hi, ranges):
    return any(lo < rhi and hi > rlo for _name, rlo, rhi in (ranges or []))


def _has_kana(text):
    return any(0x3040 <= ord(ch) <= 0x30FF for ch in (text or ""))


def _has_hangul(text):
    return any("가" <= ch <= "힣" for ch in (text or ""))


def _mojibake_score(text):
    return sum(1 for ch in (text or "") if ch in MOJIBAKE_MARKER_CHARS)


def _member_addr_slot(member, guards):
    try:
        addr = int((member.get("address") or "0x0"), 16)
    except (ValueError, TypeError):
        addr = 0
    slot = guards["slots"].get(addr)
    if not isinstance(slot, int) or slot <= 0:
        slot = member.get("slot") if isinstance(member.get("slot"), int) else 0
    return addr, slot


def _member_build_status(member, guards):
    addr, slot = _member_addr_slot(member, guards)
    hi = addr + max(slot, 1)
    if not slot:
        return "no_slot"
    if addr < 0x800000:
        return "under_safe_min"
    if _range_overlap(addr, hi, guards["deny"]):
        return "deny"
    if _range_overlap(addr, hi, guards["pair"]):
        return "pair"
    return "writable"


def _dialogue_matches(scene, region, addr, specific_only=None):
    dl = scene.get("dialogue", {})
    regs = dl.get("regions", [])
    if not regs or region not in regs:
        return False
    ranges = dl.get("addr_ranges")
    if specific_only is True and not ranges:
        return False
    if specific_only is False and ranges:
        return False
    return _in_ranges(addr, ranges) if ranges else True


def _review_only_dialogue(group, guards):
    """광역 scene으로 흘러가면 오해를 만드는 추출 노이즈/빌드 제외 후보."""
    members = group.get("members") or []
    if not members:
        return True
    region = group.get("region")
    if region == "font":
        return True

    statuses = [_member_build_status(m, guards) for m in members]
    if statuses and all(s in {"under_safe_min", "no_slot"} for s in statuses):
        return True
    if statuses and all(s in {"deny", "pair", "no_slot"} for s in statuses):
        return True

    ja = (group.get("assembled_ja") or "").strip()
    ko = (group.get("assembled_ko") or "").strip()
    if not ko:
        ko = "".join((m.get("ko") or "") for m in members).strip()
    if not ja:
        return True

    placeholder_ko = any(marker in ko for marker in PLACEHOLDER_KO_MARKERS)
    mojibake = _mojibake_score(ja)
    has_kana = _has_kana(ja)
    has_hangul = _has_hangul(ko)

    if placeholder_ko:
        return True
    if mojibake >= 3 and (not has_hangul or ko == ja):
        return True
    if not has_kana and mojibake >= 1 and not has_hangul:
        return True
    if region in {"other", "ui"} and not ko and (len(ja) <= 8 or mojibake):
        return True
    if region in {"other", "ui"} and ko == ja and not has_hangul and (not has_kana or mojibake):
        return True
    return False


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
         sprite_ids=["lz77_00021CE8"], sprite=["nintendo_presents", "common_nintendo"],
         dialogue=dict(regions=[])),
    dict(id="01_common_title", scope="shared_select", subtag="시작화면",
         title="공통 타이틀(시작하기)", canvas="02_common_title",
         sprite=["title:TITLE_OBJ", "title:TITLE_COPYRIGHT", "common_title"], dialogue=dict(regions=[])),
    dict(id="02_select_part1", scope="shared_select", subtag="1+2편 선택",
         title="1+2편 선택 화면(1편 선택)", canvas="03_select_part1",
         sprite_ids=[SELECT_TOP_TITLE_ID, SELECT_BOTTOM_TITLE_ID],
         sprite=[], dialogue=dict(regions=[])),
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
         sprite=[],
         dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDFA5E0, 0xDFAAC0],  # 모드 선택/하위 메뉴 설명
         ])),
    dict(id="12_part1_single_submenus", scope="part1", subtag="하위 메뉴",
         title="1편 싱글/맵 하위 메뉴 라벨", canvas=None, screenshot="42_part1_single_battle",
         sprite_ids=["lz77_00C1A2BC", "lz77_00C1A81C", "lz77_00C1A9DC",
                     "lz77_00C1AE74", "lz77_00C1B0E4", "lz77_00C1B3A8",
                     "lz77_00C1B610", "lz77_00C1B830"],
         sprite=[],
         dialogue=dict(regions=["part1", "other"], addr_ranges=[
             [0xD81C24, 0xD82004],  # 맵 디자인/대전 조건 도움말 선행 테이블
             [0xD82004, 0xD824C0],  # 1편 맵 디자인 도움말/파일/채우기
             [0xD83254, 0xD832E0],  # 맵 디자인 메뉴/로드 라벨
             [0x805B04, 0x805B70],  # 공통 복제본: 맵 디자인 메뉴/로드 라벨
             [0x81B104, 0x81B120],  # 파일 없음
         ])),
    dict(id="13_part1_link_submenus", scope="part1", subtag="하위 메뉴",
         title="1편 통신 하위 메뉴 라벨", canvas=None, screenshot="43_part1_link",
         sprite_ids=["lz77_00C1A564", "lz77_00C1AC60"],
         sprite=[],
         dialogue=dict(regions=["ui", "other"], addr_ranges=[
             [0x9292A8, 0x929920],  # 통신 플레이어/맵 송수신 UI
             [0x961F30, 0x9625A8],
             [0x99A7D4, 0x99AE50],
             [0x9D3078, 0x9D36F0],
             [0x805AE0, 0x805B04],  # 공통 복제본: 통신 대전 라벨
         ])),
    dict(id="14_part1_name_input", scope="part1", subtag="이름 입력",
         title="1편 이름 입력", canvas="40_part1_name_menu",
         sprite_ids=["lz77_00C102A8"], sprite=[],
         dialogue=dict(regions=["part1", "other"], addr_ranges=[
             [0xD8273C, 0xD82748],  # 이름 확인 예/아니오
             [0xD83198, 0xD83254],  # 이름 입력 문자표
             [0xD835BC, 0xD835D0],  # 예/아니오
             [0xDF8C3A, 0xDF96B0],  # 이름 입력 문자표/최초 이름 대사
             [0xDF9F5C, 0xDFA100],  # 이름 입력 문자표 잔여/확장 테이블
             [0x805A24, 0x805AE0],  # 공통 복제본: 문자표
             [0x83FAF6, 0x840000],  # 별도 이름 입력 문자표
         ])),
    dict(id="15_part1_operation_logos", scope="part1", subtag="작전/설정",
         title="1편 작전/지도/상점/룰 화면 로고", canvas=None, screenshot="41_part1_operation_room",
         sprite_ids=["lz77_00C18CB4", "lz77_00C18F48", "lz77_00C191E0", "lz77_00C194D8",
                     "lz77_00C19A9C", "lz77_00C19D14", "lz77_00C19FF0"],
         sprite=[],
         dialogue=dict(regions=["part1", "other"], addr_ranges=[
             [0x8059C4, 0x805A24],  # 공통 복제본: 룰/정찰/날씨 설정 표
             [0xDFAE9E, 0xDFD5E0],  # 워즈 숍/작전실 보상 안내
         ])),
    dict(id="16_part1_info_screen", scope="part1", subtag="유닛 정보",
         title="1편 유닛/상세 정보 화면", canvas=None,
         screenshot="32_battle_continue",
         sprite=["part1_info_screen", "part1_full_info_spec", "part1_check_label",
                 "info_screen_bg_labels", "full_info_spec"],
         dialogue=dict(regions=["part1", "other"], addr_ranges=[
             [0xD82978, 0xD83198],  # 국가/CO/유닛/지형/룰 표
             [0xDF8BBA, 0xDF8C3A],  # 유닛/획득/종합 등 정보 라벨
             [0x805204, 0x8059C4],  # 공통 복제본: 국가/유닛/지형/룰 표
         ])),
    dict(id="17_part1_campaign", scope="part1", subtag="캠페인",
         title="1편 캠페인/미션 로고", canvas=None, screenshot="20_mode_select_menu",
         sprite_ids=["lz77_00C18738", "lz77_00C19794"], sprite=[],
         dialogue=dict(regions=["part1", "other"], addr_ranges=[
             [0xD82748, 0xD82978],  # 1편 미션명/캠페인 관련 테이블
             [0x805104, 0x805204],  # 공통 복제본: 1편 미션명 테이블
         ])),
    dict(id="18_part1_battle", scope="part1", subtag="전투",
         title="1편 전투 N일째 배너", canvas=None, screenshot="30_battle_attack",
         sprite_ids=["lz77_00EE5E14"], sprite=[],
         dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDF2932, 0xDF2D00],  # 저장/항복/전투 애니/생산 제한 UI
         ])),
    dict(id="19a_part1_tutorial_story", scope="part1", subtag="대사",
         title="1편 튜토리얼/초반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xD8F000, 0xD98000],
         ])),
    dict(id="19b_part1_campaign_story_redstar", scope="part1", subtag="대사",
         title="1편 레드스타 캠페인 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xD98000, 0xDA5000],
         ])),
    dict(id="19c_part1_campaign_story_mid", scope="part1", subtag="대사",
         title="1편 중반 캠페인 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDC2900, 0xDCA000],
         ])),
    dict(id="19d_part1_campaign_story_late", scope="part1", subtag="대사",
         title="1편 후반 캠페인 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDCA000, 0xDD2000],
         ])),
    dict(id="19e_part1_unit_story_help", scope="part1", subtag="대사",
         title="1편 유닛/작전 설명 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDE9000, 0xDF0000],
             [0xDF0000, 0xDF8000],
         ])),
    dict(id="19f_part1_extra_story", scope="part1", subtag="대사",
         title="1편 추가/더미 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDFF000, 0xDFFC00],
         ])),

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
    dict(id="21a_part2_prologue_story", scope="part2", subtag="인트로",
         title="2편 프롤로그 지도/호크 대사", canvas=None, screenshot="08_part2_prologue_map_text",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA01970, 0xA01C00],  # 프롤로그 나레이션/헬보우즈/호크
         ])),
    dict(id="22_part2_title", scope="part2", subtag="시작화면",
         title="2편 타이틀", canvas="06_part2_title",
         sprite=["PART2_TITLE_OBJ", "part2_title"],
         dialogue=dict(regions=["other"], addr_ranges=[
             [0x816E1C, 0x816E40],  # 어드밴스 2 타이틀 라벨
         ])),
    dict(id="23_part2_main_menu", scope="part2", subtag="메뉴 선택",
         title="2편 메인 메뉴(모드 선택)", canvas="07_part2_main_menu",
         sprite=["part2_mode_menu", "mode_menu_obj"],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA2C000, 0xA2D000],  # 메인 메뉴/설정 설명
         ])),
    dict(id="23a_part2_shop_sound_comm", scope="part2", subtag="메뉴 선택",
         title="2편 상점/사운드/통신 메뉴", canvas=None, screenshot="07_part2_main_menu",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA2D8B8, 0xA2FE70],  # 워즈 숍/해금/구매 메시지
             [0xA34F2C, 0xA35758],  # 2편 통신 맵전송 + 메뉴 설명/사운드룸
         ])),
    dict(id="24_part2_campaign_map", scope="part2", subtag="캠페인 선택",
         title="2편 캠페인/작전 선택(월드맵)", canvas="20_mode_select_menu",
         sprite_ids=["lz77_00541BB8", "lz77_0054214C", "lz77_00547188", "lz77_005488A0",
                     "lz77_005AAA68"],
         sprite=[],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA2D000, 0xA2D8B8],  # 트라이얼/캠페인/프리 배틀 맵명
             [0xA35758, 0xA35800],  # 월드맵 영토 라벨
         ])),
    dict(id="24a_part2_operation_select", scope="part2", subtag="캠페인 선택",
         title="2편 작전 선택/출격 화면", canvas=None, screenshot="10_part2_region_map_redstar",
         sprite_ids=["lz77_00BF66F0", "lz77_005A38D4", "lz77_005AF674"],
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA34080, 0xA34B6C],  # 작전별 승리 조건/브리핑
         ])),
    dict(id="24b_part2_strategic_map_mode4", scope="part2", subtag="전략지도",
         title="2편 전략지도 Mode4 지명 라벨", canvas=None, screenshot="10_part2_region_map_redstar",
         sprite_ids=["lz77_00C2FD70", "lz77_00C30EE8"],
         sprite=[], dialogue=dict(regions=[]),
         related_dialogue_scene_ids=["21a_part2_prologue_story", "24a_part2_operation_select"]),
    dict(id="25_part2_mission_titles", scope="part2", subtag="미션 진입",
         title="2편 에어 미션 타이틀", canvas=None, screenshot="32_battle_continue",
         sprite_ids=["lz77_00C11D9C", "lz77_00C1205C"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="26a_part2_battle_start_overlays", scope="part2", subtag="전투",
         title="2편 전투 시작 회전/개시 오버레이", canvas=None, screenshot="32_battle_continue",
         sprite_ids=["lz77_00C10B34", "lz77_0045EC74", "lz77_0092DF84", "lz77_0092EB5C",
                     "lz77_00966C0C", "lz77_009677E4", "lz77_0099F4B0", "lz77_009A0088",
                     "lz77_009D7D54", "lz77_009D892C"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="26_part2_battle_labels", scope="part2", subtag="전투",
         title="2편 전투 라벨(체크·데미지 예측)", canvas="30_battle_attack",
         sprite_ids=["lz77_0045FCC8", "lz77_00BD4FBC"],
         sprite=[],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA30164, 0xA31444],  # 전투/브레이크/CO 대사
             [0xA34B6C, 0xA34F2C],  # 저장/항복/전투 옵션/맵 이름 UI
             [0xA3B880, 0xA3B900],  # CO 파워명 압축 테이블
         ])),
    dict(id="27_part2_battle_objlabels", scope="part2", subtag="전투",
         title="2편 전투 OBJ 라벨(행동·유닛·지형·상태)", canvas=None, screenshot="31_battle_dialog",
         sprite_ids=["objlabel_p2_terrain_status", "objlabel_p2_terrain_compact",
                     "objlabel_p2_unit_status", "objlabel_p2_unit_compact",
                     "objlabel_p2_co_banner", "objlabel_p2_status_header",
                     "objlabel_p2_info_screen", "objlabel_p2_action_menu"],
         sprite=[],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA31444, 0xA34080],  # 유닛/무기/지형 상세 설명
         ])),
    dict(id="28_part2_result_status", scope="part2", subtag="결과",
         title="2편 결과 성공/실패 오버레이", canvas=None, screenshot="33_battle_transport",
         sprite_ids=["lz77_00930520", "lz77_009691A8", "lz77_009A1A4C", "lz77_009DA2F0",
                     "lz77_00BFBB54", "lz77_00EE8A64", "lz77_00EE8F68"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="29_part2_result_summary", scope="part2", subtag="결과",
         title="2편 결과 요약/축하", canvas=None, screenshot="33_battle_transport",
         sprite_ids=["lz77_0059DA5C", "lz77_00BFB45C"], sprite=[],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA2FE70, 0xA30164],  # 전투 결과/승리 코멘트
         ])),
    dict(id="30a_part2_story_opening_redstar", scope="part2", subtag="대사",
         title="2편 초반/레드스타 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA01C00, 0xA08000],
         ])),
    dict(id="30b_part2_story_bluemoon", scope="part2", subtag="대사",
         title="2편 블루문/초중반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA08000, 0xA10000],
         ])),
    dict(id="30c_part2_story_yellow_comet", scope="part2", subtag="대사",
         title="2편 옐로코멧/중반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA10000, 0xA18000],
         ])),
    dict(id="30d_part2_story_green_earth", scope="part2", subtag="대사",
         title="2편 그린어스 전반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA18000, 0xA1C000],
         ])),
    dict(id="30g_part2_story_green_earth_late", scope="part2", subtag="대사",
         title="2편 그린어스 후반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA1C000, 0xA20000],
         ])),
    dict(id="30e_part2_story_blackhole_late", scope="part2", subtag="대사",
         title="2편 블랙홀 후반 스토리 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA20000, 0xA28000],
         ])),
    dict(id="30f_part2_story_final_and_co", scope="part2", subtag="대사",
         title="2편 최종전/CO 설명 대사", canvas=None, screenshot="31_battle_dialog",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA28000, 0xA2C000],
         ])),

    # ── 캠페인/공통 대사 ──
    dict(id="80a_campaign_story_early", scope="part2", subtag="대사",
         title="캠페인 초반 루트 대사", canvas=None, screenshot="20_mode_select_menu",
         sprite=[], dialogue=dict(regions=["campaign"], addr_ranges=[
             [0xE00100, 0xE05000],
         ])),
    dict(id="80b_campaign_story_mid", scope="part2", subtag="대사",
         title="캠페인 중반 루트 대사", canvas=None, screenshot="20_mode_select_menu",
         sprite=[], dialogue=dict(regions=["campaign"], addr_ranges=[
             [0xE05000, 0xE0A000],
         ])),
    dict(id="80c_campaign_story_late", scope="part2", subtag="대사",
         title="캠페인 후반/랭크 안내 대사", canvas=None, screenshot="20_mode_select_menu",
         sprite=[], dialogue=dict(regions=["campaign"], addr_ranges=[
             [0xE0A000, 0xE11300],
         ])),
    dict(id="85_ui_common", scope="all", subtag="UI/공통",
         title="공통 UI 라벨/대사", canvas=None, screenshot="02_common_title",
         sprite=["patch_block", "check_label"],
         dialogue=dict(regions=["ui"], addr_ranges=[
             [0x942000, 0x942CE0], [0x9450BC, 0x945600],
             [0x979700, 0x97B190], [0x97D8D8, 0x97DE20],
             [0x9B1F00, 0x9B3A30], [0x9B617C, 0x9B66C0],
             [0x9EA800, 0x9EC2D0], [0x9EEA20, 0x9EEF60],
         ])),
    dict(id="86_common_compact_menu_tables", scope="all", subtag="UI/공통",
         title="공통 압축 메뉴/선택 라벨 테이블", canvas=None, screenshot="02_common_title",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0x804FC8, 0x805B70],  # 시작/모드/맵 디자인/통신 공통 압축 라벨
         ])),
    dict(id="87_common_rule_settings", scope="all", subtag="설정",
         title="공통 룰/환경 설정 설명", canvas=None, screenshot="42_part1_single_battle",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xBE701C, 0xBE7030],  # 거점 전멸/불참 설정 라벨
             [0xEC30A2, 0xEC33C0],  # 정찰/날씨/수입/승리조건/애니 설정 설명
         ])),
    dict(id="88_common_comm_labels", scope="all", subtag="통신",
         title="공통 통신/플레이어 라벨", canvas=None, screenshot="43_part1_link",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xEE212C, 0xEE2848],  # 거리/국가/플레이어/통신 메시지 라벨
         ])),
    dict(id="89_common_battle_system_results", scope="all", subtag="전투",
         title="공통 전투 시스템/항복/패배 메시지", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xEFAAD4, 0xEFDE00],  # 전투 메뉴/항복 확인/패배/통신 오류
         ])),
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


def _is_unassigned_graphic(sp):
    """미배정 review에서 '텍스트 스프라이트 누락'으로 세면 안 되는 그래픽 블록.

    scan_lz77는 기본 미분류 그래픽이고, Mode4 프레임버퍼 LZ77은 4bpp 타일 에디터로 열면
    잘못된 편집면이 되므로 별도 지원 전까지 텍스트 후보에서 제외한다.
    """
    src = (sp.get("source") or "").lower()
    return src.startswith("scan_lz77") or "mode4" in src


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

    # scene 정의의 sprite_ids 순서는 LNB 노출 순서이기도 하다. 스프라이트 인덱스 파일
    # 순서로 재정렬되면 실제 활성 라벨보다 비활성/제거 소스가 먼저 보여 혼동된다.
    for sc in scenes:
        for sid in sc.get("sprite_ids", []) or []:
            add_unique(sc["id"], sid)

    for sp in sprites:
        src = (sp.get("source") or "")
        sid = sp.get("id")
        if not sid or sid in seen_sprites:
            continue
        seen_sprites.add(sid)
        section = sprite_section(src)
        if sid in explicit:
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


def expand_virtual_sprites(sprites):
    """같은 ROM 블록의 화면상 부분 편집 항목을 별도 sprite id로 노출한다."""
    base = next((s for s in sprites if s.get("id") == SELECT_OBJ_ID), None)
    out = [s for s in sprites if s.get("id") != SELECT_OBJ_ID]
    if not base:
        return out
    for sid, (variant, desc) in SELECT_VIRTUAL_META.items():
        sp = dict(base)
        sp.update({
            "id": sid,
            "base_id": SELECT_OBJ_ID,
            "layout_variant": variant,
            "desc_override": desc,
            "source": f"{base.get('source') or ''}:{variant}",
        })
        out.append(sp)
    return out


def assign_dialogue(scenes, groups):
    """region + addr_range 첫 매칭 scene에 group_id 배정.

    순서가 중요하다.
    1) 주소 range가 있는 구체 scene 먼저 매칭한다.
    2) 광역 bucket에 들어가면 화면 연결을 망치는 추출 노이즈/빌드 제외 후보를 review로 뺀다.
    3) 남은 실제 대사만 part1/part2/campaign/other 광역 bucket에 매칭한다.
    """
    guards = _load_build_guards()
    bucket = {sc["id"]: [] for sc in scenes}
    review_only = []
    unassigned = []
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
        if region == "font":
            continue

        hit = None
        for sc in scenes:
            if _dialogue_matches(sc, region, addr, specific_only=True):
                hit = sc["id"]
                break
        if hit:
            bucket[hit].append(g.get("group_id"))
            continue

        if _review_only_dialogue(g, guards):
            review_only.append(g.get("group_id"))
            continue

        for sc in scenes:
            if _dialogue_matches(sc, region, addr, specific_only=False):
                hit = sc["id"]
                break
        if hit:
            bucket[hit].append(g.get("group_id"))
        else:
            unassigned.append(g.get("group_id"))
    return bucket, unassigned, review_only


def main():
    chk = load(CHK, {"checkpoints": []})
    chk_ids = {c["name"] for c in chk.get("checkpoints", [])}
    chk_by_id = {c["name"]: c for c in chk.get("checkpoints", [])}
    spr = load(SPR, {"sprites": []}).get("sprites", [])
    obj = (load(OBJ, {}) or {}).get("sprites", []) or []
    sprites = expand_virtual_sprites(list(spr) + list(obj))
    groups = load(DGRP, {"groups": []}).get("groups", [])
    ov = load(OVERRIDES, {}) or {}

    scenes = [dict(s) for s in SCENES]
    sp_bucket, sp_un = assign_sprites(scenes, sprites)
    dl_bucket, dl_un, dl_review = assign_dialogue(scenes, groups)

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
            if x in dl_review:
                dl_review.remove(x)
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
        out_scene = {
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
        }
        if sc.get("related_dialogue_scene_ids"):
            out_scene["related_dialogue_scene_ids"] = sc["related_dialogue_scene_ids"]
        out_scenes.append(out_scene)

    out_scenes.append({
        "id": NOISE_REVIEW_SCENE_ID, "order": 9980, "scope": "review",
        "subtag": "검토", "title": "추출 노이즈/빌드 제외 대사(편집 제외)",
        "canvas": None, "canvas_status": "none",
        "checkpoint": None, "checkpoint_exists": False,
        "screenshot": {"checkpoint": None, "url": None, "mode": None, "grade": "not_a_scene",
                       "status": "not_a_scene",
                       "note": "코드/그래픽/보호 테이블에서 잡힌 문자열 후보. 실제 화면 대사로 연결하지 않음."},
        "dialogue_filter": {}, "sprite_filter": {},
        "dialogue_ids": dl_review, "sprite_ids": [],
        "counts": {"dialogue": len(dl_review), "sprite": 0},
    })

    # 미배정 review scene(누락 0 보증)
    sprites_by_id = {sp.get("id"): sp for sp in sprites}
    review_scan = sum(1 for sid in sp_un if _is_unassigned_graphic(sprites_by_id.get(sid, {})))
    review_font = sum(1 for sid in sp_un if sprites_by_id.get(sid, {}).get("type") == "font")
    review_text_candidate = max(0, len(sp_un) - review_scan - review_font)
    out_scenes.append({
        "id": "99_unassigned_review", "order": 9990, "scope": "all",
        "subtag": "미배정", "title": "미배정(검토 필요) — 규칙 미매칭",
        "canvas": None, "canvas_status": "none",
        "checkpoint": None, "checkpoint_exists": False,
        "screenshot": {"checkpoint": None, "url": None, "mode": None, "grade": "not_a_scene",
                       "status": "not_a_scene", "note": "미배정 검토 bucket"},
        "dialogue_filter": {}, "sprite_filter": {},
        "dialogue_ids": dl_un, "sprite_ids": sp_un,
        "counts": {"dialogue": len(dl_un), "sprite": len(sp_un),
                   "sprite_text_candidate": review_text_candidate,
                   "sprite_scan_lz77": review_scan, "sprite_font": review_font},
    })

    # 비텍스트 스캔 스프라이트는 review 안에서 별도 표시용 카운트
    scan_un = review_scan

    assigned_dl = sum(len(v) for v in dl_bucket.values()) + len(dl_review)
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
            "sprites_unassigned_text_candidate": review_text_candidate,
            "sprites_unassigned_font": review_font,
            "dialogue_groups_total": total_dl_groups, "dialogue_assigned": assigned_dl,
            "dialogue_review_only": len(dl_review), "dialogue_unassigned": len(dl_un),
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
