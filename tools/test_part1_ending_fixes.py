"""Regression tests for the 2026-10-07 Part 1 ending fixes (record screen, HUD labels, Hellbowz line)."""
import collections
import json
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_korean_full as builder
import part1_record_screen as record
import part1_terrain_hud_labels as hud
import part1_hellbowz_ending as hellbowz

ORIG = Path(builder.P.ROM).read_bytes()


def tile_pixels(buf, t):
    return [[record._get(buf, t, x, y) for x in range(8)] for y in range(8)]


class RecordScreenTests(unittest.TestCase):
    def test_patch_touches_only_title_and_small_glyph_tiles(self):
        rom = bytearray(ORIG)
        changed = record.patch(rom, ORIG)
        self.assertGreater(changed, 0)
        sheet = rom[record.SHEET:record.SHEET + record.TILES * 32]
        source = ORIG[record.SHEET:record.SHEET + record.TILES * 32]
        allowed = set(range(64, 96)) | {37, 38, 39, 40, 41, 53, 54, 55, 56, 57}
        for t in range(record.TILES):
            if t not in allowed:
                self.assertEqual(sheet[t * 32:(t + 1) * 32], source[t * 32:(t + 1) * 32], t)
        # Digits / rank letters stay native; nothing outside the sheet moved.
        self.assertEqual(rom[:record.SHEET], bytearray(ORIG[:record.SHEET]))
        self.assertEqual(rom[record.SHEET + record.TILES * 32:], bytearray(ORIG[record.SHEET + record.TILES * 32:]))
        with self.assertRaises(AssertionError):
            record.patch(rom, ORIG)          # second writer refused

    def test_title_uses_native_outline_and_bands(self):
        rom = bytearray(ORIG)
        record.patch(rom, ORIG)
        sheet = rom[record.SHEET:record.SHEET + record.TILES * 32]
        values = collections.Counter(record._get(sheet, t, x, y) for t in range(64, 96)
                                     for y in range(8) for x in range(8))
        self.assertTrue(set(values) <= {0, 14, 1, 2, 3, 4, 5, 6, 7, 8, 9})
        self.assertGreater(values[14], 100)

    def test_small_glyphs_come_from_the_syllable_blob(self):
        rom = bytearray(ORIG)
        record.patch(rom, ORIG)
        sheet = rom[record.SHEET:record.SHEET + record.TILES * 32]
        for ch, top in record.SMALL:
            a, b = record.small_glyph_tiles(ch)
            self.assertEqual(bytes(sheet[top * 32:(top + 1) * 32]), a, ch)
            self.assertEqual(bytes(sheet[(top + 16) * 32:(top + 17) * 32]), b, ch)
        self.assertEqual(record.small_glyph_tiles(None), (bytes(32), bytes(32)))

    def test_loader_literal_is_the_only_reference(self):
        ref = struct.pack('<I', 0x08000000 + record.SHEET)
        self.assertEqual(ORIG.count(ref), 1)
        self.assertEqual(ORIG.index(ref), record.LOADER_LITERAL)


class TerrainHudTests(unittest.TestCase):
    def test_defense_and_durability_labels(self):
        rom = bytearray(ORIG)
        self.assertEqual(hud.patch(rom, ORIG), 2)
        self.assertEqual([ch for _, ch, _ in hud.LABELS], ['방', '내'])
        for off, _, _ in hud.LABELS:
            block = rom[off:off + 128]
            self.assertNotEqual(block, ORIG[off:off + 128])
            values = {(b >> s) & 15 for b in block for s in (0, 4)}
            self.assertEqual(values, {0, 1, 15})
        changed = [i for i in range(len(rom)) if rom[i] != ORIG[i]]
        self.assertTrue(all(any(off <= i < off + 128 for off, _, _ in hud.LABELS) for i in changed))

    def test_build_no_longer_writes_yuk_over_defense(self):
        source = Path(builder.__file__).read_text(encoding='utf-8')
        self.assertNotIn("write_tiles(0xB93BD0, render_tiles('육'", source)


class HellbowzTests(unittest.TestCase):
    def test_rows_keep_approved_wording_and_fit(self):
        overrides = json.loads(Path(builder.BASE, 'data', 'dialogue_overrides.json').read_text(encoding='utf-8'))
        self.assertEqual(overrides['0x00DD0BCB'], hellbowz.TEXT)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        encode = lambda text, address: builder.encode_required_full_fidelity(text, codes, collections.Counter(), address)
        rows = hellbowz.layout(ORIG, encode)[hellbowz.ADDRESS]
        self.assertEqual(b'\x81\x40'.join(rows), encode(hellbowz.TEXT, hellbowz.ADDRESS))
        self.assertIn(hellbowz.ADDRESS, builder.PLAYTHROUGH_REPAIR_ROWS)

    def test_pointer_guard(self):
        bad = bytearray(ORIG)
        bad[hellbowz.POINTER - 4] = 0x18
        with self.assertRaises(ValueError):
            hellbowz.source_guard(bytes(bad))


