import hashlib
import struct
import unittest
from pathlib import Path

import part2_co_name_obj as m
from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

NAMES = ('캐서린', '료', '맥스', '호이프', '도미노', '빌리', '키쿠치요', '아스카', '이글', '모프',
         '헬보우즈', '콩', '캣', '스네이크', '호크', '하치', '이반', '한나', '야마모토')
# Current-generator golden over all 19 names at their original slot limits (R21, 2026-11-10).
NAMES_SHA256 = '87d0a381d5b5ef4ded022ffa15bea9cb43b56e2e22d1a126149afd4d22319dfc'


def slot_limits():
    original = (Path(__file__).resolve().parent.parent / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
    offsets = []
    for row in range(24):
        pointer = struct.unpack_from('<I', original, 0x81BE68 + row * 0x44)[0]
        if not 0x08452000 <= pointer < 0x08460000:
            break
        if pointer - 0x08000000 not in offsets:
            offsets.append(pointer - 0x08000000)
    return [lz77_decompress(original, offset)[1] for offset in offsets]


def names_digest(limits):
    return hashlib.sha256(b''.join(m.render(n, limit) for n, limit in zip(NAMES, limits))).hexdigest()


class Part2CONameObjTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limits = slot_limits()

    def test_jp_style_layout(self):
        for name, limit in zip(NAMES, self.limits):
            pixels = m.pixels(name, limit)
            self.assertLessEqual({v for row in pixels for v in row}, {0, m.BODY, m.AA, m.CORNER, m.OUTLINE}, name)
            body = [(x, y) for y, row in enumerate(pixels) for x, v in enumerate(row) if v == m.BODY]
            xs, ys = [x for x, _ in body], [y for _, y in body]
            self.assertGreaterEqual(min(ys), 1, name)
            self.assertLessEqual(max(ys), 13, name)
            self.assertGreaterEqual(max(ys) - min(ys), 9, name)          # JP-height letters (rows 1..12)
            self.assertLessEqual(abs((min(xs) + max(xs)) - 46), 2, name)  # centred like JP
            self.assertIn(pixels[min(ys) - 1][xs[ys.index(min(ys))]], (m.OUTLINE, m.CORNER), name)
            self.assertNotIn(m.BODY, [row[0] for row in pixels] + [row[-1] for row in pixels] + pixels[15], name)

    def test_full_aa_when_slot_allows(self):
        values = {v for row in m.pixels('료') for v in row}
        self.assertEqual(values, {0, m.BODY, m.AA, m.CORNER, m.OUTLINE})

    def test_counters_stay_open(self):
        # 콩: the ㅋ middle bar and the ㅇ hole must not fill in (R20 blob regression).
        pixels = m.pixels('콩')
        self.assertEqual(set(pixels[3][19:24]), {m.OUTLINE})   # gap between the ㅋ bars
        self.assertEqual(set(pixels[11][21:25]), {m.OUTLINE})  # ㅇ hole

    def test_names_fit_original_lz77_slots(self):
        self.assertEqual(len(self.limits), len(NAMES))
        for name, limit in zip(NAMES, self.limits):
            self.assertLessEqual(len(lz77_compress_optimal(m.render(name, limit), vram_safe=True)), limit, name)

    def test_generator_golden(self):
        self.assertEqual(names_digest(self.limits), NAMES_SHA256)


if __name__ == '__main__':
    unittest.main()
