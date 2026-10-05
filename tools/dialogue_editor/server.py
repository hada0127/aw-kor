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
from types import MappingProxyType
import argparse
import collections
import csv
import hmac
import io
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
sys.path.insert(0, str(ROOT / "tools"))
from editor_storage import EDITOR_LOCK, atomic_write_text, atomic_write_group, save_json as atomic_save_json, editor_request
STATIC = Path(__file__).resolve().parent / "static"
DIALOGUE_PATH = ROOT / "data" / "dialogue_map.json"
DICT_PATH = ROOT / "data" / "proper_nouns.json"
OVERRIDES_PATH = ROOT / "data" / "dialogue_overrides.json"
EDITOR_INTENTS_PATH = ROOT / "data" / "editor_override_intents.json"
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
_FALLBACK_SLOTS_CACHE = None
_SYL_CACHE = None
_SYL_INT_CACHE = None
_BUILD_SLOTS_CACHE = None
_DIRECT_SLOTS_CACHE = None
_ADDRESS_TEXT_CACHE = None
_DISPLAY_TEXT_CACHE = None
_KNOWN_FRAGMENT_CACHE = None


def file_stamp(path):
    try:
        st = Path(path).stat()
        return (st.st_ino, st.st_size, st.st_mtime_ns)
    except FileNotFoundError:
        return None


def load_groups():
    """Refresh when another editor replaces the generated group file."""
    global _GROUPS_CACHE
    stamp = file_stamp(GROUPS_PATH)
    snapshot = _GROUPS_CACHE
    if snapshot is None or stamp != snapshot[0]:
        groups = load_json(GROUPS_PATH, {"groups": []})
        snapshot = (stamp, groups)
        _GROUPS_CACHE = snapshot
    return snapshot[1]


def fallback_slots():
    global _FALLBACK_SLOTS_CACHE
    key = (file_stamp(GROUPS_PATH), file_stamp(DIALOGUE_PATH))
    if _FALLBACK_SLOTS_CACHE is None or _FALLBACK_SLOTS_CACHE[0] != key:
        slots = {}
        for group in load_groups().get("groups", []):
            for member in group.get("members", []):
                address = canon_addr(member.get("address"))
                slot = member.get("slot")
                if address and isinstance(slot, int) and slot > 0:
                    slots.setdefault(address, slot)
        for line in load_json(DIALOGUE_PATH, {"lines": []}).get("lines", []):
            address = canon_addr(line.get("address"))
            slot = line.get("slot")
            if address and isinstance(slot, int) and slot > 0:
                slots.setdefault(address, slot)
        _FALLBACK_SLOTS_CACHE = (key, slots)
    return _FALLBACK_SLOTS_CACHE[1]

sys.path.insert(0, str(ROOT / "tools"))
try:
    import preview_capture  # 실캡처 엔진(canvas-hijack)
except Exception as _e:  # PIL/하네스 부재 시 미리보기 비활성
    preview_capture = None
    _PREVIEW_ERR = repr(_e)
try:
    import build_korean_full as B
except Exception as exc:
    raise RuntimeError("dialogue editor requires build_korean_full for safe save gates") from exc
try:
    import text_metrics as TM
except Exception:
    TM = None

_LOCK = EDITOR_LOCK
_PREVIEW_LOCK = threading.Lock()  # mgbah 캡처 직렬화(하네스 로그/리소스 공유)
PREVIEW_DIR = ROOT / "temp" / "preview_cache"
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png"}


def pick_canvas(line):
    """Choose a diagnostic canvas; this does not prove the source renderer."""
    addr = canon_addr(line.get("address"))
    if line.get("region") == "part1" or (addr and 0xD80000 <= int(addr, 16) < 0xE10000):
        return "part1_welcome"
    return "part2_menu"


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, data):
    atomic_save_json(path, data)


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


