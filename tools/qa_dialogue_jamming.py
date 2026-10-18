#!/usr/bin/env python3
"""Final-owner spacing audit. Unsupported coverage is reported, never a baseline."""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

from qa_integrity_map import decode_enc, load_syl
from repoint_source_rows import row_bytes, fragments
from build_korean_full import normalize_korean_terms

ROOT = Path(__file__).resolve().parent.parent
PUNCT = str.maketrans({'！': '!', '？': '?', '。': '.', '、': ',',
                      '，': ',', '．': '.', '　': ' '})


def separator_signature(text):
    # The builder applies this approved terminology rule before encoding.
    # Country compounds are not evidence of a newly dropped word separator.
    text = normalize_korean_terms(text.translate(PUNCT)).strip(' \x00▯')
    chars, boundaries = [], set()
    for ch in text:
        if ch == ' ':
            if chars:
                boundaries.add(len(chars))
        else:
            chars.append(ch)
    boundaries.discard(len(chars))
    return ''.join(chars), boundaries


def is_jammed(authored, shipped):
    """Every authored interior separator must survive at the same character boundary."""
    expected, wanted = separator_signature(authored)
    actual, present = separator_signature(shipped.replace('\x72\x0a\x09', ' '))
    return bool(expected and expected == actual and wanted - present)


def verify_provenance(rom_path, map_path, manifest_path):
    receipt = json.loads(Path(str(rom_path) + '.build.json').read_text())
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if receipt.get('schema') != 1 or receipt.get('rom_sha256') != sha(rom_path):
        raise ValueError('ROM does not match its build receipt')
    for name, path in (('temp/integrity_map.json', map_path),
                       ('temp/repoint_manifest.json', manifest_path)):
        if (receipt.get('build_metadata') or {}).get(name) != sha(path):
            raise ValueError(f'build metadata provenance mismatch: {path}')


def final_owner_spans(writes, rom_size, *, hangul_only=True):
    """Resolve chronological writes by byte ownership, including merged spans.

    Partial owners cannot safely lend their full authored sentence to a fragment.
    Return them as unsupported instead of treating obsolete CSV slots as owners.
    """
    occupied = bytearray(rom_size)
    owners, unsupported = {}, []
    for entry in reversed(writes):
        addr, size = entry[:2]
        if not isinstance(addr, int) or not isinstance(size, int) or size < 0 or addr < 0 or addr + size > rom_size:
            raise ValueError(f'owner bounds invalid: {addr!r}, {size!r}')
        if not size:
            continue
        overlap = occupied[addr:addr + size]
        if entry[5] and (not hangul_only or any('가' <= c <= '힣' for c in entry[5])):
            if not any(overlap):
                owners[addr] = entry
            elif not all(overlap):
                unsupported.append((addr, 'partially superseded owner'))
        occupied[addr:addr + size] = b'\1' * size
    return owners, unsupported


