import ast,collections,copy,csv,json,struct,unittest
from pathlib import Path
import build_korean_full as B
import part1_ship_help as H
from dialogue_repoint import repoint_messages,is_sjis_lead
from text_metrics import visual_cells

class ShipHelpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(B.P.ROM).read_bytes();cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
 def encode(self,text,address):
  unknown=collections.Counter();r=B.encode_full_fidelity(text,self.codes,unknown,address);self.assertFalse(unknown);return r
 def decode(self,raw):
  reverse={v:k for k,v in self.codes.items()};out='';i=0
  while i<len(raw):
   if is_sjis_lead(raw[i]):
    pair=raw[i:i+2];out+=reverse.get(int.from_bytes(pair,'big'),pair.decode('shift_jis',errors='replace'));i+=2
   else:out+=chr(raw[i]);i+=1
  return out
 def fixture(self):
  rom=bytearray(self.original);texts={a:t for a,e,t in H.ROWS}
  manifest,_=repoint_messages(rom,self.original,fixable=lambda a:a in texts,fixed_bytes=lambda a:self.encode(texts[a],a),fit_level_dlg=lambda a:6,decode_text=self.decode,cell_width=lambda a:len(texts[a])*2,slots={a:e-a for a,e,t in H.ROWS},line_index={a:(e-a,self.original[a:e].decode('shift_jis')) for a,e,t in H.ROWS},table_offsets=[],extra_messages={m['source']:[m['pointer']] for m in H.MESSAGES},free_start=0xA3D000,free_end=0xA3E000)
  return rom,manifest
 def test_actual_repointer_complete_rows_controls_and_only_owned_ranges(self):
  rom,manifest=self.fixture();self.assertEqual(H.verify(rom,self.original,manifest,self.encode)['status'],'PASS');allowed=set()
  for m in H.MESSAGES:
   payload=H.expected_payload(self.original,self.encode,m);text=self.decode(payload)
   rows=text.split('\x0a\x00',1)[0].split('r')
   rows=tuple(row.replace('\x0a\x09','').replace('2','').replace('0','').replace('\u3000',' ') for row in rows)
   self.assertEqual(rows,m['visible']);self.assertTrue(all(visual_cells(row.replace(' ','\u3000'))<=24 for row in rows));self.assertNotIn(b'\x20',payload)
   def controls(raw):
    result=[];i=0
    while i<len(raw):
     if is_sjis_lead(raw[i]):i+=2
     else:result.append(raw[i]);i+=1
    return result
   self.assertEqual(controls(payload),controls(self.original[m['source']:m['end']]))
   target=struct.unpack_from('<I',rom,m['pointer'])[0]-0x08000000
   allowed.update(range(target,target+(len(payload)+3)//4*4));allowed.update(range(m['pointer'],m['pointer']+4))
  self.assertFalse(any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(rom,self.original))))
 def test_source_digest_and_pointer_guards(self):
  for m in H.MESSAGES:
   for a in [m['source'],m['pointer']]:
    original=bytearray(self.original);original[a]^=1
    with self.assertRaisesRegex(ValueError,'source/pointer'):H.source_guard(original)
 def test_manifest_missing_duplicate_and_bounds_fail(self):
  rom,manifest=self.fixture()
  for modified in [[],manifest+manifest]:
   with self.assertRaises(ValueError):H.verify(rom,self.original,modified,self.encode)
  for key,value in [('ptr_off','0xDEFAD4'),('old_len',1),('new_len',1),('new_addr','0xA3D001'),('new_addr','0x100')]:
   modified=copy.deepcopy(manifest);modified[0][key]=value
   with self.assertRaises(ValueError):H.verify(rom,self.original,modified,self.encode)
 def test_each_message_pointer_text_and_style_mutation_fail(self):
  rom,manifest=self.fixture()
  for m in H.MESSAGES:
   target=struct.unpack_from('<I',rom,m['pointer'])[0]-0x08000000;payload=H.expected_payload(self.original,self.encode,m)
   offsets=[0,1,2,payload.index(b'\x72')]
   if b'\x32' in payload:offsets.append(payload.index(b'\x32'))
   for a in [m['pointer']]+[target+offset for offset in offsets]:
    broken=bytearray(rom);broken[a]^=1
    with self.assertRaises(ValueError):H.verify(broken,self.original,manifest,self.encode)
 def test_builder_source_authorities_and_actual_lossless_writer(self):
  overrides=json.loads((Path(B.BASE)/'data/dialogue_overrides.json').read_text())
  with (Path(B.BASE)/'data/translation_for_import.csv').open() as stream:found={int(r['address'],16):r for r in csv.DictReader(stream)}
  for a,e,t in H.ROWS:
   self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[a],t);self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[a],e);self.assertIn(a,B.PLAYTHROUGH_REPAIR_ROWS)
   source=overrides[f'0x{a:08X}']
   if a==0xDEECDE:
    baseline=json.loads((Path(B.BASE)/'data/bteam_baseline.json').read_text())['overrides']
    self.assertEqual(source,baseline[f'0x{a:08X}']);self.assertTrue(B.is_verified_bteam_spacing_repair(a,source,t))
    self.assertEqual(source.replace(' ',''),t.replace(' ',''))
   else:self.assertEqual(source,t)
   if a in found:
    self.assertEqual(found[a]['korean'],t);self.assertEqual(int(found[a]['length']),len(t.encode('utf-8')))
  tree=ast.parse(Path(B.__file__).read_text());writer=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='patch_script_row');_,members=B.load_direct_script_metadata()
  env=dict(vars(B));env.update(orig=self.original,rom=bytearray(self.original),syl_to_code=self.codes,unmapped=collections.Counter(),direct_script_members=members,_dlg_ov=overrides,required_script_repoints=set(),WRITE_LOG=[])
  exec(compile(ast.Module(body=[writer],type_ignores=[]),'<actual writer>','exec'),env)
  for a,e,t in H.ROWS:env['patch_script_row'](a,e,b'','ship test',source_text=t)
  for a in [0xDEE931,0xDEEB90,0xDEED2D]:self.assertIn(a,env['required_script_repoints'])

if __name__=='__main__':unittest.main()
