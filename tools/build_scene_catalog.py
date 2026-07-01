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
  - 실제 검토가 필요한 미배정 텍스트 후보와 비텍스트/폰트 제외 완료 대상을 분리한다.
    제외 완료 대상도 증거 카운트로 남기되, UI에서 "검토 필요"로 보이지 않게 한다.
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
ENTRYPOINTS = ROOT / "data" / "scene_entrypoints.json"
SPR = ROOT / "data" / "sprites_index.json"
OBJ = ROOT / "data" / "objlabel_sprites.json"
DGRP = ROOT / "data" / "dialogue_groups.json"
OVERRIDES = ROOT / "data" / "scene_catalog_overrides.json"
OUT = ROOT / "data" / "scene_catalog.json"
SCENE_SHOT_DIR = ROOT / "temp" / "scene_screenshots"

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
LOW_CONFIDENCE_OTHER_REVIEW_RANGES = [
    # These ranges are used only after every explicit scene addr_range misses.
    # They are extraction-noise/data banks that otherwise fall into the
    # catch-all "other" region and look editable despite having no screen
    # evidence. Keep them in review instead of pretending they belong to a scene.
    ("low_code_data_sjis_false_positive", 0x800000, 0x800900),
    ("unmapped_graphic_false_text_89xx", 0x89BB00, 0x8ABE20),
    ("save_or_binary_false_text_bx", 0xB7F800, 0xB7F900),
    ("unmapped_binary_false_text_bf", 0xBF2800, 0xBF2840),
    ("part1_pre_dialogue_false_text", 0xD64000, 0xD7D000),
    ("post_campaign_false_text_e8", 0xE77000, 0xE8BF00),
    ("pre_result_false_text_ef", 0xEF9200, 0xEFA300),
]
LOW_CONFIDENCE_UI_REVIEW_RANGES = [
    # UI region false positives that are repeated mirrored symbol/table banks.
    # These rows have no KO text and are not actual menu labels; keep them out
    # of game scenes without restoring the old broad "short blank UI" rule.
    ("ui_symbol_bank_93c", 0x93C8D7, 0x93DA14),
    ("ui_symbol_bank_940", 0x940C62, 0x941D5E),
    ("ui_symbol_bank_94f", 0x94FE33, 0x94FE35),
    ("ui_symbol_bank_974", 0x974D8B, 0x975EC8),
    ("ui_symbol_bank_979", 0x979116, 0x9795EA),
    ("ui_symbol_bank_988", 0x9886D7, 0x9886D9),
    ("ui_symbol_bank_9ad", 0x9AD62F, 0x9AE76C),
    ("ui_symbol_bank_9b1", 0x9B19BA, 0x9B1E8E),
    ("ui_symbol_bank_9c0", 0x9C0F7B, 0x9C0F7D),
    ("ui_symbol_bank_9e5", 0x9E5ED3, 0x9E7010),
    ("ui_symbol_bank_9ea", 0x9EA25E, 0x9EA732),
    ("ui_link_false_text_9293", 0x929300, 0x929310),
    ("ui_link_false_text_961f", 0x961F88, 0x961F98),
    ("ui_link_false_text_99a8", 0x99A82C, 0x99A83C),
    ("ui_link_false_text_9d30", 0x9D30D0, 0x9D30E0),
    ("ui_common_false_table_9420", 0x942000, 0x942130),
    ("ui_common_false_table_9422", 0x942200, 0x942610),
    ("ui_common_false_table_9797", 0x979780, 0x97A220),
    ("ui_common_false_table_97a4", 0x97A4C0, 0x97A5C0),
    ("ui_common_false_table_97a6", 0x97A6B0, 0x97AAA0),
    ("ui_common_false_table_9b20", 0x9B2020, 0x9B2AC0),
    ("ui_common_false_table_9b2d", 0x9B2D60, 0x9B2E60),
    ("ui_common_false_table_9b2f", 0x9B2F50, 0x9B3340),
    ("ui_common_false_table_9ea8", 0x9EA8C0, 0x9EB360),
    ("ui_common_false_table_9eb6", 0x9EB600, 0x9EB700),
    ("ui_common_false_table_9eb8", 0x9EB7F0, 0x9EBC00),
]