def address_text_snapshot(path):
    """Cache a validated immutable authority; external replace changes the key."""
    global _ADDRESS_TEXT_CACHE
    key = (str(Path(path).resolve()), file_stamp(path))
    snapshot = _ADDRESS_TEXT_CACHE
    if snapshot is None or snapshot[0] != key:
        rows = B.load_address_text_overrides_tsv(path)
        rows = dict(B.ADDRESS_TEXT_OVERRIDES if rows is None else rows)
        snapshot = (key, MappingProxyType(rows), MappingProxyType({
            "0x%08X" % int(k): str(v or "") for k, v in rows.items()}))
        _ADDRESS_TEXT_CACHE = snapshot
    return snapshot


def address_text_overrides():
    return address_text_snapshot(ADDRESS_TEXT_OVERRIDES_TSV)[2]


def display_text_overrides():
    global _DISPLAY_TEXT_CACHE
    path = ROOT / "data" / "display_overrides.json"
    key = (str(path.resolve()), file_stamp(path))
    snapshot = _DISPLAY_TEXT_CACHE
    if snapshot is None or snapshot[0] != key:
        rows = B.load_display_overrides(path)
        snapshot = (key, MappingProxyType({"0x%08X" % k: v for k, v in rows.items()}))
        _DISPLAY_TEXT_CACHE = snapshot
    return snapshot[1]


DISPLAY_READONLY_REASON = "전용 표시 문구가 적용된 항목입니다. 일반 대사 편집으로 변경할 수 없습니다"
STRUCTURED_READONLY_REASON = "명령어 강조가 포함된 복합 대사입니다. 일반 조각 편집은 지원하지 않습니다"
KNOWN_FRAGMENT_READONLY_REASON = "제어 코드 사이의 짧은 고정 문구입니다. 일반 대사 편집으로 변경할 수 없습니다"


def known_fragment_addresses():
    global _KNOWN_FRAGMENT_CACHE
    key = (str(DIALOGUE_PATH), file_stamp(DIALOGUE_PATH))
    if _KNOWN_FRAGMENT_CACHE is None or _KNOWN_FRAGMENT_CACHE[0] != key:
        rows = load_json(DIALOGUE_PATH, {}).get('lines', [])
        _KNOWN_FRAGMENT_CACHE = (key, frozenset(canon_addr(row.get('address')) for row in rows
                                               if row.get('kind') == 'known-story-fragment'))
    return _KNOWN_FRAGMENT_CACHE[1]


def text_edit_readonly_reason(address, *, fixed_fragments=None, display=None):
    if fixed_fragments is None:
        fixed_fragments = known_fragment_addresses()
    if display is None:
        display = display_text_overrides()
    if canon_addr(address) in fixed_fragments:
        return KNOWN_FRAGMENT_READONLY_REASON
    if canon_addr(address) in display:
        return DISPLAY_READONLY_REASON
    canonical = canon_addr(address)
    if canonical and B.structured_script_owner(int(canonical, 16)) is not None:
        return STRUCTURED_READONLY_REASON
    return None


def edit_authority_error(address, ko):
    if not isinstance(ko, str):
        return "대사는 문자열이어야 합니다"
    readonly = text_edit_readonly_reason(address)
    if readonly:
        return readonly
    if not ko.strip() and not is_address_text_override(address):
        return "이 항목은 빈 문구로 저장할 수 없습니다. 내용을 입력하세요"
    return None


def current_ko(address, member=None, snapshot=None):
    addr = canon_addr(address)
    display = display_text_overrides()
    if addr in display and addr not in known_fragment_addresses():
        return display[addr]
    if addr and (int(addr, 16) in B.STRUCTURED_SCRIPT_ROWS or addr in known_fragment_addresses()):
        if member is None:
            member = (snapshot["by_addr"].get(addr, {}) if snapshot is not None else
                      next((row for row in load_json(DIALOGUE_PATH, {"lines": []}).get("lines", [])
                            if canon_addr(row.get("address")) == addr), {}))
        return member.get("ko") or ""
    protected = address_text_overrides()
    if addr in protected:
        return protected[addr]
    overrides = snapshot["overrides"] if snapshot is not None else B.load_dialogue_overrides(OVERRIDES_PATH)
    if addr in overrides:
        return overrides[addr]
    if member is None and snapshot is not None:
        member = snapshot["by_addr"].get(addr, {})
    if member is None:
        member = next((row for row in load_json(DIALOGUE_PATH, {"lines": []}).get("lines", [])
                       if canon_addr(row.get("address")) == addr), {})
    return member.get("ko") or ""





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


