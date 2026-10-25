"""Synthetic relocation only; real source precedence and fragment consumers."""
import ast
import collections
import copy
import csv
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import build_korean_full as builder
import df1eec_contract as c
from dialogue_repoint import repoint_messages, text_segment_cells
from repoint_source_rows import row_bytes


class ContractTests(unittest.TestCase):
    def fixture(self, mutation=None):
        orig=bytearray(b'\xff'*0x1000000)
        orig[c.MESSAGE:c.END]=c.NATIVE
        orig[c.SITE-4:c.SITE+4]=bytes.fromhex('19000000ec1edf08')
        orig[c.END:c.END+64]=c.NEXT_NATIVE
        # This normal message is processed FIRST (pointer sort), and really relocates.
        early,owner,site=0xDF1000,0xDF1002,0x100
        orig[early:early+8]=bytes.fromhex('0a0982a06b0a0000')
        orig[site:site+4]=(0x08000000+early).to_bytes(4,'little')
        rom=bytearray(orig)
        rom[c.COMPANION:c.TAIL]=c.ROWS[c.COMPANION][:-2]
        rows={**c.ROWS,owner:bytes.fromhex('8def')}
        texts={**c.TEXTS,owner:'수'}
        lines={c.FIRST:(42,''),c.COMPANION:(14,''),owner:(2,'')}
        opts=dict(line_layouts={c.FIRST:c.LAYOUT},page_reflows={c.MESSAGE:c.REFLOW},
                  free_start=0xA3D000,free_end=0xA40000,
                  extra_messages={early:[site],c.MESSAGE:[c.SITE],c.END:[]})
        if mutation: mutation(orig,rom,rows,texts,lines,opts)
        before=bytes(rom); writes=[['existing-builder-write']]; saved=copy.deepcopy(writes)
        try:
            manifest,stats=repoint_messages(rom,orig,fixable=lambda a: True,
                fixed_bytes=rows.__getitem__,source_text=texts.__getitem__,fit_level_dlg=lambda a:6,
                decode_text=lambda raw:'수',cell_width=lambda a:text_segment_cells(rows[a]),
                slots={},line_index=lines,table_offsets=[],write_log=writes,**opts)
        except (AssertionError,ValueError):
            self.assertEqual(bytes(rom),before);self.assertEqual(writes,saved)
            raise
        self.assertEqual(stats['relocated'],2)
        m=next(m for m in manifest if m['msg']=='0xDF1EEC')
        target=int(m['new_addr'],16)
        c.validate(rom[target:target+74],m)
        expected=bytearray(before)
        e=next(m for m in manifest if m['msg']=='0xDF1000')
        ep=bytes.fromhex('0a098def6b0a0000')
        expected[int(e['new_addr'],16):int(e['new_addr'],16)+8]=ep
        expected[site:site+4]=(0x08000000+int(e['new_addr'],16)).to_bytes(4,'little')
        expected[target:target+74]=c.PAYLOAD
        expected[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
        self.assertEqual(rom,expected)
        return orig,rom,m,writes

    def test_success_and_source_consumers(self):
        orig,rom,m,writes=self.fixture()
        for a,raw in c.ROWS.items():self.assertEqual(row_bytes(rom,m,f'0x{a:06X}'),raw)
        self.assertEqual(writes[-1][8]['source_spans'],c.METADATA['source_spans'])
        self.assertEqual([text_segment_cells(c.PAYLOAD[o:o+n]) for o,n in m['display_line_spans']],[38,28])
        from qa_renderer_text import payloads, check
        emitted={a:raw for a,profile,raw,native in payloads(rom,orig,[writes[-1]],[m])}
        self.assertEqual(emitted,c.ROWS)
        self.assertEqual(check(rom,orig,[writes[-1]],[m]),(2,[]))
        from audit_address_text_overrides import source_row_bytes
        for a,raw in c.ROWS.items():self.assertEqual(source_row_bytes(rom,m,f'0x{a:06X}'),raw)
        from qa_bteam_drift import check_rom
        read_bytes,read_text=Path.read_bytes,Path.read_text
        def text(p,*a,**kw):
            if str(p)=='fixture-manifest':return json.dumps([m])
            if str(p)=='fixture-writes':return json.dumps(writes[1:])
            return read_text(p,*a,**kw)
        with patch.object(Path,'read_bytes',lambda p:bytes(rom) if str(p)=='fixture-rom' else read_bytes(p)),patch.object(Path,'read_text',text):
            self.assertEqual(check_rom({'overrides':{f'0x{a:08X}':t for a,t in c.TEXTS.items()}},'fixture-rom','fixture-writes','fixture-manifest'),[])

    def test_source_precedence_real_legacy_and_authorities(self):
        tree=ast.parse(Path(builder.__file__).read_text())
        funcs=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ('_rp_dlg','_rp_fixable','_rp_fit_level','_rp_fixed_bytes')]
        codes={s:int(v,16) for s,v in json.loads(Path(builder.SYLCODE).read_text()).items()}
        ns=dict(vars(builder),syl_to_code=codes,unmapped=collections.Counter(),
                slots={c.FIRST:42,c.COMPANION:14},_rp_lossless_requested=set())
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'<real builder functions>','exec'),ns)
        legacy=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BTEAM_PREVIOUS_KOREAN_TEXT' for t in n.targets) and isinstance(n.value,ast.Dict))
        self.assertEqual(legacy[c.FIRST],'수도　점령／적　전멸　승리')
        # The existing decisions-based RESTORE filter already drops this key.
        # Exercise the real callback with the actual historical literal
        # present as well, so precedence cannot depend on that filtering.
        ns['BTEAM_PREVIOUS_KOREAN_TEXT']=legacy
        overrides=json.loads((Path(builder.BASE)/'data/dialogue_overrides.json').read_text())
        baseline=json.loads((Path(builder.BASE)/'data/bteam_baseline.json').read_text())
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[c.FIRST],c.TEXTS[c.FIRST])
        self.assertEqual(baseline['overrides']['0x00DF1EEE'],c.TEXTS[c.FIRST])
        with (Path(builder.BASE)/'data/translation_for_import.csv').open() as f:
            csvrows={int(r['address'],16):r for r in csv.DictReader(f)}
        self.assertEqual(csvrows[c.COMPANION]['korean'],'힘내야 해!')
        for a,t in c.TEXTS.items():
            self.assertEqual(overrides[f'0x{a:08X}'],t)
            self.assertEqual(ns['_rp_dlg'](a),t)
            self.assertTrue(ns['_rp_fixable'](a));self.assertEqual(ns['_rp_fit_level'](a),6)
            self.assertEqual(ns['_rp_fixed_bytes'](a),c.ROWS[a])
        self.assertEqual(ns['_rp_lossless_requested'],{c.COMPANION})
        self.assertNotIn(c.FIRST,builder.BTEAM_ROUND2_RESIDUALS)
        assignments={n.targets[0].id:n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
        self.assertIn(c.FIRST,ast.literal_eval(assignments['_restored_relocated_residuals']))
        self.assertNotIn(c.FIRST,ast.literal_eval(assignments['_allowed_wide_skips']))

    def test_lossless_fulfillment_requires_relocated_fixed_owner(self):
        _,rom,record,_=self.fixture()
        # Prove the fulfilled owner has all authored bytes, including space/bang.
        self.assertEqual(row_bytes(rom,record,'0xDF1F1B'),c.ROWS[c.COMPANION])
        tree=ast.parse(Path(builder.__file__).read_text())
        accounting=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id in
                            ('_rp_fixed_addresses','_rp_unfulfilled') for t in n.targets)]
        self.assertEqual(len(accounting),2)
        code=compile(ast.Module(body=accounting,type_ignores=[]),'<builder accounting>','exec')
        other=0xDF0000
        for status,fixed,missing in (
                ('relocated',record['fixed'],{other}),
                ('skipped',record['fixed'],{other,c.COMPANION}),
                ('relocated',['0xDF1EEE'],{other,c.COMPANION})):
            with self.subTest(status=status,fixed=fixed):
                candidate={**record,'status':status,'fixed':fixed}
                requested={other,c.COMPANION}
                ns=dict(_rp_manifest=[candidate],_rp_lossless_requested=requested.copy())
                exec(code,ns)
                self.assertEqual(ns['_rp_lossless_requested'],requested)
                self.assertEqual(ns['_rp_unfulfilled'],sorted(missing))

    def test_native_caller_controls_refs_atomic_before_earlier_message(self):
        for native,positions in ((True,range(c.MESSAGE,c.END)),(False,[c.MESSAGE,c.MESSAGE+1,0xDF1F18,0xDF1F19,0xDF1F1A,c.TAIL,c.TAIL+1,c.TAIL+2])):
            for address in positions:
                def mutate(o,r,*args): (o if native else r)[address]^=1
                with self.subTest(native=native,address=hex(address)),self.assertRaises(AssertionError):self.fixture(mutate)
        for native in (True,False):
            for a in range(c.SITE-4,c.SITE+4):
                def mutate(o,r,*args): (o if native else r)[a]^=1
                with self.subTest(caller=a,native=native),self.assertRaises(AssertionError):self.fixture(mutate)
        for target in (c.MESSAGE,c.FIRST+1,c.TAIL,c.END-1):
            def mutate(o,r,*args):o[0x200:0x204]=(0x08000000+target).to_bytes(4,'little')
            with self.subTest(reference=target),self.assertRaises(AssertionError):self.fixture(mutate)

    def test_source_layout_owners_and_end_fail_before_first_write(self):
        for case in ('missing','extra','tail','slot','companion_slot','csv','text','comma','space','bang','layout','reflow','next','sites','skip','capacity','bounds','next_native','missing_message'):
            def mutate(o,r,rows,texts,lines,opts):
                if case=='missing':lines.pop(c.COMPANION)
                if case=='extra':lines[c.FIRST+2]=(2,'')
                if case=='tail':lines[c.TAIL]=(3,'')
                if case=='slot':lines[c.FIRST]=(40,'')
                if case=='companion_slot':lines[c.COMPANION]=(16,'')
                if case=='csv':texts[c.COMPANION]='힘내야 해!'
                if case=='text':texts[c.FIRST]='수도 점령'
                if case=='comma':rows[c.FIRST]=rows[c.FIRST].replace(b'\x81\x41',b'',1)
                if case=='space':rows[c.FIRST]=rows[c.FIRST].replace(b'\x81\x40',b'',1)
                if case=='bang':rows[c.COMPANION]=rows[c.COMPANION][:-2]
                if case=='layout':opts['line_layouts'][c.FIRST]=(c.LAYOUT[0][:-2],c.LAYOUT[1])
                if case=='reflow':opts['page_reflows'][c.MESSAGE]=(*c.REFLOW[:4],b'\x81\x40')
                if case=='next':opts['extra_messages'][c.END-1]=[]
                if case=='sites':opts['extra_messages'][c.MESSAGE]=[c.SITE,c.SITE]
                if case=='skip':opts['skip_messages']={c.MESSAGE}
                if case=='capacity':opts['free_end']=opts['free_start']+73
                if case=='bounds':opts['free_end']=len(r)+4
                if case=='next_native':o[c.END]^=1
                if case=='missing_message':opts['extra_messages'].pop(c.MESSAGE)
            with self.subTest(case=case),self.assertRaises(AssertionError):self.fixture(mutate)

    def test_exact_manifest_rejects_virtual_joiners_overlap_gap_and_controls(self):
        for field,value in [('source_fragment_joiners',{'0xDF1EEE':['8140'],'0xDF1F1B':[]}),
            ('line_spans',{'0xDF1EEE':[2,38],'0xDF1F1B':[43,28]}),
            ('source_line_fragments',{'0xDF1EEE':[[2,38],[43,12]],'0xDF1F1B':[[55,16]]}),
            ('source_line_fragments',{'0xDF1EEE':[[2,38],[43,10]],'0xDF1F1B':[[43,28]]}),
            ('layout_gaps',[]),('layout_controls',{'0xDF1EEE':'720a09'}),('display_line_spans',[[2,48],[55,16]])]:
            m=copy.deepcopy(c.METADATA);m[field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):c.validate(c.PAYLOAD,m)
            validator=c.validate
            with patch.object(c,'validate',side_effect=lambda payload,record:validator(payload,m)),self.assertRaises(AssertionError):self.fixture()
        for offset in (38,53,54,69):
            bad=c.PAYLOAD[:offset]+c.PAYLOAD[offset+2:]
            with self.assertRaises(AssertionError):c.validate(bad,c.METADATA)

    def test_downstream_spacing_keeps_restoration_and_rejects_old_contract(self):
        from test_dialogue_spacing import SpacingTests, Labels
        from dialogue_spacing import apply_repairs, verify
        original, rom, record, writes = self.fixture()
        small_original, small_rom, others, other_writes, _, neighbor = SpacingTests().fixture()
        original[:1024], rom[:1024] = small_original, small_rom
        writes = writes[1:] + other_writes
        manifest = [record] + others
        ledger = dict(messages=neighbor['messages'])
        ledger['messages'][-1]['final_pages'] = [['あ い']]
        def inventory(o, r, records):
            return [dict(source=int(m['msg'],16), target=int(m['new_addr'],16),
                payload=bytes(r[int(m['new_addr'],16):int(m['new_addr'],16)+m['new_len']]),
                relocated=m,game='p1',script=True,profile=('p1_portrait',176,2)) for m in records]
        before = (bytes(rom[0xA3D008:0xA3D008+len(c.PAYLOAD)]),copy.deepcopy(record))
        with patch('dialogue_spacing.Glyphs',return_value=Labels()), \
             patch('dialogue_spacing.inventory',side_effect=inventory):
            self.assertEqual(len(apply_repairs(rom,original,manifest,writes,ledger)),1)
            self.assertEqual(verify(rom,original,manifest,ledger),1)
            self.assertEqual((bytes(rom[0xA3D008:0xA3D008+len(c.PAYLOAD)]),record),before)
            stale=dict(messages=[dict(source='00DF1EEC',profile='p1_portrait',
                before_sha256='3730051121f4653710d464368d21a2fad023d0a1a7732090eb4bd75ee277c5bc')])
            unchanged=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaisesRegex(ValueError,'stale spacing specification 0xdf1eec'):
                apply_repairs(rom,original,manifest,writes,stale)
            self.assertEqual((bytes(rom),manifest,writes),unchanged)


    @unittest.skipUnless(os.environ.get('AW_GLYPH_ROM') and os.environ.get('AW_NATIVE_ROM'), 'Read-only glyph/native fixtures not supplied')
    def test_real_glyph_width_and_native_contract(self):
        from hashlib import sha256
        from dialogue_pixel_layout import audit
        native=Path(os.environ['AW_NATIVE_ROM']).read_bytes()
        font=Path(os.environ['AW_GLYPH_ROM']).read_bytes()
        self.assertEqual(sha256(native).hexdigest(),'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
        self.assertEqual(sha256(font).hexdigest(),'205ef9a66a4540eccd22c09f62d6f0e850530fbd4c1a1f502b3eaab64226e787')
        c.preflight(native,native,[(c.FIRST,42),(c.COMPANION,14)],c.END,[c.SITE],
                    c.ROWS.__getitem__,c.TEXTS.__getitem__,lambda a:True,lambda a:6,c.LAYOUT,c.REFLOW)
        entry=dict(source=c.MESSAGE,target=0xA3D000,payload=c.PAYLOAD,game='p1',script=True,
                   profile=('p1_portrait',176,2),sites=[c.SITE])
        with patch('dialogue_pixel_layout.inventory',return_value=[entry]):
            result=audit(native,font,[])
        self.assertFalse(result['errors'])
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in result['rows']],[(152,184),(112,176)])
        self.assertTrue(all(not r['overflow'] and not r['row_overflow'] and not r['glyph_errors'] for r in result['rows']))



if __name__=='__main__':unittest.main()
