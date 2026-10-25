"""Exercise all-2977 preservation, fragments, joiners and prior-candidate neighbor."""
import copy
import unittest
from df2804_contract import MESSAGE, PAYLOAD, TEXTS
from qa_df2804_preservation import validate


class PreservationTests(unittest.TestCase):
    def fixture(self):
        old = bytearray(0x1000000)
        # Deliberately translated native neighbor: compare candidate-to-candidate.
        old[0xDF2858:0xDF2858+104] = b'K' * 104
        old[0xDF1DA4:0xDF1DAC] = bytes.fromhex('190000000428df08')
        new = bytearray(old)
        before, after = [], []
        for i in range(2977):
            key = (0xDF2858, 0xDF2790, 0xDF26FC)[i] if i < 3 else 0x100000 + i * 64
            addr, target, site = 0xA40000 + i * 64, 0xA80000 + i * 64, 0x1000 + i * 4
            size = (112, 59, 90)[i] if i < 3 else 59
            if i < 3: addr, target = 0xA20000 + i*128, 0xA30000 + i*128
            m = dict(msg=hex(key), status='relocated', new_addr=hex(addr), new_len=size,
                     ptr_sites=[hex(site)], source_line_fragments={'0xDF278C': [[52,2],[58,1]]},
                     source_fragment_joiners={'0xDF278C':['8140']}, layout_controls={},
                     source_texts={}, source_spans={}, line_spans={}, old_len=59,
                     future_logical_field={'preserve':True})
            n = copy.deepcopy(m); n['new_addr'] = hex(target)
            before.append(m); after.append(n)
            old[addr:addr+size] = new[target:target+size] = bytes([i % 256]) * size
            if i == 0:
                m['ptr_sites'].append('0x8000'); n['ptr_sites'].append('0x8000')
                old[0x8000:0x8004] = (0x08000000+addr).to_bytes(4,'little')
                new[0x8000:0x8004] = (0x08000000+target).to_bytes(4,'little')
            old[site:site+4] = (0x08000000+addr).to_bytes(4,'little')
            new[site:site+4] = (0x08000000+target).to_bytes(4,'little')
        added=dict(msg=hex(MESSAGE),status='relocated',new_addr='0xAC0000',new_len=80,
                   ptr_sites=['0xDF1DA8'], ptr_off='0xDF1DA8', old_len=82, lines=2,
                   fixed=['0xDF2806', '0xDF2831'], layout_controls={},
                   source_spans={'0xDF2806':40,'0xDF2831':34},
                   line_spans={'0xDF2806':[2,46],'0xDF2831':[51,26]},
                   source_texts={f'0x{a:06X}':t for a,t in TEXTS.items()})
        after.append(added)
        new[0xAC0000:0xAC0000+80] = PAYLOAD
        new[0xDF1DA8:0xDF1DAC] = (0x08AC0000).to_bytes(4,'little')
        return old,new,before,after

    def test_all_logical_fields_and_future_fields_protected(self):
        args=self.fixture()
        self.assertEqual(validate(*args)['preserved'],2977)
        for field in args[2][0]:
            if field == 'new_addr': continue
            changed=copy.deepcopy(args[3]); changed[0][field]=None
            with self.subTest(field=field),self.assertRaises((AssertionError,TypeError)):
                validate(args[0],args[1],args[2],changed)
        for field in ('source_line_fragments','source_fragment_joiners','layout_controls','future_logical_field'):
            changed=copy.deepcopy(args[3]);del changed[0][field]
            with self.subTest(missing=field), self.assertRaises(AssertionError):
                validate(args[0],args[1],args[2],changed)
        changed=copy.deepcopy(args[3]);changed[0]['unexpected_logical_field']=1
        with self.assertRaises(AssertionError):validate(args[0],args[1],args[2],changed)

    def test_payload_pointers_native_neighbor_and_population(self):
        old,new,before,after=self.fixture()
        for which,offset in (('old',0x1000),('new',0x1000),('old',0xA20000+111),
                            ('new',0xA30000+111),('new',0xDF2858+103),('new',0xDF2853),
                            ('new',0xDF2831),('new',0xDF2856),('new',0xDF2857),('new',0xAC0000),('new',0xDF1DA4),('old',0xDF1DA8),('old',0x8000),('new',0x8000)):
            damaged=bytearray(old if which=='old' else new);damaged[offset]^=1
            with self.subTest(which=which,offset=hex(offset)),self.assertRaises(AssertionError):
                validate(damaged if which=='old' else old,damaged if which=='new' else new,before,after)
        for records in (after[:-1], after+[after[0]], after[1:]):
            with self.assertRaises(AssertionError):validate(old,new,before,records)

    def test_added_contract_cannot_hide_virtual_owners_or_wrong_sources(self):
        old,new,before,after=self.fixture()
        for field,value in (('source_line_fragments',{}),('source_fragment_joiners',{}),
                            ('old_len',84),('source_spans',{'0xDF2806':40}),
                            ('line_spans',{}),('fixed',[]),('source_texts',{}),
                            ('ptr_off','0xDF1DA4'),('layout_controls',{'tail':5})):
            changed=copy.deepcopy(after);changed[-1][field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):
                validate(old,new,before,changed)


if __name__=='__main__':unittest.main()
