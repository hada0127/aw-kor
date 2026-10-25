"""Read-only exact build0616 preservation, including unknown metadata."""
from b830ac_contract import START, TAIL, END, ROW


def validate(old, new, old_manifest, new_manifest, old_lossless, new_lossless):
    target = f'0x{START:06X}'
    skip = {'msg': target, 'status': 'skip_impure_span'}
    matches = [i for i, m in enumerate(old_manifest) if m.get('msg') == target]
    if len(matches) != 1 or old_manifest[matches[0]] != skip:
        raise AssertionError('baseline requires exactly one exact B830AC skip_impure_span')
    index = matches[0]
    # Only this obsolete skip disappears; every remaining record stays exact.
    expected_manifest = old_manifest[:index] + old_manifest[index+1:]
    if expected_manifest != new_manifest:
        raise AssertionError('manifest metadata/address/order changed')
    records = [m for m in old_manifest if m.get('status') == 'relocated']
    if len(records) != 2982 or len({m['msg'] for m in records}) != 2982:
        raise AssertionError('expected all 2982 unique relocations')
    for m in records:
        addr, size = int(m['new_addr'],16), m['new_len']
        if not 0 <= addr < addr+size <= len(old):
            raise AssertionError('invalid allocation')
        if old[addr:addr+size] != new[addr:addr+size]:
            raise AssertionError('relocated payload changed')
        sites = m['ptr_sites']
        if not sites or m['ptr_off'] not in sites or len(set(sites)) != len(sites):
            raise AssertionError('invalid pointer sites')
        for site in sites:
            pos = int(site,16)
            expected = (0x08000000+addr).to_bytes(4,'little')
            if old[pos:pos+4] != expected or new[pos:pos+4] != expected:
                raise AssertionError('relocated pointer changed')
    if old_lossless != new_lossless:
        raise AssertionError('lossless metadata/arrays/order changed')
    fixed = {a for m in records for a in m.get('fixed',[])}
    remaining = [a for a in old_lossless['requested'] if f'0x{int(a,16):06X}' not in fixed]
    if (len(old_lossless['requested']) != 1710 or len(remaining) != 9
            or remaining != old_lossless['unfulfilled']):
        raise AssertionError('lossless 1710/9 changed')
    if len(old) != len(new) or bytes(new[START:END]) != ROW+b'\0'*4:
        raise AssertionError('final source24/tail4 changed')
    expected = [START+i for i,(a,b) in enumerate(zip(old[START:TAIL],ROW)) if a != b]
    if len(expected) != 16:
        raise AssertionError('baseline source difference is not 16B')
    if old[:START] != new[:START] or old[TAIL:] != new[TAIL:]:
        raise AssertionError('difference outside source24 (neighbors/table included)')
    return dict(preserved=2982,changed_offsets=expected,requested=1710,unfulfilled=9)
