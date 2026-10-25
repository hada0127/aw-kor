"""Full-field/order/byte/pointer failure fixtures using synthetic 2982 records."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_b82fac_contract import fixture
import b82fac_contract as c
import qa_b82fac_preservation as q


class PreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        o,r,m,w,k=fixture()
        cls.before=(bytes(r),copy.deepcopy(m),copy.deepcopy(w))
        c.append(o,r,m,w,**k)
        cls.after=(bytes(r),m,w)

    def reject(self,change):
        old,om,ow=self.before;new,nm,nw=self.after
        r,m,w=bytearray(new),copy.deepcopy(nm),copy.deepcopy(nw)
        change(r,m,w)
        with self.assertRaises(AssertionError):q.validate(old,r,om,m,ow,w)

    def test_complete_success_and_retired_role_transition(self):
        old,om,ow=self.before;new,nm,nw=self.after
        result=q.validate(old,new,om,nm,ow,nw)
        self.assertEqual(result['preserved'],2982)
        self.assertEqual(result['retired_allocations'],0)
        self.assertEqual(result['changed_bytes'],sum(a!=b for a,b in zip(old,new)))
        old_log=copy.deepcopy(ow);old_log[0][7]='bteam-round2-residual'
        q.validate(old,new,om,nm,old_log,nw)

    def test_unknown_metadata_address_order_pointer_and_payload_rejected(self):
        changes={
            'unknown-delete':lambda r,m,w:m[0].pop('unknown'),
            'unknown-add':lambda r,m,w:m[0].update(extra=1),
            'joiner':lambda r,m,w:m[0]['source_line_joiners'].update({m[0]['msg']:'1c'}),
            'address4':lambda r,m,w:m[0].update(new_addr=f'0x{c.ARENA_START+4:06X}'),
            'order':lambda r,m,w:m.__setitem__(slice(0,2),[m[1],m[0]]),
            'payload':lambda r,m,w:r.__setitem__(c.ARENA_START,1),
            'pointer':lambda r,m,w:r.__setitem__(0x10000,1),
            'ptr-off':lambda r,m,w:m[0].update(ptr_off='0x010004'),
            'ptr-sites':lambda r,m,w:m[0].update(ptr_sites=['0x010000','0x010004']),
            'native':lambda r,m,w:r.__setitem__(c.MESSAGE,0),
            'native-before':lambda r,m,w:r.__setitem__(c.MESSAGE-1,0),
            'native-after':lambda r,m,w:r.__setitem__(c.END,0),
            'sole-pointer':lambda r,m,w:r.__setitem__(c.SITE,0),
            'other-table':lambda r,m,w:r.__setitem__(c.SITE-4,0),
            'new-payload':lambda r,m,w:r.__setitem__(c.APPEND,0),
            'alignment':lambda r,m,w:r.__setitem__(c.APPEND+50,0),
            'font':lambda r,m,w:r.__setitem__(0xF00100,0),
            'old-owner':lambda r,m,w:w[0].__setitem__(7,'bteam-round2-baseline'),
            'new-owner-missing':lambda r,m,w:w.pop(),
            'new-owner-provenance':lambda r,m,w:w[-1][8].update(source_spans={c.KEY:46}),
            'extra-skip':lambda r,m,w:m.append(dict(msg=c.KEY,status='skip_wide_line')),
        }
        for name,change in changes.items():
            with self.subTest(name=name):self.reject(change)

    def test_lossless_full_arrays_and_recomputation(self):
        _,m,_=self.after
        requested=[f'0x{0xD00000+i*2:08X}' for i in range(1701)]
        missing=[f'0x{0xE00000+i*2:08X}' for i in range(9)]
        data=dict(requested=requested+missing,unfulfilled=missing)
        q.lossless(data,copy.deepcopy(data),m)
        for key in ('requested','unfulfilled'):
            after=copy.deepcopy(data);after[key].reverse()
            with self.assertRaises(AssertionError):q.lossless(data,after,m)
        bad=copy.deepcopy(data);bad['requested'][-1]='0x00B82FAC'
        with self.assertRaises(AssertionError):q.lossless(bad,bad,m)
        bad=copy.deepcopy(m);bad[0]['fixed']=[]
        with self.assertRaises(AssertionError):q.lossless(data,data,bad)


if __name__ == '__main__':unittest.main()
