"""Individually reviewed, final-stage spacing changes after the b41 reflow.

The ledger is an exact input/output contract, never an inferred translation.
Original authored wording survives wherever it differs from the shipped text.
"""
from __future__ import annotations
import copy
import json
import re
import struct
from pathlib import Path
from functools import lru_cache

from dialogue_pixel_layout import Glyphs, inventory, tokenize, physical_rows, reflow_message, sha
from repoint_source_rows import fragments, row_bytes

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/dialogue_spacing_repairs.json'
ARENA_START, ARENA_END = 0xA3D000, 0xAFF000
GBA = 0x08000000


def load_ledger():
    data=json.loads(LEDGER.read_text())
    if data.get('schema')!=1:raise ValueError('unsupported spacing ledger schema')
    seen=set()
    for row in data.get('bteam',[]):
        address=int(row['address'],16)
        if address in seen:raise ValueError('duplicate protected spacing address')
        seen.add(address)
        if ''.join(row['before'].split())!=''.join(row['after'].split()):
            raise ValueError('protected spacing ledger changes wording')
        if row['classification'] not in ('restored','retained-residual'):
            raise ValueError('unknown protected spacing disposition')
    return data


@lru_cache(maxsize=1)
def reviewed_bteam_rows():
    # Optional for tools that inspect a historical ROM in a checkout predating
    # the ledger. The product stage itself requires load_ledger() to succeed.
    if not LEDGER.exists():return {}
    return {int(r['address'],16):r for r in load_ledger().get('bteam',[])}


def reviewed_bteam_match(address, expected, actual, *, restored):
    row=reviewed_bteam_rows().get(address)
    if row is None or actual!=row['after']:return False
    if restored:
        return row['classification']=='restored' and expected==row['baseline']
    return (row['classification']=='retained-residual'
            and expected in row['retained_authorities'])


def has_reviewed_source(source):
    return any(int(row['source'],16)==source for row in load_ledger()['messages'])


def reviewed_message_pin(rom, message, old_hex):
    """Accept only the reviewed before/after pair; historical pins stay intact."""
    source=int(message['msg'],16)
    spec=next((r for r in load_ledger()['messages'] if int(r['source'],16)==source),None)
    if spec is None:return False
    if old_hex:
        if sha(bytes.fromhex(old_hex))!=spec['before_sha256']:return False
    else:
        size=spec['before_bytes']
        if (int(spec['before_target'],16)!=source or message['old_len']!=size
                or sha(bytes(rom[source:source+size]))!=spec['before_sha256']):return False
    target=int(message['new_addr'],16);size=message['new_len']
    return (target>=0 and size>0 and target+size<=len(rom)
            and sha(bytes(rom[target:target+size]))==spec['after_sha256'])


def verify_reviewed_owner_bytes(rom, message, address):
    row=reviewed_bteam_rows().get(address)
    if row is None:return False
    key=f'0x{address:06X}'
    parts=fragments(message,key)
    wanted=row['final_fragment_hex']
    if parts is None or len(parts)!=len(wanted):
        raise ValueError('reviewed protected fragment count changed')
    target=int(message['new_addr'],16)
    if any(bytes(rom[target+off:target+off+size]).hex()!=raw for (off,size),raw in zip(parts,wanted)):
        raise ValueError('reviewed protected final bytes changed')
    return True


def reviewed_bteam_half_cells(address, payload=None):
    """One extra first-row tile, only for exact reviewed portrait fragments.

    The final native pixel audit independently checks the row, arrow and
    choice reserves. This is not a general increase of the legacy 44-cell cap.
    """
    row=reviewed_bteam_rows().get(address)
    if row is None or row.get('profile') not in ('p1_portrait','p2_portrait'):return 0
    widths=row.get('final_fragment_half_cells',[])
    if not widths or max(widths)>46:return 0
    if payload is not None:
        raw=payload.hex()
        if raw not in row['final_fragment_hex']:return 0
        return widths[row['final_fragment_hex'].index(raw)]
    return max(widths)


def _visible(raw, game, glyphs):
    return [(t['raw'], t['kind']) for t in tokenize(raw, game, glyphs)
            if t['advance'] and t['kind'] != 'space']


