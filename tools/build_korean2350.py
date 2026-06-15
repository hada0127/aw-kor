#!/usr/bin/env python3
"""T1: KS X 1001 완성형 2350자 한글 폰트 확보 (build_korean_full.py 직접수정 없이 데이터+도구만).

현재 data/syllable_to_code.json 은 1030개만 매핑되어 있어, 표준 완성형 2350자 중 다수가
미매핑이다. 그 음절을 쓰는 번역은 build_korean_full.py 의 encode_text 에서 KeyError(unmapped)
가 난다. 이 도구는 2350 전체를 커버하는 글리프 블롭과 매핑 JSON 을 생성한다.

핵심 호환성 원칙 (기존 출하본을 깨지 않음 — additive only):
  - 기존 1030 음절의 SJIS code 값은 그대로 유지한다 (data/syllable_to_code.json 과 byte-identical).
  - 기존 글리프 블롭(data/korean_glyph_blob.bin)의 타일 순서/local idx 도 그대로 유지한다.
    (기존 800 타일을 동일 순서로 먼저 채운 뒤, 신규 음절 타일만 뒤에 append → local idx 보존)
  - 신규 1320 음절은 reserved 풀(extend_pool)의 아직 안 쓰인 code 에 정렬 순서로 추가 할당.

산출물:
  - data/syllable_to_code_2350.json     : 한글→hex code (2350 전체). 기존 1030 code 보존.
  - data/kor_glyphs_2350.bin            : GBA 4bpp 타일 블롭 (32B 타일, top/bot dedup). KOR_BASE 주입용.
  - data/syllable_to_glyph_2350.json    : 한글→{top,bot} local tile idx (테이블 확장에 필요).
                                          기존 syllable_to_glyph.json 과 동일 포맷 + _meta.

글리프: render_galmuri_8x16.render_char(ch) (Galmuri11-Condensed, 11px, ink 인덱스 9),
top 8x8 + bot 8x8 두 타일. build_korean_glyph_blob.py 와 동일한 dedup 규칙.

재현:  python3 tools/build_korean2350.py
검증:  python3 tools/build_korean2350.py --verify
"""
import argparse
import csv
import hashlib
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_galmuri_8x16 import render_char  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
TRANS = os.path.join(ROOT, 'data', 'translation_for_import.csv')
FOUND = os.path.join(ROOT, 'data', 'game_wars_found_texts.csv')

# 입력 (현행 출하본 — 보존 대상)
CUR_CODE = os.path.join(ROOT, 'data', 'syllable_to_code.json')
CUR_GLYPH = os.path.join(ROOT, 'data', 'syllable_to_glyph.json')
CUR_BLOB = os.path.join(ROOT, 'data', 'korean_glyph_blob.bin')

# 출력
OUT_CODE = os.path.join(ROOT, 'data', 'syllable_to_code_2350.json')
OUT_GLYPH = os.path.join(ROOT, 'data', 'syllable_to_glyph_2350.json')
OUT_BLOB = os.path.join(ROOT, 'data', 'kor_glyphs_2350.bin')

# 한자 테이블 (예약코드 풀 계산용) — build_korean_poc.py 와 동일 파라미터
KTAB_FILE = 0xB80B7C
KTAB_END_FILE = 0xB8180C
TILE_BYTES = 0x20
INK_INDEX = 9


# ---------------------------------------------------------------------------
# KS X 1001 완성형 2350 한글 집합
# ---------------------------------------------------------------------------
def ks_x_1001_2350():
    """KS X 1001 완성형 2350 한글을 EUC-KR(lead 0xB0~0xC8) 영역에서 생성.

    이 영역의 디코딩 가능한 음절 = 표준 완성형 2350 (전부 distinct, sorted = unicode sorted).
    """
    out = []
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            try:
                ch = bytes([lead, trail]).decode('euc-kr')
            except Exception:
                continue
            if '가' <= ch <= '힣':
                out.append(ch)
    out = sorted(set(out))
    assert len(out) == 2350, f'expected 2350 KS X 1001 hangul, got {len(out)}'
    return out


