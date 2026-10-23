# T4 static analysis: candidate vs baseline diff whitelist + payload, A3 jamo lookup, shared native glyphs,
# one-off writer/manifest cross-check, B-team set diff. Reads only; writes analysis/*.json in this folder.
import ast, hashlib, json, os, struct, sys, collections, unicodedata
P = '/Users/konest/project/aw-kor'; PH = P + '/temp/name-grid-phaseB'; R = PH + '/namecompose-build'; S = R + '/source'
BS = PH + '/baseline-build/source'
sys.dont_write_bytecode = True; sys.path.insert(0, S + '/tools'); os.chdir(S)
OUT = R + '/analysis'; os.makedirs(OUT, exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def rd(p): return open(p, 'rb').read()
def dump(name, obj): json.dump(obj, open(f'{OUT}/{name}', 'w'), ensure_ascii=False, indent=1)
orig = rd(S + '/original/Game Boy Wars Advance 1+2 (Japan).gba')
base = rd(P + '/output/game_wars_korean_namegrid_baseline_20261023.gba')
cand = rd(S + '/output/game_wars_korean_namecompose_20261023.gba')
assert sha(base) == 'ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a'
import build_korean_full as B, part2_name_compose_blob as blob, gen_jamo_assets as jamo
assert os.path.realpath(B.__file__).startswith(S) and os.path.realpath(blob.__file__).startswith(S)
summary = {'candidate_sha256': sha(cand), 'baseline_sha256': sha(base), 'original_sha256': sha(orig)}
U32 = lambda rom, o: struct.unpack_from('<I', rom, o)[0]

# ---- 1. diff whitelist + payload ----
writes = [(n, s, e) for n, s, e in B.NAME_COMPOSE_WRITES]
lits = list(B.NAME_COMPOSE_END_LITERALS)
allowed = [(n, s, e) for n, s, e in writes] + [(f'end_literal_0x{l:X}', l, l + 4) for l in lits]
diff = [i for i in range(len(cand)) if cand[i] != base[i]] if len(cand) == len(base) else None
def owner(i): return [n for n, s, e in allowed if s <= i < e]
outside = [i for i in diff if not owner(i)]
runs = []
for i in diff:
    if runs and i == runs[-1][1]: runs[-1][1] = i + 1
    else: runs.append([i, i + 1])
syl_to_code = {s: int(c, 16) for s, c in json.load(open(S + '/data/syllable_to_code_2350.json', encoding='utf-8')).items()}
codes = {k: int(v, 16) for k, v in json.load(open(S + '/data/jamo_to_code_40.json', encoding='utf-8')).items()}
assert list(codes) == list(jamo.load_jamo_codes())
ent = lambda n: blob.IMAGE_RT + blob.SYMBOLS[n] | 1
assert sha(blob.CODE) == blob.CODE_SHA and len(blob.CODE) <= 0x2000
dense = bytearray(22344)
for s, c in syl_to_code.items():
    struct.pack_into('<H', dense, (ord(s) - 0xAC00) * 2, c)
tail = b''.join(bytes([c >> 8, c & 255]) + struct.pack('<HH', (1275 + 2 * i) | 0x8000, (1276 + 2 * i) | 0x8000)
                for i, c in enumerate(codes.values()))
expect = {  # hand encoded per PLAN §1.5 (not via builder helpers)
    'jamo_tiles': rd(S + '/data/jamo_glyphs_40.bin'),
    'nc_dense': bytes(dense),
    'nc_image': blob.CODE + bytes(0x2000 - len(blob.CODE)),
    'a3_table_tail': tail,
    'a3_max': struct.pack('<I', max(*syl_to_code.values(), *codes.values())),
    's1_press': bytes.fromhex('00480047') + struct.pack('<I', ent('nc_tramp_press')) + bytes.fromhex('c046'),
    's2_confirm': bytes.fromhex('00480047') + struct.pack('<I', ent('nc_tramp_confirm')),
    's3_backspace': bytes.fromhex('01480047c046') + struct.pack('<I', ent('nc_tramp_backspace')),
    'd1_display': bytes.fromhex('004b1847') + struct.pack('<I', ent('nc_tramp_display')),
    'p1_alloc': struct.pack('<I', ent('nc_alloc')),
}
cross = {'module_dense_eq': jamo.dense_table(syl_to_code) == expect['nc_dense'],
         'module_tiles_eq': jamo.jamo_tiles() == expect['jamo_tiles']}
sites = dict(B.NAME_COMPOSE_SITES)
regions = []
for n, s, e in writes:
    r = {'name': n, 'start': hex(s), 'end': hex(e), 'payload_sha256': sha(expect[n]), 'candidate_sha256': sha(cand[s:e]),
         'payload_match': cand[s:e] == expect[n], 'changed_vs_baseline': cand[s:e] != base[s:e],
         'baseline_sha256': sha(base[s:e])}
    if n in sites: r['baseline_eq_original_expect'] = base[s:e] == sites[n] == orig[s:e]
    elif n not in ('a3_max',): r['baseline_zero'] = not any(base[s:e])
    regions.append(r)
table_end = 0x08F20000 + 2926 * 6
lit_res = [{'off': hex(l), 'baseline': hex(U32(base, l)), 'candidate': hex(U32(cand, l)), 'ok': U32(cand, l) == table_end} for l in lits]
fixed = {  # bytes that must stay identical to baseline (and original where native)
    'a3_min_F30300': (0xF30300, 4), 'a3_start_F30308': (0xF30308, 4), 'a3_mask_F30310': (0xF30310, 4),
    'a3_kor_base_F30314': (0xF30314, 4), 'sel_table_83FAF6': (0x83FAF6, 0x83FBAA - 0x83FAF6),
    'display_rows_83FE40': (0x83FE40, 0x83FEF4 - 0x83FE40), 'row_ptr_literals_34AC24': (0x34AC24, 0x18),
    'keep_FD78': (0x83FD78, 4), 'keep_FDE0': (0x83FDE0, 4), 'keep_FD28': (0x83FD28, 4),
    'name_module_dispatch_AFAE': (0x34AFAE, 10), 'allocator_315288': (0x315288, 0x3153B0 - 0x315288),
    'a3_tramp_A3C7E8': (0xA3C7E8, 8)}
fixed_res = {k: {'off': hex(o), 'len': l, 'cand_eq_base': cand[o:o + l] == base[o:o + l],
                 'base_eq_orig': base[o:o + l] == orig[o:o + l], 'value_head': cand[o:o + min(l, 8)].hex()}
             for k, (o, l) in fixed.items()}
assert U32(cand, 0xF30310) == 0x7FFF and U32(cand, 0xF30300) == 0x8840
diff_res = {'diff_bytes': len(diff), 'diff_runs': [[hex(a), hex(b), b - a, owner(a)] for a, b in runs],
            'outside_whitelist': [hex(i) for i in outside], 'subset_ok': not outside,
            'regions': regions, 'all_payload_match': all(r['payload_match'] for r in regions),
            'all_regions_changed': all(r['changed_vs_baseline'] for r in regions),
            'end_literals': lit_res, 'end_literals_ok': all(x['ok'] for x in lit_res),
            'fixed_bytes': fixed_res, 'fixed_ok': all(v['cand_eq_base'] for v in fixed_res.values()),
            'module_cross_check': cross, 'code_bytes': len(blob.CODE), 'code_sha256': blob.CODE_SHA,
            'symbols': {k: hex(blob.IMAGE_RT + v) for k, v in blob.SYMBOLS.items()}}
dump('diff_payload.json', diff_res)
summary['diff'] = {k: diff_res[k] for k in ('diff_bytes', 'subset_ok', 'all_payload_match', 'all_regions_changed', 'end_literals_ok', 'fixed_ok')}
summary['diff']['module_cross_check'] = cross

# ---- 2. A3 lookup path (hook literals at F30300..F30314) for jamo40 + 2350 ----
def a3(rom, code):
    mn, mx, st, en, mask, kb = (U32(rom, 0xF30300 + 4 * k) for k in range(6))
    if not (mn <= code <= mx): return ('range', None)
    hits, p = [], st
    while p < en:
        o = p - 0x08000000
        if (rom[o] << 8 | rom[o + 1]) == code: hits.append(o)
        p += 6
    if not hits: return ('absent', None)
    o = hits[0]; top, bot = struct.unpack_from('<HH', rom, o + 2)
    if not top & 0x8000: return ('nonkor', None)
    t = kb - 0x08000000 + (top & mask) * 32; b = kb - 0x08000000 + (bot & mask) * 32
    return ('ok', {'entry': hex(o), 'dup': len(hits), 'top': top & mask, 'bot': bot & mask, 'glyph': rom[t:t + 32] + rom[b:b + 32]})
bin40 = expect['jamo_tiles']; jamo_res = []
for i, (k, c) in enumerate(codes.items()):
    st, info = a3(cand, c); sb, _ = a3(base, c)
    jamo_res.append({'jamo': k, 'code': hex(c), 'candidate': st, 'baseline': sb,
                     'tiles': [info['top'], info['bot']] if info else None, 'dup': info['dup'] if info else None,
                     'glyph_eq_bin': bool(info) and info['glyph'] == bin40[64 * i:64 * i + 64],
                     'ink': bool(info) and any(info['glyph'])})
syl_diff = []
for s, c in syl_to_code.items():
    a, b = a3(cand, c), a3(base, c)
    if a[0] != b[0] or (a[1] and (a[1]['glyph'], a[1]['entry'], a[1]['dup']) != (b[1]['glyph'], b[1]['entry'], b[1]['dup'])):
        syl_diff.append(s)
a3_res = {'hook_literals_candidate': [hex(U32(cand, 0xF30300 + 4 * k)) for k in range(6)],
          'hook_literals_baseline': [hex(U32(base, 0xF30300 + 4 * k)) for k in range(6)],
          'jamo': jamo_res, 'jamo_all_ok': all(j['candidate'] == 'ok' and j['dup'] == 1 and j['glyph_eq_bin'] and j['ink'] for j in jamo_res),
          'jamo_baseline_states': dict(collections.Counter(j['baseline'] for j in jamo_res)),
          'syllables_2350_resolution_changed': syl_diff}
dump('a3_jamo.json', a3_res)
summary['a3'] = {'jamo_all_ok': a3_res['jamo_all_ok'], 'jamo_baseline_states': a3_res['jamo_baseline_states'],
                 'syllables_changed': len(syl_diff), 'literals_candidate': a3_res['hook_literals_candidate']}

# ---- 3. shared native glyphs (algorithm of test_dialogue_script_safety native_glyph, applied per ROM) ----
grid = json.load(open(PH + '/mode-scope-re/grid-map.json', encoding='utf-8'))
ACTION = {'3131', '3232', '6262', '6363', '6565'}
pairs = set()
for c in grid['cells']:
    pairs.update(x for x in (c['selection'], c['display']) if x)
for r in grid['rows']:
    pairs.update(r['pairs'])
codes_g = sorted(int(x, 16) for x in pairs - ACTION)
def native(rom, code):
    root = U32(rom, 0x52F960) - 0x08000000
    bucket = root + ((code & 255) - 0x40) * 4
    node, seen, path = U32(rom, bucket), set(), []
    while node:
        assert node not in seen; seen.add(node); off = node - 0x08000000; path.append(hex(off))
        if rom[off + 4] == code >> 8:
            return {'root': hex(root), 'bucket': hex(bucket), 'path': path, 'node': hex(off), 'glyph': rom[off + 6:off + 70]}
        node = U32(rom, off)
    return {'root': hex(root), 'bucket': hex(bucket), 'path': path, 'node': None, 'glyph': None}
g_rows, present, absent, bad = [], [], [], []
for c in codes_g:
    nb, nc = native(base, c), native(cand, c)
    same = {k: nb[k] for k in ('root', 'bucket', 'path', 'node')} == {k: nc[k] for k in ('root', 'bucket', 'path', 'node')} and nb['glyph'] == nc['glyph']
    row = {'code': '%04X' % c, 'node': nc['node'], 'path': nc['path'], 'same': same,
           'glyph_sha256': sha(nc['glyph']) if nc['glyph'] else None, 'orig_same': native(orig, c)['glyph'] == nc['glyph']}
    g_rows.append(row); (present if nc['node'] else absent).append(row['code'])
    if not same: bad.append(row['code'])
dash = native(cand, 0x815B)
glyph_res = {'codes_checked': len(codes_g), 'action_markers_excluded': sorted(ACTION), 'present': present, 'absent_both': [
    r['code'] for r in g_rows if r['node'] is None and native(base, int(r['code'], 16))['node'] is None],
    'mismatch': bad, 'rows': g_rows,
    'dash_815B': {'node': dash['node'], 'glyph_sha256': sha(dash['glyph']) if dash['glyph'] else None,
                  'same_as_baseline': native(base, 0x815B)['glyph'] == dash['glyph']}}
dump('shared_glyph.json', glyph_res)
summary['shared_glyph'] = {'codes': len(codes_g), 'present': len(present), 'absent_both': len(glyph_res['absent_both']),
                           'absent_codes': absent, 'mismatch': bad, 'dash_815B': glyph_res['dash_815B']}

# ---- 4. one-off writer / manifest cross-check against F70000..F77800 and all NAME_COMPOSE_WRITES ----
def inter(a0, a1, b0, b1): return max(a0, b0) < min(a1, b1)
NEW = [('F70000..F77800', 0xF70000, 0xF77800)] + writes
def load_ranges(path):
    return [(int(x['start'], 16), int(x['end'], 16), x.get('kind')) for x in json.load(open(path))]
iranges_base = load_ranges(PH + '/candidate-re/integrity-ranges.json')
cmap = json.load(open(S + '/temp/integrity_map.json'))
iranges_cand = [(x[0], x[0] + x[1], x[7] if len(x) > 7 else None) for x in cmap]
def man_ranges(path):
    out = []
    for x in json.load(open(path)):
        if x.get('new_addr') and x.get('new_len'):
            a = int(x['new_addr'], 16) if isinstance(x['new_addr'], str) else x['new_addr']
            out.append((a, a + int(x['new_len']), 'repoint:' + str(x.get('msg'))))
    return out
mranges_base = man_ranges(BS + '/temp/repoint_manifest.json'); mranges_cand = man_ranges(S + '/temp/repoint_manifest.json')
wa = json.load(open(PH + '/candidate-re/writer-addresses.json'))
def hits(rngs, n0, n1): return [[hex(a), hex(b), k] for a, b, k in rngs if inter(a, b, n0, n1)]
xres = {'inputs_sha256': {p: sha(rd(p)) for p in (PH + '/candidate-re/integrity-ranges.json', PH + '/candidate-re/writer-addresses.json',
        PH + '/candidate-re/direct-writers.json', S + '/temp/integrity_map.json', S + '/temp/repoint_manifest.json',
        BS + '/temp/integrity_map.json', BS + '/temp/repoint_manifest.json')}, 'regions': []}
xres['integrity_map_identical_to_baseline'] = rd(S + '/temp/integrity_map.json') == rd(BS + '/temp/integrity_map.json')
xres['repoint_manifest_identical_to_baseline'] = rd(S + '/temp/repoint_manifest.json') == rd(BS + '/temp/repoint_manifest.json')
for n, a, b in NEW:
    wa_hits = []
    for w in wa:
        s0 = int(w['start'], 16); e0 = int(w['end'], 16) if w['end'] else None
        if (e0 and inter(s0, e0, a, b)) or (not e0 and a <= s0 < b): wa_hits.append([w['name'], w['start'], w['end']])
    xres['regions'].append({'name': n, 'start': hex(a), 'end': hex(b),
        'integrity_baseline': hits(iranges_base, a, b), 'integrity_candidate': hits(iranges_cand, a, b),
        'manifest_baseline': hits(mranges_base, a, b), 'manifest_candidate': hits(mranges_cand, a, b), 'writer_addresses': wa_hits})
# direct writers: same AST extraction as candidate-re/static_audit.py on the snapshot builder; new statements = owned?
src = open(S + '/tools/build_korean_full.py', encoding='utf-8').read(); tree = ast.parse(src); now = []
for nd in ast.walk(tree):
    if isinstance(nd, (ast.Assign, ast.AugAssign)):
        ts = nd.targets if isinstance(nd, ast.Assign) else [nd.target]
        if any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'rom' for t in ts):
            now.append({'line': nd.lineno, 'source': ast.get_source_segment(src, nd)})
    if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Attribute) and nd.func.attr == 'pack_into' and len(nd.args) > 1 \
            and isinstance(nd.args[1], ast.Name) and nd.args[1].id == 'rom':
        now.append({'line': nd.lineno, 'source': ast.get_source_segment(src, nd)})
