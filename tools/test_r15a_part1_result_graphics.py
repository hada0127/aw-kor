"""R15a/R17 current-generator goldens: Part 1 result/record screens (2026-11-09).

Each asset was reached live on the JP and candidate ROMs (CHEAT where noted,
temp/fix_20261104/gfx/R15a_REPORT.md); these goldens pin the generators
without reading temp/.  AW_TEST_ROM (optional) checks a full build carries the
same decoded sheets.
"""
import hashlib
import os
import struct
import unittest
from pathlib import Path

import part1_campaign_clear_banner as clear
import part1_capture_word_obj as capture
import part1_map_result_banners as result
import part1_mission_titles as titles
import part1_record_screen as record
import part1_versus_settle_banner as settle
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

GOLDEN = {
    'title_0xC10B34': 'a082ff295a6845adf009526494a9eff6e89b114a40e90b8e6cd8a5d0db2b9cec',
    'title_0xC11D9C': '7cf549694e9d94e848fa9d4f632becc98e8096bbfeab6e3dfd6fe18f4c49ae1b',
    'title_0xC1205C': '2a2f7bb127e65d513f0ec7b8ab08f2e17bc7e3487495a03f53ca8b2446a52651',
    'clear_sheet': '6d795a2374ebc5c754778a9316e6781c4cc0f37deababff4da86db4be89d6f9b',  # R20 rank strips
    'result_WIN': 'efe4f952d9114d6213eb2e8af67aeba675c39454b77f9a9a8ceddf51b41887c7',
    'result_DRAW': '1cf0c35722a73adff3d481173b7355806fc6df18abca32236e4a6ee29748e437',
    'result_LOSE': 'ecf41073d7a36775b728d5608412bf4b81900fefe37c8ead96b8e403c65a8747',
    'record_title_tiles': '76036da7e9171a273c4a199feda413fdf181a692cd76a559ecf0ed9156b7d267',
    'settle_sheet': '2319eea49c97e08159f6452c011632db65db8985fef204bfebbf199de8425ef1',
    'capture_word': 'e6a1d6cb8f76a56736acc95ca7ae158072c07ed0e5d5841616750aebca5c7655',
}


def current():
    out = {}
    for source in (0xC10B34, 0xC11D9C, 0xC1205C):
        out[f'title_0x{source:06X}'] = titles.render(source)
    out['clear_sheet'] = clear.sheet(ORIGINAL)
    for banner in result.BANNERS:
        out[f'result_{banner[0]}'] = result.sheet(ORIGINAL, banner)
    rom = bytearray(ORIGINAL)
    record.patch(rom, ORIGINAL)
    out['record_title_tiles'] = bytes(rom[record.SHEET + 64 * 32:record.SHEET + 96 * 32])
    out['settle_sheet'] = settle.sheet(ORIGINAL)
    out['capture_word'] = capture.generated(ORIGINAL)
    return out


class R15aPart1ResultGraphics(unittest.TestCase):
    def test_current_generator_goldens(self):
        for name, data in current().items():
            self.assertEqual(hashlib.sha256(data).hexdigest(), GOLDEN[name], name)

    def test_training_titles_are_part1_table_entries(self):
        for index, source in ((0, 0xC10B34), (7, 0xC11D9C), (8, 0xC1205C)):
            self.assertEqual(struct.unpack_from('<I', ORIGINAL, titles.TABLE + 4 * index)[0],
                             0x08000000 + source)
            self.assertNotIn(source, titles.SKIP)
            values = {(b >> s) & 15 for b in titles.render(source) for s in (0, 4)}
            self.assertTrue(values <= {0, titles.INK, 11, titles.SHADOW, titles.OUTLINE})

    def test_jp_index_roles(self):
        values = {v for ch in clear.GLYPHS for row in clear.render_cell(ch) for v in row}
        self.assertTrue({1, 2, 7, 11, 13, 14} <= values <= {0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 13, 14})
        for name, ramp in result.BAND_AA.items():
            banner = next(b for b in result.BANNERS if b[0] == name)
            px = result._decode(result.sheet(ORIGINAL, banner))
            x0, y0, x1, y1 = banner[8]
            used = {px[y][x] for y in range(y0, y1) for x in range(x0, x1)}
            self.assertTrue(set(ramp) - {banner[7], result.INK} & used, name)
        word = {v for row in capture._pixels() for v in row}
        self.assertTrue({1, 12, 14} <= word <= {0, 1, 2, 3, 4, 5, 6, 12, 13, 14})

    def test_fresh_build_carries_generated_sheets(self):
        candidate = os.environ.get('AW_TEST_ROM')
        if not candidate:
            self.skipTest('AW_TEST_ROM required for fresh candidate checks')
        rom = Path(candidate).read_bytes()
        cur = current()
        for source in (0xC10B34, 0xC11D9C, 0xC1205C):
            self.assertEqual(lz77_decompress(rom, titles.stream_address(rom, source))[0],
                             cur[f'title_0x{source:06X}'])
        live = struct.unpack_from('<I', rom, clear.SOURCE_POINTERS[0])[0] - 0x08000000
        self.assertEqual(lz77_decompress(rom, live)[0], cur['clear_sheet'])
        for banner in result.BANNERS:
            self.assertEqual(lz77_decompress(rom, banner[1])[0], cur[f'result_{banner[0]}'])
        self.assertEqual(rom[record.SHEET + 64 * 32:record.SHEET + 96 * 32], cur['record_title_tiles'])
        self.assertEqual(lz77_decompress(rom, settle.SOURCE)[0], cur['settle_sheet'])
        self.assertEqual(rom[capture.OFFSET:capture.OFFSET + capture.SIZE], cur['capture_word'])


if __name__ == '__main__':
    unittest.main()