# ---------------------------------------------------------------------------
# 예약 코드 풀 (build_korean_poc.extend_pool 과 byte-identical 결과)
# ---------------------------------------------------------------------------
def valid_sjis(code):
    lead, trail = code >> 8, code & 0xFF
    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
        return False
    return 0x40 <= trail <= 0x7E or 0x80 <= trail <= 0xFC


def used_codes_in_text():
    used = set()
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            ja = r.get('japanese') or r.get('text') or ''
            try:
                b = ja.encode('shift_jis', errors='ignore')
            except Exception:
                continue
            i = 0
            while i < len(b) - 1:
                lead = b[i]
                if 0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC:
                    used.add((lead << 8) | b[i + 1])
                    i += 2
                else:
                    i += 1
    return used


def kanji_table_codes(rom):
    codes = set()
    for a in range(KTAB_FILE, KTAB_END_FILE, 6):
        sjis_le = struct.unpack('<H', rom[a:a + 2])[0]
        codes.add(((sjis_le & 0xFF) << 8) | (sjis_le >> 8))
    return codes


def extend_pool(rom):
    used = used_codes_in_text()
    table = kanji_table_codes(rom)
    pool = []
    for lead in range(0x88, 0xEB):
        for trail in range(0x40, 0xFD):
            code = (lead << 8) | trail
            if not valid_sjis(code):
                continue
            if code in used or code in table:
                continue
            pool.append(code)
    return pool


# ---------------------------------------------------------------------------
# 블롭 + 매핑 생성
# ---------------------------------------------------------------------------
def build_blob_and_glyphmap(syllables, seed_syllables):
    """syllables 전체에 대해 top/bot 8x8 타일 dedup 블롭 + {top,bot} local idx 맵 생성.

    seed_syllables(기존 1030, 정렬됨)를 먼저 같은 순서로 처리해 기존 local idx(0..799)를
    보존하고, 그 다음 신규 음절을 처리한다. 이렇게 하면 기존 블롭은 prefix-identical 이다.
    """
    tile_index = {}   # tile_bytes -> local idx
    blob = bytearray()

    def add_tile(tb):
        if tb not in tile_index:
            tile_index[tb] = len(tile_index)
            blob.extend(tb)
        return tile_index[tb]

    syl_map = {}
    empty = 0
    # 1) seed(기존) 음절을 동일 순서로 먼저 → local idx 보존
    seen = set()
    order = list(seed_syllables) + [s for s in syllables if s not in set(seed_syllables)]
    for ch in order:
        if ch in seen:
            continue
        seen.add(ch)
        top, bot = render_char(ch)
        if not any(top) and not any(bot):
            empty += 1
        ti = add_tile(bytes(top))
        bi = add_tile(bytes(bot))
        syl_map[ch] = {"top": ti, "bot": bi}
    return blob, syl_map, empty


def translation_used_syllables():
    used = set()
    with open(TRANS, newline='') as f:
        for row in csv.DictReader(f):
            for ch in (row.get('korean') or ''):
                if '가' <= ch <= '힣':
                    used.add(ch)
    return used


