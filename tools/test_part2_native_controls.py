"""Native P2 command profile: aliases, zero-width padding and bounded proofs."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import part2_native_controls as N
import qa_part2_physical_rows as Q

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'original').is_dir())
# Fixed hook bytes from reviewed round11, not a shipped-ROM path dependency.
HOOK_FIXTURE={10733544: '004a10478102f308', 15925888: '0478417804911d4a3f2932d923020b431b4eb3422dd31b4eb3422ad81a4e1b4fbe4226d232781202707802439a4201d00636f5e7708802041bd5b188144b1840194040014901134a801889180c1c6d01114aad18061c2f1c0fce0fc70fce0fc7261c20352f1c0fce0fc70fce0fc70b4800470498014a3f28094b184760f9520840880000a7e200000000f208a443f208ff7f00000000f00800000006c16100038d60000300000000000000000000000000000000000000000000000000000000'}

class NativePart2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=(ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom=bytearray(cls.original)
        for a,hexdata in HOOK_FIXTURE.items():rom[a:a+len(bytes.fromhex(hexdata))]=bytes.fromhex(hexdata)
        cls.rom=bytes(rom);cls.profile=N.NativeProfile(cls.rom)

    def test_native_wait_alias_page_alias_and_no_advance_spaces(self):
        checks=N.verify_native(self.rom)
        self.assertIn('wait_callback',checks)
        self.assertIn('wait_job_descriptor',checks)
        u32=lambda a:struct.unpack_from('<I',self.rom,a)[0]
        self.assertEqual(u32(0x314348+0x57*4),u32(0x314348+0x77*4))
        self.assertEqual(u32(0x314348+0x4b*4),u32(0x314348+0x6b*4))
        for code in (9,10,32):self.assertEqual(u32(0x314270+(code-9)*4),0x0831431C)

    def test_tampered_table_handler_callback_or_hook_is_rejected(self):
        for a in (0x3142CC,0x314348+0x57*4,0x314656,0x314596,0x804F60,0x314004,0x31568c,0xA3C7E8,0xF30280):
            with self.subTest(address=hex(a)):
                rom=bytearray(self.rom);rom[a]^=1
                with self.assertRaises(N.NativeConsumerError):N.NativeProfile(bytes(rom))

    def test_unknown_scope_does_not_promote_aliases_or_padding(self):
        raw=bytes.fromhex('88402088415788404b00')
        tokens=Q.tokenize(raw)
        self.assertEqual([t['raw'] for t in tokens if t['kind']=='unknown'],['57','4b'])
        self.assertEqual(len(Q.spacing_classification(tokens)),1)
        with self.assertRaises(N.NativeConsumerError):Q.tokenize(raw,consumer=N.CONSUMER)

    def test_verified_stream_preserves_same_row_across_wait_and_format(self):
        raw=bytes.fromhex('88402088415788400a0988414b884000')
        options=dict(consumer=N.CONSUMER,native_profile=self.profile)
        tokens=Q.tokenize(raw,**options)
        rows,unknown,terminated=Q.assemble_rows(tokens,{0x8840:'가',0x8841:'나'},'story_layout_unverified',**options)
        self.assertTrue(terminated);self.assertFalse(unknown)
        self.assertEqual([r['half_cells'] for r in rows],[8,2])
        self.assertEqual([r['page'] for r in rows],[0,1])
        self.assertEqual(rows[0]['same_row_joins'][0]['offset'],5)
        self.assertFalse(Q.spacing_classification(tokens,**options))
        self.assertFalse(rows[0]['confirmed_capacity_exceeded'])

    def test_confirmed_capacity_requires_consumer_and_native_profile(self):
        raw=bytes.fromhex('8840')*23+b'\0'
        with self.assertRaises(Q.AuditError):Q.assemble_rows(Q.tokenize(raw),{0x8840:'가'},'portrait',44)
        options=dict(consumer=N.CONSUMER,native_profile=self.profile)
        rows,_,_=Q.assemble_rows(Q.tokenize(raw,**options),{0x8840:'가'},'portrait',44,**options)
        self.assertTrue(rows[0]['confirmed_capacity_exceeded'])

    def test_malformed_consumer_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as directory:
            path=Path(directory)/'proof.json'
            for document in ([],{}, {'schema':1,'rom_sha256':N.sha(self.rom),'records':{}},
                             {'schema':1,'rom_sha256':N.sha(self.rom),'records':[None]},
                             {'schema':1,'rom_sha256':N.sha(self.rom),'records':[{'source':[]}]}):
                with self.subTest(document=document):
                    path.write_text(json.dumps(document))
                    with self.assertRaises(N.NativeConsumerError):
                        N.load_consumer_bindings(path,self.original,self.rom,[])

    def test_bounded_historical_proof_rejects_glyph_only_and_stale_payload(self):
        a,p=0xA01D24,0xA357F4
        message={'source':f'0x{a:08X}','pointer':f'0x{p:08X}','target':f'0x{a:08X}',
                 'payload_sha256':hashlib.sha256(self.rom[a:a+60]).hexdigest()}
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as temp:
            d=Path(temp);old=d/'old.gba';old.write_bytes(self.rom);trace=d/'read.log';proof=d/'proof.json'
            record={**message,'consumer':N.CONSUMER,'kind':'historical-inplace-native-read-v1',
                    'trace_rom':str(old),'trace_rom_sha256':N.sha(self.rom),'trace':str(trace)}
            def write(line):
                trace.write_text(line);record['trace_sha256']=N.sha(trace.read_bytes())
                proof.write_text(json.dumps({'schema':1,'rom_sha256':N.sha(self.rom),'records':[record]}))
            write('addr=08A01D24 pc=0831425A lr=083148F3\n')
            self.assertEqual(set(N.load_consumer_bindings(proof,self.original,self.rom,[message])),{a})
            write('addr=08A01D24 pc=08F30284 lr=0831BBED\n')
            with self.assertRaises(N.NativeConsumerError):N.load_consumer_bindings(proof,self.original,self.rom,[message])
            write('addr=08A01D24 pc=0831425A lr=083148F3\n')
            stale={**message,'payload_sha256':'0'*64}
            with self.assertRaises(N.NativeConsumerError):N.load_consumer_bindings(proof,self.original,self.rom,[stale])

    def test_exact_current_relocated_proof_accepts_only_bounded_parser_reads(self):
        source,pointer,target=0xA01D24,0xA357F4,0xA3D800
        payload=bytes.fromhex('88407788417288416b00')
        current=bytearray(self.rom)
        struct.pack_into('<I',current,pointer,target+N.GBA)
        current[target:target+len(payload)]=payload
        current=bytes(current)
        message={'source':f'0x{source:08X}','pointer':f'0x{pointer:08X}',
                 'target':f'0x{target:08X}','payload_sha256':N.sha(payload),'bound_bytes':len(payload)}
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as directory:
            root=Path(directory);rom=root/'current.gba';rom.write_bytes(current)
            trace=root/'reads.log';proof=root/'proof.json'
            base={**{k:message[k] for k in ('source','pointer','target','payload_sha256')},
                  'consumer':N.CONSUMER,'kind':'current-relocated-native-read-v1',
                  'trace_rom':str(rom),'trace_rom_sha256':N.sha(current),'trace':str(trace)}
            def write(line,record=None,records=None):
                trace.write_text(line)
                record={**(record or base),'trace_sha256':N.sha(trace.read_bytes())}
                proof.write_text(json.dumps({'schema':1,'rom_sha256':N.sha(current),
                                            'records':records or [record]}))
                return record
            valid=f'addr={target+N.GBA:08X} pc=0831425A lr=083148F3\n'
            for pc in ('0831425A','08314336'):
                write(valid.replace('0831425A',pc))
                result=N.load_consumer_bindings(proof,self.original,current,[message])
                self.assertEqual(result[source]['proof_kind'],'current-relocated-native-read-v1')
            for addr,pc,lr in ((source+N.GBA,0x0831425A,0x083148F3),
                               (target+N.GBA-1,0x0831425A,0x083148F3),
                               (target+N.GBA+len(payload),0x0831425A,0x083148F3),
                               (target+N.GBA,0x08F30284,0x0831BBED),
                               (target+N.GBA,0x0831425A,0x0831BBED)):
                with self.subTest(address=hex(addr),pc=hex(pc)):
                    write(f'addr={addr:08X} pc={pc:08X} lr={lr:08X}\n')
                    with self.assertRaises(N.NativeConsumerError):
                        N.load_consumer_bindings(proof,self.original,current,[message])
            for value in (None,True,0,-1,len(current),len(payload)+1):
                with self.subTest(length=value):
                    write(valid)
                    with self.assertRaises(N.NativeConsumerError):
                        N.load_consumer_bindings(proof,self.original,current,[{**message,'bound_bytes':value}])
            # Match record metadata to the altered audit metadata so each native
            # pointer/payload guard, rather than record inequality, must reject it.
            wrong_target=target+32
            for altered in ({**message,'target':f'0x{wrong_target:08X}',
                             'payload_sha256':N.sha(current[wrong_target:wrong_target+len(payload)])},
                            {**message,'payload_sha256':'0'*64}):
                write(valid,{**base,**{k:altered[k] for k in ('target','payload_sha256')}})
                with self.assertRaises(N.NativeConsumerError):
                    N.load_consumer_bindings(proof,self.original,current,[altered])
            # Only an unrelated byte differs: parser, pointer and payload still
            # agree, but another revision must not borrow this proof kind.
            other=bytearray(current);other[0xF70000]^=1
            other_path=root/'other.gba';other_path.write_bytes(other)
            write(valid,{**base,'trace_rom':str(other_path),'trace_rom_sha256':N.sha(other)})
            with self.assertRaises(N.NativeConsumerError):
                N.load_consumer_bindings(proof,self.original,current,[message])
            # Historical relocated ROMs cannot be silently promoted to this exact-revision proof.
            old=root/'old.gba';old.write_bytes(self.rom)
            write(valid,{**base,'trace_rom':str(old),'trace_rom_sha256':N.sha(self.rom)})
            with self.assertRaises(N.NativeConsumerError):
                N.load_consumer_bindings(proof,self.original,current,[message])
            write(valid,{**base,'kind':'historical-inplace-native-read-v1'})
            with self.assertRaises(N.NativeConsumerError):
                N.load_consumer_bindings(proof,self.original,current,[message])
            record=write(valid)
            write(valid,records=[record,record])
            with self.assertRaises(N.NativeConsumerError):
                N.load_consumer_bindings(proof,self.original,current,[message])

if __name__=='__main__':unittest.main()
