"""Exact 2982→2983 preservation gate; no runtime or residual-census claim."""
import argparse
import json
from pathlib import Path
import b82fac_contract as c


def lossless(before, after, manifest):
    if before != after or set(after) != {'requested','unfulfilled'}:
        raise AssertionError('B82FAC lossless arrays/order changed')
    requested, unfulfilled = after['requested'], after['unfulfilled']
    fixed = {int(a,16) for m in manifest if m.get('status') == 'relocated' for a in m.get('fixed',[])}
    if (len(requested) != 1710 or len(set(requested)) != 1710 or len(unfulfilled) != 9
            or c.MESSAGE in {int(a,16) for a in requested}
            or [a for a in requested if int(a,16) not in fixed] != unfulfilled):
        raise AssertionError('B82FAC lossless 1710/1701/9 recomputation differs')


def validate(old_rom, new_rom, old_manifest, new_manifest, old_log, new_log):
    target = [m for m in old_manifest if int(m['msg'],16) == c.MESSAGE]
    if target != [dict(msg=c.KEY,status='skip_wide_line',lines=[c.KEY])]:
        raise AssertionError('B82FAC old skip must be exactly one')
    expected = [m for m in old_manifest if int(m['msg'],16) != c.MESSAGE]
    expected += [dict(c.METADATA,new_addr=f'0x{c.APPEND:06X}')]
    if new_manifest != expected:
        raise AssertionError('B82FAC full metadata/order/address/skip preservation failed')
    old = [m for m in old_manifest if m.get('status') == 'relocated']
    if len(old) != 2982 or len({m['msg'] for m in old}) != 2982:
        raise AssertionError('B82FAC old2982 missing/duplicate')
    for m in old:
        start, size = int(m['new_addr'],16), int(m['new_len'])
        if not c.ARENA_START <= start < start+size <= c.APPEND:
            raise AssertionError('B82FAC old allocation boundary/overlap')
        if bytes(old_rom[start:start+size]) != bytes(new_rom[start:start+size]):
            raise AssertionError('B82FAC old payload bytes changed')
        sites = m['ptr_sites']
        if not sites or len(set(sites)) != len(sites) or m['ptr_off'] not in sites:
            raise AssertionError('B82FAC old pointer provenance')
        for site in sites:
            site = int(site,16)
            pointer = (0x08000000+start).to_bytes(4,'little')
            if bytes(old_rom[site:site+4]) != pointer or bytes(new_rom[site:site+4]) != pointer:
                raise AssertionError('B82FAC old pointer bytes changed')
    # The prior residual owner changes role in place; no other writer may move.
    import copy
    expected_log = copy.deepcopy(old_log)
    for row in expected_log:
        if row[0] == c.MESSAGE and row[7] == 'bteam-round2-residual':
            row[7] = c.RETAINED_WRITER
    without_append = [r for r in new_log if r[7] != 'repoint:0xB82FAC']
    if len(new_log) != len(old_log)+1 or without_append != expected_log:
        raise AssertionError('B82FAC prior active/retired writer log changed')
    c.final(new_rom,new_manifest,new_log)
    if bytes(old_rom[c.MESSAGE:c.END]) != c.CURRENT:
        raise AssertionError('B82FAC old current native48 changed')
    if bytes(old_rom[c.SITE:c.SITE+4]) != (0x08000000+c.MESSAGE).to_bytes(4,'little'):
        raise AssertionError('B82FAC old sole pointer changed')
    if bytes(old_rom[c.APPEND:c.APPEND+52]) != b'\xff'*52:
        raise AssertionError('B82FAC old append/alignment not free')
    if len(old_rom) != len(new_rom):
        raise AssertionError('B82FAC ROM size changed')
    # All other bytes, including every protected resource and native neighbor.
    ranges = [(c.APPEND,c.APPEND+50),(c.SITE,c.SITE+4)]
    pos = 0
    changed = 0
    for start,end in ranges:
        if old_rom[pos:start] != new_rom[pos:start]:
            raise AssertionError('B82FAC unexpected ROM difference outside write set')
        changed += sum(a != b for a,b in zip(old_rom[start:end],new_rom[start:end]))
        pos = end
    if old_rom[pos:] != new_rom[pos:]:
        raise AssertionError('B82FAC unexpected ROM tail difference')
    return dict(preserved=2982,added=c.KEY,changed_bytes=changed,retired_allocations=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom','new-rom','old-manifest','new-manifest','old-log','new-log',
                 'old-lossless','new-lossless'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    read=lambda path:json.loads(path.read_text())
    old,new=read(a.old_manifest),read(a.new_manifest)
    result=validate(a.old_rom.read_bytes(),a.new_rom.read_bytes(),old,new,
                    read(a.old_log),read(a.new_log))
    lossless(read(a.old_lossless),read(a.new_lossless),new)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
