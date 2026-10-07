"""candidate = reference ROM + (B where A != B). Valid only if A == reference at all those bytes.

usage: overlay.py BUILD_A BUILD_B REFERENCE_ROM OUT  (see tools/linux_overlay_build.sh)
"""
import hashlib, json, sys
A, B, REF, OUT = sys.argv[1:5]
a = open(A, 'rb').read(); b = open(B, 'rb').read(); ref = bytearray(open(REF, 'rb').read())
assert len(a) == len(b) == len(ref)
changed = [i for o in range(0, len(a), 4096) if a[o:o+4096] != b[o:o+4096]
           for i in range(o, min(o+4096, len(a))) if a[i] != b[i]]
conflict = [i for i in changed if a[i] != ref[i]]
# font-asset regions where A differs from ref must not be touched by B either
fontdiff = {i for o in range(0, len(a), 4096) if a[o:o+4096] != ref[o:o+4096]
            for i in range(o, min(o+4096, len(a))) if a[i] != ref[i]}
print('A!=B bytes', len(changed), 'conflicts(A!=ref at changed)', len(conflict),
      'A!=ref bytes', len(fontdiff), 'overlap', len(fontdiff & set(changed)))
if conflict:
    print('first conflicts', [hex(i) for i in conflict[:20]]); sys.exit(2)
for i in changed:
    ref[i] = b[i]
# header complement checksum 0xBD over 0xA0..0xBC
chk = (-sum(ref[0xA0:0xBD]) - 0x19) & 0xFF
assert ref[0xBD] == chk, 'header checksum changed unexpectedly'
open(OUT, 'wb').write(ref)
print('sha256', hashlib.sha256(ref).hexdigest())
print('B==candidate except A!=ref font regions:', all(ref[i] == b[i] for i in range(len(b)) if i not in fontdiff))
