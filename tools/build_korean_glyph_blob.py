#!/usr/bin/env python3
"""Phase C-1: 한글 글리프 블롭 생성 (dedup).

translation_for_import.csv의 고유 한글 음절을 추출 → render_galmuri_8x16로 각 음절의
top/bot 8x8 타일(각 0x20 bytes, 4bpp, ink 인덱스 10) 렌더 → 중복 타일 제거 후
연속 블롭(data/korean_glyph_blob.bin) + 음절→(top_tile, bot_tile) 로컬 인덱스 맵
(data/syllable_to_glyph.json) 생성.

로컬 타일 인덱스는 0-based. 실제 FONT_BASE 인덱스 = KOR_TILE_BASE + local_idx
(KOR_TILE_BASE는 Session 2 배치 단계에서 확정).
"""
import csv, json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from render_galmuri_8x16 import render_char

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'data/translation_for_import.csv')
BLOB = os.path.join(ROOT, 'data/korean_glyph_blob.bin')
MAP = os.path.join(ROOT, 'data/syllable_to_glyph.json')


def extract_syllables(path):
    syl = set()
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            for ch in (row.get('korean') or ''):
                if '가' <= ch <= '힣':
                    syl.add(ch)
    return sorted(syl)


def main():
    syl = extract_syllables(CSV)
    tile_index = {}     # tile_bytes -> local idx
    blob = bytearray()
    syl_map = {}

    def add_tile(tb):
        if tb not in tile_index:
            tile_index[tb] = len(tile_index)
            blob.extend(tb)
        return tile_index[tb]

    empty = 0
    for ch in syl:
        top, bot = render_char(ch)
        if not any(top) and not any(bot):
            empty += 1
        ti = add_tile(top)
        bi = add_tile(bot)
        syl_map[ch] = {"top": ti, "bot": bi}

    meta = {
        "syllables": len(syl),
        "unique_tiles": len(tile_index),
        "blob_bytes": len(blob),
        "tile_bytes": 0x20,
        "ink_index": 10,
        "naive_tiles": 2 * len(syl),
        "empty_render": empty,
        "blob_sha1": hashlib.sha1(bytes(blob)).hexdigest(),
        "note": "local idx 0-based; FONT_BASE idx = KOR_TILE_BASE + local_idx (Session 2)",
    }

    with open(BLOB, 'wb') as f:
        f.write(blob)
    with open(MAP, 'w', encoding='utf-8') as f:
        json.dump({"_meta": meta, "map": syl_map}, f, ensure_ascii=False, indent=0)

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"wrote {BLOB} ({len(blob)} bytes), {MAP}")


if __name__ == '__main__':
    main()
