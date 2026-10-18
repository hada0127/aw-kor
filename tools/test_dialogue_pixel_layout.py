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


if __name__=='__main__':unittest.main()