def build():
    if not os.path.exists(ROM):
        raise SystemExit(f'원본 ROM 없음: {ROM}')
    rom = open(ROM, 'rb').read()

    ks2350 = ks_x_1001_2350()

    # 기존 매핑 (보존 대상)
    cur_code = {s: int(c, 16) for s, c in json.load(open(CUR_CODE, encoding='utf-8')).items()}
    cur_glyph = json.load(open(CUR_GLYPH, encoding='utf-8'))['map']
    seed_syllables = sorted(cur_code.keys())

    # --- 호환성 점검 1: 기존 매핑이 전부 KS2350 부분집합인가 ---
    ks_set = set(ks2350)
    extra = sorted(s for s in cur_code if s not in ks_set)
    # extra 음절(KS2350 밖)이 있어도 보존해야 하므로 최종 집합에 합집합으로 포함한다.
    all_syllables = sorted(ks_set | set(cur_code.keys()))

    # --- 코드 할당 (additive) ---
    pool = extend_pool(rom)
    pool_set = set(pool)
    # 기존 code 보존
    code_map = dict(cur_code)
    used_codes = set(cur_code.values())
    # 기존 code 가 풀 안에 있는지(정합성)
    not_in_pool = [s for s, c in cur_code.items() if c not in pool_set]
    free = [c for c in pool if c not in used_codes]
    new_syllables = sorted(s for s in all_syllables if s not in code_map)
    if len(new_syllables) > len(free):
        raise SystemExit(f'free pool {len(free)} < new syllables {len(new_syllables)}')
    for i, s in enumerate(new_syllables):
        code_map[s] = free[i]

    # --- 글리프 블롭 + top/bot 맵 (additive: 기존 local idx 보존) ---
    blob, glyph_map, empty = build_blob_and_glyphmap(all_syllables, seed_syllables)

    # --- 호환성 점검 2: 기존 glyph local idx 보존 여부 ---
    glyph_preserved = all(glyph_map[s] == cur_glyph[s] for s in cur_glyph)

    # --- 호환성 점검 3: 기존 블롭 prefix-identical ---
    cur_blob = open(CUR_BLOB, 'rb').read()
    blob_prefix_ok = bytes(blob)[:len(cur_blob)] == cur_blob

    # --- 호환성 점검 4: 기존 code 보존 (byte-identical) ---
    code_preserved = all(code_map[s] == cur_code[s] for s in cur_code)

    # --- 커버리지: 번역에 실제 쓰이는 음절 중 (기존 기준) 미매핑 수 ---
    used_in_trans = translation_used_syllables()
    unmapped_old = sorted(s for s in used_in_trans if s not in cur_code)
    unmapped_new = sorted(s for s in used_in_trans if s not in code_map)
    # KS2350 중 신규로 커버된 수
    newly_covered = sorted(s for s in ks2350 if s not in cur_code)

    meta = {
        "standard": "KS X 1001 완성형 2350",
        "total_syllables": len(all_syllables),
        "ks2350": len(ks2350),
        "seed_syllables": len(seed_syllables),
        "new_syllables": len(new_syllables),
        "extra_outside_ks2350_preserved": len(extra),
        "unique_tiles": len(blob) // TILE_BYTES,
        "blob_bytes": len(blob),
        "tile_bytes": TILE_BYTES,
        "ink_index": INK_INDEX,
        "naive_tiles": 2 * len(all_syllables),
        "empty_render": empty,
        "blob_sha1": hashlib.sha1(bytes(blob)).hexdigest(),
        "pool_size": len(pool),
        "codes_used_total": len(set(code_map.values())),
        "free_codes_after": len(pool) - len(set(code_map.values())),
        # 호환성
        "compat_code_preserved": code_preserved,
        "compat_glyph_idx_preserved": glyph_preserved,
        "compat_blob_prefix_identical": blob_prefix_ok,
        "existing_codes_not_in_pool": not_in_pool,
        # 커버리지
        "translation_distinct_syllables": len(used_in_trans),
        "translation_unmapped_before(1030)": len(unmapped_old),
        "translation_unmapped_after(2350)": len(unmapped_new),
        "newly_covered_count": len(newly_covered),
        "note": "local tile idx 0-based; KOR_BASE idx = local_idx | 0x8000 (bit15 Korean marker). "
                "build_korean_full 의 hook 이 0x8000 마커를 KOR_BASE(0x08F00000)+idx*0x20 로 해석.",
    }

    # --- 출력 ---
    with open(OUT_BLOB, 'wb') as f:
        f.write(blob)
    with open(OUT_GLYPH, 'w', encoding='utf-8') as f:
        json.dump({"_meta": meta, "map": glyph_map}, f, ensure_ascii=False, indent=0)
    with open(OUT_CODE, 'w', encoding='utf-8') as f:
        json.dump({s: f'0x{c:04X}' for s, c in sorted(code_map.items())},
                  f, ensure_ascii=False, indent=0)

    return meta, code_map, glyph_map, blob


