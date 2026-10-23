"""ROM-free regressions for lossless title fit and editor budget helpers."""
import collections
import ast
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_korean_full as B
from part2_mission_title_fit import encode_pair_title, NATIVE_TITLE_SOURCES


def load_editor(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name / 'server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PairTitleFitContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codes = {k: int(v, 16) for k, v in json.loads(Path(B.SYLCODE).read_text()).items()}

    def test_five_restored_title_sources_reject_old_residuals(self):
        import qa_bteam_drift as drift
        expected = {
            0xA2D5C8: ('내일로의 7일간', '내일로　７일간', 14),
            0xA2D650: ('내일로의 7일간', '내일향한　７일', 14),
            0xA2D684: ('전차대를 격파하라!', '전차대　격파', 18),
            0xA2D6AC: ('검은 악마를 막아라!', '검은　악마를　막아！', 18),
            0xA2D6F0: ('푸른 달이여,영원히', '푸른달　영원히', 16),
        }
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())['overrides']
        overrides = json.loads((ROOT / 'data/dialogue_overrides.json').read_text())
        pins = json.loads((ROOT / 'data/bteam_round2_active_pins.json').read_text())
        tree = ast.parse(Path(B.__file__).read_text())
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name in ('_rp_dlg', '_rp_fixed_bytes', '_rp_fit_level')]
        for address, (text, abbreviated, slot) in expected.items():
            with self.subTest(address=hex(address)):
                key = f'0x{address:08X}'
                self.assertEqual(baseline[key], text)
                self.assertEqual(overrides[key], text)
                self.assertNotIn(address, B.BTEAM_ROUND2_RESIDUALS)
                self.assertNotIn(key, pins)
                ns = dict(vars(B), _rp_script_owners={}, _display_ov={},
                          _editor_intents={}, _dlg_ov=overrides, _rp_ov=lambda a: overrides[f'0x{a:08X}'],
                          _rp_bteam=set(expected), _rp_intended={}, syl_to_code=self.codes,
                          unmapped=collections.Counter(), slots={address: slot},
                          required_script_repoints=set(), _rp_inplace_jammed=lambda a: False)
                exec(compile(ast.Module(body=nodes, type_ignores=[]), B.__file__, 'exec'), ns)
                self.assertEqual(ns['_rp_dlg'](address), text)
                self.assertEqual(ns['_rp_fixed_bytes'](address), encode_pair_title(text, self.codes))
                self.assertNotEqual(ns['_rp_fixed_bytes'](address), encode_pair_title(abbreviated, self.codes))
                self.assertEqual(ns['_rp_fit_level'](address), 6)
                self.assertEqual(ns['required_script_repoints'], {address})
                # A reintroduced abbreviated final payload must be unlisted,
                # not accepted by the old residual exemption.
                issue = {'address': key, 'cause': 'relocated row differs from protected baseline'}
                self.assertEqual(drift.round2_issue_bucket(issue, set(B.BTEAM_ROUND2_RESIDUALS)), 'unlisted')

    def test_recorded_sea_vs_air_title_cannot_fit_by_losing_spaces(self):
        # Tracked T4 QA's level-10 residual; actual direct writer requires
        # 14 bytes and relocation from its ten-byte native slot.
        text, address = '해 VS 공!', 0xA2D7D4
        expected = encode_pair_title(text, self.codes)
        self.assertEqual(len(expected), 14)
        for slot in (10, 12, 13):
            with self.subTest(slot=slot):
                self.assertEqual(B.encode_fit(text, slot, self.codes, collections.Counter(), address),
                                 (None, 99))
        self.assertEqual(B.encode_fit(text, 14, self.codes, collections.Counter(), address),
                         (expected, 0))

    def test_all_native_title_sources_reject_lossy_fit(self):
        # Catalogued titles outside the old A2D000 band need the same policy.
        for address in NATIVE_TITLE_SOURCES:
            text = B.BTEAM_PREVIOUS_KOREAN_TEXT.get(address, '해 VS 공!')
            expected = encode_pair_title(B.normalize_korean_terms(text), self.codes)
            with self.subTest(address=hex(address)):
                self.assertEqual(B.encode_fit(text, len(expected) - 1, self.codes,
                                              collections.Counter(), address), (None, 99))
                self.assertEqual(B.encode_fit(text, len(expected), self.codes,
                                              collections.Counter(), address), (expected, 0))

    def test_recorded_titles_cannot_fit_by_losing_exclamation(self):
        for address, text, slot in ((0xA2D61C, '산악의 결사행!', 14),
                                    (0xA2D698, '변경을 되찾아라!', 16),
                                    (0xA2D5A0, '해상 도시 공략!', 16)):
            with self.subTest(address=hex(address)):
                exact = encode_pair_title(text, self.codes)
                self.assertEqual(len(exact), slot + 2)
                self.assertEqual(B.encode_fit(text, slot, self.codes, collections.Counter(), address),
                                 (None, 99))
                self.assertEqual(B.encode_fit(text, len(exact), self.codes, collections.Counter(), address),
                                 (exact, 0))

    def test_both_editor_budget_helpers_report_title_overflow(self):
        dialogue = load_editor('dialogue_editor')
        scene = load_editor('scene_editor')
        for slot, fits in ((10, False), (14, True)):
            with self.subTest(slot=slot):
                self.assertEqual(dialogue.validate_build_fit('해 VS 공!', slot, '0xA2D7D4')['ok'], fits)
                self.assertEqual(scene.build_fit_budget('해 VS 공!', slot, '0xA2D7D4')['fits'], fits)

    def test_title_whitespace_and_punctuation_use_independent_pairs(self):
        address = 0xA2D7D4
        for text in ('해  VS 공!', ' 해　 VS  공!　', '해[]{};▼・공!'):
            expected = encode_pair_title(text, self.codes)
            with self.subTest(text=text):
                for encode in (B.encode_full_fidelity, B.encode_required_full_fidelity):
                    self.assertEqual(encode(text, self.codes, collections.Counter(), address), expected)
                self.assertEqual(B.encode_fit(text, len(expected), self.codes,
                                              collections.Counter(), address), (expected, 0))
                self.assertEqual(B.encode_fit(text, len(expected) - 1, self.codes,
                                              collections.Counter(), address), (None, 99))
        self.assertEqual(encode_pair_title(' 　[]{};▼・', self.codes),
                         bytes.fromhex('81408140816d816e816f8170814781a58145'))

    def test_title_unsupported_input_is_rejected_without_deletion(self):
        for text in ('해·공!', '해\t공!', '해\n공!', '해😀공!', '해힣공!'):
            for encode in (B.encode_full_fidelity, B.encode_required_full_fidelity):
                with self.subTest(text=text, encoder=encode.__name__):
                    with self.assertRaises(AssertionError):
                        encode(text, self.codes, collections.Counter(), 0xA2D7D4)
            with self.assertRaises(AssertionError):
                B.encode_fit(text, 100, self.codes, collections.Counter(), 0xA2D7D4)

    def test_fit_keeps_protected_title_authority(self):
        address = 0xA2D7D4
        # Synthetic authority exercises precedence without editing approved data.
        text = '해  VS 공!'
        expected = encode_pair_title(text, self.codes)
        with patch.dict(B.BTEAM_PREVIOUS_KOREAN_TEXT, {address: text}):
            self.assertEqual(B.encode_fit('무시할 입력😀', len(expected), self.codes,
                                          collections.Counter(), address), (expected, 0))

    def test_repoint_callbacks_use_exact_pairs_and_require_relocation(self):
        tree = ast.parse(Path(B.__file__).read_text())
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name in ('_rp_fixed_bytes', '_rp_fit_level')]
        address = 0xA2D7D4
        for text in ('해  VS 공!', '해　 VS 공!', '해[]{};▼・공!'):
            expected = encode_pair_title(text, self.codes)
            ns = dict(vars(B), _rp_dlg=lambda a: text, syl_to_code=self.codes,
                      unmapped=collections.Counter(), slots={address: len(expected) - 2},
                      required_script_repoints=set(), _rp_inplace_jammed=lambda a: False)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), B.__file__, 'exec'), ns)
            self.assertEqual(ns['_rp_fixed_bytes'](address), expected)
            self.assertEqual(ns['_rp_fit_level'](address), 6)
            self.assertEqual(ns['required_script_repoints'], {address})
            ns['slots'][address] = len(expected)
            ns['required_script_repoints'].clear()
            self.assertEqual(ns['_rp_fit_level'](address), 0)
            self.assertEqual(ns['required_script_repoints'], set())

    def test_non_title_fit_policy_is_unchanged(self):
        payload, level = B.encode_fit('가 나입니다()', 6, self.codes, collections.Counter(), 0x800000)
        self.assertEqual(payload, B.encode_text('가나임', self.codes, collections.Counter(), 0x800000))
        self.assertEqual(level, 12)


if __name__ == '__main__':
    unittest.main()
