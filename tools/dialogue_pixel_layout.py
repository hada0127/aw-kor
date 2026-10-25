"""Native message inventory and final-ROM dialogue pixel layout.

Storage length is not display width. P1 B126F0 emits one 8px tile column
per pair; P2 314884 uses 315194's 1+7 pixel advance. Both resolve the
actual final glyph tiles here. Window profiles are deliberately distinct.
This module does not claim every inventoried message was played in context.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
import re

from dialogue_repoint import _read_table, scan_command_messages, is_sjis_lead
from renderer_text import renderer_for_address, P2_SCRIPT
from part2_mission_title_fit import is_pair_title

ROOT = Path(__file__).resolve().parents[1]
GBA = 0x08000000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Glyphs:
    """Resolve ROM font bytes, including patched native symbols and A3 nodes."""
    def __init__(self, rom):
        self.rom = rom
        start, end = (struct.unpack_from('<I', rom, a)[0]-GBA for a in (0xEFE970, 0xEFE974))
        if not 0 <= start < end <= len(rom) or (end-start) % 6:
            raise ValueError('invalid relocated glyph table')
        self.table = {int.from_bytes(rom[a:a+2], 'big'): struct.unpack_from('<HH', rom, a+2)
                      for a in range(start, end, 6)}
        self.codes = {int(v, 16): k for k, v in
                      json.loads((ROOT/'data/syllable_to_code_2350.json').read_text()).items()}

    def text(self, pair):
        code = int.from_bytes(pair, 'big')
        return self.codes.get(code) or pair.decode('shift_jis', 'replace')

    @lru_cache(maxsize=None)
    def bitmap(self, pair, game):
        code = int.from_bytes(pair, 'big')
        if game == 'p2' and code not in self.codes:
            pointer = struct.unpack_from('<I', self.rom, 0x807680+pair[1]*4)[0]
            seen = set()
            while pointer:
                node = pointer-GBA
                if node in seen or not 0 <= node <= len(self.rom)-72:
                    raise ValueError('invalid A3 glyph chain')
                seen.add(node)
                if self.rom[node+4] == pair[0]:
                    width = self.rom[node+5]
                    if width != 8:
                        raise ValueError(f'unsupported A3 advance {pair.hex()}: {width}')
                    raw = self.rom[node+6:node+70]
                    return tuple(tuple((raw[(y//8)*32+(y%8)*4+x//2] >> ((x%2)*4)) & 15
                                       for x in range(8)) for y in range(16))
                pointer = struct.unpack_from('<I', self.rom, node)[0]
            raise ValueError('missing A3 glyph '+pair.hex())
        if code > 0x8397:
            if code not in self.table:
                raise ValueError('missing P1/Hangul glyph '+pair.hex())
            slots = self.table[code]
        else:
            index = (((code-0x8140) & ~7)*2)+(code & 7)
            table = 0xB8027C
            if code > 0x823F:
                table = 0xB8057C; index -= 0x200
            if code > 0x833F:
                table = 0xB8087C; index -= 0x200
            slots = tuple(struct.unpack_from('<H', self.rom, table+(index+d)*2)[0] for d in (0,8))
        tiles = []
        for slot in slots:
            at = 0xF00000+(slot & 0x7FFF)*32 if slot & 0x8000 else 0xB974D0+slot*32
            raw = self.rom[at:at+32]
            if len(raw) != 32:
                raise ValueError('glyph tile out of bounds')
            tiles.extend(tuple((raw[y*4+x//2] >> ((x%2)*4)) & 15 for x in range(8)) for y in range(8))
        return tuple(tiles)


def tokenize(payload, game, glyphs=None):
    """Consume native operand widths; trailing padding is not a half glyph."""
    out = []; i = 0
    while i < len(payload):
        b = payload[i]; n = 1; kind = 'unknown'; text = f'<{b:02X}>'; width = 0
        if is_sjis_lead(b):
            if i+1 >= len(payload) or not (0x40 <= payload[i+1] <= 0xFC) or payload[i+1] == 0x7F:
                raise ValueError(f'invalid glyph pair at {i}')
            n = 2; kind = 'space' if payload[i:i+2] == b'\x81\x40' else 'glyph'
            text = glyphs.text(payload[i:i+2]) if glyphs else payload[i:i+2].hex()
            width = 8
        elif b == 0:
            kind = 'end'; text = ''
        elif b in (0x72, 0x52):
            kind = 'newline'; text = '\n'
        elif b in (0x6B, 0x4B, 0x70, 0x50):
            kind = 'page'; text = ''
        elif b == 0x20:
            width = 8 if game == 'p1' and i+1 < len(payload) and 0x81 <= payload[i+1] <= 0xE2 else 0
            kind = 'space' if width else 'padding'; text = ' ' if width else ''
        elif b in (9,10,13):
            kind = 'format'; text = ''
        elif b in (0x30,0x31,0x32,0x33):
            kind = 'style'; text = ''
        elif b in (0x77,0x57):
            kind = 'wait'; text = ''
        elif b in (0x51,0x48,0x71):
            kind = 'choice'; text = ''
            if i+1 < len(payload) and payload[i+1] in b'YNyn':
                n = 2
        elif b in (0x73,0x53):
            kind = 'speed'; text = ''
            if i+1 < len(payload) and payload[i+1] in b'0123456789_':
                n = 2
        elif b == 0x69 and game == 'p1':
            kind = 'name'; text = '<NAME>'; width = 48  # native six-pair input buffer
        elif (b in (0x4D,0x43) and game == 'p1') or (b in (0x6D,0x63) and game == 'p2'):
            if i+1 >= len(payload):
                raise ValueError('missing icon operand')
            kind = 'icon'; text = '<ICON:'+payload[i:i+2].hex()+'>'; width = 16; n = 2
        elif b == 0x3E and game == 'p1':
            kind = 'icon'; text = '<ARROW>'; width = 8
        out.append(dict(offset=i, raw=payload[i:i+n], kind=kind, text=text, advance=width))
        i += n
        if kind == 'end':
            break
    if not out or out[-1]['kind'] != 'end':
        raise ValueError('message has no bounded terminator')
    return out


def p1_consumers(original):
    """Native consumer sites, including messages not reached by opcode 19.

    Geometry evidence: docs/dialogue_layout.md. The source address is an
    identifier; geometry comes from its caller/table, not its address range.
    """
    entries={}
    def add(site, geometry, consumer):
        source=struct.unpack_from('<I',original,site)[0]-GBA
        if not 0 <= source < len(original):
            return
        entries.setdefault(source,[]).append(dict(site=site,profile=geometry,consumer=consumer))
    for opcode in (0x19,0x1A):
        for source,sites in scan_command_messages(original,hi=0x08E20000,opcode=opcode,scan_lo=0xD70000).items():
            for site in sites:
                add(site,('p1_portrait',176,2),f'opcode_{opcode:02X}')
    for lo,hi,geometry,consumer in (
        (0xDEF690,0xDEFB10,('p1_unit_help',112,4),'B3D314 unit help'),
        (0xDF5A9C,0xDF5AE8,('p1_info_panel',96,4),'B4631E terrain'),
        (0xD8D998,0xD8D9D8,('p1_link_notice',208,1),'B333FC link notice'),
        (0xDFAAB8,0xDFAB3C,('p1_menu_help',128,2),'B4AF08 menu help'),
        (0xD8C3DC,0xD8C3F0,('p1_portrait',176,2),'B28BF4 defeat'),
    ):
        for site in range(lo,hi,4):add(site,geometry,consumer)
    for lo,hi,geometry,consumer in (
        (0xB058E0,0xB058F8,('p1_editor_help',192,1),'B0584C editor left help'),
        (0xB05968,0xB0597C,('p1_editor_help',152,1),'B058F8 editor right help'),
        (0xB831E0,0xB831F4,('p1_link_status',64,1),'B33348 link status'),
    ):
        for site in range(lo,hi,4):add(site,geometry,consumer)
    add(0xB04C3C,('p1_editor_empty',72,1),'B04C2C/B04C98 editor empty label')
    for site in (0xD81A98,0xD81AB8,0xD81AD8,0xD81B18,0xD81B38,0xD81B58):
        add(site,('p1_menu_icon',80,1),'B1311C native MH icon row')
    for base in range(0xDF3B54,0xDF3CD4,0x20):
        add(base+0x0C,('p1_co_comment',120,4),'B42EF4 CO comment')
        for field,role in ((0x14,'ability'),(0x18,'break'),(0x1C,'bio')):
            add(base+field,('p1_co_'+role,112,6),'B411DC CO '+role)
    for root in range(0xDEBCC4,0xDEBD4C,4):
        record=struct.unpack_from('<I',original,root)[0]-GBA
        for _ in range(100):
            if not 0<=record<len(original)-8:raise ValueError('invalid CO quote record')
            if original[record+1]==0xFF:break
            add(record+4,('p1_portrait',176,2),'B3C634 quote')
            record+=8
        else:raise ValueError('unterminated quote records')
    for co in range(11):
        root=struct.unpack_from('<I',original,0xD863E8+co*0x124+0x20)[0]-GBA
        if 0<=root<len(original)-12:add(root+8,('p1_portrait',176,2),'B3C6D4 fallback quote')
    # B2EDC4 loads these four literals before B128A8. Sites are located by
    # their exact native literal words, and are checked again in the final ROM.
    for source in (0xDF2B9C,0xDF2BC0,0xDF2BDC,0xDF2C04):
        word=struct.pack('<I',source+GBA)
        for site in range(0xB2EDC4,0xB2EF00,4):
            if original[site:site+4]==word:add(site,('p1_animation_help',88,2),'B2ED18 animation help')
    for site in (0xB2F780,):add(site,('p1_portrait',176,2),'B2F778 production cap')
    # EC2708 index5 -> r6 -> B71204/B12910; non-opcode table consumer.
    add(0xEC2714,('p1_link_notice',208,1),'B711BE table index3 / B71204 instructions')
    add(0xEC271C,('p1_link_notice',208,1),'B711BE table index5 / B71204 instructions')
    for site in (0xB71218,0xB78568,*range(0xEC3E10,0xEC3E38,4)):
        add(site,('p1_link_notice',208,1),'B71204/B78554/B784D8 instructions')
    return entries


def profile(game, source, consumers=None):
    # 22 portrait cells are proven safe, with the final arrow outside the ink.
    if game == 'p1':
        found=(consumers or {}).get(source,[])
        specific=[e['profile'] for e in found if not e['consumer'].startswith('opcode_')]
        if specific:
            if len(set(specific))!=1:raise ValueError(f'ambiguous native consumer {source:#x}')
            return specific[0]
        if source == 0xDEFD80:
            return 'p1_narration', 192, 8
        return 'p1_portrait', 176, 2
    found=(consumers or {}).get(source,[])
    specific=[e['profile'] for e in found if e['profile'] is not None]
    if specific:
        distinct=set(specific)
        if any(p[0]=='p2_result_quote' for p in distinct):
            return ('p2_result_quote',104,2)  # common constraint of quote and portrait
        if any(p[0]=='p2_mission_brief' for p in distinct):
            return ('p2_mission_brief',168,2)
        if len({p[1:] for p in distinct})!=1:
            raise ValueError(f'ambiguous P2 native consumer {source:#x}: {distinct}')
        return next((e['profile'] for e in found if ' opcode' not in e['consumer']),specific[0])
    if source == 0xA01970:
        return 'p2_narration', 192, 4
    if source == 0xA28170:
        return 'p2_ending_scroll', 208, 5
    if 0xA29AB0 <= source < 0xA2A244:
        return 'p2_terrain_help', 112, 4
    if 0xA2A33C <= source < 0xA2C040:
        return 'p2_co_panel', 104, 6
    if 0xA31444 <= source < 0xA3408C:
        return 'p2_unit_help', 112, 4
    if 0xA2C040 <= source < 0xA2C5F0:
        return 'p2_scrolling_help', None, None
    if 0xA2C5F0 <= source < 0xA2C708:
        return 'p2_editor_help', 176, 3
    if source < 0xA024A0 or 0xA2D8B8 <= source < 0xA31444 or source >= 0xA3408C:
        return 'p2_unverified_consumer', None, None
    return 'p2_portrait', 176, 2


def p2_consumers(original):
    """ID-site provenance for the native master-table renderer families."""
    out={}
    def add(index,geometry,consumer,site=None):
        if not 0<=index<3315:raise ValueError('native P2 ID outside message table')
        pointer=0xA357B4+4*index
        source=struct.unpack_from('<I',original,pointer)[0]-GBA
        out.setdefault(source,[]).append(dict(site=pointer,id=index,id_site=site,
                                             profile=geometry,consumer=consumer))
    # Compiled opcode19 records are 16 bytes; 318A8C reads the ID at +8.
    # Retain all candidate record sites (including unused compiled scripts),
    # rather than asserting that every record is reached in normal play.
    for lo,hi in ((0x800000,0x840000),(0xA3A8E4,0xA3A8F4)):
        for site in range(lo,hi-15,4):
            op,variant,index,flags=struct.unpack_from('<IIII',original,site)
            if op in (0x19,0x1A) and variant<64 and index<3315 and flags==0:
                add(index,('p2_portrait',176,2),f'318A8C/318B50 opcode{op:02X}',site+8)
    for site in range(0x81A17C,0x81A17C+19*32,2):
        index=struct.unpack_from('<H',original,site)[0]
        if index:add(index,('p2_unit_help',112,4),'33ADB6 unit help',site)
    for terrain in range(1,32):
        site=0x9FDE84+20*terrain+14
        add(struct.unpack_from('<H',original,site)[0],('p2_terrain_help',96,4),'3473D0/34761C/347670 terrain',site)
    for site in (0x32D8A8,0x32D8B8,0x32D8C8,0x32D8D8):
        add(struct.unpack_from('<I',original,site)[0],('p2_animation_help',88,2),'32D82C animation help',site)
    for n in range(3):
        add(0x914+n,('p2_animation_menu',64,1),'31A44C/32D974 sized menu',0x816730+0x20*n)
    for lo,hi in ((0x8FCD58,0x8FCD78),(0x8FDFA0,0x8FDFB4)):
        for site in range(lo,hi,2):
            add(struct.unpack_from('<H',original,site)[0],('p2_instruction',208,1),'36797E/36EA82 instruction',site)
    for index in (0x9DB,0x9DE):add(index,('p2_instruction',208,1),'36797E/36EA82 fallback')
    for n in range(1,47):
        site=0x8FE64C+8*n
        add(struct.unpack_from('<H',original,site)[0],('p2_narrow_help',128,1),'36FAFC settled HOFS',site)
    for n in range(76):
        site=0xA3C074+2*n
        add(struct.unpack_from('<H',original,site)[0],('p2_co_panel',104,6),'385E72 CO body',site)
    for lo,hi in ((0xA3C10C,0xA3C11C),(0xA3C11C,0xA3C13C)):
        for site in range(lo,hi,2):
            index=struct.unpack_from('<H',original,site)[0]
            if index:add(index,('p2_scrolling_help',None,1),'385114 horizontal scroll',site)
    for n in range(42):
        site=0xA39F0C+0x30*n+0x10
        add(struct.unpack_from('<H',original,site)[0],('p2_mission_brief',168,2),'378254/377D5A mission briefing',site)
    add(0,('p2_narration',192,4),'38B048 prologue')
    add(0x873,('p2_ending_scroll',208,5),'36BDF0/36C0F8 ending',0x36BEB4)
    campaign=(0x7C,0xB1,0xF4,0x13F,0x182,0x1D5,0x207,*range(0x23A,0x23D),
              0x3A8,0x3DA,0x404,0x430,0x44E,0x46C,*range(0x481,0x484),*range(0x4C8,0x4CB),
              0x685,0x6B5,0x6D5,0x70A,0x72D,0x755,*range(0x772,0x775),*range(0x7B1,0x7B4),
              0x504,0x52F,0x56A,0x59A,0x5BB,0x5EF,*range(0x614,0x617),*range(0x654,0x657),
              *range(0x7F1,0x7FD),*range(0x895,0x8A1),0x263,0x27E,0x2AF,0x2C9,0x2F9,0x321,0x33F,
              *range(0x369,0x36C))
    if len(set(campaign))!=80:raise ValueError('quote selector union changed')
    for index in campaign:add(index,('p2_result_quote',104,2),'37B140 campaign selector')
    for co in range(19):
        site=0x9FC418+0x104*co+0x34
        add(struct.unpack_from('<H',original,site)[0],('p2_result_quote',104,2),'37B118 default quote',site)
        for field in range(0x20,0x2C,2):
            site=0x9FC418+0x104*co+field
            add(struct.unpack_from('<H',original,site)[0],('p2_portrait',176,2),
                '339E1C/339D40/319CD4 CO speech',site)
    for mission in range(42):
        root=struct.unpack_from('<I',original,0x819410+4*mission)[0]
        if not root:continue
        record=root-GBA
        for _ in range(100):
            if not 0<=record<len(original)-8:raise ValueError('invalid contextual CO speech record')
            if original[record+1]==0xFF:break
            add(struct.unpack_from('<H',original,record+4)[0],('p2_portrait',176,2),
                '339D9C/339DF4 conditional CO speech',record+4)
            record+=8
        else:raise ValueError('unterminated contextual CO speech records')
    for n in range(5):
        site=0x8159D4+2*n
        add(struct.unpack_from('<H',original,site)[0],('p2_portrait',176,2),'328A42 commander defeat',site)
    add(0xC9E,('p2_portrait',176,2),'32E030 production cap',0x32E038)
    for n in range(5):
        add(0xCA3+n,('p2_link_status',64,1),'33193C/3319CA coded clear; entry unverified',0x39138C+2*n)
    add(0xCA8,('p2_empty_map_header',80,1),'3331AC/332FC4 map-name header',0xA38A54)
    for n in range(19):
        site=0x816EC6+2*n
        index=struct.unpack_from('<H',original,site)[0]
        if n>=16:
            add(index,('p2_link_marquee',256,1),'333FDC/3343B6 + 38AD30 marquee; viewport 240',site)
        else:
            add(index,('p2_link_state_dependent',256,1),
                '331A80 backing only; transfer index8..11 visible192, other inherited offsets unverified',site)
    for n in range(5):
        site=0x5420D8+2*n
        add(struct.unpack_from('<H',original,site)[0],('p2_territory_label',72,1),'376A2C/376B08 territory panel',site)
    # These master-table entries have no attributed caller in the opcode,
    # result-selector or CO-reference inventories. Their story-pool address
    # alone does not prove a portrait window. Do not invent its dimensions.
    for index in (0x337,0x368,0x4C7,0x4CB,0x4CC,0x7AD,0x7AF,0x7B0):
        add(index,('p2_unverified_consumer',None,None),'master-table entry only; caller unverified')
    return out


def inventory(original, rom, manifest):
    """Reference-based denominator; aliases are separate from physical messages."""
    consumers=p1_consumers(original)
    p2=p2_consumers(original)
    refs={source:[e['site'] for e in entries] for source,entries in consumers.items()}
    relocated_by_source={int(m['msg'],16):m for m in manifest if m.get('status')=='relocated'}
    for m in manifest:
        source = int(m['msg'],16)
        if m.get('status') == 'relocated' and (0xD80000 <= source < 0xE20000 or 0xB80000 <= source < 0xB85000):
            refs.setdefault(source, []).extend(int(x,16) for x in m['ptr_sites'])
    output = []
    for game, entries in [('p1', [(source, sorted(set(sites))) for source,sites in refs.items()]),
                          ('p2', [(source,[pointer]) for pointer,source in _read_table(original,0xA357B4)])]:
        for source, sites in sorted(entries):
            target = struct.unpack_from('<I',rom,sites[0])[0]-GBA
            if any(struct.unpack_from('<I',rom,p)[0]-GBA != target for p in sites):
                raise ValueError(f'divergent message aliases {source:#x}')
            if not 0 <= target < len(rom):
                raise ValueError('message pointer outside ROM')
            relocated = relocated_by_source.get(source)
            end = target+relocated['new_len'] if relocated else rom.find(b'\0',target)+1
            if not target < end <= len(rom):
                raise ValueError('unbounded message')
            selected=consumers if game=='p1' else p2
            is_script = game == 'p1' or renderer_for_address(source) == P2_SCRIPT or source in p2
            output.append(dict(game=game,source=source,sites=sites,target=target,payload=bytes(rom[target:end]),
                               script=is_script,profile=profile(game,source,selected),relocated=relocated,
                               consumers=selected.get(source,[]),
                               pair_title=game=='p2' and is_pair_title(source)))
    return output


def physical_rows(tokens):
    rows=[]; page=0; line=0; current=[]
    for t in tokens:
        if t['kind'] in ('newline','page','end'):
            if (any(x['advance'] or x['kind']=='choice' for x in current)
                    or t['kind']=='newline' or t['raw'] in (b'k',b'K')):
                rows.append(dict(page=page,line=line,tokens=current,end=t))
            current=[]
            if t['kind']=='newline':
                line+=1
            else:
                page+=1; line=0
        else:
            current.append(t)
    return rows


def audit(original, rom, manifest):
    glyphs=Glyphs(rom); messages=inventory(original,rom,manifest)
    prologue_native=original[0xA01970:original.find(b'\0',0xA01970)+1]
    prologue_envelopes={(r['page'],r['line']):sum(t['advance'] for t in r['tokens'])
                        for r in physical_rows(tokenize(prologue_native,'p2'))}
    rows=[]; errors=[]; excluded=[]; glyph_errors={}; seen_glyphs=set()
    for m in messages:
        if not m['script']:
            excluded.append(dict(source=hex(m['source']),reason='pair title/UI label; separate consumer, not a script dialogue'))
            continue
        try:
            tokens=tokenize(m['payload'],m['game'],glyphs)
        except ValueError as exc:
            errors.append(dict(source=hex(m['source']),error=str(exc)));continue
        unknown=[t for t in tokens if t['kind']=='unknown']
        if unknown:
            errors.append(dict(source=hex(m['source']),unknown=[(t['offset'],t['raw'].hex()) for t in unknown]))
        name,limit,max_rows=m['profile']
        for row in physical_rows(tokens):
            row_limit = limit
            if m['game']=='p2' and m['source']==0xA01970:
                # All four shipped rows remain inside the original tile-write
                # envelopes, including its animated foreground reservation.
                row_limit=prologue_envelopes.get((row['page'],row['line']),0)
            if name in ('p1_portrait','p2_portrait') and row['line'] == 0 and row['end']['kind'] == 'newline':
                row_limit += 8  # next tile is on the following row; no wait arrow here
            if name=='p2_result_quote' and row['end']['raw'] in (b'k',b'K'):
                row_limit-=8
            advance=0; ink_end=0; row_glyph_errors=[]
            choices=[t for t in row['tokens'] if t['kind']=='choice']
            for t in row['tokens']:
                if t['kind'] in ('glyph','space') and len(t['raw'])==2:
                    pair=t['raw'];seen_glyphs.add((m['game'],pair.hex()))
                    try:
                        bitmap=glyphs.bitmap(pair,m['game'])
                        xs=[x for y in bitmap for x,v in enumerate(y) if v]
                        if xs:ink_end=max(ink_end,advance+max(xs)+1)
                    except ValueError as exc:
                        glyph_errors[(m['game'],pair.hex())]=str(exc);row_glyph_errors.append(str(exc))
                elif t['kind'] in ('name','icon'):
                    ink_end=max(ink_end,advance+t['advance'])
                advance+=t['advance']
            # Q/H/q have an eight-cell native cursor/choice reservation. The
            # Korean wide-row hook's glyphs occupy cells 1,5,6 in that span.
            # The command may also start the separate modal choice task after
            # a surrender question; retain its actual token offset explicitly.
            reservation=64 if choices else 0
            choice_end=advance+reservation
            caption=0
            if name=='p1_co_bio' and row['line'] in (2,3):caption=40
            if name=='p1_co_break' and row['line']==0:caption=24
            leading=0
            for t in row['tokens']:
                if t['kind']=='space':leading+=t['advance']
                elif t['advance']:break
            rows.append(dict(game=m['game'],source=hex(m['source']),target=hex(m['target']),profile=name,
                             page=row['page'],line=row['line'],text=''.join(t['text'] for t in row['tokens']),
                             advance_px=advance,ink_right_px=ink_end,limit_px=row_limit,max_rows=max_rows,
                             choice_reservation_px=reservation,choice_offsets=[t['offset'] for t in choices],
                             choice_end_px=choice_end,
                             caption_reservation_px=caption,caption_overlap=leading<caption,
                             overflow=row_limit is not None and max(advance,ink_end,choice_end)>row_limit,
                             row_overflow=max_rows is not None and row['line']>=max_rows,
                             glyph_errors=row_glyph_errors))
    return dict(summary=dict(native_references=sum(len(m['sites']) for m in messages),
                             physical_messages=len(messages),script_messages=sum(m['script'] for m in messages),
                             excluded_pair_ui_messages=len(excluded),physical_rows=len(rows),
                             profiles=dict(Counter(r['profile'] for r in rows)),glyph_codes=len(seen_glyphs),
                             overflows=sum(r['overflow'] for r in rows),row_overflows=sum(r['row_overflow'] for r in rows),
                             parser_errors=len(errors),glyph_errors=len(glyph_errors),
                             choice_rows=sum(bool(r['choice_reservation_px']) for r in rows),
                             caption_overlaps=sum(r['caption_overlap'] for r in rows),
                             unverified_consumer_messages=sum(m['script'] and m['profile'][0]=='p2_unverified_consumer' for m in messages),
                             state_dependent_messages=sum(m['script'] and m['profile'][0]=='p2_link_state_dependent' for m in messages),
                             runtime_claim='static native reference/font audit; contextual playback recorded separately'),
                rows=rows,errors=errors,glyph_errors=[dict(game=k[0],code=k[1],error=v) for k,v in glyph_errors.items()],
                excluded=excluded,rom_sha256=sha(rom),original_sha256=sha(original))


def _source_signature(raw, game):
    """Compare one logical owner's glyphs and advancing word separators."""
    tokens=tokenize(raw+b'\0',game)
    result=[]
    for t in tokens:
        if t['kind'] in ('glyph','space'):
            result.append(b'\x81\x40' if t['kind']=='space' else t['raw'])
        elif t['kind']=='newline':
            result.append(b'\x81\x40')
        elif t['kind'] not in ('format','padding','end'):
            result.append(t['raw'])
    while result and result[0]==b'\x81\x40':result.pop(0)
    while result and result[-1]==b'\x81\x40':result.pop()
    return b''.join(result)


