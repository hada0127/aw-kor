"""DF228C only: approved first sentence, current companion, native controls."""
MESSAGE = 0xDF228C
FIRST, COMPANION, TAIL = 0xDF228E, 0xDF22BD, 0xDF22D9
TEXTS = {FIRST: '여기는,먼저 많이 점령하는 쪽이 승리예요!',
         COMPANION: '먼저 15거점을 점령해!'}
ROWS = {FIRST: bytes.fromhex('8ed8888f89c881418be68fc681408bc78fa281408fcc8b6792a989c88140907a8fa281408e4d8bb78eec8f5a8149'),
        COMPANION: bytes.fromhex('8be68fc681408250825488528fcc8f8181408fcc8b6792bb8149')}
NATIVE = bytes.fromhex('0a0982b182b182cd814190e682c982bd82ad82b382f190e897cc82b582bd82d982a482aa8f9f82bf82c882cc8149720a0990e682c9825082548b92935f90e897cc82f082b782e982cc82e681496b0a00')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 44), (COMPANION, 28)]
    if (bytes(original[MESSAGE:TAIL+3]) != NATIVE or end != TAIL+3
            or bytes(original[0xDF1744:0xDF174C]) != bytes.fromhex('190000008c22df08')
            or bytes(rom[0xDF1744:0xDF174C]) != bytes(original[0xDF1744:0xDF174C])
            or sites != [0xDF1748]
            or lines not in (expected, expected + [(TAIL, 3)])):
        raise AssertionError('DF228C native pointer/source contract changed')
    for start, stop in ((MESSAGE, FIRST), (0xDF22BA, COMPANION), (TAIL, TAIL+3)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF228C native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF228C approved source/companion changed')
    return expected


def validate_payload(payload):
    if bytes(payload) != PAYLOAD:
        raise AssertionError('DF228C restored payload/control changed')
