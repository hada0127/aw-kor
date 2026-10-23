"""Final T5 aggregation: reads only produced evidence, prints per-case status, writes summary.json + evidence-manifest.json.
Exit 0 only if every required case (1-11, 13-15) passes and 12 passes or is BLOCKED with reason."""
import json, sys, subprocess, hashlib
from pathlib import Path
R = Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from t5lib import CAND, CAND_SHA, sha, parse_bp, HARNESS

def res(p):
    return json.loads((R / p).read_text())

def runs(prefix):
    return sorted(d for d in (R / 'runs').iterdir() if d.name.startswith(prefix) and (d / 'result.json').exists())

def all_pass(prefix):
    rs = [json.loads((d / 'result.json').read_text()) for d in runs(prefix)]
    return bool(rs) and all(r['pass'] for r in rs), [d.name for d in runs(prefix)]

def cmds(run):
    return [json.loads(l)['command'] for l in (R / 'runs' / run / 'commands.jsonl').read_text().splitlines()]

S = {}
def put(k, ok, ev, note=''):
    S[k] = {'status': 'PASS' if ok else 'FAIL', 'evidence': ev, 'note': note}

ok, ev = all_pass('case1-'); put('1', ok, ev, '한글/강철/붉은달 grid keys, per-step live==Composer, VRAM 64B ㄱ/ㅏ (ㅘ in case2)')
ok, ev = all_pass('case2-'); put('2', ok, ev, '한가, 닭+ㅏ→달가, V-only ㅗㅏ→ㅘ, reset ㅇㅗㅏ→와, 가한 via 갛')
ok, ev = all_pass('case3'); put('3', ok, ev)
ok, ev = all_pass('case4-'); put('4', ok, ev)
ok, ev = all_pass('case5-'); put('5', ok, ev)
c6 = [c for r in ['case11a-save', 'case11b-save'] for c in res(f'runs/{r}/result.json')['checks'] if c['name'].startswith('case6')]
put('6', len(c6) == 8 and all(c['ok'] for c in c6), ['case11a-save', 'case11b-save'], 'full8 typed twice (blank cart / overwrite), 17 accepted, 9th rejected, stored 16B')
ok, ev = all_pass('case7-'); put('7', ok, ev)
ok, ev = all_pass('case8'); put('8', ok, ev)
ok, ev = all_pass('case9'); put('9', ok, ev)
ok, ev = all_pass('case10'); put('10', ok, ev)
r11 = [res(f'runs/{r}/result.json') for r in ['case11a-save', 'case11a-cold', 'case11b-save', 'case11b-cold']]
nostate = all(not any(x.startswith(('loadstate', 'w8', 'w16')) for x in cmds(r)) for r in ['case11a-save', 'case11a-cold', 'case11b-save', 'case11b-cold'])
put('11', all(r['pass'] for r in r11) and nostate, ['case11a-save', 'case11a-cold', 'case11b-save', 'case11b-cold'], 'power-on normal keys only; separate cold processes')
r12 = res('case12-result.json')
put('12', r12['pass_automatic'] and not any(x.startswith(('loadstate', 'w8', 'w16')) for x in cmds('case12-build') + cmds('case12-cold-versus')),
    ['case12-build', 'case12-cold-versus', 'case12-result.json'], 'automatic: name kept in valid-map save + A3 copies of all 8 syllables on category5; visual: valid-map.png, category5.png, selected.png (TEAM SETTING) checked by worker')
