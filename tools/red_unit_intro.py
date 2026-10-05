"""Protected red-unit introduction through the native command-message pointer."""
import hashlib
import struct

from dialogue_repoint import normalize_text_segment, text_segment_cells
from sprite_relocations import SPRITE_STORAGE_START

START, ADDRESS, TEXT_END, END = 0xD8F3B4, 0xD8F3B6, 0xD8F3D6, 0xD8F3DC
POINTER = 0xDA45D8
TEXT = '이 빨간색이　당신의 유닛이에요.'
SOURCE_SHA = 'ae49d8bc1890a14d6752293889b53fc8edd7ac1423c9a2550b818f0470a3a521'


def source_guard(original):
    reference = struct.pack('<I', START + 0x08000000)
    if (hashlib.sha256(original[START:END]).hexdigest() != SOURCE_SHA
            or original[POINTER - 4:POINTER] != b'\x19\x00\x00\x00'
            or original[POINTER:POINTER + 4] != reference
            or original.count(reference) != 1
            or struct.pack('<I', ADDRESS + 0x08000000) in original):
        raise ValueError('Red-unit introduction source/pointer ownership changed')


def expected(original, encode):
    source_guard(original)
    text = normalize_text_segment(encode(TEXT, ADDRESS), True, START)
    if not text or any(b < 0x20 for b in text) or text_segment_cells(text) > 50:
        raise ValueError('Red-unit introduction text/control/width invalid')
    return original[START:ADDRESS] + text + original[TEXT_END:END]


def verify(rom, original, encode):
    payload = expected(original, encode)
    if bytes(rom[POINTER - 4:POINTER]) != b'\x19\x00\x00\x00':
        raise ValueError('Red-unit introduction final command opcode changed')
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if (target % 4 or not 0xA3D000 <= target < target + len(payload) <= SPRITE_STORAGE_START
            or target + len(payload) > len(rom)):
        raise ValueError('Red-unit introduction requires bounded aligned relocation')
    if bytes(rom[target:target + len(payload)]) != payload:
        raise ValueError('Red-unit introduction approved text/control mismatch; protected wording changes require contract review')
    return {'status': 'PASS', 'source': hex(START), 'target': hex(target),
            'text': TEXT, 'live_pixels_verified': False}
