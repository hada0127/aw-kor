"""Spacing mutations, final owner coverage, and provenance regressions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qa_dialogue_jamming import (check, is_jammed, final_owner_spans,
                                 validate_manifest, verify_provenance, rendered_rows)
from qa_integrity_map import load_syl

ROOT = Path(__file__).resolve().parents[1]


def write(addr, size, text):
    return [addr, size, size, '', None, text, 0, 'script:test']


def fixture():
    rom = bytearray(128)
    rom[4:8] = rom[8:12] = (0x08000040).to_bytes(4, 'little')
    original = bytearray(128)
    original[4:8] = original[8:12] = (0x08000020).to_bytes(4, 'little')
    manifest = [dict(status='relocated', msg='0x000020', new_addr='0x40', old_len=16,
        new_len=16, ptr_off='0x4', ptr_sites=['0x4', '0x8'], lines=1, fixed=['0x000022'],
        line_spans={'0x000022': [2, 8]}, source_spans={'0x000022': 8},
        source_texts={'0x000022': '가 나 다'})]
    return rom, original, manifest


def relocation_writes(manifest):
    return [[int(m['new_addr'], 16), m['new_len'], m['new_len'], '', None, None, None,
             'repoint:' + m['msg'], dict(source=int(m['msg'], 16), old_len=m['old_len'],
                 ptr_sites=[int(s, 16) for s in m['ptr_sites']],
                 source_spans=copy.deepcopy(m['source_spans']))] for m in manifest]


class DialogueJamTests(unittest.TestCase):
    def test_allowlisted_and_unlisted_wide_skips(self):
        from dialogue_repoint import repoint_messages
        original = bytearray(b'\xff' * 0xE10000)
        msg, site, addr = 0xD90000, 0xDA0000, 0xD90002
        original[msg:msg + 8] = b'\x0a\x09\x88\x40\x88\x41\x6b\0'
        original[site:site + 4] = (0x08000000 + msg).to_bytes(4, 'little')
        kwargs = dict(fixable=lambda a: True, fixed_bytes=lambda a: b'\x88\x40' * 30,
            fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
            cell_width=lambda a: 60, slots={}, line_index={addr: (4, '문장')},
            table_offsets=[], extra_messages={msg: [site]},
            free_start=0xA3D000, free_end=0xA40000)
        with self.assertRaisesRegex(AssertionError, 'Unapproved wide'):
            repoint_messages(bytearray(original), original, **kwargs)
        manifest, stats = repoint_messages(bytearray(original), original,
                                           allowed_wide_skips={addr}, **kwargs)
        self.assertEqual(stats['skip_wide_line'], 1)
        self.assertEqual(manifest[0]['lines'], ['0xD90002'])

    def test_partial_loss(self):
        self.assertTrue(is_jammed('가 나 다', '가　나다'))
        self.assertFalse(is_jammed('가 나 다', '가　나　다'))

    def test_approved_country_compounds_do_not_mask_other_loss(self):
        self.assertFalse(is_jammed('그린 어스의 대부대가', '그린어스의　대부대가'))
        self.assertTrue(is_jammed('그린 어스의 대부대가 온다', '그린어스의　대부대가온다'))

    def test_punctuation_normalization(self):
        self.assertTrue(is_jammed('가 나! 다, 라.', '가나！　다、　라。'))
        self.assertFalse(is_jammed('가 나! 다, 라.', '가　나！　다、　라。'))

    def test_wrap_cannot_mask_other_loss(self):
        self.assertTrue(is_jammed('가 나 다', '가나\x72\x0a\x09다'))
        self.assertFalse(is_jammed('가 나 다', '가 나\x72\x0a\x09다'))

    def test_merged_owner_replaces_csv_fragments(self):
        owners, unsupported = final_owner_spans([write(20, 6, '가 나'), write(26, 6, '다 라'),
                                                write(20, 12, '가 나 다 라')], 64)
        self.assertEqual(list(owners), [20])
        self.assertEqual(owners[20][1], 12)
        self.assertEqual(unsupported, [])

    def test_partial_owner_explicitly_unsupported(self):
        _, unsupported = final_owner_spans([write(20, 12, '가 나 다'), write(26, 6, '다 라')], 64)
        self.assertEqual(unsupported, [(20, 'partially superseded owner')])

    def test_level_zero_jam_is_checked(self):
        codes = {value: key for key, value in load_syl().items()}
        rom = bytearray(32)
        rom[8:12] = bytes.fromhex(f'{codes["가"]:04x}{codes["나"]:04x}')
        count, jams, unsupported = check(rom, [], [write(8, 4, '가 나')])
        self.assertEqual((count, len(jams), unsupported), (1, 1, []))

    def test_missing_mapping_and_bounds_fail(self):
        rom, orig, manifest = fixture()
        validate_manifest(rom, manifest, orig)
        for field in ('line_spans', 'source_spans', 'source_texts'):
            bad = copy.deepcopy(manifest)
            bad[0][field] = {}
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_manifest(rom, bad, orig)
        for offset, size in ((-1, 8), (10, 8), (0, 0)):
            bad = copy.deepcopy(manifest)
            bad[0]['line_spans']['0x000022'] = [offset, size]
            with self.assertRaises(ValueError):
                validate_manifest(rom, bad, orig)

    def test_both_pointer_sites_required_and_checked(self):
        rom, orig, manifest = fixture()
        for site in (4, 8):
            bad = bytearray(rom); bad[site] ^= 1
            with self.assertRaises(ValueError):
                validate_manifest(bad, manifest, orig)
        manifest[0]['ptr_sites'] = ['0x4']
        with self.assertRaisesRegex(ValueError, 'incomplete original pointer'):
            validate_manifest(rom, manifest, orig)

    def test_relocated_bytes_are_decoded(self):
        rom, orig, manifest = fixture()
        codes = {value: key for key, value in load_syl().items()}
        rom[66:74] = bytes.fromhex(f'{codes["가"]:04x}8140{codes["나"]:04x}{codes["다"]:04x}')
        rows, _ = rendered_rows(rom, manifest, relocation_writes(manifest), orig)
        self.assertEqual(rows[0]['shipped'], '가　나다')
        self.assertTrue(is_jammed(rows[0]['intended'], rows[0]['shipped']))
        import qa_spacing_from_rom as spacing
        with patch.object(spacing, 'verify_provenance'), patch.object(spacing, 'rendered_rows', return_value=(rows, [])):
            self.assertTrue(spacing._is_jam(rows[0]['intended'], rows[0]['shipped']))

    def test_whole_relocation_record_omission_fails(self):
        rom, orig, manifest = fixture()
        writes = relocation_writes(manifest)
        validate_manifest(rom, manifest, orig, writes)
        with self.assertRaisesRegex(ValueError, 'population mismatch'):
            rendered_rows(rom, [], writes, orig)
        with self.assertRaisesRegex(ValueError, 'population mismatch'):
            rendered_rows(rom, manifest, [], orig)

    def test_consistently_omitted_source_owner_fails(self):
        rom, orig, manifest = fixture()
        writes = relocation_writes(manifest)
        m = manifest[0]
        m.update(lines=0, fixed=[], line_spans={}, source_spans={}, source_texts={})
        with self.assertRaisesRegex(ValueError, 'source owner mismatch'):
            rendered_rows(rom, manifest, writes, orig)

    def test_consistently_changed_destination_fails(self):
        rom, orig, manifest = fixture()
        writes = relocation_writes(manifest)
        manifest[0]['new_addr'] = '0x50'
        rom[4:8] = rom[8:12] = (0x08000050).to_bytes(4, 'little')
        with self.assertRaisesRegex(ValueError, 'destination mismatch'):
            rendered_rows(rom, manifest, writes, orig)

    def test_provenance_rejects_other_rom_map_and_manifest(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            rom, mapping, manifest = [Path(tmp, name) for name in ('test.gba', 'map.json', 'manifest.json')]
            rom.write_bytes(b'ROM'); mapping.write_text('[]'); manifest.write_text('[]')
            sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            receipt = dict(schema=1, rom_sha256=sha(rom), build_metadata={
                'temp/integrity_map.json': sha(mapping), 'temp/repoint_manifest.json': sha(manifest)})
            Path(str(rom) + '.build.json').write_text(json.dumps(receipt))
            verify_provenance(rom, mapping, manifest)
            for path in (rom, mapping, manifest):
                before = path.read_bytes(); path.write_bytes(before + b'x')
                with self.assertRaises(ValueError):
                    verify_provenance(rom, mapping, manifest)
                path.write_bytes(before)

    def test_candidate_d96944_two_sites_and_space_mutation(self):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            self.skipTest('AW_TEST_ROM required')
        rom = bytearray(Path(path).read_bytes())
        manifest = json.loads((ROOT / 'temp/repoint_manifest.json').read_text())
        m = next(m for m in manifest if m['msg'] == '0xD96944' and m['status'] == 'relocated')
        self.assertEqual(set(m['ptr_sites']), {'0xDB2224', '0xDB2314'})
        for site in m['ptr_sites']:
            bad = bytearray(rom); bad[int(site, 16)] ^= 1
            with self.assertRaises(ValueError):
                validate_manifest(bad, manifest)
        off, size = m['line_spans']['0xD969A0']
        pos = int(m['new_addr'], 16) + off
        payload = bytes(rom[pos:pos + size])
        self.assertIn(b'\x81\x40', payload)
        rom[pos:pos + size] = payload.replace(b'\x81\x40', b'', 1) + b'  '
        _, jams, _ = check(rom, manifest, json.loads((ROOT / 'temp/integrity_map.json').read_text()))
        self.assertIn(0xD969A0, [row[0] for row in jams])

class B23RestorationTests(unittest.TestCase):
    def test_candidate_protected_restorations_and_portrait_pages(self):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            self.skipTest('AW_TEST_ROM required')
        from dialogue_repoint import assert_part1_portrait_page_rows
        from repoint_source_rows import row_bytes
        from qa_dialogue_jamming import decode_payload, separator_signature
        rom = Path(path).read_bytes()
        manifest = json.loads((ROOT / 'temp/repoint_manifest.json').read_text())
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())['overrides']
        codes = load_syl()
        for addr, site in ((0xD9EDB6, 0xDC0BF0), (0xDCB1BE, 0xDDE190),
                           (0xDCC63A, 0xDE0410), (0xDCD9DA, 0xDE2814)):
            key = f'0x{addr:06X}'
            m = next(m for m in manifest if m['status'] == 'relocated' and key in m['line_spans'])
            target = int(m['new_addr'], 16)
            self.assertEqual(int.from_bytes(rom[site:site + 4], 'little'), 0x08000000 + target)
            text = decode_payload(row_bytes(rom, m, key), codes)
            self.assertEqual(separator_signature(text), separator_signature(baseline[f'0x{addr:08X}']))
            assert_part1_portrait_page_rows(addr - 2, rom[target:target + m['new_len']])
            if addr in (0xDCC63A, 0xDCD9DA):
                following = f'0x{addr + 0x23:06X}'
                self.assertEqual(decode_payload(row_bytes(rom, m, following), codes), '이야기야。')


if __name__ == '__main__':
    unittest.main()
