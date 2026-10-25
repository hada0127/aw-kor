"""DF25F8 only: approved first sentence, authored companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "1f86efdefdf6f9a048a1e87854a5792e2212ab5193e94b9547ed6cfd272dbe73"
MESSAGE = 0xDF25F8
FIRST, COMPANION, TAIL = 0xDF25FA, 0xDF2623, 0xDF2631
TEXTS = {FIRST: '수도 점령이나 적 전멸로 이길 수 있어요!', COMPANION: '지지 마!'}
ROWS = {FIRST: bytes.fromhex('8def8a5a81408fcc8b678fa288e981408fc781408fc88bf78b6981408fa2889181408def81408fb38ec38f5a8149'),
        COMPANION: bytes.fromhex('9054905481408bc38149')}
NATIVE = bytes.fromhex('0a098ef1937390e897cc82a99347915396c582c58f9f82c282b182c682aa82c582ab82e982ed8149720a09958982af82c882a282c582cb81496b0a00')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 38), (COMPANION, 14)]
    if (sha256(original[MESSAGE:TAIL+3]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+3]) != NATIVE or end != TAIL+3
            or bytes(original[0xDF1B04:0xDF1B0C]) != bytes.fromhex('19000000f825df08')
            or bytes(rom[0xDF1B04:0xDF1B0C]) != bytes(original[0xDF1B04:0xDF1B0C])
            or sites != [0xDF1B08]
            or lines not in (expected, expected + [(TAIL, 3)])):
        raise AssertionError('DF25F8 native pointer/source contract changed')
    # Require the entire aligned native-span reference set, including entry references.
    import array
    import sys
    words = array.array('I')
    words.frombytes(original[:len(original) // 4 * 4])
    if sys.byteorder != 'little':
        words.byteswap()
    references = [(i * 4, word) for i, word in enumerate(words)
                  if 0x08000000 + MESSAGE <= word < 0x08000000 + end]
    if references != [(0xDF1B08, 0x08000000 + MESSAGE)]:
        raise AssertionError('DF25F8 unexpected aligned reference set')
    for start, stop in ((MESSAGE, FIRST), (0xDF2620, COMPANION), (TAIL, TAIL+3)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF25F8 native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF25F8 approved source/companion changed')
    return expected


def validate_payload(payload):
    if (bytes(payload) != PAYLOAD or len(payload) != 64
            or sha256(payload).hexdigest() != '34f933684ca063bc7b9789f0358ceca42df9b89a1490dda73d66fdd1103f212a'):
        raise AssertionError('DF25F8 restored payload/control changed')
