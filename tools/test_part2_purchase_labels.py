from pathlib import Path
import hashlib,json,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()/'tools'))
import part2_purchase_labels as labels
import build_korean_full as builder

class PurchaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=Path(builder.P.ROM).read_bytes();cls.expected=labels.render(cls.original)
 def test_source_ids_extents_and_font(self):
  labels.validate_source(self.original)
  self.assertEqual(len(labels.SPECS),15)
  self.assertEqual(sum(len(x)for x in self.expected.values()),5376)
  self.assertEqual([x[3]for x in labels.SPECS[9:]],list(labels.class_labels.LABELS.values())[:6])
  self.assertEqual(hashlib.sha256(labels.FONT.read_bytes()).hexdigest(),labels.FONT_SHA256)
 def test_all_visible_icon_pixels_outside_explicit_caption_mask_preserved(self):
  for native,a,h,text in labels.SPECS:
   old=labels.pixels(self.original[a:a+h*16],h);new=labels.pixels(self.expected[a],h);mask=labels.caption_mask(native,h)
   for y in range(h):
    for x in range(32):
     if (x,y)not in mask:self.assertEqual(old[y][x],new[y][x],(native,x,y))
   self.assertNotEqual(old,new)
   self.assertTrue(any(new[y][x]==1 for x,y in mask))
   self.assertTrue(any(new[y][x]==(4 if h==16 else 5)for x,y in mask))
   if h==32:self.assertEqual(old[:21],new[:21])
 def test_variable_move_icon_edge_and_shared_caption_region(self):
  grids=[labels.pixels(self.original[a:a+256],16)for _,a,_,_ in labels.SPECS[1:9]]
  for x,y in labels.caption_mask(36,16):self.assertEqual(len({g[y][x]for g in grids}),1)
  for _,a,_,_ in labels.SPECS[1:9]:
   old=labels.pixels(self.original[a:a+256],16);new=labels.pixels(self.expected[a],16)
   for x,y in ((14,7),(15,7),(14,8),(14,15)):self.assertEqual(new[y][x],old[y][x])
 def test_patch_changes_only_owned_byte_ranges_and_is_deterministic(self):
  rom=bytearray(self.original);labels.patch(rom,self.original);labels.verify_generated(rom,self.original)
  restore=bytearray(rom)
  for _,a,h,_ in labels.SPECS:restore[a:a+h*16]=self.original[a:a+h*16]
  self.assertEqual(restore,self.original);self.assertEqual(len(rom),len(self.original))
  self.assertEqual(labels.render(self.original),self.expected)
  for a,payload in self.expected.items():self.assertEqual(rom[a:a+len(payload)],payload)
 def test_source_consumer_palette_and_occupied_target_fail_before_any_write(self):
  for a in [*labels.SOURCE_SHA,*(g[0]for g in labels.GUARDS)]:
   rom=bytearray(self.original);rom[a]^=1;before=bytes(rom)
   with self.assertRaises(AssertionError):labels.patch(rom,self.original)
   self.assertEqual(rom,before)
   orig=bytearray(self.original);orig[a]^=1
   with self.assertRaises(AssertionError):labels.render(orig)
  with self.assertRaises(AssertionError):labels.patch(bytearray(3),self.original)
 def test_font_drift_rejected(self):
  labels.font.cache_clear()
  with patch.object(labels,'FONT_SHA256','wrong'):
   with self.assertRaisesRegex(AssertionError,'font changed'):labels.render(self.original)
  labels.font.cache_clear()
 def test_short_bdf_glyph_baseline_and_caption_clipping(self):
  # 보 starts y22 and ends y27; 병 includes the seventh baseline row28.
  grid=labels.pixels(self.expected[0x45B134],32)
  first={y for y in range(21,30)for x in range(8,15)if grid[y][x]==1}
  second={y for y in range(21,30)for x in range(16,23)if grid[y][x]==1}
  self.assertEqual((min(first),max(first)),(22,27));self.assertEqual((min(second),max(second)),(22,28))
 def test_real_synthetic_editor_override_preserved_and_final_corruption_rejected(self):
  rom=bytearray(self.original);labels.patch(rom,self.original)
  builder.OBJLABEL_SPRITES.clear()
  builder.rec_objlabel(labels.ASSET_ID,'part2_objlabel/purchase_captions','2편 구매 정보카드',labels.editor_labels())
  import export_sprites as ES
  tile_data=b''.join(self.expected[a] for _,a,_,_ in labels.SPECS)
  cols=ES.guess_cols(len(tile_data)//32)
  grid,w,h=ES.tiles_to_indices(tile_data,cols)
  self.assertEqual((cols,w,h),(8,64,168))
  grid[0][0]=3
  with tempfile.TemporaryDirectory(dir=(Path(__file__).resolve().parent if 'temp' in Path(__file__).resolve().parts else Path(builder.BASE)/'temp'),prefix='part2_purchase_editor_')as directory:
   base=Path(directory);ov=base/'override.json';ov.write_text(json.dumps({labels.ASSET_ID:{'indices':grid}}))
   result=builder.apply_sprite_overrides(rom,ov_path=str(ov),idx_path=str(base/'missing.json'),report_path=str(base/'report.json'))
  self.assertEqual(result['applied'],1);self.assertEqual(result['skipped'],0)
  self.assertEqual(labels.pixels(rom[0x454B94:0x454C94],16)[0][0],3)
  regions=labels.capture_regions(rom,self.original);labels.verify_regions(rom,regions)
  rom[0x454B94]^=1
  with self.assertRaisesRegex(AssertionError,'after editor'):labels.verify_regions(rom,regions)
  rom[0x454B94]^=1
  rom[0x45EB74]^=1
  with self.assertRaisesRegex(AssertionError,'palette changed'):labels.verify_regions(rom,regions)
  rom[0x45EB74]^=1
  del regions[0x454B94]
  with self.assertRaisesRegex(AssertionError,'extents'):labels.verify_regions(rom,regions)
if __name__=='__main__':unittest.main()
