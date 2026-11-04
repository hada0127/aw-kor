"""Native-token and lossless-layout regressions; no emulator required."""
import unittest
from dialogue_pixel_layout import tokenize,physical_rows,reflow_message,_source_signature
from repoint_source_rows import row_bytes


class Labels:
    def text(self,pair):
        return pair.decode('shift_jis')


class LayoutTests(unittest.TestCase):
    def test_sjis_trails_and_icon_operands_are_not_commands(self):
        ts=tokenize(bytes.fromhex('81724d726900'),'p1')
        self.assertEqual([t['kind'] for t in ts],['glyph','icon','name','end'])
        self.assertEqual([t['advance'] for t in ts],[8,16,48,0])

    def test_choice_only_row_is_counted(self):
        rows=physical_rows(tokenize(b'\x81\x40rQY\0','p1'))
        self.assertEqual([r['line'] for r in rows],[0,1])
        self.assertEqual(rows[1]['tokens'][0]['kind'],'choice')

    def test_malformed_pair_or_operand_is_rejected(self):
        for raw in (b'\x81\0',b'M'):
            with self.assertRaises(ValueError):tokenize(raw,'p1')

    def test_blank_fixed_row_and_caption_indent_survive(self):
        raw='あ'.encode('shift_jis')+b'r\x81\x40r'+'い'.encode('shift_jis')+b' '*20+b'\0'
        changes=[dict(page=0,before=['あ','　','い'],after=['　'*3+'あ','　','い'])]
        after,_=reflow_message(raw,'p1',Labels(),changes,6)
        rows=physical_rows(tokenize(after,'p1',Labels()))
        self.assertEqual([''.join(t['text'] for t in r['tokens']) for r in rows],['　'*3+'あ','　','い'])
        self.assertEqual(len(after),len(raw))

    def test_three_rows_create_native_two_row_pages(self):
        raw='あ　い　う'.encode('shift_jis')+b' '*8+b'\0'
        after,_=reflow_message(raw,'p1',Labels(),[dict(page=0,before=['あ　い　う'],after=['あ','い','う'])],2,allow_paging=True)
        rows=physical_rows(tokenize(after,'p1',Labels()))
        self.assertEqual([(r['page'],r['line']) for r in rows],[(0,0),(0,1),(1,0)])

    def test_no_silent_word_or_separator_change(self):
        raw='あ　い'.encode('shift_jis')+b' '*6+b'\0'
        for text in ('あ　う','あい'):
            with self.assertRaises(ValueError):
                reflow_message(raw,'p1',Labels(),[dict(page=0,before=['あ　い'],after=[text])],2)

    def test_choice_cannot_be_pushed_out(self):
        raw='あ　い'.encode('shift_jis')+b'rQY'+b' '*8+b'\0'
        with self.assertRaises(ValueError):
            reflow_message(raw,'p1',Labels(),[dict(page=0,before=['あ　い',''],after=['あ','い'])],2)

    def test_styles_keep_their_side_of_authored_spaces(self):
        raw='あ　'.encode('shift_jis')+b'2'+'い　う'.encode('shift_jis')+b'0'+b' '*8+b'\0'
        after,_=reflow_message(raw,'p1',Labels(),[dict(page=0,before=['あ　い　う'],after=['あ　い','う'])],2)
        self.assertIn('あ　'.encode('shift_jis')+b'2',after)

    def test_consumer_inventory_distinguishes_backing_unknown_and_visible_slots(self):
        from dialogue_pixel_layout import ROOT,p2_consumers,profile
        original=(ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        consumers=p2_consumers(original)
        self.assertEqual(profile('p2',0xA34F1C,consumers),('p2_link_status',64,1))
        self.assertEqual(profile('p2',0xA34F48,consumers),('p2_empty_map_header',80,1))
        self.assertEqual(profile('p2',0xA35758,consumers),('p2_territory_label',72,1))
        self.assertEqual(profile('p2',0xA34F5C,consumers),('p2_link_state_dependent',256,1))
        self.assertEqual(profile('p2',0xA35280,consumers),('p2_link_marquee',256,1))
        for source in (0xA2FE58,0xA351A4,0xA351CC,0xA351E0,0xA351FC):
            self.assertEqual(profile('p2',source,consumers),('p2_unverified_consumer',None,None))

    def test_source_joiners_distinguish_punctuation_and_word_gaps(self):
        m=dict(msg='0x10',new_addr='0x0',new_len=8,line_spans={'0x10':[0,2]},
               source_line_fragments={'0x10':[[0,2],[4,2]]},source_fragment_joiners={'0x10':['']})
        rom='あ。い。'.encode('shift_jis')
        self.assertEqual(row_bytes(rom,m,'0x10'),'あい'.encode('shift_jis'))
        m['source_fragment_joiners']['0x10']=['8140']
        self.assertEqual(row_bytes(rom,m,'0x10'),'あ　い'.encode('shift_jis'))
        m['source_fragment_joiners']['0x10']=['72']
        with self.assertRaises(ValueError):row_bytes(rom,m,'0x10')


class DeclaredGeometryAuditTests(unittest.TestCase):
    """plan_C B: data/dialogue_consumer_geometry.json bounds unverified windows."""

    def audit(self, rewritten, renderer='0x08000000'):
        from unittest.mock import patch
        import dialogue_pixel_layout as L
        # 4 two-byte glyphs = 32px on one row; one declared row of 24px.
        payload = b'\x82\xa0' * 4 + b'\0'
        message = dict(game='p2', source=0xA00000, target=0xA00000, payload=payload, script=True,
                       sites=[0x100], profile=('p2_unverified_consumer', None, None))
        manifest = [dict(msg='0xA00000', status='relocated', new_addr='0xA00000', new_len=len(payload),
                         **({'rewrite': {'batch': 'w3'}} if rewritten else {}))]
        geometry = [(0xA00000, 0xA00010, dict(renderer=renderer, line_px=200, lines=1, row_px=[24],
                                              evidence='t', group='g'))]

        class Glyphs:
            def __init__(self, rom): pass
            def bitmap(self, pair, game): return [[1] * 8]
            def text(self, pair): return pair.decode('shift_jis')
        with patch.object(L, 'inventory', return_value=[message]), patch.object(L, 'Glyphs', Glyphs):
            return L.audit(bytes(0xA01980), bytes(0xA01980), manifest, geometry)['summary']

    def test_overlay_written_declared_message_overflow_is_fatal(self):
        summary = self.audit(rewritten=True)
        self.assertEqual(summary['overflows'], 1)
        self.assertEqual(summary['declared_geometry_messages'], 1)
        self.assertEqual(summary['unverified_consumer_messages'], 1)

    def test_legacy_declared_overflow_is_fatal(self):
        """fixB C1 review #2: no legacy-text exemption for attributed geometry."""
        summary = self.audit(rewritten=False)
        self.assertEqual(summary['overflows'], 1)
        self.assertNotIn('declared_legacy_overflows', summary)
        self.assertEqual(summary['declared_geometry_messages'], 1)

    def test_unattributed_geometry_is_not_applied(self):
        """renderer null: inferred bounds stay out; the message remains unverified."""
        for rewritten in (False, True):
            summary = self.audit(rewritten=rewritten, renderer=None)
            self.assertEqual(summary['declared_geometry_messages'], 0)
            self.assertEqual(summary['overflows'], 0)
            self.assertEqual(summary['unverified_consumer_messages'], 1)


class PortraitFirstRowTests(unittest.TestCase):
    """fixB C1/C2: a 23-cell (184px) first portrait row is an overflow in both parts."""

    def audit(self, game, profile):
        from unittest.mock import patch
        import dialogue_pixel_layout as L
        # 23 two-byte glyphs (184px) + newline + one glyph + terminator.
        payload = b'\x82\xa0' * 23 + b'r' + b'\x82\xa0' + b'\0'
        message = dict(game=game, source=0xA00000, target=0xA00000, payload=payload, script=True,
                       sites=[0x100], profile=(profile, 176, 2))

        class Glyphs:
            def __init__(self, rom): pass
            def bitmap(self, pair, game): return [[1] * 8]
            def text(self, pair): return pair.decode('shift_jis')
        with patch.object(L, 'inventory', return_value=[message]), patch.object(L, 'Glyphs', Glyphs):
            return L.audit(bytes(0xA01980), bytes(0xA01980), [], [])

    def test_part2_first_row_184_overflows(self):
        result = self.audit('p2', 'p2_portrait')
        self.assertEqual(result['summary']['overflows'], 1)
        self.assertEqual(result['rows'][0]['limit_px'], 176)

    def test_part1_first_row_184_overflows(self):
        result = self.audit('p1', 'p1_portrait')
        self.assertEqual(result['summary']['overflows'], 1)
        self.assertEqual(result['rows'][0]['limit_px'], 176)


if __name__=='__main__':unittest.main()