def validate_manifest(rom, manifest, original=None, writes=None):
    if writes is not None:
        for index,entry in enumerate(writes):
            if entry[7]!='dialogue-spacing-final-intent':continue
            if len(entry)<9:raise ValueError('unbound final spacing intent')
            evidence=entry[8];prior=evidence.get('prior_write_index')
            if type(prior)is not int or not 0<=prior<index:
                raise ValueError('invalid final spacing intent history index')
            old=writes[prior]
            digest=hashlib.sha256(json.dumps(old,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if (digest!=evidence['prior_write_sha256'] or old[5]!=evidence['authored_before']
                    or ''.join((entry[5] or '').split())!=''.join((old[5] or '').split())):
                raise ValueError('final spacing intent changes historical authored wording')
        operations = {}
        for entry in writes:
            if not entry[7].startswith('repoint:'):
                continue
            source = int(entry[7].split(':', 1)[1], 16)
            if source in operations or len(entry) < 9:
                raise ValueError(f'duplicate or unbound relocation write: 0x{source:X}')
            operations[source] = entry
        records = [m for m in manifest if m.get('status') == 'relocated']
        if {int(m['msg'], 16) for m in records} != operations.keys():
            raise ValueError('relocation write/manifest population mismatch')
        for m in records:
            source = int(m['msg'], 16)
            entry = operations[source]
            binding = entry[8]
            if (entry[:2] != [int(m['new_addr'], 16), m['new_len']]
                    or binding['source'] != source or binding['old_len'] != m['old_len']
                    or set(binding['ptr_sites']) != {int(s, 16) for s in m['ptr_sites']}):
                raise ValueError(f'relocation write/manifest destination mismatch: 0x{source:X}')
            if binding['source_spans'] != m.get('source_spans'):
                raise ValueError(f'relocation write/source owner mismatch: 0x{source:X}')
    mapped, ranges, seen_msgs = {}, [], set()
    targets = {int(m['msg'], 16) for m in manifest if m.get('status') == 'relocated'}
    original_sites = collections.defaultdict(set)
    if original is not None:
        for index, (value,) in enumerate(struct.iter_unpack('<I', original[:len(original) // 4 * 4])):
            if value - 0x08000000 in targets:
                original_sites[value - 0x08000000].add(index * 4)
    for m in manifest:
        if m.get('status') != 'relocated':
            continue
        source, target = int(m['msg'], 16), int(m['new_addr'], 16)
        old_len, new_len = m['old_len'], m['new_len']
        if source in seen_msgs:
            raise ValueError(f'duplicate message 0x{source:X}')
        seen_msgs.add(source)
        if min(source, target) < 0 or min(old_len, new_len) <= 0 or max(source + old_len, target + new_len) > len(rom):
            raise ValueError(f'message bounds invalid: 0x{source:X}')
        sites = {int(x, 16) for x in m.get('ptr_sites', [])}
        if not sites or int(m['ptr_off'], 16) not in sites:
            raise ValueError(f'missing pointer sites: 0x{source:X}')
        excluded = {int(x, 16) for x in m.get('pointer_classification', {}).get('excluded_sites', [])}
        if original is not None and sites != original_sites[source] - excluded:
            raise ValueError(f'incomplete original pointer mapping: 0x{source:X}')
        for off in sites:
            if off < 0 or off + 4 > len(rom) or int.from_bytes(rom[off:off + 4], 'little') != 0x08000000 + target:
                raise ValueError(f'pointer mismatch 0x{off:06X}')
        spans = m.get('line_spans', {})
        if len(spans) != m.get('lines') or not set(m.get('fixed', [])) <= spans.keys():
            raise ValueError(f'incomplete line mapping: 0x{source:X}')
        # New manifests bind every source owner to its output and authored text.
        if 'source_spans' not in m or 'source_texts' not in m:
            raise ValueError(f'missing source owner coverage: 0x{source:X}')
        if spans.keys() != m['source_spans'].keys() or spans.keys() != m['source_texts'].keys():
            raise ValueError(f'incomplete source owner mapping: 0x{source:X}')
        for key in spans:
            addr = int(key, 16)
            length = m['source_spans'][key]
            if not source <= addr < addr + length <= source + old_len or addr in mapped:
                raise ValueError(f'source span invalid: {key}')
            for offset, length in fragments(m, key):
                if offset < 0 or length <= 0 or offset + length > new_len:
                    raise ValueError(f'payload span out of bounds: {key}')
            mapped[addr] = m
        ranges.append((source, source + old_len, target, target + new_len))
    for column in (0, 2):
        ordered = sorted((r[column], r[column + 1]) for r in ranges)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('overlapping relocated message ranges')
    for entry in writes or ():
        if entry[7]!='dialogue-spacing-final-intent':continue
        evidence=entry[8];address=evidence['source_address'];m=mapped.get(address)
        if m is None:raise ValueError('final spacing intent has no mapped source')
        key=f'0x{address:06X}';parts=fragments(m,key);lo=parts[0][0];hi=max(off+size for off,size in parts)
        if (evidence['fragments']!=parts or entry[0]!=int(m['new_addr'],16)+lo or entry[1]!=hi-lo
                or any(off<hi and lo<off+size for other in m['line_spans'] if other!=key
                       for off,size in fragments(m,other))):
            raise ValueError('final spacing intent envelope/source mismatch')
    return mapped, ranges


def decode_payload(payload, codes):
    # Token aware: 0x72 may also be the trail byte of a Hangul glyph.
    out, i = bytearray(), 0
    while i < len(payload):
        b = payload[i]
        if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF) and i + 1 < len(payload):
            out.extend(payload[i:i + 2]); i += 2
        elif payload[i:i + 3] == b'\x72\x0a\x09':
            out.extend(b'\x81\x40'); i += 3
        elif b == 0x72:
            out.extend(b'\x81\x40'); i += 1
        elif b in (9,10,13):
            i += 1  # native non-drawing format instructions, not missing glyphs
        else:
            out.append(b); i += 1
    return decode_enc(out, codes).rstrip(' \u3000\x00▯')


def rendered_rows(rom, manifest, writes, original=None):
    owners, unsupported = final_owner_spans(writes, len(rom))
    mapped, ranges = validate_manifest(rom, manifest, original, writes)
    codes = load_syl()
    rows = []
    for addr, m in mapped.items():
        key = f'0x{addr:06X}'
        payload = row_bytes(rom, m, key)
        text = m['source_texts'][key]
        parts = fragments(m, key)
        target = int(m['new_addr'], 16)
        # Explicit final writers in the relocated arena supersede source intent.
        owner = owners.get(target + parts[0][0])
        bounded_multi=(owner and len(owner)>8 and owner[7]=='dialogue-spacing-final-intent'
                       and owner[8].get('source_address')==addr
                       and owner[8].get('fragments')==parts
                       and owner[1]==max(off+size for off,size in parts)-parts[0][0]
                       and not any(off<parts[0][0]+owner[1] and parts[0][0]<off+size
                                   for other in m['line_spans'] if other!=key
                                   for off,size in fragments(m,other)))
        if owner and (len(parts) == 1 and owner[1] == parts[0][1] or bounded_multi):
            text = owner[5]
        rows.append(dict(addr=addr, slot=len(payload), intended=text or '',
                         shipped=decode_payload(payload, codes), relocated=True,
                         kind='repoint', level=None))
    for addr, entry in owners.items():
        containing = [r for r in ranges if r[0] <= addr < r[1]]
        if containing:
            if addr not in mapped:
                unsupported.append((addr, 'source owner merged or superseded by relocated owner'))
            continue  # Never fall back to stale in-place fragments.
        if any(lo <= addr < hi for _, _, lo, hi in ranges):
            continue
        rows.append(dict(addr=addr, slot=entry[1], intended=entry[5],
                         shipped=decode_payload(rom[addr:addr + entry[1]], codes),
                         relocated=False, kind=entry[7], level=entry[6]))
    return rows, unsupported


def check(rom, manifest, writes, original=None):
    rows, unsupported = rendered_rows(rom, manifest, writes, original)
    jams = []
    checked = 0
    for row in rows:
        expected, _ = separator_signature(row['intended'])
        shipped, _ = separator_signature(row['shipped'])
        if not expected or not any('가' <= ch <= '힣' for ch in expected):
            unsupported.append((row['addr'], 'no authored Hangul owner'))
        elif expected != shipped:
            unsupported.append((row['addr'], 'wording/control/compact encoding differs; spacing comparison unsupported'))
        else:
            checked += 1
            if is_jammed(row['intended'], row['shipped']):
                jams.append((row['addr'], row['intended'], row['shipped']))
    return checked, jams, unsupported


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', type=Path, required=True)
    ap.add_argument('--map', type=Path, default=ROOT / 'temp/integrity_map.json')
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    try:
        verify_provenance(args.rom, args.map, args.manifest)
        count, jams, unsupported = check(args.rom.read_bytes(), json.loads(args.manifest.read_text()),
            json.loads(args.map.read_text()), (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'FAIL: {exc}')
        return 2
    print(f'final owner rows checked: {count}; final-ROM jams: {len(jams)}; unsupported coverage: {len(unsupported)}')
    print('Byte spacing audit only; unsupported rows and renderer attribution are not a verified baseline.')
    if args.list:
        for a, authored, shipped in jams:
            print(f'JAM 0x{a:06X}\t{authored}\t{shipped}')
        for a, reason in unsupported:
            print(f'UNSUPPORTED 0x{a:06X}\t{reason}')
    if args.json:
        args.json.write_text(json.dumps(dict(checked=count, jams=jams, unsupported=unsupported), ensure_ascii=False, indent=2))
    return int(bool(jams))


if __name__ == '__main__':
    raise SystemExit(main())