def direct_slots():
    global _DIRECT_SLOTS_CACHE
    stamp = file_stamp(GROUPS_PATH)
    if _DIRECT_SLOTS_CACHE is None or _DIRECT_SLOTS_CACHE[0] != stamp:
        _DIRECT_SLOTS_CACHE = (stamp, B.load_direct_script_slots() if B else {})
    return _DIRECT_SLOTS_CACHE[1]


def member_slot(address, *, direct=None, build=None, fallback=None):
    addr = canon_addr(address)
    if not addr:
        return None
    ai = int(addr, 16)
    if ai in B.WHOLE_SCRIPT_ROWS:
        return B.WHOLE_SCRIPT_ROWS[ai] - ai
    slot = (direct if direct is not None else direct_slots()).get(ai) or \
           (build if build is not None else build_slots()).get(ai)
    if isinstance(slot, int) and slot > 0:
        return slot
    return (fallback if fallback is not None else fallback_slots()).get(addr)


def protected_render_region(address, slot):
    if not isinstance(slot, int) or slot <= 0:
        return None
    end = address + slot
    denied = B.in_deny(address, end)
    if denied:
        return str(denied)
    for name, lo, hi in B.DENY_REGIONS + B.PAIR_RENDERER_REGIONS:
        if address < hi and end > lo:
            return name
    return None