def reflow_message(payload, game, glyphs, changes, max_rows, owner_spans=None, *, allow_paging=False, allow_spacing_changes=False, allow_growth=False, allow_blank_rows=False):
    """Apply reviewed row strings, preserving glyph and non-layout controls.

    Invisible wait/style/icon/name instructions keep their original position
    between visible glyphs. Only authored spaces/row controls are exchanged.
    Existing source ownership follows every moved glyph for downstream QA.
    """
    tokens=tokenize(payload,game,glyphs)
    if any(t['kind']=='unknown' for t in tokens):
        raise ValueError('cannot reflow unknown native instruction')
    for t in tokens:
        t['owner']=None
        for key,parts in (owner_spans or {}).items():
            for off,size in parts:
                if off <= t['offset'] < off+size:
                    if t['offset']+len(t['raw'])>off+size:
                        raise ValueError('source owner cuts a native token')
                    if t['owner'] not in (None,key):
                        raise ValueError('source owners overlap')
                    t['owner']=key
    pages=[];current=[]
    for t in tokens:
        current.append(t)
        if t['kind'] in ('page','end'):
            pages.append(current);current=[]
    change_by_page={p['page']:p for p in changes}
    if len(change_by_page)!=len(changes) or any(p>=len(pages) for p in change_by_page):
        raise ValueError('invalid/duplicate repair page')
    emitted=[]
    for page,ts in enumerate(pages):
        if page not in change_by_page:
            emitted.extend(ts);continue
        spec=change_by_page[page]
        before=[''.join(t['text'] for t in r['tokens']) for r in physical_rows(ts)]
        if before!=spec['before']:
            raise ValueError(f'reviewed before rows changed: page {page}')
        after=spec['after']
        if not after or any(not isinstance(s,str) or (not s and not allow_blank_rows) for s in after):
            raise ValueError('empty repair rows')
        visible=[];spaces={};controls={};ordered={};old_breaks=set();index=0
        header_formats=set()
        for t in ts:
            if t['kind']!='format':break
            header_formats.add(id(t))
        for t in ts[:-1]:
            if t['advance'] and t['kind']!='space':
                visible.append(t);index+=1
            elif t['kind']=='space':
                spaces.setdefault(index,[]).append(t)
                ordered.setdefault(index,[]).append(t)
            elif t['kind']=='newline':
                old_breaks.add(index)
            elif (t['kind'] not in ('format','padding') or
                  allow_spacing_changes and t['kind']=='format' and id(t) not in header_formats):
                controls.setdefault(index,[]).append(t)
                ordered.setdefault(index,[]).append(t)
        layout={};breaks={};events={};index=0
        for row,text in enumerate(after):
            for unit in re.findall(r'<[^>]+>|.',text):
                if unit in (' ','　'):
                    layout[index]=layout.get(index,0)+1
                    events.setdefault(index,[]).append('space')
                else:
                    if index>=len(visible) or visible[index]['text']!=unit:
                        raise ValueError(f'reflow changed wording at glyph {index}: {unit!r}')
                    index+=1
            if row+1<len(after):
                breaks[index]='page' if max_rows and (row+1)%max_rows==0 else 'newline'
                events.setdefault(index,[]).append(breaks[index])
        if index!=len(visible):
            raise ValueError('reflow dropped final glyphs')
        for at,old in spaces.items():
            if (not allow_spacing_changes and layout.get(at,0)!=len(old)
                    and at not in breaks and at not in (0,len(visible))):
                raise ValueError(f'reflow changed an authored interior separator at glyph {at}')
        # A yes/no row occupies a physical row even though it has no text pair.
        tail_choice=any(t['kind']=='choice' for t in controls.get(len(visible),[]))
        if tail_choice and len(visible) in old_breaks:
            if max_rows and len(after)>=max_rows:
                raise ValueError('reflow would push the choice below its window')
            breaks[len(visible)]='newline'
            events.setdefault(len(visible),[]).append('newline')
        if max_rows and not allow_paging and len(after)>max_rows:
            raise ValueError('panel reflow exceeds visible rows; paging is not established')
        # Header formatting is native non-advancing data, not a display row.
        for t in ts:
            if t['kind']=='format':emitted.append(t)
            else:break
        for at in range(len(visible)+1):
            old=spaces.get(at,[])
            controls_by_space=[];ordinal=0
            for t in ordered.get(at,[]):
                if t['kind']=='space':ordinal+=1
                else:controls_by_space.append((ordinal,t))
            deferred=[]
            if allow_spacing_changes and at==len(visible) and tail_choice and at in old_breaks:
                choice_index=next(i for i,(_,t) in enumerate(controls_by_space) if t['kind']=='choice')
                deferred=controls_by_space[choice_index:]
                controls_by_space=controls_by_space[:choice_index]
            consumed=0;control=0
            for event in events.get(at,[]):
                while control<len(controls_by_space) and controls_by_space[control][0]<=consumed:
                    emitted.append(controls_by_space[control][1]);control+=1
                if event=='space':
                    owner=old[consumed]['owner'] if consumed<len(old) else None
                    if owner is None and 0<at<len(visible) and visible[at-1]['owner']==visible[at]['owner']:
                        owner=visible[at]['owner']
                    emitted.append(dict(raw=b'\x81\x40',kind='space',owner=owner));consumed+=1
                else:
                    emitted.append(dict(raw=b'\x6b' if event=='page' else b'\x72',kind=event,owner=None))
            emitted.extend(t for _,t in controls_by_space[control:])
            emitted.extend(t for _,t in deferred)
            if at<len(visible):emitted.append(visible[at])
        emitted.append(ts[-1])
    if allow_spacing_changes and owner_spans:
        # Legacy manifests include authored rows whose entire current payload
        # is non-drawing padding (the historical missing wording stays visible
        # as unsupported to owner QA). Keep these source keys alive as terminal
        # padding rather than deleting their provenance or inventing prose.
        alive={t['owner'] for t in emitted}
        carried=[]
        for key in owner_spans:
            if key in alive:continue
            owned=[t for t in tokens if t['owner']==key]
            if not owned or any(t['kind'] not in ('padding','space','format','newline') for t in owned):
                raise ValueError('cannot retire a non-layout source owner')
            carried.append(dict(raw=b' '*sum(len(t['raw']) for t in owned),kind='padding',owner=key))
        if carried:
            terminal=emitted.pop()
            if terminal['kind']!='end':raise ValueError('missing terminal for provenance padding')
            emitted.extend(carried);emitted.append(terminal)
    # Reclaim only non-drawing padding. Keep the pointer allocation and bound.
    native_tail=payload[tokens[-1]['offset']+1:]
    raw=b''.join(t['raw'] for t in emitted)+native_tail
    if len(raw)>len(payload) and not allow_growth:
        raise ValueError(f'reflow needs {len(raw)-len(payload)} extra bytes')
    padding=max(0,len(payload)-len(raw))
    if padding:
        terminal=emitted.pop()
        if terminal['kind']!='end':raise ValueError('missing reflow end')
        emitted.extend([dict(raw=b' '*padding,kind='padding',owner=None),terminal])
    raw=b''.join(t['raw'] for t in emitted)+native_tail
    # All waits, styles, dynamic names, icons, speed and choices stay ordered.
    layout_kinds=('glyph','space','padding','newline','page','end')+(() if allow_spacing_changes else ('format',))
    protected=lambda ts:[t['raw'] for t in ts if t['kind'] not in layout_kinds]
    def anchored(ts):
        index=0; result=[]
        for t in ts:
            if t['advance'] and t['kind']!='space':index+=1
            if t['kind'] not in layout_kinds:
                result.append((index,t['raw']))
        return result
    if protected(tokens)!=protected(tokenize(raw,game,glyphs)) or anchored(tokens)!=anchored(tokenize(raw,game,glyphs)):
        raise ValueError('reflow changed non-layout native instructions')
    parts={key:[] for key in (owner_spans or {})};offset=0
    for t in emitted:
        key=t['owner'];size=len(t['raw'])
        if key is not None:
            ranges=parts[key]
            if ranges and sum(ranges[-1])==offset:ranges[-1][1]+=size
            else:ranges.append([offset,size])
        offset+=size
    return raw,parts


