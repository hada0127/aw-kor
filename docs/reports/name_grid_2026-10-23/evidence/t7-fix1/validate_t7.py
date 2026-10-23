"""T7-FIX1 validation (read-only). Copy of t6-docs/validate.py; §5 compares against t7-fix1/sha-before.txt and allows only the F3 test file to change.
Run from repo root: python3 -B temp/name-grid-phaseB/t7-fix1/validate_t7.py"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

R = Path('docs/reports/name_grid_2026-10-23')
E = R / 'evidence'
DOCS = [R / 'PHASE_B_RE.md', R / 'PHASE_B_PLAN_APPROVAL.md', R / 'PHASE_B_QA.md', E / 'INDEX.md',
        Path('AGENTS.md'), Path('CLAUDE.md'), Path('todo.md'), Path('docs/success.md'), Path('docs/research.md'), Path('docs/fail.md')]
BANNED = ('.gba', '.sav', '.ss0', '.ss1', '.zip', '.gz', '.tar', '.ttf', '.otf', '.bdf', '.dylib')
errs = []
# mentioned on purpose as absent: missing ignored map (pre-existing failure) / planned QA tool not created
INTENTIONAL_ABSENT = {'data/dialogue_map.json', 'tools/qa_part2_name_compose.py'}

# 1. evidence integrity
idx = json.loads((E / 'index.json').read_text())['files']
on_disk = sorted(p.relative_to(E).as_posix() for p in E.rglob('*') if p.is_file() and p.name not in ('index.json', 'INDEX.md'))
listed = sorted(x['path'] for x in idx)
if on_disk != listed:
    errs.append(('evidence-set', set(on_disk) ^ set(listed)))
for x in idx:
    p = E / x['path']
    if hashlib.sha256(p.read_bytes()).hexdigest() != x['sha256'] or p.stat().st_size != x['bytes']:
        errs.append(('sha', x['path']))
    if p.name.lower().endswith(BANNED):
        errs.append(('banned', x['path']))
tot = sum(x['bytes'] for x in idx)
print('EVIDENCE files', len(idx), 'bytes', tot, 'max', max(x['bytes'] for x in idx))

# 2. relative links in docs (only lines added by this task for the big shared docs)
def added_lines(path):
    if path.parts[:3] == ('docs', 'reports', 'name_grid_2026-10-23'):
        return path.read_text().splitlines()
    out = subprocess.run(['git', 'diff', '-U0', '--', str(path)], capture_output=True, text=True).stdout
    return [l[1:] for l in out.splitlines() if l.startswith('+') and not l.startswith('+++')]
nlinks = 0
for d in DOCS:
    for line in added_lines(d):
        for m in re.finditer(r'\]\(<?([^)>\s]+)>?\)', line):
            t = m.group(1).split('#')[0]
            if not t or t.startswith(('http://', 'https://')):
                continue
            nlinks += 1
            if not (d.parent / t).exists():
                errs.append(('link', str(d), t))
        for m in re.finditer(r'`((?:docs|tools|data)/[^`*…\s]+)`', line):
            t = m.group(1).rstrip('/')
            if '{' in t or '<' in t:
                continue
            if not Path(t).exists() and t not in INTENTIONAL_ABSENT:
                errs.append(('path', str(d), t))
print('LINKS checked', nlinks)

# 3. abbreviated sha prefixes/suffixes must match a full 64-hex in the cited corpus
corpus = set()
for p in list(Path('temp/name-grid-phaseB').rglob('*.md')) + list(Path('temp/name-grid-phaseB').rglob('*.json')) + \
         list(Path('temp/name-grid-phaseB').rglob('*.log')) + list(Path('temp/name-grid-phaseB').rglob('*.txt')) + list(E.rglob('*')):
    if p.is_file() and p.stat().st_size < 3_000_000 and 'source' not in p.parts:
        try:
            corpus.update(re.findall(r'[0-9a-f]{64}', p.read_text(errors='ignore')))
        except Exception:
            pass
corpus.update(re.findall(r'[0-9a-f]{64}', Path('tools/part2_name_compose_blob.py').read_text()))
nab = 0
for d in DOCS:
    for line in added_lines(d):
        for m in re.finditer(r'\b([0-9a-f]{6,})…([0-9a-f]{3,})\b', line):
            a, b = m.groups()
            nab += 1
            if not any(h.startswith(a) and h.endswith(b) for h in corpus):
                errs.append(('abbrev-sha', str(d), f'{a}…{b}'))
        for h in re.findall(r'\b[0-9a-f]{64}\b', line):
            if h not in corpus:
                errs.append(('full-sha-unknown', str(d), h))
print('ABBREV SHA checked', nab)

# 4. git diff --check over tracked changes + new docs
r = subprocess.run(['git', 'diff', '--check'], capture_output=True, text=True)
print('GIT_DIFF_CHECK exit', r.returncode, r.stdout.strip()[:500])
if r.returncode:
    errs.append(('diff-check', r.stdout))
for d in DOCS[:4]:
    t = d.read_text()
    if re.search(r'[ \t]+$', t, re.M) or not t.endswith('\n'):
        errs.append(('ws', str(d)))

# 4b. whitespace: production files + newly authored prose must be clean; frozen evidence archive is reported, not suppressed
def nocheck(path):
    return subprocess.run(['git', 'diff', '--no-index', '--check', '/dev/null', path], capture_output=True, text=True).stdout.strip().splitlines()
files = [f.decode() for f in subprocess.run(['git', 'ls-files', '-z', '--others', '--exclude-standard'], capture_output=True).stdout.split(b'\0') if f]
ev_prefix = str(E) + '/'
prod_prose = [f for f in files if not f.startswith(ev_prefix)] + [str(E / 'INDEX.md'), str(E / 'index.json')]
prod_prose = sorted(set(prod_prose))
bad = {f: nocheck(f) for f in prod_prose}
bad = {f: v for f, v in bad.items() if v}
print('WS_PRODUCTION_AND_PROSE untracked', len(prod_prose), 'findings', len(bad))
errs += [('ws', f) for f in bad]
raw = {f: nocheck(f) for f in files if f.startswith(ev_prefix) and f not in (str(E / 'INDEX.md'), str(E / 'index.json'))}
raw = {f: v for f, v in raw.items() if v}
print('WS_RAW_EVIDENCE_ARCHIVE (reported, not fixed) files', len(raw))
for f, v in sorted(raw.items()):
    print('  ', f, 'check_output_lines', len(v), '|', v[0])
# 5. production files: only the F3 test file may differ from the T7-FIX1 start (sha-before.txt == T6 production-sha-before + 6 docs)
before = Path('temp/name-grid-phaseB/t7-fix1/sha-before.txt').read_text().splitlines()
now = subprocess.run(['shasum', '-a', '256'] + [l.split('  ', 1)[1] for l in before], capture_output=True, text=True).stdout.splitlines()
changed = sorted(b.split('  ', 1)[1] for b, n in zip(before, now) if b != n)
print('PRODUCTION_CHANGED', changed, 'rows', len(before), len(now))
if changed != ['tools/test_part2_name_compose_build.py'] or len(before) != len(now):
    errs.append(('production', changed))
dist_before = Path('temp/name-grid-phaseB/t7-fix1/dist-sha-before.txt').read_text().splitlines()
dist_now = subprocess.run(['shasum', '-a', '256'] + [l.split('  ', 1)[1] for l in dist_before], capture_output=True, text=True).stdout.splitlines()
print('DIST_UNCHANGED', dist_before == dist_now, len(dist_now))
if dist_before != dist_now:
    errs.append(('dist', set(dist_before) ^ set(dist_now)))

print('ERRORS', len(errs))
for e in errs:
    print(' ', e)
sys.exit(1 if errs else 0)
