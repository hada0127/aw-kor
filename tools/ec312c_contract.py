"""Exact EC2714 consumer late append after B82FAC. Runtime remains DEFER.

Native52/source46/header2/full52/tail4; no generic width relaxation.
"""
import array
import copy
import sys

MESSAGE, FIRST, END, SITE = 0xEC312C, 0xEC312E, 0xEC3160, 0xEC2714
ARENA_START, ARENA_END, HIGH_WATER = 0xA3D000, 0xAFF000, 0xA8D7E6
APPEND = (HIGH_WATER + 3) & ~3
TEXT = '지정일이 종료되면 소유 거점 수로 결판을 냅니다'
NATIVE = bytes.fromhex('0a098e7792e893fa82aa8f4997b982b582bd8e9e82c98f8a974c8b92935f909482c58c88928582f082c282af82dc82b70a000000')
CURRENT = bytes.fromhex('0a0990548fd18fa8814088e288e98bf5814088528fcc81408def8b6981408e4d8d5620202020202020202020202020200a000000')
ROW = bytes.fromhex('90548fd18fa88fa281408fe08b738a628bf581408ddf8f78814088528fcc81408def8b6981408860925c8f818140895489d489e2')
PAYLOAD = bytes.fromhex('0a0990548fd18fa88fa281408fe08b738a628bf581408ddf8f78814088528fcc81408def8b6981408860925c8f818140895489d489e20a000000')
KEY, SOURCE_KEY = '0xEC312C', '0xEC312E'
METADATA = dict(msg=KEY, status='relocated', ptr_off='0xEC2714',
    old_len=52, new_len=58, lines=1, fixed=[SOURCE_KEY], line_spans={SOURCE_KEY:[2,52]},
    layout_controls={}, source_spans={SOURCE_KEY:46}, source_texts={SOURCE_KEY:TEXT},
    ptr_sites=['0xEC2714'])
RETAINED_WRITER = 'ec312c-retained-native'
# Shared, already-adopted decoder/glyph bytes; B82FAC's caller/table are excluded.
# Provenance: plan0831 source-binding + planfix0841 F1 / plandelta0846.
from b82fac_contract import PINS as _SHARED_PINS
from ec3190_contract import CONSUMER_BYTES as _NATIVE_CONSUMER
PINS = {a: _SHARED_PINS[a] for a in (
    0xB12074, 0xB12098, 0xB12144, 0xB12350, 0xB12634, 0xB126D8,
    0xF30000, 0xF30030, 0xF30540, 0xEFE944, 0xD826E4, 0xB12910, 0xB10E34)}
# B1215A dispatch literal and its NUL entry -> B12350 (decoder0731,
# re-bound to current0816 by plan0831 source-binding).
PINS[0xB1216C] = (bytes.fromhex('7021b1085023b108'),) * 2
PINS[0xB71160] = (_NATIVE_CONSUMER[0xB71160],) * 2
PINS[0xEC2708] = (_NATIVE_CONSUMER[0xEC2708], bytes.fromhex('a030ec08d430ec080831ec082c31ec086031ec08640ba8087032ec088c32ec087032ec088c32ec087032ec088c32ec087032ec088c32ec08c031ec08d831ec080032ec081c32ec08'))
# Distinct from clear fill 0x164: exact caller starts at 0x100.
TILE_START, TILE_LAST_PAIR, TILE_NEXT, CLEAR_FILL = 0x100, (0x132, 0x133), 0x134, 0x164
PROFILE = ('p1_link_notice', 208, 1)


def validate(payload, record):
    expected = dict(METADATA, new_addr=f'0x{APPEND:06X}')
    if bytes(payload) != PAYLOAD or record != expected:
        raise AssertionError('EC312C exact payload/metadata/allocation changed')


def validate_row(payload):
    if bytes(payload) != ROW:
        raise AssertionError('EC312C exact 52B row required')


def require_enabled(enabled):
    if not enabled:
        raise AssertionError('EC312C late append requires dialogue repoint')


def pending_requirements(required, completed):
    if FIRST in completed:
        raise AssertionError('EC312C completed before late append')
    return set(required) & {FIRST}


def retained_owner():
    return [FIRST,46,32,CURRENT[2:34].hex(),0x20,
            '지정일　끝나면　거점　수로　승부',None,RETAINED_WRITER]


def retain_native(original, rom, write_log):
    if (bytes(original[MESSAGE:END]) != NATIVE or
            bytes(rom[MESSAGE:FIRST]) != NATIVE[:2] or
            bytes(rom[END-4:END]) != NATIVE[-4:] or
            any(row[7] == RETAINED_WRITER for row in write_log)):
        raise AssertionError('EC312C retained-source boundary/duplicate writer')
    rom[FIRST:END-4] = CURRENT[2:-4]
    write_log.append(retained_owner())


