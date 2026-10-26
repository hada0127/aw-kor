#!/usr/bin/env python3
"""Cold-boot Part 2 link replay with a paired-state branch comparison.

Run from the repository root. ROM/BIOS are supplied explicitly; scratch goes
only below temp/. This checks the harness, not game correctness on hardware.
"""
import argparse
import hashlib
import json
import subprocess
import os
import selectors
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"A": 1, "B": 2, "SELECT": 4, "START": 8,
        "RIGHT": 16, "LEFT": 32, "UP": 64, "DOWN": 128}
STAGES = {'battle_part2_controls': ['link:off', 'load:temp/release_C/canon8/verify5/battle_part2/host_end.ss0', 'loadc:temp/release_C/canon8/verify5/battle_part2/client_end.ss0', 'link:on', 'A:2:100', 'shot:host_a', 'cshot:client_a', 'START:2:100', 'shot:host_start', 'cshot:client_start', 'ckey:A:2:100', 'shot:host_ca', 'cshot:client_ca', 'wait:100', 'shot:host_wait', 'cshot:client_wait', 'save:temp/release_C/canon8/verify5/battle_part2_controls/host_end.ss0', 'savec:temp/release_C/canon8/verify5/battle_part2_controls/client_end.ss0'], 'battle_part2_host_endturn': ['link:off', 'load:temp/release_C/canon8/verify5/battle_part2_controls/host_end.ss0', 'loadc:temp/release_C/canon8/verify5/battle_part2_controls/client_end.ss0', 'link:on', 'B:2:10', 'RIGHT:2:10', 'RIGHT:2:10', 'RIGHT:2:10', 'A:2:20', 'shot:host_menu', 'DOWN:2:10', 'shot:host_end_focus', 'A:2:100', 'shot:host_after', 'cshot:client_after', 'wait:120', 'shot:host_late', 'cshot:client_late', 'save:temp/release_C/canon8/verify5/battle_part2_host_endturn/host_end.ss0', 'savec:temp/release_C/canon8/verify5/battle_part2_host_endturn/client_end.ss0'], 'battle_part2_result_yes': ['link:off', 'load:temp/release_C/canon8/verify5/battle_part2_host_endturn/host_end.ss0', 'loadc:temp/release_C/canon8/verify5/battle_part2_host_endturn/client_end.ss0', 'link:on', 'ckey:B:2:10', 'ckey:DOWN:2:10', 'ckey:DOWN:2:10', 'ckey:DOWN:2:10', 'ckey:A:2:20', 'ckey:A:2:20', 'ckey:A:2:180', 'cshot:client_dialog', 'ckey:LEFT:2:10', 'cshot:client_yes_focus', 'ckey:A:2:120', 'shot:host_00', 'cshot:client_00', 'wait:160', 'shot:host_01', 'cshot:client_01', 'wait:300', 'shot:host_02', 'cshot:client_02', 'wait:600', 'shot:host_03', 'cshot:client_03']}
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import raw_to_png  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", type=Path, required=True)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--bios", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--response-timeout", type=float, default=30)
    args = ap.parse_args()
    if args.response_timeout <= 0:
        ap.error("--response-timeout must be positive")
    for prerequisite in (args.harness, args.rom, args.bios):
        if not prerequisite.is_file():
            ap.error(f"missing prerequisite: {prerequisite}")
    if not str(args.out.resolve()).startswith(str((ROOT / "temp").resolve()) + os.sep):
        ap.error("--out must be under repository temp/")
    args.out.mkdir(parents=True, exist_ok=True)
    cmd = [str(args.harness), "--bios", str(args.bios), "--host-skip-bios",
           str(args.rom), "-", str(args.out / "emulator.log")]
    transcript = []
    result = {"rom": str(args.rom), "transcript": transcript, "matched": False}
    with (args.out / "stderr.log").open("w") as err:
        try:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=err)
        except OSError as exc:
            result["error"] = repr(exc)
            (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            raise
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        pending = bytearray()
        def send(line):
            proc.stdin.write((line + "\n").encode())
            proc.stdin.flush()
            deadline = time.monotonic() + args.response_timeout
            while b"\n" not in pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(max(0, remaining)):
                    transcript.append([line, "<timeout>"])
                    raise TimeoutError(f"response timeout: {line}")
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    transcript.append([line, "<eof>"])
                    raise RuntimeError(f"emulator exited: {line}")
                pending.extend(chunk)
            raw, _, rest = pending.partition(b"\n")
            pending[:] = rest
            answer = raw.decode(errors="replace").strip()
            transcript.append([line, answer])
            if not answer.startswith("OK "):
                raise RuntimeError(f"{line}: {answer}")
            return answer

        def press(player, key, hold, release):
            send(f"keys {player} {KEYS[key]}")
            send(f"frames {hold}")
            send(f"keys {player} 0")
            if release:
                send(f"frames {release}")

        branch = "reference"
        def both(label):
            hashes = []
            for player in (0, 1):
                path = args.out / f"{branch}_{label}_{player}.raw"
                send(f"shot {player} {path}")
                hashes.append(digest(path))
                if label.endswith(("_17", "_20", "_23", "late_900")):
                    raw_to_png(path, path.with_suffix(".png"))
                path.unlink()
            return hashes

        def stage(name, collect=False):
            tokens = STAGES[name]
            checks = []
            for index, token in enumerate(tokens):
                op, _, arg = token.partition(":")
                if op in ("link", "load", "loadc", "save", "savec", "shot", "cshot"):
                    continue
                if op == "wait":
                    send(f"frames {int(arg)}")
                elif op == "ckey":
                    key, hold, release = arg.split(":")
                    press(1, key, int(hold), int(release))
                else:
                    hold, release = arg.split(":")
                    press(0, op, int(hold), int(release))
                if collect:
                    checks.append([index, token, both(f"{name}_{index}")])
            return checks

        try:
            send("link off")
            send("frames 480")
            for key, release in (("A", 200), ("START", 200), ("DOWN", 120),
                                 ("A", 240), ("START", 240), ("A", 200)):
                press(0, key, 2, release)
            for _ in range(3):
                press(0, "DOWN", 2, 40)
            press(0, "A", 2, 180)
            send("link on")
            press(0, "UP", 2, 60)
            press(0, "A", 2, 400)
            press(0, "START", 2, 10)
            for _ in range(12):
                send("frames 250")
            press(0, "A", 2, 30)
            for count in (110, 120, 180, 300, 600):
                send(f"frames {count}")
            stage("battle_part2_controls")
            stage("battle_part2_host_endturn")
            saved_at = send("status")
            saved_sio = send("sio")
            pair = args.out / "checkpoint.pair"
            send(f"savepair {pair}")
            reference = stage("battle_part2_result_yes", collect=True)
            for count in (600, 900):
                send(f"frames {count}")
                reference.append([count, "late", both(f"late_{count}")])
            ref_regs = send("regs 0")
            ref_regs_client = send("regs 1")
            ref_timing_sio = [send("status"), send("sio")]
            send(f"loadpair {pair}")
            loaded_timing_sio = [send("status"), send("sio")]
            branch = "restored"
            restored = stage("battle_part2_result_yes", collect=True)
            for count in (600, 900):
                send(f"frames {count}")
                restored.append([count, "late", both(f"restored_late_{count}")])
            restored_regs = send("regs 0")
            restored_regs_client = send("regs 1")
            restored_timing_sio = [send("status"), send("sio")]
            comparisons = {
                "screens": reference == restored,
                "host_regs": ref_regs == restored_regs,
                "client_regs": ref_regs_client == restored_regs_client,
                "loaded_status_sio": [saved_at, saved_sio] == loaded_timing_sio,
                "replay_status_sio": ref_timing_sio == restored_timing_sio,
            }
            matched = all(comparisons.values())
            send("quit")
        except BaseException as exc:
            result["error"] = repr(exc)
            raise
        finally:
            selector.close()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            if proc.stdin:
                proc.stdin.close()
            if proc.stdout:
                proc.stdout.close()
            result["exit_code"] = proc.returncode
            (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    result.update({"rom_sha256": digest(args.rom),
              "bios_sha256": digest(args.bios), "harness_sha256": digest(args.harness),
              "saved_at": saved_at, "pair_sha256": digest(pair),
              "saved_sio": saved_sio,
              "pair_bytes": pair.stat().st_size, "reference": reference,
              "restored": restored, "reference_regs": ref_regs,
              "restored_regs": restored_regs,
              "reference_regs_client": ref_regs_client,
              "restored_regs_client": restored_regs_client,
              "reference_timing_sio": ref_timing_sio,
              "loaded_timing_sio": loaded_timing_sio,
              "restored_timing_sio": restored_timing_sio,
              "comparisons": comparisons, "matched": matched})
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"exit={result['exit_code']} matched={matched} checkpoints={len(reference)} "
          f"pair={result['pair_sha256']} rom={result['rom_sha256']}")
    if result["exit_code"] or not matched:
        print(f"failed_comparisons={[name for name, ok in comparisons.items() if not ok]}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
