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
import hashlib
import importlib.util
import json
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
OUTPUT_ROM = ROOT / "output" / "game_wars_korean_full.gba"

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

_LOCK = threading.Lock()
_PREVIEW_LOCK = threading.Lock()

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


# ── 요구7: 바이트 예산 계산(codex 교정 — 대사 슬롯은 NUL 미포함) ──────────
def encoded_len(text: str) -> int:
    """한글=2 / 전각공백=2 / 검증 ASCII=1 / 기타=2(경고대상). dialogue slot 기준 바이트수."""
    n = 0
    s2c = syl_codes()
    for ch in text:
        if ch in s2c:
            n += 2
        elif ch == "　":
            n += 2
        elif ch == "\n":
            n += 1  # 줄바꿈 0x0A
        elif 0x20 <= ord(ch) <= 0x7E:
            n += 1
        else:
            n += 2
    return n


SAFE_MIN_ADDR = 0x800000  # build_korean_full: 이 미만(코드영역)은 override skip


def line_budget(member):
    """member의 slot 예산 + 순한글 최대 음절수 + editable(빌드 적용 가능 여부).
    빌드는 slot<=0 또는 addr<SAFE_MIN_ADDR 조각을 skip → 편집해도 미반영이라 read-only 표시."""
    slot = member.get("slot")
    try:
        addr_int = int((member.get("address") or "0x0"), 16)
    except (ValueError, TypeError):
        addr_int = 0
    if not isinstance(slot, int):
        ja = member.get("ja") or ""
        slot = len(ja) * 2  # SJIS 2바이트 추정(권위 아님)
        est = True
    else:
        est = False
    editable = (not est) and slot > 0 and addr_int >= SAFE_MIN_ADDR
    reason = ""
    if not editable:
        if est:
            reason = "슬롯 길이 미상(빌드 미적용 가능)"
        elif addr_int < SAFE_MIN_ADDR:
            reason = "코드영역 주소(<0x800000, 빌드 skip)"
        elif slot <= 0:
            reason = "슬롯 0"
    return {"slot": slot, "max_syllables": slot // 2, "estimated": est,
            "editable": editable, "reason": reason}


def member_slot(address):
    """주소 → slot 바이트 길이(없으면 None=추정 불가). dialogue_groups member 권위."""
    if "addr_slot" not in _CACHE:
        idx = {}
        for g in group_index().values():
            for m in g.get("members", []):
                a = m.get("address")
                s = m.get("slot")
                if a is not None and isinstance(s, int):
                    idx[a] = s
        _CACHE["addr_slot"] = idx
    return _CACHE["addr_slot"].get(address)


def unsupported_syllables(text):
    """2350 셋에 없는 완성형 한글(인게임 '?' 깨짐 원인)을 반환. ASCII/공백/줄바꿈은 무시."""
    s2c = syl_codes()
    bad = []
    for ch in text:
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3 and ch not in s2c and ch not in bad:
            bad.append(ch)
    return bad


def is_building():
    return _BUILD["status"] == "building"


# ── 빌드 job(비동기, 직렬화) ─────────────────────────────────────────────
_BUILD = {"status": "idle", "started": 0, "finished": 0, "log_tail": "", "error": None}
_BUILD_LOCK = threading.Lock()


def _run_build():
    import subprocess
    with _BUILD_LOCK:
        _BUILD.update(status="building", started=int(time.time()), finished=0, error=None, log_tail="")
        try:
            proc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_korean_full.py")],
                                  capture_output=True, text=True, cwd=str(ROOT), timeout=1200)
            applied = ""
            for ln in (proc.stdout or "").splitlines():
                if "스프라이트 편집 적용" in ln or "스프라이트 편집" in ln:
                    applied = ln.strip()
            _BUILD.update(status="success" if proc.returncode == 0 else "fail",
                          finished=int(time.time()),
                          log_tail=(proc.stdout or "")[-1500:],
                          error=(proc.stderr or "")[-800:] if proc.returncode != 0 else None,
                          applied=applied)
            # ROM/레이아웃 캐시 무효화(stale 방지 — codex 지적)
            SE._PATCHED = None
            SE._OBJLABELS = None
            SE._BUILD_LAYOUTS = None
            SE._LAYOUTS = None
            _CACHE.pop("sprites", None)
            _CACHE.pop("romsha_key", None)
            DE._GROUPS_CACHE = None
            _CACHE.pop("groups", None)
            _CACHE.pop("addr_slot", None)
        except Exception as e:
            _BUILD.update(status="fail", finished=int(time.time()), error=repr(e))


