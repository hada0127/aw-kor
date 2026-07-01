#!/usr/bin/env python3
"""통합 화면(scene) 기반 에디터 — 단일 서버(stdlib http.server).

기존 대사 편집기(:8780)·스프라이트 편집기(:8781)를 게임 흐름(scene) 중심의 단일 도구로 통합.
정본 카탈로그 data/scene_catalog.json(tools/build_scene_catalog.py 생성)을 따라, 한 scene에
포함되는 대사·스프라이트를 한 화면에서 일괄 편집한다.

핵심: 기존 두 서버의 helper를 importlib로 재사용(중복 구현 0). 기존 서버는 그대로 유지.

실행:
  python3 tools/scene_editor/server.py            # http://127.0.0.1:8782

API(요약)
  GET  /api/state                         dirty/building/ROM sha·mtime/job
  GET  /api/scenes?scope=&tag=&q=          게임순 scene 목록(+counts)
  GET  /api/scene/items?id=&type=          scene 포함 대사 그룹 + 스프라이트
  GET  /api/dict                           통일 사전(대사)
  POST /api/dialogue/line  {id, ko}        대사 ko 저장(dialogue_overrides)
  POST /api/dialogue/preview {id, ko?, canvas?}  원본↔편집 실캡처
  GET  /preview/<png>                      대사 프리뷰 PNG
  GET  /api/sprite/tile?id=                스프라이트 인덱스 그리드+팔레트
  GET  /api/sprite/render?id=&which=       orig|patched|edit 디코드 렌더 PNG
  GET  /api/sprite/compare?id=             원본↔적용 비교 메타
  GET  /api/sprite/onscreen?id=            실화면 형태 PNG
  GET  /api/sprite/onscreen_data?id=       WYSIWYG 편집용 레이아웃/팔레트
  POST /api/sprite/save / revert / setpalette   픽셀 편집(sprites_overrides)
  POST /api/build                          전체 재빌드 job 시작(비동기)
  GET  /api/jobs?id=                        빌드 job 상태 polling
  GET  /api/download/gba?variant=full       현재 ROM 다운로드
"""
from __future__ import annotations
import argparse
import collections
import csv
import hmac
import hashlib
import importlib.util
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
CATALOG = ROOT / "data" / "scene_catalog.json"
DGROUPS = ROOT / "data" / "dialogue_groups.json"
SYLCODE = ROOT / "data" / "syllable_to_code_2350.json"
ADDRESS_TEXT_OVERRIDES_TSV = ROOT / "data" / "address_text_overrides.tsv"
OUTPUT_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUTPUT_VARIANTS = {
    "full": OUTPUT_ROM,
}
SCENE_SHOT_DIR = ROOT / "temp" / "scene_screenshots"
LEGACY_SCENE_SHOT_DIR = ROOT / "temp" / "comparison_sheets_v2"
REVIEW_ONLY_SCENE_IDS = {"98_extraction_noise_review"}
AUTH_COOKIE = "aw_scene_editor_auth"
AUTH_PASSWORD = os.environ.get("SCENE_EDITOR_PASSWORD") or ""
AUTH_TOKEN = secrets.token_urlsafe(32)

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png"}


def _load_module(name, relpath):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 기존 두 편집기의 helper 재사용(모듈로 로드 — main()은 __main__ 가드라 미실행)
DE = _load_module("de_server", "tools/dialogue_editor/server.py")
SE = _load_module("se_server", "tools/sprite_editor/server.py")
# 빌드 모듈(슬롯 권위 load_slots + DENY/PAIR 영역) — 편집 정합성 게이트용. __main__ 가드라 안전.
try:
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    import build_korean_full as B
    import text_metrics as TM
except Exception as exc:
    raise RuntimeError("scene editor requires build_korean_full/text_metrics for safe save gates") from exc

_LOCK = threading.Lock()
_PREVIEW_LOCK = threading.Lock()
SAFE_CHECKPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# ── 인덱스(1회 로드 캐시) ────────────────────────────────────────────────
_CACHE = {}


def load_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def catalog():
    return load_json(CATALOG, {"scenes": [], "coverage": {}})


def group_index():
    if "groups" not in _CACHE:
        gd = load_json(DGROUPS, {"groups": []})
        _CACHE["groups"] = {g.get("group_id"): g for g in gd.get("groups", [])}
    return _CACHE["groups"]


def sprite_index():
    # SE.sprite_list()는 index + objlabel 합성. id→sprite.
    if "sprites" not in _CACHE:
        _CACHE["sprites"] = {s.get("id"): s for s in SE.sprite_list()}
    return _CACHE["sprites"]


def syl_codes():
    if "syl" not in _CACHE:
        _CACHE["syl"] = json.loads(SYLCODE.read_text(encoding="utf-8"))
    return _CACHE["syl"]


def syl_to_code_ints():
    if "syl_int" not in _CACHE:
        _CACHE["syl_int"] = {
            s: int(c, 16) if isinstance(c, str) else int(c)
            for s, c in syl_codes().items()
        }
    return _CACHE["syl_int"]


def valid_checkpoints():
    """서빙 허용 checkpoint = screen_checkpoints 정의 + 카탈로그 screenshot 참조(allowlist)."""
    checkpoint_path = ROOT / "data" / "screen_checkpoints.json"
    mtimes = (
        checkpoint_path.stat().st_mtime if checkpoint_path.exists() else 0,
        CATALOG.stat().st_mtime if CATALOG.exists() else 0,
    )
    if _CACHE.get("valid_chk_mtimes") != mtimes:
        names = set()
        chk = load_json(checkpoint_path, {"checkpoints": []})
        for c in chk.get("checkpoints", []):
            if c.get("name"):
                names.add(c["name"])
        for sc in catalog().get("scenes", []):
            cp = (sc.get("screenshot") or {}).get("checkpoint")
            if cp:
                names.add(cp)
        _CACHE["valid_chk"] = names
        _CACHE["valid_chk_mtimes"] = mtimes
    return _CACHE["valid_chk"]


def checkpoint_index():
    checkpoint_path = ROOT / "data" / "screen_checkpoints.json"
    mtime = checkpoint_path.stat().st_mtime if checkpoint_path.exists() else 0
    if _CACHE.get("checkpoint_index_mtime") != mtime:
        chk = load_json(checkpoint_path, {"checkpoints": []})
        _CACHE["checkpoint_index"] = {c.get("name"): c for c in chk.get("checkpoints", []) if c.get("name")}
        _CACHE["checkpoint_index_mtime"] = mtime
    return _CACHE["checkpoint_index"]


def scene_shot_path(checkpoint: str | None):
    """checkpoint id → 캡처 PNG 경로. 신규 temp/scene_screenshots 우선, 기존 시트는 fallback."""
    if not checkpoint:
        return None
    rel = f"{checkpoint}_patched/frame.png"
    for base in (SCENE_SHOT_DIR, LEGACY_SCENE_SHOT_DIR):
        p = (base / rel).resolve()
        try:
            if base.resolve() in p.parents and p.exists() and p.is_file():
                return p
        except OSError:
            continue
    return None


def _current_rom_sha():
    """현재 output ROM 전체 sha256(rom_state 캐시 재사용)."""
    rom_state()  # _CACHE['romsha'] 채움
    return _CACHE.get("romsha")


