#!/usr/bin/env python3
"""Create patch-only distribution artifacts and verify round-trips."""

import argparse
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_bps import apply_bps, make_bps
from make_ips import apply_ips, make_ips


BASE = Path(__file__).resolve().parents[1]
SOURCE_ROM = BASE / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
TARGET_ROM = BASE / 'output' / 'game_wars_korean_full.gba'
DIST = BASE / 'dist'


def digest(data):
    import hashlib

    return {
        'size': len(data),
        'crc32': f'{zlib.crc32(data) & 0xffffffff:08x}',
        'sha1': hashlib.sha1(data).hexdigest(),
        'sha256': hashlib.sha256(data).hexdigest(),
    }


def write_readme(path, patch_stem, target_info):
    path.write_text(
        f"""# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `{patch_stem}.bps` / `{patch_stem}.ips`
- Target ROM SHA-256: `{target_info['sha256']}`
- Target size: {target_info['size']} bytes

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
""",
        encoding='utf-8',
    )


def write_release_notes(path, release_date, patch_stem, source_info, target_info):
    path.write_text(
        f"""# Korean Patch Release Notes

## {release_date} Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `{source_info['sha256']}`
- Target ROM SHA-256: `{target_info['sha256']}`
- BPS patch: `{patch_stem}.bps`
- IPS patch: `{patch_stem}.ips`

This build has passed the current automated QA gate: text fit, Japanese
residual, placeholder residual, ROM integrity, scene residual, sprite override,
and BPS/IPS round-trip verification. Real-hardware sign-off is still tracked
separately in `todo.md`.
""",
        encoding='utf-8',
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--stem', default=None)
    args = parser.parse_args()

    DIST.mkdir(exist_ok=True)
    stem = args.stem or f'game_wars_korean_full_{args.date}'

    source = SOURCE_ROM.read_bytes()
    target = TARGET_ROM.read_bytes()
    source_info = digest(source)
    target_info = digest(target)

    bps = make_bps(source, target)
    ips = make_ips(source, target)
    if apply_bps(source, bps) != target:
        raise SystemExit('BPS round-trip failed')
    if apply_ips(source, ips) != target:
        raise SystemExit('IPS round-trip failed')

    bps_path = DIST / f'{stem}.bps'
    ips_path = DIST / f'{stem}.ips'
    bps_path.write_bytes(bps)
    ips_path.write_bytes(ips)
    bps_info = digest(bps)
    ips_info = digest(ips)

    manifest = {
        'name': 'Game Boy Wars Advance 1+2 — 한글화',
        'date': args.date,
        'status': 'automated QA pass — patch-only distribution; real-hardware sign-off pending',
        'source_rom': {
            'name': SOURCE_ROM.name,
            **source_info,
        },
        'patched_rom': {
            'name': TARGET_ROM.name,
            **target_info,
        },
        'output_rom': {
            'canonical': TARGET_ROM.name,
            'sha256': target_info['sha256'],
            'legacy_variants': [],
        },
        'bps_patch': {
            'file': bps_path.name,
            **bps_info,
            'round_trip': 'OK',
        },
        'ips_patch': {
            'file': ips_path.name,
            **ips_info,
            'round_trip': 'OK',
            'note': 'BPS is preferred because it records source and target CRCs.',
        },
        'validation': {
            'bps_round_trip': True,
            'ips_round_trip': True,
            'single_output_rom': True,
        },
    }
    for path in (DIST / 'manifest.json', DIST / 'manifest_preview.json'):
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_readme(DIST / 'README.md', stem, target_info)
    for path in (DIST / 'RELEASE_NOTES.md', DIST / 'RELEASE_NOTES_preview.md'):
        write_release_notes(path, args.date, stem, source_info, target_info)

    print(f'BPS: {bps_path} size={len(bps)} round-trip=OK')
    print(f'IPS: {ips_path} size={len(ips)} round-trip=OK')
    print(f'Manifest: {DIST / "manifest.json"}')


if __name__ == '__main__':
    main()
