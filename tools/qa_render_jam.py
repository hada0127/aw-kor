#!/usr/bin/env python3
"""Renderer-bound final-ROM spacing audit; no blanket Part 2 exemption."""
import argparse,json
from pathlib import Path
from qa_dialogue_jamming import verify_provenance
from qa_renderer_text import payloads
from renderer_text import P1_SCRIPT,P2_SCRIPT,single_bytes
from text_metrics import encoded_visual_cells

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    for name in ('rom','map','manifest'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();verify_provenance(args.rom,args.map,args.manifest)
    rom=args.rom.read_bytes();original=(ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
    writes=json.loads(args.map.read_text());manifest=json.loads(args.manifest.read_text())
    # P1's space hook applies only before a two-byte glyph (B12764 call).
    p1_hook=rom[0xB12764:0xB1276C]==bytes.fromhex('004800474105f308')
    errors=[];count=0
    for addr,renderer,raw,native in payloads(rom,original,writes,manifest):
        count+=1
        try:encoded_visual_cells(raw,renderer,p1_space_hook=p1_hook)
        except ValueError as exc:errors.append((hex(addr),str(exc)))
        for i,b in single_bytes(raw.rstrip(b' \x00')):
            if b!=0x20 or i==0:continue
            following=raw[i+1] if i+1<len(raw) else 0
            if renderer==P2_SCRIPT or (renderer==P1_SCRIPT and not(p1_hook and (0x81<=following<=0x9f or 0xe0<=following<=0xef))):
                errors.append((hex(addr+i),'consume-only interior space'))
    for row in errors:print('JAM',*row)
    print(f'renderer payloads: {count}; unsafe tokens/spacing: {len(errors)}')
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