def start_build():
    # 경합 방지: 상태 판정+예약을 락 안에서. 이중 스레드 생성 차단.
    with _BUILD_LOCK:
        if _BUILD["status"] == "building":
            return {"ok": False, "error": "이미 빌드 중"}
        _BUILD["status"] = "building"
    threading.Thread(target=_run_build, daemon=True).start()
    return {"ok": True, "status": "building"}


def rom_state():
    if not OUTPUT_ROM.exists():
        return {"exists": False}
    st = OUTPUT_ROM.stat()
    key = ("romsha", st.st_mtime, st.st_size)
    if _CACHE.get("romsha_key") != key:
        _CACHE["romsha_key"] = key
        _CACHE["romsha"] = hashlib.sha256(OUTPUT_ROM.read_bytes()).hexdigest()
    return {"exists": True, "sha256": _CACHE["romsha"][:16], "size": st.st_size,
            "mtime": int(st.st_mtime)}


def dirty_state():
    """미빌드 편집 여부 = override 파일 mtime > ROM mtime일 때만 dirty(빌드 후 깨끗).
    개수도 함께 반환(전체 override 규모 표시용)."""
    dov = load_json(DE.OVERRIDES_PATH, {}) or {}
    sov = load_json(SE.OVERRIDES_PATH, {}) or {}
    rom_m = OUTPUT_ROM.stat().st_mtime if OUTPUT_ROM.exists() else 0
    def newer(p):
        return Path(p).exists() and Path(p).stat().st_mtime > rom_m + 1
    d_dirty = newer(DE.OVERRIDES_PATH)
    s_dirty = newer(SE.OVERRIDES_PATH)
    return {"dialogue_overrides": len(dov) if d_dirty else 0,
            "sprite_overrides": len(sov) if s_dirty else 0,
            "dialogue_total": len(dov), "sprite_total": len(sov),
            "dirty": bool(d_dirty or s_dirty)}


