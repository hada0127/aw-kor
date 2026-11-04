#!/usr/bin/env python3
"""1편 이름 조합(Phase C, PLAN B T2a)의 생성 include 세 개를 만든다.

Part 2 SOURCE 파일(tools/name_compose/*, tools/hangul_compose.py)은 import 만 한다 — 1바이트도 고치지 않는다
(PLAN B D0: 고치면 tools/part2_name_compose_blob.py 가 stale 로 빌드 실패).

정본(이 파일 밖에 같은 값을 다시 적지 않는다):
  - 사설 그리드 레이아웃·선택표: tools/name_compose/gen_tables.py (PRIVATE_GRID·selection_grid)
  - 자모 코드: data/jamo_to_code_40.json (gen_jamo_assets.load_jamo_codes)
  - 1편 host/placeholder 코드·런타임 주소: 아래 HOST_CODES·PLACEHOLDERS·CONFIG 한 곳 (T0 값)

생성물(추적하지 않는다 — build_image_p1.py 가 작업 폴더에 만든다):
  - tables.h    : Part 2 tables_h() 출력에서 `#define NC_MAX_SLOTS 8u` 한 줄만
                  `#define NC_MAX_SLOTS ((unsigned)obj[0x62])` 로 바꾼 것(core.c 는 commit(obj,…) 안에서만 씀)
  - grid_p1.inc : nc_sel_priv(6x15 u16 BE, Part 2 와 같은 바이트) · nc_row_priv_0..5(1편 행 형식
                  `0A 09`+쌍+`0A 00 00 00`, 자모 자리는 host 코드) · nc1_host_tab · nc1_placeholders
  - p1_config.h : CONFIG → #define

nc1_host_tab 형식(엔트리 4B, 33개, .balign 4): [u8 자모 index(PREVIEW_JAMO 순, 타일 = jamo_first_tile+2*index)]
  [u8 0] [u16 host 코드, little-endian .hword]. nc1_placeholders: 8 × u16 little-endian .hword.

사용:  python3 tools/name_compose_p1/gen_tables_p1.py --out DIR
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOLS, 'name_compose'))
sys.path.insert(0, TOOLS)

import hangul_compose as hc  # noqa: E402
import gen_tables  # noqa: E402  (Part 2 — import 만)
from gen_jamo_assets import load_jamo_codes, load_syllable_codes  # noqa: E402

SPACE_CODE = hc.SPACE_CODE
GRID_W, GRID_H = gen_tables.GRID_W, gen_tables.GRID_H
SELECTABLE = hc.SELECTABLE_JAMO                     # 33 = 초성 19 + 선택 모음 14 (host 순서)

# ---------------------------------------------------------------------------------------------
# T0 정본 자리 (PLAN B §3.4·NR-1/NR-8). 값은 T0(temp/fix_20261104/p1compose/t0/p1_config.json,
# T0_RE.md — ROM re/base.gba sha256 32aaae30…4428 런타임 실측)에서 왔다. 바꾸면 이 블록만 고치고
# test_part1_name_compose_core.T0Values 가 JSON 과 다시 대조한다.
T0_PENDING = False

# 이름 화면 사전 4묶음(원본 = 현재 빌드, P1_NAME_RE §6 · T0 NR-1). 파일 오프셋, u16 BE 코드 목록, 첫 바이트 0 종단.
# 생성자(0x08B488D8–F2)가 bank 1 에 이 순서로 이어 적재한다(113코드, tile_start 0, 코드 i → 타일 2i/2i+1).
DICT_LISTS = (0xBE7178, 0xBE71CC, 0xBE720C, 0xBE7244)
DICT_COUNTS = (40, 31, 26, 16)

# placeholder 8 = 숨은 한자(0x08BE7244) 앞 8개 — NAME 박스 칸 i 의 한글 글리프를 이 코드의 사전 타일에 덮어 그린다.
PLACEHOLDERS = (0x8E52, 0x90AC, 0x93FA, 0x89BA, 0x967B, 0x91E5, 0x8BE0, 0x88EA)
# host 33, SELECTABLE_JAMO 순서(T0 NR-8): 탁음 가나(0x08BE720C) 중 ヴ(8394) 뺀 25 → ㄱ…ㅔ,
# 숨은 한자 뒤 8 → ㅕㅖㅗㅛㅜㅠㅡㅣ. 그리드 자모 라벨을 이 코드의 사전 타일에 덮어 그린다.
HOST_CODES = (
    0x834B, 0x834D, 0x834F, 0x8351, 0x8353, 0x8355, 0x8357, 0x8359, 0x835B, 0x835D,   # ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅ
    0x835F, 0x8361, 0x8364, 0x8366, 0x8368, 0x836F, 0x8372, 0x8375, 0x8378,           # ㅆㅇㅈㅉㅊㅋㅌㅍㅎ
    0x837B, 0x8370, 0x8373, 0x8376, 0x8379, 0x837C,                                   # ㅏㅐㅑㅒㅓㅔ
    0x95BD, 0x8D4C, 0x8CB3, 0x8E71, 0x8FF0, 0x9286, 0x8DA1, 0x97CD,                   # ㅕㅖㅗㅛㅜㅠㅡㅣ
)
HOST_OF = dict(zip(SELECTABLE, HOST_CODES))

# §3.4 키 (T0 NR-1/2/4/9 확정값). cache_count_off 는 T2b 의 사전 목록 탐색 상한(코드 수 u16)이라 추가했다.
CONFIG = {
    'obj_ptr': 0x03004690,
    'cache_base': 0x02010AD4,
    'cache_bank': 1,
    'cache_count_off': 0x2,        # = bank*2 (u16 코드 수)
    'cache_list_off': 0x204,       # = 6 + bank*510 (코드 i = 2바이트 SJIS 순서 hi,lo)
    'cache_tile_off': 0x60E,       # = 0x60C + bank*2 (u16 tile_start)
    'cache_code_order': 'be',
    'vram_charblock': 0x06000000,  # BG0CNT 0x4E00 → charbase 0, 타일 t = 0x06000000 + t*32
    'kor_base': 0x08F00000,
    'tbl_start': 0x08F20000,       # 리터럴 파일 0xEFE970 (= P.NEW_TBL_RT)
    'tbl_end': 0x08F24494,         # 리터럴 파일 0xEFE974 = tbl_start + 2926*6
    'jamo_first_tile': 1275,       # gen_jamo_assets.FIRST_TILE
    'pal_remap': None,             # NR-2: 사전 로더는 raw 복사(리맵 없음)
    'tilemap_lit': 0x08BE7280,     # 값 0x02012D44 (NR-4)
}
CONFIG_KEYS = tuple(CONFIG)
OPTIONAL_NONE = ('pal_remap',)      # None 이 유효값인 키

# 1편 native 행 y2 의 x10/x11 표시는 8168/814B(원본 0x08DF8C88). Part 2 의 814A 는 1편 사전 목록에 없어
# 빈칸으로 그려지므로 1편 native 표시 코드를 그대로 쓴다(PLAN B D7 「사전에 있을 때」 조건의 확인 결과).
DISPLAY_OVERRIDE_P1 = {(10, 2): 0x8168, (11, 2): 0x814B}
NATIVE_ROW_ADDRS = (0x08DF8C38, 0x08DF8C60, 0x08DF8C88, 0x08DF8CB0, 0x08DF8CCC, 0x08DF8CE8)
ROW_PREFIX, ROW_SUFFIX = b'\x0A\x09', b'\x0A\x00\x00\x00'
MAX_SLOTS_LINE = f'#define NC_MAX_SLOTS {hc.MAX_SLOTS}u\n'
MAX_SLOTS_P1_LINE = '#define NC_MAX_SLOTS ((unsigned)obj[0x62])\n'


def check_codes(codes, host_codes=HOST_CODES, placeholders=PLACEHOLDERS, syllables=None):
    """host·placeholder 제약(PLAN B T2a). 위반이면 ValueError."""
    if len(host_codes) != len(SELECTABLE) or len(placeholders) != 8:
        raise ValueError(f'need {len(SELECTABLE)} hosts and 8 placeholders')
    allc = list(host_codes) + list(placeholders)
    if len(set(allc)) != len(allc):
        raise ValueError('host/placeholder codes must be pairwise distinct')
    literals = {c for row in gen_tables.selection_grid(codes) for c in row
                if c not in codes.values()} | {SPACE_CODE}
    jamo = set(codes.values())
    syl = set((syllables or load_syllable_codes()).values())
    for c in allc:
        if not 0x8100 <= c <= 0xFFFF:
            raise ValueError(f'0x{c:04X} not a 2-byte code')
        if (c >> 8) in gen_tables.ACTION_LEADS:
            raise ValueError(f'0x{c:04X} lead byte is an action code')
        if c in literals:
            raise ValueError(f'0x{c:04X} collides with a private grid literal')
        if c in jamo:
            raise ValueError(f'0x{c:04X} collides with a jamo code')
        if c in syl:
            raise ValueError(f'0x{c:04X} collides with a 2350 syllable code')


def tables_h_p1(codes):
    src = gen_tables.tables_h(codes).decode('utf-8')
    if src.count(MAX_SLOTS_LINE) != 1:
        raise ValueError('expected exactly one NC_MAX_SLOTS line in Part 2 tables.h')
    out = src.replace(MAX_SLOTS_LINE, MAX_SLOTS_P1_LINE)
    if out.count('\n') != src.count('\n') or 'NC_MAX_SLOTS 8u' in out:
        raise ValueError('NC_MAX_SLOTS substitution changed line structure')
    return out.encode('utf-8')


def display_rows_p1(grid, codes, host_of=None):
    """1편 형식 표시행 6개: `0A 09` + 쌍(17/17/17/11/11/11) + `0A 00 00 00`. 자모 자리는 host 코드."""
    host_of = HOST_OF if host_of is None else host_of
    host_by_code = {codes[j]: h for j, h in host_of.items()}
    rows = []
    for y, sel in enumerate(grid):
        n = gen_tables.ROW_PAIR_COUNT[y]
        pairs = [SPACE_CODE] * n
        mapping = gen_tables.WIDE_ROW_PAIRS if n == 17 else gen_tables.NARROW_ROW_PAIRS
        for x, pair in enumerate(mapping):
            c = DISPLAY_OVERRIDE_P1.get((x, y), sel[x])
            pairs[pair] = host_by_code.get(c, c)
        rows.append(ROW_PREFIX + b''.join(p.to_bytes(2, 'big') for p in pairs) + ROW_SUFFIX)
    return rows


def row_lengths_p1():
    return tuple(len(ROW_PREFIX) + 2 * n + len(ROW_SUFFIX) for n in gen_tables.ROW_PAIR_COUNT)


def host_tab_bytes(host_of=None):
    host_of = HOST_OF if host_of is None else host_of
    out = bytearray()
    for j in SELECTABLE:
        out += bytes([hc.PREVIEW_JAMO.index(j), 0]) + host_of[j].to_bytes(2, 'little')
    return bytes(out)


def placeholders_bytes(placeholders=PLACEHOLDERS):
    return b''.join(p.to_bytes(2, 'little') for p in placeholders)


def _byte_lines(data, per=16):
    return ''.join('\t.byte ' + ', '.join(f'0x{b:02X}' for b in data[i:i + per]) + '\n'
                   for i in range(0, len(data), per))


def grid_inc_p1(codes):
    check_codes(codes)
    grid = gen_tables.selection_grid(codes)
    rows = display_rows_p1(grid, codes)
    lines = ['@ 생성 파일 — tools/name_compose_p1/gen_tables_p1.py. 손으로 고치지 않는다.\n',
             '\t.global\tnc_sel_priv\n\t.global\tnc_row_priv\n',
             '\t.global\tnc1_host_tab\n\t.global\tnc1_placeholders\n',
             '\t.balign 4\nnc_sel_priv:\t@ 6x15 u16 BE (Part 2 사설 선택표와 같은 바이트)\n']
    for y, row in enumerate(grid):
        data = ', '.join(f'0x{c >> 8:02X}, 0x{c & 0xFF:02X}' for c in row)
        lines.append(f'\t.byte {data}\t@ row {y}\n')
    lines.append('\t.balign 4\nnc_row_priv:\t@ 6 rows, 1편 형식 0A 09 + pairs + 0A 00 00 00, 연속 배치\n')
    for y, row in enumerate(rows):
        lines.append(f'nc_row_priv_{y}:\t@ row {y} ({len(row)}B)\n')
        lines.append(_byte_lines(row))
    lines.append('\t.balign 4\nnc1_host_tab:\t@ 33 x {u8 jamo index, u8 0, u16 host LE}\n')
    lines.append(_byte_lines(host_tab_bytes(), 16))
    lines.append('\t.balign 4\nnc1_placeholders:\t@ 8 x u16 LE\n')
    lines.append(_byte_lines(placeholders_bytes()))
    lines.append('\t.balign 4\n')
    return ''.join(lines).encode('utf-8')


def config_h(cfg=None):
    cfg = CONFIG if cfg is None else cfg
    if tuple(cfg) != CONFIG_KEYS:
        raise ValueError(f'config keys {tuple(cfg)} != {CONFIG_KEYS}')
    missing = [k for k, v in cfg.items() if v is None and k not in OPTIONAL_NONE]
    if missing:
        raise ValueError(f'config values pending (T0): {missing}')
    if cfg['cache_code_order'] not in ('be', 'le'):
        raise ValueError('cache_code_order must be be|le')
    out = ['/* 생성 파일 — tools/name_compose_p1/gen_tables_p1.py. 손으로 고치지 않는다. */\n',
           '#ifndef NC1_CONFIG_H\n#define NC1_CONFIG_H\n']
    for k, v in cfg.items():
        name = 'NC1_' + k.upper()
        if k == 'cache_code_order':
            out.append(f'#define NC1_CACHE_CODE_BE {1 if v == "be" else 0}u\n')
        elif k == 'pal_remap':
            if v is None:
                out.append('#define NC1_PAL_REMAP 0u\n')
            else:
                if len(v) != 16 or any(not 0 <= n <= 15 for n in v):
                    raise ValueError('pal_remap must be 16 nibbles')
                out.append('#define NC1_PAL_REMAP 1u\n')
                out.append('#define NC1_PAL_REMAP_TABLE { ' + ', '.join(str(n) for n in v) + ' }\n')
        else:
            out.append(f'#define {name} 0x{v:08X}u\n')
    out.append(f'#define NC1_HOST_COUNT {len(SELECTABLE)}u\n#define NC1_PLACEHOLDER_COUNT {len(PLACEHOLDERS)}u\n')
    out.append('#endif\n')
    return ''.join(out).encode('utf-8')


def generate(codes=None, cfg=None):
    """{'tables.h','grid_p1.inc','p1_config.h'} → bytes. cfg 미확정(T0) 이면 ValueError."""
    if codes is None:
        codes = load_jamo_codes()
    return {'tables.h': tables_h_p1(codes), 'grid_p1.inc': grid_inc_p1(codes), 'p1_config.h': config_h(cfg)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, help='생성 include 를 쓸 폴더')
    args = ap.parse_args()
    if T0_PENDING:
        print('WARNING: T0_PENDING — host/placeholder values are PROVISIONAL', file=sys.stderr)
    os.makedirs(args.out, exist_ok=True)
    for name, data in generate().items():
        with open(os.path.join(args.out, name), 'wb') as f:
            f.write(data)
        print(f'wrote {name} ({len(data)}B)')


if __name__ == '__main__':
    main()
