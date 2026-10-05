"""Regressions for bounded tutorial repairs found by native-control review."""
import ast
import collections
import importlib.util
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import build_korean_full as B
from dialogue_repoint import is_sjis_lead, repoint_messages, text_segment_cells, normalize_text_segment

ROWS = ((0xD8FE6C,0xD8FE82,'Ａ 버튼으로 전투 시작해！'),
        (0xD90202,0xD90220,'아직　행동하지 않은 유닛이'),
        (0xD913B4,0xD913D8,'하면 못 쓰러뜨려'),
        (0xD916CD,0xD916D5,'하지만, '),
        (0xD916D6,0xD916E0,'바주카병'),
        (0xD916E1,0xD916F1,'은 1이면 돼.'),
        (0xD98E5C,0xD98E6A,'으로 유인해 '))

STYLE_ROWS = ((0xD8FE41,0xD8FE45,'지금 '),
              (0xD8FE4B,0xD8FE69,'할 상대는 하나뿐'),
              (0xD913DB,0xD913E1,'지금 '),
              (0xD913E7,0xD913F1,'해 줘'),
              (0xD9169E,0xD916B6,'예를 들어, 산에선 '),
              (0xD916BC,0xD916CA,'은 2가 들어'),
              (0xD98E74,0xD98E76,'로 '))
FIXED_WORDS = ((0xD8FE46,0xD8FE4A,'공격'), (0xD913E2,0xD913E6,'공격'),
               (0xD916B7,0xD916BB,'보병'), (0xD98E77,0xD98E7B,'공격'))

def controls(raw):
    result=[];i=0
    while i<len(raw):
        byte=raw[i]
        if is_sjis_lead(byte):i+=2;continue
        if byte!=0x20:result.append(byte)
        i+=1
        if byte==0:break
    return result

class RemainingControlRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=Path(B.P.ROM).read_bytes()
        cls.codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
        cls.tree=ast.parse(Path(B.__file__).read_text())
        cls.writer=next(n for n in ast.walk(cls.tree) if isinstance(n,ast.FunctionDef) and n.name=='patch_script_row')

    def encode(self,text,a):
        return B.encode_full_fidelity(text,self.codes,collections.Counter(),a)

    def writer_env(self):
        _,members=B.load_direct_script_metadata()
        env=dict(vars(B));env.update(orig=self.original,rom=bytearray(self.original),syl_to_code=self.codes,
            unmapped=collections.Counter(),direct_script_members=members,
            _dlg_ov=B.load_dialogue_overrides(str(Path(B.BASE)/'data/dialogue_overrides.json')),
            required_script_repoints=set(),WRITE_LOG=[])
        exec(compile(ast.Module(body=[self.writer],type_ignores=[]),'<actual writer>','exec'),env)
        return env

    def structured_payload(self,env):
        call=next(n for n in ast.walk(self.tree) if isinstance(n,ast.Call)
                  and isinstance(n.func,ast.Name) and n.func.id=='patch_script_row'
                  and isinstance(n.args[0],ast.Constant) and n.args[0].value==0xD8FCE2)
        self.assertEqual(call.args[1].value,0xD8FD08)
        return eval(compile(ast.Expression(call.args[2]),'<actual structured payload>','eval'),env)

    def test_owner_metadata_and_bteam_text_are_preserved(self):
        from qa_text_fit import load_direct_patch_texts
        direct=load_direct_patch_texts();slots,members=B.load_direct_script_metadata()
        for a,e,text in ROWS:
            self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[a],e)
            self.assertIn(a,B.PLAYTHROUGH_REPAIR_ROWS)
            self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[a],text)
            self.assertEqual(direct[a],(e,text));self.assertEqual(slots[a],e-a)
            self.assertEqual(B.direct_script_override_text(a,e,members,{}),text)
        self.assertEqual(B.STRUCTURED_SCRIPT_ROWS[0xD8FCE2],0xD8FD08)
        ov=B.load_dialogue_overrides(str(Path(B.BASE)/'data/dialogue_overrides.json'))
        self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xD90202],ov['0x00D90202'])
        for a,e in [(0xD90202,0xD90222),(0xD916CD,0xD916F1)]:
            with self.assertRaisesRegex(AssertionError,'plain script operand boundary exceeded'):
                B.direct_script_override_text(a,e,members,{})

    def test_actual_writer_preserves_external_controls_and_requires_relocation(self):
        env=self.writer_env()
        for a,e,text in ROWS:
            env['patch_script_row'](a,e,b'ignored','regression',source_text=text)
            full=self.encode(text,a)
            expected=self.original[a:e] if len(full)>e-a else full+b' '*(e-a-len(full))
            self.assertEqual(env['rom'][a:e],expected)
            self.assertEqual(env['WRITE_LOG'][-1][5],text)
        self.assertEqual(env['required_script_repoints'],{0xD8FE6C,0xD916CD})
        env['patch_script_row'](0xD8FCE2,0xD8FD08,self.structured_payload(env),'attack movement row')
        self.assertEqual(controls(env['rom'][0xD8FCE2:0xD8FD08]),[0x32,0x30,0x33,0x30])
        self.assertTrue(B.verify_repaired_message_controls(self.original,env['rom']))
        for a in (0xD8FD08,0xD90220,0xD90221,0xD916D5,0xD916E0):
            bad=bytearray(env['rom']);bad[a]=0x20
            with self.assertRaisesRegex(AssertionError,'repaired message control changed'):
                B.verify_repaired_message_controls(self.original,bad)
        self.assertTrue(self.encode(ROWS[-1][2],ROWS[-1][0]).endswith(b'\x81\x40'))

    def test_real_repointer_keeps_native_control_signature_and_full_words(self):
        env=self.writer_env()
        payloads={a:self.encode(t,a)for a,e,t in ROWS}
        spans={a:e for a,e,t in ROWS}
        payloads[0xD8FCE2]=self.structured_payload(env)
        spans[0xD8FCE2]=0xD8FD08
        groups=((0xD8FCE0,0xD8FD24),(0xD8FE69,0xD8FE86),(0xD90200,0xD90276),
                (0xD913AC,0xD913DA),(0xD916CA,0xD916F4),(0xD98E54,0xD98E82))
        for start,end in groups:
            with self.subTest(source=hex(start)):
                msg,pointer,free=0xD90000,0xDA0000,0xA3D000
                native=self.original[start:end]+b'\0'
                original=bytearray(b'\xff'*0xE10000);original[msg:msg+len(native)]=native
                struct.pack_into('<I',original,pointer,0x08000000+msg)
                selected={msg+a-start:raw for a,raw in payloads.items() if start<=a<end}
                lines={msg+a-start:(spans[a]-a,'reviewed') for a in payloads if start<=a<end}
                rom=bytearray(original)
                manifests,_=repoint_messages(rom,original,fixable=lambda a:a in selected,
                    fixed_bytes=selected.__getitem__,fit_level_dlg=lambda _:6,decode_text=lambda _:'reviewed',
                    cell_width=lambda a:text_segment_cells(selected[a]),slots={},line_index=lines,
                    table_offsets=[],extra_messages={msg:[pointer]},free_start=free,free_end=free+4096)
                self.assertEqual(manifests[0]['status'],'relocated')
                target=struct.unpack_from('<I',rom,pointer)[0]-0x08000000
                live=bytes(rom[target:target+manifests[0]['new_len']])
                self.assertEqual(controls(live),controls(native))
                for raw in selected.values():self.assertIn(normalize_text_segment(raw,True,msg),live)

    def test_remaining_styles_keep_seven_editable_and_four_fixed_owners(self):
        from qa_text_fit import load_direct_patch_texts
        direct=load_direct_patch_texts();slots,members=B.load_direct_script_metadata()
        for a,e,text in STYLE_ROWS:
            self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[a],e)
            self.assertIn(a,B.PLAYTHROUGH_REPAIR_ROWS)
            self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[a],text)
            self.assertEqual(direct[a],(e,text))
            self.assertEqual(B.direct_script_override_text(a,e,members,{}),text)
        for a,e,text in FIXED_WORDS:
            self.assertNotIn(a,direct)
            self.assertNotIn(a,B.SCRIPT_PLAIN_OPERAND_SPANS)
        for a,e in ((0xD913DB,0xD913F1),(0xD9169E,0xD916CA),(0xD98E74,0xD98E7E)):
            with self.assertRaisesRegex(AssertionError,'plain script operand boundary exceeded'):
                B.direct_script_override_text(a,e,members,{})

    def test_fixed_writer_survives_and_full_native_controls_are_preserved(self):
        env=self.writer_env()
        with patch.object(B,'WRITE_LOG',env['WRITE_LOG']):
            for a,e,text in FIXED_WORDS:
                B.write_known_story_fragment(env['rom'],self.original,a,self.encode(text,a),text)
        for a,e,text in STYLE_ROWS:
            env['patch_script_row'](a,e,b'ignored','style repair',source_text=text)
        self.assertEqual(env['required_script_repoints'],{0xD8FE41,0xD98E74})
        self.assertEqual(B.final_fixed_fragment_addresses(env['WRITE_LOG'],env['rom']),
                         frozenset(a for a,e,t in FIXED_WORDS))
        self.assertTrue(B.verify_repaired_message_controls(self.original,env['rom']))
        for a in (0xD8FE40,0xD8FE45,0xD8FE4A,0xD913E1,0xD913E6,0xD916B6,0xD916BB,0xD98E76,0xD98E7B):
            bad=bytearray(env['rom']);bad[a]=0x20
            with self.assertRaisesRegex(AssertionError,'repaired message control changed'):
                B.verify_repaired_message_controls(self.original,bad)

    def test_full_four_messages_repoint_with_original_control_signature(self):
        # Include original untouched leading text spans, as production does;
        # otherwise the real repointer correctly rejects a large header gap.
        for start in (0xD8FE00,0xD913AC,0xD9169C,0xD98DF0):
            with self.subTest(message=hex(start)):
                end=self.original.index(b'\0',start)+1
                native=self.original[start:end]
                msg,pointer,free=0xD90000,0xDA0000,0xA3D000
                original=bytearray(b'\xff'*0xE10000);original[msg:msg+len(native)]=native
                struct.pack_into('<I',original,pointer,0x08000000+msg)
                rom=bytearray(original);selected={};lines={};expected_fixed=[]
                for a,e,text in ROWS+STYLE_ROWS:
                    if start<=a<end:
                        at=msg+a-start;selected[at]=self.encode(text,a);lines[at]=(e-a,text)
                for a,e,text in FIXED_WORDS:
                    if start<=a<end:
                        at=msg+a-start;raw=self.encode(text,a)
                        rom[at:at+len(raw)]=raw;lines[at]=(e-a,text);expected_fixed.append(raw)
                first=start
                while not is_sjis_lead(self.original[first]):first+=1
                stop=first
                while is_sjis_lead(self.original[stop]):stop+=2
                lines.setdefault(msg+first-start,(stop-first,'original first text'))
                manifest,_=repoint_messages(rom,original,fixable=lambda a:a in selected,
                    fixed_bytes=selected.__getitem__,fit_level_dlg=lambda _:6,
                    decode_text=lambda raw:raw.hex(),cell_width=lambda a:text_segment_cells(selected[a]),
                    slots={},line_index=lines,table_offsets=[],extra_messages={msg:[pointer]},
                    free_start=free,free_end=free+4096)
                self.assertEqual(manifest[0]['status'],'relocated')
                target=struct.unpack_from('<I',rom,pointer)[0]-0x08000000
                live=bytes(rom[target:target+manifest[0]['new_len']])
                self.assertEqual(controls(live),controls(native))
                for raw in list(selected.values())+expected_fixed:
                    self.assertIn(normalize_text_segment(raw,True,msg),live)

    def test_known_command_words_remain_readonly_in_editor(self):
        spec=importlib.util.spec_from_file_location('remaining_fixed_editor',Path(B.BASE)/'tools/dialogue_editor/server.py')
        de=importlib.util.module_from_spec(spec);spec.loader.exec_module(de)
        data=json.loads((Path(B.BASE)/'data/dialogue_map.json').read_text())
        current={int(row['address'],16):row for row in data['lines']}
        for a,e,text in FIXED_WORDS:
            self.assertEqual(current[a]['kind'],'known-story-fragment')
            self.assertEqual(current[a]['ko'],text)
            self.assertEqual(de.text_edit_readonly_reason(f'0x{a:08X}'),de.KNOWN_FRAGMENT_READONLY_REASON)

    def test_both_editors_expose_three_bazooka_operands(self):
        def load(name):
            spec=importlib.util.spec_from_file_location('remaining_'+name,Path(B.BASE)/'tools'/name/'server.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        de,ce=load('dialogue_editor'),load('scene_editor')
        from build_dialogue_groups import korean_segments
        members=[dict(address=f'0x{a:08X}',ko=text,ja=self.original[a:e].decode('shift_jis'),slot=e-a,kind='script:operand') for a,e,text in ROWS[3:6]]
        segments=[dict(kind='frag',address=m['address'])for m in members]
        self.assertEqual(korean_segments(segments,members),segments)
        for member,(a,e,text) in zip(members,ROWS[3:6]):
            self.assertEqual(de.current_ko(member['address'],member=member),text)
            self.assertEqual(ce.effective_member_ko(member,{}),text)
            self.assertEqual(de.member_slot(member['address']),e-a)
            self.assertIsNone(de.text_edit_readonly_reason(member['address']))
            self.assertEqual(ce.line_budget(member)['slot'],e-a)

if __name__=='__main__':unittest.main()
