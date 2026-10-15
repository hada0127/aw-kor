#!/usr/bin/env python3
"""Make a tainted, checksummed cartridge SRAM experiment from a source save.

Offsets passed to --set are relative to the newest 4 KiB save block for the
selected game. The output is deliberately a legacy SRAM import, not a normal
play game-save receipt. The caller must verify the resulting screen in-game.
"""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BLOCK_SIZE = 0x1000
SAVE_SIZE = 0x20000
PARTS = {'p1': (0, 0x10000, b'wars'), 'p2': (0x10000, 0x20000, b'2ars')}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checksum(block):
    """Empirical 4 KiB save checksum, verified across recorded P1/P2 saves."""
    if len(block) != BLOCK_SIZE:
        raise ValueError('Save block must be 4096 bytes')
    return (sum(block[:6]) + sum(block[8:]) - 1) & 0xff


def valid_block(block, signature):
    return (len(block) == BLOCK_SIZE and block[:4] == signature
            and block[5] == (0x09 if signature == b'wars' else 0x0f)
            and (block[4], block[-1]) in ((0x55, 0xaa), (0xaa, 0x55))
            and block[6] == checksum(block) and block[7] == (block[6] ^ 0xff))


def newest_block(save, part):
    if len(save) != SAVE_SIZE:
        raise ValueError('Expected exact 128 KiB cartridge SRAM')
    start, stop, signature = PARTS[part]
    candidates = []
    for offset in range(start, stop, BLOCK_SIZE):
        block = save[offset:offset + BLOCK_SIZE]
        if block[:4] == signature:
            if not valid_block(block, signature):
                raise ValueError(f'Invalid {part} save block at {offset:#x}')
            candidates.append((int.from_bytes(block[8:12], 'little'), offset))
    if not candidates:
        raise ValueError(f'No validated {part} save block found')
    counters = [counter for counter, _ in candidates]
    if len(counters) != len(set(counters)):
        raise ValueError('Ambiguous save-block counters')
    return max(candidates)[1]


def parse_edit(spec):
    try:
        offset_s, value_s = spec.split('=', 1)
        offset, value = int(offset_s, 0), int(value_s, 0)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid --set {spec!r}; expected 0xOFFSET=0xBYTE') from exc
    if not 0x10 <= offset < BLOCK_SIZE - 1:
        raise ValueError('Edit must be within save-block payload 0x10..0xffe')
    if not 0 <= value <= 0xff:
        raise ValueError('Edit value must be one byte')
    return offset, value


def mutate(save, part, edits):
    base = newest_block(save, part)
    output = bytearray(save)
    changes = []
    offsets = set()
    for relative, value in edits:
        if not 0x10 <= relative < BLOCK_SIZE - 1 or not 0 <= value <= 0xff:
            raise ValueError('Edit must be a payload byte at 0x10..0xffe')
        if relative in offsets:
            raise ValueError(f'Duplicate edit offset {relative:#x}')
        offsets.add(relative)
        absolute = base + relative
        before = output[absolute]
        if before == value:
            raise ValueError(f'No-op edit at {relative:#x}')
        output[absolute] = value
        changes.append({'block_offset': f'0x{relative:03x}', 'absolute_offset': f'0x{absolute:05x}',
                        'before': f'0x{before:02x}', 'after': f'0x{value:02x}'})
    if not changes:
        raise ValueError('At least one edit is required')
    old_checksum = save[base + 6]
    output[base + 6] = checksum(output[base:base + BLOCK_SIZE])
    output[base + 7] = output[base + 6] ^ 0xff
    if not valid_block(output[base:base + BLOCK_SIZE], PARTS[part][2]):
        raise AssertionError('Generated checksum did not validate')
    return bytes(output), base, old_checksum, changes


def make_save(source, out, part, edit_specs, expected_sha):
    source = source.resolve()
    out = out.resolve()
    temp = (ROOT / 'temp').resolve()
    if temp not in out.parents or out.suffix != '.sav':
        raise ValueError('Output must be a new .sav file under project temp/')
    receipt_path = out.with_suffix('.json')
    if source == out or out.exists() or receipt_path.exists():
        raise FileExistsError('Output save or receipt already exists')
    data = source.read_bytes()
    source_sha = digest(data)
    if source_sha != expected_sha:
        raise ValueError(f'Source SHA-256 mismatch: {source_sha}')
    edits = [parse_edit(x) for x in edit_specs]
    result, base, old_checksum, changes = mutate(data, part, edits)
    registry = json.loads((ROOT / 'data/game_save_cheat_provenance.json').read_text())
    provenance_class = 'legacy_unverified_sram'
    if registry['provenance_classes'][provenance_class]['cheat_tainted'] is not True:
        raise ValueError('Provenance registry does not require cheat taint')
    receipt = {'kind': 'sram-cheat-v1', 'provenance_class': provenance_class,
               'cheat_tainted': True, 'evidence_scope': 'Screen QA only; not normal-play progress',
               'source': str(source), 'source_sha256': source_sha,
               'part': part, 'block_offset': f'0x{base:05x}', 'edits': changes,
               'checksum_before': f'0x{old_checksum:02x}',
               'checksum_after': f'0x{result[base + 6]:02x}',
               'result': str(out), 'result_sha256': digest(result)}
    out.parent.mkdir(parents=True, exist_ok=True)
    created_save = False
    created_receipt = False
    try:
        with out.open('xb') as file:
            created_save = True
            file.write(result)
        with receipt_path.open('x', encoding='utf-8') as file:
            created_receipt = True
            json.dump(receipt, file, ensure_ascii=False, indent=2)
            file.write('\n')
    except BaseException:
        if created_receipt:
            receipt_path.unlink()
        if created_save:
            out.unlink()
        raise
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--part', choices=sorted(PARTS), required=True)
    parser.add_argument('--set', dest='edits', action='append', required=True,
                        help='Relative payload byte: 0xOFFSET=0xBYTE; repeatable')
    args = parser.parse_args()
    print(make_save(args.source, args.out, args.part, args.edits, args.source_sha256))


if __name__ == '__main__':
    main()
