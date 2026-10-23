"""T5: compile the minimal r8-r11 BP-log copy with the official 0.10.5 compile-mgbah argv (only source/output paths differ)."""
import json,subprocess,hashlib,pathlib
H=pathlib.Path(__file__).resolve().parent;O=H.parents[1]/'official-mgba'
ref=[json.loads(l) for l in (O/'commands.jsonl').read_text().splitlines()]
argv=[c for c in ref if c['name']=='compile-mgbah'][0]['command']
src=str(H.parents[3]/'tools/mgba_harness.c');assert argv.count(src)==1
out=str(O/'mgbah');assert argv.count(out)==1
new=[str(H/'mgba_harness_t5.c') if a==src else str(H/'mgbah-t5') if a==out else a for a in argv]
defs=[a for a in new if a.startswith('-D')];assert len(defs)==len([a for a in argv if a.startswith('-D')])
p=subprocess.run(new,capture_output=True,text=True)
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
rec={'argv':new,'reference_argv':argv,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'defines':defs,'n_defines':len(defs),
 'source_sha256':sha(H/'mgba_harness_t5.c'),'original_source_sha256':sha(src),'binary_sha256':sha(H/'mgbah-t5') if p.returncode==0 else None,
 'library_sha256':sha(O/'build/libmgba.dylib'),'official_mgbah_sha256':sha(O/'mgbah')}
(H/'build.json').write_text(json.dumps(rec,indent=1));print(json.dumps({k:rec[k] for k in ['exit','n_defines','source_sha256','original_source_sha256','binary_sha256','library_sha256','stderr']},indent=1))
