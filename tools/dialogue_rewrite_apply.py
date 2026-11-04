#!/usr/bin/env python3
"""W3 dialogue rewrite overlay: reviewed whole-message rewrites, final text stage.

Two roles share one implementation so the builder and the offline tool cannot
disagree about a message:

* Offline (CLI): validate reviewed batch output against a *frozen baseline*
  candidate (a build whose ``data/dialogue_rewrites.json`` was empty), then
  record accepted messages in ``data/dialogue_rewrites.json`` and the B-team
  bulk ledger (checks 1-9 of plan_A T3.2).
* Builder (``apply_overlay``): after legacy relocation, spacing/layout and the
  late appends settle, rewrite each listed message once more. A message that
  fits its current *relocated* allocation is rewritten in place; every other
  message (including every native, never-relocated message) is written whole to
  a fresh overlay arena that starts after all settled allocations and ends
  before the sprite area at 0xAFF000. Old bytes stay as orphans. Pointer sites
  are reused from the validated relocation record (or proven complete for a
  native) and must point at the expected current allocation before any write.
  Pinned/contract-owned messages are refused and listed, never bypassed.

Placeholder template (authoritative; T3.1 export should call ``template_for``):
the active payload is tokenized with ``dialogue_pixel_layout.tokenize``.
Text tokens (Hangul, 0x81xx symbols, fullwidth alnum, renderable spaces) are
editable text; every other token becomes a placeholder that must survive in
the same order: ``{r}{R}`` row, ``{k}{K}{p}{P}`` page, ``{w}{W}`` wait,
``{s0}..{s3}`` style, ``{v:..}`` speed, ``{q:..}`` choice, ``{name}``,
``{icon:..}``, ``{arrow}``, ``{f:..}`` format, ``{kw:..}`` non-Korean glyph
(kana/kanji keyword) and ``{|}`` (zero-width seam between two source rows).
An unchanged text piece keeps its exact original bytes.
"""
from __future__ import annotations

import argparse
import array
import bisect
import collections
import copy
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

REWRITES = ROOT / 'data/dialogue_rewrites.json'
LEDGER = ROOT / 'data/bteam_approved_rewrites.json'
BASELINE = ROOT / 'data/bteam_baseline.json'
GLOSSARY = ROOT / 'data/proper_nouns.json'
SYLCODE = ROOT / 'data/syllable_to_code_2350.json'
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
FOUND = ROOT / 'data/game_wars_found_texts.csv'
GBA = 0x08000000
SCHEMA = 1
# Existing guarded dialogue pool; 0xAFF000.. belongs to relocated sprites.
ARENA_START, ARENA_END = 0xA3D000, 0xAFF000
EMPTY_DOC = ('W3 humanizer whole-message overlay. Applied by build_korean_full '
             'apply_dialogue_rewrites after spacing/layout/late appends, before final audits. '
             'Written only by tools/dialogue_rewrite_apply.py.')
SUPERSEDED_INTENT = 'dialogue-spacing-final-intent-superseded'
# Writers that ordinary relocation/spacing/layout use. Any other writer that
# overlaps a message's live payload is a bespoke contract: the message is locked.
STANDARD_ARENA_TAGS = ('repoint:', 'dialogue-spacing-final', 'dialogue-pixel-layout',
                       'spacing-retired-allocation')
LOCKING_NATIVE_TAGS = ('retained', 'bteam-round2', 'prologue', 'co-panel', 'colin',
                       'm23-prompt', 'contract')
# 2026-11-04 user decision (「이제 B팀 대사나 명칭을 존중할 필요없어」): B-team wording is
# no longer protected as policy. These writers only restore the B-team baseline
# wording, so they no longer lock a message; a changed B-team row still goes to
# the pinned ledger (qa_bteam_drift). Other bteam-round2 writers stay locked:
# residual/compact/composite/follow bytes are exact-byte checks in the builder.
BTEAM_POLICY_TAGS = ('bteam-round2-baseline', 'bteam-round2-relocated-baseline')
# Prologue envelopes are animation-bound; scrolling/unverified have no window.
LOCKED_SOURCES = {0xA01970: 'p2 prologue animation envelopes'}
EXTERNAL_ONLY_NAMES = ('앤디', '사미', '올라프', '그릿', '콜린', '사샤', '칸베이', '소냐',
                       '드레이크', '제스', '스텀', '플랙', '래시', '애더', '호크', '센세이',
                       '하치', '이글', '넬')
CTL_NAMES = {0x72: 'r', 0x52: 'R', 0x6B: 'k', 0x4B: 'K', 0x70: 'p', 0x50: 'P', 0x77: 'w', 0x57: 'W'}
PH_RE = re.compile(r'\{[^{}]*\}')
FOLD = {'！': '!', '？': '?', '、': ',', '。': '.', '，': ',', '．': '.', '　': ' ',
        '：': ':', '（': '(', '）': ')', '～': '~', '…': '...'}
FOLD.update({chr(0xFF10 + i): chr(0x30 + i) for i in range(10)})
FOLD.update({chr(0xFF21 + i): chr(0x41 + i) for i in range(26)})
FOLD.update({chr(0xFF41 + i): chr(0x61 + i) for i in range(26)})


class RewriteError(ValueError):
    """One message cannot be rewritten; ``code`` is stable for reports."""
    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}' if detail else code)
        self.code = code
        self.detail = detail


class OverlayError(ValueError):
    """The whole overlay is refused before any ROM/manifest/log mutation."""
    def __init__(self, problems):
        self.problems = problems
        super().__init__('dialogue rewrite overlay refused: ' + '; '.join(
            f'{p["source"]}:{p["code"]}' + (f' ({p["detail"]})' if p.get('detail') else '')
            for p in problems[:12]) + (f' (+{len(problems)-12} more)' if len(problems) > 12 else ''))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def key6(address):
    return f'0x{address:06X}'


def key8(address):
    return f'0x{address:08X}'


def fold(text):
    text = text.replace('・・・', '...')
    return ''.join(FOLD.get(c, c) for c in text)


def canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode('utf-8')


def empty_rewrites():
    return {'_doc': EMPTY_DOC, 'messages': {}, 'schema': SCHEMA}


def load_rewrites(path=REWRITES):
    """``{}`` and a schema-1 document with no messages are both the empty overlay."""
    path = Path(path)
    if not path.exists():
        return empty_rewrites()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data == {}:
        return empty_rewrites()
    if data.get('schema') != SCHEMA or not isinstance(data.get('messages'), dict):
        raise ValueError('unsupported dialogue rewrite overlay schema')
    for key, entry in data['messages'].items():
        if key != key6(int(key, 16)) or entry.get('source') != key:
            raise ValueError(f'non-canonical rewrite key {key}')
        for field in ('game', 'before_sha256', 'after_sha256', 'ko', 'batch', 'reviewed_by', 'review_ref'):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise ValueError(f'rewrite {key} missing {field}')
    return data


# --------------------------------------------------------------------------- pins

def pinned_ranges():
    """Byte ranges whose exact payload/pointer bytes a late contract pins."""
    import b82fac_contract as b82
    import ec312c_contract as ec3
    import d821f0_contract as d82
    import b830ac_contract as b83
    out = []
    for start, pair in b82.PINS.items():
        out.append((start, start + len(pair[-1]), 'B82FAC pin'))
    for start, pair in ec3.PINS.items():
        out.append((start, start + len(pair[-1]), 'EC312C pin'))
    for start, end, _ in d82.CURRENT_PINS:
        if start < 0xF00000:  # font/hook pins cannot hold a script message or pointer
            out.append((start, end, 'D821F0 pin'))
    out.append((0xD8D998, 0xD8D998 + len(b83.CANDIDATE_TABLE), 'B830AC candidate table'))
    out.append((b83.START, b83.END, 'B830AC source24'))
    out.append((b83.SITE, b83.SITE + 4, 'B830AC pointer'))
    for start, raw in b83.CALLERS.items():
        out.append((start, start + len(raw), 'B830AC caller'))
    out.append((b82.MESSAGE, b82.END, 'B82FAC native'))
    out.append((b82.APPEND, b82.APPEND + 52, 'B82FAC allocation'))
    out.append((ec3.MESSAGE, ec3.END, 'EC312C native'))
    out.append((ec3.APPEND, ec3.APPEND + 60, 'EC312C allocation'))
    out.append((d82.MESSAGE, d82.END, 'D821F0 native'))
    out.append((d82.APPEND, d82.APPEND + 40, 'D821F0 allocation'))
    out.extend(contract_message_ranges())
    return sorted(out)


