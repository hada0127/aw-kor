#!/usr/bin/env python3
"""QA(committed 게이트): 출하 ROM의 대사 재배치(repoint)를 **ROM 직접** 검증.

temp manifest를 신뢰하지 않는다. 출하 ROM에서 in-place 베이스라인을 복원(포인터 테이블→원본,
여유공간→원본 0xFF)한 뒤 repoint 엔진을 재실행해, 결과가 출하 ROM과 **byte-identical**인지 본다.
→ 포인터 갱신·free-space 메시지 바이트·쪼롱이님 라인 복원이 모두 결정적으로 검증된다(codex 리뷰 반영).

사용: python3 tools/qa_repoint_integrity.py [output.gba]
종료코드: 불일치/오류면 1.
"""
import csv, json, os, struct, sys, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))
import build_korean_full as B
from text_metrics import visual_cells
from dialogue_repoint import repoint_messages, _line_index

TABLE = 0xA357B4
TABLE_N = 3315
FREE_START, FREE_END = 0xA3D000, 0xB00000


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, 'output', 'game_wars_korean_full.gba')
    orig = open(os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba'), 'rb').read()
    shipped = open(out_path, 'rb').read()
    if len(shipped) != len(orig):
        print('[FAIL] ROM 크기 불일치'); return 1

    # 재배치된 포인터가 하나도 없으면(=repoint off 빌드) 통과(검증 대상 없음).
    relocated_ptrs = sum(1 for o in range(TABLE, TABLE + TABLE_N * 4, 4)
                         if FREE_START <= struct.unpack_from('<I', shipped, o)[0] - 0x08000000 < FREE_END)
    if relocated_ptrs == 0:
        print('[OK] 재배치 포인터 0 — repoint 미적용 빌드(검증 생략)'); return 0

    # 1) 출하 ROM에서 in-place 베이스라인 복원: 포인터테이블→원본, 여유공간→원본(0xFF)
    base = bytearray(shipped)
    base[TABLE:TABLE + TABLE_N * 4] = orig[TABLE:TABLE + TABLE_N * 4]
    base[FREE_START:FREE_END] = orig[FREE_START:FREE_END]

    # 2) repoint 엔진 재실행에 필요한 헬퍼(build와 동형)
    syl = {s: int(c, 16) for s, c in json.load(open(B.SYLCODE, encoding='utf-8')).items()}
    um = collections.Counter()
    code_to_syl = {v: k for k, v in syl.items()}
    dlg = {}
    for k, v in json.load(open(os.path.join(BASE, 'data', 'dialogue_overrides.json'), encoding='utf-8')).items():
        try:
            dlg[int(k, 16)] = (v or '').strip()
        except (ValueError, TypeError):
            pass
    slots = {}
    for r in csv.DictReader(open(os.path.join(BASE, 'data', 'game_wars_found_texts.csv'), encoding='utf-8', errors='ignore')):
        try:
            slots[int((r.get('address') or '').strip(), 16)] = int(r.get('length') or 0)
        except (ValueError, TypeError):
            pass

    def fixable(a):
        return a in dlg and dlg[a] and any('가' <= c <= '힣' for c in dlg[a])

    def fixed_bytes(a):
        return B.encode_full_fidelity(dlg[a], syl, um)

    def fit_level_dlg(a):
        enc, lvl = B.encode_fit(dlg[a], slots.get(a, 0), syl, um)
        return 99 if enc is None else lvl

    def decode_text(raw):
        out = []
        i = 0
        while i < len(raw):
            b = raw[i]
            if b == 0x20:
                out.append(' '); i += 1
            elif b >= 0x81 and i + 1 < len(raw):
                c = (b << 8) | raw[i + 1]
                if c == 0x8140:
                    out.append(' ')
                elif c in code_to_syl:
                    out.append(code_to_syl[c])
                else:
                    try:
                        out.append(bytes([b, raw[i + 1]]).decode('shift_jis'))
                    except Exception:
                        out.append('\x00')
                i += 2
            else:
                out.append(chr(b) if 0x21 <= b <= 0x7E else '\x00'); i += 1
        return ''.join(out)

    man, st = repoint_messages(
        base, orig, fixable=fixable, fixed_bytes=fixed_bytes, fit_level_dlg=fit_level_dlg,
        decode_text=decode_text, cell_width=lambda a: visual_cells(B.normalize_for_fit(dlg.get(a) or '')),
        slots=slots, line_index=_line_index(os.path.join(BASE, 'data', 'game_wars_found_texts.csv')),
        table_offsets=[TABLE], free_start=FREE_START, free_end=FREE_END, min_level=6, max_cells=50)

    # 3) 재구성한 baseline+repoint == 출하 ROM ? (byte-identical)
    if bytes(base) != bytes(shipped):
        # 첫 불일치 지점 보고
        for i in range(len(base)):
            if base[i] != shipped[i]:
                print(f'[FAIL] 첫 불일치 0x{i:06X}: 재구성=0x{base[i]:02X} 출하=0x{shipped[i]:02X}')
                break
        return 1
    relocated = st.get('relocated', 0)
    lines_fixed = st.get('lines_fixed', 0)
    # 출하 ROM의 재배치 포인터 수 == 시뮬 relocated 수
    if relocated != relocated_ptrs:
        print(f'[FAIL] 재배치 포인터 수 불일치: 시뮬 {relocated} != 출하 {relocated_ptrs}')
        return 1
    print(f'[OK] 출하 ROM repoint 무결성 PASS — in-place 베이스 복원→재배치 재현이 출하본과 byte-identical. '
          f'relocated {relocated} msgs / {lines_fixed} lines, free {st.get("free_used")}B.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
