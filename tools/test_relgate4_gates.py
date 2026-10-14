"""Focused regression guards for RELGATE-4 visual and catalog baselines."""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_scene_catalog as catalog
import audit_scene_residual_scans as residual
import qa_visual_regions as visual
from lz77_scan import lz77_decompress


class Relgate4GatesTest(unittest.TestCase):
    def test_inferred_compact_consumers_remain_in_review(self):
        import json
        data = json.loads((visual.ROOT / "data/scene_catalog.json").read_text())
        pending = next(s for s in data["scenes"] if s["id"] == "99_unassigned_review")
        self.assertEqual(set(pending["dialogue_ids"]),
                         {"g_00DF8B6A", "g_00DF8B92", "g_00DF8B9A"})
        self.assertEqual(data["coverage"]["dialogue_unassigned"], 3)

    def test_pending_visual_verdict_does_not_complete_review(self):
        shot = {"path": "archive/evidence/frame.png",
                "visual_result": {"status": "pending", "reviewer": "", "frame_refs": []}}
        self.assertFalse(residual.completed_visual_verdict(shot))
        shot["visual_result"] = {"status": "pass", "reviewer": "reviewer",
                                 "frame_refs": [shot["path"]]}
        self.assertTrue(residual.completed_visual_verdict(shot))
        shot["visual_result"]["frame_refs"] = ["other.png"]
        self.assertFalse(residual.completed_visual_verdict(shot))

    def test_shop_baseline_matches_c5_rom_and_rejects_damage(self):
        rom = visual.ROOT / "output/game_wars_korean_candidate_20261014_b31.gba"
        self.assertEqual(
            hashlib.sha256(rom.read_bytes()).hexdigest(),
            "416a1c50d048b4f21b9defa023e11df701e7bcd3a81cecaeb2c9518245a384c2",
        )
        raw, _ = lz77_decompress(rom.read_bytes(), 0x00C03F68)
        layer = visual.th.make_part1_option_block("상점", 28)
        self.assertEqual(raw, visual.th.option_layer_to_tiles(layer))
        self.assertEqual(hashlib.sha256(layer.tobytes()).hexdigest(),
                         visual.PART1_OPTION_LAYER_SHA256["wars_shop"])
        visual.assert_part1_option_logo_palette("part1 option wars_shop", layer)
        blank = Image.new("L", (128, 32))
        with self.assertRaises(AssertionError):
            visual.assert_part1_option_logo_palette("part1 option wars_shop", blank)
        garbled = layer.copy()
        garbled.putpixel((0, 0), 3)
        original = visual.th.make_part1_option_block
        def damaged(text, max_size):
            return garbled if text == "상점" else original(text, max_size)
        with patch.object(visual.th, "make_part1_option_block", side_effect=damaged):
            with self.assertRaisesRegex(AssertionError, "wars_shop: layer hash changed"):
                visual.run_asset_checks()

    def test_pending_sprites_do_not_masquerade_as_dialogue(self):
        dialogue, sprites = catalog.classify_unassigned_coverage(
            {"dialogue_unassigned": 0, "review_pending_total": 25,
             "sprites_unassigned_text_candidate": 25}, {"dialogue_ids": []})
        self.assertEqual(dialogue, [])
        self.assertEqual(len(sprites), 1)
        self.assertEqual(sprites[0]["sprite_text_candidate"], 25)
        dialogue, sprites = catalog.classify_unassigned_coverage(
            {"dialogue_unassigned": 2, "review_pending_total": 0,
             "sprites_unassigned_text_candidate": 0}, {"dialogue_ids": ["a", "b"]})
        self.assertEqual(len(dialogue), 1)
        self.assertEqual(sprites, [])


if __name__ == "__main__":
    unittest.main()
