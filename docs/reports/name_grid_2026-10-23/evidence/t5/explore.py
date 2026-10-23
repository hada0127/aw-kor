"""Exploration: replay a route with a screenshot after every key release (no savestate imports)."""
import sys
from t5lib import *
tag=sys.argv[1]; route=Path(sys.argv[2]).read_text().split('\n'); save=sys.argv[3] if len(sys.argv)>3 else None
e=Emu(tag,'candidate',save=save)
try:
    k=0
    for c in route:
        if not c: continue
        e.cmd(c)
        if c.startswith('frames') and e.frame>0 and c!='frames 1':
            k+=1; e.shot(f's{k:02d}-f{e.frame}')
finally: print('exit',e.close())
