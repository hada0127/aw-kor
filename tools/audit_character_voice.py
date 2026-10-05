#!/usr/bin/env python3
"""Read-only hancharacter adapter for AW's editor snapshot, not a ROM verdict.

Unknown attribution, unmeasurable axes and absent contracts are explicit. No
text is rewritten; no model/service is called; no voice-density pass is invented.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from localization_dependencies import ROOT, specification, verified_checkout
from localization_evidence import sha, write_json


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def export_documents(groups):
    families = {}
    entries = {}
    excluded = []
    for group in groups:
        key = group['group_id']
        if group.get('region') not in ('part1', 'part2', 'campaign') or group.get('flagged'):
            excluded.append({'group_id': key, 'reason': 'outside dialogue region or flagged extraction'})
            continue
        source = group.get('assembled_ja')
        target = group.get('assembled_ko')
        if not isinstance(source, str) or not source or not isinstance(target, str):
            raise ValueError(f'Missing source/target snapshot for {key}')
        family = group['region']
        full = f'{family}/{key}'
        if full in entries or '\0' in source or '\0' in target:
            raise ValueError(f'Duplicate key or NUL in text: {full}')
        entries[full] = target
        families.setdefault(family, []).append({'key': key, 'evidence': source, 'pivot': source})
    return entries, families, excluded


def attributed_speaker(key, source, target, registry, root=ROOT):
    entry = registry.get(key)
    if entry is None:
        return None
    if entry.get('source_sha256') != text_hash(source) or entry.get('target_sha256') != text_hash(target):
        raise ValueError(f'Stale speaker attribution: {key}')
    speaker = entry.get('speaker')
    if not isinstance(speaker, str) or not speaker.isidentifier() or speaker in ('unattributed', 'close'):
        raise ValueError(f'Invalid speaker ID: {key}')
    if entry.get('review_status') != 'reviewed':
        raise ValueError(f'Unreviewed speaker attribution: {key}')
    evidence = (root / entry['evidence_path']).resolve()
    if not evidence.is_relative_to(root.resolve()) or sha(evidence) != entry.get('evidence_sha256'):
        raise ValueError(f'Speaker evidence mismatch: {key}')
    return speaker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups', type=Path, default=ROOT / 'data/dialogue_groups.json')
    parser.add_argument('--attribution', type=Path, default=ROOT / 'data/character_attribution.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    checkout = verified_checkout()
    sys.path.insert(0, str(checkout))
    from hancharacter import measure, manifest_adapter
    conformance = {lang: [str(f) for f in measure.conformance(lang)] for lang in ('ja', 'ko')}
    if any(conformance.values()):
        raise ValueError(f'Upstream measurement conformance failed: {conformance}')
    groups_bytes = args.groups.read_bytes()
    attribution_bytes = args.attribution.read_bytes()
    groups = json.loads(groups_bytes)['groups']
    attribution_doc = json.loads(attribution_bytes)
    if attribution_doc.get('schema') != 1:
        raise ValueError('Unsupported attribution schema')
    registry = attribution_doc['groups']
    entries, families, excluded = export_documents(groups)
    seal = manifest_adapter.manifest_digest(entries)
    manifest = {'ruleset': 'aw-editor-snapshot-1', 'digest': seal, 'entries': entries,
                'basis': 'editor snapshot only; not ROM readback or release authority'}
    host = {'kind': 'hanpatch-host-rows', 'schemaVersion': 1,
            'languages': {'evidence': 'ja', 'pivot': 'ja', 'target': 'ko'},
            'manifestDigest': seal, 'families': families}
    args.out.mkdir(parents=True, exist_ok=False)
    write_json(args.out / 'manifest.json', manifest)
    write_json(args.out / 'host_rows.json', host)
    joined = manifest_adapter.load_joined(args.out / 'manifest.json', args.out / 'host_rows.json',
                                         expected_ruleset='aw-editor-snapshot-1')
    if set(registry) - {row['row_key'] for row in joined}:
        raise ValueError('Attribution contains a row absent from the exported snapshot')
    speakers = {}
    for row in joined:
        speakers[row['row_key']] = attributed_speaker(row['row_key'], row['evidence'], row['target'], registry)
    probes = []
    for row in joined:
        key = row['row_key']
        source, target = row['evidence'], row['target']
        matches = {lang: [axis for axis in measure.measurable_axes(lang)
                           if measure.get_plugin(lang).match(text, axis, None)]
                   for lang, text in [('ja', source), ('ko', target)]}
        if any(matches.values()):
            probes.append({'key': key, 'speaker': speakers[key], 'fragment_marker_candidates': matches,
                           'source': source, 'target': target,
                           'note': 'Heuristic candidates, not a voice loss/invention verdict'})
    segmentation = {'status': 'NOT_RUN', 'eligible_voice_units': None,
                    'reason': 'GBA speaker/control segmentation and reviewed voice contracts are not established'}
    if args.groups.read_bytes() != groups_bytes or args.attribution.read_bytes() != attribution_bytes:
        raise ValueError('Voice inputs changed during audit')
    verified_checkout()
    report = {'status': 'report_only_no_sealed_contract', 'upstream': specification(),
              'input_sha256': {'groups': hashlib.sha256(groups_bytes).hexdigest(),
                               'attribution': hashlib.sha256(attribution_bytes).hexdigest()},
              'languages': host['languages'], 'manifest_digest': seal,
              'total_groups': len(groups), 'exported_groups': len(joined), 'excluded_groups': excluded,
              'attributed_groups': sum(s is not None for s in speakers.values()),
              'unknown_speaker_groups': sum(s is None for s in speakers.values()),
              'segmentation': segmentation, 'plugin_conformance': conformance,
              'marker_candidates': probes,
              'limits': ['Editor snapshot, not final ROM text', 'No speaker is inferred',
                         'No sealed voice contracts; no density/LOSS/INVENTION pass',
                         'Extraction groups and regions are not a complete game population proof']}
    write_json(args.out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'total_groups', 'exported_groups',
                                           'attributed_groups', 'unknown_speaker_groups')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
