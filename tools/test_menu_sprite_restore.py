import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import restore_menu_sprite_style as restore


class MenuSpriteRestoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).with_name('fixtures') / 'menu_sprite_overrides_6fc6085.json'
        cls.original = json.loads(fixture.read_text())

    def test_fixture_is_the_known_source(self):
        for key, expected in restore.GENERATED_RECORDS.items():
            self.assertEqual(restore.digest(self.original[key]), expected)

    def test_known_generated_records_migrate_without_metadata_changes(self):
        records = copy.deepcopy(self.original)
        records['custom'] = {'indices': [[3]], 'note': 'user drawing'}
        result = restore.migrate_records(records)
        self.assertEqual(result['custom'], records['custom'])
        for key in restore.GENERATED_RECORDS:
            before, after = copy.deepcopy(records[key]), copy.deepcopy(result[key])
            self.assertNotEqual(before.pop('indices'), after.pop('indices'))
            self.assertEqual(before, after)
        self.assertEqual(records, {**self.original, 'custom': records['custom']})
        self.assertEqual(restore.migrate_records(result), result)

    def test_changed_user_pixels_or_metadata_reject_entire_migration(self):
        for mutation in ('pixel', 'metadata'):
            records = copy.deepcopy(self.original)
            key = 'lz77_00C03AF0'
            if mutation == 'pixel':
                records[key]['indices'][0][0] = 13
            else:
                records[key]['note'] = 'user drawing'
            snapshot = copy.deepcopy(records)
            with self.assertRaisesRegex(ValueError, 'User-edited'):
                restore.migrate_records(records)
            self.assertEqual(records, snapshot)

    def test_deleted_overrides_are_not_recreated(self):
        self.assertEqual(restore.migrate_records({}), {})

    def test_menu_render_rejects_a_changed_font(self):
        title = restore.title
        title.verify_menu_font.cache_clear()
        try:
            with patch.object(title, 'MENU_FONT_SHA256', 'incorrect'):
                with self.assertRaisesRegex(ValueError, 'font differs'):
                    title.make_part1_option_block('작전룸', 28)
                with self.assertRaisesRegex(ValueError, 'font differs'):
                    title.make_part1_header_with_footer(0xC18CB4, '작전룸', 20)
        finally:
            title.verify_menu_font.cache_clear()


if __name__ == '__main__':
    unittest.main()
