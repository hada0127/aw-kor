import unittest
import hashlib
from pathlib import Path
import build_korean_full as B
import part1_result_rank_word as R
class ResultRankWordTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.original=Path(B.P.ROM).read_bytes()
 def test_owned_strip_and_native_glyph_pixels(self):
  rom=bytearray(self.original);R.patch(rom,self.original,B._render_value_obj)
  self.assertEqual(rom[:R.START],self.original[:R.START]);self.assertEqual(rom[R.END:],self.original[R.END:])
  self.assertEqual(rom[R.END-32:R.END],bytes(32))
  before=B._render_value_obj('랭크',3,ink=1);after=rom[R.START:R.END]
  for x,y in zip(before,after):
   for shift in (0,4):
    if (x>>shift)&15:self.assertEqual((y>>shift)&15,1)
  self.assertEqual({v for b in after for v in (b&15,b>>4)},{0,1,5})
 def test_source_geometry_and_existing_writer_drift_rejected(self):
  for a in (R.START,R.TABLE,R.TABLE+8,R.END-1):
   original=bytearray(self.original);original[a]^=1
   with self.assertRaises(ValueError):R.patch(bytearray(original),original,B._render_value_obj)
   rom=bytearray(self.original);rom[a]^=1
   with self.assertRaises(ValueError):R.patch(rom,self.original,B._render_value_obj)
 def test_renderer_shape_and_ink_rejected(self):
  for raw in (bytes(95),bytes([0x22])*96):
   with self.assertRaises(ValueError):R.render(lambda *a,**k:raw)
 def test_exact_font_shadow_and_clipping(self):
  self.assertEqual(hashlib.sha256(R.render(B._render_value_obj)).hexdigest(),
                   '67b0207350d830bff0b32c4178935b1dd85c6250074e2db72cc9d61d0992520d')
  for x,y in ((0,7),(23,0)):
   raw=bytearray(96);raw[(x//8)*32+y*4+(x%8)//2]=1<<(4*(x%2))
   with self.assertRaisesRegex(ValueError,'clip'):R.render(lambda *a,**k:raw)
 def test_post_editor_snapshot_detects_late_overwrite(self):
  rom=bytearray(self.original);R.patch(rom,self.original,B._render_value_obj);snapshot=R.capture(rom);R.verify(rom,snapshot)
  for a in (R.START,R.TABLE,R.END-1):
   broken=bytearray(rom);broken[a]^=1
   with self.assertRaises(ValueError):R.verify(broken,snapshot)
if __name__=='__main__':unittest.main()