# Builder post-overlay text contracts (build_korean_full re-runs each verify()
# after the W3 overlay; see its 'contracts_rechecked'). Each pins the complete
# bytes of its native source message, so any rewrite of that message fails the
# build. Spans come from the contract modules' own constants.
NATIVE_TEXT_CONTRACTS = ('secret_hire_dialogue', 'polite_choice_dialogue', 'polite_registration',
                         'red_unit_intro', 'protected_help_apology', 'map_design_intro',
                         'return_mode_question', 'part1_ship_help', 'part1_submarine_help',
                         'part1_m19_dialogue')


def _contract_spans(module):
    """[(start, end)] native source spans a builder text contract module pins."""
    name = module.__name__
    if name == 'polite_choice_dialogue' or name == 'protected_help_apology':
        return [(start, end) for start, end, _pointer, _digest in module.SPECS]
    if name == 'polite_registration':
        return [(row[0], row[3]) for row in module.ROWS]
    if name == 'return_mode_question':
        return [(start, end) for start, end, _pointer in module.ROWS]
    if name == 'part1_ship_help':
        return [(m['source'], m['end']) for m in module.MESSAGES]
    if name == 'part1_submarine_help':
        return [(module.SOURCE, module.END)]
    if name == 'map_design_intro':
        return [(module.START, module.END + 4)]  # SOURCE_SHA and verify() cover the 4 control bytes
    return [(module.START, module.END)]


def contract_message_ranges():
    """(start, end, label) native spans pinned by a builder post-overlay text contract."""
    import importlib
    out = []
    for name in NATIVE_TEXT_CONTRACTS:
        for start, end in _contract_spans(importlib.import_module(name)):
            if not 0 <= start < end:
                raise ValueError(f'{name}: bad contract span {start:#x}..{end:#x}')
            out.append((start, end, f'{name} contract'))
    return out


def reviewed_wide_rows():
    """{address: final fragment hex} of reviewed B-team rows wider than 44 half-cells.

    build_korean_full's B-team restoration stage calls
    dialogue_spacing.verify_reviewed_owner_bytes on these rows (listed in
    BTEAM_RESTORE_BASELINE_ROWS) and fails unless every final fragment keeps
    its reviewed bytes.
    """
    import build_korean_full as builder
    from dialogue_spacing import reviewed_bteam_rows, reviewed_bteam_half_cells
    return {a: list(r['final_fragment_hex']) for a, r in reviewed_bteam_rows().items()
            if a in builder.BTEAM_RESTORE_BASELINE_ROWS and reviewed_bteam_half_cells(a) > 44}


def reviewed_wide_row_issues(payload, fragments):
    """Reject issues for reviewed wide B-team rows whose final bytes a rewrite changes."""
    wide = reviewed_wide_rows()
    issues = []
    for key in sorted(fragments):
        wanted = wide.get(int(key, 16))
        if wanted is None:
            continue
        got = [bytes(payload[off:off + size]).hex() for off, size in fragments[key]]
        if got != wanted:
            issues.append(dict(code='pinned', severity='reject',
                               detail=f'{key}: reviewed B-team wide row exact bytes '
                                      '(dialogue_spacing.verify_reviewed_owner_bytes)'))
    return issues


def text_contract_sources():
    """{source: label} for Part 2 messages whose complete text a builder contract pins.

    build_korean_full re-runs these contracts after the overlay; a rewrite of one
    of these messages always fails the build, so it is refused here instead.
    """
    import part2_dialogue_layout_contracts as layout
    import part2_context_contract as context
    import part2_volcano_context as volcano
    out = {source: 'part2_dialogue_layout_contracts' for source in layout.CONTRACTS}
    out[context.SOURCE] = 'part2_context_contract'
    out.update({row[0]: 'part2_context_contract teacher' for row in context.TEACHER_SOURCES})
    out.update({row[0]: 'part2_volcano_context' for row in volcano.CASES})
    return out


_ROUND2_PINNED = None


def round2_pinned_rows():
    """Listed B-team round-2 residual rows and active byte pins (qa_bteam_drift ROM gate).

    classify_round2_issues byte-pins these rows' source slot and, when their
    message is relocated, the whole live message; a rewrite always fails that
    gate, so such a message is a technical pin (not a B-team wording lock).
    """
    global _ROUND2_PINNED
    if _ROUND2_PINNED is None:
        import csv
        with (ROOT / 'data/bteam_round2_residuals.tsv').open(encoding='utf-8', newline='') as stream:
            rows = {int(r['address'], 16) for r in csv.DictReader(stream, delimiter='\t')}
        pins = json.loads((ROOT / 'data/bteam_round2_active_pins.json').read_text(encoding='utf-8'))
        _ROUND2_PINNED = sorted(rows | {int(k, 16) for k in pins})
    return _ROUND2_PINNED


def exception_rows():
    """0x%08X B-team rows with any individually approved exception.

    qa_bteam_drift.ledger_errors refuses a ledger entry at every address in
    APPROVED_EXCEPTIONS or bteam_baseline ``_user_approved_exceptions``,
    including the renderer-only Part 2 prologue 。→． rows (e.g. 0xA01B08).
    W3 therefore cannot change such a row; an unchanged row adds no entry.
    """
    import qa_bteam_drift as drift
    recorded = json.loads(BASELINE.read_text(encoding='utf-8')).get('_user_approved_exceptions', {})
    return set(drift.APPROVED_EXCEPTIONS) | set(recorded)


def _intersections(ranges, lo, hi):
    return sorted({label for start, end, label in ranges if start < hi and lo < end})


# ----------------------------------------------------------------------- baseline

