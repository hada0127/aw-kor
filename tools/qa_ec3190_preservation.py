"""Read-only 2981→2982 logical preservation gate; not a full ROM diff/runtime gate."""
import argparse
import json
from pathlib import Path
from ec3190_contract import MESSAGE, SITE, END, validate as validate_contract, assert_manifest


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
    if len(old) != 2981 or MESSAGE in old or set(new) != set(old)|{MESSAGE}:
        raise AssertionError('expected 2981 preserved messages plus EC3190 only')
    for key,before in old.items():
        after = new[key]
        logical = lambda m: {k:v for k,v in m.items() if k != 'new_addr'}
        if logical(before) != logical(after): raise AssertionError(f'{key:06X} logical metadata changed')
        if payload(old_rom,before) != payload(new_rom,after): raise AssertionError(f'{key:06X} payload changed')
    validate_contract(payload(new_rom,new[MESSAGE]),new[MESSAGE])
    if old_rom[SITE:SITE+4] != bytes.fromhex('9031ec08'):
        raise AssertionError('EC3190 original table pointer changed')
    # Prior candidate neighbors remain translated; only source42 returns native.
    from ec3190_contract import FIRST, TAIL, NATIVE, CONSUMER_BYTES
    ranges = [(MESSAGE-32,FIRST),(TAIL,END+64)]
    for start,raw in CONSUMER_BYTES.items():
        if start <= SITE < start+len(raw):
            ranges.extend(((start,SITE),(SITE+4,start+len(raw))))
        else: ranges.append((start,start+len(raw)))
    for start,end in ranges:
        if len(old_rom[start:end]) != end-start or old_rom[start:end] != new_rom[start:end]:
            raise AssertionError('EC3190 native neighbor/table/caller changed')
    if bytes(new_rom[FIRST:TAIL]) != NATIVE[2:-4]:
        raise AssertionError('EC3190 retired source must return to native42')
    return dict(preserved=2981,added='0xEC3190',physical_allocation_fields=['new_addr'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old-rom','new-rom','old-manifest','new-manifest'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(validate(a.old_rom.read_bytes(),a.new_rom.read_bytes(),
        json.loads(a.old_manifest.read_text()),json.loads(a.new_manifest.read_text())),indent=2))


if __name__ == '__main__': main()
