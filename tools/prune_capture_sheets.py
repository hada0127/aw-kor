"""Remove only reproducible contact sheets from a cleanly closed capture.

Individual screenshots, source frames, ledgers and states are never removed.
Every removed sheet has a fsynced reconstruction receipt, including RGB hashes.
Explicit references in docs/data are retained. Default requires a CLOSED run.
Opt-in committed-prefix mode permits recorder append only; concurrent evidence
reference writers or past-artifact changes are not supported.
"""
import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, features, __version__ as pillow_version
from recompress_closed_frames import unused, identity, sync_dir
from playthrough_capture import ROOT, sha, save_json


def reference_names():
    command = ['rg', '--no-ignore', '--hidden', '-o', '--with-filename',
               r'[0-9]+_[A-Z]+_[0-9]+_sheet\.png', str(ROOT)]
    for suffix in ('md', 'json', 'jsonl', 'txt', 'log', 'csv', 'tsv'):
        command.extend(['--glob', '*.' + suffix])
    for excluded in ('**/actions.jsonl', '**/frames.jsonl', '**/emulator.log',
                     '**/.git/**', '**/node_modules/**', '**/frames/**'):
        command.extend(['--glob', '!' + excluded])
    # These same two files are already ignored below by verified plan kind.
    # Avoid scanning their large reconstruction receipts before discarding hits.
    excluded_plans = {}
    for plan_path in (ROOT / 'temp').glob('*/plan.json'):
        # Unusual names stay in the complete scan; never expand a glob wildcard.
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', plan_path.parent.name):
            continue
        try:
            if plan_path.resolve() != plan_path or not stat.S_ISREG(plan_path.lstat().st_mode):
                continue
            stamp = identity(plan_path)
            if json.loads(plan_path.read_text()).get('kind') != 'capture-sheet-pruning-v1':
                continue
            if identity(plan_path) != stamp:
                raise ValueError('Prune plan changed while classifying references')
            excluded_plans[plan_path] = stamp
            for name in ('plan.json', 'receipts.jsonl'):
                command.extend(['--glob', '!/' + str((plan_path.parent / name).relative_to(ROOT))])
        except (OSError, json.JSONDecodeError):
            continue
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if any(identity(path) != stamp for path, stamp in excluded_plans.items()):
        raise ValueError('Prune plan changed during reference scan')
    if result.returncode not in (0, 1) or result.stderr:
        raise ValueError('Reference scan failed')
    names = set()
    own_dirs = {}
    for line in result.stdout.splitlines():
        filename, name = line.rsplit(':', 1)
        path = Path(filename)
        if path.name in ('plan.json', 'receipts.jsonl') and path.is_relative_to(ROOT / 'temp'):
            if path.parent not in own_dirs:
                try:
                    plan = json.loads((path.parent / 'plan.json').read_text())
                    own_dirs[path.parent] = plan.get('kind') == 'capture-sheet-pruning-v1'
                except (OSError, ValueError):
                    own_dirs[path.parent] = False
            if own_dirs[path.parent]:
                continue
        names.add(name)
    return names


def font_identity():
    font = ImageFont.load_default()
    if not hasattr(font.path, 'getvalue'):
        raise ValueError('Unsupported default font representation')
    return {'pillow_version': pillow_version, 'freetype_version': features.version('freetype2'),
            'font_sha256': hashlib.sha256(font.path.getvalue()).hexdigest(), 'font_size': font.size}