class Baseline:
    """Frozen state at the stage boundary: ROM, manifest and write log."""

    def __init__(self, original, rom, manifest, writes):
        from dialogue_pixel_layout import Glyphs, inventory
        self.original = original
        self.rom = rom
        self.manifest = manifest
        self.writes = writes
        self.glyphs = Glyphs(bytes(rom))
        self.messages = {m['source']: m for m in inventory(original, rom, manifest)}
        self.pins = pinned_ranges()
        self._hits = None
        self._referenced = None
        self._index = None

    # Aligned original pointer words to every inventoried source, and native
    # interior entries referenced by any aligned original word.
    def _scan(self):
        from dialogue_repoint import _line_index
        words = array.array('I')
        words.frombytes(bytes(self.original[:len(self.original) // 4 * 4]))
        if sys.byteorder != 'little':
            words.byteswap()
        sources = set(self.messages)
        entries = set(_line_index(FOUND)) | sources
        hits = collections.defaultdict(set)
        referenced = set()
        for i, value in enumerate(words):
            target = value - GBA
            if target in entries:
                referenced.add(target)
                if target in sources:
                    hits[target].add(i * 4)
        self._hits, self._referenced = hits, referenced

    @property
    def hits(self):
        if self._hits is None:
            self._scan()
        return self._hits

    @property
    def referenced(self):
        if self._referenced is None:
            self._scan()
        return self._referenced

    def overlapping_writes(self, lo, hi):
        if self._index is None:
            rows = sorted(((int(w[0]), int(w[0]) + int(w[1]), i) for i, w in enumerate(self.writes)
                           if int(w[1]) > 0), key=lambda r: r[0])
            self._index = ([r[0] for r in rows], rows, [r for r in rows if r[1] - r[0] > 4096])
        starts, rows, large = self._index
        found = set()
        k = bisect.bisect_left(starts, hi)
        j = k - 1
        while j >= 0 and rows[j][0] > lo - 4096:
            if rows[j][1] > lo:
                found.add(rows[j][2])
            j -= 1
        found.update(r[2] for r in large if r[0] < hi and lo < r[1])
        return sorted(found)

    def high_water(self):
        high = ARENA_START
        for m in self.manifest:
            if m.get('status') == 'relocated':
                high = max(high, int(m['new_addr'], 16) + int(m['new_len']))
        for w in self.writes:
            a, n = int(w[0]), int(w[1])
            if n and a < ARENA_END and a + n > ARENA_START:
                high = max(high, a + n)
        return high


# ----------------------------------------------------------------------- template

class Template:
    def __init__(self, m, pieces, phs, tail, owners, owner_texts, record, end, tail_owners=()):
        self.m = m
        self.tail_owners = tail_owners  # (offset in tail, size, owner) runs
        self.pieces = pieces      # n+1 dict(owner, raw, text)
        self.phs = phs            # n dict(name, raw, owner, kind)
        self.tail = tail          # terminator + bytes kept after it
        self.owners = owners      # key -> old fragments
        self.owner_texts = owner_texts
        self.record = record      # live manifest record or None for native
        self.end = end            # native message end (old_len bound)

    @property
    def text(self):
        out = []
        for i, piece in enumerate(self.pieces):
            out.append(fold(piece['text']))
            if i < len(self.phs):
                out.append(self.phs[i]['name'])
        return ''.join(out)

    @property
    def names(self):
        return [ph['name'] for ph in self.phs]


def _is_text_glyph(pair, glyphs):
    code = int.from_bytes(pair, 'big')
    if code in glyphs.codes:
        return True
    if pair[0] == 0x81:
        return True
    return pair[0] == 0x82 and 0x4F <= pair[1] <= 0x9A


def _placeholder(t, glyphs):
    raw, kind = t['raw'], t['kind']
    if kind in ('newline', 'page', 'wait'):
        return '{%s}' % CTL_NAMES[raw[0]]
    if kind == 'style':
        return '{s%d}' % (raw[0] - 0x30)
    if kind == 'name':
        return '{name}'
    if kind == 'icon':
        return '{arrow}' if raw == b'>' else '{icon:%s}' % raw.hex()
    if kind == 'choice':
        return '{q:%s}' % raw.hex()
    if kind == 'speed':
        return '{v:%s}' % raw.hex()
    if kind == 'format':
        return '{f:%s}' % raw.hex()
    if kind == 'glyph':
        return '{kw:%s}' % glyphs.text(raw)
    raise RewriteError('unknown_instruction', f'{kind} {raw.hex()}')


def _owners_for(base, m):
    """Live owner fragments (relative to the active payload) and their texts."""
    from repoint_source_rows import fragments
    record = m['relocated']
    if record:
        owners = {}
        for key in record['line_spans']:
            parts = fragments(record, key)
            owners[key] = [tuple(p) for p in parts]
        return owners, dict(record.get('source_texts', {})), record, None
    if m['target'] != m['source']:
        raise RewriteError('pointer_moved_unrecorded', 'native pointer target differs from source')
    from dialogue_spacing import _nonrelocated_owners
    try:
        owners, texts, spans = _nonrelocated_owners(m, base.rom, None, base.writes, base.original)
    except (ValueError, StopIteration, KeyError) as exc:
        raise RewriteError('native_owner_unproven', str(exc))
    owners = {k: [tuple(p) for p in v] for k, v in owners.items()}
    end = max(m['source'] + len(m['payload']), max(int(k, 16) + n for k, n in spans.items()))
    return owners, texts, None, (end, spans)


def lock_reason(base, m):
    """Why this message may not be rewritten here (None if eligible)."""
    if not m['script'] or m.get('pair_title'):
        return 'not_script'
    if m['source'] in LOCKED_SOURCES:
        return 'locked:' + LOCKED_SOURCES[m['source']]
    contract = text_contract_sources().get(m['source'])
    if contract:
        return 'pinned:' + contract
    name, width, rows = m['profile']
    if width is None or rows is None or name in ('p2_unverified_consumer', 'p2_link_state_dependent'):
        return 'consumer_geometry_unverified'
    if name == 'p1_editor_help':
        return 'pinned:D821F0 Help dictionary consumer'
    record = m['relocated']
    spans = [(m['target'], m['target'] + len(m['payload']))]
    native_end = m['source'] + (record['old_len'] if record else len(m['payload']))
    spans.append((m['source'], native_end))
    labels = set()
    for lo, hi in spans:
        labels.update(_intersections(base.pins, lo, hi))
    sites = [int(s, 16) for s in record['ptr_sites']] if record else list(m['sites'])
    for site in sites:
        labels.update(_intersections(base.pins, site, site + 4))
    if labels:
        return 'pinned:' + ','.join(sorted(labels))
    pinned = round2_pinned_rows()
    k = bisect.bisect_left(pinned, m['source'])
    if k < len(pinned) and pinned[k] < native_end:
        return 'pinned:B-team round-2 residual byte pin'
    for index in base.overlapping_writes(m['target'], m['target'] + len(m['payload'])):
        tag = str(base.writes[index][7])
        if tag in BTEAM_POLICY_TAGS:
            continue
        if record:
            if not tag.startswith(STANDARD_ARENA_TAGS):
                return 'contract_owned:' + tag
        elif any(word in tag for word in LOCKING_NATIVE_TAGS):
            return 'contract_owned:' + tag
    return None


def template_for(base, source):
    from dialogue_pixel_layout import tokenize
    m = base.messages.get(source)
    if m is None:
        raise RewriteError('unknown_message', key6(source))
    reason = lock_reason(base, m)
    if reason:
        code = reason.split(':', 1)[0]
        raise RewriteError(code, reason.split(':', 1)[1] if ':' in reason else '')
    owners, texts, record, native = _owners_for(base, m)
    try:
        tokens = tokenize(m['payload'], m['game'], base.glyphs)
    except ValueError as exc:
        raise RewriteError('unparsable_payload', str(exc))
    byte_owner = [None] * len(m['payload'])
    for key, parts in owners.items():
        for off, size in parts:
            for i in range(off, off + size):
                if byte_owner[i] not in (None, key):
                    raise RewriteError('owner_overlap', key)
                byte_owner[i] = key
    pieces, phs = [], []
    piece = dict(owner=None, raw=b'', text='', assigned=False)

    def close():
        pieces.append(dict(owner=piece['owner'], raw=piece['raw'], text=piece['text']))

    for t in tokens[:-1]:
        lo, hi = t['offset'], t['offset'] + len(t['raw'])
        ids = set(byte_owner[lo:hi])
        if len(ids) != 1:
            raise RewriteError('owner_cuts_token', f'+{lo:#x}')
        owner = ids.pop()
        kind = t['kind']
        text_like = kind in ('space', 'padding') or (kind == 'glyph' and _is_text_glyph(t['raw'], base.glyphs))
        if text_like:
            neutral = owner is None and kind in ('space', 'padding')
            if not neutral:
                if piece['assigned'] and piece['owner'] != owner:
                    close()
                    phs.append(dict(name='{|}', raw=b'', owner=None, kind='seam'))
                    piece = dict(owner=owner, raw=b'', text='', assigned=True)
                piece['owner'] = owner
                piece['assigned'] = True
            piece['raw'] += t['raw']
            piece['text'] += ' ' if kind == 'space' else ('' if kind == 'padding' else base.glyphs.text(t['raw']))
            continue
        close()
        phs.append(dict(name=_placeholder(t, base.glyphs), raw=t['raw'], owner=owner, kind=kind))
        piece = dict(owner=None, raw=b'', text='', assigned=False)
    close()
    tail_at = tokens[-1]['offset']
    tail = m['payload'][tail_at:]
    tail_owners = []
    for i, owner in enumerate(byte_owner[tail_at:]):
        if tail_owners and tail_owners[-1][2] == owner and sum(tail_owners[-1][:2]) == i:
            tail_owners[-1][1] += 1
        else:
            tail_owners.append([i, 1, owner])
    owner_texts = {}
    for key in owners:
        owner_texts[key] = _owner_text(pieces, phs, key)
    return Template(m, pieces, phs, tail, owners, owner_texts, record, native,
                    [tuple(r) for r in tail_owners])


def _owner_text(pieces, phs, key, texts=None):
    out = []
    for i, piece in enumerate(pieces):
        if piece['owner'] == key:
            out.append(fold(texts[i] if texts is not None else piece['text']))
        if i < len(phs) and phs[i]['kind'] in ('newline', 'page'):
            out.append(' ')
    return ' '.join(''.join(out).split())


# ------------------------------------------------------------------------ encode

def _encode_piece(text, encode, source):
    match = re.match(r'^(\s*)(.*?)(\s*)$', text, re.S)
    lead, core, trail = match.groups()
    raw = b'\x81\x40' if lead else b''
    if core:
        raw += encode(core, source)
    if trail:
        raw += b'\x81\x40'
    return raw


def render(tpl, ko, encode, unowned=None):
    """New payload, owner fragments/joiners and owner texts for ``ko``.

    A text segment owned by no source row (spacing-repair fragment, native
    leftover between rows) is fixed unless ``unowned`` is a list: then a change
    to a segment that already holds bytes is allowed and appended to it as
    ``dict(piece, before, after)``. Such a message must be written whole to the
    overlay arena (``plan_overlay`` never keeps it in its slot). Placeholders and
    controls stay fixed in order and count either way; inserting text into an
    empty unowned position is still refused.
    """
    names = PH_RE.findall(ko)
    if names != tpl.names:
        raise RewriteError('placeholder_mismatch', f'{len(names)} vs {len(tpl.names)}')
    texts = PH_RE.split(ko)
    if any('{' in t or '}' in t for t in texts):
        raise RewriteError('placeholder_mismatch', 'stray brace')
    source = tpl.m['source']
    out = bytearray()
    spans = []
    for i, piece in enumerate(tpl.pieces):
        new = texts[i]
        if fold(new) == fold(piece['text']):
            raw = piece['raw']
        else:
            if piece['owner'] is None:
                if unowned is None or not piece['raw']:
                    raise RewriteError('unowned_segment_changed', f'piece {i}')
                unowned.append(dict(piece=i, before=fold(piece['text']), after=new))
            try:
                raw = _encode_piece(new, encode, source)
            except (ValueError, KeyError) as exc:
                raise RewriteError('unencodable', str(exc))
            if tpl.m['game'] == 'p1':
                from dialogue_pixel_layout import tokenize
                try:
                    pieces = tokenize(raw + b'\0', 'p1')
                except ValueError as exc:
                    raise RewriteError('unencodable', str(exc))
                if any(t['raw'] == b'\x81\x44' for t in pieces):
                    raise RewriteError('blank_glyph', 'Part 1 0x8144 renders blank')
        spans.append((len(out), len(raw), piece['owner'], None))
        out += raw
        if i < len(tpl.phs):
            ph = tpl.phs[i]
            spans.append((len(out), len(ph['raw']), ph['owner'], ph['kind']))
            out += ph['raw']
    for off, size, owner in tpl.tail_owners:
        spans.append((len(out) + off, size, owner, 'tail'))
    out += tpl.tail
    fragments = collections.defaultdict(list)
    joiners = collections.defaultdict(list)
    gap_break = collections.defaultdict(bool)
    for off, size, owner, kind in spans:
        if owner is None:
            if kind in ('newline', 'page'):
                for key in fragments:
                    gap_break[key] = True
            continue
        if not size:
            continue
        runs = fragments[owner]
        if runs and runs[-1][0] + runs[-1][1] == off:
            runs[-1][1] += size
        else:
            if runs:
                joiners[owner].append('8140' if gap_break[owner] else '')
            runs.append([off, size])
        gap_break[owner] = False
    owner_texts = {key: _owner_text(tpl.pieces, tpl.phs, key, texts) for key in tpl.owners}
    for key in tpl.owners:
        if key not in fragments:
            raise RewriteError('owner_erased', key)
        if tpl.owner_texts.get(key) and not owner_texts[key]:
            raise RewriteError('owner_erased', key)
    return bytes(out), {k: [list(p) for p in v] for k, v in fragments.items()}, dict(joiners), owner_texts


def layout_issues(payload, m, glyphs):
    """The final builder pixel audit's row rules for one message."""
    from dialogue_pixel_layout import tokenize, physical_rows
    name, limit, max_rows = m['profile']
    issues = []
    try:
        tokens = tokenize(payload, m['game'], glyphs)
    except ValueError as exc:
        return [f'parse:{exc}'], 0
    widest = 0
    for row in physical_rows(tokens):
        row_limit = limit
        if name in ('p1_portrait', 'p2_portrait') and row['line'] == 0 and row['end']['kind'] == 'newline':
            row_limit += 8
        if name == 'p2_result_quote' and row['end']['raw'] in (b'k', b'K'):
            row_limit -= 8
        advance = ink = 0
        for t in row['tokens']:
            if t['kind'] in ('glyph', 'space') and len(t['raw']) == 2:
                try:
                    bitmap = glyphs.bitmap(t['raw'], m['game'])
                except ValueError as exc:
                    issues.append(f'glyph:{exc}')
                    bitmap = ()
                xs = [x for y in bitmap for x, v in enumerate(y) if v]
                if xs:
                    ink = max(ink, advance + max(xs) + 1)
            elif t['kind'] in ('name', 'icon'):
                ink = max(ink, advance + t['advance'])
            advance += t['advance']
        reserve = 64 if any(t['kind'] == 'choice' for t in row['tokens']) else 0
        used = max(advance, ink, advance + reserve)
        widest = max(widest, used)
        if used > row_limit:
            issues.append(f'overflow:p{row["page"]}l{row["line"]} {used}>{row_limit}px')
        if row['line'] >= max_rows:
            issues.append(f'row_overflow:p{row["page"]}l{row["line"]}>={max_rows}')
        caption = 40 if name == 'p1_co_bio' and row['line'] in (2, 3) else 24 if name == 'p1_co_break' and row['line'] == 0 else 0
        leading = 0
        for t in row['tokens']:
            if t['kind'] == 'space':
                leading += t['advance']
            elif t['advance']:
                break
        if leading < caption:
            issues.append(f'caption_overlap:p{row["page"]}l{row["line"]}')
    return issues, widest


def builder_encoder(syl_to_code):
    from build_korean_full import encode_required_full_fidelity

    def encode(text, address):
        return bytes(encode_required_full_fidelity(text, syl_to_code, collections.Counter(), address))
    return encode


def load_syl_to_code():
    return {s: int(c, 16) for s, c in json.loads(SYLCODE.read_text(encoding='utf-8')).items()}


# -------------------------------------------------------------------- overlay plan

def plan_overlay(base, rewrites, encode, *, arena_end=ARENA_END):
    """Validate every entry and compute every placement; no mutation."""
    problems, plans = [], []
    entries = sorted(rewrites.get('messages', {}).items(), key=lambda kv: int(kv[0], 16))
    for key, entry in entries:
        source = int(key, 16)
        try:
            tpl = template_for(base, source)
            m = tpl.m
            if m['game'] != entry['game']:
                raise RewriteError('game_mismatch', entry['game'])
            if sha(m['payload']) != entry['before_sha256']:
                raise RewriteError('stale_before', 'live payload differs from the reviewed baseline')
            unowned = []
            payload, fragments, joiners, owner_texts = render(tpl, entry['ko'], encode, unowned)
            if sha(payload) != entry['after_sha256']:
                raise RewriteError('stale_after', 'encoder output differs from the reviewed bytes')
            issues, _ = layout_issues(payload, m, base.glyphs)
            if issues:
                raise RewriteError('layout', ', '.join(issues[:4]))
            record = tpl.record
            if record:
                sites = sorted(int(s, 16) for s in record['ptr_sites'])
                excluded = {int(s, 16) for s in record.get('pointer_classification', {}).get('excluded_sites', [])}
                if base.hits.get(source, set()) - excluded != set(sites):
                    raise RewriteError('reference_unproven', 'relocation pointer coverage changed')
                old_len = int(record['old_len'])
                spans = dict(record['source_spans'])
            else:
                from dialogue_spacing import guard_new_relocation
                end, spans = tpl.end
                hits = {source: base.hits.get(source, set())}
                try:
                    guard_new_relocation(m, base.original, base.rom, hits, base.referenced, end)
                except ValueError as exc:
                    raise RewriteError('reference_unproven', str(exc))
                sites = sorted(m['sites'])
                old_len = end - source
            for site in sites:
                if struct.unpack_from('<I', base.rom, site)[0] != GBA + m['target']:
                    raise RewriteError('stale_pointer', key6(site))
            # Changed unowned text is only allowed in a whole-message arena write.
            same_slot = bool(record) and len(payload) <= len(m['payload']) and not unowned
            plans.append(dict(key=key, entry=entry, tpl=tpl, payload=payload, fragments=fragments,
                              joiners=joiners, owner_texts=owner_texts, sites=sites, old_len=old_len,
                              spans=spans, same_slot=same_slot))
        except RewriteError as exc:
            problems.append(dict(source=key, code=exc.code, detail=exc.detail))
    if problems:
        raise OverlayError(problems)
    start = (base.high_water() + 3) & ~3
    free = start
    for plan in plans:
        if plan['same_slot']:
            plan['target'] = plan['tpl'].m['target']
            continue
        plan['target'] = free
        free = (free + len(plan['payload']) + 3) & ~3
    used_end = max([start] + [p['target'] + len(p['payload']) for p in plans if not p['same_slot']])
    if used_end > arena_end:
        need = sum((len(p['payload']) + 3) & ~3 for p in plans if not p['same_slot'])
        raise OverlayError([dict(source='*', code='capacity',
                                 detail=f'need {need}B from {start:#x}, available {arena_end - start}B before {arena_end:#x}')])
    for plan in plans:
        if plan['same_slot']:
            continue
        lo, hi = plan['target'], plan['target'] + len(plan['payload'])
        if (any(b != 0xFF for b in base.original[lo:hi]) or any(b != 0xFF for b in base.rom[lo:hi])
                or base.overlapping_writes(lo, hi)):
            raise OverlayError([dict(source=plan['key'], code='arena_occupied', detail=f'{lo:#x}..{hi:#x}')])
    return dict(plans=plans, arena_start=start, arena_used_end=used_end)


def apply_overlay(original, rom, manifest, writes, rewrites, encode, *, arena_end=ARENA_END, base=None):
    """Builder stage. Empty overlay: returns zero stats and touches nothing."""
    stats = dict(messages=0, rows=0, bteam_rows=0, repointed=0, same_slot=0,
                 arena_start=None, arena_used_end=None, superseded_intents=0)
    if not rewrites.get('messages'):
        return stats
    base = base or Baseline(original, rom, manifest, writes)
    plan = plan_overlay(base, rewrites, encode, arena_end=arena_end)
    try:
        bteam = set(json.loads(BASELINE.read_text(encoding='utf-8')).get('overrides', {}))
    except OSError:
        bteam = set()
    index_by_msg = {}
    for i, rec in enumerate(manifest):
        index_by_msg.setdefault(int(rec['msg'], 16), []).append(i)
    for p in plan['plans']:
        tpl, m, entry = p['tpl'], p['tpl'].m, p['entry']
        source, target, payload = m['source'], p['target'], p['payload']
        old_target, old_size = m['target'], len(m['payload'])
        binding_tag = f'repoint:0x{source:06X}'
        updated = copy.deepcopy(tpl.record) if tpl.record else dict(
            msg=key6(source), status='relocated', ptr_off=key6(min(p['sites'])), old_len=p['old_len'],
            lines=len(tpl.owners), fixed=[], layout_controls={}, source_spans=p['spans'],
            source_texts={}, ptr_sites=[key6(s) for s in p['sites']])
        updated.update(new_addr=key6(target), new_len=len(payload),
                       line_spans={k: v[0] for k, v in p['fragments'].items()},
                       source_line_fragments=p['fragments'],
                       source_fragment_joiners={k: p['joiners'].get(k, []) for k in p['fragments']},
                       source_texts=dict(p['owner_texts']))
        updated['rewrite'] = dict(batch=entry['batch'], review_ref=entry['review_ref'],
                                  before_sha256=entry['before_sha256'], after_sha256=entry['after_sha256'],
                                  previous_target=key6(old_target), previous_len=old_size,
                                  previous_status='relocated' if tpl.record else 'native')
        if tpl.record and old_target != target:
            writes.append([old_target, old_size, old_size, bytes(rom[old_target:old_target + old_size]).hex(),
                           None, None, None, 'dialogue-rewrite-retired-allocation'])
        binding = [target, len(payload), len(payload), '', None, None, None, binding_tag,
                   dict(source_spans=updated['source_spans'], source=source, old_len=updated['old_len'],
                        ptr_sites=[int(s, 16) for s in updated['ptr_sites']])]
        bound = [i for i, w in enumerate(writes) if w[7] == binding_tag]
        if tpl.record:
            if len(bound) != 1:
                raise AssertionError(f'missing/duplicate live relocation binding {binding_tag}')
            writes[bound[0]] = binding
            rec_index = [i for i in index_by_msg.get(source, []) if manifest[i].get('status') == 'relocated']
            if len(rec_index) != 1:
                raise AssertionError(f'missing/duplicate relocation record {key6(source)}')
            manifest[rec_index[0]].clear()
            manifest[rec_index[0]].update(updated)
        else:
            if bound:
                raise AssertionError(f'unexpected relocation binding {binding_tag}')
            prior = index_by_msg.get(source, [])
            if prior:  # supersede the inactive skip record instead of adding a second record
                updated['rewrite']['previous_status'] = manifest[prior[0]].get('status')
                manifest[prior[0]].clear()
                manifest[prior[0]].update(updated)
                for i in prior[1:]:
                    manifest[i]['status'] = 'superseded_by_rewrite'
            else:
                manifest.append(updated)
            writes.append(binding)
        rom[target:target + len(payload)] = payload
        writes.append([target, len(payload), len(payload), payload.hex(), None, None, None,
                       'dialogue-rewrite-final'])
        if target != old_target:
            for site in p['sites']:
                raw = struct.pack('<I', GBA + target)
                rom[site:site + 4] = raw
                writes.append([site, 4, 4, raw.hex(), None, None, None, 'dialogue-rewrite-pointer'])
            stats['repointed'] += 1
        else:
            stats['same_slot'] += 1
        owner_addresses = {int(k, 16) for k in p['fragments']}
        for w in writes:
            if (w[7] == 'dialogue-spacing-final-intent' and len(w) > 8
                    and w[8].get('source_address') in owner_addresses):
                w[7] = SUPERSEDED_INTENT
                w[8]['superseded_by'] = f'dialogue-rewrite:{key6(source)}'
                stats['superseded_intents'] += 1
        stats['messages'] += 1
        stats['rows'] += len(p['fragments'])
        stats['bteam_rows'] += sum(key8(int(k, 16)) in bteam for k in p['fragments'])
    from qa_dialogue_jamming import validate_manifest
    validate_manifest(rom, manifest, original, writes)
    stats['arena_start'] = key6(plan['arena_start'])
    stats['arena_used_end'] = key6(plan['arena_used_end'])
    return stats


# ------------------------------------------------------------------ validation 1-9

def _jp_text(original, source):
    from dialogue_pixel_layout import tokenize
    end = original.find(b'\0', source) + 1
    out = []
    try:
        for t in tokenize(bytes(original[source:end]), 'p2' if source < 0xB00000 else 'p1'):
            if t['kind'] in ('glyph', 'space'):
                out.append(t['raw'].decode('shift_jis', 'replace'))
    except ValueError:
        return ''
    return ''.join(out)


def glossary_terms():
    data = json.loads(GLOSSARY.read_text(encoding='utf-8'))
    terms = []
    for group in ('characters', 'nations', 'places'):
        for row in data.get(group, []):
            ko = row.get('edit') or row.get('ko')
            if row.get('ja') and ko:
                terms.append((row['ja'], ko))
    return terms


def _plain(text):
    return PH_RE.sub(' ', text)


def _norm_external(text):
    return re.sub(r'[^0-9A-Za-z가-힣]', '', _plain(fold(text)))


def external_index(paths):
    messages, sentences = set(), set()
    for path in paths or ():
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        rows = data if isinstance(data, list) else data.get('messages', [])
        for row in rows:
            text = row.get('text', '') if isinstance(row, dict) else str(row)
            norm = _norm_external(text)
            if len(norm) >= 4:
                messages.add(norm)
            for part in re.split(r'[.!?\n]+', fold(text)):
                norm = _norm_external(part)
                if len(norm) >= 8:
                    sentences.add(norm)
    return messages, sentences


def external_matches(ko, index):
    messages, sentences = index
    hits = []
    norm = _norm_external(ko)
    if norm and norm in messages:
        hits.append(norm)
    for part in re.split(r'[.!?\n]+', PH_RE.sub('', fold(ko))):
        n = _norm_external(part)
        if len(n) >= 8 and n in sentences and n not in hits:
            hits.append(n)
    return hits


# Orchestrator decision 2026-11-04 (W3 wave 2): an exact external match longer
# than this many normalized characters (Hangul/alnum, no spaces or punctuation)
# is a copy and is refused. A shorter one is a common phrase that independent
# workers (who never saw the external text) can produce; it is admitted and
# listed with admitted_by "+short_common_phrase".
EXTERNAL_COPY_MAX_COMMON = 10


def external_issues(ko, index):
    """Reject long exact external matches; note short common phrases."""
    issues = []
    for hit in external_matches(ko, index):
        if len(hit) > EXTERNAL_COPY_MAX_COMMON:
            issues.append(dict(code='external_copy', severity='reject', detail=f'{len(hit)}:{hit[:24]}'))
        else:
            issues.append(dict(code='external_short_match', severity='note', detail=f'{len(hit)}:{hit}'))
    return issues


def validate_message(tpl, ko, *, encode, syl_to_code, glossary, external, jp, current_ko, glyphs):
    """Checks 1-7. Returns (issues, payload, fragments, joiners, owner_texts)."""
    from build_korean_full import normalize_korean_terms
    import lint_translation
    issues = []

    def reject(code, detail=''):
        issues.append(dict(code=code, severity='reject', detail=detail))
    plain = _plain(ko)
    bad = sorted({c for c in plain if '가' <= c <= '힣' and c not in syl_to_code})
    if bad:  # 2
        reject('outside_2350', ''.join(bad))
    compact = ''.join(plain.split())
    compact_now = ''.join(_plain(current_ko).split())
    for ja, term in glossary:  # 3
        t = ''.join(term.split())
        if ja in jp and t in compact_now and t not in compact:
            reject('glossary_dropped', f'{ja}->{term}')
    for name in EXTERNAL_ONLY_NAMES:
        if name in compact and name not in compact_now:
            reject('external_name', name)
    latin = set(re.findall(r'[A-Za-z]+', plain)) - set(re.findall(r'[A-Za-z]+', fold(current_ko) + fold(jp)))
    if latin:
        reject('latin_text', ','.join(sorted(latin)))
    issues.extend(external_issues(ko, external))  # 5
    if normalize_korean_terms(plain) != plain:  # 6
        reject('term_conflict', 'normalize_korean_terms changes the text')
    if any(word in plain for word in ('게임보이 워즈', '게임보이워즈')):
        reject('term_conflict', '어드밴스 워즈 표기')
    if any(ph.startswith('{q:') for ph in tpl.names) and re.search('아니오|아니요', plain):
        reject('term_conflict', '예/아뇨 표기')
    sylset = set(syl_to_code)
    for severity, rule, message in lint_translation.check(  # 7
            key8(tpl.m['source']), jp, plain, sylset, None, syl_to_code, skip_byte_budget=True):
        if severity == 'error':
            reject('lint_' + rule, message)
        elif severity == 'warning':
            issues.append(dict(code='lint_' + rule, severity='warning', detail=message))
    payload = fragments = joiners = owner_texts = None
    unowned = []
    try:  # 1 (+ encoding)
        payload, fragments, joiners, owner_texts = render(tpl, ko, encode, unowned)
    except RewriteError as exc:
        reject(exc.code, exc.detail)
    for change in unowned:  # listed in diff.json; forces an arena write
        issues.append(dict(code='unowned_segment_overlay', severity='note',
                           detail=f'piece {change["piece"]}: {change["before"]!r} -> {change["after"]!r}'))
    if payload is not None:  # 4
        layout, width = layout_issues(payload, tpl.m, glyphs)
        for item in layout:
            reject('width', item)
    return issues, payload, fragments, joiners, owner_texts


def row_display(payload, fragments, joiners, key):
    """Text qa_bteam_drift.check_rom decodes for one owner row of ``payload``.

    The overlay record written by ``apply_overlay`` maps the row to exactly
    these fragments/joiners, so this is the final-ROM reading of that row.
    """
    import qa_bteam_drift as drift
    record = dict(msg='0x000000', new_addr='0x000000', new_len=len(payload),
                  line_spans={k: list(v[0]) for k, v in fragments.items()},
                  source_line_fragments=fragments,
                  source_fragment_joiners={k: joiners.get(k, []) for k in fragments})
    address = int(key, 16)
    raw = drift.source_row_bytes(payload, record, key).replace(b'\x72\x0a\x09', b'\x81\x40')
    raw = drift.script_format_bytes(raw, address)
    if address in (0xA2AA08, 0xA2BC3C):
        raw = drift.co_breaks_as_spaces(raw)
    return drift.decode_enc(raw, drift.load_syl()).rstrip(' \u3000')


def displayed_row_text(authored, actual, address, baseline=None):
    """Owner/ledger text of a B-team row that check_rom reads as ``actual``.

    Prefers the B-team baseline (no change), then the authored text. Otherwise
    the authored text is aligned to the display and only two writer facts are
    absorbed: a fullwidth space the encoder keeps (a piece's leading space,
    e.g. after {W}) and a glyph form that folds to the authored punctuation
    (e.g. '.' shipped as 。 where display_equivalent predicts ．). Anything
    else returns None: the row would fail the final B-team ROM gate.
    """
    from qa_bteam_drift import display_equivalent as shown
    if baseline is not None and shown(baseline, address) == actual:
        return baseline
    authored = authored.rstrip()
    if shown(authored, address) == actual:
        return authored
    out, pos = [], 0
    tokens = re.findall(r'\.\.\.|.', authored, re.S)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        want = shown(token, address)
        seg = actual[pos:pos + len(want)]
        if seg == want:
            out.append(token)
        elif actual[pos:pos + 1] == '\u3000' and not token.isspace():
            out.append(' ')
            pos += 1
            continue
        elif (seg and not re.search('[가-힣0-9A-Za-z]', token) and fold(seg) == fold(token)
                and shown(seg, address) == seg):
            out.append(seg)
        else:
            return None
        pos += len(want)
        i += 1
    if actual[pos:] or shown(''.join(out), address) != actual:
        return None
    return ''.join(out)


def bteam_payload_issue(payload, fragments, key):
    """The builder's final B-team restoration check for one relocated row, or None.

    build_korean_full validates every BTEAM_RESTORE_BASELINE_ROWS row (that is
    not a listed residual) fragment by fragment after the overlay: renderer
    bytes only, at most 44 half-cells. Run the same check here so a rewrite of
    such a row is refused instead of failing the build.
    """
    import build_korean_full as builder
    from qa_integrity_map import load_syl
    address = int(key, 16)
    if address not in builder.BTEAM_RESTORE_BASELINE_ROWS or address in builder.BTEAM_ROUND2_RESIDUALS:
        return None
    if address in builder.BTEAM_COMPACT_VERIFIED_ROWS:
        return 'compact B-team row (verified writer bytes only)'
    codes = load_syl()
    for off, size in fragments[key]:
        try:
            builder.validate_bteam_payload(payload[off:off + size], codes, address)
        except AssertionError as exc:
            return str(exc)
    return None


def bteam_owner_texts(payload, fragments, joiners, owner_texts, bteam):
    """(owner_texts, issues) with every B-team row text equal to its ROM display."""
    texts, issues = dict(owner_texts), []
    for key in sorted(owner_texts):
        address = key8(int(key, 16))
        if address not in bteam or key not in fragments:
            continue
        problem = bteam_payload_issue(payload, fragments, key)
        if problem:
            issues.append(dict(code='bteam_payload', severity='reject', detail=f'{key}: {problem}'))
            continue
        try:
            actual = row_display(payload, fragments, joiners, key)
        except ValueError as exc:
            issues.append(dict(code='bteam_display_mismatch', severity='reject', detail=f'{key}: {exc}'))
            continue
        text = displayed_row_text(owner_texts[key], actual, int(key, 16), bteam[address])
        if text is not None and text != bteam[address] and address in exception_rows():
            issues.append(dict(code='bteam_exception_row', severity='reject',
                               detail=f'{key}: user-approved exception row ({address}); '
                                      'qa_bteam_drift refuses a ledger entry here'))
        elif text is None:
            issues.append(dict(code='bteam_display_mismatch', severity='reject',
                               detail=f'{key}: text {owner_texts[key]!r} vs ROM {actual!r}'))
        else:
            texts[key] = text
    return texts, issues


REVIEW_BANNER = re.compile(r'\S+\s+(\w+)\s+review:\s*model=(\S+)\s+effort=(\S+)')


def batch_reviewer(batch_dir, review):
    """Actual reviewer: review.json ``reviewed_by``, else the review.err banner.

    The harness review banner (``▶ codex review: model=gpt-6-astra effort=medium
    ...``) names the model that really reviewed the batch; a placeholder such as
    ``harness-review/unknown/unknown`` is not provenance. '' when unknown.
    """
    value = str(review.get('reviewed_by') or '')
    if value and 'unknown' not in value.lower():
        return value
    err = Path(batch_dir) / 'review.err'
    if err.exists():
        match = REVIEW_BANNER.search(err.read_text(encoding='utf-8', errors='replace'))
        if match:
            return ' '.join(match.groups())
    return ''


REVIEW_FLAG_NAMES = ('punct_missing', 't2_leftover', 'skeleton_mismatch', 'kana_residue', 'no_hangul')


def _visible_len(text):
    return len(re.sub(r'\s', '', _plain(text)))


def review_flags(tpl, ko, meta, jp, glossary, bteam, flagged_all, issues):
    """Messages BRIEF_review requires an explicit verdict for (never batch-admitted)."""
    flags = []
    if tpl.m['source'] in flagged_all:
        flags.append('review_flagged_all')
    if meta.get('bteam') or any(key8(int(k, 16)) in bteam for k in tpl.owners):
        flags.append('bteam')
    for flag in meta.get('flags', []):
        if flag in REVIEW_FLAG_NAMES or str(flag).startswith('punct_173'):
            flags.append(str(flag))
    before, after = _visible_len(tpl.text), _visible_len(ko)
    if before and (after >= 1.5 * before or after * 1.5 <= before):
        flags.append('length_1.5x')
    compact = ''.join(_plain(ko).split())
    if any(ja in jp and ''.join(term.split()) not in compact for ja, term in glossary):
        flags.append('glossary_warning')
    if any(i['severity'] == 'warning' for i in issues):
        flags.append('validator_warning')
    if meta.get('locked'):
        flags.append('locked')
    return flags


def admission(verdict, flags, batch_verdict):
    """(admitted, rule). Explicit accept, or un-sampled+unflagged under batch pass."""
    value = verdict.get('verdict')
    if value == 'accept':
        return True, 'explicit_accept'
    if value in ('revert', 'rewrite_needed'):
        return False, 'review_' + value
    if value is not None:
        return False, f'review_unknown:{value}'
    if flags:
        return False, 'flagged_without_verdict:' + ','.join(flags)
    if batch_verdict == 'pass':
        return True, 'batch_pass_unsampled'
    return False, f'unsampled_batch_verdict:{batch_verdict}'


# ------------------------------------------------------------------------- CLI

def ledger_rows(entry, bteam):
    """{0x%08X address: to} for the B-team rows an accepted rewrite really changes.

    A row whose rewritten owner text equals its baseline text is not a change:
    qa_bteam_drift sees no drift there, and a from == to ledger entry is a
    HARD-FAIL, so it never enters the ledger.
    """
    out = {}
    exceptions = exception_rows()
    for row_key in entry['bteam_rows']:
        addr = key8(int(row_key, 16))
        to = entry['owner_texts'][row_key]
        if to != bteam[addr]:
            if addr in exceptions:  # bteam_owner_texts rejects these first
                raise ValueError(f'{addr}: ledger row on a user-approved exception')
            out[addr] = to
    return out


def _load_baseline(args):
    original = ORIGINAL.read_bytes()
    rom = bytearray(Path(args.rom).read_bytes())
    receipt = Path(str(args.rom) + '.build.json')
    if receipt.exists():
        files = (json.loads(receipt.read_text()).get('inputs_after') or {}).get('files', {})
        recorded = files.get('data/dialogue_rewrites.json')
        if recorded not in (None, sha(canonical_bytes(empty_rewrites()))):
            raise SystemExit('baseline ROM was built with a non-empty rewrite overlay; use the frozen W2 baseline')
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    writes = json.loads(Path(args.map).read_text(encoding='utf-8'))
    return Baseline(original, rom, manifest, writes)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else None


def cmd_apply(args):
    base = _load_baseline(args)
    syl = load_syl_to_code()
    encode = builder_encoder(syl)
    glossary = glossary_terms()
    external = external_index(args.external)
    rewrites = load_rewrites(args.rewrites)
    ledger_path = Path(args.ledger)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    bteam = baseline.get('overrides', {})
    log, diff, owned = [], [], []
    accepted = {}
    excluded = {}
    for item in args.exclude or ():
        source, _, why = item.partition(':')
        excluded[int(source, 16)] = why or 'excluded'
    for batch_dir in map(Path, args.batches):
        out = _read_json(batch_dir / 'out.json') or {}
        review = _read_json(batch_dir / 'review.json') or {}
        inp = _read_json(batch_dir / 'in.json') or {}
        batch = out.get('batch') or review.get('batch') or batch_dir.name
        reviewer = batch_reviewer(batch_dir, review)
        review_ref = str(batch_dir / 'review.json')
        meta = {int(m['id'], 16): m for m in inp.get('messages', [])}
        batch_verdict = (review.get('summary') or {}).get('batch_verdict')
        flagged_all = {int(i, 16) for i in review.get('flagged_all', [])}
        for msg in out.get('messages', []):
            source = int(msg['id'], 16)
            row = dict(batch=batch, id=key6(source), status='rejected', issues=[])
            if source in excluded and not msg.get('unchanged'):
                row['issues'].append(dict(code='wave_excluded', severity='reject', detail=excluded[source]))
                log.append(row)
                continue
            verdict = (review.get('verdicts', {}).get(msg['id'])
                       or review.get('verdicts', {}).get(key6(source).lower()) or {})
            try:
                tpl = template_for(base, source)
            except RewriteError as exc:
                row['issues'].append(dict(code=exc.code, severity='reject', detail=exc.detail))
                log.append(row)
                continue
            ko = msg.get('ko', '')
            if msg.get('unchanged') or fold(ko) == fold(tpl.text):
                row['status'] = 'unchanged'
                log.append(row)
                continue
            if not reviewer:
                row['issues'].append(dict(code='review_meta_missing', severity='reject', detail='reviewed_by'))
                log.append(row)
                continue
            jp = meta.get(source, {}).get('jp') or _jp_text(base.original, source)
            issues, payload, fragments, joiners, owner_texts = validate_message(
                tpl, ko, encode=encode, syl_to_code=syl, glossary=glossary, external=external,
                jp=jp, current_ko=tpl.text, glyphs=base.glyphs)
            if payload is not None:
                issues.extend(reviewed_wide_row_issues(payload, fragments))
                owner_texts, display = bteam_owner_texts(payload, fragments, joiners, owner_texts, bteam)
                issues.extend(display)
            row['issues'] = issues
            if any(i['severity'] == 'reject' for i in issues):
                log.append(row)
                continue
            flags = review_flags(tpl, ko, meta.get(source, {}), jp, glossary, bteam, flagged_all, issues)
            admitted, why = admission(verdict, flags, batch_verdict)  # 8
            short = [i['detail'] for i in issues if i['code'] == 'external_short_match']
            if admitted and short:
                why += '+short_common_phrase'
            row['admitted_by'] = why
            row['review_flags'] = flags
            if not admitted:
                row['status'] = 'not_accepted'
                row['issues'].append(dict(code='review', severity='reject', detail=why))
                log.append(row)
                continue
            row['status'] = 'accepted'
            log.append(row)
            rows = sorted(owner_texts)
            accepted[key6(source)] = dict(
                source=key6(source), game=tpl.m['game'], profile=tpl.m['profile'][0],
                before_sha256=sha(tpl.m['payload']), after_sha256=sha(payload), ko=ko, ko_before=tpl.text,
                owner_texts=owner_texts, batch=batch, reviewed_by=reviewer, review_ref=review_ref,
                reason=msg.get('reason', ''), bteam_rows=[k for k in rows if key8(int(k, 16)) in bteam])
            if tpl.record and tpl.record.get('source_line_fragments') and any(
                    w[7] == 'dialogue-spacing-final-intent' and len(w) > 8
                    and key6(w[8].get('source_address', -1)) in tpl.owners for w in base.writes):
                owned.append(dict(source=key6(source), supersedes='dialogue-spacing-final-intent'))
            _, before_width = layout_issues(tpl.m['payload'], tpl.m, base.glyphs)
            _, after_width = layout_issues(payload, tpl.m, base.glyphs)
            diff.append(dict(id=key6(source), part=1 if tpl.m['game'] == 'p1' else 2, addr_rows=rows, jp=jp,
                             ko_before=tpl.text, ko_after=ko, bteam=bool(accepted[key6(source)]['bteam_rows']),
                             review=verdict.get('verdict', 'not_sampled'), admitted_by=why,
                             reason=msg.get('reason', ''), external_short_matches=short,
                             unowned_changes=[i['detail'] for i in issues if i['code'] == 'unowned_segment_overlay'],
                             width_before=before_width, width_after=after_width))
    merged = copy.deepcopy(rewrites)
    merged['messages'].update(accepted)
    report_dir = Path(args.report_dir) if args.report_dir else None
    try:
        overlay = plan_overlay(base, merged, encode)
    except OverlayError as exc:
        print(f'FAIL overlay preflight: {exc}')
        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / 'apply_log.json').write_text(json.dumps(log, ensure_ascii=False, indent=1))
        return 2
    moved = {p['key']: not p['same_slot'] for p in overlay['plans']}
    for row in diff:
        row['repointed'] = moved.get(row['id'], False)
    # 9: B-team rows -> bulk ledger, digest printed for the qa_bteam_drift pin.
    entries = ledger.setdefault('entries', {})
    added = noop = removed = 0
    for key, entry in accepted.items():
        changed = ledger_rows(entry, bteam)
        noop += len(entry['bteam_rows']) - len(changed)
        for addr, to in changed.items():
            entries[addr] = dict(**{'from': bteam[addr]}, to=to, batch=entry['batch'],
                                 reviewed_by=entry['reviewed_by'], review_ref=entry['review_ref'], message=key)
            added += 1
        for row_key in entry['bteam_rows']:
            addr = key8(int(row_key, 16))
            if addr not in changed and entries.pop(addr, None) is not None:
                removed += 1  # stale entry for a row now back at its baseline text
    if not args.dry_run:
        Path(args.rewrites).write_bytes(canonical_bytes(merged))
        if added or removed:
            ledger_path.write_bytes(canonical_bytes(ledger))
    digest = sha(canonical_bytes(ledger)) if added or removed else sha(ledger_path.read_bytes())
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / 'apply_log.json').write_text(json.dumps(log, ensure_ascii=False, indent=1))
        (report_dir / 'diff.json').write_text(json.dumps(diff, ensure_ascii=False, indent=1))
        (report_dir / 'superseded_ledger_owners.json').write_text(json.dumps(owned, ensure_ascii=False, indent=1))
    counts = collections.Counter(r['status'] for r in log)
    print(f'accepted {counts["accepted"]}, unchanged {counts["unchanged"]}, rejected {counts["rejected"]}, '
          f'not_accepted {counts["not_accepted"]}; overlay messages {len(merged["messages"])}, '
          f'arena {overlay["arena_start"]:#x}..{overlay["arena_used_end"]:#x}')
    print(f'B-team ledger rows added {added}, removed {removed} (unchanged B-team rows skipped {noop}); '
          f'APPROVED_REWRITE_LEDGER_DIGEST = {digest!r}')
    return 0


def cmd_check_external(args):
    """Report every exact match with its length; fail only on a long (copy) match."""
    index = external_index([args.check_external])
    data = load_rewrites(args.rewrites)
    long_ = short = 0
    for key, entry in sorted(data['messages'].items()):
        for hit in external_matches(entry['ko'], index):
            copy_ = len(hit) > EXTERNAL_COPY_MAX_COMMON
            long_ += copy_
            short += not copy_
            print(f'EXTERNAL {key} len={len(hit)} {"COPY" if copy_ else "short_common_phrase"} {hit[:40]}')
    print(f'rewrites checked: {len(data["messages"])}; exact external matches: {long_ + short} '
          f'(copy >{EXTERNAL_COPY_MAX_COMMON}: {long_}, short common phrase: {short})')
    return int(bool(long_))


def cmd_refresh_reviewers(args):
    """Re-derive reviewed_by of existing rewrites/ledger entries from their review_ref."""
    def reviewer(ref, current):
        path = Path(ref) if Path(ref).is_absolute() else ROOT / ref
        review = _read_json(path) or {}
        return batch_reviewer(path.parent, dict(review, reviewed_by=current)) or current
    rewrites = load_rewrites(args.rewrites)
    ledger_path = Path(args.ledger)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    changed = collections.Counter()
    for name, entries in (('rewrites', rewrites['messages']), ('ledger', ledger.get('entries', {}))):
        for entry in entries.values():
            value = reviewer(entry['review_ref'], entry['reviewed_by'])
            if value != entry['reviewed_by']:
                entry['reviewed_by'] = value
                changed[name] += 1
    if not args.dry_run:
        Path(args.rewrites).write_bytes(canonical_bytes(rewrites))
        ledger_path.write_bytes(canonical_bytes(ledger))
    print(f'reviewed_by refreshed: rewrites {changed["rewrites"]}, ledger {changed["ledger"]}; '
          f'APPROVED_REWRITE_LEDGER_DIGEST = {sha(canonical_bytes(ledger))!r}')
    return 0


def cmd_template(args):
    base = _load_baseline(args)
    out = []
    for value in args.template:
        source = int(value, 16)
        try:
            tpl = template_for(base, source)
            out.append(dict(id=key6(source), game=tpl.m['game'], profile=list(tpl.m['profile']),
                            ko=tpl.text, placeholders=tpl.names, rows=sorted(tpl.owners),
                            relocated=bool(tpl.record), before_sha256=sha(tpl.m['payload'])))
        except RewriteError as exc:
            out.append(dict(id=key6(source), locked=exc.code, detail=exc.detail))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_locked(args):
    base = _load_baseline(args)
    rows = []
    for source, m in sorted(base.messages.items()):
        if not m['script'] or m.get('pair_title'):
            continue
        reason = lock_reason(base, m)
        if reason is None:
            try:
                template_for(base, source)
                continue
            except RewriteError as exc:
                reason = f'{exc.code}:{exc.detail}'
        rows.append(dict(source=key6(source), game=m['game'], profile=m['profile'][0], reason=reason))
    Path(args.list_locked).write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    counts = collections.Counter(r['reason'].split(':', 1)[0] for r in rows)
    print(f'locked/blocked script messages: {len(rows)} {dict(counts)}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rom', default=str(ROOT / 'output/game_wars_korean_full.gba'),
                    help='frozen baseline candidate (built with an empty overlay)')
    ap.add_argument('--manifest', default=str(ROOT / 'temp/repoint_manifest.json'))
    ap.add_argument('--map', default=str(ROOT / 'temp/integrity_map.json'))
    ap.add_argument('--batches', nargs='+', help='batch dirs holding out.json/review.json(/in.json)')
    ap.add_argument('--rewrites', default=str(REWRITES))
    ap.add_argument('--ledger', default=str(LEDGER))
    ap.add_argument('--external', nargs='*', default=[], help='external-patch message JSON(s) to refuse')
    ap.add_argument('--report-dir')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--exclude', nargs='*', default=[], metavar='ID:REASON',
                    help='refuse these message ids in this run (logged as wave_excluded)')
    ap.add_argument('--check-external', help='G11: refuse exact external matches in --rewrites')
    ap.add_argument('--template', nargs='+', help='print placeholder templates for message sources')
    ap.add_argument('--list-locked', help='write locked/blocked script message list (JSON)')
    ap.add_argument('--refresh-reviewers', action='store_true',
                    help='re-derive reviewed_by of --rewrites/--ledger entries from review_ref (review.err banner)')
    args = ap.parse_args(argv)
    if args.check_external:
        return cmd_check_external(args)
    if args.refresh_reviewers:
        return cmd_refresh_reviewers(args)
    if args.template:
        return cmd_template(args)
    if args.list_locked:
        return cmd_locked(args)
    if not args.batches:
        ap.error('--batches is required in apply mode')
    return cmd_apply(args)


if __name__ == '__main__':
    raise SystemExit(main())
