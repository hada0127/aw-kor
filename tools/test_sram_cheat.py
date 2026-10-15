import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import sram_cheat as C


class SRAMCheatTests(unittest.TestCase):
    def setUp(self):
        self.p1 = C.ROOT / 'temp/release_C/work/b28_saves/S80bc_m16/game.sav'
        self.m8 = C.ROOT / 'temp/continuation_2026-09-30/m8_worldmap_save/game.sav'
        self.later = C.ROOT / 'temp/release_C/work/w2b4/saves/anchor_run16.sav'

    def test_checksum_matches_real_part1_and_part2_blocks(self):
        for part, path in [('p1', self.p1), ('p2', self.m8), ('p2', self.later)]:
            data = path.read_bytes()
            base = C.newest_block(data, part)
            self.assertTrue(C.valid_block(data[base:base + C.BLOCK_SIZE], C.PARTS[part][2]))

    def test_m8_to_later_known_candidate_progress_bytes(self):
        source, donor = self.m8.read_bytes(), self.later.read_bytes()
        a, b = C.newest_block(source, 'p2'), C.newest_block(donor, 'p2')
        # The range has a candidate mission ID plus the observed cleared-map
        # vector. Equality here proves byte editing/checksum, not game meaning.
        edits = [(offset, donor[b + offset]) for offset in range(0x52e, 0x560)
                 if source[a + offset] != donor[b + offset]]
        result, base, old_checksum, changes = C.mutate(source, 'p2', edits)
        self.assertEqual(base, a)
        self.assertNotEqual(old_checksum, result[base + 6])
        self.assertEqual(result[a + 0x52e:a + 0x560], donor[b + 0x52e:b + 0x560])
        self.assertEqual(len(changes), len(edits))
        self.assertTrue(C.valid_block(result[a:a + C.BLOCK_SIZE], b'2ars'))
        self.assertEqual(source, self.m8.read_bytes())

    def test_receipt_and_output_are_tainted_and_source_is_immutable(self):
        source = self.m8.read_bytes()
        with tempfile.TemporaryDirectory(dir=C.ROOT / 'temp') as directory:
            out = Path(directory) / 'candidate.sav'
            receipt_path = C.make_save(self.m8, out, 'p2', ['0x52e=0x1b'], hashlib.sha256(source).hexdigest())
            receipt = json.loads(receipt_path.read_text())
            self.assertTrue(receipt['cheat_tainted'])
            self.assertEqual(receipt['provenance_class'], 'legacy_unverified_sram')
            self.assertEqual(receipt['source_sha256'], hashlib.sha256(source).hexdigest())
            self.assertEqual(receipt['result_sha256'], hashlib.sha256(out.read_bytes()).hexdigest())
            self.assertEqual(self.m8.read_bytes(), source)
            with self.assertRaises(FileExistsError):
                C.make_save(self.m8, out, 'p2', ['0x52e=0x1b'], hashlib.sha256(source).hexdigest())

    def test_rejects_bad_hash_header_and_ambiguous_edits(self):
        source = self.m8.read_bytes()
        with self.assertRaises(ValueError):
            C.mutate(source, 'p2', [(6, 1)])
        with self.assertRaises(ValueError):
            C.mutate(source, 'p2', [(0xfff, 1)])
        with self.assertRaises(ValueError):
            C.mutate(source, 'p2', [(0x52e, 1), (0x52e, 2)])
        damaged = bytearray(source)
        damaged[C.newest_block(source, 'p2') + 0x52e] ^= 1
        with self.assertRaises(ValueError):
            C.newest_block(damaged, 'p2')
        with tempfile.TemporaryDirectory(dir=C.ROOT / 'temp') as directory:
            with self.assertRaises(ValueError):
                C.make_save(self.m8, Path(directory) / 'bad.sav', 'p2', ['0x52e=0x1b'], '0' * 64)

    def test_newest_block_uses_full_counter_after_low_byte_wrap(self):
        data = bytearray(self.m8.read_bytes())
        for base, counter in [(0x10000, 0xff), (0x11000, 0x100)]:
            data[base + 8:base + 12] = counter.to_bytes(4, 'little')
            data[base + 6] = C.checksum(data[base:base + C.BLOCK_SIZE])
            data[base + 7] = data[base + 6] ^ 0xff
        self.assertEqual(C.newest_block(data, 'p2'), 0x11000)


if __name__ == '__main__':
    unittest.main()
