"""Refresh the two existing menu overrides using the reviewed menu renderer."""
import hashlib
import json
from pathlib import Path

import build_title_hangul as title
from export_sprites import tiles_to_indices
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/sprites_overrides.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    changes = []
    changed = False
    for sid in ('lz77_00C03880', 'lz77_00C03AF0'):
        record = data[sid]
        offset = int(sid[5:], 16)
        _, _, text, size = next(row for row in title.PART1_MODE_OPTION_BLOCKS if row[1] == offset)
        raw = title.option_layer_to_tiles(title.make_part1_option_block(text, size))
        compressed = lz77_compress_optimal(raw, vram_safe=True)
        if len(compressed) > title.PART1_MODE_OPTION_BLOCK_CAPACITY[offset]:
            raise ValueError(f'{sid}: compressed payload exceeds original allocation')
        grid, width, height = tiles_to_indices(raw, record['width'] // 8)
        if (width, height) != (record['width'], record['height']):
            raise ValueError(f'{sid}: override dimensions changed')
        changes.append({'id': sid, 'old_pixels_sha256': hashlib.sha256(bytes(
            pixel for row in record['indices'] for pixel in row)).hexdigest(),
            'new_pixels_sha256': hashlib.sha256(bytes(pixel for row in grid for pixel in row)).hexdigest(),
            'new_tiles_sha256': hashlib.sha256(raw).hexdigest()})
        changed |= record['indices'] != grid
        record['indices'] = grid
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(changes, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
