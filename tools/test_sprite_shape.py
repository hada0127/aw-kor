"""Adversarial checks independent of the sprite fitter."""
import unittest
from PIL import Image
from qa_sprite_shape import uniform_reference, hada_uniform_reference, compare, compare_plate, components


class ShapeTest(unittest.TestCase):
    def test_natural_reference_passes(self):
        for ch in '캠페인상점편집통신트라이얼사운드룸!':
            self.assertFalse(compare(ch,uniform_reference(ch,20))['failures'],ch)

    def test_all_plate_syllables_keep_height_and_natural_aspect(self):
        import json
        from pathlib import Path
        from hangul_pixel_fit import plate_line
        # Declared geometry comes from the pinned, approved profile, never from
        # the generator's own constants.
        profile=json.loads((Path(__file__).resolve().parents[1]/'data/part2_mode_plate_geometry.json').read_text(encoding='utf-8'))
        for text in ('캠페인','자유전','상점','편집','통신','트라이얼','사운드룸'):
            mask,records=plate_line(text)
            scale=profile['labels'][text]['width_scale']
            self.assertLessEqual(scale, profile['max_width_scale'])
            for ch,box in records:
                actual=mask.crop(box)
                self.assertGreaterEqual(actual.getbbox()[3]-actual.getbbox()[1],20)
                self.assertFalse(compare_plate(ch,actual,scale)['failures'],ch)
                # An undeclared stretch is still rejected.
                self.assertIn('non-uniform scale', compare_plate(ch,actual,1.0)['failures'])

    def test_plate_oracle_rejects_blob_and_lost_stroke(self):
        import json
        from pathlib import Path
        from hangul_pixel_fit import plate_glyph
        scale=json.loads((Path(__file__).resolve().parents[1]/'data/part2_mode_plate_geometry.json').read_text(encoding='utf-8'))['labels']['통신']['width_scale']
        good=plate_glyph('통',scale)
        blob=good.copy()
        for y in range(2,7):
            for x in range(4,good.width-4): blob.putpixel((x,y),255)
        self.assertTrue(compare_plate('통',blob,scale)['failures'])
        thin=good.copy()
        for y in range(thin.height):
            for x in range(thin.width):
                if thin.getpixel((x,y)) and (x+y)%2: thin.putpixel((x,y),0)
        self.assertTrue(compare_plate('통',thin,scale)['failures'])

    def test_wide_plate_glyph_rejected(self):
        mask=uniform_reference('상',20)
        bad=mask.resize((56,20),Image.Resampling.NEAREST)
        self.assertIn('non-uniform scale',compare('상',bad)['failures'])

    def test_split_stroke_rejected(self):
        mask=uniform_reference('편',24).copy()
        before=len(components(mask))
        # Choose a full cut that splits a jamo, rather than only removing AA.
        for x in range(1,mask.width-1):
            cut=mask.copy()
            for y in range(cut.height): cut.putpixel((x,y),0)
            if len(components(cut))>before:
                self.assertIn('split/merged/stray components',compare('편',cut)['failures'])
                return
        self.fail('test did not find a splitting cut')

    def test_stray_component_rejected(self):
        mask=uniform_reference('통',20)
        bad=Image.new('L',(mask.width+5,mask.height));bad.paste(mask,(0,0))
        bad.putpixel((bad.width-1,5),255)
        self.assertIn('split/merged/stray components',compare('통',bad)['failures'])

    def test_exclamation_requires_separated_dot(self):
        mask=uniform_reference('!',22).copy()
        self.assertEqual(len(components(mask)),2)
        for x,y in min(components(mask),key=len):mask.putpixel((x,y),0)
        self.assertTrue(compare('!',mask)['failures'])

    def test_native_galmuri_effects_preserve_nu_components(self):
        from PIL import ImageFont,ImageDraw
        from pathlib import Path
        from hangul_pixel_fit import paint_bitmap
        font=ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'reference/fonts/Galmuri11-Bold.ttf'),11)
        layer=Image.new('P',(40,20))
        records=paint_bitmap(layer,'누계',font,(2,0),6,outline=15)
        ref=Image.new('L',layer.size);draw=ImageDraw.Draw(ref);draw.fontmode='1';draw.text((2,0),'누계',font=font,fill=255)
        for ch,box in records:
            actual=layer.crop(box).point(lambda v:255 if v==6 else 0)
            self.assertFalse(compare(ch,actual,ref.crop(box))['failures'])

    def test_native_bitmap_cannot_be_squashed(self):
        reference=Image.new('L',(9,9))
        for y in (0,4,8):
            for x in range(9):reference.putpixel((x,y),255)
        self.assertFalse(compare('급',reference,reference)['failures'])
        bad=reference.resize((9,7),Image.Resampling.NEAREST)
        self.assertIn('non-uniform scale',compare('급',bad,reference)['failures'])

if __name__=='__main__':unittest.main()
