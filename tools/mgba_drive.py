#!/usr/bin/env python3
"""Drive the headless mgba harness. stderr(SWI log) -> file to avoid pipe deadlock."""
import subprocess, sys, struct, time
HARNESS="/tmp/mgbah"; ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"
SWILOG=open("/tmp/swi.log","w")
p=subprocess.Popen([HARNESS,ROM],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=SWILOG,
                   env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"},text=True)
def cmd(c):
    p.stdin.write(c+"\n"); p.stdin.flush()
    return p.stdout.readline().strip()
def press(mask,hold=6,after=60):
    cmd("keys %d"%mask); cmd("frames %d"%hold); cmd("keys 0"); cmd("frames %d"%after)
KEYS=dict(A=1,B=2,SEL=4,START=8,RIGHT=16,LEFT=32,UP=64,DOWN=128)
def raw2png(raw,out,order=(0,1,2)):
    from PIL import Image
    d=open(raw,'rb').read(); w,h=struct.unpack("<HH",d[:4]); cs=d[4]; px=d[5:]
    img=Image.new('RGB',(w,h)); o=img.load()
    for y in range(h):
        for x in range(w):
            i=(y*w+x)*cs
            o[x,y]=(px[i+order[0]],px[i+order[1]],px[i+order[2]])
    img.resize((w*3,h*3),Image.NEAREST).save(out)
if __name__=="__main__":
    # simple REPL from argv script file or interactive
    import sys
    if len(sys.argv)>1:
        for c in open(sys.argv[1]):
            c=c.strip()
            if not c or c.startswith('#'): continue
            print(c,"->",cmd(c))
    cmd("quit"); SWILOG.flush()
