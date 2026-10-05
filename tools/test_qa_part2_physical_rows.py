import contextlib
import io
import json
from pathlib import Path
import struct
import unittest
import tempfile
from PIL import Image

import qa_part2_physical_rows as Q


class PhysicalRowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_part2_native_controls import HOOK_FIXTURE
        cls.original = (Q.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(cls.original)
        for start, hexdata in HOOK_FIXTURE.items():
            raw = bytes.fromhex(hexdata)
            rom[start:start+len(raw)] = raw
        cls.profile_rom = bytes(rom)
        cls.options = dict(consumer=Q.NC.CONSUMER, native_profile=Q.NC.NativeProfile(cls.profile_rom))

    def fixture(self):
        original = bytearray(128)
        struct.pack_into('<I', original, 0, Q.GBA+16)
        original[16:20] = bytes.fromhex('88400000')
        return original, bytearray(original)

    def test_receipt_binding_rejects_each_mismatch(self):
        source, rom, manifest, codes = b'original', b'changed!', b'[]', b'{}'
        receipt = {'source_sha256': Q.digest(source), 'rom_sha256': Q.digest(rom),
                   'build_metadata': {Q.MANIFEST_KEY: Q.digest(manifest)},
                   'inputs_before': {'files': {Q.CODE_KEY: Q.digest(codes)}},
                   'inputs_after': {'files': {Q.CODE_KEY: Q.digest(codes)}}}
        Q.bind_artifacts(source, rom, manifest, receipt, codes, Q.digest(source))
        for changed in range(5):
            with self.subTest(changed=changed):
                inputs = [source, rom, manifest, receipt, codes]
                if changed == 3:
                    inputs[3] = {**receipt, 'inputs_after': {'files': {}}}
                else:
                    inputs[changed] += b'x'
                with self.assertRaises(Q.AuditError):
                    Q.bind_artifacts(*inputs, expected_original=Q.digest(source))

    def test_native_boundary_and_early_terminator(self):
        original, rom = self.fixture()
        rom[20:24] = bytes.fromhex('88418842')
        target, payload = Q.bound_message(original, rom, 0, 16, 24, {})
        self.assertEqual(target, 16)
        self.assertEqual(len(payload), 8)
        tokens = Q.tokenize(payload)
        self.assertEqual([t['kind'] for t in tokens], ['text', 'end'])
        broken = bytearray(original); broken[16:24] = b'12345678'
        with self.assertRaises(Q.AuditError):
            Q.source_span(broken, 16, 24)

    def test_relocation_bound_and_rejection(self):
        original, rom = self.fixture()
        struct.pack_into('<I', rom, 0, Q.GBA+64)
        rom[64:70] = bytes.fromhex('884072884100')
        record = {'msg': '0x10', 'status': 'relocated', 'ptr_off': '0x0',
                  'new_addr': '0x40', 'old_len': 8, 'new_len': 6}
        self.assertEqual(Q.bound_message(original, rom, 0, 16, 24, {16: record}),
                         (64, bytes.fromhex('884072884100')))
        for key, value in [('ptr_off', '0x4'), ('new_addr', '0x44'), ('new_len', 1000), ('old_len', 7)]:
            with self.subTest(field=key), self.assertRaises(Q.AuditError):
                Q.bound_message(original, rom, 0, 16, 24, {16: {**record, key: value}})
        with self.assertRaises(Q.AuditError):
            Q.bound_message(original, rom, 0, 16, 24, {})
        with self.assertRaises(Q.AuditError):
            Q.relocation_index([record, record])

    def test_invalid_pointer_and_manifest_cannot_hide_unmoved_pointer(self):
        original, rom = self.fixture()
        for pointer in [-1, 126]:
            with self.subTest(pointer=pointer), self.assertRaises(Q.AuditError):
                Q.bound_message(original, rom, pointer, 16, 24, {})
        with self.assertRaises(Q.AuditError):
            Q.bound_message(original, rom, 0, 16, 24, {16: {'new_len': 8}})
        with self.assertRaises(Q.AuditError):
            Q.bound_message(original, rom, 0, 17, 24, {})

    def test_sjis_trail_control_bytes_are_text(self):
        tokens = Q.tokenize(bytes.fromhex('81778172816b00'))
        self.assertEqual([t['kind'] for t in tokens], ['text', 'text', 'text', 'end'])
        rows, unknown, terminated = Q.assemble_rows(tokens, {}, 'story_layout_unverified')
        self.assertEqual(rows[0]['half_cells'], 6)
        self.assertTrue(terminated)
        self.assertFalse(unknown)

    def test_joins_newlines_pages_and_capacity_evidence(self):
        word = bytes.fromhex('8840')*12
        payload = word+b'\x77'+word+b'\x72'+word+b'\x6b'+word+b'\0'
        tokens = Q.tokenize(payload)
        rows, _, _ = Q.assemble_rows(tokens, {0x8840: '가'}, 'story_layout_unverified')
        self.assertEqual([(r['page'], r['line'], r['half_cells']) for r in rows],
                         [(0, 0, 48), (0, 1, 24), (1, 0, 24)])
        self.assertIsNone(rows[0]['capacity_half_cells'])
        self.assertFalse(rows[0]['confirmed_capacity_exceeded'])
        known, _, _ = Q.assemble_rows(tokens, {}, 'portrait', 44, **self.options)
        self.assertTrue(known[0]['confirmed_capacity_exceeded'])
        for context in ['intro', 'objective', 'prologue', 'story_layout_unverified']:
            with self.subTest(context=context), self.assertRaises(Q.AuditError):
                Q.assemble_rows(tokens, {}, context, 44)

    def test_unknown_commands_and_invalid_pair_never_pass(self):
        for control in [0x57, 0x4B, 0x32, 0x33, 0x69, 0x0A]:
            tokens = Q.tokenize(b'\x88\x40'+bytes([control])+b'\x72'+b'\x88\x40'*23+b'\0')
            rows, unknown, _ = Q.assemble_rows(tokens, {}, 'portrait')
            self.assertEqual(unknown[0]['raw'], f'{control:02x}')
            self.assertTrue(all(not r['controls_understood'] for r in rows))
            self.assertFalse(any(r['confirmed_capacity_exceeded'] for r in rows))
        tokens = Q.tokenize(b'\x88\0')
        self.assertEqual([t['kind'] for t in tokens], ['invalid_pair', 'end'])
        rows, unknown, terminated = Q.assemble_rows(Q.tokenize(b'\x88\x40'), {}, 'portrait')
        self.assertFalse(terminated)
        self.assertFalse(rows[0]['controls_understood'])

    def test_padding_and_visible_fullwidth_space(self):
        payload = bytes.fromhex('884020202081408841202000')
        rows, _, _ = Q.assemble_rows(Q.tokenize(payload), {0x8840:'가', 0x8841:'각'}, 'story_layout_unverified')
        self.assertEqual(rows[0]['half_cells'], 6)
        self.assertEqual(rows[0]['text'], '가\u3000각')
        self.assertEqual(len(rows[0]['unverified_spacing']), 3)
        self.assertFalse(rows[0]['controls_understood'])
        trailing, _, _ = Q.assemble_rows(Q.tokenize(bytes.fromhex('884020207288412000')), {}, 'portrait', 44, **self.options)
        self.assertTrue(all(r['controls_understood'] for r in trailing))
        self.assertTrue(Q.spacing_classification(Q.tokenize(bytes.fromhex('88402077884100'))))
        self.assertFalse(Q.pair_violations(bytes.fromhex('8840814088410000')))
        self.assertEqual(Q.pair_violations(bytes.fromhex('884037884100'))[0]['raw'], '3788')
        self.assertTrue(Q.pair_violations(bytes.fromhex('8840')))

    def test_real_native_title_inventory_and_supported_subset(self):
        original = (Q.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.assertEqual(Q.digest(original), Q.ORIGINAL_SHA)
        titles = Q.active_titles(original, original)
        strict = Q.strict_titles(original, titles)
        self.assertEqual(len(titles), 179)
        self.assertGreater(len(strict), 0)
        self.assertLessEqual(len(strict), len(titles))
        pointers = {r[0] for r in strict}
        entries = Q._read_table(original, Q.TABLE)
        active_source = {s for p, s in entries if p in pointers}
        self.assertIn(0xA2D5C8, active_source)
        self.assertNotIn(0xA2D888, active_source)

    def test_candidate_title_and_descriptor_are_independently_checked(self):
        original = (Q.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        for case in ('long', 'descriptor', 'unknown_pointer'):
            rom = bytearray(original)
            if case == 'long':
                struct.pack_into('<I', rom, 0xA382C0, Q.GBA+0xA3D000)
                rom[0xA3D000:0xA3D019] = b'\x88\x40'*12+b'\0'
            elif case == 'descriptor':
                rom[0x9EFDFC] ^= 1
            else:
                struct.pack_into('<I', rom, 0xA38084, Q.GBA+len(rom))
            with self.subTest(case=case):
                result = Q.audit(original, rom, {}, {})
                self.assertTrue(result['structural_errors'])
                self.assertEqual(Q.failure_status(result['summary']), 1)

    def test_relocation_overlap_and_native_data_are_rejected(self):
        original = bytearray(b'\xff'*0xA40000)
        def row(start, size):
            return {'new_addr': hex(start), 'new_len': size}
        records = {1: row(0xA3D000, 10), 2: row(0xA3D00A, 10)}
        Q.validate_relocation_intervals(original, original, records)
        with self.assertRaisesRegex(Q.AuditError, '중첩'):
            Q.validate_relocation_intervals(original, original, {**records, 2:row(0xA3D009,10)})
        for start, size in ((0xA3CFFF, 10), (0xAFEFFF, 2), (0xA3D000, 0),
                            (0xA3D000, -1), (0xA3D000, 1.5)):
            with self.subTest(start=start, size=size), self.assertRaises(Q.AuditError):
                Q.validate_relocation_intervals(original, original, {1:row(start,size)})
        original[0xA3D000] = 0
        with self.assertRaisesRegex(Q.AuditError, '원본 데이터'):
            Q.validate_relocation_intervals(original, original, records)

    def test_portrait_evidence_binds_revision_payload_and_real_png(self):
        with tempfile.TemporaryDirectory(dir=Q.ROOT/'temp') as directory:
            root = Path(directory);png = root/'screen.png';path = root/'evidence.json'
            Image.new('RGB', (240,160)).save(png)
            payload = b'\x88\x40\0'
            record = dict(source='0x10', renderer='part2_a3_portrait', capacity_half_cells=44,
                          rom_sha256='candidate', payload_sha256=Q.digest(payload),
                          screenshot='screen.png', screenshot_sha256=Q.digest(png.read_bytes()))
            def write(row):
                path.write_text(json.dumps({'schema':1,'records':[row]}))
            write(record)
            self.assertEqual(set(Q.validate_portrait_evidence(path,'candidate',{16:payload})),{16})
            for field, value in [('rom_sha256','old'),('payload_sha256','bad'),
                                 ('screenshot_sha256','bad'),('renderer','unverified'),
                                 ('capacity_half_cells',50),('source','0x20')]:
                write({**record,field:value})
                with self.subTest(field=field), self.assertRaises(Q.AuditError):
                    Q.validate_portrait_evidence(path,'candidate',{16:payload})
            png.write_bytes(b'\x89PNG\r\n\x1a\ninvalid')
            write({**record,'screenshot_sha256':Q.digest(png.read_bytes())})
            with self.assertRaises(Q.AuditError):
                Q.validate_portrait_evidence(path,'candidate',{16:payload})
            Image.new('RGB', (480,320)).save(png)
            write({**record,'screenshot_sha256':Q.digest(png.read_bytes())})
            with self.assertRaisesRegex(Q.AuditError, '240x160'):
                Q.validate_portrait_evidence(path,'candidate',{16:payload})
            # Valid PNG chunks/CRCs, but an invalid compressed IDAT stream.
            import zlib
            def chunk(kind, data):
                return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
            png.write_bytes(b'\x89PNG\r\n\x1a\n'+
                chunk(b'IHDR',struct.pack('>IIBBBBB',240,160,8,2,0,0,0))+
                chunk(b'IDAT',b'not a zlib stream')+chunk(b'IEND',b''))
            with Image.open(png) as image:
                image.verify()  # CRC-only validation really does accept it.
            write({**record,'screenshot_sha256':Q.digest(png.read_bytes())})
            with self.assertRaisesRegex(Q.AuditError, '손상'):
                Q.validate_portrait_evidence(path,'candidate',{16:payload})

    def test_cli_requires_separate_consumer_and_png_evidence(self):
        # Real native pointer inventory and handler bytes, with explicitly
        # synthetic trace/PNG fixtures: this tests binding, not runtime coverage.
        inventory = Q.audit(self.original, self.profile_rom, {}, {})
        message = next(m for m in inventory['messages'] if m['context'] == 'story_layout_unverified')
        with tempfile.TemporaryDirectory(dir=Q.ROOT/'temp') as directory:
            root = Path(directory)
            rom = root/'candidate.gba'; rom.write_bytes(self.profile_rom)
            manifest = root/'manifest.json'; manifest.write_text('[]')
            codes = root/'codes.json'; codes.write_text('{}')
            receipt = root/'receipt.json'
            receipt.write_text(json.dumps({
                'source_sha256': Q.digest(self.original), 'rom_sha256': Q.digest(self.profile_rom),
                'build_metadata': {Q.MANIFEST_KEY: Q.digest(manifest.read_bytes())},
                'inputs_before': {'files': {Q.CODE_KEY: Q.digest(codes.read_bytes())}},
                'inputs_after': {'files': {Q.CODE_KEY: Q.digest(codes.read_bytes())}}}))
            png = root/'screen.png'; Image.new('RGB', (240,160)).save(png)
            layout = root/'layout.json'
            layout.write_text(json.dumps({'schema':1,'records':[dict(
                source=message['source'], renderer='part2_a3_portrait', capacity_half_cells=44,
                rom_sha256=Q.digest(self.profile_rom), payload_sha256=message['payload_sha256'],
                screenshot=png.name, screenshot_sha256=Q.digest(png.read_bytes()))]}))
            trace = root/'trace.log'
            trace.write_text(f"addr={int(message['source'],16)+Q.GBA:08X} pc=0831425A lr=083148F3\n")
            consumer = root/'consumer.json'
            consumer.write_text(json.dumps({'schema':1,'rom_sha256':Q.digest(self.profile_rom),'records':[dict(
                **{k:message[k] for k in ('source','pointer','target','payload_sha256')},
                consumer=Q.NC.CONSUMER, kind='historical-inplace-native-read-v1',
                trace_rom=str(rom), trace_rom_sha256=Q.digest(self.profile_rom),
                trace=str(trace), trace_sha256=Q.digest(trace.read_bytes()))]}))
            args = ['--rom',str(rom),'--original',str(Q.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba'),
                    '--manifest',str(manifest),'--receipt',str(receipt),'--codes',str(codes)]
            for name, extra, verified, capacity in (
                ('png_only',['--layout-evidence',str(layout)],False,None),
                ('consumer_only',['--consumer-evidence',str(consumer)],True,None),
                ('both',['--layout-evidence',str(layout),'--consumer-evidence',str(consumer)],True,44)):
                with self.subTest(case=name), contextlib.redirect_stdout(io.StringIO()):
                    output = root/name
                    status = Q.main(args+extra+['--output',str(output)])
                    self.assertEqual(status,0)  # This selected native fixture fits.
                    report = json.loads((output/'summary.json').read_text())
                    messages = json.loads((output/'messages.json').read_text())
                    current = next(m for m in messages if m['source']==message['source'])
                    self.assertEqual(current['consumer_status'],'native_verified' if verified else 'unverified')
                    self.assertEqual(current['capacity_half_cells'],capacity)
                    self.assertEqual(report['native_consumer_verified_messages'],int(verified))
                    self.assertEqual(report['consumer_unverified_messages'],report['messages']-int(verified))
                    self.assertEqual(report['native_title_unverified_pointers'],58)
                    if verified:
                        self.assertEqual(report['inputs'][str(consumer)],Q.digest(consumer.read_bytes()))
                        self.assertEqual(report['consumer_evidence_inputs'][str(trace)],Q.digest(trace.read_bytes()))
                        self.assertIn('newline',report['native_profile']['regions'])
                    else:
                        self.assertEqual(report['png_only_messages'],1)
                        self.assertEqual(report['confirmed_portrait_width_candidates'],0)
                        self.assertIsNone(report['native_profile'])
                    if '--layout-evidence' in extra:
                        self.assertEqual(report['inputs'][str(layout)],Q.digest(layout.read_bytes()))
            receipt.write_text('[]')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(Q.main(args+['--output',str(root/'bad_receipt')]),2)

    def test_exit_status_distinguishes_confirmed_failures_from_unknowns(self):
        clean = dict(structural_errors=0, active_title_pair_errors=0, invalid_pair_tokens=0,
                     confirmed_portrait_width_candidates=0, unknown_messages=766)
        self.assertEqual(Q.failure_status(clean), 0)
        for key in ('structural_errors', 'active_title_pair_errors', 'invalid_pair_tokens', 'confirmed_portrait_width_candidates'):
            with self.subTest(key=key):
                self.assertEqual(Q.failure_status({**clean, key: 1}), 1)


if __name__ == '__main__':
    unittest.main()
