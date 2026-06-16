#!/usr/bin/env python3
"""대사 조각 그룹화 — 인게임 한 메시지 단위로 묶기 (codex/agy/claude 자문 종합).

발견(claude 자문, ROM 바이트 워크 + B-team kor.tbl 대조): dialogue_map의 '조각'들은
별도 포인터 문자열이 아니라 **하나의 연속 ROM 문자열**을 추출이 제어코드/변수삽입 지점에서
자른 것. 엔진은 포인터 하나를 읽어 0x00(종료)까지 2바이트씩 walk하며 한 대사창에 출력.
  0x00 = 종료, 0x0A = 줄바꿈, 0x09 = 제어, 0x6b/0x72/0x77/0x57 = 박스/라인 제어,
  0x33 <SJIS literal> 0x30 / 0x32 <literal> 0x30 = 변수삽입 토큰(literal=런타임 치환 기본값)

그룹화(권위·결정적): 주소순으로 인접한 동일 region·비노이즈 조각들 중, **사이 ROM 구간에
0x00이 없으면 같은 메시지**(변수삽입/제어만 있음), 0x00이 있으면 경계. 휴리스틱 문법추정 미사용.
안전장치: 그룹 크기 상한 플래그, 노이즈 제외, region 경계, 수동 오버라이드(data/dialogue_group_overrides.json).

편집/빌드: 그룹은 표시·문맥용. 저장은 기존대로 **주소별** dialogue_overrides.json에 역기록(조각마다
독립 슬롯). 빌드는 [addr,addr+slot)만 쓰고 gap(제어/삽입)은 손대지 않아 자동 보존(신규 빌드로직 0).

출력: data/dialogue_groups.json
실행: python3 tools/build_dialogue_groups.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(BASE, "original", "Game Boy Wars Advance 1+2 (Japan).gba")
DMAP = os.path.join(BASE, "data", "dialogue_map.json")
OVERRIDES = os.path.join(BASE, "data", "dialogue_group_overrides.json")
OUT = os.path.join(BASE, "data", "dialogue_groups.json")

MAX_GAP = 0x60          # 조각 간 허용 ROM 간격(초과 시 경계)
FLAG_SIZE = 16          # 이 이상 조각 수 그룹은 수동검토 플래그
GROUP_REGIONS = {"part1", "part2", "campaign"}  # 자동 그룹 대상(나머지는 단독)


def addr_int(a):
    return int(a, 16) if isinstance(a, str) else int(a)


def sjis_len(text):
    """원문(JA) 바이트 길이 근사 — 조각 텍스트 끝 위치 계산용."""
    try:
        return len(text.encode("shift_jis"))
    except Exception:
        n = 0
        for ch in text:
            try:
                n += len(ch.encode("shift_jis"))
            except Exception:
                n += 2
        return n


def decode_gap(rom, start, end):
    """조각 사이 ROM 구간의 제어/변수삽입 토큰을 사람이 읽는 세그먼트로."""
    segs = []
    i = start
    while i < end and i < len(rom):
        b = rom[i]
        if b == 0x00:
            segs.append({"kind": "end", "raw": "00"}); i += 1; continue
        if b in (0x32, 0x33) and i + 1 < end:
            # 변수삽입: 0x33 <SJIS literal...> 0x30
            j = i + 1
            lit = bytearray()
            while j < end and rom[j] != 0x30:
                lit.append(rom[j]); j += 1
            default = ""
            try:
                default = bytes(lit).decode("shift_jis", "replace")
            except Exception:
                default = bytes(lit).hex()
            segs.append({"kind": "var", "raw": rom[i:j + 1].hex(), "default": default})
            i = j + 1; continue
        if b == 0x0A:
            segs.append({"kind": "newline", "raw": "0a"}); i += 1; continue
        if b in (0x09, 0x6B, 0x72, 0x77, 0x57, 0x69):
            segs.append({"kind": "ctrl", "raw": "%02x" % b}); i += 1; continue
        i += 1  # 기타(조각 텍스트 잔여 등) 무시
    return segs


def main():
    rom = open(ROM, "rb").read()
    dm = json.load(open(DMAP, encoding="utf-8"))
    over = json.load(open(OVERRIDES, encoding="utf-8")) if os.path.exists(OVERRIDES) else {}
    force_split = set(over.get("split_before", []))   # 이 주소 앞에서 강제 분리
    force_join = set(over.get("join_before", []))      # 이 주소 앞 강제 결합

    reals = [l for l in dm["lines"] if not l.get("is_noise") and (l.get("ja") or "").strip()]
    reals.sort(key=lambda l: addr_int(l["address"]))

    groups = []
    cur = None
    prev = None
    for l in reals:
        a = addr_int(l["address"])
        new_group = True
        if prev is not None:
            pa = addr_int(prev["address"])
            pend = pa + sjis_len(prev.get("ja") or "")
            gap = a - pa
            same_region = prev.get("region") == l.get("region") and l.get("region") in GROUP_REGIONS
            gap_has_zero = (0x00 in rom[pend:a]) if 0 <= pend <= a < len(rom) else True
            joinable = same_region and gap < MAX_GAP and not gap_has_zero
            if l["address"] in force_split:
                joinable = False
            if l["address"] in force_join:
                joinable = True
            new_group = not joinable
        if new_group:
            cur = {"members": [], "region": l.get("region"), "segments": []}
            groups.append(cur)
        else:
            # 직전 조각과 현재 조각 사이의 삽입/제어 세그먼트 기록
            pa = addr_int(prev["address"]); pend = pa + sjis_len(prev.get("ja") or "")
            cur["segments"].extend(decode_gap(rom, pend, a))
        cur["members"].append({"address": l["address"], "ja": l.get("ja") or "",
                               "ko": l.get("ko") or "", "ship_ko": l.get("ship_ko"),
                               "slot": l.get("slot"), "id": l.get("id"), "kind": l.get("kind")})
        # 세그먼트 흐름에 조각 텍스트 표식
        cur["segments"].append({"kind": "frag", "address": l["address"]})
        prev = l

    # 마무리: 메타 + 플래그 + assembled
    out_groups = []
    multi = 0
    for gi, g in enumerate(g for g in groups):
        n = len(g["members"])
        if n > 1:
            multi += 1
        # assembled JA/KO: 조각 텍스트 + 변수삽입 표식 순서대로
        def assemble(field):
            parts = []
            mi = 0
            for s in g["segments"]:
                if s["kind"] == "frag":
                    m = next((m for m in g["members"] if m["address"] == s["address"]), None)
                    parts.append((m.get(field) or "") if m else "")
                elif s["kind"] == "var":
                    parts.append("⟦%s⟧" % (s.get("default") or "var"))
                elif s["kind"] == "newline":
                    parts.append("\n")
            return "".join(parts)
        out_groups.append({
            "group_id": "g_%s" % g["members"][0]["address"].replace("0x", ""),
            "region": g["region"], "size": n,
            "flagged": n >= FLAG_SIZE,
            "members": g["members"],
            "segments": g["segments"],
            "assembled_ja": assemble("ja"),
            "assembled_ko": assemble("ko"),
        })

    meta = {"tool": "tools/build_dialogue_groups.py", "rom": os.path.basename(ROM),
            "method": "ROM 0x00-delimited message scan (codex/agy/claude 자문 종합)",
            "max_gap": MAX_GAP, "flag_size": FLAG_SIZE,
            "total_reals": len(reals), "groups": len(out_groups),
            "multi_fragment_groups": multi,
            "flagged_groups": sum(1 for g in out_groups if g["flagged"])}
    json.dump({"meta": meta, "groups": out_groups}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("groups: %d (multi-fragment %d, flagged %d) from %d reals → %s"
          % (len(out_groups), multi, meta["flagged_groups"], len(reals), OUT))
    # 표본
    for g in out_groups:
        if g["size"] >= 2 and g["region"] == "part1":
            print("  e.g. %s: %r" % (g["group_id"], g["assembled_ja"][:60]))
            break


if __name__ == "__main__":
    main()