def sample_frames(start):
    first = start['start_core_frame']
    hold, release = start['hold_frames'], start['release_frames']
    if not (type(first) is int and first > 0 and type(hold) is int and
            type(release) is int and 0 <= hold <= 60 and 1 <= release <= 1800):
        raise ValueError('Unsupported action contract')
    return [first + offset + i for offset, count in ((0, hold), (hold, release))
            for i in range(count) if i % max(1, count // 18) == 0 or i == count - 1]


def regular(path, root):
    if path.resolve() != path or not path.is_relative_to(root):
        raise ValueError('Unexpected path')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unexpected file type or hardlink')
    return identity(path)


def frame_pixels(path, expected):
    before = regular(path, ROOT)
    pixels = cached_pixels(path, expected, before)
    if identity(path) != before:
        raise ValueError('Source frame changed')
    return pixels


@lru_cache(maxsize=256)
def cached_pixels(path, expected, before):
    with Image.open(path) as im:
        if im.size != (240, 160):
            raise ValueError('Unexpected source frame dimensions')
        pixels = im.convert('RGB').tobytes()
    if hashlib.sha256(pixels).hexdigest() != expected or identity(path) != before:
        raise ValueError('Source frame changed or RGB mismatch')
    return pixels


def reconstruct(samples):
    sheet = Image.new('RGB', (960, ((len(samples) + 3) // 4) * 180), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(samples):
        image = Image.frombytes('RGB', (240, 160), frame_pixels(Path(row['image']), row['rgb_sha256']))
        x, y = i % 4 * 240, i // 4 * 180
        sheet.paste(image, (x, y + 20))
        draw.text((x + 3, y + 3), str(row['frame']), fill='white')
    return sheet


def restore_sheet(record, destination):
    """Restore identical RGB pixels; PNG compression bytes may differ."""
    destination = Path(destination)
    if destination.resolve() != destination or not destination.is_relative_to(ROOT / 'output/qa'):
        raise ValueError('Invalid restore destination')
    image = reconstruct(record['samples'])
    if hashlib.sha256(image.tobytes()).hexdigest() != record['rgb_sha256']:
        raise ValueError('Restore RGB mismatch; check recorded Pillow version')
    (ROOT / 'temp').mkdir(exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile(dir=ROOT / 'temp', prefix='sheet_restore_', delete=False) as stream:
            stage = Path(stream.name)
            image.save(stream, format='PNG', compress_level=3)
            stream.flush(); os.fsync(stream.fileno())
        os.link(stage, destination)  # Atomic publication without replacing an existing file.
        sync_dir(destination.parent)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
            sync_dir(stage.parent)


def prepare(run, limit):
    regular(run / 'exit.json', ROOT)
    end = json.loads((run / 'exit.json').read_text())
    if not (end['status'] == 'closed' and end['emulator_exit_code'] == 0 and
            end['cleanup_errors'] == [] and end['error'] is None and
            end['last_observed_core_frame'] == end['committed_core_frame']):
        raise ValueError('Run is not cleanly closed')
    checkpoint = json.loads((run / 'resume.checkpoint.json').read_text())
    if checkpoint['core_frame'] != end['committed_core_frame']:
        raise ValueError('Closed checkpoint boundary mismatch')
    protected = reference_names()
    starts, captured = {}, []
    for line in (run / 'actions.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row.get('status') == 'started':
            if row['segment'] in starts:
                raise ValueError('Duplicate action start')
            starts[row['segment']] = row
        elif row.get('status') == 'captured':
            captured.append(row)
    plans = []
    for row in captured[20:-20]:
        if row.get('sheet') is None:
            continue
        start = starts[row['segment']]
        expected_end = start['start_core_frame'] + start['hold_frames'] + start['release_frames'] - 1
        if row['end_core_frame'] != expected_end or row['start_core_frame'] != start['start_core_frame']:
            raise ValueError('Action frame boundary mismatch')
        name = f"{row['segment']:04d}_{start['key']}_{expected_end:07d}"
        path = run / (name + '_sheet.png')
        if Path(row['sheet']) != path or Path(row['png']) != run / (name + '.png'):
            raise ValueError('Action artifact path mismatch')
        if not path.exists() or path.name in protected:
            continue
        regular(path, run)
        regular(Path(row['png']), run)
        regular(Path(row['checkpoint']), run)
        plans.append({'sheet': str(path), 'endpoint': row['png'],
                      'checkpoint': row['checkpoint'], 'frames': sample_frames(start)})
        if len(plans) >= limit:
            break
    wanted = {frame for p in plans for frame in p['frames']}
    samples = {}
    ledger = run / 'frames.jsonl'
    before = regular(ledger, run)
    digest = hashlib.sha256()
    size = 0
    with ledger.open('rb') as stream:
        for line in stream:
            size += len(line)
            digest.update(line)
            row = json.loads(line)
            frame = row['core_frame']
            if frame in wanted:
                rgb = row['rgb_sha256']
                if not re.fullmatch('[0-9a-f]{64}', rgb) or row['image'] != f'frames/{rgb}.png' or frame in samples:
                    raise ValueError('Invalid sampled frame')
                samples[frame] = {'frame': frame, 'image': str(run / row['image']), 'rgb_sha256': rgb}
    if identity(ledger) != before or size != checkpoint['ledger_bytes'] or digest.hexdigest() != checkpoint['ledger_sha256']:
        raise ValueError('Ledger integrity mismatch')
    if samples.keys() != wanted:
        raise ValueError('Missing source frames')
    for plan in plans:
        plan['samples'] = [samples[f] for f in plan.pop('frames')]
    return plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--restore', type=Path, help='Restore missing sheets from fsynced receipts, with identical RGB pixels')
    parser.add_argument('--max-sheets', type=int, default=3000)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--guard-batch-size', type=int, default=50, help='Committed-prefix batch size: 50 through 200')
    parser.add_argument('--committed-prefix', action='store_true', help='Opt in to old committed sheets from an append-only live or failed run')
    args = parser.parse_args()
    if args.guard_batch_size != 50 and not args.committed_prefix:
        parser.error("nondefault guard batch requires --committed-prefix")
    if not 50 <= args.guard_batch_size <= 200:
        parser.error("guard batch size must be 50 through 200")
    if args.restore:
        if args.run or args.work or args.apply or args.committed_prefix:
            parser.error('--restore cannot be combined with pruning options')
        receipt = args.restore.resolve()
        if not receipt.is_relative_to(ROOT / 'temp'):
            raise ValueError('Invalid restore receipt path')
        plan = json.loads((receipt.parent / 'plan.json').read_text())
        if plan['font'] != font_identity():
            raise ValueError('Restore requires recorded Pillow/FreeType/default font environment')
        records = {}
        for line in receipt.read_text().splitlines():
            row = json.loads(line)
            records[row['sheet']] = row
        restored = 0
        for destination, row in records.items():
            if Path(destination).exists():
                continue
            restore_sheet(row, Path(destination)); restored += 1
        print(json.dumps({'restored': restored, 'identity': 'RGB pixels; PNG compression bytes may differ'}))
        return
    if args.run is None or args.work is None:
        parser.error('--run and --work are required for pruning')
    run = args.run.resolve()
    work = args.work.resolve()
    if not run.is_relative_to(ROOT / 'output/qa') or not work.is_relative_to(ROOT / 'temp') or args.max_sheets < 1:
        raise ValueError('Invalid scope')
    prefix_guard = None
    if args.committed_prefix:
        from live_sheet_prefix import prepare as prepare_prefix, batch_guard
        plans, prefix_guard = prepare_prefix(run, args.max_sheets)
    else:
        plans = prepare(run, args.max_sheets)
    work.mkdir(parents=True, exist_ok=False)
    sync_dir(work.parent)
    protected = {} if prefix_guard else {name: sha(run / name) for name in ('exit.json', 'resume.checkpoint.json', 'actions.jsonl', 'frames.jsonl')}
    save_json(work / 'plan.json', {'kind': 'capture-sheet-pruning-v1', 'run': str(run), 'count': len(plans), 'protected': protected,
        'font': font_identity(), 'tool_sha256': sha(Path(__file__)),
        'prefix_evidence': prefix_guard.evidence() if prefix_guard else None,
        'prefix_tool_sha256': sha(ROOT / 'tools/live_sheet_prefix.py') if prefix_guard else None,
        'restoration': 'RGB-identical; PNG bytes may differ. Pending visual reviews remain pending.',
        'reference_scope': 'Repository md/json/jsonl/txt/log/csv/tsv except generated actions/frames/emulator logs. No concurrent evidence writer supported.'})
    guard_batch_size = args.guard_batch_size if prefix_guard else 50
    saved = 0
    with (work / 'receipts.jsonl').open('x') as receipts:
        sync_dir(work)
        for index, plan in enumerate(plans):
            if index % guard_batch_size == 0:
                if prefix_guard:
                    live_references = batch_guard(plans[index:index + guard_batch_size], prefix_guard)
                else:
                    unused([Path(p['sheet']) for p in plans[index:index + 50]])
            path = Path(plan['sheet'])
            if prefix_guard and path.name in live_references:
                continue
            before = regular(path, run)
            rebuilt = reconstruct(plan['samples'])
            with Image.open(path) as original:
                if original.mode != 'RGB' or original.size != rebuilt.size or original.tobytes() != rebuilt.tobytes():
                    raise ValueError('Contact sheet reconstruction mismatch')
            plan.update(status='verified_original_present', source_sha256=sha(path),
                        rgb_sha256=hashlib.sha256(rebuilt.tobytes()).hexdigest(), bytes=path.stat().st_size)
            receipts.write(json.dumps(plan) + '\n'); receipts.flush(); os.fsync(receipts.fileno())
            if args.apply:
                if prefix_guard:
                    prefix_guard.check_plan(plan)
                if identity(path) != before:
                    raise ValueError('Sheet changed before removal')
                path.unlink(); saved += plan['bytes']
                plan['status'] = 'removed_reconstructible_sheet'
                receipts.write(json.dumps(plan) + '\n'); receipts.flush(); os.fsync(receipts.fileno())
            if (index + 1) % 100 == 0:
                sync_dir(run)
                print(json.dumps({'processed': index + 1, 'saved_bytes': saved}), flush=True)
    sync_dir(run); sync_dir(work)
    if prefix_guard:
        prefix_guard.check()
    if any(sha(run / name) != value for name, value in protected.items()):
        raise ValueError('Protected evidence changed')
    print(json.dumps({'processed': len(plans), 'saved_bytes': saved, 'protected_unchanged': True}), flush=True)


if __name__ == '__main__':
    main()
