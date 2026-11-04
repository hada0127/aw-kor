"""dialogue_rewrite_apply: W3 overlay validation and final-stage allocation.

Synthetic tests need no ROM. Overlay tests use a frozen baseline candidate
(empty overlay): AW_TEST_REWRITE_BASE (dir with build1.gba +
snap/temp/{repoint_manifest,integrity_map}.json, default
temp/fix_20261104/build1) or AW_TEST_REWRITE_ROM/_MAP/_MANIFEST; else skip.
The shared AW_TEST_ROM/MAP/MANIFEST name a shipped candidate whose overlay is
already applied (template_for refuses those messages as contract_owned), so
they are deliberately not read here.
Run: PYTHONPATH=tools python3 -m unittest tools.test_dialogue_rewrite_apply
"""
import copy
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import dialogue_rewrite_apply as dra

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = Path(os.environ.get('AW_TEST_REWRITE_BASE', ROOT / 'temp/fix_20261104/build1'))
ROM = Path(os.environ.get('AW_TEST_REWRITE_ROM', BASE_DIR / 'build1.gba'))
MAP = Path(os.environ.get('AW_TEST_REWRITE_MAP', BASE_DIR / 'snap/temp/integrity_map.json'))
MANIFEST = Path(os.environ.get('AW_TEST_REWRITE_MANIFEST', BASE_DIR / 'snap/temp/repoint_manifest.json'))
HAVE_BASE = ROM.exists() and MAP.exists() and MANIFEST.exists() and dra.ORIGINAL.exists()

# Synthetic set (plain, non-B-team rows of the 2026-11-04 W2 baseline).
P2_SAME_SLOT = 0xA01AB0      # relocated, shorter rewrite stays in its allocation
P2_NATIVE = 0xA024D4         # never relocated -> overlay arena
P1_MULTI = 0xD95860          # relocated, two command-stream pointer sites
P1_NATIVE = 0xD82080         # native portrait message
P1_PINNED = 0xB82F54         # pointer lives in the B830AC/B82FAC pinned table
P2_BTEAM = 0xA02590          # relocated B-team portrait row
P2_UNOWNED = 0xA13E44        # relocated, leading '！' owned by no source row

# Wave-2 (2026-11-04) build failures, previously refused with --exclude
# (temp/fix_20261104/waves/w2/excluded.txt); now refused by rule.
W2_CONTRACT_IDS = {
    0xDF8EAC: 'polite_choice_dialogue', 0xDF9698: 'polite_choice_dialogue',
    0xDF9654: 'polite_registration', 0xDF9674: 'polite_registration',
    0xD8F3B4: 'red_unit_intro', 0xD8F6FC: 'protected_help_apology', 0xD82028: 'map_design_intro',
    0xDF2A64: 'return_mode_question', 0xDEEB60: 'part1_ship_help', 0xDEECDC: 'part1_ship_help',
    0xDEEDD8: 'part1_submarine_help', 0xDCF608: 'part1_m19_dialogue'}
W2_WIDE_ROWS = {0xDF2078: 0xDF207A, 0xDF228C: 0xDF228E, 0xDF239C: 0xDF239E,
                0xDF26FC: 0xDF26FE, 0xDF2804: 0xDF2806, 0xDFD1B0: 0xDFD1B2}
W2_EXCEPTION_IDS = {0xA01B08: '0x00A01B08'}
W2_BATCHES = {0xD82028: 'p1-campaign.1', 0xD8F3B4: 'p1-campaign.1', 0xD8F6FC: 'p1-campaign.1',
              0xDCF608: 'p1-campaign.8', 0xDEEB60: 'p1-campaign.9', 0xDEECDC: 'p1-campaign.9',
              0xDEEDD8: 'p1-campaign.10', 0xDF2078: 'p1-campaign.10', 0xDF228C: 'p1-campaign.10',
              0xDF239C: 'p1-campaign.10', 0xDF26FC: 'p1-campaign.10', 0xDF2804: 'p1-campaign.10',
              0xDF2A64: 'p1-campaign.10', 0xDF8EAC: 'p1-campaign.11', 0xDF9654: 'p1-campaign.11',
              0xDF9674: 'p1-campaign.11', 0xDF9698: 'p1-campaign.11', 0xDFD1B0: 'p1-campaign.11',
              0xA01B08: 'p2-prologue.1'}
W2_DIR = Path(os.environ.get('AW_TEST_W2_DIR', ROOT / 'temp/fix_20261104/waves/w2'))
W2_ROM = W2_DIR / 'w2base.gba'
W2_MAP = W2_DIR / 'base/temp/integrity_map.json'
W2_MANIFEST = W2_DIR / 'base/temp/repoint_manifest.json'
W2_BATCH_ROOT = Path(os.environ.get('AW_TEST_W2_BATCHES', ROOT / 'temp/fix_20261104/humanizer/batches'))
HAVE_W2 = (W2_ROM.exists() and W2_MAP.exists() and W2_MANIFEST.exists() and dra.ORIGINAL.exists()
           and all((W2_BATCH_ROOT / b / 'out.json').exists() for b in set(W2_BATCHES.values())))


def edit(tpl, old, new):
    text = tpl.text
    if old not in text:
        raise AssertionError(f'{old!r} not in {text!r}')
    return text.replace(old, new, 1)