# These scene IDs are address buckets, not independently reproducible screens.
# Their dialogue remains editable, but the editor/audits must not attach a
# child scene's screenshot to them as if it were a unique game frame.
CONTAINER_SCENE_REASONS = {
    "19a_part1_tutorial_story": "1편 튜토리얼/초반 스토리 주소묶음. 실제 화면은 19a* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "19b_part1_campaign_story_redstar": "1편 레드스타 캠페인 주소묶음. 실제 화면은 19b* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "19c_part1_campaign_story_mid": "1편 중반 캠페인 주소묶음. 실제 화면은 19c* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "19d_part1_campaign_story_late": "1편 후반 캠페인 주소묶음. 현재 별도 화면 hit가 없고 residual scan hit 0이다.",
    "19e_part1_unit_story_help": "1편 유닛/작전 설명 주소묶음. 실제 화면은 19e* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30a_part2_story_opening_redstar": "2편 레드스타 초반 주소묶음. 실제 화면은 30a* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30b_part2_story_bluemoon": "2편 블루문/초중반 주소묶음. 실제 화면은 30b* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30c_part2_story_yellow_comet": "2편 옐로코멧/중반 주소묶음. 실제 화면은 30c* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30d_part2_story_green_earth": "2편 그린어스 전반 주소묶음. 실제 화면은 30d* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30e_part2_story_blackhole_late": "2편 블랙홀 후반 주소묶음. 실제 화면은 30e* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30f_part2_story_final_and_co": "2편 최종전/CO 설명 주소묶음. 실제 화면은 30f* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "30g_part2_story_green_earth_late": "2편 그린어스 후반 주소묶음. 실제 화면은 30g* split scene으로 캡처했고, 현재 parent residual scan hit 0이다.",
    "23d_part2_b8_compact_display_tables": "2편 B8 압축 표시문 주소묶음. 유닛/무기/상점/CO/브레이크 라벨은 여러 화면에서 참조되지만 이 주소 테이블 자체는 독립 프레임이 아니며 현재 residual scan hit 0이다.",
    "88_common_comm_labels": "공통 통신 라벨 데이터 주소묶음. 독립 실화면 캡처 대상이 아니며, 현재 menu/focus residual scan hit 0이다.",
    "89a_common_battle_surrender_confirm_common_copies": "항복 확인 공통 복제본 주소묶음. 3P free-battle 실화면은 89a의 Part2 복제본(0xA34CB0)을 읽으며, 이 공통 copy는 현재 residual scan hit 0이다.",
    "89b_common_battle_defeat_comm_messages_common_copies": "전투 패배/통신 오류 공통 복제본 주소묶음. 3P free-battle 항복 패배 실화면은 89b의 Part2 복제본(0xA34D18)을 읽으며, 이 공통/통신 오류 copy는 현재 residual scan hit 0이다.",
}

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


def _rel(path):
    if not path:
        return None
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def checkpoint_capture_path(checkpoint):
    if not checkpoint:
        return None
    return _rel(SCENE_SHOT_DIR / f"{checkpoint}_patched" / "frame.png")


def checkpoint_provenance_path(shot, entrypoint=None):
    if entrypoint and entrypoint.get("source_state"):
        return entrypoint.get("source_state")
    if shot and shot.get("state"):
        return shot.get("state")
    return _rel(CHK)


def preview_canvas_keys():
    return _load_preview_registry()[0]


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def load_scene_entrypoints():
    """장면별 실화면 캡처/진입점 보정.

    SCENES 안의 screenshot 값은 오래된 기본값으로 남겨두고, 실제 QA에서 확인한
    화면별 고유 체크포인트는 data/scene_entrypoints.json을 정본으로 사용한다.
    """
    raw = load(ENTRYPOINTS, {}) or {}
    scenes = raw.get("scenes") or {}
    return scenes if isinstance(scenes, dict) else {}


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
            "in_deny": getattr(B, "in_deny", None),
        }
    except Exception:
        return {"slots": {}, "deny": [], "pair": [], "in_deny": None}


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
    slot = (guards.get("slots") or {}).get(addr)
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
    in_deny = guards.get("in_deny")
    if callable(in_deny) and in_deny(addr, hi):
        return "deny"
    if _range_overlap(addr, hi, guards["deny"]):
        return "deny"
    if _range_overlap(addr, hi, guards["pair"]):
        return "pair"
    return "writable"


def _low_confidence_other_review_reason(addr):
    for name, lo, hi in LOW_CONFIDENCE_OTHER_REVIEW_RANGES:
        if lo <= addr < hi:
            return name
    return None


def _low_confidence_ui_review_reason(addr):
    for name, lo, hi in LOW_CONFIDENCE_UI_REVIEW_RANGES:
        if lo <= addr < hi:
            return name
    return None


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


