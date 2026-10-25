"""DF2804 only: conditional source contract, exact comma and final override companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "7829ecb0169359a8cf7a370dfb8df4d500a577ad0462f1e0f4e355d0c3de1487"
MESSAGE = 0xDF2804
FIRST, COMPANION, TAIL = 0xDF2806, 0xDF2831, 0xDF2853
TEXTS = {FIRST: '수도 점령이나,적 전멸로 이길 수 있어요!', COMPANION: '이제 한고비예요,힘내요!'}
ROWS = {FIRST: bytes.fromhex('8def8a5a81408fcc8b678fa288e981418fc781408fc88bf78b6981408fa2889181408def81408fb38ec38f5a8149'),
        COMPANION: bytes.fromhex('8fa28fd4814092af88668d658eec8f5a81419369894e8f5a8149')}
NATIVE = bytes.fromhex('0a098ef1937390e897cc82e281419347915396c582c58f9f82c282b182c682aa82c582ab82e982ed8149720a0982e082a482d082c682d382f182ce82e882e6814182aa82f182ce82c182c482cb81496b0a00')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 40), (COMPANION, 34)]
    if (sha256(original[MESSAGE:TAIL+3]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+3]) != NATIVE or end != TAIL+3
            or bytes(original[0xDF1DA4:0xDF1DAC]) != bytes.fromhex('190000000428df08')
            or bytes(rom[0xDF1DA4:0xDF1DAC]) != bytes(original[0xDF1DA4:0xDF1DAC])
            or bytes(original[TAIL+3:TAIL+5]) != b'\0\0'
            or bytes(rom[TAIL+3:TAIL+5]) != b'\0\0'
            or sites != [0xDF1DA8]
            or lines not in (expected, expected + [(TAIL, 3)])):
        raise AssertionError('DF2804 native pointer/source contract changed')
    # Require the entire aligned native-span reference set, including entry references.
    import array
    import sys
    words = array.array('I')
    words.frombytes(original[:len(original) // 4 * 4])
    if sys.byteorder != 'little':
        words.byteswap()
    references = [(i * 4, word) for i, word in enumerate(words)
                  if 0x08000000 + MESSAGE <= word < 0x08000000 + end]
    if references != [(0xDF1DA8, 0x08000000 + MESSAGE)]:
        raise AssertionError('DF2804 unexpected aligned reference set')
    for start, stop in ((MESSAGE, FIRST), (0xDF282E, COMPANION), (TAIL, TAIL+3)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF2804 native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF2804 approved source/companion changed')
    return expected


def validate_payload(payload):
    if (bytes(payload) != PAYLOAD or len(payload) != 80
            or sha256(payload).hexdigest() != '8993f1e798153a956382cf470d1c9af594c6afece7740eac454a0a0be09c3fd2'):
        raise AssertionError('DF2804 restored payload/control changed')