ok13a, ev13a = all_pass('case13')
put('13', ok13a, ev13a, 'Korean/jamo active: dakuten/handakuten/R -> sound 68, live unchanged; legacy カ: dakuten/R/handakuten == original ROM')
r14 = res('runs/case14-original/result.json'); put('14', r14['pass'], ['case14-original'])
c15 = res('case15-contracts.json'); rs = res('case15-rowseq.json')
m0 = res('runs/case15-mode0-SYNTHETIC/notes.json'); m1 = res('runs/case15-mode1/notes.json')
bn = res('runs/case15-baseline-native/result.json')
tot = c15['totals']
need = ['S1/mode1/c_ret0', 'S1/mode1/c_ret1', 'S2/mode1/c_ret0', 'S2/mode1/c_ret1', 'S3/mode1/c_ret0', 'D1/mode1', 'D1/mode0', 'S1/mode0', 'S2/mode0', 'S3/mode0', 'P1/modeNone']
w = c15['runs']['case15-mode1']['stack_watch']
stores = [x for x in w if x['pc'].startswith('08f75') and x['addr'] in ('03007d28', '03007d2c')]
reads = [x for x in w if x['pc'] in ('08314ec6', '08314ec8')][:12]
stack_ok = (len([x for x in stores if x['addr'] == '03007d28' and x['new'] == '00008000']) >= 6 and len([x for x in stores if x['addr'] == '03007d2c' and x['new'] == '00000000']) >= 6
            and len(reads) == 12 and all((x['addr'] == '03007d28' and x['old'] == '00008000') or (x['addr'] == '03007d2c' and x['old'] == '00000000') for x in reads))
d1 = c15['runs']['case15-mode1']['d1_events'][0]
p1 = [e for r in ['case15-pending'] for e in []]
ok15 = (not c15['errors'] and all(k in tot for k in need) and rs['mode0_equals_baseline'] and rs['mode1_uses_private_rows'] and m0['native_like'] and m1['mode1_like']
        and bn['live'] == '8341000000000000' and bn['bp_path'] == ['S1', 'sound', 'AE00_append', 'RET_B0C6'] and stack_ok and d1.get('rowdraw_sp') == '03007d28')
put('15', ok15, ['case15-contracts.json', 'case15-rowseq.json', 'case15-pending', 'case15-mode1', 'case15-mode0-SYNTHETIC', 'case15-baseline-native'],
    f'contract errors {len(c15["errors"])}; totals {tot}; rowdraw stack args via rw watch {stack_ok}; mode0 is SYNTHETIC (w8 obj+0x60:=0 in pending state)')

# hygiene
led = [json.loads(l) for l in (R / 'processes.jsonl').read_text().splitlines()]
starts = {(x['tag'], x['pid']) for x in led if x['event'] == 'start'}
ends = {(x['tag'], x['pid']): x.get('exit') for x in led if x['event'] == 'end'}
unended = [s for s in starts if s not in ends]
live = subprocess.run(['pgrep', '-f', str(HARNESS)], capture_output=True, text=True).stdout.split()
loads = sorted({x.split(' ', 1)[1] for d in (R / 'runs').iterdir() if (d / 'commands.jsonl').exists() for x in cmds(d.name) if x.startswith('loadstate')})
writes = sorted({(d.name, x) for d in (R / 'runs').iterdir() if (d / 'commands.jsonl').exists() for x in cmds(d.name) if x.startswith(('w8', 'w16'))})
hyg = {'candidate_sha_now': sha(CAND), 'candidate_sha_ok': sha(CAND) == CAND_SHA, 'unended_processes': unended, 'live_harness_pids': live,
       'nonzero_exits': {f'{k[0]}:{k[1]}': v for k, v in ends.items() if v not in (0,)},
       'loadstate_sources': loads, 'loadstate_all_t5_owned': all(p.startswith(str(R)) for p in loads), 'ram_writes': writes,
       'ram_writes_only_synthetic_mode0': all(r[0] == 'case15-mode0-SYNTHETIC' for r in writes),
       'leftover_probe_saves': [str(p) for p in (R / 'runs').rglob('mgbah_probe_save_*')]}
hyg_ok = hyg['candidate_sha_ok'] and not hyg['unended_processes'] and not hyg['live_harness_pids'] and hyg['loadstate_all_t5_owned'] and hyg['ram_writes_only_synthetic_mode0'] and not hyg['leftover_probe_saves']

summary = {'candidate': str(CAND), 'candidate_sha256': CAND_SHA, 'cases': S, 'hygiene': hyg, 'hygiene_ok': hyg_ok,
           'harness': json.loads((R / 'harness/build.json').read_text()) | {'stdout': None}}
