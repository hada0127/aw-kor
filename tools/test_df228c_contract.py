"""Narrow DF228C relocation, source, control and actual-font regressions."""
import ast
import collections
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import build_korean_full as builder
from df228c_contract import MESSAGE, FIRST, COMPANION, TAIL, TEXTS, ROWS, NATIVE, PAYLOAD
from dialogue_repoint import repoint_messages, text_segment_cells
from dialogue_spacing import reviewed_bteam_half_cells, load_ledger


class DF228CTests(unittest.TestCase):
    def fixture(self, mutation=None):
        original = bytearray(b'\xff' * 0x1000000)
        original[MESSAGE:TAIL+3] = NATIVE
        original[0xDF1744:0xDF174C] = bytes.fromhex('190000008c22df08')
        original[0xA01970] = 0
        rom = bytearray(original)
        rows, texts = dict(ROWS), dict(TEXTS)
        lines = {FIRST: (44, ''), COMPANION: (28, ''), TAIL: (3, '')}
        if mutation:
            mutation(original, rom, rows, texts, lines)
        before = bytes(rom)
        writes = []
        manifest, stats = repoint_messages(
            rom, original, fixable=lambda a: True, fixed_bytes=rows.__getitem__,
            fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
            cell_width=lambda a: text_segment_cells(rows[a]), slots={}, line_index=lines,
            table_offsets=[], extra_messages={MESSAGE: [0xDF1748]},
            free_start=0xA3D000, free_end=0xA40000,
            max_cells_for_address=lambda a: reviewed_bteam_half_cells(a, rows[a]) if a == FIRST else 44,
            source_text=texts.__getitem__, write_log=writes)
        self.assertEqual(stats.get('relocated',0), 1)
        self.assertEqual(len(manifest), 1)
        m = manifest[0]
        self.assertEqual(bytes(rom[0xA3D000:0xA3D000+len(PAYLOAD)]), PAYLOAD)
        expected = bytearray(before)
        expected[0xA3D000:0xA3D000+len(PAYLOAD)] = PAYLOAD
        expected[0xDF1748:0xDF174C] = (0x08A3D000).to_bytes(4, 'little')
        self.assertEqual(rom, expected)  # Includes every unrelated byte and native source.
        return original, rom, m, writes

    def test_exact_bytes_ownership_and_tail(self):
        _, rom, m, writes = self.fixture()
        self.assertEqual(m['source_spans'], {'0xDF228E': 44, '0xDF22BD': 28})
        self.assertEqual(m['source_texts'], {f'0x{a:06X}': t for a,t in TEXTS.items()})
        self.assertEqual(m['line_spans'], {'0xDF228E': [2,46], '0xDF22BD': [51,26]})
        self.assertEqual(m['new_len'],80)
        self.assertEqual(m['old_len'],80)
        self.assertEqual(m['ptr_sites'],['0xDF1748'])
        self.assertEqual(writes[0][8]['source_spans'],m['source_spans'])
        self.assertNotIn('0xDF22D9',str(m))
        from qa_integrity_map import load_syl
        for a,raw in ROWS.items():
            builder.validate_bteam_payload(raw,load_syl(),a)

    def test_native_pointer_controls_source_companion_tampering(self):
        for address in (MESSAGE, 0xDF22BA, TAIL, TAIL+1, TAIL+2, 0xDF1744, 0xDF1748):
            for native in (True, False):
                def mutate(o,r,rows,texts,lines):
                    (o if native else r)[address] ^= 1
                with self.subTest(address=hex(address),native=native), self.assertRaises(AssertionError):
                    self.fixture(mutate)
        for which in ('companion_bytes','companion_text','first_bytes','span','tailspan','extra_pointer','tail_pointer'):
            def mutate(o,r,rows,texts,lines):
                if which=='companion_bytes':rows[COMPANION] += b'\x81\x49'
                if which=='companion_text':texts[COMPANION]='먼저 15거점을 점령하는 거예요!'
                if which=='first_bytes':rows[FIRST]=rows[FIRST][2:]
                if which=='span':lines[COMPANION]=(40,'')
                if which=='tailspan':lines[TAIL]=(2,'')
                if which in ('extra_pointer','tail_pointer'):
                    target=MESSAGE if which=='extra_pointer' else TAIL
                    o[0xDF1700:0xDF1704]=(0x08000000+target).to_bytes(4,'little')
            with self.subTest(which=which),self.assertRaises(AssertionError):self.fixture(mutate)

    def test_builder_source_precedence_and_real_encoder(self):
        tree=ast.parse(Path(builder.__file__).read_text())
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ('_rp_dlg','_rp_fit_level')]
        ns={}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<builder scoped functions>','exec'),ns)
        codes={s:int(c,16) for s,c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for a,t in TEXTS.items():
            self.assertEqual(ns['_rp_dlg'](a),t)
            self.assertEqual(ns['_rp_fit_level'](a),6)
            self.assertEqual(builder.encode_required_full_fidelity(t,codes,collections.Counter(),a),ROWS[a])
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[COMPANION],TEXTS[COMPANION])
        baseline=json.loads((Path(builder.BASE)/'data/bteam_baseline.json').read_text())
        self.assertEqual(baseline['overrides']['0x00DF228E'],TEXTS[FIRST])
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
        before = (bytes(rom[0xA3D000:0xA3D000+80]),copy.deepcopy(record))
        with patch('dialogue_spacing.Glyphs',return_value=Labels()), \
             patch('dialogue_spacing.inventory',side_effect=inventory):
            self.assertEqual(len(apply_repairs(rom,original,manifest,writes,ledger)),1)
            self.assertEqual(verify(rom,original,manifest,ledger),1)
            self.assertEqual((bytes(rom[0xA3D000:0xA3D000+80]),record),before)
            stale=dict(messages=[dict(source='00DF228C',profile='p1_portrait',
                before_sha256='2a5d0df761cde36a39fad3375ec75bc05e3d57431de126c91793ee46446cec42')])
            unchanged=(bytes(rom),copy.deepcopy(manifest),copy.deepcopy(writes))
            with self.assertRaisesRegex(ValueError,'stale spacing specification 0xdf228c'):
                apply_repairs(rom,original,manifest,writes,stale)
            self.assertEqual((bytes(rom),manifest,writes),unchanged)

    @unittest.skipUnless(os.environ.get('AW_GLYPH_ROM'),'Set AW_GLYPH_ROM to an existing candidate; never builds')
    def test_actual_glyph_audit_and_negative_row_positions(self):
        from dialogue_pixel_layout import audit
        original, _, m, _ = self.fixture()
        native_path=os.environ.get('AW_NATIVE_ROM')
        if native_path:
            native=Path(native_path).read_bytes()
            self.assertEqual(native[MESSAGE:TAIL+3],NATIVE)
            self.assertEqual(native[0xDF1744:0xDF174C],original[0xDF1744:0xDF174C])
        font_rom=Path(os.environ['AW_GLYPH_ROM']).read_bytes()
        def check(payload):
            entry=dict(source=MESSAGE,target=0xA3D000,payload=payload,game='p1',script=True,
                       profile=('p1_portrait',176,2),sites=[0xDF1748])
            with patch('dialogue_pixel_layout.inventory',return_value=[entry]):
                result=audit(original,font_rom,[m])
            self.assertFalse(result['errors'])
            return result['rows']
        rows=check(PAYLOAD)
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in rows],[(184,184),(104,176)])
        self.assertTrue(all(not r['overflow'] and not r['row_overflow'] and not r['glyph_errors'] for r in rows))
        for payload,index in ((b'\x0a\x09'+ROWS[FIRST]+b'k\x0a\0',0),
            (b'\x0a\x09'+ROWS[COMPANION]+b'\x72\x0a\x09'+ROWS[FIRST]+b'k\x0a\0',1),
            (b'\x0a\x09'+ROWS[FIRST]+b'\x81\x49\x72\x0a\x09'+ROWS[COMPANION]+b'k\x0a\0',0)):
            self.assertTrue(check(payload)[index]['overflow'])


if __name__=='__main__':unittest.main()
