import collections,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import protected_help_apology as C
from dialogue_repoint import repoint_messages

class ProtectedHelpApologyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unknown=collections.Counter();result=B.encode_full_fidelity(text,self.codes,unknown,address);self.assertFalse(unknown);return result
 def fixture(self):
  rom=bytearray(self.original);rom[0xA3D000:0xA3D100]=b'\xff'*256
  payload=self.encode(C.APOLOGY,0xD8F6FE);rom[0xD8F6FE:0xD8F70E]=payload+b' '*8
  manifest,stats=repoint_messages(rom,self.original,fixable=lambda a:a==0xD82058,
   fixed_bytes=lambda a:self.encode(C.HELP,a),fit_level_dlg=lambda a:B.encode_fit(C.HELP,36,self.codes,collections.Counter(),a)[1],
   decode_text=lambda b:'',cell_width=lambda a:44,slots={0xD82058:36},line_index={0xD82058:(36,'作り方は「ヘルプ」に書いてあります。')},
   table_offsets=[],extra_messages={0xD82058:[0xD7EDD4]},free_start=0xA3D000,free_end=0xA3D100,min_level=1)
  self.assertEqual(stats['relocated'],1);return rom
 def test_full_help_relocation_and_apology_native_slot(self):
  rom=self.fixture();self.assertEqual(C.verify(rom,self.original,self.encode)['status'],'PASS')
  self.assertEqual(rom[0xD82058:0xD82080],self.original[0xD82058:0xD82080])
 def test_source_and_native_controls_fail_closed(self):
  for offset in (0xD82058,0xD8207C,0xD7EDD4,0xD8F6FE,0xD8F70E,0xDA4CB8):
   original=bytearray(self.original);original[offset]^=1
   with self.assertRaisesRegex(ValueError,'original'):C.source_guard(original)
  for offset in (0xD7EDD4,0xA3D000,0xA3D000+44,0xD8207C,0xD8F6FC,0xD8F706,0xD8F70E,0xDA4CB8):
   rom=self.fixture();rom[offset]^=1
   with self.assertRaises(ValueError):C.verify(rom,self.original,self.encode)
 def test_old_informal_apology_rejected(self):
  rom=self.fixture();old=self.encode('미안해',0xD8F6FE);rom[0xD8F6FE:0xD8F70E]=old+b' '*(16-len(old))
  with self.assertRaisesRegex(ValueError,'polite'):C.verify(rom,self.original,self.encode)
 def test_pointer_alias_width_and_storage_bounds_rejected(self):
  original=bytearray(self.original);struct.pack_into('<I',original,0x100,0x08D82058)
  with self.assertRaisesRegex(ValueError,'original'):C.source_guard(original)
  with self.assertRaisesRegex(ValueError,'width'):
   C.help_payload(self.original,lambda text,a:b'\x81\x40'*26)
  rom=self.fixture();struct.pack_into('<I',rom,0xD7EDD4,C.SPRITE_STORAGE_START+0x08000000)
  with self.assertRaisesRegex(ValueError,'bounded'):C.verify(rom,self.original,self.encode)
 def test_individual_source_authorities_match_baseline(self):
  root=Path(B.BASE);base=json.loads((root/'data/bteam_baseline.json').read_text())['overrides'];ov=json.loads((root/'data/dialogue_overrides.json').read_text())
  with (root/'data/translation_for_import.csv').open(encoding='utf-8') as f:csvrows={r['address']:r for r in csv.DictReader(f)}
  for address,text in ((0xD82058,C.HELP),(0xD8F6FE,C.APOLOGY)):
   key=f'0x{address:08X}';self.assertEqual(base[key],text);self.assertEqual(ov[key],text);self.assertEqual(csvrows[key]['korean'],text);self.assertEqual(int(csvrows[key]['length']),len(text.encode()))
  self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xD82058],C.HELP)

if __name__=='__main__':unittest.main()
