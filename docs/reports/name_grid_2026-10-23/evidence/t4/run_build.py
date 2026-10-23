# T4: snapshot(tracked + T1~T3 uncommitted inputs) -> one full candidate build -> 5 gates. Parent/protected files are read-only.
import hashlib, json, os, pathlib, shutil, subprocess, sys, datetime
P = pathlib.Path('/Users/konest/project/aw-kor'); R = P / 'temp/name-grid-phaseB/namecompose-build'; S = R / 'source'
CAND = 'output/game_wars_korean_namecompose_20261023.gba'
EXPECTED_STATUS = sorted([
    ' M tools/build_korean_full.py', ' M tools/part2_native_controls.py', ' M tools/test_part2_native_controls.py',
    '?? data/jamo_glyphs_40.bin', '?? data/jamo_to_code_40.json', '?? tools/gen_jamo_assets.py', '?? tools/name_compose/',
    '?? tools/part2_name_compose_blob.py', '?? tools/test_jamo_assets.py', '?? tools/test_name_compose_core.py',
    '?? tools/test_part2_name_compose_build.py'])
EXCEPT2 = ('data/sprite_build_layouts.json', 'data/objlabel_sprites.json')
M = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'track': 'structural', 'commands': []}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(): (R / 'METADATA.json').write_text(json.dumps(M, ensure_ascii=False, indent=2) + '\n')
def run(args, cwd, env, name):
    with (R / name).open('a') as f:
        f.write('$ ' + ' '.join(map(str, args)) + '\n'); f.flush()
        rc = subprocess.run(list(map(str, args)), cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
        f.write('\nEXIT ' + str(rc) + '\n')
    M['commands'].append({'argv': list(map(str, args)), 'cwd': str(cwd), 'exit': rc, 'log': str(R / name)}); save()
    print(name, 'EXIT', rc, flush=True); return rc
def git(*a): return subprocess.check_output(['git', *a], cwd=P)
def status(): return sorted(l for l in git('status', '--porcelain=v1', '--untracked-files=normal').decode().splitlines() if l)
def inputs():
    tracked = [n for n in git('ls-files', '-z').decode().split('\0') if n]
    untracked = [n for n in git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0') if n]
    return {n: (sha(P / n) if (P / n).is_file() else None) for n in tracked + untracked}, untracked
def protected():
    paths = [P / 'original/Game Boy Wars Advance 1+2 (Japan).gba'] + sorted((P / 'output').glob('*.gba'))
    paths += [P / 'output' / ('game_wars_korean_' + x + '.gba') for x in ('full', 'final', 'title_test')]
    paths += sorted(p for p in (P / 'dist').rglob('*') if p.is_file())
    return {str(p.relative_to(P)): (sha(p) if p.is_file() else None) for p in paths}
try:
    assert not S.exists(), 'source already exists; preserve evidence'
    M['head'] = git('rev-parse', 'HEAD').decode().strip()
    assert M['head'] == '90908180938c2bf40ee38dea43c4c1304b09df8a', M['head']
    M['parent_status_before'] = status()
    assert M['parent_status_before'] == EXPECTED_STATUS, M['parent_status_before']
    M['parent_inputs_before'], M['untracked_inputs'] = inputs()
    M['protected_before'] = protected()
    pb = M['protected_before']
    assert pb['original/Game Boy Wars Advance 1+2 (Japan).gba'] == 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
    assert pb['output/game_wars_korean_namegrid_baseline_20261023.gba'] == 'ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a'
    assert pb['output/game_wars_korean_b44_reference_20261023.gba'] == '1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02'
    S.mkdir()
    for n, h in M['parent_inputs_before'].items():
        if h is None: continue
        d = S / n; d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(P / n, d)
    M['snapshot_manifest_before'] = {n: sha(S / n) for n, h in M['parent_inputs_before'].items() if h is not None}
    assert M['snapshot_manifest_before'] == {n: h for n, h in M['parent_inputs_before'].items() if h is not None}
    (R / 'snapshot_manifest.json').write_text(json.dumps({'head': M['head'], 'untracked_inputs': M['untracked_inputs'],
        'files': M['snapshot_manifest_before']}, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
    rom = 'original/Game Boy Wars Advance 1+2 (Japan).gba'
    (S / 'original').mkdir(exist_ok=True); shutil.copyfile(P / rom, S / rom); (S / rom).chmod(0o444)
    M['original_copy_sha256'] = sha(S / rom); assert M['original_copy_sha256'] == pb[rom]
    for d in ('temp', 'output', 'temp/tmp'): (S / d).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AW_FONT_DIR=str(P / 'temp/name-grid-phaseB/fonts'),
               AW_HADASANS_FONT='/Users/konest/project/hada-font/fonts/hada-sans/otf/HadaSans-Bold.otf',
               AW_HADASANS_BLACK_FONT='/Users/konest/project/hada-font/fonts/hada-sans/otf/HadaSans-Black.otf',
               TMPDIR=str(S / 'temp/tmp'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    M['font_env'] = {k: env[k] for k in ('AW_FONT_DIR', 'AW_HADASANS_FONT', 'AW_HADASANS_BLACK_FONT')}
    fonts = list(pathlib.Path(env['AW_FONT_DIR']).glob('*')) + [pathlib.Path(env[k]) for k in ('AW_HADASANS_FONT', 'AW_HADASANS_BLACK_FONT')]
    M['fonts_sha256'] = {str(p): sha(p) for p in fonts if p.is_file()}
    import PIL
    M['python'] = sys.executable + ' ' + sys.version; M['pillow'] = PIL.__version__
    M['except2_before'] = {n: M['snapshot_manifest_before'].get(n) for n in EXCEPT2}
    save()
    rc = run(['nice', '-n', '15', sys.executable, 'tools/build_korean_full.py', '--out', CAND, '--no-sync-outputs',
              '--report', 'temp/encode_report.csv'], S, env, 'build.log')
    M['build_exit'] = rc
    M['snapshot_manifest_after'] = {n: (sha(S / n) if (S / n).is_file() else None) for n in M['snapshot_manifest_before']}
    M['snapshot_changed'] = sorted(n for n in M['snapshot_manifest_before'] if M['snapshot_manifest_after'][n] != M['snapshot_manifest_before'][n])
    M['except2_after'] = {n: M['snapshot_manifest_after'].get(n) for n in EXCEPT2}
    M['snapshot_changed_outside_except2'] = [n for n in M['snapshot_changed'] if n not in EXCEPT2]
    if rc == 0:
        M['candidate_sha256'] = sha(S / CAND)
        M['build_artifacts'] = {n: sha(S / n) for n in ('temp/integrity_map.json', 'temp/repoint_manifest.json', 'temp/encode_report.csv')}
        save()
        gates = [['tools/phase6_basic_test.py', CAND],
                 ['tools/qa_integrity_map.py', '--rom', CAND, '--map', 'temp/integrity_map.json', '--byte-only'],
                 ['tools/qa_text_fit.py', '--rom', CAND, '--map', 'temp/integrity_map.json', '--manifest', 'temp/repoint_manifest.json'],
                 ['tools/qa_bteam_drift.py', '--rom', CAND, '--map', 'temp/integrity_map.json', '--repoint-manifest', 'temp/repoint_manifest.json', '--json', 'temp/candidate_bteam_details.json'],
                 ['tools/qa_part2_name_grid_shared_glyph.py', CAND]]
        M['gate_exits'] = [run([sys.executable] + g, S, env, 'gate%d.log' % i) for i, g in enumerate(gates, 1)]
        M['candidate_sha256_after_gates'] = sha(S / CAND)
        M['build_artifacts_after_gates'] = {n: sha(S / n) for n in M['build_artifacts']}
        dest = P / CAND
        assert not dest.exists() or sha(dest) == M['candidate_sha256'], 'existing candidate differs; do not overwrite'
        if not dest.exists(): shutil.copyfile(S / CAND, dest)
        M['published_candidate'] = str(dest); M['published_sha256'] = sha(dest)
except Exception as e:
    M['blocked'] = repr(e); print('BLOCKED:', repr(e), flush=True)
finally:
    after, _ = inputs()
    M['parent_inputs_unchanged'] = after == M.get('parent_inputs_before')
    M['parent_status_after'] = status(); M['parent_status_unchanged'] = M['parent_status_after'] == M.get('parent_status_before')
    pa = protected(); pa.pop(CAND, None); pb2 = dict(M.get('protected_before', {})); pb2.pop(CAND, None)
    M['protected_after'] = pa; M['protected_unchanged'] = pa == pb2
    M['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps({k: M.get(k) for k in ('blocked', 'build_exit', 'gate_exits', 'candidate_sha256', 'published_sha256', 'snapshot_changed',
          'parent_inputs_unchanged', 'parent_status_unchanged', 'protected_unchanged')}, ensure_ascii=False), flush=True)
