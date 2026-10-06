#!/usr/bin/env python3
"""bteam_addresses.json (B-team authority set used by the build, editors and QA)
must name exactly the addresses of bteam_baseline.json (the protected B-team text).

A relocation recorded in bteam_baseline.json `_relocation_notes` moves a B-team row
to its owner address; bteam_addresses.json has to move with it, otherwise the
repoint selector and the jam-skip exemption treat the owner as non-B-team
(review5 #2, candidate5 B831C4/A34F24/A34F40).
"""
import json
import os
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _canon(key):
    return '0x%08X' % int(key, 16)


def _load():
    with open(os.path.join(BASE, 'data', 'bteam_addresses.json'), encoding='utf-8') as f:
        addresses = json.load(f)
    with open(os.path.join(BASE, 'data', 'bteam_baseline.json'), encoding='utf-8') as f:
        baseline = json.load(f)
    return addresses, baseline


class BteamAddressesConsistencyTest(unittest.TestCase):
    def test_address_set_equals_baseline_keys(self):
        addresses, baseline = _load()
        listed = [_canon(a) for a in addresses['addresses']]
        self.assertEqual(len(listed), len(set(listed)), 'duplicate address in bteam_addresses.json')
        keys = {_canon(k) for k in baseline['overrides']}
        self.assertEqual(sorted(set(listed) - keys), [], 'in bteam_addresses.json but not in the baseline')
        self.assertEqual(sorted(keys - set(listed)), [], 'baseline B-team row missing from bteam_addresses.json')
        self.assertEqual(baseline.get('count'), len(keys))

    def test_relocated_owners_are_b_team_and_old_keys_are_not(self):
        addresses, baseline = _load()
        listed = {_canon(a) for a in addresses['addresses']}
        notes = {k: v for k, v in baseline.get('_relocation_notes', {}).items() if not k.startswith('_')}
        self.assertTrue(notes)
        for owner in notes:
            self.assertIn(_canon(owner), listed, owner)
        # The pre-relocation keys (one table entry late) must not be B-team any more.
        for stale in ('0x00A2A2DC', '0x00A2A300', '0x00B831CC', '0x00A34F2C', '0x00A34F48'):
            self.assertNotIn(stale, listed, stale)

    def test_addresses_are_sorted(self):
        addresses, _ = _load()
        listed = addresses['addresses']
        self.assertEqual(listed, sorted(listed))


if __name__ == '__main__':
    unittest.main()
