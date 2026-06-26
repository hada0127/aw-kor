#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dialogue_map.py — aw-kor 대사 원문→번역 맵 빌더 (T4)

muramasa-kor translations/jp_messages.json 포맷을 참조해, aw-kor 의 3개 소스를 병합한
대사 맵(data/dialogue_map.json)을 생성한다.

병합 소스:
  1) data/game_wars_found_texts.csv      — 원문(일본어 ja = text열) + hex_bytes/length. 주소 superset.
  2) data/translation_for_import.csv     — 번역(ko = korean열). address,japanese,korean,length.
  3) temp/integrity_map.json (선택)      — 실제 출하본 무결성맵.
        엔트리 = [addr_int, slot(=length 필드), enc_len, enc_hex(빅엔디안),
                  fill, ko(출하 한국어), level, kind]
        있으면 출하 ko(ship_ko) + slot + kind 를 병기한다.

출력: data/dialogue_map.json
  {
    "meta": {...통계/생성정보...},
    "lines": [
      {
        "id": <int>,
        "address": "0x00E050AB",
        "ja": <원문 일본어>,
        "ko": <번역 한국어 (없으면 "")>,
        "ship_ko": <무결성맵 출하 한국어 또는 null>,
        "slot": <무결성맵 slot/length 또는 null>,
        "kind": <무결성맵 kind 또는 null>,
        "region": "part1|part2|campaign|ui|font|other",
        "is_noise": <추출 노이즈 추정 bool>
      }, ...
    ]
  }

사용:
  python3 tools/build_dialogue_map.py
  python3 tools/build_dialogue_map.py --out data/dialogue_map.json
