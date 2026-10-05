import ast,collections,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import return_mode_question as Q

class ReturnQuestionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,size,address):
  unknown=collections.Counter();result=B.encode_fit(text,size,self.codes,unknown,address);self.assertFalse(unknown);return result
 def fixture(self):
  rom=bytearray(self.original)
  for start,end,pointer in Q.ROWS:
   payload,level=self.encode(Q.TEXT,end-start,start);self.assertEqual(level,0);rom[start:end]=payload+b' '*(end-start-len(payload))
  return rom
 def test_level_zero_complete_polite_question_both_native_slots(self):
  rom=self.fixture();self.assertEqual(Q.verify(rom,self.original,self.encode)['status'],'PASS')
  for start,end,pointer in Q.ROWS:
   payload,_=self.encode(Q.TEXT,end-start,start);old,_=self.encode('모드 선택으로 돌아갈까?',end-start,start)
   self.assertNotEqual(payload,old);self.assertIn(self.codes['요'].to_bytes(2,'big'),payload)
 def test_old_informal_wording_rejected(self):
  for start,end,pointer in Q.ROWS:
   rom=self.fixture();payload,_=self.encode('모드 선택으로 돌아갈까?',end-start,start);rom[start:end]=payload+b' '*(end-start-len(payload))
   with self.assertRaisesRegex(ValueError,'approved text'):Q.verify(rom,self.original,self.encode)
 def test_original_and_final_control_pointer_guards(self):
  for start,end,pointer in Q.ROWS:
   for offset in [start,pointer]:
    original=bytearray(self.original);original[offset]^=1
    with self.assertRaisesRegex(ValueError,'original'):Q.verify(self.fixture(),original,self.encode)
   for offset in [end,pointer]:
    rom=self.fixture();rom[offset]^=1
    with self.assertRaisesRegex(ValueError,'control/pointer'):Q.verify(rom,self.original,self.encode)
 def test_lossy_encoding_rejected(self):
  with self.assertRaisesRegex(ValueError,'level-0'):Q.verify(self.fixture(),self.original,lambda text,size,a:(b'x',1))
 def test_authorities_match_approved_unchanged_baseline_and_writer(self):
  root=Path(B.BASE);ov=json.loads((root/'data/dialogue_overrides.json').read_text());base=json.loads((root/'data/bteam_baseline.json').read_text())['overrides']
  with (root/'data/translation_for_import.csv').open() as stream:rows={int(r['address'],16):r for r in csv.DictReader(stream)}
  for start,end,pointer in Q.ROWS:
   self.assertEqual(ov[f'0x{start:08X}'],Q.TEXT);self.assertEqual(base[f'0x{start:08X}'],Q.TEXT);self.assertEqual(rows[start]['korean'],Q.TEXT);self.assertEqual(int(rows[start]['length']),len(Q.TEXT.encode()))
  tree=ast.parse(Path(B.__file__).read_text());writers=[n for n in ast.walk(tree) if isinstance(n,ast.Tuple) and len(n.elts)>=3 and isinstance(n.elts[0],ast.Constant) and n.elts[0].value==0xA34CE8 and isinstance(n.elts[2],ast.Constant)]
  self.assertTrue(writers);self.assertTrue(all(n.elts[2].value==Q.TEXT for n in writers))

if __name__=='__main__':unittest.main()
