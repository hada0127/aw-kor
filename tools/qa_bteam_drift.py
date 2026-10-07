#!/usr/bin/env python3
"""B팀(짜옹이) 권위 번역 drift 검사(QA).

절대제약: B팀/짜옹이 캠페인 번역 문구는 수정 불가(재배치/복원만). 2026-06-24 codex 적대
리뷰가 작업트리에서 B팀 대사 3건이 슬롯 여유에도 축약·개작된 것을 적발 → 이런 우발적 변형을
영구 자동 검출하기 위한 게이트.

방식: `data/bteam_baseline.json`(B팀 적용 주소의 권위 override 스냅샷)과 현재
`data/dialogue_overrides.json`을 주소별로 비교. 값이 다르면 DRIFT(우발적 변형 의심).

짜옹이 본인이 의도적으로 B팀 문구를 바꾸려면: 편집 후 `--accept`로 baseline을 재생성한다
(의도적 변경만 통과시키고, 그 외 우발 변형은 차단).

사용:
  python3 tools/qa_bteam_drift.py            # drift 있으면 출력 + 비0 종료
  python3 tools/qa_bteam_drift.py --accept   # 현재 override로 baseline 갱신(의도적 변경 확정)
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

from qa_integrity_map import decode_enc, fill_pattern, load_syl
from dialogue_regions import is_part1_dialog_address, is_part2_story_address

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
BASELINE = os.path.join(BASE, 'data', 'bteam_baseline.json')

# Exact B-team source/display exceptions reviewed at script row boundaries.
# Shared with the writer so the final-ROM gate cannot drift from its policy.
BTEAM_SCRIPT_SPACING_REPAIRS = {
    0xDEECDE: ('해상유닛.지상 유닛을', '해상 유닛.지상 유닛을'),
    0xDC3C63: ('사령관님,료!', ' 사령관님, 료!'),
    0xDEDFB6: ('공중유닛에 강한,', '공중 유닛에 강한,'),
    0xDEE15E: ('공중유닛.공중유닛에', '공중 유닛. 공중 유닛에'),
}


def norm(a: str) -> str:
    try:
        return '0x%08X' % int(a, 16)
    except (ValueError, TypeError):
        return a


def load_overrides() -> dict:
    ov = json.load(open(OVERRIDES, encoding='utf-8'))
    return {norm(k): v for k, v in ov.items()}


# SHA-256 of every baseline entry that is NOT a user-approved exception
# (sorted JSON). Hand edits or a broad --accept change it and fail the gate;
# changing B-team wording needs a reviewed code change of this pin.
# The 2026-10-07 consensus re-keys two misaligned entries only; see
# temp/claude_2026-10-07/plan/bteam_final_decisions.tsv.
PINNED_CORE_DIGEST = '902a7394955376af68c1eea20c0d0da7278b42f2a8c58f5f287889ab5a727110'
ALIGNMENT_RESTORE_ADDRESSES = frozenset({0x00A19300, 0x00A1B3C8})
ALIGNMENT_COMPOSITE_NEXT = {0x00A19300: 0x00A1930F}
ALIGNMENT_LEGACY_KEYS = {
    '0x00A19300': '0x00A19324',
    '0x00A1B3C8': '0x00A1B3EC',
}

# Exact round-2 deferrals; previously deferred addresses with a reviewed
# restore decision must no longer be forced to fail after restoration.
ROUND2_MANIFEST = Path(BASE, 'data', 'bteam_round2_decisions.tsv')
ROUND2_RESIDUAL_DIGEST = 'd84f1d18a819dccf6050db25b569f91e582e9af959d39ea1dae36e89de076165'
ROUND2_ACTIVE_PINS_DIGEST = '661d2d0dd777a6aac93c9d9ba3fa3202dfe9c5752be1f60e0c5e1f80ba9c5ccb'
with ROUND2_MANIFEST.open('rb') as _stream:
    if hashlib.sha256(_stream.read()).hexdigest() != '6cfb219377f7078b7976a83a40d429a00886b6181346eb422f44770e96047b52':
        raise ValueError('B-team round-2 decision manifest digest changed')
with ROUND2_MANIFEST.open(encoding='utf-8', newline='') as _stream:
    _round2_rows = list(csv.DictReader(_stream, delimiter='\t'))
DEFERRED_ADDRESSES = frozenset(int(row['address'], 16) for row in _round2_rows
                                if row['decision'] == 'DEFER')
FIX_GATE_ADDRESSES = frozenset(int(row['address'], 16) for row in _round2_rows
                              if row['decision'] == 'FIX_GATE')
if len(_round2_rows) != 287 or len(DEFERRED_ADDRESSES) != 11:
    raise ValueError('B-team round-2 deferral count changed')
COMPACT_GLYPH_ADDRESSES = frozenset(int(x, 16) for x in '''
B818D0 B818F4 B81900 B81970 B81988 B81994 B819C4 B819E8
B81AC0 B81ACC B82CF6 B82D02 B82D0E B82D76 B82DD6 B82DE2
B84F28 B84F38 B84F4C B84F5C B84F6C
'''.split())
# Newly exposed by preserving punctuation and authored spaces. These were not
# among the 649 consensus rows and need separate review, not silent clearance.
NEW_STRICT_ADDRESSES = frozenset(int(x, 16) for x in '''
A021A0 A02450 A03F0C A15D3C A2C144 A2C5F0 A2C704 A2C8B0
A2C8C4 A2C970 A2C994 A2CA38 A2CA44 A2CA60 A2CA70 A2CA88
A2CBFC A2CC0C A2D55C A2D58C A2D5A0 A2D61C A2D698 A2D6C0
A2D704 A2D7A4 A2D7FC A2D828 A2D838 A2D848 A2D889 A309AC
A30C88 A30E40 A33C3C A33D1C A34F5C A34FC8 A3500C A3506C
A351A4 B8306C B830EC B8310C B83188 B8319C B83254 B83268
B83870 B8387C B838A4 B838B0 B838BC B83A3C B83A98 B83AC8
B83D10 B83DE0 B84128 B84238 D9159E DC3B0E DC495E DC4B2A
DC51AE DC5812 DC5D12 DC7006 DC9662 DCB0BA DCBD36 DD1476
DF3AC3 DF3AD2 E062DE E064B2 E0F7EE
'''.split())


def compact_glyph_map() -> dict[str, str]:
    """Read the actual compact FONT_BASE substitution table from the builder.

    Keep this tied to the writer's literal map, and fail closed if it becomes
    computed or disappears. The same source drives patch_part2_ui_kanji_glyphs.
    """
    source = Path(BASE, 'tools', 'build_korean_full.py').read_text(encoding='utf-8')
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'PART2_UI_KANJI_GLYPH_SUBS'
                for t in node.targets):
            result = ast.literal_eval(node.value)
            if not isinstance(result, dict) or not result:
                break
            return result
    raise ValueError('compact UI glyph substitution table unavailable')


def decode_compact(enc: bytes, code2syl: dict, glyphs: dict[str, str]) -> str:
    """Decode bytes through the compact renderer's substituted glyphs."""
    # The compact writer owns fixed-size rows and terminates glyph text with
    # zero bytes; these are not displayed glyphs. Embedded zeros remain errors.
    ordinary = decode_enc(enc.rstrip(b'\x00'), code2syl)
    return ''.join(glyphs.get(ch, ch) for ch in ordinary)


