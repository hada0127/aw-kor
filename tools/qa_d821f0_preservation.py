"""Exact 2984→2985 preservation gate; no runtime or residual-census claim."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import d821f0_contract as c


def lossless(before, after, manifest):
    if before != after or set(after) != {'requested','unfulfilled'}:
        raise AssertionError('D821F0 lossless arrays/order changed')
    requested, unfulfilled = after['requested'], after['unfulfilled']
    fixed = {int(a,16) for m in manifest if m.get('status') == 'relocated' for a in m.get('fixed',[])}
    if (len(requested) != 1710 or len(set(requested)) != 1710 or len(unfulfilled) != 9
            or c.FIRST in {int(a,16) for a in requested}
            or [a for a in requested if int(a,16) not in fixed] != unfulfilled):
        raise AssertionError('D821F0 lossless 1710/1701/9 recomputation differs')


def baseline(rom, manifest):
    old = [m for m in manifest if m.get('status') == 'relocated']
    if len(old) != 2984 or len({m['msg'] for m in old}) != 2984:
        raise AssertionError('D821F0 old2984 missing/duplicate')
    for m in old:
        start, size = int(m['new_addr'],16), int(m['new_len'])
        if not c.ARENA_START <= start < start+size <= c.HIGH_WATER:
            raise AssertionError('D821F0 old allocation boundary/overlap')
        sites = m['ptr_sites']
        if not sites or len(set(sites)) != len(sites) or m['ptr_off'] not in sites:
            raise AssertionError('D821F0 old pointer provenance')
        for site in sites:
            site = int(site,16)
            pointer = (0x08000000+start).to_bytes(4,'little')
            if bytes(rom[site:site+4]) != pointer:
                raise AssertionError('D821F0 old pointer bytes changed')
    spans = sorted((int(m['new_addr'],16), int(m['new_addr'],16)+m['new_len']) for m in old)
    if max(end for start,end in spans) != c.HIGH_WATER or any(
            left[1] > right[0] for left,right in zip(spans,spans[1:])):
        raise AssertionError('D821F0 old allocation overlap/high-water')
    return old


def validate(old_rom, new_rom, old_manifest, new_manifest, old_log, new_log):
    if any(int(m['msg'],16) == c.MESSAGE for m in old_manifest) or c.source_owners(old_manifest):
        raise AssertionError('D821F0 old manifest already contains target/source')
    expected = old_manifest + [c.record()]
    if new_manifest != expected:
        raise AssertionError('D821F0 full metadata/order/address/skip preservation failed')
    old = baseline(old_rom, old_manifest)
    for m in old:
        start, size = int(m['new_addr'],16), int(m['new_len'])
        if bytes(old_rom[start:start+size]) != bytes(new_rom[start:start+size]):
            raise AssertionError('D821F0 old payload bytes changed')
        for site in m['ptr_sites']:
            site = int(site,16)
            if bytes(new_rom[site:site+4]) != bytes(old_rom[site:site+4]):
                raise AssertionError('D821F0 old pointer bytes changed')
    # The prior residual owner changes role in place; no other writer may move.
    import copy
    expected_log = copy.deepcopy(old_log)
    candidates = [r for r in expected_log if r[0] == c.FIRST and
                  r[7] in ('bteam-round2-residual', c.RETAINED_WRITER)]
    if len(candidates) != 1:
        raise AssertionError('D821F0 prior retained/residual owner missing or duplicate')
    candidates[0][7] = c.RETAINED_WRITER
    if candidates[0] != c.retained_owner():
        raise AssertionError('D821F0 prior residual owner metadata changed')
    without_append = [r for r in new_log if r[7] != c.DISPLAY_WRITER]
    if len(new_log) != len(old_log)+1 or without_append != expected_log:
        raise AssertionError('D821F0 prior active/retired writer log changed')
    c.final(new_rom,new_manifest,new_log)
    if bytes(old_rom[c.MESSAGE:c.END]) != c.CURRENT:
        raise AssertionError('D821F0 old current native40 changed')
    if bytes(old_rom[c.SITE:c.SITE+4]) != (0x08000000+c.MESSAGE).to_bytes(4,'little'):
        raise AssertionError('D821F0 old sole pointer changed')
    if bytes(old_rom[c.APPEND:c.APPEND+40]) != b'\xff'*40:
        raise AssertionError('D821F0 old append/alignment not free')
    if len(old_rom) != len(new_rom):
        raise AssertionError('D821F0 ROM size changed')
    # All other bytes, including every protected resource and native neighbor.
    ranges = [(c.APPEND,c.APPEND+40),(c.SITE,c.SITE+4)]
    pos = 0
    changed = 0
    for start,end in ranges:
        if old_rom[pos:start] != new_rom[pos:start]:
            raise AssertionError('D821F0 unexpected ROM difference outside write set')
        changed += sum(a != b for a,b in zip(old_rom[start:end],new_rom[start:end]))
        pos = end
    if old_rom[pos:] != new_rom[pos:]:
        raise AssertionError('D821F0 unexpected ROM tail difference')
    return dict(preserved=2984,added=c.KEY,changed_bytes=changed,retired_allocations=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom','new-rom','old-manifest','new-manifest','old-log','new-log',
                 'old-lossless','new-lossless'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    # Fresh-build comparison must bind the accepted build0916 final baseline.
    pins = {'old_rom': '634cc03f6abd4be50b645ce1ce73835ece0386abe800ed09171399fbd4896db5', 'old_manifest': 'fb3da52ab18576f7e4a901db0d35ce9c7080d1bf671c96ddf72fa0ed1531d263', 'old_log': 'a24f0dac05b369f009f3351d427b44b0338ceb96f58a3c3b27578ddce1fe78d4', 'old_lossless': '93c235df8a6cba7a620cd1509268ef97b10536ac5f001935a2e24d54dbfb584a'}
    for key, digest in pins.items():
        if sha256(getattr(a,key).read_bytes()).hexdigest() != digest:
            raise AssertionError(f'D821F0 accepted0916 baseline mismatch: {key}')
    read=lambda path:json.loads(path.read_text())
    old,new=read(a.old_manifest),read(a.new_manifest)
    result=validate(a.old_rom.read_bytes(),a.new_rom.read_bytes(),old,new,
                    read(a.old_log),read(a.new_log))
    lossless(read(a.old_lossless),read(a.new_lossless),new)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