def monotone_reflow(payload,game,glyphs,changes,owner_spans):
    """Consumer-unknown exception: delete reviewed fullwidth spaces only.

    Keep every original row, glyph, instruction and padding byte in order.
    No row can grow, no font/window width is assumed, and no new padding is
    manufactured. The guarded relocation path still validates all pointers.
    """
    tokens=tokenize(payload,game,glyphs)
    if any(t['kind'] in ('unknown','choice','name','icon') for t in tokens):
        raise ValueError('monotone spacing requires fixed glyphs and understood instructions')
    pages={}
    for row in physical_rows(tokens):pages.setdefault(row['page'],[]).append(row)
    remove=set();seen=set()
    for spec in changes:
        page=spec['page']
        if page in seen or page not in pages:raise ValueError('invalid monotone repair page')
        seen.add(page);rows=pages[page]
        before=[''.join(t['text'] for t in r['tokens']) for r in rows]
        if before!=spec['before'] or len(rows)!=len(spec['after']):
            raise ValueError('monotone spacing must preserve original rows')
        for row,text in zip(rows,spec['after']):
            visible=[t['text'] for t in row['tokens'] if t['advance'] and t['kind']!='space']
            wanted={};index=0
            for unit in re.findall(r'<[^>]+>|.',text):
                if unit in (' ','　'):wanted[index]=wanted.get(index,0)+1
                else:
                    if index>=len(visible) or visible[index]!=unit:raise ValueError('monotone spacing changed row wording')
                    index+=1
            if index!=len(visible):raise ValueError('monotone spacing lost row glyphs')
            present={};index=0
            for t in row['tokens']:
                if t['kind']=='space':present.setdefault(index,[]).append(t)
                elif t['advance']:index+=1
            if any(n>len(present.get(at,[])) for at,n in wanted.items()):
                raise ValueError('monotone spacing cannot add a separator')
            for at,old in present.items():
                for t in old[wanted.get(at,0):]:
                    if t['raw']!=b'\x81\x40':raise ValueError('monotone removal is not a fullwidth space')
                    remove.add(t['offset'])
    parts={key:[] for key in owner_spans};result=bytearray()
    for t in tokens:
        if t['offset'] in remove:continue
        matched=[]
        for key,ps in owner_spans.items():
            for off,size in ps:
                if off<=t['offset']<off+size:
                    if t['offset']+len(t['raw'])>off+size:raise ValueError('monotone source cuts token')
                    matched.append(key)
        if len(matched)>1:raise ValueError('monotone source owners overlap')
        if matched:
            ranges=parts[matched[0]]
            if ranges and sum(ranges[-1])==len(result):ranges[-1][1]+=len(t['raw'])
            else:ranges.append([len(result),len(t['raw'])])
        result.extend(t['raw'])
    result.extend(payload[tokens[-1]['offset']+1:])
    return bytes(result),parts


def _owner_text(raw, game, glyphs):
    return ''.join(t['text'] if t['kind'] != 'newline' else ' '
                   for t in tokenize(raw+b'\0', game, glyphs)).replace('　', ' ').strip()


def _spacing_intent(authored, before, after):
    """Whitespace delta with one-to-one renderer punctuation comparison only.

    Historical characters remain literal; no wording or terminology fold can
    make a different authored sentence eligible for replacement.
    """
    strip = lambda s: ''.join(s.split())
    fold=str.maketrans({'！':'!','？':'?','。':'.','、':',','，':',','．':'.','・':'.',
                       '”':'"','“':'"'})
    if not authored:return authored,False
    original=strip(authored)
    if original.translate(fold) != strip(before).translate(fold):
        return authored, False
    if strip(before) != strip(after):
        raise ValueError('spacing changed owner wording')
    result=[];index=0;space=False
    for ch in after:
        if ch.isspace():space=bool(result)
        else:
            if space:result.append(' ');space=False
            result.append(original[index]);index+=1
    if index!=len(original):raise ValueError('authored punctuation width changed')
    return ''.join(result), True


def _pointer_hits(original, sources):
    result = {s: set() for s in sources}
    for i, (value,) in enumerate(struct.iter_unpack('<I', original)):
        if value-GBA in result:
            result[value-GBA].add(i*4)
    return result