def verify_compact_font(rom: bytes, glyphs: dict[str, str]) -> None:
    """Prove that this ROM, not just builder source, carries the substitute tiles."""
    from build_korean_poc import FONT_FILE, KTAB_FILE, KTAB_END_FILE, ROM
    from render_galmuri_8x16 import render_char
    original = Path(ROM).read_bytes()
    slots = {}
    for pos in range(KTAB_FILE, KTAB_END_FILE, 6):
        try:
            jp = original[pos:pos + 2].decode('shift_jis')
        except UnicodeDecodeError:
            continue
        slots[jp] = struct.unpack_from('<HH', original, pos + 2)
    for jp, ko in glyphs.items():
        if jp not in slots:
            raise ValueError(f'compact glyph has no original font slot: {jp}')
        top, bottom = slots[jp]
        actual = (rom[FONT_FILE + top * 32:FONT_FILE + (top + 1) * 32],
                  rom[FONT_FILE + bottom * 32:FONT_FILE + (bottom + 1) * 32])
        if actual != tuple(render_char(ko)):
            raise ValueError(f'compact glyph tile mismatch in inspected ROM: {jp}->{ko}')


def display_equivalent(value: str, address: int, *, actual: bool = False) -> str:
    """Predict only documented writer glyph substitutions on baseline text.

    The ROM side stays literal: a halfwidth space or punctuation byte in a
    dialogue renderer must not pass as its visible fullwidth counterpart.
    """
    if actual:
        return value
    dialogue = is_part2_story_address(address) or is_part1_dialog_address(address)
    if dialogue:
        # The dialogue writer promotes authored ASCII to visible SJIS glyphs.
        # Preserve the number and position of punctuation and spaces.
        value = value.replace('...', '・・・').replace(' ', '　')
        value = ''.join(chr(ord(ch) + 0xFEE0) if ch.isascii() and ch.isalnum()
                        else ch for ch in value)
    else:
        value = value.replace(' ', '　')
    # This 36-byte Part 1 link preload now carries the complete protected
    # wording.  Its compact consumer uses the SJIS fullwidth period glyph.
    if address in {0xB8322C, 0xB83254}:
        value = value.replace('.', '。')
    punctuation = {}
    if is_part1_dialog_address(address):
        punctuation.update({'!': '！', '?': '？', ',': '、', '.': '。',
                            '-': '―', '「': '”', '」': '”'})
    elif is_part2_story_address(address):
        punctuation.update({'!': '！', '?': '？', ',': '、', '.': '。', '-': 'ー'})
    return value.translate(str.maketrans(punctuation))