class ApprovedBteamExceptionTests(unittest.TestCase):
    def setUp(self):
        import qa_bteam_drift as drift
        self.drift = drift
        self.base = json.loads(Path(builder.BASE, 'data', 'bteam_baseline.json').read_text(encoding='utf-8'))
        self.overrides = drift.load_overrides()

    def test_dd0d1a_user_approved_exception_is_consistent(self):
        exc = self.base['_user_approved_exceptions']['0x00DD0D1A']
        self.assertEqual((exc['from'], exc['to']), self.drift.APPROVED_EXCEPTIONS['0x00DD0D1A'])
        self.assertIn('제안대로', exc['approved'])
        self.assertEqual(self.overrides['0x00DD0D1A'], exc['to'])
        bteam = json.loads(Path(builder.BASE, 'data', 'bteam_addresses.json').read_text())
        self.assertIn('0x00DD0D1A', json.dumps(bteam))          # still a protected address
        self.assertEqual(self.drift.check(self.base, self.overrides)['errors'], [])

    def test_unrelated_baseline_change_alongside_exception_fails(self):
        import copy
        base = copy.deepcopy(self.base)
        other = next(a for a in base['overrides'] if a != '0x00DD0D1A')
        base['overrides'][other] += ' (edited)'
        errors = self.drift.check(base, self.overrides)['errors']
        self.assertTrue(any('core digest' in e for e in errors), errors)

    def test_exception_tuple_cannot_be_widened_or_edited(self):
        import copy
        for mutate in (lambda b: b['_user_approved_exceptions']['0x00DD0D1A'].update(to='다른 문구'),
                       lambda b: b['_user_approved_exceptions'].update({'0x00DD0B32': {
                           'from': 'x', 'to': 'y', 'approved': 'no'}})):
            base = copy.deepcopy(self.base)
            mutate(base)
            self.assertTrue(self.drift.check(base, self.overrides)['errors'])
        overrides = dict(self.overrides, **{'0x00DD0D1A': '다른 문구'})
        self.assertTrue(self.drift.check(self.base, overrides)['errors'])

    def test_accept_refuses_changes_outside_the_exception(self):
        other = next(a for a in self.base['overrides'] if a != '0x00DD0D1A')
        overrides = dict(self.overrides, **{other: self.overrides.get(other, '') + ' (edited)'})
        with self.assertRaisesRegex(ValueError, 'outside the approved exceptions'):
            self.drift.accept(self.base, overrides)
        widened = self.drift.accept(self.base, overrides, allow_bteam_changes=True)
        # Even with the explicit flag the pinned digest keeps the gate failing until reviewed.
        self.assertTrue(self.drift.check(widened, overrides)['errors'])


class HellbowzVerifyTests(unittest.TestCase):
    def setUp(self):
        candidate = Path(builder.BASE, 'output', 'game_wars_korean_candidate_5bb5c941.gba')
        if not candidate.exists():
            self.skipTest('candidate ROM not present')
        self.rom = bytearray(candidate.read_bytes())
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        self.encode = lambda text, address: builder.encode_required_full_fidelity(
            text, codes, collections.Counter(), address)
        target = struct.unpack_from('<I', self.rom, hellbowz.POINTER)[0] - 0x08000000
        self.target = target
        payload = bytes(self.rom[target:self.rom.index(b'\0', target) + 1])
        # Contract taken from the candidate itself (rows as relocated, NUL gap).
        self.expected = (('row', (payload[:-1],)), ('gap', b'\0'))

    def test_candidate_passes_and_mutations_fail(self):
        self.assertEqual(hellbowz.verify(self.rom, ORIG, self.expected, self.encode)['status'], 'PASS')
        mutations = {
            'opcode': lambda r: r.__setitem__(hellbowz.POINTER - 4, 0x18),
            'unaligned': lambda r: struct.pack_into('<I', r, hellbowz.POINTER, 0x08000000 + self.target + 2),
            'original': lambda r: struct.pack_into('<I', r, hellbowz.POINTER, 0x08000000 + hellbowz.START),
            'out_of_bounds': lambda r: struct.pack_into('<I', r, hellbowz.POINTER, 0x08000000 + 0xA00000),
            'neighbor_text': lambda r: r.__setitem__(self.target + 4, r[self.target + 4] ^ 1),
        }
        for name, mutate in mutations.items():
            rom = bytearray(self.rom)
            mutate(rom)
            with self.subTest(name), self.assertRaises(ValueError):
                hellbowz.verify(rom, ORIG, self.expected, self.encode)


if __name__ == '__main__':
    unittest.main()