def scene_shot_info(sc):
    shot = dict(sc.get("screenshot") or {})
    checkpoint = shot.get("checkpoint")
    p = scene_shot_path(checkpoint)
    shot["exists"] = bool(p)
    if p:
        shot["url"] = f"/scene_shots/{urllib.parse.quote(checkpoint)}.png"
        shot["mtime"] = int(p.stat().st_mtime)
        # stale 검출(codex major): provenance ROM sha ↔ 현재 ROM sha 비교.
        prov = p.parent / "provenance.json"
        shot["stale"] = None  # 판정 불가(provenance 없음)
        if prov.exists():
            try:
                psha = (json.loads(prov.read_text(encoding="utf-8")) or {}).get("rom_sha256")
                cur = _current_rom_sha()
                if psha and cur:
                    shot["stale"] = (psha != cur)
                    shot["prov_sha"] = psha[:16]
            except Exception:
                pass
    return shot


def scene_extra_shots_info(sc):
    out = []
    by_name = checkpoint_index()
    for extra in ((sc.get("entrypoint") or {}).get("extra_screenshots") or []):
        if isinstance(extra, str):
            checkpoint = extra
            label = ""
        else:
            checkpoint = extra.get("checkpoint")
            label = extra.get("label", "")
        if not checkpoint:
            continue
        meta = by_name.get(checkpoint, {})
        shot = {
            "checkpoint": checkpoint,
            "label": label,
            "mode": meta.get("mode"),
            "grade": meta.get("grade"),
            "note": meta.get("note", ""),
            "capture_path": meta.get("capture_path"),
            "provenance_path": meta.get("provenance_path"),
        }
        out.append(scene_shot_info({"screenshot": shot}))
    return out


def public_scene(sc):
    out = {k: sc[k] for k in ("id", "order", "scope", "subtag", "title",
                              "scene_role", "capture_required",
                              "canvas", "canvas_status", "counts") if k in sc}
    counts = dict(out.get("counts") or {})
    refs = related_dialogue_scene_ids(sc)
    if refs:
        scenes_by_id = {s.get("id"): s for s in catalog().get("scenes", [])}
        rel = sum(len((scenes_by_id.get(ref_id) or {}).get("dialogue_ids", [])) for ref_id in refs)
        if rel:
            counts["related_dialogue"] = rel
            out["counts"] = counts
        out["related_dialogue_scene_ids"] = refs
    out["screenshot"] = scene_shot_info(sc)
    extra = scene_extra_shots_info(sc)
    if extra:
        out["extra_screenshots"] = extra
    return out


# ── 요구7: 바이트 예산 계산(codex 교정 — 대사 슬롯은 NUL 미포함) ──────────
def encoded_len(text: str) -> int:
    """한글=2 / 전각공백=2 / 검증 ASCII=1 / 기타=2(경고대상). dialogue slot 기준 바이트수."""
    return TM.encoded_len(text)


def build_fit_budget(text: str, slot):
    """빌드 encode_fit 기준 길이. UI 표시/저장 게이트가 출하 빌드와 어긋나지 않게 한다."""
    raw = encoded_len(text or "")
    if not isinstance(slot, int) or slot <= 0:
        return {"raw_len": raw, "encoded_len": raw, "fit_level": None, "fits": True}
    if not B:
        return {"raw_len": raw, "encoded_len": raw, "fit_level": None, "fits": raw <= slot}
    dropped = collections.Counter()
    try:
        raw_enc = B.encode_text(text or "", syl_to_code_ints(), dropped)
    except KeyError as exc:
        return {"raw_len": raw, "encoded_len": raw, "fit_level": 99, "fits": False,
                "unsupported": [exc.args[0]], "error": "폰트 미수록 음절"}
    if dropped:
        return {"raw_len": raw, "encoded_len": len(raw_enc), "fit_level": 99, "fits": False,
                "unsupported": [ch for ch, _n in dropped.most_common()],
                "error": "렌더 불가 문자"}
    if not raw_enc and (text or "").strip():
        return {"raw_len": raw, "encoded_len": 0, "fit_level": 99, "fits": False,
                "unsupported": [], "error": "빌드 인코딩 결과가 비어 있음"}
    enc, level = B.encode_fit(text or "", slot, syl_to_code_ints(), collections.Counter())
    if enc is None:
        return {"raw_len": raw, "encoded_len": raw, "fit_level": 99, "fits": False}
    return {"raw_len": raw, "encoded_len": len(enc), "fit_level": level, "fits": len(enc) <= slot}


SAFE_MIN_ADDR = 0x800000  # build_korean_full: 이 미만(코드영역)은 override skip


def build_slots():
    """빌드 권위 슬롯 길이(found_texts length, addr_int→len). dialogue_groups slot과 49건 불일치
    → 빌드가 실제 쓰는 이 값이 권위(M9)."""
    if "build_slots" not in _CACHE:
        _CACHE["build_slots"] = (B.load_slots() if B else {})
    return _CACHE["build_slots"]


def bteam_addresses():
    """B팀(짜옹이) 권위 적용 주소 집합(정규화 0x%08X). 편집 시 경고 플래그용.
    짜옹이 본인 편집은 허용하되, 우발적 변형은 qa_bteam_drift.py 게이트가 별도 차단."""
    if "bteam_addrs" not in _CACHE:
        try:
            data = json.loads((ROOT / "data" / "bteam_addresses.json").read_text(encoding="utf-8"))
            _CACHE["bteam_addrs"] = set(data.get("addresses", []))
        except Exception:
            _CACHE["bteam_addrs"] = set()
    return _CACHE["bteam_addrs"]


def is_bteam(address):
    try:
        return ("0x%08X" % int(address, 16)) in bteam_addresses()
    except (ValueError, TypeError):
        return False


def is_address_text_override(address):
    try:
        addr = int(str(address), 16)
    except (ValueError, TypeError):
        return False
    return addr in address_text_overrides()


def effective_member_ko(member, dialogue_overrides):
    addr = member.get("address")
    if is_address_text_override(addr):
        try:
            addr_int = int(str(addr), 16)
        except (ValueError, TypeError):
            addr_int = None
        if addr_int is not None:
            return address_text_overrides().get(addr_int, member.get("ko") or "")
        return member.get("ko") or ""
    return dialogue_overrides.get(addr, member.get("ko") or "")


def address_text_overrides():
    """Live ADDRESS_TEXT_OVERRIDES authority.

    build_korean_full imports data/address_text_overrides.tsv once, but the
    editor can update that TSV while the server process stays alive.  Keep a
    small mtime cache here so protected text rows display and validate against
    the same file that the next build subprocess will consume.
    """
    if ADDRESS_TEXT_OVERRIDES_TSV.exists():
        st = ADDRESS_TEXT_OVERRIDES_TSV.stat()
        key = (st.st_mtime_ns, st.st_size)
        if _CACHE.get("address_text_overrides_key") != key:
            rows = {}
            with ADDRESS_TEXT_OVERRIDES_TSV.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                if reader.fieldnames != ["address", "text"]:
                    raise ValueError(f"{ADDRESS_TEXT_OVERRIDES_TSV}: expected TSV header address<TAB>text")
                for row in reader:
                    raw_addr = (row.get("address") or "").strip()
                    if not raw_addr:
                        continue
                    rows[int(raw_addr, 16)] = "" if row.get("text") is None else str(row.get("text"))
            _CACHE["address_text_overrides_key"] = key
            _CACHE["address_text_overrides"] = rows
        return _CACHE.get("address_text_overrides", {})
    if "address_text_overrides_fallback" not in _CACHE:
        _CACHE["address_text_overrides_fallback"] = {
            int(k): str(v or "") for k, v in getattr(B, "ADDRESS_TEXT_OVERRIDES", {}).items()
        }
    return _CACHE["address_text_overrides_fallback"]


