#!/usr/bin/env python3
"""Screen proof that an OBJ title sheet is drawn with its cells edge to edge.

Each OBJ cell of the sheet (decoded from the ROM the frame was captured with)
is located independently in the captured frame: the best position is where
the cell's palette indices map to frame colours most consistently. The proof
holds when every cell is found (consistency >= 0.98) and cell k sits exactly
k * cell width to the right of cell 0 on the same row.
usage: qa_screen_obj_contiguity.py --rom ROM --frame PNG --asset OFF --cells N
       --cell-w TILES --cell-h TILES [--first TILE] [--json OUT]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw_fonts  # noqa: E402
from lz77_scan import lz77_decompress  # noqa: E402


def locate(frame, cell):
    """Best (score, x, y) of an index grid inside an RGB frame (transparent 0 ignored)."""
    cell = np.array(cell)
    ys, xs = np.nonzero(cell)
    if len(ys) < 20:
        return None
    vals = cell[ys, xs]
    keyed = frame[..., 0].astype(np.int64) << 16 | frame[..., 1].astype(np.int64) << 8 | frame[..., 2]
    fh, fw = keyed.shape
    ch, cw = cell.shape
    best = (0.0, None, None)
    for y in range(0, fh - ch + 1):
        for x in range(0, fw - cw + 1):
            colours = keyed[ys + y, xs + x]
            score, mapped = 0, set()
            for v in np.unique(vals):
                sel = colours[vals == v]
                uniq, counts = np.unique(sel, return_counts=True)
                score += counts.max()
                mapped.add(int(uniq[counts.argmax()]))
            # The palette mapping must be one colour per index (injective):
            # a blank or flat area cannot satisfy several indices at once.
            if len(mapped) != len(np.unique(vals)):
                continue
            score /= len(vals)
            if score > best[0]:
                best = (score, x, y)
    return best


def prove(rom, frame_path, asset, cells, cell_w, cell_h, first=0):
    data = lz77_decompress(rom, asset)[0]
    frame = np.array(Image.open(frame_path).convert('RGB'))
    found = []
    for k in range(cells):
        cell = aw_fonts.obj_canvas(data, 1, cell_w, cell_h, first + k * cell_w * cell_h)
        found.append(locate(frame, cell))
    present = [(k, f) for k, f in enumerate(found) if f is not None]
    ok = bool(present) and all(f[0] >= 0.98 for _, f in present) and len(present) >= 2
    if ok:
        k0, f0 = present[0]
        ok = all(f[1] - f0[1] == (k - k0) * cell_w * 8 and f[2] == f0[2] for k, f in present)
    return {'asset': f'0x{asset:06X}', 'frame': str(frame_path), 'cells': cells,
            'cell_px': [cell_w * 8, cell_h * 8],
            'found': [None if f is None else {'score': round(f[0], 4), 'x': f[1], 'y': f[2]} for f in found],
            'contiguous': ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--frame', required=True)
    ap.add_argument('--asset', required=True, type=lambda s: int(s, 0))
    ap.add_argument('--cells', type=int, required=True)
    ap.add_argument('--cell-w', type=int, required=True)
    ap.add_argument('--cell-h', type=int, required=True)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--json')
    a = ap.parse_args()
    result = prove(Path(a.rom).read_bytes(), a.frame, a.asset, a.cells, a.cell_w, a.cell_h, a.first)
    print(json.dumps(result, ensure_ascii=False))
    if a.json:
        Path(a.json).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result['contiguous'] else 1


if __name__ == '__main__':
    sys.exit(main())
