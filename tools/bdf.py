"""Minimal BDF bitmap font parser -> per-char pixel grid."""
def load_bdf(path):
    glyphs={}; cur=None; bitmap=False; rows=[]
    fbb=None
    for line in open(path,encoding='latin-1'):
        p=line.split()
        if not p: continue
        if p[0]=='FONTBOUNDINGBOX': fbb=list(map(int,p[1:5]))
        elif p[0]=='STARTCHAR': cur={'name':p[1]}
        elif p[0]=='ENCODING' and cur is not None: cur['enc']=int(p[1])
        elif p[0]=='BBX' and cur is not None: cur['bbx']=list(map(int,p[1:5]))
        elif p[0]=='BITMAP': bitmap=True; rows=[]
        elif p[0]=='ENDCHAR':
            bitmap=False; cur['rows']=rows
            if 'enc' in cur: glyphs[cur['enc']]=cur
            cur=None
        elif bitmap and cur is not None: rows.append(p[0])
    return glyphs,fbb
def glyph_grid(g):
    w,h,xo,yo=g['bbx']
    grid=[]
    for hexrow in g['rows']:
        val=int(hexrow,16); nbits=len(hexrow)*4
        bits=[(val>>(nbits-1-i))&1 for i in range(w)]
        grid.append(bits)
    return grid,w,h,xo,yo
if __name__=="__main__":
    import sys
    for f in ['Galmuri11','Galmuri11-Condensed','Galmuri9','Galmuri7']:
        path='reference/fonts/%s.bdf'%f
        try: gl,fbb=load_bdf(path)
        except Exception as e: print(f,"ERR",e); continue
        print("=== %s  FONTBOUNDINGBOX=%s  glyphs=%d ==="%(f,fbb,len(gl)))
        for ch in '한게받글':
            g=gl.get(ord(ch))
            if not g: print("  %s: (none)"%ch); continue
            grid,w,h,xo,yo=glyph_grid(g)
            print("  '%s' bbx=%s:"%(ch,g['bbx']))
            for row in grid: print("    "+''.join('#' if b else '.' for b in row))
