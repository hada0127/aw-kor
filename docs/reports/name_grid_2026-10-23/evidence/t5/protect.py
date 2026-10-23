"""Protected-file hashes before/after T5 (read only). usage: protect.py before|after"""
import hashlib,json,sys,subprocess,pathlib
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[2];B=R.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=set()
for pat in ['original/*.gba','output/*.gba','output/*.sav','dist/**/*']:paths.update(p for p in ROOT.glob(pat) if p.is_file())
for d in ['native-re','candidate-re','list-link-re','mode-scope-re','namecompose-build/analysis','b44-reference','t1-assets','t2-core','t3-builder']:
 paths.update(p for p in (B/d).rglob('*') if p.is_file() and p.suffix in ('.sav','.ss0','.json','.route','.py','.md','.gba'))
for f in ['tools/hangul_compose.py','tools/mgba_harness.c','tools/part2_name_compose_blob.py','data/jamo_to_code_40.json','data/jamo_glyphs_40.bin','data/syllable_to_code_2350.json','tools/build_korean_full.py']:paths.add(ROOT/f)
for f in ['mgbah','build/libmgba.0.10.5.dylib','run-single.sh']:paths.add(B/'official-mgba'/f)
res={'hashes':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},
 'git_head':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip(),
 'git_status':subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True).stdout,
 'git_diff_sha256':hashlib.sha256(subprocess.run(['git','diff'],cwd=ROOT,capture_output=True).stdout).hexdigest()}
out=R/f'protected-{sys.argv[1]}.json'
if sys.argv[1]=='before':assert not out.exists()
out.write_text(json.dumps(res,indent=1));print(sys.argv[1],len(res['hashes']),res['git_head'],res['git_diff_sha256'])
if sys.argv[1]=='after':
 b=json.loads((R/'protected-before.json').read_text())
 diff=[k for k in set(b['hashes'])|set(res['hashes']) if b['hashes'].get(k)!=res['hashes'].get(k)]
 same=not diff and b['git_head']==res['git_head'] and b['git_status']==res['git_status'] and b['git_diff_sha256']==res['git_diff_sha256']
 print('PROTECTED_UNCHANGED' if same else 'PROTECTED_CHANGED',diff[:20]);sys.exit(0 if same else 1)
