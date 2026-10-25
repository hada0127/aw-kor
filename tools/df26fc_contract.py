"""DF26FC only: conditional source contract, exact comma and final override companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "9f7c1615c29074e9617dc03ec8b091d1d00fba221e249f4783891c8e36de2a53"
MESSAGE = 0xDF26FC
FIRST, COMPANION, TAIL = 0xDF26FE, 0xDF2729, 0xDF2751
TEXTS = {FIRST: '수도 점령이나,적 전멸로 이길 수 있어요!', COMPANION: '모프 사령관은 강적이에요,힘내요!'}
ROWS = {FIRST: bytes.fromhex('8def8a5a81408fcc8b678fa288e981418fc781408fc88bf78b6981408fa2889181408def81408fb38ec38f5a8149'),
        COMPANION: bytes.fromhex('8bfc929e81408da98b6788708f7e814088498fc78fa28ed38f5a81419369894e8f5a8149')}
NATIVE = bytes.fromhex('0a098ef1937390e897cc82a981419347915396c582c58f9f82c282b182c682aa82c582ab82e982ed8149720a0983828362837683568387815b834f839382cd8bad934782e6814182aa82f182ce82c182c482cb81496b0a00')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 40), (COMPANION, 40)]
    if (sha256(original[MESSAGE:TAIL+3]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+3]) != NATIVE or end != TAIL+3
            or bytes(original[0xDF1C84:0xDF1C8C]) != bytes.fromhex('19000000fc26df08')
            or bytes(rom[0xDF1C84:0xDF1C8C]) != bytes(original[0xDF1C84:0xDF1C8C])
            or sites != [0xDF1C88]
            or lines not in (expected, expected + [(TAIL, 3)])):
        raise AssertionError('DF26FC native pointer/source contract changed')
    # Require the entire aligned native-span reference set, including entry references.
    import array
    import sys
    words = array.array('I')
    words.frombytes(original[:len(original) // 4 * 4])
    if sys.byteorder != 'little':
        words.byteswap()
    references = [(i * 4, word) for i, word in enumerate(words)
                  if 0x08000000 + MESSAGE <= word < 0x08000000 + end]
    if references != [(0xDF1C88, 0x08000000 + MESSAGE)]:
        raise AssertionError('DF26FC unexpected aligned reference set')
    for start, stop in ((MESSAGE, FIRST), (0xDF2726, COMPANION), (TAIL, TAIL+3)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF26FC native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF26FC approved source/companion changed')
    return expected


def validate_payload(payload):
    if (bytes(payload) != PAYLOAD or len(payload) != 90
            or sha256(payload).hexdigest() != '62aea5879f70e447fa4dddb0afd5a5605483e9d0a1b2f797185ee5abb4f27d4b'):
        raise AssertionError('DF26FC restored payload/control changed')
