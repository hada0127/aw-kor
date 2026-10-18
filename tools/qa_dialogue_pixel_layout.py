#!/usr/bin/env python3
"""Audit actual final ROM fonts, native message references and window bounds."""
import argparse
import json
from pathlib import Path

from dialogue_pixel_layout import ROOT, audit, sha
from qa_dialogue_jamming import verify_provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('rom','map','manifest','json'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    verify_provenance(args.rom,args.map,args.manifest)
    result=audit((ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes(),
                 args.rom.read_bytes(),json.loads(args.manifest.read_text()))
    result['manifest_sha256']=sha(args.manifest.read_bytes())
    result['integrity_map_sha256']=sha(args.map.read_bytes())
    result['repairs_sha256']=sha((ROOT/'data/dialogue_layout_repairs.json').read_bytes())
    failed={key:result['summary'][key] for key in
            ('overflows','row_overflows','parser_errors','glyph_errors','caption_overlaps')
            if result['summary'][key]}
    result['passed']=not failed
    result['native_profile_coverage_complete']=not (result['summary']['unverified_consumer_messages'] or result['summary']['state_dependent_messages'])
    result['scope']='Defined native consumer/backing profiles only. Unverified consumers and state-dependent visible offsets remain explicit; separate UI/extraction and runtime ledgers required.'
    args.json.parent.mkdir(parents=True,exist_ok=True)
    args.json.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps(result['summary'],ensure_ascii=False))
    print('FAIL '+str(failed) if failed else 'PASS within the stated static scope')
    return int(bool(failed))


if __name__=='__main__':
    raise SystemExit(main())
