#!/usr/bin/env python3
"""Cross-check a candidate ROM's build records against a whole-ROM Ghidra export.

Static aid only: every finding needs a runtime check (mgba BP/watch) before it is
treated as a defect.  Inputs:
  --ghidra DIR   export from tools/ghidra/full_analysis.sh (ORIGINAL ROM analysis)
  --orig ROM     original ROM
  --cand ROM     candidate ROM (e.g. output/game_wars_korean_candidate_20261013_b21.gba)
  --records DIR  directory holding integrity_map.json + repoint_manifest.json of the SAME
                 build as --cand (e.g. temp/b21_20261013).  If <cand>.build.json exists its
                 build_metadata SHA-256 values are verified against these files.
  --out DIR      writes a_stale_refs.tsv, b_unknown_consumers.tsv, c_renderers.tsv,
                 d_hook_side_effects.tsv, e_control_tables.tsv, diff_ranges.tsv, summary.json

Categories (see temp/ghidra_audit_20261013/report.md for interpretation):
  a  stale references to OLD addresses of relocated messages / repointed targets
  b  build-written regions without a static reader
  c  text-renderer / parser candidates vs the known renderer list
  d  callers of code the build patched (hook side effects)
  e  control-code switch tables of known parsers vs tool assumptions
"""
import argparse
import bisect
import collections
import hashlib
import json
import os
import struct
import sys

GBA = 0x08000000
ROM_LO, ROM_HI = 0x08000000, 0x09000000

KNOWN_RENDERERS = {
    0x08313F8C: 'P2 tilemap renderer (313)',
    0x08B11BB0: 'common tilemap renderer (B11)',
    0x08B12074: 'P1 dialogue parser (B12074, table 0xB120F4)',
    0x0831424C: 'P2 script parser (31424C)',
    0x08373D10: 'P2 header drawer',
    0x08B1311C: 'P1 compact/map-label consumer (B1311C)',
    0x08B126F0: 'P1 dialogue render loop (B126F0..B12758)',
    0x08B12984: 'P1 second text renderer (B12B1A caller region)',
    0x08B1BEFC: 'P1 veneer to IWRAM 030065E0',
    0x08B48910: 'P1 name grid renderer',
    0x08313D90: 'P2 313 family',
    0x08382944: 'P2 (decomp-out list)',
    0x08383DCC: 'P2 (decomp-out list)',
}
KNOWN_RANGES = [  # (lo, hi, label) partial knowledge: map-select renderer family etc.
    (0x0831B000, 0x0831C000, 'P2 map-select renderer family 0x0831Bxxx'),
    (0x03006080, 0x03006800, 'P2 A3 glyph cache (IWRAM 03006080, ROM 08A3C7E4)'),
    (0x030065E0, 0x03006800, 'P1 SJIS->glyph (IWRAM 030065E0, ROM 08EFE788)'),
]
COPY_HELPERS = {0x0838B434: 'P2 copy helper 0838B434'}
SJIS_LEADS = {0x80, 0x81, 0x84, 0x88, 0x89, 0x98, 0x9F, 0xA0, 0xDF, 0xE0, 0xE2, 0xEF, 0xF0, 0xFC}
# Tool assumptions (parser start -> control set the tools model).  Keep in sync with
# tools/part2_native_controls.py KNOWN (+0x72 newline, 0x20 consume, lowercase aliases),
# tools/qa_render_jam.py (P1: 0x81-0xE2 two-byte, 0x21-0x7E printable, else 1-byte ctrl)
# and tools/text_metrics.py ('\n'=0x0A only newline, ASCII 0x20-0x7E = 1 visible cell).
TOOL_ASSUMED = {
    0x0831424C: {'src': 'part2_native_controls.KNOWN+newline',
                 'codes': {0x57, 0x77, 0x4B, 0x6B, 0x09, 0x0A, 0x30, 0x31, 0x32, 0x33, 0x72, 0x20}},
    0x08B12074: {'src': 'qa_render_jam (P1: only 0x00 term; 0x20 hook; others = printable/1-byte)',
                 'codes': {0x00, 0x20}},
}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def parse_addr(s):
    """'08B12074' or 'IW_P1_03006448:030065E0' -> (space, int)."""
    if ':' in s:
        sp, v = s.split(':', 1)
        return sp, int(v, 16)
    return '', int(s, 16)


