"""T7-FIX1 (read-only): current tree vs (a) T4 build-input snapshot manifest, (b) the Astra full-v1 review manifest.
Expected: vs T4 only the six T6-edited docs (already different at review time, equal to manifest-v1) + the F3 test file;
vs manifest-v1 only the F3 test file among production/tools/data/docs-outside-report paths."""
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
B = ROOT / 'temp/name-grid-phaseB'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
t4 = json.loads((B / 'namecompose-build/snapshot_manifest.json').read_text())
v1 = json.loads((B / 'final-review/manifest-v1.json').read_text())['files']
d4 = [r for r, h in sorted(t4['files'].items()) if not (ROOT / r).is_file() or sha(ROOT / r) != h]
d1 = [r for r, x in sorted(v1.items()) if not (ROOT / r).is_file() or sha(ROOT / r) != x['sha256']]
docs_eq_v1 = {r: (r in v1 and sha(ROOT / r) == v1[r]['sha256']) for r in d4 if r != 'tools/test_part2_name_compose_build.py'}
print('T4_SNAPSHOT_FILES', len(t4['files']), 'head', t4['head'])
print('DIFF_VS_T4', d4)
print('  of which equal to review manifest-v1 (pre-existing T6 doc edits):', docs_eq_v1)
print('MANIFEST_V1_FILES', len(v1))
print('DIFF_VS_MANIFEST_V1', d1)
ok = (all(docs_eq_v1.values()) and 'tools/test_part2_name_compose_build.py' in d4
      and all(r == 'tools/test_part2_name_compose_build.py' or r.startswith('docs/reports/name_grid_2026-10-23/') for r in d1))
print('EXPECTED_ONLY_F3_TEST_AND_OWNED_REPORT_FILES', ok)
sys.exit(0 if ok else 1)
