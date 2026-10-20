import contextlib
import copy
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_part1_compact_help as gate


class CompactHelpGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = bytearray(gate.ROM.read_bytes())

    def run_gate(self, rom=None, frame_dir=None, live_targets=None):
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "temp") as d:
            root = Path(d)
            rom_path = root / "candidate.gba"
            rom_path.write_bytes(self.rom if rom is None else rom)
            out = root / "report.json"
            with patch.object(sys, "argv", ["gate", "--rom", str(rom_path), "--out", str(out)]), \
                 patch.object(gate, "CURRENT_VISUAL_FRAME_DIR", frame_dir or gate.CURRENT_VISUAL_FRAME_DIR), \
                 patch.object(gate, "WIDTH_EVIDENCE_FRAME", (frame_dir or gate.CURRENT_VISUAL_FRAME_DIR) / gate.WIDTH_EVIDENCE_FRAME.name), \
                 patch.object(gate, "load_live_code_report_targets", return_value=live_targets if live_targets is not None else set()), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = gate.main()
            return code, json.loads(out.read_text())

    def test_relocated_second_line_corruption_is_detected(self):
        rom = self.rom.copy()
        p = struct.unpack_from("<I", rom, 0xDFAAF8)[0] - 0x08000000
        second = rom.index(b"\x72\x0A\x09", p, p + 80) + 3
        rom[second] ^= 1
        code, report = self.run_gate(rom)
        self.assertEqual(code, 1)
        self.assertIn("relocated_full_message_mismatch", {i["type"] for i in report["issues"]})
        self.assertFalse(next(r for r in report["rows"] if r["address"] == "0x00DFA8CB")["actual_prefix_matches"])

    def test_third_relocated_row_is_blocking(self):
        rom = self.rom.copy()
        p = struct.unpack_from("<I", rom, 0xDFAAF8)[0] - 0x08000000
        first = bytes(rom[p + 2:p + 32])
        payload = b"\x0A\x09" + first + b"\x72\x0A\x09\x81\x40\x72\x0A\x09\x81\x40\x0A\x00"
        rom[p:p + len(payload)] = payload
        code, report = self.run_gate(rom)
        self.assertEqual(code, 1)
        self.assertIn("displayed_row_limit", {i["type"] for i in report["issues"]})

    def test_missing_and_replaced_frame_fail(self):
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "temp") as d:
            folder = Path(d)
            for name in gate.EVIDENCE_SHA256:
                (folder / name).write_bytes((gate.CURRENT_VISUAL_FRAME_DIR / name).read_bytes())
            (folder / gate.WIDTH_EVIDENCE_FRAME.name).write_bytes(b"replacement")
            (folder / "0012_DOWN_0001435.png").unlink()
            code, report = self.run_gate(frame_dir=folder)
            self.assertEqual(code, 1)
            bad = {i["file"] for i in report["issues"] if i["type"] == "evidence_sha256_mismatch"}
            self.assertEqual(bad, {gate.WIDTH_EVIDENCE_FRAME.name, "0012_DOWN_0001435.png"})

    def test_mismatched_measurement_sha_fails(self):
        with patch.dict(gate.EVIDENCE_SHA256, {"window_measurement.json": "0" * 64}):
            code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("current_visual_capture_receipt_invalid", {i["type"] for i in report["issues"]})

    def test_refreshed_synthetic_covers_remaining_eleven(self):
        code, report = self.run_gate(live_targets=gate.LIVE_CODE_INJECTION_EVIDENCE)
        self.assertEqual(code, 0)
        self.assertEqual(report["render_evidence_missing_addresses"], [])
        self.assertEqual(report["synthetic_render_evidence_count"], 11)
        self.assertEqual(report["visual_evidence_missing_count"], 11)

    def test_real_synthetic_loader_rejects_missing_hidden_frame_and_wrong_mapping(self):
        source = gate.ROOT / "data/evidence/part1_help_b43_synthetic/report.json"
        data = json.loads(source.read_text())
        rom = bytes(self.rom)
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "temp") as d:
            path = Path(d) / "report.json"
            def check(document):
                path.write_text(json.dumps(document))
                issues = []
                targets = gate.load_live_code_report_targets(
                    path, data["rom_sha256"], rom, issues, [])
                return targets, issues
            targets, issues = check(data)
            self.assertFalse(issues, issues)
            self.assertEqual(targets, gate.LIVE_CODE_INJECTION_EVIDENCE)
            missing = copy.deepcopy(data)
            hidden = next(r for r in missing["rows"] if r["case_id"] == "hidden")
            hidden["additional_frames"] = []
            _, issues = check(missing)
            self.assertIn("invalid_live_code_injection_evidence", {x["type"] for x in issues})
            wrong = copy.deepcopy(data)
            next(r for r in wrong["rows"] if r["case_id"] == "code16")["target_reads"]["0x00DFA8AA"] = "0x08A7C018"
            _, issues = check(wrong)
            self.assertIn("invalid_live_code_injection_evidence", {x["type"] for x in issues})

    def test_truncated_rom_writes_fail_report(self):
        code, report = self.run_gate(rom=b"GBA")
        self.assertEqual(code, 1)
        self.assertGreater(report["issue_count"], 0)

    def test_malformed_receipt_writes_fail_report(self):
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "temp") as d:
            folder = Path(d)
            for name in gate.EVIDENCE_SHA256:
                (folder / name).write_bytes((gate.CURRENT_VISUAL_FRAME_DIR / name).read_bytes())
            (folder / "baseline.json").write_text("[]")
            code, report = self.run_gate(frame_dir=folder)
            self.assertEqual(code, 1)
            self.assertIn("current_visual_capture_receipt_unreadable", {i["type"] for i in report["issues"]})


if __name__ == "__main__":
    unittest.main()