def read_tsv(path):
    with open(path, encoding='utf-8') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            p = line.rstrip('\n').split('\t')
            yield dict(zip(hdr, p))


class Intervals:
    def __init__(self, items):  # items: (lo, hi_inclusive, payload)
        self.items = sorted(items)
        self.starts = [i[0] for i in self.items]

    def find(self, a):
        i = bisect.bisect_right(self.starts, a) - 1
        # bodies may overlap rarely; scan back a few
        for j in range(i, max(i - 8, -1), -1):
            lo, hi, p = self.items[j]
            if lo <= a <= hi:
                return p
        return None

    def overlaps(self, lo, hi):
        i = bisect.bisect_right(self.starts, hi) - 1
        out = []
        while i >= 0 and len(out) < 50:
            a, b, p = self.items[i]
            if b >= lo and a <= hi:
                out.append(p)
            if a < lo - 0x10000:
                break
            i -= 1
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ghidra', required=True)
    ap.add_argument('--orig', required=True)
    ap.add_argument('--cand', required=True)
    ap.add_argument('--records', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    orig = open(a.orig, 'rb').read()
    cand = open(a.cand, 'rb').read()
    imap_p = os.path.join(a.records, 'integrity_map.json')
    man_p = os.path.join(a.records, 'repoint_manifest.json')
    prov = {'orig_sha256': hashlib.sha256(orig).hexdigest(), 'cand_sha256': hashlib.sha256(cand).hexdigest(),
            'integrity_map_sha256': sha(imap_p), 'repoint_manifest_sha256': sha(man_p),
            'ghidra_rom': open(os.path.join(a.ghidra, 'rom.sha256')).read().split()[0]
            if os.path.exists(os.path.join(a.ghidra, 'rom.sha256')) else None}
    bj = a.cand + '.build.json'
    if os.path.exists(bj):
        meta = json.load(open(bj))
        bm = meta.get('build_metadata', {})
        prov['build_json'] = bj
        prov['build_json_rom_sha_ok'] = meta.get('rom_sha256') == prov['cand_sha256']
        prov['records_match_build_json'] = (bm.get('temp/integrity_map.json') == prov['integrity_map_sha256']
                                            and bm.get('temp/repoint_manifest.json') == prov['repoint_manifest_sha256'])
        if not (prov['build_json_rom_sha_ok'] and prov['records_match_build_json']):
            print('ERROR: records/candidate do not match build.json provenance', prov, file=sys.stderr)
            return 2
    if prov['ghidra_rom'] and prov['ghidra_rom'] != prov['orig_sha256']:
        print('WARNING: Ghidra export was not made from --orig', file=sys.stderr)

    # ---------- Ghidra export
    G = a.ghidra
    funcs = {}
    for r in read_tsv(os.path.join(G, 'functions.tsv')):
        sp, e = parse_addr(r['entry'])
        funcs[(sp, e)] = {'mode': r['mode'], 'size': int(r['size']), 'name': r['name'],
                          'callers': [parse_addr(x) for x in r['callers'].split(',') if x],
                          'callees': [parse_addr(x) for x in r['callees'].split(',') if x]}
    bodies = Intervals([(parse_addr(r['start'])[1], parse_addr(r['end'])[1], parse_addr(r['func']))
                        for r in read_tsv(os.path.join(G, 'bodies.tsv')) if not parse_addr(r['start'])[0]])
    code = Intervals([(parse_addr(r['start'])[1], parse_addr(r['end'])[1], r['mode'])
                      for r in read_tsv(os.path.join(G, 'code_ranges.tsv')) if not parse_addr(r['start'])[0]])
    lit = {}  # literal addr -> [(insn, func)]
    for r in read_tsv(os.path.join(G, 'const_refs.tsv')):
        sp, la = parse_addr(r['literal_addr'])
        lit.setdefault(la, []).append((r['insn'], r['func']))
    feats = {parse_addr(r['func']): r for r in read_tsv(os.path.join(G, 'feature.tsv'))}
    switches = collections.defaultdict(list)
    for r in read_tsv(os.path.join(G, 'switches.tsv')):
        switches[parse_addr(r['func'])].append(r)

    def fname(k):
        sp, e = k
        return (sp + ':' if sp else '') + '%08X' % e

    def owner(addr):  # ROM absolute -> function key or None
        return bodies.find(addr)

    def part_of(addr):
        # embedded multiboot (link-cable) images: GBA logo copies at 0x8FEDA0.. / 0xEC3EE4..,
        # linked for EWRAM 0x02000000 -> their literals/refs are not valid ROM refs.
        if 0x088F0000 <= addr < 0x08A00000 or 0x08EC0000 <= addr < 0x08EF0000:
            return 'multiboot?'
        if addr < 0x08300000:
            return 'launcher'
        return 'P2' if addr < 0x08B00000 else 'P1'

    # ---------- ROM-pointer words (aligned) in orig and cand
    def words(b):
        n = len(b) // 4
        return struct.unpack('<%dI' % n, b[:n * 4])
    wo, wc = words(orig), words(cand)

    def loc_kind(off):
        A = GBA + off
        if A in lit:
            return 'literal'
        if code.find(A) is not None:
            return 'code'
        return 'data'

    ptr_c = collections.defaultdict(list)  # value -> [offset]
    for i, v in enumerate(wc):
        if ROM_LO <= v < ROM_HI:
            ptr_c[v & ~1].append(i * 4)
    ptr_o = collections.defaultdict(list)
    for i, v in enumerate(wo):
        if ROM_LO <= v < ROM_HI:
            ptr_o[v & ~1].append(i * 4)
    sorted_ptr_c = sorted(ptr_c)

    # ---------- diff ranges
    diff = []
    i, n = 0, len(orig)
    while i < n:
        if orig[i] != cand[i]:
            j = i
            while j < n and (orig[j] != cand[j] or (j + 4 < n and orig[j:j + 4] != cand[j:j + 4])):
                j += 1
            diff.append((i, j))
            i = j
        else:
            i += 1
    imap = json.load(open(imap_p))
    man = json.load(open(man_p))
    text_cov = Intervals([(e[0], e[0] + max(e[1], e[2], 1) - 1, e[7]) for e in imap])
    ptr_site_set = set()
    for m in man:
        for s in m.get('ptr_sites', []):
            ptr_site_set.add(int(s, 16))

    def classify_diff(lo, hi):
        if text_cov.overlaps(lo, hi - 1):
            return 'text(integrity_map)'
        if any(s in ptr_site_set for s in range(lo & ~3, hi, 4)):
            return 'pointer(repoint)'
        o = orig[lo:hi]
        if o.count(0xFF) == len(o) or o.count(0) == len(o):
            return 'free-space'
        if bodies.find(GBA + lo) is not None or code.find(GBA + lo) is not None:
            return 'code-patch'
        if all(GBA + k in lit for k in range(lo & ~3, hi, 4)):
            return 'literal-patch'
        return 'asset/data'
    with open(os.path.join(a.out, 'diff_ranges.tsv'), 'w') as f:
        f.write('start\tend\tlen\tclass\towner_func\n')
        dclass = collections.Counter()
        diff_rows = []
        for lo, hi in diff:
            c = classify_diff(lo, hi)
            ow = owner(GBA + lo)
            diff_rows.append((lo, hi, c, ow))
            dclass[c] += 1
            f.write('%08X\t%08X\t%d\t%s\t%s\n' % (GBA + lo, GBA + hi, hi - lo, c, fname(ow) if ow else ''))

    diff_starts = [r[0] for r in diff_rows]

    def diff_near(off):
        i = bisect.bisect_right(diff_starts, off) - 1
        return diff_rows[max(i - 1, 0):i + 2] if i >= 0 else []

    # ================= (a) stale references
    a_rows = []
    # a1: generic repoint pairs from aligned word diffs
    repoint_pairs = collections.defaultdict(set)
    for i4 in range(len(wo)):
        vo, vc = wo[i4], wc[i4]
        if vo != vc and ROM_LO <= vo < ROM_HI and ROM_LO <= vc < ROM_HI:
            repoint_pairs[vo].add(vc)
    for vo, news in repoint_pairs.items():
        for off in ptr_o.get(vo & ~1, []):
            if wo[off // 4] != vo:
                continue
            if wc[off // 4] == vo:
                k = loc_kind(off)
                ow = owner(GBA + off) if k != 'data' else None
                lf = lit.get(GBA + off, [])
                in_asset = any(lo <= off < hi and c == 'asset/data' for lo, hi, c, _ in diff_near(off))
                a_rows.append({'check': 'a1_same_value_not_repointed' + ('(site_in_rewritten_asset)' if in_asset else ''),
                               'site': '%08X' % (GBA + off), 'site_kind': k,
                               'old_value': '%08X' % vo, 'repointed_elsewhere_to': ','.join('%08X' % x for x in sorted(news)),
                               'func': ';'.join(f for _, f in lf) or (fname(ow) if ow else ''),
                               'old_slot_changed': orig[(vo & ~1) - GBA:(vo & ~1) - GBA + 16] != cand[(vo & ~1) - GBA:(vo & ~1) - GBA + 16]})
    # a2: manifest relocated messages: exact (any alignment) + interior aligned refs
    for m in man:
        if m.get('status') != 'relocated':
            continue
        msg = int(m['msg'], 16)
        ol = int(m.get('old_len') or 0)
        sites = set(int(s, 16) for s in m.get('ptr_sites', []))
        needle = struct.pack('<I', GBA + msg)
        pos = 0
        while True:
            hit = orig.find(needle, pos)
            if hit < 0:
                break
            pos = hit + 1
            if hit in sites:
                if cand[hit:hit + 4] == needle:
                    a_rows.append({'check': 'a2_manifest_site_not_written', 'site': '%08X' % (GBA + hit),
                                   'site_kind': loc_kind(hit) if hit % 4 == 0 else 'unaligned',
                                   'old_value': '%08X' % (GBA + msg), 'repointed_elsewhere_to': m.get('new_addr'),
                                   'func': '', 'old_slot_changed': ''})
                continue
            if cand[hit:hit + 4] != needle:
                continue  # changed by some other writer
            k = loc_kind(hit) if hit % 4 == 0 else 'unaligned'
            ow = owner(GBA + hit) if k in ('literal', 'code') else None
            a_rows.append({'check': 'a2_exact_old_msg_ref', 'site': '%08X' % (GBA + hit), 'site_kind': k,
                           'old_value': '%08X' % (GBA + msg), 'repointed_elsewhere_to': m.get('new_addr'),
                           'func': ';'.join(f for _, f in lit.get(GBA + hit, [])) or (fname(ow) if ow else ''),
                           'old_slot_changed': orig[msg:msg + ol] != cand[msg:msg + ol]})
        lo_i = bisect.bisect_right(sorted_ptr_c, GBA + msg)
        hi_i = bisect.bisect_left(sorted_ptr_c, GBA + msg + ol)
        for v in sorted_ptr_c[lo_i:hi_i]:
            for off in ptr_c[v]:
                if wo[off // 4] != wc[off // 4]:
                    continue
                k = loc_kind(off)
                lf = lit.get(GBA + off, [])
                tchg = orig[v - GBA:v - GBA + 8] != cand[v - GBA:v - GBA + 8]
                a_rows.append({'check': 'a2_interior_ref_into_relocated_span' + ('' if tchg else '(target_bytes_unchanged)'),
                               'site': '%08X' % (GBA + off), 'site_kind': k,
                               'old_value': '%08X(+0x%X)' % (v, v - GBA - msg), 'repointed_elsewhere_to': m.get('new_addr'),
                               'func': ';'.join(f for _, f in lf), 'old_slot_changed': orig[msg:msg + ol] != cand[msg:msg + ol]})
    with open(os.path.join(a.out, 'a_stale_refs.tsv'), 'w') as f:
        cols = ['check', 'site', 'site_kind', 'old_value', 'repointed_elsewhere_to', 'func', 'old_slot_changed']
        f.write('\t'.join(cols) + '\n')
        for r in a_rows:
            f.write('\t'.join(str(r[c]) for c in cols) + '\n')

    # ================= (b) unknown consumers
    last = {}
    for e in imap:
        last[e[0]] = e
    # relocated targets also are build-written regions
    for m in man:
        if m.get('status') == 'relocated':
            na = int(m['new_addr'], 16)
            last.setdefault(na, [na, m.get('new_len', 0), m.get('new_len', 0), '', None, '', None, 'repoint-relocated'])
    table_runs = {}  # data pointer word offset -> run start offset

    def reader(addr_off, window=0x400):
        A = GBA + addr_off
        offs = ptr_c.get(A, [])
        kinds = collections.Counter(loc_kind(o) for o in offs)
        if kinds.get('literal'):
            fs = sorted({f for o in offs for _, f in lit.get(GBA + o, [])})
            return 'code-literal', ','.join(fs[:6])
        if kinds.get('data'):
            o = next(x for x in offs if loc_kind(x) == 'data')
            # walk back to start of pointer run (table)
            s = o
            while s >= 4 and ROM_LO <= wc[s // 4 - 1] < ROM_HI:
                s -= 4
            tref = ptr_c.get(GBA + s, [])
            tk = sorted({f for x in tref for _, f in lit.get(GBA + x, [])})
            if tk:
                return 'pointer-table(code-ref)', 'table@%08X idx%d by %s' % (GBA + s, (o - s) // 4, ','.join(tk[:4]))
            if tref:
                return 'pointer-table(data-ref)', 'table@%08X idx%d (table ptr in data)' % (GBA + s, (o - s) // 4)
            return 'pointer-table(computed)', 'table@%08X idx%d (no ptr to table start; computed base?)' % (GBA + s, (o - s) // 4)
        i = bisect.bisect_right(sorted_ptr_c, A) - 1
        if i >= 0 and A - sorted_ptr_c[i] <= window:
            return 'interior-of-referenced-block', 'block@%08X +0x%X' % (sorted_ptr_c[i], A - sorted_ptr_c[i])
        return 'none', ('nearest ptr target below: %08X (-0x%X)' % (sorted_ptr_c[i], A - sorted_ptr_c[i])) if i >= 0 else ''
    b_rows = []
    bc = collections.Counter()
    for addr in sorted(last):
        e = last[addr]
        kind = e[7]
        st, det = reader(addr)
        bc[(kind.split(':')[0] + ':*' if kind.startswith(('script:', 'repoint:')) else kind, st)] += 1
        if st in ('none', 'pointer-table(computed)'):
            b_rows.append((addr, e[1], kind, st, det, (e[5] or '')[:24]))
    # non-text diff regions (asset/free-space/code) readers
    for lo, hi, c, ow in diff_rows:
        if c in ('text(integrity_map)', 'pointer(repoint)', 'code-patch', 'literal-patch'):
            continue
        st, det = reader(lo, 0x10000 if c == 'asset/data' else 0x400)
        bc[('diff:' + c, st)] += 1
        if st in ('none', 'pointer-table(computed)'):
            b_rows.append((lo, hi - lo, 'diff:' + c, st, det, ''))
    with open(os.path.join(a.out, 'b_unknown_consumers.tsv'), 'w') as f:
        f.write('addr\tlen\tregion_kind\treader_status\tdetail\ttext\n')
        for r in b_rows:
            f.write('%08X\t%s\t%s\t%s\t%s\t%s\n' % (GBA + r[0], r[1], r[2], r[3], r[4], r[5].replace('\t', ' ').replace('\n', ' ')))
    with open(os.path.join(a.out, 'b_reader_status_counts.tsv'), 'w') as f:
        f.write('region_kind\treader_status\tcount\n')
        for (k, s), v in sorted(bc.items()):
            f.write('%s\t%s\t%d\n' % (k, s, v))

    # ================= (c) renderer inventory
    text_regions = Intervals([(GBA + e[0], GBA + e[0] + max(e[1], 1) - 1, e[7]) for e in last.values()])
    c_rows = []
    known_keys = {('', k) for k in KNOWN_RENDERERS}
    callers_of_known = set()
    for k in known_keys:
        if k in funcs:
            callers_of_known.update(funcs[k]['callers'])
    for key, f in feats.items():
        ni = int(f['n_insn'])
        if ni < 12:
            continue
        cmps = {int(x, 16) for x in f['cmp_imm'].split(',') if x}
        bls = {parse_addr(x) for x in f['bl_targets'].split(',') if x}
        score = 0
        why = []
        if int(f['ldrb']) >= 1 and int(f['loops']) >= 1:
            score += 2; why.append('ldrb-loop')
        sj = cmps & SJIS_LEADS
        if sj:
            score += 2 + (len(sj) >= 2); why.append('cmp-sjis:' + ','.join('%X' % x for x in sorted(sj)))
        if int(f['computed_jumps']):
            score += 1; why.append('switch')
        if int(f['const_vram']):
            score += 1; why.append('vram')
        if int(f['const_io']) and ('B' in f['swi'].split(',') or 'C' in f['swi'].split(',') or int(f['const_io'])):
            score += 0
        if f['swi']:
            why.append('swi:' + f['swi'])
            if {'B', 'C'} & set(f['swi'].split(',')):
                score += 1
        if bls & {('', h) for h in COPY_HELPERS}:
            score += 1; why.append('copy-helper')
        if bls & known_keys:
            score += 1; why.append('calls-known:' + ','.join(fname(x) for x in bls & known_keys))
        if int(f['strh']) >= 1 and int(f['loops']):
            why.append('strh-loop')
        # text regions consumed via code literals
        consumed = set()
        sp, e = key
        if score < 4:
            continue
        known = key in known_keys or any(lo <= e < hi for lo, hi, _ in KNOWN_RANGES)
        label = KNOWN_RENDERERS.get(e) or next((l for lo, hi, l in KNOWN_RANGES if lo <= e < hi), '')
        c_rows.append((score, fname(key), part_of(e) if not sp else sp, known, label, ';'.join(why),
                       len(funcs.get(key, {}).get('callers', []))))
    # consumed text regions per candidate function (literal pointers into build-written text)
    lit_by_func = collections.defaultdict(set)
    for r in read_tsv(os.path.join(G, 'rom_refs.tsv')):
        v = int(r['value'], 16) & ~1
        reg = text_regions.find(v)
        if reg:
            lit_by_func[r['func']].add(reg)
    c_rows.sort(key=lambda r: (-r[0], r[1]))
    with open(os.path.join(a.out, 'c_renderers.tsv'), 'w') as f:
        f.write('score\tfunc\tpart\tknown\tlabel\tevidence\tncallers\tconsumes_written_kinds(literal)\n')
        for r in c_rows:
            f.write('\t'.join(str(x) for x in r) + '\t' + ','.join(sorted(lit_by_func.get(r[1], set()))[:8]) + '\n')

    # ================= (d) hook side effects
    d_rows = []

    def thumb_bl(b, off):
        if off + 4 > len(b):
            return None
        h1, h2 = struct.unpack_from('<HH', b, off)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xF800) not in (0xF800, 0xE800):
            return None
        o = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
        if o & 0x400000:
            o -= 0x800000
        return GBA + off + 4 + o
    callers_of = collections.defaultdict(set)
    for k, f in funcs.items():
        for c in f['callees']:
            callers_of[c].add(k)
    for lo, hi, c, ow in diff_rows:
        if c not in ('code-patch', 'literal-patch'):
            continue
        fk = ow
        if fk is None and c == 'literal-patch':
            fs = {x for o in range(lo & ~3, hi, 4) for _, x in lit.get(GBA + o, [])}
            fk = parse_addr(sorted(fs)[0]) if fs else None
        detail = []
        for off in range(max(lo - 2, 0) & ~1, hi, 2):
            ob, cb = thumb_bl(orig, off), thumb_bl(cand, off)
            if cb and ob != cb:
                detail.append('BL@%08X %s->%08X' % (GBA + off, ('%08X' % ob) if ob else 'none', cb))
                if ob:
                    others = sorted(fname(x) for x in callers_of.get(('', ob), set()) if x != fk)
                    detail.append('  other callers of %08X: %d [%s]' % (ob, len(others), ','.join(others[:12])))
        for o4 in range(lo & ~3, hi, 4):
            vo, vc = wo[o4 // 4], wc[o4 // 4]
            if vo != vc and (ROM_LO <= vc < ROM_HI):
                detail.append('word@%08X %08X->%08X' % (GBA + o4, vo, vc))
        callers = sorted(fname(x) for x in funcs.get(fk, {}).get('callers', [])) if fk else []
        d_rows.append(('%08X' % (GBA + lo), hi - lo, c, fname(fk) if fk else '', len(callers),
                       ','.join(callers[:20]), ' | '.join(detail)[:900]))
    with open(os.path.join(a.out, 'd_hook_side_effects.tsv'), 'w') as f:
        f.write('patch_addr\tlen\tclass\tpatched_func\tncallers\tcallers\tdetail\n')
        for r in d_rows:
            f.write('\t'.join(str(x) for x in r) + '\n')

    # ================= (e) control-code tables
    e_rows = []
    for key, sws in switches.items():
        sp, e = key
        is_known = ('', e) in known_keys or any(lo <= e < hi for lo, hi, _ in KNOWN_RANGES)
        for r in sws:
            cases = []
            for tok in r['cases(value:target)'].split(','):
                if ':' not in tok:
                    continue
                v, t = tok.split(':', 1)
                try:
                    cases.append((int(v, 16), t))
                except ValueError:
                    pass
            if not cases:
                continue
            tgt_count = collections.Counter(t for _, t in cases)
            default_t, _ = tgt_count.most_common(1)[0]
            handled = sorted(v for v, t in cases if t != default_t)
            assumed = TOOL_ASSUMED.get(e)
            mism = ''
            if assumed:
                miss = sorted(set(handled) - assumed['codes'])
                extra = sorted(assumed['codes'] - set(handled) - {0x00, 0x20})
                mism = 'parser-handles-not-in-tool:%s; tool-assumes-not-in-switch:%s' % (
                    ','.join('%02X' % x for x in miss), ','.join('%02X' % x for x in extra))
            if not (is_known or assumed or len(handled) >= 3):
                continue
            # value ranges likely bytes of text: report only byte-sized switches
            if max(v for v, _ in cases) > 0x1FF:
                continue
            e_rows.append((fname(key), r['switch_insn'], len(cases), is_known, '%02X..%02X' % (min(v for v, _ in cases), max(v for v, _ in cases)),
                           ','.join('%02X' % v for v in handled), default_t, mism))
    with open(os.path.join(a.out, 'e_control_tables.tsv'), 'w') as f:
        f.write('func\tswitch_insn\tncases\tknown\tcase_range\tnon_default_cases\tdefault_target\ttool_mismatch\n')
        for r in e_rows:
            f.write('\t'.join(str(x) for x in r) + '\n')

    # e2: single-byte parser commands introduced by the build inside written text.
    # Command sets come from the switch export of the two known script parsers
    # (non-default cases of both dispatch tables, excluding terminator 0x00).
    def parser_codes(entry):
        codes = set()
        for r in switches.get(('', entry), []):
            cases = [tuple(t.split(':', 1)) for t in r['cases(value:target)'].split(',') if ':' in t]
            if not cases:
                continue
            dflt = collections.Counter(t for _, t in cases).most_common(1)[0][0]
            codes |= {int(v, 16) for v, t in cases if t != dflt}
        return codes - {0x00}
    pcodes = {'P2_31424C': parser_codes(0x0831424C), 'P1_B12074': parser_codes(0x08B12074)}

    def single_tokens(b):
        out = collections.Counter()
        i = 0
        while i < len(b):
            x = b[i]
            if x == 0:
                break
            if 0x81 <= x <= 0x9F or 0xE0 <= x <= 0xFC:
                i += 2
                continue
            out[x] += 1
            i += 1
        return out
    reloc_src = {int(m['new_addr'], 16): (int(m['msg'], 16), int(m.get('old_len') or 0))
                 for m in man if m.get('status') == 'relocated'}
    e2 = []
    for addr in sorted(last):
        e = last[addr]
        ln = max(e[1] or 0, e[2] or 0)
        if ln <= 0 or addr < 0x300000:
            continue
        src = reloc_src.get(addr)
        to = single_tokens(orig[src[0]:src[0] + src[1]]) if src else single_tokens(orig[addr:addr + ln])
        tc = single_tokens(cand[addr:addr + ln])
        part = 'P1' if (src[0] if src else addr) >= 0xB00000 else 'P2'  # relocated: part of the source
        for pname, codes in pcodes.items():
            added = {k: tc[k] - to.get(k, 0) for k in codes if tc[k] > to.get(k, 0)}
            if added:
                e2.append(('%08X' % (GBA + addr), ln, part, pname, e[7],
                           ','.join('%02X(%s)x%d' % (k, chr(k) if 0x20 < k < 0x7F else '.', v) for k, v in sorted(added.items())),
                           (e[5] or '')[:30].replace('\t', ' ').replace('\n', ' ')))
    with open(os.path.join(a.out, 'e2_introduced_parser_commands.tsv'), 'w') as f:
        f.write('# parser command sets from switches.tsv: ' + '; '.join('%s=%s' % (k, ','.join('%02X' % x for x in sorted(v))) for k, v in pcodes.items()) + '\n')
        f.write('addr\tlen\taddr_part\tparser_set\twriter\tadded_commands\tko\n')
        for r in e2:
            f.write('\t'.join(str(x) for x in r) + '\n')

    summary = {'provenance': prov,
               'ghidra': {'functions': len(funcs), 'functions_rom': sum(1 for k in funcs if not k[0]),
                          'literal_words': len(lit), 'switch_funcs': len(switches)},
               'diff_ranges': dict(dclass),
               'a_stale_refs': dict(collections.Counter(r['check'] + '/' + r['site_kind'] for r in a_rows)),
               'b_unknown_consumers': dict(collections.Counter(r[3] for r in b_rows)),
               'b_reader_status_all': {'%s|%s' % k: v for k, v in bc.items()},
               'c_renderer_candidates': len(c_rows),
               'c_unknown_candidates': sum(1 for r in c_rows if not r[3]),
               'd_patch_ranges': len(d_rows),
               'e_switch_rows': len(e_rows),
               'e2_introduced_parser_commands': dict(collections.Counter('%s|%s' % (r[2], r[3]) for r in e2))}
    json.dump(summary, open(os.path.join(a.out, 'summary.json'), 'w'), indent=1)
    print(json.dumps(summary, indent=1)[:3000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
