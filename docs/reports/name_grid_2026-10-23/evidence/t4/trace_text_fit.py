# One process per source root. Observes qa_text_fit.main's local check_text(a, ko, ja, slot_override) call/return
# with a local tracer (line events off) and records which call incremented overflow / wider. No classification copy.
import contextlib, io, json, os, re, sys
src, rom, imap, manifest, out = sys.argv[1:6]
src = os.path.realpath(src); tools = os.path.join(src, 'tools')
os.chdir(src); sys.dont_write_bytecode = True; sys.path.insert(0, tools)
import qa_text_fit as Q
qfile = os.path.realpath(Q.__file__)
assert qfile == os.path.join(tools, 'qa_text_fit.py'), qfile
leak = sorted({os.path.realpath(getattr(m, '__file__', '') or '') for n, m in list(sys.modules.items())
               if n != '__main__' and getattr(m, '__file__', None) and '/temp/name-grid-phaseB/' in os.path.realpath(m.__file__)
               and not os.path.realpath(m.__file__).startswith(src + os.sep)})
events, calls, entry, caller = [], [0], {}, {}
def local(frame, event, arg):
    if event == 'return':
        a, ko, ja, so, ov, wd = entry.pop(id(frame)); line = caller.pop(id(frame))
        loc = frame.f_locals
        dov, dwd = loc['overflow'] - ov, loc['wider'] - wd
        assert dov in (0, 1) and dwd in (0, 1) and not (dov and dwd), (a, dov, dwd)
        if dov: events.append({'address': a, 'type': 'overflow', 'ko': ko, 'ja': ja, 'slot_override': so, 'caller_line': line})
        if dwd: events.append({'address': a, 'type': 'wider', 'ko': ko, 'ja': ja, 'slot_override': so, 'caller_line': line})
    return local
def glob(frame, event, arg):
    co = frame.f_code
    if event == 'call' and co.co_name == 'check_text' and co.co_filename == Q.__file__:
        loc = frame.f_locals; calls[0] += 1
        entry[id(frame)] = (loc['a'], loc['ko'], loc['ja'], loc['slot_override'], loc['overflow'], loc['wider'])
        caller[id(frame)] = frame.f_back.f_lineno
        frame.f_trace_lines = False
        return local
    return None
buf = io.StringIO()
sys.settrace(glob)
try:
    with contextlib.redirect_stdout(buf):
        rc = Q.main(['--rom', rom, '--map', imap, '--manifest', manifest])
finally:
    sys.settrace(None)
text = buf.getvalue()
printed = {'overflow': int(re.search(r'overflow\(슬롯초과 skip→원문\): (\d+)', text).group(1)),
           'wider': int(re.search(r'visual-wider than JA: (\d+)', text).group(1))}
res = {'source': src, 'qa_text_fit': qfile, 'foreign_modules': leak, 'main_return': rc, 'check_text_calls': calls[0],
       'unreturned': len(entry), 'printed': printed, 'stdout': text}
for t in ('overflow', 'wider'):
    ev = [e for e in events if e['type'] == t]
    mult = {}
    for e in ev: mult['0x%06X' % e['address']] = mult.get('0x%06X' % e['address'], 0) + 1
    # (address, type) set with occurrence count: qa_text_fit counts repeated identical calls for one address.
    res[t] = {'events': len(ev), 'unique_addresses': len(mult), 'set_with_multiplicity': dict(sorted(mult.items())),
              'repeated': {a: n for a, n in sorted(mult.items()) if n > 1},
              'count_matches_printed': len(ev) == printed[t] and sum(mult.values()) == printed[t]}
res['events'] = [dict(e, address='0x%06X' % e['address']) for e in events]
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ('source', 'main_return', 'check_text_calls', 'unreturned', 'printed', 'foreign_modules')}, ensure_ascii=False))
for t in ('overflow', 'wider'): print(t, {k: v for k, v in res[t].items() if k != "set_with_multiplicity"})
sys.exit(0 if all(res[t]['count_matches_printed'] for t in ('overflow', 'wider')) and not leak and not entry else 3)
