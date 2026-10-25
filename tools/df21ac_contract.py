"""DF21AC only: approved first sentence, authored companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "a7b8127708334da9adea132e64a22a5bed5116f4113c29f54e537b8b63a920ee"
MESSAGE = 0xDF21AC
FIRST, COMPANION, TAIL = 0xDF21AE, 0xDF21D9, 0xDF21E7
TEXTS = {FIRST: '수도 점령이나 적 전멸로,이길 수 있어요!', COMPANION: '힘내!'}
ROWS = {FIRST: bytes.fromhex('8def8a5a81408fcc8b678fa288e981408fc781408fc88bf78b6981418fa2889181408def81408fb38ec38f5a8149'),
        COMPANION: bytes.fromhex('9369894e8149')}
NATIVE = bytes.fromhex('0a098ef1937390e897cc82a99347915396c582c581418f9f82c282b182c682aa82c582ab82e982ed8149720a0982aa82f182ce82e982cc82e681496b0a000000')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0\0\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 40), (COMPANION, 14)]
    if (sha256(original[MESSAGE:TAIL+5]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+5]) != NATIVE or end != TAIL+5
            or bytes(original[0xDF1624:0xDF162C]) != bytes.fromhex('19000000ac21df08')
            or bytes(rom[0xDF1624:0xDF162C]) != bytes(original[0xDF1624:0xDF162C])
            or sites != [0xDF1628]
            or lines not in (expected, expected + [(TAIL, 5)])):
        raise AssertionError('DF21AC native pointer/source contract changed')
    # Require the entire aligned native-span reference set, including entry references.
    import array
    import sys
    words = array.array('I')
    words.frombytes(original[:len(original) // 4 * 4])
    if sys.byteorder != 'little':
        words.byteswap()
    references = [(i * 4, word) for i, word in enumerate(words)
                  if 0x08000000 + MESSAGE <= word < 0x08000000 + end]
    if references != [(0xDF1628, 0x08000000 + MESSAGE)]:
        raise AssertionError('DF21AC unexpected aligned reference set')
    for start, stop in ((MESSAGE, FIRST), (0xDF21D6, COMPANION), (TAIL, TAIL+5)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF21AC native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF21AC approved source/companion changed')
    return expected


def validate_payload(payload):
    if (bytes(payload) != PAYLOAD or len(payload) != 62
            or sha256(payload).hexdigest() != '16296759bdff20dff00ed66e9e27f2566036e42bcd6ecd87b63dbbddf3c652be'):
        raise AssertionError('DF21AC restored payload/control changed')
