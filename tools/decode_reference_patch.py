#!/usr/bin/env python3
"""외부 배포 한글패치(서양 USA판 Advance Wars 1/2) 복원 + 한글 디코드.

목적: 같은 게임의 외부 한글 번역을 디코드해 **우리 미번역 UI/시스템 갭의 타깃 번역**을 얻는다.
- full-delta(.bin: AW2FULL1/AW1TST38) = USA 원본에서 타깃을 재구성(헤더+offset/length 레코드).
- 한글 인코딩: 2바이트 코드(c0~c5). 폰트 0x810000(AW2), 8x16 4bpp, code→glyph idx:
    idx = (code & 0xff) + (-0x90 + (lead - 0xc0) * 122)
  글리프를 Galmuri11-Condensed로 glyph-match(픽셀 일치)해 code→음절 표를 자동 구축(2350자 참조).

입력(다운로드 폴더): USA 원본 .gba + 패치 .bin. 경로는 --usa/--patch로 지정.
출력: data/reference/<name>_korean_strings.json (디코드된 distinct 문자열).

사용:
  python3 tools/decode_reference_patch.py --usa "~/Downloads/.../AW2 USA.gba" \
      --patch /tmp/awref/aw2/AW2_..._FULLDELTA_v0.31.bin --magic AW2FULL1 \
      --font 0x810000 --name aw2
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bdf import load_bdf, glyph_grid  # noqa: E402

SYLCODE = ROOT / "data" / "syllable_to_code_2350.json"
GALMURI = ROOT / "reference" / "fonts" / "Galmuri11-Condensed.bdf"


def apply_fulldelta(src: bytes, patch: bytes, magic: bytes) -> bytes:
    assert patch[:8] == magic, patch[:8]
    tlen = struct.unpack_from("<I", patch, 8)[0]
    res = bytearray(tlen)
    res[: min(len(src), tlen)] = src[: min(len(src), tlen)]
    rcnt = struct.unpack_from("<I", patch, 12)[0]
    pos = 16
    for _ in range(rcnt):
        off, ln = struct.unpack_from("<II", patch, pos)
        pos += 8
        res[off : off + ln] = patch[pos : pos + ln]
        pos += ln
    return bytes(res)


def font_bitmap(rom: bytes, font_base: int, idx: int):
    g = rom[font_base + idx * 64 : font_base + (idx + 1) * 64]
    bm = [[0] * 8 for _ in range(16)]
    for r in range(16):
        for c in range(0, 8, 2):
            b = g[r * 4 + c // 2]
            bm[r][c] = 1 if (b & 0xF) else 0
            bm[r][c + 1] = 1 if ((b >> 4) & 0xF) else 0
    return bm


def galmuri_bitmap(font, ch, top_pad=3):
    if ord(ch) not in font:
        return None
    grid, w, h, xo, yo = glyph_grid(font[ord(ch)])
    bm = [[0] * 8 for _ in range(16)]
    for r in range(h):
        cr = top_pad + r
        for c in range(w):
            cc = c + xo
            if 0 <= cr < 16 and 0 <= cc < 8 and grid[r][c]:
                bm[cr][cc] = 1
    return bm


def build_idx2syl(rom, font_base, nglyph=1300):
    font, _ = load_bdf(str(GALMURI))
    syls = list(json.load(open(SYLCODE, encoding="utf-8")).keys())
    galref = [(s, galmuri_bitmap(font, s)) for s in syls]
    galref = [(s, b) for s, b in galref if b]
    idx2syl = {}
    for i in range(nglyph):
        fb = font_bitmap(rom, font_base, i)
        if not any(any(r) for r in fb):
            idx2syl[i] = None
            continue
        best, bs = None, -1
        for s, gb in galref:
            sc = sum(1 for r in range(16) for c in range(8) if fb[r][c] == gb[r][c])
            if sc > bs:
                bs, best = sc, s
        idx2syl[i] = best
    return idx2syl


def make_decoder(rom, font_base):
    idx2syl = build_idx2syl(rom, font_base)

    def code2syl(code):
        lead = code >> 8
        idx = (code & 0xFF) + (-0x90 + (lead - 0xC0) * 122)
        return idx2syl.get(idx) if 0 <= idx < 1300 else None

    def decode_str(off):
        out = []
        i = off
        while i < len(rom):
            b = rom[i]
            if b == 0:
                break
            if 0xC0 <= b <= 0xC5 and i + 1 < len(rom):
                out.append(code2syl((b << 8) | rom[i + 1]) or "�")
                i += 2
            elif b == 0x0D:
                out.append("\n")
                i += 1
            elif b == 0x20:
                out.append(" ")
                i += 1
            elif 0x21 <= b < 0x7F:
                out.append(chr(b))
                i += 1
            else:
                i += 1
        return "".join(out)

    return decode_str


def extract_strings(rom, decode_str, lo, hi):
    seen, out = set(), []
    i = lo
    while i < hi:
        if 0xC0 <= rom[i] <= 0xC5 and (i == lo or rom[i - 1] in (0, 0x0D)):
            s = decode_str(i)
            if len(s.strip()) >= 1 and s not in seen:
                seen.add(s)
                out.append(s)
        while i < hi and rom[i] != 0:
            i += 1
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usa", required=True)
    ap.add_argument("--patch", required=True)
    ap.add_argument("--magic", required=True)
    ap.add_argument("--font", default="0x810000")
    ap.add_argument("--range", default="0x810000:0x880000")
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    src = open(os.path.expanduser(args.usa), "rb").read()
    patch = open(os.path.expanduser(args.patch), "rb").read()
    rom = apply_fulldelta(src, patch, args.magic.encode())
    font_base = int(args.font, 16)
    lo, hi = (int(x, 16) for x in args.range.split(":"))
    decode_str = make_decoder(rom, font_base)
    strings = extract_strings(rom, decode_str, lo, hi)
    bad = sum(1 for s in strings if "�" in s)
    out_dir = ROOT / "data" / "reference"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}_korean_strings.json"
    json.dump(strings, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{args.name}: {len(strings)} distinct strings, undecoded glyphs in {bad} ({100*bad/max(len(strings),1):.1f}%)")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
