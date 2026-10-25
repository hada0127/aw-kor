"""Scoped source-only contract; runtime DEFER is unchanged."""
import array
import copy
from hashlib import sha256
import sys

MESSAGE, FIRST, TAIL, END, SITE = 0xE10D78, 0xE10D7A, 0xE10D8A, 0xE10D8C, 0xE114F8
TEXT = '식은 죽 먹기지!'
ROW = bytes.fromhex('8e538f7e81408feb81408be5888f90548149')
NATIVE = bytes.fromhex('0a0982e782ad82b582e582a482be82ba81490a00')
CALLER = bytes.fromhex('19000000780de108')
PAYLOAD = b'\x0a\x09' + ROW + b'\x0a\x00'
METADATA = dict(msg='0xE10D78', status='relocated', old_len=20, new_len=22, lines=1,
    ptr_off='0xE114F8', ptr_sites=['0xE114F8'], fixed=['0xE10D7A'],
    source_spans={'0xE10D7A':16}, source_texts={'0xE10D7A':TEXT},
    line_spans={'0xE10D7A':[2,18]}, layout_controls={})


def validate(payload, record):
    if (bytes(payload) != PAYLOAD or sha256(payload).hexdigest() !=
            '9bbbf069e609be346040dd99df31191f85523494dae1321f65d860842aaa1168'):
        raise AssertionError('E10D78 exact 22B payload changed')
    if {k:v for k,v in record.items() if k != 'new_addr'} != METADATA:
        raise AssertionError('E10D78 exact owner/metadata changed')


def assert_manifest(manifest):
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if len(records) != 1:
        raise AssertionError('E10D78 missing/duplicate manifest')
    validate(PAYLOAD, records[0])


def preflight(original, rom, lines, end, sites, fixed_bytes, source_text,
              fixable, fit_level):
    if (bytes(original[MESSAGE:END]) != NATIVE or
            sha256(original[MESSAGE:END]).hexdigest() !=
            '4a6fb22f1597ee8ce28831b4e667760cbc3639dba83330aed953363d2341cdcc'
            or end != END or lines != [(FIRST,16)] or sites != [SITE]
            or bytes(original[SITE-4:SITE+4]) != CALLER
            or bytes(rom[SITE-4:SITE+4]) != CALLER):
        raise AssertionError('E10D78 native/source/caller boundary changed')
    for start, stop in ((MESSAGE,FIRST),(TAIL,END)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('E10D78 working native control changed')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('E10D78 aligned reference set changed')
    if (source_text is None or source_text(FIRST) != TEXT or fixed_bytes(FIRST) != ROW
            or not fixable(FIRST) or fit_level(FIRST) != 99):
        raise AssertionError('E10D78 source authority/encoding changed')
    record = copy.deepcopy(METADATA)
    validate(PAYLOAD,record)
    return PAYLOAD,record
