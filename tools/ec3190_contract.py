"""Scoped source-only contract; runtime DEFER is unchanged."""
import array
import copy
from hashlib import sha256
import sys

MESSAGE, FIRST, TAIL, END, SITE = 0xEC3190, 0xEC3192, 0xEC31BC, 0xEC31C0, 0xEC271C
TEXT = '있음으로 하면 사령관 능력이 유효해집니다'
ROW = bytes.fromhex('8fb38f838f7c8b69814092a98bf581408da98b678870814089d28b5d8fa281408f7892fb92bb905e89d489e2')
NATIVE = bytes.fromhex('0a098341838a82c982b782e982c683568387815b834f8393945c97cd82aa974c8cf882c982c882e882dc82b70a000000')
CONSUMER_BYTES = {
    0xEC2708: bytes.fromhex('a030ec08d430ec080831ec082c31ec086031ec089031ec087032ec088c32ec087032ec088c32ec087032ec088c32ec087032ec088c32ec08c031ec08d831ec080032ec081c32ec08'),
    0xB71160: bytes.fromhex('f0b582b0084908680268101c343000780c1c002814d1131c373300201856062806d0024919e00000c0a6c2080827ec08106f0249483000780fe000004027ec08101c263000780006001600280cd10549101c363000780006001680004018066803e000002027ec08134e27683868006b86421dd0a1f72efc104c02250095b22040000190201c032111221a239ff722fec0208001009080204000019003201121221c331ca1f784fb3a3005703868066302b0f0bc01bc00474432ec08442d0102'),
    0xB12910: bytes.fromhex('70b556464d46444670b484b0041c0d1c924699460b9e0c9a2404240c2d042d0c3604360c1204120c10490020087010480021039200f0b0ff8046240424142d042d14484600900196039a02924046211c2a1c534600f00ef8404604b038bc9846a146aa4670bc02bc0847'),
}

PAYLOAD = b'\x0a\x09' + ROW + b'\x0a\x00\x00\x00'
METADATA = dict(msg='0xEC3190', status='relocated', old_len=48, new_len=50, lines=1,
    ptr_off='0xEC271C', ptr_sites=['0xEC271C'], fixed=['0xEC3192'],
    source_spans={'0xEC3192':42}, source_texts={'0xEC3192':TEXT},
    line_spans={'0xEC3192':[2,44]}, layout_controls={})


def validate(payload, record):
    if (bytes(payload) != PAYLOAD or sha256(payload).hexdigest() !=
            'ca17bd6cd782b1bf0699a7af090d3294fdf1662a01791169062dc595672eb394'):
        raise AssertionError('EC3190 exact 50B payload changed')
    if {k:v for k,v in record.items() if k != 'new_addr'} != METADATA:
        raise AssertionError('EC3190 exact owner/metadata changed')


def assert_manifest(manifest):
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if len(records) != 1:
        raise AssertionError('EC3190 missing/duplicate manifest')
    validate(PAYLOAD, records[0])


def preflight(original, rom, lines, end, sites, fixed_bytes, source_text,
              fixable, fit_level):
    if (bytes(original[MESSAGE:END]) != NATIVE or
            sha256(original[MESSAGE:END]).hexdigest() !=
            '8f73f9f4ea2e64fc8263d6bd3444f416963e4c80882bea52f27bb95aa7f6148c'
            or end != END or lines != [(FIRST,42)] or sites != [SITE]):
        raise AssertionError('EC3190 native/source/caller boundary changed')
    # Non-opcode table entry: bind root, selection and render caller.
    for start, raw in CONSUMER_BYTES.items():
        if bytes(original[start:start+len(raw)]) != raw or bytes(rom[start:start+len(raw)]) != raw:
            raise AssertionError('EC3190 table/root/consumer changed')
    for start, stop in ((MESSAGE,FIRST),(TAIL,END)):
        if rom[start:stop] != original[start:stop]:
            raise AssertionError('EC3190 working native control changed')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('EC3190 aligned reference set changed')
    if (source_text is None or source_text(FIRST) != TEXT or fixed_bytes(FIRST) != ROW
            or not fixable(FIRST) or fit_level(FIRST) != 99):
        raise AssertionError('EC3190 source authority/encoding changed')
    record = copy.deepcopy(METADATA)
    validate(PAYLOAD,record)
    return PAYLOAD,record