def round2_width_equivalent(baseline: str, actual: str, address: int) -> bool:
    """Accept only reviewed FIX_GATE glyph aliases, with every character retained."""
    if address not in FIX_GATE_ADDRESSES:
        return False
    aliases = str.maketrans({' ': '　', '!': '！', '?': '？', ',': '、',
                             '.': '。', '～': '〜', '-': 'ー', '―': 'ー'})
    def canonical(value: str) -> str:
        value = value.translate(aliases)
        return ''.join(chr(ord(ch) + 0xFEE0) if ch.isascii() and ch.isalnum()
                       else ch for ch in value)
    expected = baseline.translate(aliases)
    if is_part1_dialog_address(address) or is_part2_story_address(address):
        return canonical(baseline) == actual
    return actual in {expected, canonical(baseline)}


ROUND2_PREFIX_GLYPH_ROWS = {0xA2CA88: 2, 0xB83870: 3,
                            0xB8387C: 3, 0xB838A4: 4,
                            0xB838B0: 4, 0xB838BC: 3}
ROUND2_OBJECTIVE_ROWS = {
    0xA01ED0: ('산을 넘어,캣의 연구 기지를공격하라!', '산을　넘어、　캣의　연구　기지를', '공격하라！'),
    0xA021A0: ('캣에게 빼앗긴 국토를되찾아라!', '캣에게　빼앗긴　국토를', '되찾아라！'),
    0xA02450: ('블랙홀 군의 본거지를쳐라!', '블랙홀　군의　본거지를', '쳐라！'),
}


def round2_objective_equivalent(rom: bytes, baseline: str, actual: str,
                                address: int, row_start: int) -> bool:
    """Check both displayed rows of three reviewed objective sentences."""
    if address not in ROUND2_OBJECTIVE_ROWS or address not in FIX_GATE_ADDRESSES:
        return False
    # The first row is already decoded by check_rom. The predicate must be in
    # the immediately following physical row, after exactly one 0x72 break.
    lead_end = rom.find(b'\x72', row_start + 20, row_start + 48)
    if lead_end < 0:
        return False
    tail_end = rom.find(b'\x00', lead_end + 1, lead_end + 40)
    if tail_end < 0:
        return False
    tail_raw = rom[lead_end + 1:tail_end].rstrip(b' ')
    if not tail_raw or b'\x72' in tail_raw:
        return False
    tail = decode_enc(tail_raw, load_syl())
    expected_baseline, expected_first, expected_tail = ROUND2_OBJECTIVE_ROWS[address]
    return (baseline == expected_baseline and actual == expected_first
            and tail == expected_tail)


def reviewed_seam_variants(value: str, msg: int, rows: dict) -> set[str]:
    """Expected side only: add a reviewed seam space; never remove one."""
    variants = {value}
    for prev, next_ in rows.get(msg, ()):
        joined = prev + next_
        spaced = prev + '　' + next_
        variants |= {v.replace(joined, spaced, 1) for v in variants if joined in v}
    return variants


def matches_reviewed_bteam_spacing(address: int, baseline: str, actual: str) -> bool:
    """Accept only an individually reviewed whitespace repair at its source row."""
    repair = BTEAM_SCRIPT_SPACING_REPAIRS.get(address)
    return (repair is not None and baseline == repair[0]
            and display_equivalent(actual, address, actual=True)
            == display_equivalent(repair[1], address))


def load_reviewed_seams() -> dict[int, list[tuple[str, str]]]:
    path = Path(BASE, 'data', 'part2_seam_decisions.tsv')
    rows = {}
    with path.open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            if row['decision'] == 'space':
                rows.setdefault(int(row['msg'], 16), []).append(
                    (row['prev_word'], row['next_word']))
    return rows


