#!/usr/bin/env python3
"""2편 이름 조합 코어의 생성 include 두 개를 만든다(PLAN-v5 §1.2·§1.6, T2).

정본(이 파일 밖에 같은 값을 다시 적지 않는다):
  - 자모 코드: data/jamo_to_code_40.json (gen_jamo_assets.load_jamo_codes 로 검증해 읽음)
  - 조합 규칙 상수: tools/hangul_compose.py (L/V/T 목록·복합모음·겹받침·종성→초성)
  - 사설 그리드 레이아웃: 아래 PRIVATE_GRID 한 곳

생성물(추적하지 않는다 — build_image.py 가 작업 폴더에 만든다):
  - tables.h : C 코어용 표 (NC_L_CODE[19], NC_V_CODE[21], NC_SEL_V[14], 복합모음/겹받침 표 등)
  - grid.inc : tramp.s 가 include 하는 사설 선택표 nc_sel_priv(6x15 u16 BE)와
               사설 표시행 nc_row_priv(native 와 같은 형식 `09`+쌍+`00`, 17/17/17/11/11/11쌍)

사용:  python3 tools/name_compose/gen_tables.py --out DIR
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import hangul_compose as hc  # noqa: E402
from gen_jamo_assets import load_jamo_codes  # noqa: E402

SPACE_CODE = hc.SPACE_CODE          # 0x8140, native 빈 셀/간격과 같은 전각 공백
GRID_W, GRID_H = 15, 6
NONE = 0xFF

# §1.2 사설 선택 레이아웃. 자모는 글자, ' '는 공백 셀(8140), 4자리 hex 는 native 원본 코드 그대로.
# row2 x10/x11 은 legacy 탁점·반탁점(3131/3232), row3~5 x10..14 는 취소/뒤로/확인 wide 버튼(63/62/65).
PRIVATE_GRID = (
    ('ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', '824f', '8250', '8251', '8252', '8253'),
    ('ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ', ' ', '8254', '8255', '8256', '8257', '8258'),
    ('ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅛ', '3131', '3232', '8145', '8149', '8148'),
    ('ㅜ', 'ㅠ', 'ㅡ', 'ㅣ', ' ', ' ', ' ', ' ', ' ', ' ', '6363', '6363', '6363', '6363', '6363'),
    (' ',) * 10 + ('6262',) * 5,
    (' ',) * 10 + ('6565',) * 5,
)
# 표시만 native 와 다르게 지정하는 셀: legacy 탁점·반탁점 셀은 원래 표시 814A/814B 를 유지한다.
DISPLAY_OVERRIDE = {(10, 2): 0x814A, (11, 2): 0x814B}
# native 가 첫 바이트로 분기하는 동작 코드(이 좌표들은 원본 코드 그대로여야 한다 — 분류 동일성).
ACTION_LEADS = (0x31, 0x32, 0x62, 0x63, 0x65)
# 선택 x → 표시 pair index. row0~2 는 17쌍(pair 5·11 간격), row3~5 는 11쌍(x0..9 → 0..4,6..10, pair5 간격).
WIDE_ROW_PAIRS = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16)
NARROW_ROW_PAIRS = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10)
ROW_PAIR_COUNT = (17, 17, 17, 11, 11, 11)


def selection_grid(codes):
    """6x15 사설 선택 코드(int). codes = load_jamo_codes()."""
    grid = []
    for row in PRIVATE_GRID:
        if len(row) != GRID_W:
            raise ValueError('grid row width != 15')
        out = []
        for label in row:
            if label == ' ':
                out.append(SPACE_CODE)
            elif label in codes:
                out.append(codes[label])
            elif len(label) == 4:
                out.append(int(label, 16))
            else:
                raise ValueError(f'unknown grid label {label!r}')
        grid.append(out)
    if len(grid) != GRID_H:
        raise ValueError('grid height != 6')
    return grid


def display_rows(grid):
    """사설 표시행 6개(bytes). 선택표에서 좌표 매핑으로 만든다(공백까지 동기화)."""
    rows = []
    for y, sel in enumerate(grid):
        pairs = [SPACE_CODE] * ROW_PAIR_COUNT[y]
        mapping = WIDE_ROW_PAIRS if ROW_PAIR_COUNT[y] == 17 else NARROW_ROW_PAIRS
        for x, pair in enumerate(mapping):
            pairs[pair] = DISPLAY_OVERRIDE.get((x, y), sel[x])
        rows.append(b'\x09' + b''.join(p.to_bytes(2, 'big') for p in pairs) + b'\x00')
    return rows


def _c_array(ctype, name, values, fmt='0x{:04X}'):
    body = ', '.join(fmt.format(v) for v in values)
    return f'static const {ctype} {name}[{len(values)}] = {{ {body} }};\n'


def tables_h(codes):
    L, V, T = hc.L_LIST, hc.V_LIST, hc.T_LIST
    sel_v = [V.index(j) for j in hc.SELECTABLE_JAMO if j in V]
    cv = list(hc.COMPOUND_VOWELS.items())
    fc = list(hc.FINAL_CLUSTERS.items())
    t_of_l = [T.index(c) if c in T else 0 for c in L]
    l_of_t = [hc.FINAL_TO_INITIAL.get(t, NONE) for t in T]
    byte = '{}'
    out = ['/* 생성 파일 — tools/name_compose/gen_tables.py. 손으로 고치지 않는다. */\n',
           '#ifndef NC_TABLES_H\n#define NC_TABLES_H\n',
           f'#define NC_SPACE_CODE 0x{SPACE_CODE:04X}u\n',
           f'#define NC_MAX_SLOTS {hc.MAX_SLOTS}u\n',
           f'#define NC_NONE 0x{NONE:02X}u\n',
           f'#define NC_L_COUNT {len(L)}u\n#define NC_V_COUNT {len(V)}u\n#define NC_T_COUNT {len(T)}u\n',
           f'#define NC_SEL_V_COUNT {len(sel_v)}u\n#define NC_CV_COUNT {len(cv)}u\n#define NC_FC_COUNT {len(fc)}u\n',
           '/* 미완성 active 표시용 자모 코드(초성 19, 모음 21: 복합 7 포함). */\n',
           _c_array('uint16_t', 'NC_L_CODE', [codes[c] for c in L]),
           _c_array('uint16_t', 'NC_V_CODE', [codes[c] for c in V]),
           '/* 선택 가능한 모음 14개 → V 인덱스(선택 셀 분류: 코드 = NC_V_CODE[NC_SEL_V[i]]). */\n',
           _c_array('uint8_t', 'NC_SEL_V', sel_v, byte),
           '/* 복합 모음: (첫 V, 둘째 V) → 결과 V. 역삭제는 결과 → 첫 V. */\n',
           _c_array('uint8_t', 'NC_CV_FIRST', [V.index(a) for (a, _), _ in cv], byte),
           _c_array('uint8_t', 'NC_CV_SECOND', [V.index(b) for (_, b), _ in cv], byte),
           _c_array('uint8_t', 'NC_CV_RESULT', [V.index(r) for _, r in cv], byte),
           '/* 겹받침: (첫 T, 더하는 자음의 L) → 결과 T. 역삭제·이동은 결과 → (첫 T, 이동 L). */\n',
           _c_array('uint8_t', 'NC_FC_FIRST', [T.index(a) for (a, _), _ in fc], byte),
           _c_array('uint8_t', 'NC_FC_SECOND_L', [L.index(b) for (_, b), _ in fc], byte),
           _c_array('uint8_t', 'NC_FC_RESULT', [T.index(r) for _, r in fc], byte),
           '/* 자음 L → 같은 홑받침 T(없으면 0: ㄸㅃㅉ). 홑받침 T → 이동할 초성 L(겹·없음은 NC_NONE). */\n',
           _c_array('uint8_t', 'NC_T_OF_L', t_of_l, byte),
           _c_array('uint8_t', 'NC_L_OF_T', l_of_t, byte),
           '#endif\n']
    return ''.join(out).encode('utf-8')


def grid_inc(codes):
    grid = selection_grid(codes)
    rows = display_rows(grid)
    lines = ['@ 생성 파일 — tools/name_compose/gen_tables.py. 손으로 고치지 않는다.\n',
             '\t.balign 4\nnc_sel_priv:\t@ 6x15 u16 BE (native 선택표와 같은 바이트 순서)\n']
    for y, row in enumerate(grid):
        data = ', '.join(f'0x{c >> 8:02X}, 0x{c & 0xFF:02X}' for c in row)
        lines.append(f'\t.byte {data}\t@ row {y}\n')
    lines.append('\t.balign 4\nnc_row_priv:\t@ 6 rows, native 형식 09 + pairs + 00, 연속 배치\n')
    for y, row in enumerate(rows):
        lines.append(f'nc_row_priv_{y}:\n')
        lines.append(f'\t.byte {", ".join(f"0x{b:02X}" for b in row)}\t@ row {y} ({len(row)}B)\n')
    lines.append('\t.balign 4\n')
    return ''.join(lines).encode('utf-8')


def row_lengths():
    return tuple(2 + 2 * n for n in ROW_PAIR_COUNT)


def generate(codes=None):
    """{'tables.h': bytes, 'grid.inc': bytes}"""
    if codes is None:
        codes = load_jamo_codes()
    return {'tables.h': tables_h(codes), 'grid.inc': grid_inc(codes)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, help='생성 include 를 쓸 폴더')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name, data in generate().items():
        with open(os.path.join(args.out, name), 'wb') as f:
            f.write(data)
        print(f'wrote {name} ({len(data)}B)')


if __name__ == '__main__':
    main()
