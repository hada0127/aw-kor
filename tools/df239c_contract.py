"""DF239C only: approved first sentence, authored companion, native controls."""
from hashlib import sha256

NATIVE_SHA256 = "d325da43fc2a9b3f4eb4c2b601e41e8b1c351f3dde82e1ac9bd726281443b832"
MESSAGE = 0xDF239C
FIRST, COMPANION, TAIL = 0xDF239E, 0xDF23CD, 0xDF23ED
TEXTS = {FIRST: '여기는,먼저 많이 점령하는 쪽이 승리예요!',
         COMPANION: '그래・・・12거점을 점령하는 거예요!'}
ROWS = {FIRST: bytes.fromhex('8ed8888f89c881418be68fc681408bc78fa281408fcc8b6792a989c88140907a8fa281408e4d8bb78eec8f5a8149'),
        COMPANION: bytes.fromhex('88878aec8145814581458250825188528fcc8f8181408fcc8b6792a989c8814088528eec8f5a8149')}
NATIVE = bytes.fromhex('0a0982b182b182cd814190e682c982bd82ad82b382f190e897cc82b582bd82d982a482aa8f9f82bf82c882cc8149720a0982bb82a4814581458145825082518b92935f90e897cc82b782e982cc82e681496b0a00')
PAYLOAD = b'\x0a\x09' + ROWS[FIRST] + b'\x72\x0a\x09' + ROWS[COMPANION] + b'\x6b\x0a\0'


def source_lines(original, rom, lines, end, sites, fixed_bytes, source_text):
    """Reject stale ownership before relocation; tail is exclusively a gap."""
    expected = [(FIRST, 44), (COMPANION, 32)]
    if (sha256(original[MESSAGE:TAIL+3]).hexdigest() != NATIVE_SHA256
            or bytes(original[MESSAGE:TAIL+3]) != NATIVE or end != TAIL+3
            or bytes(original[0xDF18C4:0xDF18CC]) != bytes.fromhex('190000009c23df08')
            or bytes(rom[0xDF18C4:0xDF18CC]) != bytes(original[0xDF18C4:0xDF18CC])
            or sites != [0xDF18C8]
            or lines not in (expected, expected + [(TAIL, 3)])):
        raise AssertionError('DF239C native pointer/source contract changed')
    for start, stop in ((MESSAGE, FIRST), (0xDF23CA, COMPANION), (TAIL, TAIL+3)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF239C native control changed')
    for address in expected:
        a = address[0]
        if fixed_bytes(a) != ROWS[a] or source_text is None or source_text(a) != TEXTS[a]:
            raise AssertionError('DF239C approved source/companion changed')
    return expected


def validate_payload(payload):
    if bytes(payload) != PAYLOAD:
        raise AssertionError('DF239C restored payload/control changed')
