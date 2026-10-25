"""B82FAC late append only. Static contract; runtime remains DEFER.

Pins transcribed from aw-reloc0736 and decoder0731 preserved evidence.
The native source stays retired/current; only D8D9CC is redirected.
"""
import array
import copy
import sys

MESSAGE, END, SITE = 0xB82FAC, 0xB82FDC, 0xD8D9CC
ARENA_START, ARENA_END, HIGH_WATER = 0xA3D000, 0xAFF000, 0xA8D7B1
APPEND = (HIGH_WATER + 3) & ~3
TEXT = '맵을 저장 중이야,전원을 끄지 말아 줘!!'
NATIVE = bytes.fromhex('837d8362837682f095db91b6928682e6814182c582f182b082f182f090d882e782c882a282c582cb8149814900000000')
CURRENT = bytes.fromhex('8fc68fc281408fef81408fc88f6d814088d2905481408bc3202020202020202020202020202020202020202000000000')
ROW = bytes.fromhex('8bd98f8181408fc68fc281408fef8fa28eba81418fc88f6d8f81814088d2905481408bca8e9b81408ff181498149')
PAYLOAD = ROW + NATIVE[-4:]
KEY = '0xB82FAC'
METADATA = dict(msg=KEY, status='relocated', ptr_off='0xD8D9CC',
    old_len=48, new_len=50, lines=1, fixed=[KEY], line_spans={KEY:[0,46]},
    layout_controls={}, source_spans={KEY:44}, source_texts={KEY:TEXT}, ptr_sites=['0xD8D9CC'])
