"""qa_terms_from_rom: active ownership, token-aware decoding, name boundaries.

Synthetic tests need no ROM. The candidate test runs when AW_TEST_ROM,
AW_TEST_MAP and AW_TEST_MANIFEST point at one matching build.
Run: PYTHONPATH=tools python3 -m unittest tools.test_qa_terms_from_rom
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import qa_terms_from_rom as T

ROOT = Path(__file__).resolve().parents[1]
SYL = {s: int(c, 16) for s, c in json.loads(
    (ROOT / 'data/syllable_to_code_2350.json').read_text(encoding='utf-8')).items()}
SP = b'\x81\x40'


def ko(text):
    return b''.join(SP if ch == '　' else SYL[ch].to_bytes(2, 'big') for ch in text)


class NameBoundaryTests(unittest.TestCase):
    def test_one_syllable_variant_counts_only_names(self):
        for text, want in (('몹님。', 1), ('몹　사령관을', 1), ('오오、몹님', 1), ('몹이', 1),
                           ('몹', 1), ('불의를　몹시　싫어한다', 0), ('몹쓸　녀석', 0),
                           ('적몹', 0)):
            with self.subTest(text=text):
                self.assertEqual(T.name_occurrences(text, '몹'), want)

    def test_longer_variants_keep_substring_matching(self):
        self.assertEqual(T.name_occurrences('신참　이완　사령관을', '이완'), 1)
        self.assertEqual(T.name_occurrences('하지만　캐트님、', '캐트'), 1)


class TokenTextTests(unittest.TestCase):
    def setUp(self):
        self.codes = T.load_code2syl()

    def test_native_controls_are_not_letters(self):
        p2 = ko('그') + b'w' + ko('점은') + b'wwr' + ko('각') + b'k' + b'  \0'
        self.assertEqual(T._token_text(p2, 'p2', self.codes), '그점은 각 ')
        # Part 1 name marker and keyword style span draw no letters.
        p1 = b'\n\ti' + ko('님') + b'r2' + ko('정찰차') + b'0' + ko('는') + b'k\n\0'
        self.assertEqual(T._token_text(p1, 'p1', self.codes), '님 정찰차는 ')
        for text in (T._token_text(p2, 'p2', self.codes), T._token_text(p1, 'p1', self.codes)):
            self.assertFalse(set(text) & set('wrkiW20'))


class ActiveOwnershipTests(unittest.TestCase):
    """Old slots, retired allocations and superseded intents are not shipped text."""

    SCRIPT_ROW = 0xA29AB0  # P2 master-table help: native r/k/style commands

    def build(self, folder, *, pointer=0x200):
        rom = bytearray(self.SCRIPT_ROW + 0x40)
        old = ko('몹님')          # native slot of the relocated message (dead)
        new = ko('모프님') + b'\0'
        retired = ko('몹　사령관')
        rom[0x100:0x100 + len(old)] = old
        rom[0x200:0x200 + len(new)] = new
        rom[0x300:0x300 + len(retired)] = retired
        rom[0x10:0x14] = (0x08000000 + pointer).to_bytes(4, 'little')
        inline = ko('캣님') + b'w' + ko('좋아') + b'k\0'
        rom[self.SCRIPT_ROW:self.SCRIPT_ROW + len(inline)] = inline
        ui = ko('모프')
        rom[0x380:0x380 + len(ui)] = ui
        writes = [
            [0x100, len(old), len(old), old.hex(), None, '몹님', 0, 'import-csv'],
            [0x300, len(retired), len(retired), retired.hex(), None, '몹 사령관', 0, 'dialogue-spacing-final'],
            [0x300, len(retired), len(retired), retired.hex(), None, None, None,
             'dialogue-rewrite-retired-allocation'],
            [0x200, len(new), len(new), new.hex(), None, None, None, 'dialogue-rewrite-final'],
            [0x10, 4, 4, rom[0x10:0x14].hex(), None, None, None, 'dialogue-rewrite-pointer'],
            [self.SCRIPT_ROW, len(inline), len(inline), inline.hex(), None, '캣님 좋아', 0, 'import-csv'],
            [0x380, len(ui), len(ui), ui.hex(), None, '모프', 0, 'import-csv'],
        ]
        manifest = [{'msg': '0x000100', 'status': 'relocated', 'old_len': len(old) + 1,
                     'new_addr': '0x000200', 'new_len': len(new), 'ptr_off': '0x000010',
                     'ptr_sites': ['0x000010']}]
        paths = [Path(folder) / n for n in ('rom.gba', 'map.json', 'manifest.json')]
        paths[0].write_bytes(rom)
        paths[1].write_text(json.dumps(writes))
        paths[2].write_text(json.dumps(manifest))
        return [str(p) for p in paths]

    def test_only_active_text_is_scanned(self):
        codes = T.load_code2syl()
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            active, stats = T.load_active(codes, *self.build(tmp))
        texts = {addr: row['ko'] for addr, row in active.items()}
        self.assertEqual(texts, {0x200: '모프님', self.SCRIPT_ROW: '캣님좋아 ', 0x380: '모프'})
        self.assertEqual(active[0x200]['source'], 0x100)
        self.assertEqual((stats['relocated'], stats['inplace'], stats['retired_rows']), (1, 2, 1))
        self.assertFalse(any(T.name_occurrences(t, '몹') for t in texts.values()))

    def test_stale_pointer_is_a_hard_error(self):
        codes = T.load_code2syl()
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            with self.assertRaisesRegex(ValueError, 'does not reach'):
                T.load_active(codes, *self.build(tmp, pointer=0x100))

    def test_candidate_has_no_forbidden_active_names(self):
        paths = [os.environ.get(k) for k in ('AW_TEST_ROM', 'AW_TEST_MAP', 'AW_TEST_MANIFEST')]
        if not all(paths) or not all(Path(p).is_file() for p in paths):
            self.skipTest('matching candidate ROM/map/manifest required')
        codes = T.load_code2syl()
        active, _ = T.load_active(codes, *paths)
        hits = [(hex(a), forbidden, row['ko'][:40]) for forbidden, _canon, label in T.build_forbidden()
                if '[SUBSTR-AMBIG]' not in label
                for a, row in active.items() if T.name_occurrences(row['ko'], forbidden)]
        self.assertEqual(hits, [])


if __name__ == '__main__':
    unittest.main()
