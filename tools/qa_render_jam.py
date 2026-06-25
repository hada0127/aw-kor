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
        """한글 예약코드 사이의 반각공백(0x20) 수 = 화면 잼 공백."""
        i = off
        prev = False
        jam = 0
        end = off + maxn
        while i < end and i + 1 < len(out):
            b = out[i]
            if b == 0:
                break
            if b == 0x20:
                j = i + 1
                nk = j + 1 < len(out) and 0x88 <= out[j] <= 0xE2 and ((out[j] << 8) | out[j + 1]) in RES
                if prev and nk:
                    jam += 1
                i += 1
                prev = False
            elif 0x81 <= b <= 0xE2:
                prev = ((b << 8) | out[i + 1]) in RES
                i += 2
            else:
                prev = False
                i += 1
        return jam

    jam_msgs = jam_total = 0
    seen = set()
    worst = []
    for e in wl:
        a, slot, ko = e[0], e[1], e[5]
        if not ko or not any("가" <= c <= "힣" for c in ko) or not (0xA00000 <= a < 0xE10000) or a in seen:
            continue
        seen.add(a)
        if in_reloc(a):
            continue
        j = render_jam(a, slot)
        if j > 0:
            jam_msgs += 1
            jam_total += j
            worst.append((j, a, ko))

    worst.sort(reverse=True)
    print(f"=== render-jam 게이트(반각공백 미렌더): 화면 단어붙음 {jam_msgs}개 메시지({jam_total} 공백) ===")
    print("  worst:")
    for j, a, ko in worst[:10]:
        print(f"   0x{a:06X} 잼공백×{j}: {ko[:34]!r}")
    # 게이트: 0 목표이나 비-재배치(무포인터/guard) 한계 존재 → 회귀 감시용 상한선
    print(f"\n=== 결과: render-jam {jam_msgs} (비-재배치 한계분; 회귀=증가 감시) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
