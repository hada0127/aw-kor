"""Real native inventory and actual generated relocation, never a ROM build."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import ec3190_contract as c
from dialogue_repoint import repoint_messages, _line_index
import dialogue_pixel_layout as layout
import test_ec3190_contract as contract_tests
from qa_ec3190_preservation import validate


@unittest.skipUnless(os.environ.get('AW_EC3190_BASELINE'), 'read-only build0531 required')
class InventoryTests(unittest.TestCase):
    def test_actual_inventory_generated_record_and_2981_preservation(self):
        root=Path(os.environ['AW_EC3190_BASELINE'])
        original=(root/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        baseline=(root/'output/game_wars_korean_df28c0_candidate.gba').read_bytes()
        manifest=json.loads((root/'temp/repoint_manifest.json').read_text())
        from hashlib import sha256
        self.assertEqual(sha256(baseline).hexdigest(),'91d0a2faab043894cda7176129ee6b2e0879fdbe56ebfc88a28b6603c70fa7f8')
        self.assertEqual(sha256(original).hexdigest(),'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
        tree,ns=contract_tests.ContractTests().callbacks()
        source_index=_line_index(str(Path(contract_tests.builder.FOUND)))
        self.assertEqual(source_index[c.FIRST][0],42)
        rom=bytearray(baseline);writes=[]
        records,stats=repoint_messages(rom,original,fixable=ns['_rp_fixable'],
            fixed_bytes=ns['_rp_fixed_bytes'],fit_level_dlg=ns['_rp_fit_level'],
            source_text=ns['_rp_dlg'],decode_text=lambda raw:'',cell_width=ns['_rp_cell_width'],
            slots={c.FIRST:42},line_index={c.FIRST:source_index[c.FIRST]},table_offsets=[],
            extra_messages={c.MESSAGE:[c.SITE]},free_start=0xA8D780,free_end=0xAFF000,
            write_log=writes,require_ec3190=True)
        self.assertEqual(stats['relocated'],1)
        c.assert_manifest(records)
        m=records[0];target=int(m['new_addr'],16)
        c.validate(rom[target:target+50],m)
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0][7],'repoint:0xEC3190')
        # Model final residual removal only in this in-memory fixture.
        rom[c.FIRST:c.TAIL]=original[c.FIRST:c.TAIL]
        self.assertEqual(validate(baseline,rom,manifest,manifest+records)['preserved'],2981)
        consumers=layout.p1_consumers(original)
        self.assertEqual(consumers[c.MESSAGE],[dict(site=c.SITE,profile=('p1_link_notice',208,1),
            consumer='B711BE table index5 / B71204 instructions')])
        # Exercise the real inventory; then restrict only expensive pixel audit.
        entries=layout.inventory(original,rom,manifest+records)
        selected=[e for e in entries if e['source']==c.MESSAGE]
        self.assertEqual(len(selected),1)
        e=selected[0]
        self.assertEqual(e['target'],target);self.assertEqual(e['payload'],c.PAYLOAD)
        self.assertEqual(e['sites'],[c.SITE]);self.assertEqual(e['profile'],('p1_link_notice',208,1))
        with patch.object(layout,'inventory',return_value=selected):result=layout.audit(original,rom,manifest+records)
        self.assertFalse(result['errors'])
        self.assertEqual([(r['advance_px'],r['limit_px']) for r in result['rows']],[(176,208)])
        for row in result['rows']:
            for key in ('overflow','row_overflow','glyph_errors','caption_overlap'):self.assertFalse(row[key])
        for raw,key in ((b'\x0a\x09'+c.ROW+b'\x81\x40'*5+b'\x0a\0','overflow'),
                        (b'\x0a\x09'+c.ROW+b'\x72\x0a\x09'+c.ROW+b'\x0a\0','row_overflow')):
            bad=dict(e,payload=raw)
            with patch.object(layout,'inventory',return_value=[bad]):failed=layout.audit(original,rom,manifest+records)
            self.assertTrue(any(r[key] for r in failed['rows']))
        # Introduce an independently observed alias and demand actual pointer agreement.
        alias=copy.deepcopy(consumers);alias[c.MESSAGE].append(dict(alias[c.MESSAGE][0],site=0x100))
        with patch.object(layout,'p1_consumers',return_value=alias),self.assertRaisesRegex(ValueError,'divergent message aliases'):
            layout.inventory(original,rom,manifest+records)
        lossless=json.loads((root/'temp/repoint_lossless_requests.json').read_text())
        fixed={a for item in manifest+records if item.get('status')=='relocated' for a in item.get('fixed',[])}
        self.assertEqual(len(lossless['requested']),1710)
        self.assertEqual([a for a in lossless['requested'] if f'0x{int(a,16):06X}' not in fixed],lossless['unfulfilled'])
        self.assertEqual(len(lossless['unfulfilled']),9)
        self.assertEqual(ns['_rp_lossless_requested'],set())
        if os.environ.get('AW_EC3190_EVIDENCE'):
            Path(os.environ['AW_EC3190_EVIDENCE']).write_text(json.dumps(dict(record=m,writes=writes,
                source=e['source'],target=e['target'],sites=e['sites'],profile=e['profile'],
                rows=result['rows'],preserved=2981,lossless=lossless),indent=2,ensure_ascii=False))


if __name__=='__main__':unittest.main()