EDITOR_VISIBLE_FONT_DIALOGUE_RANGES = [
    # 0xB8 high-byte region is mostly font/name-grid adjacent data, but this
    # proven display span contains Part2 unit/weapon names, break quotes, shop
    # unlock/map labels, CO names, CO power names, and army labels.
    (0xB81800, 0xB85000),
]
GLYPH_DICTIONARY_TEXT_ADDRS = {
    # Compact CO power renderers consume these rows as two-byte glyph dictionaries,
    # not as display strings. build_dialogue_map excludes them; keep scene
    # catalog/editor visibility in lockstep.
    0xA3B880,
    0xB842E8,
}


def _editor_visible_font_dialogue(addr):
    if addr is None:
        return False
    if addr in GLYPH_DICTIONARY_TEXT_ADDRS:
        return False
    return any(start <= addr < end for start, end in EDITOR_VISIBLE_FONT_DIALOGUE_RANGES)


def _review_only_dialogue(group, guards):
    """광역 scene으로 흘러가면 오해를 만드는 추출 노이즈/빌드 제외 후보."""
    members = group.get("members") or []
    if not members:
        return True
    region = group.get("region")
    if region == "font" and not _editor_visible_font_dialogue(_member_addr_slot(members[0], guards)[0]):
        return True

    statuses = [_member_build_status(m, guards) for m in members]
    if statuses and all(s in {"under_safe_min", "no_slot"} for s in statuses):
        return True
    if statuses and all(s in {"deny", "pair", "no_slot"} for s in statuses):
        return True

    addr, _slot = _member_addr_slot(members[0], guards)
    if region == "other" and _low_confidence_other_review_reason(addr):
        return True

    ja = (group.get("assembled_ja") or "").strip()
    ko = (group.get("assembled_ko") or "").strip()
    if not ko:
        ko = "".join((m.get("ko") or "") for m in members).strip()
    if not ja:
        return True

    if region == "ui" and not ko and _low_confidence_ui_review_reason(addr):
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
    if region == "other" and not ko and (len(ja) <= 8 or mojibake):
        return True
    if region == "ui" and not ko and mojibake:
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
             [0x9292A0, 0x929920],  # 통신 플레이어/맵 송수신 UI
             [0x961F28, 0x9625A8],
             [0x99A7CC, 0x99AE50],
             [0x9D3070, 0x9D36F0],
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
             [0xD8C540, 0xD8C560],  # 전 보급 중 직접 패치 메시지
             [0xDF2932, 0xDF2D00],  # 저장/항복/전투 애니/생산 제한 UI
         ])),
    dict(id="19a_part1_tutorial_story", scope="part1", subtag="대사",
         title="1편 튜토리얼/초반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xD8F000, 0xD98000],
         ])),
    dict(id="19b_part1_campaign_story_redstar", scope="part1", subtag="대사",
         title="1편 레드스타 캠페인 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xD98000, 0xDA5000],
         ])),
    dict(id="19c_part1_campaign_story_mid", scope="part1", subtag="대사",
         title="1편 중반 캠페인 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDC2900, 0xDCA000],
         ])),
    dict(id="19d_part1_campaign_story_late", scope="part1", subtag="대사",
         title="1편 후반 캠페인 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part1"], addr_ranges=[
             [0xDCA000, 0xDD2000],
         ])),
    dict(id="19e_part1_unit_story_help", scope="part1", subtag="대사",
         title="1편 유닛/작전 설명 대사", canvas=None,
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
         title="2편 진입 스플래시 로고", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_004D8AF8"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="20a_part2_menu_newspaper_bg", scope="part2", subtag="인트로",
         title="2편 메뉴 신문 배경", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_005B5D10"], sprite=[],
         dialogue=dict(regions=[])),
    dict(id="21_part2_intro_blackhole", scope="part2", subtag="인트로",
         title="2편 인트로 블랙홀/도미노/프롤로그", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_004E0478", "lz77_005BBB3C"],
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
    dict(id="23a_part2_wars_shop", scope="part2", subtag="메뉴 선택",
         title="2편 워즈 숍/해금 상점", canvas=None, screenshot="07_part2_main_menu",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA2D8B8, 0xA2FE70],  # 워즈 숍/해금/구매 메시지
         ])),
    dict(id="23d_part2_b8_compact_display_tables", scope="part2", subtag="메뉴 선택",
         title="2편 B8 압축 표시문(유닛·상점·CO·브레이크 라벨)", canvas=None, screenshot="07_part2_main_menu",
         sprite=[], dialogue=dict(regions=["font"], addr_ranges=[
             [0xB81800, 0xB85000],  # B8 표시 문자열 테이블: 유닛/상점/CO/브레이크 라벨
         ])),
    dict(id="23b_part2_comm_multiplayer", scope="part2", subtag="메뉴 선택",
         title="2편 통신 메뉴/맵 교환", canvas=None, screenshot="07_part2_main_menu",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA34F2C, 0xA352B4],  # 2편 통신 준비/맵전송/멀티팩 설명
         ])),
    dict(id="23c_part2_sound_room", scope="part2", subtag="메뉴 선택",
         title="2편 사운드룸 트랙 목록", canvas=None, screenshot="07_part2_main_menu",
         sprite_ids=["lz77_00519B90"],
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA352B4, 0xA35758],  # 사운드룸 트랙 목록
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
         sprite_ids=["lz77_00C10B34"],
         sprite=[], dialogue=dict(regions=[])),
    dict(id="26_part2_battle_labels", scope="part2", subtag="전투",
         title="2편 전투 라벨(체크·데미지 예측)", canvas="30_battle_attack",
         sprite_ids=["lz77_0045FCC8", "lz77_00BD4FBC"],
         sprite=[],
         dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA30164, 0xA31444],  # 전투/브레이크/CO 대사
             [0xA34B6C, 0xA34F2C],  # 저장/항복/전투 옵션/맵 이름 UI
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
         title="2편 초반/레드스타 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA01C00, 0xA08000],
         ])),
    dict(id="30b_part2_story_bluemoon", scope="part2", subtag="대사",
         title="2편 블루문/초중반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA08000, 0xA10000],
         ])),
    dict(id="30c_part2_story_yellow_comet", scope="part2", subtag="대사",
         title="2편 옐로코멧/중반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA10000, 0xA18000],
         ])),
    dict(id="30d_part2_story_green_earth", scope="part2", subtag="대사",
         title="2편 그린어스 전반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA18000, 0xA1C06C],
         ])),
    dict(id="30g_part2_story_green_earth_late", scope="part2", subtag="대사",
         title="2편 그린어스 후반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA1C06C, 0xA20000],
         ])),
    dict(id="30e_part2_story_blackhole_late", scope="part2", subtag="대사",
         title="2편 블랙홀 후반 스토리 대사", canvas=None,
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA20000, 0xA28000],
         ])),
    dict(id="30f_part2_story_final_and_co", scope="part2", subtag="대사",
         title="2편 최종전/CO 설명 대사", canvas=None,
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
         title="공통 전투 시스템 메뉴", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xEFAAD4, 0xEFAE20],  # 전투 메뉴/시스템 라벨/예·아니오
         ])),
    dict(id="89a_common_battle_surrender_confirm", scope="all", subtag="전투",
         title="공통 전투 항복 확인", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA34CB0, 0xA34CE8],  # 실제 3P free-battle 항복 확인 메시지 복제본
         ])),
    dict(id="89a_common_battle_surrender_confirm_common_copies", scope="all", subtag="전투",
         title="공통 전투 항복 확인 복제본(미검증)", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xEFDAA0, 0xEFDB00],  # 공통 항복 확인 메시지 copy; 별도 활성 화면 미확보
         ])),
    dict(id="89b_common_battle_defeat_comm_messages", scope="all", subtag="전투",
         title="공통 전투 패배/통신 오류 메시지", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["part2"], addr_ranges=[
             [0xA34D18, 0xA34DD0],  # 실제 3P free-battle 항복 패배 메시지 복제본
         ])),
    dict(id="89b_common_battle_defeat_comm_messages_common_copies", scope="all", subtag="전투",
         title="공통 전투 패배/통신 오류 메시지 복제본(미검증)", canvas=None, screenshot="30_battle_attack",
         sprite=[], dialogue=dict(regions=["other"], addr_ranges=[
             [0xEFD8A4, 0xEFDA00],  # 각 군 패배 메시지 copy; 별도 활성 화면 미확보
             [0xEFDDBD, 0xEFDE00],  # 통신 오류/리셋 메시지 copy; 별도 활성 화면 미확보
         ])),
]

