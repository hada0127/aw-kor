"""Candidate cold boot with a T5 copy of native-re/replay-normal/new-eight.sav (ア×8, made by normal keys on the original ROM)
-> native replay-cold route keys/frames (load list -> map -> name re-entry). RAM read after each of the final A presses."""
import json
from t5lib import *
assert sha(EIGHT_SAV)==EIGHT_SAV_SHA
seq=[l for l in (B/'native-re/replay-cold/route.txt').read_text().splitlines() if l.startswith(('keys ','frames '))]
(R/'routes/legacy-cold-to-name.route').write_text('\n'.join(seq)+'\n')
# index of the last three 'keys 1'
ai=[i for i,c in enumerate(seq) if c=='keys 1'][-3:]
e=Emu('prep-legacy','candidate',save=EIGHT_SAV,bps=BPS_ALL)
try:
    for i,c in enumerate(seq):
        if i==ai[0]:
            e.shot('before-last3'); print('before last3 ptr',hex(e.objptr()))
        e.cmd(c)
        if i in [a+3 for a in ai]:
            if not e.objptr(): print('after A ptr 0'); continue
            ptr,o=e.obj(); print('after A',hex(ptr),'mode',o[0x60],'len',o[0x61],o[0x65:0x6b].hex(),o[0x2c:0x3c].hex(),'tail',o[0x70:0x80].hex(),'cur',struct.unpack_from('<hh',o,0x1e))
    e.shot('reentry'); ptr,o=e.obj('reentry-obj.bin'); e.mem(0x0200B09C,16,'destination.bin')
    e.savestate('legacy-name.ss0')
finally: print('exit',e.close())