def validate_build_fit(text, slot, address=None):
    ai = int(address, 16) if address else None
    raw = TM.encoded_len(text or "") if TM else len(text or "")
    if not isinstance(slot, int) or slot <= 0:
        return {"ok": True, "raw_len": raw, "encoded_len": raw, "fit_level": None, "slot": slot}
    if not B:
        return {"ok": raw <= slot, "raw_len": raw, "encoded_len": raw, "fit_level": None, "slot": slot,
                "error": None if raw <= slot else "%dB 슬롯에 넣을 수 없습니다(원문 인코딩 %dB)" % (slot, raw)}
    dropped = collections.Counter()
    try:
        raw_enc = B.encode_text(text or "", syl_to_code_ints(), dropped, ai)
    except KeyError as exc:
        return {"ok": False, "raw_len": raw, "encoded_len": raw, "fit_level": 99, "slot": slot,
                "unsupported": [exc.args[0]], "error": "폰트 미수록 음절"}
    raw = len(raw_enc)
    if dropped:
        return {"ok": False, "raw_len": raw, "encoded_len": len(raw_enc), "fit_level": 99, "slot": slot,
                "unsupported": [ch for ch, _n in dropped.most_common()], "error": "렌더 불가 문자"}
    if not raw_enc and (text or "").strip():
        return {"ok": False, "raw_len": raw, "encoded_len": 0, "fit_level": 99, "slot": slot,
                "unsupported": [], "error": "빌드 인코딩 결과가 비어 있음"}
    try:
        enc, level = B.encode_fit(text or "", slot, syl_to_code_ints(), collections.Counter(), ai)
    except B.UnsupportedDialogueQuoteError:
        return {"ok": False, "raw_len": raw, "encoded_len": raw, "fit_level": 99, "slot": slot,
                "error": "이 대화창에서는 「 」 인용부호를 사용해 주세요."}
    if enc is None:
        return {"ok": False, "raw_len": raw, "encoded_len": raw, "fit_level": 99, "slot": slot,
                "error": "%dB 슬롯에 넣을 수 없습니다(원문 인코딩 %dB)" % (slot, raw)}
    return {"ok": len(enc) <= slot, "raw_len": raw, "encoded_len": len(enc),
            "fit_level": level, "slot": slot,
            "warning": B.dialogue_fit_warning(text or "", enc, syl_to_code_ints(), ai)}


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
    @editor_request
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
        ov = B.load_dialogue_overrides(OVERRIDES_PATH) or {}
        protected_rows = address_text_overrides()
        display_rows = display_text_overrides()
        fixed_fragments = known_fragment_addresses()
        slot_snapshot = {"direct": direct_slots(), "build": build_slots(), "fallback": fallback_slots()}
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
                ko = display_rows.get(addr, protected if protected is not None else ov.get(addr, base_ko))
                canonical_addr = canon_addr(addr)
                ai = int(canonical_addr, 16) if canonical_addr else 0
                if addr in fixed_fragments:
                    ko = base_ko
                elif ai in B.STRUCTURED_SCRIPT_ROWS:
                    ko = display_rows.get(addr, base_ko)
                owner = B.script_row_owner(ai) if B else ai
                slot = member_slot(canonical_addr, **slot_snapshot)
                readonly = text_edit_readonly_reason(addr, fixed_fragments=fixed_fragments, display=display_rows)
                members.append({**member, "address": addr, "ko": ko, "bteam": is_bteam(addr),
                                "slot": slot, "reason": readonly or "",
                                "editable": not readonly and owner == ai and ai >= 0x800000 and bool(slot) and not B.is_glyph_dictionary_address(ai) and not protected_render_region(ai, slot),
                                "source_role": "glyph_dictionary" if B and B.is_glyph_dictionary_address(ai) else "text",
                                "layout_prefix_bytes": len(B.PART2_EDITOR_ICON_PREFIX) if B and ai in B.PART2_EDITOR_ICON_LABEL_SLOTS else 0,
                                "owner_address": "0x%08X" % owner})
            if qstr and qstr not in (g.get("assembled_ja") or "") and \
               all(qstr not in (m.get("ko") or "") for m in members):
                continue
            out.append({"group_id": g.get("group_id"), "region": g.get("region"),
                        "size": g.get("size"), "flagged": g.get("flagged"),
                        "assembled_ja": g.get("assembled_ja"), "segments": g.get("segments"),
                        "ko_segments": g.get("ko_segments"),
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
        if not path.is_relative_to(STATIC.resolve()):
            return self._send(403, {"error": "forbidden"})
        if not path.is_file():
            return self._send(404, {"error": "missing " + rel})
        ctype = MIME.get(path.suffix, "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)

    def _dialogue(self, q):
        data = load_json(DIALOGUE_PATH, {"lines": []})
        lines = data.get("lines", [])
        _ov = B.load_dialogue_overrides(OVERRIDES_PATH) or {}  # 편집/채움 번역을 즉시 반영(line view)
        protected_rows = address_text_overrides()
        fixed_fragments = known_fragment_addresses()
        display_rows = display_text_overrides()
        for ln in lines:
            a = canon_addr(ln.get("address"))
            if a in fixed_fragments:
                ln["editable"] = False
                ln["reason"] = KNOWN_FRAGMENT_READONLY_REASON
            elif a in display_rows:
                ln["ko"] = display_rows[a]
                ln["editable"] = False
                ln["reason"] = DISPLAY_READONLY_REASON
            elif a and int(a, 16) in B.STRUCTURED_SCRIPT_ROWS:
                pass  # Keep the generated complete authored row, not its legacy TSV fragment.
            elif a in protected_rows:
                ln["ko"] = protected_rows[a]
            elif _ov and a in _ov and _ov[a]:
                ln["ko"] = _ov[a]
            if a and B.structured_script_owner(int(a, 16)) is not None:
                ln["editable"] = False
                ln["reason"] = STRUCTURED_READONLY_REASON
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
    @editor_request
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
        if u.path == "/api/lines":
            return self._send(200, self._save_lines(body))
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

    def _save_lines(self, body):
        """Validate every fragment under one lock before publishing a group."""
        lines = body.get("lines")
        if not isinstance(lines, list) or not lines or len(lines) > 256:
            return {"ok": False, "error": "1~256개 대사 조각이 필요합니다"}
        with _LOCK:
            data = load_json(DIALOGUE_PATH, {"lines": []})
            overrides = B.load_dialogue_overrides(OVERRIDES_PATH)
            snapshot = {"data": data, "overrides": overrides,
                        "by_addr": {canon_addr(row.get("address")): row for row in data.get("lines", [])}}
            checked = []
            for index, line in enumerate(lines):
                if not isinstance(line, dict):
                    return {"ok": False, "error": "대사 조각 형식 오류", "index": index}
                result = self._save_line({**line, "dry_run": True}, snapshot=snapshot)
                if not result.get("ok"):
                    return {**result, "index": index, "saved": 0}
                checked.append(result)
            warnings = [{"address": row["address"], "warning": row["warning"]}
                        for row in checked if row.get("warning")]
            changes = {row["address"]: row["ko"] for row in checked}
            if len(changes) != len(checked):
                return {"ok": False, "error": "중복 주소가 있습니다", "saved": 0}
            intents = B.load_editor_override_intents(EDITOR_INTENTS_PATH)
            protected = dict(address_text_overrides())
            requested = changes
            confirm_requested = {checked[i]["address"] for i, line in enumerate(lines) if line.get("confirm_current") is True}
            # Unchanged TSV display values must never replace distinct source prose.
            changes = {addr: ko for addr, ko in requested.items()
                       if current_ko(addr, snapshot=snapshot) != ko
                       or (addr in confirm_requested and addr not in protected and not is_bteam(addr)
                           and overrides.get(addr) != ko)}
            confirmed = {addr: ko for addr, ko in requested.items()
                         if addr in confirm_requested and addr not in changes
                         and ((not is_bteam(addr) and addr not in protected)
                              or (addr in protected and protected[addr] == ko and overrides.get(addr) == ko))
                         and intents.get(addr) != B.editor_text_digest(ko)}
            unchanged = len(checked) - len(changes) - len(confirmed)
            if not changes and not confirmed:
                return {"ok": True, "saved": 0, "confirmed": 0, "unchanged": unchanged, "warnings": warnings}
            for addr, ko in confirmed.items():
                intents[addr] = B.editor_text_digest(ko)
            if not changes:
                atomic_write_group({EDITOR_INTENTS_PATH: (json.dumps(intents, sort_keys=True, indent=2) + "\n").encode()})
                return {"ok": True, "saved": 0, "confirmed": len(confirmed), "unchanged": unchanged, "warnings": warnings}
            groups = load_json(GROUPS_PATH, {"groups": []})
            touched_protected = changes.keys() & protected.keys()
            for addr, ko in changes.items():
                overrides[addr] = ko
                intents[addr] = B.editor_text_digest(ko)
                if addr in protected:
                    protected[addr] = ko
            for row in data.get("lines", []):
                addr = canon_addr(row.get("address"))
                if addr in changes:
                    row["ko"] = changes[addr]
            for group in groups.get("groups", []):
                for row in group.get("members", []):
                    addr = canon_addr(row.get("address"))
                    if addr in changes:
                        row["ko"] = changes[addr]
            writes = {EDITOR_INTENTS_PATH: (json.dumps(intents, sort_keys=True, indent=2) + "\n").encode(),
                      OVERRIDES_PATH: (json.dumps(overrides, ensure_ascii=False, indent=2) + "\n").encode(),
                      DIALOGUE_PATH: (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(),
                      GROUPS_PATH: (json.dumps(groups, ensure_ascii=False, indent=1) + "\n").encode()}
            if touched_protected:
                stream = io.StringIO(newline="")
                writer = csv.DictWriter(stream, fieldnames=["address", "text"], delimiter="\t", lineterminator="\n")
                writer.writeheader()
                for addr in sorted(protected, key=lambda value: int(value, 16)):
                    writer.writerow({"address": addr, "text": protected[addr]})
                writes[ADDRESS_TEXT_OVERRIDES_TSV] = stream.getvalue().encode()
            atomic_write_group(writes)
            global _GROUPS_CACHE
            _GROUPS_CACHE = None
            return {"ok": True, "saved": len(changes), "confirmed": len(confirmed), "unchanged": unchanged, "warnings": warnings}

    def _save_line(self, body, *, snapshot=None):
        lid = body.get("id")
        ko = body.get("ko", "")
        with _LOCK:
            data = snapshot["data"] if snapshot is not None else load_json(DIALOGUE_PATH, {"lines": []})
            addr = canon_addr(body.get("address"))
            if addr:
                hit = snapshot["by_addr"].get(addr) if snapshot is not None else next((ln for ln in data.get("lines", []) if canon_addr(ln.get("address")) == addr), None)
            else:
                hit = next((ln for ln in data.get("lines", []) if ln.get("id") == lid), None)
            if hit is None:
                key = addr or ("id %r" % lid)
                return {"ok": False, "error": "%s 없음" % key}
            # B팀(짜옹이) 권위 주소 save-time 보호 — 변형(ln["ko"]=ko) **전에** 검사(codex 순서지적 반영).
            addr = canon_addr(hit.get("address"))
            authority_error = edit_authority_error(addr, ko)
            if authority_error:
                return {"ok": False, "error": authority_error}
            if B and addr and B.is_glyph_dictionary_address(int(addr, 16)):
                return {"ok": False, "error": "글리프 등록용 사전입니다. 일반 대사로 편집할 수 없습니다"}
            owner = B.script_row_owner(int(addr, 16)) if B and addr else None
            if owner is not None and owner != int(addr, 16):
                return {"ok": False, "owner_address": "0x%08X" % owner,
                        "error": "합쳐진 문장입니다. 0x%08X에서 전체 문장을 편집하세요" % owner}
            protected_address_text = is_address_text_override(addr)
            if protected_address_text and any(ch in ko for ch in ("\t", "\n", "\r")):
                return {"ok": False, "error": "보호 문구 TSV 저장값에는 탭/개행을 넣을 수 없습니다"}
            if addr and not body.get("confirm_bteam"):
                _bt = set(load_json(ROOT / "data" / "bteam_addresses.json", {}).get("addresses", []))
                if ("0x%08X" % int(addr, 16)) in _bt:
                    _base = (load_json(ROOT / "data" / "bteam_baseline.json", {}).get("overrides") or {}
                             ).get("0x%08X" % int(addr, 16))
                    if current_ko(addr, hit, snapshot=snapshot) != ko:
                        return {"ok": False, "bteam_confirm_required": True,
                                "error": "짜옹이님(B팀) 권위 주소. confirm_bteam=true로 재전송하세요.",
                                "bteam_baseline": _base}
            check_target = {**hit, "ko": ko}
            slot = member_slot(addr)
            if not addr or int(addr, 16) < 0x800000 or not isinstance(slot, int) or slot <= 0:
                return {"ok": False, "error": "등록된 빌드 슬롯이 없는 주소입니다"}
            protected_region = protected_render_region(int(addr, 16), slot)
            if protected_region:
                return {"ok": False, "error": "특수 렌더/보호 영역 — 일반 대사 편집 불가: " + protected_region}
            fit = validate_build_fit(ko, slot, addr)
            if not fit.get("ok"):
                return {"ok": False, "error": fit.get("error") or "빌드 fit 검증 실패",
                        "unsupported": fit.get("unsupported"), "raw_len": fit.get("raw_len"),
                        "encoded_len": fit.get("encoded_len"), "slot": fit.get("slot")}
            if body.get("dry_run"):
                return {"ok": True, "dry_run": True, "id": hit.get("id"), "address": addr,
                        "ko": ko, "check": check_line(check_target, load_json(DICT_PATH, {})),
                        "raw_len": fit.get("raw_len"), "encoded_len": fit.get("encoded_len"),
                        "fit_level": fit.get("fit_level"), "warning": fit.get("warning"), "slot": fit.get("slot"),
                        "protected_address_text": protected_address_text,
                        "storage": ("address_text_overrides.tsv+dialogue_overrides.json"
                                    if protected_address_text else "dialogue_overrides.json")}
            saved = self._save_lines({"lines": [body]})
            if not saved.get("ok"):
                return saved

        return {"ok": True, "saved": saved["saved"], "confirmed": saved["confirmed"], "unchanged": saved["unchanged"], "id": lid, "ko": ko, "check": check_line(check_target, load_json(DICT_PATH, {})),
                "raw_len": fit.get("raw_len"), "encoded_len": fit.get("encoded_len"),
                "fit_level": fit.get("fit_level"), "warning": fit.get("warning"), "slot": fit.get("slot"),
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
