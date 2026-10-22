"""Source-gated compact Hangul captions for the Part 1 Design Maps menu.

The map-list hook deliberately rejects state 03000F80 because it also draws a
hidden map buffer. The editor uses that state with distinct D824 sources, so
three rejected exits delegate to this small source and row guard.
"""
import hashlib
import struct

CODE_OFFSET = 0xF31E00
CODE = bytes.fromhex(
    '0648874208d10648854205d30548854202d20548054b184705480047800f0003'
    '4c24d808ae24d808a01cb8081d06f308dd06f308000000000000000000000000'
    '0000000000000000000000000000000000000000000000000000000000000000'
    '094885420ed3094885420bd20848854205d30848854203d30748854200d20436'
    '06480047064800474c24d808ae24d8087424d8089824d8089c24d8083b06f308'
    'dd06f308000000000000000000000000039f094887420ad108290ad20748301a'
    'c009052805d2c0004018054f38470548004705480047c046800f00030a2e0102'
    '8f06f308a907f308dd06f308'
)
# Rejected targets in the Round 2 gate, source gate and row-state gate.
REPLACES = {
    0xF3075C: (0x08F306DD, 0x08F31E01),
    0xF31FB4: (0x08F306DD, 0x08F31E61),
    0xF31FE4: (0x08F307A9, 0x08F31EB1),
}


def patch(rom, original):
    if len(CODE) != 0xEC:
        raise AssertionError(f'editor helper layout changed: {len(CODE)}')
    if bytes(original[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != bytes(len(CODE)):
        raise AssertionError('editor helper ROM allocation occupied')
    if bytes(rom[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != bytes(len(CODE)):
        raise AssertionError('editor helper table overlap or allocation occupied')
    for address, (old, _) in REPLACES.items():
        if struct.unpack_from('<I', rom, address)[0] != old:
            raise AssertionError(f'editor gate predecessor changed at {address:#x}')
    rom[CODE_OFFSET:CODE_OFFSET + len(CODE)] = CODE
    for address, (_, new) in REPLACES.items():
        struct.pack_into('<I', rom, address, new)
    return {'code': hex(CODE_OFFSET), 'size': len(CODE),
            'sha256': hashlib.sha256(CODE).hexdigest(),
            'source_range': ['0x08D8244C', '0x08D824AE'],
            'state': '0x03000F80'}


def verify(rom):
    if bytes(rom[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != CODE:
        raise AssertionError('editor helper overwritten')
    for address, (_, new) in REPLACES.items():
        if struct.unpack_from('<I', rom, address)[0] != new:
            raise AssertionError(f'editor gate overwritten at {address:#x}')
