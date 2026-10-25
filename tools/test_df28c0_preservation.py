"""Exercise all-2980 preservation, fragments, joiners and prior-candidate neighbor."""
import copy
import unittest
from df28c0_contract import MESSAGE, PAYLOAD, METADATA
from qa_df28c0_preservation import validate


class PreservationTests(unittest.TestCase):
    def fixture(self):
        old = bytearray(0x1000000)
        # Deliberately translated native neighbor: compare candidate-to-candidate.
        old[0xDF28A0:0xDF28C0] = b'K' * 32
        old[0xDF2900:0xDF2940] = b'T' * 64
        old[0xDF1E64:0xDF1E6C] = bytes.fromhex('19000000c028df08')
        new = bytearray(old)
        before, after = [], []
        for i in range(2980):
            key = (0xDF1F2C, 0xDF2804, 0xDF26FC)[i] if i < 3 else 0x100000 + i * 64
            addr, target, site = 0xA40000 + i * 64, 0xA80000 + i * 64, 0x1000 + i * 4
            size = (66, 80, 90)[i] if i < 3 else 59
            if i < 3: addr, target = 0xA20000 + i*128, 0xA30000 + i*128
            m = dict(msg=hex(key), status='relocated', new_addr=hex(addr), new_len=size,
                     ptr_off=hex(site), ptr_sites=[hex(site)], source_line_fragments={'0xDF278C': [[52,2],[58,1]]},
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
        added=copy.deepcopy(METADATA); added['new_addr']='0xAC0000'
        after.append(added)
        new[0xAC0000:0xAC0000+66] = PAYLOAD
        new[0xDF1E68:0xDF1E6C] = (0x08AC0000).to_bytes(4,'little')
        return old,new,before,after

    def test_all_logical_fields_and_future_fields_protected(self):
        args=self.fixture()
        self.assertEqual(validate(*args)['preserved'],2980)
        for field in args[2][0]:
            if field == 'new_addr': continue
            changed=copy.deepcopy(args[3]); changed[0][field]=None
            with self.subTest(field=field),self.assertRaises((AssertionError,TypeError)):
                validate(args[0],args[1],args[2],changed)
        for field in args[2][0]:
            changed=copy.deepcopy(args[3]);del changed[0][field]
            with self.subTest(missing=field), self.assertRaises((AssertionError,KeyError)):
                validate(args[0],args[1],args[2],changed)
        changed=copy.deepcopy(args[3]);changed[0]['unexpected_logical_field']=1
        with self.assertRaises(AssertionError):validate(args[0],args[1],args[2],changed)

    def test_payload_pointers_native_neighbor_and_population(self):
        old,new,before,after=self.fixture()
        for which,offset in (('old',0x1000),('new',0x1000),('old',0xA20000+65),
                            ('new',0xA30000+65),('new',0xDF28A0),('new',0xDF293F),
                            ('new',0xDF28EC),('new',0xDF28C0),('new',0xDF28FD),('new',0xAC0000),('new',0xDF1E64),('old',0xDF1E68),('old',0x8000),('new',0x8000)):
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
                            ('ptr_off','0xDF1E64'),('layout_controls',{'tail':5})):
            changed=copy.deepcopy(after);changed[-1][field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):
                validate(old,new,before,changed)

    def test_pointer_membership_joiner_and_extra_record_mutations(self):
        old,new,before,after=self.fixture()
        # Equal metadata in both manifests must not hide a false ptr_off.
        before[0]['ptr_off']=after[0]['ptr_off']='0x9000'
        with self.assertRaises(AssertionError):validate(old,new,before,after)
        old,new,before,after=self.fixture()
        changed=copy.deepcopy(after)
        changed[0]['source_fragment_joiners']['0xDF278C']=['']
        with self.assertRaises(AssertionError):validate(old,new,before,changed)
        extra=copy.deepcopy(after[0]);extra['msg']='0x222222'
        with self.assertRaises(AssertionError):validate(old,new,before,after+[extra])
        with self.assertRaises(AssertionError):validate(old,new,before+[before[0]],after)



if __name__=='__main__':unittest.main()