STORY_SPLIT_SCENES = {
    "19a_part1_tutorial_story": [
        # part1_main_sweep/state_015 shows g_00D8F30E ("여기는 아라라 지방...").
        ("19a1_part1_tutorial_opening", "1편 튜토리얼 초반 대사", 0xD8F000, 0xD9219E),
        # AW1 GameFAQs 2113 front save exact-watch hits g_00D965DE
        # ("하지만, 전투는 정면승부만...") in the heavy-tank advice sequence.
        ("19a2_part1_heavy_tank_advice_story", "1편 중전차/정면승부 회피 조언 대사", 0xD9650F, 0xD96DAE),
    ],
    "19e_part1_unit_story_help": [
        # Direct verified unit-info help panel from first battle day-2 probe.
        ("19e1_part1_unit_info_detail_help", "1편 유닛 정보 상세 설명", 0xDECA12, 0xDEF5E1),
        # Exact watch from AW1 2111 front save hits g_00DF7452
        # ("오늘은 작전 전에 휩 사령관에 대해...") in the CO/weather help sequence.
        ("19e7_part1_hoip_co_weather_help", "1편 호이프/날씨/사령관 능력 설명", 0xDF7166, 0xDF75C0),
        # state_008/state_009 show g_00DF5D62/g_00DF5E12, both in this late help block.
        ("19e6_part1_unit_help_late", "1편 유닛/작전 설명 후반 대사", 0xDF55C3, 0xDF8000),
    ],
    "19b_part1_campaign_story_redstar": [
        # AW1 GameFAQs 11186 front save exact-watch hits g_00D9A26A
        # ("호이프 부대가 상륙하기 전...") in the early landing setup sequence.
        ("19b2_part1_hoip_landing_setup_story", "1편 호이프 상륙 전 안내 대사", 0xD9A26A, 0xD9A400),
        # AW1 GameFAQs 2111 front save exact-watch hits g_00D9CBCE
        # ("나쁜 예감이 들어요...") during the Olaf/Hoip ambush weather sequence.
        ("19b1_part1_hoip_ambush_weather_story", "1편 호이프 매복/날씨 브레이크 대사", 0xD9CBCE, 0xD9D5CE),
    ],
    "19c_part1_campaign_story_mid": [
        # Exact watch from 2112_front_a5/mode_up_base hits g_00DC2937
        # ("사령관님, 료! 들려요?") in the mid-campaign radio sequence.
        ("19c1_part1_mid_campaign_radio_story", "1편 중반 무전기/작전 대사", 0xDC2937, 0xDC3FDE),
        # Exact watch from 2111_front_a5/mode_up_base hits g_00DC4C02
        # ("색적 맵인가...") on the mid-campaign fog-of-war map.
        ("19c2_part1_mid_fog_map_story", "1편 중반 색적 맵 설명 대사", 0xDC4C02, 0xDC4E2E),
    ],
    "30a_part2_story_opening_redstar": [
        # part2_main_sweep first30 s011..s027 show A01C90/A01CA3 red-star opening dialogue.
        ("30a1_part2_redstar_story_early", "2편 레드스타 초반 스토리 대사 1", 0xA01C00, 0xA04C64),
    ],
    "30b_part2_story_bluemoon": [
        # Exact watch from 3285_off0f menu state hits g_00A0E398
        # ("캐서린한테서 호출이 있었다고...") in the post-Red-Star liberation briefing.
        # Static script boundary review keeps this scene through the next independent script at A0F1FC.
        ("30b1_part2_redstar_liberation_macro_briefing_story", "2편 레드스타 해방 후 매크로랜드 브리핑 대사", 0xA0E398, 0xA0F1FC),
    ],
    "30c_part2_story_yellow_comet": [
        # Exact watch from base_2821_010_1000/step_01 hits g_00A15240
        # ("우리나라 북방에 블랙홀 군이 나타났다고?") in the Yellow Comet north invasion flow.
        ("30c1_part2_yellowcomet_north_invasion_story", "2편 옐로코멧 북방 침공 대사", 0xA15240, 0xA1600C),
    ],
    "30d_part2_story_green_earth": [
        # step_32 shows g_00A1BF24 ("여기는 그린어스 아닌가?").
        ("30d2_part2_green_earth_story_late", "2편 그린어스 전반 스토리 대사 2", 0xA19F6C, 0xA1C06C),
    ],
    "30g_part2_story_green_earth_late": [
        # Pointer-table watch from 5719_off09000 hits table A36DA0 -> g_00A1C06C
        # ("모두, 힘내. 그린어스에서 원군이 와 줄 거야.") on the Green Earth
        # reinforcement/hold-out map dialogue before the volcano sortie block.
        ("30g0_part2_green_earth_reinforcement_story", "2편 그린어스 원군/버티기 대사", 0xA1C06C, 0xA1D244),
        # Exact watch from 8496_off0e map state hits g_00A1D244
        # ("호크, 콩이 와 있어.") in the volcano sortie sequence.
        ("30g1_part2_green_earth_volcano_sortie_story", "2편 그린어스 화산 출격 대사", 0xA1D244, 0xA1D550),
        # Same route exact-watch hits g_00A1D550; follow-up visual flow contains lava pattern
        # advice up to before the next unresolved late block at A1DF84.
        ("30g2_part2_green_earth_volcano_lava_story", "2편 그린어스 화산/용암 전술 대사", 0xA1D550, 0xA1DF84),
        # Exact watch from base_2821_010_1000/step_01 with route RIGHT,RIGHT,DOWN,DOWN,A,A
        # hits g_00A1FAD8 ("이 부근 상황은 어떤가, 아스카?") in the late Green Earth
        # suspicious-area briefing. Keep it through the last Green Earth late group before A200B4.
        ("30g3_part2_green_earth_suspicious_area_story", "2편 그린어스 후반 수상 지역 브리핑 대사", 0xA1FAD8, 0xA200B4),
    ],
    "30e_part2_story_blackhole_late": [
        # Breakscan R_D_015 logs reads from g_00A202D4 and final state shows the
        # Yellow Comet large-fortress/Snake briefing ("적의 대형 요새...").
        ("30e4_part2_blackhole_yellowcomet_fortress_story", "2편 블랙홀/옐로코멧 대형 요새 브리핑 대사", 0xA202D4, 0xA20F38),
        # Exact watch from base_2821_010_1000/step_01 with route LEFT,A,A hits g_00A20F38
        # ("현지에서 모은 물자는...") in the Yellow Comet/Snake supply briefing sequence.
        ("30e3_part2_blackhole_yellowcomet_supply_briefing_story", "2편 블랙홀/옐로코멧 보급 브리핑 대사", 0xA20F38, 0xA21559),
        # Exact watch from campaign_continue_matrix/5759 menu hits g_00A26D48
        # ("미사일 발사대는 완성됐나") at the start of the missile-base approach sequence.
        ("30e1_part2_blackhole_missile_approach_story", "2편 블랙홀 미사일 기지 접근 대사", 0xA26D48, 0xA27024),
        # Exact watch from campaign_continue_matrix/RIGHT/after_A hits g_00A27024
        # ("아스카만이 아니야...") in the final missile-base sequence.
        ("30e2_part2_blackhole_final_missile_story", "2편 블랙홀 최종 미사일 기지 후반 대사", 0xA27024, 0xA28000),
    ],
    "30f_part2_story_final_and_co": [
        # part2_menu_sweep/state_036 is a CO profile screen, not final battle dialogue.
        ("30f2_part2_co_profile_story", "2편 CO 설명/프로필 대사", 0xA29824, 0xA2C000),
    ],
}


