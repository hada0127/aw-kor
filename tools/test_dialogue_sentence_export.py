"""dialogue_sentence_export: lossless placeholder decomposition, flags, determinism.

Synthetic tests need no ROM. ROM tests run when the default (or AW_TEST_ROM /
AW_TEST_MAP / AW_TEST_MANIFEST) candidate inputs exist, otherwise skip.
Run: PYTHONPATH=tools python3 -m unittest tools.test_dialogue_sentence_export
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import dialogue_sentence_export as dse


class JG:
    def text(self, pair):
        return pair.decode('cp932')


def sj(s):
    return s.encode('cp932')


class GlossaryTermTests(unittest.TestCase):
    def test_canonical_term_drops_descriptive_labels(self):
        cases = [
            ({'term': '캐논포 (キャノン砲; 캐넌 금지)', 'current': '캐논포', 'edit': ''}, '캐논포'),
            ({'term': '사령관 (쇼군/장군 금지)', 'current': '쇼군/장군', 'edit': '사령관'}, '사령관'),
            ({'term': '사령관 (シレイ 플레이어 직함; 시레이 금지)', 'current': '사령관/사령', 'edit': ''},
             '사령관'),
            ({'term': '브레이크', 'current': '브레이크', 'edit': ''}, '브레이크'),
            ({'term': '수송선 (輸送船; 수송함 금지)', 'edit': ''}, '수송선'),
        ]
        for entry, want in cases:
            with self.subTest(term=entry['term']):
                self.assertEqual(dse.canonical_term(entry), want)

    def test_committed_common_terms_export_clean_values(self):
        pn = json.loads((dse.ROOT / 'data/proper_nouns.json').read_text())
        for e in pn['common_terms']:
            ja = e.get('ja_note') or ''
            if ja and '/' not in ja:
                value = dse.canonical_term(e)
                with self.subTest(ja=ja):
                    self.assertTrue(value)
                    for mark in ('(', '（', ';', '금지', '->'):
                        self.assertNotIn(mark, value)


class DecomposeTests(unittest.TestCase):
    def test_p2_controls_become_placeholders_losslessly(self):
        raw = sj('ふう、') + b'w' + sj('相手だわ。') + b'r' + sj('うん') + b'k' + b'  \0'
        d = dse.decompose(raw, 'p2', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(dse.joined(d), 'ふう、{w}相手だわ。{r}うん{k}')
        self.assertEqual([x['ph'] for x in d['skeleton']], ['{w}', '{r}', '{k}'])
        self.assertEqual(d['suffix'], b'  \0')
        self.assertEqual(len(d['segments']), len(d['skeleton']) + 1)

    def test_p1_header_rides_on_newline_and_prefix(self):
        raw = b'\x0a\x09\x09' + sj('あ') + b'r\x0a\x09\x09' + sj('い') + b'k\x0a\0'
        d = dse.decompose(raw, 'p1', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(d['prefix'], b'\x0a\x09\x09')
        self.assertEqual(d['skeleton'][0]['raw'], b'r\x0a\x09\x09')
        self.assertEqual(dse.joined(d), 'あ{r}い{k}')
        self.assertEqual(d['suffix'], b'\x0a\0')

    def test_keyword_style_span_is_one_fixed_placeholder(self):
        raw = sj('この') + b'2' + sj('歩兵') + b'0' + sj('を') + b'\0'
        d = dse.decompose(raw, 'p1', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(dse.joined(d), 'この{kw:歩兵}を')
        self.assertEqual(d['skeleton'][0]['kind'], 'keyword')

    def test_unclosed_style_stays_raw_style(self):
        raw = sj('あ') + b'3' + sj('い') + b'r' + sj('う') + b'0\0'
        d = dse.decompose(raw, 'p2', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(dse.joined(d), 'あ{s:33}い{r}う{s:30}')

    def test_name_icon_wait_and_inline_format(self):
        raw = b'i' + sj('さん') + b'M\x01' + b'W' + sj('あ') + b'\x0a' + sj('い') + b'\0'
        d = dse.decompose(raw, 'p1', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(dse.joined(d), '{name}さん{icon:4d01}{W}あ{f:0a}い')

    def test_space_and_padding(self):
        raw = sj('あ') + b'\x81\x40' + sj('い') + b'    ' + b'r' + sj('う') + b'\0'
        d = dse.decompose(raw, 'p2', JG(), ' ')
        self.assertEqual(dse.reassemble(d), raw)
        self.assertEqual(dse.joined(d), 'あ い{r}う')
        self.assertEqual(d['segments'][0]['raw'], sj('あ') + b'\x81\x40' + sj('い') + b'    ')


class FlagTests(unittest.TestCase):
    def test_punct_missing_per_page(self):
        self.assertEqual(dse.punct_missing_pages('行くぞ！{k}待て？{k}', '가자{k}기다려?{k}'), [0])
        self.assertEqual(dse.punct_missing_pages('行くぞ！{w}{k}', '가자!{w}{k}'), [])
        self.assertEqual(dse.punct_missing_pages('え{kw:歩兵}！{k}', '어 {kw:보병}{k}'), [0])
        # page count mismatch is not judged here (skeleton_mismatch covers it)
        self.assertEqual(dse.punct_missing_pages('a！{k}b！{k}', 'a{k}'), [])

    def test_chunks_cover_all_in_order(self):
        items = list(range(301))
        ch = dse._chunks(items, 125)
        self.assertEqual(sum(ch, []), items)
        self.assertTrue(all(len(c) <= 151 for c in ch))


def _paths():
    rom = Path(os.environ.get('AW_TEST_ROM', dse.DEFAULT_ROM))
    m = Path(os.environ.get('AW_TEST_MAP', dse.DEFAULT_MAP))
    mf = Path(os.environ.get('AW_TEST_MANIFEST', dse.DEFAULT_MANIFEST))
    return rom, m, mf


@unittest.skipUnless(all(p.exists() for p in (*_paths(), dse.DEFAULT_ORIGINAL)), 'candidate ROM/map/manifest absent')
class RomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rom, m, mf = _paths()
        cls.argv = ['--rom', str(rom), '--map', str(m), '--manifest', str(mf)]
        cls.tmp = tempfile.TemporaryDirectory(dir=str(dse.ROOT / 'temp'))
        cls.plan = Path(cls.tmp.name) / 'batches.json'
        assert dse.main(['plan', *cls.argv, '--out', str(cls.plan)]) == 0
        cls.doc = json.loads(cls.plan.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _export(self, batch, out):
        assert dse.main(['export', *self.argv, '--batch-plan', str(self.plan), '--batch', batch,
                         '--out-dir', str(out)]) == 0
        return (Path(out) / batch / 'in.json').read_bytes()

    def test_plan_counts_and_pilot(self):
        t = self.doc['totals']
        self.assertEqual(self.doc['pilot'], 'p2-tutorial.1')
        self.assertTrue(20 <= t['p2_batches'] <= 30, t)
        self.assertTrue(12 <= t['p1_batches'] <= 18, t)
        ids = [i for b in self.doc['batches'] for i in b['ids']]
        keys = [(b['part'], i) for b in self.doc['batches'] for i in b['ids']]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(ids), t['p1'] + t['p2'])

    def test_pilot_export_is_deterministic_and_lossless(self):
        a = self._export('p2-tutorial.1', Path(self.tmp.name) / 'a')
        b = self._export('p2-tutorial.1', Path(self.tmp.name) / 'b')
        self.assertEqual(a, b)
        doc = json.loads(a)
        self.assertGreaterEqual(len(doc['messages']), 50)
        for m in doc['messages']:
            # contract: payload == prefix + seg/skeleton interleave + suffix
            raw = bytes.fromhex(m['prefix'])
            for n, seg in enumerate(m['segments']):
                raw += bytes.fromhex(seg['raw'])
                if n < len(m['skeleton']):
                    raw += bytes.fromhex(m['skeleton'][n]['raw'])
            raw += bytes.fromhex(m['suffix'])
            self.assertEqual(raw.hex(), m['payload_hex'], m['id'])
            text = ''.join(s['ko'] + (m['skeleton'][n]['ph'] if n < len(m['skeleton']) else '')
                           for n, s in enumerate(m['segments']))
            self.assertEqual(text, m['decomp_ko'], m['id'])
            if m['template'] == 'export-decomp':
                self.assertEqual([x['ph'] for x in m['skeleton']], m['placeholders'])
            # ko and placeholders agree whichever template produced them
            self.assertEqual(dse.PLACEHOLDER.findall(m['ko']), m['placeholders'], m['id'])
            self.assertIn('register', m['speaker'])
            self.assertIn('capacity', m)
            self.assertIn(m['relocatable'], (True, False))

    def test_known_flags_and_pins(self):
        recs, _ = dse.build_messages(dse.DEFAULT_ORIGINAL.read_bytes(), _paths()[0].read_bytes(),
                                     json.loads(_paths()[2].read_text()), _paths()[1])
        by = {k[1]: v for k, v in recs.items()}
        # msg77 carried T2 leftover; msg 92 carried punct_173 W3 item
        self.assertIn('t2_leftover', by[0xA02B08]['flags'])
        # pinned contract messages are locked and not relocatable
        for src in (0xD821F0, 0xB82FAC, 0xB830AC):
            if src in by:
                self.assertTrue(by[src]['locked'], hex(src))
                self.assertFalse(by[src]['relocatable'], hex(src))
        # punct_173 flags come from the gitignored temp/ ledger; a snapshot
        # without it emits no such flags, so the pins need that input present.
        if not dse.DEFAULT_PUNCT.exists():
            self.skipTest(f'punct_173 ledger absent: {dse.DEFAULT_PUNCT}')
        self.assertIn('punct_173:W3', by[0xA031CC]['flags'])
        n173 = sum(1 for r in recs.values() if any(f.startswith('punct_173:') for f in r.get('flags', [])))
        self.assertGreater(n173, 50)


if __name__ == '__main__':
    unittest.main()
