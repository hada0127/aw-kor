import json, sys, hashlib
b = json.load(open('analysis/textfit_baseline.json')); c = json.load(open('analysis/textfit_candidate.json'))
res = {}
for t in ('overflow', 'wider'):
    sb, sc = b[t]['set_with_multiplicity'], c[t]['set_with_multiplicity']
    res[t] = {'baseline_events': b[t]['events'], 'candidate_events': c[t]['events'], 'baseline_keys': len(sb), 'candidate_keys': len(sc),
              'new_keys': sorted(set(sc) - set(sb)), 'gone_keys': sorted(set(sb) - set(sc)),
              'multiplicity_changed': sorted(a for a in set(sb) & set(sc) if sb[a] != sc[a]),
              'printed_baseline': b['printed'][t], 'printed_candidate': c['printed'][t]}
key = lambda e: json.dumps([e['address'], e['type'], e['ko'], e['ja'], e['slot_override'], e['caller_line']], ensure_ascii=False)
res['full_event_lists_identical'] = sorted(map(key, b['events'])) == sorted(map(key, c['events']))
res['repeated_caller_lines'] = sorted({e['caller_line'] for e in b['events'] if e['type'] == 'overflow' and b['overflow']['repeated'].get(e['address'])})
res['input_sha256'] = {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in ('analysis/textfit_baseline.json', 'analysis/textfit_candidate.json')}
ok = all(not res[t]['new_keys'] and not res[t]['gone_keys'] and not res[t]['multiplicity_changed'] for t in ('overflow', 'wider')) and res['full_event_lists_identical']
res['pass'] = ok
json.dump(res, open('analysis/textfit_diff.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False)); sys.exit(0 if ok else 5)