def guard_new_relocation(message, original, rom, hits, referenced_entries, end):
    """Original start references and interior native entries must be complete."""
    source = message['source']
    sites = set(message['sites'])
    if hits[source] != sites or not sites:
        raise ValueError(f'unclassified original start-pointer sites {source:#x}: {sorted(hits[source]-sites)} / missing {sorted(sites-hits[source])}')
    if any(struct.unpack_from('<I', rom, s)[0] != GBA+source for s in sites):
        raise ValueError('new relocation has changed live pointer')
    if not source < end <= len(original) or 0 not in original[source:end]:
        raise ValueError('unbounded original message')
    if any(source<=site<end for site in sites):
        raise ValueError('message contains its own pointer site')
    # Same entry-target policy as ordinary repoint_messages. Pointer-shaped
    # graphics bytes are not evidence of a native interior entry by themselves.
    for target in referenced_entries:
        if source < target < end:
            raise ValueError(f'referenced interior entry {target:#x} in {source:#x}')


def _nonrelocated_owners(m, rom, final_owners, writes=None, original=None):
    if writes is not None:
        return _native_provenance(m,rom,writes,original)
    start, end = m['target'], m['target']+len(m['payload'])
    owners, texts, source_spans = {}, {}, {}
    for address, entry in final_owners.items():
        if address >= end or address+entry[1] <= start:
            continue
        if address < start or address+entry[1] > end:
            # Slot padding may extend past the bounded terminator, but no
            # visible glyph, instruction or neighboring row may be clipped.
            if address < start or any(c not in (0, 32) for c in rom[end:address+entry[1]]):
                raise ValueError(f'partial native owner {address:#x}')
        size = min(entry[1], end-address)
        key = f'0x{address:06X}'
        owners[key] = [[address-start, size]]
        source_spans[key] = size
        texts[key] = entry[5]
    if not owners:
        raise ValueError('no complete final authored owners')
    covered = set()
    for parts in owners.values():
        for off, size in parts:
            covered.update(range(off, off+size))
    # Every visible token needs a final owner. Unowned controls remain native.
    for t in tokenize(m['payload'], m['game'], Glyphs(bytes(rom))):
        if t['advance'] and t['kind'] != 'space' and t['offset'] not in covered:
            raise ValueError(f'unowned visible token +{t["offset"]:#x}')
    return owners, texts, source_spans


