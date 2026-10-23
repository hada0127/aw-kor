"""ROM-free regressions for lossless title fit and its editor consumers."""
import collections
import importlib.util
import json
from pathlib import Path
import sys
import unittest

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
            expected = B.encode_required_full_fidelity(text, self.codes, collections.Counter(), address)
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

    def test_both_editors_reject_recorded_title_overflow(self):
        dialogue = load_editor('dialogue_editor')
        scene = load_editor('scene_editor')
        for slot, fits in ((10, False), (14, True)):
            with self.subTest(slot=slot):
                self.assertEqual(dialogue.validate_build_fit('해 VS 공!', slot, '0xA2D7D4')['ok'], fits)
                self.assertEqual(scene.build_fit_budget('해 VS 공!', slot, '0xA2D7D4')['fits'], fits)

    def test_non_title_fit_policy_is_unchanged(self):
        payload, level = B.encode_fit('가 나입니다()', 6, self.codes, collections.Counter(), 0x800000)
        self.assertEqual(payload, B.encode_text('가나임', self.codes, collections.Counter(), 0x800000))
        self.assertEqual(level, 12)


if __name__ == '__main__':
    unittest.main()
