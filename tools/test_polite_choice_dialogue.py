import collections,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import polite_choice_dialogue as C
from dialogue_repoint import repoint_messages
class PoliteChoiceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unknown=collections.Counter();result=B.encode_full_fidelity(text,self.codes,unknown,address);self.assertFalse(unknown);return result
 def fit_level(self,address):
  payload,level=B.encode_fit(C.CANCEL,24,self.codes,collections.Counter(),address)
  return 6 if B.story_requires_lossless_repoint(address,payload,self.encode(C.CANCEL,address)) else level
 def fixture(self):
  r=bytearray(self.original);r[0xDF8EAE:0xDF8ED0]=self.encode(C.FIRST,0xDF8EAE);r[0xA3D000:0xA3D100]=b'\xff'*256
  m,s=repoint_messages(r,self.original,fixable=lambda a:a==0xDF969A,fixed_bytes=lambda a:self.encode(C.CANCEL,a),fit_level_dlg=self.fit_level,decode_text=lambda b:'',cell_width=lambda a:28,slots={0xDF969A:24},line_index={0xDF969A:(24,'あら、やっぱりやめるの？')},table_offsets=[],extra_messages={0xDF9698:[0xDF9AFC]},free_start=0xA3D000,free_end=0xA3D100,min_level=1)
  self.assertEqual(s.get('relocated',0),1,(m,s));return r
 def test_native_choice_contract_and_complete_words(self):
  r=self.fixture();self.assertEqual(C.verify(r,self.original,self.encode)['status'],'PASS')
  self.assertEqual(r[0xDF8ED0:0xDF8ED4],bytes.fromhex('7251590a'))
  self.assertTrue(C.cancel_payload(self.original,self.encode).endswith(bytes.fromhex('7251590a000000000000')))
 def test_source_pointer_and_final_choice_mutations_rejected(self):
  for a in (0xDF8EAE,0xDF969A,0xDF9CAC,0xDF9AFC):
   original=bytearray(self.original);original[a]^=1
   with self.assertRaisesRegex(ValueError,'original'):C.source_guard(original)
  for a in (0xDF8ED0,0xDF8ED1,0xDF8ED2,0xDF96B2,0xDF9AFC,0xA3D000+30):
   r=self.fixture();r[a]^=1
   with self.assertRaises(ValueError):C.verify(r,self.original,self.encode)
 def test_old_informal_first_question_rejected(self):
  r=self.fixture();p=self.encode('이 게임은 처음이야?',0xDF8EAE);r[0xDF8EAE:0xDF8ED0]=p+b' '*(34-len(p))
  with self.assertRaisesRegex(ValueError,'first-game'):C.verify(r,self.original,self.encode)
 def test_alias_and_storage_boundaries(self):
  original=bytearray(self.original);struct.pack_into('<I',original,0x100,0x08DF9698)
  with self.assertRaisesRegex(ValueError,'original'):C.source_guard(original)
  r=self.fixture();struct.pack_into('<I',r,0xDF9AFC,C.SPRITE_STORAGE_START+0x08000000)
  with self.assertRaisesRegex(ValueError,'bounded'):C.verify(r,self.original,self.encode)
 def test_authorities_preserve_approved_baseline(self):
  root=Path(B.BASE);base=json.loads((root/'data/bteam_baseline.json').read_text())['overrides'];ov=json.loads((root/'data/dialogue_overrides.json').read_text())
  with (root/'data/translation_for_import.csv').open(encoding='utf-8') as f:rows={r['address']:r for r in csv.DictReader(f)}
  for address,text in ((0xDF8EAE,C.FIRST),(0xDF969A,C.CANCEL)):
   key=f'0x{address:08X}';self.assertEqual(base[key],text);self.assertEqual(ov[key],text);self.assertEqual(rows[key]['korean'],text);self.assertEqual(int(rows[key]['length']),len(text.encode()))
  self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xDF8EAE],C.FIRST)
if __name__=='__main__':unittest.main()