def check_pins(original, rom, *, final=False):
    if bytes(original[MESSAGE:END]) != NATIVE or bytes(rom[MESSAGE:END]) != CURRENT:
        raise AssertionError('EC312C original/current native52 changed')
    for start, (native, current) in PINS.items():
        if bytes(original[start:start+len(native)]) != native:
            raise AssertionError(f'EC312C original consumer pin {start:#x}')
        expected = bytearray(current)
        if final and start <= SITE < start+len(current):
            expected[SITE-start:SITE-start+4] = (0x08000000+APPEND).to_bytes(4,'little')
        if bytes(rom[start:start+len(current)]) != expected:
            raise AssertionError(f'EC312C working consumer pin {start:#x}')
    from dialogue_pixel_layout import p1_consumers
    entries = p1_consumers(original).get(MESSAGE)
    if entries != [dict(site=SITE, profile=PROFILE,
                        consumer='B711BE table index3 / B71204 instructions')]:
        raise AssertionError('EC312C exact inventory consumer/profile changed')


def preflight(original, rom, manifest, write_log, *, line_index, slots,
              source_text, fixed_bytes, valid_codes, enabled=True,
              arena_start=ARENA_START, arena_end=ARENA_END, align=4):
    require_enabled(enabled)
    check_pins(original, rom)
    targets = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if targets != [dict(msg=KEY,status='skip_wide_line',lines=[SOURCE_KEY])]:
        raise AssertionError('EC312C missing/duplicate/intermediate target')
    if source_owners(manifest):
        raise AssertionError('EC312C source already has an active owner')
    relocated = [m for m in manifest if m.get('status') == 'relocated']
    if len(relocated) != 2983 or len({m['msg'] for m in relocated}) != 2983:
        raise AssertionError('EC312C requires final 2983 allocations')
    high = max(int(m['new_addr'],16)+m['new_len'] for m in relocated)
    if (high != HIGH_WATER or arena_start != ARENA_START or arena_end != ARENA_END
            or align != 4 or (high+3)//4*4 != APPEND
            or not arena_start <= APPEND < APPEND+60 <= arena_end <= len(rom)):
        raise AssertionError('EC312C scoped arena/high-water/align/capacity')
    lines = [(a, item[0]) for a,item in line_index.items() if MESSAGE <= a < END]
    if (lines != [(FIRST,46)] or slots.get(FIRST) != 46
            or source_text(FIRST) != TEXT):
        raise AssertionError('EC312C source46/authority/line ownership')
    validate_row(fixed_bytes(FIRST))
    codes = {int.from_bytes(ROW[i:i+2],'big') for i in range(0,52,2)}
    if valid_codes is None or not (codes - {0x8140}) <= set(valid_codes):
        raise AssertionError('EC312C missing required glyph')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('EC312C aligned start/interior/tail aliases changed')
    if (bytes(original[HIGH_WATER:APPEND+60]) != b'\xff'*(APPEND+60-HIGH_WATER)
            or bytes(rom[HIGH_WATER:APPEND+60]) != b'\xff'*(APPEND+60-HIGH_WATER)):
        raise AssertionError('EC312C original adopted arena occupied')
    for row in write_log:
        start, length = int(row[0]), int(row[1])
        if start < APPEND+60 and HIGH_WATER < start+length:
            raise AssertionError('EC312C append/alignment intersects prior writer')
        if start < SITE+4 and SITE < start+length:
            raise AssertionError('EC312C pointer intersects prior payload owner')
        if len(row) > 8 and SITE in row[8].get('ptr_sites', []):
            raise AssertionError('EC312C pointer already owned')
    from qa_ec312c_preservation import baseline
    baseline(rom, manifest)
    check_retained(rom, write_log)


def check_retained(rom, write_log):
    expected = retained_owner()
    if ([r for r in write_log if r[7] == RETAINED_WRITER] != [expected]
            or bytes(rom[MESSAGE:END]) != CURRENT):
        raise AssertionError('EC312C retired native writer missing/changed')
    # Last writer covering any retired byte must be this explicit owner.
    for address in range(FIRST,END-4):
        owners = [r for r in write_log if int(r[0]) <= address < int(r[0])+int(r[1])]
        if not owners or owners[-1] != expected:
            raise AssertionError('EC312C retired source overwritten')


def source_owners(manifest):
    return [m for m in manifest if SOURCE_KEY in m.get('line_spans', {})
            or SOURCE_KEY in m.get('source_spans', {}) or SOURCE_KEY in m.get('fixed', [])]


