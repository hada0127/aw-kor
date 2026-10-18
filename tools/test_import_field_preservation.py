"""Untranslated/noise fields cannot silently overwrite ROM data with fragments."""
import collections
import unittest
import build_korean_full as B


class ImportFieldTests(unittest.TestCase):
    def test_noise_that_encoded_to_empty_is_rejected(self):
        self.assertEqual(B.encode_text('劔劔',{},collections.Counter(),0x8AFAA0),b'')
        self.assertEqual(B.unencodable_import_field('劔劔',{},0x8AFAA0),{'劔':2})

    def test_partial_symbol_output_is_also_rejected(self):
        text='栫°拠＝＝＝＝＝欠＝建'
        self.assertTrue(B.encode_text(text,{},collections.Counter(),0xD2F069))
        self.assertEqual(set(B.unencodable_import_field(text,{},0xD2F069)),set('栫拠欠建'))

    def test_representable_labels_and_authored_korean_keep_existing_encoder(self):
        for text in ('ABC 12','１２３','?!'):
            self.assertEqual(B.unencodable_import_field(text,{},0x800000),{})
        self.assertEqual(B.unencodable_import_field('검',{ '검':0x8840 },0x800000),{})


if __name__=='__main__':unittest.main()
