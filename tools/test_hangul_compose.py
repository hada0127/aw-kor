"""고정 반례 + 독립 키열/Unicode 산술 오라클로 참조 모델을 검사한다."""
import json
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hangul_compose as hc

# 모델의 전이/분해 상수를 재사용하지 않는 기대 키열과 중간 음절.
INITIALS = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
VOWEL_KEYS = 'ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅗ ㅗㅏ ㅗㅐ ㅗㅣ ㅛ ㅜ ㅜㅓ ㅜㅔ ㅜㅣ ㅠ ㅡ ㅡㅣ ㅣ'.split()
FINAL_KEYS = ['', *'ㄱ ㄲ ㄱㅅ ㄴ ㄴㅈ ㄴㅎ ㄷ ㄹ ㄹㄱ ㄹㅁ ㄹㅂ ㄹㅅ ㄹㅌ ㄹㅍ ㄹㅎ ㅁ ㅂ ㅂㅅ ㅅ ㅆ ㅇ ㅈ ㅊ ㅋ ㅌ ㅍ ㅎ'.split()]
TABLE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'syllable_to_code_2350.json'
TABLE = {c: int(v, 16) for c, v in json.loads(TABLE_PATH.read_text(encoding='utf-8')).items()}
REVERSE = {v: c for c, v in TABLE.items()}


def oracle(char):
    n = ord(char) - 0xAC00
    l, v, t = n // 588, n // 28 % 21, n % 28
    vk, tk = VOWEL_KEYS[v], FINAL_KEYS[t]
    keys = INITIALS[l] + vk + tk
    # 각 키 직후의 완성 후보. 첫 초성에는 완성 후보가 없다.
    candidates = [None]
    candidates.append(chr(0xAC00 + l * 588 + VOWEL_KEYS.index(vk[0]) * 28))
    if len(vk) == 2:
        candidates.append(chr(0xAC00 + l * 588 + v * 28))
    if tk:
        candidates.append(chr(0xAC00 + l * 588 + v * 28 + FINAL_KEYS.index(tk[0])))
        if len(tk) == 2:
            candidates.append(char)
    return keys, candidates


