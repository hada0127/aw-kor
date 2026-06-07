"""Minimal BPS patch encoder/decoder used for release round-trip checks.

The encoder intentionally emits only SourceRead and TargetRead spans and expects
source and target ROMs to have the same size. The decoder accepts all BPS action
types so externally produced patches can be checked with the same helper.
"""
import sys,zlib,struct


def wvarint(n):
    out=bytearray()
    while True:
        x=n&0x7F; n>>=7
        if n==0: out.append(0x80|x); break
        out.append(x); n-=1
    return bytes(out)


def rvarint(buf, pos):
    value = 0
    shift = 1
    while True:
        x = buf[pos]
        pos += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def decode_signed(n):
    offset = n >> 1
    return -offset - 1 if (n & 1) else offset


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


def apply_bps(src, patch, verify=True):
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS1 patch')
    if verify and (zlib.crc32(patch[:-4]) & 0xffffffff) != struct.unpack('<I', patch[-4:])[0]:
        raise ValueError('BPS patch CRC mismatch')

    pos = 4
    source_size, pos = rvarint(patch, pos)
    target_size, pos = rvarint(patch, pos)
    metadata_size, pos = rvarint(patch, pos)
    pos += metadata_size
    if source_size != len(src):
        raise ValueError(f'source size mismatch: {len(src)} != {source_size}')

    body_end = len(patch) - 12
    out = bytearray()
    source_rel = 0
    target_rel = 0
    while pos < body_end:
        data, pos = rvarint(patch, pos)
        action = data & 3
        length = (data >> 2) + 1
        if action == 0:  # SourceRead
            start = len(out)
            out += src[start:start + length]
        elif action == 1:  # TargetRead
            out += patch[pos:pos + length]
            pos += length
        elif action == 2:  # SourceCopy
            rel, pos = rvarint(patch, pos)
            source_rel += decode_signed(rel)
            out += src[source_rel:source_rel + length]
            source_rel += length
        elif action == 3:  # TargetCopy
            rel, pos = rvarint(patch, pos)
            target_rel += decode_signed(rel)
            for _ in range(length):
                out.append(out[target_rel])
                target_rel += 1

    if len(out) != target_size:
        raise ValueError(f'target size mismatch: {len(out)} != {target_size}')
    if verify:
        source_crc, target_crc, _patch_crc = struct.unpack('<III', patch[-12:])
        if (zlib.crc32(src) & 0xffffffff) != source_crc:
            raise ValueError('BPS source CRC mismatch')
        if (zlib.crc32(out) & 0xffffffff) != target_crc:
            raise ValueError('BPS target CRC mismatch')
    return bytes(out)


if __name__=="__main__":
    src=open(sys.argv[1],"rb").read(); tgt=open(sys.argv[2],"rb").read()
    bps=make_bps(src,tgt); open(sys.argv[3],"wb").write(bps)
    ok = apply_bps(src, bps) == tgt
    print("BPS:",sys.argv[3],"size=%d bytes, round-trip=%s"%(len(bps), "OK" if ok else "FAIL"))
    assert ok
