"""plan0931/planreview1001: retained Help source, exact40B late display append.

Static contract only. Runtime/Link remain DEFER; no generic width/NUL change.
"""
import array
import copy
from hashlib import sha256
import sys

MESSAGE = FIRST = 0xD821F0
END, SITE = 0xD82218, 0xB05968
KEY = SOURCE_KEY = '0xD821F0'
ARENA_START, ARENA_END, HIGH_WATER = 0xA3D000, 0xAFF000, 0xA8D822
APPEND = (HIGH_WATER + 3) & ~3
TEXT = '선택 중인 지형,병종을 배치합니다.'
NATIVE = bytes.fromhex('914991f082b582c482a282e9926e8c60814195ba8eed82f0947a927582b582dc82b7814200000000')
CURRENT = bytes.fromhex('8dc291d781408fef8fa58140905492dc81408d438fe08f8181408ccc915492b489d489e200000000')
ROW = bytes.fromhex('8dc291d781408fef8fa58140905492dc81418d438fe08f8181408ccc915492b489d489e28142')
PAYLOAD = ROW + b'\0\0'
PROFILE = ('p1_editor_help',152,1)
RETAINED_WRITER = 'd821f0-retained-native'
DISPLAY_WRITER = 'repoint:0xD821F0'
METADATA = dict(msg=KEY,status='relocated',ptr_off='0xB05968',old_len=40,
    new_len=40,lines=1,fixed=[KEY],line_spans={KEY:[0,38]},layout_controls={},
    source_spans={KEY:36},source_texts={KEY:TEXT},ptr_sites=['0xB05968'])


def record():
    return copy.deepcopy(dict(METADATA,new_addr=f'0x{APPEND:06X}'))


def validate(payload, metadata):
    if bytes(payload) != PAYLOAD or metadata != record():
        raise AssertionError('D821F0 exact40/body38/tail2/metadata changed')


def require_enabled(enabled):
    if not enabled:
        raise AssertionError('D821F0 display append requires dialogue repoint')


def pending_requirements(required, completed):
    if FIRST in completed:
        raise AssertionError('D821F0 completed before late append')
    return set(required) & {FIRST}


def retained_owner():
    return [FIRST,36,36,CURRENT[:36].hex(),None,
            '선택　중인　지형　병종을　배치합니다',None,RETAINED_WRITER]


def display_owner():
    return [APPEND,40,40,'',None,None,None,DISPLAY_WRITER,
            dict(source_spans={KEY:36},source=MESSAGE,old_len=40,ptr_sites=[SITE])]


def retain_native(original, rom, write_log):
    if (bytes(original[MESSAGE:END]) != NATIVE or bytes(rom[END-4:END]) != b'\0'*4
            or any(r[7] == RETAINED_WRITER for r in write_log)):
        raise AssertionError('D821F0 native boundary/duplicate retained writer')
    rom[MESSAGE:END-4] = CURRENT[:36]
    write_log.append(retained_owner())


def check_retained(rom, write_log):
    expected = retained_owner()
    if (bytes(rom[MESSAGE:END]) != CURRENT
            or [r for r in write_log if r[7] == RETAINED_WRITER] != [expected]):
        raise AssertionError('D821F0 retained source/owner changed')
    for address in range(MESSAGE,END-4):
        owners = [r for r in write_log if int(r[0]) <= address < int(r[0])+int(r[1])]
        if not owners or owners[-1] != expected:
            raise AssertionError('D821F0 retained source last writer changed')


def source_owners(manifest):
    return [m for m in manifest if KEY in m.get('line_spans',{})
            or KEY in m.get('source_spans',{}) or KEY in m.get('fixed',[])]