class CompositionTests(unittest.TestCase):
    def composer(self, keys=''):
        c = hc.Composer(TABLE)
        self.type(c, keys)
        return c

    def type(self, c, keys):
        for key in keys:
            self.assertEqual(c.press(key), hc.Result(True), (keys, key, c.snapshot()))

    def text(self, c):
        return ''.join(REVERSE[value] if kind == 'code' else value for kind, value in c.preview())

    def reject(self, c, operation, reason):
        before = c.snapshot()
        self.assertEqual(operation(), hc.Result(False, reason))
        self.assertEqual(c.snapshot(), before)

    def test_table_and_inventory(self):
        self.assertEqual(hc.load_table(), TABLE)
        self.assertEqual(len(TABLE), 2350)
        self.assertEqual(len(set(TABLE.values())), 2350)
        self.assertTrue(all(1 <= v <= 65535 for v in TABLE.values()))
        self.assertEqual(len(set(hc.SELECTABLE_JAMO)), 33)
        self.assertEqual(len(set(hc.PREVIEW_JAMO)), 40)
        for char, code in TABLE.items():
            n = ord(char) - 0xAC00
            self.assertEqual(hc.code_for(TABLE, n // 588, n // 28 % 21, n % 28), code)

    def test_fixed_words_and_migration(self):
        cases = [('ㅎㅏㄴㄱㅡㄹ', '한글'), ('ㄱㅏㅇㅊㅓㄹ', '강철'),
                 ('ㅂㅜㄹㄱㅇㅡㄴㄷㅏㄹ', '붉은달'),
                 ('ㅎㅏㄴㅏ', '하나'), ('ㅎㅏㄴㄱㅏ', '한가'),
                 ('ㄷㅏㄹㄱㅏ', '달가'), ('ㄱㅏㅂㅅㅣ', '갑시')]
        for keys, expected in cases:
            with self.subTest(expected=expected):
                c = self.composer(keys)
                self.assertEqual(self.text(c), expected)
                self.assertEqual(c.confirm(), hc.Result(True))
                self.assertEqual(c.snapshot(), (tuple(TABLE[ch] for ch in expected), None))
                expected_bytes = b''.join(TABLE[ch].to_bytes(2, 'big') for ch in expected).ljust(16, b'\0')
                self.assertEqual(c.serialize(), expected_bytes)
                self.assertEqual(c.confirm(), hc.Result(True))

    def test_compound_vowels(self):
        for keys, vowel, expected in [('ㅗㅏ', 'ㅘ', '과'), ('ㅗㅐ', 'ㅙ', '괘'), ('ㅗㅣ', 'ㅚ', '괴'),
                                      ('ㅜㅓ', 'ㅝ', '궈'), ('ㅜㅔ', 'ㅞ', '궤'), ('ㅜㅣ', 'ㅟ', '귀'),
                                      ('ㅡㅣ', 'ㅢ', '의')]:
            initial = 'ㅇ' if expected == '의' else 'ㄱ'
            c = self.composer(initial + keys)
            self.assertEqual(self.text(c), expected)
            self.assertTrue(c.backspace().accepted)
            self.assertEqual(self.text(c), {'ㅗ': '고', 'ㅜ': '구', 'ㅡ': '으'}[keys[0]])
            v = self.composer(keys)
            self.assertEqual(v.preview(), [('active', vowel)])
            self.assertTrue(v.backspace().accepted)
            self.assertEqual(v.preview(), [('active', keys[0])])
            self.assertTrue(v.backspace().accepted)
            self.assertEqual(v.preview(), [])

    def test_all_final_clusters(self):
        for keys in ['ㄱㅅ', 'ㄴㅈ', 'ㄴㅎ', 'ㄹㄱ', 'ㄹㅁ', 'ㄹㅂ', 'ㄹㅅ', 'ㄹㅌ', 'ㄹㅍ', 'ㄹㅎ', 'ㅂㅅ']:
            # 실제 표에서 해당 겹받침까지 도달하는 예를 독립 오라클로 선택.
            char = next(ch for ch in sorted(TABLE) if FINAL_KEYS[(ord(ch) - 0xAC00) % 28] == keys
                        and all(p is None or p in TABLE for p in oracle(ch)[1]))
            c = self.composer(oracle(char)[0])
            self.assertEqual(self.text(c), char)
            self.assertTrue(c.backspace().accepted)
            first = chr(ord(char) - (ord(char) - 0xAC00) % 28 + FINAL_KEYS.index(keys[0]))
            self.assertEqual(self.text(c), first)
        c = self.composer('ㄱㅏㄱㄱ')
        self.assertEqual(c.preview(), [('code', TABLE['각']), ('active', 'ㄱ')])

    def test_backspace_stages_and_loaded(self):
        for keys, stages in [('ㄷㅏㄹㄱ', ['달', '다', 'ㄷ', '']),
                             ('ㅇㅗㅐ', ['오', 'ㅇ', ''])]:
            c = self.composer(keys)
            for expected in stages:
                self.assertTrue(c.backspace().accepted)
                self.assertEqual(self.text(c), expected)
            self.reject(c, c.backspace, 'empty')
        c = self.composer()
        c.load([TABLE['가']])
        self.assertTrue(c.backspace().accepted)
        self.assertEqual(c.preview(), [])
        self.type(c, 'ㄱㅏ')
        self.assertTrue(c.backspace().accepted)
        self.assertEqual(c.preview(), [('active', 'ㄱ')])

    def test_incomplete_and_invalid(self):
        for keys in ['ㄱ', 'ㅏ', 'ㅗㅐ']:
            c = self.composer(keys)
            self.reject(c, c.confirm, 'incomplete')
            self.reject(c, c.space, 'incomplete')
            self.reject(c, lambda: c.press('ㄴ'), 'incomplete')
        c = self.composer('ㅏ')
        self.reject(c, lambda: c.press('ㅏ'), 'invalid_transition')
        for invalid in ['', '가', 'ㅘ', 'a', ' ', 'ㄱㅏ', None, 3]:
            before = c.snapshot()
            with self.assertRaises(ValueError):
                c.press(invalid)
            self.assertEqual(c.snapshot(), before)

    def test_new_active_boundaries(self):
        c = self.composer('ㄱㅏㅃ')
        self.assertEqual(c.preview(), [('code', TABLE['가']), ('active', 'ㅃ')])
        self.type(c, 'ㅏ')
        self.assertEqual(self.text(c), '가빠')
        c = self.composer('ㄱㅏㅓ')
        self.assertEqual(c.preview(), [('code', TABLE['가']), ('active', 'ㅓ')])
        self.reject(c, c.confirm, 'incomplete')
        self.assertEqual(c.serialize(), bytes.fromhex('88 40') + bytes(14))
        c.reset()
        self.assertEqual(c.confirm(), hc.Result(True))
        self.assertEqual(c.space(), hc.Result(True))
        self.assertEqual(c.preview(), [('code', 0x8140)])
        self.assertEqual(c.backspace(), hc.Result(True))
        self.assertEqual(c.snapshot(), ((), None))

    def test_eighth_slot_and_boundaries(self):
        c = self.composer()
        c.load([TABLE['가']] * 8)
        for key in ['ㄱ', 'ㅏ']:
            self.reject(c, lambda: c.press(key), 'no_slot')
        self.reject(c, c.space, 'no_slot')
        self.assertTrue(c.backspace().accepted)
        self.type(c, 'ㅎㅏ')
        self.assertTrue(c.press('ㄴ').accepted)
        self.reject(c, lambda: c.press('ㅏ'), 'no_slot')
        self.reject(c, lambda: c.press('ㄱ'), 'no_slot')
        self.reject(c, c.space, 'no_slot')
        self.assertTrue(c.backspace().accepted)
        self.assertEqual(c.preview()[-1], ('active', '하'))
        self.reject(c, lambda: c.press('ㅃ'), 'no_slot')
        self.reject(c, lambda: c.press('ㅏ'), 'no_slot')
        self.assertTrue(c.confirm().accepted)
        self.assertEqual(len(c.preview()), 8)
        c.load([TABLE['가']] * 6)
        self.type(c, 'ㄱㅏ')
        self.assertTrue(c.space().accepted)
        self.assertEqual(c.preview()[-2:], [('code', TABLE['가']), ('code', 0x8140)])

    def test_strict_rejection_counterexamples(self):
        self.assertNotIn('갣', TABLE)
        c = self.composer('ㄱㅐ')
        self.reject(c, lambda: c.press('ㄷ'), 'not_in_2350')
        self.assertEqual(c.preview(), [('active', '개')])
        examples = {'뢨': '뢔', '썅': '쌰', '쏀': '쎼', '쓩': '쓔', '쭁': '쬬'}
        report = hc.reachability_report(TABLE)
        for target, missing in examples.items():
            self.assertIn(target, TABLE)
            self.assertNotIn(missing, TABLE)
            self.assertIn(missing, report['unreachable'][target])
            keys, candidates = oracle(target)
            c = self.composer()
            for key, candidate in zip(keys, candidates):
                if candidate is not None and candidate not in TABLE:
                    self.reject(c, lambda: c.press(key), 'not_in_2350')
                    break
                self.assertTrue(c.press(key).accepted)

    def test_migration_rejection_atomicity(self):
        cases = []
        for char in sorted(TABLE):
            n = ord(char) - 0xAC00
            t = n % 28
            if not t or not all(p is None or p in TABLE for p in oracle(char)[1]):
                continue
            tk = FINAL_KEYS[t]
            front = chr(ord(char) - t + (FINAL_KEYS.index(tk[0]) if len(tk) == 2 else 0))
            for v, vk in enumerate(VOWEL_KEYS):
                if len(vk) != 1:
                    continue
                following = chr(0xAC00 + INITIALS.index(tk[-1]) * 588 + v * 28)
                if front not in TABLE or following not in TABLE:
                    cases.append((char, vk, front, following))
        self.assertTrue(cases)
        for char, key, front, following in cases:
            c = self.composer(oracle(char)[0])
            self.reject(c, lambda: c.press(key), 'not_in_2350')
        print(f'migration_rejection_cases={len(cases)} example={cases[0]}')

    def test_serialization_load_reset(self):
        c = self.composer('ㄱㅏ')
        self.assertEqual(c.serialize(), bytes(16))
        self.assertEqual(c.confirm(), hc.Result(True))
        self.assertEqual(c.serialize(), bytes.fromhex('88 40') + bytes(14))
        self.assertTrue(c.space().accepted)
        self.assertEqual(c.serialize(), bytes.fromhex('88 40 81 40') + bytes(12))
        for codes in [[0x1234, 0xFFFF, TABLE['가']], [TABLE['가']] * 8, [], [0x8140]]:
            c.load(codes)
            serialized = c.serialize()
            self.assertEqual(len(serialized), 16)
            self.assertEqual(serialized, b''.join(n.to_bytes(2, 'big') for n in codes).ljust(16, b'\0'))
            c.load(serialized)
            self.assertEqual(c.snapshot(), (tuple(codes), None))
        c.load([0x1234, 0, 0xFFFF])
        self.assertEqual(c.snapshot(), ((0x1234,), None))
        c.load(bytes.fromhex('12 34 00 00 FF FF') + bytes(10))
        self.assertEqual(c.snapshot(), ((0x1234,), None))
        self.type(c, 'ㄱ')
        for bad in [b'', bytes(15), bytes(17), [1] * 9, [-1], [65536], [True], ['0x8840'], (1,)]:
            before = c.snapshot()
            with self.assertRaises(ValueError):
                c.load(bad)
            self.assertEqual(c.snapshot(), before)
        c.reset()
        self.assertEqual(c.snapshot(), ((), None))
        c.load([TABLE['가']])
        self.assertEqual(c.snapshot(), ((TABLE['가'],), None))

    def test_exhaustive_syllables(self):
        reachable = set()
        missing_supported = {}
        rejected = 0
        for n in range(11172):
            char = chr(0xAC00 + n)
            keys, candidates = oracle(char)
            c = self.composer()
            for key, candidate in zip(keys, candidates):
                if candidate is not None and candidate not in TABLE:
                    self.reject(c, lambda: c.press(key), 'not_in_2350')
                    rejected += 1
                    break
                self.assertTrue(c.press(key).accepted, (char, key))
            else:
                self.assertEqual(c.preview(), [('active', char)])
                self.assertEqual(TABLE[char], hc.code_for(TABLE, n // 588, n // 28 % 21, n % 28))
                reachable.add(char)
            if char in TABLE:
                missing = tuple(dict.fromkeys(p for p in candidates if p is not None and p not in TABLE))
                if missing:
                    missing_supported[char] = missing
        report = hc.reachability_report(TABLE)
        self.assertEqual(report['unreachable'], missing_supported)
        self.assertEqual(report['reachable'], len(reachable))
        self.assertEqual(report['mapped'], 2350)
        self.assertEqual(reachable, set(TABLE) - set(missing_supported))
        print(f'exhaustive=11172 reached={len(reachable)} rejected={rejected} supported_unreachable={len(missing_supported)}')

    def test_deterministic_sequences(self):
        rng = random.Random(20261023)
        c = self.composer()
        operations = [lambda key=k: c.press(key) for k in hc.SELECTABLE_JAMO]
        operations += [c.backspace, c.space, c.confirm]
        rejects = 0
        for i in range(20000):
            if i % 100 == 0:
                c.reset()
            before = c.snapshot()
            result = rng.choice(operations)()
            if not result.accepted:
                rejects += 1
                self.assertIsNotNone(result.reason)
                self.assertEqual(c.snapshot(), before)
            self.assertLessEqual(len(c.preview()), 8)
            self.assertEqual(len(c.serialize()), 16)
            if c.active is not None and c.active.complete:
                self.assertIn(c.active.char, TABLE)
        print(f'random_operations=20000 seed=20261023 rejections={rejects}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
