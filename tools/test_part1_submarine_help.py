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
  # plan_C B-pin late writer (fixB C1 review #1): the reviewed final rows keep the
  # row-3 sentence space and outgrow the repointer allocation, so they move to a
  # fresh allocation at the aligned high water and the pointer follows.
  source=H.expected_payload(self.original,self.encode,final=False);self.assertEqual(source[:2],b'\x0a\x09')
  entry=manifest[0];target=int(entry['new_addr'],16);final=H.expected_payload(self.original,self.encode)
  self.assertEqual(bytes(rom[target:target+len(source)]),source);self.assertEqual(entry['new_len'],len(source))
  self.assertGreater(len(final),(entry['new_len']+3)//4*4)
  self.assertTrue(H.verify(rom,self.original,manifest,self.encode,final=False)['status']=='PASS')
  fresh=(target+entry['new_len']+3)&~3;self.assertEqual(set(self.original[fresh:fresh+len(final)]),{0xFF})
  rom[fresh:fresh+len(final)]=final;struct.pack_into('<I',rom,H.POINTER,0x08000000+fresh)
  entry.update(new_addr=f'0x{fresh:06X}',new_len=len(final));self.fresh=(target,fresh)
  return rom,manifest
 def test_actual_repointer_preserves_four_rows_controls_and_complete_text(self):
  rom,manifest=self.fixture();r=H.verify(rom,self.original,manifest,self.encode);self.assertEqual(r['status'],'PASS')
  payload=H.expected_payload(self.original,self.encode);text=self.decode(payload)
  visible=[]
  for row in text.split('r\n\t'):
   for control in ['\n','\t','\x00','0','2','3']:row=row.replace(control,'')
   visible.append(row.replace('　',' '))
  self.assertEqual(visible,list(H.FINAL_VISIBLE_ROWS))
  self.assertEqual(len(visible),4);self.assertTrue(all(len(row)<=14 for row in visible))  # p1_unit_help 112px = 14 cells (plan_C B-pin row 4 uses 13)
  self.assertIn('공격받는다。 인접한',H.FINAL_VISIBLE_ROWS)  # sentence space kept (fixB C1 review #1)
  outside=bytearray(rom);old,fresh=self.fresh;end=fresh+manifest[0]['new_len']
  outside[old:end]=self.original[old:end];outside[H.POINTER:H.POINTER+4]=self.original[H.POINTER:H.POINTER+4]
  self.assertEqual(outside,self.original)
 def test_bpin_entry_matches_contract_and_moves(self):
  import bpin_contract as P
  e=P.MESSAGES[H.SOURCE];old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
  self.assertEqual(new,H.expected_payload(self.original,self.encode))
  self.assertEqual(old,H.expected_payload(self.original,self.encode,final=False))
  self.assertEqual((e['stage'],e['kind'],e['from'],e['target']),('late','relocated',0xA799D0,0xA8D84C))
  self.assertGreater(len(new),P._align4(len(old)))
  for a,s,t in H.FINAL_ROWS:
   key=f'0x{a:06X}';off,size=e['fragments'][key][0]
   self.assertEqual(e['owner_texts'][key],t.replace('。','.'))
   self.assertEqual(new[off:off+size],bytes(self.encode(t,a)))
 def test_bpin_late_growth_moves_and_repoints(self):
  import bpin_contract as P
  from unittest import mock
  e=P.MESSAGES[H.SOURCE];old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
  def state():
   rom=bytearray(self.original);rom[e['from']:e['from']+len(old)]=old;struct.pack_into('<I',rom,H.POINTER,0x08000000+e['from'])
   manifest=[dict(msg='0xDEEDD8',status='relocated',new_addr=f"0x{e['from']:06X}",new_len=len(old),ptr_off='0xDEFAD0',
                  old_len=H.END-H.SOURCE,ptr_sites=['0xDEFAD0']),
             dict(msg='0xD821F0',status='relocated',new_addr='0xA8D824',new_len=38)]
   writes=[[e['from'],len(old),len(old),'',None,None,None,'repoint:0xDEEDD8',dict(source=H.SOURCE,ptr_sites=[H.POINTER])],
           [0xA8D824,40,38,'',None,None,None,'d821f0-late-append']]
   return rom,manifest,writes
  with mock.patch.object(P,'MESSAGES',{H.SOURCE:e}):
   rom,manifest,writes=state()
   self.assertEqual(P.apply('late',rom,self.original,manifest,writes),1)
   self.assertEqual(struct.unpack_from('<I',rom,H.POINTER)[0],0x08000000+0xA8D84C)
   self.assertEqual(bytes(rom[0xA8D84C:0xA8D84C+len(new)]),new);self.assertEqual(bytes(rom[e['from']:e['from']+len(old)]),old)
   self.assertEqual((manifest[0]['new_addr'],manifest[0]['new_len'],manifest[0]['rewrite']['previous_target']),('0xA8D84C',len(new),'0xA799D0'))
   self.assertEqual(sorted(w[7] for w in writes if w[0]==0xA8D84C),['bpin-contract-final','repoint:0xDEEDD8'])
   self.assertEqual([w[7] for w in writes if w[0]==e['from']],['dialogue-rewrite-retired-allocation'])
   self.assertEqual([w[7] for w in writes if w[0]==H.POINTER],['dialogue-rewrite-pointer'])
   self.assertEqual(H.verify(rom,self.original,manifest,self.encode)['status'],'PASS')
   # stale source payload, moved high water, occupied fresh slot and stale pointer reject
   for mutate in (lambda r,m,w:r.__setitem__(e['from']+5,r[e['from']+5]^1),
                  lambda r,m,w:m[1].update(new_len=50),
                  lambda r,m,w:r.__setitem__(0xA8D850,0),
                  lambda r,m,w:struct.pack_into('<I',r,H.POINTER,0x08000000+e['from']+4)):
    rom,manifest,writes=state();mutate(rom,manifest,writes)
    with self.assertRaises(AssertionError):P.apply('late',rom,self.original,manifest,writes)
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
