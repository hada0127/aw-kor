#!/usr/bin/env python3
"""Sentence-level dialogue export for the W3 humanizer (PLAN A T3.1/T3.4).

Read-only. Exports whole native messages (Part 1 + Part 2) as rewrite batches:
assembled JP (original ROM) and assembled KO (current candidate ROM) with every
control/keyword token replaced by a placeholder, fragment rows, speaker and
register hint, window width per consumer, current slot capacity, overlay
relocatability and pinned-intersection locks (decision_W3_arena.md), plus
defect flags (punct_missing, carried T2 items, Japanese punctuation, ...).

Contract (plan_A.md §3.2, extended):
  payload == prefix + seg[0].raw + skeleton[0].raw + seg[1].raw + ... + seg[n].raw + suffix
  where len(segments) == len(skeleton) + 1. `ko` is the same sequence with
  segment text and skeleton placeholders. `reassemble()` proves this per message.

Usage:
  python3 tools/dialogue_sentence_export.py plan  --rom ROM --out temp/fix_20261104/humanizer/batches.json
  python3 tools/dialogue_sentence_export.py export --rom ROM --batch-plan batches.json --batch p2-tutorial.1 \
          --out-dir temp/fix_20261104/humanizer/batches
  python3 tools/dialogue_sentence_export.py export ... --batch all
Deterministic: same inputs -> byte-identical outputs (no timestamps).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from dialogue_pixel_layout import Glyphs, tokenize, inventory, physical_rows  # noqa: E402

GBA = 0x08000000
SCHEMA = 'aw-kor/dialogue-sentence-export/v1'
DEFAULT_ORIGINAL = ROOT / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
DEFAULT_ROM = ROOT / 'temp/fix_20261104/t2/game_wars_korean_candidate_20261104_t2.gba'
DEFAULT_MAP = ROOT / 'temp/fix_20261104/t2/snap/temp/integrity_map.json'
DEFAULT_MANIFEST = ROOT / 'temp/fix_20261104/t2/snap/temp/repoint_manifest.json'
DEFAULT_PUNCT = ROOT / 'temp/fix_20261104/punct_173.json'
P2_TABLE, P2_COUNT = 0xA357B4, 3315
P2_CO_NAMES = 2583          # master-table ids 2583..2601 = CO names (CO table order)
P2_CO_COUNT = 19

# ---------------------------------------------------------------- placeholders
NAMED = {0x72: '{r}', 0x52: '{R}', 0x6B: '{k}', 0x4B: '{K}', 0x70: '{p}', 0x50: '{P}',
         0x77: '{w}', 0x57: '{W}'}
SENTENCE_END = '!?！？'
JP_PUNCT = set('、。・･')
KANA = re.compile(r'[ぁ-ゖァ-ヺ]')
HANGUL = re.compile(r'[가-힣]')
PLACEHOLDER = re.compile(r'\{[^{}]*\}')


def _ph(tok):
    b = tok['raw'][0]
    k = tok['kind']
    if k in ('newline', 'page', 'wait'):
        return NAMED[b]
    if k == 'name':
        return '{name}'
    if k == 'icon':
        return '{arrow}' if tok['raw'] == b'>' else '{icon:%s}' % tok['raw'].hex()
    if k == 'choice':
        return '{q:%s}' % tok['raw'].hex()
    if k == 'speed':
        return '{spd:%s}' % tok['raw'].hex()
    if k == 'style':
        return '{s:%s}' % tok['raw'].hex()
    if k == 'format':
        return '{f:%s}' % tok['raw'].hex()
    return '{x:%s}' % tok['raw'].hex()


def _is_text(tok):
    return tok['kind'] in ('glyph', 'space', 'padding')


def decompose(payload, game, glyphs=None, space=' '):
    """Split a payload into prefix / segments / skeleton / suffix (lossless).

    Text tokens (glyph, rendered space, padding) form segments; every other
    token becomes a skeleton placeholder. A style-open (31/32/33) + glyphs +
    style-close (30) run is one `{kw:TEXT}` placeholder (fixed keyword).
    Format bytes (09/0A/0D) directly after a placeholder ride on it; leading
    format bytes form the prefix; trailing padding/format/terminator the suffix.
    """
    toks = tokenize(payload, game, glyphs)
    # suffix: terminator plus trailing padding/format (scan backwards)
    end = len(toks)
    while end and toks[end-1]['kind'] in ('end', 'padding', 'format'):
        end -= 1
    suffix = b''.join(t['raw'] for t in toks[end:])
    start = 0
    while start < end and toks[start]['kind'] == 'format':
        start += 1
    prefix = b''.join(t['raw'] for t in toks[:start])
    segments = [dict(raw=b'', text='', offset=len(prefix))]
    skeleton = []
    i = start
    pos = len(prefix)
    while i < end:
        t = toks[i]
        if _is_text(t):
            seg = segments[-1]
            seg['raw'] += t['raw']
            if t['kind'] == 'glyph':
                seg['text'] += t['text']
            elif t['kind'] == 'space':
                seg['text'] += space
            pos += len(t['raw'])
            i += 1
            continue
        if t['kind'] == 'format' and skeleton and segments[-1]['raw'] == b'':
            skeleton[-1]['raw'] += t['raw']
            pos += len(t['raw'])
            i += 1
            continue
        item = None
        if t['kind'] == 'style' and t['raw'][0] in (0x31, 0x32, 0x33):
            j = i + 1
            while j < end and toks[j]['kind'] in ('glyph', 'space'):
                j += 1
            if j < end and j > i + 1 and toks[j]['kind'] == 'style' and toks[j]['raw'][0] == 0x30:
                inner = ''.join(x['text'] if x['kind'] == 'glyph' else space for x in toks[i+1:j])
                raw = b''.join(x['raw'] for x in toks[i:j+1])
                item = dict(ph='{kw:%s}' % inner, raw=raw, kind='keyword', offset=pos)
                i = j + 1
        if item is None:
            item = dict(ph=_ph(t), raw=t['raw'], kind=t['kind'], offset=pos)
            i += 1
        pos += len(item['raw'])
        skeleton.append(item)
        segments.append(dict(raw=b'', text='', offset=pos))
    return dict(prefix=prefix, suffix=suffix, segments=segments, skeleton=skeleton, tokens=toks)


def reassemble(d):
    out = bytearray(d['prefix'])
    for n, seg in enumerate(d['segments']):
        out += seg['raw']
        if n < len(d['skeleton']):
            out += d['skeleton'][n]['raw']
    return bytes(out + d['suffix'])


def joined(d):
    parts = []
    for n, seg in enumerate(d['segments']):
        parts.append(seg['text'])
        if n < len(d['skeleton']):
            parts.append(d['skeleton'][n]['ph'])
    return ''.join(parts)


def pages(text):
    """Split placeholder text at page placeholders -> list of page strings."""
    return re.split(r'\{[kKpP]\}', text)


def _strip_ph(s):
    return PLACEHOLDER.sub(lambda m: m.group(0)[4:-1] if m.group(0).startswith('{kw:') else '', s)


def _visible_tail(s):
    s = _strip_ph(s).rstrip(' 　\n')
    return s


def punct_missing_pages(jp, ko):
    """Pages whose JP ends in ！/？ but the KO page does not end in !/?.

    Only compared when page counts match (otherwise skeleton_mismatch covers it).
    """
    jpp, kop = pages(jp), pages(ko)
    if len(jpp) != len(kop):
        return []
    out = []
    for n, (a, b) in enumerate(zip(jpp, kop)):
        ta, tb = _visible_tail(a), _visible_tail(b)
        if not ta or not tb:
            continue
        if ta[-1] in SENTENCE_END and tb[-1] not in SENTENCE_END:
            out.append(n)
    return out


# ---------------------------------------------------------------- inputs
def sha256(b):
    return hashlib.sha256(b).hexdigest()


def load_inputs(args):
    original = Path(args.original).read_bytes()
    rom = Path(args.rom).read_bytes()
    manifest = json.loads(Path(args.manifest).read_text())
    shas = dict(original_sha256=sha256(original), rom_sha256=sha256(rom),
                rom=str(Path(args.rom)), map=str(Path(args.map)), manifest=str(Path(args.manifest)),
                manifest_sha256=sha256(Path(args.manifest).read_bytes()),
                map_sha256=sha256(Path(args.map).read_bytes()))
    return original, rom, manifest, shas


def pinned_ranges():
    """[start,end) byte ranges fixed by the four relocation contracts."""
    import b830ac_contract as a
    import b82fac_contract as b
    import ec312c_contract as c
    import d821f0_contract as d
    rng = []
    rng.append((a.START, a.END, 'B830AC exact payload'))
    rng.append((a.SITE, a.SITE+4, 'B830AC pointer site'))
    rng.append((0xD8D998, 0xD8D998+len(a.CANDIDATE_TABLE), 'B830AC candidate table 0xD8D998'))
    rng.append((b.MESSAGE, b.END, 'B82FAC exact payload'))
    rng.append((b.SITE, b.SITE+4, 'B82FAC pointer site'))
    for k, v in b.PINS.items():
        rng.append((k, k+len(v[0]), 'B82FAC pin'))
    rng.append((c.MESSAGE, c.END, 'EC312C exact payload'))
    rng.append((c.SITE, c.SITE+4, 'EC312C pointer site'))
    for k, v in c.PINS.items():
        rng.append((k, k+len(v[0]), 'EC312C pin'))
    rng.append((d.MESSAGE, d.END, 'D821F0 exact payload'))
    rng.append((d.SITE, d.SITE+4, 'D821F0 pointer site'))
    for s, e, _ in d.CURRENT_PINS:
        rng.append((s, e, 'D821F0 source/consumer/Help-dictionary pin'))
    return sorted(set(rng))


def _hits(ranges, lo, hi):
    return sorted({f'{name} {s:#x}-{e:#x}' for s, e, name in ranges if s < hi and lo < e})


def canonical_term(entry):
    """Adopted Korean form of a common_terms entry, never its descriptive label.

    `term` may carry notes such as '캐논포 (キャノン砲; 캐넌 금지)'. Prefer `edit`,
    then a single-valued `current`, then `term` without its trailing note.
    """
    if entry.get('edit'):
        return entry['edit']
    current = (entry.get('current') or '').strip()
    if current and '/' not in current and '(' not in current:
        return current
    return re.sub(r'\s*[(（].*$', '', entry['term']).strip()


def load_glossary(original, rom, glyphs):
    pn = json.loads((ROOT/'data/proper_nouns.json').read_text())
    g = {}
    for cat in ('characters', 'nations', 'places'):
        for e in pn[cat]:
            g[e['ja']] = e['edit'] or e['ko']
    for e in pn['common_terms']:
        ja = e.get('ja_note') or ''
        if ja and '/' not in ja:
            g[ja] = canonical_term(e)
    # Part 2 CO name table (current KO decode). Drop entries whose KO collides.
    issues = []
    ptrs = struct.unpack_from('<%dI' % P2_COUNT, rom, P2_TABLE)
    optrs = struct.unpack_from('<%dI' % P2_COUNT, original, P2_TABLE)
    names = {}
    for co in range(P2_CO_COUNT):
        i = P2_CO_NAMES + co
        jp = _plain(original, optrs[i]-GBA, 'p2', None)
        ko = _plain(rom, ptrs[i]-GBA, 'p2', glyphs)
        names[co] = (jp, ko)
    by_ko = defaultdict(list)
    for co, (jp, ko) in names.items():
        by_ko[ko].append(jp)
    for co, (jp, ko) in names.items():
        if len(by_ko[ko]) > 1:
            issues.append(f'P2 CO name {jp} decodes to {ko!r} shared with {by_ko[ko]} (glossary entry withheld)')
            continue
        g.setdefault(jp, ko)
    g.setdefault('ゲームボーイウォーズ', '어드밴스 워즈')
    return g, names, issues


def _plain(rom, off, game, glyphs):
    raw = rom[off:rom.index(b'\0', off)+1]
    toks = tokenize(raw, game, glyphs if glyphs else _JG())
    return ''.join(t['text'] for t in toks if t['kind'] in ('glyph',)).strip()


class _JG:
    def text(self, pair):
        return pair.decode('cp932', 'replace')


# speaker register table (research_external.md §3; JP-version names only)
REGISTER = {
    'キャサリン': ('캐서린', '부드럽고 친근한 반말, 설명은 짧고 명료하게'),
    'ドミノ': ('도미노', '친근한 반말, 감탄사를 상황에 맞게'),
    'アスカ': ('아스카', '짧고 단호한 반말'),
    'ビリー': ('빌리', '연장자풍(자네), 느긋한 어휘·어미'),
    'ホイップ': ('호이프', '고풍스러운 자칭·과장된 선언, 장중한 어미는 드물게'),
    'イーグル': ('이글', '군인다운 간결한 반말'),
    'キクチヨ': ('키쿠치요', '연장자 발화, 느긋한 리듬'),
}


def p2_portraits(original):
    """message id -> set(portrait ids) from op38 record right before op19/1A."""
    out = defaultdict(set)
    for lo, hi in ((0x800000, 0x840000), (0xA3A8E4, 0xA3A8F4)):
        for site in range(lo, hi-15, 4):
            op, var, idx, fl = struct.unpack_from('<IIII', original, site)
            if op in (0x19, 0x1A) and var < 64 and idx < P2_COUNT and fl == 0 and site >= 16:
                p = struct.unpack_from('<4I', original, site-16)
                if p[0] == 0x38:
                    out[idx].add(p[2])
    for co in range(P2_CO_COUNT):
        for field in range(0x20, 0x2C, 2):
            idx = struct.unpack_from('<H', original, 0x9FC418+0x104*co+field)[0]
            out[idx].add(co)
        out[struct.unpack_from('<H', original, 0x9FC418+0x104*co+0x34)[0]].add(co)
    return out


def speaker_for(part, ids, portraits, co_names):
    if part == 1:
        return dict(name='unknown', jp=None, register='unknown — 문맥과 현재 KO 어미로 판단',
                    basis='Part 1 VM speaker opcode not mapped (plan §7)')
    ps = sorted({p for i in ids for p in portraits.get(i, ())})
    if not ps:
        return dict(name='unknown', jp=None, register='unknown — 문맥과 현재 KO 어미로 판단',
                    basis='no op38 portrait record / CO table reference')
    named = [p for p in ps if p < P2_CO_COUNT]
    if len(ps) == 1 and named:
        jp, ko = co_names[ps[0]]
        reg = REGISTER.get(jp, (ko, 'unknown — 원문 어미와 인물 관계로 판단'))[1]
        return dict(name=ko, jp=jp, portrait=ps[0], register=reg,
                    basis='portrait id == CO table index (op38 before op19); mapping unverified')
    if len(ps) == 1:
        return dict(name=f'portrait_{ps[0]}', jp=None, portrait=ps[0],
                    register='인물 미확인 — 원문 어미·문맥으로 판단(상관에게 하는 보고면 -습니다/-겠습니다)',
                    basis='portrait id >= 19 (generic or variant portrait); identity unverified')
    return dict(name='multiple', jp=None, portraits=ps, register='여러 화자 참조 — 문맥 판단',
                basis='message referenced with several portraits')


# carried items from T2 (T2_REPORT.md §1 「남은 것」, §7) + research_external §2
LEFTOVERS = [
    (1, 0xDC4670, None, '#2 남은 결함: 「잠수」 앞 여는 괄호 「 누락(원문 「もぐる」 인용)'),
    (1, 0xDA2B84, None, '#2 남은 결함: 「이보병을」 붙음, 「골라 줄 / 래?」 어절 중간 줄 나눔'),
    (2, None, 3070, '#6 남은 결함: 「공격 가능 곳은」 문법, 「２」 따옴표 누락'),
    (2, None, 77, 'msg77 남은 결함: 「선택한 종료」 — 원문 「終了」의 따옴표 「」 누락'),
    (2, 0xA1B408, None, '0xA1B408 「캣 님。」 오역 — 원문 すぐに撃退するの。(1353 앞 대사)'),
    (2, None, 1502, 'research_external §2: 「전장에 사정은 없다」 오역 — 원문 戦場で私情ははさまん(사적인 감정을 끼우지 않는다)'),
    (2, None, 909, 'research_external §2: 중복 표현 이력(T2 #4 수정됨) — 재작성 시 재발 금지'),
    (2, None, 3020, 'research_external §2: 중복 표현 이력(T2 #5 수정됨) — 재작성 시 재발 금지'),
]


def load_ledgers():
    own = defaultdict(set)
    sp = json.loads((ROOT/'data/dialogue_spacing_repairs.json').read_text())
    for m in sp.get('messages', []):
        own[int(m['source'], 16)].add('spacing_repairs')
    for m in json.loads((ROOT/'data/dialogue_layout_repairs.json').read_text()):
        own[int(m['source'], 16)].add('layout_repairs')
    seam = ROOT/'data/part2_seam_decisions.tsv'
    if seam.exists():
        for line in seam.read_text().splitlines()[1:]:
            f = line.split('\t')
            if f and f[0].startswith('0x'):
                own[int(f[0], 16)].add('seam_decisions')
    return own


def load_writes(map_path):
    """address -> list of (slot, ko, kind) text writers, in write order."""
    w = defaultdict(list)
    for e in json.loads(Path(map_path).read_text()):
        addr, slot, _l, _h, _f, ko, _lv, kind = e[:8]
        kind = str(kind)
        if kind.startswith(('repoint:', 'dialogue-spacing', 'spacing-retired')):
            w[('alloc', addr)].append(slot)
            continue
        w[addr].append((slot, ko, kind))
    return w


# ---------------------------------------------------------------- apply template
def load_template_api(original, rom, manifest, map_path):
    """Authoritative placeholder template from tools/dialogue_rewrite_apply.py (T3.2).

    Returns (callable(source)->(text, names) or raises, error class) or None when
    the apply module is absent/incompatible; export then falls back to its own
    lossless decomposition and marks `template: export-decomp`.
    """
    try:
        import dialogue_rewrite_apply as dra
        base = dra.Baseline(original, bytearray(rom), manifest, json.loads(Path(map_path).read_text()))
    except Exception as exc:  # module absent or API changed
        return None, f'{type(exc).__name__}: {exc}'

    def get(source):
        tpl = dra.template_for(base, source)
        return tpl.text, list(tpl.names)
    return (get, dra.RewriteError), None


# ---------------------------------------------------------------- collection
def collect(original, rom, manifest, map_path, punct_path=DEFAULT_PUNCT):
    glyphs = Glyphs(rom)
    inv = inventory(original, rom, manifest)
    msgs = {}
    for m in inv:
        if not m['script'] or m['pair_title']:
            continue
        part = 1 if m['game'] == 'p1' else 2
        key = (part, m['source'])
        if key in msgs:                      # P2 table aliases -> one message
            msgs[key]['sites'] = sorted(set(msgs[key]['sites']) | set(m['sites']))
            continue
        msgs[key] = dict(part=part, source=m['source'], target=m['target'], sites=list(m['sites']),
                         profile=m['profile'], relocated=m['relocated'])
    p2_ids = defaultdict(list)
    for i, p in enumerate(struct.unpack_from('<%dI' % P2_COUNT, original, P2_TABLE)):
        p2_ids[p-GBA].append(i)
    return glyphs, msgs, p2_ids


def build_messages(original, rom, manifest, map_path, punct_path=DEFAULT_PUNCT, only=None,
                   use_template=True):
    glyphs, msgs, p2_ids = collect(original, rom, manifest, map_path)
    tapi, terr = load_template_api(original, rom, manifest, map_path) if use_template else (None, 'disabled')
    writes = load_writes(map_path)
    bteam = {int(k, 16): v for k, v in
             json.loads((ROOT/'data/bteam_baseline.json').read_text())['overrides'].items()}
    gloss, co_names, gloss_issues = load_glossary(original, rom, glyphs)
    portraits = p2_portraits(original)
    pins = pinned_ranges()
    ledgers = load_ledgers()
    man_by = {int(e['msg'], 16): e for e in manifest}
    punct = defaultdict(list)
    if punct_path and Path(punct_path).exists():
        for it in json.loads(Path(punct_path).read_text())['items']:
            if it['status'] != 'fixed':
                punct[it['id']].append(it)
    spans = {}
    for key, m in msgs.items():
        src = m['source']
        spans[key] = (src, original.index(b'\0', src)+1)
    by_part = defaultdict(list)
    for (part, src), (s, e) in spans.items():
        by_part[part].append((s, e))
    out = {}
    for key in sorted(msgs):
        if only is not None and key not in only:
            continue
        m = msgs[key]
        part, src = key
        game = 'p1' if part == 1 else 'p2'
        s, e = spans[key]
        tgt = m['target']
        payload = rom[tgt:rom.index(b'\0', tgt)+1]
        rec = dict(id=f'0x{src:06x}', part=part, source=f'0x{src:06X}', target=f'0x{tgt:06X}',
                   ptr_sites=[f'0x{x:06X}' for x in m['sites']])
        ids = p2_ids.get(src, []) if part == 2 else []
        if part == 2:
            rec['msg_index'] = ids
        flags, notes, lock, noreloc = [], [], [], []
        name, px, rows_max = m['profile']
        rec['profile'] = name
        rec['window_px'] = px
        rec['max_cells_per_row'] = px // 8 if px else None
        rec['max_rows'] = rows_max
        # decomposition
        try:
            ko_d = decompose(payload, game, glyphs, ' ')
            jp_d = decompose(original[s:e], game, _JG(), '　')
        except ValueError as exc:
            rec.update(locked=True, lock_reasons=[f'parse_error: {exc}'], relocatable=False)
            out[key] = rec
            continue
        assert reassemble(ko_d) == payload and reassemble(jp_d) == original[s:e]
        rec['speaker'] = speaker_for(part, ids, portraits, co_names)
        rec['jp'] = joined(jp_d)
        rec['ko'] = joined(ko_d)
        rec['placeholders'] = [x['ph'] for x in ko_d['skeleton']]
        rec['template'] = 'export-decomp'
        if tapi is not None:
            get, err_cls = tapi
            try:
                text, names = get(src)
                rec['ko'], rec['placeholders'] = text, names
                rec['template'] = 'dialogue_rewrite_apply.template_for'
            except err_cls as exc:
                lock.append(f'apply_template: {exc.code}' + (f' {exc.detail}' if exc.detail else ''))
            except Exception as exc:  # unexpected apply-side failure: keep visible, lock
                lock.append(f'apply_template_error: {type(exc).__name__}: {exc}')
        jp_ph = [x['ph'] for x in jp_d['skeleton'] if x['kind'] not in ('format',)]
        ko_ph = [x['ph'] for x in ko_d['skeleton'] if x['kind'] not in ('format',)]
        norm = lambda L: [re.sub(r'^\{kw:.*\}$', '{kw}', p) for p in L]  # noqa: E731
        if norm(jp_ph) != norm(ko_ph):
            flags.append('skeleton_mismatch')
            notes.append('JP 제어 순서와 현재 KO 제어 순서가 다름 — placeholder 는 현재 KO 기준')
        if any(x['kind'] == 'unknown' for x in ko_d['skeleton']):
            lock.append('unknown_control')
        # rows (fragment rows inside the original span)
        rows = []
        rel = man_by.get(src)
        row_addrs = set(a for a in range(s, e) if a in writes)
        if rel and rel.get('source_spans'):
            row_addrs |= {int(a, 16) for a in rel['source_spans']}
        for a in sorted(row_addrs):
            ws = writes.get(a, [])
            slot = (rel or {}).get('source_spans', {}).get(f'0x{a:06X}') or (ws[-1][0] if ws else None)
            ko_row = next((w[1] for w in reversed(ws) if w[1] is not None), None)
            r = dict(addr=f'0x{a:08X}', offset=a-s, slot=slot, writer=ws[-1][2] if ws else None,
                     ko=ko_row, bteam=a in bteam)
            if a in bteam:
                r['bteam_baseline'] = bteam[a]
            rows.append(r)
        rec['rows'] = rows
        rec['bteam'] = any(r['bteam'] for r in rows)
        # segment ownership
        line_spans = None
        if tgt != src and rel and rel.get('status') == 'relocated' and int(rel['new_addr'], 16) == tgt:
            line_spans = {int(a, 16): v for a, v in rel.get('line_spans', {}).items()}

        def owner(off, length, base_src):
            hit = set()
            for o in range(off, off+max(length, 1)):
                if line_spans is not None:
                    for a, (st, ln) in line_spans.items():
                        if st <= o < st+ln:
                            hit.add(a)
                elif base_src is not None:
                    ab = base_src+o
                    for r in rows:
                        ra = int(r['addr'], 16)
                        if ra <= ab < ra+(r['slot'] or 0):
                            hit.add(ra)
            return [f'0x{a:08X}' for a in sorted(hit)]
        cur_base = src if tgt == src else None
        rec['decomp_ko'] = joined(ko_d)
        rec['segments'] = [dict(ko=seg['text'], raw=seg['raw'].hex(),
                                rows=owner(seg['offset'], len(seg['raw']), cur_base) if seg['raw'] else [])
                           for seg in ko_d['segments']]
        if tgt != src and line_spans is None:
            notes.append('재배치 후 spacing 단계에서 다시 옮겨져 행 소유 정보 없음(segments.rows 빈 값)')
        rec['skeleton'] = [dict(ph=x['ph'], raw=x['raw'].hex()) for x in ko_d['skeleton']]
        rec['prefix'] = ko_d['prefix'].hex()
        rec['suffix'] = ko_d['suffix'].hex()
        rec['payload_hex'] = payload.hex()
        rec['jp_payload_hex'] = original[s:e].hex()
        # per physical row widths (current KO)
        krows = []
        for row in physical_rows(ko_d['tokens']):
            adv = sum(t['advance'] for t in row['tokens'])
            choice = any(t['kind'] == 'choice' for t in row['tokens'])
            lim = px
            if lim is not None:
                if name in ('p1_portrait', 'p2_portrait') and row['line'] == 0 and row['end']['kind'] == 'newline':
                    lim += 8
                if name == 'p2_result_quote' and row['end']['raw'] in (b'k', b'K'):
                    lim -= 8
            used = adv + (64 if choice else 0)
            krows.append(dict(page=row['page'], line=row['line'], cells=math.ceil(used/8),
                              limit_cells=lim//8 if lim is not None else None))
        rec['ko_rows'] = krows
        rec['max_pages'] = None
        # capacity
        cur_len = len(payload)
        if tgt == src:
            cap, cap_src = e-s, 'original span (in place)'
        else:
            al = writes.get(('alloc', tgt))
            if al:
                cap, cap_src = max(al), 'allocation at target (integrity map)'
            else:
                cap, cap_src = cur_len, 'current payload length (allocation unknown)'
        rec['capacity'] = dict(bytes=cap, current_len=cur_len, slack=cap-cur_len, source=cap_src,
                               original_len=e-s)
        rec['relocated'] = tgt != src
        # locks / relocatability (decision_W3_arena.md)
        if name == 'p2_unverified_consumer':
            lock.append('unverified_consumer (docs/dialogue_layout.md; caller unknown)')
        if name == 'p2_link_state_dependent':
            lock.append('link_state_dependent (docs/dialogue_layout.md)')
        hits = set(_hits(pins, s, e))
        hits |= set(_hits(pins, tgt, tgt+cur_len))
        for site in m['sites']:
            hits |= set(_hits(pins, site, site+4))
        if hits:
            lock.extend(f'pin: {h}' for h in sorted(hits))
        inner = [o for o, oe in by_part[part] if s < o < e]
        outer = [o for o, oe in by_part[part] if o < s < oe]
        if inner:
            noreloc.append('interior reference: ' + ', '.join(f'0x{x:06X}' for x in sorted(inner)))
        if outer:
            noreloc.append('inside another message: ' + ', '.join(f'0x{x:06X}' for x in sorted(outer)))
        if not m['sites']:
            noreloc.append('no pointer sites')
        if rel and str(rel.get('status', '')).startswith('skip'):
            noreloc.append(f'legacy repoint {rel["status"]} (reference/structure not cleared)')
        if len(m['sites']) > 1:
            rec['multi_ref'] = True
            notes.append(f'포인터 {len(m["sites"])}곳 — 재배치 시 전부 이동해야 함')
        rec['locked'] = bool(lock)
        rec['lock_reasons'] = lock
        rec['relocatable'] = not lock and not noreloc
        rec['relocatable_reasons'] = noreloc + (['locked'] if lock else [])
        # flags
        if rec['bteam']:
            flags.append('bteam')
        pm = punct_missing_pages(rec['jp'], rec['decomp_ko'])
        if pm:
            flags.append('punct_missing')
            rec['punct_missing_pages'] = pm
        for i in ids:
            for it in punct.get(i, []):
                tag = f'punct_173:{it["status"]}'
                if tag not in flags:
                    flags.append(tag)
                notes.append(f'punct_173 page{it["page"]} ({it["status"]}): {it["reason"]}')
                if 'punct_missing' not in flags:
                    flags.append('punct_missing')
                pp = rec.setdefault('punct_missing_pages', [])
                if it['page'] not in pp:
                    pp.append(it['page'])
                    pp.sort()
        visible = _strip_ph(rec['decomp_ko'])
        if any(c in JP_PUNCT for c in visible):
            flags.append('jp_punct')
        if KANA.search(visible):
            flags.append('kana_residue')
        if not HANGUL.search(visible):
            flags.append('no_hangul')
        if re.search(r'(?<![\w])(\w{2,}) \1(?!\w)', visible):
            flags.append('dup_word')
        for lp, la, li, note in LEFTOVERS:
            if lp != part:
                continue
            if (la is not None and (la == src or s <= la < e)) or (li is not None and li in ids):
                flags.append('t2_leftover')
                notes.append(note)
        led = sorted(ledgers.get(src, ()))
        if led:
            rec['ledgers'] = led
        if any(w > (r['limit_cells'] or 999) for r in krows for w in (r['cells'],)):
            flags.append('width_over_now')
        rec['glossary'] = {ja: ko for ja, ko in sorted(gloss.items()) if ja in _strip_ph(rec['jp'])}
        choice = any(x['kind'] == 'choice' for x in ko_d['skeleton'])
        if choice:
            rec['glossary'].update({'はい': '예', 'いいえ': '아뇨'})
        rec['flags'] = sorted(set(flags), key=flags.index)
        rec['notes'] = notes
        out[key] = rec
    return out, gloss_issues


# ---------------------------------------------------------------- batch plan
P2_STRATA = (('prologue', 0, 62), ('tutorial', 62, 210), ('early', 210, 760), ('middle', 760, 1500),
             ('late', 1500, 2234), ('system', 2234, P2_COUNT))
P1_STRATA = (('system', ((0x000000, 0xD80000), (0xE20000, 0x1000000))), ('campaign', ((0xD80000, 0xE20000),)))
TARGET = 125
# plan T3.4: P2 ~25 batches, P1 ~15, pilot = P2 tutorial.1 (~100 -> tutorial split in two)
TARGETS = {(2, 'tutorial'): 75, (1, 'system'): 150, (1, 'campaign'): 150}


def _chunks(items, target=TARGET):
    if not items:
        return []
    n = max(1, round(len(items)/target))
    size = math.ceil(len(items)/n)
    return [items[i:i+size] for i in range(0, len(items), size)]


def coverage_gaps(original, msgs, p2_ids, map_path):
    """Translated rows inside dialogue ranges that no exported message covers.

    These have no native pointer reference in the inventory (e.g. inline P1
    command-stream text such as 0xDA2B84), so W3 cannot export or relocate them.
    """
    from bisect import bisect_right
    from dialogue_regions import PART1_DIALOG_RANGES, PART2_STORY_RANGES
    spans = sorted((s, original.index(b'\0', s)+1) for (_p, s) in msgs)

    def covered(a):
        i = bisect_right(spans, (a, 1 << 40)) - 1
        return i >= 0 and spans[i][0] <= a < spans[i][1]
    rows = sorted({e[0] for e in json.loads(Path(map_path).read_text())
                   if str(e[7]).startswith(('import', 'dialogue-override', 'script', 'known-story')) and e[5]})
    out = {}
    for name, ranges in (('p1', PART1_DIALOG_RANGES), ('p2', PART2_STORY_RANGES)):
        un = [a for a in rows if any(lo <= a < hi for lo, hi in ranges) and not covered(a)]
        out[name] = dict(count=len(un), rows=[f'0x{a:06X}' for a in un])
    ids = {i for v in p2_ids.values() for i in v}
    att = []
    for part, addr, idx, note in LEFTOVERS:
        hit = (addr is not None and covered(addr)) or (idx is not None and idx in ids)
        if not hit:
            att.append(dict(part=part, address=f'0x{addr:06X}' if addr else None, msg_index=idx, note=note,
                            status='not exported: no native pointer reference in inventory'))
    out['leftovers_not_exported'] = att
    out['_doc'] = ('rows written by translation import/overrides inside dialogue ranges but outside every '
                   'pointer-referenced message; W3 cannot export/relocate them (in-slot edits only, by another path)')
    return out


def make_plan(original, rom, manifest, map_path, shas):
    glyphs, msgs, p2_ids = collect(original, rom, manifest, map_path)
    batches = []
    p2 = sorted((min(p2_ids.get(src, [P2_COUNT])), src) for (part, src) in msgs if part == 2)
    for name, lo, hi in P2_STRATA:
        sel = [src for i, src in p2 if lo <= i < hi]
        for n, ch in enumerate(_chunks(sel, TARGETS.get((2, name), TARGET)), 1):
            batches.append(dict(id=f'p2-{name}.{n}', part=2, stratum=name,
                                ids=[f'0x{x:06x}' for x in ch],
                                msg_index_range=[min(p2_ids[ch[0]]), min(p2_ids[ch[-1]])]))
    p1 = sorted(src for (part, src) in msgs if part == 1)
    for name, ranges in P1_STRATA:
        sel = [x for x in p1 if any(lo <= x < hi for lo, hi in ranges)]
        for n, ch in enumerate(_chunks(sel, TARGETS.get((1, name), TARGET)), 1):
            batches.append(dict(id=f'p1-{name}.{n}', part=1, stratum=name,
                                ids=[f'0x{x:06x}' for x in ch],
                                address_range=[f'0x{ch[0]:06X}', f'0x{ch[-1]:06X}']))
    for b in batches:
        b['msg_count'] = len(b['ids'])
    assigned = {(b['part'], int(i, 16)) for b in batches for i in b['ids']}
    if assigned != set(msgs) or sum(b['msg_count'] for b in batches) != len(msgs):
        raise SystemExit(f'batch plan does not cover inventory exactly: {len(assigned)} vs {len(msgs)}')
    gaps = coverage_gaps(original, msgs, p2_ids, map_path)
    pilot = 'p2-tutorial.1'
    rest = [b['id'] for b in batches if b['id'] != pilot]
    waves = [[pilot]] + [rest[i:i+5] for i in range(0, len(rest), 5)]
    return dict(schema=SCHEMA+'/batches', inputs=shas, target_batch_size=TARGET,
                target_overrides={f'p{k[0]}-{k[1]}': v for k, v in sorted(TARGETS.items())},
                strata=dict(p2=[list(x) for x in P2_STRATA], p1=[[a, [[f'0x{lo:06X}', f'0x{hi:06X}'] for lo, hi in r]] for a, r in P1_STRATA]),
                pilot=pilot, waves=waves, coverage_gaps=gaps,
                totals=dict(p2=sum(b['msg_count'] for b in batches if b['part'] == 2),
                            p1=sum(b['msg_count'] for b in batches if b['part'] == 1),
                            p2_batches=sum(b['part'] == 2 for b in batches),
                            p1_batches=sum(b['part'] == 1 for b in batches)),
                batches=batches)


def export_batch(plan, batch_id, original, rom, manifest, map_path, shas, punct_path=DEFAULT_PUNCT,
                 built=None):
    b = next((x for x in plan['batches'] if x['id'] == batch_id), None)
    if b is None:
        raise SystemExit(f'unknown batch {batch_id}')
    only = {(b['part'], int(i, 16)) for i in b['ids']}
    recs, issues = built or build_messages(original, rom, manifest, map_path, punct_path, only=only)
    missing = only - set(recs)
    if missing:
        raise SystemExit(f'{batch_id}: messages not in current inventory: {sorted(missing)[:5]}')
    msgs = [recs[(b['part'], int(i, 16))] for i in b['ids']]
    counts = dict(messages=len(msgs), locked=sum(m.get('locked', False) for m in msgs),
                  relocatable=sum(m.get('relocatable', False) for m in msgs),
                  bteam=sum(m.get('bteam', False) for m in msgs),
                  flagged={f: sum(f in m.get('flags', []) for m in msgs)
                           for f in sorted({f for m in msgs for f in m.get('flags', [])})})
    counts['template'] = {t: sum(m.get('template') == t for m in msgs)
                          for t in sorted({m.get('template') for m in msgs if m.get('template')})}
    return dict(schema=SCHEMA, batch=batch_id, part=b['part'], stratum=b['stratum'],
                inputs=shas, brief='temp/fix_20261104/humanizer/BRIEF_rewrite.md',
                contract='ko/placeholders = dialogue_rewrite_apply.template_for (authoritative, when '
                         'template == that); decomp_ko/segments/skeleton = export lossless decomposition: '
                         'payload == prefix + seg0.raw + skeleton0.raw + ... + segN.raw + suffix. '
                         'ASCII space = rendered space (0x8140, or P1 rendered 0x20); padding omitted',
                glossary_issues=issues, counts=counts, messages=msgs)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('plan', 'export'))
    ap.add_argument('--rom', default=str(DEFAULT_ROM))
    ap.add_argument('--original', default=str(DEFAULT_ORIGINAL))
    ap.add_argument('--map', default=str(DEFAULT_MAP))
    ap.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    ap.add_argument('--punct', default=str(DEFAULT_PUNCT))
    ap.add_argument('--out', help='plan: output batches.json')
    ap.add_argument('--batch-plan', help='export: batches.json')
    ap.add_argument('--batch', help='export: batch id or "all"')
    ap.add_argument('--part', type=int, choices=(1, 2), help='export --batch all: restrict part')
    ap.add_argument('--out-dir', help='export: directory; writes <out-dir>/<batch>/in.json')
    a = ap.parse_args(argv)
    original, rom, manifest, shas = load_inputs(a)
    if a.cmd == 'plan':
        if not a.out:
            ap.error('plan needs --out')
        plan = make_plan(original, rom, manifest, a.map, shas)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(dump(plan))
        t = plan['totals']
        print(f'plan: p2 {t["p2"]} msgs / {t["p2_batches"]} batches, p1 {t["p1"]} msgs / {t["p1_batches"]} batches -> {a.out}')
        return 0
    if not (a.batch_plan and a.batch and a.out_dir):
        ap.error('export needs --batch-plan --batch --out-dir')
    plan = json.loads(Path(a.batch_plan).read_text())
    ids = [b['id'] for b in plan['batches'] if a.part in (None, b['part'])] if a.batch == 'all' else [a.batch]
    built = build_messages(original, rom, manifest, a.map, a.punct) if len(ids) > 1 else None
    for bid in ids:
        doc = export_batch(plan, bid, original, rom, manifest, a.map, shas, a.punct, built)
        d = Path(a.out_dir)/bid
        d.mkdir(parents=True, exist_ok=True)
        (d/'in.json').write_text(dump(doc))
        c = doc['counts']
        print(f'{bid}: {c["messages"]} msgs, locked {c["locked"]}, relocatable {c["relocatable"]}, '
              f'bteam {c["bteam"]}, flags {c["flagged"]} -> {d/"in.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
