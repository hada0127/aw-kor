"""Synthetic contract fixtures; no product ROM/build/census/runtime execution."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ec312c_contract as c
import qa_ec312c_preservation as q
from dialogue_repoint import text_segment_cells
from repoint_source_rows import row_bytes


def fixture():
    original=bytearray(b'\xff'*0x1000000)
    original[c.MESSAGE:c.END]=c.NATIVE
    original[0x1000:0x1002]=b'\x00\xff'
    for root in range(0xDEBCC4,0xDEBD4C,4):
        original[root:root+4]=(0x08001000).to_bytes(4,'little')
    for start,(native,current) in c.PINS.items():
        original[start:start+len(native)]=native
    rom=bytearray(original)
    for start,(native,current) in c.PINS.items():
        rom[start:start+len(current)]=current
    manifest=[]; log=[]
    for i in range(2983):
        address=c.ARENA_START+i*4 if i<2982 else c.HIGH_WATER-1
        site=0x10000+i*4
        rom[address]=0
        rom[site:site+4]=(0x08000000+address).to_bytes(4,'little')
        key=f'0x{0xD00000+i*2:06X}'
        manifest.append(dict(msg=key,status='relocated',new_addr=f'0x{address:06X}',
            new_len=1,ptr_off=f'0x{site:06X}',ptr_sites=[f'0x{site:06X}'],
            fixed=[key],unknown={'nested':['must preserve',i]},source_line_joiners={key:'1b'}))
    manifest.insert(100,dict(msg=c.KEY,status='skip_wide_line',lines=[c.SOURCE_KEY]))
    manifest.insert(101,dict(msg='0xB83FA8',status='skip_wide_line',lines=['0xB83FA8']))
    c.retain_native(original,rom,log)
    options=dict(line_index={c.FIRST:(46,'source Japanese')},slots={c.FIRST:46},
        source_text=lambda a:c.TEXT,fixed_bytes=lambda a:c.ROW,
        valid_codes={int.from_bytes(c.ROW[i:i+2],'big') for i in range(0,52,2)})
    return original,rom,manifest,log,options


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=fixture()

    def fresh(self):
        o,r,m,w,k=self.base
        return bytearray(o),bytearray(r),copy.deepcopy(m),copy.deepcopy(w),dict(k)

    def reject(self,change):
        o,r,m,w,k=self.fresh();change(o,r,m,w,k)
        before=bytes(r);saved=copy.deepcopy(w);records=copy.deepcopy(m)
        with self.assertRaises(AssertionError):c.append(o,r,m,w,**k)
        self.assertEqual(bytes(r),before);self.assertEqual(w,saved);self.assertEqual(m,records)

    def test_exact_append_pending_source_row_and_existing_inventory_site(self):
        o,r,m,w,k=self.fresh();old=bytes(r);records=copy.deepcopy(m);logs=copy.deepcopy(w)
        pending=c.pending_requirements({c.FIRST,123},{123})
        self.assertEqual(pending,{c.FIRST})
        from hashlib import sha256
        self.assertEqual(sha256(c.PAYLOAD).hexdigest(),
                         '46bc7c1dff4ecc98b810028c85f869f98b4ee6bcb4655fc80ea0519b1719287d')
        stats=c.append(o,r,m,w,**k)
        self.assertEqual(stats['free_used'],60)
        self.assertEqual(q.validate(old,r,records,m,logs,w)['preserved'],2983)
        self.assertEqual(row_bytes(r,m[-1],c.SOURCE_KEY),c.ROW)
        self.assertEqual(text_segment_cells(c.ROW),52)
        completed={123};c.close_requirements(r,m,w,{c.FIRST,123},completed,pending)
        self.assertEqual(completed,{123,c.FIRST})
        c.check_pins(o,r,final=True)
        import dialogue_pixel_layout as layout
        # Minimal terminator records for unrelated native quote roots.
        for root in range(0xDEBCC4,0xDEBD4C,4):
            o[root:root+4]=(0x08001000).to_bytes(4,'little')
        consumers=layout.p1_consumers(o)
        self.assertEqual([e['site'] for e in consumers[c.MESSAGE]],[c.SITE])
        with patch.object(layout,'p1_consumers',return_value={c.MESSAGE:consumers[c.MESSAGE]}), \
             patch.object(layout,'p2_consumers',return_value={}), \
             patch.object(layout,'_read_table',return_value=[]):
            entries=layout.inventory(o,r,[m[-1]])
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['target'],c.APPEND)
        self.assertEqual(entries[0]['payload'],c.PAYLOAD)
        self.assertEqual(entries[0]['sites'],[c.SITE])
        self.assertEqual(entries[0]['profile'],c.PROFILE)
        self.assertNotEqual(w[0][7],w[-1][7])

    def test_retired_writer_is_not_an_active_restoration_in_real_drift_reader(self):
        import qa_bteam_drift as drift
        o,r,m,w,k=self.fresh()
        read_bytes,read_text=Path.read_bytes,Path.read_text
        selected=[]
        def text(path,*args,**kwargs):
            if str(path)=='fixture-map':return json.dumps(w)
            if str(path)=='fixture-manifest':return json.dumps(selected)
            return read_text(path,*args,**kwargs)
        def raw(path):
            return bytes(r) if str(path)=='fixture-rom' else read_bytes(path)
        def check():
            with patch.object(Path,'read_bytes',raw),patch.object(Path,'read_text',text):
                return drift.check_rom({'overrides':{'0x00EC312E':c.TEXT}},
                    'fixture-rom','fixture-map','fixture-manifest')
        self.assertEqual([issue['address'] for issue in check()],['0x00EC312E'])
        c.append(o,r,m,w,**k);selected.append(m[-1])
        self.assertEqual(check(),[])
        r[c.SITE]^=1
        self.assertEqual(check()[0]['cause'],'repoint pointer mismatch')

    def test_every_native_byte_and_consumer_mutations(self):
        # Fail-fast pins avoid any allocation or aligned scan on these mutations.
        for original in (True,False):
            for offset in range(52):
                with self.subTest(original=original,offset=offset):
                    self.reject(lambda o,r,m,w,k:(o if original else r).__setitem__(c.MESSAGE+offset,
                        (o if original else r)[c.MESSAGE+offset]^1))
            for start in (*c.PINS, *range(c.SITE,c.SITE+4)):
                with self.subTest(original=original,pin=hex(start)):
                    self.reject(lambda o,r,m,w,k:(o if original else r).__setitem__(start,
                        (o if original else r)[start]^1))

    def test_aliases_near_far_start_interior_tail(self):
        for site in (0x100,0xF80000):
            for target in (c.MESSAGE,c.MESSAGE+1,c.MESSAGE+22,c.END-4,c.END-1):
                with self.subTest(site=site,target=target):
                    self.reject(lambda o,r,m,w,k:o.__setitem__(slice(site,site+4),
                        (0x08000000+target).to_bytes(4,'little')))

    def test_inputs_fail_without_writes(self):
        mutations={
            'disabled':lambda o,r,m,w,k:k.update(enabled=False),
            'missing':lambda o,r,m,w,k:m.pop(100),
            'duplicate':lambda o,r,m,w,k:m.append(copy.deepcopy(m[100])),
            'already-relocated':lambda o,r,m,w,k:m[100].update(status='relocated'),
            'source46':lambda o,r,m,w,k:k.update(line_index={c.FIRST:(44,'')}),
            'missing-source':lambda o,r,m,w,k:k.update(line_index={}),
            'second-row':lambda o,r,m,w,k:k.update(line_index={c.FIRST:(46,''),c.FIRST+2:(2,'')}),
            'slot46':lambda o,r,m,w,k:k.update(slots={c.FIRST:44}),
            'authority':lambda o,r,m,w,k:k.update(source_text=lambda a:c.TEXT+'!'),
            'longer':lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:c.ROW+b'\x81\x49'),
            'control':lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:c.ROW[:-1]+b'\x72'),
            'glyph':lambda o,r,m,w,k:k.update(valid_codes=set()),
            'high-water':lambda o,r,m,w,k:m[-1].update(new_len=5),
            'arena-start':lambda o,r,m,w,k:k.update(arena_start=c.ARENA_START+4),
            'arena-end':lambda o,r,m,w,k:k.update(arena_end=c.ARENA_END+4),
            'align':lambda o,r,m,w,k:k.update(align=2),
            'capacity':lambda o,r,m,w,k:k.update(arena_end=c.APPEND+59),
            'occupied':lambda o,r,m,w,k:r.__setitem__(c.APPEND,0),
            'alignment-owner':lambda o,r,m,w,k:w.append([c.APPEND+58,2,2,'',None,None,None,'bad']),
            'pointer-owner':lambda o,r,m,w,k:w.append([c.SITE,4,4,'',None,None,None,'bad']),
            'pointer-provenance':lambda o,r,m,w,k:w.append([0x500,4,4,'',None,None,None,'bad',{'ptr_sites':[c.SITE]}]),
            'old-pointer':lambda o,r,m,w,k:r.__setitem__(0x10000,r[0x10000]^1),
            'source-owner':lambda o,r,m,w,k:m[0].update(line_spans={c.SOURCE_KEY:[0,1]}),
            'old-overlap':lambda o,r,m,w,k:m[0].update(new_len=5),
            'retired-owner':lambda o,r,m,w,k:w.clear(),
        }
        for name,change in mutations.items():
            with self.subTest(name=name):self.reject(change)

    def test_generated_contract_rejects_payload_metadata_and_missing_owner(self):
        record=dict(c.METADATA,new_addr=f'0x{c.APPEND:06X}')
        for i in range(58):
            raw=bytearray(c.PAYLOAD);raw[i]^=1
            with self.assertRaises(AssertionError):c.validate(raw,record)
        for key in record:
            bad=copy.deepcopy(record);bad.pop(key)
            with self.assertRaises(AssertionError):c.validate(c.PAYLOAD,bad)
        o,r,m,w,k=self.fresh();c.append(o,r,m,w,**k)
        with self.assertRaises(AssertionError):c.final(r,m,w[:-1])
        duplicate=copy.deepcopy(m);duplicate[0]['fixed']=[c.SOURCE_KEY]
        with self.assertRaises(AssertionError):c.final(r,duplicate,w)
        with self.assertRaises(AssertionError):c.close_requirements(r,m,w,{c.FIRST},set(),set())
        with self.assertRaises(AssertionError):c.pending_requirements({c.FIRST},{c.FIRST})

    def test_scoped_allocator_rejects_missing_duplicate_sites_and_input_drift(self):
        import dialogue_repoint as rp
        allocator=rp.repoint_messages
        changes={
            'missing-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[]}),
            'duplicate-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[c.SITE,c.SITE]}),
            'wrong-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[c.SITE-4]}),
            'source46':lambda kw:kw.update(line_index={c.FIRST:(44,'')}),
            'second-row':lambda kw:kw.update(line_index={c.FIRST:(46,''),c.FIRST+2:(2,'')}),
            'wide-callback':lambda kw:kw.update(max_cells_for_address=lambda a:54),
            'disabled-fix':lambda kw:kw.update(fixable=lambda a:False),
        }
        for name,change in changes.items():
            def invoke(*args,**kw):
                change(kw)
                return allocator(*args,**kw)
            with self.subTest(name=name),patch.object(rp,'repoint_messages',side_effect=invoke):
                self.reject(lambda o,r,m,w,k:None)

    def test_prepared_validation_fails_before_allocation_writes(self):
        with patch.object(c,'validate',side_effect=AssertionError('prepared metadata')):
            self.reject(lambda o,r,m,w,k:None)

    def test_real_builder_callbacks_preserve_early_skip_and_authorities(self):
        import ast
        import csv
        from test_ec3190_contract import ContractTests as Existing
        import build_korean_full as b
        tree,ns=Existing().callbacks()
        from text_metrics import visual_cells
        ns['_rp_visual_cells']=visual_cells
        ns['slots']={c.FIRST:46};ns['_rp_bteam']={c.FIRST}
        self.assertEqual(ns['_rp_dlg'](c.FIRST),c.TEXT)
        self.assertEqual(ns['_rp_fixed_bytes'](c.FIRST),c.ROW)
        self.assertTrue(ns['_rp_fixable'](c.FIRST))
        self.assertEqual(ns['_rp_fit_level'](c.FIRST),99)
        self.assertGreater(ns['_rp_cell_width'](c.FIRST),44)
        self.assertEqual(ns['_rp_lossless_requested'],set())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Name) and n.func.id=='repoint_messages']
        self.assertEqual(len(calls),1)
        cap=next(k.value for k in calls[0].keywords if k.arg=='max_cells_for_address')
        limit=eval(compile(ast.Expression(cap),'<early cap>','eval'),ns)
        self.assertEqual(limit(c.FIRST),44)
        self.assertNotIn(c.FIRST,ns['required_script_repoints'])
        baseline=json.loads((Path(b.BASE)/'data/bteam_baseline.json').read_text())
        self.assertEqual(baseline['overrides']['0x00EC312E'],c.TEXT)
        self.assertEqual(ns['_dlg_ov']['0x00EC312E'],c.TEXT)
        with (Path(b.BASE)/'data/translation_for_import.csv').open() as stream:
            row=next(r for r in csv.DictReader(stream) if int(r['address'],16)==c.FIRST)
        self.assertEqual(row['korean'],c.TEXT)
        from dialogue_repoint import _line_index
        self.assertEqual(_line_index(b.FOUND)[c.FIRST][0],46)

    def test_builder_encoding_caps_and_call_order(self):
        import build_korean_full as b
        syl=json.loads((Path(b.BASE)/'data/syllable_to_code_2350.json').read_text())
        syl={k:int(v,16) if isinstance(v,str) else int(v) for k,v in syl.items()}
        raw=b.encode_full_fidelity(c.TEXT,syl,set(),c.FIRST)
        self.assertEqual(bytes(raw),c.ROW)
        b.validate_bteam_payload(c.ROW,{v:k for k,v in syl.items()},c.FIRST)
        for raw in (c.ROW+b'\x81\x49',c.ROW+b'\x72\x0a\x09'+c.ROW):
            with self.assertRaises(AssertionError):b.validate_bteam_payload(raw,{},c.FIRST)
        self.assertNotIn(c.FIRST,b.BTEAM_RESTORED_ROW_HALF_CELLS)
        self.assertEqual(c.exact_half_cells(c.FIRST,c.ROW),52)
        self.assertNotIn(c.FIRST,b.BTEAM_ROUND2_RESIDUALS)
        source=Path(b.__file__).read_text()
        self.assertLess(source.index('_spacing_applied = apply_dialogue_spacing'),source.index("st['ec312c_late_append']"))
        self.assertLess(source.index("st['ec312c_late_append']"),source.index('_pixel_audit = audit_pixel_layout'))
        self.assertIn('required_script_repoints - _allowed_script_residuals - _b82fac_pending - _ec312c_pending',source)
        self.assertLess(source.index('_b82fac.close_requirements('),source.index("st['ec312c_late_append']"))

    def test_exact_consumer_endpoints_and_wrong_tile_arguments(self):
        import dialogue_pixel_layout as layout
        tokens=layout.tokenize(c.PAYLOAD,'p1')
        rows=layout.physical_rows(tokens)
        self.assertEqual(len(rows),1)
        glyphs=[t for t in rows[0]['tokens'] if t['kind'] in ('glyph','space')]
        self.assertEqual(len(glyphs),26)
        self.assertEqual(sum(t['advance'] for t in rows[0]['tokens']),208)
        self.assertEqual((c.TILE_START,c.TILE_LAST_PAIR,c.TILE_NEXT,c.CLEAR_FILL),
                         (0x100,(0x132,0x133),0x134,0x164))
        self.assertEqual(tuple(range(c.TILE_START,c.TILE_START+2*len(glyphs)))[-2:],(0x132,0x133))
        self.assertEqual(c.TILE_START+2*len(glyphs),c.TILE_NEXT)
        # Decode the actual pinned MOV immediate + LSL-by-one instructions.
        raw=c.PINS[0xB71160][0]
        self.assertEqual(raw[0x96:0x9c],bytes.fromhex('802040000190'))
        self.assertEqual(raw[0x7e:0x84],bytes.fromhex('b22040000190'))
        self.assertEqual(raw[0x96]*2,c.TILE_START)
        self.assertEqual(raw[0x7e]*2,c.CLEAR_FILL)
        for start,value in ((0xB711F6,0x98),(0xB711F6,0xB2),
                            (0xB12170,0x51),(0xB12926,0x0B),(0xB1298C,0x05),(0xB129AA,0xF1)):
            self.reject(lambda o,r,m,w,k:r.__setitem__(start,value))
        for raw in (c.ROW[:-2]+b'\x81\x40', c.ROW+b' ', c.ROW+b'\x81\x40',
                    c.ROW+b'\x72\x0a\x09'+c.ROW, c.ROW+b'\x6b'+c.ROW):
            self.reject(lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:raw))

    def test_generic_44_still_skips_and_final_gate_binds_owner(self):
        import ast
        import build_korean_full as b
        import dialogue_repoint as rp
        o,r,m,w,k=self.fresh()
        before=bytes(r); logs=copy.deepcopy(w)
        records,stats=rp.repoint_messages(r,o,fixable=lambda a:True,
            fixed_bytes=lambda a:c.ROW,fit_level_dlg=lambda a:99,
            decode_text=lambda raw:c.TEXT,source_text=lambda a:c.TEXT,
            cell_width=lambda a:52,slots={c.FIRST:46},line_index=k['line_index'],
            table_offsets=[],extra_messages={c.MESSAGE:[c.SITE]},
            free_start=c.APPEND,free_end=c.ARENA_END,
            max_cells_for_address=lambda a:44,allowed_wide_skips={c.FIRST},
            valid_codes=k['valid_codes'],write_log=w)
        self.assertEqual(records,[dict(msg=c.KEY,status='skip_wide_line',lines=[c.SOURCE_KEY])])
        self.assertEqual(bytes(r),before);self.assertEqual(w,logs)
        with self.assertRaises(AssertionError):b.validate_bteam_payload(c.ROW,{},0xD00000)
        self.assertEqual(c.exact_half_cells(c.MESSAGE,c.ROW),0)
        with self.assertRaises(AssertionError):c.close_requirements(r,m,w,{c.FIRST},set(),{c.FIRST})
        c.append(o,r,m,w,**k)
        tree=ast.parse(Path(b.__file__).read_text())
        gates=[n for n in ast.walk(tree) if isinstance(n,ast.If) and
               isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name)
               and n.test.left.id=='_address' and
               any(isinstance(x,ast.Constant) and x.value==c.FIRST for x in n.test.comparators)]
        gate=next(n for n in gates if any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)
                  and x.func.attr=='final' for x in ast.walk(n)))
        ns=dict(_address=c.FIRST,_ec312c=c,rom=r,orig=o,_rp_manifest=m,WRITE_LOG=w,
                _spacing_limit=0,_payload=c.ROW)
        compiled=compile(ast.Module(body=[gate],type_ignores=[]),'<final builder gate>','exec')
        exec(compiled,ns);self.assertEqual(ns['_spacing_limit'],52)
        w.append(copy.deepcopy(w[-1]))
        with self.assertRaises(AssertionError):exec(compiled,ns)

    def test_real_inventory_and_glyph_bytes_fixture(self):
        import struct
        import dialogue_pixel_layout as layout
        o,r,m,w,k=self.fresh();c.append(o,r,m,w,**k)
        # Use existing checked-in Galmuri bytes, never generate/import a font.
        root=Path(__file__).resolve().parents[1]
        codes=json.loads((root/'data/syllable_to_code_2350.json').read_text())
        glyphs=json.loads((root/'data/syllable_to_glyph_2350.json').read_text())['map']
        blob=(root/'data/kor_glyphs_2350.bin').read_bytes()
        r[0xF00000:0xF00000+len(blob)]=blob
        table=bytearray()
        for text in sorted(set(c.TEXT)-{' '}):
            indices=glyphs[text]
            table.extend(int(codes[text],16).to_bytes(2,'big')+struct.pack('<HH',
                         indices['top']|0x8000,indices['bot']|0x8000))
        r[0xF20000:0xF20000+len(table)]=table
        struct.pack_into('<II',r,0xEFE970,0x08F20000,0x08F20000+len(table))
        # Native fullwidth-space top/bottom map to an empty fixture tile.
        r[0xB974D0:0xB974F0]=bytes(32)
        struct.pack_into('<H',r,0xB8027C,0);struct.pack_into('<H',r,0xB8028C,0)
        o[0xA01970]=0  # unrelated prologue is an empty, terminated fixture
        consumers=layout.p1_consumers(o)
        selected={c.MESSAGE:consumers[c.MESSAGE]}
        with patch.object(layout,'p1_consumers',return_value=selected), \
             patch.object(layout,'p2_consumers',return_value={}), \
             patch.object(layout,'_read_table',return_value=[]):
            result=layout.audit(o,r,[m[-1]])
            entry=layout.inventory(o,r,[m[-1]])[0]
        self.assertEqual(entry['payload'],c.PAYLOAD)
        self.assertEqual(entry['target'],c.APPEND)
        self.assertEqual(entry['sites'],[c.SITE]);self.assertEqual(entry['profile'],c.PROFILE)
        self.assertEqual(result['summary']['native_references'],1)
        self.assertEqual(result['summary']['physical_messages'],1)
        self.assertEqual(result['summary']['script_messages'],1)
        self.assertEqual(result['summary']['physical_rows'],1)
        self.assertEqual(result['summary']['profiles'],{'p1_link_notice':1})
        self.assertEqual([(x['advance_px'],x['ink_right_px'],x['limit_px'],x['max_rows'])
                          for x in result['rows']],[(208,208,208,1)])
        for key in ('overflows','row_overflows','parser_errors','glyph_errors','caption_overlaps'):
            self.assertEqual(result['summary'][key],0)
        for payload,key in ((c.PAYLOAD[:-4]+b'\x81\x40'+c.PAYLOAD[-4:],'overflows'),
                            (c.PAYLOAD[:-4]+b'\x72\x0a\x09'+c.ROW+c.PAYLOAD[-4:],'row_overflows')):
            with patch.object(layout,'inventory',return_value=[dict(entry,payload=payload)]):
                failed=layout.audit(o,r,[m[-1]])
            self.assertGreater(failed['summary'][key],0)
        r[0xF20000]^=1
        with patch.object(layout,'inventory',return_value=[entry]):
            failed=layout.audit(o,r,[m[-1]])
        self.assertGreater(failed['summary']['glyph_errors'],0)


if __name__ == '__main__':unittest.main()
