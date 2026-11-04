"""2026-10-23 approved Part 2 prologue punctuation after the W3 overlay (fixB)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import part2_prologue_punctuation as pp  # noqa: E402

COMMA, PERIOD = '、'.encode('shift_jis'), '。'.encode('shift_jis')
KCOMMA, KPERIOD = '，'.encode('shift_jis'), '．'.encode('shift_jis')
GA = bytes.fromhex('8840')


def message(msg, new_addr, payload, *, rewrite=True, old_len=0x20):
    entry = {'msg': msg, 'status': 'relocated', 'new_addr': f'0x{new_addr:X}',
             'new_len': len(payload), 'old_len': old_len,
             'line_spans': {msg: [0, len(payload)]}}
    if rewrite:
        entry['rewrite'] = {'batch': 'p2-prologue.1'}
    return entry


class PrologueAfterOverlay(unittest.TestCase):
    def setUp(self):
        self.rom = bytearray(0xB00000)

    def place(self, address, payload):
        self.rom[address:address + len(payload)] = payload

    def test_rewritten_prologue_message_gets_approved_marks(self):
        payload = GA + COMMA + b'w' + GA + PERIOD + b'k\x00'
        self.place(0xA8D8C8, payload)
        manifest = [message('0xA01B08', 0xA8D8C8, payload)]
        self.assertEqual(len(pp.remaining_japanese(self.rom, manifest)), 2)
        writes = []
        edits = pp.patch_rewritten(self.rom, manifest, writes)
        self.assertEqual([e['after_hex'] for e in edits], [KCOMMA.hex(), KPERIOD.hex()])
        self.assertEqual(self.rom[0xA8D8C8:0xA8D8C8 + len(payload)],
                         GA + KCOMMA + b'w' + GA + KPERIOD + b'k\x00')
        self.assertEqual([w[7] for w in writes], ['part2-prologue-approved-punctuation'] * 2)
        self.assertEqual(pp.remaining_japanese(self.rom, manifest), [])

    def test_rewritten_payload_matches_patch_rewritten(self):
        payload = GA + COMMA + b'w' + GA + PERIOD + b'r' + GA + b'k\x00'
        self.place(0xA8D8C8, payload)
        pp.patch_rewritten(self.rom, [message('0xA019F8', 0xA8D8C8, payload)], [])
        self.assertEqual(pp.rewritten_payload(payload), bytes(self.rom[0xA8D8C8:0xA8D8C8 + len(payload)]))
        self.assertEqual(pp.rewritten_payload(GA + b'k\x00'), GA + b'k\x00')

    def test_unrewritten_or_outside_messages_are_not_touched(self):
        payload = GA + PERIOD + b'\x00'
        self.place(0xA3D000, payload)
        self.place(0xA90000, payload)
        manifest = [message('0xA01B98', 0xA3D000, payload, rewrite=False),
                    message('0xA02000', 0xA90000, payload)]
        self.assertEqual(pp.patch_rewritten(self.rom, manifest, []), [])
        self.assertEqual(self.rom[0xA3D002:0xA3D004], PERIOD)
        self.assertEqual(self.rom[0xA90002:0xA90004], PERIOD)
        # The repoint copy of a prologue message is still audited (no silent pass).
        self.assertEqual([r[1] for r in pp.remaining_japanese(self.rom, manifest)], ['0xA01B98'])

    def test_in_place_script_is_audited_except_retired_sources(self):
        self.place(0xA01A30, GA + PERIOD)          # live in-place row
        self.place(0xA01B10, GA + PERIOD)          # retired by the relocation below
        moved = GA + KPERIOD + b'\x00'
        self.place(0xA8D8C8, moved)
        manifest = [message('0xA01B08', 0xA8D8C8, moved, old_len=0x5F)]
        spans = pp.live_prologue_spans(manifest)
        self.assertIn((0xA01970, 0xA01B08, 'in-place'), spans)
        self.assertIn((0xA01B67, 0xA01C88, 'in-place'), spans)
        found = pp.remaining_japanese(self.rom, manifest)
        self.assertEqual([(a, o) for a, o, _ in found], [(0xA01A32, 'in-place')])

    def test_drift_oracle_expects_approved_marks_only_in_prologue(self):
        from qa_bteam_drift import display_equivalent
        self.assertEqual(display_equivalent('호크, 거기 있느냐!', 0xA019F8),
                         '호크，　거기　있느냐！')
        self.assertEqual(display_equivalent('기대하고 있다.', 0xA01C78), '기대하고　있다．')
        # The ROM side stays literal: a shipped 、 does not fold to the approved mark.
        self.assertEqual(display_equivalent('호크、　거기', 0xA019F8, actual=True), '호크、　거기')
        # Outside the prologue the Part 2 story writer still uses 、/。.
        self.assertEqual(display_equivalent('가, 나.', 0xA01CB8), '가、　나。')


class PunctuationGateHelpers(unittest.TestCase):
    def test_rewrite_pointer_bytes_are_not_text(self):
        from qa_part1_dialogue_punctuation import active_text_payloads
        rom = bytearray(0xDB0000)
        rom[0xDA554C:0xDA5550] = bytes.fromhex('1c7baa08')
        writes = [[0xDA554C, 4, 4, '1c7baa08', None, '', None, 'dialogue-rewrite-pointer']]
        self.assertEqual(list(active_text_payloads(writes, rom)), [])
        writes[0][7] = 'dialogue-override'
        self.assertEqual(len(list(active_text_payloads(writes, rom))), 1)


if __name__ == '__main__':
    unittest.main()
