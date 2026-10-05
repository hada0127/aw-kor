import json
from pathlib import Path
import sys
import tempfile
import unittest

from audit_character_voice import export_documents, attributed_speaker, text_hash
from localization_dependencies import ROOT, verified_checkout


class VoiceAdapterTests(unittest.TestCase):
    def test_unknown_speaker_is_not_guessed(self):
        self.assertIsNone(attributed_speaker('part1/g_1', 'わしじゃ', '나다', {}))

    def test_export_keeps_blank_target_and_explains_exclusions(self):
        groups = [{'group_id': 'g_1', 'region': 'part1', 'assembled_ja': 'わしじゃ', 'assembled_ko': ''},
                  {'group_id': 'noise', 'region': 'other'}]
        entries, families, excluded = export_documents(groups)
        self.assertEqual(entries, {'part1/g_1': ''})
        self.assertEqual(len(excluded), 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): export_documents(groups + groups[:1])

    def test_changed_text_invalidates_speaker_review(self):
        registry = {'part1/g_1': {'source_sha256': text_hash('わしじゃ'), 'target_sha256': text_hash('나다')}}
        with self.assertRaisesRegex(ValueError, 'Stale'):
            attributed_speaker('part1/g_1', 'わしじゃ', '새 번역', registry)

    def test_upstream_join_detects_edited_text_and_both_missing_row_directions(self):
        checkout = verified_checkout(); sys.path.insert(0, str(checkout))
        from hancharacter import manifest_adapter as adapter, measure
        for language in ('ja', 'ko'): self.assertEqual(measure.conformance(language), [])
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            tmp = Path(tmp); entries = {'part1/g_1': '나다'}
            manifest = {'entries': entries, 'digest': adapter.manifest_digest(entries), 'ruleset': 'test'}
            host = {'kind': 'hanpatch-host-rows', 'schemaVersion': 1,
                    'languages': {'evidence': 'ja', 'target': 'ko'},
                    'families': {'part1': [{'key': 'g_1', 'evidence': 'わしじゃ'}]}}
            (tmp / 'manifest.json').write_text(json.dumps(manifest))
            (tmp / 'rows.json').write_text(json.dumps(host))
            self.assertEqual(adapter.load_joined(tmp / 'manifest.json', tmp / 'rows.json')[0]['target'], '나다')
            manifest['entries']['part1/g_1'] = '변경'
            (tmp / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                adapter.load_joined(tmp / 'manifest.json', tmp / 'rows.json')
            manifest['digest'] = adapter.manifest_digest(manifest['entries'])
            for key in ('missing', None):
                host['families']['part1'] = [{'key': key, 'evidence': 'x'}] if key else []
                with self.assertRaises(ValueError): adapter.join(manifest, host)


if __name__ == '__main__': unittest.main()
