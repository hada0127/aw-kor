"""DF28C0: exact two-source ownership of a 66-byte, two-display-row reflow.

Preflight is scoped to this message and runs before the relocation loop writes.
It is not a rollback of earlier builder stages or unrelated relocation failures.
"""
import array
import copy
from hashlib import sha256
import sys

MESSAGE, FIRST, COMPANION, TAIL, END = 0xDF28C0, 0xDF28C2, 0xDF28EF, 0xDF28FD, 0xDF2900
SITE = 0xDF1E68
NEXT_NATIVE = bytes.fromhex('f55bb3080000020000000000010000003509b408000002004509b40800000100055cb30800000200000000000000070073318cbb8ddd82cc8ff38bb582f0835a')
TEXTS = {FIRST: '여기는,수도 점령,혹은 적 전멸로 승리예요!', COMPANION: '힘내요!'}
ROWS = {FIRST: bytes.fromhex('8ed8888f89c881418def8a5a81408fcc8b67814192e48f7e81408fc781408fc88bf78b6981408e4d8bb78eec8f5a8149'),
        COMPANION: bytes.fromhex('9369894e8f5a8149')}
NATIVE = bytes.fromhex('0a0982b182b182cd81418ef1937390e897cc814182e082b582ad82cd9347915396c582c58f9f979882e68149720a0982aa82f182ce82c182c482cb81496b0a00')
NATIVE_SHA256 = 'd5cdd4aed7bd133329d19a9b4029bb4da63c349437de276f3371eba0a942e7b1'
PAYLOAD = bytes.fromhex('0a098ed8888f89c881418def8a5a81408fcc8b67814192e48f7e81408fc781408fc88bf78b698140720a098e4d8bb78eec8f5a814981409369894e8f5a81496b0a00')
LAYOUT = (ROWS[FIRST][:38], ROWS[FIRST][38:])
REFLOW = (FIRST, COMPANION, LAYOUT[0], LAYOUT[1] + b'\x81\x40' + ROWS[COMPANION], b'')
METADATA = dict(msg='0xDF28C0', status='relocated', old_len=64, new_len=66, lines=2,
    ptr_off='0xDF1E68', ptr_sites=['0xDF1E68'], fixed=['0xDF28C2','0xDF28EF'],
    source_spans={'0xDF28C2':42,'0xDF28EF':14},
    source_texts={f'0x{a:06X}':t for a,t in TEXTS.items()},
    line_spans={'0xDF28C2':[2,38],'0xDF28EF':[55,8]},
    source_line_fragments={'0xDF28C2':[[2,38],[43,10]],'0xDF28EF':[[55,8]]},
    source_fragment_joiners={'0xDF28C2':[''],'0xDF28EF':[]},
    display_line_spans=[[2,38],[43,20]], layout_controls={},
    layout_gaps=[dict(offset=53,length=2,hex='8140',kind='sentence_separator')])


def validate(payload, record):
    if (bytes(payload) != PAYLOAD or len(payload) != 66 or
            sha256(payload).hexdigest() != 'a4586efd73e340858009023ae6580dca2c35ac231522211594b1803d09ce911a'):
        raise AssertionError('DF28C0 exact payload changed')
    if {k:v for k,v in record.items() if k != 'new_addr'} != METADATA:
        raise AssertionError('DF28C0 exact ownership/layout metadata changed')
    # Explicitly account for each byte: owners, native controls and physical gap.
    spans = [(0,2),(40,3),(63,3)]
    spans += [tuple(p) for parts in record['source_line_fragments'].values() for p in parts]
    spans += [(g['offset'],g['length']) for g in record['layout_gaps']]
    covered = [i for off,size in spans for i in range(off,off+size)]
    if sorted(covered) != list(range(66)) or payload[53:55] != b'\x81\x40':
        raise AssertionError('DF28C0 ownership partition changed')


def preflight(original, rom, lines, end, sites, fixed_bytes, source_text,
              fixable, fit_level, line_layout, reflow):
    expected = [(FIRST,42),(COMPANION,14)]
    if (bytes(original[MESSAGE:END]) != NATIVE or
            sha256(original[MESSAGE:END]).hexdigest() != NATIVE_SHA256 or end != END
            or bytes(original[END:END+64]) != NEXT_NATIVE
            or lines != expected or sites != [SITE]
            or bytes(original[SITE-4:SITE+4]) != bytes.fromhex('19000000c028df08')
            or rom[SITE-4:SITE+4] != original[SITE-4:SITE+4]):
        raise AssertionError('DF28C0 native/source/caller boundary changed')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('DF28C0 aligned native reference set changed')
    for start,stop in ((MESSAGE,FIRST),(0xDF28EC,COMPANION),(TAIL,END)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF28C0 working native control changed')
    for a in TEXTS:
        if (source_text is None or source_text(a) != TEXTS[a] or fixed_bytes(a) != ROWS[a]
                or not fixable(a) or fit_level(a) != (99 if a == FIRST else 6)):
            raise AssertionError('DF28C0 source precedence/encoding changed')
    if line_layout != LAYOUT or reflow != REFLOW:
        raise AssertionError('DF28C0 physical row layout changed')
    payload = b'\x0a\x09' + reflow[2] + b'\x72\x0a\x09' + reflow[3] + b'\x6b\x0a\0'
    record = copy.deepcopy(METADATA)
    validate(payload,record)
    return payload,record


def assert_manifest(manifest):
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if len(records) != 1:
        raise AssertionError('DF28C0 missing/duplicate manifest')
    validate(PAYLOAD, records[0])


def validate_generated(payload, record, prepared):
    # Generic assembly owns physical rows. Check every ACTUAL field before
    # replacing that representation with the prepared semantic source fragments.
    expected = {k: copy.deepcopy(v) for k,v in METADATA.items() if k not in
                ('source_line_fragments','source_fragment_joiners','display_line_spans','layout_gaps')}
    expected['line_spans'][f'0x{COMPANION:06X}'] = [43,20]
    # The generic assembler records its explicit-layout newline before reflow.
    # Final ownership assigns that same physical newline to native controls.
    expected['layout_controls'] = {f'0x{FIRST:06X}': '720a09'}
    if record != expected or prepared != (PAYLOAD, METADATA):
        raise AssertionError('DF28C0 prepared/generated payload/metadata changed')
    validate(payload, prepared[1])
