import importlib.util
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import playthrough_capture as P
import jev_game_choice as LiveJ
import jev_call_evidence as Calls

SPEC = importlib.util.spec_from_file_location('game_choice', Path(__file__).with_name('jev_game_choice.py'))
J = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(J)


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        audit = tempfile.TemporaryDirectory(dir=J.ROOT / 'temp')
        self.addCleanup(audit.cleanup)
        patcher = patch.object(Calls, 'AUDIT_ROOT', Path(audit.name))
        patcher.start(); self.addCleanup(patcher.stop)
        env_patch = patch.dict(J.os.environ, {'JEV_API_KEY': 'mock-test-secret'})
        env_patch.start(); self.addCleanup(env_patch.stop)
        self.candidates = [{'id': 'c0', 'stage': 'inspect'}, {'id': 'c1', 'stage': 'commit'}]
        self.response = {'model': 'jev-latest', 'usage': {'input_tokens': 20, 'output_tokens': 4},
                         'answers': {'next_action': {'type': 'choice', 'choice': 'c0', 'confidence': .8,
                           'probabilities': {'c0': .9, 'c1': .1}}}}

    def test_persistent_calls_allow_eighth_block_ninth_and_duplicate(self):
        for i in range(8):
            Calls.reserve(f'{i:064x}', Path('report.json'))
        with self.assertRaisesRegex(J.JevError, 'already reserved'):
            Calls.reserve(f'{0:064x}', Path('different-session.json'))
        with self.assertRaisesRegex(J.JevError, 'Daily'):
            Calls.reserve(f'{8:064x}', Path('report.json'))

    def test_persistent_response_failure_retains_usage(self):
        path = Calls.reserve('a' * 64, Path('report.json'))
        Calls.complete(path, 'api_or_response_error', response=self.response, error=J.JevError('bad answer'))
        record = json.loads(path.read_text())
        self.assertEqual(record['usage'], self.response['usage'])
        self.assertEqual(record['status'], 'api_or_response_error')
        with self.assertRaises(J.JevError):
            Calls.reserve('a' * 64, Path('new-session.json'))

    def test_cli_failed_response_is_reserved_before_api_and_cannot_retry(self):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            root = Path(temp); source = root / 'candidate.json'; dest = root / 'result.json'
            doc = {'state': {}, 'objective': 'inspect', 'candidates': [
                {'id': f'c{i}', 'action': 'wait', 'preconditions': 'visible',
                 'expected': 'unchanged', 'stage': 'inspect'} for i in range(2)]}
            source.write_text(json.dumps(doc))
            bad_response = {'model': 'jev-latest', 'usage': self.response['usage'], 'answers': {}}
            def api(*args):
                self.assertEqual(json.loads(dest.read_text())['status'], 'request_started')
                self.assertEqual(len(list(Calls.AUDIT_ROOT.glob('*.json'))), 1)
                return bad_response
            with patch.object(J.sys, 'argv', ['jev', '--input', str(source), '--live', '--output', str(dest)]), \
                 patch.object(J, 'request_api', side_effect=api):
                self.assertEqual(J.main(), 2)
            record = json.loads(next(Calls.AUDIT_ROOT.glob('*.json')).read_text())
            self.assertEqual(record['usage'], self.response['usage'])
            with patch.object(J.sys, 'argv', ['jev', '--input', str(source), '--live', '--output', str(dest)]), \
                 patch.object(J, 'request_api') as api:
                self.assertEqual(J.main(), 2)
                api.assert_not_called()

    def test_missing_key_cannot_create_paid_call_reservation(self):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            root = Path(temp); source = root / 'candidate.json'; dest = root / 'result.json'
            source.write_text(json.dumps({'state': {}, 'objective': 'inspect', 'candidates': [
                {'id': f'c{i}', 'action': 'wait', 'preconditions': 'visible',
                 'expected': 'unchanged', 'stage': 'inspect'} for i in range(2)]}))
            with patch.dict(J.os.environ, {'JEV_API_KEY': ''}), \
                 patch.object(J.sys, 'argv', ['jev', '--input', str(source), '--live', '--output', str(dest)]), \
                 patch.object(J, 'request_api') as api:
                self.assertEqual(J.main(), 2)
                api.assert_not_called()
            self.assertFalse(dest.exists())
            self.assertFalse(list(Calls.AUDIT_ROOT.glob('*.json')))

    def test_stage_specific_confidence_thresholds(self):
        self.assertTrue(J.validate(self.response, self.candidates)['candidate_confidence_eligible'])
        self.response['answers']['next_action']['confidence'] = .64
        result = J.validate(self.response, self.candidates)
        self.assertTrue(result['candidate_confidence_eligible'])
        self.response['answers']['next_action']['choice'] = 'c1'
        self.response['answers']['next_action']['probabilities'] = {'c0': .1, 'c1': .9}
        self.assertFalse(J.validate(self.response, self.candidates)['candidate_confidence_eligible'])
        self.response['answers']['next_action']['confidence'] = .7
        self.assertTrue(J.validate(self.response, self.candidates)['candidate_confidence_eligible'])

    def test_rejects_unknown_ids_non_top_choice_and_bad_probability(self):
        for mutate in (
            lambda a: a.update(probabilities={'c0': .9, 'c2': .1}),
            lambda a: a.update(choice='c1'),
            lambda a: a.update(probabilities={'c0': float('nan'), 'c1': .1}),
        ):
            response = __import__('copy').deepcopy(self.response)
            mutate(response['answers']['next_action'])
            with self.assertRaises(J.JevError): J.validate(response, self.candidates)

    def test_capture_binding_rejects_stale_rom_frame_checkpoint_and_image(self):
        state = {'observed_rom_sha256': 'a' * 64, 'observed_frame': 42,
                 'checkpoint_sha256': 'b' * 64, 'frame_image_sha256': 'c' * 64}
        expected = {'rom_sha256': 'a' * 64, 'frame': 42,
                    'checkpoint_sha256': 'b' * 64, 'frame_image_sha256': 'c' * 64}
        self.assertTrue(J.validate_capture_binding(state, **expected))
        for key, value in (('observed_rom_sha256', 'd' * 64), ('observed_frame', 43),
                           ('checkpoint_sha256', 'd' * 64), ('frame_image_sha256', 'd' * 64)):
            stale = dict(state); stale[key] = value
            with self.subTest(key=key), self.assertRaises(J.JevError):
                J.validate_capture_binding(stale, **expected)
        stale = dict(state); stale['observed_frame'] = True
        with self.assertRaises(J.JevError): J.validate_capture_binding(stale, **expected)

    def test_only_eligible_predeclared_local_macro_is_returned(self):
        doc = {'candidates': [{'id': 'c0', 'stage': 'inspect', 'inputs': [{'key': 'UP', 'release_frames': 5,
                                                                          'hold_frames': 2}]}]}
        eligible = {'choice': 'c0', 'candidate_confidence_eligible': True}
        self.assertEqual(J.selected_macro(doc, eligible), doc['candidates'][0]['inputs'])
        eligible['candidate_confidence_eligible'] = False
        self.assertIsNone(J.selected_macro(doc, eligible))
        eligible['candidate_confidence_eligible'] = True
        self.assertIsNone(J.selected_macro({'candidates': [{'id': 'c0', 'stage': 'inspect'}]}, eligible))
        doc['candidates'][0]['stage'] = 'commit'
        self.assertIsNone(J.selected_macro(doc, eligible))

    def test_payload_never_sends_local_input_macro(self):
        doc = {'state': {'turn': 1}, 'objective': 'safe progress', 'candidates': [
            {'id': 'c0', 'action': 'inspect menu', 'preconditions': 'map visible',
             'expected': 'menu opens', 'stage': 'inspect',
             'inputs': [{'key': 'UP', 'release_frames': 2, 'hold_frames': 1}]},
            {'id': 'c1', 'action': 'wait', 'preconditions': 'map visible',
             'expected': 'no change', 'stage': 'inspect'}]}
        self.assertNotIn('inputs', json.dumps(J.payload(doc)))

    def test_probability_mass_and_margin_are_checked(self):
        self.response['answers']['next_action']['probabilities'] = {'c0': .52, 'c1': .48}
        with self.assertRaises(J.JevError): J.validate(self.response, self.candidates)
        self.response['answers']['next_action']['probabilities'] = {'c0': .95, 'c1': .1}
        with self.assertRaises(J.JevError): J.validate(self.response, self.candidates)

    def test_input_size_and_non_finite_state_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            path = Path(temp) / 'input.json'
            path.write_bytes(b' ' * (J.MAX_FILE + 1))
            with self.assertRaises(J.JevError): J.load_input(path)
            doc = {'state': {'bad': float('nan')}, 'objective': 'test', 'candidates': [
                {'id': 'c0', 'action': 'a', 'preconditions': 'p', 'expected': 'e', 'stage': 'inspect'},
                {'id': 'c1', 'action': 'b', 'preconditions': 'p', 'expected': 'e', 'stage': 'inspect'}]}
            path.write_text(json.dumps(doc))
            with self.assertRaises(J.JevError): J.load_input(path)
            path.write_text('[' * 3000 + ']' * 3000)
            with self.assertRaises(J.JevError): J.load_input(path)

    def test_unreadable_input_is_a_recoverable_candidate_error(self):
        with patch.object(Path, 'open', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(J.JevError, 'could not be read'):
                J.load_input(J.ROOT / 'tools/fixtures/jev_semantic_smoke.json')

    def test_macro_caps_and_non_confirming_keys_are_enforced(self):
        candidate = {'id': 'c0', 'action': 'inspect', 'preconditions': 'map',
                     'expected': 'same screen', 'stage': 'inspect',
                     'inputs': [{'key': 'UP', 'release_frames': 10, 'hold_frames': 2}]}
        doc = {'state': {}, 'objective': 'safe', 'candidates': [candidate,
            {'id': 'c1', 'action': 'wait', 'preconditions': 'map', 'expected': 'none', 'stage': 'inspect'}]}
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            path = Path(temp) / 'input.json'
            path.write_text(json.dumps(doc))
            J.load_input(path)
            for macro in (
                [{'key': 'A', 'release_frames': 10, 'hold_frames': 2}],
                [{'key': 'UP', 'release_frames': 481, 'hold_frames': 1}],
                [{'key': 'UP', 'release_frames': 60, 'hold_frames': 1}] * 9,
            ):
                broken = json.loads(json.dumps(doc)); broken['candidates'][0]['inputs'] = macro
                path.write_text(json.dumps(broken))
                with self.assertRaises(J.JevError): J.load_input(path)

    def test_invalid_usage_model_and_boolean_probability_are_rejected(self):
        invalid_responses = []
        bad = __import__('copy').deepcopy(self.response); bad['usage'] = {'input_tokens': True, 'output_tokens': 1}
        invalid_responses.append(bad)
        bad = __import__('copy').deepcopy(self.response); bad['model'] = 'bad model!'
        invalid_responses.append(bad)
        bad = __import__('copy').deepcopy(self.response); bad['answers']['next_action']['probabilities']['c0'] = True
        invalid_responses.append(bad)
        for response in invalid_responses:
            with self.subTest(response=response), self.assertRaises(J.JevError): J.validate(response, self.candidates)

    def test_recorder_stale_image_binding_is_rejected_before_paid_call(self):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            root = Path(temp); out = root / 'run'; out.mkdir()
            checkpoint = out / 'frame.checkpoint.json'; checkpoint.write_text('{}\n')
            image_sha = 'c' * 64
            (out / 'frames.jsonl').write_text(json.dumps({'core_frame': 42,
                'image': 'frames/' + image_sha + '.png', 'rgb_sha256': image_sha}) + '\n')
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'objective': 'safe', 'state': {
                'observed_rom_sha256': 'a' * 64, 'observed_frame': 42,
                'checkpoint_sha256': P.sha(checkpoint), 'frame_image_sha256': 'd' * 64},
                'candidates': [{'id': 'c0', 'action': 'inspect', 'preconditions': 'visible',
                    'expected': 'safe', 'stage': 'inspect'}, {'id': 'c1', 'action': 'wait',
                    'preconditions': 'visible', 'expected': 'safe', 'stage': 'inspect'}]}))
            recorder = object.__new__(P.Recorder)
            recorder.out = out; recorder.rom_sha = 'a' * 64; recorder.committed = 42
            recorder.counter = 42; recorder.last_checkpoint = str(checkpoint)
            recorder.proc = type('Proc', (), {'poll': lambda self: None})()
            recorder.protocol_failed = False; recorder.jev_requests = set()
            with patch.object(LiveJ, 'request_api') as api, self.assertRaises(J.JevError):
                recorder.jev_choice(candidate)
            api.assert_not_called()
            valid_doc = json.loads(candidate.read_text())
            valid_doc['state']['frame_image_sha256'] = image_sha
            candidate.write_text(json.dumps(valid_doc))
            (out / 'frames.jsonl').write_text('not-json\n')
            with patch.object(LiveJ, 'request_api') as api, self.assertRaisesRegex(RuntimeError, 'invalid final record'):
                recorder.jev_choice(candidate)
            api.assert_not_called()

    def test_recorder_persists_success_and_failed_api_attempt_reports(self):
        suffix = uuid.uuid4().hex
        # jev_choice prefixes its date directory with "jev_".
        report_dir = J.ROOT / 'temp' / ('jev_' + 'test_' + suffix)
        report_dir.mkdir(parents=True)

        def make_recorder(root):
            out = root / 'run'; out.mkdir(parents=True)
            checkpoint = out / 'frame.checkpoint.json'; checkpoint.write_text('{}\n')
            image_sha = 'c' * 64
            (out / 'frames.jsonl').write_text(json.dumps({'core_frame': 42,
                'image': 'frames/' + image_sha + '.png', 'rgb_sha256': image_sha}) + '\n')
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'objective': 'safe progress ' + root.name, 'state': {
                'observed_rom_sha256': 'a' * 64, 'observed_frame': 42,
                'checkpoint_sha256': P.sha(checkpoint), 'frame_image_sha256': image_sha},
                'candidates': [{'id': 'c0', 'action': 'move cursor to inspect',
                    'preconditions': 'map visible', 'expected': 'cursor moved', 'stage': 'inspect',
                    'inputs': [{'key': 'UP', 'release_frames': 5, 'hold_frames': 1}]},
                    {'id': 'c1', 'action': 'wait', 'preconditions': 'map visible',
                    'expected': 'no change', 'stage': 'inspect'}]}))
            recorder = object.__new__(P.Recorder)
            recorder.out = out; recorder.rom_sha = 'a' * 64; recorder.committed = 42
            recorder.counter = 42; recorder.last_checkpoint = str(checkpoint)
            recorder.proc = type('Proc', (), {'poll': lambda self: None})()
            recorder.protocol_failed = False; recorder.jev_requests = set(); recorder.min_free = 0
            recorder.actions = (out / 'actions.jsonl').open('w+', encoding='utf-8')
            return recorder, candidate

        good_response = {'model': 'jev-latest', 'usage': {'input_tokens': 30, 'output_tokens': 4},
            'answers': {'next_action': {'type': 'choice', 'choice': 'c0', 'confidence': .9,
                'probabilities': {'c0': .9, 'c1': .1}}}}
        try:
            with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
                recorder, candidate = make_recorder(Path(temp) / 'good')
                with patch.dict(LiveJ.os.environ, {'JEV_API_KEY': ''}), \
                     patch.object(LiveJ, 'request_api') as api:
                    with self.assertRaisesRegex(J.JevError, 'missing'):
                        recorder.jev_choice(candidate)
                    api.assert_not_called()
                self.assertFalse(list(Calls.AUDIT_ROOT.glob('*.json')))
                def success_api(*_args):
                    attempt_path = report_dir / 'capture_choice_42_1.json'
                    self.assertEqual(json.loads(attempt_path.read_text())['status'], 'request_started')
                    return good_response
                with patch.object(P.time, 'strftime', return_value='test_' + suffix), \
                     patch.object(P.time, 'time_ns', return_value=1), \
                     patch.object(LiveJ, 'request_api', side_effect=success_api):
                    macro = recorder.jev_choice(candidate)
                recorder.actions.close()
                reports = list(report_dir.glob('capture_choice_*.json'))
                self.assertEqual(len(reports), 1)
                report = json.loads(reports[0].read_text())
                self.assertEqual(report['status'], 'choice_recorded')
                self.assertEqual(report['usage']['input_tokens'], 30)
                persistent = json.loads(next(Calls.AUDIT_ROOT.glob('*.json')).read_text())
                self.assertEqual(persistent['status'], 'choice_recorded')
                self.assertEqual(persistent['usage']['input_tokens'], 30)
                self.assertEqual(macro[0]['key'], 'UP')
                action_event = json.loads(Path(recorder.actions.name).read_text().splitlines()[-1])
                self.assertEqual(action_event['report'], str(reports[0]))
                with patch.object(LiveJ, 'request_api') as duplicate_api:
                    with self.assertRaisesRegex(ValueError, 'already ran'):
                        recorder.jev_choice(candidate)
                    duplicate_api.assert_not_called()
                recorder.jev_requests.update(f'prior-{i}' for i in range(8))
                alternate = json.loads(candidate.read_text()); alternate['objective'] += ' with a distinct request'
                candidate.write_text(json.dumps(alternate))
                with patch.object(LiveJ, 'request_api') as capped_api:
                    with self.assertRaisesRegex(ValueError, 'limit reached'):
                        recorder.jev_choice(candidate)
                    capped_api.assert_not_called()

                failed, candidate2 = make_recorder(Path(temp) / 'failed')
                def failed_api(*_args):
                    attempt_path = report_dir / 'capture_choice_42_2.json'
                    self.assertEqual(json.loads(attempt_path.read_text())['status'], 'request_started')
                    raise RuntimeError('timeout')
                with patch.object(P.time, 'strftime', return_value='test_' + suffix), \
                     patch.object(P.time, 'time_ns', return_value=2), \
                     patch.object(LiveJ, 'request_api', side_effect=failed_api):
                    with self.assertRaisesRegex(RuntimeError, 'timeout'):
                        failed.jev_choice(candidate2)
                failed.actions.close()
                reports = sorted(report_dir.glob('capture_choice_*.json'))
                self.assertEqual(len(reports), 2)
                failed_report = next(json.loads(p.read_text()) for p in reports
                                     if json.loads(p.read_text())['status'] == 'api_or_response_error')
                self.assertEqual(failed_report['error_type'], 'RuntimeError')

                malformed, candidate3 = make_recorder(Path(temp) / 'malformed')
                response = {'model': 'jev-latest', 'usage': {'input_tokens': 31, 'output_tokens': 2},
                            'answers': {}}
                with patch.object(P.time, 'strftime', return_value='test_' + suffix), \
                     patch.object(P.time, 'time_ns', return_value=3), \
                     patch.object(LiveJ, 'request_api', return_value=response):
                    with self.assertRaises(J.JevError): malformed.jev_choice(candidate3)
                malformed.actions.close()
                reports = list(report_dir.glob('capture_choice_*.json'))
                malformed_report = next(json.loads(p.read_text()) for p in reports
                                         if json.loads(p.read_text()).get('frame') == 42
                                         and json.loads(p.read_text()).get('status') == 'api_or_response_error'
                                         and json.loads(p.read_text()).get('usage', {}).get('input_tokens') == 31)
                self.assertEqual(malformed_report['model'], 'jev-latest')
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)

    def test_rejected_event_links_attempt_report(self):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as temp:
            path = Path(temp) / 'actions.jsonl'
            recorder = object.__new__(P.Recorder)
            recorder.committed = 42; recorder.last_jev_report = 'temp/attempt.json'
            with path.open('w', encoding='utf-8') as stream:
                recorder.actions = stream
                recorder.record_jev_rejection(J.JevError('stale frame'))
            event = json.loads(path.read_text())
            self.assertEqual(event['status'], 'jev_rejected')
            self.assertEqual(event['report'], 'temp/attempt.json')


if __name__ == '__main__': unittest.main()