def matches_alignment_composite(wanted: str, first: str, second: str,
                                gap: bytes, address: int) -> bool:
    """Only the consensus A19300/A1930F pair may cross its native 0x72 row break."""
    return (address in ALIGNMENT_COMPOSITE_NEXT and gap == b'\x72' and
            bool(first) and bool(second) and
            wanted == display_equivalent(first + second, address, actual=True))


# User-approved B-team wording exceptions, exact (address, from, to). The
# baseline's _user_approved_exceptions must equal this table; adding or editing
# one is a reviewed code change. 0xDD0D1A: じょうでき=上出来, user 「제안대로」 2026-10-07.
APPROVED_EXCEPTIONS = {
    '0x00DD0D1A': ('뭐,자네치고는,상등품이군.', '뭐, 자네치고는 잘했군.'),
}


def core_digest(base: dict) -> str:
    exceptions = base.get('_user_approved_exceptions', {})
    core = {k: v for k, v in base.get('overrides', {}).items() if k not in exceptions}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def exception_errors(base: dict, overrides: dict) -> list:
    """Each exception is valid only for its exact (address, from, to) tuple."""
    errors = []
    recorded = base.get('_user_approved_exceptions', {})
    if {a: (e.get('from'), e.get('to')) for a, e in recorded.items() if isinstance(e, dict)} != APPROVED_EXCEPTIONS:
        errors.append('baseline exceptions differ from the approved (address, from, to) table')
    for addr, exc in recorded.items():
        if (not isinstance(exc, dict) or not exc.get('approved') or not exc.get('from')
                or not exc.get('to') or exc['from'] == exc['to']):
            errors.append(f'{addr}: malformed user-approved exception')
            continue
        if base.get('overrides', {}).get(addr) != exc['to']:
            errors.append(f'{addr}: baseline differs from the approved exception text')
        if overrides.get(addr) != exc['to']:
            errors.append(f'{addr}: override differs from the approved exception text')
    return errors


def check(base: dict, overrides: dict, pinned: str = None) -> dict:
    expected = base.get('overrides', {})
    drift = [(a, w, overrides[a]) for a, w in expected.items() if a in overrides and overrides[a] != w]
    # The two consensus re-keys precede the other worker's override migration.
    # Accept only their exact legacy text in the source-data gate; the final
    # ROM gate still protects the corrected source addresses and fails today.
    missing = [(a, w) for a, w in expected.items()
               if a not in overrides and overrides.get(ALIGNMENT_LEGACY_KEYS.get(a)) != w]
    errors = exception_errors(base, overrides)
    pinned = PINNED_CORE_DIGEST if pinned is None else pinned
    if core_digest(base) != pinned:
        errors.append('baseline entries outside the approved exceptions changed (core digest mismatch)')
    return {'drift': drift, 'missing': missing, 'errors': errors}


def accept(base: dict, overrides: dict, *, allow_bteam_changes: bool = False, pinned: str = None) -> dict:
    """New baseline from current overrides. Refuses to widen beyond the exceptions."""
    new = dict(base)
    new['overrides'] = {a: overrides[a] for a in base.get('overrides', {}) if a in overrides}
    new['count'] = len(new['overrides'])
    if exception_errors(new, overrides):
        raise ValueError('approved exceptions do not match the current overrides')
    pinned = PINNED_CORE_DIGEST if pinned is None else pinned
    if core_digest(new) != pinned and not allow_bteam_changes:
        changed = sorted(a for a, v in new['overrides'].items()
                         if a not in base.get('_user_approved_exceptions', {})
                         and base['overrides'].get(a) != v)
        raise ValueError('--accept would change B-team entries outside the approved exceptions: '
                         + ', '.join(changed[:10]) + (' ...' if len(changed) > 10 else '')
                         + ' (needs --allow-bteam-changes and a new PINNED_CORE_DIGEST)')
    return new


