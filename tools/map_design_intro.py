"""Protected map-design introduction in its exact native slot.

Wording: plan_C B-pin reviewed Catherine banmal (2026-11-04 user, tools/bpin_contract.py).
"""
import hashlib
import struct
TEXT = '여기서는 맵을 자유롭게 만들 수 있어.'
START, END, POINTER = 0xD82028, 0xD82054, 0xD7EDC4
SOURCE_SHA = 'fe1a80bcf797d235794011fecc2fe7f5886ad405aa6f88c4b300ebc67b914d62'

def verify(rom, original, encode_fit):
    reference = struct.pack('<I', 0x08000000 + START)
    if (hashlib.sha256(original[START:END+4]).hexdigest() != SOURCE_SHA
            or original[POINTER:POINTER+4] != reference or original.count(reference) != 1):
        raise ValueError('Map design original source/pointer changed')
    payload, level = encode_fit(TEXT, END - START, START)
    if payload is None or level != 0 or len(payload) > END - START:
        raise ValueError('Map design requires complete level-0 text within its slot')
    # The in-place writer pads the native slot with non-drawing 0x20.
    if bytes(rom[START:END]) != payload + b' ' * (END - START - len(payload)):
        raise ValueError('Map design approved text mismatch')
    if bytes(rom[END:END+4]) != bytes(original[END:END+4]) or bytes(rom[POINTER:POINTER+4]) != reference:
        raise ValueError('Map design control/pointer changed')
    return {'status': 'PASS', 'address': hex(START), 'text': TEXT, 'live_pixels_verified': False}
