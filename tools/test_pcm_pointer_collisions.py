"""Local original ROM required; no source ROM data is stored as test fixtures."""
import collections
from hashlib import sha256
import json
from pathlib import Path
import struct
import unittest

import build_korean_full as builder
from dialogue_repoint import repoint_messages
import pcm_pointer_collisions as pcm

ROOT = Path(__file__).resolve().parents[1]


class PcmPointerCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        if sha256(cls.original).hexdigest() != pcm.SOURCE_SHA256:
            raise AssertionError('PCM regression requires canonical local original ROM')
        cls.sites = sorted(pcm.SITES | {pcm.REAL_SITE})
        mapping = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())
        cls.mapping = {s: int(code, 16) for s, code in mapping.items()}
        cls.full_source = json.loads((ROOT / 'data/dialogue_overrides.json').read_text())['0x00DCE8F2']
        unknown = collections.Counter()
        cls.payload = builder.encode_full_fidelity(cls.full_source, cls.mapping, unknown, 0xDCE8F2)
        if unknown:
            raise AssertionError(unknown)

    def classify(self, current, sites=None, message=pcm.TARGET, original=None):
        return pcm.classify_pointer_sites(message, self.sites if sites is None else sites,
                                         self.original if original is None else original, current)

    def test_exact_three_pairs_only_and_no_mutation(self):
        current = bytearray(self.original)
        before = sha256(current).hexdigest()
        kept, evidence = self.classify(current)
        self.assertEqual(kept, [pcm.REAL_SITE])
        self.assertEqual(evidence['excluded_sites'], ['0x1202F0', '0x6A3A68', '0xCFDAD0'])
        self.assertEqual(sha256(current).hexdigest(), before)
        self.assertEqual(self.classify(current, sites=self.sites + [0x1234])[0], [pcm.REAL_SITE, 0x1234])
        self.assertEqual(self.classify(current, message=pcm.TARGET + 4), (self.sites, None))
        self.assertEqual(self.classify(current, sites=[pcm.REAL_SITE]), ([pcm.REAL_SITE], None))

    def test_source_revision_and_size_fail_closed(self):
        changed = bytearray(self.original)
        changed[0] ^= 1
        for source, current in ((changed, self.original), (b'', self.original),
                                (self.original, self.original[:-1])):
            with self.subTest(length=len(source)):
                kept, evidence = self.classify(current, original=source)
                self.assertEqual(kept, self.sites)
                self.assertEqual(evidence['status'], 'guard_rejected')
                self.assertEqual(evidence['excluded_sites'], [])

    def test_every_current_evidence_link_fails_closed(self):
        addresses = [pcm.REAL_SITE - 4, pcm.REAL_SITE]
        for header, site, bank, table, song, track, commands, handler in pcm.CASES:
            addresses.extend([header, header + 12, header + 16, header + 15 + pcm.SAMPLE_SIZE, site, bank + 107 * 12,
                              bank + 107 * 12 + 4, table + 209 * 8,
                              song, song + 4, song + 16, track, track + 3,
                              commands + (0xBD - 0xB1) * 4, handler])
        # Includes branches and code well outside the earlier four small anchors.
        addresses.extend(start + 2 for start, _, _ in pcm.CONSUMERS)
        addresses.extend(end - 1 for _, end, _ in pcm.CONSUMERS)
        for address in addresses:
            with self.subTest(address=hex(address)):
                changed = bytearray(self.original)
                changed[address] ^= 1
                kept, evidence = self.classify(changed)
                self.assertEqual(kept, self.sites)
                self.assertEqual(evidence['status'], 'guard_rejected')
                self.assertEqual(evidence['excluded_sites'], [])

    def repoint(self, current, original=None):
        return repoint_messages(
            current, self.original if original is None else original, fixable=lambda a: a == 0xDCE8F2,
            fixed_bytes=lambda a: self.payload, fit_level_dlg=lambda a: 6,
            decode_text=lambda raw: raw.hex(), cell_width=lambda a: len(self.payload),
            slots={}, line_index={a: (n, '') for a, n in
                                  ((0xDCE8F2, 32), (0xDCE915, 14), (0xDCE928, 38), (0xDCE951, 26))},
            table_offsets=[], extra_messages={pcm.TARGET: [pcm.REAL_SITE]},
            free_start=0xA3D000, free_end=0xA3D100)

    def test_actual_relocation_restores_full_source_controls_and_samples(self):
        self.assertEqual(self.full_source, '・・・하지만 아직　의심하지 않는 건')
        self.assertEqual(len(self.payload), 38)
        self.assertEqual(self.payload[:6], b'\x81\x45' * 3)
        current = bytearray(self.original)
        manifest, stats = self.repoint(current)
        self.assertEqual(stats['relocated'], 1)
        self.assertEqual(stats['pcm_collision_sites_excluded'], 3)
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]['pointer_classification']['status'], 'classified')
        relocated = struct.unpack_from('<I', current, pcm.REAL_SITE)[0] - pcm.GBA
        self.assertEqual(relocated, 0xA3D000)
        expected = (self.original[pcm.TARGET:0xDCE8F2] + self.payload
                    + self.original[0xDCE912:0xDCE970])
        self.assertEqual(current[relocated:relocated + len(expected)], expected)
        # Complete ROM equality outside the allocated message and real typed pointer.
        restored = bytearray(current)
        restored[relocated:relocated + len(expected)] = self.original[relocated:relocated + len(expected)]
        restored[pcm.REAL_SITE:pcm.REAL_SITE + 4] = self.original[pcm.REAL_SITE:pcm.REAL_SITE + 4]
        self.assertEqual(restored, self.original)
        for header, *_ in pcm.CASES:
            self.assertEqual(sha256(current[header + 16:header + 16 + pcm.SAMPLE_SIZE]).hexdigest(), pcm.SAMPLE_SHA256)

    def test_current_translated_siblings_are_preserved(self):
        current = bytearray(self.original)
        replacements = ((0xDCE915, 14, '남아 있어.'), (0xDCE928, 38, '진짜 네가 했다면 료!'),
                        (0xDCE951, 26, '그땐 각오해 둬!'))
        for address, size, text in replacements:
            payload = builder.encode_full_fidelity(text, self.mapping, collections.Counter(), address)
            self.assertLessEqual(len(payload), size)
            current[address:address + size] = payload + b' ' * (size - len(payload))
        before = bytes(current)
        manifest, stats = self.repoint(current)
        self.assertEqual(stats['relocated'], 1)
        expected = before[pcm.TARGET:0xDCE8F2] + self.payload + before[0xDCE912:0xDCE970]
        self.assertEqual(current[0xA3D000:0xA3D000 + len(expected)], expected)
        self.assertEqual(current[pcm.TARGET:0xDCE970], before[pcm.TARGET:0xDCE970])

    def test_new_unknown_original_hit_keeps_existing_skip(self):
        changed = bytearray(self.original)
        unknown = 0xA3D200
        struct.pack_into('<I', changed, unknown, pcm.GBA + pcm.TARGET)
        current = bytearray(changed)
        before = bytes(current)
        manifest, stats = self.repoint(current, original=changed)
        self.assertEqual(stats['skip_ptr_ambiguous'], 1)
        self.assertEqual(set(manifest[0]['sites']), {hex(s) for s in self.sites + [unknown]})
        self.assertEqual(manifest[0]['pointer_classification']['reason'], 'original_revision')
        self.assertEqual(current, before)

    def test_new_current_reference_keeps_existing_skip(self):
        current = bytearray(self.original)
        struct.pack_into('<I', current, 0xA3D200, pcm.GBA + pcm.TARGET)
        before = bytes(current)
        manifest, stats = self.repoint(current)
        self.assertEqual(stats['skip_ptr_ambiguous'], 1)
        self.assertIn('unrecognized_reference_A3D200', manifest[0]['pointer_classification']['reason'])
        self.assertEqual(current, before)

    def test_consumer_tamper_retains_skip_guard_without_writes(self):
        current = bytearray(self.original)
        current[pcm.CONSUMERS[0][0] + 2] ^= 1
        before = bytes(current)
        manifest, stats = self.repoint(current)
        self.assertEqual(stats['skip_ptr_ambiguous'], 1)
        self.assertEqual(stats['pcm_collision_guard_rejected'], 1)
        self.assertEqual(stats['pcm_collision_sites_excluded'], 0)
        self.assertEqual(manifest[0]['sites'], [hex(s) for s in self.sites])
        self.assertEqual(current, before)


if __name__ == '__main__':
    unittest.main()