RETAINED_WRITER = 'b82fac-retained-native'
# Each pair is immutable original / already-adopted working bytes, not a new hook.
PINS = {
    0xb12074: (bytes.fromhex('f0b584b0051c0e1c296a087809380a1c2a2868d88000024940180068874600009820b108'),
        bytes.fromhex('f0b584b0051c0e1c296a087809380a1c2a2868d88000024940180068874600009820b108')),
    0xb12144: (bytes.fromhex('286a0130286297e7296a08783038e8850131296290e71078772800d968e2800001494018006887467021b108'),
        bytes.fromhex('286a0130286297e7296a08783038e8850131296290e71078772800d968e2800001494018006887467021b108')),
    0xb12350: (bytes.fromhex('686a002801d100206de128620020686203e0'),
        bytes.fromhex('686a002801d100206de128620020686203e0')),
    0xb12634: (bytes.fromhex('012004b0f0bc02bc0847'),
        bytes.fromhex('012004b0f0bc02bc0847')),
    0xb12716: (bytes.fromhex('e06b69f0fafa201cfff72ffa051c201c291cfff7a4fc00040014012811d0012802dc002805d00ce002282ad0032824d007e002480021405e01f0c9f821e0'),
        bytes.fromhex('e06b69f0fafa201cfff72ffa051c201c291cfff7a4fc00040014012811d0012802dc002805d00ce002282ad0032824d007e002480021405e01f0c9f821e0')),
    0xb12758: (bytes.fromhex('206aa18ee28d09f0cdfb201c291cfff76bff201c38300078002802d070202bf04ffe206a02302062211c3231087801300870a08e0230a086002030560028c1db70bc01bc0047'),
        bytes.fromhex('206aa18ee28d09f0cdfb201c004800474105f30838300078002802d070202bf04ffe206a02302062211c3231087801300870a08e0230a086002030560028c1db70bc01bc0047')),
    0xf30000: (bytes.fromhex('00000000000000000000000000000000000000000000000000000000'),
        bytes.fromhex('030404d4054b4001c71806480047044b4004400c4001c71802480047')),
    0xf30030: (bytes.fromhex('00000000000000000000000000000000000000000000000000000000'),
        bytes.fromhex('030404d4054b4001c71806480047044b4004400c4001c71802480047')),
    0xf30540: (bytes.fromhex('000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
        bytes.fromhex('3221625c5200a16a89183323e35c9b01c9182046034a9646034b18472046034b1847c0465d05f3084126b1086d27b108')),
    0xefe944: (bytes.fromhex('000c1a431143084330800236604601300006000e84460f28ced903b038bc9846a146aa46f0bc01bc00470000'),
        bytes.fromhex('000c1a431143084330800236604601300006000e84460f28ced903b038bc9846a146aa46f0bc01bc00470000')),
    0xd826e4: (bytes.fromhex('a127b10800000a0000000000010000005526b10800000100'),
        bytes.fromhex('a127b10800000a0000000000010000005526b10800000100')),
    0xb12098: (bytes.fromhex('4421b1084421b1085a21b1085a21b1084421b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1084421b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1084c21b1084c21b1084c21b1084c21b108'),
        bytes.fromhex('4421b1084421b1085a21b1085a21b1084421b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1080005f3085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1085a21b1084c21b1084c21b1084c21b1084c21b108')),
    0xd8d998: (bytes.fromhex('8831b8086031b8083031b8080c31b808ec30b808c830b808ac30b8088c30b8086c30b8084430b8081c30b8080030b808dc2fb808ac2fb8087c2fb808542fb80800e001e0'),
        bytes.fromhex('94d2a5086031b8083031b808b0d2a508d8d2a508fcd2a508ac30b8082cd3a50850d3a50878d3a508a4d3a5080030b808dc2fb808ac2fb8087c2fb808542fb80800e001e0')),
    0xb33e3c: (bytes.fromhex('b4d8d80814d9d808'),
        bytes.fromhex('b4d8d80814d9d808')),
    0xb33e18: (bytes.fromhex('10b5084800680078032808d1064c206800880d210022fff7e5fa2168088010bc01bc0047b4d8d80814d9d808'),
        bytes.fromhex('10b5084800680078032808d1064c206800880d210022fff7e5fa2168088010bc01bc0047b4d8d80814d9d808')),
    0xb333fc: (bytes.fromhex('70b582b0000409040d0c1204160c88421ed0dff711fb114c02200090b22040000190201c032111221a23ddf705fd0c49a80040180368c0208001009098204000019003201121221cdff764fa3a300670281c02b070bc02bc08470000442d010298d9d808'),
        bytes.fromhex('70b582b0000409040d0c1204160c88421ed0dff711fb114c02200090b22040000190201c032111221a23ddf705fd0c49a80040180368c0208001009098204000019003201121221cdff764fa3a300670281c02b070bc02bc08470000442d010298d9d808')),
    0xb12910: (bytes.fromhex('70b556464d46444670b484b0041c0d1c924699460b9e0c9a2404240c2d042d0c3604360c1204120c10490020087010480021039200f0b0ff8046240424142d042d14484600900196039a02924046211c2a1c534600f00ef8404604b038bc9846a146aa4670bc02bc08470000142f0003e426d80870b58446049c059d06980904090c1204120c0004000c6646346200247462b3620023b585f485f086b0866046383003700838017001300270013001700130027061463931ff2008700131022008700248f06370bc01bc0047c119b10830b5114801f018fc0006001601256d42c04341420143cc0f0c4801f00dfc00060016a84200d00134094801f005fc00060016a84200d001340020002c00dd012030bc02bc08470000e426d808fc26d8081c27d80800b5054800f07eff044800f07bff044800f078ff01bc0047e426d808fc26d8081c27d808f0b557464e464546'),
        bytes.fromhex('70b556464d46444670b484b0041c0d1c924699460b9e0c9a2404240c2d042d0c3604360c1204120c10490020087010480021039200f0b0ff8046240424142d042d14484600900196039a02924046211c2a1c534600f00ef8404604b038bc9846a146aa4670bc02bc08470000142f0003e426d80870b58446049c059d06980904090c1204120c0004000c6646346200247462b3620023b585f485f086b0866046383003700838017001300270013001700130027061463931ff2008700131022008700248f06370bc01bc0047c119b10830b5114801f018fc0006001601256d42c04341420143cc0f0c4801f00dfc00060016a84200d00134094801f005fc00060016a84200d001340020002c00dd012030bc02bc08470000e426d808fc26d8081c27d80800b5054800f07eff044800f07bff044800f078ff01bc0047e426d808fc26d8081c27d808f0b557464e464546')),
    0xb126d8: (bytes.fromhex('10680068818901200840002802d0201cfff7bcfc211c3931087801300870000602160e1c002a0adb201c3a30007800060016824244db002a01db00203070e06b69f0fafa201cfff72ffa051c201c291cfff7a4fc00040014012811d0012802dc002805d00ce002282ad0032824d007e002480021405e01f0c9f821e0081d0003206aa18ee28d09f0cdfb201c291cfff76bff201c38300078002802d070202bf04ffe206a02302062211c3231087801300870a08e0230a086002030560028c1db70bc01bc0047000000b507490878022801d100200870054801f0c2f8044801f0bff801bc00470000142f00039435d808d035d808021c1b4b186a1062586a5062986a9062988d9085d88dd085988ed0869086181c38300178101c38300170181c30300178101c30300170181c31300078111c31310870181c3230007801310870181c3330007801310870181c3930007806310870181c3a30007801310870d86bd0637047e8100102'),
        bytes.fromhex('10680068818901200840002802d0201cfff7bcfc211c3931087801300870000602160e1c002a0adb201c3a30007800060016824244db002a01db00203070e06b69f0fafa201cfff72ffa051c201c291cfff7a4fc00040014012811d0012802dc002805d00ce002282ad0032824d007e002480021405e01f0c9f821e0081d0003206aa18ee28d09f0cdfb201c004800474105f30838300078002802d070202bf04ffe206a02302062211c3231087801300870a08e0230a086002030560028c1db70bc01bc0047000000b507490878022801d100200870054801f0c2f8044801f0bff801bc00470000142f00039435d808d035d808021c1b4b186a1062586a5062986a9062988d9085d88dd085988ed0869086181c38300178101c38300170181c30300178101c30300170181c31300078111c31310870181c3230007801310870181c3330007801310870181c3930007806310870181c3a30007801310870d86bd0637047e8100102')),
    0xb10e34: (bytes.fromhex('f0b5059c069d090412041b041e0c2404240c2d042d0c0023c90b4018920a87180022a24213d258003918002020330132b04206d20d80023101300004000cb042f8d31804030c1004020ca242ebd3f0bc01bc0047c90a1f2211404378202252421a400a4342707047890b03221140890003780d2252421a400a43027070470000890143783f221a400a43427070470000f0b557464e464546e0b482b0071cfff79bfb654880463968fff7deff79684046fff7d0fff9684046fff7e2ff'),
        bytes.fromhex('f0b5059c069d090412041b041e0c2404240c2d042d0c0023c90b4018920a87180022a24213d258003918002020330132b04206d20d80023101300004000cb042f8d31804030c1004020ca242ebd3f0bc01bc0047c90a1f2211404378202252421a400a4342707047890b03221140890003780d2252421a400a43027070470000890143783f221a400a43427070470000f0b557464e464546e0b482b0071cfff79bfb654880463968fff7deff79684046fff7d0fff9684046fff7e2ff')),
}


def validate(payload, record):
    expected = dict(METADATA, new_addr=f'0x{APPEND:06X}')
    if bytes(payload) != PAYLOAD or record != expected:
        raise AssertionError('B82FAC exact payload/metadata/allocation changed')


def validate_row(payload):
    if bytes(payload) != ROW:
        raise AssertionError('B82FAC exact 46B row required')


def require_enabled(enabled):
    if not enabled:
        raise AssertionError('B82FAC late append requires dialogue repoint')


def pending_requirements(required, completed):
    if MESSAGE in completed:
        raise AssertionError('B82FAC completed before late append')
    return set(required) & {MESSAGE}


def retain_native(original, rom, write_log):
    if (bytes(original[MESSAGE:END]) != NATIVE or
            bytes(rom[END-4:END]) != NATIVE[-4:] or
            any(row[7] == RETAINED_WRITER for row in write_log)):
        raise AssertionError('B82FAC retired-source boundary/duplicate writer')
    rom[MESSAGE:END-4] = CURRENT[:-4]
    write_log.append([MESSAGE,44,24,CURRENT[:24].hex(),0x20,
                      '저장　중　전원　끄지　마',None,RETAINED_WRITER])


def check_pins(original, rom, *, final=False):
    if bytes(original[MESSAGE:END]) != NATIVE or bytes(rom[MESSAGE:END]) != CURRENT:
        raise AssertionError('B82FAC original/current native48 changed')
    for start, (native, current) in PINS.items():
        if bytes(original[start:start+len(native)]) != native:
            raise AssertionError(f'B82FAC original consumer pin {start:#x}')
        expected = bytearray(current)
        if final and start <= SITE < start+len(current):
            expected[SITE-start:SITE-start+4] = (0x08000000+APPEND).to_bytes(4,'little')
        if bytes(rom[start:start+len(current)]) != expected:
            raise AssertionError(f'B82FAC working consumer pin {start:#x}')


def preflight(original, rom, manifest, write_log, *, line_index, slots,
              source_text, fixed_bytes, valid_codes, enabled=True,
              arena_start=ARENA_START, arena_end=ARENA_END, align=4):
    require_enabled(enabled)
    check_pins(original, rom)
    targets = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if targets != [dict(msg=KEY,status='skip_wide_line',lines=[KEY])]:
        raise AssertionError('B82FAC missing/duplicate/intermediate target')
    relocated = [m for m in manifest if m.get('status') == 'relocated']
    if len(relocated) != 2982 or len({m['msg'] for m in relocated}) != 2982:
        raise AssertionError('B82FAC requires final 2982 allocations')
    high = max(int(m['new_addr'],16)+m['new_len'] for m in relocated)
    if (high != HIGH_WATER or arena_start != ARENA_START or arena_end != ARENA_END
            or align != 4 or (high+3)//4*4 != APPEND
            or not arena_start <= APPEND < APPEND+52 <= arena_end <= len(rom)):
        raise AssertionError('B82FAC scoped arena/high-water/align/capacity')
    lines = [(a, item[0]) for a,item in line_index.items() if MESSAGE <= a < END]
    if (lines != [(MESSAGE,44)] or slots.get(MESSAGE) != 44
            or source_text(MESSAGE) != TEXT):
        raise AssertionError('B82FAC source44/authority/line ownership')
    validate_row(fixed_bytes(MESSAGE))
    codes = {int.from_bytes(ROW[i:i+2],'big') for i in range(0,46,2)}
    if valid_codes is None or not (codes - {0x8140,0x8141,0x8149}) <= set(valid_codes):
        raise AssertionError('B82FAC missing required glyph')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('B82FAC aligned start/interior/tail aliases changed')
    if bytes(original[APPEND:APPEND+52]) != b'\xff'*52:
        raise AssertionError('B82FAC original adopted arena occupied')
    for row in write_log:
        start, length = int(row[0]), int(row[1])
        if start < APPEND+52 and APPEND < start+length:
            raise AssertionError('B82FAC append/alignment intersects prior writer')
    check_retained(rom, write_log)


def check_retained(rom, write_log):
    expected = [MESSAGE,44,24,CURRENT[:24].hex(),0x20,
                '저장　중　전원　끄지　마',None,RETAINED_WRITER]
    if ([r for r in write_log if r[7] == RETAINED_WRITER] != [expected]
            or bytes(rom[MESSAGE:END]) != CURRENT):
        raise AssertionError('B82FAC retired native writer missing/changed')
    # Last writer covering any retired byte must be this explicit owner.
    for address in range(MESSAGE,END-4):
        owners = [r for r in write_log if int(r[0]) <= address < int(r[0])+int(r[1])]
        if not owners or owners[-1] != expected:
            raise AssertionError('B82FAC retired source overwritten')


def final(rom, manifest, write_log):
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if len(records) != 1:
        raise AssertionError('B82FAC final target missing/duplicate')
    validate(rom[APPEND:APPEND+50], records[0])
    if bytes(rom[SITE:SITE+4]) != (0x08000000+APPEND).to_bytes(4,'little'):
        raise AssertionError('B82FAC final pointer changed')
    check_retained(rom,write_log)
    owner = [APPEND,50,50,'',None,None,None,'repoint:0xB82FAC',
             dict(source_spans={KEY:44},source=MESSAGE,old_len=48,ptr_sites=[SITE])]
    if [r for r in write_log if r[7] == 'repoint:0xB82FAC'] != [owner]:
        raise AssertionError('B82FAC final payload owner missing/changed')
    overlaps = [r for r in write_log if int(r[0]) < APPEND+52 and APPEND < int(r[0])+int(r[1])]
    if overlaps != [owner] or bytes(rom[APPEND+50:APPEND+52]) != b'\xff\xff':
        raise AssertionError('B82FAC active allocation/alignment ownership changed')


def close_requirements(rom, manifest, write_log, required, completed, pending):
    final(rom,manifest,write_log)
    if pending != (set(required) & {MESSAGE}) or MESSAGE in completed:
        raise AssertionError('B82FAC pending obligation changed/premature completion')
    completed.add(MESSAGE)
    if not pending <= completed:
        raise AssertionError('B82FAC late requirement not fulfilled')


def append(original, rom, manifest, write_log, **kwargs):
    """Use the existing allocator after spacing. Failure rejects the candidate.

    Preflight failures do not write. A later failure does not promise rollback
    of the build's working buffer (including earlier successful stages).
    """
    preflight(original,rom,manifest,write_log,**kwargs)
    from dialogue_repoint import repoint_messages, text_segment_cells
    from qa_b82fac_preservation import validate as preserve
    before, old_manifest, old_log = bytes(rom), copy.deepcopy(manifest), copy.deepcopy(write_log)
    high_water = max(int(m['new_addr'],16)+m['new_len'] for m in manifest
                     if m.get('status') == 'relocated')
    next_free = (high_water + 3) & ~3  # computed allocation; APPEND is only its expected pin
    added, stats = repoint_messages(rom,original,
        fixable=lambda a:a==MESSAGE, fixed_bytes=lambda a:ROW,
        fit_level_dlg=lambda a:99, decode_text=lambda raw:TEXT,
        cell_width=lambda a:text_segment_cells(ROW), slots={MESSAGE:44},
        line_index={MESSAGE:(44,kwargs['line_index'][MESSAGE][1])},
        table_offsets=[], extra_messages={MESSAGE:[SITE]},
        free_start=next_free, free_end=ARENA_END, align=4,
        max_cells_for_address=lambda a:52, source_text=lambda a:TEXT,
        valid_codes=kwargs['valid_codes'], write_log=write_log,
        require_b82fac=True)
    if len(added) != 1 or stats.get('relocated') != 1 or stats.get('free_used') != 52:
        raise AssertionError('B82FAC late append did not allocate exactly once')
    validate(rom[APPEND:APPEND+50],added[0])
    candidate = [m for m in manifest if int(m['msg'],16) != MESSAGE] + added
    preserve(before,rom,old_manifest,candidate,old_log,write_log)
    manifest[:] = candidate
    return dict(relocated=1,removed_skip_wide_line=1,free_used=52,
                free_remaining=ARENA_END-APPEND-52)