# ── scene 항목 조회 ──────────────────────────────────────────────────────
def scene_items(scene, want="all"):
    gi = group_index()
    si = sprite_index()
    dov = load_json(DE.OVERRIDES_PATH, {}) or {}
    out_d, out_s = [], []
    if want in ("all", "dialogue"):
        for gid in scene.get("dialogue_ids", []):
            g = gi.get(gid)
            if not g:
                continue
            members = []
            for m in g.get("members", []):
                ko = dov.get(m.get("address"), m.get("ko") or "")
                members.append({"address": m.get("address"), "ja": m.get("ja"), "ko": ko,
                                "kind": m.get("kind"), "budget": line_budget(m)})
            out_d.append({"group_id": gid, "region": g.get("region"), "size": g.get("size"),
                          "flagged": g.get("flagged"), "assembled_ja": g.get("assembled_ja"),
                          "segments": g.get("segments"), "members": members})
    if want in ("all", "sprite"):
        for sid in scene.get("sprite_ids", []):
            sp = si.get(sid)
            if not sp:
                continue
            is_text, desc = SE.classify_sprite(sp.get("source"))
            out_s.append({"id": sid, "source": sp.get("source"), "type": sp.get("type"),
                          "offset": sp.get("offset"), "desc": desc, "is_text": is_text,
                          "has_onscreen": SE.get_layout(sid) is not None})
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
        out.append({k: sc[k] for k in ("id", "order", "scope", "subtag", "title",
                                       "canvas", "canvas_status", "counts") if k in sc})
    out.sort(key=lambda s: s.get("order", 0))
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    # ── GET ──
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p in ("/", "/index.html"):
            return self._static("index.html")
        if p.startswith("/static/"):
            return self._static(p[len("/static/"):])
        if p == "/api/state":
            return self._send(200, {"rom": rom_state(), "dirty": dirty_state(),
                                    "build": {k: _BUILD[k] for k in ("status", "started", "finished")}})
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
                                    "subtag": sc.get("subtag"), "canvas": sc.get("canvas"),
                                    "canvas_status": sc.get("canvas_status"),
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
            return self._send(200, {k: _BUILD[k] for k in ("status", "started", "finished", "log_tail", "error")})
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
        self._send(200, path.read_bytes(), MIME.get(path.suffix, "application/octet-stream"))

    def _serve_preview(self, name):
        pdir = DE.PREVIEW_DIR
        pdir.mkdir(parents=True, exist_ok=True)
        safe = (pdir / name).resolve()
        if pdir.resolve() not in safe.parents or safe.suffix != ".png" or not safe.exists():
            return self._send(404, {"error": "no preview"})
        self._send(200, safe.read_bytes(), "image/png")

    # 스프라이트 핸들러 재사용: SE의 Handler 메서드 바디를 모듈 함수로 호출
    def _sprite_proxy(self, kind, q):
        sid = q.get("id", [""])[0]
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return self._send(404, {"error": "id 없음: %s" % sid})
        if kind == "tile":
            return self._send(200, self._tile_data(sid, sp))
        if kind == "compare":
            return self._send(200, self._compare_data(sid, sp))
        if kind == "onscreen_data":
            return self._send(200, self._onscreen_data(sid, sp))

    def _tile_data(self, sid, sp):
        ov = load_json(SE.OVERRIDES_PATH, {}) or {}
        rec = ov.get(sid)
        desc = SE.classify_sprite(sp.get("source"))[1]
        has_os = SE.get_layout(sid) is not None
        if rec and rec.get("indices"):
            grid = rec["indices"]; h = len(grid); w = len(grid[0]) if grid else 0
            return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": w // 8,
                    "type": sp.get("type"), "palette": SE.palette_for(sp), "indices": grid,
                    "edited": True, "offset": sp.get("offset"), "source": sp.get("source"),
                    "desc": desc, "has_onscreen": has_os}
        dec = SE.decode_indices(sp)
        if dec is None:
            return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
        grid, w, h, cols = dec
        return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                "type": sp.get("type"), "palette": SE.palette_for(sp), "indices": grid,
                "edited": False, "offset": sp.get("offset"), "source": sp.get("source"),
                "desc": desc, "has_onscreen": has_os}

    def _compare_data(self, sid, sp):
        o = SE.decode_from_rom(SE.rom_bytes(), sp)
        pat = SE.decode_from_rom(SE.patched_bytes(), sp) if SE.patched_bytes() else None
        changed = (o and pat and o[0] != pat[0])
        ov = load_json(SE.OVERRIDES_PATH, {}) or {}
        has_edit = sid in ov and bool(ov[sid].get("indices"))
        qid = urllib.parse.quote(sid)
        return {"ok": True, "id": sid, "offset": sp.get("offset"), "type": sp.get("type"),
                "source": sp.get("source"),
                "orig_url": "/api/sprite/render?id=%s&which=orig" % qid,
                "patched_url": ("/api/sprite/render?id=%s&which=patched" % qid) if pat else None,
                "edit_url": ("/api/sprite/render?id=%s&which=edit" % qid) if has_edit else None,
                "build_changed": bool(changed), "has_edit": has_edit}

    def _onscreen_data(self, sid, sp):
        import struct as _s
        from collections import Counter
        lay = SE.get_layout(sid)
        if not lay:
            return {"ok": False, "error": "no layout for %s" % sid}
        dec = SE.decode_indices(sp)
        cols = dec[3] if dec else (sp.get("tile_cols") or 1)
        palp = lay.get("pal_file")
        if palp and (ROOT / palp).exists():
            palb = (ROOT / palp).read_bytes()
            dom = Counter((c.get("palbase", 256), c["bank"]) for c in lay["cells"]).most_common(1)[0][0]
            palbase, bank = dom

            def col(i):
                v = _s.unpack("<H", palb[i * 2:i * 2 + 2])[0]
                return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31]
            palette = [col(palbase + bank * 16 + i) for i in range(16)]
        else:
            palette = [list(c) for c in SE.palette_for(sp)]
        return {"ok": True, "w": lay["w"], "h": lay["h"], "x0": lay["x0"], "y0": lay["y0"],
                "obj1d": lay.get("obj1d", 1), "tile_cols": cols, "cells": lay["cells"],
                "palette": palette, "screen": lay.get("screen"), "build": lay.get("build", False)}

    def _sprite_render(self, q):
        sid = q.get("id", [""])[0]
        which = q.get("which", ["orig"])[0]
        if which not in ("orig", "patched", "edit"):
            return self._send(400, {"error": "which=orig|patched|edit"})
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
        if not OUTPUT_ROM.exists():
            return self._send(404, {"error": "output ROM 없음 — 먼저 빌드하세요"})
        data = OUTPUT_ROM.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", 'attachment; filename="game_wars_korean_full.gba"')
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
        if p == "/api/dialogue/line":
            return self._send(200, self._save_line(body))
        if p == "/api/dialogue/preview":
            return self._send(200, self._dialogue_preview(body))
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
        if not addr:
            return {"ok": False, "error": "address 필요"}
        if is_building():
            return {"ok": False, "error": "빌드 중 — 완료 후 저장하세요"}
        # 빌드 미적용(코드영역/슬롯미상) 조각 차단 — 편집해도 ROM 미반영
        try:
            addr_int = int(addr, 16)
        except (ValueError, TypeError):
            addr_int = 0
        if addr_int < SAFE_MIN_ADDR:
            return {"ok": False, "error": "코드영역 주소(<0x800000) — 빌드 미적용, 편집 불가"}
        # 서버측 하드게이트(클라 우회/오차 방어): 슬롯 초과·미수록 음절 차단
        bad = unsupported_syllables(ko)
        if bad:
            return {"ok": False, "error": "폰트 미수록 음절(인게임 ‘?’): " + "".join(bad), "unsupported": bad}
        slot = member_slot(addr)
        elen = encoded_len(ko)
        if isinstance(slot, int) and elen > slot:
            return {"ok": False, "error": "슬롯 초과 %dB>%dB" % (elen, slot), "over": True,
                    "encoded_len": elen, "slot": slot}
        with _LOCK:
            ov = DE.load_json(DE.OVERRIDES_PATH, {}) or {}
            ov[addr] = ko
            DE.save_json(DE.OVERRIDES_PATH, ov)
            # dialogue_map.json의 ko도 동기(편집 표시 일관)
            data = DE.load_json(DE.DIALOGUE_PATH, {"lines": []})
            for ln in data.get("lines", []):
                if ln.get("address") == addr:
                    ln["ko"] = ko
            DE.save_json(DE.DIALOGUE_PATH, data)
        return {"ok": True, "address": addr, "ko": ko, "encoded_len": encoded_len(ko)}

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
                "orig": {"url": url(res["orig"]["png"]), "truncated": res["orig"]["truncated"], "text": ja},
                "applied": {"url": url(res["applied"]["png"]), "truncated": res["applied"]["truncated"], "text": ko}}

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
        try:
            enc = SE.encode_indices(indices, w, h)
        except Exception as e:
            return {"ok": False, "error": "encode: %r" % e}
        if sp.get("type") == "lz77":
            fits = (len(enc) == sp.get("size"))
        else:
            fits = (len(enc) <= (sp.get("size") or len(enc)))
        with _LOCK:
            ov = SE.load_json(SE.OVERRIDES_PATH, {}) or {}
            ov[sid] = {"offset": sp.get("offset"), "type": sp.get("type"), "width": w, "height": h,
                       "indices": indices, "palette": palette, "raw_len": len(enc),
                       "orig_size": sp.get("size"), "comp_size": sp.get("comp_size"), "fits_raw": fits}
            SE.save_json(SE.OVERRIDES_PATH, ov)
            try:
                SE.EDIT_DIR.mkdir(parents=True, exist_ok=True)
                pal = [tuple(c) for c in (palette or [list(c) for c in SE.ES.GRAYSCALE])]
                SE.ES.render_png(indices, w, h, pal, str(SE.EDIT_DIR / f"{sid}.png"), scale=2)
            except Exception:
                pass
        return {"ok": True, "id": sid, "raw_len": len(enc), "orig_size": sp.get("size"), "fits_raw": fits}

    def _sprite_revert(self, body):
        sid = body.get("id")
        with _LOCK:
            ep = SE.EDIT_DIR / f"{sid}.png"
            if ep.exists():
                ep.unlink()
            ov = SE.load_json(SE.OVERRIDES_PATH, {})
            ov.pop(sid, None)
            SE.save_json(SE.OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid}

    def _sprite_setpalette(self, body):
        sid = body.get("id")
        palette = body.get("palette")
        sp = SE.sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not palette or not isinstance(palette, list):
            return {"ok": False, "error": "palette(16×[r,g,b]) 필요"}
        with _LOCK:
            ov = SE.load_json(SE.OVERRIDES_PATH, {}) or {}
            rec = ov.get(sid, {})
            rec.update({"offset": sp.get("offset"), "type": sp.get("type"), "palette": palette})
            ov[sid] = rec
            SE.save_json(SE.OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8782)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    cov = catalog().get("coverage", {})
    print(f"통합 scene 에디터: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print(f"  scenes: {len(catalog().get('scenes', []))}  "
          f"대사배정 {cov.get('dialogue_assigned')}  스프배정 {cov.get('sprites_assigned')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
