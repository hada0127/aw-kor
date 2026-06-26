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


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, 'rb') as f:
        return f.read()


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
                               ('ADDRESS_TEXT_OVERRIDES governance',
                                'audit_address_text_overrides.py', ['--strict']),
                               ('scene container residual', 'audit_scene_residual_scans.py', ['--strict']),
                               ('sprite override fit', 'audit_sprite_override_report.py', ['--strict'])]:
        rc = subprocess.run([sys.executable, os.path.join(here, tool), *extra],
                            capture_output=True, text=True).returncode
        print(f'[{ "OK" if rc == 0 else "FAIL"}] {label} 게이트 (rc={rc})')
        if rc != 0:
            ok = False

    print('\n=== 결과: ' + ('PASS' if ok else 'FAIL (배포본을 Phase F에서 재생성 필요)') + ' ===')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
