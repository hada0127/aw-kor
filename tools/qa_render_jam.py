#!/usr/bin/env python3
"""QA(render-aware 게이트): 대사 렌더러가 **반각공백(0x20)을 글리프 폭 0으로 스킵**(화면 단어붙음)하는 것을
바이트 레벨에서 잡는다. qa_spacing은 0x20을 공백으로 세는 사각지대 → 실화면 잼을 못 봄(2026-06-25 발견).

판정: 한글 예약코드 사이의 **반각공백(0x20)** = 화면 잼. 전각(0x8140)은 정상 렌더(제외).
재배치 범위 [msg, msg+old_len)는 free space에서 전각 변환본을 렌더하므로 제외(in-place 슬롯은 stale).

출력: 화면 단어붙음 메시지 수. 사용: python3 tools/qa_render_jam.py
"""
from __future__ import annotations

import bisect
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "output", "game_wars_korean_full.gba")
MAP = os.path.join(BASE, "temp", "integrity_map.json")
MANIFEST = os.path.join(BASE, "temp", "repoint_manifest.json")
SYLCODE = os.path.join(BASE, "data", "syllable_to_code_2350.json")


def main():
    out = open(OUT, "rb").read()
    RES = set(int(v, 16) for v in json.load(open(SYLCODE, encoding="utf-8")).values())
    wl = json.load(open(MAP, encoding="utf-8"))
    man = [m for m in json.load(open(MANIFEST, encoding="utf-8")) if m.get("status") == "relocated"] \
        if os.path.exists(MANIFEST) else []
    ranges = sorted((int(m["msg"], 16), int(m["msg"], 16) + m.get("old_len", 0)) for m in man)
    starts = [r[0] for r in ranges]

    def in_reloc(a):
        i = bisect.bisect_right(starts, a) - 1
        return i >= 0 and a < ranges[i][1]

    def render_jam(off, maxn):
        """content(=enc_len 범위) 내부 반각공백(0x20)을 next 바이트 종류로 분류:
        - sjis: next=SJIS lead(0x81-0xE2, content path) → Part1 render hook이 화면 공백 렌더.
        - asc : next=printable ASCII(0x21-0x7E, jump table 경로) → render hook 미적용 = 잔여.
        ★maxn=enc_len(슬롯 아님). **다음 글자도 content 내부**(i+1<end)여야 잼 — 슬롯 끝 FILL 패딩이
        다음 구조(▼=0x6B/제어/다음 메시지)와 잼으로 오인되던 false positive 제거(2026-06-25)."""
        i = off
        prev = False
        sjis = asc = 0
        end = off + maxn
        while i < end:
            b = out[i]
            if b == 0:
                break
            if b == 0x20:
                if prev and i + 1 < end:            # 다음 글자가 content 내부일 때만
                    nb = out[i + 1]
                    if 0x81 <= nb <= 0xE2:
                        sjis += 1
                    elif 0x21 <= nb <= 0x7E:
                        asc += 1
                i += 1
                prev = False
            elif 0x81 <= b <= 0xE2:
                prev = True
                i += 2
            elif 0x21 <= b <= 0x7E:
                prev = True
                i += 1
            else:
                prev = False
                i += 1
        return sjis, asc

    # Part1 대사 파서(0x8b12xxx) 0x20 렌더 hook 적용 여부(2026-06-25 완성, in-game 확증).
    # 적용 시 Part1 영역(>=0xC00000) interior 0x20은 화면에 공백 렌더 → 잼 아님(hook 처리).
    HOOK_ON = (
        len(out) > 0xB120F8
        and int.from_bytes(out[0xB120F4:0xB120F8], "little") == 0x08F30500
        and out[0xB12764:0xB1276C] == bytes.fromhex("004800474105f308")
    )
    P1 = 0xC00000  # Part1/Part2 경계(render-jam은 Part1=0xD8-0xDC, Part2=0xA0-0xA3)

    # 주소별 **마지막 writer**(ROM 바이트 = 마지막 write)의 enc_len을 content 범위로 사용.
    # (import-csv를 script:*/dialogue-override가 덮어쓰는 다중 writer 정합 — enc_len이 실제 content 길이.)
    last = {}
    for e in wl:
        last[e[0]] = e

    hook_msgs = hook_total = jam_msgs = jam_total = 0
    worst = []
    for a in sorted(last):
        e = last[a]
        slot, enclen, ko = e[1], e[2], e[5]
        if not (0xA00000 <= a < 0xE10000) or enclen <= 0:
            continue
        if in_reloc(a):
            continue
        sjis, asc = render_jam(a, enclen)   # ★content(enc_len) 범위만 — 슬롯 FILL 패딩 제외
        if sjis + asc <= 0:
            continue
        # 렌더 hook 적용 범위:
        #  - Part1(>=0xC00000): render hook이 content path(next=SJIS 0x81-0xE2)만 처리. next=ASCII(jump table)는 잔여.
        #  - Part2(<0xC00000): 별도 파서(0x313/0xB11) 자체 공백 hook이 0x20 렌더(기존 "완료"). → 면제.
        if a >= P1:
            hooked = sjis if HOOK_ON else 0
            residual = asc
        else:
            hooked = sjis + asc       # Part2 공백 hook 렌더
            residual = 0
        if hooked:
            hook_msgs += 1
            hook_total += hooked
        if residual:
            jam_msgs += 1
            jam_total += residual
            worst.append((residual, a, "Part1-ASCII(jumptable)", str(ko)[:30]))

    worst.sort(reverse=True, key=lambda x: x[0])
    print("=== render-jam 게이트(반각공백 미렌더, content=enc_len 범위) ===")
    if HOOK_ON:
        print(f"  ✅ Part1 대사 0x20 렌더 hook ON → Part1 next=SJIS {hook_msgs}메시지({hook_total} 공백) 화면 렌더")
    print(f"  ⚠ 잔여 {jam_msgs}메시지({jam_total} 공백) — Part1 next=ASCII(jump table) / 기타:")
    for r, a, tag, ko in worst[:12]:
        print(f"   0x{a:06X} [{tag}] 잼×{r}: {ko!r}")
    print(f"\n=== 결과: render-jam 잔여 {jam_total} 공백/{jam_msgs} 메시지 (Part1 SJIS hook {hook_total} 제외) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
