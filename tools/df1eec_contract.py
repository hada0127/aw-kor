"""DF1EEC: exact two-source ownership of a 74-byte, two-display-row reflow.

Preflight is scoped to this message and runs before the relocation loop writes.
It is not a rollback of earlier builder stages or unrelated relocation failures.
"""
import array
import copy
from hashlib import sha256
import sys

MESSAGE, FIRST, COMPANION, TAIL, END = 0xDF1EEC, 0xDF1EEE, 0xDF1F1B, 0xDF1F29, 0xDF1F2C
SITE = 0xDF1268
NEXT_NATIVE = bytes.fromhex('0a098ef1937390e897cc814182e082b582ad82cd9347915396c582c58f9f979882e68142720a0982bd82cc82f182be82ed82cb81416982b382f181496b0a0000')
TEXTS = {FIRST: '여기는,수도 점령,혹은 적 전멸로 승리예요!', COMPANION: '힘내는 거예요!'}
ROWS = {FIRST: bytes.fromhex('8ed8888f89c881418def8a5a81408fcc8b67814192e48f7e81408fc781408fc88bf78b6981408e4d8bb78eec8f5a8149'),
        COMPANION: bytes.fromhex('9369894e89c8814088528eec8f5a8149')}
NATIVE = bytes.fromhex('0a0982b182b182cd81418ef1937390e897cc814182e082b582ad82cd9347915396c582c58f9f979882e68149720a0982aa82f182ce82e982cc82e681496b0a00')
NATIVE_SHA256 = '61cbd69a586621e55cb1bb3c458c56ef933584653c13c0c711545fbcc58bcf0d'
PAYLOAD = bytes.fromhex('0a098ed8888f89c881418def8a5a81408fcc8b67814192e48f7e81408fc781408fc88bf78b698140720a098e4d8bb78eec8f5a814981409369894e89c8814088528eec8f5a81496b0a00')
LAYOUT = (ROWS[FIRST][:38], ROWS[FIRST][38:])
REFLOW = (FIRST, COMPANION, LAYOUT[0], LAYOUT[1] + b'\x81\x40' + ROWS[COMPANION], b'')
METADATA = dict(msg='0xDF1EEC', status='relocated', old_len=64, new_len=74, lines=2,
    ptr_off='0xDF1268', ptr_sites=['0xDF1268'], fixed=['0xDF1EEE','0xDF1F1B'],
    source_spans={'0xDF1EEE':42,'0xDF1F1B':14},
    source_texts={f'0x{a:06X}':t for a,t in TEXTS.items()},
    line_spans={'0xDF1EEE':[2,38],'0xDF1F1B':[55,16]},
    source_line_fragments={'0xDF1EEE':[[2,38],[43,10]],'0xDF1F1B':[[55,16]]},
    source_fragment_joiners={'0xDF1EEE':[''],'0xDF1F1B':[]},
    display_line_spans=[[2,38],[43,28]], layout_controls={},
    layout_gaps=[dict(offset=53,length=2,hex='8140',kind='sentence_separator')])


def validate(payload, record):
    if (bytes(payload) != PAYLOAD or len(payload) != 74 or
            sha256(payload).hexdigest() != '2582f65b926c68f4894edb844c7f40813f487854a0624a34746f1af7ad589b2f'):
        raise AssertionError('DF1EEC exact payload changed')
    if {k:v for k,v in record.items() if k != 'new_addr'} != METADATA:
        raise AssertionError('DF1EEC exact ownership/layout metadata changed')
    # Explicitly account for each byte: owners, native controls and physical gap.
    spans = [(0,2),(40,3),(71,3)]
    spans += [tuple(p) for parts in record['source_line_fragments'].values() for p in parts]
    spans += [(g['offset'],g['length']) for g in record['layout_gaps']]
    covered = [i for off,size in spans for i in range(off,off+size)]
    if sorted(covered) != list(range(74)) or payload[53:55] != b'\x81\x40':
        raise AssertionError('DF1EEC ownership partition changed')


def preflight(original, rom, lines, end, sites, fixed_bytes, source_text,
              fixable, fit_level, line_layout, reflow):
    expected = [(FIRST,42),(COMPANION,14)]
    if (bytes(original[MESSAGE:END]) != NATIVE or
            sha256(original[MESSAGE:END]).hexdigest() != NATIVE_SHA256 or end != END
            or bytes(original[END:END+64]) != NEXT_NATIVE
            or lines != expected or sites != [SITE]
            or bytes(original[SITE-4:SITE+4]) != bytes.fromhex('19000000ec1edf08')
            or rom[SITE-4:SITE+4] != original[SITE-4:SITE+4]):
        raise AssertionError('DF1EEC native/source/caller boundary changed')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('DF1EEC aligned native reference set changed')
    for start,stop in ((MESSAGE,FIRST),(0xDF1F18,COMPANION),(TAIL,END)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('DF1EEC working native control changed')
    for a in TEXTS:
        if (source_text is None or source_text(a) != TEXTS[a] or fixed_bytes(a) != ROWS[a]
                or not fixable(a) or fit_level(a) != 6):
            raise AssertionError('DF1EEC source precedence/encoding changed')
    if line_layout != LAYOUT or reflow != REFLOW:
        raise AssertionError('DF1EEC physical row layout changed')
    payload = b'\x0a\x09' + reflow[2] + b'\x72\x0a\x09' + reflow[3] + b'\x6b\x0a\0'
    record = copy.deepcopy(METADATA)
    validate(payload,record)
    return payload,record
