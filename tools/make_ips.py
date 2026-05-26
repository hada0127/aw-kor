#!/usr/bin/env python3
"""IPS 패치 인코더 (src/tgt 동일 크기, 16MB 이내).

IPS 포맷: "PATCH" + 레코드들 + "EOF".
레코드: offset(3B BE) + size(2B BE) + data.  (RLE 미사용 — 단순/안전)
- 최대 오프셋 0xFFFFFF(16MB), 최대 레코드 0xFFFF → 긴 run은 분할.
- 오프셋이 0x454F46("EOF")와 겹치면 1바이트 앞당겨 회피.

사용: python tools/make_ips.py <src.gba> <tgt.gba> <out.ips>
"""
import sys

EOF_OFF = 0x454F46  # "EOF" 마커와 충돌하는 오프셋


def make_ips(src, tgt):
    assert len(src) == len(tgt), 'same size only'
    assert len(tgt) <= 0x1000000, 'IPS는 16MB 이내만 (24비트 오프셋)'
    out = bytearray(b'PATCH')
    i, n = 0, len(tgt)
    while i < n:
        if src[i] == tgt[i]:
            i += 1
            continue
        j = i
        while j < n and src[j] != tgt[j]:
            j += 1
        # [i, j) 가 변경 구간. 0xFFFF 청크로 분할.
        k = i
        while k < j:
            chunk = min(0xFFFF, j - k)
            off = k
            # "EOF" 오프셋 회피: 한 바이트 앞에서 시작(직전 동일바이트 포함)
            if off == EOF_OFF and k > 0:
                off = k - 1
                chunk = min(0xFFFF, j - off)
            out += off.to_bytes(3, 'big')
            out += chunk.to_bytes(2, 'big')
            out += tgt[off:off + chunk]
            k = off + chunk
        i = j
    out += b'EOF'
    return bytes(out)


def apply_ips(src, patch):
    assert patch[:5] == b'PATCH'
    out = bytearray(src)
    i = 5
    while True:
        if patch[i:i + 3] == b'EOF':
            break
        off = int.from_bytes(patch[i:i + 3], 'big'); i += 3
        size = int.from_bytes(patch[i:i + 2], 'big'); i += 2
        if size == 0:  # RLE
            rle = int.from_bytes(patch[i:i + 2], 'big'); i += 2
            val = patch[i]; i += 1
            out[off:off + rle] = bytes([val]) * rle
        else:
            out[off:off + size] = patch[i:i + size]; i += size
    return bytes(out)


if __name__ == '__main__':
    src = open(sys.argv[1], 'rb').read()
    tgt = open(sys.argv[2], 'rb').read()
    ips = make_ips(src, tgt)
    open(sys.argv[3], 'wb').write(ips)
    # round-trip 검증
    ok = apply_ips(src, ips) == tgt
    print(f'IPS: {sys.argv[3]} size={len(ips)} bytes, round-trip={"OK" if ok else "FAIL"}')
    assert ok
