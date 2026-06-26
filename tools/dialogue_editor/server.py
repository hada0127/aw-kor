#!/usr/bin/env python3
"""대사 편집기 — 경량 웹도구 (stdlib http.server, 외부 의존성 없음).

muramasa-kor tools/ui_editor 패턴 참조. aw-kor 대사 원문(JA)→한글(KO) 편집 +
통일 사전(proper_nouns.json) 조회/추가/수정/삭제 + 대사의 고유명사 일치 검사.

실행:
  python3 tools/dialogue_editor/server.py            # http://127.0.0.1:8780
  python3 tools/dialogue_editor/server.py --port 9100

데이터:
  data/dialogue_map.json   {meta, lines:[{id,address,ja,ko,slot,region,is_noise}]}
  data/proper_nouns.json   {characters/nations/places/common_terms:[{ja,ko,edit,...}]}

편집 저장:
  대사 ko 수정 → dialogue_map.json 갱신 + data/dialogue_overrides.json(address→ko) 누적(빌드 통합용).
  사전 수정 → proper_nouns.json 갱신.

API
  GET  /api/dialogue?region=&q=&filter=        대사 목록(필터)
  GET  /api/dict                               통일 사전
  POST /api/line     {id, ko}                  대사 ko 저장
  POST /api/dict     {action, category, ja, ko, edit}  사전 CRUD
  POST /api/check    {id} | {ja, ko}           한 대사의 사전 일치 검사
  GET  /api/check_all                          전체 대사 사전 불일치 목록
"""
import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
DIALOGUE_PATH = ROOT / "data" / "dialogue_map.json"
DICT_PATH = ROOT / "data" / "proper_nouns.json"
OVERRIDES_PATH = ROOT / "data" / "dialogue_overrides.json"
GROUPS_PATH = ROOT / "data" / "dialogue_groups.json"
_GROUPS_CACHE = None


def load_groups():
    """조립 그룹(대사 조각→인게임 메시지). 1회 로드 캐시(재생성: tools/build_dialogue_groups.py)."""
    global _GROUPS_CACHE
    if _GROUPS_CACHE is None:
        _GROUPS_CACHE = load_json(GROUPS_PATH, {"groups": []})
    return _GROUPS_CACHE

sys.path.insert(0, str(ROOT / "tools"))
try:
    import preview_capture  # 실캡처 엔진(canvas-hijack)
except Exception as _e:  # PIL/하네스 부재 시 미리보기 비활성
    preview_capture = None
    _PREVIEW_ERR = repr(_e)
try:
    import build_korean_full as B
except Exception:
    B = None

_LOCK = threading.Lock()
_PREVIEW_LOCK = threading.Lock()  # mgbah 캡처 직렬화(하네스 로그/리소스 공유)
PREVIEW_DIR = ROOT / "temp" / "preview_cache"
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png"}


def pick_canvas(line):
    """대사 라인의 region/kind → 실캡처 canvas 선택. (현재 part2_menu 단일; 확장 예정)"""
    return "part2_menu"


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_BTEAM_CACHE = None


def is_bteam(address):
    """주소가 쪼롱이님(B팀) 권위 주소인가(사전 경고 배지용). resolved 3340 집합."""
    global _BTEAM_CACHE
    if _BTEAM_CACHE is None:
        _BTEAM_CACHE = set(load_json(ROOT / "data" / "bteam_addresses.json", {}).get("addresses", []))
    if not address:
        return False
    try:
        return ("0x%08X" % int(str(address), 16)) in _BTEAM_CACHE
    except (ValueError, TypeError):
        return False


def dict_categories(d):
    """proper_nouns.json에서 카테고리별 리스트 키를 반환(리스트 값만)."""
    return [k for k, v in d.items() if isinstance(v, list)]


def dict_entries(d):
    """(category, entry) 평탄화."""
    for cat in dict_categories(d):
        for e in d[cat]:
            yield cat, e


def effective_ko(entry):
    return (entry.get("edit") or "").strip() or (entry.get("ko") or "").strip()


