"""Bounded synthetic-buffer fixtures with immutable accepted0916 pin bytes.

Reads AW_ACCEPTED0916 (default local accepted snapshot); never writes a ROM or
runs a builder/census/emulator. Pin inputs are checked, not silently regenerated.
"""
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import d821f0_contract as c
import qa_d821f0_preservation as q

SNAPSHOT = Path(os.environ.get('AW_ACCEPTED0916',
    '/home/taro1/weekend-20261024/temp/aw-ec312c-build0916'))


def fixture():
    original = bytearray((SNAPSHOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
    current = (SNAPSHOT/'output/game_wars_korean_ec312c_candidate.gba').read_bytes()
    if (sha256(original).hexdigest() != 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
            or sha256(current).hexdigest() != '634cc03f6abd4be50b645ce1ce73835ece0386abe800ed09171399fbd4896db5'):
        raise AssertionError('test input is not original/accepted0916')
    rom = bytearray(original)
    for a,b,digest in c.CURRENT_PINS:
        rom[a:b] = current[a:b]
    # Real pin bytes; synthetic old2984 allocations exercise the whole-field gate.
    manifest=[]
    for i in range(2984):
        address=c.ARENA_START+i*4 if i<2983 else c.HIGH_WATER-1
        site=0x10000+i*8
        rom[address]=0
        rom[site:site+4]=(0x08000000+address).to_bytes(4,'little')
        rom[site+4:site+8]=(0x08000000+address).to_bytes(4,'little')
        key=f'0x{0xD00000+i*2:06X}'
        manifest.append(dict(msg=key,status='relocated',new_addr=f'0x{address:06X}',new_len=1,
            ptr_off=f'0x{site:06X}',ptr_sites=[f'0x{site:06X}',f'0x{site+4:06X}'],
            fixed=[key],unknown={'nested':['keep',i]},source_line_joiners={key:'1b'}))
    manifest.insert(100,dict(msg='0xB83FA8',status='skip_wide_line',lines=['0xB83FA8']))
    log=[]
    for writer in ('import-csv','dialogue-override'):
        log.append([c.FIRST,36,36,c.CURRENT[:36].hex(),32,
                    '선택 중인 지형 병종을 배치합니다',0,writer])
    c.retain_native(original,rom,log)
    options=dict(line_index={c.FIRST:(36,'選択している地形、兵種を配置します。')},
        slots={c.FIRST:36},source_text=lambda a:c.TEXT,fixed_bytes=lambda a:c.ROW,
        valid_codes={int.from_bytes(c.ROW[i:i+2],'big') for i in range(0,38,2)})
    return original,rom,manifest,log,options


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=fixture()

    def fresh(self):
        o,r,m,w,k=self.base
        return bytearray(o),bytearray(r),copy.deepcopy(m),copy.deepcopy(w),copy.deepcopy(k)

    def reject(self,change):
        o,r,m,w,k=self.fresh();change(o,r,m,w,k)
        old,saved,logs=bytes(r),copy.deepcopy(m),copy.deepcopy(w)
        with self.assertRaises(AssertionError):c.append(o,r,m,w,**k)
        self.assertEqual(bytes(r),old);self.assertEqual(m,saved);self.assertEqual(w,logs)

    def test_exact40_append_pending_inventory_and_full_row(self):
        o,r,m,w,k=self.fresh();old,om,ow=bytes(r),copy.deepcopy(m),copy.deepcopy(w)
        pending=c.pending_requirements({c.FIRST,123},{123})
        result=c.append(o,r,m,w,**k)
        self.assertEqual(result,dict(relocated=1,free_used=40,free_remaining=0x717B4))
        self.assertEqual(q.validate(old,r,om,m,ow,w)['preserved'],2984)
        self.assertEqual(m,om+[c.record()]);self.assertEqual(w,ow+[c.display_owner()])
        from repoint_source_rows import row_bytes
        self.assertEqual(row_bytes(r,m[-1],c.KEY),c.ROW)
        completed={123};c.close_requirements(r,m,w,{c.FIRST,123},completed,pending)
        self.assertEqual(completed,{123,c.FIRST});c.check_pins(o,r,final=True)
        import dialogue_pixel_layout as layout
        consumers=layout.p1_consumers(o)
        with patch.object(layout,'p1_consumers',return_value={c.MESSAGE:consumers[c.MESSAGE]}), \
             patch.object(layout,'p2_consumers',return_value={}), \
             patch.object(layout,'_read_table',return_value=[]):
            entries=layout.inventory(o,r,[m[-1]])
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['target'],c.APPEND)
        self.assertEqual(entries[0]['payload'],c.PAYLOAD)
        self.assertEqual(entries[0]['profile'],c.PROFILE)
        rows=layout.physical_rows(layout.tokenize(c.PAYLOAD,'p1'))
        self.assertEqual(len(rows),1)
        self.assertEqual(sum(t['advance'] for t in rows[0]['tokens']),152)
        import part1_editor_help_dictionary as d
        codes=[d.dictionary(r)[i:i+2] for i in range(0,140,2)]
        for i in range(0xD81C24,0xD81CFC,2):
            pair=bytes(r[i:i+2])
            if pair not in codes:codes.append(pair)
        self.assertEqual(len(codes),73)
        self.assertEqual(0x0E+len(codes)*2-1,0x9F)

    def test_source_provenance_authority_capacity_owners_and_fallback(self):
        changes={
            'disabled':lambda o,r,m,w,k:k.update(enabled=False),
            'early-owner':lambda o,r,m,w,k:m.append(c.record()),
            'hidden-source-owner':lambda o,r,m,w,k:m[0].update(source_spans={c.KEY:36}),
            'source36':lambda o,r,m,w,k:k.update(line_index={c.FIRST:(38,'')}),
            'slot44':lambda o,r,m,w,k:k.update(slots={c.FIRST:44}),
            'extra-row':lambda o,r,m,w,k:k['line_index'].update({c.FIRST+2:(2,'')}),
            'authority':lambda o,r,m,w,k:k.update(source_text=lambda a:c.TEXT.replace(',',' ')),
            'source-as-display':lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:c.CURRENT[:36]),
            'period':lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:c.ROW[:-2]),
            'space':lambda o,r,m,w,k:k.update(fixed_bytes=lambda a:c.ROW[:4]+c.ROW[6:]),
            'glyph':lambda o,r,m,w,k:k.update(valid_codes=set()),
            'high-water':lambda o,r,m,w,k:m[-1].update(new_len=2),
            'count':lambda o,r,m,w,k:m.pop(),
            'duplicate-old':lambda o,r,m,w,k:m.append(copy.deepcopy(m[0])),
            'align':lambda o,r,m,w,k:k.update(align=2),
            'arena-start':lambda o,r,m,w,k:k.update(arena_start=c.ARENA_START+4),
            'capacity39':lambda o,r,m,w,k:k.update(arena_end=c.APPEND+39),
            'occupied':lambda o,r,m,w,k:r.__setitem__(c.APPEND,0),
            'aligned-bytes':lambda o,r,m,w,k:r.__setitem__(c.HIGH_WATER,0),
            'retained-owner':lambda o,r,m,w,k:w.pop(),
            'retained-duplicate':lambda o,r,m,w,k:w.append(c.retained_owner()),
            'retained-overwritten':lambda o,r,m,w,k:w.append([c.MESSAGE+2,2,2,'',None,None,None,'bad']),
            'range-owner':lambda o,r,m,w,k:w.append([c.APPEND+39,2,2,'',None,None,None,'bad']),
            'alignment-owner':lambda o,r,m,w,k:w.append([c.HIGH_WATER,2,2,'',None,None,None,'bad']),
            'pointer-owner':lambda o,r,m,w,k:w.append([c.SITE,4,4,'',None,None,None,'bad']),
            'pointer-metadata':lambda o,r,m,w,k:w.append([0,1,1,'',None,None,None,'bad',{'ptr_sites':[c.SITE]}]),
            'old-extra-pointer':lambda o,r,m,w,k:r.__setitem__(0x10004,r[0x10004]^1),
            'old-overlap':lambda o,r,m,w,k:m[0].update(new_len=5),
        }
        for name,change in changes.items():
            with self.subTest(name=name):self.reject(change)

    def test_source_decoder_overlay_dictionary_glyph_pins(self):
        for original in (True,False):
            for start,end,digest in c.ORIGINAL_PINS if original else c.CURRENT_PINS:
                with self.subTest(original=original,start=hex(start)):
                    self.reject(lambda o,r,m,w,k:(o if original else r).__setitem__(start,
                        (o if original else r)[start]^1))
        for offset in range(40):
            with self.subTest(native=offset):
                self.reject(lambda o,r,m,w,k:r.__setitem__(c.MESSAGE+offset,r[c.MESSAGE+offset]^1))
        for target in (c.MESSAGE+2,0x02000000,c.END,0xFFFFFF):
            with self.subTest(pointer=hex(target)):
                self.reject(lambda o,r,m,w,k:r.__setitem__(slice(c.SITE,c.SITE+4),
                    (0x08000000+target).to_bytes(4,'little')))

    def test_editor_consumer_variant_is_exact_and_not_mixed(self):
        import struct
        import part1_editor_compact_labels as editor
        _,rom,_,_,_=self.fresh()
        rom[editor.CODE_OFFSET:editor.CODE_OFFSET+len(editor.CODE)]=editor.CODE
        for address,(_,target) in editor.REPLACES.items():
            struct.pack_into('<I',rom,address,target)
        struct.pack_into('<I',rom,editor.LEGACY_ROW_SITE,editor.LEGACY_ROW_TARGET)
        self.assertEqual(bytes(rom[editor.RETURN_SITE:editor.RETURN_SITE+22]),
                         editor.RETURN_OLD)
        c.check_current_pins(rom)
        for address in (editor.CODE_OFFSET,editor.RETURN_SITE,editor.LEGACY_ROW_SITE):
            with self.subTest(address=hex(address)):
                damaged=bytearray(rom);damaged[address]^=1
                with self.assertRaises(AssertionError):c.check_current_pins(damaged)
        mixed=bytearray(rom)
        _,old,_,_,_=self.fresh()
        mixed[0xF30600:0xF30800]=old[0xF30600:0xF30800]
        with self.assertRaisesRegex(AssertionError,'variants mixed'):
            c.check_current_pins(mixed)

    def test_new_aligned_aliases_start_interior_tail(self):
        for site in (0x100,0xF80000):
            for target in (c.MESSAGE,c.MESSAGE+1,c.MESSAGE+36,c.END-1):
                with self.subTest(site=site,target=target):
                    self.reject(lambda o,r,m,w,k:o.__setitem__(slice(site,site+4),
                        (0x08000000+target).to_bytes(4,'little')))

    def test_exact_bytes_tail2_and_metadata(self):
        for i in range(40):
            raw=bytearray(c.PAYLOAD);raw[i]^=1
            with self.assertRaises(AssertionError):c.validate(raw,c.record())
        for n in (0,1,3,4):
            with self.assertRaises(AssertionError):c.validate(c.ROW+b'\0'*n,c.record())
        for key in c.record():
            record=c.record();record.pop(key)
            with self.assertRaises(AssertionError):c.validate(c.PAYLOAD,record)
        o,r,m,w,k=self.fresh();c.append(o,r,m,w,**k)
        for log in (w[:-1],w+[c.display_owner()]):
            with self.assertRaises(AssertionError):c.final(r,m,log)
        for target in (c.MESSAGE,c.APPEND+2,c.APPEND+38):
            bad=bytearray(r);bad[c.SITE:c.SITE+4]=(0x08000000+target).to_bytes(4,'little')
            with self.assertRaises(AssertionError):c.final(bad,m,w)
        with self.assertRaises(AssertionError):c.pending_requirements({c.FIRST},{c.FIRST})
        with self.assertRaises(AssertionError):c.close_requirements(r,m,w,{c.FIRST},set(),set())

    def test_scoped_allocator_inputs_and_prepared42_fail_without_writes(self):
        import dialogue_repoint as rp
        allocator=rp.repoint_messages
        changes={
            'missing-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[]}),
            'duplicate-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[c.SITE,c.SITE]}),
            'wrong-site':lambda kw:kw.update(extra_messages={c.MESSAGE:[c.SITE-4]}),
            'line38':lambda kw:kw.update(line_index={c.FIRST:(38,'')}),
            'wide-cap':lambda kw:kw.update(max_cells_for_address=lambda a:46),
            'disabled-fix':lambda kw:kw.update(fixable=lambda a:False),
        }
        for name,change in changes.items():
            def invoke(*args,**kw):
                change(kw);return allocator(*args,**kw)
            with self.subTest(name=name),patch.object(rp,'repoint_messages',side_effect=invoke):
                self.reject(lambda o,r,m,w,k:None)
        with patch.object(c,'validate',side_effect=AssertionError('prepared exact40')):
            self.reject(lambda o,r,m,w,k:None)
        # Disabling the scoped tail rule produces generic42; append must reject it.
        def generic(*args,**kw):
            kw['require_d821f0']=False
            return allocator(*args,**kw)
        o,r,m,w,k=self.fresh()
        with patch.object(rp,'repoint_messages',side_effect=generic),self.assertRaises(AssertionError):
            c.append(o,r,m,w,**k)

    def test_real_drift_reader_requires_actual_display_not_retained_source(self):
        import qa_bteam_drift as drift
        o,r,m,w,k=self.fresh();selected=[]
        read_bytes,read_text=Path.read_bytes,Path.read_text
        def text(path,*args,**kw):
            if str(path)=='fixture-map':return json.dumps(w)
            if str(path)=='fixture-manifest':return json.dumps(selected)
            return read_text(path,*args,**kw)
        def raw(path):return bytes(r) if str(path)=='fixture-rom' else read_bytes(path)
        def check():
            with patch.object(Path,'read_bytes',raw),patch.object(Path,'read_text',text):
                return drift.check_rom({'overrides':{'0x00D821F0':c.TEXT}},
                    'fixture-rom','fixture-map','fixture-manifest')
        self.assertEqual(check()[0]['cause'],'repoint line mapping invalid')
        c.append(o,r,m,w,**k);selected.append(m[-1]);self.assertEqual(check(),[])
        for offset in (0,14,36,38,39):
            r[c.APPEND+offset]^=1
            self.assertEqual(check()[0]['cause'],'repoint line mapping invalid')
            r[c.APPEND+offset]^=1
        selected[0]['line_spans'][c.KEY]=[0,36]
        self.assertEqual(check()[0]['cause'],'repoint line mapping invalid')

    def test_builder_authority_and_integration_order(self):
        import build_korean_full as b
        syl=json.loads((Path(b.BASE)/'data/syllable_to_code_2350.json').read_text())
        syl={k:int(v,16) if isinstance(v,str) else int(v) for k,v in syl.items()}
        self.assertEqual(bytes(b.encode_full_fidelity(c.TEXT,syl,set(),c.FIRST)),c.ROW)
        source=Path(b.__file__).read_text()
        self.assertLess(source.index("st['ec312c_late_append']"),source.index("st['d821f0_late_append']"))
        self.assertLess(source.index("st['d821f0_late_append']"),source.index('_pixel_audit = audit_pixel_layout'))
        self.assertLess(source.index('_d821f0.close_requirements('),source.index('_restored_relocated_residuals.add(0xD821F0)'))
        self.assertNotIn(c.FIRST,b.BTEAM_ROUND2_RESIDUALS)
        self.assertNotIn(c.FIRST,b.BTEAM_RESTORED_ROW_HALF_CELLS)
        self.assertEqual(json.loads((Path(b.BASE)/'data/bteam_baseline.json').read_text())['overrides']['0x00D821F0'],c.TEXT)
        from dialogue_repoint import _line_index
        self.assertEqual(_line_index(b.FOUND)[c.FIRST][0],36)


if __name__=='__main__':unittest.main()
