"""The reviewed compact shop wording is separate from protected source text."""
import collections,json,unittest
from pathlib import Path
import build_korean_full as B

class ShopCoinDisplayAuthorityTests(unittest.TestCase):
 def test_source_and_reviewed_display_are_separate(self):
  root=Path(B.BASE);key='0x00DFA6E2';address=int(key,16)
  source=json.loads((root/'data/dialogue_overrides.json').read_text())[key]
  baseline=json.loads((root/'data/bteam_baseline.json').read_text())['overrides'][key]
  self.assertEqual(source,baseline);self.assertEqual(source,'워즈코인을 사용해서')
  display=B.load_display_overrides()[address]
  self.assertEqual(display,'워즈 코인으로');self.assertNotEqual(source,display)
  self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[address],display)
 def test_display_preserves_pinned_prior_candidate_slot_and_native_boundary(self):
  # Prior a96a1f2354b46b6c927daffcc34b364ac6eb59709db632e6c8bb71f7bb710ff9.
  # docs/success.md:2996-3010 pins the reviewed compact displayed wording.
  codes={s:int(c,16) for s,c in json.loads(Path(B.SYLCODE).read_text()).items()}
  address,end=0xDFA6E2,0xDFA6F8
  original=Path(B.P.ROM).read_bytes()
  self.assertEqual(original[address:end].decode('shift_jis'),'ウォーズコインを使って')
  self.assertEqual(original[end:end+3],b'\x72\x0a\x09')
  text=B.load_display_overrides()[address]
  payload,fit_level=B.encode_fit(text,end-address,codes,collections.Counter(),address)
  self.assertEqual(fit_level,0)  # No shortening, spacing removal or fallback.
  expected=bytes.fromhex('8f6c8ffc8140917e8fa58f7c8b692020202020202020')
  self.assertEqual(payload+b' '*(end-address-len(payload)),expected)

if __name__=='__main__':unittest.main()
