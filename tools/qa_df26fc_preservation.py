"""Post-build DF26FC comparison; reads published ROMs, never builds or writes them.

This is the logical-message preservation gate, not a complete ROM diff/runtime gate.
Only new_addr is physical allocation metadata; unknown future fields stay protected.
"""
import argparse
import json
from pathlib import Path

from df26fc_contract import MESSAGE, PAYLOAD

PHYSICAL_ALLOCATION_FIELDS = frozenset({'new_addr'})


def validate(old_rom, new_rom, old_manifest, new_manifest):
    def records(manifest):
        result = {}
        for m in manifest:
            if m.get('status') != 'relocated':
                continue
            key = int(m['msg'], 16)
            if key in result:
                raise AssertionError('duplicate logical message')
            result[key] = m
        return result

    def payload(rom, m):
        address, size = int(m['new_addr'], 16), m['new_len']
        if not (0 <= address < address + size <= len(rom)):
            raise AssertionError('allocation outside ROM')
        sites = m['ptr_sites']
        if not sites or len(set(sites)) != len(sites):
            raise AssertionError('missing/duplicate pointer sites')
        for site in sites:
            offset = int(site, 16)
            if not (0 <= offset <= len(rom) - 4) or int.from_bytes(
                    rom[offset:offset+4], 'little') != 0x08000000 + address:
                raise AssertionError('pointer differs from manifest allocation')
        return bytes(rom[address:address+size])

    old, new = records(old_manifest), records(new_manifest)
    if len(old) != 2976 or MESSAGE in old or set(new) != set(old) | {MESSAGE}:
        raise AssertionError('expected 2976 preserved messages plus DF26FC only')
    for key, before in old.items():
        after = new[key]
        logical = lambda m: {k: v for k, v in m.items() if k not in PHYSICAL_ALLOCATION_FIELDS}
        if logical(before) != logical(after):
            raise AssertionError(f'{key:06X} logical metadata changed')
        if payload(old_rom, before) != payload(new_rom, after):
            raise AssertionError(f'{key:06X} payload changed')
    if payload(new_rom, new[MESSAGE]) != PAYLOAD:
        raise AssertionError('DF26FC payload changed')
    # Adjacent native message and controls are protected independently of relocation.
    for start, end in ((0xDF26FC, 0xDF26FE), (0xDF2726, 0xDF2754),
                       (0xDF2754, 0xDF2754 + 59)):
        if bytes(old_rom[start:end]) != bytes(new_rom[start:end]):
            raise AssertionError('native controls/companion/next message changed')
    return {'preserved': len(old), 'added': '0xDF26FC',
            'physical_allocation_fields': sorted(PHYSICAL_ALLOCATION_FIELDS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom', 'new-rom', 'old-manifest', 'new-manifest'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.old_rom.read_bytes(), args.new_rom.read_bytes(),
                             json.loads(args.old_manifest.read_text()),
                             json.loads(args.new_manifest.read_text())), indent=2))


if __name__ == '__main__':
    main()