def save_address_text_override(addr: str, ko: str) -> None:
    """Persist a protected address edit to the TSV build authority."""
    addr_int = int(addr, 16)
    rows = dict(address_text_overrides())
    if addr_int not in rows:
        raise ValueError(f"{addr}: ADDRESS_TEXT_OVERRIDES row not found")
    rows[addr_int] = ko
    ADDRESS_TEXT_OVERRIDES_TSV.parent.mkdir(parents=True, exist_ok=True)
    with ADDRESS_TEXT_OVERRIDES_TSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "text"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({"address": "0x%08X" % key, "text": rows[key]})
    _CACHE.pop("address_text_overrides_key", None)
    _CACHE.pop("address_text_overrides", None)


def sync_dialogue_display_data(addr: str, ko: str) -> None:
    """Keep editor-facing generated data aligned with the build authority."""
    data = DE.load_json(DE.DIALOGUE_PATH, {"lines": []})
    for ln in data.get("lines", []):
        if canon_addr(ln.get("address")) == addr:
            ln["ko"] = ko
            if "ship_ko" in ln:
                ln["ship_ko"] = ko
    DE.save_json(DE.DIALOGUE_PATH, data)

    groups = load_json(DGROUPS, {"groups": []})
    for group in groups.get("groups", []):
        for member in group.get("members", []):
            if canon_addr(member.get("address")) == addr:
                member["ko"] = ko
                if "ship_ko" in member:
                    member["ship_ko"] = ko
    DGROUPS.write_text(json.dumps(groups, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _CACHE.pop("groups", None)
    _CACHE.pop("addr_slot", None)


def bteam_baseline_for(addr: str):
    if is_address_text_override(addr):
        return address_text_overrides().get(int(addr, 16))
    try:
        base = DE.load_json(ROOT / "data" / "bteam_baseline.json", {}) or {}
        return (base.get("overrides") or {}).get("0x%08X" % int(addr, 16))
    except Exception:
        return None


def canon_addr(address):
    try:
        addr = int(str(address or "").strip(), 16)
    except (ValueError, TypeError):
        return None
    if not 0 <= addr <= 0xFFFFFFFF:
        return None
    return "0x%08X" % addr


def canonical_override_map(raw):
    out = {}
    for key, value in (raw or {}).items():
        ckey = canon_addr(key)
        if ckey:
            out[ckey] = value
    return out


def deny_pair_status(addr_int, slot):
    """[addr,addr+slot)가 DENY_REGIONS와 겹치면 ('deny',name), PAIR_RENDERER면 ('pair',name). (M10)"""
    if not B:
        return (None, None)
    lo, hi = addr_int, addr_int + max(slot, 1)
    try:
        deny = B.in_deny(lo, hi)
    except Exception:
        deny = None
    if deny:
        return ("deny", deny)
    for name, rlo, rhi in getattr(B, "DENY_REGIONS", []):
        if lo < rhi and hi > rlo:
            return ("deny", name)
    for name, rlo, rhi in getattr(B, "PAIR_RENDERER_REGIONS", []):
        if lo < rhi and hi > rlo:
            return ("pair", name)
    return (None, None)


def line_budget(member):
    """member의 slot 예산 + 순한글 최대 음절수 + editable(빌드 적용 가능 여부).
    슬롯 권위 = 빌드 found_texts length(M9). 빌드는 slot<=0/addr<SAFE_MIN_ADDR/DENY 영역을 skip."""
    try:
        addr_int = int((member.get("address") or "0x0"), 16)
    except (ValueError, TypeError):
        addr_int = 0
    # 슬롯 권위: 빌드 found length > dialogue_groups slot. min으로 안전.
    g_slot = member.get("slot")
    b_slot = build_slots().get(addr_int)
    if str(member.get("kind") or "").startswith("script:") and isinstance(g_slot, int) and g_slot > 0:
        # Direct script patches write the explicit [start,end) span in build_korean_full.py.
        # found_texts often contains only the first source fragment, so using b_slot would
        # falsely expose the current shipped text as over budget.
        slot = g_slot
        est = False
    elif isinstance(b_slot, int) and b_slot > 0:
        slot = min(b_slot, g_slot) if isinstance(g_slot, int) and g_slot > 0 else b_slot
        est = False
    elif isinstance(g_slot, int) and g_slot > 0:
        slot = g_slot
        est = False
    else:
        slot = len((member.get("ja") or "")) * 2
        est = True
    kind, region = deny_pair_status(addr_int, slot)
    editable = (not est) and slot > 0 and addr_int >= SAFE_MIN_ADDR and kind != "deny" and kind != "pair"
    reason = ""
    if not editable:
        if kind == "deny":
            reason = "빌드 deny 영역(%s) — 덮으면 손상" % region
        elif kind == "pair":
            reason = "pair 렌더러 영역(%s) — 특수 처리 필요" % region
        elif est:
            reason = "슬롯 길이 미상(빌드 미적용 가능)"
        elif addr_int < SAFE_MIN_ADDR:
            reason = "코드영역 주소(<0x800000, 빌드 skip)"
        elif slot <= 0:
            reason = "슬롯 0"
    return {"slot": slot, "max_syllables": slot // 2, "estimated": est,
            "editable": editable, "reason": reason}


def member_slot(address):
    """주소 → 빌드 권위 슬롯 길이. found length 우선, 없으면 dialogue_groups slot."""
    try:
        ai = int(address, 16)
    except (ValueError, TypeError):
        return None
    key = "0x%08X" % ai
    if "addr_slot" not in _CACHE:
        idx = {}
        for g in group_index().values():
            for m in g.get("members", []):
                a = m.get("address"); s = m.get("slot")
                if a is not None and isinstance(s, int):
                    k = canon_addr(a)
                    if not k:
                        continue
                    rec = idx.setdefault(k, {"slot": s, "script_slot": None})
                    rec["slot"] = max(rec["slot"], s)
                    if str(m.get("kind") or "").startswith("script:"):
                        rec["script_slot"] = max(rec["script_slot"] or 0, s)
        _CACHE["addr_slot"] = idx
    rec = _CACHE["addr_slot"].get(key) or {}
    if rec.get("script_slot"):
        return rec["script_slot"]
    b = build_slots().get(ai)
    if isinstance(b, int) and b > 0:
        return b
    return rec.get("slot")


def unsupported_syllables(text):
    """2350 셋에 없는 완성형 한글(인게임 '?' 깨짐 원인)을 반환. ASCII/공백/줄바꿈은 무시."""
    return TM.unmapped_syllables(text, frozenset(syl_codes().keys()))


def is_building():
    return _BUILD["status"] == "building"


# ── 빌드 job(비동기, 직렬화) ─────────────────────────────────────────────
_BUILD = {"status": "idle", "started": 0, "finished": 0, "log_tail": "", "error": None, "output_verify": None}
_BUILD_LOCK = threading.Lock()
BUILD_FRESHNESS_MARGIN_NS = 1_000_000_000


class EditorHTTPServer(ThreadingHTTPServer):
    # The in-app browser/VS Code can leave several pending localhost connects on
    # the default :8782 port.  The stdlib default backlog is small enough for
    # those pending SYNs to starve new verifier/API clients.
    request_queue_size = 128
    daemon_threads = True
    allow_reuse_address = True


def _run_build():
    # M6: _BUILD_LOCK은 상태 변경에만(짧게). subprocess(최대 1200s)는 락 밖에서 실행 →
    # 빌드 중에도 /api/state·/api/build(거부) 등이 응답함. status='building'은 start_build가 이미 설정.
    import subprocess
    build_started_ns = time.time_ns()
    fresh_after_ns = max(0, build_started_ns - BUILD_FRESHNESS_MARGIN_NS)
    with _BUILD_LOCK:
        _BUILD.update(status="building", started=int(build_started_ns / 1_000_000_000),
                      finished=0, error=None, log_tail="")
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_korean_full.py")],
                              capture_output=True, text=True, cwd=str(ROOT), timeout=1200)
        applied = ""
        for ln in (proc.stdout or "").splitlines():
            if "스프라이트 편집 적용" in ln or "스프라이트 편집" in ln:
                applied = ln.strip()
        output_verify = output_sync_state(min_mtime_ns=fresh_after_ns) if proc.returncode == 0 else None
        ok = proc.returncode == 0 and bool(output_verify and output_verify.get("ok"))
        error = (proc.stderr or "")[-800:] if proc.returncode != 0 else None
        if proc.returncode == 0 and not ok:
            error = "빌드 산출물 SHA 불일치: " + "; ".join(output_verify.get("issues") or [])
        with _BUILD_LOCK:
            _BUILD.update(status="success" if ok else "fail",
                          finished=int(time.time()),
                          log_tail=(proc.stdout or "")[-1500:],
                          error=error,
                          applied=applied,
                          output_verify=output_verify)
    except Exception as e:
        with _BUILD_LOCK:
            _BUILD.update(status="fail", finished=int(time.time()), error=repr(e), output_verify=None)
    finally:
        # ROM/레이아웃/대사 캐시 무효화(stale 방지)
        SE._PATCHED = None
        SE._OBJLABELS = None
        SE._BUILD_LAYOUTS = None
        SE._LAYOUTS = None
        DE._GROUPS_CACHE = None
        for k in ("sprites", "romsha_key", "groups", "addr_slot", "build_slots"):
            _CACHE.pop(k, None)


def start_build():
    # 경합 방지: 상태 판정+예약을 락 안에서. 이중 스레드 생성 차단.
    with _BUILD_LOCK:
        if _BUILD["status"] == "building":
            return {"ok": False, "error": "이미 빌드 중"}
        _BUILD["status"] = "building"
        _BUILD["output_verify"] = None
    threading.Thread(target=_run_build, daemon=True).start()
    return {"ok": True, "status": "building"}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def output_sync_state(min_mtime_ns: int | None = None):
    variants = {}
    issues = []
    full_sha = None
    out_cache = _CACHE.setdefault("outputsha", {})
    for name, path in OUTPUT_VARIANTS.items():
        if not path.exists():
            variants[name] = {"exists": False}
            issues.append(f"{name} 없음")
            continue
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
        rec = out_cache.get(name)
        if not rec or rec[0] != key:
            rec = (key, sha256_path(path))
            out_cache[name] = rec
        sha = rec[1]
        variants[name] = {
            "exists": True,
            "sha256": sha[:16],
            "full_sha256": sha,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "mtime_ns": st.st_mtime_ns,
        }
        if min_mtime_ns is not None and st.st_mtime_ns < min_mtime_ns:
            issues.append(f"{name} 이전 빌드 산출물(mtime < build freshness threshold)")
        if name == "full":
            full_sha = sha
    if full_sha:
        for name, info in variants.items():
            if info.get("exists") and info.get("full_sha256") != full_sha:
                issues.append(f"{name} SHA != full")
    ok = bool(full_sha) and not issues
    return {
        "ok": ok,
        "sha256": full_sha[:16] if full_sha else None,
        "full_sha256": full_sha,
        "variants": variants,
        "issues": issues,
    }


def rom_state():
    if not OUTPUT_ROM.exists():
        return {"exists": False}
    st = OUTPUT_ROM.stat()
    key = ("romsha", st.st_mtime_ns, st.st_size)
    if _CACHE.get("romsha_key") != key:
        _CACHE["romsha_key"] = key
        rec = (_CACHE.get("outputsha") or {}).get("full")
        output_key = (st.st_mtime_ns, st.st_size)
        _CACHE["romsha"] = rec[1] if rec and rec[0] == output_key else sha256_path(OUTPUT_ROM)
    return {"exists": True, "sha256": _CACHE["romsha"][:16], "size": st.st_size,
            "mtime": st.st_mtime, "mtime_ns": st.st_mtime_ns, "full_sha256": _CACHE["romsha"]}


def dirty_state():
    """미빌드 편집 여부 = override 파일 mtime > ROM mtime일 때만 dirty(빌드 후 깨끗).
    개수도 함께 반환(전체 override 규모 표시용)."""
    dov = load_json(DE.OVERRIDES_PATH, {}) or {}
    sov = load_json(SE.OVERRIDES_PATH, {}) or {}
    aov = address_text_overrides()
    rom_st = OUTPUT_ROM.stat() if OUTPUT_ROM.exists() else None
    rom_m = rom_st.st_mtime if rom_st else 0
    rom_m_ns = rom_st.st_mtime_ns if rom_st else 0

    def newer(p):
        return Path(p).exists() and Path(p).stat().st_mtime_ns > rom_m_ns + 1_000_000

    d_dirty = newer(DE.OVERRIDES_PATH)
    s_dirty = newer(SE.OVERRIDES_PATH)
    a_dirty = newer(ADDRESS_TEXT_OVERRIDES_TSV)
    newest_override_m_ns = max(
        [
            Path(p).stat().st_mtime_ns
            for p in (DE.OVERRIDES_PATH, SE.OVERRIDES_PATH, ADDRESS_TEXT_OVERRIDES_TSV)
            if Path(p).exists()
        ] or [0]
    )
    return {"dialogue_overrides": len(dov) if d_dirty else 0,
            "sprite_overrides": len(sov) if s_dirty else 0,
            "address_text_overrides": len(aov) if a_dirty else 0,
            "dialogue_total": len(dov), "sprite_total": len(sov),
            "address_text_total": len(aov),
            "rom_mtime": rom_m, "rom_mtime_ns": rom_m_ns,
            "newest_override_mtime": newest_override_m_ns / 1_000_000_000 if newest_override_m_ns else 0,
            "newest_override_mtime_ns": newest_override_m_ns,
            "dirty": bool(d_dirty or s_dirty or a_dirty),
            "apply_needed": bool(d_dirty or s_dirty or a_dirty)}


# ── scene 항목 조회 ──────────────────────────────────────────────────────
def related_dialogue_scene_ids(scene):
    """그래픽 중심 scene에도 같은 좌측 패널에서 편집할 관련 대사 bucket을 함께 노출한다.
    카탈로그에 명시된 연결만 따른다. 과거에는 scope 단위 전체 대사 bucket을 자동 연결했지만
    타이틀/메뉴처럼 실제 대사가 없는 화면에 수백~수천 개 대사가 붙어 장면 의미가 깨졌다."""
    sid = scene.get("id")
    if sid in {"19_part1_story", "30_part2_story", "80_campaign_story",
               "85_ui_common", "90_other_dialogue", "99_unassigned_review"}:
        return []
    return list(scene.get("related_dialogue_scene_ids") or [])


def scene_items(scene, want="all"):
    gi = group_index()
    si = sprite_index()
    dov = load_json(DE.OVERRIDES_PATH, {}) or {}
    out_d, out_s = [], []
    review_only_scene = scene.get("id") in REVIEW_ONLY_SCENE_IDS
    if want in ("all", "dialogue"):
        dialogue_entries = [(gid, None) for gid in scene.get("dialogue_ids", [])]
        if want == "all":
            scenes_by_id = {s.get("id"): s for s in catalog().get("scenes", [])}
            seen = {gid for gid, _ in dialogue_entries}
            for ref_id in related_dialogue_scene_ids(scene):
                ref = scenes_by_id.get(ref_id)
                if not ref:
                    continue
                for gid in ref.get("dialogue_ids", []):
                    if gid in seen:
                        continue
                    seen.add(gid)
                    dialogue_entries.append((gid, ref.get("title") or ref_id))
        for gid, linked_from in dialogue_entries:
            g = gi.get(gid)
            if not g:
                continue
            members = []
            for m in g.get("members", []):
                ko = effective_member_ko(m, dov)
                budget = line_budget(m)
                budget.update(build_fit_budget(ko, budget.get("slot")))
                if review_only_scene and (budget.get("unsupported") is not None or budget.get("error")):
                    budget["editable"] = False
                    budget["reason"] = "저신뢰 추출 후보 검토 bucket — 현재 값이 빌드 렌더러에서 보존되지 않음"
                budget["bteam"] = is_bteam(m.get("address"))
                if budget["bteam"]:
                    budget["bteam_warn"] = "짜옹이님(B팀) 권위 번역 — 신중히 편집(우발 변형은 qa_bteam_drift 게이트가 차단)"
                if is_address_text_override(m.get("address")):
                    budget["protected_address_text"] = True
                    budget["protected_warn"] = "보호 문구 — 저장 시 address_text_overrides.tsv에 반영됩니다"
                members.append({"address": m.get("address"), "ja": m.get("ja"), "ko": ko,
                                "kind": m.get("kind"), "budget": budget})
            out_d.append({"group_id": gid, "region": g.get("region"), "size": g.get("size"),
                          "flagged": g.get("flagged"), "assembled_ja": g.get("assembled_ja"),
                          "segments": g.get("segments"), "members": members,
                          "linked_from": linked_from})
    if want in ("all", "sprite"):
        for sid in scene.get("sprite_ids", []):
            sp = si.get(sid) or SE.sprite_by_id(sid)
            if not sp:
                continue
            is_text, desc = SE.classify_sprite(sp.get("source"))
            desc = sp.get("desc_override") or desc
            has_onscreen = (SE.get_layout(sid) is not None) and not SE.is_mode4_bitmap(sp)
            out_s.append({"id": sid, "source": sp.get("source"), "type": sp.get("type"),
                          "offset": sp.get("offset"), "desc": desc, "is_text": is_text,
                          "has_onscreen": has_onscreen})
    return out_d, out_s


def filter_scenes(scope, tag, q):
    scenes = catalog().get("scenes", [])
    out = []
    for sc in scenes:
        if scope and scope != "all" and sc.get("scope") != scope and sc.get("id") != "99_unassigned_review":
            # all 스코프 scene은 어떤 필터에서도 표시; review는 항상 표시
            if sc.get("scope") != "all":
                continue
        if tag and sc.get("subtag") != tag:
            continue
        if q:
            q_lower = q.lower()
            hay = (sc.get("title", "") + sc.get("id", "") + sc.get("subtag", "")).lower()
            if q_lower not in hay:
                continue
        out.append(public_scene(sc))
    out.sort(key=lambda s: s.get("order", 0))
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _auth_enabled(self):
        return bool(AUTH_PASSWORD)

    def _auth_cookie_value(self):
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == AUTH_COOKIE:
                return value
        return ""

    def _authenticated(self):
        if not self._auth_enabled():
            return True
        return hmac.compare_digest(self._auth_cookie_value(), AUTH_TOKEN)

    def _require_auth(self):
        if self._authenticated():
            return True
        self._send(401, {"ok": False, "auth_required": True, "error": "비밀번호가 필요합니다"})
        return False

    def _login(self, body):
        if not self._auth_enabled():
            return self._send(200, {"ok": True, "auth_required": False, "authenticated": True})
        password = str(body.get("password") or "")
        if not hmac.compare_digest(password, AUTH_PASSWORD):
            return self._send(401, {"ok": False, "auth_required": True, "error": "비밀번호가 틀렸습니다"})
        cookie = f"{AUTH_COOKIE}={AUTH_TOKEN}; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800"
        return self._send(
            200,
            {"ok": True, "auth_required": True, "authenticated": True},
            headers=[("Set-Cookie", cookie)],
        )

    def _logout(self):
        cookie = f"{AUTH_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return self._send(
            200,
            {"ok": True, "auth_required": self._auth_enabled(), "authenticated": False},
            headers=[("Set-Cookie", cookie)],
        )

    # ── GET ──
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p in ("/", "/index.html"):
            return self._static("index.html")
        if p.startswith("/static/"):
            return self._static(p[len("/static/"):])
        if p == "/api/auth/status":
            return self._send(200, {
                "ok": True,
                "auth_required": self._auth_enabled(),
                "authenticated": self._authenticated(),
            })
        if not self._require_auth():
            return
        if p.startswith("/scene_shots/"):
            return self._serve_scene_shot(urllib.parse.unquote(p[len("/scene_shots/"):]))
        if p == "/api/state":
            dirty = dirty_state()
            output_sync = output_sync_state()
            return self._send(200, {"rom": rom_state(), "dirty": dirty,
                                    "apply_needed": dirty.get("apply_needed"),
                                    "output_sync": output_sync,
                                    "build": {k: _BUILD.get(k) for k in (
                                        "status", "started", "finished", "output_verify"
                                    )}})
        if p == "/api/scenes":
            return self._send(200, {"scenes": filter_scenes(q.get("scope", [""])[0],
                                                             q.get("tag", [""])[0],
                                                             q.get("q", [""])[0]),
                                    "coverage": catalog().get("coverage", {}),
                                    "scopes": catalog().get("scopes", [])})
        if p == "/api/scene/items":
            sid = q.get("id", [""])[0]
            sc = next((s for s in catalog().get("scenes", []) if s.get("id") == sid), None)
            if not sc:
                return self._send(404, {"error": "no scene %s" % sid})
            d, s = scene_items(sc, q.get("type", ["all"])[0])
            return self._send(200, {"id": sid, "title": sc.get("title"), "scope": sc.get("scope"),
                                    "subtag": sc.get("subtag"),
                                    "scene_role": sc.get("scene_role"),
                                    "capture_required": sc.get("capture_required"),
                                    "canvas": sc.get("canvas"),
                                    "canvas_status": sc.get("canvas_status"),
                                    "related_dialogue_scene_ids": related_dialogue_scene_ids(sc),
                                    "screenshot": scene_shot_info(sc),
                                    "extra_screenshots": scene_extra_shots_info(sc),
                                    "dialogue": d, "sprites": s})
        if p == "/api/dict":
            return self._send(200, load_json(DE.DICT_PATH, {}))
        if p == "/api/syllables":
            # JS 즉시 검증용: 폰트 수록 음절 목록(2350). 미수록 입력 차단에 사용.
            return self._send(200, {"syllables": list(syl_codes().keys())})
        if p == "/preview/":
            return self._send(404, {"error": "no preview"})
        if p.startswith("/preview/"):
            return self._serve_preview(p[len("/preview/"):])
        if p == "/api/sprite/tile":
            return self._sprite_proxy("tile", q)
        if p == "/api/sprite/render":
            return self._sprite_render(q)
        if p == "/api/sprite/compare":
            return self._sprite_proxy("compare", q)
        if p == "/api/sprite/onscreen":
            return self._sprite_onscreen(q)
        if p == "/api/sprite/onscreen_data":
            return self._sprite_proxy("onscreen_data", q)
        if p == "/api/palettes":
            return self._send(200, {"palettes": SE.palette_library()})
        if p == "/api/jobs":
            return self._send(200, {k: _BUILD.get(k) for k in (
                "status", "started", "finished", "log_tail", "error", "output_verify"
            )})
        if p == "/api/download/gba":
            return self._download()
        return self._send(404, {"error": "not found"})

    def _static(self, rel):
        # 경로 탈출 방지: STATIC 하위로 강제 제한
        path = (STATIC / rel).resolve()
        base = STATIC.resolve()
        if base != path and base not in path.parents:
            return self._send(403, {"error": "forbidden"})
        if not path.exists() or not path.is_file():
            return self._send(404, {"error": "missing " + rel})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(path.suffix, "application/octet-stream"))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_preview(self, name):
        pdir = DE.PREVIEW_DIR
        pdir.mkdir(parents=True, exist_ok=True)
        safe = (pdir / name).resolve()
        if pdir.resolve() not in safe.parents or safe.suffix != ".png" or not safe.exists():
            return self._send(404, {"error": "no preview"})
        self._send(200, safe.read_bytes(), "image/png")

    def _serve_scene_shot(self, name):
        if not name.endswith(".png") or "/" in name or "\\" in name:
            return self._send(404, {"error": "no scene shot"})  # basename만 허용(codex minor)
        checkpoint = Path(name).stem
        if not SAFE_CHECKPOINT_RE.fullmatch(checkpoint):
            return self._send(403, {"error": "forbidden"})
        if checkpoint not in valid_checkpoints():  # allowlist: 카탈로그/체크포인트 정의된 것만(codex minor)
            return self._send(404, {"error": "unknown checkpoint: " + checkpoint})
        p = scene_shot_path(checkpoint)
        if not p:
            return self._send(404, {"error": "scene shot not captured: " + checkpoint})
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # 스프라이트 핸들러 재사용: SE의 Handler 메서드 바디를 모듈 함수로 호출
    def _sprite_proxy(self, kind, q):
        sid = q.get("id", [""])[0]
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return self._send(404, {"error": "id 없음: %s" % sid})
        if kind == "tile":
            return self._send(200, self._tile_data(sid, sp, q))
        if kind == "compare":
            return self._send(200, self._compare_data(sid, sp))
        if kind == "onscreen_data":
            return self._send(200, self._onscreen_data(sid, sp))

    def _tile_data(self, sid, sp, q):
        which = (q.get("which", ["current"])[0] or "current").strip()
        if which not in ("current", "orig"):
            return {"ok": False, "error": "which=current|orig"}
        ov = load_json(SE.OVERRIDES_PATH, {}) or {}
        key = SE.override_id(sp)
        rec = ov.get(key)
        desc = sp.get("desc_override") or SE.classify_sprite(sp.get("source"))[1]
        has_os = SE.get_layout(sid) is not None
        if SE.is_mode4_bitmap(sp):
            qid = urllib.parse.quote(sid)
            data = SE.decode_mode4_bitmap(SE.rom_bytes() if which == "orig" else SE.patched_bytes(), sp)
            if data is None:
                return {"ok": False, "error": "Mode4 비트맵 디코드 실패"}
            _, w, h = data
            return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": 0,
                    "type": "mode4_bitmap", "palette": [], "indices": [],
                    "edited": False, "offset": sp.get("offset"), "source": sp.get("source"),
                    "desc": desc, "has_onscreen": False, "readonly": True,
                    "readonly_reason": "Mode4 8bpp 프레임버퍼 리소스라 4bpp 타일 편집으로 저장할 수 없습니다.",
                    "orig_url": "/api/sprite/render?id=%s&which=orig" % qid,
                    "patched_url": "/api/sprite/render?id=%s&which=patched" % qid,
                    "which": which}
        if which == "orig":
            dec = SE.decode_indices(sp)
            if dec is None:
                return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
            grid, w, h, cols = dec
            return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                    "type": sp.get("type"), "palette": SE.default_palette_for(sp), "indices": grid,
                    "edited": False, "offset": sp.get("offset"), "source": sp.get("source"),
                    "desc": desc, "has_onscreen": has_os, "which": "orig"}
        if rec and rec.get("indices"):
            grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
            return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": w // 8,
                    "type": sp.get("type"), "palette": SE.palette_for(sp), "indices": grid,
                    "edited": True, "offset": sp.get("offset"), "source": sp.get("source"),
                    "desc": desc, "has_onscreen": has_os}
        dec = SE.decode_current_indices(sp)
        if dec is None:
            return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
        grid, w, h, cols = dec
        return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                "type": sp.get("type"), "palette": SE.palette_for(sp), "indices": grid,
                "edited": False, "offset": sp.get("offset"), "source": sp.get("source"),
                "desc": desc, "has_onscreen": has_os}

    def _compare_data(self, sid, sp):
        if SE.is_mode4_bitmap(sp):
            o = SE.decode_mode4_bitmap(SE.rom_bytes(), sp)
            pat = SE.decode_mode4_bitmap(SE.patched_bytes(), sp) if SE.patched_bytes() else None
            changed = bool(o and pat and o[0] != pat[0])
        else:
            o = SE.decode_from_rom(SE.rom_bytes(), sp)
            pat = SE.decode_from_rom(SE.patched_bytes(), sp) if SE.patched_bytes() else None
            changed = (o and pat and o[0] != pat[0])
        ov = load_json(SE.OVERRIDES_PATH, {}) or {}
        key = SE.override_id(sp)
        has_edit = key in ov and bool(ov[key].get("indices"))
        qid = urllib.parse.quote(sid)
        return {"ok": True, "id": sid, "offset": sp.get("offset"), "type": sp.get("type"),
                "source": sp.get("source"),
                "orig_url": "/api/sprite/render?id=%s&which=orig" % qid,
                "patched_url": ("/api/sprite/render?id=%s&which=patched" % qid) if pat else None,
                "edit_url": ("/api/sprite/render?id=%s&which=edit" % qid) if has_edit else None,
                "build_changed": bool(changed), "has_edit": has_edit}

    def _onscreen_data(self, sid, sp):
        import struct as _s
        lay = SE.get_layout(sid)
        if not lay:
            return {"ok": False, "error": "no layout for %s" % sid}
        dec = SE.decode_current_indices(sp)
        cols = dec[3] if dec else (sp.get("tile_cols") or 1)
        cells = [dict(c) for c in lay["cells"]]
        palp = lay.get("pal_file")
        palettes = {}
        if palp and (ROOT / palp).exists():
            palb = (ROOT / palp).read_bytes()

            def col(abs_i):
                if abs_i * 2 + 2 > len(palb):
                    return [0, 0, 0]
                i = abs_i
                v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
                return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]

            for cell in cells:
                palbase = cell.get("palbase", 256)
                bank = cell.get("bank", 0)
                key = f"{palbase}:{bank}"
                cell["palette_key"] = key
                if key not in palettes:
                    palettes[key] = [col(palbase + bank * 16 + i) for i in range(16)]
            first_key = cells[0].get("palette_key") if cells else None
            palette = palettes.get(first_key, [[0, 0, 0]] * 16)
        else:
            palette = [list(c) for c in SE.palette_for(sp)]
            palettes["default"] = palette
            for cell in cells:
                cell["palette_key"] = "default"
        return {"ok": True, "w": lay["w"], "h": lay["h"], "x0": lay["x0"], "y0": lay["y0"],
                "obj1d": lay.get("obj1d", 1), "tile_cols": cols, "cells": cells,
                "palette": palette, "palettes": palettes,
                "screen": lay.get("screen"), "build": lay.get("build", False)}

    def _sprite_render(self, q):
        sid = q.get("id", [""])[0]
        which = q.get("which", ["orig"])[0]
        if which not in ("orig", "patched", "edit"):
            return self._send(400, {"error": "which=orig|patched|edit"})
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return self._send(404, {"error": "id 없음: %s" % sid})
        if which == "edit":
            # 편집본 없으면 ROM 폴백 대신 404(‘편집중’에 원본 표시 방지 — m7)
            ov = SE.load_json(SE.OVERRIDES_PATH, {}) or {}
            key = SE.override_id(sp)
            if not (ov.get(key) and ov[key].get("indices")):
                return self._send(404, {"error": "편집본 없음"})
        try:
            data = SE.render_compare_png(sid, which)
        except Exception as e:
            return self._send(500, {"error": "render: %r" % e})
        if not data:
            return self._send(404, {"error": "no render"})
        return self._send(200, data, "image/png")

    def _sprite_onscreen(self, q):
        sid = q.get("id", [""])[0]
        try:
            data = SE.render_onscreen_png(sid)
        except Exception as e:
            return self._send(500, {"error": "onscreen: %r" % e})
        if not data:
            return self._send(404, {"error": "no onscreen layout"})
        return self._send(200, data, "image/png")

    def _download(self):
        if is_building():
            return self._send(409, {"error": "빌드 중 — 완료 후 다운로드하세요"})
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        variant = (q.get("variant", ["full"])[0] or "full").strip()
        if variant not in OUTPUT_VARIANTS:
            return self._send(400, {"error": "unknown variant: " + variant,
                                    "variants": sorted(OUTPUT_VARIANTS)})
        path = OUTPUT_VARIANTS[variant]
        if not path.exists():
            return self._send(404, {"error": f"output ROM 없음({variant}) — 먼저 빌드하세요"})
        # 배포 불변식: canonical full ROM 하나만 다운로드한다.
        sync = output_sync_state()
        if not sync.get("ok"):
            return self._send(409, {"error": "output ROM 없음 또는 이전 빌드 산출물 — 먼저 적용(빌드)을 다시 실행하세요",
                                    "output_sync": sync})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── POST ──
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"error": "bad json: %r" % e})
        p = u.path
        if p == "/api/login":
            return self._login(body)
        if p == "/api/logout":
            return self._logout()
        if not self._require_auth():
            return
        if p == "/api/dialogue/line":
            return self._send(200, self._save_line(body))
        if p == "/api/dialogue/preview":
            return self._send(200, self._dialogue_preview(body))
        if p == "/api/dict":
            return self._send(200, self._edit_dict(body))
        if p in ("/api/sprite/save", "/api/sprite/revert", "/api/sprite/setpalette") and is_building():
            return self._send(200, {"ok": False, "error": "빌드 중 — 완료 후 편집하세요"})
        if p == "/api/sprite/save":
            return self._send(200, self._sprite_save(body))
        if p == "/api/sprite/revert":
            return self._send(200, self._sprite_revert(body))
        if p == "/api/sprite/setpalette":
            return self._send(200, self._sprite_setpalette(body))
        if p == "/api/build":
            return self._send(200, start_build())
        return self._send(404, {"error": "not found"})

    def _save_line(self, body):
        """대사 ko 저장(주소 기준 override). 그룹 멤버(조각)별 독립 슬롯."""
        addr = body.get("address")
        ko = body.get("ko", "")
        addr = canon_addr(addr)
        if not addr:
            return {"ok": False, "error": "address 필요"}
        if is_building():
            return {"ok": False, "error": "빌드 중 — 완료 후 저장하세요"}
        # 빌드 미적용(코드영역/슬롯미상) 조각 차단 — 편집해도 ROM 미반영
        addr_int = int(addr, 16)
        if addr_int < SAFE_MIN_ADDR:
            return {"ok": False, "error": "코드영역 주소(<0x800000) — 빌드 미적용, 편집 불가"}
        protected_address_text = is_address_text_override(addr)
        # DENY/PAIR 영역 차단(덮으면 그래픽/렌더 손상 — M10)
        kind, region = deny_pair_status(addr_int, member_slot(addr) or 1)
        if kind == "deny":
            return {"ok": False, "error": "빌드 deny 영역(%s) — 편집 불가(손상 방지)" % region}
        if kind == "pair":
            return {"ok": False, "error": "pair 렌더러 영역(%s) — 특수 처리 필요, 편집 불가" % region}
        # 서버측 하드게이트(클라 우회/오차 방어): 슬롯 초과·미수록 음절 차단
        bad = unsupported_syllables(ko)
        if bad:
            return {"ok": False, "error": "폰트 미수록 음절(인게임 ‘?’): " + "".join(bad), "unsupported": bad}
        # B팀(짜옹이) 권위 주소 save-time 보호(짜옹이 본인 편집은 허용하되 우발 변형 차단).
        # confirm_bteam=True 명시 전에는 차단 + baseline 대비 무엇이 바뀌는지 알린다.
        if is_bteam(addr) and not body.get("confirm_bteam"):
            _want = bteam_baseline_for(addr)
            if _want is None or _want != ko:
                return {"ok": False, "bteam_confirm_required": True,
                        "error": "짜옹이님(B팀) 권위 번역 주소입니다. 변경하려면 confirm_bteam=true로 재전송하세요.",
                        "bteam_baseline": _want}
        slot = member_slot(addr)
        fit = build_fit_budget(ko, slot)
        if fit.get("unsupported") is not None:
            return {"ok": False, "error": fit.get("error") or "렌더 불가 문자",
                    "unsupported": fit.get("unsupported"), "encoded_len": fit["encoded_len"],
                    "raw_len": fit["raw_len"], "slot": slot}
        if isinstance(slot, int) and not fit["fits"]:
            return {"ok": False, "error": "슬롯 초과 %dB>%dB" % (fit["raw_len"], slot), "over": True,
                    "encoded_len": fit["encoded_len"], "raw_len": fit["raw_len"], "slot": slot}
        if body.get("dry_run"):
            return {"ok": True, "dry_run": True, "address": addr, "ko": ko, "encoded_len": fit["encoded_len"],
                    "raw_len": fit["raw_len"], "fit_level": fit["fit_level"], "slot": slot,
                    "protected_address_text": protected_address_text,
                    "storage": "address_text_overrides.tsv" if protected_address_text else "dialogue_overrides.json"}
        with _LOCK:
            if protected_address_text:
                save_address_text_override(addr, ko)
            else:
                ov = canonical_override_map(DE.load_json(DE.OVERRIDES_PATH, {}) or {})
                ov[addr] = ko
                DE.save_json(DE.OVERRIDES_PATH, ov)
            # dialogue_map/dialogue_groups의 ko도 동기(편집 표시·governance 일관)
            sync_dialogue_display_data(addr, ko)
        return {"ok": True, "address": addr, "ko": ko, "encoded_len": fit["encoded_len"],
                "raw_len": fit["raw_len"], "fit_level": fit["fit_level"],
                "protected_address_text": protected_address_text,
                "storage": "address_text_overrides.tsv" if protected_address_text else "dialogue_overrides.json"}

    def _edit_dict(self, body):
        """통일 사전 CRUD(add/edit/delete) — proper_nouns.json. DE 로직 재사용(Phase 4 잔여)."""
        action = body.get("action")
        cat = body.get("category")
        ja = (body.get("ja") or "").strip()
        with _LOCK:
            pn = DE.load_json(DE.DICT_PATH, {})
            if cat not in pn or not isinstance(pn.get(cat), list):
                if action == "add" and cat:
                    pn[cat] = []
                else:
                    return {"ok": False, "error": "category %r 없음" % cat}
            lst = pn[cat]
            if action == "add":
                if not ja:
                    return {"ok": False, "error": "ja 필요"}
                if any((e.get("ja") or "") == ja for e in lst):
                    return {"ok": False, "error": "이미 존재: %s" % ja}
                lst.append({"ja": ja, "ko": body.get("ko", ""), "edit": body.get("edit", "")})
            elif action == "edit":
                e = next((e for e in lst if (e.get("ja") or "") == ja), None)
                if not e:
                    return {"ok": False, "error": "없음: %s" % ja}
                if "ko" in body:
                    e["ko"] = body["ko"]
                if "edit" in body:
                    e["edit"] = body["edit"]
            elif action == "delete":
                pn[cat] = [e for e in lst if (e.get("ja") or "") != ja]
            else:
                return {"ok": False, "error": "unknown action"}
            if isinstance(pn.get("counts"), dict):
                pn["counts"] = {k: len(v) for k, v in pn.items() if isinstance(v, list)}
            DE.save_json(DE.DICT_PATH, pn)
        return {"ok": True}

    def _dialogue_preview(self, body):
        if DE.preview_capture is None:
            return {"ok": False, "error": "preview 엔진 비활성"}
        ja = body.get("ja") or ""
        ko = body.get("ko") or ""
        canvas = body.get("canvas") or "part2_menu"
        # canvas 검증: preview_capture가 지원하는 키만(scene.canvas는 checkpoint id가 아닌 preview 키).
        supported = set(getattr(DE.preview_capture, "CANVASES", {}).keys())
        if canvas not in supported:
            return {"ok": False, "error": "이 화면은 실캡처 미지원(canvas=%s, 지원=%s)"
                    % (canvas, ",".join(sorted(supported)) or "없음")}
        try:
            with _PREVIEW_LOCK:
                res = DE.preview_capture.compare(ja, ko, canvas=canvas)
        except Exception as e:
            return {"ok": False, "error": "캡처 실패: %r" % e}

        def url(png):
            return "/preview/" + Path(png).name
        return {"ok": True, "canvas": canvas,
                "orig": {"url": url(res["orig"]["png"]), "truncated": res["orig"]["truncated"],
                         "text": ja, "sweep": res["orig"].get("sweep")},
                "applied": {"url": url(res["applied"]["png"]), "truncated": res["applied"]["truncated"],
                            "text": ko, "sweep": res["applied"].get("sweep")}}

    def _sprite_save(self, body):
        sid = body.get("id")
        indices = body.get("indices")
        palette = body.get("palette")
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not indices or not isinstance(indices, list) or not indices[0]:
            return {"ok": False, "error": "indices(2D 0..15) 필요"}
        h = len(indices); w = len(indices[0])
        # 차원 검증(m8): 8의 배수 + 모든 행 길이 일치(빈/비정형 인코딩 차단)
        if w == 0 or h == 0 or w % 8 or h % 8:
            return {"ok": False, "error": "indices 차원 오류(8의 배수 필요): %d×%d" % (w, h)}
        if any(len(row) != w for row in indices):
            return {"ok": False, "error": "indices 행 길이 불일치"}
        try:
            enc = SE.encode_indices(indices, w, h)
        except Exception as e:
            return {"ok": False, "error": "encode: %r" % e}
        if not enc:
            return {"ok": False, "error": "인코딩 결과 0바이트"}
        if sp.get("type") == "lz77":
            fits = (len(enc) == sp.get("size"))
        else:
            fits = (len(enc) <= (sp.get("size") or len(enc)))
        key = SE.override_id(sp)
        with _LOCK:
            ov = SE.load_json(SE.OVERRIDES_PATH, {}) or {}
            ov[key] = {"offset": sp.get("offset"), "type": sp.get("type"), "width": w, "height": h,
                       "indices": indices, "palette": palette, "raw_len": len(enc),
                       "orig_size": sp.get("size"), "comp_size": sp.get("comp_size"), "fits_raw": fits}
            SE.save_json(SE.OVERRIDES_PATH, ov)
            try:
                SE.EDIT_DIR.mkdir(parents=True, exist_ok=True)
                pal = [tuple(c) for c in (palette or [list(c) for c in SE.ES.GRAYSCALE])]
                SE.ES.render_png(indices, w, h, pal, str(SE.EDIT_DIR / f"{key}.png"), scale=2)
            except Exception:
                pass
        return {"ok": True, "id": sid, "base_id": key, "raw_len": len(enc), "orig_size": sp.get("size"), "fits_raw": fits}

    def _sprite_revert(self, body):
        sid = body.get("id")
        key = SE.override_id(sid)
        with _LOCK:
            ep = SE.EDIT_DIR / f"{key}.png"
            if ep.exists():
                ep.unlink()
            ov = SE.load_json(SE.OVERRIDES_PATH, {})
            ov.pop(key, None)
            SE.save_json(SE.OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid, "base_id": key}

    def _sprite_setpalette(self, body):
        sid = body.get("id")
        palette = body.get("palette")
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not palette or not isinstance(palette, list):
            return {"ok": False, "error": "palette(16×[r,g,b]) 필요"}
        key = SE.override_id(sp)
        with _LOCK:
            ov = SE.load_json(SE.OVERRIDES_PATH, {}) or {}
            rec = ov.get(key, {})
            rec.update({"offset": sp.get("offset"), "type": sp.get("type"), "palette": palette})
            ov[key] = rec
            SE.save_json(SE.OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid, "base_id": key}


def main():
    global AUTH_PASSWORD
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8782)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--password", default=None,
                    help="웹 UI 비밀번호. 생략 시 SCENE_EDITOR_PASSWORD를 사용하고, 둘 다 없으면 인증 비활성")
    args = ap.parse_args()
    if args.password is not None:
        AUTH_PASSWORD = args.password
    srv = EditorHTTPServer((args.host, args.port), Handler)
    cov = catalog().get("coverage", {})
    print(f"통합 scene 에디터: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print("  auth: " + ("enabled" if AUTH_PASSWORD else "disabled"))
    print(f"  scenes: {len(catalog().get('scenes', []))}  "
          f"대사배정 {cov.get('dialogue_assigned')}  스프배정 {cov.get('sprites_assigned')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