def check_rom(base: dict, rom_path: str, map_path: str, manifest_path: str,
              map_rom_path: str | None = None) -> list[dict]:
    """Compare protected text with final ROM bytes, including relocated messages.

    Relocation metadata records each original line's final byte span. Reject
    stale write metadata before checking text so a mismatched map cannot pass.
    """
    rom = Path(rom_path).read_bytes()
    map_rom = Path(map_rom_path).read_bytes() if map_rom_path else rom
    if len(map_rom) != len(rom):
        raise ValueError('ROM and map ROM lengths differ')
    writes = json.loads(Path(map_path).read_text(encoding='utf-8'))
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    by_addr = {int(row[0]): row for row in writes if row[3]}
    protected_addrs = sorted(int(key, 16) for key in base['overrides'])
    import bisect
    covering = {}
    for row in writes:
        start, slot = int(row[0]), int(row[1])
        if slot <= 0:
            continue
        lo = bisect.bisect_left(protected_addrs, start)
        hi = bisect.bisect_left(protected_addrs, start + slot, lo)
        for covered in protected_addrs[lo:hi]:
            covering[covered] = row
    expected = {}
    for addr, slot, _enc_len, enc_hex, fill, *_rest in writes:
        enc = bytes.fromhex(enc_hex)
        if fill is not None:
            pattern = fill_pattern(fill)
            for k in range(len(enc), slot):
                expected[addr + k] = pattern[(k - len(enc)) % len(pattern)]
        for k, byte in enumerate(enc):
            expected[addr + k] = byte
    stale = [addr for addr, byte in expected.items() if addr >= len(map_rom) or map_rom[addr] != byte]
    if stale:
        raise ValueError(f'integrity map does not match ROM ({len(stale)} bytes; first 0x{stale[0]:X})')
    relocated = sorted((int(m['msg'], 16), int(m['msg'], 16) + int(m['old_len']), m)
                       for m in manifest if m.get('status') == 'relocated')
    starts = [x[0] for x in relocated]
    codes = load_syl()
    compact = compact_glyph_map()
    compact_writers = {'part1-unit-compact-name', 'part1-compact-ui',
                       'part1-battle-menu-font', 'bteam-round2-compact-residual'}
    if (set(protected_addrs) & COMPACT_GLYPH_ADDRESSES or
            any(row[3] and row[7] in compact_writers and int(row[0]) in protected_addrs
                for row in writes)):
        verify_compact_font(rom, compact)
    seams = load_reviewed_seams()
    def decode(payload: bytes, address: int, writer: str = '') -> str:
        if address in COMPACT_GLYPH_ADDRESSES and writer not in compact_writers:
            raise ValueError(f'0x{address:08X}: compact renderer writer evidence changed: {writer!r}')
        if writer in compact_writers:
            return decode_compact(payload, codes, compact)
        return decode_enc(payload, codes)

    issues = []
    for key, baseline in base['overrides'].items():
        addr = int(key, 16)
        objective_start = None
        i = bisect.bisect_right(starts, addr) - 1
        relocation = relocated[i] if i >= 0 and addr < relocated[i][1] else None
        # Exact writer wins over an earlier padded slot that happens to cover it.
        row = by_addr.get(addr) or covering.get(addr)
        if relocation:
            m = relocation[2]
            target = int(m['new_addr'], 16)
            sites = m.get('ptr_sites')
            if not sites:
                raise ValueError(f'{key}: relocated message lacks ptr_sites')
            if map_rom_path:
                end = target + int(m['new_len'])
                if rom[target:end] != map_rom[target:end] or any(
                        rom[int(site, 16):int(site, 16) + 4] !=
                        map_rom[int(site, 16):int(site, 16) + 4] for site in sites):
                    raise ValueError(f'{key}: overlay changed protected relocated message or pointer')
            bad_sites = [site for site in sites if int.from_bytes(
                rom[int(site, 16):int(site, 16) + 4], 'little') != 0x08000000 + target]
            span = m.get('line_spans', {}).get(f'0x{addr:06X}')
            payload = None
            if bad_sites:
                actual = '<bad repoint pointer at ' + ', '.join(bad_sites) + '>'
                cause = 'repoint pointer mismatch'
            elif not span:
                actual = '<protected row missing from relocated line spans>'
                cause = 'repoint line mapping missing'
            else:
                off, length = span
                if off < 0 or length <= 0 or off + length > int(m['new_len']):
                    actual = '<invalid relocated line span>'
                    cause = 'repoint line mapping invalid'
                else:
                    payload = rom[target + off:target + off + length]
                    objective_start = target + off
                    # A wrapped row may contain this verified internal control.
                    actual = decode(payload.replace(b'\x72\x0a\x09', b'\x81\x40'), addr).rstrip(' \u3000')
                    cause = 'relocated row differs from protected baseline'
            wanted = display_equivalent(baseline, addr)
            matched = wanted == display_equivalent(actual, addr, actual=True)
            if not matched and payload is not None and is_part2_story_address(addr):
                message = int(m['msg'], 16)
                matched = display_equivalent(actual, addr, actual=True) in reviewed_seam_variants(wanted, message, seams)
            if not matched and payload is not None:
                # The explicit wrap replaced an authored space; some older
                # baselines had no space at that point. Keep both readings.
                no_wrap_space = decode(payload.replace(b'\x72\x0a\x09', b''), addr)
                matched = wanted == display_equivalent(no_wrap_space, addr, actual=True)
            if not matched and payload is not None and actual:
                # A few authority rows cover consecutive physical rows.
                ordered = sorted(m['line_spans'].items(), key=lambda entry: entry[1][0])
                idx = next((n for n, (key2, _) in enumerate(ordered)
                            if int(key2, 16) == addr), -1)
                if idx >= 0:
                    parts = [actual]
                    prior_end = ordered[idx][1][0] + ordered[idx][1][1]
                    for _next_key, (next_off, next_len) in ordered[idx + 1:idx + 3]:
                        if next_len <= 0 or next_off != prior_end:
                            break
                        parts.append(decode(rom[target + next_off:target + next_off + next_len], addr))
                        prior_end = next_off + next_len
                        if wanted in (display_equivalent(''.join(parts), addr, actual=True),
                                      display_equivalent('　'.join(parts), addr, actual=True)):
                            actual = ' | '.join(parts)
                            matched = True
                            break
        elif row:
            row_start = int(row[0])
            objective_start = addr
            enc_end = row_start + int(row[2])
            if map_rom_path and rom[addr:row_start + int(row[1])] != map_rom[addr:row_start + int(row[1])]:
                raise ValueError(f'{key}: overlay changed protected in-place slot')
            actual = decode(rom[addr:max(addr, enc_end)], addr, row[7])
            if addr != 0xD9159E:
                actual = actual.rstrip(' \u3000')
            if row[7] == 'part2-prologue-inline-renderer':
                # The writer owns a whole multi-line script at this address;
                # the B-team authority applies to its first displayed row.
                payload = rom[addr:enc_end].split(b'\x77\x72', 1)[0]
                actual = decode(payload, addr, row[7]).rstrip(' \u3000')
            matched = display_equivalent(actual, addr, actual=True) == display_equivalent(baseline, addr)
            if not matched and addr in seams and is_part2_story_address(addr):
                matched = display_equivalent(actual, addr, actual=True) in reviewed_seam_variants(
                    display_equivalent(baseline, addr), addr, seams)
            if not matched and addr in ALIGNMENT_COMPOSITE_NEXT and row_start == addr:
                next_addr = ALIGNMENT_COMPOSITE_NEXT[addr]
                next_row = by_addr.get(next_addr)
                if next_row and int(next_row[0]) == next_addr and next_addr >= enc_end:
                    next_text = decode(rom[next_addr:next_addr + int(next_row[2])],
                                       next_addr, next_row[7]).rstrip(' \u3000')
                    matched = matches_alignment_composite(
                        display_equivalent(baseline, addr), actual, next_text,
                        rom[enc_end:next_addr], addr)
            cause = (f'final in-place writer {row[7]} level={row[6]}'
                     f' at 0x{row_start:08X}; source={row[5]!r}')
        else:
            # No write evidence is a hard failure; guessing a text boundary
            # would turn unknown controls or binary assets into a false pass.
            actual = '<no text write in integrity map>'
            matched = False
            cause = 'protected address has no final text write evidence'
        if not matched:
            matched = matches_reviewed_bteam_spacing(addr, baseline, actual)
        if not matched:
            matched = round2_width_equivalent(baseline, actual, addr)
        if not matched and addr in ROUND2_PREFIX_GLYPH_ROWS and addr in FIX_GATE_ADDRESSES:
            matched = actual == '　' * ROUND2_PREFIX_GLYPH_ROWS[addr] + display_equivalent(baseline, addr)
        if not matched and objective_start is not None:
            matched = round2_objective_equivalent(rom, baseline, actual, addr, objective_start)
        if addr in DEFERRED_ADDRESSES:
            matched = False  # Reviewed decision withholds acceptance, even on a later ROM.
        if not matched:
            issues.append({'address': key, 'baseline': baseline, 'rom_text': actual,
                           'cause': cause,
                           'decision': 'DEFER' if addr in DEFERRED_ADDRESSES else
                                       'FIX_GATE_BLOCKED' if addr in COMPACT_GLYPH_ADDRESSES else
                                       'ALIGNMENT_RESTORE' if addr in ALIGNMENT_RESTORE_ADDRESSES else
                                       'NEW_STRICT_MISMATCH' if addr in NEW_STRICT_ADDRESSES else
                                       'RESTORE_BASELINE'})
    return issues


