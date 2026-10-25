"""Spacing opt-in, provenance and native reference failure regressions."""
import copy
import struct
import unittest
from unittest.mock import patch
from dialogue_pixel_layout import reflow_message, tokenize
from dialogue_spacing import _spacing_intent, guard_new_relocation, _native_provenance, apply_repairs


class Labels:
    def text(self,pair):return pair.decode('shift_jis')


class SpacingTests(unittest.TestCase):
    def test_dd0108_repointer_survives_downstream_spacing(self):
        from test_dialogue_script_safety import ScriptSafetyTests
        from dialogue_spacing import load_ledger, verify, reviewed_bteam_rows, reviewed_bteam_half_cells
        from dialogue_repoint import text_segment_cells
        from repoint_source_rows import row_bytes
        from build_korean_full import validate_bteam_payload
        from qa_integrity_map import load_syl

        original, rom, record, full, _ = ScriptSafetyTests().dd0108_fixture()
        # Exercise the real batch writer with a second, growing repair: an
        # empty no-op alone would not test allocation/metadata side effects.
        small_original, small_rom, other_records, writes, _, neighbor = self.fixture()
        original[:1024] = small_original
        rom[:1024] = small_rom
        manifest = [record] + other_records
        target = int(record['new_addr'], 16)
        writes.append([target, record['new_len'], record['new_len'], '', None, None, None,
                       'repoint:0xDD0108', dict(source_spans=record['source_spans'],
                       source=0xDD0108, old_len=record['old_len'], ptr_sites=[0xDE705C])])
        ledger = load_ledger()
        ledger['messages'] = [r for r in ledger['messages'] if int(r['source'], 16) == 0xDD0108]
        ledger['messages'] += neighbor['messages']
        ledger['messages'][-1]['final_pages'] = [['あ い']]
        # Inventory/font construction require a whole product ROM; isolate
        # those inputs only. apply_repairs, reflow, pins and verify stay real.
        def inventory(original, rom, manifest):
            return [dict(source=int(m['msg'], 16), target=int(m['new_addr'], 16),
                         payload=bytes(rom[int(m['new_addr'], 16):int(m['new_addr'], 16)+m['new_len']]),
                         relocated=m, game='p1', script=True, profile=('p1_portrait',176,2))
                    for m in manifest]

        before = (bytes(rom[target:target+record['new_len']]), copy.deepcopy(record),
                  bytes(rom[0xDE7058:0xDE7060]))
        with patch('dialogue_spacing.Glyphs', return_value=Labels()), \
             patch('dialogue_spacing.inventory', side_effect=inventory):
            applied = apply_repairs(rom, original, manifest, writes, ledger)
            self.assertEqual([r['source'] for r in applied], ['000100'])
            self.assertEqual(verify(rom, original, manifest, ledger), 1)
            self.assertGreater(int(other_records[0]['new_addr'], 16), target)
            self.assertEqual((bytes(rom[target:target+record['new_len']]), record,
                              bytes(rom[0xDE7058:0xDE7060])), before)
            # Reintroducing the obsolete contract must still fail closed,
            # before any neighbor, ROM, manifest or write-log mutation.
            stale = dict(messages=[dict(source='00DD0108', profile='p1_portrait',
                         before_sha256='e3e5d4001199b0213ac81ff70b491bcd278db19737de49d7acb4a8385662dc21')])
            unchanged = (bytes(rom), copy.deepcopy(manifest), copy.deepcopy(writes))
            with self.assertRaisesRegex(ValueError, 'stale spacing specification 0xdd0108'):
                apply_repairs(rom, original, manifest, writes, stale)
            self.assertEqual((bytes(rom), manifest, writes), unchanged)
        for address, expected in full.items():
            self.assertEqual(row_bytes(rom, record, f'0x{address:06X}'), expected)
            for off,size in record['source_line_fragments'][f'0x{address:06X}']:
                validate_bteam_payload(bytes(rom[target+off:target+off+size]), load_syl(), address)
        self.assertEqual([text_segment_cells(rom[target+off:target+off+size])
                          for off,size in record['display_line_spans']], [24,42])
        self.assertEqual(record['source_fragment_joiners'], {'0xDD010A':[''], '0xDD0137':[]})
        self.assertNotIn(0xDD010A, reviewed_bteam_rows())
        self.assertEqual(reviewed_bteam_half_cells(0xDD010A), 0)

    def test_unknown_consumer_allows_only_monotone_space_removal(self):
        from dialogue_spacing import monotone_reflow
        raw='あ　い'.encode('shift_jis')+b'  r'+'う'.encode('shift_jis')+b'\0'
        change=[dict(page=0,before=['あ　い','う'],after=['あい','う'])]
        out,_=monotone_reflow(raw,'p2',Labels(),change,{'a':[[0,len(raw)]]})
        self.assertEqual(out,'あい'.encode('shift_jis')+b'  r'+'う'.encode('shift_jis')+b'\0')
        for rows in (['あ い','う '],['あい う'],['あう','い']):
            with self.assertRaises(ValueError):
                monotone_reflow(raw,'p2',Labels(),[dict(change[0],after=rows)],{'a':[[0,len(raw)]]})

    def test_reviewed_pin_requires_exact_before_and_after(self):
        from dialogue_spacing import reviewed_message_pin,sha
        rom=bytearray(b'\xff'*100);rom[10:14]=b'old\0';rom[50:54]=b'new\0'
        row=dict(source='00000A',before_target='00000A',before_bytes=4,
                 before_sha256=sha(b'old\0'),after_sha256=sha(b'new\0'))
        message=dict(msg='0x00000A',old_len=4,new_addr='0x000032',new_len=4)
        with patch('dialogue_spacing.load_ledger',return_value=dict(messages=[row])):
            self.assertTrue(reviewed_message_pin(rom,message,None))
            self.assertTrue(reviewed_message_pin(rom,message,b'old\0'.hex()))
            self.assertFalse(reviewed_message_pin(rom,message,b'bad\0'.hex()))
            rom[50]=ord('N')
            self.assertFalse(reviewed_message_pin(rom,message,None))
            rom[50]=ord('n');rom[10]=ord('O')
            self.assertFalse(reviewed_message_pin(rom,message,None))

    def test_finite_ledger_preserves_narration_and_reviewed_compounds(self):
        from dialogue_spacing import load_ledger
        rows={int(r['source'],16):r for r in load_ledger()['messages']}
        narr=rows[0xDEFD80]['final_pages'][0]
        self.assertEqual(len(narr),8);self.assertEqual(narr[5],'')
        self.assertTrue(narr[6].startswith('<NAME> 사령관님'))
        self.assertIn('맥스님의',' '.join(rows[0xA192BC]['final_pages'][0]))
        withheld={int(r['source'],16) for r in load_ledger()['withheld_unverified']}
        self.assertEqual(withheld,{0xA12428,0xA13128,0xA19350,0xA19370,0xA25738,0xA25768,0xA25788})
        self.assertFalse(withheld & rows.keys())
        for source,bad in [(0xDCAC18,'도와 주'),(0xDD184C,'도와 주'),(0xA0331C,'도와 주'),
                           (0xA28718,'도와 주'),(0xA34784,'도와 주'),(0xDD0198,'빌려 주'),
                           (0xDD041C,'빌려 주'),(0xA1F9AC,'빌려 주'),(0xA254F0,'빌려 주'),
                           (0xA310F8,'빌려 주'),(0xB83CA8,'봐 주'),(0xD94AF0,'봐 주'),
                           (0xD9E72C,'봐 주'),(0xDC5244,'봐 주')]:
            if source in rows:self.assertNotIn(bad,' '.join(' '.join(p) for p in rows[source]['final_pages']))

    def test_growth_and_separator_changes_are_explicit(self):
        raw='あい'.encode('shift_jis')+b'\0'
        pages=[dict(page=0,before=['あい'],after=['あ い'])]
        with self.assertRaises(ValueError):reflow_message(raw,'p1',Labels(),pages,2)
        after,_=reflow_message(raw,'p1',Labels(),pages,2,allow_spacing_changes=True,allow_growth=True)
        self.assertEqual(after,'あ　い'.encode('shift_jis')+b'\0')
        remove=[dict(page=0,before=['あ　い'],after=['あい'])]
        with self.assertRaises(ValueError):reflow_message(after,'p1',Labels(),remove,2)

    def test_cross_owner_space_stays_unowned(self):
        raw='あい'.encode('shift_jis')+b'\0'
        after,parts=reflow_message(raw,'p1',Labels(),[dict(page=0,before=['あい'],after=['あ い'])],2,
            {'a':[[0,2]],'b':[[2,2]]},allow_spacing_changes=True,allow_growth=True)
        self.assertEqual(parts,{'a':[[0,2]],'b':[[4,2]]})
        self.assertEqual(after[2:4],b'\x81\x40')

    def test_wait_style_name_and_choice_stay_at_glyph_anchors(self):
        raw='あ'.encode('shift_jis')+b'w2i'+'い'.encode('shift_jis')+b'0rQY\0'
        after,_=reflow_message(raw,'p1',Labels(),
            [dict(page=0,before=['あ<NAME>い',''],after=['あ <NAME>い'])],2,
            allow_spacing_changes=True,allow_growth=True)
        def anchors(payload):
            index=0;out=[]
            for t in tokenize(payload,'p1',Labels()):
                if t['advance'] and t['kind']!='space':index+=1
                if t['kind'] in ('wait','style','name','choice'):out.append((index,t['raw']))
            return out
        self.assertEqual(anchors(raw),anchors(after))
        rows=__import__('dialogue_pixel_layout').physical_rows(tokenize(after,'p1',Labels()))
        self.assertEqual([r['line'] for r in rows],[0,1])
        self.assertEqual(rows[1]['tokens'][0]['kind'],'choice')

    def test_padding_only_legacy_owner_is_preserved_unsupported(self):
        raw='あ'.encode('shift_jis')+b'  r'+'い'.encode('shift_jis')+b'\0'
        after,parts=reflow_message(raw,'p1',Labels(),
            [dict(page=0,before=['あ','い'],after=['あ い'])],2,{'missing':[[2,2]]},
            allow_spacing_changes=True,allow_growth=True)
        off,size=parts['missing'][0]
        self.assertEqual(after[off:off+size],b'  ')
        self.assertEqual(tokenize(after,'p1',Labels())[-1]['kind'],'end')

    def test_authored_wording_is_not_replaced_with_shipped_wording(self):
        self.assertEqual(_spacing_intent('상대에겐','상대는있어','상대는 있어'),('상대에겐',False))
        self.assertEqual(_spacing_intent('그 님에게!','그 님에게！','그님에게！'),('그님에게!',True))
        self.assertEqual(_spacing_intent(None,'원문','원 문'),(None,False))

    def test_original_alias_and_interior_reference_guards(self):
        original=bytearray(b'\xff'*64);original[32:36]=b'abc\0'
        struct.pack_into('<I',original,0,0x08000020)
        struct.pack_into('<I',original,4,0x08000022)
        m=dict(source=32,sites=[0]);hits={32:{0}}
        with self.assertRaisesRegex(ValueError,'interior'):
            guard_new_relocation(m,original,original,hits,{34},36)
        with self.assertRaisesRegex(ValueError,'start-pointer'):
            guard_new_relocation(m,original,original,{32:{0,8}},set(),36)
        guard_new_relocation(m,original,original,hits,set(),36)

    def test_renderer_accepts_only_exact_native_choice_operand(self):
        from renderer_text import halfwidth_violations,P1_SCRIPT
        self.assertEqual(halfwidth_violations(b'QY\0',P1_SCRIPT,b'rQY\0'),[])
        self.assertTrue(halfwidth_violations(b'QN\0',P1_SCRIPT,b'QY\0'))
        self.assertTrue(halfwidth_violations(b'YQ\0',P1_SCRIPT,b'QY\0'))

    def test_format_instructions_and_blank_fixed_rows_survive(self):
        raw=b'\x0a\x09r'+'あ'.encode('shift_jis')+b'\x0a\x09'+'い'.encode('shift_jis')+b'\0'
        after,_=reflow_message(raw,'p2',Labels(),
            [dict(page=0,before=['','あい'],after=['','あ い'])],6,
            allow_spacing_changes=True,allow_growth=True,allow_blank_rows=True)
        self.assertEqual(after.count(b'\x0a\x09'),2)
        rows=__import__('dialogue_pixel_layout').physical_rows(tokenize(after,'p2',Labels()))
        self.assertEqual([''.join(t['text'] for t in r['tokens']) for r in rows],['','あ　い'])

    def test_bteam_approval_is_exact_and_does_not_clear_a_retained_residual(self):
        from dialogue_spacing import reviewed_bteam_match
        row=dict(baseline='baseline',before='기존문장',after='기존 문장',
                 classification='retained-residual',retained_authorities=['기존문장'])
        with patch('dialogue_spacing.reviewed_bteam_rows',return_value={123:row}):
            self.assertTrue(reviewed_bteam_match(123,'기존문장','기존 문장',restored=False))
            self.assertFalse(reviewed_bteam_match(123,'baseline','기존 문장',restored=True))
            self.assertFalse(reviewed_bteam_match(123,'기존문장','기존문장',restored=False))
            self.assertFalse(reviewed_bteam_match(124,'기존문장','기존 문장',restored=False))

    def test_extra_first_row_cell_requires_exact_reviewed_portrait_fragment(self):
        from build_korean_full import validate_bteam_payload
        raw=b'\x88\x40'*23
        row=dict(profile='p1_portrait',final_fragment_hex=[raw.hex()],final_fragment_half_cells=[46])
        with patch('dialogue_spacing.reviewed_bteam_rows',return_value={123:row}):
            validate_bteam_payload(raw,{0x8840:'가'},123)
            with self.assertRaisesRegex(AssertionError,'44 half-cells'):
                validate_bteam_payload(raw[:-2]+b'\x88\x41',{0x8840:'가',0x8841:'각'},123)
            row['profile']='p1_co_bio'
            with self.assertRaisesRegex(AssertionError,'44 half-cells'):
                validate_bteam_payload(raw,{0x8840:'가'},123)

    def test_native_protected_interior_writers_keep_separate_intent(self):
        original=bytearray(b'\xff'*128)
        payload=b'\x0a\x09'+'あい'.encode('shift_jis')+b'\0'
        original[64:64+len(payload)]=payload
        writes=[[66,2,2,payload[2:4].hex(),None,'first',0,'script:first'],
                [68,2,2,payload[4:6].hex(),None,'protected',0,'bteam-restored']]
        m=dict(target=64,source=64,game='p1',payload=payload)
        with patch('dialogue_spacing.Glyphs',return_value=Labels()):
            owners,texts,spans=_native_provenance(m,original,writes,original)
        self.assertEqual(texts['0x000044'],'protected')
        self.assertEqual(owners['0x000042'],[[2,2]])
        self.assertEqual(owners['0x000044'],[[4,2]])
        broken=writes+[[69,1,1,payload[5:6].hex(),None,None,None,'raw']]
        with patch('dialogue_spacing.Glyphs',return_value=Labels()):
            with self.assertRaisesRegex(ValueError,'splits token'):
                _native_provenance(m,original,broken,original)

    def fixture(self):
        from dialogue_pixel_layout import sha
        original=bytearray(b'\xff'*1024);rom=bytearray(original)
        raw='あい'.encode('shift_jis')+b'\0'
        original[256:261]=raw;rom[512:517]=raw
        struct.pack_into('<I',original,0,0x08000100)
        struct.pack_into('<I',rom,0,0x08000200)
        record=dict(msg='0x000100',status='relocated',new_addr='0x000200',new_len=5,old_len=5,
                    ptr_off='0x000000',ptr_sites=['0x000000'],lines=1,fixed=[],
                    line_spans={'0x000100':[0,5]},source_spans={'0x000100':5},source_texts={'0x000100':'あい'})
        binding=[512,5,5,'',None,None,None,'repoint:0x000100',
                 dict(source_spans=record['source_spans'],source=256,old_len=5,ptr_sites=[0])]
        writes=[binding,[512,5,5,raw.hex(),None,'あい',0,'legacy-owner']]
        message=dict(source=256,target=512,sites=[0],game='p1',payload=raw,relocated=record,
                     script=True,profile=('p1_portrait',176,2))
        ledger=dict(schema=1,messages=[dict(source='000100',profile='p1_portrait',before_sha256=sha(raw),after_sha256=sha('あ　い'.encode('shift_jis')+b'\0'),
                       pages=[dict(page=0,before=['あい'],after=['あ い'])],source_fragment_joiners={'0x000100':[]})])
        return original,rom,[record],writes,message,ledger

    def apply_fixture(self,original,rom,manifest,writes,message,ledger):
        with patch('dialogue_spacing.Glyphs',return_value=Labels()), \
             patch('dialogue_spacing.inventory',return_value=[message]), \
             patch('dialogue_repoint._line_index',return_value={}), \
             patch('dialogue_spacing.ARENA_START',768),patch('dialogue_spacing.ARENA_END',1024):
            return apply_repairs(rom,original,manifest,writes,ledger)

    def test_growth_updates_one_binding_and_retires_abandoned_owner(self):
        from qa_dialogue_jamming import validate_manifest,final_owner_spans
        original,rom,manifest,writes,message,ledger=self.fixture()
        old=bytes(rom[512:517])
        self.apply_fixture(original,rom,manifest,writes,message,ledger)
        self.assertEqual(bytes(rom[512:517]),old)
        self.assertEqual(manifest[0]['new_addr'],'0x000300')
        self.assertEqual(struct.unpack_from('<I',rom)[0],0x08000300)
        self.assertEqual(len([w for w in writes if w[7].startswith('repoint:')]),1)
        validate_manifest(rom,manifest,original,writes)
        self.assertNotIn(512,final_owner_spans(writes,len(rom),hangul_only=False)[0])

    def test_latest_authored_writer_survives_without_erasing_historical_intent(self):
        from qa_dialogue_jamming import validate_manifest,rendered_rows
        original,rom,manifest,writes,message,ledger=self.fixture()
        manifest[0]['source_texts']['0x000100']='historical mismatch'
        ledger['messages'][0]['pages'][0]['after']=['あ','い']
        ledger['messages'][0]['after_sha256']=__import__('dialogue_pixel_layout').sha('あ'.encode('shift_jis')+b'r'+'い'.encode('shift_jis')+b'\0')
        ledger['messages'][0]['source_fragment_joiners']={'0x000100':['']}
        self.apply_fixture(original,rom,manifest,writes,message,ledger)
        self.assertEqual(manifest[0]['source_texts']['0x000100'],'historical mismatch')
        from qa_dialogue_jamming import final_owner_spans
        with patch('qa_dialogue_jamming.final_owner_spans',side_effect=lambda w,n,**kw:final_owner_spans(w,n,hangul_only=False)):
            self.assertEqual(rendered_rows(rom,manifest,writes,original)[0][0]['intended'],'あい')
        intent=next(w for w in writes if w[7]=='dialogue-spacing-final-intent')
        intent[8]['fragments']=[]
        with self.assertRaisesRegex(ValueError,'envelope'):
            validate_manifest(rom,manifest,original,writes)

    def test_stale_duplicate_or_pointer_failure_does_not_mutate_batch(self):
        for defect in ('stale','duplicate','pointer','output'):
            original,rom,manifest,writes,message,ledger=self.fixture()
            if defect=='stale':ledger['messages'][0]['before_sha256']='bad'
            if defect=='duplicate':writes.append(copy.deepcopy(writes[0]))
            if defect=='pointer':struct.pack_into('<I',rom,0,0x08000204)
            if defect=='output':ledger['messages'][0]['after_sha256']='bad'
            before=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaises(ValueError):
                self.apply_fixture(original,rom,manifest,writes,message,ledger)
            self.assertEqual((bytes(rom),manifest,writes),before)

    def test_unattributed_p2_family_and_unknown_geometry_reject_reflow(self):
        for consumers,profile in (([],('p2_portrait',176,2)),
                                  ([dict(consumer='unverified')],('p2_unverified_consumer',None,None))):
            original,rom,manifest,writes,message,ledger=self.fixture()
            message.update(game='p2',consumers=consumers,profile=profile)
            ledger['messages'][0]['profile']=profile[0]
            before=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaises(ValueError):
                self.apply_fixture(original,rom,manifest,writes,message,ledger)
            self.assertEqual((bytes(rom),manifest,writes),before)


if __name__=='__main__':unittest.main()
