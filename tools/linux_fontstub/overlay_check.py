"""Prove overlay validity from build write traces (fontstub_build.py AW_TRACE_OUT).

1. Every byte where A (stub HEAD) != reference lies inside a write made by a
   font-using top-level patch call (font root) of A.
2. Every byte changed by A or B relative to the original ROM is covered by
   some traced write (no untraced writer hides a dependency).
3. Font-root write spans are identical in A and B (same assets, offsets,
   allocation) and no A!=B byte lies inside any font-root span of A or B.
4. A!=B bytes are attributed to non-font roots; listed per root.
"""
import bisect, collections, json, sys
A, B, REF, ORIG, TA, TB, OUT = sys.argv[1:8]
a = open(A, 'rb').read(); b = open(B, 'rb').read(); ref = open(REF, 'rb').read(); orig = open(ORIG, 'rb').read()
ta = json.load(open(TA)); tb = json.load(open(TB))


def diff(x, y):
    return [i for o in range(0, len(x), 4096) if x[o:o+4096] != y[o:o+4096]
            for i in range(o, min(o+4096, len(x))) if x[i] != y[i]]


def merged(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def index(trace, roots=None):
    iv = [tuple(x) for r, lst in trace['writes'].items() if roots is None or r in roots for x in lst]
    m = merged(iv)
    return m, [s for s, _ in m]


def inside(pos, idx):
    m, starts = idx
    j = bisect.bisect_right(starts, pos) - 1
    return j >= 0 and pos < m[j][1]


froots = set(ta['font_roots']) | set(tb['font_roots'])
fa, fb = index(ta, froots), index(tb, froots)
alla, allb = index(ta), index(tb)
d_ref = diff(a, ref); d_ab = diff(a, b)
res = {'font_roots': sorted(froots)}
res['A_vs_ref_bytes'] = len(d_ref)
res['A_vs_ref_outside_font_writes'] = [hex(i) for i in d_ref if not inside(i, fa)][:50]
ua = [i for i in diff(orig, a) if not inside(i, alla)]
ub = [i for i in diff(orig, b) if not inside(i, allb)]
res['untraced_changes_A'] = len(ua); res['untraced_changes_B'] = len(ub)
res['untraced_sample_A'] = [hex(i) for i in ua[:20]]
res['font_spans_equal_A_B'] = fa[0] == fb[0]
res['font_span_bytes'] = sum(e - s for s, e in fa[0])
res['A_vs_B_bytes'] = len(d_ab)
res['A_vs_B_inside_font_spans'] = [hex(i) for i in d_ab if inside(i, fa) or inside(i, fb)][:50]
res['A_vs_B_conflicts_with_ref'] = sum(1 for i in d_ab if a[i] != ref[i])
attr = collections.Counter()
nonfont = [('B', r, index({'writes': {r: l}})) for r, l in tb['writes'].items() if r not in froots]
nonfont += [('A', r, index({'writes': {r: l}})) for r, l in ta['writes'].items() if r not in froots]
for i in d_ab:
    owners = sorted({f'{side}:{r}' for side, r, idx in nonfont if inside(i, idx)})
    attr['+'.join(owners) if owners else 'UNATTRIBUTED'] += 1
res['A_vs_B_by_root_B'] = dict(attr.most_common())
ok = (not res['A_vs_ref_outside_font_writes'] and not ua and not ub and res['font_spans_equal_A_B']
      and not res['A_vs_B_inside_font_spans'] and res['A_vs_B_conflicts_with_ref'] == 0
      and 'UNATTRIBUTED' not in attr)
res['verdict'] = 'PASS' if ok else 'FAIL'
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'font_roots'}, indent=1)[:3000])
sys.exit(0 if ok else 1)
