#!/usr/bin/env python3
"""Audit the restored menu profile and migrate only two known generated overrides.

No ROM is written. Unknown records are preserved; user changes to the two
target records fail before any write. Rendered sheets are asset evidence,
not proof of in-game reachability.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from PIL import Image
import build_title_hangul as title
from export_sprites import tiles_to_indices
from sprite_text_aa import PART1_STYLE_PALETTES
from editor_storage import EDITOR_LOCK, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
# Canonical records committed in 6fc6085, generated during the Noto change.
GENERATED_RECORDS = {
    'lz77_00C03880': 'db0986da4e9be82d6117fa5fbbeb1f332d33819d913f32bcaf2c3518d0d39cc5',
    'lz77_00C03AF0': '9b1faefea9ac05b1eaabc196f465a07fc6c02dcf42bf4514f4ff730650d12f62',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def migrate_records(records):
    result = copy.deepcopy(records)
    for key, previous_hash in GENERATED_RECORDS.items():
        if key not in records:
            continue  # Removed override remains removed; the builder renders it.
        record = records[key]
        offset = int(key.split('_')[1], 16)
        _, _, label, size = next(row for row in title.PART1_MODE_OPTION_BLOCKS if row[1] == offset)
        raw = title.option_layer_to_tiles(title.make_part1_option_block(label, size))
        grid, width, height = tiles_to_indices(raw, 32)
        updated = copy.deepcopy(record)
        updated['indices'] = grid
        if record == updated:
            continue  # Idempotent, including user metadata.
        if digest(record) != previous_hash:
            raise ValueError(f'User-edited override must be preserved: {key}')
        if (width, height) != (record['width'], record['height']):
            raise ValueError(f'Storage dimensions changed: {key}')
        result[key] = updated
    return result


def audit(out):
    font_hash = hashlib.sha256(title.MENU_FONT_PATH.read_bytes()).hexdigest()
    if font_hash != title.MENU_FONT_SHA256:
        raise ValueError('Restored OkDanDan font differs from the verified source')
    source = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
    specs = [(offset, label, size, True) for _, offset, label, size in title.PART1_MODE_OPTION_BLOCKS]
    specs += [(offset, label, size, False) for _, offset, label, size in title.PART1_SUBMENU_LOGO_BLOCKS]
    specs += [(offset, label, size, False) for _, offset, label, size in title.PART1_MAIN_HEADER_BLOCKS]
    rows, images = [], []
    for offset, label, size, option in specs:
        layer = title.make_part1_option_block(label, size) if option else title.make_part1_header_with_footer(offset, label, size)
        raw = title.option_layer_to_tiles(layer) if option else title.part1_logo_layer_to_tiles(layer)
        compressed = title.lz77_compress_optimal(raw, vram_safe=True)
        original, capacity = title.lz77_decompress(source, offset)
        if len(raw) != len(original) or len(compressed) > capacity:
            raise ValueError(f'Slot does not fit: {offset:#x}')
        if title.lz77_decompress(compressed, 0)[0] != raw:
            raise ValueError(f'Compression round trip failed: {offset:#x}')
        if not set(layer.tobytes()) <= {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14}:
            raise ValueError(f'Unexpected palette index: {offset:#x}')
        if not option:
            footer_y = title.part1_footer_y(offset)
            region = (0, footer_y, 80, 32)
            if layer.crop(region).tobytes() != title.original_part1_footer(offset).crop(region).tobytes():
                raise ValueError(f'Protected English footer changed: {offset:#x}')
        rows.append({'offset': hex(offset), 'label': label, 'compressed_bytes': len(compressed),
                     'capacity': capacity, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                     'bbox': layer.getbbox()})
        colored = layer.convert('P')
        colored.putpalette([v for color in PART1_STYLE_PALETTES[2] for v in color] + [0] * 720)
        images.append(colored.convert('RGB').resize((layer.width * 3, 96), Image.Resampling.NEAREST))
    out.mkdir(parents=True, exist_ok=True)
    # Size from actual images, so future wider labels or additional rows cannot
    # silently overlap or fall outside the review sheet.
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images)
    sheet = Image.new('RGB', (cell_width * 3, cell_height * ((len(images) + 2) // 3)), '#eeeeee')
    for index, image in enumerate(images):
        sheet.paste(image, ((index % 3) * cell_width, (index // 3) * cell_height))
    sheet.save(out / 'restored_assets.png')
    report = {'font_sha256': font_hash, 'source_sha256': hashlib.sha256(source).hexdigest(),
              'scope': f'{len(rows)} rendered assets; runtime reachability requires separate cold captures',
              'assets': rows}
    (out / 'profile_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'temp/sprite_2026-09-23')
    parser.add_argument('--migrate-known-overrides', action='store_true')
    args = parser.parse_args()
    report = audit(args.out)
    if args.migrate_known_overrides:
        path = ROOT / 'data/sprites_overrides.json'
        with EDITOR_LOCK:
            before = path.read_bytes()
            records = json.loads(before)
            updated = migrate_records(records)
            if path.read_bytes() != before:
                raise ValueError('Overrides changed during audit; refusing to overwrite')
            if updated != records:
                atomic_write_text(path, json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
        report['override_records_before'] = {key: digest(value) for key, value in records.items()}
        report['override_records_after'] = {key: digest(value) for key, value in updated.items()}
        (args.out / 'migration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"PASS: {len(report['assets'])} menu assets, original capacities and protected footers")


if __name__ == '__main__':
    main()
