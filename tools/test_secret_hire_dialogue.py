import collections,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import secret_hire_dialogue as S

class SecretHireTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unknown=collections.Counter();data=B.encode_full_fidelity(text,self.codes,unknown,address);self.assertFalse(unknown);return data
 def fixture(self):
  rom=bytearray(self.original);payload=S.expected(self.original,self.encode);target=0xA3D000
  rom[target:target+len(payload)]=payload;struct.pack_into('<I',rom,S.POINTER,target+0x08000000);return rom
 def test_full_approved_meaning_and_controls(self):
  payload=S.expected(self.original,self.encode)
  self.assertEqual(payload[:2],b'\x0a\x09');self.assertEqual(payload[-6:],b'k\x0a\x00\x00\x00\x00');self.assertEqual(payload.count(b'\x72\x0a\x09'),1)
  self.assertEqual(S.verify(self.fixture(),self.original,self.encode)['status'],'PASS')
  self.assertGreater(len(payload),S.END-S.START)
 def test_source_pointer_control_and_truncated_payload_rejected(self):
  for offset in (S.START,S.POINTER,S.TEXT_END):
   original=bytearray(self.original);original[offset]^=1
   with self.assertRaisesRegex(ValueError,'original'):S.expected(original,self.encode)
  for offset in (0xA3D000,0xA3D010,S.POINTER):
   rom=self.fixture();rom[offset]^=1
   with self.assertRaises(ValueError):S.verify(rom,self.original,self.encode)
 def test_old_inplace_pointer_rejected(self):
  with self.assertRaisesRegex(ValueError,'relocation'):S.verify(self.original,self.original,self.encode)
 def repoint(self, layouts):
  from dialogue_repoint import repoint_messages
  rom=bytearray(self.original);rom[0xA3D000:0xA3D100]=b'\xff'*256
  manifest,stats=repoint_messages(rom,self.original,fixable=lambda a:a==S.ADDRESS,
   fixed_bytes=lambda a:self.encode(S.TEXT,a),fit_level_dlg=lambda a:6,decode_text=lambda b:'',
   cell_width=lambda a:54,slots={S.ADDRESS:44},line_index={S.ADDRESS:(44,'original')},
   table_offsets=[],extra_messages={S.START:[S.POINTER]},free_start=0xA3D000,free_end=0xA3D100,
   line_layouts=layouts)
  return rom,manifest,stats
 def test_real_allocator_requires_explicit_lossless_layout(self):
  rom,manifest,stats=self.repoint({})
  self.assertEqual(stats.get('relocated',0),0)
  rom,manifest,stats=self.repoint(S.layout(self.original,self.encode))
  self.assertEqual(stats['relocated'],1)
  self.assertEqual(S.verify(rom,self.original,self.encode)['status'],'PASS')
  self.assertEqual(rom[S.START:S.END],self.original[S.START:S.END])
  changed={i for i,(a,b) in enumerate(zip(rom,self.original)) if a!=b}
  self.assertTrue(all(0xA3D000<=a<0xA3D100 or S.POINTER<=a<S.POINTER+4 for a in changed))
 def test_layout_cannot_drop_text_or_inject_controls(self):
  rows=S.layout(self.original,self.encode)[S.ADDRESS]
  for bad in ((rows[0],rows[1][:-2]),(rows[0]+b'\x00',rows[1]),(rows[0],)):
   with self.assertRaisesRegex(ValueError,'exact full text'):self.repoint({S.ADDRESS:bad})
 def test_all_authorities_match_approved_baseline(self):
  root=Path(B.BASE);key='0x00DFD082'
  self.assertEqual(json.loads((root/'data/bteam_baseline.json').read_text())['overrides'][key],S.TEXT)
  self.assertEqual(json.loads((root/'data/dialogue_overrides.json').read_text())[key],S.TEXT)
  self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[S.ADDRESS],S.TEXT)
  with (root/'data/translation_for_import.csv').open() as f:rows=[r for r in csv.DictReader(f) if r['address']==key]
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['korean'],S.TEXT);self.assertEqual(int(rows[0]['length']),len(S.TEXT.encode()))
  with (root/'data/address_text_overrides.tsv').open() as f:rows=[r for r in csv.reader(f,delimiter='\t') if r and r[0]==key]
  self.assertEqual(rows,[[key,S.TEXT]])

if __name__=='__main__':unittest.main()
