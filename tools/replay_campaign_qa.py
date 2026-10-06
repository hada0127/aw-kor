#!/usr/bin/env python3
"""Local, model-free cold replay and every-frame regression comparison.

Capture equality is not proof that a translation is correct. Only recorded
routes are replayed; this tool does not discover or finish unexplored missions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from playthrough_capture import (KEYS, ROOT, default_hold, parse_action, validate_action, save_json, sha,
                                 verify_parent, checkpoint_cheat_tainted, run_cheat_evidence)


def cheat_classification(run, checkpoint=None, *, strict=True):
    """Cheat classification from the run's own records, not exit.json alone.

    Evidence: verified checkpoint flag, ledger cheat rows, baseline inheritance,
    actions cheat events/dispatches, the sticky marker and the exit flag. strict
    also counts an unreadable ledger/baseline as tainted (used after verify_run).
    """
    run = Path(run)
    evidence = run_cheat_evidence(run)
    if checkpoint is not None:
        evidence['checkpoint_flag'] = checkpoint_cheat_tainted(checkpoint)
    try:
        exit_flag = json.loads((run / 'exit.json').read_text()).get('cheat_tainted') is True
    except (OSError, ValueError):
        exit_flag = None
    evidence.pop('ledger_verified', None)
    tainted = any(v is True for v in evidence.values()) or exit_flag is True
    if strict:
        # The ledger and baseline are authoritative; unreadable means not normal play.
        tainted = tainted or evidence['ledger_rows'] is None or evidence['baseline_inherited'] is None
    return {'cheat_tainted': tainted, 'normal_play': not tainted,
            'classification': 'cheat_tainted_not_normal_play' if tainted else 'normal_play',
            'exit_flag': exit_flag, 'exit_flag_consistent': exit_flag is tainted,
            'evidence': evidence}


class UsageParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(64, f'{self.prog}: error: {message}\n')


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def parse_inputs(text):
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split()
        if len(parts) not in (2, 3) or parts[0].upper() not in KEYS:
            raise ValueError(f'Invalid input at line {number}: {line!r}')
        key, count, hold = parse_action(parts)
        result.append((key, count, hold) if hold != default_hold(key) else (key, count))
    if not result:
        raise ValueError('Empty input route')
    return result


def export_inputs(run):
    """Export a closed cold-boot route; incomplete runs are never baselines."""
    baseline = json.loads((run / 'baseline.json').read_text())
    if baseline.get('initial_game_save'):
        raise ValueError('A game-save boot cannot be exported as an empty-save cold route')
    if baseline['initial_core_frame'] != 0 or baseline.get('parent_checkpoint'):
        raise ValueError('Export requires a cold-boot run, not a resumed suffix')
    if baseline.get('cheat_inherited'):
        raise ValueError('A cheat-tainted run cannot be exported as a normal route')
    closed = json.loads((run / 'exit.json').read_text())
    # Not exit.json alone: ledger rows, actions, marker and baseline count too.
    if closed.get('cheat_tainted') or cheat_classification(run, strict=False)['cheat_tainted']:
        raise ValueError('A cheat-tainted run cannot be exported as a normal route')
    if closed['status'] != 'closed' or closed['emulator_exit_code'] != 0:
        raise ValueError('Export requires a successfully closed capture')
    commands = []
    pending = None
    for row in rows(run / 'actions.jsonl'):
        if row.get('status') == 'started':
            if pending is not None:
                raise ValueError('Overlapping started actions')
            pending = row
        elif row.get('status') == 'captured':
            if pending is None or pending['segment'] != row['segment']:
                raise ValueError('Unpaired captured action')
            key = pending['key']
            if 'hold_frames' not in pending:
                raise ValueError('Action hold duration is missing; cannot reconstruct input')
            hold = pending['hold_frames']
            count = pending['release_frames']
            validate_action(key, count, hold)
            if row['end_core_frame'] - pending['start_core_frame'] + 1 != hold + count:
                raise ValueError('Action frame count mismatch')
            commands.append(f'{key} {count}' + (f' {hold}' if hold != default_hold(key) else ''))
            pending = None
    if pending is not None:
        raise ValueError('Incomplete action cannot be exported as a finished route')
    text = '\n'.join(commands) + '\n'
    parse_inputs(text)
    return text


def verify_run(run):
    """Verify closed capture, binary identity, ledger, and every unique PNG."""
    baseline = json.loads((run / 'baseline.json').read_text())
    closed = json.loads((run / 'exit.json').read_text())
    if closed['status'] != 'closed' or closed['emulator_exit_code'] != 0:
        raise ValueError(f'Capture did not close successfully: {run}')
    if sha(run / 'baseline.gba') != baseline['rom_sha256']:
        raise ValueError('Captured ROM hash mismatch')
    checkpoint_path = run / 'resume.checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text())
    for key in ('rom_sha256', 'harness_sha256', 'libmgba_sha256'):
        if checkpoint[key] != baseline[key]:
            raise ValueError(f'Checkpoint identity mismatch: {key}')
    # This verifies ledger SHA, frame continuity/end frame, and all PNG pixels.
    verify_parent(checkpoint_path, checkpoint)
    state = (run / checkpoint['state']).resolve()
    if not state.is_relative_to(run.resolve()) or sha(state) != checkpoint['state_sha256']:
        raise ValueError('Checkpoint state mismatch')
    if checkpoint['core_frame'] != closed['committed_core_frame'] or checkpoint['core_frame'] != closed['last_observed_core_frame']:
        raise ValueError('Shutdown frame mismatch')
    if checkpoint['ledger_bytes'] != (run / 'frames.jsonl').stat().st_size:
        raise ValueError('Uncommitted ledger suffix')
    seen = set()
    count = 0
    for row in rows(run / 'frames.jsonl'):
        digest = row['rgb_sha256']
        if row['image'] != f'frames/{digest}.png' or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid image identity')
        seen.add(digest)  # verify_parent already decoded and verified each PNG.
        count += 1
    if not count:
        raise ValueError('Empty capture cannot establish a replay result')
    return {'frames': count, 'unique_pngs': len(seen), 'baseline': baseline,
            'cheat': cheat_classification(run, checkpoint)}


def compare_ledgers(left, right):
    changed = total = 0
    ranges = []
    opened = None
    for old, new in itertools.zip_longest(rows(left), rows(right)):
        if old is None or new is None:
            raise ValueError('Capture frame counts differ; route comparison is not aligned')
        if (old['core_frame'], old['keys']) != (new['core_frame'], new['keys']):
            raise ValueError('Frame/input sequence mismatch; comparison is not aligned')
        total += 1
        if old['rgb_sha256'] != new['rgb_sha256']:
            changed += 1
            if opened is None:
                opened = {'first_frame': new['core_frame'], 'last_frame': new['core_frame'],
                          'reference_image': old['image'], 'candidate_image': new['image']}
                ranges.append(opened)
            else:
                opened['last_frame'] = new['core_frame']
        else:
            opened = None
    return {'frames_compared': total, 'changed_frames': changed, 'changed_ranges': ranges,
            'status': 'identical_to_reference' if not changed else 'visual_review_required',
            'translation_correctness': 'not established by pixel comparison'}


def compare_runs(reference, candidate):
    if reference.resolve() == candidate.resolve():
        raise ValueError('Reference and candidate must be distinct runs')
    for run in (reference, candidate):
        baseline = json.loads((run / 'baseline.json').read_text())
        if baseline['initial_core_frame'] != 0 or baseline.get('parent_checkpoint'):
            raise ValueError('Comparison requires cold-boot runs, not resumed suffixes')
    old, new = verify_run(reference), verify_run(candidate)
    for record in (old, new):
        if record['baseline']['initial_core_frame'] != 0 or record['baseline'].get('parent_checkpoint'):
            raise ValueError('Comparison requires cold-boot runs, not resumed suffixes')
    for key in ('harness_sha256', 'libmgba_sha256', 'initial_core_frame'):
        if old['baseline'][key] != new['baseline'][key]:
            raise ValueError(f'Incompatible reference: {key}')
    result = compare_ledgers(reference / 'frames.jsonl', candidate / 'frames.jsonl')
    result.update(reference=str(reference.resolve()), candidate=str(candidate.resolve()),
                  reference_rom_sha256=old['baseline']['rom_sha256'],
                  candidate_rom_sha256=new['baseline']['rom_sha256'],
                  reference_cheat=old['cheat'], candidate_cheat=new['cheat'])
    tainted = old['cheat']['cheat_tainted'] or new['cheat']['cheat_tainted']
    result['normal_play_evidence'] = not tainted
    if tainted:
        # Excluded from normal-play evidence: the status itself says so.
        result['pixel_status'] = result['status']
        result['status'] = 'cheat_tainted_' + result['status']
    return result


def run_replays(args):
    commands = parse_inputs(args.inputs.read_text())
    route = ''.join(' '.join(map(str, command)) + '\n' for command in commands)
    identity = {'rom_sha256': sha(args.rom), 'harness_sha256': sha(args.harness),
                'libmgba_sha256': sha(Path('/opt/homebrew/lib/libmgba.dylib').resolve()),
                'runner_sha256': sha(Path(__file__)),
                'inputs_sha256': hashlib.sha256(route.encode()).hexdigest()}
    if args.reference:
        verified = verify_run(args.reference)
        if verified['cheat']['cheat_tainted']:
            raise ValueError('A cheat-tainted reference cannot anchor a normal replay')
        if export_inputs(args.reference) != route:
            raise ValueError('Reference route differs from requested inputs')
        for key in ('harness_sha256', 'libmgba_sha256'):
            if verified['baseline'][key] != identity[key]:
                raise ValueError(f'Reference binary mismatch: {key}')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'inputs.txt').write_text(route)
    summary = {'status': 'running', **identity, 'runs': [],
               'reference_mode': 'external' if args.reference else 'first_run_unreviewed',
               'min_free_gib': args.min_free_gib, 'run_timeout_seconds': args.run_timeout_seconds,
               'scope': 'recorded route only; all frames captured; visual review separate'}
    save_json(args.out / 'summary.json', summary)
    reference = args.reference
    try:
        for repeat in range(1, args.repeat + 1):
            if (sha(args.rom) != identity['rom_sha256'] or sha(args.harness) != identity['harness_sha256']
                    or sha(Path('/opt/homebrew/lib/libmgba.dylib').resolve()) != identity['libmgba_sha256']):
                raise ValueError('Input binary changed during repeated replay')
            run = args.out / f'run_{repeat:03d}'
            command = [sys.executable, str(ROOT / 'tools/playthrough_capture.py'),
                       '--rom', str(args.rom.resolve()), '--harness', str(args.harness.resolve()),
                       '--out', str(run.resolve()), '--min-free-gib', str(args.min_free_gib)]
            with (args.out / f'run_{repeat:03d}.log').open('w') as log:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True,
                                           stdout=log, stderr=subprocess.STDOUT, cwd=ROOT,
                                           start_new_session=True)
                try:
                    summary['active_process_group'] = process.pid
                    save_json(args.out / 'summary.json', summary)
                    process.communicate(route + 'quit\n', timeout=args.run_timeout_seconds)
                except BaseException:
                    if process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGINT)
                        except ProcessLookupError:
                            pass
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            process.wait()
                    raise
                finally:
                    summary['active_process_group'] = None
            if process.returncode:
                raise RuntimeError(f'Capture failed ({process.returncode}); see run_{repeat:03d}.log')
            if export_inputs(run) != route:
                raise ValueError('Completed actions differ from requested route')
            captured_identity = json.loads((run / 'baseline.json').read_text())
            if any(captured_identity[key] != identity[key] for key in ('rom_sha256', 'harness_sha256', 'libmgba_sha256')):
                raise ValueError('Captured binaries differ from requested identities')
            if reference:
                result = compare_runs(reference, run)
                save_json(run / 'comparison.json', result)
                summary['runs'].append({'run': str(run), 'status': result['status'],
                                        'changed_frames': result['changed_frames'],
                                        'report': str(run / 'comparison.json')})
                if result['changed_frames']:
                    summary['status'] = 'visual_review_required'
                    save_json(args.out / 'summary.json', summary)
                    return 2
            else:
                verified = verify_run(run)
                summary['runs'].append({'run': str(run), 'status': 'captured_unreviewed',
                                        'frames': verified['frames']})
                reference = run
            save_json(args.out / 'summary.json', summary)
        summary['status'] = ('identical_to_external_reference' if args.reference else
                             'deterministic_against_unreviewed_first_run' if args.repeat > 1 else
                             'captured_only_no_comparison')
        save_json(args.out / 'summary.json', summary)
        return 0
    except BaseException as exc:
        summary.update(status='failed', error=str(exc), error_type=type(exc).__name__)
        save_json(args.out / 'summary.json', summary)
        raise


def main():
    parser = UsageParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    export = sub.add_parser('export')
    export.add_argument('--run', type=Path, required=True)
    export.add_argument('--out', type=Path, required=True)
    compare = sub.add_parser('compare')
    compare.add_argument('--reference', type=Path, required=True)
    compare.add_argument('--candidate', type=Path, required=True)
    compare.add_argument('--out', type=Path, required=True)
    compare.add_argument('--wait-seconds', type=float, default=0,
                         help='Locally wait for both captures to close before comparing')
    run = sub.add_parser('run')
    for name in ('rom', 'harness', 'inputs', 'out'):
        run.add_argument('--' + name, type=Path, required=True)
    run.add_argument('--reference', type=Path)
    run.add_argument('--repeat', type=int, default=1)
    run.add_argument('--min-free-gib', type=float, default=15)
    run.add_argument('--run-timeout-seconds', type=float, default=21600)
    args = parser.parse_args()
    if args.operation == 'export':
        if verify_run(args.run)['cheat']['cheat_tainted']:
            raise SystemExit('A cheat-tainted or provenance-unverifiable run cannot be exported as a normal route')
        text = export_inputs(args.run)
        with args.out.open('x') as stream:
            stream.write(text)
        print(json.dumps({'commands': len(parse_inputs(text)), 'inputs': str(args.out)}))
        return 0
    if args.operation == 'compare':
        if args.out.exists():
            parser.error('Comparison output already exists; choose a new path')
        if not math.isfinite(args.wait_seconds) or args.wait_seconds < 0:
            parser.error('wait-seconds must be finite and >= 0')
        deadline = time.monotonic() + args.wait_seconds
        while not all((p / 'exit.json').exists() for p in (args.reference, args.candidate)):
            if time.monotonic() >= deadline:
                parser.error('Captures have not closed; comparison was not performed')
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        result = compare_runs(args.reference, args.candidate)
        save_json(args.out, result)
        print(json.dumps({k: result[k] for k in ('status', 'frames_compared', 'changed_frames')}))
        return 2 if result['changed_frames'] else 0
    if args.repeat < 1 or not math.isfinite(args.min_free_gib) or args.min_free_gib < 1:
        parser.error('repeat and min-free-gib must be >= 1')
    if not math.isfinite(args.run_timeout_seconds) or args.run_timeout_seconds <= 0:
        parser.error('run-timeout-seconds must be finite and positive')
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    code = run_replays(args)
    print((args.out / 'summary.json').read_text())
    return code


if __name__ == '__main__':
    raise SystemExit(main())
