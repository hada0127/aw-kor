"""Narrow DF2804 relocation, source, control and actual-font regressions."""
import ast
import collections
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import build_korean_full as builder
from df2804_contract import MESSAGE, FIRST, COMPANION, TAIL, TEXTS, ROWS, NATIVE, PAYLOAD
from dialogue_repoint import repoint_messages, text_segment_cells
from dialogue_spacing import reviewed_bteam_half_cells, load_ledger


class DF2804Tests(unittest.TestCase):
    def fixture(self, mutation=None):
        original = bytearray(b'\xff' * 0x1000000)
        original[MESSAGE:TAIL+3] = NATIVE
        original[0xDF1DA4:0xDF1DAC] = bytes.fromhex('190000000428df08')
        original[0xA01970] = 0
        original[TAIL+3:TAIL+5] = b'\0\0'
        original[TAIL+5:TAIL+13] = b'\x0a\x09\x82\xa0\x6b\x0a\0\0'
        rom = bytearray(original)
        # The current candidate already has translated companion and neighbor.
        rom[COMPANION:TAIL] = ROWS[COMPANION] + b' ' * 8
        rom[TAIL+7:TAIL+9] = b'\x8d\xef'
        rows, texts = dict(ROWS), dict(TEXTS)
        lines = {FIRST: (40, ''), COMPANION: (34, ''), TAIL: (3, '')}
        if mutation:
            mutation(original, rom, rows, texts, lines)
        before = bytes(rom)
        writes = []
        try:
            manifest, stats = repoint_messages(
                rom, original, fixable=lambda a: True, fixed_bytes=rows.__getitem__,
                fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
                cell_width=lambda a: text_segment_cells(rows[a]), slots={}, line_index=lines,
                table_offsets=[], extra_messages={MESSAGE: [0xDF1DA8]},
                free_start=0xA3D000, free_end=0xA40000,
                max_cells_for_address=lambda a: reviewed_bteam_half_cells(a, rows[a]) if a == FIRST else 44,
                source_text=texts.__getitem__, write_log=writes)
        except AssertionError:
            self.assertEqual(bytes(rom), before)
            self.assertEqual(writes, [])
            raise
        if mutation and stats.get('relocated', 0) != 1:
            raise RuntimeError('Mutation was skipped rather than rejected by the contract')
        self.assertEqual(stats.get('relocated',0), 1)
        self.assertEqual(len(manifest), 1)
        m = manifest[0]
        self.assertEqual(bytes(rom[0xA3D000:0xA3D000+len(PAYLOAD)]), PAYLOAD)
        expected = bytearray(before)
        expected[0xA3D000:0xA3D000+len(PAYLOAD)] = PAYLOAD
        expected[0xDF1DA8:0xDF1DAC] = (0x08A3D000).to_bytes(4, 'little')
        self.assertEqual(rom, expected)  # Includes every unrelated byte and native source.
        return original, rom, m, writes

    def test_exact_bytes_ownership_and_tail(self):
        _, rom, m, writes = self.fixture()
        self.assertEqual(m['source_spans'], {'0xDF2806': 40, '0xDF2831': 34})
        self.assertEqual(m['source_texts'], {f'0x{a:06X}': t for a,t in TEXTS.items()})
        self.assertEqual(m['line_spans'], {'0xDF2806': [2,46], '0xDF2831': [51,26]})
        self.assertEqual(m['new_len'],80)
        self.assertEqual(m['old_len'],82)
        self.assertEqual(len(ROWS[FIRST]),46)
        self.assertEqual(len(ROWS[COMPANION]),26)
        self.assertEqual(m['ptr_sites'],['0xDF1DA8'])
        self.assertEqual(writes[0][8]['source_spans'],m['source_spans'])
        self.assertNotIn('0xDF2853',str(m))
        self.assertEqual(m['fixed'], ['0xDF2806', '0xDF2831'])
        self.assertEqual(m.get('layout_controls', {}), {})
        self.assertNotIn('source_line_fragments', m)
        self.assertNotIn('source_fragment_joiners', m)
        from qa_integrity_map import load_syl
        for a,raw in ROWS.items():
            builder.validate_bteam_payload(raw,load_syl(),a)

    def test_native_pointer_controls_source_companion_tampering(self):
        for address in (*range(MESSAGE,FIRST), *range(0xDF282E,COMPANION), *range(TAIL,TAIL+5), *range(0xDF1DA4,0xDF1DAC)):
            for native in (True, False):
                def mutate(o,r,rows,texts,lines):
                    (o if native else r)[address] ^= 1
                with self.subTest(address=hex(address),native=native), self.assertRaises(AssertionError):
                    self.fixture(mutate)
        for which in ('companion_bytes','companion_text','first_bytes','first_text','source_body','space_loss','first_span','extra_owner','span','tailspan','comma_loss','comma_space','comma_space_bytes','csv_companion','extra_pointer','tail_pointer','mid_pointer','far_start_pointer','far_tail_pointer'):
            def mutate(o,r,rows,texts,lines):
                if which=='companion_bytes':rows[COMPANION] = bytes.fromhex('9369894e8149')
                if which=='companion_text':texts[COMPANION]='힘내!'
                if which=='first_bytes':rows[FIRST]=rows[FIRST][2:]
                if which=='first_text':texts[FIRST]=texts[FIRST].replace('전멸로 ', '전멸로,')
                if which=='source_body':o[FIRST] ^= 1
                if which=='comma_loss':rows[FIRST]=rows[FIRST].replace(b'\x81\x41',b'',1)
                if which=='comma_space':texts[FIRST]=texts[FIRST].replace(',', ', ')
                if which=='comma_space_bytes':rows[FIRST]=rows[FIRST].replace(b'\x81\x41',b'\x81\x41\x81\x40',1)
                if which=='csv_companion':texts[COMPANION]='조금만 더 힘내, 화이팅!'
                if which=='space_loss':rows[FIRST]=rows[FIRST].replace(b'\x81\x40',b'',1)
                if which=='first_span':lines[FIRST]=(38,'')
                if which=='extra_owner':lines[TAIL+1]=(4,'')
                if which=='span':lines[COMPANION]=(38,'')
                if which=='tailspan':lines[TAIL]=(2,'')
                if which in ('extra_pointer','tail_pointer','mid_pointer','far_start_pointer','far_tail_pointer'):
                    target=MESSAGE if which in ('extra_pointer','far_start_pointer') else (FIRST+1 if which=='mid_pointer' else TAIL)
                    site=0x100 if which.startswith('far_') else 0xDF1700
                    o[site:site+4]=(0x08000000+target).to_bytes(4,'little')
            with self.subTest(which=which),self.assertRaises(AssertionError):self.fixture(mutate)

    def test_rejects_live_punctuation_loss_and_virtual_tail_joiner(self):
        from df2804_contract import validate_payload
        live = bytes.fromhex('9369894e8f5a8149')  # Reject DF2078's different companion.
        for raw in (PAYLOAD[:-1] + b'\x81\x40\0',
                    b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + live + b'k\x0a\0',
                    PAYLOAD[:46] + PAYLOAD[48:],  # First-row exclamation loss.
                    PAYLOAD + b'\0\0'):
            with self.assertRaises(AssertionError):
                validate_payload(raw)
        self.fixture(lambda o,r,rows,texts,lines: lines.pop(TAIL))

    def test_end_hash_site_and_source_owner_guards(self):
        from df2804_contract import source_lines
        original, rom, _, _ = self.fixture()
        # Restore the native pointer after fixture relocation for direct guard checks.
        rom[0xDF1DA8:0xDF1DAC] = original[0xDF1DA8:0xDF1DAC]
        args = [original, rom, [(FIRST,40),(COMPANION,34)], TAIL+3, [0xDF1DA8], ROWS.__getitem__, TEXTS.__getitem__]
        for index, value in ((3,TAIL+5), (4,[]), (2,[(FIRST,40),(COMPANION,34),(TAIL,5)])):
            changed = list(args); changed[index] = value
            with self.assertRaises(AssertionError): source_lines(*changed)
        with patch('df2804_contract.NATIVE_SHA256', '0'*64), self.assertRaises(AssertionError):
            source_lines(*args)
        from hashlib import sha256
        self.assertEqual(sha256(PAYLOAD).hexdigest(),'8993f1e798153a956382cf470d1c9af594c6afece7740eac454a0a0be09c3fd2')

    def test_builder_source_precedence_and_real_encoder(self):
        tree=ast.parse(Path(builder.__file__).read_text())
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ('_rp_dlg','_rp_fit_level','_rp_fixable')]
        ns={}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<builder scoped functions>','exec'),ns)
        codes={s:int(c,16) for s,c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for a,t in TEXTS.items():
            self.assertEqual(ns['_rp_dlg'](a),t)
            self.assertEqual(ns['_rp_fit_level'](a),6)
            self.assertTrue(ns['_rp_fixable'](a))
            self.assertEqual(builder.encode_required_full_fidelity(t,codes,collections.Counter(),a),ROWS[a])
        overrides=json.loads((Path(builder.BASE)/'data/dialogue_overrides.json').read_text())
        self.assertEqual(overrides[f'0x{COMPANION:08X}'],TEXTS[COMPANION])
        import csv
        with (Path(builder.BASE)/'data/translation_for_import.csv').open() as stream:
            rows = {int(r['address'],16):r for r in csv.DictReader(stream)}
        self.assertEqual(rows[COMPANION]['korean'],'조금만 더 힘내, 화이팅!')
        self.assertNotEqual(rows[COMPANION]['korean'],TEXTS[COMPANION])
        baseline=json.loads((Path(builder.BASE)/'data/bteam_baseline.json').read_text())
        self.assertEqual(baseline['overrides']['0x00DF2806'],TEXTS[FIRST])
        self.assertNotIn(FIRST,builder.BTEAM_ROUND2_RESIDUALS)
        self.assertNotIn(FIRST,builder.BTEAM_PREVIOUS_KOREAN_TEXT)
        ledger=load_ledger()
        self.assertFalse(any(int(r['source'],16)==MESSAGE for r in ledger['messages']))
        self.assertEqual(reviewed_bteam_half_cells(FIRST,ROWS[FIRST]),46)
        self.assertEqual(reviewed_bteam_half_cells(FIRST,ROWS[FIRST]+b'\x81\x49'),0)

    def test_downstream_spacing_keeps_restoration_and_rejects_old_contract(self):
        from test_dialogue_spacing import SpacingTests, Labels
        from dialogue_spacing import apply_repairs, verify
        original, rom, record, writes = self.fixture()
        small_original, small_rom, others, other_writes, _, neighbor = SpacingTests().fixture()
        original[:1024], rom[:1024] = small_original, small_rom
        writes += other_writes
        manifest = [record] + others
        ledger = dict(messages=neighbor['messages'])
        ledger['messages'][-1]['final_pages'] = [['あ い']]
        def inventory(o, r, records):
            return [dict(source=int(m['msg'],16), target=int(m['new_addr'],16),
                payload=bytes(r[int(m['new_addr'],16):int(m['new_addr'],16)+m['new_len']]),
                relocated=m,game='p1',script=True,profile=('p1_portrait',176,2)) for m in records]
        before = (bytes(rom[0xA3D000:0xA3D000+len(PAYLOAD)]),copy.deepcopy(record))
        with patch('dialogue_spacing.Glyphs',return_value=Labels()), \
             patch('dialogue_spacing.inventory',side_effect=inventory):
            self.assertEqual(len(apply_repairs(rom,original,manifest,writes,ledger)),1)
            self.assertEqual(verify(rom,original,manifest,ledger),1)
            self.assertEqual((bytes(rom[0xA3D000:0xA3D000+len(PAYLOAD)]),record),before)
            stale=dict(messages=[dict(source='00DF2804',profile='p1_portrait',
                before_sha256='3730051121f4653710d464368d21a2fad023d0a1a7732090eb4bd75ee277c5bc')])
            unchanged=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaisesRegex(ValueError,'stale spacing specification 0xdf2804'):
                apply_repairs(rom,original,manifest,writes,stale)
            self.assertEqual((bytes(rom),manifest,writes),unchanged)

    def test_final_pointer_based_qa_detects_later_writer_and_pointer_damage(self):
        from qa_bteam_drift import check_rom
        _, rom, record, writes = self.fixture()
        base = {'overrides': {f'0x{a:08X}': t for a, t in TEXTS.items()}}
        read_bytes, read_text = Path.read_bytes, Path.read_text
        def check(data, mapping):
            # Only virtual fixture paths are intercepted; real tables stay authoritative.
            def text(path, *args, **kwargs):
                if str(path) == 'fixture-writes': return json.dumps(writes)
                if str(path) == 'fixture-manifest': return json.dumps([mapping])
                return read_text(path, *args, **kwargs)
            with patch.object(Path, 'read_bytes', lambda path: bytes(data) if str(path) == 'fixture-rom' else read_bytes(path)), \
                 patch.object(Path, 'read_text', text):
                return check_rom(base, 'fixture-rom', 'fixture-writes', 'fixture-manifest')
        self.assertEqual(check(rom, record), [])
        target = int(record['new_addr'], 16)
        for offset in (6, 46, 75):  # first-row space, first !, companion !
            changed = bytearray(rom)
            changed[target+offset:target+offset+2] = b'\x81\x41'
            self.assertTrue(check(changed, record))
        changed = bytearray(rom)
        changed[0xDF1DA8] ^= 1
        self.assertTrue(all(r['cause'] == 'repoint pointer mismatch' for r in check(changed, record)))
        wrong = copy.deepcopy(record)
        del wrong['line_spans'][f'0x{FIRST:06X}']
        self.assertTrue(check(rom, wrong))

    def test_required_relocation_and_post_writer_exclusion(self):
        tree = ast.parse(Path(builder.__file__).read_text())
        assignments = {n.targets[0].id: n for n in ast.walk(tree)
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id in ('_restored_relocated_residuals', '_allowed_wide_skips')}
        required = ast.literal_eval(assignments['_restored_relocated_residuals'].value)
        self.assertIn(FIRST, required)
        self.assertNotIn(FIRST, ast.literal_eval(assignments['_allowed_wide_skips'].value))
        guard = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
            and ast.unparse(n.test) == 'not _restored_relocated_residuals <= completed_script_repoints')
        ns = {'_restored_relocated_residuals': required, 'completed_script_repoints': required - {FIRST}}
        code = compile(ast.Module(body=[guard], type_ignores=[]), '<required relocation>', 'exec')
        with self.assertRaises(AssertionError):
            exec(code, ns)
        ns['completed_script_repoints'] = required
        exec(code, ns)
        self.assertNotIn(FIRST, builder.BTEAM_ROUND2_RESIDUALS)

    @unittest.skipUnless(os.environ.get('AW_GLYPH_ROM') and os.environ.get('AW_NATIVE_ROM'),
                         'Set AW_GLYPH_ROM and AW_NATIVE_ROM; never builds')
    def test_actual_glyph_audit_and_negative_row_positions(self):
        from dialogue_pixel_layout import audit
        original, _, m, _ = self.fixture()
        native_path=os.environ.get('AW_NATIVE_ROM')
        if native_path:
            native=Path(native_path).read_bytes()
            from hashlib import sha256
            self.assertEqual(sha256(native).hexdigest(), 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
            self.assertEqual(native[MESSAGE:TAIL+3],NATIVE)
            self.assertEqual(native[0xDF1DA4:0xDF1DAC],original[0xDF1DA4:0xDF1DAC])
            from df2804_contract import source_lines
            self.assertEqual(source_lines(native,native,[(FIRST,40),(COMPANION,34)],TAIL+3,
                [0xDF1DA8],ROWS.__getitem__,TEXTS.__getitem__),[(FIRST,40),(COMPANION,34)])
        font_rom=Path(os.environ['AW_GLYPH_ROM']).read_bytes()
        from hashlib import sha256
        self.assertEqual(sha256(font_rom).hexdigest(), 'cc612b3fb5e21aa753349d2cdeed165a640eefaa7dd2abd80e3ab2e3e46a3ecf')
        def check(payload):
            entry=dict(source=MESSAGE,target=0xA3D000,payload=payload,game='p1',script=True,
                       profile=('p1_portrait',176,2),sites=[0xDF1DA8])
            with patch('dialogue_pixel_layout.inventory',return_value=[entry]):
                result=audit(original,font_rom,[m])
            self.assertFalse(result['errors'])
            return result['rows']
        rows=check(PAYLOAD)
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in rows],[(184,184),(104,176)])
        self.assertTrue(all(not r['overflow'] and not r['row_overflow'] and not r['glyph_errors'] and not r['caption_overlap'] for r in rows))
        for payload,index in ((b'\x0a\x09'+ROWS[FIRST]+b'k\x0a\0',0),
            (b'\x0a\x09'+ROWS[COMPANION]+b'\x72\x0a\x09'+ROWS[FIRST]+b'k\x0a\0',1),
            (b'\x0a\x09'+ROWS[FIRST]+b'\x81\x40\x72\x0a\x09'+ROWS[COMPANION]+b'k\x0a\0',0)):
            negative=check(payload)[index]
            self.assertTrue(negative['overflow'])
        self.assertEqual(negative['advance_px'],192)
        self.assertEqual(negative['limit_px'],184)


if __name__=='__main__':unittest.main()
