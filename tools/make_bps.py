"""Minimal BPS patch encoder (source==target size). Emits SourceRead/TargetRead spans."""
import sys,zlib,struct
def wvarint(n):
    out=bytearray()
    while True:
        x=n&0x7F; n>>=7
        if n==0: out.append(0x80|x); break
        out.append(x); n-=1
    return bytes(out)
def make_bps(src,tgt):
    assert len(src)==len(tgt),"this minimal encoder needs equal sizes"
    p=bytearray(b'BPS1')
    p+=wvarint(len(src)); p+=wvarint(len(tgt)); p+=wvarint(0)  # no metadata
    i=0; n=len(src); outpos=0
    while i<n:
        if src[i]==tgt[i]:
            j=i
            while j<n and src[j]==tgt[j]: j+=1
            length=j-i
            p+=wvarint(((length-1)<<2)|0)  # SourceRead
            i=j
        else:
            j=i
            while j<n and src[j]!=tgt[j]: j+=1
            length=j-i
            p+=wvarint(((length-1)<<2)|1)  # TargetRead
            p+=tgt[i:j]
            i=j
    p+=struct.pack('<I',zlib.crc32(src)&0xffffffff)
    p+=struct.pack('<I',zlib.crc32(tgt)&0xffffffff)
    p+=struct.pack('<I',zlib.crc32(bytes(p))&0xffffffff)
    return bytes(p)
if __name__=="__main__":
    src=open(sys.argv[1],"rb").read(); tgt=open(sys.argv[2],"rb").read()
    bps=make_bps(src,tgt); open(sys.argv[3],"wb").write(bps)
    print("BPS:",sys.argv[3],"size=%d bytes"%len(bps))
