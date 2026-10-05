"""Guard/runtime-byte regression for the seven native terrain captions."""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import part2_terrain_movement_labels as p

class TerrainMovementTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=(p.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
  cls.rom=bytearray(cls.original);cls.stats=p.patch(cls.rom,cls.original);cls.writes=p.expected_writes(cls.original)
  cls.regions=p.capture_regions(cls.rom,cls.original)
 def test_reviewed_code_and_atlas_golden_and_source_literal_chain(self):
  self.assertEqual(hashlib.sha256(p.CODE).hexdigest(),'49b4df10e3f43a1d7f6dd8b608b65408585961a009d558e8dd569373827270b3')
  self.assertEqual(hashlib.sha256(p.render(self.original)).hexdigest(),'f4c2969cc30d9b68168556c5ddbc05ba2872226d14702fa4e7f89a94d0c92fb5')
  self.assertEqual(struct.unpack_from('<I',self.original,0x31970c)[0],0x08814fc0)
  self.assertEqual(struct.unpack_from('<I',self.original,0x814fc0)[0],0x0201db40)
  self.assertEqual(len(self.writes),8);self.assertEqual(self.stats['additional_oam'],0)
 def test_tracked_asm_assembles_to_reviewed_embedded_bytes(self):
  if not shutil.which('clang'):self.skipTest('clang unavailable; embedded byte and ASM SHA guards still run')
  with tempfile.TemporaryDirectory(dir=p.ROOT/'temp',prefix='terrain_asm_')as directory:
   obj=Path(directory)/'code.o';subprocess.run(['clang','-target','armv4t-none-eabi','-c',str(p.ASM),'-o',str(obj)],check=True,capture_output=True)
   raw=obj.read_bytes();self.assertEqual(raw[:6],b'\x7fELF\x01\x01')
   offset=struct.unpack_from('<I',raw,32)[0];size,count,names_index=struct.unpack_from('<HHH',raw,46)
   headers=[struct.unpack_from('<10I',raw,offset+i*size)for i in range(count)]
   names_header=headers[names_index];names=raw[names_header[4]:names_header[4]+names_header[5]]
   sections={names[h[0]:].split(b'\0',1)[0]:raw[h[4]:h[4]+h[5]]for h in headers}
   self.assertEqual(sections[b'.text'],p.CODE);self.assertNotIn(b'.rel.text',sections);self.assertNotIn(b'.rela.text',sections)
 def test_only_eight_owned_regions_change_and_native_exit_is_untouched(self):
  restored=bytearray(self.rom)
  for a,data in self.writes:restored[a:a+len(data)]=self.original[a:a+len(data)]
  self.assertEqual(restored,self.original)
  self.assertEqual(self.rom[0x347700:0x347710],self.original[0x347700:0x347710])
  self.assertEqual(self.rom[0x83e0d8:0x83e0dc],self.original[0x83e0d8:0x83e0dc])
 def test_parent_wait1_and_original_callback_timing_preserved(self):
  p.validate_parent_script(self.original)
  self.assertEqual(self.rom[0x83e090:0x83e0b8],self.original[0x83e090:0x83e0b8])
  self.assertEqual(self.rom[0x83e0bc:0x83e0d0],self.original[0x83e0bc:0x83e0d0])
  self.assertEqual(struct.unpack_from('<I',self.rom,0x83e0b8)[0],0x08000000+p.CAVE+p.SYMBOLS['late_exit_bridge']+1)
  late=p.CODE[p.SYMBOLS['late_exit_bridge']:p.SYMBOLS['clear_cells']]
  self.assertIn(struct.pack('<I',0x083476f5),late);self.assertIn(struct.pack('<I',0x08311c7d),late)
 def test_native_destinations_and_draw_clear_geometry(self):
  self.assertEqual(struct.unpack_from('<7I',p.CODE,p.SYMBOLS['obj_destinations']),p.obj_destinations(self.original))
  offsets=struct.unpack_from('<28H',p.CODE,p.SYMBOLS['cell_offsets']);self.assertEqual(offsets,p.CELL_OFFSETS)
  coords=dict(self.writes)[0x83e081];costs=dict(self.writes)[0x83e06c]
  for side in(0,128):
   for subset in range(128):
    for index in range(subset.bit_count()):
     x=side+coords[index*2]+2;y=coords[index*2+1];off=(x+32)//8*2+y//8*64
     self.assertIn(off,offsets[::2]);self.assertIn(off+64,offsets);self.assertEqual(x+40,side+costs[index*2]*8)
 def test_generated_visible_icon_pixels_preserved(self):
  from part2_purchase_labels import pixels
  atlas=p.render(self.original)
  for index in range(7):
   a=0x454494+index*256;old=pixels(self.original[a:a+256],16);new=pixels(atlas[index*256:(index+1)*256],16);mask=p.caption_mask(28+index)
   for y in range(16):
    for x in range(32):
     if (x,y)not in mask and old[y][x]:self.assertEqual(new[y][x],old[y][x],(index,x,y))
 def test_atomic_source_cave_and_native_mutation_rejection(self):
  for a in(0x454494,0x45eb74,0x3474f6,0x83e0b4,0x31970c,0x38b434,0x31bc38,0x83e0e8,p.CAVE,p.ATLAS,p.CAVE+p.CAPACITY-1):
   rom=bytearray(self.original);rom[a]^=1;before=bytes(rom)
   with self.assertRaises(ValueError):p.patch(rom,self.original)
   self.assertEqual(rom,before)
  with patch.object(p,'FONT_SHA256','wrong'):
   with self.assertRaisesRegex(ValueError,'font changed'):p.render(self.original)
 def test_unrelated_translation_is_allowed_but_global_interior_pointer_is_not(self):
  rom=bytearray(self.original);rom[0x200000]^=1;p.patch(rom,self.original);self.assertNotEqual(rom[0x200000],self.original[0x200000])
  rom=bytearray(self.original);struct.pack_into('<I',rom,0xf31001,0x083472bd)
  with self.assertRaisesRegex(ValueError,'global incoming'):p.patch(rom,self.original)
 def test_original_inventory_is_explicit_and_has_no_hook_interior_entries(self):
  refs=p.original_inventory(self.original)
  self.assertEqual(set(refs),p.ORIGINAL_REFS);p._validate_original_inventory(refs)
  self.assertEqual(struct.unpack_from('<I',self.original,0x83dfac)[0],0x0883db6a)
  self.assertEqual([r for r in refs if r[2]==0x347475],[('pointer',0x83e0f8,0x347475)])
  # Equal original/current inventories must still reject an unsafe original
  # entry or a PC-relative load whose word crosses the beginning of a hook.
  for site,n,_ in p.SITES:
   for extra in (('thumb_bl',0x1000,site+2),('pointer',0x1001,site+3),
                 ('thumb_ldr',0x1000,site-2)):
    bad=sorted(refs+[extra])
    with patch.object(p,'original_inventory',return_value=bad),patch.object(p,'inventory',return_value=bad):
     with self.assertRaisesRegex(ValueError,'original hook interior/PC-data'):p._verify_xrefs(self.original,self.original)
  for refs_bad in (refs[:-1],refs+[('pointer',0x1000,0x83e090)]):
   with self.assertRaisesRegex(ValueError,'reference contexts'):p._validate_original_inventory(refs_bad)
 def test_new_coordinate_parent_or_init_consumer_is_rejected(self):
  # Every alignment is scanned, including callback pointers in non-code data.
  for target in (0x83e06c,0x83e081,0x83e090,0x83e0e8,0x347351,0x34735d,0x347475):
   rom=bytearray(self.original);struct.pack_into('<I',rom,0xf31001,0x08000000+target)
   with self.assertRaisesRegex(ValueError,'global incoming'):p._verify_xrefs(self.original,rom)
 def test_small_inventory_decodes_each_native_reference_kind(self):
  # Synthetic 768B images exercise the actual scanner, without full-ROM scans
  # or borrowing original assets. Both ADR signs failed before the bit23 fix.
  cases=(
   ('thumb_bl',0x100,0x182,struct.pack('<HH',0xf000,0xf83f)),
   ('thumb_b',0x100,0x182,struct.pack('<H',0xe03f)),
   ('thumb_cond',0x100,0x182,struct.pack('<H',0xd13f)),
   ('thumb_ldr',0x100,0x180,struct.pack('<H',0x481f)),
   ('thumb_adr',0x100,0x180,struct.pack('<H',0xa01f)),
   ('arm_b',0x100,0x184,struct.pack('<I',0xea00001f)),
   ('arm_bl',0x100,0x184,struct.pack('<I',0xeb00001f)),
   ('arm_ldr',0x100,0x180,struct.pack('<I',0xe59f0078)),
   ('arm_ldr',0x200,0x180,struct.pack('<I',0xe51f0088)),
   ('arm_adr',0x100,0x180,struct.pack('<I',0xe28f0078)),
   ('arm_adr',0x200,0x180,struct.pack('<I',0xe24f0088)),
  )
  with patch.multiple(p,SPANS=((0x180,10),),INTEREST=set(range(0x180,0x18a)),_XREF_SITES=((0x180,10),)):
   self.assertEqual(p.inventory(bytes(768)),[])
   for kind,source,target,code in cases:
    with self.subTest(kind=kind,source=source,code=code.hex()):
     rom=bytearray(768);rom[source:source+len(code)]=code
     self.assertIn((kind,source,target),p.inventory(rom))
 def test_final_gate_rejects_code_atlas_native_and_reservation_hole_changes(self):
  p.verify_generated(self.rom,self.original);p.verify_regions(self.rom,self.original,self.regions)
  for a in(p.CAVE,p.CAVE+len(p.CODE),p.ATLAS,p.ATLAS+2240,0x3474f6,0x45eb74):
   rom=bytearray(self.rom);rom[a]^=1
   with self.assertRaises(ValueError):p.verify_regions(rom,self.original,self.regions)
  with self.assertRaises(ValueError):p.verify_regions(self.rom,self.original,{})
 def test_actual_builder_editor_override_roundtrip_preserves_code_and_captures_atlas(self):
  import build_korean_full as builder
  import export_sprites as export
  lab=p.editor_labels()[0];self.assertEqual(sorted(lab['perm']),list(range(70)))
  atlas=p.render(self.original);visual=b''.join(atlas[i*32:i*32+32]for i in lab['perm'])
  grid,w,h=export.tiles_to_indices(visual,5);self.assertEqual((w,h),(40,112));grid[0][0]^=1
  spec={'id':p.ASSET_ID,'labels':[dict(lab,offset_int=p.ATLAS)]};rom=bytearray(self.rom)
  with tempfile.TemporaryDirectory(dir=p.ROOT/'temp',prefix='terrain_editor_')as directory:
   base=Path(directory);ov=base/'overrides.json';ov.write_text(json.dumps({p.ASSET_ID:{'indices':grid}}))
   result=builder.apply_sprite_overrides(rom,objl_specs=[spec],ov_path=str(ov),idx_path=str(base/'missing.json'),report_path=str(base/'report.json'))
  self.assertEqual(result['applied'],1);self.assertEqual(result['skipped'],0)
  self.assertNotEqual(rom[p.ATLAS:p.ATLAS+2240],self.rom[p.ATLAS:p.ATLAS+2240])
  self.assertEqual(rom[p.CAVE:p.CAVE+len(p.CODE)],p.CODE)
  with self.assertRaises(ValueError):p.verify_generated(rom,self.original)
  snapshot=p.capture_regions(rom,self.original);p.verify_regions(rom,self.original,snapshot)
  rom[p.ATLAS]^=1
  with self.assertRaises(ValueError):p.verify_regions(rom,self.original,snapshot)
if __name__=='__main__':unittest.main()
