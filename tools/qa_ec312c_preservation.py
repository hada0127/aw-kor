"""Exact 2983→2984 preservation gate; no runtime or residual-census claim."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import ec312c_contract as c


def lossless(before, after, manifest):
    if before != after or set(after) != {'requested','unfulfilled'}:
        raise AssertionError('EC312C lossless arrays/order changed')
    requested, unfulfilled = after['requested'], after['unfulfilled']
    fixed = {int(a,16) for m in manifest if m.get('status') == 'relocated' for a in m.get('fixed',[])}
    if (len(requested) != 1710 or len(set(requested)) != 1710 or len(unfulfilled) != 9
            or c.FIRST in {int(a,16) for a in requested}
            or [a for a in requested if int(a,16) not in fixed] != unfulfilled):
        raise AssertionError('EC312C lossless 1710/1701/9 recomputation differs')


def baseline(rom, manifest):
    old = [m for m in manifest if m.get('status') == 'relocated']
    if len(old) != 2983 or len({m['msg'] for m in old}) != 2983:
        raise AssertionError('EC312C old2983 missing/duplicate')
    for m in old:
        start, size = int(m['new_addr'],16), int(m['new_len'])
        if not c.ARENA_START <= start < start+size <= c.APPEND:
            raise AssertionError('EC312C old allocation boundary/overlap')
        sites = m['ptr_sites']
        if not sites or len(set(sites)) != len(sites) or m['ptr_off'] not in sites:
            raise AssertionError('EC312C old pointer provenance')
        for site in sites:
            site = int(site,16)
            pointer = (0x08000000+start).to_bytes(4,'little')
            if bytes(rom[site:site+4]) != pointer:
                raise AssertionError('EC312C old pointer bytes changed')
    spans = sorted((int(m['new_addr'],16), int(m['new_addr'],16)+m['new_len']) for m in old)
    if max(end for start,end in spans) != c.HIGH_WATER or any(
            left[1] > right[0] for left,right in zip(spans,spans[1:])):
        raise AssertionError('EC312C old allocation overlap/high-water')
    return old


def validate(old_rom, new_rom, old_manifest, new_manifest, old_log, new_log):
    target = [m for m in old_manifest if int(m['msg'],16) == c.MESSAGE]
    if target != [dict(msg=c.KEY,status='skip_wide_line',lines=[c.SOURCE_KEY])]:
        raise AssertionError('EC312C old skip must be exactly one')
    expected = [m for m in old_manifest if int(m['msg'],16) != c.MESSAGE]
    expected += [dict(c.METADATA,new_addr=f'0x{c.APPEND:06X}')]
    if new_manifest != expected:
        raise AssertionError('EC312C full metadata/order/address/skip preservation failed')
    old = baseline(old_rom, old_manifest)
    for m in old:
        start, size = int(m['new_addr'],16), int(m['new_len'])
        if bytes(old_rom[start:start+size]) != bytes(new_rom[start:start+size]):
            raise AssertionError('EC312C old payload bytes changed')
        for site in m['ptr_sites']:
            site = int(site,16)
            if bytes(new_rom[site:site+4]) != bytes(old_rom[site:site+4]):
                raise AssertionError('EC312C old pointer bytes changed')
    # The prior residual owner changes role in place; no other writer may move.
    import copy
    expected_log = copy.deepcopy(old_log)
    for row in expected_log:
        if row[0] == c.FIRST and row[7] == 'bteam-round2-residual':
            row[7] = c.RETAINED_WRITER
    without_append = [r for r in new_log if r[7] != 'repoint:0xEC312C']
    if len(new_log) != len(old_log)+1 or without_append != expected_log:
        raise AssertionError('EC312C prior active/retired writer log changed')
    c.final(new_rom,new_manifest,new_log)
    if bytes(old_rom[c.MESSAGE:c.END]) != c.CURRENT:
        raise AssertionError('EC312C old current native52 changed')
    if bytes(old_rom[c.SITE:c.SITE+4]) != (0x08000000+c.MESSAGE).to_bytes(4,'little'):
        raise AssertionError('EC312C old sole pointer changed')
    if bytes(old_rom[c.APPEND:c.APPEND+60]) != b'\xff'*60:
        raise AssertionError('EC312C old append/alignment not free')
    if len(old_rom) != len(new_rom):
        raise AssertionError('EC312C ROM size changed')
    # All other bytes, including every protected resource and native neighbor.
    ranges = [(c.APPEND,c.APPEND+58),(c.SITE,c.SITE+4)]
    pos = 0
    changed = 0
    for start,end in ranges:
        if old_rom[pos:start] != new_rom[pos:start]:
            raise AssertionError('EC312C unexpected ROM difference outside write set')
        changed += sum(a != b for a,b in zip(old_rom[start:end],new_rom[start:end]))
        pos = end
    if old_rom[pos:] != new_rom[pos:]:
        raise AssertionError('EC312C unexpected ROM tail difference')
    return dict(preserved=2983,added=c.KEY,changed_bytes=changed,retired_allocations=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom','new-rom','old-manifest','new-manifest','old-log','new-log',
                 'old-lossless','new-lossless'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    # Fresh-build comparison must bind the accepted build0816 final baseline.
    pins = {
        'old_rom': 'df095a51619ef2ee2c244d5438e15f316d0201858503a6651e33cce5f144d7d0',
        'old_manifest': '7c0649fc45e20205fb785e296b77a243bf0c60fcd622301ab6e291153a7377e4',
        'old_log': 'efae05727e15e9a4e2221260d18e47dbc1398e654a93730dcb5a077f5ab2564c',
        'old_lossless': '93c235df8a6cba7a620cd1509268ef97b10536ac5f001935a2e24d54dbfb584a',
    }
    for key, digest in pins.items():
        if sha256(getattr(a,key).read_bytes()).hexdigest() != digest:
            raise AssertionError(f'EC312C accepted0816 baseline mismatch: {key}')
    read=lambda path:json.loads(path.read_text())
    old,new=read(a.old_manifest),read(a.new_manifest)
    result=validate(a.old_rom.read_bytes(),a.new_rom.read_bytes(),old,new,
                    read(a.old_log),read(a.new_log))
    lossless(read(a.old_lossless),read(a.new_lossless),new)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
