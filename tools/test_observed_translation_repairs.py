"""Source-bound regression tests for individually reviewed campaign repairs."""
from pathlib import Path
import collections
import ast
import csv
import json
import struct
import unittest
from unittest.mock import patch
import build_korean_full as builder
from dialogue_repoint import is_sjis_lead

# Each text was individually checked against its source and adjacent controls.
ROWS = [(0xA21840, 0xA2185A, 'そんなことはありませんぞ、', '그렇지 않습니다,'),
 (0xA2185B, 0xA21861, '先生！', '선생님!'),
 (0xA21990, 0xA219AA, 'そんなことはありませんぞ、', '그렇지 않습니다,'),
 (0xA219AB, 0xA219B1, '先生！', '선생님!'),
 (0xD8FAEE, 0xD8FB12, 'なに？！アララ地方にレッドスター軍が', '뭐라고?! 아라라 지방에 레드스타 군이'),
 (0xA0F27A, 0xA0F286, 'けどよ・・・', '미안해. 하지만・・・'),
 (0xA0F189, 0xA0F1A9, 'おれたちブラックホールのもんだ。', '우리 블랙홀의 것이다.'),
 (0xA0F333, 0xA0F33F, 'なめんじゃ、', '얕보지, '),
 (0xA0F340, 0xA0F348, 'ねぇぞ！', '마!'),
 (0xA0D370, 0xA0D376, 'ええ。', '그래.'),
 (0xA0D9F0, 0xA0D9F6, 'ええ。', '그래.'),
 (0xA0DEF9, 0xA0DEFF, 'おい、', '어이,'),
 (0xA0DF00, 0xA0DF12, '話はまだ途中だぜ！', '얘긴 아직 안 끝났어!'),
 (10503348, 10503358, 'コング様。', '콩 님.\u3000'),
 (10503868, 10503878, 'コング様！', '콩 님!\u3000'),
 (10508940, 10508950, 'コング様、', '콩 님,'),
 (10509194, 10509212, 'おれは、コングだ！', '나는, 콩이다!'),
 (10509216, 10509224, 'コング？', '콩?'),
 (10509263, 10509271, 'コング、', '\u3000콩,'),
 (10514932, 10514956, 'コングとかいったな・・・', '콩이라고 했었지・・・'),
 (10519583, 10519591, 'コング、', '\u3000콩,'),
 (10521510, 10521552, 'そのコングの部隊が待機しているという情報は', '그 콩의 부대가 대기하고 있다는 정보는'),
 (10521607, 10521629, 'あのコングってヤツが、', '\u3000그 콩이라는 녀석이,'),
 (10521717, 10521749, 'コングはそんなまわりくどいコト、', '콩은 그렇게 빙 둘러 가는 일은,'),
 (10525501, 10525535, '７日目にはコングの部隊がやってきて', '7일째엔 콩의 부대가 찾아와서'),
 (10528768, 10528778, 'コングー、', '콩-,'),
 (10528779, 10528799, 'コングコングコングー', '\u3000콩 콩 콩-'),
 (10535808, 10535818, 'コング様！', '콩 님!'),
 (10538384, 10538394, 'コング様！', '콩 님!'),
 (10539839, 10539847, 'コング。', '콩.'),
 (10542228, 10542238, 'コング様。', '콩 님.'),
 (10542544, 10542552, 'コング、', '콩,\u3000'),
 (10547104, 10547114, 'コング様、', '콩 님,'),
 (10547371, 10547387, 'おれはコングだ！', '난 콩이다!'),
 (10547392, 10547400, 'コング？', '콩?'),
 (10548384, 10548408, 'コングとかいったな・・・', '콩이라고 했었지・・・'),
 (10549856, 10549866, 'コングー、', '콩-,'),
 (10559832, 10559842, 'コング様！', '콩 님!'),
 (10561614, 10561622, 'コング。', '콩.'),
 (10563048, 10563066, 'コング、あきらめな', '콩, 포기해'),
 (10600115, 10600137, 'コングの方はどうです？', '콩 쪽은 어때요?'),
 (10605133, 10605151, 'コングが来てるよ。', '\u3000콩이 와 있어.'),
 (10635414, 10635446, 'コングは何をしているんでしょう。', '콩은 뭘 하고 있는 걸까요.'),
 (10538572, 10538586, 'コング様・・・', '콩 님・・・'),
 (10560124, 10560138, 'コング様・・・', '콩 님・・・'),
 (14607710, 14607722, 'できるため、', ' 가능해서,'),
 (14605723, 14605725, 'や', '과 '),
 (14605737, 14605741, '、空', ', 공중'),
 (14606262, 14606280, '空ユニットに強い、', '공중 유닛에 강한,'),
 (14606304, 14606320, '視界が広いことも', '시야가 넓은 점도'),
 (14608584, 14608590, 'を運ぶ', '을'),
 (14608593, 14608609, 'ためのユニット。', '운반하기 위한 유닛.'),
 (14608510, 14608534, '空ユニットなので、地形に', '이동력이 지형에 따라'),
 (14608537, 14608561, 'よる移動力の減少もない。', '줄지 않는 공중 유닛.'),
 (14606686, 14606710, '空ユニット。空ユニットに', '공중 유닛. 공중 유닛에'),
 (14606751, 14606767, '移動力をほこる。', '이동력을 자랑한다.'),
 (10517286, 10517300, 'わかりましたが', '알았습니다만'),
 (0xA01F58, 0xA01F66, '山間の敵研究所', '산속 적 연구소'),
 (0xA0236D, 0xA0237B, 'ドミノを救え！', '도미노를 구해!'),
 (0xA0C15D, 0xA0C177, '　この任務はドミノの・・・', '　이 임무는 도미노의・・・'),
 (0xA0C293, 0xA0C2A1, 'やる気だしな！', '의욕이 넘쳐!'),
 (0xA12145, 0xA12153, 'やる気だしな！', '의욕이 넘쳐!'),
 (0xA0C1DD, 0xA0C1EB, '本当だったら、', '원래라면,'),
 (0xA0C2A4, 0xA0C2AE, 'それじゃ、', '그럼, '),
 (0xA0C4DA, 0xA0C4F4, 'サクテキマップって言うの。', '색적 지도라고 해.'),
 (0xA0C4F5, 0xA0C509, 'ユニットにはそれぞれ', '유닛에는 각각 '),
 (0xA0C50F, 0xA0C517, 'があって', '가 있어서'),
 (0xA0C669, 0xA0C67D, 'そこそこ戦えるから、', '그럭저럭 싸우니, '),
 (0xA0C14E, 0xA0C15C, 'でもいいのか？', '하지만 괜찮아?'),
 (0xA0C750, 0xA0C766, '隣に移動されない限り、', '옆에 오지 않는 한, '),
 (0xA01ED0, 0xA01EEE, '山をこえ、キャットの研究基地を', '산을 넘어, 캣의 연구 기지를'),
 (0xA021A0, 0xA021BA, 'キャットにうばわれた国土を', '캣에게 빼앗긴 국토를'),
 (0xA02450, 0xA0246A, 'ブラックホール軍の本拠地を', '블랙홀 군의 본거지를'),
 (0xA020BF, 0xA020DF, 'ブラックホール軍の本意は・・・？', '블랙홀 군의 진의는...?'),
 (0xA0CBC9, 0xA0CBD9, 'おぼえていくわ。', '익혀 갈 거야.'),
 (0xA0CC58, 0xA0CC60, 'それは、', '그건, '),
 (0xA0CC61, 0xA0CC65, 'この', '이 '),
 (0xA0CC6B, 0xA0CC6F, 'よ。', '야.'),
 (0xA0D1F2, 0xA0D20A, '視界を広げておかないと、', '시야를 넓혀 두지 않으면, '),
 (0xA0D62B, 0xA0D63D, 'さぐりを入れてみて', '조사해 보고'),
 (0xA0DFBC, 0xA0DFCC, 'レッドスター軍も', '레드스타군도'),
 (0xA0E17F, 0xA0E19B, '勝たしてはくれないわね・・・', '이기게 해 주진 않네...'),
 (0xA0D3B4, 0xA0D3C6, 'スネークが侵攻する', '스네이크가 침공하는'),
 (0xA0DAB8, 0xA0DAD0, 'つなげているみたいなの。', '연결한 것 같아.'),
 (0xA0E299, 0xA0E2AD, '回復能力を持っている', '회복 능력을 가진'),
 (0xA0D013, 0xA0D023, 'ドミノの情報にも', '도미노의 정보에도'),
 (0xA0DC64, 0xA0DC74, 'そうと分かれば、', '그렇다면, '),
 (0xA0DA9F, 0xA0DAB7, 'パイプをボルトかなにかで', ' 파이프를 볼트 같은 걸로'),
 (0xA0E28A, 0xA0E298, '弱点がなくて、', '약점이 없고, '),
 (0xA104E0, 0xA104E4, 'は、', '하,'),
 (0xA104E5, 0xA104EF, 'はあ・・・', ' 하아・・・'),
 (0xA104F1, 0xA104F9, 'しかし、', ' 하지만,'),
 (0xA104FB, 0xA10521, 'われわれでは相手にならないのでは・・・', '저희로는 상대가 안 될 텐데요・・・'),
 (0xA27ADC, 0xA27AE0, '今、', '지금,'),
 (0xA27AE1, 0xA27AF1, 'この時をもって、', ' 이 시각을 기해,'),
 (0xA27AF3, 0xA27B15, '私がブラックホール軍のそうすいだ。', '내가 블랙홀군의 총수다.'),
 (0xA227B4, 0xA227D6, 'そう言ったのはお父さんじゃないの。', '그렇게 말씀하신 건 아버지잖아요.'),
 (0xA24518, 0xA24534, '明日の攻撃で何とかしないと、', '내일 공격으로 어떻게든 하지 않으면,'),
 (0xA24536, 0xA24558, '図面のデータを消されてしまう・・・', '도면 데이터가 지워져・・・ '),
 (0xA24559, 0xA24565, '急がなきゃ！', '서둘러야 해!'),
 (0xA12FD4, 0xA12FE4, 'レッドスター軍も', '레드스타군도'),
 (0xA08A15, 0xA08A3B, '対空戦車や対空ミサイルが爆撃機にやられ', '대공전차나 대공미사일이 폭격기에 당하지'),
 (0xA08A3C, 0xA08A46, 'ないよう、', '않도록, '),
 (0xA0FDD3, 0xA0FDF5, 'こっちの作戦を成功させておかないと', '우리 작전을 성공시켜 두지 않으면'),
 (0xA12664, 0xA1267C, '歩兵系を山にのぼらせたり', ' 보병계를 산에 올리거나'),
 (0xA15C3B, 0xA15C59, 'ぼくを信じてまかせてくださった', '나를 믿고 맡겨 주신'),
 (0xA1C252, 0xA1C260, 'あまりキレイな', '별로 고운'),
 (0xA1E3A0, 0xA1E3C6, '増えただけって事にならなきゃいいけど。', '늘어나기만 한 게 아니면 좋겠는데.'),
 (0xA1EAF7, 0xA1EB03, 'これが最後に', '이게 마지막이'),
 (0xA1EB04, 0xA1EB1A, 'なればいいのだけれど。', '되면 좋겠는데.'),
 (0xA264B3, 0xA264CD, 'このまま、なにもしないって', '이대로 아무것도 안 하고 있을'),
 (0xA264CE, 0xA264E2, 'わけにもいかないよ。', '수도 없잖아.'),
 (0xA26C94, 0xA26C9C, '全滅して', '전멸해'),
 (0xA26C9D, 0xA26CAD, 'しまわないよう、', '버리지 않도록, '),
 (0xA02B1F, 0xA02B35, 'もうやることはないと、', ' 더 할 일이 없다고, '),
 (0xA06224, 0xA06232, '攻撃できない、', '공격할 수 없다는 '),
 (0xA06233, 0xA06245, 'というのも同じね。', '점도 같네.'),
 (0xA0F288, 0xA0F2A6, '自分の国をメチャクチャにされて', '자기 나라가 엉망이 돼서'),
 (0xA1CFC8, 0xA1CFEC, '歩兵を乗せた輸送車も搭載できることを', '보병을 태운 수송차도 실을 수 있단 걸'),
 (0xA265BF, 0xA265C5, 'それで', '그걸로'),
 (0xA265A1, 0xA265B5, 'なにも考えずに・・・', '아무 생각도 없이・・・')]


class ObservedTranslationRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder_tree = ast.parse(Path(builder.__file__).read_text())
        cls.dialogue = builder.load_dialogue_overrides(Path(builder.BASE) / 'data/dialogue_overrides.json')
        cls.intents = builder.load_editor_override_intents(Path(builder.BASE) / 'data/editor_override_intents.json')
        cls.import_rows = {}
        cls.comprehensive_rows = {}
        for path, destination in [(builder.TRANS, cls.import_rows),
                                  (builder.COMPREHENSIVE_TRANS, cls.comprehensive_rows)]:
            with open(path, newline='') as stream:
                for row in csv.DictReader(stream):
                    destination[int(row['address'], 16)] = row

    def imported_text(self, address):
        """Read the actual curated row or the builder's Translated-only supplement."""
        if address in self.import_rows:
            row = self.import_rows[address]
        else:
            row = self.comprehensive_rows[address]
            self.assertEqual(row['status'], 'Translated')
            self.assertTrue(0xA00000 <= address < 0xA40000)
        text = row['korean'].strip()
        self.assertTrue(text)
        self.assertNotIn(text, builder.PLACEHOLDER_KO)
        return builder.TEXT_OVERRIDES.get(text, text)

    def repoint_selector(self, addresses):
        """Execute production selection, including protected owners and editor receipts."""
        _, members = builder.load_direct_script_metadata()
        literal_rows = {}
        for node in sorted((n for n in ast.walk(self.builder_tree) if isinstance(n, ast.Tuple)),
                           key=lambda n: n.lineno):
            if len(node.elts) != 4 or not all(isinstance(n, ast.Constant) for n in node.elts):
                continue
            start, end, text, label = (n.value for n in node.elts)
            if type(start) is int and type(end) is int and end > start and isinstance(text, str) and isinstance(label, str):
                literal_rows[start] = (end, text)
        owners = {}
        for address in addresses:
            literal = literal_rows.get(address)
            end = builder.SCRIPT_PLAIN_OPERAND_SPANS.get(address, literal[0] if literal else None)
            if end is not None:
                text = builder.direct_script_override_text(address, end, members, self.dialogue)
                if text is None and literal:
                    text = literal[1]
                if text is not None:
                    owners[address] = (end - address, text)
        bteam = json.loads((Path(builder.BASE) / 'data/bteam_addresses.json').read_text())
        namespace = {**vars(builder), '_dlg_ov': dict(self.dialogue),
                     '_editor_intents': dict(self.intents), '_rp_script_owners': owners,
                     '_display_ov': builder.load_display_overrides(),
                     '_rp_bteam': {int(a, 16) for a in bteam['addresses']},
                     '_rp_intended': {a: owners[a][1] if a in owners else self.imported_text(a) for a in addresses}}
        names = ('_rp_strip_sp', '_rp_ov', '_rp_dlg')
        nodes = [next(n for n in ast.walk(self.builder_tree)
                      if isinstance(n, ast.FunctionDef) and n.name == name) for name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual repoint selector>', 'exec'), namespace)
        return namespace

    def test_individual_rows_preserve_source_boundaries_and_exact_authority(self):
        original = Path(builder.P.ROM).read_bytes()
        dialogue = json.loads((Path(builder.BASE) / 'data/dialogue_overrides.json').read_text())
        intents = builder.load_editor_override_intents(Path(builder.BASE) / 'data/editor_override_intents.json')
        _, members = builder.load_direct_script_metadata()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for address, end, japanese, korean in ROWS:
            with self.subTest(address=hex(address)):
                key = f'0x{address:08X}'
                edited = dialogue.get(key)
                if (edited is not None and builder.ADDRESS_TEXT_OVERRIDES.get(address) == edited
                        and intents.get(key) == builder.editor_text_digest(edited)):
                    korean = edited  # Explicit editor action has its own source-authority receipt.
                self.assertEqual(original[address:end].decode('shift_jis'), japanese)
                self.assertFalse(is_sjis_lead(original[end]))
                self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
                self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
                self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], korean)
                self.assertEqual(builder.direct_script_override_text(address, end, members, dialogue), korean)
                missing = collections.Counter()
                full = builder.encode_full_fidelity(korean, codes, missing, address)
                self.assertFalse(missing)
                self.assertTrue(full)

    def test_reviewed_inline_defaults_match_the_authoritative_rows(self):
        node = next(n for n in self.builder_tree.body if isinstance(n, ast.Assign)
                    and isinstance(n.value, ast.Dict)
                    and any(isinstance(t, ast.Name) and t.id == 'ADDRESS_TEXT_OVERRIDES'
                            for t in n.targets))
        defaults = ast.literal_eval(node.value)
        for address, _, _, text in ROWS:
            # A pre-existing TSV-only repair has no fallback entry. Compare
            # every actual inline default against the individually reviewed text.
            if address in defaults:
                self.assertEqual(defaults[address], text, hex(address))

    def test_m8_repairs_preserve_controls_and_require_repoint_for_full_long_row(self):
        original = Path(builder.P.ROM).read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        writer = next(n for n in ast.walk(self.builder_tree)
                      if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        self.assertEqual(builder.SOURCE_TEXT_OVERRIDES['ええ。'], '그래')
        self.assertEqual(builder.SOURCE_TEXT_OVERRIDES['おい、'], '어이')
        selector = self.repoint_selector((0xA0D370, 0xA0D9F0, 0xA0DEF9, 0xA0DF00))
        for address, end, text, delimiter, following in (
                (0xA0D370, 0xA0D376, '그래.', b'\x81\x42', b'\x77\x77'),
                (0xA0D9F0, 0xA0D9F6, '그래.', b'\x81\x42', b'\x77'),
                (0xA0DEF9, 0xA0DEFF, '어이,', b'\x81\x41', b'\x77'),
                (0xA0DF00, 0xA0DF12, '얘긴 아직 안 끝났어!', b'\x81\x49', b'\x77\x72')):
            with self.subTest(address=hex(address)):
                self.assertEqual(selector['_rp_dlg'](address), text)
                env = dict(vars(builder))
                env.update(orig=original, rom=bytearray(original), syl_to_code=codes,
                           unmapped=collections.Counter(), direct_script_members={},
                           _dlg_ov={}, required_script_repoints=set(), WRITE_LOG=[])
                exec(compile(ast.Module(body=[writer], type_ignores=[]), '<actual writer>', 'exec'), env)
                env['patch_script_row'](address, end, b'ignored', 'M8 delimiter', source_text=text)
                payload = env['rom'][address:end]
                full = builder.encode_full_fidelity(selector['_rp_dlg'](address), codes,
                                                    collections.Counter(), address)
                self.assertEqual(full[-2:], delimiter)
                if address == 0xA0DF00:
                    self.assertEqual(end-address, 18)
                    self.assertEqual(len(full), 24)
                    self.assertEqual(payload, original[address:end])
                    self.assertEqual(env['required_script_repoints'], {address})
                    with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
                        builder.verify_required_script_repoints({address}, set())
                    builder.verify_required_script_repoints({address}, {address})
                else:
                    self.assertEqual(len(payload), 6)
                    self.assertEqual(payload, full)
                    self.assertFalse(env['required_script_repoints'])
                self.assertEqual(env['rom'][end:end+len(following)], following)
                self.assertEqual(env['rom'][:address], original[:address])
                self.assertEqual(env['rom'][end:], original[end:])
                self.assertEqual(env['WRITE_LOG'][-1][5], text)

    def test_possession_prohibition_and_apology_keep_whole_messages_and_owners(self):
        import qa_part2_physical_rows as physical
        import qa_text_fit
        original = Path(builder.P.ROM).read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        reverse = {code: syllable for syllable, code in codes.items()}
        direct = qa_text_fit.load_direct_patch_texts(include_writer=True)
        patched = {0xA0F189: (0xA0F1A9, '우리 블랙홀의 것이다.'),
                   0xA0F333: (0xA0F33F, '얕보지, '), 0xA0F340: (0xA0F348, '마!'),
                   0xA0F27A: (0xA0F286, '미안해. 하지만・・・')}
        addresses = (0xA0F164, 0xA0F175, 0xA0F189, 0xA0F1AA,
                     0xA0F328, 0xA0F333, 0xA0F340, 0xA0F26D, 0xA0F27A)
        selector = self.repoint_selector(addresses)
        # The applied B-team baseline, not the earlier imported CSV, is authority.
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())['overrides']
        self.assertEqual(baseline['0x00A0F26D'], '미,')
        self.assertEqual(self.dialogue['0x00A0F26D'], baseline['0x00A0F26D'])
        self.assertEqual(self.dialogue['0x00A0F27A'], '미안해. 하지만・・・')
        self.assertIn(0xA0F26D, selector['_rp_bteam'])
        for address in (*patched, 0xA0F268, 0xA0F26D, 0xA0F27A):
            self.assertNotIn(f'0x{address:08X}', self.intents)
        self.assertEqual(selector['_rp_dlg'](0xA0F26D), '미,')
        self.assertEqual(selector['_rp_dlg'](0xA0F27A), '미안해. 하지만・・・')
        rom = bytearray(original)
        writer = next(n for n in ast.walk(self.builder_tree)
                      if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        env = {**vars(builder), 'orig': original, 'rom': rom, 'syl_to_code': codes,
               'unmapped': collections.Counter(), 'direct_script_members': {},
               '_dlg_ov': {f'0x{a:08X}': '잘못된 이전 문구' for a in patched},
               'required_script_repoints': set(), 'WRITE_LOG': []}
        exec(compile(ast.Module(body=[writer], type_ignores=[]), '<actual writer>', 'exec'), env)
        changed_spans = []
        for address in addresses:
            if address in patched:
                end, text = patched[address]
                self.assertEqual(direct[address], (end, text, 'patch_script_row'))
                self.assertEqual(selector['_rp_dlg'](address), text)
                env['patch_script_row'](address, end, b'ignored', 'context repair', source_text=text)
                expected = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
                if address == 0xA0F27A:
                    self.assertEqual(len(expected), 22)
                    self.assertEqual(end-address, 12)
                    self.assertEqual(rom[address:end], original[address:end])
                    with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
                        builder.verify_required_script_repoints({address}, set())
                    builder.verify_required_script_repoints({address}, {address})
                else:
                    self.assertEqual(rom[address:address+len(expected)], expected)
            else:
                row = self.import_rows.get(address) or self.comprehensive_rows[address]
                end = address + len(row['japanese'].encode('shift_jis'))
                text = selector['_rp_dlg'](address)
                encoded, _ = builder.encode_fit(text, end-address, codes, env['unmapped'], address)
                self.assertIsNotNone(encoded)
                rom[address:end] = encoded + bytes([builder.FILL_BYTE]) * (end-address-len(encoded))
            changed_spans.append((address, end))
        # Execute the actual fixed dictionary loop body on just this source slot.
        fixed_loop = next(n for n in ast.walk(self.builder_tree)
                          if isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
                          and isinstance(n.iter.func, ast.Attribute)
                          and isinstance(n.iter.func.value, ast.Dict)
                          and any(isinstance(k, ast.Constant) and k.value == 0xA0F268
                                  for k in n.iter.func.value.keys))
        fixed_dict = ast.literal_eval(fixed_loop.iter.func.value)
        self.assertEqual(fixed_dict[0xA0F268], '미, ')
        self.assertEqual(original[0xA0F268:0xA0F26C].decode('shift_jis'), 'す、')
        self.assertNotIn(0xA0F268, builder.SCRIPT_PLAIN_OPERAND_SPANS)
        self.assertNotIn(0xA0F268, builder.ADDRESS_TEXT_OVERRIDES)
        env.update(faddr=0xA0F268, text=fixed_dict[0xA0F268])
        with patch.object(builder, 'WRITE_LOG', env['WRITE_LOG']):
            exec(compile(ast.Module(body=fixed_loop.body, type_ignores=[]), '<fixed fragment body>', 'exec'), env)
        self.assertEqual(rom[0xA0F268:0xA0F26C], bytes.fromhex('8c7a8141'))
        self.assertIn(0xA0F268, builder.final_fixed_fragment_addresses(env['WRITE_LOG'], rom))
        changed_spans.append((0xA0F268, 0xA0F26C))
        self.assertFalse(env['unmapped'])
        self.assertEqual(env['required_script_repoints'], {0xA0F27A})
        self.assertEqual(rom[0xA0F26D:0xA0F277], bytes.fromhex('8c7a8141')+b' '*6)
        cursor = 0
        for start, end in sorted(changed_spans):
            self.assertEqual(rom[cursor:start], original[cursor:start])
            cursor = end
        self.assertEqual(rom[cursor:], original[cursor:])
        cases = (
            (0xA36170, 0xA0F164, 0xA0F1CC,
             '너희　나라라고？[6b]레드스타는　이미[57][72]우리　블랙홀의　것이다。[6b]시끄럽게　구는　놈은　부순다[6b][00]'),
            (0xA36190, 0xA0F328, 0xA0F34C,
             '봤냐！[57][57][72]얕보지、　[57]마！[6b][00]'),
            (0xA36184, 0xA0F268, 0xA0F288,
             '미、[57]미、[57][57][72]미안해。　하지만・・・[6b][00]'))
        for pointer, start, end, expected in cases:
            with self.subTest(message=hex(start)):
                self.assertEqual(struct.unpack_from('<I', original, pointer)[0], 0x08000000+start)
                before = physical.tokenize(original[start:end])
                payload = bytes(rom[start:end])
                if start == 0xA0F268:
                    # Unit-test the relocation payload separately from preserved source slots.
                    # The post-build checker must still verify the actual redirected native pointer.
                    full = builder.encode_full_fidelity(selector['_rp_dlg'](0xA0F27A), codes,
                                                        collections.Counter(), 0xA0F27A)
                    payload = payload[:0x12] + full + payload[0x1E:]
                    self.assertEqual(len(payload), 42)
                after = physical.tokenize(payload)
                controls = lambda tokens: [t['raw'] for t in tokens
                                           if t['kind'] not in ('text', 'padding')]
                self.assertEqual(controls(after), controls(before))
                actual = ''.join(physical.decode_pairs(bytes.fromhex(t['raw']), reverse)
                                 if t['kind'] == 'text' else '['+t['raw']+']'
                                 for t in after if t['kind'] != 'padding')
                self.assertEqual(actual, expected)

    def test_arara_baseline_uses_native_pointer_and_required_lossless_repoint(self):
        from dialogue_repoint import repoint_messages, scan_command_messages, text_segment_cells
        import qa_part2_physical_rows as physical
        original = Path(builder.P.ROM).read_bytes()
        address, end, message, message_end, pointer = 0xD8FAEE, 0xD8FB12, 0xD8FAEC, 0xD8FB6C, 0xDA554C
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())['overrides']
        text = baseline['0x00D8FAEE']
        self.assertEqual(text, '뭐라고?! 아라라 지방에 레드스타 군이')
        self.assertEqual(self.dialogue['0x00D8FAEE'], text)
        self.assertNotIn('0x00D8FAEE', self.intents)
        self.assertEqual(scan_command_messages(original)[message], [pointer])
        self.assertEqual(original[pointer-4:pointer], b'\x19\0\0\0')
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(full), 42)
        self.assertEqual(text_segment_cells(full), 42)
        self.assertEqual(original[end:end+3], b'\x72\x0a\x09')
        selector = self.repoint_selector((address,))
        self.assertEqual(selector['_rp_dlg'](address), text)
        writer = next(n for n in ast.walk(self.builder_tree)
                      if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        env = {**vars(builder), 'orig': original, 'rom': bytearray(original), 'syl_to_code': codes,
               'unmapped': collections.Counter(), 'direct_script_members': {}, '_dlg_ov': self.dialogue,
               'required_script_repoints': set(), 'WRITE_LOG': []}
        exec(compile(ast.Module(body=[writer], type_ignores=[]), '<actual writer>', 'exec'), env)
        env['patch_script_row'](address, end, b'ignored', 'arara restoration', source_text=text)
        self.assertEqual(env['rom'], original)  # Overflow staging preserves source and all neighbors.
        self.assertEqual(env['required_script_repoints'], {address})
        with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
            builder.verify_required_script_repoints({address}, set())
        lines = {0xD8FAEE: (36, ''), 0xD8FB15: (16, ''),
                 0xD8FB2A: (20, ''), 0xD8FB41: (38, '')}
        # Run the existing guarded repointer on this single native message in memory.
        manifest, stats = repoint_messages(
            env['rom'], original, fixable=lambda a: a == address,
            fixed_bytes=lambda a: full, fit_level_dlg=lambda a: 6,
            decode_text=lambda raw: physical.decode_pairs(raw, {v:k for k,v in codes.items()}),
            cell_width=lambda a: text_segment_cells(full), slots={}, line_index=lines,
            table_offsets=[], extra_messages={message:[pointer]},
            free_start=0xA3D000, free_end=0xA3D200)
        self.assertEqual(stats['relocated'], 1)
        entry = next(e for e in manifest if e['status'] == 'relocated')
        self.assertEqual(entry['fixed'], ['0xD8FAEE'])
        builder.verify_required_script_repoints({address}, {int(a,16) for a in entry['fixed']})
        target = struct.unpack_from('<I', env['rom'], pointer)[0]-0x08000000
        expected = original[message:address]+full+original[end:message_end]
        self.assertEqual(entry['new_len'], len(expected))
        self.assertEqual(env['rom'][target:target+len(expected)], expected)
        self.assertEqual(env['rom'][address:end], original[address:end])
        self.assertEqual(env['rom'][message:message_end], original[message:message_end])
        for a,b in ((0,target),(target+len(expected),pointer),(pointer+4,len(original))):
            self.assertEqual(env['rom'][a:b], original[a:b])

    def test_pawn_stammer_retains_fixed_writer_and_native_control_boundary(self):
        address, end = 0xA22FFC, 0xA23000
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), 'コ、')
        literals = [value.value for node in ast.walk(self.builder_tree)
                    if isinstance(node, ast.Dict)
                    for key, value in zip(node.keys, node.values)
                    if isinstance(key, ast.Constant) and key.value == address
                    and isinstance(value, ast.Constant)]
        self.assertEqual(literals, ['조, '])
        # This fixed fragment is not a newly editable direct-script operand.
        self.assertNotIn(address, builder.SCRIPT_PLAIN_OPERAND_SPANS)
        self.assertNotIn(address, builder.ADDRESS_TEXT_OVERRIDES)
        self.assertNotIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        missing = collections.Counter()
        encoded = builder.encode_text(literals[0], codes, missing)
        self.assertEqual(len(encoded), end-address)
        self.assertFalse(missing)
        rom = bytearray(original)
        writes = []
        with patch.object(builder, 'WRITE_LOG', writes):
            builder.write_known_story_fragment(rom, original, address, encoded, literals[0])
        self.assertEqual(rom[address:end],
                         builder.encode_full_fidelity('조,', codes, collections.Counter(), address))
        self.assertEqual(rom[:address], original[:address])
        self.assertEqual(rom[end:], original[end:])
        self.assertEqual(writes[-1][7], 'known-story-fragment')
        self.assertEqual(builder.final_fixed_fragment_addresses(writes, rom), frozenset({address}))

    def test_expanded_anti_air_phrase_has_no_legacy_two_byte_writer(self):
        main = next(n for n in ast.walk(ast.parse(Path(builder.__file__).read_text()))
                    if isinstance(n, ast.FunctionDef) and n.name == 'main')
        legacy_dictionary_addresses = {k.value for node in ast.walk(main) if isinstance(node, ast.Dict)
                                       for k in node.keys if isinstance(k, ast.Constant)}
        for address, end, _, _ in ROWS:
            if 0xDEDD00 <= address < 0xDEF000:
                for interior in range(address, end):
                    self.assertNotIn(interior, legacy_dictionary_addresses)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[0xDEDD9B], 0xDEDD9D)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[0xDEDDA9], 0xDEDDAD)

    def test_lab_joined_dialogue_rows_fit_the_portrait_box(self):
        from dialogue_repoint import text_segment_cells
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for addresses in [(0xA0C14E, 0xA0C15D), (0xA0C669, 0xA0C67E), (0xA0C750, 0xA0C767)]:
            select = self.repoint_selector(addresses)['_rp_dlg']
            payload = b''.join(builder.encode_full_fidelity(
                select(a), codes,
                collections.Counter(), a) for a in addresses)
            with self.subTest(addresses=addresses):
                # Native full-width glyph = two 4px metric cells; portrait box fits 22 glyphs.
                self.assertLessEqual(text_segment_cells(payload), 44)

    def test_joined_second_row_uses_actual_override_and_receipt_precedence(self):
        for address in (0xA0C67E, 0xA0C767):
            with self.subTest(address=hex(address)):
                namespace = self.repoint_selector([address])
                choose = namespace['_rp_dlg']
                key = f'0x{address:08X}'
                self.assertNotIn(address, namespace['_rp_script_owners'])
                namespace['_dlg_ov'][key] = '다른 문장.'
                namespace['_editor_intents'].pop(key, None)
                self.assertEqual(choose(address), '다른 문장.')
                namespace['_dlg_ov'][key] = ' 명시 편집. '
                namespace['_editor_intents'][key] = builder.editor_text_digest(' 명시 편집. ')
                self.assertEqual(choose(address), ' 명시 편집. ')
                namespace['_editor_intents'][key] = builder.editor_text_digest('이전 문장')
                self.assertEqual(choose(address), '명시 편집.')
                # Use a private map: never mutate the builder or user's current overrides.
                namespace['ADDRESS_TEXT_OVERRIDES'] = {**builder.ADDRESS_TEXT_OVERRIDES,
                                                       address: '보호된 둘째 줄.'}
                self.assertEqual(choose(address), '보호된 둘째 줄.')

    def test_kong_repetition_is_three_and_particles_match_name(self):
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA0A80B].count('콩'), 3)
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA1D24D], '　콩이 와 있어.')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA24896], '콩은 뭘 하고 있는 걸까요.')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA071F4], '콩이라고 했었지・・・')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA1227C], '콩 님・・・')

    def test_troops_motivation_is_a_statement_in_both_source_contexts(self):
        original = Path(builder.P.ROM).read_bytes()
        for preceding, address in [(0xA0C27E, 0xA0C293), (0xA12130, 0xA12145)]:
            self.assertEqual(original[preceding:address-1].decode('shift_jis'), 'ぼくの部隊のみんなも')
            self.assertEqual(original[address-1], 0x72)
            self.assertEqual(original[address:address+14].decode('shift_jis'), 'やる気だしな！')
            self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], '의욕이 넘쳐!')

    def test_transport_description_keeps_movement_and_carrying_meaning(self):
        expected = {0xDEE87E:'이동력이 지형에 따라', 0xDEE899:'줄지 않는 공중 유닛.',
                    0xDEE8C8:'을', 0xDEE8D1:'운반하기 위한 유닛.'}
        for address, text in expected.items():
            self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], text)
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xDEDD9B], '과 ')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xDEDDA9], ', 공중')

    def test_bteam_spacing_exceptions_are_only_exact_reviewed_pairs(self):
        dialogue = json.loads((Path(builder.BASE) / 'data/dialogue_overrides.json').read_text())
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())['overrides']
        intents = builder.load_editor_override_intents(Path(builder.BASE) / 'data/editor_override_intents.json')
        # 0xDEECDE: ship help 해상유닛 -> 해상 유닛 (whitespace only; integrity map 'script:ship help complete context').
        self.assertEqual(set(builder.BTEAM_SCRIPT_SPACING_REPAIRS), {0xDC3C63,0xDEDFB6,0xDEE15E,0xDEECDE})
        for address, (source, display) in builder.BTEAM_SCRIPT_SPACING_REPAIRS.items():
            key = f'0x{address:08X}'
            edited = dialogue.get(key)
            if not (edited is not None and builder.ADDRESS_TEXT_OVERRIDES.get(address) == edited
                    and intents.get(key) == builder.editor_text_digest(edited)):
                self.assertEqual(dialogue[key], source)
            self.assertEqual(baseline[f'0x{address:08X}'], source)
            self.assertEqual(source.replace(' ',''), display.replace(' ',''))
            self.assertTrue(builder.is_verified_bteam_spacing_repair(address,source,display))
            self.assertFalse(builder.is_verified_bteam_spacing_repair(address,source,display+' '))
            self.assertFalse(builder.is_verified_bteam_spacing_repair(address+1,source,display))

    def test_blurb_predicates_stay_in_their_original_second_rows(self):
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())['overrides']
        original = Path(builder.P.ROM).read_bytes()
        expected = [(0xA01ED0,0xA01EEF,0xA01EF9,'攻撃せよ！','공격하라!'),
                    (0xA021A0,0xA021BB,0xA021C7,'とりもどせ！','되찾아라!'),
                    (0xA02450,0xA0246B,0xA02473,'たたけ！','쳐라!')]
        for address, second, end, japanese, predicate in expected:
            source, display = builder.BTEAM_SCRIPT_LAYOUT_REPAIRS[address]
            key = f'0x{address:08X}'
            self.assertEqual(source, baseline[key])
            edited = self.dialogue.get(key)
            valid_edit = (edited is not None
                          and builder.ADDRESS_TEXT_OVERRIDES.get(address) == edited
                          and self.intents.get(key) == builder.editor_text_digest(edited))
            if not valid_edit:
                self.assertEqual(edited, source)
                self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], display)
            self.assertEqual(original[second-1], 0x72)
            self.assertEqual(original[second:end].decode('shift_jis'), japanese)
            # This binds A01EEF to its comprehensive-only source and the others
            # to the curated import; a missing/changed real predicate now fails.
            if second == 0xA01EEF:
                self.assertNotIn(second, self.import_rows)
                self.assertEqual(self.comprehensive_rows[second]['japanese'], japanese)
            else:
                self.assertEqual(self.import_rows[second]['japanese'], japanese)
            self.assertEqual(self.imported_text(second), predicate)
            namespace = self.repoint_selector([address, second])
            self.assertEqual(namespace['_rp_dlg'](address), edited if valid_edit else display)
            second_key = f'0x{second:08X}'
            second_edit = self.dialogue.get(second_key)
            valid_second_edit = (second_edit is not None
                                 and self.intents.get(second_key) == builder.editor_text_digest(second_edit))
            self.assertEqual(namespace['_rp_dlg'](second), second_edit if valid_second_edit else predicate)
            self.assertEqual(source.replace(' ',''), (display+predicate).replace(' ',''))
            self.assertNotIn(predicate, display)
            self.assertTrue(builder.is_verified_bteam_script_repair(address, source, display))
            self.assertFalse(builder.is_verified_bteam_script_repair(address, source, display+'!'))
            self.assertFalse(builder.is_verified_bteam_script_repair(address+1, source, display))

    def test_layout_source_drift_requires_matching_owner_and_editor_receipt(self):
        for address in builder.BTEAM_SCRIPT_LAYOUT_REPAIRS:
            with self.subTest(address=hex(address)):
                namespace = self.repoint_selector([address])
                choose = namespace['_rp_dlg']
                key = f'0x{address:08X}'
                edited = ' 다른 지시. '
                namespace['_dlg_ov'][key] = edited
                namespace['_editor_intents'].pop(key, None)
                with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                    choose(address)
                namespace['_editor_intents'][key] = builder.editor_text_digest(edited)
                with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                    choose(address)
                length = namespace['_rp_script_owners'][address][0]
                namespace['_rp_script_owners'][address] = (length, edited)
                self.assertEqual(choose(address), edited)
                namespace['_editor_intents'][key] = builder.editor_text_digest('오래된 편집')
                with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                    choose(address)

    def test_learning_prediction_and_reef_keep_source_controls_and_highlight(self):
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[0xA0CB90:0xA0CBB0].decode('shift_jis'), 'それだけ分かっていれば上出来よ！')
        self.assertEqual(original[0xA0CBB0:0xA0CBB2], b'\x77\x72')
        self.assertEqual(original[0xA0CBB2:0xA0CBC8].decode('shift_jis'), 'あとは戦っている内に、')
        self.assertEqual(original[0xA0CBC8], 0x77)
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[0xA0CBC9], '익혀 갈 거야.')
        for address in (0xA0CC60, 0xA0CC65, 0xA0CC6A):
            self.assertEqual(original[address], 0x77)
        self.assertEqual(original[0xA0CC66:0xA0CC6A].decode('shift_jis'), '岩礁')
        self.assertEqual(original[0xA0CC6F], 0x6B)
        main = next(n for n in ast.walk(self.builder_tree)
                    if isinstance(n, ast.FunctionDef) and n.name == 'main')
        literals = [(key.value, value.value) for node in ast.walk(main) if isinstance(node, ast.Dict)
                    for key, value in zip(node.keys, node.values)
                    if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)]
        self.assertEqual([value for key, value in literals if key == 0xA0CC66], ['암초'])
        for address in (0xA0CC61, 0xA0CC6B):
            self.assertNotIn(address, [key for key, _ in literals])
        highlighted = next(value for key, value in literals if key == 0xA0CC66)
        joined = (builder.ADDRESS_TEXT_OVERRIDES[0xA0CC58]
                  + builder.ADDRESS_TEXT_OVERRIDES[0xA0CC61] + highlighted
                  + builder.ADDRESS_TEXT_OVERRIDES[0xA0CC6B])
        self.assertEqual(joined, '그건, 이 암초야.')
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for address in (0xA0CBC9, 0xA0CC58, 0xA0CC61, 0xA0CC6B):
            text = builder.ADDRESS_TEXT_OVERRIDES[address]
            payload = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
            self.assertLessEqual(len(payload), builder.SCRIPT_PLAIN_OPERAND_SPANS[address] - address)
            if text.endswith(' '):
                self.assertEqual(payload[-2:], b'\x81\x40')

    def test_following_mission_joined_rows_fit_with_explicit_boundaries(self):
        from dialogue_repoint import text_segment_cells
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for addresses in [(0xA0D1F2, 0xA0D20B), (0xA0DC64, 0xA0DC75),
                          (0xA0DA98, 0xA0DA9F), (0xA0E28A, 0xA0E299),
                          (0xA0D008, 0xA0D013)]:
            with self.subTest(addresses=addresses):
                choose = self.repoint_selector(addresses)['_rp_dlg']
                payload = b''.join(builder.encode_full_fidelity(choose(a), codes,
                                      collections.Counter(), a) for a in addresses)
                self.assertLessEqual(text_segment_cells(payload), 44)
                if addresses[0] in (0xA0D1F2, 0xA0DC64, 0xA0E28A):
                    self.assertTrue(choose(addresses[0]).endswith(' '))
                if addresses[1] == 0xA0DA9F:
                    self.assertTrue(choose(addresses[1]).startswith(' '))

    def test_supplies_and_easy_adverb_stay_in_their_source_rows(self):
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[0xA0DFCC], 0x72)
        self.assertEqual(original[0xA0DFCD:0xA0DFD3].decode('shift_jis'), '物資、')
        choose = self.repoint_selector([0xA0DFBC, 0xA0DFCD])['_rp_dlg']
        self.assertNotIn('물자', choose(0xA0DFBC))
        self.assertEqual(choose(0xA0DFCD), '물자,')
        self.assertEqual(original[0xA0E16C:0xA0E17E].decode('shift_jis'), 'さすがに敵も簡単に')
        self.assertEqual(original[0xA0E17E], 0x72)
        choose = self.repoint_selector([0xA0E16C, 0xA0E17F])['_rp_dlg']
        self.assertIn('쉽게', choose(0xA0E16C))
        self.assertNotIn('쉽게', choose(0xA0E17F))

    def test_all_42_mission_blurbs_are_two_dialogue_rows_with_native_line_control(self):
        original = Path(builder.P.ROM).read_bytes()
        targets = [struct.unpack_from('<I', original, off)[0]-0x08000000
                   for off in range(0xA357E8,0xA35890,4)]
        self.assertEqual(len(targets),42)
        self.assertEqual(targets[0],0xA01C90)
        next_target = struct.unpack_from('<I',original,0xA35890)[0]-0x08000000
        self.assertEqual(next_target,0xA024A0)
        for start, end in zip(targets,targets[1:]+[next_target]):
            self.assertTrue(builder.is_part2_story_address(start))
            self.assertFalse(builder.in_region(builder.PAIR_RENDERER_REGIONS,start,end))
            cursor=start; parts=[bytearray()]; controls=[]
            while cursor<end:
                value=original[cursor]
                if is_sjis_lead(value):
                    parts[-1].extend(original[cursor:cursor+2]);cursor+=2
                elif value==0x72:
                    controls.append(value);parts.append(bytearray());cursor+=1
                else:
                    self.assertEqual(value,0)
                    self.assertFalse(any(original[cursor:end]));break
            self.assertEqual(controls,[0x72])
            self.assertEqual(len(parts),2)
            self.assertTrue(all(part.decode('shift_jis') for part in parts))
        for address in (0xA2D000,0xA2D888):
            self.assertFalse(builder.is_part2_story_address(address))

if __name__ == '__main__':
    unittest.main()
