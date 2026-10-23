import hashlib, json, pathlib, subprocess, sys
P = pathlib.Path('/Users/konest/project/aw-kor'); R = P / 'temp/name-grid-phaseB/namecompose-build'; S = R / 'source'
M = json.load(open(R / 'METADATA.json')); sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
git = lambda *a: subprocess.check_output(['git', *a], cwd=P).decode()
tracked = [n for n in git('ls-files', '-z').split('\0') if n]; untracked = [n for n in git('ls-files', '--others', '--exclude-standard', '-z').split('\0') if n]
now = {n: (sha(P / n) if (P / n).is_file() else None) for n in tracked + untracked}
status = sorted(l for l in git('status', '--porcelain=v1').splitlines() if l)
prot_paths = list(M['protected_before']) + ['output/game_wars_korean_namecompose_20261023.gba']
prot = {k: (sha(P / k) if (P / k).is_file() else None) for k in prot_paths}
snap = {n: sha(S / n) for n in M['snapshot_manifest_before']}
res = {'head': git('rev-parse', 'HEAD').strip(), 'parent_inputs_unchanged': now == M['parent_inputs_before'],
       'parent_status_unchanged': status == M['parent_status_before'], 'parent_status': status,
       'protected_unchanged': {k: v for k, v in prot.items() if k in M['protected_before']} == M['protected_before'],
       'protected': prot, 'snapshot_unchanged_since_build': snap == M['snapshot_manifest_before'],
       'candidate_parent_sha': prot['output/game_wars_korean_namecompose_20261023.gba'],
       'candidate_snapshot_sha': sha(S / 'output/game_wars_korean_namecompose_20261023.gba'),
       'snapshot_manifest_json_sha256': sha(R / 'snapshot_manifest.json'),
       'snapshot_files': len(M['snapshot_manifest_before'])}
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = res['parent_inputs_unchanged'] and res['parent_status_unchanged'] and res['protected_unchanged'] and res['snapshot_unchanged_since_build'] \
     and res['candidate_parent_sha'] == res['candidate_snapshot_sha'] == M['candidate_sha256']
print('FINAL', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 6)