def classify_round2_issues(issues: list[dict], base: dict, rom_path: str,
                           manifest_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Count only byte-pinned listed residuals and exact reviewed deferrals as expected."""
    path = Path(BASE, 'data', 'bteam_round2_residuals.tsv')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ROUND2_RESIDUAL_DIGEST:
        raise ValueError('B-team residual manifest digest changed')
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    listed = {int(row['address'], 16): row for row in rows}
    if len(rows) != 177 or len(listed) != len(rows):
        raise ValueError('B-team residual list count or addresses changed')
    pins_path = Path(BASE, 'data', 'bteam_round2_active_pins.json')
    if hashlib.sha256(pins_path.read_bytes()).hexdigest() != ROUND2_ACTIVE_PINS_DIGEST:
        raise ValueError('B-team active residual pin digest changed')
    pins = {int(key, 16): value for key, value in json.loads(
        pins_path.read_text(encoding='utf-8')).items()}
    rom = Path(rom_path).read_bytes()
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    spans = {}
    messages = {}
    for message in manifest:
        if message.get('status') == 'relocated':
            for key, (offset, length) in message.get('line_spans', {}).items():
                address = int(key, 16)
                if address in spans:
                    raise ValueError(f'0x{address:08X}: duplicate relocated line mapping')
                spans[address] = (int(message['new_addr'], 16) + offset, length)
                messages[address] = message
    for addr, row in listed.items():
        key = f'0x{addr:08X}'
        payload = bytes.fromhex(row['payload_hex'])
        if (key not in base['overrides'] or row['expected_baseline'] != base['overrides'][key]
                or not row['reason'] or not payload or rom[addr:addr + len(payload)] != payload):
            raise ValueError(f'{key}: listed residual metadata or source bytes changed')
        message = messages.get(addr)
        pinned_message = pins.get(addr)
        if bool(message) != bool(pinned_message):
            raise ValueError(f'{key}: active residual mapping or byte pin missing')
        if message:
            target = int(message['new_addr'], 16)
            length = int(message['new_len'])
            off, span_length = message['line_spans'][f'0x{addr:06X}']
            if (off < 0 or span_length <= 0 or off + span_length > length
                    or len(bytes.fromhex(pinned_message)) != length
                    or rom[target:target + length].hex() != pinned_message):
                raise ValueError(f'{key}: active residual message bytes or span changed')
            sites = message.get('ptr_sites') or []
            if not sites or any(int.from_bytes(rom[int(site, 16):int(site, 16) + 4],
                                               'little') != 0x08000000 + target for site in sites):
                raise ValueError(f'{key}: active residual pointer changed')
        if row['active_payload_hex']:
            if addr not in spans or not row['active_text']:
                raise ValueError(f'{key}: active residual has no relocated line')
            pos, length = spans[addr]
            active = bytes.fromhex(row['active_payload_hex'])
            pair_title = 0xA2D55C <= addr <= 0xA2D8A8
            padding = (b'\x00' if pair_title else b' ') * (length - len(active))
            if len(active) > length or rom[pos:pos + length] != active + padding:
                raise ValueError(f'{key}: active residual bytes changed')
            if row['active_follow_hex']:
                follow = spans.get(0xA2BC57)
                expected_follow = bytes.fromhex(row['active_follow_hex'])
                if addr != 0xA2BC3C or follow is None or follow[1] != len(expected_follow) or \
                        rom[follow[0]:follow[0] + follow[1]] != expected_follow:
                    raise ValueError(f'{key}: residual continuation bytes changed')
    expected_residuals, deferred, unlisted = [], [], []
    for issue in issues:
        addr = int(issue['address'], 16)
        structural = issue['cause'] in {'repoint pointer mismatch',
                                        'repoint line mapping missing',
                                        'repoint line mapping invalid',
                                        'protected address has no final text write evidence'}
        if structural:
            unlisted.append(issue)
        elif addr in DEFERRED_ADDRESSES:
            deferred.append(issue)
        elif addr in listed and issue['cause'] in {
                'relocated row differs from protected baseline'}:
            expected_residuals.append(issue)
        elif addr in listed and issue['cause'].startswith('final in-place writer '):
            expected_residuals.append(issue)
        else:
            unlisted.append(issue)
    if {int(x['address'], 16) for x in deferred} != DEFERRED_ADDRESSES:
        raise ValueError('B-team deferred issue set changed')
    return expected_residuals, deferred, unlisted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--accept', action='store_true',
                    help='현재 override로 baseline 갱신(승인된 예외 범위만; 그 밖의 변경은 거부)')
    ap.add_argument('--allow-bteam-changes', action='store_true',
                    help='--accept와 함께: 예외 밖 B팀 문구 변경까지 확정(별도 승인 필요, PINNED_CORE_DIGEST도 갱신해야 게이트 통과)')
    ap.add_argument('--rom', help='최종 ROM 보호 대사 전수 검사')
    ap.add_argument('--map', default=os.path.join(BASE, 'temp', 'integrity_map.json'))
    ap.add_argument('--map-rom', help='overlay 후보일 때 map을 만든 B 빌드 ROM (기본: --rom)')
    ap.add_argument('--repoint-manifest', default=os.path.join(BASE, 'temp', 'repoint_manifest.json'))
    ap.add_argument('--json', help='ROM 불일치 전체 JSON 보고서 경로')
    args = ap.parse_args()

    ovn = load_overrides()

    if args.accept:
        # 우발 drift를 권위본으로 봉인하는 사고 방지: 명시적 환경변수 승인 필요(codex 리뷰).
        if os.environ.get('AW_BTEAM_ACCEPT') != '1':
            print('거부: baseline 갱신은 의도적 B팀 변경 확정 전용. 변경 내역을 git diff로 확인 후\n'
                  '  AW_BTEAM_ACCEPT=1 python3 tools/qa_bteam_drift.py --accept 로 재실행하라.', file=sys.stderr)
            sys.exit(2)
        base = json.load(open(BASELINE, encoding='utf-8'))
        try:
            base = accept(base, ovn, allow_bteam_changes=args.allow_bteam_changes)
        except ValueError as exc:
            print('거부: ' + str(exc), file=sys.stderr)
            sys.exit(2)
        json.dump(base, open(BASELINE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'baseline 갱신: {base["count"]}개 B팀 주소를 현재 override로 확정 (core digest {core_digest(base)})')
        return

    base = json.load(open(BASELINE, encoding='utf-8'))
    absent = (DEFERRED_ADDRESSES | COMPACT_GLYPH_ADDRESSES |
              NEW_STRICT_ADDRESSES | ALIGNMENT_RESTORE_ADDRESSES) - {
        int(key, 16) for key in base['overrides']}
    if absent:
        print('[HARD-FAIL] reviewed gate addresses missing from baseline: ' +
              ', '.join(f'0x{addr:08X}' for addr in sorted(absent)), file=sys.stderr)
        sys.exit(1)
    result = check(base, ovn)
    drift, missing = result['drift'], result['missing']
    for error in result['errors']:
        print(f'[HARD-FAIL] {error}', file=sys.stderr)
    if result['errors']:
        sys.exit(1)
    expected = base.get('overrides', {})
    if args.rom:
        try:
            issues = check_rom(base, args.rom, args.map, args.repoint_manifest, args.map_rom)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'[HARD-FAIL] ROM 검사 입력 오류: {exc}', file=sys.stderr)
            sys.exit(1)
        if args.json:
            Path(args.json).write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            residuals, deferred, unlisted = classify_round2_issues(
                issues, base, args.rom, args.repoint_manifest)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'[HARD-FAIL] ROM residual classification error: {exc}', file=sys.stderr)
            sys.exit(1)
        print(f'B팀 최종 ROM 검사: {len(expected)}개, mismatch {len(issues)}개 '
              f'(listed residual {len(residuals)}, deferred {len(deferred)}, '
              f'unlisted {len(unlisted)})')
        print('  [DEFERRED] ' + ', '.join(x['address'] for x in deferred))
        for issue in unlisted:
            print(f"  [ROM-DRIFT:{issue['decision']}] {issue['address']} baseline={issue['baseline']!r} "
                  f"ROM={issue['rom_text']!r} cause={issue['cause']}")
        if unlisted:
            sys.exit(1)
    print(f'B팀 보호 주소: {len(expected)}')
    print(f'DRIFT(우발적 변형 의심): {len(drift)}  / MISSING(override 삭제됨): {len(missing)}')
    for addr, want, cur in drift[:40]:
        print(f'  [DRIFT] {addr}')
        print(f'          baseline: {want!r}')
        print(f'          현재:     {cur!r}')
    for addr, want in missing[:20]:
        print(f'  [MISSING] {addr}  baseline={want!r}')

    if drift or missing:
        print('\n[HARD-FAIL] B팀 권위문 변형/삭제 감지. 의도적이면 --accept, 아니면 복원하라.',
              file=sys.stderr)
        sys.exit(1)
    print('[HARD-OK] B팀 권위문 drift 0')


if __name__ == '__main__':
    main()
