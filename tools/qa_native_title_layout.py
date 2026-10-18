#!/usr/bin/env python3
"""Final-ROM native map-title encoding, bitmap, slot and geometry audit."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import part2_mission_title_fit as fit
from lz77_scan import lz77_decompress
from qa_dialogue_jamming import verify_provenance

ROOT=Path(__file__).resolve().parents[1]
GBA=0x08000000


def audit(original,rom):
    titles=fit.active_titles(original,rom)
    if rom[fit.BASE:fit.BASE+len(fit.CODE)]!=fit.CODE:
        raise ValueError('map-title loader bytes differ from assembled source')
    for address,expected,target in fit.SITES:
        replacement=bytes.fromhex('00490847')+struct.pack('<I',GBA+target+1)+bytes.fromhex('c046')*((len(expected)-8)//2)
        if rom[address:address+len(expected)]!=replacement:
            raise ValueError('mission-title hook differs from guarded layout')
    address,expected,target=fit.MAP_SITE
    if rom[address:address+len(expected)]!=bytes.fromhex('08b4014b1847c046')+struct.pack('<I',GBA+target+1):
        raise ValueError('map-title trampoline differs from guarded layout')
    table=struct.unpack_from('<I',rom,0x37C548)[0]-GBA
    if table!=0xF40000:
        raise ValueError('native title font table moved outside its reservation')
    glyphs={};advances={}
    for at in range(table,0xF42000-11,12):
        code,_,ptr,advance=struct.unpack_from('<HHII',rom,at)
        if not ptr:break
        if code in glyphs or not GBA<=ptr<GBA+len(rom):
            raise ValueError('duplicate or invalid native title font entry')
        decoded=lz77_decompress(rom,ptr-GBA)
        if decoded is None or len(decoded[0])!=512 or not 0<advance<=32:
            raise ValueError('invalid native title glyph payload/advance')
        glyphs[code],advances[code]=decoded[0],advance
    else:raise ValueError('native title font table has no bounded terminator')
    spacing=struct.unpack_from('<12H',original,0x8FD6C4)
    rows=[];descriptor_index=0
    for pointer,address,codes,_ in titles:
        if not codes or any(c not in glyphs or (c!=0x8140 and not any(glyphs[c])) for c in codes):
            raise ValueError('native title has missing or blank visible art')
        raw,layout=fit.map_title_raster(codes,glyphs,advances,spacing)
        if len(codes)>9:
            at=fit.MAP_DESCRIPTORS+32*descriptor_index;descriptor_index+=1
            key,ptr,total,count=struct.unpack_from('<IIHB',rom,at)
            if (key,total,count)!=(address+GBA,layout['sum_width'],layout['chunks']):
                raise ValueError('map-title descriptor key/count/width differs from native raster')
            if rom[at+11] or rom[at+12:at+12+count]!=bytes(layout['widths']) or any(rom[at+12+count:at+32]):
                raise ValueError('map-title descriptor width/padding differs')
            if not GBA+fit.GLYPHS<=ptr<GBA+fit.END:
                raise ValueError('map-title chunk asset escapes reservation')
            decoded=lz77_decompress(rom,ptr-GBA)
            if decoded is None or decoded[0]!=raw or ptr-GBA+decoded[1]>fit.END:
                raise ValueError('map-title chunk pixels or size differ from source raster')
            layout['vram_banks']=[dict(tile_base=bank,title_end=bank+count*16,decoration_start=bank+0x90)
                                  for bank in (0,0xD0)]
        else:
            if layout['compact']:
                raise ValueError('unhooked short map title exceeds native viewport')
        cell=20 if len(codes)>9 else 24
        mission_ink=[]
        for i,code in enumerate(codes):
            glyph=fit.compact_glyph(glyphs[code]) if len(codes)>9 else glyphs[code]
            mission_ink.extend(i*cell+x for row in fit.glyph_pixels(glyph) for x,v in enumerate(row) if v)
        # The original animation reserves 224px across its nine native cells.
        if mission_ink and max(mission_ink)>=224:
            raise ValueError('mission animation ink exceeds its native title strip')
        layout.update(source=f'{struct.unpack_from("<I",original,pointer)[0]-GBA:08X}',
                      pointer=f'{pointer:08X}',target=f'{address:08X}',
                      mission_cell_px=cell,mission_ink_right=max(mission_ink,default=-1)+1)
        rows.append(layout)
    if any(rom[fit.MAP_DESCRIPTORS+32*descriptor_index:fit.MAP_DESCRIPTORS+32*(descriptor_index+1)]):
        raise ValueError('map-title descriptor terminator missing')
    return dict(passed=True,active_descriptors=180,unique_titles=len(titles),
                strict_titles=len(titles),map_composites=descriptor_index,
                sources_below_old_range=sum(int(x['source'],16)<fit.TITLE_START for x in rows),
                rom_sha256=hashlib.sha256(rom).hexdigest(),rows=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('rom','map','manifest','json'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();verify_provenance(a.rom,a.map,a.manifest)
    result=audit((ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes(),a.rom.read_bytes())
    a.json.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