def apply_repairs(rom, original, manifest, writes, repairs):
    """Build-time, source-bound layout operations; no font or renderer changes."""
    from repoint_source_rows import fragments,row_bytes
    glyphs=Glyphs(bytes(rom));by_source={m['source']:m for m in inventory(original,rom,manifest)}
    report=[];seen=set()
    for spec in repairs:
        source=int(spec['source'],16)
        if source in seen:raise ValueError('duplicate repair message')
        seen.add(source)
        m=by_source[source];before=m['payload']
        if sha(before)!=spec['before_sha256'] or m['profile'][0]!=spec['profile']:
            raise ValueError(f'repair input changed: {source:#x}')
        record=m['relocated']
        owners={key:fragments(record,key) for key in record['line_spans']} if record else {}
        old_rows={key:row_bytes(rom,record,key) for key in owners}
        after,parts=reflow_message(before,m['game'],glyphs,spec['pages'],spec['rows_per_page'],owners,
                                  allow_paging=m['profile'][0] in ('p1_portrait','p2_portrait'))
        if len(after)!=len(before):raise ValueError('layout allocation changed')
        target=m['target'];rom[target:target+len(after)]=after
        if record:
            if any(not p for p in parts.values()):raise ValueError('reflow erased source ownership')
            record['source_line_fragments']=parts
            record['line_spans']={key:value[0] for key,value in parts.items()}
            joins={}
            for key,ranges in parts.items():
                expected=_source_signature(old_rows[key],m['game']);cursor=0;separators=[]
                for i,(off,size) in enumerate(ranges):
                    piece=_source_signature(after[off:off+size],m['game'])
                    if expected[cursor:cursor+len(piece)]==piece:separator=b''
                    elif i and expected[cursor:cursor+len(piece)+2]==b'\x81\x40'+piece:separator=b'\x81\x40'
                    else:raise ValueError(f'fragment changes logical source {key}')
                    if i:separators.append(separator.hex())
                    cursor+=len(separator)+len(piece)
                if cursor!=len(expected):raise ValueError(f'fragment drops logical source {key}')
                joins[key]=separators
            record['source_fragment_joiners']=joins
            for key,old in old_rows.items():
                if _source_signature(old,m['game'])!=_source_signature(row_bytes(rom,record,key),m['game']):
                    raise ValueError(f'reflow changed logical source {key}')
        writes.append([target,len(after),len(after),after.hex(),None,None,None,'dialogue-pixel-layout'])
        if record is None and m['profile'][0]=='p1_co_break':
            # These native title slots already include the three caption cells.
            # Keep a complete final source writer: older records describe only
            # the unindented Korean title and would otherwise read a prefix plus
            # a truncated title after the reservation is restored.
            source_row=source+2
            owner=next((w for w in reversed(writes[:-1]) if w[0]==source_row and w[5]),None)
            if owner is None:raise ValueError('missing native CO title owner')
            first=physical_rows(tokenize(after,m['game'],glyphs))[0]
            title=after[2:first['end']['offset']]
            if (len(title)>owner[1] or
                    _source_signature(title,m['game'])!=_source_signature(before[2:2+len(bytes.fromhex(owner[3]))],m['game'])):
                raise ValueError('CO title no longer fits its original source slot')
            writes.append([source_row,len(title),len(title),title.hex(),None,owner[5],owner[6],
                           'dialogue-pixel-layout-source'])
        report.append(dict(source=spec['source'],target=hex(target),before_sha256=sha(before),
                           after_sha256=sha(after),pages=spec['pages'],source_fragments=parts))
    return report
