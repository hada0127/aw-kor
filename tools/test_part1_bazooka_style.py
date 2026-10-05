"""Keep native unit highlights outside independently editable text operands."""
import ast
import collections
import importlib.util
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
import build_korean_full as B
from dialogue_repoint import repoint_messages, text_segment_cells

ROWS = ((0xD91499, 0xD914A3, '바주카병'),
        (0xD914A4, 0xD914C2, ' 무서움을 느껴 봐!'),
        (0xD91895, 0xD9189F, '바주카병'),
        (0xD918A0, 0xD918C2, '이라도 수는 우리가 더 많아!'))

class BazookaStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}

    def encode(self, text, address):
        return B.encode_full_fidelity(text, self.codes, collections.Counter(), address)

    def test_pure_owners_and_current_words_are_preserved(self):
        from qa_text_fit import load_direct_patch_texts
        direct = load_direct_patch_texts()
        slots, members = B.load_direct_script_metadata()
        for a,e,text in ROWS:
            self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[a], e)
            self.assertIn(a, B.PLAYTHROUGH_REPAIR_ROWS)
            self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[a], text)
            self.assertEqual(direct[a], (e,text))
            self.assertEqual(slots[a], e-a)
            self.assertEqual(B.script_row_owner(a), a)
            self.assertIsNone(B.structured_script_owner(a))
            self.assertEqual(B.direct_script_override_text(a,e,members,{}), text)
            self.assertLessEqual(len(self.encode(text,a)), e-a)
        self.assertEqual(ROWS[0][2]+ROWS[1][2], '바주카병 무서움을 느껴 봐!')
        self.assertEqual(ROWS[2][2]+ROWS[3][2], '바주카병이라도 수는 우리가 더 많아!')
        with self.assertRaisesRegex(AssertionError, 'plain script operand boundary exceeded'):
            B.direct_script_override_text(0xD91499,0xD914C2,members,{})

    def test_actual_writer_keeps_external_style_and_lossless_tail(self):
        tree=ast.parse(Path(B.__file__).read_text())
        writer=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='patch_script_row')
        env=dict(vars(B));env.update(orig=self.original,rom=bytearray(self.original),syl_to_code=self.codes,
             unmapped=collections.Counter(),direct_script_members={},_dlg_ov={},required_script_repoints=set(),WRITE_LOG=[])
        exec(compile(ast.Module(body=[writer],type_ignores=[]),'<actual writer>','exec'),env)
        for a,e,text in ROWS:
            env['patch_script_row'](a,e,b'ignored','bazooka regression',source_text=text)
            full=self.encode(text,a)
            self.assertEqual(env['rom'][a:e], full+b' '*(e-a-len(full)))
            self.assertEqual(env['WRITE_LOG'][-1][5],text)
        for a in (0xD91498,0xD914A3,0xD914C2,0xD91894,0xD9189F,0xD918C2,0xD918CD,0xD918D2):
            self.assertEqual(env['rom'][a],self.original[a])
        self.assertTrue(B.verify_repaired_message_controls(self.original,env['rom']))
        for a in (0xD914A3,0xD9189F):
            bad=bytearray(env['rom']);bad[a]=0x20
            with self.assertRaisesRegex(AssertionError,'repaired message control changed'):
                B.verify_repaired_message_controls(self.original,bad)

    def test_real_repointer_preserves_split_operand_style_sequence(self):
        for index in (0,2):
            a,e,word=ROWS[index];tail_a,tail_end,tail=ROWS[index+1]
            # Real original native token sequence, rebased into an isolated
            # message fixture; production repoint_messages is exercised.
            msg,pointer,free=0xD90000,0xDA0000,0xA3D000
            native=self.original[a-1:tail_end+1]+b'\0'
            original=bytearray(b'\xff'*0xE10000)
            original[msg:msg+len(native)]=native
            struct.pack_into('<I',original,pointer,0x08000000+msg)
            first=msg+1;second=msg+tail_a-(a-1)
            payloads={first:self.encode(word,a),second:self.encode(tail,tail_a)}
            rom=bytearray(original)
            manifests,_=repoint_messages(rom,original,fixable=lambda x:x in payloads,
                fixed_bytes=payloads.__getitem__,fit_level_dlg=lambda _:6,decode_text=lambda _: 'text',
                cell_width=lambda x:text_segment_cells(payloads[x]),slots={},
                line_index={first:(e-a,word),second:(tail_end-tail_a,tail)},
                table_offsets=[],extra_messages={msg:[pointer]},free_start=free,free_end=free+4096)
            self.assertEqual(manifests[0]['status'],'relocated')
            target=struct.unpack_from('<I',rom,pointer)[0]-0x08000000
            live=bytes(rom[target:target+manifests[0]['new_len']])
            self.assertEqual(live,b'\x32'+payloads[first]+b'\x30'+payloads[second]+self.original[tail_end:tail_end+1]+b'\0')

    def test_both_editors_keep_two_editable_operands_and_group_members(self):
        def load(name):
            spec=importlib.util.spec_from_file_location('bazooka_'+name,Path(B.BASE)/'tools'/name/'server.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        DE,CE=load('dialogue_editor'),load('scene_editor')
        from build_dialogue_groups import korean_segments
        members=[{'address':f'0x{a:08X}','ko':text,'ja':self.original[a:e].decode('shift_jis'),'slot':e-a,'kind':'script:operand'} for a,e,text in ROWS]
        segments=[{'kind':'frag','address':m['address']} for m in members]
        self.assertEqual(korean_segments(segments,members),segments)
        for m,(a,e,text) in zip(members,ROWS):
            self.assertEqual(DE.current_ko(m['address'],member=m),text)
            self.assertEqual(CE.effective_member_ko(m,{}),text)
            self.assertIsNone(DE.text_edit_readonly_reason(m['address']))
            self.assertEqual(DE.member_slot(m['address']),e-a)
            budget=CE.line_budget(m)
            self.assertTrue(budget['editable']);self.assertEqual(budget['slot'],e-a)

if __name__=='__main__':unittest.main()
