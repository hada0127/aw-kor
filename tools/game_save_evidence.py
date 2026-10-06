"""Export an unchanged cartridge save from a recorded checkpoint, with provenance.

The resulting file is a normal game save, not a cross-ROM emulator state. Loading
it never verifies scenes preceding the new boot, nor the patched scene itself.

Two receipt kinds exist. ``cartridge-save-from-recorded-checkpoint-v1`` keeps a
live link to its source checkpoint and re-verifies that run's frame chain on use.
``cartridge-save-anchored-v1`` (2026-10-06 evidence-chain cut) is self-contained:
it records the source checkpoint only as information, and verification never
opens the source checkpoint, its run directory or any ancestor frame.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess

from playthrough_capture import (ROOT, sha, save_json, verify_parent, checkpoint_cheat_tainted,
                                 run_cheat_evidence, evidence_tainted)
from emu_platform import LIBMGBA, harness_env


VALID_SAVE_SIZES = {512, 8192, 32768, 65536, 131072}
LEGACY_KIND = 'cartridge-save-from-recorded-checkpoint-v1'
ANCHORED_KIND = 'cartridge-save-anchored-v1'
RECEIPT_KINDS = {LEGACY_KIND, ANCHORED_KIND}
STORAGE_PATTERN = rb'(FLASH1M|FLASH512|FLASH|SRAM_F|SRAM|EEPROM)_V[0-9]{3}'
STORAGE_CAPACITIES = {b'FLASH1M': {131072}, b'FLASH512': {65536}, b'FLASH': {65536},
                      b'SRAM': {32768}, b'SRAM_F': {32768}, b'EEPROM': {512, 8192}}
SOURCE_CHAIN_MODES = {'full-frame-chain', 'checkpoint-binaries-only'}
# How an exporter established the source's cheat state (2026-10-07). An explicit
# cheat_tainted=false is accepted only with one of these; anything else that cannot
# be checked against an available source counts as cheat-tainted (fail closed).
CHEAT_PROVENANCE_MODES = {'full-frame-chain', 'checkpoint-ledger-scan'}
CHEAT_REGISTRY = ROOT / 'data' / 'game_save_cheat_provenance.json'
# Local append-only log of receipt digests written by this tool at export time.
ATTESTATION_LOG = ROOT / 'output' / 'qa' / 'game_save_attestations.jsonl'


def load_cheat_registry(path=None):
    try:
        data = json.loads(Path(path or CHEAT_REGISTRY).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    entries = data.get('receipts')
    if not isinstance(entries, dict):
        raise ValueError('Game-save cheat provenance registry is malformed')
    for key, entry in entries.items():
        if (not is_sha256(key) or not isinstance(entry, dict) or type(entry.get('cheat_tainted')) is not bool
                or not isinstance(entry.get('basis'), str) or not entry['basis'].strip()):
            raise ValueError('Game-save cheat provenance registry entry is malformed')
    return entries


def source_cheat_state(checkpoint_path, checkpoint, _depth=0):
    """Cheat state of a source checkpoint from its run directory and ancestry metadata.

    Local evidence: checkpoint flag, baseline inheritance, ledger prefix rows,
    the sticky marker and dispatch rows. Ancestry (no frame images needed): the
    parent checkpoint (recursively) and the initial game-save receipt.
    True: tainted. False: verified clean. None: something could not be resolved.
    Raises when recorded evidence shows cheats but the checkpoint lost its flag.
    """
    if _depth > 128:
        return None
    checkpoint_path = Path(checkpoint_path)
    root = checkpoint_path.parent
    evidence = run_cheat_evidence(root, checkpoint)
    positive = any(evidence[k] is True for k in ('baseline_inherited', 'ledger_rows', 'actions_events',
                                                 'taint_marker'))
    unresolved = (not evidence['ledger_verified']
                  or (evidence_tainted(evidence) and not positive and not evidence['checkpoint_flag']))
    ancestor = False
    try:
        baseline = json.loads((root / 'baseline.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        baseline = None
        unresolved = True
    if baseline is not None and baseline.get('parent_checkpoint'):
        parent_path = Path(baseline['parent_checkpoint'])
        try:
            ok = parent_path.is_file() and sha(parent_path) == baseline.get('parent_checkpoint_sha256')
        except OSError:
            ok = False
        state = source_cheat_state(parent_path, json.loads(parent_path.read_text()), _depth + 1) if ok else None
        if state is None:
            unresolved = True
        elif state:
            ancestor = True
    if baseline is not None and baseline.get('initial_game_save'):
        seed = baseline['initial_game_save']
        receipt_path = root / seed.get('receipt', 'game_save.json')
        try:
            ok = receipt_path.is_file() and sha(receipt_path) == seed.get('receipt_sha256')
        except OSError:
            ok = False
        if not ok:
            unresolved = True
        elif receipt_cheat_status(json.loads(receipt_path.read_text()), seed['receipt_sha256'],
                                  _depth=_depth + 1)['tainted']:
            ancestor = True
    if (positive or ancestor) and not evidence['checkpoint_flag']:
        raise ValueError('Cheat taint dropped from source checkpoint')
    if evidence['checkpoint_flag'] or positive or ancestor:
        return True
    return None if unresolved else False


def attestation_log():
    return Path(ATTESTATION_LOG)


def record_attestation(receipt_path, record):
    """Append the exported receipt digest to the local append-only attestation log."""
    log = attestation_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    row = {'receipt_sha256': sha(receipt_path), 'kind': record['kind'],
           'cheat_tainted': record['cheat_tainted'], 'cheat_provenance': record['cheat_provenance'],
           'source_checkpoint_sha256': record.get('source_checkpoint_sha256'),
           'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    with log.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def attested_clean(receipt_sha256):
    """True only if this exact receipt digest was attested clean at export time."""
    try:
        lines = attestation_log().read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return False
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('receipt_sha256') == receipt_sha256:
            rows.append(row)
    return bool(rows) and all(row.get('cheat_tainted') is False for row in rows)


def receipt_cheat_status(record, receipt_sha256, *, _depth=0):
    """Cheat provenance of a game-save receipt: {'tainted': bool, 'basis': str}.

    Order: receipt flag true; available source checkpoint with resolvable
    ancestry (must agree with the flag); otherwise an explicit or implied clean
    state is accepted only for this exact receipt digest via the reviewed
    registry or the export-time attestation log. Everything else is tainted.
    """
    flag = record.get('cheat_tainted')
    if 'cheat_tainted' in record and type(flag) is not bool:
        raise ValueError('Game-save cheat flag is malformed')
    if flag is False and record.get('cheat_provenance') not in CHEAT_PROVENANCE_MODES:
        raise ValueError('Game-save cheat flag false without exporter provenance')
    source_state = None
    source = Path(record['source_checkpoint']) if isinstance(record.get('source_checkpoint'), str) else None
    try:
        if source is not None and source.is_file() and sha(source) == record.get('source_checkpoint_sha256'):
            source_state = source_cheat_state(source, json.loads(source.read_text()), _depth)
    except OSError:
        source_state = None
    if source_state is True and flag is not True:
        raise ValueError('Cheat taint dropped from game save')
    if flag is True:
        return {'tainted': True, 'basis': 'receipt-flag'}
    if source_state is False:
        return {'tainted': False, 'basis': 'source-checkpoint-ledger'}
    entry = load_cheat_registry().get(receipt_sha256)
    if entry is not None:
        return {'tainted': entry['cheat_tainted'], 'basis': 'registry'}
    if flag is False and attested_clean(receipt_sha256):
        return {'tainted': False, 'basis': 'export-attestation'}
    return {'tainted': True, 'basis': 'unverifiable'}


def rom_storage_types(rom):
    return set(re.findall(STORAGE_PATTERN, Path(rom).read_bytes()))


def verify_migration_storage(source_rom, target_rom, save_size, *, source_types=None):
    """Compare save storage types; an anchored receipt supplies its recorded types."""
    source = set(source_types) if source_types is not None else rom_storage_types(source_rom)
    target = rom_storage_types(target_rom)
    if len(source) != 1 or target != source:
        raise ValueError('Save migration source/target storage types differ or are ambiguous')
    if save_size not in STORAGE_CAPACITIES[next(iter(source))]:
        raise ValueError('Save migration size does not match target storage type')


def is_sha256(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def check_rom_binding(record, expected_rom_sha256, migration_source_sha256):
    if migration_source_sha256 is not None:
        if (not is_sha256(migration_source_sha256) or not is_sha256(expected_rom_sha256)
                or migration_source_sha256 == expected_rom_sha256):
            raise ValueError('Save migration requires distinct valid source and target ROM hashes')
        if record.get('rom_sha256') != migration_source_sha256:
            raise ValueError('Game-save does not match declared migration source ROM')
    elif expected_rom_sha256 is not None and record.get('rom_sha256') != expected_rom_sha256:
        raise ValueError('Game-save ROM does not match target ROM')


def verify_anchored_record(record, saved, *, expected_harness_sha256, expected_libmgba_sha256):
    """Self-contained anchored checks. Never opens the source checkpoint or its run."""
    hashes = ('save_sha256', 'rom_sha256', 'libmgba_sha256', 'harness_sha256',
              'source_checkpoint_sha256', 'source_state_sha256')
    if (record.get('kind') != ANCHORED_KIND or record.get('schema') != 1
            or any(not is_sha256(record.get(k)) for k in hashes)
            or type(record.get('save_size')) is not int or type(record.get('source_core_frame')) is not int
            or not isinstance(record.get('save'), str) or not isinstance(record.get('source_checkpoint'), str)
            or not isinstance(record.get('created_at'), str) or not record['created_at']
            or not isinstance(record.get('reason'), str) or not record['reason'].strip()
            or record.get('source_chain_verification') not in SOURCE_CHAIN_MODES
            or not isinstance(record.get('save_storage'), list) or len(record['save_storage']) != 1
            or record['save_storage'][0] not in {k.decode() for k in STORAGE_CAPACITIES}):
        raise ValueError('Anchored game-save receipt is malformed')
    if 'cheat_tainted' in record and type(record['cheat_tainted']) is not bool:
        raise ValueError('Anchored game-save cheat flag is malformed')
    if not is_sha256(expected_harness_sha256) or not is_sha256(expected_libmgba_sha256):
        raise ValueError('Anchored game-save verification requires harness and emulator library hashes')
    if record['harness_sha256'] != expected_harness_sha256:
        raise ValueError('Anchored game-save harness mismatch')
    if record['libmgba_sha256'] != expected_libmgba_sha256:
        raise ValueError('Anchored game-save emulator library mismatch')
    size = saved.stat().st_size
    if (size not in VALID_SAVE_SIZES or size != record['save_size']
            or size not in STORAGE_CAPACITIES[record['save_storage'][0].encode()]
            or sha(saved) != record['save_sha256']):
        raise ValueError('Game-save bytes do not match receipt')
    if len(set(saved.read_bytes())) <= 1:
        raise ValueError('Game-save contains only uniform fill bytes')


def contained_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('Save evidence path escapes its directory')
    if not path.is_file():
        raise ValueError("Save evidence is not a regular file")
    return path


def verify_receipt(path, *, verify_frames=True, expected_rom_sha256=None,
                   migration_source_sha256=None, frame_cache=None,
                   expected_harness_sha256=None, expected_libmgba_sha256=None):
    path = Path(path).resolve()
    record = json.loads(path.read_text())
    if record.get('kind') not in RECEIPT_KINDS:
        raise ValueError('Unknown game-save receipt')
    check_rom_binding(record, expected_rom_sha256, migration_source_sha256)
    if not isinstance(record.get('save'), str):
        raise ValueError('Game-save receipt is malformed: save')
    saved = contained_file(path.parent, record['save'])
    if record['kind'] == ANCHORED_KIND:
        # Evidence-chain cut: verify_frames/frame_cache intentionally unused.
        verify_anchored_record(record, saved, expected_harness_sha256=expected_harness_sha256,
                               expected_libmgba_sha256=expected_libmgba_sha256)
        receipt_cheat_status(record, sha(path))   # raises on dropped/malformed provenance
        return saved, record
    if saved.stat().st_size not in VALID_SAVE_SIZES or sha(saved) != record['save_sha256']:
        raise ValueError('Game-save bytes do not match receipt')
    if len(set(saved.read_bytes())) <= 1:
        raise ValueError('Game-save contains only uniform fill bytes')
    cp = Path(record['source_checkpoint']).resolve()
    if sha(cp) != record['source_checkpoint_sha256']:
        raise ValueError('Source checkpoint changed')
    checkpoint = json.loads(cp.read_text())
    for key in ('rom_sha256', 'libmgba_sha256', 'core_frame', 'state_sha256'):
        if checkpoint[key] != record[key]:
            raise ValueError(f'Game-save origin mismatch: {key}')
    receipt_cheat_status(record, sha(path))   # raises on dropped/malformed provenance
    if record['source_harness_sha256'] != checkpoint['harness_sha256']:
        raise ValueError('Game-save source harness mismatch')
    state = contained_file(cp.parent, checkpoint['state'])
    if sha(state) != checkpoint['state_sha256'] or sha(cp.parent / 'baseline.gba') != checkpoint['rom_sha256']:
        raise ValueError('Game-save source binary changed')
    if b'FLASH1M_V' in (cp.parent / 'baseline.gba').read_bytes() and saved.stat().st_size != 131072:
        raise ValueError('FLASH1M save must contain exactly 131072 bytes')
    if verify_frames:
        verify_parent(cp, checkpoint, frame_cache=frame_cache)
    return saved, record


def verify_recorded_seed(root, baseline):
    seed = baseline.get('initial_game_save')
    if not seed:
        return
    root = Path(root)
    for name, expected in ((seed['save'], seed['save_sha256']),
                           (seed['receipt'], seed['receipt_sha256']),
                           (seed['loaded_copy'], seed['save_sha256'])):
        if sha(contained_file(root, name)) != expected:
            raise ValueError('Recorded game-save seed changed')
    receipt = json.loads(contained_file(root, seed['receipt']).read_text())
    if receipt.get('kind') not in RECEIPT_KINDS:
        raise ValueError('Unknown recorded game-save receipt')
    if receipt['save_sha256'] != seed['save_sha256']:
        raise ValueError('Recorded game-save receipt mismatch')
    port = seed.get('emulator_port')
    expected_harness, expected_lib = baseline.get('harness_sha256'), baseline.get('libmgba_sha256')
    if port is not None:
        # Explicit --game-save-emulator-port run: the receipt keeps its source identity.
        if (receipt['kind'] != ANCHORED_KIND or not isinstance(port, dict)
                or set(port) != {'source_harness_sha256', 'source_libmgba_sha256'}
                or port['source_harness_sha256'] != receipt.get('harness_sha256')
                or port['source_libmgba_sha256'] != receipt.get('libmgba_sha256')
                or (port['source_harness_sha256'] == expected_harness
                    and port['source_libmgba_sha256'] == expected_lib)):
            raise ValueError('Recorded game-save emulator port is malformed or mismatched')
        expected_harness, expected_lib = port['source_harness_sha256'], port['source_libmgba_sha256']
    if receipt['kind'] == ANCHORED_KIND:
        # The anchored receipt is this run's chain root: check only local copies.
        verify_anchored_record(receipt, contained_file(root, seed['save']),
                               expected_harness_sha256=expected_harness,
                               expected_libmgba_sha256=expected_lib)
    # Raises on malformed/dropped flags; verify_parent enforces inheritance of the result.
    status = receipt_cheat_status(receipt, seed['receipt_sha256'])
    target = baseline.get('rom_sha256')
    if target and receipt['rom_sha256'] != target:
        # Older captures predate explicit migration metadata; preserve their
        # recorded byte/hash evidence without claiming this newer guard.
        legacy = baseline.get('schema_version', 1) < 4 and 'migration' not in seed
        if not legacy and seed.get('migration') != {'source_rom_sha256': receipt['rom_sha256'],
                                      'target_rom_sha256': target}:
            raise ValueError('Recorded game-save migration is missing or mismatched')
    elif seed.get('migration') is not None:
        raise ValueError('Unexpected recorded game-save migration')
    return status


def dump_checkpoint_save(checkpoint_path, checkpoint, harness, out):
    """Load the checkpoint state with the harness and dump its cartridge save unchanged."""
    rom = checkpoint_path.parent / 'baseline.gba'
    state = contained_file(checkpoint_path.parent, checkpoint['state'])
    lib = LIBMGBA.resolve()
    if sha(rom) != checkpoint['rom_sha256'] or sha(state) != checkpoint['state_sha256']:
        raise ValueError('Checkpoint ROM/state changed')
    if sha(lib) != checkpoint['libmgba_sha256']:
        raise ValueError('Export must use the recorded emulator library')
    out = out.resolve()
    for p in (out, harness.resolve()):
        if any(c.isspace() for c in str(p)):
            raise ValueError('Harness paths cannot contain whitespace')
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(rom, out / 'source.gba')
    shutil.copyfile(state, out / 'source.ss0')
    if sha(out / 'source.gba') != checkpoint['rom_sha256'] or sha(out / 'source.ss0') != checkpoint['state_sha256']:
        raise ValueError('Export source copy mismatch')
    env = harness_env()
    command = f'loadstate {out / "source.ss0"}\nframecounter\ndumpsave {out / "game.sav"}\nframecounter\nquit\n'
    result = subprocess.run([str(harness.resolve()), str(out / 'source.gba'), str(out / 'emulator.log')],
                            input=command, text=True, capture_output=True, timeout=30, env=env)
    (out / 'export.log').write_text(result.stdout + result.stderr)
    lines = result.stdout.splitlines()
    expected_frame = f'OK framecounter {checkpoint["core_frame"]}'
    if result.returncode or len(lines) != 5 or not lines[0].endswith('ok=1') or lines[1] != expected_frame or lines[3] != expected_frame or not lines[2].startswith('OK dumpsave size=') or lines[4] != 'OK quit':
        raise RuntimeError('Save export failed or advanced the emulated frame')
    saved = out / 'game.sav'
    if saved.stat().st_size not in VALID_SAVE_SIZES or saved.stat().st_size != int(lines[2].split('=')[-1]):
        raise RuntimeError('Incomplete game-save export')
    return out, saved


def export(checkpoint_path, harness, out, *, frame_cache=None, announce=True):
    checkpoint_path = checkpoint_path.resolve()
    checkpoint = json.loads(checkpoint_path.read_text())
    verify_parent(checkpoint_path, checkpoint, frame_cache=frame_cache)
    out, saved = dump_checkpoint_save(checkpoint_path, checkpoint, harness, out)
    receipt = {key: checkpoint[key] for key in ('rom_sha256', 'libmgba_sha256', 'core_frame', 'state_sha256')}
    receipt.update(kind=LEGACY_KIND, save=saved.name,
                   save_sha256=sha(saved), source_checkpoint=str(checkpoint_path),
                   source_checkpoint_sha256=sha(checkpoint_path),
                   source_harness_sha256=checkpoint['harness_sha256'], export_harness_sha256=sha(harness),
                   evidence_scope='Cartridge bytes at source frame, possibly from an earlier in-game save. Game acceptance and saved progress require observed in-game Continue; no scene or ending approval')
    # verify_parent above checked the full chain, so the checkpoint flag is authoritative.
    receipt['cheat_tainted'] = checkpoint_cheat_tainted(checkpoint)
    receipt['cheat_provenance'] = 'full-frame-chain'
    save_json(out / 'game_save.json', receipt)
    record_attestation(out / 'game_save.json', receipt)
    verify_receipt(out / 'game_save.json', verify_frames=False)
    if announce:
        print(out / 'game_save.json')
    return out / 'game_save.json'


def verify_checkpoint_binaries(checkpoint_path, checkpoint):
    """Bounded source check used when the source run's frames are no longer kept."""
    root = checkpoint_path.parent
    baseline_path = root / 'baseline.json'
    baseline = json.loads(baseline_path.read_text())
    # Same rule as verify_parent: schema>=3 checkpoints must bind their baseline.
    if (('baseline_sha256' in checkpoint or baseline.get('schema_version', 1) >= 3)
            and checkpoint.get('baseline_sha256') != sha(baseline_path)):
        raise ValueError('Source checkpoint baseline changed')
    for key in ('rom_sha256', 'harness_sha256', 'libmgba_sha256'):
        if baseline.get(key) != checkpoint.get(key):
            raise ValueError(f'Source checkpoint identity mismatch: {key}')
    inherited = baseline.get('cheat_inherited')
    if inherited not in (None, True) or ('cheat_tainted' in checkpoint and checkpoint['cheat_tainted'] is not True):
        raise ValueError('Source checkpoint cheat flags are malformed')
    if inherited is True and not checkpoint_cheat_tainted(checkpoint):
        raise ValueError('Cheat-inherited source checkpoint lost its taint')
    # True/False when the ledger prefix verifies; None (unverifiable) otherwise.
    return source_cheat_state(checkpoint_path, checkpoint)


