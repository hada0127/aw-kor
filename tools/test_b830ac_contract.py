"""Bounded writer/inventory/preservation fixtures; no ROM output or build."""
import ast
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import b830ac_contract as c
import dialogue_pixel_layout as layout
import build_korean_full as builder
import dialogue_repoint as repointer
from qa_b830ac_preservation import validate

ROOT = Path(os.environ.get('AW_B830AC_BASELINE', '.'))

@unittest.skipUnless(os.environ.get('AW_B830AC_BASELINE'), 'read-only build0616 required')
class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.baseline = (ROOT/'output/game_wars_korean_ec3190_candidate.gba').read_bytes()
        cls.manifest = json.loads((ROOT/'temp/repoint_manifest.json').read_text())
        cls.lossless = json.loads((ROOT/'temp/repoint_lossless_requests.json').read_text())
        cls.candidate_manifest = [m for m in cls.manifest if m.get('msg') != '0xB830AC']
        from hashlib import sha256
        assert sha256(cls.baseline).hexdigest() == 'c23f1d97ea45fbe8541b9f3ebc84d17e7fca9dfafeff0e3dd5e202937310bd2e'
        tree = ast.parse(Path(builder.__file__).read_text())
        main = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_build')
        start = next(i for i,n in enumerate(main.body) if isinstance(n,ast.ImportFrom) and n.module=='b830ac_contract')
        stop = next(i for i,n in enumerate(main.body[start:],start) if isinstance(n,ast.ImportFrom) and n.module=='part2_mission_title_fit')
        cls.code = compile(ast.Module(body=main.body[start:stop],type_ignores=[]),'<actual baseline writer>','exec')
        cls.syl = {k:int(v,16) if isinstance(v,str) else v for k,v in json.loads((ROOT/'data/syllable_to_code_2350.json').read_text()).items()}

    def run_writer(self, rom, owner=c.OWNER, authority=c.TEXT, original=None, syl=None, writes=None):
        from qa_bteam_drift import display_equivalent
        writes=[] if writes is None else writes
        ns=dict(orig=self.original if original is None else original,rom=rom,WRITE_LOG=writes,
            _round2_baseline={'0x00B830AC':authority},_round2_final_writes={} if owner is None else {c.START:owner},
            BTEAM_ROUND2_RESTORE={c.START},BTEAM_ROUND2_RESIDUALS={},_round2_relocated=set(),
            LINK_WELCOME_SENTENCES={},_round2_script_punctuation=set(),
            _bteam_display_equivalent=display_equivalent,encode_text=builder.encode_text,
            syl_to_code=self.syl if syl is None else syl,unmapped={})
        exec(self.code,ns)
        return writes

    def working(self):
        rom=bytearray(self.baseline);rom[c.START:c.TAIL]=c.ROW
        return rom

    def test_actual_writer_positive_and_preservation(self):
        rom=self.working();writes=self.run_writer(rom);c.final(rom,writes)
        self.assertEqual(validate(self.baseline,rom,self.manifest,self.candidate_manifest,self.lossless,self.lossless)['preserved'],2982)
        if os.environ.get('AW_B830AC_EVIDENCE'):
            from hashlib import sha256
            Path(os.environ['AW_B830AC_EVIDENCE']).write_text(json.dumps(dict(
                kind='in-memory focused fixture, not fresh build',
                baseline_sha256=sha256(self.baseline).hexdigest(),
                modeled_sha256=sha256(rom).hexdigest(),writes=writes,
                preservation=validate(self.baseline,rom,self.manifest,self.candidate_manifest,self.lossless,self.lossless)),indent=2,ensure_ascii=False))
        self.assertNotIn(c.START,builder.BTEAM_ROUND2_RESIDUALS)
        self.assertEqual(len(builder.BTEAM_ROUND2_RESIDUALS),90)

    def test_actual_repointer_and_manifest_contract(self):
        rom = self.working()
        before = bytes(rom)
        calls = []
        encoded, level = builder.encode_fit(c.TEXT, 24, self.syl, {}, c.START)
        self.assertEqual((encoded, level), (c.ROW, 0))

        def fit_level(address):
            self.assertEqual(address, c.START)
            calls.append(address)
            return level

        writes = []
        manifest, stats = repointer.repoint_messages(
            rom, self.original, fixable=lambda a: a == c.START,
            fixed_bytes=lambda a: c.ROW, fit_level_dlg=fit_level,
            decode_text=lambda raw: raw.decode('shift_jis', errors='replace'),
            cell_width=lambda a: repointer.text_segment_cells(c.ROW),
            slots={c.START: 24}, line_index={c.START: (24, c.TEXT)},
            table_offsets=[], extra_messages={c.START: [c.SITE]},
            free_start=0xA8D7B4, free_end=0xA8D7B8, write_log=writes)
        self.assertEqual(calls, [c.START])  # Passed guards and evaluated real line.
        self.assertEqual(manifest, [])  # Actual no-jam branch emits no skip record.
        self.assertEqual(stats, {'extra_messages': 1, 'free_used': 0, 'free_avail': 4})
        self.assertEqual(bytes(rom), before)
        self.assertEqual(writes, [])
        index = next(i for i, m in enumerate(self.manifest) if m.get('msg') == '0xB830AC')
        candidate = self.manifest[:index] + manifest + self.manifest[index+1:]
        result = validate(self.baseline, rom, self.manifest, candidate, self.lossless, self.lossless)
        self.assertEqual(result['preserved'], 2982)
        if os.environ.get('AW_B830AC_EVIDENCE'):
            Path(os.environ['AW_B830AC_EVIDENCE'] + '.repointer.json').write_text(json.dumps(dict(
                kind='bounded actual repoint_messages, one real consumer; not full build',
                input_hex=c.ROW.hex(), fit_level=level, fit_calls=calls,
                actual_manifest=manifest, stats=stats, writes=writes,
                removed_index=index, removed_record=self.manifest[index], preservation=result), indent=2))

    def test_manifest_removal_negatives(self):
        rom = self.working()
        old = self.manifest
        candidate = self.candidate_manifest
        bad_candidates = {}
        bad_candidates['unchanged'] = old
        bad_candidates['other deletion'] = candidate[1:]
        skip_index = next(i for i, m in enumerate(candidate) if m.get('status', '').startswith('skip'))
        bad_candidates['other skip deletion'] = candidate[:skip_index] + candidate[skip_index+1:]
        bad = copy.deepcopy(candidate); del bad[0]['status']
        bad_candidates['missing key'] = bad
        bad = copy.deepcopy(candidate); bad[0]['unknown'] = 'changed'
        bad_candidates['other metadata'] = bad
        bad = copy.deepcopy(candidate); bad[0]['status'] = 'changed'
        bad_candidates['other value'] = bad
        bad = copy.deepcopy(candidate); bad[0], bad[1] = bad[1], bad[0]
        bad_candidates['order'] = bad
        for status in ('relocated', 'skip_forced', 'skip_impure_span'):
            bad_candidates[status] = candidate + [dict(msg='0xB830AC', status=status)]
        skip = dict(msg='0xB830AC', status='skip_impure_span')
        bad_candidates['duplicate target'] = candidate + [skip, skip]
        bad_candidates['duplicate other'] = candidate + [candidate[0]]
        for label, bad in bad_candidates.items():
            with self.subTest(candidate=label), self.assertRaisesRegex(AssertionError, 'manifest'):
                validate(self.baseline, rom, old, bad, self.lossless, self.lossless)
        for replacement in ([], [dict(skip, extra=True)], [dict(skip, status='skip_forced')],
                            [dict(skip, status='relocated')], [skip, skip]):
            bad = copy.deepcopy(old)
            index = next(i for i, m in enumerate(bad) if m.get('msg') == '0xB830AC')
            bad[index:index+1] = replacement
            with self.subTest(baseline=replacement), self.assertRaisesRegex(AssertionError, 'baseline'):
                validate(self.baseline, rom, bad, candidate, self.lossless, self.lossless)

    def test_prewrite_negatives(self):
        mutations=[('owner',None),('owner',c.OWNER[:1]+[28]+c.OWNER[2:]),('authority','보낼 지도'),
            ('native',c.START),('native',c.TAIL),('rom',c.TAIL),('rom',c.SITE),
            ('rom',0xD8D998),('rom',0xB33424),('rom',c.START)]
        for kind,value in mutations:
            with self.subTest(kind=kind,value=value):
                rom=self.working();orig=bytearray(self.original);kw={}
                if kind=='rom':rom[value]^=1
                elif kind=='native':orig[value]^=1;kw['original']=orig
                else:kw[kind]=value
                before=bytes(rom);writes=[];kw['writes']=writes
                with self.assertRaises((AssertionError,ValueError,KeyError)):self.run_writer(rom,**kw)
                self.assertEqual(bytes(rom),before);self.assertEqual(writes,[])
        rom=self.working();rom[0x100:0x104]=(0x08000000+c.START+2).to_bytes(4,'little')
        with self.assertRaisesRegex(AssertionError,'aligned'):self.run_writer(rom)
        syl=dict(self.syl);syl.pop('보')
        rom=self.working();before=bytes(rom)
        with self.assertRaises((AssertionError,ValueError,KeyError)):self.run_writer(rom,syl=syl)
        self.assertEqual(rom,before)
        with self.assertRaisesRegex(AssertionError,'encoding'):c.preflight(self.original,rom,c.OWNER,c.TEXT,c.ROW[:-2])

    def test_final_owner_and_tail(self):
        rom=self.working();writes=self.run_writer(rom)
        for altered in ([],writes+[list(c.OWNER)],writes+[[c.TAIL,1,1,'00',0,None,None,'late']]):
            with self.assertRaises(AssertionError):c.final(rom,altered)
        rom[c.TAIL]=1
        with self.assertRaises(AssertionError):c.final(rom,writes)

    def test_preservation_negatives(self):
        rom=self.working()
        for pos in (c.START-1,c.TAIL,0xD8D998,int(next(m for m in self.manifest if m.get('status')=='relocated')['new_addr'],16)):
            bad=bytearray(rom);bad[pos]^=1
            with self.assertRaises(AssertionError):validate(self.baseline,bad,self.manifest,self.candidate_manifest,self.lossless,self.lossless)
        for key,value in (('new_addr','0xA40000'),('unknown','changed'),('ptr_sites',[])):
            bad=copy.deepcopy(self.candidate_manifest);next(m for m in bad if m.get('status')=='relocated')[key]=value
            with self.assertRaises(AssertionError):validate(self.baseline,rom,self.manifest,bad,self.lossless,self.lossless)
        loss=copy.deepcopy(self.lossless);loss['requested'].reverse()
        with self.assertRaises(AssertionError):validate(self.baseline,rom,self.manifest,self.candidate_manifest,self.lossless,loss)

    def inventory(self,rom,consumers):
        with patch.object(layout,'p1_consumers',return_value=consumers),patch.object(layout,'p2_consumers',return_value={}),patch.object(layout,'_read_table',return_value=[]):
            entries=layout.inventory(self.original,rom,[])
        if len(entries)!=1:raise AssertionError('missing consumer')
        e=entries[0]
        if (e['source']!=c.START or e['target']!=c.START or e['sites']!=[c.SITE]
                or e['payload']!=c.ROW+b'\0' or e['profile']!=('p1_link_notice',208,1)):
            raise AssertionError('actual inventory pointer/payload/profile changed')
        return entries

    def test_real_inventory(self):
        consumers=layout.p1_consumers(self.original)
        self.assertEqual(consumers[c.START],[dict(site=c.SITE,profile=('p1_link_notice',208,1),consumer='B333FC link notice')])
        bounded={c.START:consumers[c.START]};rom=self.working();self.run_writer(rom)
        entries=self.inventory(rom,bounded)
        with patch.object(layout,'inventory',return_value=entries):result=layout.audit(self.original,rom,[])
        self.assertFalse(result['errors']);self.assertEqual([(r['advance_px'],r['limit_px']) for r in result['rows']],[(96,208)])
        for row in result['rows']:
            for key in ('overflow','row_overflow','glyph_errors','caption_overlap'):self.assertFalse(row[key])
        with self.assertRaisesRegex(AssertionError,'missing consumer'):self.inventory(rom,{})
        for pos in (c.SITE,c.START+2):
            bad=bytearray(rom);bad[pos]=0
            with self.assertRaises((AssertionError,ValueError)):self.inventory(bad,bounded)
        for raw,key in ((c.ROW+b'\x81\x40'*30+b'\0','overflow'),(c.ROW+b'\x72'+c.ROW+b'\0','row_overflow')):
            with patch.object(layout,'inventory',return_value=[dict(entries[0],payload=raw)]):bad=layout.audit(self.original,rom,[])
            self.assertTrue(any(r[key] for r in bad['rows']))

if __name__=='__main__':unittest.main()
