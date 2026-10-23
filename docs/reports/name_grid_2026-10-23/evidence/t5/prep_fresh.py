"""Candidate cold boot (no save) -> candidate fresh route (native fresh3 keys with the mode-select DOWN timing widened) -> name screen.
Only keys/frames; then A presses to close the guidance text, reading RAM each time. Saves T5-owned savestates."""
from t5lib import *
seq=(R/'routes/candidate-fresh-to-name.route').read_text().split()
seq=[' '.join(seq[i:i+2]) for i in range(0,len(seq),2)]
e=Emu('prep-fresh','candidate',bps=BPS_ALL)
try:
    for c in seq: e.cmd(c)
    e.shot('name-entry')
    ptr,o=e.obj('name-entry-obj.bin')
    print('entry obj',hex(ptr),'mode',o[0x60],'len',o[0x61],'cur',struct.unpack_from('<hh',o,0x1e),'65-6A',o[0x65:0x6b].hex(),'tail',o[0x70:0x80].hex(),'live',o[0x2c:0x3c].hex())
    e.savestate('name-entry.ss0')
    for i in range(3):
        e.tap(A,60); e.shot(f'after-a{i+1}')
        ptr,o=e.obj(f'after-a{i+1}-obj.bin')
        print('A',i+1,'len',o[0x61],'cur',struct.unpack_from('<hh',o,0x1e),'65-6A',o[0x65:0x6b].hex(),'live',o[0x2c:0x3c].hex(),'tail',o[0x70:0x74].hex())
    bp=parse_bp(e.bp_lines(0)); names={}
    for r in bp: names[r['name']]=names.get(r['name'],0)+1
    print(names)
finally:
    print('exit',e.close())