"""
import argparse
import csv
import json
import os
import sys
import unicodedata
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOUND_CSV = os.path.join(REPO, "data", "game_wars_found_texts.csv")
TRANS_CSV = os.path.join(REPO, "data", "translation_for_import.csv")
INTEGRITY = os.path.join(REPO, "temp", "integrity_map.json")
DIALOGUE_OVERRIDES = os.path.join(REPO, "data", "dialogue_overrides.json")
DEFAULT_OUT = os.path.join(REPO, "data", "dialogue_map.json")


def norm_addr(a):
    """주소 문자열 → int. 8자리 초과(잘못 병합된 행)·비정상은 None."""
    if a is None:
        return None
    a = a.strip().upper()
    if a.startswith("0X"):
        a = a[2:]
    if not a:
        return None
    try:
        v = int(a, 16)
    except ValueError:
        return None
    # ROM 은 16MB(0xFFFFFF). 그보다 큰 값은 CSV 깨짐(주소 두 개가 붙은 행 등).
    if v < 0 or v > 0xFFFFFF:
        return None
    return v


def region_of(addr):
    """주소 high byte(>>16) 로 region 추정. CLAUDE.md / 임무 힌트 기반."""
    hi = (addr >> 16) & 0xFF
    if 0xA0 <= hi <= 0xA3:
        return "part2"          # Advance 2 대사 클러스터
    if 0xD8 <= hi <= 0xDF:
        return "part1"          # Advance 1 대사
    if 0xE0 <= hi <= 0xE2:
        return "campaign"       # 캠페인
    # UI 라벨 영역: 0x92,0x94,0x96,0x97,0x99,0x9B,0x9D,0x9E 등 0x92~0x9E 대역
    if 0x92 <= hi <= 0x9E:
        return "ui"
    if hi == 0xB8 or hi == 0xB9:
        return "font"           # 폰트/이름그리드 인접 영역
    return "other"


# --- 노이즈(추출 깨짐) 추정 휴리스틱 -------------------------------------------
# found_texts 상당수는 무작위 한자 + 키릴(Ё 등) + 기호 조합으로, 실제 대사가 아님.
_KANA = lambda o: 0x3040 <= o <= 0x30FF
_CJK = lambda o: 0x4E00 <= o <= 0x9FFF
_CJK_EXT = lambda o: 0x3400 <= o <= 0x4DBF
_FULLWIDTH = lambda o: 0xFF00 <= o <= 0xFFEF
_CJK_PUNCT = lambda o: 0x3000 <= o <= 0x303F  # 、。「」… 등
_LATIN = lambda o: (0x41 <= o <= 0x5A) or (0x61 <= o <= 0x7A)
_ASCII_DIGIT = lambda o: 0x30 <= o <= 0x39


def is_noise(text):
    """원문이 추출 노이즈로 추정되면 True.

    실제 일본어 대사는 가나(히라/가타)가 섞이거나, 자연스러운 CJK 문장부호를 포함한다.
    노이즈는 보통 (a) 가나가 전혀 없고 (b) 키릴/기타 비정상 스크립트가 끼거나
    (c) 무작위 한자만 짧게 나열된다.
    """
    if text is None:
        return True
    t = text.strip()
    if not t:
        return True

    has_kana = False
    has_cyrillic = False
    has_other_weird = False  # 키릴 외 비정상 스크립트(아르메니아/그리스 등)
    cjk = 0
    kana = 0
    latin = 0
    total = 0

    for ch in t:
        o = ord(ch)
        if ch.isspace():
            continue
        total += 1
        if _KANA(o):
            has_kana = True
            kana += 1
        elif _CJK(o) or _CJK_EXT(o):
            cjk += 1
        elif _LATIN(o) or _ASCII_DIGIT(o):
            latin += 1
        elif _FULLWIDTH(o) or _CJK_PUNCT(o):
            pass  # 정상 부호로 간주
        elif 0x0400 <= o <= 0x04FF:  # 키릴
            has_cyrillic = True
        elif o < 0x80:
            pass  # 기본 ASCII 부호
        else:
            # 그 외 스크립트(그리스/아르메니아/특수기호 등) → 의심
            cat = unicodedata.category(ch)
            if cat[0] in ("L",):  # 다른 언어 문자
                has_other_weird = True

    if total == 0:
        return True

    # 키릴/타스크립트 섞임 = 거의 확실히 노이즈
    if has_cyrillic or has_other_weird:
        return True

    # 가나가 있고 글자 수가 어느 정도면 정상 대사로 본다
    if has_kana:
        return False

    # 가나가 전혀 없는 경우:
    #   - 라틴/숫자 위주(영문 UI 라벨, 수치)는 노이즈 아님
    if latin > 0 and cjk == 0:
        return False
    #   - 한자만으로 구성: 짧으면(<=4) 노이즈 가능성↑(무작위 한자열).
    #     단, 단일 한자/숙어 라벨도 있으므로 매우 보수적으로 4자 이하 한자-only만 노이즈로.
    if cjk > 0 and latin == 0 and kana == 0:
        if total <= 4:
            return True
        # 5자 이상 한자-only는 실제 한문/숙어 라벨일 수 있어 노이즈로 단정하지 않음
        return False

    # 그 외(부호 위주 등)는 노이즈 아님으로
    return False


def has_hangul(text):
    return any("가" <= ch <= "힣" for ch in (text or ""))


def load_dialogue_overrides():
    if not os.path.exists(DIALOGUE_OVERRIDES):
        return {}
    try:
        data = json.load(open(DIALOGUE_OVERRIDES, encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    for key, value in data.items():
        v = norm_addr(key)
        if v is not None:
            out[v] = value or ""
    return out


def load_build_text_overrides():
    """빌드가 실제 ROM에 적용하는 텍스트 override를 UI map에도 반영한다.

    scene/dialogue editor는 dialogue_map/groups를 읽기 때문에 여기서 빌드 권위
    `build_korean_full.py`의 SOURCE/ADDRESS/TEXT override를 반영하지 않으면
    ROM에는 번역되어 들어가는데 UI에는 미번역처럼 보이는 항목이 생긴다.
    """
    try:
        tools_dir = os.path.join(REPO, "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import build_korean_full as B  # noqa: WPS433
        addr_overrides = dict(B.ADDRESS_TEXT_OVERRIDES)
        slots = B.load_slots()
        for addr, text in list(addr_overrides.items()):
            slot = slots.get(addr, 1)
            if B.in_region(B.PAIR_RENDERER_REGIONS, addr, addr + max(slot, 1)):
                addr_overrides[addr] = B.normalize_pair_renderer_text(text)
        return addr_overrides, B.SOURCE_TEXT_OVERRIDES, B.TEXT_OVERRIDES
    except Exception:
        return {}, {}, {}


def load_direct_patch_texts():
    try:
        import qa_text_fit  # noqa: WPS433
        return {start: text for start, (_end, text) in qa_text_fit.load_direct_patch_texts().items()}
    except Exception:
        return {}


def display_ko_for(addr, ja, csv_ko, ship_ko, addr_overrides, source_overrides, text_overrides, direct_patches, dialogue_overrides):
    """UI에 보여줄 현재 번역. 우선순위는 빌드 적용 순서와 맞춘다."""
    ko = csv_ko or ""
    protected_addr_override = addr in addr_overrides
    if protected_addr_override:
        ko = addr_overrides[addr] or ""
    else:
        if ja in source_overrides and not has_hangul(ko):
            ko = source_overrides[ja] or ""
        if ko in text_overrides:
            ko = text_overrides[ko] or ""
    direct_hit = addr in direct_patches
    if direct_hit:
        ko = direct_patches[addr] or ""
    if not ko and ship_ko and addr not in addr_overrides and not direct_hit:
        # integrity_map은 실제 빌드 산출에서 역추출한 문자열이다. CSV/inline 경로에
        # 없는 직접 패치 라벨도 UI에는 현재 ROM 기준으로 보여야 한다.
        ko = ship_ko
    if addr in dialogue_overrides and addr not in addr_overrides:
        ko = dialogue_overrides[addr] or ""
    if protected_addr_override:
        # Protected rows skip editor overlays/display normalizers, but later
        # direct script patches still win because build_korean_full writes them
        # after the import/override pass.
        return ko
    if ko:
        try:
            import build_korean_full as B  # noqa: WPS433
            ko = B.normalize_korean_terms(ko)
        except Exception:
            pass
        ko = ko.replace("지도을", "지도를").replace("지도은", "지도는")
    return ko


def main():
    ap = argparse.ArgumentParser(description="aw-kor 대사 맵 빌더")
    ap.add_argument("--out", default=DEFAULT_OUT, help="출력 JSON 경로")
    ap.add_argument("--found", default=FOUND_CSV)
    ap.add_argument("--trans", default=TRANS_CSV)
    ap.add_argument("--integrity", default=INTEGRITY)
    args = ap.parse_args()

    # 1) found_texts: 주소 superset + 원문(ja)
    found = {}
    found_bad = 0
    with open(args.found, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            v = norm_addr(row.get("address"))
            if v is None:
                found_bad += 1
                continue
            # 동일 주소 중복 시 첫 행 유지(파일 순서 = ROM 순서)
            if v not in found:
                found[v] = {
                    "ja": (row.get("text") or "").strip(),
                    "length": (row.get("length") or "").strip(),
                }

    # 2) translation: 번역 ko
    trans = {}
    trans_bad = 0
    with open(args.trans, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            v = norm_addr(row.get("address"))
            if v is None:
                trans_bad += 1
                continue
            trans[v] = {
                "ja": (row.get("japanese") or "").strip(),
                "ko": (row.get("korean") or "").strip(),
            }

    # 3) integrity map (선택)
    integrity = {}
    have_integrity = os.path.exists(args.integrity)
    if have_integrity:
        with open(args.integrity, encoding="utf-8") as f:
            ig = json.load(f)
        for e in ig:
            # [addr, slot, enc_len, enc_hex, fill, ko, level, kind]
            addr = e[0]
            integrity[addr] = {
                "slot": e[1] if len(e) > 1 else None,
                "ship_ko": (e[5] if len(e) > 5 else None),
                "kind": (e[7] if len(e) > 7 else None),
            }

    addr_overrides, source_overrides, text_overrides = load_build_text_overrides()
    direct_patches = load_direct_patch_texts()
    dialogue_overrides = load_dialogue_overrides()

    # 모든 주소의 합집합(found 가 superset 이지만 trans-only 10건 등 안전하게 합집합)
    all_addrs = sorted(set(found) | set(trans) | set(integrity))

    lines = []
    region_counter = Counter()
    noise_count = 0
    real_count = 0
    missing_ko = 0          # 실대사인데 번역 누락(ko 비었거나 ja==ko)
    have_ship_ko = 0
    for idx, addr in enumerate(all_addrs):
        f_ent = found.get(addr)
        t_ent = trans.get(addr)
        i_ent = integrity.get(addr)

        # ja: found 우선, 없으면 translation 의 japanese
        ja = ""
        if f_ent and f_ent["ja"]:
            ja = f_ent["ja"]
        elif t_ent and t_ent["ja"]:
            ja = t_ent["ja"]

        ship_ko = i_ent["ship_ko"] if i_ent else None
        ko = display_ko_for(
            addr, ja, t_ent["ko"] if t_ent else "", ship_ko,
            addr_overrides, source_overrides, text_overrides, direct_patches, dialogue_overrides,
        )
        slot = i_ent["slot"] if i_ent else None
        kind = i_ent["kind"] if i_ent else None

        region = region_of(addr)
        noise = is_noise(ja)
        # 원문(ja)이 비었더라도 실제 출하/번역 한국어가 있으면 노이즈가 아니다.
        # (예: 원본 ROM 이 zero-fill 이던 UI 라벨을 한국어로 채운 fixed_zero_text 류)
        if noise and not ja and (ship_ko or ko):
            noise = False

        region_counter[region] += 1
        if noise:
            noise_count += 1
        else:
            real_count += 1
            # 실대사 기준 번역 누락 판정
            if (not ko) or (ko == ja):
                missing_ko += 1
        if ship_ko:
            have_ship_ko += 1

        lines.append({
            "id": idx,
            "address": "0x%08X" % addr,
            "ja": ja,
            "ko": ko,
            "ship_ko": ship_ko,
            "slot": slot,
            "kind": kind,
            "region": region,
            "is_noise": noise,
        })

    meta = {
        "tool": "tools/build_dialogue_map.py",
        "project": "aw-kor",
        "format_ref": "muramasa-kor/translations/jp_messages.json",
        "sources": {
            "found_texts": os.path.relpath(args.found, REPO),
            "translation": os.path.relpath(args.trans, REPO),
            "integrity_map": (os.path.relpath(args.integrity, REPO)
                              if have_integrity else None),
            "dialogue_overrides": (os.path.relpath(DIALOGUE_OVERRIDES, REPO)
                                   if os.path.exists(DIALOGUE_OVERRIDES) else None),
            "build_text_overrides": "tools/build_korean_full.py",
            "direct_script_patches": "tools/qa_text_fit.py:load_direct_patch_texts",
        },
        "counts": {
            "total_lines": len(lines),
            "real_dialogue_est": real_count,
            "noise_est": noise_count,
            "with_translation": sum(1 for l in lines if l["ko"]),
            "with_ship_ko": have_ship_ko,
            "missing_ko_among_real": missing_ko,
            "found_rows_bad_addr": found_bad,
            "trans_rows_bad_addr": trans_bad,
        },
        "region_distribution": dict(sorted(region_counter.items())),
        "region_legend": {
            "part1": "0xD8-0xDF (Advance 1 대사)",
            "part2": "0xA0-0xA3 (Advance 2 대사)",
            "campaign": "0xE0-0xE2 (캠페인)",
            "ui": "0x92-0x9E (UI 라벨)",
            "font": "0xB8-0xB9 (폰트/이름그리드 인접)",
            "other": "그 외",
        },
        "noise_heuristic": (
            "가나(히라/가타) 없음 + 키릴/기타 스크립트 섞임, 또는 4자 이하 한자-only "
            "행을 추출 노이즈로 추정. is_noise=true 행도 결과에 포함."
        ),
    }

    out = {"meta": meta, "lines": lines}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 콘솔 통계
    print("[build_dialogue_map] -> %s" % args.out)
    print("  total lines           : %d" % len(lines))
    print("  real dialogue (est)   : %d" % real_count)
    print("  noise (est)           : %d" % noise_count)
    print("  with translation (ko) : %d" % meta["counts"]["with_translation"])
    print("  with ship_ko          : %d" % have_ship_ko)
    print("  missing ko among real : %d" % missing_ko)
    print("  bad addr (found/trans): %d / %d" % (found_bad, trans_bad))
    print("  region distribution   :")
    for r, n in sorted(region_counter.items()):
        print("    %-9s %d" % (r, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