fn = {nd.name: (nd.lineno, nd.end_lineno) for nd in tree.body if isinstance(nd, ast.FunctionDef)}
def func_of(line): return next((k for k, (a, b) in fn.items() if a <= line <= b), None)
old = collections.Counter(x['source'] for x in json.load(open(PH + '/candidate-re/direct-writers.json')))
cur = collections.Counter(x['source'] for x in now)
added = [dict(x, function=func_of(x['line'])) for x in now if cur[x['source']] > old.get(x['source'], 0)]
removed = sorted((old - cur).elements())
xres['direct_writers'] = {'baseline_count': sum(old.values()), 'candidate_count': len(now), 'added': added, 'removed': removed,
    'added_all_owned': all((a['function'] or '').startswith(('_name_compose', '_part2_name_compose')) for a in added)}
xres['conflict_free'] = all(not r['integrity_baseline'] and not r['integrity_candidate'] and not r['manifest_baseline']
    and not r['manifest_candidate'] for r in xres['regions']) and xres['direct_writers']['added_all_owned']
dump('writer_crosscheck.json', xres)
summary['crosscheck'] = {'conflict_free_integrity_manifest_and_owned_writers': xres['conflict_free'],
    'writer_address_overlaps': {r['name']: r['writer_addresses'] for r in xres['regions'] if r['writer_addresses']},
    'integrity_map_identical_to_baseline': xres['integrity_map_identical_to_baseline'],
    'repoint_manifest_identical_to_baseline': xres['repoint_manifest_identical_to_baseline'],
    'direct_writers': {k: (v if k != 'added' else [(a['line'], a['function'], a['source'][:80]) for a in v]) for k, v in xres['direct_writers'].items()}}

