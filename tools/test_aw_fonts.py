"""2026-10-08 font rule: OkDanDan for large ROM text, Galmuri for small text."""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

import aw_fonts

TOOLS = Path(__file__).resolve().parent
# Tools that only draw review sheets/screenshots (never ROM pixels) may use system fonts.
NON_ROM_TOOLS = {'build_comparison_sheet.py', 'build_sprite_style_sheet.py', 'drive_part2_first_battle.py',
                 'auto_playthrough.py', 'capture_part1_link_map_list_sweep.py', 'qa_scene_screenshot_sanity.py',
                 'probe_part1_compact_help_reads.py', 'prove_compact_display_mutation.py'}
FORBIDDEN = re.compile(r'(AppleSDGothic|AppleGothic|NanumGothic|NotoSans|Pretendard)[^\'"]*\.(ttc|ttf|otf)|'
                       r'/System/Library/Fonts|/Library/Fonts/')


class FontRuleTests(unittest.TestCase):
    def test_font_dir_override_and_platform_default(self):
        code = 'import aw_fonts; print(aw_fonts.OKDANDAN)'
        env = dict(os.environ, AW_FONT_DIR='/x/fonts')
        out = subprocess.run([sys.executable, '-c', code], cwd=TOOLS, env=env, capture_output=True,
                             text=True, check=True).stdout.strip()
        self.assertEqual(out, '/x/fonts/OkDanDan-Bold.otf')
        env.pop('AW_FONT_DIR')
        out = subprocess.run([sys.executable, '-c', code], cwd=TOOLS, env=env, capture_output=True,
                             text=True, check=True).stdout.strip()
        expected = 'Library/Fonts' if sys.platform == 'darwin' else 'aw-fonts'
        self.assertEqual(Path(out), Path.home() / expected / 'OkDanDan-Bold.otf')

    def test_missing_or_different_font_fails_closed(self):
        code = 'import aw_fonts; aw_fonts.okdandan_path()'
        env = dict(os.environ, AW_FONT_DIR='/nonexistent-aw-fonts')
        result = subprocess.run([sys.executable, '-c', code], cwd=TOOLS, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('OkDanDan-Bold font not found', result.stderr)

    def test_no_rom_writer_uses_a_forbidden_font(self):
        offenders = []
        for path in sorted(TOOLS.glob('*.py')):
            if path.name.startswith('test_') or path.name in NON_ROM_TOOLS:
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if FORBIDDEN.search(line) and 'font rule' not in line and 'was ' not in line:
                    offenders.append(f'{path.name}:{number}: {line.strip()}')
        self.assertEqual(offenders, [])

    def test_cell_check_rejects_cut_and_unproven_straddle(self):
        grid = [[0] * 16 for _ in range(8)]
        grid[3][7] = grid[3][8] = 1          # one glyph across the x=8 OBJ edge
        with self.assertRaisesRegex(AssertionError, 'straddles'):
            aw_fonts.check_cells(grid, (8,), 't')
        native = [[0] * 16 for _ in range(8)]
        with self.assertRaisesRegex(AssertionError, 'straddles'):
            aw_fonts.check_cells(grid, (8,), 't', native=native)
        native[5][7] = native[5][8] = 2      # native art proves edge-to-edge cells
        aw_fonts.check_cells(grid, (8,), 't', native=native)
        aw_fonts.check_cells(grid, (8,), 't', native=True)
        grid[0][2] = 1                       # ink on the canvas border would be cut
        with self.assertRaisesRegex(AssertionError, 'canvas edge'):
            aw_fonts.check_cells(grid, (8,), 't', native=True)
        aw_fonts.check_cells(grid, (8,), 't', native=True, edges=False)

    def test_screen_proof_locates_cells_edge_to_edge(self):
        import numpy as np
        import qa_screen_obj_contiguity as prover
        rng = np.random.default_rng(7)
        cells = [rng.integers(0, 4, size=(8, 8)) for _ in range(2)]
        palette = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        for gap, expected in ((0, True), (3, False)):
            frame = np.full((24, 40, 3), 200, dtype=np.uint8)
            for k, cell in enumerate(cells):
                x0 = 4 + k * (8 + gap)
                region = frame[5:13, x0:x0 + 8]
                region[cell > 0] = palette[cell[cell > 0]]
            found = [prover.locate(frame, cell.tolist()) for cell in cells]
            xs = [f[1] for f in found]
            self.assertEqual(xs[1] - xs[0] == 8, expected)

    @unittest.skipUnless(os.environ.get('AW_TEST_ROM'), 'set AW_TEST_ROM to the candidate under test')
    def test_registered_screen_proofs_cover_their_consumers(self):
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes()
        self.assertTrue(aw_fonts.screen_contiguity(0xBFB45C, rom))
        for sheet in (0xC10B34, 0xC11D9C, 0xC1205C, 0xC15A68, 0xC15C5C):
            self.assertEqual(aw_fonts.screen_contiguity(sheet, rom), 'screen:0x00C12FD8')
        self.assertTrue(aw_fonts.screen_contiguity(0xBFB45C, rom, final=True))
        self.assertTrue(aw_fonts.screen_contiguity(0xC12FD8, rom, final=True))
        self.assertIsNone(aw_fonts.screen_contiguity(0x5B7930, rom))
        changed = bytearray(rom)
        changed[0xB512A0] ^= 1
        with self.assertRaisesRegex(AssertionError, 'consumer changed'):
            aw_fonts.screen_contiguity(0xBFB45C, changed)
        changed = bytearray(rom)
        changed[0x100] ^= 1
        with self.assertRaisesRegex(AssertionError, 'ROM changed'):
            aw_fonts.screen_contiguity(0xBFB45C, changed, final=True)

    def test_final_line_height_includes_outline(self):
        self.assertEqual(aw_fonts.drawn_line_height({(0, 2), (1, 15)}, 1, 1), 16)
        with self.assertRaisesRegex(AssertionError, 'small'):
            aw_fonts.require_large_line({(0, 2), (1, 15)}, 1, 1)
        self.assertEqual(aw_fonts.require_large_line({(0, 2), (1, 16)}, 1, 1), 17)

    def test_sparse_screen_cell_rejects_whole_sheet(self):
        import numpy as np
        import qa_screen_obj_contiguity as prover
        from unittest.mock import patch
        from PIL import Image
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(dir=aw_fonts.ROOT / 'temp') as directory:
            frame = Path(directory) / 'frame.png'
            Image.new('RGB', (32, 16)).save(frame)
            with patch.object(prover, 'lz77_decompress', return_value=(bytes(128), 8)), \
                 patch.object(prover.aw_fonts, 'obj_canvas', return_value=[[1] * 8 for _ in range(8)]), \
                 patch.object(prover, 'locate', side_effect=[(1.0, 0, 0), None, (1.0, 16, 0)]):
                self.assertFalse(prover.prove(bytes(128), frame, 0, 3, 1, 1)['contiguous'])

    def test_link_logo_forced_capacity_switches_to_galmuri(self):
        from PIL import ImageFont
        from unittest.mock import patch
        import build_korean_full as build
        import lz77_compress
        original = (aw_fonts.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        actual_truetype = ImageFont.truetype
        calls, attempts = [], []
        cursor = [0]

        def track_font(path, size, *args, **kwargs):
            calls.append((str(path), size))
            return actual_truetype(path, size, *args, **kwargs)

        def force_capacity(raw, vram_safe=True):
            attempts.append(calls[cursor[0]:])
            cursor[0] = len(calls)
            sizes = [size for path, size in attempts[-1] if path.endswith('Galmuri11-Bold.ttf')]
            return b'\0' if sizes and max(sizes) < aw_fonts.GALMURI_MAX_SIZE else bytes(len(raw) + 1)

        with patch.object(ImageFont, 'truetype', side_effect=track_font), \
             patch.object(lz77_compress, 'lz77_compress_optimal', side_effect=force_capacity), \
             patch.object(build, 'rec_label_layout'):
            build.patch_part2_link_mode_residual_labels(rom)
        def galmuri_sizes(attempt):
            return [size for path, size in attempt if path.endswith('Galmuri11-Bold.ttf')]
        self.assertTrue(any(aw_fonts.GALMURI_MAX_SIZE in galmuri_sizes(a) for a in attempts[:-1]))
        self.assertLess(max(galmuri_sizes(attempts[-1])), aw_fonts.GALMURI_MAX_SIZE)

    @unittest.skipUnless(aw_fonts.OKDANDAN.is_file(), 'OkDanDan-Bold not installed')
    def test_word_cells_never_straddle(self):
        grid = [[0] * 128 for _ in range(32)]
        size = aw_fonts.draw_okdandan_words(grid, (('전투', (2, 2, 62, 30)), ('개시!', (66, 2, 126, 30))),
                                            26, ink=10, shadow=14)
        self.assertGreater(size, aw_fonts.GALMURI_MAX_SIZE)
        aw_fonts.check_cells(grid, (64,), 'words')

    @unittest.skipUnless(aw_fonts.OKDANDAN.is_file(), 'OkDanDan-Bold not installed')
    def test_line_keeps_one_baseline(self):
        chars = '캠페인'
        size = aw_fonts.okdandan_fit_line(24, chars)
        heights = {aw_fonts.okdandan_glyph(ch, size, chars=chars)[2] for ch in chars}
        self.assertEqual(len(heights), 1)
        self.assertLessEqual(heights.pop(), 24)


if __name__ == '__main__':
    unittest.main()
