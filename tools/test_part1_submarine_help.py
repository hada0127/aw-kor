import ast,collections,copy,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import part1_submarine_help as H
from dialogue_repoint import repoint_messages,is_sjis_lead

class SubmarineHelpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes()
  cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unmapped=collections.Counter();result=B.encode_full_fidelity(text,self.codes,unmapped,address)
  self.assertFalse(unmapped);return result
 def decode(self,raw):
  reverse={v:k for k,v in self.codes.items()};out='';i=0
  while i<len(raw):
   if is_sjis_lead(raw[i]):
    pair=raw[i:i+2];out+=reverse.get(int.from_bytes(pair,'big'),pair.decode('shift_jis',errors='replace'));i+=2
   else:out+=chr(raw[i]);i+=1
  return out
 def fixture(self):
  rom=bytearray(self.original);texts={a:t for a,e,t in H.ROWS}
  manifest,_=repoint_messages(rom,self.original,fixable=lambda a:a in texts,fixed_bytes=lambda a:self.encode(texts[a],a),fit_level_dlg=lambda a:6,decode_text=self.decode,cell_width=lambda a:len(texts[a])*2,slots={a:e-a for a,e,t in H.ROWS},line_index={a:(e-a,self.original[a:e].decode('shift_jis')) for a,e,t in H.ROWS},table_offsets=[],extra_messages={H.SOURCE:[H.POINTER]},free_start=0xA3D000,free_end=0xA3E000)
  return rom,manifest
 def test_actual_repointer_preserves_four_rows_controls_and_complete_text(self):
  rom,manifest=self.fixture();r=H.verify(rom,self.original,manifest,self.encode);self.assertEqual(r['status'],'PASS')
  payload=H.expected_payload(self.original,self.encode);text=self.decode(payload)
  visible=[]
  for row in text.split('r\n\t'):
   for control in ['\n','\t','\x00','0','2','3']:row=row.replace(control,'')
   visible.append(row.replace('　',' '))
  self.assertEqual(visible,['해상 유닛。”잠수”하면','잠수함、 호위함에만','공격받는다。 인접한','적이 없으면 안 보인다'])
  self.assertEqual(len(visible),4);self.assertTrue(all(len(row)<=12 for row in visible))
  outside=bytearray(rom);entry=manifest[0];target=int(entry['new_addr'],16)
  outside[target:target+entry['new_len']]=self.original[target:target+entry['new_len']];outside[H.POINTER:H.POINTER+4]=self.original[H.POINTER:H.POINTER+4]
  self.assertEqual(outside,self.original)
 def test_original_source_and_pointer_drift_reject(self):
  for address in [H.SOURCE,H.SOURCE+16,H.POINTER]:
   original=bytearray(self.original);original[address]^=1
   with self.assertRaisesRegex(ValueError,'source/pointer'):H.expected_payload(original,self.encode)
 def test_missing_duplicate_wrong_pointer_and_bounds_reject(self):
  rom,manifest=self.fixture()
  for changed in [[],manifest+manifest]:
   with self.assertRaises(ValueError):H.verify(rom,self.original,changed,self.encode)
  for key,value in [('ptr_off','0xDEFAD4'),('old_len',115),('new_len',1),('new_addr','0xA3D001'),('new_addr','0x100')]:
   changed=copy.deepcopy(manifest);changed[0][key]=value
   with self.assertRaises(ValueError):H.verify(rom,self.original,changed,self.encode)
  broken=bytearray(rom);broken[H.POINTER]^=4
  with self.assertRaisesRegex(ValueError,'final pointer'):H.verify(broken,self.original,manifest,self.encode)
 def test_text_and_style_control_mutations_reject(self):
  rom,manifest=self.fixture();target=int(manifest[0]['new_addr'],16);payload=H.expected_payload(self.original,self.encode)
  for offset in [0,1,2,payload.index(b'\x33'),payload.index(b'\x72')]:
   broken=bytearray(rom);broken[target+offset]^=1
   with self.assertRaisesRegex(ValueError,'text/control/style'):H.verify(broken,self.original,manifest,self.encode)
 def test_builder_authorities_use_complete_text_and_lossless_owner(self):
  overrides=json.loads((Path(B.BASE)/'data/dialogue_overrides.json').read_text())
  for a,e,t in H.ROWS:
   self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[a],t);self.assertEqual(overrides[f'0x{a:08X}'],t)
   self.assertIn(a,B.PLAYTHROUGH_REPAIR_ROWS);self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[a],e)
  with (Path(B.BASE)/'data/translation_for_import.csv').open() as stream:
   found={int(row['address'],16):row['korean'] for row in csv.DictReader(stream)}
  for a,e,t in H.ROWS:
   if a in found:self.assertEqual(found[a],t)
  tree=ast.parse(Path(B.__file__).read_text())
  main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
  self.assertFalse(any(isinstance(k,ast.Constant) and k.value==0xDEEDF0 for n in ast.walk(main) if isinstance(n,ast.Dict) for k in n.keys if k is not None), 'Fixed-length gap writer must not own expanded DEEDF0')
  writer=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='patch_script_row');_,members=B.load_direct_script_metadata()
  env=dict(vars(B));env.update(orig=self.original,rom=bytearray(self.original),syl_to_code=self.codes,unmapped=collections.Counter(),direct_script_members=members,_dlg_ov=overrides,required_script_repoints=set(),WRITE_LOG=[])
  exec(compile(ast.Module(body=[writer],type_ignores=[]),'<actual writer>','exec'),env)
  for a,e,t in H.ROWS:env['patch_script_row'](a,e,b'','submarine test',source_text=t)
  self.assertIn(0xDEEDF0,env['required_script_repoints']);self.assertIn(0xDEEDF8,env['required_script_repoints'])

if __name__=='__main__':unittest.main()
