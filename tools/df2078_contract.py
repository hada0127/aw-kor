"""DF2078 only: approved first sentence, authored companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "7805309fb48c20d4b0c08566ca51f4a91ef0a50d0e19b75e4c5ff252e399c0a8"
MESSAGE = 0xDF2078
FIRST, COMPANION, TAIL = 0xDF207A, 0xDF20A5, 0xDF20B3
TEXTS = {FIRST: '승리조건은,수도 점령,혹은 적 전멸이에요!', COMPANION: '힘내요!'}
ROWS = {FIRST: bytes.fromhex('8e4d8bb78fd988548f7e81418def8a5a81408fcc8b67814192e48f7e81408fc781408fc88bf78fa28ed38f5a8149'),
        COMPANION: bytes.fromhex('9369894e8f5a8149')}
NATIVE = bytes.fromhex('0a098f9f97988ff08c8f82cd81418ef1937390e897cc814182e082b582ad82cd9347915396c582e68149720a0982aa82f182ce82c182c482cb81496b0a000000')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0\0\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 40), (COMPANION, 14)]
    if (sha256(original[MESSAGE:TAIL+5]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+5]) != NATIVE or end != TAIL+5
            or bytes(original[0xDF1444:0xDF144C]) != bytes.fromhex('190000007820df08')
            or bytes(rom[0xDF1444:0xDF144C]) != bytes(original[0xDF1444:0xDF144C])
            or sites != [0xDF1448]
            or lines not in (expected, expected + [(TAIL, 5)])):
        raise AssertionError('DF2078 native pointer/source contract changed')
    # Unlike generic entry-only scanning, reject every aligned interior target.
    import array
    import sys
    words = array.array('I')
    words.frombytes(original[:len(original) // 4 * 4])
    if sys.byteorder != 'little':
        words.byteswap()
    if any(0x08000000 + MESSAGE < word < 0x08000000 + end for word in words):
        raise AssertionError('DF2078 unexpected interior reference')
    for start, stop in ((MESSAGE, FIRST), (0xDF20A2, COMPANION), (TAIL, TAIL+5)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF2078 native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF2078 approved source/companion changed')
    return expected


def validate_payload(payload):
    if bytes(payload) != PAYLOAD:
        raise AssertionError('DF2078 restored payload/control changed')
