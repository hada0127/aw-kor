#!/usr/bin/env python3
"""배포 무결성 게이트 (Phase A0).

검증: manifest.patched_rom.sha256 == sha256(output/game_wars_korean_full.gba)
      == sha256(원본 ROM에 dist BPS 적용) == sha256(원본 ROM에 dist IPS 적용)
추가: full/final/title_test 3종 산출물이 바이트 동일한지.

배포 전(Phase F) 이 게이트가 PASS여야 한다. 현재는 출하 ROM과 dist가 어긋나면 FAIL로
staleness를 명시한다. exit 0=PASS, 1=FAIL.
"""
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))
from make_bps import apply_bps          # noqa: E402
from make_ips import apply_ips          # noqa: E402
from lz77_scan import lz77_decompress   # noqa: E402
from PIL import Image                   # noqa: E402

ORIGINAL = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
OUTPUTS = {
    'full': os.path.join(BASE, 'output', 'game_wars_korean_full.gba'),
    'final': os.path.join(BASE, 'output', 'game_wars_korean_final.gba'),
    'title_test': os.path.join(BASE, 'output', 'game_wars_korean_title_test.gba'),
}
MANIFESTS = [
    os.path.join(BASE, 'dist', 'manifest.json'),
    os.path.join(BASE, 'dist', 'manifest_preview.json'),
]
PART2_RESULT_SUMMARY_OFF = 0x0059DA5C
PART2_RESULT_SUMMARY_DIRTY_BOXES = [
    (0, 0, 56, 48),
    (64, 0, 128, 48),
    (136, 0, 200, 48),
    (208, 0, 256, 48),
    (48, 56, 236, 72),
    (0, 72, 236, 102),
    (0, 100, 196, 124),
    (0, 240, 256, 256),
]
COMPACT_DISPLAY_VISUAL_MATRIX = os.path.join(BASE, 'data', 'compact_display_visual_matrix.json')
COMPACT_DISPLAY_MANUAL_VISUAL_EVIDENCE = os.path.join(BASE, 'data', 'compact_display_manual_visual_evidence.json')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def parse_addr(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def part2_result_summary_dirty_tile(tile_id):
    """Tiles touched by the Korean result-summary label redraw."""
    x = (tile_id % 32) * 8
    y = (tile_id // 32) * 8
    for x0, y0, x1, y1 in PART2_RESULT_SUMMARY_DIRTY_BOXES:
        # PIL rectangle endpoints are inclusive; count boundary tiles as dirty.
        if x <= x1 and x + 7 >= x0 and y <= y1 and y + 7 >= y0:
            return True
    return False


def nonblack_pixel_count(path):
    img = Image.open(path).convert('RGB')
    return sum(1 for px in img.getdata() if px != (0, 0, 0))


def verify_part2_result_summary_preservation(original, current):
    """Catch sparse/blank-output regressions that erase score/rank tiles."""
    orig_dec = lz77_decompress(original, PART2_RESULT_SUMMARY_OFF)
    cur_dec = lz77_decompress(current, PART2_RESULT_SUMMARY_OFF)
    if orig_dec is None or cur_dec is None:
        return False, 'LZ77 decode failed'
    orig_data, orig_consumed = orig_dec
    cur_data, cur_consumed = cur_dec
    if len(orig_data) != 1024 * 32 or len(cur_data) != 1024 * 32:
        return False, f'unexpected size orig={len(orig_data)} current={len(cur_data)}'
    if cur_consumed > orig_consumed:
        return False, f'compressed block overflow current={cur_consumed} original={orig_consumed}'

    preserved_nonzero = 0
    changed_preserved = []
    for tile_id in range(1024):
        start = tile_id * 32
        orig_tile = orig_data[start:start + 32]
        cur_tile = cur_data[start:start + 32]
        if part2_result_summary_dirty_tile(tile_id) or not any(orig_tile):
            continue
        preserved_nonzero += 1
        if orig_tile != cur_tile:
            changed_preserved.append(tile_id)
    cur_nonzero = sum(1 for tile_id in range(1024)
                      if any(cur_data[tile_id * 32:tile_id * 32 + 32]))
    if preserved_nonzero < 200:
        return False, f'preservation sample too small: {preserved_nonzero}'
    if changed_preserved:
        sample = ','.join(f'0x{x:03X}' for x in changed_preserved[:12])
        return False, f'changed preserved score/rank tiles={len(changed_preserved)} sample={sample}'
    if cur_nonzero < 300:
        return False, f'too few nonzero tiles in result summary: {cur_nonzero}'
    return True, (f'preserved_nonzero={preserved_nonzero}, current_nonzero={cur_nonzero}, '
                  f'compressed={cur_consumed}/{orig_consumed}')


def verify_compact_display_visual_matrix(current_sha):
    """Ensure the E12 matrix snapshot is not stale against the current output ROM."""
    if not current_sha:
        return False, 'current output SHA unavailable'
    if not os.path.exists(COMPACT_DISPLAY_VISUAL_MATRIX):
        return False, f'matrix missing: {COMPACT_DISPLAY_VISUAL_MATRIX}'
    try:
        matrix = json.load(open(COMPACT_DISPLAY_VISUAL_MATRIX, encoding='utf-8'))
    except Exception as e:
        return False, f'matrix JSON load failed: {e}'
    matrix_sha = matrix.get('rom_sha256')
    if matrix_sha != current_sha:
        return False, f'matrix ROM SHA stale: matrix={matrix_sha} output={current_sha}'
    for dep_key, dep_label in [
        ('renderer_trace', 'renderer trace'),
        ('code_context_analysis', 'code context analysis'),
        ('xref_analysis', 'xref analysis'),
    ]:
        dep = matrix.get(dep_key) or {}
        if dep.get('present') and dep.get('current_rom') is not True:
            return False, (
                f'{dep_label} stale in compact visual matrix: '
                f'{dep.get("rom_sha256")} != {current_sha}'
            )
    manual = matrix.get('manual_visual_evidence') or {}
    manual_source_sha = manual.get('source_sha256')
    if manual_source_sha:
        if not os.path.exists(COMPACT_DISPLAY_MANUAL_VISUAL_EVIDENCE):
            return False, f'manual visual evidence source missing: {COMPACT_DISPLAY_MANUAL_VISUAL_EVIDENCE}'
        actual_manual_sha = sha256(read(COMPACT_DISPLAY_MANUAL_VISUAL_EVIDENCE))
        if manual_source_sha != actual_manual_sha:
            return False, (
                'manual visual evidence source SHA stale: '
                f'matrix={manual_source_sha} actual={actual_manual_sha}'
            )
    if manual.get('invalid_count', 0):
        return False, f'manual visual evidence invalid_count={manual.get("invalid_count")}'
    if manual.get('stale_count', 0):
        return False, f'manual visual evidence stale_count={manual.get("stale_count")}'
    if manual.get('unmatched_current_count', 0):
        return False, f'manual visual evidence unmatched_current_count={manual.get("unmatched_current_count")}'
    target_by_key = {}
    for group in matrix.get('groups', []):
        gid = group.get('id')
        for target in group.get('targets', []):
            addr = parse_addr(target.get('address'))
            if gid and addr is not None:
                target_by_key[(gid, addr)] = target
    for row in manual.get('entries', []):
        if not row.get('accepted'):
            continue
        addr = parse_addr(row.get('address'))
        key = (row.get('group'), addr)
        target = target_by_key.get(key)
        if target is None:
            return False, f'accepted manual evidence is not a matrix target: {row.get("group")} {row.get("address")}'
        if int(row.get('pixel_diff_count') or 0) <= 0:
            return False, f'accepted manual evidence has nonpositive diff: {row.get("address")}'
        contact = row.get('contact_sheet')
        if not contact or not os.path.exists(os.path.join(BASE, contact)):
            return False, f'accepted manual evidence contact missing: {row.get("address")} {contact}'
        contact_sha = row.get('contact_sheet_sha256')
        if not contact_sha:
            return False, f'accepted manual evidence contact SHA missing: {row.get("address")} {contact}'
        if sha256(read(os.path.join(BASE, contact))) != contact_sha:
            return False, f'accepted manual evidence contact SHA mismatch: {row.get("address")} {contact}'
        if row.get('type') == 'single_address_mutation_pixel_diff':
            diff_mask = row.get('diff_mask')
            if not diff_mask or not os.path.exists(os.path.join(BASE, diff_mask)):
                return False, f'accepted manual evidence diff mask missing: {row.get("address")} {diff_mask}'
            diff_mask_sha = row.get('diff_mask_sha256')
            if not diff_mask_sha:
                return False, f'accepted manual evidence diff mask SHA missing: {row.get("address")} {diff_mask}'
            diff_mask_path = os.path.join(BASE, diff_mask)
            if sha256(read(diff_mask_path)) != diff_mask_sha:
                return False, f'accepted manual evidence diff mask SHA mismatch: {row.get("address")} {diff_mask}'
            if nonblack_pixel_count(diff_mask_path) != int(row.get('pixel_diff_count') or 0):
                return False, f'accepted manual evidence diff mask pixel count mismatch: {row.get("address")} {diff_mask}'
            null_control = row.get('null_control') or {}
            if null_control.get('enabled'):
                if not null_control.get('deterministic'):
                    return False, f'accepted manual evidence null-control is not deterministic: {row.get("address")}'
                if int(null_control.get('pixel_diff_count') or 0) != 0:
                    return False, f'accepted manual evidence null-control diff is nonzero: {row.get("address")}'
            if row.get('expected_diff_box') is not None and row.get('diff_bbox_within_expected_box') is not True:
                return False, f'accepted manual evidence diff bbox outside expected box: {row.get("address")}'
        attached = any(
            ev.get('accepted') and ev.get('contact_sheet') == contact
            for ev in target.get('manual_visual_evidence', [])
        )
        if not attached:
            return False, f'accepted manual evidence not attached to target row: {row.get("group")} {row.get("address")}'
    for group in matrix.get('groups', []):
        summary = group.get('summary') or {}
        if summary.get('expected_count_match') is False:
            return False, f'{group.get("id")} expected_count mismatch'
    return True, (
        f'matrix_sha={matrix_sha[:8]}, manual_current={manual.get("current_count", 0)}, '
        f'manual_accepted={manual.get("accepted_count", 0)}'
    )


def main():
    ok = True
    print('=== 배포 무결성 게이트 (verify_dist_integrity) ===')

    # 1) 산출물 3종 동일성
    out_sha = {}
    for name, path in OUTPUTS.items():
        if not os.path.exists(path):
            print(f'[WARN] 산출물 없음: {path}')
            continue
        out_sha[name] = sha256(read(path))
    if out_sha:
        uniq = set(out_sha.values())
        print(f'산출물 SHA: ' + ', '.join(f'{k}={v[:8]}' for k, v in out_sha.items()))
        if len(uniq) != 1:
            print('[FAIL] full/final/title_test SHA 불일치')
            ok = False
        else:
            print('[OK] 산출물 3종 바이트 동일')
    current_sha = out_sha.get('full')

    if not os.path.exists(ORIGINAL):
        print(f'[WARN] 원본 ROM 없음(round-trip 생략): {ORIGINAL}')
        original = None
    else:
        original = read(ORIGINAL)
    current_rom = read(OUTPUTS['full']) if os.path.exists(OUTPUTS['full']) else None

    if original is not None and current_rom is not None:
        result_ok, result_msg = verify_part2_result_summary_preservation(original, current_rom)
        print(f'[{ "OK" if result_ok else "FAIL"}] Part2 결과 요약 숫자/랭크 타일 보존: {result_msg}')
        if not result_ok:
            ok = False

    matrix_ok, matrix_msg = verify_compact_display_visual_matrix(current_sha)
    print(f'[{ "OK" if matrix_ok else "FAIL"}] E12 compact visual matrix 동기화: {matrix_msg}')
    if not matrix_ok:
        ok = False

    # 2) manifest별 3중(4중) 해시 일치
    for mpath in MANIFESTS:
        if not os.path.exists(mpath):
            print(f'[WARN] manifest 없음: {mpath}')
            continue
        m = json.load(open(mpath, encoding='utf-8'))
        man_sha = (m.get('patched_rom') or {}).get('sha256')
        print(f'\n--- {os.path.basename(mpath)} ---')
        print(f'manifest.patched_rom.sha256 = {man_sha}')
        print(f'현재 output(full).sha256     = {current_sha}')
        if man_sha != current_sha:
            print('[FAIL] manifest.patched_sha != 현재 output sha (배포본 STALE)')
            ok = False
        else:
            print('[OK] manifest.patched_sha == 현재 output sha')

        if original is None:
            continue
        for kind, applier in (('bps_patch', apply_bps), ('ips_patch', apply_ips)):
            info = m.get(kind) or {}
            fn = info.get('file')
            if not fn:
                continue
            ppath = os.path.join(BASE, 'dist', fn)
            if not os.path.exists(ppath):
                print(f'[WARN] 패치 파일 없음: {ppath}')
                continue
            patch = read(ppath)
            try:
                result = applier(original, patch)
            except Exception as e:
                print(f'[FAIL] {kind} 적용 오류({fn}): {e}')
                ok = False
                continue
            rsha = sha256(bytes(result))
            match = (rsha == current_sha)
            print(f'{kind}({fn}) 적용결과 sha = {rsha[:16]}  {"[OK]" if match else "[FAIL] != output"}')
            if not match:
                ok = False

    # B팀(쪼롱이) 권위문 drift + CSV 손상 ROM 일본어 잔존 + scene container residual 증거를
    # 배포 전 하드게이트로 묶는다(codex/agy/claude 리뷰).
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    for label, tool, extra in [('B팀 drift', 'qa_bteam_drift.py', []),
                               ('CSV ROM 일본어 잔존', 'qa_csv_integrity.py', ['--fail-on-rom-japanese']),
                               ('text fit', 'qa_text_fit.py', []),
                               ('ADDRESS_TEXT_OVERRIDES governance',
                                'audit_address_text_overrides.py', ['--strict']),
                               ('CSV override shadow', 'audit_csv_override_shadow.py', ['--strict']),
                               ('repoint punctuation', 'audit_repoint_punctuation.py', ['--strict']),
                               ('repoint integrity', 'qa_repoint_integrity.py', []),
                               ('CO glyph dictionary coverage', 'qa_glyph_dictionary_tables.py', []),
                               ('Part1 compact help', 'qa_part1_compact_help.py', []),
                               ('scene container residual', 'audit_scene_residual_scans.py', ['--strict']),
                               ('visual region', 'qa_visual_regions.py', []),
                               ('sprite override fit', 'audit_sprite_override_report.py', ['--strict'])]:
        res = subprocess.run([sys.executable, os.path.join(here, tool), *extra],
                             capture_output=True, text=True)
        rc = res.returncode
        print(f'[{ "OK" if rc == 0 else "FAIL"}] {label} 게이트 (rc={rc})')
        if rc != 0:
            if res.stdout:
                print(res.stdout)
            if res.stderr:
                print(res.stderr, file=sys.stderr)
            ok = False

    print('\n=== 결과: ' + ('PASS' if ok else 'FAIL (배포본을 Phase F에서 재생성 필요)') + ' ===')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
