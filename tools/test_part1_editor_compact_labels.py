import hashlib
import struct
import unittest

import part1_editor_compact_labels as editor
import part1_record_map_labels as record

POOL = 0x03000E00
END = 0x03001D00
SOURCE = 0x08D82474
DEST = 0x02012D44
CELL = 0x02012E0A
PARENT = (0x03000F20, 0x03000EC0, 0x030010A0,
          0x03001040, 0x03001220, 0x03001280)
# The prototype's exact lookup has 18 editor keys; a range hit alone is insufficient.
KEYS = (0x4C, 0x4E, 0x58, 0x5A, 0x5C, 0x64, 0x66, 0x74, 0x76,
        0x84, 0x86, 0x88, 0x92, 0x94, 0x98, 0x9E, 0xAA, 0xAC)
KEYS = {0x08D82400 + offset for offset in KEYS}


def predicate(p, source, owner=0, dst=DEST, post=None):
    # Mirrors the assembled predicate's ordered comparisons. Do not dereference
    # the synthetic slot until the range and stride checks have passed.
    delta = (p - POOL) & 0xFFFFFFFF
    if delta >= 0xF00 or delta % 0x60:
        return False
    return (owner == 0 and dst == DEST and
            0x08D8244C <= source < 0x08D824AE and
            (source + 2 if post is None else post) == source + 2)


def consume(p, source, cell, column, **fields):
    if not predicate(p, source, **fields) or source not in KEYS:
        return None
    delta_source = source - 0x08D8244C
    shift = (0 if delta_source in (0x10, 0x3C) else
             8 if delta_source in (0x0C, 0x38) else
             4 if delta_source < 0x3E or 0x4C <= delta_source < 0x50 else 0)
    cell += shift
    delta = (cell - CELL) & 0xFFFFFFFF
    if source < 0x08D82474:
        delta = (delta - 0x40) & 0xFFFFFFFF
    row = delta >> 7
    if row >= 5 or not 2 <= column < 8 or (delta & 0x7F) != 2 * column:
        return None
    return 0xD8 + row * 8 + column