def check_current_pins(rom):
    gate_variants = []
    for start,end,digest in CURRENT_PINS:
        actual = sha256(rom[start:end]).hexdigest()
        if start in EDITOR_GATE_PINS and actual == EDITOR_GATE_PINS[start]:
            gate_variants.append('editor')
        elif actual == digest:
            if start in EDITOR_GATE_PINS:
                gate_variants.append('accepted0916')
        else:
            raise AssertionError(f'D821F0 current source/consumer pin {start:#x}')
    if len(set(gate_variants)) != 1:
        raise AssertionError('D821F0 editor gate pin variants mixed')
    if gate_variants[0] == 'editor':
        from part1_editor_compact_labels import verify as verify_editor_gate
        verify_editor_gate(rom)
    from part1_editor_help_dictionary import verify, dictionary
    verify(rom)  # fixed source hashes, exact 70-entry order and loader
    codes = {dictionary(rom)[i:i+2] for i in range(0,140,2)}
    if not {ROW[i:i+2] for i in range(0,38,2)} - {b'\x81\x40'} <= codes:
        raise AssertionError('D821F0 Help dictionary lacks required glyph')


def check_pins(original, rom, *, final=False):
    if bytes(original[MESSAGE:END]) != NATIVE:
        raise AssertionError('D821F0 original native40 changed')
    for start,end,digest in ORIGINAL_PINS:
        if sha256(original[start:end]).hexdigest() != digest:
            raise AssertionError(f'D821F0 original consumer pin {start:#x}')
    check_current_pins(rom)
    expected = APPEND if final else MESSAGE
    if (bytes(original[SITE:SITE+4]) != (0x08000000+MESSAGE).to_bytes(4,'little')
            or bytes(rom[SITE:SITE+4]) != (0x08000000+expected).to_bytes(4,'little')):
        raise AssertionError('D821F0 sole display pointer changed')
    from dialogue_pixel_layout import p1_consumers
    if p1_consumers(original).get(MESSAGE) != [dict(site=SITE,profile=PROFILE,
                                                   consumer='B058F8 editor right help')]:
        raise AssertionError('D821F0 inventory consumer/profile changed')


