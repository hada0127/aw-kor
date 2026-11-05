"""Builder guards for saved power title overrides."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
import part2_power_title_glyphs as titles
import test_part2_power_title_glyphs as glyph_tests
from export_sprites import tiles_to_indices


class PowerTitleOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        glyph_tests.PowerTitleTests.setUpClass()
        cls.fixture = glyph_tests.PowerTitleTests
        cls.sprite = {'id': titles.ASSET_ID, 'offset_int': titles.OFFSET,
                      'offset': hex(titles.OFFSET), 'type': 'lz77', 'tile_cols': 32,
                      'size': titles.RAW_SIZE, 'comp_size': titles.SLOT_SIZE, 'source': 'scan_lz77'}
        cls.palette = [[i * 17] * 3 for i in range(16)]
        cls.grid = tiles_to_indices(cls.fixture.rendered, 32)[0]

    def test_builder_rejects_stale_or_missing_binding_before_any_asset_write(self):
        from build_korean_full import apply_sprite_overrides
        for binding in (None, 'v1:' + '0' * 64):
            with self.subTest(binding=binding), tempfile.TemporaryDirectory(dir=titles.ROOT / 'temp', prefix='power_stale_build_') as directory:
                directory = Path(directory)
                record = {'indices': self.grid}
                if binding is not None:
                    record[titles.BINDING_KEY] = binding
                override = directory / 'overrides.json'
                override.write_text(json.dumps({titles.ASSET_ID: record}))
                before = override.read_bytes()
                rom = bytearray(self.fixture.patched)
                result = apply_sprite_overrides(rom, ov_path=str(override), report_path=str(directory / 'report.json'),
                                               power_title_context=(self.fixture.names, self.fixture.codes))
                self.assertEqual((result['applied'], result['skipped']), (0, 1))
                self.assertEqual(rom, self.fixture.patched)
                self.assertEqual(override.read_bytes(), before)
                self.assertIn('보존', json.loads((directory / 'report.json').read_text())['records'][0]['reason'])

    def test_capture_checks_binding_even_when_applied_bytes_equal_automatic_output(self):
        payload = bytes(self.fixture.patched[titles.ATLAS:titles.ATLAS + titles.ATLAS_CAPACITY])
        result = {'expected_writes': [(titles.ASSET_ID, titles.ATLAS, payload)]}
        with self.assertRaisesRegex(AssertionError, 'dictionary binding'):
            titles.capture_regions(self.fixture.patched, self.fixture.original, self.fixture.names, self.fixture.codes,
                                   editor_result=result)
        result['dictionary_bindings'] = {titles.ASSET_ID: titles.dictionary_binding(
            self.fixture.patched, self.fixture.names, self.fixture.codes)}
        result['expected_writes'][0] = (titles.ASSET_ID, titles.ATLAS, payload[:-1] + b'\1')
        with self.assertRaisesRegex(AssertionError, 'byte extent'):
            titles.capture_regions(self.fixture.patched, self.fixture.original, self.fixture.names, self.fixture.codes,
                                   editor_result=result)

    def test_binding_includes_same_count_order_changes_and_every_name(self):
        original = titles.dictionary_binding(self.fixture.patched, self.fixture.names, self.fixture.codes)
        names = dict(self.fixture.names)
        address = max(names)
        names[address] = '흑파도'
        rom = bytearray(self.fixture.patched)
        encode = lambda s: b''.join(self.fixture.codes[ch].to_bytes(2, 'big') for ch in s)
        rom[address:titles.NAMES_END] = encode(names[address]).ljust(titles.NAMES_END - address, b'\0')
        self.assertEqual(titles.bind_dictionary(rom, names, self.fixture.codes), self.fixture.dictionary)
        self.assertNotEqual(original, titles.dictionary_binding(rom, names, self.fixture.codes))

        names = dict(self.fixture.names)
        names[titles.NAMES_START] = '적기'
        dictionary = ''.join(dict.fromkeys(''.join(names.values())))
        rom = bytearray(self.fixture.patched)
        first_end = list(names)[1]
        rom[titles.NAMES_START:first_end] = encode('적기').ljust(first_end - titles.NAMES_START, b'\0')
        rom[titles.DICTIONARY:titles.DICTIONARY + titles.DICTIONARY_SIZE] = encode(dictionary).ljust(titles.DICTIONARY_SIZE, b'\0')
        self.assertEqual(len(dictionary), len(self.fixture.dictionary))
        self.assertNotEqual(dictionary, self.fixture.dictionary)
        self.assertNotEqual(original, titles.dictionary_binding(rom, names, self.fixture.codes))


if __name__ == "__main__":
    unittest.main()
