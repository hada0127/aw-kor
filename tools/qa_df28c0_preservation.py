"""Read-only 2980→2981 logical preservation gate; not a full ROM diff/runtime gate."""
import argparse
import json
from pathlib import Path
from df28c0_contract import MESSAGE, SITE, END, validate as validate_contract, assert_manifest


def validate(old_rom, new_rom, old_manifest, new_manifest):
    def records(manifest):
        result = {}
        for m in manifest:
            if m.get('status') != 'relocated': continue
            key = int(m['msg'],16)
            if key in result: raise AssertionError('duplicate logical message')
            result[key] = m
        return result

    def payload(rom,m):
        address,size = int(m['new_addr'],16),m['new_len']
        if not 0 <= address < address+size <= len(rom):
            raise AssertionError('allocation outside ROM')
        sites = [int(s,16) for s in m['ptr_sites']]
        if not sites or len(set(sites)) != len(sites) or int(m['ptr_off'],16) not in sites:
            raise AssertionError('missing/duplicate pointer sites or ptr_off')
        for site in sites:
            if not 0 <= site <= len(rom)-4 or int.from_bytes(rom[site:site+4],'little') != 0x08000000+address:
                raise AssertionError('pointer differs from allocation')
        return bytes(rom[address:address+size])

    assert_manifest(new_manifest)
    old,new = records(old_manifest),records(new_manifest)
    if len(old) != 2980 or MESSAGE in old or set(new) != set(old)|{MESSAGE}:
        raise AssertionError('expected 2980 preserved messages plus DF28C0 only')
    for key,before in old.items():
        after = new[key]
        logical = lambda m: {k:v for k,v in m.items() if k != 'new_addr'}
        if logical(before) != logical(after): raise AssertionError(f'{key:06X} logical metadata changed')
        if payload(old_rom,before) != payload(new_rom,after): raise AssertionError(f'{key:06X} payload changed')
    validate_contract(payload(new_rom,new[MESSAGE]),new[MESSAGE])
    if (old_rom[SITE-4:SITE+4] != bytes.fromhex('19000000c028df08')
            or new_rom[SITE-4:SITE] != bytes.fromhex('19000000')):
        raise AssertionError('DF28C0 caller changed')
    # Next native message compares against the PRIOR CANDIDATE, not source ROM.
    for start,end in ((0xDF28A0,MESSAGE),(MESSAGE,MESSAGE+2),(0xDF28EC,END),(END,0xDF2940)):
        if len(old_rom[start:end]) != end-start or old_rom[start:end] != new_rom[start:end]:
            raise AssertionError('DF28C0 controls/neighbors native changed')
    return dict(preserved=2980,added='0xDF28C0',physical_allocation_fields=['new_addr'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom','new-rom','old-manifest','new-manifest'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(validate(a.old_rom.read_bytes(),a.new_rom.read_bytes(),
        json.loads(a.old_manifest.read_text()),json.loads(a.new_manifest.read_text())),indent=2))


if __name__ == '__main__': main()