def preflight(original, rom, manifest, write_log, *, line_index, slots,
              source_text, fixed_bytes, valid_codes, enabled=True,
              arena_start=ARENA_START, arena_end=ARENA_END, align=4):
    require_enabled(enabled)
    check_pins(original,rom)
    if any(int(m['msg'],16) == MESSAGE for m in manifest) or source_owners(manifest):
        raise AssertionError('D821F0 early/duplicate active source owner')
    from qa_d821f0_preservation import baseline
    baseline(rom,manifest)
    if (arena_start != ARENA_START or arena_end != ARENA_END or align != 4
            or not arena_start <= APPEND < APPEND+40 <= arena_end <= len(rom)):
        raise AssertionError('D821F0 scoped arena/alignment/capacity changed')
    if ([(a,item[0]) for a,item in line_index.items() if MESSAGE <= a < END] != [(FIRST,36)]
            or slots.get(FIRST) != 36 or source_text(FIRST) != TEXT
            or bytes(fixed_bytes(FIRST)) != ROW):
        raise AssertionError('D821F0 source36/full authority38 changed')
    if valid_codes is None or not {int.from_bytes(ROW[i:i+2],'big') for i in range(0,38,2)
                                  if ROW[i] != 0x81} <= set(valid_codes):
        raise AssertionError('D821F0 missing glyph')
    words = array.array('I'); words.frombytes(original[:len(original)//4*4])
    if sys.byteorder != 'little': words.byteswap()
    refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+MESSAGE <= w < 0x08000000+END]
    if refs != [(SITE,0x08000000+MESSAGE)]:
        raise AssertionError('D821F0 aligned start/interior/tail aliases changed')
    for image in (original,rom):
        if bytes(image[HIGH_WATER:APPEND+40]) != b'\xff'*(APPEND+40-HIGH_WATER):
            raise AssertionError('D821F0 adopted allocation/alignment occupied')
    for row in write_log:
        start,length = int(row[0]),int(row[1])
        if start < APPEND+40 and HIGH_WATER < start+length:
            raise AssertionError('D821F0 allocation overlaps writer')
        if (start < SITE+4 and SITE < start+length or
                len(row)>8 and SITE in row[8].get('ptr_sites',[])):
            raise AssertionError('D821F0 pointer already owned')
    check_retained(rom,write_log)


def final(rom, manifest, write_log):
    records = [m for m in manifest if int(m['msg'],16) == MESSAGE]
    if records != [record()] or source_owners(manifest) != records:
        raise AssertionError('D821F0 final record/source owner missing or duplicate')
    validate(rom[APPEND:APPEND+40],records[0])
    if bytes(rom[SITE:SITE+4]) != (0x08000000+APPEND).to_bytes(4,'little'):
        raise AssertionError('D821F0 actual display pointer mismatch')
    check_retained(rom,write_log)
    check_current_pins(rom)
    if bytes(rom[HIGH_WATER:APPEND]) != b'\xff'*2:
        raise AssertionError('D821F0 alignment bytes changed')
    owner = display_owner()
    if [r for r in write_log if r[7] == DISPLAY_WRITER] != [owner]:
        raise AssertionError('D821F0 display owner missing/duplicate/changed')
    if ([r for r in write_log if len(r)>8 and SITE in r[8].get('ptr_sites',[])] != [owner]
            or any(int(r[0]) < SITE+4 and SITE < int(r[0])+int(r[1]) for r in write_log)):
        raise AssertionError('D821F0 pointer owner changed')
    if [r for r in write_log if int(r[0]) < APPEND+40 and HIGH_WATER < int(r[0])+int(r[1])] != [owner]:
        raise AssertionError('D821F0 allocation/alignment owner changed')


def close_requirements(rom, manifest, write_log, required, completed, pending):
    final(rom,manifest,write_log)
    if pending != (set(required)&{FIRST}) or FIRST in completed:
        raise AssertionError('D821F0 pending changed/premature completion')
    completed.add(FIRST)


def append(original, rom, manifest, write_log, **kwargs):
    """Preflight before writes; later failure rejects the build, not a rollback promise."""
    preflight(original,rom,manifest,write_log,**kwargs)
    from dialogue_repoint import repoint_messages, text_segment_cells
    from qa_d821f0_preservation import validate as preserve
    before, old_manifest, old_log = bytes(rom),copy.deepcopy(manifest),copy.deepcopy(write_log)
    high = max(int(m['new_addr'],16)+m['new_len'] for m in manifest if m.get('status')=='relocated')
    added,stats = repoint_messages(rom,original,
        fixable=lambda a:a==FIRST,fixed_bytes=lambda a:ROW,fit_level_dlg=lambda a:99,
        decode_text=lambda raw:TEXT,cell_width=lambda a:text_segment_cells(ROW),
        slots={FIRST:36},line_index={FIRST:(36,kwargs['line_index'][FIRST][1])},
        table_offsets=[],extra_messages={MESSAGE:[SITE]},free_start=(high+3)&~3,
        free_end=ARENA_END,align=4,max_cells_for_address=lambda a:44,
        source_text=lambda a:TEXT,valid_codes=kwargs['valid_codes'],write_log=write_log,
        require_d821f0=True)
    if len(added)!=1 or stats.get('relocated')!=1 or stats.get('free_used')!=40:
        raise AssertionError('D821F0 late allocation must be exactly40 once')
    candidate = old_manifest + added
    preserve(before,rom,old_manifest,candidate,old_log,write_log)
    manifest[:] = candidate
    return dict(relocated=1,free_used=40,free_remaining=ARENA_END-APPEND-40)

# Immutable accepted0916 pins below: source, consumer, dictionary append and
# existing decoder/overlay/glyph resources. B05968 is excluded for repoint;
# unrelated jamo tiles F09F60..F0A960 are written later by name-compose.
# The separate final whole-ROM gate preserves those tiles against accepted0916.
# Only the two editor-hook spans have an exact second digest for the current
# 236B consumer gate. All other accepted0916 pins remain unchanged.
EDITOR_GATE_PINS = {
    0xF30600: '6e5283af9ed2584b1d4e4329700df5abab2f807b13cee2408eb252a969835749',
    0xF31E00: '46c6e9bffe30b22963827b05201b21c948a73e8502ee0ee82f519a683887130a',
}
CURRENT_PINS = (
    (0xB12A58,0xB12CB4,'e1db2185d7f9179f0cfca847134434d0f3ce1889dfb80fb578814f04a852f4aa'),
    (0xB10E34,0xB10E88,'2f4fff798b4b740cc6c02e8156bef98ba12a46b7fe4a542f8edbccd6c932fae4'),
    (0xB14028,0xB140BC,'c2c94b1ef88b7db3f147f9cc5f04aaf6b4a9a8fd193c389e02bb2f3904643800'),
    (0xD81258,0xD81278,'a1c95230212b34a80daf87cf1d0628499a91930c72dc14cb3c9cb4b4b1940d33'),
    (0xD8273C,0xD82746,'7d118cee1d2cf7a5ae82a8dbbe283f1481394cb3e8e2c111416f731dbda7a69d'),
    (0xD832CC,0xD832D4,'f27b1b63e6d93f457bbdf85166d8f4d0307372155b7cd6f7c806977a84c80e58'),
    (0xB0584C,0xB058E0,'4674e7f0e7523d87939128b21eca30a059997111dc1c1803ad7670af371da2a4'),
    (0xB1BEAC,0xB1BF48,'07fa5011b089a1a6ce66284aa7b69b5b6bbe089ce4943829418dc6b85a7d5809'),
    (0xD82124,0xD821EA,'4126b746da5ad3bf06ca1f1e413b013a0064437c8d5e635145bfa05a6b2c7459'),
    (0xD821F0,0xD82292,'333b2daa2e08e44281396689ef4776d8a99162e1b53b8de33d98c85ca0dc5141'),
    (0xD81C24,0xD81CFE,'063f0602773c7dc3be14eda80885164d469fd8bd48b6a427a34051754e4537be'),
    (0xB058F8,0xB05964,'8dabcd4fef8db6075548f1ae418253af538cae350573c69d28dff3cd67cbecaf'),
    (0xB0597C,0xB05BC0,'20bcfc13415ab32f3f7903ca8cf69c04639d5592e4e9e914f787797ecb79d492'),
    (0xB1311C,0xB131B0,'48c8b20a86e400db9787c2504cd57443402bb2d784a84501d33a7e11cdf3b649'),
    (0xB12074,0xB12638,'3cebb16cb78a2a9a589bf8c6dfc2f596954ad1d50a213bcbffb4f5cb11acf003'),
    (0xEFE5E4,0xEFE698,'7fd7adc86e8f9ca89d66d0d96f2393d0d8ffadeaddeeda9427c9c724bb66627f'),
    (0xF30600,0xF30800,'708d168279bc67ee2302a1df30805c97813a27cdc956b7aa04839b4274ce0ee5'),
    (0xF31E00,0xF32000,'b7f08292c6ab3deec8694695e2ba577d998d653442b2adf62241b228a00b5883'),
    (0xF51000,0xF5108E,'2d4ed20de2c1735d99066235997254e00f0095cb0da8b7cd0d643b6fba340cc2'),
    (0xF51200,0xF51238,'72deef4beab2d53a524f42eb9b850714b09f8d62d3fff2596bb87696e4e4ed11'),
    (0xB12CB4,0xB12CBC,'fe1ef3d4978ca627e5884cd0f0daf9275eb9b29fadae9686846d878f76f136ef'),
    (0xD81D30,0xD81D80,'ceb6d4c358669559163f04ece4218bbfbd11c577ef7f2af2d07191d05fa11355'),
    (0xF00000,0xF09F60,'d0db9869ada163974ff1a7663ab1520ded531288f3598493813236cf91903006'),
    (0xF0A960,0xF24494,'7784539ccc3f09b8bde65fe2b68c88341c59baa6160908b1f9aa79ea95cb3e1e'),
)
ORIGINAL_PINS = (
    (0xB12A58,0xB12CB4,'e1db2185d7f9179f0cfca847134434d0f3ce1889dfb80fb578814f04a852f4aa'),
    (0xB10E34,0xB10E88,'2f4fff798b4b740cc6c02e8156bef98ba12a46b7fe4a542f8edbccd6c932fae4'),
    (0xB14028,0xB140BC,'c2c94b1ef88b7db3f147f9cc5f04aaf6b4a9a8fd193c389e02bb2f3904643800'),
    (0xD81258,0xD81278,'a1c95230212b34a80daf87cf1d0628499a91930c72dc14cb3c9cb4b4b1940d33'),
    (0xD8273C,0xD82746,'122acbcd5b5f6f7e0102ca223702e01899f87ea17be3b563318af26080aac36b'),
    (0xD832CC,0xD832D4,'68e7cdd79c0fffe41814350b6c0a88065f8c4f885a5b6844c6c57f49c49a8ed4'),
    (0xB0584C,0xB058E0,'4674e7f0e7523d87939128b21eca30a059997111dc1c1803ad7670af371da2a4'),
    (0xB1BEAC,0xB1BF48,'07fa5011b089a1a6ce66284aa7b69b5b6bbe089ce4943829418dc6b85a7d5809'),
    (0xD82124,0xD821EA,'2ed145d1acd34e8f98ba965a0f476cadd198978b1ac9cc65ccac19a61273a893'),
    (0xD821F0,0xD82292,'9ee022dd8641f4e04c723b93a073692949463a1c81fe89166afdfd3cb12c4c51'),
    (0xD81C24,0xD81CFE,'96d5b15d60631adfc5a88ed05c92359acb0889bcb4d1498f99a3e895d96c1d4e'),
    (0xB058F8,0xB05964,'8dabcd4fef8db6075548f1ae418253af538cae350573c69d28dff3cd67cbecaf'),
    (0xB0597C,0xB05BC0,'20bcfc13415ab32f3f7903ca8cf69c04639d5592e4e9e914f787797ecb79d492'),
    (0xB1311C,0xB131B0,'1a33121c6790210e34b3d36f33edbec78a80de30f60a9372d114849651c0955a'),
    (0xB12074,0xB12638,'0c6adec25aedf38efd60f2e942387633e2ca6c655c5e1229ba3dad1b4aeb629e'),
    (0xEFE5E4,0xEFE698,'7fd7adc86e8f9ca89d66d0d96f2393d0d8ffadeaddeeda9427c9c724bb66627f'),
    (0xF30600,0xF30800,'076a27c79e5ace2a3d47f9dd2e83e4ff6ea8872b3c2218f66c92b89b55f36560'),
    (0xF31E00,0xF32000,'076a27c79e5ace2a3d47f9dd2e83e4ff6ea8872b3c2218f66c92b89b55f36560'),
    (0xF51000,0xF5108E,'b7f064b4bd27a3d68b5e66519cfac498d2e96da9bfd1bacf4110f4c7c98feca3'),
    (0xF51200,0xF51238,'d4817aa5497628e7c77e6b606107042bbba3130888c5f47a375e6179be789fbb'),
    (0xB12CB4,0xB12CBC,'e59327f2447230d90d40c745f143a639d331f8b00f099ee4473548143c07fef5'),
    (0xD81D30,0xD81D80,'ceb6d4c358669559163f04ece4218bbfbd11c577ef7f2af2d07191d05fa11355'),
    (0xF00000,0xF09F60,'78ffe35598baf1045eec3b22a6be97de66f5a7d365e163dfd595e2fe1394443b'),
    (0xF0A960,0xF24494,'945509ba632dcf2d4357da5ce4750284d18a0a3ed33edfc86087202a6b3b945a'),
)
