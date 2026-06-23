#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Game Boy Wars Advance 1+2 한글 패치 — 엔드유저용 자기완결 적용기.

표준 라이브러리만 사용합니다. (Python 3.6 이상이면 추가 설치 없이 동작)

하는 일:
  1) 사용자가 가진 "원본 일본판 ROM"과 같은 폴더(dist)의 BPS 패치를 읽는다.
  2) 원본 ROM의 SHA-256을 manifest.json의 값과 대조해 올바른 ROM인지 확인한다.
  3) BPS 패치를 적용한다(내부 source/target CRC32 검증 포함).
  4) 결과 ROM의 SHA-256을 manifest와 대조해 검증한 뒤 .gba로 저장한다.

가장 쉬운 사용법 (인자 없이 실행):
    python3 apply_patch.py
  → 이 스크립트가 있는 폴더에서 원본 ROM과 BPS 패치를 자동으로 찾습니다.

직접 지정:
    python3 apply_patch.py "원본 ROM.gba" [출력.gba] [--patch 패치.bps]

BPS 적용 로직은 프로젝트의 tools/make_bps.py(apply_bps)에서 이식했습니다.
"""
import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# BPS 디코더 (tools/make_bps.py에서 이식 — 모든 액션 타입 지원)
# --------------------------------------------------------------------------
def rvarint(buf, pos):
    value = 0
    shift = 1
    while True:
        x = buf[pos]
        pos += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def decode_signed(n):
    offset = n >> 1
    return -offset - 1 if (n & 1) else offset


def apply_bps(src, patch, verify=True):
    if patch[:4] != b'BPS1':
        raise ValueError('BPS1 패치 파일이 아닙니다.')
    if verify and (zlib.crc32(patch[:-4]) & 0xffffffff) != struct.unpack('<I', patch[-4:])[0]:
        raise ValueError('BPS 패치 자체가 손상되었습니다 (patch CRC mismatch).')

    pos = 4
    source_size, pos = rvarint(patch, pos)
    target_size, pos = rvarint(patch, pos)
    metadata_size, pos = rvarint(patch, pos)
    pos += metadata_size
    if source_size != len(src):
        raise ValueError(
            f'원본 ROM 크기가 맞지 않습니다: {len(src)} bytes != 기대값 {source_size} bytes')

    body_end = len(patch) - 12
    out = bytearray()
    source_rel = 0
    target_rel = 0
    while pos < body_end:
        data, pos = rvarint(patch, pos)
        action = data & 3
        length = (data >> 2) + 1
        if action == 0:  # SourceRead
            start = len(out)
            out += src[start:start + length]
        elif action == 1:  # TargetRead
            out += patch[pos:pos + length]
            pos += length
        elif action == 2:  # SourceCopy
            rel, pos = rvarint(patch, pos)
            source_rel += decode_signed(rel)
            out += src[source_rel:source_rel + length]
            source_rel += length
        elif action == 3:  # TargetCopy
            rel, pos = rvarint(patch, pos)
            target_rel += decode_signed(rel)
            for _ in range(length):
                out.append(out[target_rel])
                target_rel += 1

    if len(out) != target_size:
        raise ValueError(f'결과 ROM 크기가 맞지 않습니다: {len(out)} != {target_size}')
    if verify:
        source_crc, target_crc, _patch_crc = struct.unpack('<III', patch[-12:])
        if (zlib.crc32(src) & 0xffffffff) != source_crc:
            raise ValueError('원본 ROM CRC가 패치와 맞지 않습니다 (잘못된 ROM).')
        if (zlib.crc32(out) & 0xffffffff) != target_crc:
            raise ValueError('패치 결과 CRC 검증 실패 (내부 오류).')
    return bytes(out)


# --------------------------------------------------------------------------
# 도우미
# --------------------------------------------------------------------------
def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest():
    mpath = HERE / 'manifest.json'
    if not mpath.exists():
        die(f'manifest.json을 찾을 수 없습니다: {mpath}\n'
            '이 스크립트는 패치 배포 폴더(dist) 안에서 실행해야 합니다.')
    try:
        return json.loads(mpath.read_text(encoding='utf-8'))
    except Exception as e:  # noqa: BLE001
        die(f'manifest.json을 읽을 수 없습니다: {e}')


def die(msg):
    print('\n[오류] ' + msg, file=sys.stderr)
    sys.exit(1)


def find_source_rom(manifest):
    """폴더에서 manifest source SHA-256과 일치하는 .gba를 찾는다."""
    want = manifest['source_rom']['sha256']
    expected_name = manifest['source_rom'].get('name', '')
    candidates = sorted(HERE.glob('*.gba')) + sorted(HERE.parent.glob('*.gba'))
    # 패치 결과물(이미 한글화된 ROM)은 제외
    for cand in candidates:
        try:
            data = cand.read_bytes()
        except Exception:  # noqa: BLE001
            continue
        if sha256_hex(data) == want:
            return cand
    if expected_name:
        print(f'  (참고: 원본 ROM의 정식 파일명은 "{expected_name}" 입니다.)')
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Game Boy Wars Advance 1+2 한글 패치 적용기 (표준 라이브러리만 사용)')
    parser.add_argument('rom', nargs='?', default=None,
                        help='원본 일본판 ROM 경로 (.gba). 생략 시 폴더에서 자동 탐색.')
    parser.add_argument('output', nargs='?', default=None,
                        help='출력 ROM 경로 (.gba). 생략 시 기본 이름으로 저장.')
    parser.add_argument('--patch', default=None,
                        help='적용할 BPS 패치 경로. 생략 시 폴더에서 자동 선택.')
    args = parser.parse_args()

    print('=== Game Boy Wars Advance 1+2 한글 패치 적용기 ===\n')
    manifest = load_manifest()

    # 1) 패치 파일 결정
    if args.patch:
        patch_path = Path(args.patch)
    else:
        patch_name = (manifest.get('bps_patch') or {}).get('file')
        patch_path = HERE / patch_name if patch_name else None
        if not patch_path or not patch_path.exists():
            bps_files = sorted(HERE.glob('*.bps'))
            patch_path = bps_files[-1] if bps_files else None
    if not patch_path or not Path(patch_path).exists():
        die('BPS 패치 파일을 찾을 수 없습니다. --patch로 직접 지정하세요.')
    patch = Path(patch_path).read_bytes()
    print(f'패치 파일 : {patch_path}')

    # 패치 파일 자체 무결성(manifest와 대조, 있으면)
    bps_info = manifest.get('bps_patch') or {}
    if bps_info.get('sha256') and Path(patch_path).name == bps_info.get('file'):
        if sha256_hex(patch) != bps_info['sha256']:
            die('BPS 패치 파일이 manifest와 다릅니다 (배포본 손상).')
        print('  - 패치 SHA-256 검증: OK')

    # 2) 원본 ROM 결정
    if args.rom:
        rom_path = Path(args.rom)
        if not rom_path.exists():
            die(f'원본 ROM을 찾을 수 없습니다: {rom_path}')
        source = rom_path.read_bytes()
        actual = sha256_hex(source)
        if actual != manifest['source_rom']['sha256']:
            die('지정한 ROM이 올바른 원본 일본판이 아닙니다.\n'
                f'  필요한 SHA-256 : {manifest["source_rom"]["sha256"]}\n'
                f'  입력한 ROM    : {actual}\n'
                f'  정식 파일명   : {manifest["source_rom"].get("name", "")}')
    else:
        print('원본 ROM을 폴더에서 자동 탐색 중...')
        rom_path = find_source_rom(manifest)
        if not rom_path:
            die('올바른 원본 일본판 ROM(.gba)을 폴더에서 찾지 못했습니다.\n'
                f'  필요한 SHA-256 : {manifest["source_rom"]["sha256"]}\n'
                '  ROM 경로를 인자로 직접 지정하세요:\n'
                '    python3 apply_patch.py "원본 ROM.gba"')
        source = rom_path.read_bytes()
    print(f'원본 ROM  : {rom_path}')
    print('  - 원본 SHA-256 검증: OK')

    # 3) 패치 적용
    try:
        result = apply_bps(source, patch, verify=True)
    except Exception as e:  # noqa: BLE001
        die(f'패치 적용 실패: {e}')

    # 4) 결과 검증
    result_sha = sha256_hex(result)
    want_sha = manifest['patched_rom']['sha256']
    if result_sha != want_sha:
        die('패치 결과 SHA-256가 manifest와 다릅니다 (검증 실패).\n'
            f'  기대값 : {want_sha}\n'
            f'  실제   : {result_sha}')
    print('  - 결과 SHA-256 검증: OK')

    # 5) 저장 (원본 ROM 덮어쓰기 방지)
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = HERE / 'Game Boy Wars Advance 1+2 (Korean).gba'
    try:
        same = out_path.resolve() == Path(rom_path).resolve()
    except Exception:  # noqa: BLE001
        same = str(out_path) == str(rom_path)
    if same:
        die('출력 경로가 원본 ROM과 같습니다. 원본을 덮어쓰지 않도록 다른 출력 파일명을 지정하세요.')
    out_path.write_bytes(result)

    print('\n=== 완료 ===')
    print(f'한글 ROM 저장: {out_path}')
    print('이제 mGBA 등 에뮬레이터나 실기 플래시카트에서 실행하세요.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
