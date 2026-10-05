import collections,csv,json,unittest
from pathlib import Path
import build_korean_full as B
import polite_registration as C

class PoliteRegistrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unknown=collections.Counter();payload=B.encode_full_fidelity(text,self.codes,unknown,address);self.assertFalse(unknown);return payload
 def fixture(self):
  rom=bytearray(self.original)
  for start,address,text_end,end,pointer,text,digest in C.ROWS:
   p=self.encode(text,address);rom[address:text_end]=p+b' '*(text_end-address-len(p))
  return rom
 def test_full_text_fits_native_slots_and_keeps_choice_control(self):
  self.assertEqual([len(self.encode(row[5],row[1])) for row in C.ROWS],[16,26])
  rom=self.fixture();self.assertEqual(C.verify(rom,self.original,self.encode)['status'],'PASS')
  self.assertEqual(rom[0xDF9690:0xDF9698],bytes.fromhex('7251590a00000000'))
 def test_original_final_controls_and_old_tone_rejected(self):
  for start,address,text_end,end,pointer,text,digest in C.ROWS:
   for offset in (start,text_end,pointer):
    original=bytearray(self.original);original[offset]^=1
    with self.assertRaisesRegex(ValueError,'original'):C.verify(self.fixture(),original,self.encode)
    rom=self.fixture();rom[offset]^=1
    with self.assertRaisesRegex(ValueError,'controls/pointer'):C.verify(rom,self.original,self.encode)
   rom=self.fixture();old=text.replace('요','');p=self.encode(old,address);rom[address:text_end]=p+b' '*(text_end-address-len(p))
   with self.assertRaisesRegex(ValueError,'polite'):C.verify(rom,self.original,self.encode)
 def test_width_overflow_rejected(self):
  with self.assertRaisesRegex(ValueError,'exceeds'):C.verify(self.fixture(),self.original,lambda t,a:b'x'*100)
 def test_individual_protected_authorities(self):
  root=Path(B.BASE);base=json.loads((root/'data/bteam_baseline.json').read_text())['overrides'];ov=json.loads((root/'data/dialogue_overrides.json').read_text())
  with (root/'data/translation_for_import.csv').open(encoding='utf-8') as f:rows={r['address']:r for r in csv.DictReader(f)}
  for _,address,_,_,_,text,_ in C.ROWS:
   key=f'0x{address:08X}';self.assertEqual(base[key],text);self.assertEqual(ov[key],text);self.assertEqual(rows[key]['korean'],text);self.assertEqual(int(rows[key]['length']),len(text.encode()))
  self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xDF9656],C.ROWS[0][5])

if __name__=='__main__':unittest.main()
