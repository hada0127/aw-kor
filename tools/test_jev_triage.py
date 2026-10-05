import json
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import jev_triage as J


class JevTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (J.ROOT / 'temp').mkdir(exist_ok=True)

    def rows(self, data):
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as directory:
            p = Path(directory) / 'input.json'
            p.write_text(json.dumps(data))
            return J.load_rows(p)

    def test_expected_labels_and_extra_fields_never_sent(self):
        rows = self.rows([{'id': 'a', 'ja': '禁止', 'ko': '금지',
                           'expected_error': False, 'secret_extra': 'excluded'}])
        payload = J.make_payload(rows, 'jev-latest')
        text = json.dumps(payload)
        self.assertNotIn('expected_error', text)
        self.assertNotIn('excluded', text)
        self.assertEqual(set(payload['questions']), {'a'})

    def test_limits_and_duplicate_ids(self):
        row = {'id': 'a', 'ja': '禁止', 'ko': '금지'}
        for data in ([], [row] * 9, [row, row], [{**row, 'ja': ''}],
                     [{**row, 'context': 'x' * 4001}], [{**row, 'id': '../bad'}]):
            with self.subTest(data=str(data)[:60]), self.assertRaises(J.JevError):
                self.rows(data)

    def test_probability_and_response_fail_closed(self):
        base = {'model': 'jev-latest', 'usage': {'input_tokens': 1, 'output_tokens': 2}}
        for value in (True, '0.1', math.nan, math.inf, -0.1, 1.1, None):
            with self.subTest(value=value), self.assertRaises(J.JevError):
                J.validate_response({**base, 'answers': {'a': {'type': 'noul', 'noul': value}}}, ['a'])
        for answers in ({}, {'b': {'type': 'noul', 'noul': .2}}, {'a': {'type': 'choice', 'noul': .2}}):
            with self.assertRaises(J.JevError):
                J.validate_response({**base, 'answers': answers}, ['a'])
        valid = {**base, 'answers': {'a': {'type': 'noul', 'noul': .2}}}
        self.assertEqual(J.validate_response(valid, ['a'])[0], {'a': .2})
        with self.assertRaises(J.JevError):
            J.validate_response({**valid, 'usage': {'input_tokens': True, 'output_tokens': 2}}, ['a'])

    def test_reports_cannot_overwrite_production_or_existing_files(self):
        with self.assertRaises(J.JevError):
            J.report_path(str(J.ROOT / 'data' / 'translation_for_import.csv'))
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as directory:
            p = Path(directory) / 'report.json'
            p.write_text('{}')
            with self.assertRaises(J.JevError):
                J.report_path(str(p))

    def test_redirect_never_forwards_credentials(self):
        with self.assertRaises(J.JevError):
            J.NoRedirect().redirect_request(None, None, 302, None, None, 'https://example.org')

    def test_no_key_and_key_in_content_fail_before_network(self):
        with patch.dict(J.os.environ, {}, clear=True), self.assertRaises(J.JevError):
            J.request_api('/v1/models')
        for secret in ('test-secret-value', 'test-secret-"-\\-value'):
            with patch.dict(J.os.environ, {'JEV_API_KEY': secret}), self.assertRaises(J.JevError):
                J.request_api('/v1/systemone', {'state': secret})

    def test_default_dry_run_has_no_network(self):
        fixture = J.ROOT / 'tools/fixtures/jev_semantic_smoke.json'
        with patch('sys.argv', ['jev_triage', '--input', str(fixture)]), \
             patch.object(J, 'request_api') as api, patch('builtins.print'):
            self.assertEqual(J.main(), 0)
            api.assert_not_called()

    def test_http_failure_is_sanitized_and_not_retried(self):
        secret = 'test-secret-value'
        failure = urllib.error.HTTPError('https://api.typesafe.ai', 401, secret, {}, io.BytesIO(b''))
        with patch.dict(J.os.environ, {'JEV_API_KEY': secret}), \
             patch.object(J.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = failure
            with self.assertRaises(J.JevError) as caught:
                J.request_api('/v1/models')
            self.assertNotIn(secret, str(caught.exception))
            self.assertIn('401', str(caught.exception))
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_live_writes_only_validated_report(self):
        fixture = J.ROOT / 'tools/fixtures/jev_semantic_smoke.json'
        answer = {'model': 'jev-latest', 'usage': {'input_tokens': 10, 'output_tokens': 8},
                  'answers': {r['id']: {'type': 'noul', 'noul': .5} for r in J.load_rows(fixture)}}
        with tempfile.TemporaryDirectory(dir=J.ROOT / 'temp') as directory:
            dest = Path(directory) / 'result.json'
            argv = ['jev_triage', '--input', str(fixture), '--live', '--output', str(dest)]
            with patch('sys.argv', argv), patch.object(J, 'request_api', return_value=answer) as api, \
                 patch('builtins.print'):
                self.assertEqual(J.main(), 0)
                self.assertEqual(api.call_count, 1)
            report = json.loads(dest.read_text())
            self.assertFalse(report['release_approval'])
            self.assertTrue(all(r['triage'] == 'uncertain_review' for r in report['results']))
            self.assertNotIn('ja', report)

    def test_wire_serialization_matches_report_hash_input(self):
        payload = {'state': '금지', 'questions': {'q': {'type': 'noul'}}, 'model': 'jev-latest'}
        with patch.dict(J.os.environ, {'JEV_API_KEY': 'test-secret-value'}), \
             patch.object(J.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{}'
            J.request_api('/v1/systemone', payload)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.data, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())

    def test_partial_http_response_fails_without_reflected_body(self):
        with patch.dict(J.os.environ, {'JEV_API_KEY': 'test-secret-value'}), \
             patch.object(J.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = J.http.client.IncompleteRead(b'test-secret-value')
            with self.assertRaises(J.JevError) as caught:
                J.request_api('/v1/models')
            self.assertNotIn('test-secret-value', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
