import collections,csv,json,unittest
from pathlib import Path
import build_korean_full as B
import map_design_intro as M

class MapDesignIntroTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,size,address):
  unknown=collections.Counter();value=B.encode_fit(text,size,self.codes,unknown,address);self.assertFalse(unknown);return value
 def fixture(self):
  rom=bytearray(self.original);payload,level=self.encode(M.TEXT,44,M.START);self.assertEqual(level,0);rom[M.START:M.END]=payload;return rom
 def test_exact_native_slot_complete_polite_text(self):
  rom=self.fixture();self.assertEqual(M.verify(rom,self.original,self.encode)['status'],'PASS')
  self.assertEqual(rom[:M.START],self.original[:M.START]);self.assertEqual(rom[M.END:],self.original[M.END:])
 def test_old_informal_or_lossy_text_rejected(self):
  rom=self.fixture();p,l=self.encode('여기서는 맵을 자유롭게 만들 수 있어.',44,M.START);rom[M.START:M.END]=p+b' '*(44-len(p))
  with self.assertRaisesRegex(ValueError,'polite'):M.verify(rom,self.original,self.encode)
  with self.assertRaisesRegex(ValueError,'level-0'):M.verify(self.fixture(),self.original,lambda t,s,a:(b'x'*44,1))
 def test_original_and_final_control_pointer_changes_rejected(self):
  for offset in (M.START,M.END,M.POINTER):
   original=bytearray(self.original);original[offset]^=1
   with self.assertRaisesRegex(ValueError,'original'):M.verify(self.fixture(),original,self.encode)
  for offset in (M.END,M.POINTER):
   rom=self.fixture();rom[offset]^=1
   with self.assertRaisesRegex(ValueError,'control/pointer'):M.verify(rom,self.original,self.encode)
 def test_protected_baseline_and_import_authorities_match(self):
  root=Path(B.BASE);key='0x00D82028'
  self.assertEqual(json.loads((root/'data/bteam_baseline.json').read_text())['overrides'][key],M.TEXT)
  self.assertEqual(json.loads((root/'data/dialogue_overrides.json').read_text())[key],M.TEXT)
  self.assertNotIn(M.START,B.ADDRESS_TEXT_OVERRIDES)
  with (root/'data/translation_for_import.csv').open() as f:rows=[r for r in csv.DictReader(f) if r['address']==key]
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['korean'],M.TEXT);self.assertEqual(int(rows[0]['length']),len(M.TEXT.encode()))

if __name__=='__main__':unittest.main()