(R / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
for k in sorted(S, key=int):
    print(f'case {k:>2}: {S[k]["status"]}  {S[k]["note"][:110]}')
print('hygiene', 'OK' if hyg_ok else 'FAIL', {k: v for k, v in hyg.items() if k not in ('loadstate_sources',)})

# minimal evidence list for T6 (paths relative to repo root + sha256)
ROOT = R.parents[2]
keep = ['t5lib.py', 'cases.py', 'case11.py', 'case12.py', 'case14.py', 'case15.py', 'case15_rowseq.py', 'case15_mode0_vs_baseline.py', 'verify.py', 'protect.py', 'prep_fresh.py', 'prep_legacy.py', 'explore.py',
        'expectations.json', 'summary.json', 'case12-result.json', 'case15-contracts.json', 'case15-rowseq.json', 'processes.jsonl', 'REPORT.md',
        'harness/harness.diff', 'harness/build.json', 'harness/build.py', 'harness/mgba_harness_t5.c', 'harness/flags_make_defines.txt',
        'routes/candidate-fresh-to-name.route', 'routes/legacy-cold-to-name.route', 'routes/legacy-cold-to-editor.route', 'routes/fresh3-keys.route',
        'protected-before.json', 'protected-after.json']
for run, files in {
    'case1-강철': ['result.json', 'steps.jsonl', 'preview.png', 'vram-ㄱ.bin'], 'case1-vowel': ['result.json', 'vram-ㅏ.bin', 'preview-a.png'],
    'case2-wa-vonly': ['result.json', 'vram-ㅘ.bin', 'preview.png'], 'case6': [],
    'case11a-save': ['result.json', 'steps.jsonl', 'commands.jsonl', 'full8.png', 'sv-confirm.png', 'sv-done.png', 'confirm-destination.bin', 'bp.log', 'launch.json', 'exit.json'],
    'case11a-cold': ['result.json', 'commands.jsonl', 'cold-list.png', 'reentry.png', 'reentry-obj.bin', 'list-name-0200B204.bin', 'launch.json', 'exit.json'],
    'case11b-save': ['result.json', 'commands.jsonl', 'sv-confirm.png', 'sv-yes-selected.png', 'confirm-destination.bin', 'launch.json', 'exit.json'],
    'case11b-cold': ['result.json', 'commands.jsonl', 'cold-list.png', 'reentry.png', 'reentry-obj.bin', 'launch.json', 'exit.json'],
    'case12-build': ['valid-map.png', 'commands.jsonl', 'launch.json'], 'case12-cold-versus': ['category5.png', 'selected.png', 'commands.jsonl', 'launch.json'],
    'case13': ['result.json', 'steps.jsonl'], 'case13b-candidate-legacy-kana': ['result.json', 'cand-dakuten.png'], 'case14-original': ['result.json', 'one-a.png', 'orig-dakuten.png', 'launch.json'],
    'case15-mode1': ['bp.log', 'notes.json'], 'case15-mode0-SYNTHETIC': ['bp.log', 'notes.json', 'after-a.png'], 'case15-baseline-native': ['result.json', 'after-a.png'],
    'case15-pending': ['bp.log'], 'prep-fresh': ['name-entry.png', 'bp.log', 'commands.jsonl'], 'prep-legacy': ['reentry.png', 'commands.jsonl'],
}.items():
    keep += [f'runs/{run}/{f}' for f in files]
man = []
for k in keep:
    p = R / k
    if p.exists():
        man.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size})
    else:
        man.append({'path': str(p.relative_to(ROOT)), 'missing': True})
(R / 'evidence-manifest.json').write_text(json.dumps({'note': 'minimal T5 evidence for T6 docs/reports/.../evidence/ (no ROM, no cartridge saves). Save files are listed in summary only by sha256.', 'files': man}, ensure_ascii=False, indent=1))
required = [k for k in S if k != '12']
final = all(S[k]['status'] == 'PASS' for k in required) and S['12']['status'] == 'PASS' and hyg_ok
print('T5_RESULT', 'PASS' if final else 'FAIL', 'missing evidence:', [m['path'] for m in man if m.get('missing')])
sys.exit(0 if final else 1)