def _native_provenance(m, rom, writes, original):
    """Recover bounded byte owners, including b41's anonymous final reflows.

    An anonymous legacy/native fragment is explicitly unsupported (empty intent),
    rather than borrowed prose from a partially superseded historical writer.
    Individual protected interior rows keep their own addresses and intent.
    """
    start=m['target'];size=len(m['payload']);end=start+size
    stage=next((i for i,w in enumerate(writes) if w[0]==start and w[7]=='dialogue-pixel-layout'),None)
    relevant=writes if stage is None else writes[:stage]
    local=bytearray(original[start:end]);labels=[None]*size
    for i,w in enumerate(relevant):
        lo=max(start,w[0]);hi=min(end,w[0]+w[1])
        if lo>=hi or not w[3]:continue
        raw=bytes.fromhex(w[3])
        if len(raw)>w[1]:raise ValueError('native writer exceeds slot')
        if len(raw)<w[1]:
            if w[4] is None:raise ValueError('native writer has unknown fill')
            from qa_integrity_map import fill_pattern
            pattern=fill_pattern(w[4]);missing=w[1]-len(raw)
            raw+=bytes(pattern[i%len(pattern)] for i in range(missing))
        local[lo-start:hi-start]=raw[lo-w[0]:hi-w[0]]
        labels[lo-start:hi-start]=[i]*(hi-lo)
    if stage is None and bytes(local)!=m['payload']:
        for off,(old,new) in enumerate(zip(local,m['payload'])):
            if old==new:continue
            if labels[off] is not None:
                raise ValueError('native recorded writer differs from current bytes')
            # Legacy builder replacements without WRITE_LOG evidence remain
            # anonymous/unsupported. Never attribute them to Japanese input.
            local[off]=new
    glyphs=Glyphs(bytes(rom));tokens=tokenize(bytes(local),m['game'],glyphs)
    groups=[]
    for t in tokens:
        lo=t['offset'];hi=lo+len(t['raw']);ids=set(labels[lo:hi])
        if len(ids)!=1:raise ValueError('native winning writer splits token')
        label=ids.pop()
        if groups and groups[-1][2]==label and groups[-1][1]==lo:
            groups[-1][1]=hi
        else:groups.append([lo,hi,label])
    owners={};texts={};spans={}
    for lo,hi,label in groups:
        if all(t['kind'] in ('padding','format','newline','space') for t in tokens if lo<=t['offset']<hi):
            continue
        key=f'0x{start+lo:06X}';owners[key]=[[lo,hi-lo]];spans[key]=hi-lo
        entry=relevant[label] if label is not None else None
        complete=(entry is not None and entry[0]==start+lo and entry[1]==hi-lo)
        texts[key]=entry[5] if complete and entry[5] else ''
    if stage is not None:
        specs=json.loads((ROOT/'data/dialogue_layout_repairs.json').read_text())
        spec=next(s for s in specs if int(s['source'],16)==m['source'])
        if sha(bytes(local))!=spec['before_sha256']:
            raise ValueError('cannot reconstruct pre-b41 native provenance')
        raw,parts=reflow_message(bytes(local),m['game'],glyphs,spec['pages'],spec['rows_per_page'],owners,
                                allow_paging=m['profile'][0] in ('p1_portrait','p2_portrait'))
        if raw!=m['payload']:raise ValueError('b41 provenance replay differs')
        owners=parts
    return owners,texts,spans