class SyntheticTests(unittest.TestCase):
    def test_empty_overlay_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'r.json'
            path.write_text('{}')
            self.assertEqual(dra.load_rewrites(path)['messages'], {})
            path.write_bytes(dra.canonical_bytes(dra.empty_rewrites()))
            self.assertEqual(dra.load_rewrites(path)['messages'], {})
        # W3 waves fill the committed overlay; it must stay loadable, canonical and
        # carry per-row owner texts (the qa_bteam_drift source gate reads them).
        committed = ROOT / 'data/dialogue_rewrites.json'
        data = dra.load_rewrites(committed)
        self.assertEqual(committed.read_bytes(), dra.canonical_bytes(json.loads(committed.read_text())))
        for key, entry in data['messages'].items():
            self.assertTrue(entry.get('owner_texts'), key)

    def test_empty_overlay_touches_nothing(self):
        rom, manifest, writes = bytearray(b'\xff' * 64), [{'msg': '0x1'}], [[0, 1, 1, '', None, None, None, 'x']]
        before = (bytes(rom), copy.deepcopy(manifest), copy.deepcopy(writes))
        stats = dra.apply_overlay(None, rom, manifest, writes, dra.empty_rewrites(), None)
        self.assertEqual(stats['messages'], 0)
        self.assertEqual((bytes(rom), manifest, writes), before)

    def test_fold_and_placeholders(self):
        self.assertEqual(dra.fold('하！？、。・・・　１Ａ'), '하!?,.... 1A')
        self.assertEqual(dra.PH_RE.findall('a{r}b{kw:ホ}{|}c'), ['{r}', '{kw:ホ}', '{|}'])

    def test_review_admission_rules(self):
        self.assertEqual(dra.admission({'verdict': 'accept'}, ['bteam'], 'redo'), (True, 'explicit_accept'))
        self.assertFalse(dra.admission({'verdict': 'revert'}, [], 'pass')[0])
        self.assertFalse(dra.admission({'verdict': 'rewrite_needed'}, [], 'pass')[0])
        self.assertEqual(dra.admission({}, [], 'pass'), (True, 'batch_pass_unsampled'))
        self.assertFalse(dra.admission({}, [], 'redo')[0])
        self.assertFalse(dra.admission({}, [], None)[0])
        ok, why = dra.admission({}, ['length_1.5x'], 'pass')
        self.assertFalse(ok)
        self.assertTrue(why.startswith('flagged_without_verdict'))

    def test_external_exact_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ext.json'
            path.write_text(json.dumps([{'text': '이 땅에 다시 평화가 찾아왔다.\n하지만 오래가진 않겠지.'}],
                                       ensure_ascii=False))
            index = dra.external_index([path])
        self.assertTrue(dra.external_matches('이 땅에, 다시 평화가{r}찾아왔다!{k}', index))
        self.assertFalse(dra.external_matches('이 땅엔 평화가 돌아왔다.{k}', index))

    def test_external_copy_length_rule(self):
        # > 10 normalized characters: copy (reject); <= 10: short common phrase (note only).
        index = ({'고마워정말고마워', '이땅에다시평화가찾아왔다'}, set())
        long_ = dra.external_issues('이 땅에 다시 평화가 찾아왔다.{k}', index)
        self.assertEqual([(i['code'], i['severity']) for i in long_], [('external_copy', 'reject')])
        self.assertTrue(long_[0]['detail'].startswith('12:'))
        short = dra.external_issues('고마워, 정말 고마워!{k}', index)
        self.assertEqual(short, [dict(code='external_short_match', severity='note', detail='8:고마워정말고마워')])
        # Exactly the threshold is still a common phrase.
        ten = ({'가나다라마바사아자차'}, set())
        self.assertEqual(dra.external_issues('가나다라마 바사아자차{k}', ten)[0]['severity'], 'note')
        self.assertEqual(dra.external_issues('없는 문장{k}', index), [])

    def test_batch_reviewer_from_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.assertEqual(dra.batch_reviewer(tmp, {'reviewed_by': 'harness-review/test'}), 'harness-review/test')
            self.assertEqual(dra.batch_reviewer(tmp, {'reviewed_by': 'harness-review/unknown/unknown'}), '')
            (tmp / 'review.err').write_text('▶ codex review: model=gpt-6-astra effort=medium sandbox=read-only '
                                            'out=/x/review.md\n', encoding='utf-8')
            self.assertEqual(dra.batch_reviewer(tmp, {'reviewed_by': 'harness-review/unknown/unknown'}),
                             'codex gpt-6-astra medium')
            self.assertEqual(dra.batch_reviewer(tmp, {}), 'codex gpt-6-astra medium')

    def test_committed_ledger_reviewers_are_known(self):
        ledger = json.loads(dra.LEDGER.read_text(encoding='utf-8'))
        for addr, entry in ledger.get('entries', {}).items():
            self.assertNotIn('unknown', entry['reviewed_by'].lower(), addr)

    def test_displayed_row_text(self):
        # Leading fullwidth space after {W} is part of the shipped row (p2 story).
        self.assertEqual(dra.displayed_row_text('뭐야?', '\u3000뭐야？', 0xA27A85), ' 뭐야?')
        # '.' shipped as 。 where display_equivalent predicts ． (p2 system row).
        import qa_bteam_drift as qbd
        self.assertEqual(qbd.display_equivalent('주세요.', 0xA34E98), '주세요．')
        self.assertEqual(dra.displayed_row_text('주세요.', '주세요。', 0xA34E98), '주세요。')
        self.assertEqual(qbd.display_equivalent('주세요。', 0xA34E98), '주세요。')
        # Baseline wins when it already displays as shipped (no ledger change).
        self.assertEqual(dra.displayed_row_text('뭐야 ?', '뭐야？', 0xA27A85, baseline='뭐야?'), '뭐야?')
        # Wording, a dropped authored space or a shipped control letter is never absorbed.
        self.assertIsNone(dra.displayed_row_text('뭐야?', '뭐냐？', 0xA27A85))
        self.assertIsNone(dra.displayed_row_text('뭐 야?', '뭐야？', 0xA27A85))
        self.assertIsNone(dra.displayed_row_text('뭐야?', 'W뭐야？', 0xA27A85))
        # fixB J: outside the dialogue writers '...' ships as a compacted 「・・・」 run (B12074 consumer).
        self.assertEqual(qbd.display_equivalent('후후후・・・ 이때를!', 0xB83AC8), '후후후…\u3000이때를！')
        self.assertEqual(dra.displayed_row_text('후후후... 이때를!', '후후후…\u3000이때를！', 0xB83AC8),
                         '후후후・・・ 이때를!')
        self.assertIsNone(dra.displayed_row_text('후후후... 이때를!', '후후후…\u3000이때다！', 0xB83AC8))

    def test_ledger_skips_unchanged_bteam_rows(self):
        """A B-team row whose rewritten text equals its baseline never enters the ledger."""
        import qa_bteam_drift as qbd
        baseline = json.loads(dra.BASELINE.read_text(encoding='utf-8'))
        overrides = baseline['overrides']
        free = [a for a in sorted(overrides)
                if a not in qbd.APPROVED_EXCEPTIONS
                and a not in baseline.get('_user_approved_exceptions', {})]
        same, moved = free[0], free[1]
        entry = dict(bteam_rows=[f'{int(same, 16):#08x}', f'{int(moved, 16):#08x}'],
                     owner_texts={f'{int(same, 16):#08x}': overrides[same],
                                  f'{int(moved, 16):#08x}': overrides[moved] + '!'})
        rows = dra.ledger_rows(entry, overrides)
        self.assertEqual(rows, {moved: overrides[moved] + '!'})
        ledger = {'approved': 'test', 'entries': {a: {'from': overrides[a], 'to': t, 'batch': 'b',
                                                      'reviewed_by': 'r', 'review_ref': 'x', 'message': 'm'}
                                                  for a, t in rows.items()}}
        raw = dra.canonical_bytes(ledger)
        effective = dict(overrides)
        effective.update({same: overrides[same], moved: overrides[moved] + '!'})
        self.assertEqual(qbd.ledger_errors(baseline, effective, raw, dra.sha(raw)), [])
        # The old behaviour (noop row in the ledger) is the HARD-FAIL this guards against.
        ledger['entries'][same] = dict(ledger['entries'][moved], **{'from': overrides[same], 'to': overrides[same]})
        raw = dra.canonical_bytes(ledger)
        self.assertTrue(any('does not change the text' in e
                            for e in qbd.ledger_errors(baseline, effective, raw, dra.sha(raw))))


    def test_contract_ranges_follow_builder_modules(self):
        """Native spans come from the builder's post-overlay contract modules themselves."""
        builder_src = (ROOT / 'tools/build_korean_full.py').read_text(encoding='utf-8')
        ranges = dra.contract_message_ranges()
        for name in dra.NATIVE_TEXT_CONTRACTS:
            self.assertRegex(builder_src, rf'(import|from) {name}\b', name)  # builder really rechecks it
            self.assertTrue([r for r in ranges if r[2] == f'{name} contract'], name)
        def label(source):
            return sorted(lbl for lo, hi, lbl in ranges if lo <= source < hi)
        for source, name in W2_CONTRACT_IDS.items():
            self.assertEqual(label(source), [f'{name} contract'], hex(source))
        # contract spans reach Baseline.pins through pinned_ranges()
        pins = dra.pinned_ranges()
        for item in ranges:
            self.assertIn(item, pins)

    def test_reviewed_wide_row_bytes(self):
        wide = dra.reviewed_wide_rows()
        for row in W2_WIDE_ROWS.values():
            self.assertIn(row, wide)
        row = W2_WIDE_ROWS[0xDF2078]
        raw = [bytes.fromhex(h) for h in wide[row]]
        payload, frags = b"", []
        for piece in raw:
            payload += b'\x81\x40' + piece
            frags.append((len(payload) - len(piece), len(piece)))
        key = f'{row:#08X}'.replace('0X', '0x')
        self.assertEqual(dra.reviewed_wide_row_issues(payload, {key: frags}), [])
        changed = bytearray(payload)
        changed[frags[0][0]] ^= 1
        issues = dra.reviewed_wide_row_issues(bytes(changed), {key: frags})
        self.assertEqual([i['code'] for i in issues], ['pinned'])
        self.assertIn('reviewed B-team wide row exact bytes', issues[0]['detail'])
        self.assertEqual(dra.reviewed_wide_row_issues(payload, {'0xA02590': [(0, 2)]}), [])
        # plan_C B: a rewrite back within the plain 44 half-cell cap is admitted (note only)
        short = b'\x81\x40' + bytes.fromhex(wide[row][0])[:20]
        issues = dra.reviewed_wide_row_issues(short, {key: [(2, 20)]})
        self.assertEqual([(i['code'], i['severity']) for i in issues], [('reviewed_wide_row_superseded', 'note')])

    def test_exception_rows_include_renderer_only(self):
        """qa_bteam_drift refuses a ledger entry on every recorded exception, renderer-only included."""
        import qa_bteam_drift as qbd
        baseline = json.loads(dra.BASELINE.read_text(encoding='utf-8'))
        recorded = baseline['_user_approved_exceptions']
        rows = dra.exception_rows()
        self.assertEqual(rows, set(qbd.APPROVED_EXCEPTIONS) | set(recorded))
        self.assertTrue(recorded['0x00A01B08'].get('renderer_only'))
        self.assertIn('0x00A01B08', rows)
        overrides = baseline['overrides']
        key = '0x00A01B08'
        same = dict(bteam_rows=['0xA01B08'], owner_texts={'0xA01B08': overrides[key]})
        self.assertEqual(dra.ledger_rows(same, overrides), {})   # unchanged row: skipped
        moved = dict(bteam_rows=['0xA01B08'], owner_texts={'0xA01B08': '음．'})
        with self.assertRaises(ValueError):
            dra.ledger_rows(moved, overrides)
        # the drift gate this mirrors
        raw = dra.canonical_bytes({'approved': 't', 'entries': {key: {
            'from': overrides[key], 'to': '음．', 'batch': 'b', 'reviewed_by': 'r', 'review_ref': 'x'}}})
        self.assertTrue(any('overlaps an individually approved exception' in e
                            for e in qbd.ledger_errors(baseline, overrides, raw, dra.sha(raw))))

    def test_bteam_row_display_folds_final_ellipsis(self):
        """fixB J: a rendered 「・・・」 row compares as the 「…」 check_rom reads (actual=True fold)."""
        from unittest import mock
        overrides = json.loads(dra.BASELINE.read_text(encoding='utf-8'))['overrides']
        key, row = '0xA025C4', '0x00A025C4'
        self.assertIn('・・・', overrides[row])
        frags = {key: [(0, 0)]}
        cases = {'・・・어쩔　수　없군。': overrides[row],     # shipped pre-compaction run, baseline wording
                 '・・・어쩔　수　없다。': None}               # wording change is still refused
        for rendered, want in cases.items():
            with mock.patch.object(dra, 'bteam_payload_issue', return_value=None), \
                    mock.patch.object(dra, 'row_display', return_value=rendered):
                texts, issues = dra.bteam_owner_texts(b'', frags, {}, {key: overrides[row]}, overrides)
            if want is None:
                self.assertEqual([i['code'] for i in issues], ['bteam_display_mismatch'])
            else:
                self.assertEqual((issues, texts[key]), ([], want))

    def test_unattributed_geometry_keeps_lock(self):
        """fixB C1 review #2: renderer-null geometry never unlocks a message."""
        def message(profile):
            return dict(source=0xA00004, script=True, pair_title=False, profile=profile)
        for native in (('p2_unverified_consumer', None, None), ('p2_link_state_dependent', None, None)):
            for renderer, unlocked in ((None, False), ('', False), ('0x08314BBE', True)):
                geometry = [(0xA00000, 0xA00010, dict(renderer=renderer, line_px=104, lines=2,
                                                      row_px=[104, 88], evidence=['t'], group='g'))]
                m = message(native)
                dra.apply_consumer_geometry([m], geometry)
                if unlocked:
                    self.assertEqual(m['profile'], ('declared:g', 104, 2))
                    self.assertEqual(m['row_px'], [104, 88])
                else:
                    self.assertEqual(m['profile'], native)
                    self.assertNotIn('row_px', m)
                    self.assertEqual(dra.lock_reason(None, m), 'consumer_geometry_unverified')

    def test_portrait_first_row_limit_and_ellipsis_measure(self):
        """fixB C1/C2: no portrait first row gets a 184px allowance; 「・・・」 is measured compacted."""
        class Glyphs:
            def bitmap(self, pair, game): return [[1] * 8]
            def text(self, pair): return pair.decode('shift_jis')
        glyph, dot = b'\x82\xa0', b'\x81\x45'
        def issues(game, body):
            m = dict(game=game, source=0xA00000, profile=(game + '_portrait', 176, 2))
            return dra.layout_issues(body + b'r' + glyph + b'\0', m, Glyphs())[0]
        self.assertTrue(any('overflow' in i for i in issues('p2', glyph * 23)))
        self.assertTrue(any('overflow' in i for i in issues('p1', glyph * 23)))
        self.assertEqual(issues('p1', glyph * 22), [])
        self.assertEqual(issues('p2', glyph * 22), [])
        # 20 glyphs + 3 dots = 23 cells raw, 21 cells after the builder's ellipsis stage.
        self.assertEqual(issues('p2', glyph * 20 + dot * 3), [])

    def test_shipped_unattributed_geometry_entries_stay_locked(self):
        """The 13 renderer-null entries of data/dialogue_consumer_geometry.json unlock nothing."""
        entries = [(lo, hi, e) for lo, hi, e in dra.consumer_geometry() if not e.get('renderer')]
        self.assertEqual(sorted(e['id'] for _, _, e in entries),
                         sorted(['0x337', '0x368', '0x4c7', '0x4cb', '0x4cc', '0x7ad', '0x7af', '0x7b0',
                                 '0xb45', '0xcb9', '0xcba', '0xcbb', '0xcbc']))
        for lo, _, _ in entries:
            m = dict(source=lo, script=True, pair_title=False, profile=('p2_unverified_consumer', None, None))
            dra.apply_consumer_geometry([m])
            self.assertEqual(dra.lock_reason(None, m), 'consumer_geometry_unverified')


