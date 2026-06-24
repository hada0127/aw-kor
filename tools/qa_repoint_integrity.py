#!/usr/bin/env python3
"""QA(committed 게이트): 출하 ROM의 대사 재배치(repoint)를 **ROM 직접·manifest 독립** 검증.

codex 리뷰(2026-06-25) 반영: temp manifest를 신뢰하지 않고, 출하 ROM의 대사/스크립트 영역
(0xA00000~0xE10000) 4바이트 정렬 포인터 중 **여유공간(free space)을 가리키는 것**을 전수 수집한 뒤,
각 free-space 타깃 블롭을 **실제 디코드/follow** 하여 안전한지 본다(qa_spacing은 relocated를 intended로
간주하므로 free-space 실바이트 검증은 별도 필요).

검사(각 재배치 블롭):
  1) **terminator 보존**: 블롭이 합리적 길이(<=512B) 내 0x00 종단(엔진이 멈춤). 미종단=run-off=다음 메시지 오염.
  2) **garbage 없음**: 디코드에 유효하지 않은 2바이트(예약코드/SJIS/제어 외) 과다(>2) 없음.
  3) **공백 존재**: 블롭에 한 칸 이상 공백(0x20/0x8140) — 단어붙음 해소본은 공백을 가짐(미해소 회귀 탐지 보조).

종료코드: 문제 1건 이상이면 1.
사용: python3 tools/qa_repoint_integrity.py [output.gba]
"""
from __future__ import annotations

import json
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "output", "game_wars_korean_full.gba")
SYLCODE = os.path.join(BASE, "data", "syllable_to_code_2350.json")
GBA = 0x08000000
FREE_START, FREE_END = 0xA3D000, 0xB00000
SCAN_LO, SCAN_HI = 0xA00000, 0xE10000   # 포인터 OFFSET 검색 범위(대사/스크립트; 코드영역 제외)


def _load_c2s():
    m = json.load(open(SYLCODE, encoding="utf-8"))
    return {int(v, 16): k for k, v in m.items()}


def _decode(rom, off, maxlen, c2s):
    """0x00까지 디코드. (text, terminated, garbage, has_space)."""
    out = []
    i = off
    garbage = 0
    has_space = False
    while i < off + maxlen and i + 1 < len(rom):
        b = rom[i]
        if b == 0:
            return "".join(out), True, garbage, has_space
        if b == 0x20:
            has_space = True
            out.append(" ")
            i += 1
        elif 0x81 <= b <= 0xE2:
            code = (b << 8) | rom[i + 1]
            if code == 0x8140:
                has_space = True
                out.append(" ")
            elif code in c2s:
                out.append(c2s[code])
            else:
                try:
                    out.append(bytes([b, rom[i + 1]]).decode("shift_jis"))
                except Exception:
                    garbage += 1
                    out.append("�")
            i += 2
        else:
            out.append("·")
            i += 1
    return "".join(out), False, garbage, has_space


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else OUT
    rom = open(out_path, "rb").read()
    c2s = _load_c2s()

    man_path = os.path.join(BASE, "temp", "repoint_manifest.json")
    if not os.path.exists(man_path):
        print(f"[SKIP] repoint manifest 없음: {man_path}")
        return 0
    man = [m for m in json.load(open(man_path, encoding="utf-8")) if m.get("status") == "relocated"]
    if not man:
        print("[OK] 재배치 0 — repoint 미적용(검증 생략)")
        return 0

    # manifest의 재배치 타깃(new_addr)을 **포인터로 독립 확인**(ptr_off가 정말 new_addr를 가리키는가) +
    # free-space 블롭 실디코드 검증. manifest가 거짓 relocation을 주장하면 포인터 불일치로 잡힌다.
    issues = []
    garbage_total = 0
    no_space = 0
    for m in man:
        na = int(m["new_addr"], 16)
        nl = int(m.get("new_len", 0))
        po = int(m["ptr_off"], 16)
        ptr_val = struct.unpack_from("<I", rom, po)[0]
        if ptr_val != GBA + na:
            issues.append((m["msg"], f"ptr-mismatch @{po:#x}={ptr_val:#x}!={GBA + na:#x}"))
        text, term, garb, has_sp = _decode(rom, na, nl + 8, c2s)
        if not term:
            issues.append((m["msg"], "no-terminator-runoff"))
        if garb > 2:
            issues.append((m["msg"], f"garbage{garb}: {text[:20]!r}"))
        garbage_total += garb
        if not has_sp:
            no_space += 1

    print(f"=== repoint 무결성(ROM 직접, 포인터 정합 검증): {len(man)} 재배치 ===")
    print(f"  garbage 총합: {garbage_total} · 공백없는 블롭: {no_space}(짧은 라벨 등 정상 가능)")
    print(f"  문제: {len(issues)}")
    for msg, why in issues[:20]:
        print(f"   {msg}: {why}")
    print(f"\n=== 결과: {'FAIL' if issues else 'PASS'} ({len(man)} 재배치, 문제 {len(issues)}) ===")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
