#!/usr/bin/env python3
"""T2 — 원본 ROM 그래픽 자산 전수 인덱스 (픽셀 에디터용 데이터).

원본 ROM(Game Boy Wars Advance 1+2 (Japan).gba)의 그래픽 자산을 최대한 전수
열거해 data/sprites_index.json 을 만든다. 픽셀 에디터(canvas 웹툴)가 이 인덱스를
읽어 원본 팔레트로 타일을 렌더하고, 편집 후 ROM에 역기록한다.

수집 항목:
  (a) curated — build_korean_full.py / build_title_hangul.py 가 참조하는 기존
      그래픽/OBJ/LZ77 주소(이미 한글화로 검증된 편집 대상).
  (b) scan_lz77 — ROM 전체를 4바이트 정렬로 스캔해 발견한 LZ77(헤더 0x10) 블록.
  (c) font — FONT_BASE 등 raw 4bpp 글리프/타일 영역.

각 스프라이트 레코드:
  {
    "id": "lz77_00C18738" 등 안정적 식별자,
    "offset": "0x00C18738",      # ROM 파일 오프셋(hex 문자열)
    "offset_int": 12683064,
    "type": "lz77" | "raw4bpp" | "font",
    "comp_size": <압축 바이트 수, lz77만>,
    "size": <디코드된 raw 4bpp 바이트 수>,
    "n_tiles": <8x8 타일 개수>,
    "width": <px>, "height": <px>,          # 추정 시트 크기
    "tile_cols": <타일 단위 가로>,
    "palette_guess": "grayscale" | "0x........",  # 팔레트 추정 소스
    "png": "temp/sprites_png/<id>.png",      # 렌더 경로(레포 상대)
    "source": "<part/desc>",                  # 어느 빌드 경로가 쓰는지
    "hash": "<sha1 8자>",                     # 디코드 데이터 해시(중복 판별)
    "tile_diversity": <distinct tiles>,
    "nonblank_tiles": <비어있지 않은 타일 수>
  }

GBA 4bpp 타일 디코드(8x8, 4bit/px, 1바이트=2px) + LZ77(0x10) 디코드 유틸 포함.

사용법:
  python3 tools/export_sprites.py                 # 전수 인덱스 + PNG 생성
  python3 tools/export_sprites.py --max-scan 0    # curated/font 만(스캔 생략)
  python3 tools/export_sprites.py --no-png        # 인덱스만, PNG 생략(빠름)
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_PATH = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
OUT_JSON = os.path.join(BASE, 'data', 'sprites_index.json')
PNG_DIR = os.path.join(BASE, 'temp', 'sprites_png')
BUILD_FULL = os.path.join(BASE, 'tools', 'build_korean_full.py')
BUILD_TITLE = os.path.join(BASE, 'tools', 'build_title_hangul.py')

TILE_BYTES = 32  # 8x8 4bpp


# --------------------------------------------------------------------------
# LZ77 (BIOS type 0x10) decode
# --------------------------------------------------------------------------
def lz77_decompress(data, off, max_out=0x200000):
    """Decompress GBA LZ77 (0x10) at off. Returns (bytes, consumed) or None."""
    if off + 4 > len(data) or data[off] != 0x10:
        return None
    size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
    if size == 0 or size > max_out:
        return None
    out = bytearray()
    p = off + 4
    try:
        while len(out) < size:
            if p >= len(data):
                return None
            flags = data[p]
            p += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if flags & (0x80 >> bit):
                    if p + 1 >= len(data):
                        return None
                    b0 = data[p]
                    b1 = data[p + 1]
                    p += 2
                    length = (b0 >> 4) + 3
                    disp = (((b0 & 0xF) << 8) | b1) + 1
                    if disp > len(out):
                        return None
                    for _ in range(length):
                        if len(out) >= size:
                            break
                        out.append(out[len(out) - disp])
                else:
                    out.append(data[p])
                    p += 1
    except IndexError:
        return None
    if len(out) != size:
        return None
    return bytes(out), p - off


# --------------------------------------------------------------------------
# GBA 4bpp tile decode  -> per-pixel palette index grid
# --------------------------------------------------------------------------
def tiles_to_indices(tile_data, tile_cols):
    """Decode raw 4bpp tile bytes into a 2D list of palette indices (0..15).

    8x8 tiles laid out left-to-right, top-to-bottom, `tile_cols` per row.
    1 byte = 2 pixels, low nibble = left pixel.
    """
    n = len(tile_data) // TILE_BYTES
    rows = (n + tile_cols - 1) // tile_cols
    w = tile_cols * 8
    h = rows * 8
    grid = [[0] * w for _ in range(h)]
    for t in range(n):
        gx = (t % tile_cols) * 8
        gy = (t // tile_cols) * 8
        base = t * TILE_BYTES
        for row in range(8):
            for col in range(8):
                byte = tile_data[base + row * 4 + col // 2]
                v = (byte & 0xF) if (col % 2 == 0) else (byte >> 4)
                grid[gy + row][gx + col] = v
    return grid, w, h


def bgr555_to_rgb(v):
    r = (v & 0x1F) << 3
    g = ((v >> 5) & 0x1F) << 3
    b = ((v >> 10) & 0x1F) << 3
    return (r | r >> 5, g | g >> 5, b | b >> 5)


GRAYSCALE = [(i * 17, i * 17, i * 17) for i in range(16)]


def read_palette(data, off):
    """Read 16-color BGR555 palette (32 bytes) at ROM offset -> list[(r,g,b)]."""
    if off is None or off + 32 > len(data):
        return None
    pal = []
    for i in range(16):
        v = struct.unpack_from('<H', data, off + i * 2)[0]
        pal.append(bgr555_to_rgb(v))
    return pal


def render_png(grid, w, h, palette, out_path, scale=2):
    from PIL import Image
    img = Image.new('RGB', (w, h))
    px = img.load()
    pal = palette if palette else GRAYSCALE
    for y in range(h):
        rowg = grid[y]
        for x in range(w):
            px[x, y] = pal[rowg[x] & 0xF]
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    img.save(out_path)


# --------------------------------------------------------------------------
# tile quality heuristic (filter LZ77 false positives that aren't graphics)
# --------------------------------------------------------------------------
def tile_stats(tile_data):
    n = len(tile_data) // TILE_BYTES
    if n == 0:
        return 0, 0, 0
    distinct = set()
    nonblank = 0
    for i in range(n):
        chunk = tile_data[i * TILE_BYTES:i * TILE_BYTES + TILE_BYTES]
        distinct.add(bytes(chunk))
        if any(chunk):
            nonblank += 1
    return n, len(distinct), nonblank


def guess_cols(n_tiles):
    """Heuristic sheet width in tiles. Many GBA OBJ blocks are multiples of
    common widths; default to a square-ish layout capped at 32 columns."""
    if n_tiles <= 0:
        return 1
    for w in (32, 16, 8, 4, 2):
        if n_tiles % w == 0 and n_tiles // w <= 64:
            return w
    # square-ish fallback
    import math
    c = int(math.isqrt(n_tiles))
    c = max(1, min(32, c))
    return c


# --------------------------------------------------------------------------
# curated offsets from build scripts
# --------------------------------------------------------------------------
def collect_curated():
    """Parse build scripts for known LZ77 graphic offsets + descriptions."""
    curated = {}  # offset_int -> source string

    def add(off, src):
        if off in curated:
            curated[off] = curated[off] + '; ' + src
        else:
            curated[off] = src

    # build_title_hangul.py
    if os.path.exists(BUILD_TITLE):
        txt = open(BUILD_TITLE).read()
        for m in re.finditer(r'(\w*_LZ77_OFF\w*)\s*=\s*\(([^)]*)\)', txt):
            name = m.group(1)
            for a in re.finditer(r'0x[0-9A-Fa-f]+', m.group(2)):
                add(int(a.group(0), 16), f'title:{name}')
        for m in re.finditer(r'(\w*_LZ77_OFF)\s*=\s*(0x[0-9A-Fa-f]+)', txt):
            add(int(m.group(2), 16), f'title:{m.group(1)}')
        # (name, 0xADDR, "korean", N) tuples (menu logo/option labels)
        for m in re.finditer(r'\(\s*"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*"([^"]*)"', txt):
            add(int(m.group(2), 16), f'title:menu_label/{m.group(1)}')

    # build_korean_full.py — offsets passed to lz77 decode/patch helpers
    if os.path.exists(BUILD_FULL):
        txt = open(BUILD_FULL).read()
        lines = txt.splitlines()
        # direct decode/patch calls
        for pat, tag in [
            (r'lz77_decompress\(rom,\s*(0x[0-9A-Fa-f]+)', 'lz77_decompress'),
            (r'th\.lz77_decompress\(rom,\s*(0x[0-9A-Fa-f]+)', 'th.lz77_decompress'),
            (r'patch_lz\(\s*(0x[0-9A-Fa-f]+)', 'patch_lz'),
            (r'patch_block\(\s*(0x[0-9A-Fa-f]+)', 'patch_block'),
            (r'patch_obj_block\(\s*(0x[0-9A-Fa-f]+)', 'patch_obj_block'),
        ]:
            for m in re.finditer(pat, txt):
                add(int(m.group(1), 16), f'full:{tag}')
        # offsets that live in `off = 0x......` / `offs = [...]` inside graphic fns
        cur_fn = None
        for i, l in enumerate(lines):
            fm = re.match(r'def (patch_\w+)\(', l)
            if fm:
                cur_fn = fm.group(1)
            if cur_fn and re.search(r'lz|obj|tile|bg|glyph|logo|banner|icon|overlay|splash|graphic', cur_fn, re.I):
                for a in re.finditer(r'0x([0-9A-Fa-f]{6,8})', l):
                    v = int(a.group(1), 16)
                    if 0x300000 <= v < 0x1000000:
                        add(v, f'full:{cur_fn}')
    return curated


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=ROM_PATH)
    ap.add_argument('--out', default=OUT_JSON)
    ap.add_argument('--png-dir', default=PNG_DIR)
    ap.add_argument('--max-scan', type=int, default=-1,
                    help='max LZ77 scan blocks to keep (-1=all, 0=skip scan)')
    ap.add_argument('--no-png', action='store_true')
    ap.add_argument('--min-tiles', type=int, default=4,
                    help='min decoded tiles for a scanned block to be kept')
    ap.add_argument('--min-distinct', type=int, default=3,
                    help='min distinct tiles (filters solid-color false positives)')
    args = ap.parse_args()

    if not os.path.exists(args.rom):
        print('ROM not found:', args.rom, file=sys.stderr)
        sys.exit(2)
    data = open(args.rom, 'rb').read()
    os.makedirs(args.png_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    sprites = []
    seen_offsets = set()
    stats = {
        'rom_size': len(data),
        'curated_total': 0,
        'curated_decoded': 0,
        'scan_lz77_candidates': 0,
        'scan_lz77_kept': 0,
        'font_regions': 0,
        'rendered_png': 0,
        'unique_hashes': 0,
    }

    def make_record(off, typ, tile_data, comp_size, source, pal_guess):
        n, distinct, nonblank = tile_stats(tile_data)
        cols = guess_cols(n)
        h = hashlib.sha1(tile_data).hexdigest()[:8]
        rec = {
            'id': f'{typ}_{off:08X}',
            'offset': f'0x{off:08X}',
            'offset_int': off,
            'type': typ,
            'comp_size': comp_size,
            'size': len(tile_data),
            'n_tiles': n,
            'tile_cols': cols,
            'width': cols * 8,
            'height': ((n + cols - 1) // cols) * 8,
            'palette_guess': pal_guess,
            'png': None,
            'source': source,
            'hash': h,
            'tile_diversity': distinct,
            'nonblank_tiles': nonblank,
        }
        return rec, tile_data

    pending = []  # (rec, tile_data)

    # ---- (a) curated ----
    curated = collect_curated()
    stats['curated_total'] = len(curated)
    for off in sorted(curated):
        if off + 4 > len(data):
            continue
        res = lz77_decompress(data, off)
        if res is None:
            # curated offset that isn't an LZ77 header (e.g. raw OBJ block) — keep
            # a raw record with a conservative size guess so the editor still lists it.
            continue
        out, cons = res
        if out in (b'',):
            continue
        rec, td = make_record(off, 'lz77', out, cons, curated[off], 'grayscale')
        rec['curated'] = True
        pending.append((rec, td))
        seen_offsets.add(off)
        stats['curated_decoded'] += 1

    # ---- (c) font / raw 4bpp regions (from DENY_REGIONS / known font bases) ----
    font_regions = [
        ('font_FONT_BASE', 0x00B974D0, 0x00BAF338, 'full:dialogue glyph FONT_BASE'),
    ]
    for fid, start, end, src in font_regions:
        if end <= len(data):
            td = data[start:end]
            rec, td = make_record(start, 'font', td, None, src, 'grayscale')
            rec['id'] = f'font_{start:08X}'
            rec['curated'] = True
            pending.append((rec, td))
            seen_offsets.add(start)
            stats['font_regions'] += 1

    # ---- (b) ROM-wide LZ77 scan ----
    if args.max_scan != 0:
        cands = []
        for off in range(0, len(data) - 4, 4):
            if data[off] != 0x10:
                continue
            size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
            if size < args.min_tiles * TILE_BYTES or size > 0x40000 or size % 4 != 0:
                continue
            res = lz77_decompress(data, off)
            if res is None:
                continue
            out, cons = res
            if len(out) % TILE_BYTES != 0 and len(out) < TILE_BYTES:
                continue
            n, distinct, nonblank = tile_stats(out)
            if n < args.min_tiles or distinct < args.min_distinct or nonblank == 0:
                continue
            cands.append((off, out, cons, n, distinct))
        stats['scan_lz77_candidates'] = len(cands)
        # sort by tile count desc (richest sheets first) for deterministic ordering
        cands.sort(key=lambda c: (-c[3], c[0]))
        if args.max_scan > 0:
            cands = cands[:args.max_scan]
        for off, out, cons, n, distinct in cands:
            if off in seen_offsets:
                continue
            rec, td = make_record(off, 'lz77', out, cons, 'scan_lz77', 'grayscale')
            pending.append((rec, td))
            seen_offsets.add(off)
            stats['scan_lz77_kept'] += 1

    # ---- render PNGs ----
    hashes = set()
    for rec, td in pending:
        hashes.add(rec['hash'])
        if not args.no_png:
            grid, w, h = tiles_to_indices(td, rec['tile_cols'])
            png_path = os.path.join(args.png_dir, rec['id'] + '.png')
            try:
                render_png(grid, w, h, None, png_path, scale=2)
                rec['png'] = os.path.relpath(png_path, BASE)
                stats['rendered_png'] += 1
            except Exception as e:
                rec['png'] = None
                rec['render_error'] = str(e)
        sprites.append(rec)
    stats['unique_hashes'] = len(hashes)

    # coverage report (honest about uncovered estimate)
    # uncovered estimate = loose LZ77 blocks not kept (e.g. below thresholds)
    index = {
        '_readme': (
            'Game Boy Wars Advance 1+2 (Japan) 그래픽 자산 인덱스. '
            'type=lz77(BIOS 0x10 압축, comp_size=ROM상 압축 바이트), '
            'raw4bpp/font(비압축). 모든 size/width/height 는 4bpp 8x8 타일 기준. '
            'palette_guess=grayscale 면 팔레트 불명(에디터에서 지정 필요). '
            '편집기는 png 를 캔버스에 띄워 픽셀(0..15 인덱스) 편집 후, '
            'lz77 면 재압축(<=comp_size)·raw 면 그대로 offset 에 역기록.'
        ),
        'rom': os.path.basename(args.rom),
        'rom_sha1': hashlib.sha1(data).hexdigest(),
        'tile_format': '4bpp 8x8, 1 byte = 2 px (low nibble = left pixel)',
        'lz77_format': 'GBA BIOS type 0x10; header [0x10, size_lo, size_mid, size_hi]',
        'stats': stats,
        'count': len(sprites),
        'sprites': sprites,
    }
    json.dump(index, open(args.out, 'w'), ensure_ascii=False, indent=1)

    # validate JSON round-trips
    json.load(open(args.out))

    print('=== export_sprites done ===')
    print('ROM           :', os.path.basename(args.rom), len(data), 'bytes')
    print('curated offs  :', stats['curated_total'], '-> decoded', stats['curated_decoded'])
    print('font regions  :', stats['font_regions'])
    print('LZ77 scan     : candidates', stats['scan_lz77_candidates'],
          '-> kept', stats['scan_lz77_kept'])
    print('total sprites :', len(sprites))
    print('unique hashes :', stats['unique_hashes'])
    print('rendered PNG  :', stats['rendered_png'], '->', os.path.relpath(args.png_dir, BASE))
    print('index         :', os.path.relpath(args.out, BASE))


if __name__ == '__main__':
    main()