def export_anchored(checkpoint_path, harness, out, *, reason, verify_source_frames=True,
                    frame_cache=None, announce=True):
    """Export a self-contained chain-root receipt (2026-10-06 evidence-chain cut).

    The source checkpoint is verified now (full frame chain by default) and then
    recorded only as information; later verification never needs it again.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Anchored export requires a non-empty reason')
    checkpoint_path = checkpoint_path.resolve()
    checkpoint = json.loads(checkpoint_path.read_text())
    harness_sha = sha(harness)
    if harness_sha != checkpoint['harness_sha256']:
        raise ValueError('Anchored export must use the checkpoint harness')
    if verify_source_frames:
        verify_parent(checkpoint_path, checkpoint, frame_cache=frame_cache)
        cheat_state, cheat_provenance = checkpoint_cheat_tainted(checkpoint), 'full-frame-chain'
    else:
        cheat_state = verify_checkpoint_binaries(checkpoint_path, checkpoint)
        cheat_provenance = 'checkpoint-ledger-scan' if cheat_state is not None else 'unverifiable-source-ledger'
        if cheat_state is None:
            cheat_state = True   # fail closed: frames/ledger unavailable, never normal play
    storage = rom_storage_types(checkpoint_path.parent / 'baseline.gba')
    if len(storage) != 1:
        raise ValueError('Source ROM save storage type is missing or ambiguous')
    out, saved = dump_checkpoint_save(checkpoint_path, checkpoint, harness, out)
    receipt = {'kind': ANCHORED_KIND, 'schema': 1, 'save': saved.name, 'save_sha256': sha(saved),
               'save_size': saved.stat().st_size, 'save_storage': sorted(t.decode() for t in storage),
               'rom_sha256': checkpoint['rom_sha256'], 'libmgba_sha256': checkpoint['libmgba_sha256'],
               'harness_sha256': harness_sha,
               'source_checkpoint': str(checkpoint_path), 'source_checkpoint_sha256': sha(checkpoint_path),
               'source_core_frame': checkpoint['core_frame'], 'source_state_sha256': checkpoint['state_sha256'],
               'source_chain_verification': 'full-frame-chain' if verify_source_frames else 'checkpoint-binaries-only',
               'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'reason': reason.strip(),
               'evidence_scope': 'Chain root after the 2026-10-06 evidence-chain cut. Source checkpoint fields are informational and never re-verified. Cartridge bytes only; game acceptance requires observed in-game Continue; no scene or ending approval'}
    receipt['cheat_tainted'] = bool(cheat_state)
    receipt['cheat_provenance'] = cheat_provenance
    save_json(out / 'game_save.json', receipt)
    record_attestation(out / 'game_save.json', receipt)
    verify_receipt(out / 'game_save.json', expected_rom_sha256=checkpoint['rom_sha256'],
                   expected_harness_sha256=harness_sha, expected_libmgba_sha256=checkpoint['libmgba_sha256'])
    if announce:
        print(out / 'game_save.json')
    return out / 'game_save.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--harness', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--anchored', action='store_true',
                        help='Write a self-contained cartridge-save-anchored-v1 receipt (new chain root)')
    parser.add_argument('--reason', help='Required with --anchored: short note why the chain is cut here')
    parser.add_argument('--skip-source-frame-check', action='store_true',
                        help='With --anchored: verify only the source checkpoint binaries, not its frame chain (recorded in the receipt)')
    args = parser.parse_args()
    if args.anchored:
        if not args.reason or not args.reason.strip():
            parser.error('--anchored requires --reason')
        export_anchored(args.checkpoint, args.harness, args.out, reason=args.reason,
                        verify_source_frames=not args.skip_source_frame_check)
    else:
        if args.reason or args.skip_source_frame_check:
            parser.error('--reason/--skip-source-frame-check require --anchored')
        export(args.checkpoint, args.harness, args.out)