def expand_story_split_scenes(scenes):
    """Insert narrower story scenes before broad buckets, preserving old IDs."""
    expanded = []
    for scene in scenes:
        splits = STORY_SPLIT_SCENES.get(scene["id"], [])
        for sid, title, start, end in splits:
            expanded.append({
                "id": sid,
                "scope": scene["scope"],
                "subtag": scene["subtag"],
                "title": title,
                "canvas": scene.get("canvas"),
                "screenshot": scene.get("screenshot"),
                "sprite": [],
                "dialogue": {
                    "regions": list(scene.get("dialogue", {}).get("regions", [])),
                    "addr_ranges": [[start, end]],
                },
            })
        if splits:
            scene = dict(scene)
            scene["related_dialogue_scene_ids"] = [sid for sid, *_ in splits]
        expanded.append(scene)
    return expanded

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
    빌드에서 일본어 원본을 빈칸 처리하는 제거/잔여 블록도 실제 편집 대상이 아니므로
    게임 scene의 누락 텍스트 후보로 세지 않는다.
    """
    src = (sp.get("source") or "").lower()
    removal_tokens = (
        "patch_part2_battle_start_day_overlay_obj",
        "patch_part2_domino_co_name_obj",
        "patch_part2_intro_campaign_residual_graphics",
    )
    return src.startswith("scan_lz77") or "mode4" in src or any(t in src for t in removal_tokens)


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
        if _is_unassigned_graphic(sp):
            unassigned.append(sid)
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
        if region == "font" and not _editor_visible_font_dialogue(addr):
            continue

        if _review_only_dialogue(g, guards):
            review_only.append(g.get("group_id"))
            continue

        hit = None
        for sc in scenes:
            if _dialogue_matches(sc, region, addr, specific_only=True):
                hit = sc["id"]
                break
        if hit:
            bucket[hit].append(g.get("group_id"))
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
    scene_entrypoints = load_scene_entrypoints()

    scenes = [dict(s) for s in expand_story_split_scenes(SCENES)]
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
        entrypoint = scene_entrypoints.get(sc["id"], {}) or {}
        container_reason = CONTAINER_SCENE_REASONS.get(sc["id"])
        is_container = bool(container_reason)
        # SCENES의 canvas= 는 기본 screen_checkpoint id, data/scene_entrypoints.json은
        # 실제 화면 검증으로 확정한 장면별 고유 진입점/캡처를 우선한다.
        if is_container:
            checkpoint = None
            checkpoint_exists = False
            shot_checkpoint = None
            screenshot = {"checkpoint": None, "url": None, "mode": None,
                          "grade": "not_a_scene", "status": "container",
                          "note": container_reason,
                          "capture_path": None, "provenance_path": None}
        else:
            checkpoint = entrypoint.get("checkpoint") or sc.get("canvas")
            checkpoint_exists = bool(checkpoint and checkpoint in chk_ids)
            shot_checkpoint = entrypoint.get("screenshot") or sc.get("screenshot") or checkpoint
            shot = chk_by_id.get(shot_checkpoint)
            if shot:
                shot_grade = shot.get("grade") or ("stale_state" if shot.get("stale_bg") else "ground_truth")
                screenshot = {"checkpoint": shot_checkpoint,
                              "url": f"/scene_shots/{shot_checkpoint}.png",
                              "mode": shot.get("mode"), "grade": shot_grade,
                              "status": "capturable", "note": shot.get("note", ""),
                              "capture_path": shot.get("capture_path") or checkpoint_capture_path(shot_checkpoint),
                              "provenance_path": shot.get("provenance_path") or checkpoint_provenance_path(shot, entrypoint)}
            else:
                screenshot = {"checkpoint": shot_checkpoint, "url": None, "mode": None,
                              "grade": "missing_checkpoint", "status": "missing_checkpoint", "note": "",
                              "capture_path": checkpoint_capture_path(shot_checkpoint),
                              "provenance_path": checkpoint_provenance_path(None, entrypoint)}
        # 실캡처 canvas = 레지스트리에서 checkpoint→canvas로 도출(지원 키만).
        preview = None if is_container else (pv_by_chk.get(checkpoint) or pv_by_chk.get(sc["id"]))
        if preview not in pv_keys:
            preview = None
        canvas_status = "ready" if preview else "none"
        out_scene = {
            "id": sc["id"], "order": order * 10, "scope": sc["scope"],
            "subtag": sc["subtag"], "title": sc["title"],
            "scene_role": "container" if is_container else "screen",
            "capture_required": not is_container,
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
        if entrypoint and not is_container:
            out_scene["entrypoint"] = entrypoint
        if sc.get("related_dialogue_scene_ids"):
            out_scene["related_dialogue_scene_ids"] = sc["related_dialogue_scene_ids"]
        out_scenes.append(out_scene)

    out_scenes.append({
        "id": NOISE_REVIEW_SCENE_ID, "order": 9980, "scope": "review",
        "subtag": "제외완료", "title": "저신뢰 추출 제외 완료(실대사 아님)",
        "scene_role": "excluded",
        "review_status": "resolved_excluded",
        "canvas": None, "canvas_status": "none",
        "checkpoint": None, "checkpoint_exists": False,
        "screenshot": {"checkpoint": None, "url": None, "mode": None, "grade": "not_a_scene",
                       "status": "excluded",
                       "note": "검증 완료: 코드/그래픽/보호 테이블/저신뢰 데이터 대역에서 잡힌 문자열 후보이며 실제 화면 대사로 연결하지 않는다."},
        "dialogue_filter": {}, "sprite_filter": {},
        "dialogue_ids": dl_review, "sprite_ids": [],
        "counts": {"dialogue": len(dl_review), "sprite": 0,
                   "excluded_low_confidence_dialogue": len(dl_review),
                   "pending_review": 0},
    })

    # 미배정 review scene(누락 0 보증)
    sprites_by_id = {sp.get("id"): sp for sp in sprites}
    review_scan = sum(1 for sid in sp_un if _is_unassigned_graphic(sprites_by_id.get(sid, {})))
    review_font = sum(1 for sid in sp_un if sprites_by_id.get(sid, {}).get("type") == "font")
    review_text_candidate = max(0, len(sp_un) - review_scan - review_font)
    pending_review = len(dl_un) + review_text_candidate
    out_scenes.append({
        "id": "99_unassigned_review", "order": 9990, "scope": "all",
        "subtag": "제외완료" if pending_review == 0 else "검토필요",
        "title": ("비텍스트/폰트 제외 완료 — 미배정 텍스트 0"
                  if pending_review == 0 else "미배정 검토 필요 — 텍스트 후보 있음"),
        "scene_role": "excluded" if pending_review == 0 else "review_pending",
        "review_status": "resolved_excluded" if pending_review == 0 else "pending",
        "canvas": None, "canvas_status": "none",
        "checkpoint": None, "checkpoint_exists": False,
        "screenshot": {"checkpoint": None, "url": None, "mode": None, "grade": "not_a_scene",
                       "status": "excluded" if pending_review == 0 else "review_pending",
                       "note": ("검증 완료: 미배정 텍스트 후보 0. 남은 항목은 비텍스트 scan_lz77 그래픽 또는 font 블록이라 장면 편집 대상이 아니다."
                                if pending_review == 0 else "미배정 텍스트 후보가 남아 있어 검토 필요.")},
        "dialogue_filter": {}, "sprite_filter": {},
        "dialogue_ids": dl_un, "sprite_ids": sp_un,
        "counts": {"dialogue": len(dl_un), "sprite": len(sp_un),
                   "sprite_text_candidate": review_text_candidate,
                   "sprite_scan_lz77": review_scan, "sprite_font": review_font,
                   "pending_review": pending_review,
                   "excluded_scan_lz77": review_scan,
                   "excluded_font": review_font},
    })

    # 비텍스트 스캔 스프라이트는 review 안에서 별도 표시용 카운트
    scan_un = review_scan

    game_scene_dl = sum(len(v) for v in dl_bucket.values())
    assigned_dl = game_scene_dl + len(dl_review)
    assigned_sp = sum(len(v) for v in sp_bucket.values())
    total_dl_groups = sum(
        1
        for g in groups
        if g.get("members")
        and (
            g.get("region") != "font"
            or _editor_visible_font_dialogue(
                _member_addr_slot((g.get("members") or [{}])[0], {})[0]
            )
        )
    )
    catalog = {
        "version": 1,
        "_doc": "게임 흐름순 scene 카탈로그(통합 UI 에디터 정본). tools/build_scene_catalog.py 생성. "
                "수동보정 data/scene_catalog_overrides.json. 실제 검토 필요 항목과 검증 완료 제외 항목을 분리한다.",
        "generated_from": {"checkpoints": str(CHK.relative_to(ROOT)),
                            "entrypoints": str(ENTRYPOINTS.relative_to(ROOT)),
                            "sprites": str(SPR.relative_to(ROOT)),
                            "dialogue": str(DGRP.relative_to(ROOT))},
        "scopes": ["all", "shared_select", "part1", "part2"],
        "coverage": {
            "sprites_total": len(sprites), "sprites_assigned": assigned_sp,
            "sprites_unassigned": len(sp_un), "sprites_unassigned_scan_lz77": scan_un,
            "sprites_unassigned_text_candidate": review_text_candidate,
            "sprites_unassigned_font": review_font,
            "sprites_excluded_scan_lz77": review_scan,
            "sprites_excluded_font": review_font,
            "review_pending_total": len(dl_un) + review_text_candidate,
            "dialogue_excluded_low_confidence": len(dl_review),
            "dialogue_groups_total": total_dl_groups,
            "dialogue_game_scene_assigned": game_scene_dl,
            "dialogue_assigned": assigned_dl,
            "dialogue_review_only": len(dl_review), "dialogue_unassigned": len(dl_un),
        },
        "scenes": out_scenes,
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"scene_catalog.json 생성: {len(out_scenes)} scenes → {OUT}")
    print(f"  스프라이트: {assigned_sp}/{len(sprites)} 배정, 검토필요 {review_text_candidate}, 제외 scan_lz77 {scan_un}/font {review_font}")
    print(f"  대사그룹:   {assigned_dl}/{total_dl_groups} 배정, 미배정 {len(dl_un)}, 저신뢰 제외 {len(dl_review)}")
    print("  scene별 count(게임순):")
    for sc in out_scenes:
        print(f"    {sc['id']:28s} [{sc['scope']:13s}|{sc['subtag']:8s}] "
              f"대사{sc['counts']['dialogue']:5d} 스프{sc['counts']['sprite']:4d} "
              f"canvas={sc['canvas_status']}")


if __name__ == "__main__":
    main()