@unittest.skipUnless(HAVE_BASE, 'frozen baseline candidate not available')
class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = dra.Baseline(dra.ORIGINAL.read_bytes(), bytearray(ROM.read_bytes()),
                                json.loads(MANIFEST.read_text()), json.loads(MAP.read_text()))
        cls.syl = dra.load_syl_to_code()
        cls.encode = staticmethod(dra.builder_encoder(cls.syl))
        cls.rewrites = {}
        cases = {
            P2_SAME_SLOT: ('워즈 월드 안에서', '워즈 월드의'),
            P2_NATIVE: ('생각보다', '예상보다 훨씬'),
            P1_MULTI: ('그리고', '그리고 말이야,'),
            P1_NATIVE: ('눌러 메뉴에서', '눌러서 메뉴에서'),
        }
        for source, (old, new) in cases.items():
            cls.rewrites[source] = cls.entry(source, edit(cls.tpl(source), old, new))

    @classmethod
    def tpl(cls, source):
        return dra.template_for(cls.base, source)

    @classmethod
    def entry(cls, source, ko, **extra):
        tpl = dra.template_for(cls.base, source)
        payload = dra.render(tpl, ko, cls.encode, [])[0]
        return dict(source=dra.key6(source), game=tpl.m['game'], before_sha256=dra.sha(tpl.m['payload']),
                    after_sha256=dra.sha(payload), ko=ko, batch='test', reviewed_by='test', review_ref='test', **extra)

    def doc(self, *sources):
        return {'schema': 1, 'messages': {dra.key6(s): self.rewrites[s] for s in sources}}

    def run_overlay(self, doc, **kw):
        rom = bytearray(self.base.rom)
        manifest = copy.deepcopy(self.base.manifest)
        writes = copy.deepcopy(self.base.writes)
        stats = dra.apply_overlay(self.base.original, rom, manifest, writes, doc, self.encode, base=self.base, **kw)
        return rom, manifest, writes, stats

    def record(self, manifest, source):
        found = [m for m in manifest if int(m['msg'], 16) == source and m.get('status') == 'relocated']
        self.assertEqual(len(found), 1)
        return found[0]

    def test_unchanged_text_roundtrips_bytes(self):
        for source in (P2_SAME_SLOT, P2_NATIVE, P1_MULTI, P1_NATIVE):
            tpl = self.tpl(source)
            self.assertEqual(dra.render(tpl, tpl.text, self.encode)[0], tpl.m['payload'])

    def test_full_synthetic_set(self):
        doc = self.doc(P2_SAME_SLOT, P2_NATIVE, P1_MULTI, P1_NATIVE)
        rom, manifest, writes, stats = self.run_overlay(doc)
        self.assertEqual((stats['messages'], stats['same_slot'], stats['repointed']), (4, 1, 3))
        start = int(stats['arena_start'], 16)
        self.assertEqual(start, (self.base.high_water() + 3) & ~3)
        self.assertGreaterEqual(start, 0xA8D84C)
        allowed = []
        for source in (P2_SAME_SLOT, P2_NATIVE, P1_MULTI, P1_NATIVE):
            m = self.base.messages[source]
            rec = self.record(manifest, source)
            target = int(rec['new_addr'], 16)
            payload = bytes(rom[target:target + rec['new_len']])
            self.assertEqual(dra.sha(payload), doc['messages'][dra.key6(source)]['after_sha256'])
            sites = [int(s, 16) for s in rec['ptr_sites']]
            for site in sites:  # multi-reference: every site follows
                self.assertEqual(struct.unpack_from('<I', rom, site)[0], 0x08000000 + target)
            if source == P2_SAME_SLOT:
                self.assertEqual(target, m['target'])
                allowed.append((target, target + len(m['payload'])))
            else:
                self.assertGreaterEqual(target, start)
                self.assertLess(target + rec['new_len'], dra.ARENA_END)
                allowed.append((target, target + rec['new_len']))
                allowed.extend((s, s + 4) for s in sites)
                # orphaned old bytes are left as they were
                self.assertEqual(rom[m['target']:m['target'] + len(m['payload'])], m['payload'])
            self.assertIn('rewrite', rec)
        self.assertEqual(len(self.record(manifest, P1_MULTI)['ptr_sites']), 2)
        # whole-ROM diff containment
        changed = _diff_ranges(self.base.rom, rom)
        for lo, hi in changed:
            self.assertTrue(any(a <= lo and hi <= b for a, b in allowed), f'unexpected change {lo:#x}..{hi:#x}')
        from qa_dialogue_jamming import validate_manifest
        validate_manifest(rom, manifest, self.base.original, writes)
        tags = [w[7] for w in writes[len(self.base.writes):]]
        self.assertEqual(tags.count('dialogue-rewrite-final'), 4)
        self.assertEqual(tags.count('dialogue-rewrite-pointer'), 1 + 2 + len(self.base.messages[P1_NATIVE]['sites']))

    def test_same_slot_shrink_owns_whole_old_allocation(self):
        """S3 (fixB): a shorter same-slot rewrite zero-pads and owns the old tail."""
        from qa_part1_dialogue_punctuation import active_text_payloads
        m = self.base.messages[P2_SAME_SLOT]
        old_size = len(m['payload'])
        rom, manifest, writes, stats = self.run_overlay(self.doc(P2_SAME_SLOT))
        self.assertEqual(stats['same_slot'], 1)
        target = m['target']
        final = [w for w in writes[len(self.base.writes):] if w[7] == 'dialogue-rewrite-final']
        self.assertEqual(len(final), 1)
        payload = bytes.fromhex(final[0][3])
        self.assertLess(len(payload), old_size)
        self.assertEqual(final[0][:3], [target, old_size, len(payload)])
        self.assertEqual(final[0][4], 0x00)
        self.assertEqual(bytes(rom[target:target + old_size]), payload + bytes(old_size - len(payload)))
        rec = self.record(manifest, P2_SAME_SLOT)
        self.assertEqual(rec['new_len'], len(payload))  # binding = real message; ownership = old slot
        # no surviving half token of the previous writer inside the old allocation
        lo, hi = target, target + old_size
        region = [w for w in writes if w[0] < hi and lo < w[0] + max(int(w[1]), int(w[2]))]
        for _entry, _start, _payload in active_text_payloads(region, bytes(rom)):
            pass

    def test_deterministic(self):
        doc = self.doc(P2_SAME_SLOT, P2_NATIVE, P1_MULTI, P1_NATIVE)
        a = self.run_overlay(doc)
        b = self.run_overlay(copy.deepcopy(doc))
        self.assertEqual(bytes(a[0]), bytes(b[0]))
        self.assertEqual(a[1], b[1])
        self.assertEqual(a[2], b[2])

    def test_pinned_message_rejected(self):
        with self.assertRaises(dra.RewriteError) as ctx:
            dra.template_for(self.base, P1_PINNED)
        self.assertEqual(ctx.exception.code, 'pinned')
        self.assertIn('B830AC candidate table', ctx.exception.detail)
        doc = {'schema': 1, 'messages': {dra.key6(P1_PINNED): dict(
            source=dra.key6(P1_PINNED), game='p1', before_sha256='0', after_sha256='0', ko='x',
            batch='t', reviewed_by='t', review_ref='t')}}
        rom = bytearray(self.base.rom)
        with self.assertRaises(dra.OverlayError) as err:
            dra.apply_overlay(self.base.original, rom, [], [], doc, self.encode, base=self.base)
        self.assertEqual(err.exception.problems[0]['code'], 'pinned')
        self.assertEqual(bytes(rom), bytes(self.base.rom))

    def test_builder_text_contract_messages_rejected(self):
        """Messages whose complete text a post-overlay builder contract pins are refused."""
        expected = {0xA1F944: 'part2_dialogue_layout_contracts', 0xA1F9D8: 'part2_dialogue_layout_contracts',
                    0xA21840: 'part2_context_contract teacher', 0xA21990: 'part2_context_contract teacher',
                    0xA199B0: 'part2_context_contract', 0xA1D444: 'part2_volcano_context',
                    0xA1D4BC: 'part2_volcano_context'}
        self.assertEqual(dra.text_contract_sources(), expected)
        for source, label in expected.items():
            with self.assertRaises(dra.RewriteError) as ctx:
                dra.template_for(self.base, source)
            self.assertEqual((ctx.exception.code, ctx.exception.detail), ('pinned', label))

    def test_capacity_failure_mutates_nothing(self):
        doc = self.doc(P2_NATIVE, P1_NATIVE)
        start = (self.base.high_water() + 3) & ~3
        rom = bytearray(self.base.rom)
        manifest = copy.deepcopy(self.base.manifest)
        writes = copy.deepcopy(self.base.writes)
        with self.assertRaises(dra.OverlayError) as err:
            dra.apply_overlay(self.base.original, rom, manifest, writes, doc, self.encode,
                              base=self.base, arena_end=start + 16)
        self.assertEqual(err.exception.problems[0]['code'], 'capacity')
        self.assertEqual(bytes(rom), bytes(self.base.rom))
        self.assertEqual(manifest, self.base.manifest)
        self.assertEqual(writes, self.base.writes)

    def test_stale_payload_and_pointer_rejected(self):
        stale = dict(self.rewrites[P2_SAME_SLOT], before_sha256='0' * 64)
        with self.assertRaises(dra.OverlayError) as err:
            dra.plan_overlay(self.base, {'messages': {dra.key6(P2_SAME_SLOT): stale}}, self.encode)
        self.assertEqual(err.exception.problems[0]['code'], 'stale_before')
        moved = copy.copy(self.base)
        moved.rom = bytearray(self.base.rom)
        site = int(self.base.messages[P1_MULTI]['relocated']['ptr_sites'][1], 16)
        struct.pack_into('<I', moved.rom, site, 0x08A00000)
        with self.assertRaises(dra.OverlayError) as err:
            dra.plan_overlay(moved, self.doc(P1_MULTI), self.encode)
        self.assertEqual(err.exception.problems[0]['code'], 'stale_pointer')

    def test_validation_rejects(self):
        tpl = self.tpl(P2_NATIVE)

        def codes(ko, glossary=(), external=(set(), set()), jp=''):
            issues = dra.validate_message(tpl, ko, encode=self.encode, syl_to_code=self.syl, glossary=glossary,
                                          external=external, jp=jp, current_ko=tpl.text,
                                          glyphs=self.base.glyphs)[0]
            return {i['code'] for i in issues if i['severity'] == 'reject'}
        self.assertEqual(codes(edit(tpl, '생각보다', '예상보다')), set())
        self.assertIn('placeholder_mismatch', codes(tpl.text.replace('{k}', '')))
        self.assertIn('outside_2350', codes(edit(tpl, '생각보다', '햏보다')))
        self.assertIn('term_conflict', codes(edit(tpl, '생각보다', '장군보다')))
        # 2026-11-04 user (inputs.md msg9): title is 게임보이 워즈 어드밴스 again.
        self.assertNotIn('term_conflict', codes(edit(tpl, '생각보다', '게임보이 워즈 어드밴스보다')))
        for old in ('어드밴스 워즈보다', '어드밴스　워즈보다', '어드밴스워즈보다'):
            with self.subTest(old=old):
                self.assertIn('term_conflict', codes(edit(tpl, '생각보다', old)))
        self.assertIn('lint_hex_token', codes(edit(tpl, '생각보다', '0x1234보다')))
        self.assertIn('latin_text', codes(edit(tpl, '생각보다', 'OK보다')))
        self.assertIn('external_name', codes(edit(tpl, '생각보다', '앤디보다')))
        self.assertIn('width', codes(edit(tpl, '생각보다', '생각보다 훨씬 더 훨씬 더 훨씬 더 훨씬 더')))
        ko = edit(tpl, '생각보다', '예상보다')
        index = ({dra._norm_external(ko)}, set())
        long_ = len(dra._norm_external(ko)) > dra.EXTERNAL_COPY_MAX_COMMON
        self.assertEqual('external_copy' in codes(ko, external=index), long_)
        p1 = self.tpl(P1_NATIVE)
        gl = [('メニュー', '메뉴')]
        issues = dra.validate_message(p1, p1.text.replace('메뉴에서', '거기서'), encode=self.encode,
                                      syl_to_code=self.syl, glossary=gl, external=(set(), set()),
                                      jp='メニュー', current_ko=p1.text, glyphs=self.base.glyphs)[0]
        self.assertIn('glossary_dropped', {i['code'] for i in issues})

    def test_unowned_segment_and_owner_erase(self):
        tpl = self.tpl(P2_SAME_SLOT)
        owned = [i for i, p in enumerate(tpl.pieces) if p['owner'] and p['text'].strip()]
        texts = dra.PH_RE.split(tpl.text)
        texts[owned[0]] = ''
        names = tpl.names
        ko = ''.join(t + (names[i] if i < len(names) else '') for i, t in enumerate(texts))
        if len([i for i in owned if tpl.pieces[i]['owner'] == tpl.pieces[owned[0]]['owner']]) == 1:
            with self.assertRaises(dra.RewriteError) as ctx:
                dra.render(tpl, ko, self.encode)
            self.assertEqual(ctx.exception.code, 'owner_erased')

    def test_bteam_rows_agree_with_final_rom_gate(self):
        """Owner/ledger text equals what qa_bteam_drift.check_rom reads (wave-1 excluded cases)."""
        import qa_bteam_drift as qbd
        bteam = json.loads(dra.BASELINE.read_text(encoding='utf-8'))['overrides']
        cases = {0xA27A80: ('뭐,{W} 뭐야?{W}{r}네가 어째서!?{k}', '0xA27A85', ' 뭐야?'),
                 0xA27AA8: ('헬,{W} 헬보우즈님...{W}{r}호크, 무슨 짓을...!{k}', '0xA27AAD', ' 헬보우즈님...'),
                 0xA34E98: ('미사일을 쏠 곳을 골라 주세요.{k}', '0xA34E98', '미사일을 쏠 곳을 골라 주세요。')}
        doc = {'schema': 1, 'messages': {}}
        entries = {}
        for source, (ko, row, want) in cases.items():
            tpl = self.tpl(source)
            payload, fragments, joiners, texts = dra.render(tpl, ko, self.encode)
            self.assertNotEqual(texts[row], want)  # the raw owner text is what wave 1 had to exclude
            texts, issues = dra.bteam_owner_texts(payload, fragments, joiners, texts, bteam)
            self.assertEqual((issues, texts[row]), ([], want))
            entry = self.entry(source, ko, owner_texts=texts)
            doc['messages'][dra.key6(source)] = entry
            for key, to in dra.ledger_rows(dict(entry, bteam_rows=[row]), bteam).items():
                entries[key] = {'from': bteam[key], 'to': to, 'batch': 'b', 'reviewed_by': 'r',
                                'review_ref': 'x', 'message': dra.key6(source)}
        self.assertEqual(len(entries), 3)
        ledger = dra.canonical_bytes({'approved': 'test', 'entries': entries})
        rom, manifest, writes, _ = self.run_overlay(doc)
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            paths = [Path(tmp, n) for n in ('r.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes, ensure_ascii=False))
            paths[2].write_text(json.dumps(manifest, ensure_ascii=False))
            base = json.loads(dra.BASELINE.read_text(encoding='utf-8'))
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                issues = qbd.check_rom(base, *map(str, paths), ledger_bytes=ledger, ledger_pinned=dra.sha(ledger))
            finally:
                os.chdir(cwd)
        self.assertFalse([i for i in issues if i['address'] in entries], issues)
        overrides = json.loads(Path(qbd.OVERRIDES).read_text(encoding='utf-8'))
        src = qbd.check(base, overrides, ledger_bytes=ledger, ledger_pinned=dra.sha(ledger), rewrites=doc)
        self.assertFalse([d for d in src['drift'] if d[0] in entries])
        self.assertFalse([e for e in src['errors'] if any(a in e for a in entries)])

    def test_unowned_segment_overlay(self):
        """Unowned text may change only in a whole-message arena write (2026-11-04 item 7)."""
        source = P2_UNOWNED
        tpl = self.tpl(source)
        idx = next(i for i, p in enumerate(tpl.pieces) if p['owner'] is None and p['text'].strip())
        texts = dra.PH_RE.split(tpl.text)
        texts[idx] = '?' if dra.fold(texts[idx]) != '?' else '!'
        join = lambda parts: ''.join(t + (tpl.names[i] if i < len(tpl.names) else '') for i, t in enumerate(parts))
        ko = join(texts)
        with self.assertRaises(dra.RewriteError) as ctx:
            dra.render(tpl, ko, self.encode)
        self.assertEqual(ctx.exception.code, 'unowned_segment_changed')
        log = []
        payload, _, _, owner_texts = dra.render(tpl, ko, self.encode, log)
        self.assertEqual([c['piece'] for c in log], [idx])
        self.assertNotEqual(payload, tpl.m['payload'])
        self.assertLessEqual(len(payload), len(tpl.m['payload']))  # would fit its slot
        self.assertEqual(owner_texts, tpl.owner_texts)
        issues = dra.validate_message(tpl, ko, encode=self.encode, syl_to_code=self.syl, glossary=(),
                                      external=(set(), set()), jp='', current_ko=tpl.text,
                                      glyphs=self.base.glyphs)[0]
        self.assertIn('unowned_segment_overlay', {i['code'] for i in issues})
        self.assertFalse([i for i in issues if i['severity'] == 'reject'], issues)
        doc = {'schema': 1, 'messages': {dra.key6(source): self.entry(source, ko)}}
        plan = dra.plan_overlay(self.base, doc, self.encode)['plans'][0]
        self.assertFalse(plan['same_slot'])
        rom, manifest, writes, stats = self.run_overlay(doc)
        self.assertEqual((stats['repointed'], stats['same_slot']), (1, 0))
        record = self.record(manifest, source)
        self.assertNotEqual(int(record['new_addr'], 16), tpl.m['target'])
        self.assertTrue([w for w in writes if w[7] == 'dialogue-rewrite-retired-allocation'
                         and w[0] == tpl.m['target']])
        # Inserting text at an empty unowned position stays refused (unless it
        # touches a style control: see test_empty_style_slot_and_kana_drop).
        styled = lambda i: any(tpl.phs[j]['name'] in ('{s0}', '{s2}', '{s3}')
                               for j in (i - 1, i) if 0 <= j < len(tpl.phs))
        empty = next((i for i, p in enumerate(tpl.pieces)
                      if p['owner'] is None and not p['raw'] and not styled(i)), None)
        if empty is not None:
            texts = dra.PH_RE.split(tpl.text)
            texts[empty] = '가'
            with self.assertRaises(dra.RewriteError):
                dra.render(tpl, join(texts), self.encode, [])

    def test_empty_style_slot_and_kana_drop(self):
        """plan_C B (2026-11-04): an empty emphasis slot may take its keyword, a
        Part 1 small-tsu kana token may be dropped; both force the arena write."""
        def styled(tpl, i):
            return any(tpl.phs[j]['name'] in ('{s0}', '{s2}', '{s3}') for j in (i - 1, i) if 0 <= j < len(tpl.phs))
        def join(tpl, parts):
            return ''.join(t + (tpl.names[i] if i < len(tpl.names) else '') for i, t in enumerate(parts))
        tpl = self.tpl(0xD961A0)  # 「그리고{s2}{s0} …」: empty unowned {s2}..{s0}
        slot = next(i for i, p in enumerate(tpl.pieces)
                    if p['owner'] is None and not p['raw'] and i and tpl.phs[i - 1]['name'] == '{s2}')
        self.assertTrue(styled(tpl, slot))
        texts = dra.PH_RE.split(tpl.text)
        texts[slot] = '자주포'
        ko = join(tpl, texts)
        with self.assertRaises(dra.RewriteError):
            dra.render(tpl, ko, self.encode)            # no unowned list: still refused
        unowned = []
        payload = dra.render(tpl, ko, self.encode, unowned)[0]
        self.assertEqual([u['piece'] for u in unowned], [slot])
        self.assertEqual(len(payload), len(tpl.m['payload']) + len(self.encode('자주포', tpl.m['source'])))
        doc = {'schema': 1, 'messages': {dra.key6(0xD961A0): self.entry(0xD961A0, ko)}}
        self.assertFalse(dra.plan_overlay(self.base, doc, self.encode)['plans'][0]['same_slot'])
        tpl = self.tpl(0xDC5244)  # 「뭐라고{kw:っ}?!」
        self.assertEqual(tpl.names.count('{kw:っ}'), 2)
        ko = tpl.text.replace('{kw:っ}', '{kw-:っ}')
        with self.assertRaises(dra.RewriteError):
            dra.render(tpl, ko, self.encode)
        unowned = []
        payload = dra.render(tpl, ko, self.encode, unowned)[0]
        self.assertEqual(len(payload), len(tpl.m['payload']) - 4)  # two 2-byte kana dropped
        self.assertEqual(len(unowned), 2)
        with self.assertRaises(dra.RewriteError):     # only small tsu may be dropped
            dra.render(tpl, ko.replace('{kw-:っ}', '{kw-:ア}', 1), self.encode, [])

    def test_caption_indent_kept(self):
        """A changed CO-bio caption row keeps its 5-cell leading indent (0xDF3764 「海」)."""
        tpl = self.tpl(0xDF3764)
        ko = tpl.text.replace('해상', '바다', 1)
        payload = dra.render(tpl, ko, self.encode, [])[0]
        self.assertEqual(len(payload), len(tpl.m['payload']))
        self.assertEqual(dra.layout_issues(payload, tpl.m, self.base.glyphs)[0], [])

    def test_exception_row_left_as_approved(self):
        """A rewrite of 0xA01B08 that keeps the user-approved 「음．」 row adds no ledger row."""
        bteam = json.loads(dra.BASELINE.read_text(encoding='utf-8'))['overrides']
        tpl = self.tpl(0xA01B08)
        ko = '음.{k}예전에{w} 나는{w} 이 별에서 전쟁을 일으켜,{w}{r}그 틈을 타 공략하려 했지만 실패했다.{k}'
        payload, fragments, joiners, texts = dra.render(tpl, ko, self.encode, [])
        raw_texts = dict(texts)
        texts, issues = dra.bteam_owner_texts(payload, fragments, joiners, texts, bteam)
        self.assertEqual(issues, [])
        self.assertEqual(texts['0xA01B08'], bteam['0x00A01B08'])
        self.assertEqual(dra.ledger_rows(dict(bteam_rows=['0xA01B08'], owner_texts=texts), bteam), {})
        # Read as the builder ships it (patch_rewritten 、/。 -> ，/．): same outcome.
        texts, issues = dra.bteam_owner_texts(payload, fragments, joiners, raw_texts, bteam, source=0xA01B08)
        self.assertEqual(issues, [])
        self.assertEqual(texts['0xA01B08'], bteam['0x00A01B08'])

    def test_prologue_rewrite_compared_as_shipped(self):
        """fixB C2: 0xA019F8 is read after patch_rewritten, where the final gate reads it."""
        bteam = json.loads(dra.BASELINE.read_text(encoding='utf-8'))['overrides']
        tpl = self.tpl(0xA019F8)
        payload, fragments, joiners, texts = dra.render(tpl, '호크, 거기 있느냐!{k}', self.encode, [])
        _, issues = dra.bteam_owner_texts(payload, fragments, joiners, dict(texts), bteam)
        self.assertEqual([i['code'] for i in issues], ['bteam_display_mismatch'])  # pre-stage bytes
        texts, issues = dra.bteam_owner_texts(payload, fragments, joiners, texts, bteam, source=0xA019F8)
        self.assertEqual(issues, [])
        self.assertEqual(texts['0xA019F8'], '호크, 거기 있느냐!')
        # A different wording still has to match the shipped display exactly.
        payload, fragments, joiners, texts = dra.render(tpl, '호크, 거기 있느냐!{k}', self.encode, [])
        texts['0xA019F8'] = '호크. 거기 있느냐!'
        _, issues = dra.bteam_owner_texts(payload, fragments, joiners, texts, bteam, source=0xA019F8)
        self.assertEqual([i['code'] for i in issues], ['bteam_display_mismatch'])

    def test_superseded_spacing_intent(self):
        intents = [w for w in self.base.writes if w[7] == 'dialogue-spacing-final-intent' and len(w) > 8]
        for w in intents:
            source = None
            for m in self.base.manifest:
                if m.get('status') == 'relocated' and dra.key6(w[8]['source_address']) in m.get('line_spans', {}):
                    source = int(m['msg'], 16)
            if source is None:
                continue
            try:
                tpl = dra.template_for(self.base, source)
                payload = dra.render(tpl, tpl.text, self.encode)[0]
            except dra.RewriteError:
                continue
            words = [p for p in tpl.pieces if p['owner'] and len(p['text'].strip()) > 1]
            if not words:
                continue
            ko = tpl.text.replace(dra.fold(words[0]['text']), dra.fold(words[0]['text'])[:-1], 1)
            try:
                entry = self.entry(source, ko)
                doc = {'schema': 1, 'messages': {dra.key6(source): entry}}
                dra.plan_overlay(self.base, doc, self.encode)
            except (dra.RewriteError, dra.OverlayError):
                continue
            rom, manifest, writes, stats = self.run_overlay(doc)
            self.assertGreaterEqual(stats['superseded_intents'], 1)
            self.assertFalse([x for x in writes if x[7] == 'dialogue-spacing-final-intent'
                              and x[8]['source_address'] == w[8]['source_address']])
            return
        self.skipTest('no rewritable spacing-intent owner in this baseline')


@unittest.skipUnless(HAVE_BASE, 'frozen baseline candidate not available')
class CliTests(unittest.TestCase):
    def test_batch_apply_ledger_and_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base = dra.Baseline(dra.ORIGINAL.read_bytes(), bytearray(ROM.read_bytes()),
                                json.loads(MANIFEST.read_text()), json.loads(MAP.read_text()))
            bt = dra.template_for(base, P2_BTEAM)
            plain = dra.template_for(base, P2_SAME_SLOT)
            native = dra.template_for(base, P2_NATIVE)
            batch = tmp / 'p2-test'
            batch.mkdir()
            out = {'batch': 'p2-test', 'messages': [
                {'id': f'{P2_BTEAM:#x}', 'ko': edit(bt, '피해가', '피해만'), 'unchanged': False, 'reason': 't'},
                {'id': f'{P2_SAME_SLOT:#x}', 'ko': edit(plain, '워즈 월드 안에서', '워즈 월드의'), 'reason': 't'},
                {'id': f'{P2_NATIVE:#x}', 'ko': edit(native, '생각보다', '예상보다'), 'reason': 't'}]}
            review = {'batch': 'p2-test', 'reviewed_by': 'harness-review/test', 'sampled': [f'{P2_NATIVE:#x}'],
                      'flagged_all': [f'{P2_BTEAM:#x}'],
                      'verdicts': {f'{P2_BTEAM:#x}': {'verdict': 'accept', 'note': 't'},
                                   f'{P2_NATIVE:#x}': {'verdict': 'revert', 'note': 't'}},
                      'summary': {'batch_verdict': 'pass'}}
            (batch / 'out.json').write_text(json.dumps(out, ensure_ascii=False))
            (batch / 'review.json').write_text(json.dumps(review, ensure_ascii=False))
            rewrites = tmp / 'rewrites.json'
            ledger = tmp / 'ledger.json'
            ledger.write_bytes((ROOT / 'data/bteam_approved_rewrites.json').read_bytes())
            res = subprocess.run([sys.executable, str(ROOT / 'tools/dialogue_rewrite_apply.py'),
                                  '--rom', str(ROM), '--manifest', str(MANIFEST), '--map', str(MAP),
                                  '--batches', str(batch), '--rewrites', str(rewrites), '--ledger', str(ledger),
                                  '--report-dir', str(tmp / 'report')], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            data = dra.load_rewrites(rewrites)
            self.assertEqual(sorted(data['messages']), [dra.key6(P2_SAME_SLOT), dra.key6(P2_BTEAM)])
            diff = {d['id']: d for d in json.loads((tmp / 'report/diff.json').read_text())}
            self.assertEqual(diff[dra.key6(P2_BTEAM)]['admitted_by'], 'explicit_accept')
            self.assertEqual(diff[dra.key6(P2_SAME_SLOT)]['admitted_by'], 'batch_pass_unsampled')
            led = json.loads(ledger.read_text())
            baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())['overrides']
            rows = [k for k, v in led['entries'].items() if v['message'] == dra.key6(P2_BTEAM)]
            self.assertTrue(rows)
            for key in rows:
                self.assertEqual(led['entries'][key]['from'], baseline[key])
                self.assertEqual(led['entries'][key]['reviewed_by'], 'harness-review/test')
            self.assertIn(dra.sha(ledger.read_bytes()), res.stdout)
            self.assertEqual(ledger.read_bytes(), dra.canonical_bytes(led))
            # G11 mode on the result
            ext = tmp / 'ext.json'
            ext.write_text(json.dumps([{'text': data['messages'][dra.key6(P2_SAME_SLOT)]['ko']}], ensure_ascii=False))
            res = subprocess.run([sys.executable, str(ROOT / 'tools/dialogue_rewrite_apply.py'),
                                  '--check-external', str(ext), '--rewrites', str(rewrites)],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 1, res.stdout)


    def test_exclude_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base = dra.Baseline(dra.ORIGINAL.read_bytes(), bytearray(ROM.read_bytes()),
                                json.loads(MANIFEST.read_text()), json.loads(MAP.read_text()))
            plain = dra.template_for(base, P2_SAME_SLOT)
            batch = tmp / 'p2-x'
            batch.mkdir()
            (batch / 'out.json').write_text(json.dumps({'batch': 'p2-x', 'messages': [
                {'id': f'{P2_SAME_SLOT:#x}', 'ko': edit(plain, '워즈 월드 안에서', '워즈 월드의'), 'reason': 't'}]},
                ensure_ascii=False))
            (batch / 'review.json').write_text(json.dumps({'batch': 'p2-x', 'reviewed_by': 'r', 'verdicts': {},
                                                          'summary': {'batch_verdict': 'pass'}}))
            rewrites, ledger = tmp / 'rw.json', tmp / 'led.json'
            ledger.write_bytes((ROOT / 'data/bteam_approved_rewrites.json').read_bytes())
            res = subprocess.run([sys.executable, str(ROOT / 'tools/dialogue_rewrite_apply.py'),
                                  '--rom', str(ROM), '--manifest', str(MANIFEST), '--map', str(MAP),
                                  '--batches', str(batch), '--rewrites', str(rewrites), '--ledger', str(ledger),
                                  '--exclude', f'{P2_SAME_SLOT:#x}:test reason', '--report-dir', str(tmp / 'rep')],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(dra.load_rewrites(rewrites)['messages'], {})
            log = json.loads((tmp / 'rep/apply_log.json').read_text())
            self.assertEqual(log[0]['issues'], [dict(code='wave_excluded', severity='reject', detail='test reason')])

@unittest.skipUnless(HAVE_W2, 'wave-2 frozen baseline/batches not available')
class Wave2ExcludedTests(unittest.TestCase):
    """The 19 wave-2 --exclude ids are refused by rule (no --exclude needed)."""

    def test_wave2_excluded_ids_rejected_by_rule(self):
        ids = set(W2_CONTRACT_IDS) | set(W2_WIDE_ROWS) | set(W2_EXCEPTION_IDS)
        self.assertEqual(ids, set(W2_BATCHES))
        self.assertEqual(len(ids), 19)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dirs = []
            for name in sorted(set(W2_BATCHES.values())):
                src = W2_BATCH_ROOT / name
                # out_pre_extfix.json is the out.json wave 2 applied (later extfix edits other rows)
                out_path = src / 'out_pre_extfix.json'
                out = json.loads((out_path if out_path.exists() else src / 'out.json').read_text(encoding='utf-8'))
                want = {s for s, b in W2_BATCHES.items() if b == name}
                out['messages'] = [m for m in out['messages'] if int(m['id'], 16) in want]
                self.assertEqual(len(out['messages']), len(want), name)
                self.assertFalse([m['id'] for m in out['messages'] if m.get('unchanged')], name)
                dst = tmp / name
                dst.mkdir()
                (dst / 'out.json').write_text(json.dumps(out, ensure_ascii=False))
                for extra in ('review.json', 'review.err', 'in.json'):
                    if (src / extra).exists():
                        (dst / extra).write_bytes((src / extra).read_bytes())
                dirs.append(str(dst))
            rewrites, ledger = tmp / 'rw.json', tmp / 'led.json'
            rewrites.write_bytes(dra.canonical_bytes(dra.empty_rewrites()))
            ledger_bytes = (W2_DIR / 'empty_ledger.json').read_bytes()
            ledger.write_bytes(ledger_bytes)
            res = subprocess.run([sys.executable, str(ROOT / 'tools/dialogue_rewrite_apply.py'),
                                  '--rom', str(W2_ROM), '--manifest', str(W2_MANIFEST), '--map', str(W2_MAP),
                                  '--rewrites', str(rewrites), '--ledger', str(ledger), '--report-dir',
                                  str(tmp / 'rep'), '--batches', *dirs], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            log = {int(r['id'], 16): r for r in json.loads((tmp / 'rep/apply_log.json').read_text())}
            accepted = {s for s, r in log.items() if r['status'] == 'accepted'}
            self.assertIn(f'accepted {len(accepted)},', res.stdout)
            self.assertEqual({int(k, 16) for k in dra.load_rewrites(rewrites)['messages']}, accepted)
            if not accepted:
                self.assertEqual(ledger.read_bytes(), ledger_bytes)
        self.assertEqual(set(log), ids)
        # plan_C B (2026-11-04): contract-owned messages stay refused; a reviewed
        # wide row rewritten back within 44 half-cells, and an exception row the
        # rewrite leaves exactly as approved, are admitted.
        for source in accepted:
            self.assertNotIn(source, W2_CONTRACT_IDS)
            codes = {i['code'] for i in log[source]['issues']}
            if source in W2_WIDE_ROWS:
                self.assertIn('reviewed_wide_row_superseded', codes, hex(source))
            self.assertNotIn('bteam_exception_row', codes, hex(source))
        for source, row in log.items():
            if source in accepted:
                continue
            self.assertEqual(row['status'], 'rejected', hex(source))
            first = next(i for i in row['issues'] if i['severity'] == 'reject')
            self.assertNotEqual(first['code'], 'wave_excluded')
            if source in W2_CONTRACT_IDS:
                self.assertEqual((first['code'], first['detail']),
                                 ('pinned', f'{W2_CONTRACT_IDS[source]} contract'), hex(source))
            elif source in W2_WIDE_ROWS:
                self.assertEqual(first['code'], 'pinned', hex(source))
                self.assertIn(f'{W2_WIDE_ROWS[source]:#08X}'[2:], first['detail'])
                self.assertIn('reviewed B-team wide row exact bytes', first['detail'])
            else:
                self.assertEqual(first['code'], 'bteam_exception_row', hex(source))
                self.assertIn(W2_EXCEPTION_IDS[source], first['detail'])


def _diff_ranges(a, b):
    out = []
    step = 4096
    for block in range(0, len(a), step):
        if a[block:block + step] == b[block:block + step]:
            continue
        i = block
        while i < min(block + step, len(a)):
            if a[i] != b[i]:
                j = i
                while j < len(a) and a[j] != b[j]:
                    j += 1
                out.append((i, j))
                i = j
            else:
                i += 1
    return out


if __name__ == '__main__':
    unittest.main()
