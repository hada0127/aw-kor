"""Export an unchanged cartridge save from a recorded checkpoint, with provenance.

The resulting file is a normal game save, not a cross-ROM emulator state. Loading
it never verifies scenes preceding the new boot, nor the patched scene itself.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess

from playthrough_capture import sha, save_json, verify_parent


VALID_SAVE_SIZES = {512, 8192, 32768, 65536, 131072}


def verify_migration_storage(source_rom, target_rom, save_size):
    pattern = rb'(FLASH1M|FLASH512|FLASH|SRAM_F|SRAM|EEPROM)_V[0-9]{3}'
    source = set(re.findall(pattern, Path(source_rom).read_bytes()))
    target = set(re.findall(pattern, Path(target_rom).read_bytes()))
    if len(source) != 1 or target != source:
        raise ValueError('Save migration source/target storage types differ or are ambiguous')
    capacities = {b'FLASH1M': {131072}, b'FLASH512': {65536}, b'FLASH': {65536},
                  b'SRAM': {32768}, b'SRAM_F': {32768}, b'EEPROM': {512, 8192}}
    if save_size not in capacities[next(iter(source))]:
        raise ValueError('Save migration size does not match target storage type')


def contained_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('Save evidence path escapes its directory')
    if not path.is_file():
        raise ValueError("Save evidence is not a regular file")
    return path


def verify_receipt(path, *, verify_frames=True, expected_rom_sha256=None,
                   migration_source_sha256=None, frame_cache=None):
    path = Path(path).resolve()
    record = json.loads(path.read_text())
    if record.get('kind') != 'cartridge-save-from-recorded-checkpoint-v1':
        raise ValueError('Unknown game-save receipt')
    if migration_source_sha256 is not None:
        if (not isinstance(migration_source_sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', migration_source_sha256)
                or not isinstance(expected_rom_sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', expected_rom_sha256)
                or migration_source_sha256 == expected_rom_sha256):
            raise ValueError('Save migration requires distinct valid source and target ROM hashes')
        if record.get('rom_sha256') != migration_source_sha256:
            raise ValueError('Game-save does not match declared migration source ROM')
    elif expected_rom_sha256 is not None and record.get('rom_sha256') != expected_rom_sha256:
        raise ValueError('Game-save ROM does not match target ROM')
    saved = contained_file(path.parent, record['save'])
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
    if receipt.get('kind') != 'cartridge-save-from-recorded-checkpoint-v1':
        raise ValueError('Unknown recorded game-save receipt')
    if receipt['save_sha256'] != seed['save_sha256']:
        raise ValueError('Recorded game-save receipt mismatch')
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


def export(checkpoint_path, harness, out, *, frame_cache=None, announce=True):
    checkpoint_path = checkpoint_path.resolve()
    checkpoint = json.loads(checkpoint_path.read_text())
    verify_parent(checkpoint_path, checkpoint, frame_cache=frame_cache)
    rom = checkpoint_path.parent / 'baseline.gba'
    state = contained_file(checkpoint_path.parent, checkpoint['state'])
    lib = Path('/opt/homebrew/lib/libmgba.dylib').resolve()
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
    env = {k: v for k, v in os.environ.items() if not k.startswith("DYLD_")}
    env['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib'
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
    receipt = {key: checkpoint[key] for key in ('rom_sha256', 'libmgba_sha256', 'core_frame', 'state_sha256')}
    receipt.update(kind='cartridge-save-from-recorded-checkpoint-v1', save=saved.name,
                   save_sha256=sha(saved), source_checkpoint=str(checkpoint_path),
                   source_checkpoint_sha256=sha(checkpoint_path),
                   source_harness_sha256=checkpoint['harness_sha256'], export_harness_sha256=sha(harness),
                   evidence_scope='Cartridge bytes at source frame, possibly from an earlier in-game save. Game acceptance and saved progress require observed in-game Continue; no scene or ending approval')
    save_json(out / 'game_save.json', receipt)
    verify_receipt(out / 'game_save.json', verify_frames=False)
    if announce:
        print(out / 'game_save.json')
    return out / 'game_save.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--harness', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    export(args.checkpoint, args.harness, args.out)
