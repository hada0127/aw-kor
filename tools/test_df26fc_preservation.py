"""Exercise all-2976 preservation, including the next message's split tail."""
import copy
import unittest
from df26fc_contract import MESSAGE, PAYLOAD
from qa_df26fc_preservation import validate


class PreservationTests(unittest.TestCase):
    def fixture(self):
        old = bytearray(0x1000000)
        new = bytearray(old)
        before, after = [], []
        for i in range(2976):
            key = 0xDF2754 if i == 0 else 0x100000 + i * 64
            addr, target, site = 0xA40000 + i * 64, 0xA80000 + i * 64, 0x1000 + i * 4
            m = dict(msg=hex(key), status='relocated', new_addr=hex(addr), new_len=59,
                     ptr_sites=[hex(site)], source_line_fragments={'0xDF278C': [[52,2],[58,1]]},
                     source_fragment_joiners={'0xDF278C':['8140']}, layout_controls={},
                     source_texts={}, source_spans={}, line_spans={}, old_len=59,
                     future_logical_field={'preserve':True})
            n = copy.deepcopy(m); n['new_addr'] = hex(target)
            before.append(m); after.append(n)
            old[addr:addr+59] = new[target:target+59] = bytes([i % 256]) * 59
            old[site:site+4] = (0x08000000+addr).to_bytes(4,'little')
            new[site:site+4] = (0x08000000+target).to_bytes(4,'little')
        added=dict(msg=hex(MESSAGE),status='relocated',new_addr='0xAC0000',new_len=90,
                   ptr_sites=['0xDF1C88'])
        after.append(added)
        new[0xAC0000:0xAC0000+90] = PAYLOAD
        new[0xDF1C88:0xDF1C8C] = (0x08AC0000).to_bytes(4,'little')
        return old,new,before,after

    def test_all_logical_fields_and_future_fields_protected(self):
        args=self.fixture()
        self.assertEqual(validate(*args)['preserved'],2976)
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
        for which,offset in (('old',0x1000),('new',0x1000),('old',0xA40000),
                            ('new',0xA80000),('new',0xDF2754+58),('new',0xDF2751),
                            ('new',0xDF2729),('new',0xAC0000)):
            damaged=bytearray(old if which=='old' else new);damaged[offset]^=1
            with self.subTest(which=which,offset=hex(offset)),self.assertRaises(AssertionError):
                validate(damaged if which=='old' else old,damaged if which=='new' else new,before,after)
        for records in (after[:-1], after+[after[0]], after[1:]):
            with self.assertRaises(AssertionError):validate(old,new,before,records)


if __name__=='__main__':unittest.main()