def is_address_text_override(address):
    if not B:
        return False
    try:
        return int(str(address), 16) in B.ADDRESS_TEXT_OVERRIDES
    except (ValueError, TypeError):
        return False


def canon_addr(address):
    try:
        return "0x%08X" % int(str(address or "").strip(), 16)
    except (ValueError, TypeError):
        return None


def check_line(line, pn):
    """대사 한 줄을 사전과 대조. ja에 사전 항목의 ja가 들어 있으면 ko에 사전 ko가 있어야 한다."""
    ja = line.get("ja") or ""
    ko = line.get("ko") or ""
    issues = []
    for cat, e in dict_entries(pn):
        eja = (e.get("ja") or "").strip()
        eko = effective_ko(e)
        if not eja or not eko:
            continue
        if eja in ja and eko not in ko:
            issues.append({"category": cat, "ja": eja, "expected_ko": eko})
    return issues


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

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/" or u.path == "/index.html":
            return self._serve_static("index.html")
        if u.path.startswith("/static/"):
            return self._serve_static(u.path[len("/static/"):])
        if u.path == "/api/dialogue":
            return self._send(200, self._dialogue(q))
        if u.path == "/api/dict":
            return self._send(200, load_json(DICT_PATH, {}))
        if u.path == "/api/check_all":
            return self._send(200, self._check_all())
        if u.path.startswith("/preview/"):
            return self._serve_preview(u.path[len("/preview/"):])
        if u.path == "/api/groups":
            return self._send(200, self._groups(q))
        return self._send(404, {"error": "not found"})

    def _groups(self, q):
        """조립 그룹 목록. 섹션 필터 + 멤버별 live ko(overrides 우선). 인게임(주소) 순."""
        gd = load_groups()
        groups = gd.get("groups", [])
        section = (q.get("section", [""])[0] or "").strip()
        qstr = (q.get("q", [""])[0] or "").strip()
        only_multi = (q.get("multi", [""])[0] or "") == "1"
        SEC2REG = {"common": "other", "part1": "part1", "part2": "part2"}
        want_reg = SEC2REG.get(section)
        ov = load_json(OVERRIDES_PATH, {}) or {}
        dialogue_lines = load_json(DIALOGUE_PATH, {"lines": []}).get("lines", [])
        by_addr = {
            canon_addr(ln.get("address")): ln
            for ln in dialogue_lines
            if canon_addr(ln.get("address"))
        }
        out = []
        for g in groups:
            if want_reg and g.get("region") != want_reg:
                continue
            if only_multi and g.get("size", 1) < 2:
                continue
            members = []
            for m in g.get("members", []):
                addr = canon_addr(m.get("address")) or m.get("address")
                canonical = by_addr.get(addr) or {}
                member = {**m}
                if canonical:
                    member.update({
                        "id": canonical.get("id"),
                        "slot": canonical.get("slot", member.get("slot")),
                        "kind": canonical.get("kind", member.get("kind")),
                        "ship_ko": canonical.get("ship_ko", member.get("ship_ko")),
                    })
                base_ko = canonical.get("ko", m.get("ko") or "")
                ko = base_ko if is_address_text_override(addr) else ov.get(addr, base_ko)
                members.append({**member, "address": addr, "ko": ko, "bteam": is_bteam(addr)})
            if qstr and qstr not in (g.get("assembled_ja") or "") and \
               all(qstr not in (m.get("ko") or "") for m in members):
                continue
            out.append({"group_id": g.get("group_id"), "region": g.get("region"),
                        "size": g.get("size"), "flagged": g.get("flagged"),
                        "assembled_ja": g.get("assembled_ja"), "segments": g.get("segments"),
                        "members": members})
        return {"meta": gd.get("meta", {}), "count": len(out),
                "total": len(groups), "lines": out[:1500]}

    def _serve_preview(self, name):
        # temp/preview_cache 내 PNG만 제공(경로 탈출 방지)
        safe = (PREVIEW_DIR / name).resolve()
        if PREVIEW_DIR.resolve() not in safe.parents or safe.suffix != ".png" or not safe.exists():
            return self._send(404, {"error": "no preview"})
        self._send(200, safe.read_bytes(), "image/png")

    def _serve_static(self, rel):
        path = (STATIC / rel).resolve()
        if STATIC not in path.parents and path != STATIC / rel:
            return self._send(403, {"error": "forbidden"})
        if not path.exists():
            return self._send(404, {"error": "missing " + rel})
        ctype = MIME.get(path.suffix, "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)

    def _dialogue(self, q):
        data = load_json(DIALOGUE_PATH, {"lines": []})
        lines = data.get("lines", [])
        _ov = load_json(OVERRIDES_PATH, {}) or {}  # 편집/채움 번역을 즉시 반영(line view)
        if _ov:
            for ln in lines:
                a = ln.get("address")
                if a in _ov and _ov[a] and not is_address_text_override(a):
                    ln["ko"] = _ov[a]
        region = (q.get("region", [""])[0] or "").strip()
        # 허브 섹션(공통/1편/2편)→region 매핑
        section = (q.get("section", [""])[0] or "").strip()
        SEC2REG = {"common": "other", "part1": "part1", "part2": "part2"}
        if section in SEC2REG:
            region = SEC2REG[section]
        qstr = (q.get("q", [""])[0] or "").strip()
        filt = (q.get("filter", [""])[0] or "").strip()
        pn = load_json(DICT_PATH, {}) if filt == "mismatch" else None
        out = []
        for ln in lines:
            if region and ln.get("region") != region:
                continue
            if filt == "noise" and not ln.get("is_noise"):
                continue
            if filt == "real" and ln.get("is_noise"):
                continue
            if filt == "untranslated" and (ln.get("ko") or "").strip() and (ln.get("ko") != ln.get("ja")):
                continue
            if qstr and qstr not in (ln.get("ja") or "") and qstr not in (ln.get("ko") or ""):
                continue
            if filt == "mismatch":
                if not check_line(ln, pn):
                    continue
            out.append(ln)
        # 인게임 출력 순서 근사: ROM 주소순(저장=스크립트 순서에 근접)
        def _addr(l):
            try:
                return int((l.get("address") or "0x0"), 16)
            except Exception:
                return 0
        out.sort(key=_addr)
        return {"meta": data.get("meta", {}), "count": len(out), "total": len(lines),
                "regions": sorted({l.get("region", "") for l in lines}), "lines": out[:2000]}

    def _check_all(self):
        data = load_json(DIALOGUE_PATH, {"lines": []})
        pn = load_json(DICT_PATH, {})
        res = []
        for ln in data.get("lines", []):
            if ln.get("is_noise"):
                continue
            iss = check_line(ln, pn)
            if iss:
                res.append({"id": ln.get("id"), "address": ln.get("address"),
                            "ja": ln.get("ja"), "ko": ln.get("ko"), "issues": iss,
                            "bteam": is_bteam(ln.get("address"))})
        return {"count": len(res), "mismatches": res[:1000]}

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"error": "bad json: %r" % e})
        if u.path == "/api/line":
            return self._send(200, self._save_line(body))
        if u.path == "/api/dict":
            return self._send(200, self._edit_dict(body))
        if u.path == "/api/check":
            return self._send(200, self._check_one(body))
        if u.path == "/api/preview":
            return self._send(200, self._preview(body))
        return self._send(404, {"error": "not found"})

    def _preview(self, body):
        """대사 한 줄의 원본(JA)↔적용(KO) 실캡처. body={id, ko?(라이브 편집값), canvas?}."""
        if preview_capture is None:
            return {"ok": False, "error": "preview 엔진 비활성: %s" % _PREVIEW_ERR}
        lid = body.get("id")
        data = load_json(DIALOGUE_PATH, {"lines": []})
        ln = next((l for l in data.get("lines", []) if l.get("id") == lid), None)
        if not ln:
            return {"ok": False, "error": "id %r 없음" % lid}
        ja = ln.get("ja") or ""
        ko = body.get("ko") if body.get("ko") is not None else (ln.get("ko") or "")
        canvas = body.get("canvas") or pick_canvas(ln)
        try:
            with _PREVIEW_LOCK:
                res = preview_capture.compare(ja, ko, canvas=canvas)
        except Exception as e:
            return {"ok": False, "error": "캡처 실패: %r" % e}

        def url(png):
            return "/preview/" + Path(png).name
        return {"ok": True, "id": lid, "canvas": canvas,
                "orig": {"url": url(res["orig"]["png"]), "truncated": res["orig"]["truncated"], "text": ja},
                "applied": {"url": url(res["applied"]["png"]), "truncated": res["applied"]["truncated"], "text": ko}}

    def _save_line(self, body):
        lid = body.get("id")
        ko = body.get("ko", "")
        with _LOCK:
            data = load_json(DIALOGUE_PATH, {"lines": []})
            addr = canon_addr(body.get("address"))
            if addr:
                hit = next((ln for ln in data.get("lines", []) if canon_addr(ln.get("address")) == addr), None)
            else:
                hit = next((ln for ln in data.get("lines", []) if ln.get("id") == lid), None)
            if hit is None:
                key = addr or ("id %r" % lid)
                return {"ok": False, "error": "%s 없음" % key}
            # B팀(쪼롱이) 권위 주소 save-time 보호 — 변형(ln["ko"]=ko) **전에** 검사(codex 순서지적 반영).
            addr = canon_addr(hit.get("address"))
            if is_address_text_override(addr):
                return {"ok": False, "error": "빌드 안전 ADDRESS_TEXT_OVERRIDES 보호 주소 — 편집기 override 미적용, 편집 불가"}
            if addr and not body.get("confirm_bteam"):
                try:
                    _bt = set(load_json(ROOT / "data" / "bteam_addresses.json", {}).get("addresses", []))
                    if ("0x%08X" % int(addr, 16)) in _bt:
                        _base = (load_json(ROOT / "data" / "bteam_baseline.json", {}).get("overrides") or {}
                                 ).get("0x%08X" % int(addr, 16))
                        return {"ok": False, "bteam_confirm_required": True,
                                "error": "쪼롱이님(B팀) 권위 주소. confirm_bteam=true로 재전송하세요.",
                                "bteam_baseline": _base}
                except (ValueError, TypeError):
                    pass
            check_target = {**hit, "ko": ko}
            if body.get("dry_run"):
                return {"ok": True, "dry_run": True, "id": hit.get("id"), "address": addr,
                        "ko": ko, "check": check_line(check_target, load_json(DICT_PATH, {}))}
            hit["ko"] = ko   # 검사 통과 후에만 변형
            save_json(DIALOGUE_PATH, data)
            ov = load_json(OVERRIDES_PATH, {})
            if addr:
                ov[addr] = ko
                save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": lid, "ko": ko, "check": check_line(hit, load_json(DICT_PATH, {}))}

    def _edit_dict(self, body):
        action = body.get("action")
        cat = body.get("category")
        ja = (body.get("ja") or "").strip()
        with _LOCK:
            pn = load_json(DICT_PATH, {})
            if cat not in pn or not isinstance(pn.get(cat), list):
                if action == "add" and cat:
                    pn[cat] = []
                else:
                    return {"ok": False, "error": "category %r 없음" % cat}
            lst = pn[cat]
            if action == "add":
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
            save_json(DICT_PATH, pn)
        return {"ok": True}

    def _check_one(self, body):
        if "id" in body:
            data = load_json(DIALOGUE_PATH, {"lines": []})
            ln = next((l for l in data.get("lines", []) if l.get("id") == body["id"]), None)
            if not ln:
                return {"ok": False, "error": "id 없음"}
        else:
            ln = {"ja": body.get("ja", ""), "ko": body.get("ko", "")}
        return {"ok": True, "issues": check_line(ln, load_json(DICT_PATH, {}))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"대사 편집기: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print(f"  dialogue: {DIALOGUE_PATH}  dict: {DICT_PATH}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
