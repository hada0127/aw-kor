import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qa_text_fit as Q


class TextFitCliTests(unittest.TestCase):
    def test_help_does_not_scan_translation_data(self):
        output = io.StringIO()
        with patch.object(Q, 'load_found') as scan, contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as result:
                Q.main(['--help'])
        self.assertEqual(result.exception.code, 0)
        scan.assert_not_called()
        self.assertIn('usage:', output.getvalue())

    def test_unknown_option_does_not_start_scan(self):
        with patch.object(Q, 'load_found') as scan, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                Q.main(['--unknown-option'])
        self.assertEqual(result.exception.code, 2)
        scan.assert_not_called()

    def test_actual_level12_encoding_is_counted_alongside_overflow(self):
        # Only the final candidate fits: remove spaces and parentheses, shorten
        # 입니다 to 임. Earlier shortened candidates still retain parentheses.
        root = Path(Q.BASE)
        with tempfile.TemporaryDirectory(prefix='qa_text_fit_', dir=root / 'temp') as directory:
            work = Path(directory)
            found, trans, syl = (work / name for name in ('found.csv', 'trans.csv', 'syl.json'))
            with found.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['address', 'length', 'text', 'hex_bytes'])
                writer.writeheader()
                for address, size in [('800000', 6), ('800010', 4), ('800020', 1)]:
                    writer.writerow(dict(address=address, length=size, text='あい', hex_bytes=''))
            with trans.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['address', 'korean', 'japanese'])
                writer.writeheader()
                for address, text in [('800000', '가 나입니다()'), ('800010', '가나'), ('800020', '가나')]:
                    writer.writerow(dict(address=address, korean=text, japanese='あい'))
            actual_codes = json.loads(Path(Q.SYLCODE).read_text(encoding='utf-8'))
            syl.write_text(json.dumps({char: actual_codes[char] for char in '가나입니다임'}), encoding='utf-8')
            output = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.multiple(Q, FOUND=str(found), TRANS=str(trans), SYLCODE=str(syl),
                                                 COMPREHENSIVE_TRANS=str(work / 'absent.csv'),
                                                 ADDRESS_TEXT_OVERRIDES={}, SOURCE_TEXT_OVERRIDES={},
                                                 TEXT_OVERRIDES={}))
                stack.enter_context(patch.object(Q, 'load_direct_patch_texts', return_value={}))
                stack.enter_context(patch.object(Q, 'load_display_overrides', return_value={}))
                stack.enter_context(patch.object(Q, 'refresh_compact_glyph_dictionary_overrides'))
                stack.enter_context(patch.object(Q, 'in_deny', return_value=False))
                stack.enter_context(contextlib.redirect_stdout(output))
                Q.main([])
            report = output.getvalue()
            lines = report.splitlines()
            self.assertIn('written(한글 인코딩): 2', lines)
            levels_line = next(line for line in lines if line.startswith('fit levels: '))
            levels = dict(item.split('=') for item in levels_line.removeprefix('fit levels: ').split(', '))
            expected_levels = {f'level{k}': '0' for k in range(13)}
            expected_levels.update(level0='1', level12='1')
            self.assertEqual(levels, expected_levels)
            self.assertIn('layout-loss fallback(level>=6, 재배치 검토): 1', lines)
            self.assertIn('overflow(슬롯초과 skip→원문): 1', lines)


if __name__ == '__main__':
    unittest.main()