def apply_repairs(rom, original, manifest, writes, ledger=None):
    """Validate the complete batch before mutating its ROM or shared metadata."""
    from qa_dialogue_jamming import final_owner_spans
    from dialogue_repoint import _line_index
    ledger = load_ledger() if ledger is None else ledger
    glyphs = Glyphs(bytes(rom))
    messages = {m['source']: m for m in inventory(original, rom, manifest)}
    final_owners, _ = final_owner_spans(writes, len(rom), hangul_only=False)
    sources = {int(s['source'], 16) for s in ledger['messages']}
    if len(sources) != len(ledger['messages']):
        raise ValueError('duplicate spacing source')
    hits = _pointer_hits(original, sources)
    entries = set(_line_index(ROOT/'data/game_wars_found_texts.csv')) | set(messages)
    referenced_entries={v-GBA for v, in struct.iter_unpack('<I',original) if v-GBA in entries}
    high = max([ARENA_START]+[int(m['new_addr'],16)+m['new_len']
                           for m in manifest if m.get('status') == 'relocated'])
    free = (high+3)&~3
    pending = []
    for spec in ledger['messages']:
        source = int(spec['source'],16)
        m = messages[source]
        if (not m['script'] or m['profile'][0] != spec['profile']
                or sha(m['payload']) != spec['before_sha256']):
            raise ValueError(f'stale spacing specification {source:#x}')
        profile, width, max_rows = m['profile']
        monotone=spec.get('mode')=='monotone_separator_removal'
        if m['game']=='p2' and not m.get('consumers'):
            raise ValueError('spacing has no attributed consumer; numeric fallback is insufficient')
        if monotone and profile!='p2_unverified_consumer':
            raise ValueError('monotone exception is restricted to declared unknown consumers')
        if not monotone and (width is None or max_rows is None or profile == 'p2_link_state_dependent'):
            raise ValueError('spacing has no confirmed consumer geometry')
        record = m['relocated']
        if record:
            owners = {k:fragments(record,k) for k in record['line_spans']}
            texts, spans = dict(record['source_texts']), dict(record['source_spans'])
            old_rows = {k:row_bytes(rom,record,k) for k in owners}
            sites = {int(s,16) for s in record['ptr_sites']}
            excluded = {int(s,16) for s in record.get('pointer_classification',{}).get('excluded_sites',[])}
            if hits[source]-excluded != sites or any(
                    struct.unpack_from('<I',rom,s)[0] != GBA+m['target'] for s in sites):
                raise ValueError('existing relocation pointer coverage changed')
        else:
            owners,texts,spans = _nonrelocated_owners(m,rom,final_owners,writes,original)
            old_rows={}
            native_tokens=tokenize(m['payload'],m['game'],glyphs)
            for key,ps in owners.items():
                chunks=[]
                for i,(off,size) in enumerate(ps):
                    if i:
                        gap_start=sum(ps[i-1])
                        if any(gap_start<=t['offset']<off and t['kind'] in ('newline','page','space') for t in native_tokens):
                            chunks.append(b'\x81\x40')
                    chunks.append(m['payload'][off:off+size])
                old_rows[key]=b''.join(chunks)
            end = max(source+len(m['payload']), max(int(k,16)+n for k,n in spans.items()))
            guard_new_relocation(m,original,rom,hits,referenced_entries,end)
            sites = set(m['sites'])
            record = dict(msg=f'0x{source:06X}',status='relocated',ptr_off=f'0x{min(sites):06X}',
                          old_len=end-source,lines=len(owners),fixed=[],layout_controls={},
                          source_spans=spans,source_texts=texts,ptr_sites=[f'0x{s:06X}' for s in sorted(sites)])
        if monotone:
            after,parts=monotone_reflow(m['payload'],m['game'],glyphs,spec['pages'],owners)
        else:
            after,parts = reflow_message(m['payload'],m['game'],glyphs,spec['pages'],max_rows,owners,
                                        allow_paging=profile in ('p1_portrait','p2_portrait'),
                                        allow_spacing_changes=True,allow_growth=True,
                                        allow_blank_rows=profile in ('p1_co_ability','p1_co_break','p1_co_bio','p2_co_panel') or source==0xDEFD80)
        if sha(after)!=spec['after_sha256']:
            raise ValueError('reviewed spacing output bytes changed')
        if _visible(after,m['game'],glyphs) != _visible(m['payload'],m['game'],glyphs):
            raise ValueError('spacing altered glyph bytes')
        if any(not v for v in parts.values()):
            raise ValueError(f'spacing erased source ownership {source:#x}: {[k for k,v in parts.items() if not v]}')
        target=m['target'] if m['relocated'] and len(after)<=len(m['payload']) else free
        updated = copy.deepcopy(record)
        updated.update(new_addr=f'0x{target:06X}',new_len=len(after),source_line_fragments=parts,
                       line_spans={k:p[0] for k,p in parts.items()})
        # Each removed row break was reviewed in the assembled page. Joiners
        # follow its exact logical boundary, including attached name particles.
        # reflow emits only owner fragments separated by native row controls;
        # the ledger records the precise separator for every resulting gap.
        joins = spec['source_fragment_joiners']
        if joins.keys() != parts.keys() or any(len(joins[k]) != len(parts[k])-1 for k in parts):
            raise ValueError('reviewed fragment joiner population changed')
        updated['source_fragment_joiners'] = joins
        updated['source_texts'] = dict(texts)
        owner_changes=[];final_intents=[]
        for key in parts:
            chunks=[]
            for i,(off,size) in enumerate(parts[key]):
                if i:chunks.append(bytes.fromhex(joins[key][i-1]))
                chunks.append(after[off:off+size])
            before_text=_owner_text(old_rows[key],m['game'],glyphs)
            after_text=_owner_text(b''.join(chunks),m['game'],glyphs)
            intent,changed=_spacing_intent(texts[key],before_text,after_text)
            updated['source_texts'][key]=intent
            prior_parts=owners[key]
            prior=final_owners.get(m['target']+prior_parts[0][0])
            final_before=None;final_after=None
            if len(prior_parts)==1 and prior and prior[1]==prior_parts[0][1]:
                final_before=prior[5]
                final_after,_=_spacing_intent(final_before,before_text,after_text)
                lo=parts[key][0][0];hi=max(off+size for off,size in parts[key])
                if any(off<hi and lo<off+size for other,ps in parts.items() if other!=key for off,size in ps):
                    raise ValueError('final intent envelope crosses another source owner')
                prior_index=next(i for i,w in enumerate(writes) if w is prior)
                final_intents.append((key,lo,hi,final_after,prior_index,copy.deepcopy(prior)))
            owner_changes.append(dict(source=key,before=before_text,after=after_text,
                                      authored_before=texts[key],authored_after=intent,
                                      intent_spacing_updated=changed,final_writer_before=final_before,
                                      final_writer_after=final_after))
        indices=[i for i,w in enumerate(writes) if w[7]==f'repoint:0x{source:06X}']
        if len(indices)!=(1 if m['relocated'] else 0):
            raise ValueError('missing/duplicate live relocation binding')
        if target==free:
            if free+len(after)>min(ARENA_END,len(original),len(rom)) or any(b != 255 for b in original[free:free+len(after)]) or any(
                    b != 255 for b in rom[free:free+len(after)]):
                raise ValueError('spacing allocation exceeds guarded free arena')
            free=(free+len(after)+3)&~3
        pending.append((m,updated,after,spec,owner_changes,final_intents))
    report=[]
    for m,updated,after,spec,owner_changes,final_intents in pending:
        source=m['source'];target=int(updated['new_addr'],16)
        old_target=m['target'];old_size=len(m['payload'])
        # Anonymous unchanged-byte retirement shadows stale authored arena
        # writers; original native source writers remain historical evidence.
        if m['relocated'] and old_target!=target:
            writes.append([old_target,old_size,old_size,bytes(rom[old_target:old_target+old_size]).hex(),None,None,None,'spacing-retired-allocation'])
        binding=[target,len(after),len(after),'',None,None,None,f'repoint:0x{source:06X}',
                 dict(source_spans=updated['source_spans'],source=source,old_len=updated['old_len'],
                      ptr_sites=[int(s,16) for s in updated['ptr_sites']])]
        indices=[i for i,w in enumerate(writes) if w[7] == binding[7]]
        if m['relocated']:
            if len(indices)!=1:raise ValueError('missing/duplicate live relocation binding')
            writes[indices[0]]=binding
            m['relocated'].clear();m['relocated'].update(updated)
        else:
            if indices:raise ValueError('unexpected new relocation binding')
            manifest.append(updated);writes.append(binding)
        rom[target:target+len(after)]=after
        writes.append([target,len(after),len(after),after.hex(),None,None,None,'dialogue-spacing-final'])
        for key,lo,hi,intent,prior_index,prior in final_intents:
            writes.append([target+lo,hi-lo,hi-lo,after[lo:hi].hex(),None,intent,prior[6],
                           'dialogue-spacing-final-intent',dict(source_address=int(key,16),
                            fragments=updated['source_line_fragments'][key],prior_write_index=prior_index,
                            prior_write_sha256=sha(json.dumps(prior,ensure_ascii=False,sort_keys=True).encode()),
                            authored_before=prior[5])])
        for site in binding[8]['ptr_sites']:
            raw=struct.pack('<I',GBA+target);rom[site:site+4]=raw
            writes.append([site,4,4,raw.hex(),None,None,None,'dialogue-spacing-pointer'])
        report.append(dict(source=spec['source'],target=updated['new_addr'],before_sha256=sha(m['payload']),
                           after_sha256=sha(after),pages=spec['pages'],owners=owner_changes))
    return report


def verify(rom, original, manifest, ledger=None):
    ledger = load_ledger() if ledger is None else ledger
    messages={m['source']:m for m in inventory(original,rom,manifest)}
    glyphs=Glyphs(bytes(rom));checked=0
    for spec in ledger['messages']:
        m=messages[int(spec['source'],16)]
        if sha(m['payload'])!=spec['after_sha256']:
            raise ValueError('final spacing payload hash changed')
        rows=physical_rows(tokenize(m['payload'],m['game'],glyphs))
        actual={}
        for row in rows:actual.setdefault(row['page'],[]).append(''.join(t['text'] for t in row['tokens']).replace('　',' '))
        # Paging may split one reviewed native page into multiple pages.
        expected=[]
        for p in spec['final_pages']:expected.append(p)
        if list(actual.values()) != expected:
            raise ValueError(f'final spacing page differs: {spec["source"]}')
        checked+=len(spec['pages'])
    return checked
