"""Static checks for the Part 2 battle-start day OBJ replacement."""

import unittest
import hashlib
from pathlib import Path

from build_korean_full import patch_part2_battle_start_day_overlay_obj
from lz77_scan import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = {
    0x45EC74: (9216, range(10, 18)),
    0x92DF84: (7168, range(10, 14)),
    0x966C0C: (7168, range(10, 14)),
    0x99F4B0: (7168, range(10, 14)),
    0x9D7D54: (7168, range(10, 14)),
    0x92EB5C: (1024, range(0, 2)),
    0x9677E4: (1024, range(0, 2)),
    0x9A0088: (1024, range(0, 2)),
    0x9D892C: (1024, range(0, 2)),
}
CELL_HASHES = {
    '일': '94a98d9c0712164cca1a683bae3cf0649a3fc708716857f17fa3d2157002e3d4',
    '째': '1cca0ce9ea7ef23e693770265a5eabc211e397866556735935c92da850bebf0b',
    '작': '2749f627da1684849a262b6a7f0deb7e59f1c1dec9b03c1a9c11e2a2a2292634',
    '전': 'a4ccfe878d1fe54f85b85ac1c59924f5473f488dea916e94c0d9249e206dbec7',
    '개': '4484d871ddc7b0759fd0ce6c9623af4d9ec2b2e67feae6866f6d242fa369cfa5',
    '시': 'ff798cff79c35262e72a751f3e18b8d5a64b5dd0d6ecfb8169363ee25601a616',
    '실': 'a4fc0b6ee6ffe560cf3575706d317f3c524a86ef57e684da4b7b396d00342c54',
    '패': 'aed324f484dd0715dba934cf411165aff6b62e87f96c3db854d92f29c0982a84',
}
FIXB_CORE_SHA = {
    '일': 'a1e85314b81ec2becc5d137a4f50cc03bc47d1654a87c0f34e93798574749043',
    '째': '2a939ea15ffab053dd8618ea673211d5eed71c25977263f1865c683fcba460e5',
    '작': '2a6159f8c101390f2a918316d91019df03646183c0ebe8b748d7df69878db7aa',
    '전': 'a4e58a0275190f95ed26c622ee98bb2662725425e7dbdb52a401bd951a094708',
    '개': '140915559c18493244c8bc974989224b42cbf1cab9ebb07680c7bf9b0e333e8e',
    '시': 'cf668318d429410ade9d8f19093eb5dbdbb91f3ee13c8449a1b07bca9067a005',
    '실': '050df728cd0dcaaf4316092dcaa8e53c7e5a51c610ae0a197c55f35e80ecd2cb',
    '패': '7ebd423aee1422a5891a703cfe40514c9e29324ca3785facdd833532570a000c',
}
LABELS = {0x45EC74: '일째작전개시실패',
          **{off: '일째개시' for off in (0x92DF84, 0x966C0C, 0x99F4B0, 0x9D7D54)},
          **{off: '작전' for off in (0x92EB5C, 0x9677E4, 0x9A0088, 0x9D892C)}}


def validate_cell(cell, ch):
    """Pin the committed Hada Bold layout, face size, and palette per cell."""
    if hashlib.sha256(cell).hexdigest() != CELL_HASHES[ch]:
        raise AssertionError(f'wrong rendered cell: {ch}')
    pixels = []
    for y in range(32):
        for x in range(32):
            pos = ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            pixels.append((x, y, cell[pos] >> (4 * (x % 2)) & 15))
    if {v for _, _, v in pixels} != {0, 6, 9, 11, 13, 15}:
        raise AssertionError(f'wrong palette: {ch}')
    face = [(x, y) for x, y, v in pixels if v == 15]
    box = (min(x for x, _ in face), min(y for _, y in face),
           max(x for x, _ in face) + 1, max(y for _, y in face) + 1)
    if not (2 <= box[0] <= 3 and box[1] == 3 and 27 <= box[2] <= 28 and box[3] == 28):
        raise AssertionError(f'face outside JP cell ink range: {ch}: {box}')


class BattleDayBannerTest(unittest.TestCase):
    def test_replacement_tiles_and_native_digits(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        patched = bytearray(original)
        self.assertEqual(patch_part2_battle_start_day_overlay_obj(patched), 512)
        for off, (expected_size, chunks) in BLOCKS.items():
            before, consumed = lz77_decompress(original, off)
            after, used = lz77_decompress(patched, off)
            self.assertEqual(len(after), expected_size, hex(off))
            self.assertLessEqual(used, consumed, hex(off))
            if expected_size > 1024:
                self.assertEqual(after[:10 * 512], before[:10 * 512], hex(off))
            for chunk in chunks:
                cell = after[chunk * 512:(chunk + 1) * 512]
                # AA changes edge shades only. The b29r2 white binary core,
                # which carries the glyph's counter/gaps, equals fixB (0983d1eb)
                # (core-mask digests taken from that ROM; no output/ dependency).
                core = bytes((b >> shift) & 15 == 15 for b in cell for shift in (0, 4))
                self.assertEqual(hashlib.sha256(core).hexdigest(),
                                 FIXB_CORE_SHA[LABELS[off][chunk - chunks.start]], (hex(off), chunk))
                self.assertTrue(any(cell), (hex(off), chunk))
                self.assertNotEqual(cell, before[chunk * 512:(chunk + 1) * 512])
                validate_cell(cell, LABELS[off][chunk - chunks.start])

    def test_corrupted_cell_rejected(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        patched = bytearray(original)
        patch_part2_battle_start_day_overlay_obj(patched)
        data, _ = lz77_decompress(patched, 0x45EC74)
        first, second = data[10 * 512:11 * 512], data[11 * 512:12 * 512]
        for corrupted in (bytes(512), second, bytes(v ^ 0x01 for v in first)):
            with self.subTest(corrupted=hashlib.sha256(corrupted).hexdigest()[:8]):
                with self.assertRaises(AssertionError):
                    validate_cell(corrupted, '일')


if __name__ == '__main__':
    unittest.main()