class EditorCompactGateTests(unittest.TestCase):
    def setUp(self):
        size = max(editor.CODE_OFFSET + len(editor.CODE),
                   max(editor.REPLACES) + 4,
                   max(address + len(payload) for address, payload in record.WRITES))
        original = bytearray(size)
        original[editor.RETURN_SITE:editor.RETURN_SITE + 22] = editor.RETURN_OLD
        self.original = bytes(original)
        self.rom = bytearray(self.original)
        for address, (old, _) in editor.REPLACES.items():
            struct.pack_into('<I', self.rom, address, old)
        struct.pack_into('<I', self.rom, editor.LEGACY_ROW_SITE, editor.LEGACY_ROW_TARGET)
        struct.pack_into('<I', self.rom, editor.LEGACY_LOOKUP_LITERAL,
                         editor.LEGACY_LOOKUP_TARGET)

    def test_payload_matches_linked_editor_gate(self):
        self.assertEqual(len(editor.CODE), 236)
        self.assertEqual(hashlib.sha256(editor.CODE).hexdigest(),
                         '9d9662da832257e0b14528f25566ae7a9d846b4d11cb2b7b2bfd800fcd11cc80')
        self.assertIn(struct.pack('<I', 0x08D8244C), editor.CODE)
        self.assertIn(struct.pack('<I', 0x02012E0A), editor.CODE)
        # Thumb-1 B at 08F31E9E must reach the old native row fallback.
        self.assertEqual(struct.unpack_from('<H', editor.CODE, 0x9E)[0], 0xE08F)
        self.assertEqual(0x08F31EA2 + ((0xE08F & 0x7FF) << 1),
                         0x08F31FC0)

    def test_patch_is_guarded_confined_and_final_checked(self):
        before = bytes(self.rom)
        editor.patch(self.rom, self.original)
        editor.verify(self.rom)
        allowed = set(range(editor.CODE_OFFSET, editor.CODE_OFFSET + len(editor.CODE)))
        for address in editor.REPLACES:
            allowed.update(range(address, address + 4))
        self.assertTrue(all(a == b or index in allowed
                            for index, (a, b) in enumerate(zip(before, self.rom))))
        for at in (editor.CODE_OFFSET, editor.RETURN_SITE,
                   editor.LEGACY_LOOKUP_LITERAL, *editor.REPLACES):
            self.rom[at] ^= 1
            with self.assertRaisesRegex(AssertionError, 'overwritten'):
                editor.verify(self.rom)
            self.rom[at] ^= 1

    def test_atomic_failures(self):
        for kind in ('occupied', 'predecessor', 'legacy', 'lookup', 'return', 'original', 'truncated', 'reinstall'):
            with self.subTest(kind=kind):
                rom = bytearray(self.rom)
                original = self.original
                if kind == 'occupied':
                    rom[editor.CODE_OFFSET + 1] = 1
                elif kind == 'predecessor':
                    rom[next(iter(editor.REPLACES))] ^= 1
                elif kind == 'legacy':
                    rom[editor.LEGACY_ROW_SITE] ^= 1
                elif kind == 'lookup':
                    rom[editor.LEGACY_LOOKUP_LITERAL] ^= 1
                elif kind == 'return':
                    rom[editor.RETURN_SITE] ^= 1
                elif kind == 'original':
                    original = bytearray(original)
                    original[editor.CODE_OFFSET] = 1
                elif kind == 'truncated':
                    rom = rom[:-1]
                elif kind == 'reinstall':
                    editor.patch(rom, original)
                before = bytes(rom)
                with self.assertRaises(AssertionError):
                    editor.patch(rom, original)
                self.assertEqual(bytes(rom), before)

    def test_record_overlay_contract(self):
        for address, payload in record.WRITES:
            self.rom[address:address + len(payload)] = payload
        editor.patch(self.rom, self.original)
        overlays = {address: struct.pack('<I', target)
                    for address, (_, target) in editor.REPLACES.items()}
        record.verify(self.rom, overlays)
        self.assertEqual(struct.unpack_from('<I', self.rom, 0xF31FE4)[0], 0x08F307A9)
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            record.verify(self.rom)

    def test_all_slots_parent_states_and_exact_lookup(self):
        for i in range(40):
            p = POOL + i * 0x60
            self.assertEqual(consume(p, SOURCE, CELL, 2), 0xDA)
        for p in PARENT:
            self.assertEqual(consume(p, SOURCE, CELL, 2), 0xDA)
        self.assertEqual(consume(0x03000F80, SOURCE, CELL, 2), 0xDA)
        self.assertEqual(consume(0x03000FE0, SOURCE, CELL, 2), 0xDA)
        for key in KEYS:
            delta = key - 0x08D8244C
            cell = CELL + (0x44 if delta == 0x10 else
                           0x40 if delta < 0x28 else
                           4 if delta == 0x3C else
                           0 if delta < 0x3E or 0x4C <= delta < 0x50 else 4)
            column = 4 if delta in (0x0C, 0x38) else 2
            self.assertEqual(consume(POOL, key, cell, column), 0xD8 + column)
        self.assertIsNone(consume(POOL, 0x08D82472, CELL, 0))
        self.assertIsNone(consume(POOL, 0x08D824A8, CELL, 0))

    def test_no_out_of_pool_dereference_and_single_field_rejections(self):
        for p in (POOL - 0x60, POOL - 1, END, END + 0x60,
                  POOL + 1, POOL + 0x20, POOL + 0x40,
                  0x03000DA0, 0x02000E00, 0xFFFFFFFF):
            self.assertFalse(predicate(p, SOURCE))
        for fields in ({'owner': 1}, {'dst': DEST + 2}, {'dst': 0x02022D44},
                       {'post': SOURCE}, {'post': SOURCE + 4}):
            self.assertIsNone(consume(POOL, SOURCE, CELL, 0, **fields))
        for source in (0x08D8244B, 0x08D824AE, 0x08D824A5):
            self.assertIsNone(consume(POOL, source, CELL, 0))
        self.assertTrue(predicate(END - 0x60, 0x08D824AC))

    def test_rows_columns_underflow_and_shift_once(self):
        for row in (0, 4):
            for col in (2, 7):
                self.assertEqual(consume(POOL, SOURCE, CELL + row * 0x80 + (col-2) * 2, col),
                                 0xD8 + row * 8 + col)
        for cell, col in ((CELL - 2, 1), (CELL + 5 * 0x80, 2),
                          (CELL + 16, 8), (CELL + 1, 0),
                          (CELL + 0x40, 0), (CELL + 2, 0),
                          (0x02022E0A, 0)):
            self.assertIsNone(consume(POOL, SOURCE, cell, col))
        self.assertIsNone(consume(POOL, 0x08D8244C, CELL, 2))
        self.assertEqual(consume(POOL, 0x08D8244C, CELL + 0x40, 2), 0xDA)
        self.assertIsNone(consume(POOL, SOURCE, CELL + 0x40, 2))
        self.assertEqual(consume(POOL, 0x08D82498, CELL, 2), 0xDA)
        self.assertIsNone(consume(POOL, 0x08D82498, CELL, 0))
        self.assertEqual(consume(POOL, 0x08D82484, CELL, 4), 0xDC)
        self.assertEqual(consume(POOL, 0x08D82488, CELL + 4, 2), 0xDA)
        self.assertEqual(consume(POOL, 0x08D82458, CELL + 0x40, 4), 0xDC)
        self.assertEqual(consume(POOL, 0x08D8245C, CELL + 0x44, 2), 0xDA)


if __name__ == '__main__':
    unittest.main()
