"""Load the Part 1 Design Maps Help glyphs only while that Help is open.

The editor's normal bank-1 dictionary lacks many syllables in the protected
Help text. Combining both dictionaries exceeds this screen's safe VRAM tile
range, so the existing loader selects a separate source for the Help state.
"""

import hashlib


DICTIONARY_OFFSET = 0xF51000
HOOK_OFFSET = 0xF51200
SITE = 0xB12CB4
SITE_EXPECTED = bytes.fromhex('064800220123fff7')
SITE_PATCH = bytes.fromhex('004800470112f508')  # ldr r0; bx r0; 08F51201
HOOK = bytes.fromhex(
    '0e2904d1074a954201d1074800e007480022012310b400f003f810bc'
    '054b1847034c2047000e00030010f5087832d808dd2bb108bf2cb108'
)
# plan_C B-pin (2026-11-04 user, tools/bpin_contract.py): reviewed native Help rows and
# the D82218 retained source (놓, 릅) -> 66 codes. The tile budget below allows 72.
SOURCE_SPANS = (
    (0xD82124, 0xD821EA, '5fb7c9ecabda9e9455c01ada064c7d2062f037f350d54cb7f743fd3e6f30fd4f'),
    (0xD821F0, 0xD82292, '63cf4137a1ebc3c70de35419fc2b6eb05c651b2d9c1c36d873e1fec0436ea49b'),
)
CODE_COUNT = 66
MAX_CODES = 72  # 0x0E + 2*72 = 0x9E < 0xA0


def dictionary(rom):
    codes = []
    seen = set()
    for start, end, expected_sha in SOURCE_SPANS:
        source = bytes(rom[start:end])
        if hashlib.sha256(source).hexdigest() != expected_sha:
            raise AssertionError(f'Part 1 editor Help source changed at {start:#x}')
        for address in range(start, end, 2):
            code = bytes(rom[address:address + 2])
            if code in (b'\0\0', b'  ', b'\x81\x40') or code in seen:
                continue
            if not (0x81 <= code[0] <= 0xEF and
                    (0x40 <= code[1] <= 0x7E or 0x80 <= code[1] <= 0xFC)):
                raise AssertionError(f'Part 1 editor Help invalid code at {address:#x}')
            codes.append(code)
            seen.add(code)
    if len(codes) != CODE_COUNT or len(codes) > MAX_CODES:
        raise AssertionError(f'Part 1 editor Help glyph count changed: {len(codes)}')
    # Live Help starts bank 1 at tile 0x0E; the last Help tile stays below 0xA0.
    if 0x0E + len(codes) * 2 >= 0xA0:
        raise AssertionError('Part 1 editor Help tile budget exceeded')
    return b''.join(codes) + b'\0\0'


def patch(rom, original):
    payload = dictionary(rom)
    if bytes(original[SITE:SITE + len(SITE_EXPECTED)]) != SITE_EXPECTED:
        raise AssertionError('Part 1 editor Help native loader changed')
    if bytes(rom[SITE:SITE + len(SITE_EXPECTED)]) != SITE_EXPECTED:
        raise AssertionError('Part 1 editor Help loader already patched')
    for address, data in ((DICTIONARY_OFFSET, payload), (HOOK_OFFSET, HOOK)):
        if any(original[address:address + len(data)]) or any(rom[address:address + len(data)]):
            raise AssertionError(f'Part 1 editor Help allocation occupied at {address:#x}')
    rom[DICTIONARY_OFFSET:DICTIONARY_OFFSET + len(payload)] = payload
    rom[HOOK_OFFSET:HOOK_OFFSET + len(HOOK)] = HOOK
    rom[SITE:SITE + len(SITE_PATCH)] = SITE_PATCH
    return {'codes': len(payload) // 2 - 1, 'dictionary_bytes': len(payload), 'hook_bytes': len(HOOK),
            'source_spans': [f'{a:08X}..{b:08X}' for a, b, _ in SOURCE_SPANS]}


def verify(rom):
    payload = dictionary(rom)
    if (bytes(rom[DICTIONARY_OFFSET:DICTIONARY_OFFSET + len(payload)]) != payload or
            bytes(rom[HOOK_OFFSET:HOOK_OFFSET + len(HOOK)]) != HOOK or
            bytes(rom[SITE:SITE + len(SITE_PATCH)]) != SITE_PATCH):
        raise AssertionError('Part 1 editor Help dictionary or loader overwritten')