def verify():
    """산출물 재로딩 + 무결성/호환성 재검증."""
    rom = open(ROM, 'rb').read()
    code = {s: int(c, 16) for s, c in json.load(open(OUT_CODE, encoding='utf-8')).items()}
    glyph = json.load(open(OUT_GLYPH, encoding='utf-8'))['map']
    blob = open(OUT_BLOB, 'rb').read()
    cur_code = {s: int(c, 16) for s, c in json.load(open(CUR_CODE, encoding='utf-8')).items()}
    cur_glyph = json.load(open(CUR_GLYPH, encoding='utf-8'))['map']
    cur_blob = open(CUR_BLOB, 'rb').read()

    problems = []
    # 1) 2350 KS 전부 포함
    ks2350 = ks_x_1001_2350()
    miss = [s for s in ks2350 if s not in code]
    if miss:
        problems.append(f'{len(miss)} KS2350 syllables missing from code map: {miss[:10]}')
    # 2) code/ glyph 1:1 일치
    if set(code.keys()) != set(glyph.keys()):
        problems.append('code keys != glyph keys')
    # 3) code 충돌 없음
    if len(set(code.values())) != len(code):
        problems.append('duplicate codes assigned')
    # 4) 모든 code 가 valid SJIS & 풀 안
    pool = set(extend_pool(rom))
    bad = [s for s, c in code.items() if c not in pool]
    if bad:
        problems.append(f'{len(bad)} codes outside reserved pool: {bad[:10]}')
    # 5) 기존 code 보존
    if not all(code[s] == cur_code[s] for s in cur_code):
        problems.append('existing 1030 codes NOT preserved')
    # 6) 기존 glyph idx 보존
    if not all(glyph[s] == cur_glyph[s] for s in cur_glyph):
        problems.append('existing glyph local idx NOT preserved')
    # 7) 블롭 prefix-identical
    if blob[:len(cur_blob)] != cur_blob:
        problems.append('blob prefix NOT identical to existing korean_glyph_blob.bin')
    # 8) 블롭 길이 = unique tiles * 32
    maxidx = max(max(v['top'], v['bot']) for v in glyph.values())
    if len(blob) < (maxidx + 1) * TILE_BYTES:
        problems.append(f'blob too short for max tile idx {maxidx}')
    if len(blob) % TILE_BYTES != 0:
        problems.append('blob length not multiple of tile size')
    # 9) 인덱스가 bit15 와 충돌하지 않음 (idx | 0x8000 안전)
    if maxidx >= 0x8000:
        problems.append(f'tile idx {maxidx} >= 0x8000 collides with Korean marker bit')

    return problems, {
        'code': len(code), 'glyph': len(glyph), 'tiles': len(blob) // TILE_BYTES,
        'blob_bytes': len(blob), 'max_tile_idx': maxidx,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true', help='산출물만 재검증')
    args = ap.parse_args()

    if args.verify:
        problems, stats = verify()
        print(json.dumps({'verify_stats': stats, 'problems': problems}, ensure_ascii=False, indent=2))
        raise SystemExit(1 if problems else 0)

    meta, code_map, glyph_map, blob = build()
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f'\nwrote:\n  {OUT_CODE}\n  {OUT_GLYPH}\n  {OUT_BLOB} ({len(blob)} bytes)')

    # 자체 검증
    problems, stats = verify()
    print('\n=== verify ===')
    print(json.dumps({'verify_stats': stats, 'problems': problems}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit('VERIFY FAILED')
    print('OK')


if __name__ == '__main__':
    main()
