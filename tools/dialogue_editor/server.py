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
  GET  /api/dict                               통일 사전(정규화 필드 포함)
  POST /api/line     {id, ko}                  대사 ko 저장
  POST /api/dict     {action, category, key/source/current/canonical}  사전 CRUD
  POST /api/check    {id} | {ja, ko}           한 대사의 사전 일치 검사
  GET  /api/check_all                          전체 대사 사전 불일치 목록
"""
import argparse
import collections
import csv
import hmac
import html
import json
import os
import secrets
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
ADDRESS_TEXT_OVERRIDES_TSV = ROOT / "data" / "address_text_overrides.tsv"
SYLCODE = ROOT / "data" / "syllable_to_code_2350.json"
EDITOR_PASSWORD_FILE = ROOT / "temp" / "editor_password.txt"


def resolve_editor_password(*env_names):
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return value
    if EDITOR_PASSWORD_FILE.exists():
        return EDITOR_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    password = secrets.token_urlsafe(12)
    EDITOR_PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    EDITOR_PASSWORD_FILE.write_text(password + "\n", encoding="utf-8")
    return password


AUTH_COOKIE = "aw_dialogue_editor_auth"
AUTH_PASSWORD = resolve_editor_password("DIALOGUE_EDITOR_PASSWORD", "AW_EDITOR_PASSWORD")
AUTH_TOKEN = secrets.token_urlsafe(32)
_GROUPS_CACHE = None
_SYL_CACHE = None
_SYL_INT_CACHE = None
_BUILD_SLOTS_CACHE = None


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
try:
    import text_metrics as TM
except Exception:
    TM = None

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
    """주소가 짜옹이님(B팀) 권위 주소인가(사전 경고 배지용). resolved 3340 집합."""
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


DICT_EDITABLE_CATEGORIES = {
    "characters",
    "nations",
    "places",
    "discovered_candidates",
    "common_terms",
}
DICT_READONLY_CATEGORIES = {"issues"}


def dict_entries(d, *, include_readonly=False):
    """(category, entry) 평탄화."""
    for cat in dict_categories(d):
        if not include_readonly and cat in DICT_READONLY_CATEGORIES:
            continue
        for e in d[cat]:
            yield cat, e


def _norm(s):
    return (s or "").strip()


def dict_entry_key(category, entry):
    if category == "common_terms":
        note = _norm(entry.get("ja_note"))
        term = _norm(entry.get("term"))
        if note == "(build TERM_NORMALIZATION)" and term:
            return "\x1f".join([note, term])
        return note or term
    if category == "issues":
        return "\x1f".join([_norm(entry.get("ja")), _norm(entry.get("chosen_ko"))])
    return _norm(entry.get("ja"))


def dict_entry_source(category, entry):
    if category == "common_terms":
        note = _norm(entry.get("ja_note"))
        term = _norm(entry.get("term"))
        if note == "(build TERM_NORMALIZATION)" and "->" in term:
            return term.split("->", 1)[0].strip()
        return note or term
    return _norm(entry.get("ja")) or _norm(entry.get("ja_note")) or _norm(entry.get("term"))


def dict_entry_current(category, entry):
    if category == "common_terms":
        return _norm(entry.get("current"))
    if category == "issues":
        other = entry.get("other_ko") or {}
        if isinstance(other, dict):
            return "/".join(str(k) for k in other if _norm(k))
        return ""
    return _norm(entry.get("ko")) or _norm(entry.get("current"))


def effective_ko(entry, category=None):
    if category == "common_terms":
        return (_norm(entry.get("edit")) or _norm(entry.get("ko")) or
                _norm(entry.get("current")) or _norm(entry.get("term")))
    if category == "issues":
        return _norm(entry.get("edit")) or _norm(entry.get("chosen_ko")) or _norm(entry.get("ko"))
    return _norm(entry.get("edit")) or _norm(entry.get("ko")) or _norm(entry.get("chosen_ko"))


def dict_entry_expected_terms(category, entry):
    canonical = effective_ko(entry, category)
    terms = [t.strip() for t in canonical.split("/") if t.strip()] if category == "common_terms" else [canonical]
    allowed = entry.get("allowed") or entry.get("allowed_ko") or {}
    if isinstance(allowed, dict):
        terms.extend(_norm(k) for k in allowed)
    elif isinstance(allowed, list):
        terms.extend(_norm(v) for v in allowed)
    out = []
    for term in terms:
        if term and term not in out:
            out.append(term)
    return out


def dict_entry_note(category, entry):
    parts = []
    if category == "common_terms":
        term = _norm(entry.get("term"))
        if "->" in term:
            parts.append("치환 규칙: " + term)
    for field in ("note", "hint"):
        value = _norm(entry.get(field))
        if value:
            parts.append(value)
    variants = entry.get("variants") or entry.get("other_ko") or {}
    if isinstance(variants, dict) and variants:
        parts.append("관측: " + ", ".join(f"{k}({v})" for k, v in variants.items()))
    allowed = entry.get("allowed") or entry.get("allowed_ko") or {}
    if isinstance(allowed, dict) and allowed:
        parts.append("허용: " + ", ".join(f"{k}({v})" for k, v in allowed.items()))
    elif isinstance(allowed, list) and allowed:
        parts.append("허용: " + ", ".join(str(v) for v in allowed))
    return " · ".join(parts)


def normalized_dict_entry(category, entry):
    out = dict(entry)
    source = dict_entry_source(category, entry)
    current = dict_entry_current(category, entry)
    canonical = effective_ko(entry, category)
    readonly = category in DICT_READONLY_CATEGORIES
    if readonly:
        status = "검토 이슈"
    elif not source:
        status = "원문 없음"
    elif not canonical:
        status = "미확정"
    elif _norm(entry.get("edit")):
        status = "수동 확정"
    elif category == "common_terms":
        status = "치환 규칙"
    else:
        status = "기본 확정"
    out.update({
        "_key": dict_entry_key(category, entry),
        "_source": source,
        "_current": current,
        "_canonical": canonical,
        "_status": status,
        "_note": dict_entry_note(category, entry),
        "_readonly": readonly,
    })
    return out


def normalize_dict_payload(pn):
    out = {}
    for key, value in (pn or {}).items():
        if isinstance(value, list):
            out[key] = [normalized_dict_entry(key, e) for e in value if isinstance(e, dict)]
        else:
            out[key] = value
    out["_schema"] = {
        "source": "원문/출처(JA)",
        "current": "현재/관측 표기 또는 치환 대상",
        "canonical": "확정 표기(KO) - UI에서 편집하는 단일 최종값",
        "readonly_categories": sorted(DICT_READONLY_CATEGORIES),
    }
    return out


def dict_response(pn=None):
    return normalize_dict_payload(pn if pn is not None else load_json(DICT_PATH, {}))


def _find_dict_entry(entries, category, body):
    key = _norm(body.get("key") or body.get("_key"))
    if key:
        hit = next((e for e in entries if dict_entry_key(category, e) == key), None)
        if hit:
            return hit
    source = _norm(body.get("source") or body.get("ja"))
    if category == "common_terms":
        return next((e for e in entries
                     if _norm(e.get("ja_note")) == source), None)
    if category == "issues":
        canonical = _norm(body.get("canonical") or body.get("chosen_ko") or body.get("edit"))
        return next((e for e in entries
                     if _norm(e.get("ja")) == source and (
                         not canonical or effective_ko(e, category) == canonical)), None)
    return next((e for e in entries if _norm(e.get("ja")) == source), None)


def _make_dict_entry(category, body):
    source = _norm(body.get("source") or body.get("ja"))
    current = _norm(body.get("current") if "current" in body else body.get("ko"))
    canonical = _norm(body.get("canonical") if "canonical" in body else body.get("edit"))
    if not source:
        return None, "원문/출처 필요"
    if category in DICT_READONLY_CATEGORIES:
        return None, "%s 카테고리는 자동 검토 결과라 직접 추가할 수 없습니다" % category
    if category == "common_terms":
        if not canonical:
            return None, "common_terms에는 확정 표기 필요"
        label = canonical or current or source
        return {"term": label, "ja_note": source, "current": current, "edit": canonical}, None
    base_ko = current or canonical
    if not base_ko:
        return None, "현재/확정 표기 필요"
    entry = {"ja": source, "ko": base_ko, "edit": ""}
    if canonical and canonical != base_ko:
        entry["edit"] = canonical
    return entry, None


def edit_dict_payload(body):
    action = body.get("action")
    cat = body.get("category")
    with _LOCK:
        pn = load_json(DICT_PATH, {})
        if cat not in DICT_EDITABLE_CATEGORIES and cat not in DICT_READONLY_CATEGORIES:
            return {"ok": False, "error": "category %r 편집 불가" % cat}
        if cat in DICT_READONLY_CATEGORIES and action != "delete":
            return {"ok": False, "error": "%s 카테고리는 자동 검토 결과라 직접 편집할 수 없습니다" % cat}
        if cat not in pn or not isinstance(pn.get(cat), list):
            if action == "add" and cat in DICT_EDITABLE_CATEGORIES:
                pn[cat] = []
            else:
                return {"ok": False, "error": "category %r 없음" % cat}
        lst = pn[cat]
        if action == "add":
            entry, error = _make_dict_entry(cat, body)
            if error:
                return {"ok": False, "error": error}
            if any(dict_entry_key(cat, e) == dict_entry_key(cat, entry) for e in lst):
                return {"ok": False, "error": "이미 존재: %s" % dict_entry_source(cat, entry)}
            lst.append(entry)
        elif action == "edit":
            e = _find_dict_entry(lst, cat, body)
            if not e:
                return {"ok": False, "error": "항목 없음"}
            if cat == "common_terms":
                if "source" in body or "ja" in body:
                    e["ja_note"] = _norm(body.get("source") or body.get("ja"))
                if "current" in body or "ko" in body:
                    e["current"] = _norm(body.get("current") if "current" in body else body.get("ko"))
                if "canonical" in body or "edit" in body:
                    e["edit"] = _norm(body.get("canonical") if "canonical" in body else body.get("edit"))
            else:
                if "source" in body or "ja" in body:
                    e["ja"] = _norm(body.get("source") or body.get("ja"))
                if "current" in body or "ko" in body:
                    e["ko"] = _norm(body.get("current") if "current" in body else body.get("ko"))
                if "canonical" in body or "edit" in body:
                    canonical = _norm(body.get("canonical") if "canonical" in body else body.get("edit"))
                    e["edit"] = "" if canonical == _norm(e.get("ko")) else canonical
        elif action == "delete":
            e = _find_dict_entry(lst, cat, body)
            if not e:
                return {"ok": False, "error": "항목 없음"}
            if cat in DICT_READONLY_CATEGORIES:
                return {"ok": False, "error": "%s 카테고리는 자동 검토 결과라 삭제할 수 없습니다" % cat}
            pn[cat] = [x for x in lst if x is not e]
        else:
            return {"ok": False, "error": "unknown action"}
        if isinstance(pn.get("counts"), dict):
            pn["counts"] = {k: len(v) for k, v in pn.items() if isinstance(v, list)}
        save_json(DICT_PATH, pn)
    return {"ok": True, "dict": dict_response(pn)}


def is_address_text_override(address):
    addr = canon_addr(address)
    return bool(addr and addr in address_text_overrides())


def canon_addr(address):
    try:
        return "0x%08X" % int(str(address or "").strip(), 16)
    except (ValueError, TypeError):
        return None


def address_text_overrides():
    rows = {}
    if ADDRESS_TEXT_OVERRIDES_TSV.exists():
        with ADDRESS_TEXT_OVERRIDES_TSV.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if reader.fieldnames != ["address", "text"]:
                raise ValueError(f"{ADDRESS_TEXT_OVERRIDES_TSV}: expected TSV header address<TAB>text")
            for row in reader:
                addr = canon_addr(row.get("address"))
                if addr:
                    rows[addr] = "" if row.get("text") is None else str(row.get("text"))
    elif B:
        rows = {"0x%08X" % int(k): str(v or "") for k, v in getattr(B, "ADDRESS_TEXT_OVERRIDES", {}).items()}
    return rows


def save_address_text_override(addr, ko):
    if "\t" in ko or "\n" in ko or "\r" in ko:
        raise ValueError("보호 문구 TSV 저장값에는 탭/개행을 넣을 수 없습니다")
    rows = address_text_overrides()
    if addr not in rows:
        return False
    rows[addr] = ko
    ADDRESS_TEXT_OVERRIDES_TSV.parent.mkdir(parents=True, exist_ok=True)
    with ADDRESS_TEXT_OVERRIDES_TSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "text"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for key in sorted(rows, key=lambda x: int(x, 16)):
            writer.writerow({"address": key, "text": rows[key]})
    return True


def sync_dialogue_display_data(addr, ko):
    data = load_json(DIALOGUE_PATH, {"lines": []})
    for ln in data.get("lines", []):
        if canon_addr(ln.get("address")) == addr:
            ln["ko"] = ko
            if "ship_ko" in ln:
                ln["ship_ko"] = ko
    save_json(DIALOGUE_PATH, data)

    groups = load_json(GROUPS_PATH, {"groups": []})
    for group in groups.get("groups", []):
        for member in group.get("members", []):
            if canon_addr(member.get("address")) == addr:
                member["ko"] = ko
                if "ship_ko" in member:
                    member["ship_ko"] = ko
    save_json(GROUPS_PATH, groups)
    global _GROUPS_CACHE
    _GROUPS_CACHE = None


def syl_codes():
    global _SYL_CACHE
    if _SYL_CACHE is None:
        _SYL_CACHE = load_json(SYLCODE, {}) or {}
    return _SYL_CACHE


def syl_to_code_ints():
    global _SYL_INT_CACHE
    if _SYL_INT_CACHE is None:
        _SYL_INT_CACHE = {
            s: int(c, 16) if isinstance(c, str) else int(c)
            for s, c in syl_codes().items()
        }
    return _SYL_INT_CACHE


def build_slots():
    global _BUILD_SLOTS_CACHE
    if _BUILD_SLOTS_CACHE is None:
        _BUILD_SLOTS_CACHE = B.load_slots() if B else {}
    return _BUILD_SLOTS_CACHE


def member_slot(address):
    addr = canon_addr(address)
    if not addr:
        return None
    if B:
        try:
            b_slot = build_slots().get(int(addr, 16))
            if isinstance(b_slot, int) and b_slot > 0:
                return b_slot
        except (ValueError, TypeError):
            pass
    for group in load_groups().get("groups", []):
        for member in group.get("members", []):
            if canon_addr(member.get("address")) == addr and isinstance(member.get("slot"), int):
                return member.get("slot")
    data = load_json(DIALOGUE_PATH, {"lines": []})
    hit = next((ln for ln in data.get("lines", []) if canon_addr(ln.get("address")) == addr), None)
    slot = hit.get("slot") if hit else None
    return slot if isinstance(slot, int) and slot > 0 else None


def validate_build_fit(text, slot):
    raw = TM.encoded_len(text or "") if TM else len(text or "")
    if not isinstance(slot, int) or slot <= 0:
        return {"ok": True, "raw_len": raw, "encoded_len": raw, "fit_level": None, "slot": slot}
    if not B:
        return {"ok": raw <= slot, "raw_len": raw, "encoded_len": raw, "fit_level": None, "slot": slot,
                "error": None if raw <= slot else "슬롯 초과 %dB>%dB" % (raw, slot)}
    dropped = collections.Counter()
    try:
        raw_enc = B.encode_text(text or "", syl_to_code_ints(), dropped)
    except KeyError as exc:
        return {"ok": False, "raw_len": raw, "encoded_len": raw, "fit_level": 99, "slot": slot,
                "unsupported": [exc.args[0]], "error": "폰트 미수록 음절"}
    if dropped:
        return {"ok": False, "raw_len": raw, "encoded_len": len(raw_enc), "fit_level": 99, "slot": slot,
                "unsupported": [ch for ch, _n in dropped.most_common()], "error": "렌더 불가 문자"}
    if not raw_enc and (text or "").strip():
        return {"ok": False, "raw_len": raw, "encoded_len": 0, "fit_level": 99, "slot": slot,
                "unsupported": [], "error": "빌드 인코딩 결과가 비어 있음"}
    enc, level = B.encode_fit(text or "", slot, syl_to_code_ints(), collections.Counter())
    if enc is None:
        return {"ok": False, "raw_len": raw, "encoded_len": raw, "fit_level": 99, "slot": slot,
                "error": "슬롯 초과 %dB>%dB" % (raw, slot)}
    return {"ok": len(enc) <= slot, "raw_len": raw, "encoded_len": len(enc),
            "fit_level": level, "slot": slot}


def check_line(line, pn):
    """대사 한 줄을 사전과 대조. ja에 사전 항목의 ja가 들어 있으면 ko에 사전 ko가 있어야 한다."""
    ja = line.get("ja") or ""
    ko = line.get("ko") or ""
    issues = []
    primary_sources = {
        dict_entry_source(cat, e)
        for cat, e in dict_entries(pn)
        if cat != "common_terms" and dict_entry_source(cat, e)
    }
    for cat, e in dict_entries(pn):
        eja = dict_entry_source(cat, e)
        if cat == "common_terms" and eja in primary_sources:
            continue
        expected_terms = dict_entry_expected_terms(cat, e)
        if not eja or not expected_terms:
            continue
        if eja in ja and not any(term in ko for term in expected_terms):
            issues.append({"category": cat, "ja": eja, "expected_ko": "/".join(expected_terms)})
    return issues


class Handler(BaseHTTPRequestHandler):
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

    def _raw_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _body(self):
        raw = self._raw_body()
        return json.loads(raw or b"{}") if raw else {}

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
        if not AUTH_PASSWORD:
            return True
        return hmac.compare_digest(self._auth_cookie_value(), AUTH_TOKEN)

    def _require_auth(self, path):
        if self._authenticated() or path in ("/login", "/api/auth/status"):
            return True
        if path.startswith("/api/"):
            self._send(401, {"ok": False, "auth_required": True, "error": "비밀번호가 필요합니다"})
        else:
            self._send(200, self._login_page(), "text/html; charset=utf-8")
        return False

    def _login_page(self, error=""):
        err = html.escape(error or "")
        return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AW 대사 에디터 로그인</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#10131a;color:#e8edf5;font:14px/1.5 -apple-system,"Apple SD Gothic Neo",sans-serif}}
form{{width:min(360px,calc(100vw - 32px));display:grid;gap:10px;background:#181d27;border:1px solid #2b3342;border-radius:10px;padding:20px;box-shadow:0 16px 54px rgba(0,0,0,.45)}}
strong{{font-size:16px}} span{{color:#9aa7b8;font-size:12px}} input,button{{font:inherit;border-radius:7px;padding:8px 10px}}
input{{background:#0d1016;color:#e8edf5;border:1px solid #303848}} button{{background:#5b9dff;color:#06101e;border:1px solid #5b9dff;font-weight:700;cursor:pointer}}
.err{{min-height:18px;color:#ef6b6b;font-size:12px}}
</style></head><body>
<form method="post" action="/login">
  <strong>AW 대사 편집기</strong>
  <span>비밀번호를 입력하세요.</span>
  <input name="password" type="password" autocomplete="current-password" autofocus>
  <button type="submit">들어가기</button>
  <div class="err">{err}</div>
</form></body></html>"""

    def _login(self):
        raw = self._raw_body()
        ctype = self.headers.get("Content-Type", "")
        if "application/json" in ctype:
            try:
                data = json.loads(raw or b"{}")
            except Exception:
                data = {}
            password = str(data.get("password") or "")
        else:
            data = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
            password = data.get("password", [""])[0]
        if AUTH_PASSWORD and not hmac.compare_digest(password, AUTH_PASSWORD):
            if "application/json" in ctype:
                return self._send(401, {"ok": False, "auth_required": True, "error": "비밀번호가 틀렸습니다"})
            return self._send(401, self._login_page("비밀번호가 틀렸습니다"), "text/html; charset=utf-8")
        cookie = f"{AUTH_COOKIE}={AUTH_TOKEN}; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800"
        if "application/json" in ctype:
            return self._send(200, {"ok": True, "authenticated": True}, headers=[("Set-Cookie", cookie)])
        return self._send(303, "", headers=[("Set-Cookie", cookie), ("Location", "/")])

    def _logout(self):
        cookie = f"{AUTH_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return self._send(303, "", headers=[("Set-Cookie", cookie), ("Location", "/login")])

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/login":
            return self._send(200, self._login_page(), "text/html; charset=utf-8")
        if u.path == "/logout":
            return self._logout()
        if u.path == "/api/auth/status":
            return self._send(200, {"ok": True, "auth_required": bool(AUTH_PASSWORD),
                                    "authenticated": self._authenticated()})
        if not self._require_auth(u.path):
            return
        if u.path == "/" or u.path == "/index.html":
            return self._serve_static("index.html")
        if u.path.startswith("/static/"):
            return self._serve_static(u.path[len("/static/"):])
        if u.path == "/api/dialogue":
            return self._send(200, self._dialogue(q))
        if u.path == "/api/dict":
            return self._send(200, dict_response())
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
        protected_rows = address_text_overrides()
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
                protected = protected_rows.get(addr)
                ko = protected if protected is not None else ov.get(addr, base_ko)
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
        protected_rows = address_text_overrides()
        for ln in lines:
            a = canon_addr(ln.get("address"))
            if a in protected_rows:
                ln["ko"] = protected_rows[a]
            elif _ov and a in _ov and _ov[a]:
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
        if u.path == "/login":
            return self._login()
        if u.path == "/logout":
            return self._logout()
        if not self._require_auth(u.path):
            return
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
            # B팀(짜옹이) 권위 주소 save-time 보호 — 변형(ln["ko"]=ko) **전에** 검사(codex 순서지적 반영).
            addr = canon_addr(hit.get("address"))
            protected_address_text = is_address_text_override(addr)
            if protected_address_text and any(ch in ko for ch in ("\t", "\n", "\r")):
                return {"ok": False, "error": "보호 문구 TSV 저장값에는 탭/개행을 넣을 수 없습니다"}
            if addr and not body.get("confirm_bteam"):
                try:
                    _bt = set(load_json(ROOT / "data" / "bteam_addresses.json", {}).get("addresses", []))
                    if ("0x%08X" % int(addr, 16)) in _bt:
                        _base = (load_json(ROOT / "data" / "bteam_baseline.json", {}).get("overrides") or {}
                                 ).get("0x%08X" % int(addr, 16))
                        return {"ok": False, "bteam_confirm_required": True,
                                "error": "짜옹이님(B팀) 권위 주소. confirm_bteam=true로 재전송하세요.",
                                "bteam_baseline": _base}
                except (ValueError, TypeError):
                    pass
            check_target = {**hit, "ko": ko}
            slot = member_slot(addr) or hit.get("slot")
            fit = validate_build_fit(ko, slot)
            if not fit.get("ok"):
                return {"ok": False, "error": fit.get("error") or "빌드 fit 검증 실패",
                        "unsupported": fit.get("unsupported"), "raw_len": fit.get("raw_len"),
                        "encoded_len": fit.get("encoded_len"), "slot": fit.get("slot")}
            if body.get("dry_run"):
                return {"ok": True, "dry_run": True, "id": hit.get("id"), "address": addr,
                        "ko": ko, "check": check_line(check_target, load_json(DICT_PATH, {})),
                        "raw_len": fit.get("raw_len"), "encoded_len": fit.get("encoded_len"),
                        "fit_level": fit.get("fit_level"), "slot": fit.get("slot"),
                        "protected_address_text": protected_address_text,
                        "storage": ("address_text_overrides.tsv+dialogue_overrides.json"
                                    if protected_address_text else "dialogue_overrides.json")}
            hit["ko"] = ko   # 검사 통과 후에만 변형
            ov = load_json(OVERRIDES_PATH, {})
            if addr:
                if protected_address_text:
                    try:
                        saved_protected = save_address_text_override(addr, ko)
                    except ValueError as exc:
                        return {"ok": False, "error": str(exc)}
                    if not saved_protected:
                        return {"ok": False, "error": "ADDRESS_TEXT_OVERRIDES 행 없음: " + addr}
                ov[addr] = ko
                save_json(OVERRIDES_PATH, ov)
                if protected_address_text:
                    sync_dialogue_display_data(addr, ko)
                else:
                    save_json(DIALOGUE_PATH, data)
            else:
                save_json(DIALOGUE_PATH, data)
        return {"ok": True, "id": lid, "ko": ko, "check": check_line(check_target, load_json(DICT_PATH, {})),
                "raw_len": fit.get("raw_len"), "encoded_len": fit.get("encoded_len"),
                "fit_level": fit.get("fit_level"), "slot": fit.get("slot"),
                "protected_address_text": protected_address_text,
                "storage": ("address_text_overrides.tsv+dialogue_overrides.json"
                            if protected_address_text else "dialogue_overrides.json")}

    def _edit_dict(self, body):
        return edit_dict_payload(body)

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
    global AUTH_PASSWORD
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--password", default=None,
                    help="웹 UI 비밀번호. 생략 시 DIALOGUE_EDITOR_PASSWORD/AW_EDITOR_PASSWORD/default를 사용")
    ap.add_argument("--no-password", action="store_true",
                    help="로컬 자동화 전용: 비밀번호 인증 비활성")
    args = ap.parse_args()
    if args.no_password:
        AUTH_PASSWORD = ""
    elif args.password is not None:
        AUTH_PASSWORD = args.password
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"대사 편집기: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print("  auth: " + ("enabled" if AUTH_PASSWORD else "disabled"))
    print(f"  dialogue: {DIALOGUE_PATH}  dict: {DICT_PATH}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
