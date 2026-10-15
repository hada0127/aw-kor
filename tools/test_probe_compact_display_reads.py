"""Recorder checkpoint validation for compact display read probes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_compact_display_reads import parse_watch_log, recorder_endpoint_state


class RecorderEndpointStateTest(unittest.TestCase):
    def test_same_rom_state_and_hash_required(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "temp") as directory:
            root = Path(directory)
            state = root / "frame.ss0"
            state.write_bytes(b"state")
            receipt = root / "frame.checkpoint.json"
            receipt.write_text(json.dumps({
                "rom_sha256": "rom-a",
                "state": state.name,
                "state_sha256": hashlib.sha256(state.read_bytes()).hexdigest(),
            }))
            checkpoint = {"recorder_endpoint": {"checkpoint": str(receipt)}}
            self.assertEqual(recorder_endpoint_state(checkpoint, "rom-a"), state)
            with self.assertRaisesRegex(ValueError, "ROM mismatch"):
                recorder_endpoint_state(checkpoint, "rom-b")
            state.write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                recorder_endpoint_state(checkpoint, "rom-a")

    def test_exact_watch_hit_is_counted_without_group_index(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "temp") as directory:
            log = Path(directory) / "watch.log"
            log.write_text("0 addr=08DF8B62 pc=08B12082 lr=08B13187 r0=08DF8B62 r1=08DF8B62 old=00000093 new=00000000\n")
            hits = parse_watch_log(log, {}, {}, [0xDF8B62], 4)
            self.assertEqual(hits[0]["source"]["target_start"], "0x00DF8B62")
            self.assertTrue(hits[0]["source"]["target_span_match"])


if __name__ == "__main__":
    unittest.main()
