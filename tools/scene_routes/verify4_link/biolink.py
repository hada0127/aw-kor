#!/usr/bin/env python3
"""Shared driver for the VERIFY-4b BIOS-linked two-core harness.

Host = selected cartridge, client = empty cartridge slot booting the real GBA BIOS
(path/SHA recorded, never copied into tracked paths) and receiving a native
MultiBoot download. Every command and response is kept in a transcript.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import KEYS, raw_to_png  # noqa: E402

ROM = ROOT / "output/game_wars_korean_candidate_20261015_b35.gba"
ROM_SHA = "7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36"
BIOS = ROOT / "temp/bios/gba_bios.bin"
BIOS_SHA = "fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570"
HARNESS = ROOT / "temp/release_C/verify4b/mgba_link_harness"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Link:
    def __init__(self, out):
        assert sha(ROM) == ROM_SHA, "ROM SHA mismatch"
        assert sha(BIOS) == BIOS_SHA, "BIOS SHA mismatch"
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.transcript = []
        self.screens = {}
        self.cheat_tainted = False
        self.state_loads = []
        self.saved_states = []
        self.harness_sha256 = sha(HARNESS)
        args = [str(HARNESS), "--bios", str(BIOS), "--host-skip-bios", str(ROM), "-",
                str(self.out / "emulator.log")]
        self.stderr = (self.out / "stderr.log").open("w")
        self.proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, text=True, bufsize=1)

    def cmd(self, line):
        parts = line.split()
        if parts and parts[0] in {'w16', 'w32', 'setreg', 'loadmb'}:
            self.cheat_tainted = True
        if parts and parts[0] == 'loadstate':
            if len(parts) != 3:
                raise ValueError('loadstate requires player and path')
            path = Path(parts[2])
            meta = path.with_name(path.name + '.provenance.json')
            if meta.is_file():
                record = json.loads(meta.read_text())
                if record.get('rom_sha256') != ROM_SHA or record.get('state_sha256') != sha(path):
                    raise ValueError(f'savestate provenance mismatch: {path}')
                producer = ROOT / record.get('producer_receipt', '')
                producer_record = json.loads(producer.read_text()) if producer.is_file() else {}
                receipt_matches = (record.get('bios_sha256') == BIOS_SHA and
                                   producer_record.get('rom_sha256') == ROM_SHA and
                                   producer_record.get('emulator_exit_code') == 0 and
                                   producer_record.get('cheat_tainted') is False and
                                   any(saved.get('path') == str(path.relative_to(ROOT))
                                       for saved in producer_record.get('saved_states', [])))
                tainted = record.get('cheat_tainted') is not False or not receipt_matches
            else:
                tainted = True
            self.cheat_tainted |= tainted
            self.state_loads.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                                     'provenance': str(meta.relative_to(ROOT)) if meta.is_file() else None,
                                     'provenance_sha256': sha(meta) if meta.is_file() else None,
                                     'cheat_tainted': tainted})
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        response = self.proc.stdout.readline().strip()
        self.transcript.append({"command": line, "response": response})
        print(response, flush=True)
        if not response.startswith("OK "):
            raise RuntimeError(f"{line!r}: {response!r}")
        if parts and parts[0] == 'savestate':
            path = Path(parts[2])
            meta = path.with_name(path.name + '.provenance.json')
            record = {'rom_sha256': ROM_SHA, 'bios_sha256': BIOS_SHA,
                      'state_sha256': sha(path), 'cheat_tainted': self.cheat_tainted,
                      'producer_receipt': str((self.out / 'receipt.json').relative_to(ROOT))}
            meta.write_text(json.dumps(record, indent=2) + '\n')
            self.saved_states.append({'path': str(path.relative_to(ROOT)), 'provenance': str(meta.relative_to(ROOT))})
        return response

    def press(self, key, hold=2, release=6, player=0):
        mask = sum(KEYS[k] for k in key.split("+"))
        self.cmd(f"keys {player} {mask}")
        self.cmd(f"frames {hold}")
        self.cmd(f"keys {player} 0")
        if release:
            self.cmd(f"frames {release}")

    def capture(self, name, player, sync=False):
        raw = self.out / f"{name}_p{player}.raw"
        png = raw.with_suffix(".png")
        resp = self.cmd(f"{'syncshot' if sync else 'shot'} {player} {raw}")
        raw_to_png(raw, png)
        raw.unlink()
        self.screens[name] = {"player": player, "path": str(png.relative_to(ROOT)), "sha256": sha(png),
                              "response": resp}
        return png

    def finish(self, extra):
        try:
            if self.proc.poll() is None:
                try:
                    self.cmd("quit")
                except Exception:
                    pass
                self.proc.stdin.close()
        finally:
            code = self.proc.wait(timeout=30)
            self.stderr.close()
        receipt = {"rom_sha256": ROM_SHA, "bios_path": str(BIOS.relative_to(ROOT)), "bios_sha256": BIOS_SHA,
                   "harness_source_sha256": sha(ROOT / "tools/mgba_link_harness.c"),
                   "harness_path": str(HARNESS.relative_to(ROOT)),
                   "harness_binary_sha256": self.harness_sha256,
                   "transfer": "native BIOS MultiBoot (real BIOS on both cores; client cartridge slot empty)",
                   "emulator_exit_code": code, "screens": self.screens, "transcript": self.transcript}
        receipt.update(extra)
        receipt['cheat_tainted'] = self.cheat_tainted or extra.get('cheat_tainted') is not False
        receipt['state_loads'] = self.state_loads
        receipt['saved_states'] = self.saved_states
        (self.out / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
        print("EXIT", code, flush=True)
        return code
