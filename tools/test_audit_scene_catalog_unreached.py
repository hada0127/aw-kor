"""Bounded negative dialogue coverage stays a warning only with complete evidence."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from PIL import Image

from tools.audit_scene_catalog import classify_unreached_dialogue

ROOT = Path(__file__).resolve().parents[1]
GROUP = 'g_00DF8B6A'
ROM_SHA = '7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'


class UnreachedDialogueTest(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT/'data/scene_catalog_overrides.json').read_text())[
            'unreached_dialogue'][0]

    def classify(self, record=None, rom_sha=ROM_SHA):
        return classify_unreached_dialogue([GROUP], [record or self.record], rom_sha)

    def assert_critical(self, record, reason, rom_sha=ROM_SHA):
        warnings, critical = self.classify(record, rom_sha)
        self.assertEqual(warnings, [])
        self.assertEqual([x['group_id'] for x in critical], [GROUP])
        self.assertIn(reason, critical[0]['problems'])

    def modified_probe(self, change):
        directory = TemporaryDirectory(dir=ROOT/'temp')
        self.addCleanup(directory.cleanup)
        work = Path(directory.name)
        rec = copy.deepcopy(self.record)
        old = json.loads((ROOT/rec['watch_logs'][0]['receipt']).read_text())
        log = work/'watch.log'
        events = work/'frame_events.jsonl'
        frame = work/'control_frame.png'
        log.write_bytes((ROOT/old['watch_log']).read_bytes())
        events.write_bytes((ROOT/old['frame_event_log']).read_bytes())
        frame.write_bytes((ROOT/old['control_frame']).read_bytes())
        old['watch_log'] = str(log.relative_to(ROOT))
        old['frame_event_log'] = str(events.relative_to(ROOT))
        old['control_frame'] = str(frame.relative_to(ROOT))
        old['watch_setup'][0]['command'] = (
            f"watchaddr {old['watch_setup'][0]['gba_start'][2:]} "
            f"{old['watch_setup'][0]['size']} r {log}")
        change(old, log, events)
        old['watch_log_sha256'] = hashlib.sha256(log.read_bytes()).hexdigest()
        old['frame_event_log_sha256'] = hashlib.sha256(events.read_bytes()).hexdigest()
        old['control_frame_sha256'] = hashlib.sha256(frame.read_bytes()).hexdigest()
        receipt = work/'receipt.json'
        receipt.write_text(json.dumps(old))
        rec['watch_logs'][0].update(path=old['watch_log'], screen=old['control_frame'],
                                    receipt=str(receipt.relative_to(ROOT)),
                                    receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())
        return rec

    def test_complete_negative_evidence_is_warning(self):
        warnings, critical = self.classify()
        self.assertEqual([x['group_id'] for x in warnings], [GROUP])
        self.assertEqual(critical, [])

    def test_unchanged_relocated_probe_is_warning(self):
        warnings, critical = self.classify(self.modified_probe(lambda receipt, log, events: None))
        self.assertEqual([x['group_id'] for x in warnings], [GROUP])
        self.assertEqual(critical, [])

    def test_missing_or_broken_evidence_is_critical(self):
        for field, reason in (('routes', 'one route required'),
                              ('watch_logs', 'one watch log required'),
                              ('reviewer', 'reviewer missing'),
                              ('rationale', 'rationale missing')):
            with self.subTest(field=field):
                record = copy.deepcopy(self.record)
                record.pop(field)
                self.assert_critical(record, reason)
        record = copy.deepcopy(self.record)
        record['watch_logs'][0]['positive_control_address'] = '0x08DF8B6A'
        self.assert_critical(record, 'target/control span mismatch')

    def test_stale_candidate_rom_is_critical(self):
        self.assert_critical(self.record, 'probe ROM SHA mismatch', '0' * 64)

    def test_missing_watch_setup_is_critical(self):
        self.assert_critical(self.modified_probe(lambda receipt, log, events: receipt.update(watch_setup=[])),
                             'watch setup missing')

    def test_unrelated_frame_or_route_is_critical(self):
        for change in (lambda receipt, log, events: receipt['control_hits'][0].update(core_frame=42),
                       lambda receipt, log, events: receipt['control_hits'][0].update(route_id='unrelated')):
            with self.subTest(change=change):
                self.assert_critical(self.modified_probe(change),
                                     'positive control frame/route does not match probe log')

    def test_interior_byte_hit_is_critical(self):
        def change(receipt, log, events):
            line = log.read_text().splitlines()[0]
            changed = line.replace('addr=08DF8B62', 'addr=08DF8B6B')
            log.write_text(log.read_text() + changed + '\n')
            events.write_text(events.read_text() + json.dumps({
                'log_line': 4, 'core_frame': 6520, 'raw': changed}) + '\n')
        self.assert_critical(self.modified_probe(change), 'target member slot read on probe route')

    def test_absent_positive_control_is_critical(self):
        def change(receipt, log, events):
            log.write_text('')
            events.write_text('')
            receipt['control_hits'] = []
        self.assert_critical(self.modified_probe(change), 'positive control hit evidence missing')

    def test_multi_member_gap_without_watch_is_critical(self):
        group = next(g for g in json.loads((ROOT/'data/dialogue_groups.json').read_text())['groups']
                     if g['group_id'] == GROUP)
        group = copy.deepcopy(group)
        second = copy.deepcopy(group['members'][0])
        second.update(address='0x00DF8B72', slot=3)
        group['members'].append(second)
        group['size'] = 2
        def change(receipt, log, events):
            receipt['target_span'] = ['0x08DF8B6A', '0x08DF8B75']
        record = self.modified_probe(change)
        with mock.patch('tools.audit_scene_catalog.load', return_value={'groups': [group]}):
            self.assert_critical(record, 'target member slot unwatched')

    def test_separated_members_with_full_watches_are_warning(self):
        group = next(g for g in json.loads((ROOT/'data/dialogue_groups.json').read_text())['groups']
                     if g['group_id'] == GROUP)
        group = copy.deepcopy(group)
        second = copy.deepcopy(group['members'][0])
        second.update(address='0x00DF8B72', slot=3)
        group['members'].append(second)
        group['size'] = 2
        def change(receipt, log, events):
            receipt['target_span'] = ['0x08DF8B6A', '0x08DF8B75']
            receipt['watch_setup'].insert(1, {
                'gba_start': '0x08DF8B72', 'size': 3, 'mode': 'r',
                'command': f'watchaddr 08DF8B72 3 r {log}',
                'response': 'OK watchaddr 08DF8B72 len=3 set=3',
            })
        record = self.modified_probe(change)
        with mock.patch('tools.audit_scene_catalog.load', return_value={'groups': [group]}):
            warnings, critical = self.classify(record)
        self.assertEqual([row['group_id'] for row in warnings], [GROUP])
        self.assertEqual(critical, [])

    def test_unrelated_screenshot_with_valid_hashes_is_critical(self):
        def change(receipt, log, events):
            frame = log.parent/'control_frame.png'
            Image.new('RGB', (1, 1), (255, 0, 0)).save(frame)
            receipt['control_frame_core_frame'] = receipt['first_watched_frame']
        self.assert_critical(self.modified_probe(change),
                             'control screenshot frame does not match positive control hit')


if __name__ == '__main__':
    unittest.main()