# ---- 5. B-team (address, cause, decision) set diff ----
bb = json.load(open(BS + '/temp/retry1_bteam_details.json')); cb = json.load(open(S + '/temp/candidate_bteam_details.json'))
key = lambda x: (x['address'], x['cause'], x['decision'])
sb, sc = set(map(key, bb)), set(map(key, cb))
full_b = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in bb}; full_c = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in cb}
bres = {'baseline': len(bb), 'candidate': len(cb), 'baseline_unique_keys': len(sb), 'candidate_unique_keys': len(sc),
        'new': sorted(sc - sb), 'gone': sorted(sb - sc), 'full_record_identical': full_b == full_c,
        'decisions_candidate': dict(collections.Counter(x['decision'] for x in cb))}
dump('bteam_diff.json', bres)
summary['bteam'] = {k: bres[k] for k in bres}
dump('summary.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=1))
ok = (summary['diff']['subset_ok'] and summary['diff']['all_payload_match'] and summary['diff']['all_regions_changed'] and
      summary['diff']['end_literals_ok'] and summary['diff']['fixed_ok'] and all(cross.values()) and a3_res['jamo_all_ok'] and
      not syl_diff and not bad and glyph_res['dash_815B']['same_as_baseline'] and xres['conflict_free'] and not bres['new'])
print('ANALYZE', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 4)
