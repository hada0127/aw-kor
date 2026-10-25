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
import e10d78_contract as c
from dialogue_repoint import repoint_messages, text_segment_cells
from repoint_source_rows import row_bytes


class ContractTests(unittest.TestCase):
    def prepare_fixture(self, mutation=None, callbacks=None):
        orig=bytearray(b'\xff'*0x1000000)
        orig[c.MESSAGE:c.END]=c.NATIVE
        orig[c.SITE-4:c.SITE+4]=c.CALLER
        early,owner,site=0xDF1000,0xDF1002,0x100
        orig[early:early+8]=bytes.fromhex('0a0982a06b0a0000')
        orig[site:site+4]=(0x08000000+early).to_bytes(4,'little')
        rom=bytearray(orig)
        rows={c.FIRST:c.ROW,owner:bytes.fromhex('8def')}
        texts={c.FIRST:c.TEXT,owner:'수'}
        lines={c.FIRST:(16,''),owner:(2,'')}
        opts=dict(require_e10d78=True,free_start=0xA3D000,free_end=0xA40000,
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
        m=next(m for m in manifest if m['msg']=='0xE10D78')
        target=int(m['new_addr'],16)
        c.validate(rom[target:target+22],m)
        expected=bytearray(before)
        e=next(m for m in manifest if m['msg']=='0xDF1000')
        expected[int(e['new_addr'],16):int(e['new_addr'],16)+8]=bytes.fromhex('0a098def6b0a0000')
        expected[site:site+4]=(0x08000000+int(e['new_addr'],16)).to_bytes(4,'little')
        expected[target:target+22]=c.PAYLOAD
        expected[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
        self.assertEqual(rom,expected)
        return orig,rom,m,writes

    def test_success_exact_bytes_owner_and_writes(self):
        orig,rom,m,writes=self.fixture()
        self.assertEqual(row_bytes(rom,m,'0xE10D7A'),c.ROW)
        self.assertEqual(text_segment_cells(c.ROW)*4,72)
        self.assertEqual(writes[-1][8],dict(source_spans={'0xE10D7A':16},source=c.MESSAGE,
                                          old_len=20,ptr_sites=[c.SITE]))
        self.assertEqual(sum(w[7]=='repoint:0xE10D78' for w in writes[1:]),1)
        self.assertEqual(rom[c.SITE-4:c.SITE],c.CALLER[:4])
        c.assert_manifest([m])

    def test_native_caller_controls_far_refs_atomic_before_earlier_message(self):
        for native,positions in ((True,range(c.MESSAGE,c.END)),
                                  (False,[c.MESSAGE,c.MESSAGE+1,c.TAIL,c.TAIL+1])):
            for address in positions:
                def mutate(o,r,*args): (o if native else r)[address]^=1
                with self.subTest(native=native,address=hex(address)):self.assert_rejected(mutate)
        for native in (True,False):
            for a in range(c.SITE-4,c.SITE+4):
                def mutate(o,r,*args): (o if native else r)[a]^=1
                with self.subTest(caller=a,native=native):self.assert_rejected(mutate)
        for target in (c.MESSAGE,c.FIRST,c.FIRST+1,c.TAIL,c.END-1):
            def mutate(o,r,*args):o[0xF80000:0xF80004]=(0x08000000+target).to_bytes(4,'little')
            with self.subTest(reference=target):self.assert_rejected(mutate)

    def test_source_and_configuration_fail_before_first_write(self):
        for case in ('owner','missing','both_missing','extra','tail','slot','text','bang','space',
                     'ascii','layout','reflow','next','duplicate','skip','wide','capacity','bounds','glyphs'):
            def mutate(o,r,rows,texts,lines,opts):
                if case=='owner':lines.pop(c.FIRST)
                if case in ('missing','both_missing'):opts['extra_messages'].pop(c.MESSAGE)
                if case=='both_missing':lines.pop(c.FIRST)
                if case=='extra':lines[c.FIRST+2]=(2,'')
                if case=='tail':lines[c.TAIL]=(2,'')
                if case=='slot':lines[c.FIRST]=(18,'')
                if case=='text':texts[c.FIRST]='아주 쉬웠어!'
                if case=='bang':rows[c.FIRST]=rows[c.FIRST][:-2]
                if case=='space':rows[c.FIRST]=rows[c.FIRST].replace(b'\x81\x40',b'',1)
                if case=='ascii':rows[c.FIRST]=rows[c.FIRST].replace(b'\x81\x40',b' ',1)
                if case=='layout':opts['line_layouts']={c.FIRST:(c.ROW[:8],c.ROW[8:])}
                if case=='reflow':opts['page_reflows']={c.MESSAGE:()}
                if case=='next':opts['extra_messages'][c.END-1]=[]
                if case=='duplicate':opts['extra_messages'][c.MESSAGE]=[c.SITE,c.SITE]
                if case=='skip':opts['skip_messages']={c.MESSAGE}
                if case=='wide':opts['allowed_wide_skips']={c.FIRST}
                if case=='capacity':opts['free_end']=opts['free_start']+21
                if case=='bounds':opts['free_end']=len(r)+4
                if case=='glyphs':opts['valid_codes']=frozenset()
            with self.subTest(case=case):self.assert_rejected(mutate)
        for cb in (dict(fixable=lambda a:False),dict(fit_level_dlg=lambda a:6)):
            self.assert_rejected(callbacks=cb)

    def callbacks(self):
        tree=ast.parse(Path(builder.__file__).read_text())
        names=('_rp_dlg','_rp_ov','_rp_fixable','_rp_fit_level','_rp_fixed_bytes')
        funcs=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
        codes={s:int(v,16) for s,v in json.loads(Path(builder.SYLCODE).read_text()).items()}
        overrides=json.loads((Path(builder.BASE)/'data/dialogue_overrides.json').read_text())
        ns=dict(vars(builder),syl_to_code=codes,unmapped=collections.Counter(),slots={c.FIRST:16},
                _rp_lossless_requested=set(),_rp_fixed_fragments=set(),_rp_script_owners={},
                _dlg_ov=overrides,_display_ov=builder.load_display_overrides(),_editor_intents={},_rp_bteam={c.FIRST},
                required_script_repoints=set())
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'<actual builder callbacks>','exec'),ns)
        return tree,ns

    def test_actual_source_authority_and_natural_fit99(self):
        tree,ns=self.callbacks()
        legacy=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='BTEAM_PREVIOUS_KOREAN_TEXT' for t in n.targets)
                    and isinstance(n.value,ast.Dict))
        self.assertIn(c.FIRST,legacy);self.assertNotIn(c.FIRST,builder.BTEAM_PREVIOUS_KOREAN_TEXT)
        baseline=json.loads((Path(builder.BASE)/'data/bteam_baseline.json').read_text())
        with (Path(builder.BASE)/'data/translation_for_import.csv').open() as f:
            csvrows={int(r['address'],16):r for r in csv.DictReader(f)}
        for actual in (baseline['overrides']['0x00E10D7A'],ns['_dlg_ov']['0x00E10D7A'],
                       csvrows[c.FIRST]['korean']):
            self.assertEqual(actual,'식은 죽 먹기지!')
        self.assertNotIn(c.FIRST,builder.ADDRESS_TEXT_OVERRIDES)
        self.assertEqual(ns['_rp_dlg'](c.FIRST),'식은 죽 먹기지!')
        self.assertTrue(ns['_rp_fixable'](c.FIRST))
        self.assertEqual(ns['_rp_fixed_bytes'](c.FIRST),c.ROW)
        self.assertEqual(ns['_rp_fit_level'](c.FIRST),99)
        self.assertEqual(ns['_rp_lossless_requested'],set())
        self.assertNotIn(c.FIRST,builder.BTEAM_ROUND2_RESIDUALS)
        # Invoke preflight with the actual callback chain; reject an earlier stale authority.
        orig=bytearray(b'\xff'*0x1000000);orig[c.MESSAGE:c.END]=c.NATIVE;orig[c.SITE-4:c.SITE+4]=c.CALLER
        def check():return c.preflight(orig,orig,[(c.FIRST,16)],c.END,[c.SITE],ns['_rp_fixed_bytes'],
                                      ns['_rp_dlg'],ns['_rp_fixable'],ns['_rp_fit_level'])
        self.assertEqual(check()[0],c.PAYLOAD)
        for name,value in (('_display_ov',{c.FIRST:'잘했어!'}),('_rp_script_owners',{c.FIRST:(16,'잘했어!')})):
            old=ns[name];ns[name]=value
            with self.subTest(authority=name),self.assertRaises(AssertionError):check()
            ns[name]=old

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
        for records in ([],[m,m],[dict(m,fixed=['0xE10D78'])],[dict(m,ptr_sites=['0xE114F4'])],
                        [dict(m,status='skip_forced')]):
            with self.assertRaises(AssertionError):c.assert_manifest(records)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='_assert_e10d78_manifest']
        self.assertEqual(len(calls),1)
        required=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
                  for k in n.keywords if k.arg=='require_e10d78' and isinstance(k.value,ast.Constant) and k.value.value is True]
        self.assertEqual(len(required),1)
        for records in ([m],[]):
            env=dict(_assert_e10d78_manifest=c.assert_manifest,_rp_manifest=records)
            run=lambda:exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(value=calls[0])],type_ignores=[])),'builder','exec'),env)
            if records:run()
            else:
                with self.assertRaises(AssertionError):run()

    def test_exact_payload_metadata_rejects_tail_and_virtual_owners(self):
        for payload in (c.PAYLOAD[:-2]+b'\x6b\x0a\x00',c.PAYLOAD[:-4]+c.PAYLOAD[-2:]):
            with self.assertRaises(AssertionError):c.validate(payload,c.METADATA)
        for field,value in [('fixed',['0xE10D78']),('line_spans',{'0xE10D7A':[2,16]}),
                            ('source_spans',{'0xE10D7A':18}),('source_line_fragments',{}),
                            ('source_fragment_joiners',{}),('lines',2)]:
            bad=dict(c.METADATA,**{field:value})
            with self.subTest(field=field),self.assertRaises(AssertionError):c.validate(c.PAYLOAD,bad)


    def test_prepared_contract_checked_before_target_payload_and_pointer_writes(self):
        original_preflight=c.preflight
        def changed(*args,**kwargs):
            payload,record=original_preflight(*args,**kwargs)
            record['source_spans']['0xE10D7A']=18
            return payload,record
        def only_target(o,r,rows,texts,lines,opts):
            opts['extra_messages'].pop(0xDF1000)
            lines.pop(0xDF1002)
        with patch.object(c,'preflight',side_effect=changed):
            self.assert_rejected(only_target,pattern='prepared payload/metadata')

    @unittest.skipUnless(os.environ.get('AW_E10D78_BASELINE'), 'Read-only baseline not supplied')
    def test_baseline_lossless_arrays_and_actual_pixel_consumer(self):
        from hashlib import sha256
        from dialogue_pixel_layout import audit
        root=Path(os.environ['AW_E10D78_BASELINE'])
        original=(root/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        candidate=(root/'output/game_wars_korean_df1eec_candidate.gba').read_bytes()
        lossless_raw=(root/'temp/repoint_lossless_requests.json').read_bytes()
        self.assertEqual(sha256(lossless_raw).hexdigest(),'93c235df8a6cba7a620cd1509268ef97b10536ac5f001935a2e24d54dbfb584a')
        self.assertEqual(sha256(original).hexdigest(),'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
        self.assertEqual(sha256(candidate).hexdigest(),'a3e1d6f850e9d6711df7f1e3a65da2d91959a59b6fbd23ad94c6479e0d3bce69')
        lossless=json.loads(lossless_raw); saved=copy.deepcopy(lossless)
        manifest=json.loads((root/'temp/repoint_manifest.json').read_text())
        tree,ns=self.callbacks()
        ns['_rp_lossless_requested']={int(a,16) for a in lossless['requested']}
        self.assertEqual(len(ns['_rp_lossless_requested']),1710)
        c.preflight(original,candidate,[(c.FIRST,16)],c.END,[c.SITE],ns['_rp_fixed_bytes'],
                    ns['_rp_dlg'],ns['_rp_fixable'],ns['_rp_fit_level'])
        self.assertEqual(ns['_rp_fit_level'](c.FIRST),99)
        self.assertEqual(sorted(ns['_rp_lossless_requested']),[int(a,16) for a in saved['requested']])
        ns['_rp_manifest']=manifest+[dict(c.METADATA,new_addr='0xA3D000')]
        accounting=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and
                    any(isinstance(t,ast.Name) and t.id in ('_rp_fixed_addresses','_rp_unfulfilled') for t in n.targets)]
        exec(compile(ast.Module(body=accounting,type_ignores=[]),'accounting','exec'),ns)
        self.assertEqual([f'0x{a:08X}' for a in ns['_rp_unfulfilled']],saved['unfulfilled'])
        self.assertEqual(len(saved['unfulfilled']),9)
        self.assertEqual(lossless,saved)
        # In-memory checker fixture, NOT a new ROM build or runtime candidate.
        from qa_e10d78_preservation import validate as preserved
        hypothetical=bytearray(candidate);target=0xFF0000
        hypothetical[target:target+22]=c.PAYLOAD
        hypothetical[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
        self.assertEqual(preserved(candidate,hypothetical,manifest,
            manifest+[dict(c.METADATA,new_addr=hex(target))])['preserved'],2979)

        entry=dict(source=c.MESSAGE,target=0xA3D000,payload=c.PAYLOAD,game='p1',script=True,
                   profile=('p1_portrait',176,2),sites=[c.SITE])
        with patch('dialogue_pixel_layout.inventory',return_value=[entry]):result=audit(original,candidate,[])
        self.assertFalse(result['errors'])
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in result['rows']],[(72,176)])
        self.assertTrue(all(not r['overflow'] and not r['row_overflow'] and not r['glyph_errors'] for r in result['rows']))


if __name__=='__main__':unittest.main()
