import unittest
from pathlib import Path
from unittest.mock import mock_open, patch
import qa_text_fit as Q
import build_korean_full as B
from part1_ship_help import ROWS as SHIP
from part1_submarine_help import ROWS as SUB

class HelpWriterInventoryTests(unittest.TestCase):
 def test_actual_late_writers_match_all_source_rows(self):
  rows=Q.load_direct_patch_texts(include_writer=True)
  for address,end,text in SHIP+SUB:
   self.assertEqual(rows[address],(end,text,'patch_script_row'))
   self.assertEqual(B.SCRIPT_PLAIN_OPERAND_SPANS[address],end)
   self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[address],text)
 def source(self):return Path(B.__file__).read_text()
 def load(self,source):
  with patch.object(Q,'open',mock_open(read_data=source),create=True):
   return Q.load_direct_patch_texts(include_writer=True)
 def test_actual_writer_binding_change_fails_closed(self):
  source=self.source()
  for changed in (source.replace('for _a, _e, _text in SHIP_HELP_ROWS:', 'for _a, _e in SHIP_HELP_ROWS:'),
                  source.replace("source_text=_text)","source_text='unexpected')")):
   with self.assertRaisesRegex(ValueError,'external help'):self.load(changed)
 def test_missing_and_duplicate_loop_rejected(self):
  source=self.source()
  with self.assertRaisesRegex(ValueError,'Missing external help'):
   self.load(source.replace('in SHIP_HELP_ROWS:', 'in UNKNOWN_ROWS:'))
  with self.assertRaisesRegex(ValueError,'Duplicate external help'):
   self.load(source+"\nfor _a, _e, _text in SHIP_HELP_ROWS:\n    patch_script_row(_a,_e,b'',source_text=_text)\n")
 def test_later_literal_writer_replaces_external_row_in_source_order(self):
  a,e,text=SHIP[0]
  rows=self.load(self.source()+f"\nfixed_text_patch({a}, {e-a}, '후속 변경')\n")
  self.assertEqual(rows[a],(e,'후속 변경','fixed_text_patch'))

if __name__=='__main__':unittest.main()
