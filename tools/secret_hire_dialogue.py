"""Approved B-team secret-hire dialogue, source and final relocation contract."""
import hashlib
import struct
from dialogue_repoint import normalize_text_segment, text_segment_cells
from sprite_relocations import SPRITE_STORAGE_START
TEXT = '이건 비밀인데, 그 헬보우즈를 고용할 수 있다네!'
START, ADDRESS, TEXT_END, END, POINTER = 0xDFD080, 0xDFD082, 0xDFD0AE, 0xDFD0B4, 0xDFE444
SOURCE_SHA = '8d2a3ca1ac8a698d7eddc050154df29601aa61ae942f6528ab41b3bc820a0075'

def expected(original, encode):
    if hashlib.sha256(original[START:0xDFD0B4]).hexdigest() != SOURCE_SHA or struct.unpack_from('<I', original, POINTER)[0] != START + 0x08000000:
        raise ValueError('Secret hire original source/pointer changed')
    # Adjacent message in the same native shop table proves its two-row sequence.
    if hashlib.sha256(original[0xDFD0B4:0xDFD104]).hexdigest() != '1834a3efb9cae0c7d86008a44f01590a6ad6723b9f9e71adbe46b5b54f6f844e':
        raise ValueError('Secret hire native two-row reference changed')
    needle = struct.pack('<I', START + 0x08000000)
    if original.count(needle) != 1:
        raise ValueError('Secret hire pointer ownership changed')
    rows = layout(original, encode, guarded=True)[ADDRESS]
    normalized = [normalize_text_segment(row, True, START) for row in rows]
    if any(text_segment_cells(row) > 50 for row in normalized):
        raise ValueError('Secret hire exceeds dialogue width')
    return original[START:ADDRESS] + b'\x72\x0a\x09'.join(normalized) + original[TEXT_END:END]

def layout(original, encode, guarded=False):
    rows = ('이건 비밀인데,', '그 헬보우즈를 고용할 수 있다네!')
    if ' '.join(rows) != TEXT:
        raise ValueError('Secret hire source meaning changed')
    result = {ADDRESS: tuple(encode(row, ADDRESS) for row in rows)}
    if not guarded:
        expected(original, encode)
    return result

def verify(rom, original, encode):
    payload = expected(original, encode)
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if target % 4 or not 0xA3D000 <= target < target + len(payload) <= SPRITE_STORAGE_START:
        raise ValueError('Secret hire must use bounded aligned relocation')
    if bytes(rom[target:target + len(payload)]) != payload:
        raise ValueError('Secret hire text/control mismatch')
    return {'status': 'PASS', 'source': hex(START), 'target': hex(target), 'text': TEXT, 'live_pixels_verified': False}