def final(rom, manifest, write_log):
    for start, (_, raw) in PINS.items():
        expected = bytearray(raw)
        if start <= SITE < start+len(raw):
            expected[SITE-start:SITE-start+4] = (0x08000000+APPEND).to_bytes(4,'little')
        if bytes(rom[start:start+len(raw)]) != expected:
            raise AssertionError(f'EC312C final consumer pin {start:#x}')
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if len(records) != 1 or source_owners(manifest) != records:
        raise AssertionError('EC312C final target missing/duplicate')
    validate(rom[APPEND:APPEND+58], records[0])
    if bytes(rom[SITE:SITE+4]) != (0x08000000+APPEND).to_bytes(4,'little'):
        raise AssertionError('EC312C final pointer changed')
    check_retained(rom,write_log)
    if bytes(rom[HIGH_WATER:APPEND]) != b'\xff'*(APPEND-HIGH_WATER):
        raise AssertionError('EC312C preceding alignment changed')
    owner = [APPEND,58,58,'',None,None,None,'repoint:0xEC312C',
             dict(source_spans={SOURCE_KEY:46},source=MESSAGE,old_len=52,ptr_sites=[SITE])]
    if [r for r in write_log if r[7] == 'repoint:0xEC312C'] != [owner]:
        raise AssertionError('EC312C final payload owner missing/changed')
    pointer_owners = [r for r in write_log if len(r) > 8 and
                      isinstance(r[8], dict) and SITE in r[8].get('ptr_sites', [])]
    if pointer_owners != [owner] or any(int(r[0]) < SITE+4 and SITE < int(r[0])+int(r[1])
                                      for r in write_log):
        raise AssertionError('EC312C sole pointer ownership changed')
    overlaps = [r for r in write_log if int(r[0]) < APPEND+60 and APPEND < int(r[0])+int(r[1])]
    if overlaps != [owner] or bytes(rom[APPEND+58:APPEND+60]) != b'\xff\xff':
        raise AssertionError('EC312C active allocation/alignment ownership changed')


def close_requirements(rom, manifest, write_log, required, completed, pending):
    final(rom,manifest,write_log)
    if pending != (set(required) & {FIRST}) or FIRST in completed:
        raise AssertionError('EC312C pending obligation changed/premature completion')
    completed.add(FIRST)
    if not pending <= completed:
        raise AssertionError('EC312C late requirement not fulfilled')


def append(original, rom, manifest, write_log, **kwargs):
    """Use the existing allocator after spacing. Failure rejects the candidate.

    Preflight failures do not write. A later failure does not promise rollback
    of the build's working buffer (including earlier successful stages).
    """
    preflight(original,rom,manifest,write_log,**kwargs)
    from dialogue_repoint import repoint_messages, text_segment_cells
    from qa_ec312c_preservation import validate as preserve
    before, old_manifest, old_log = bytes(rom), copy.deepcopy(manifest), copy.deepcopy(write_log)
    high_water = max(int(m['new_addr'],16)+m['new_len'] for m in manifest
                     if m.get('status') == 'relocated')
    next_free = (high_water + 3) & ~3  # computed allocation; APPEND is only its expected pin
    added, stats = repoint_messages(rom,original,
        fixable=lambda a:a==FIRST, fixed_bytes=lambda a:ROW,
        fit_level_dlg=lambda a:99, decode_text=lambda raw:TEXT,
        cell_width=lambda a:text_segment_cells(ROW), slots={FIRST:46},
        line_index={FIRST:(46,kwargs['line_index'][FIRST][1])},
        table_offsets=[], extra_messages={MESSAGE:[SITE]},
        free_start=next_free, free_end=ARENA_END, align=4,
        max_cells_for_address=lambda a:52, source_text=lambda a:TEXT,
        valid_codes=kwargs['valid_codes'], write_log=write_log,
        require_ec312c=True)
    if len(added) != 1 or stats.get('relocated') != 1 or stats.get('free_used') != 60:
        raise AssertionError('EC312C late append did not allocate exactly once')
    validate(rom[APPEND:APPEND+58],added[0])
    candidate = [m for m in manifest if int(m['msg'],16) != MESSAGE] + added
    preserve(before,rom,old_manifest,candidate,old_log,write_log)
    manifest[:] = candidate
    return dict(relocated=1,removed_skip_wide_line=1,free_used=60,
                free_remaining=ARENA_END-APPEND-60)


def exact_half_cells(address, payload):
    """Only exact source+body selects this consumer; final() binds its owner."""
    if address != FIRST:
        return 0
    validate_row(payload)
    return 52
