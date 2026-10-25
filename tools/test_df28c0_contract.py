"""Scoped synthetic writes, actual builder callbacks and R1 row/message regression."""
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
import df28c0_contract as c
from dialogue_repoint import repoint_messages, text_segment_cells
from repoint_source_rows import row_bytes


class ContractTests(unittest.TestCase):
    def prepare_fixture(self, mutation=None, callbacks=None):
        orig=bytearray(b'\xff'*0x1000000)
        orig[c.MESSAGE:c.END]=c.NATIVE
        orig[c.END:c.END+64]=c.NEXT_NATIVE
        orig[c.SITE-4:c.SITE+4]=bytes.fromhex('19000000c028df08')
        early,owner,site=0xDF1000,0xDF1002,0x100
        orig[early:early+8]=bytes.fromhex('0a0982a06b0a0000')
        orig[site:site+4]=(0x08000000+early).to_bytes(4,'little')
        rom=bytearray(orig)
        rows={**c.ROWS,owner:bytes.fromhex('8def')}
        texts={**c.TEXTS,owner:'수'}
        lines={c.FIRST:(42,''),c.COMPANION:(14,''),owner:(2,'')}
        opts=dict(require_df28c0=True,line_layouts={c.FIRST:c.LAYOUT},page_reflows={c.MESSAGE:c.REFLOW},free_start=0xA3D000,free_end=0xA40000,
                  extra_messages={early:[site],c.MESSAGE:[c.SITE],c.END:[]})
        if mutation: mutation(orig,rom,rows,texts,lines,opts)
        before=bytes(rom); writes=[['existing-builder-write']]; saved=copy.deepcopy(writes)
        cb=dict(fixable=lambda a:True,fixed_bytes=rows.__getitem__,source_text=texts.__getitem__,
                fit_level_dlg=lambda a:99 if a==c.FIRST else 6)
        if callbacks: cb.update(callbacks)
        kwargs=dict(decode_text=lambda raw:'수',
                    cell_width=lambda a:text_segment_cells(rows[a]),slots={},line_index=lines,
                    table_offsets=[],write_log=writes,**cb,**opts)
        return orig,rom,kwargs,before,writes,saved

    def assert_rejected(self, mutation=None, callbacks=None, pattern=None):
        orig,rom,kwargs,before,writes,saved=self.prepare_fixture(mutation,callbacks)
        expected=(self.assertRaisesRegex(AssertionError,pattern) if pattern
                  else self.assertRaises(AssertionError))
        with expected:
            repoint_messages(rom,orig,**kwargs)
        with self.subTest(preservation='ROM'):
            self.assertEqual(bytes(rom),before)
        with self.subTest(preservation='write_log'):
            self.assertEqual(writes,saved)

    def fixture(self, mutation=None, callbacks=None):
        orig,rom,kwargs,before,writes,_=self.prepare_fixture(mutation,callbacks)
        manifest,stats=repoint_messages(rom,orig,**kwargs)
        site=0x100
        self.assertEqual(stats['relocated'],2)
        m=next(m for m in manifest if m['msg']=='0xDF28C0')
        target=int(m['new_addr'],16)
        c.validate(rom[target:target+66],m)
        expected=bytearray(before)
        e=next(m for m in manifest if m['msg']=='0xDF1000')
        expected[int(e['new_addr'],16):int(e['new_addr'],16)+8]=bytes.fromhex('0a098def6b0a0000')
        expected[site:site+4]=(0x08000000+int(e['new_addr'],16)).to_bytes(4,'little')
        expected[target:target+66]=c.PAYLOAD
        expected[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
        self.assertEqual(rom,expected)
        return orig,rom,m,writes

    def callbacks(self):
        tree=ast.parse(Path(builder.__file__).read_text())
        names=('_rp_dlg','_rp_ov','_rp_fixable','_rp_fit_level','_rp_fixed_bytes')
        funcs=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
        codes={s:int(v,16) for s,v in json.loads(Path(builder.SYLCODE).read_text()).items()}
        overrides=json.loads((Path(builder.BASE)/'data/dialogue_overrides.json').read_text())
        ns=dict(vars(builder),syl_to_code=codes,unmapped=collections.Counter(),slots={c.FIRST:42,c.COMPANION:14},
                _rp_lossless_requested=set(),_rp_fixed_fragments=set(),_rp_script_owners={},
                _dlg_ov=overrides,_display_ov=builder.load_display_overrides(),_editor_intents={},_rp_bteam={c.FIRST},
                required_script_repoints=set())
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'<actual builder callbacks>','exec'),ns)
        return tree,ns

    def test_r1_actual_builder_row_set_and_separate_manifest_gate(self):
        tree,ns=self.callbacks()
        _,_,m,_=self.fixture()
        assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id in ('_rp_fixed_addresses','_rp_unfulfilled',
                         '_restored_relocated_residuals') for t in n.targets)]
        code=compile(ast.Module(body=assignments,type_ignores=[]),'<builder success accounting>','exec')
        restored=next(ast.literal_eval(n.value) for n in assignments
                      if n.targets[0].id=='_restored_relocated_residuals')
        self.assertIn(c.FIRST,restored);self.assertNotIn(c.MESSAGE,restored)
        others=dict(msg='0x000001',status='relocated',fixed=[hex(a) for a in restored-{c.FIRST}])
        for records,success in (([others,m],True),([others],False)):
            env=dict(_rp_manifest=records,_rp_lossless_requested={0xD94479})
            exec(code,env)
            self.assertEqual(restored <= env['_rp_fixed_addresses'],success)
            self.assertEqual(env['_rp_unfulfilled'],[0xD94479])
        for records in ([],[m,m],[dict(m,fixed=['0xDF28C0'])],[dict(m,ptr_sites=['0xE114F4'])],
                        [dict(m,status='skip_forced')]):
            with self.assertRaises(AssertionError):c.assert_manifest(records)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='_assert_df28c0_manifest']
        self.assertEqual(len(calls),1)
        required=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
                  for k in n.keywords if k.arg=='require_df28c0' and isinstance(k.value,ast.Constant) and k.value.value is True]
        self.assertEqual(len(required),1)
        for records in ([m],[]):
            env=dict(_assert_df28c0_manifest=c.assert_manifest,_rp_manifest=records)
            run=lambda:exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(value=calls[0])],type_ignores=[])),'builder','exec'),env)
            if records:run()
            else:
                with self.assertRaises(AssertionError):run()

    @unittest.skipUnless(os.environ.get('AW_DF28C0_BASELINE'), 'Read-only baseline not supplied')
    def test_baseline_lossless_arrays_and_actual_pixel_consumer(self):
        from hashlib import sha256
        from dialogue_pixel_layout import audit
        root=Path(os.environ['AW_DF28C0_BASELINE'])
        original=(root/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        candidate=(root/'output/game_wars_korean_e10d78_candidate.gba').read_bytes()
        lossless_raw=(root/'temp/repoint_lossless_requests.json').read_bytes()
        self.assertEqual(sha256(lossless_raw).hexdigest(),'93c235df8a6cba7a620cd1509268ef97b10536ac5f001935a2e24d54dbfb584a')
        self.assertEqual(sha256(original).hexdigest(),'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
        self.assertEqual(sha256(candidate).hexdigest(),'cf24d8f31e341480793d13614b49f2bca5b6d42af207189a0b2135eb1e92c046')
        lossless=json.loads(lossless_raw); saved=copy.deepcopy(lossless)
        manifest=json.loads((root/'temp/repoint_manifest.json').read_text())
        tree,ns=self.callbacks()
        ns['_rp_lossless_requested']={int(a,16) for a in lossless['requested']}
        self.assertEqual(len(ns['_rp_lossless_requested']),1710)
        c.preflight(original,candidate,[(c.FIRST,42),(c.COMPANION,14)],c.END,[c.SITE],ns['_rp_fixed_bytes'],
                    ns['_rp_dlg'],ns['_rp_fixable'],ns['_rp_fit_level'],c.LAYOUT,c.REFLOW)
        self.assertEqual(ns['_rp_fit_level'](c.FIRST),99)
        self.assertEqual(ns['_rp_fit_level'](c.COMPANION),6)
        self.assertEqual(sorted(ns['_rp_lossless_requested']),[int(a,16) for a in saved['requested']])
        ns['_rp_manifest']=manifest+[dict(c.METADATA,new_addr='0xA3D000')]
        accounting=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and
                    any(isinstance(t,ast.Name) and t.id in ('_rp_fixed_addresses','_rp_unfulfilled') for t in n.targets)]
        exec(compile(ast.Module(body=accounting,type_ignores=[]),'accounting','exec'),ns)
        self.assertEqual([f'0x{a:08X}' for a in ns['_rp_unfulfilled']],saved['unfulfilled'])
        self.assertEqual(len(saved['unfulfilled']),9)
        self.assertEqual(lossless,saved)
        # In-memory checker fixture, NOT a new ROM build or runtime candidate.
        from qa_df28c0_preservation import validate as preserved
        hypothetical=bytearray(candidate);target=0xFF0000
        hypothetical[target:target+66]=c.PAYLOAD
        hypothetical[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
        self.assertEqual(preserved(candidate,hypothetical,manifest,
            [m for m in manifest if int(m['msg'],16)!=c.MESSAGE]+[dict(c.METADATA,new_addr=hex(target))])['preserved'],2980)

        entry=dict(source=c.MESSAGE,target=0xA3D000,payload=c.PAYLOAD,game='p1',script=True,
                   profile=('p1_portrait',176,2),sites=[c.SITE])
        with patch('dialogue_pixel_layout.inventory',return_value=[entry]):result=audit(original,candidate,[])
        self.assertFalse(result['errors'])
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in result['rows']],[(152,184),(80,176)])
        self.assertTrue(all(not r['overflow'] and not r['row_overflow'] and not r['glyph_errors'] for r in result['rows']))
        self.assertTrue(all(not r['caption_overlap'] for r in result['rows']))
        entry['payload']=bytes.fromhex('0a09')+c.ROWS[c.FIRST]+bytes.fromhex('720a09')+c.ROWS[c.COMPANION]+bytes.fromhex('6b0a00')
        with patch('dialogue_pixel_layout.inventory',return_value=[entry]):naive=audit(original,candidate,[])
        self.assertEqual(naive['rows'][0]['advance_px'],192)
        self.assertTrue(naive['rows'][0]['overflow'])


    def test_success_and_source_consumers(self):
        orig,rom,m,writes=self.fixture()
        for a,raw in c.ROWS.items():self.assertEqual(row_bytes(rom,m,f'0x{a:06X}'),raw)
        self.assertEqual(writes[-1][8]['source_spans'],c.METADATA['source_spans'])
        self.assertEqual([text_segment_cells(c.PAYLOAD[o:o+n]) for o,n in m['display_line_spans']],[38,20])
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
            stale=dict(messages=[dict(source='00DF28C0',profile='p1_portrait',
                before_sha256='3730051121f4653710d464368d21a2fad023d0a1a7732090eb4bd75ee277c5bc')])
            unchanged=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaisesRegex(ValueError,'stale spacing specification 0xdf28c0'):
                apply_repairs(rom,original,manifest,writes,stale)
            self.assertEqual((bytes(rom),manifest,writes),unchanged)




    def test_native_caller_controls_far_refs_atomic_before_earlier_message(self):
        for native,positions in ((True,range(c.MESSAGE,c.END)),
                (False,[c.MESSAGE,c.MESSAGE+1,0xDF28EC,0xDF28ED,0xDF28EE,c.TAIL,c.TAIL+1,c.TAIL+2])):
            for address in positions:
                def mutate(o,r,*args): (o if native else r)[address]^=1
                with self.subTest(native=native,address=hex(address)):self.assert_rejected(mutate)
        for native in (True,False):
            for address in range(c.SITE-4,c.SITE+4):
                def mutate(o,r,*args): (o if native else r)[address]^=1
                with self.subTest(caller=address,native=native):self.assert_rejected(mutate)
        for target in (c.MESSAGE,c.FIRST,c.FIRST+1,c.TAIL,c.END-1):
            def mutate(o,r,*args):o[0xF80000:0xF80004]=(0x08000000+target).to_bytes(4,'little')
            with self.subTest(reference=target):self.assert_rejected(mutate)

    def test_source_configuration_preflight_atomic(self):
        for case in ('missing_owner','both_missing','extra','tail','slot','companion_slot','csv','text',
                     'comma','space','bang','layout','reflow','next','sites','skip','capacity','bounds',
                     'next_native','missing_message','wide','header','level'):
            def mutate(o,r,rows,texts,lines,opts):
                if case=='missing_owner':lines.pop(c.COMPANION)
                if case=='both_missing':
                    lines.pop(c.FIRST);lines.pop(c.COMPANION);opts['extra_messages'].pop(c.MESSAGE)
                if case=='extra':lines[c.FIRST+2]=(2,'')
                if case=='tail':lines[c.TAIL]=(3,'')
                if case=='slot':lines[c.FIRST]=(40,'')
                if case=='companion_slot':lines[c.COMPANION]=(16,'')
                if case=='csv':texts[c.COMPANION]='힘내!'
                if case=='text':texts[c.FIRST]='수도 점령'
                if case=='comma':rows[c.FIRST]=rows[c.FIRST].replace(bytes.fromhex('8141'),b'',1)
                if case=='space':rows[c.FIRST]=rows[c.FIRST].replace(bytes.fromhex('8140'),b'',1)
                if case=='bang':rows[c.COMPANION]=rows[c.COMPANION][:-2]
                if case=='layout':opts['line_layouts'][c.FIRST]=(c.LAYOUT[0][:-2],c.LAYOUT[1])
                if case=='reflow':opts['page_reflows'][c.MESSAGE]=(*c.REFLOW[:4],bytes.fromhex('8140'))
                if case=='next':opts['extra_messages'][c.END-1]=[]
                if case=='sites':opts['extra_messages'][c.MESSAGE]=[c.SITE,c.SITE]
                if case=='skip':opts['skip_messages']={c.MESSAGE}
                if case=='capacity':opts['free_end']=opts['free_start']+65
                if case=='bounds':opts['free_end']=len(r)+4
                if case=='next_native':o[c.END]^=1
                if case=='missing_message':opts['extra_messages'].pop(c.MESSAGE)
                if case=='wide':opts['allowed_wide_skips']={c.FIRST}
                if case=='header':opts['max_header_gap']=1
                if case=='level':opts['min_level']=100
            with self.subTest(case=case):self.assert_rejected(mutate)
        for cb in (dict(fixable=lambda a:False),dict(fit_level_dlg=lambda a:6),dict(source_text=None)):
            self.assert_rejected(callbacks=cb)

    def test_actual_callbacks_keep_authority_and_lossless_predicate_before_force(self):
        tree,ns=self.callbacks()
        for a in c.TEXTS:
            self.assertEqual(ns['_rp_dlg'](a),c.TEXTS[a])
            self.assertEqual(ns['_rp_fixed_bytes'](a),c.ROWS[a])
            self.assertTrue(ns['_rp_fixable'](a))
            self.assertEqual(ns['_rp_fit_level'](a),99 if a==c.FIRST else 6)
        self.assertEqual(ns['_rp_lossless_requested'],set())
        for a,expected in ((c.FIRST,(None,99)),(c.COMPANION,(c.ROWS[c.COMPANION],0))):
            self.assertEqual(builder.encode_fit(c.TEXTS[a],ns['slots'][a],ns['syl_to_code'],
                                               ns['unmapped'],a),expected)
        self.assertNotIn(c.FIRST,builder.BTEAM_PREVIOUS_KOREAN_TEXT)
        self.assertNotIn(c.FIRST,builder.BTEAM_ROUND2_RESIDUALS)
        assignments={n.targets[0].id:n.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
                     and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
        self.assertNotIn(c.FIRST,ast.literal_eval(assignments['_allowed_wide_skips']))
        overrides=json.loads((Path(builder.BASE)/'data/dialogue_overrides.json').read_text())
        baseline=json.loads((Path(builder.BASE)/'data/bteam_baseline.json').read_text())
        with (Path(builder.BASE)/'data/translation_for_import.csv').open() as f:
            csvrows={int(r['address'],16):r for r in csv.DictReader(f)}
        self.assertEqual(csvrows[c.COMPANION]['korean'],'힘내!')
        for actual in (baseline['overrides']['0x00DF28C2'],builder.ADDRESS_TEXT_OVERRIDES[c.FIRST],
                       overrides['0x00DF28C2'],csvrows[c.FIRST]['korean']):self.assertEqual(actual,c.TEXTS[c.FIRST])
        self.assertEqual(overrides['0x00DF28EF'],c.TEXTS[c.COMPANION])
        # A future lossless request must still be recorded before forced fit6.
        ns['encode_fit']=lambda *a:(b'short',0)
        ns['needs_safe_dialogue_punctuation']=lambda a:True
        ns['story_requires_lossless_repoint']=lambda *a:True
        ns['_rp_fit_level'](c.COMPANION)
        self.assertEqual(ns['_rp_lossless_requested'],{c.COMPANION})

    def test_generated_metadata_and_prepared_record_checked_before_target_writes(self):
        def only_target(o,r,rows,texts,lines,opts):
            opts['extra_messages'].pop(0xDF1000);lines.pop(0xDF1002)
        validator=c.validate_generated
        for field in ('ptr_off','ptr_sites','fixed','source_spans','source_texts','line_spans',
                      'old_len','new_len','lines','layout_controls'):
            def corrupt(payload,record,prepared):
                record[field]=None
                return validator(payload,record,prepared)
            with self.subTest(field=field),patch.object(c,'validate_generated',new=corrupt):
                self.assert_rejected(only_target,pattern='prepared/generated')
        preflight=c.preflight
        def corrupt_plan(*args,**kwargs):
            payload,record=preflight(*args,**kwargs);record['ptr_sites']=[]
            return payload,record
        with patch.object(c,'preflight',new=corrupt_plan):
            self.assert_rejected(only_target,pattern='prepared/generated')

    def test_exact_metadata_all_bytes_and_explicit_empty_joiner(self):
        c.validate(c.PAYLOAD,c.METADATA)
        for offset in range(66):
            damaged=bytearray(c.PAYLOAD);damaged[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(AssertionError):c.validate(damaged,c.METADATA)
        for field in c.METADATA:
            bad=copy.deepcopy(c.METADATA);del bad[field]
            with self.subTest(field=field),self.assertRaises(AssertionError):c.validate(c.PAYLOAD,bad)
        for field,value in (('source_fragment_joiners',{'0xDF28C2':['8140'],'0xDF28EF':[]}),
                            ('source_line_fragments',{'0xDF28C2':[[2,38],[43,12]],'0xDF28EF':[[55,8]]}),
                            ('display_line_spans',[[2,38],[43,10],[55,8]]),('layout_gaps',[])):
            bad=copy.deepcopy(c.METADATA);bad[field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):c.validate(c.PAYLOAD,bad)


if __name__=='__main__':unittest.main()
