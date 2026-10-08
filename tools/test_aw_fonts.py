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
