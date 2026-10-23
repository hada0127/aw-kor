"""T7-FIX1: targeted update of docs/reports/name_grid_2026-10-23/evidence (run from repo root, once).
- archives the pre-F1 T5 files under t5/superseded-case13/ (byte-identical to what index.json listed before; sha asserted)
- replaces the 8 T5 files whose temp source changed (case13 rerun, case15 analyze, verify, REPORT correction)
- adds case13 BP/command/launch/exit evidence, new T5 logs, and the t7-fix1 group
- rewrites index.json (other rows untouched). INDEX.md is written by make_index_t7.py."""
import hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
B = ROOT / 'temp/name-grid-phaseB'
E = ROOT / 'docs/reports/name_grid_2026-10-23/evidence'
F = B / 't7-fix1'
BANNED = ('.gba', '.sav', '.ss0', '.ss1', '.zip', '.gz', '.tar', '.ttf', '.otf', '.bdf', '.dylib')
SUP_RUN = 't5-runtime/runs-superseded/case13-1792750756'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

doc = json.loads((E / 'index.json').read_text())
idx = doc['files']
if sys.argv[1:] == ['--refresh-t7']:
    # re-copy only rows of the t7-fix1 group / superseded README whose temp source changed after the first apply
    n = 0
    for x in idx:
        if x['group'] == 't7-fix1' or x['path'] == 't5/superseded-case13/README.md':
            src = ROOT / x['source']
            if sha(src) != x['sha256']:
                shutil.copyfile(src, E / x['path'])
                x['sha256'], x['bytes'] = sha(E / x['path']), (E / x['path']).stat().st_size
                assert x['sha256'] == sha(src)
                n += 1
                print('refreshed', x['path'])
    (E / 'index.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    print('refresh rows', n)
    sys.exit(0)
by = {x['path']: x for x in idx}
assert len(idx) == 282 and not (E / 't5/superseded-case13').exists(), 'already applied?'

# 1. archive (old evidence path -> superseded path, source = where the identical bytes still live in temp)
ARCH = [('t5/cases.py', 't7-fix1/pre-fix/cases.py'),
        ('t5/runs/case13/result.json', f'{SUP_RUN}/result.json'),
        ('t5/runs/case13/steps.jsonl', f'{SUP_RUN}/steps.jsonl'),
        ('t5/summary.json', 't7-fix1/pre-fix/t5/summary.json'),
        ('t5/case15-contracts.json', 't7-fix1/pre-fix/t5/case15-contracts.json'),
        ('t5/evidence-manifest.json', 't7-fix1/pre-fix/t5/evidence-manifest.json'),
        ('t5/REPORT.md', 't7-fix1/pre-fix/t5/REPORT.md'),
        ('t5/t6-verify-rerun.log', 't6-docs/t5-verify.log')]
new_rows = []
for old, src_rel in ARCH:
    x = by[old]
    src = B / src_rel
    assert sha(src) == x['sha256'] == sha(E / old), (old, src_rel)
    rel = old.replace('t5/', 't5/superseded-case13/', 1)
    dst = E / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(E / old, dst)
    assert sha(dst) == x['sha256']
    new_rows.append({'group': 't5-superseded', 'path': rel, 'source': f'temp/name-grid-phaseB/{src_rel}', 'sha256': x['sha256'], 'bytes': x['bytes']})
# the T6 verify log moves (its current-path claim "case 13 PASS" relied on the 각 steps); the rest are replaced below
(E / 't5/t6-verify-rerun.log').unlink()
idx = [x for x in idx if x['path'] != 't5/t6-verify-rerun.log']

# 2. replace changed T5 files from their (unchanged-path) temp source
CHANGED = ['t5/cases.py', 't5/runs/case13/result.json', 't5/runs/case13/steps.jsonl', 't5/summary.json',
           't5/case15-contracts.json', 't5/evidence-manifest.json', 't5/REPORT.md', 't5/processes.jsonl']
for x in idx:
    if x['path'] in CHANGED:
        src = ROOT / x['source']
        shutil.copyfile(src, E / x['path'])
        x['sha256'], x['bytes'] = sha(E / x['path']), (E / x['path']).stat().st_size
        assert x['sha256'] == sha(src)
    elif x['path'].startswith('t5/'):
        assert sha(ROOT / x['source']) == x['sha256'], ('unexpected temp change', x['path'])

# 3. additions
ADD = [('t5', f't5-runtime/runs/case13/{f}', f't5/runs/case13/{f}') for f in ('bp.log', 'commands.jsonl', 'launch.json', 'exit.json')]
listed = {x['source'] for x in idx}
ADD += [('t5', f't5-runtime/logs/{p.name}', f't5/logs/{p.name}') for p in sorted((B / 't5-runtime/logs').iterdir())
        if p.is_file() and f'temp/name-grid-phaseB/t5-runtime/logs/{p.name}' not in listed]
T7 = ['REPORT.md', 'test_part2_name_compose_build.stdout.log', 'test_part2_name_compose_build.stderr.log',
      'test_part2_name_compose_build.exit.txt', 'test_part2_name_compose_build.env.txt',
      'audit_tmp.py', 'audit_tmp.stdout.log', 'audit_tmp.stderr.log', 'audit_tmp.exit.txt',
      'test_part2_name_compose_build.t3-to-fix1.diff', 'cases.py.fix1.diff',
      'compare_t4_snapshot.py', 'compare_t4_snapshot.log', 'sha-before.txt', 'sha-after.txt',
      'update_evidence.py', 'make_index_t7.py', 'validate_t7.py']
ADD += [('t5-superseded', 't7-fix1/superseded-case13-README.md', 't5/superseded-case13/README.md')]
ADD += [('t7-fix1', f't7-fix1/{f}', f't7-fix1/{f}') for f in T7]
for g, src_rel, dst_rel in ADD:
    src = B / src_rel
    assert src.is_file() and not src.name.lower().endswith(BANNED), src
    assert dst_rel not in {x['path'] for x in idx + new_rows}, dst_rel
    dst = E / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    assert sha(src) == sha(dst)
    new_rows.append({'group': g, 'path': dst_rel, 'source': f'temp/name-grid-phaseB/{src_rel}', 'sha256': sha(dst), 'bytes': dst.stat().st_size})

idx += new_rows
order = ['plan', 'research', 't1', 't2', 't3', 't4', 't5', 't5-superseded', 't7-fix1']
idx.sort(key=lambda x: order.index(x['group']))  # stable: keeps the original row order inside a group
doc['files'] = idx
doc['note'] += ' T7-FIX1 (2026-10-23): pre-F1 T5 files archived under t5/superseded-case13/ (invalid as incomplete-jamo coverage), see t7-fix1/REPORT.md.'
(E / 'index.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
print('index rows', len(idx), 'added', len(new_rows), 'replaced', len(CHANGED), 'moved 1 (t6-verify-rerun.log)')
