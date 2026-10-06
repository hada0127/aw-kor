#!/usr/bin/env python3
"""Frame-exact recorder. Input: KEY RELEASE_FRAMES [HOLD_FRAMES], note TEXT, quit.

Every emulated frame maps to a lossless PNG. Identical RGB frames share files.
Each successful command ends at a verified checkpoint. Resume creates a new run;
pass the previous checkpoint.json, never an unverified diagnostic state.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import struct
import subprocess
import sys
import time
from PIL import Image, ImageDraw
from PIL import __version__ as pillow_version
import frame_png
from frame_png import encode_frame_png
from emu_platform import LIBMGBA, harness_env

KEYS = {'A': 1, 'B': 2, 'SELECT': 4, 'START': 8, 'RIGHT': 16, 'LEFT': 32,
        'UP': 64, 'DOWN': 128, 'R': 256, 'L': 512, 'NONE': 0}
ROOT = Path(__file__).resolve().parents[1]


def default_hold(key):
    return 0 if key == 'NONE' else 2


def parse_action(tokens):
    if not 1 <= len(tokens) <= 3:
        raise ValueError('Use KEY RELEASE_FRAMES [HOLD_FRAMES]')
    key = tokens[0].upper()
    count = int(tokens[1]) if len(tokens) >= 2 else 120
    hold = int(tokens[2]) if len(tokens) == 3 else default_hold(key)
    validate_action(key, count, hold)
    return key, count, hold


def validate_action(key, count, hold):
    if key not in KEYS or not isinstance(count, int) or not 1 <= count <= 1800:
        raise ValueError('Invalid key or release frame count (1..1800)')
    if not isinstance(hold, int) or (hold != 0 if key == 'NONE' else not 1 <= hold <= 120):
        raise ValueError('Hold must be 1..120 frames, or 0 for NONE')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class FrameLedger:
    """Hash the exact UTF-8 bytes written to a new, single-writer ledger.

    Metadata checks detect replacement, truncation and edits between writes.
    They are not a lock against a hostile concurrent writer during write(2).
    The checkpoint digest attests to bytes written, not a fresh disk reread.
    This local-filesystem recorder fails closed even on metadata-only changes;
    externally managed/synchronized ledgers are not supported live writers.
    Resume still verifies the actual committed prefix and every referenced PNG.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.stream = self.path.open('xb', buffering=0)
        self.digest = hashlib.sha256()
        self.size = 0
        self.failed = False
        self.expected = self._identity(os.fstat(self.stream.fileno()))

    @staticmethod
    def _identity(stat):
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def _check(self):
        if self.failed:
            raise RuntimeError('Frame ledger is invalid after an earlier write/check failure')
        try:
            opened = self._identity(os.fstat(self.stream.fileno()))
            named = self._identity(self.path.lstat())
            if opened != self.expected or named != self.expected:
                raise RuntimeError('Frame ledger changed outside its recorder')
        except Exception:
            self.failed = True
            raise

    def write(self, text):
        self._check()
        raw = text.encode('utf-8')
        try:
            written = self.stream.write(raw)
            if written != len(raw):
                raise RuntimeError('Incomplete frame ledger write')
            current = self._identity(os.fstat(self.stream.fileno()))
            if current[:2] != self.expected[:2] or current[2] != self.size + len(raw):
                raise RuntimeError('Frame ledger size changed during write')
            self.digest.update(raw)
            self.size += len(raw)
            self.expected = current
        except Exception:
            self.failed = True
            raise
        return len(text)

    def snapshot(self):
        self._check()
        return self.digest.hexdigest(), self.size

    def flush(self):
        self.stream.flush()

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.stream.close()


def save_json(path, value):
    tmp = path.with_suffix(path.suffix + '.partial')
    with tmp.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    sync_path(path.parent)


def sync_path(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class FrameVerificationCache:
    """Bounded, process-local proofs created only by successful RGB decoding.

    No cache file is loaded. Each hit still reads and hashes the complete PNG.
    Entries bind exact PNG bytes to an expected RGB digest and 240x160 size.
    """
    def __init__(self, max_entries=65536, max_png_bytes=1024 * 1024):
        if not 0 <= max_entries <= 65536 or not 1 <= max_png_bytes <= 1024 * 1024:
            raise ValueError('Invalid frame verification cache bounds')
        self._proofs = set()
        self.max_entries = max_entries
        self.max_png_bytes = max_png_bytes
        self.hits = 0
        self.decodes = 0

    def verify(self, path, expected):
        if not isinstance(expected, str) or re.fullmatch(r'[0-9a-f]{64}', expected) is None:
            raise RuntimeError('Parent image hash mismatch')
        with path.open('rb') as stream:
            before = os.fstat(stream.fileno())
            data = stream.read(self.max_png_bytes + 1)
            cacheable = len(data) <= self.max_png_bytes
            key = (hashlib.sha256(data).digest(), bytes.fromhex(expected)) if cacheable else None
            hit = key is not None and key in self._proofs
            if not hit:
                if cacheable:
                    source = io.BytesIO(data)
                else:
                    stream.seek(0)
                    source = stream
                with Image.open(source) as image:
                    if image.size != (240, 160) or hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != expected:
                        raise RuntimeError('Parent image hash mismatch')
                self.decodes += 1
            after = os.fstat(stream.fileno())
            current = path.stat()
            def identity(st):
                return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
            if identity(before) != identity(after) or identity(after) != identity(current):
                raise RuntimeError('Parent image changed during verification')
        if hit:
            self.hits += 1
        elif key is not None and len(self._proofs) < self.max_entries:
            self._proofs.add(key)


def verify_parent(checkpoint_path, checkpoint, _visited=None, *, frame_cache=None):
    """Verify the exact committed prefix, including every referenced RGB image."""
    checkpoint_path = checkpoint_path.resolve()
    visited = set() if _visited is None else set(_visited)
    if checkpoint_path in visited or len(visited) >= 128:
        raise RuntimeError('Parent checkpoint cycle or excessive depth')
    visited.add(checkpoint_path)
    root = checkpoint_path.parent
    baseline = json.loads((root / 'baseline.json').read_text(encoding='utf-8'))
    if ('baseline_sha256' in checkpoint or baseline.get('schema_version', 1) >= 3) and checkpoint.get('baseline_sha256') != sha(root / 'baseline.json'):
        raise RuntimeError('Parent baseline hash mismatch')
    transport_proof_rgb = None
    if baseline.get('frame_transport') and checkpoint['core_frame'] != baseline['initial_core_frame']:
        proof_path = root / 'frame_transport_verification.json'
        if checkpoint.get('frame_transport_verification_sha256') != sha(proof_path):
            raise RuntimeError('Frame transport proof hash mismatch')
        proof = json.loads(proof_path.read_text())
        first = (baseline['initial_core_frame'] + 1) & 0xffffffff
        if (proof.get('schema') != 1 or type(proof.get('schema')) is not int
                or any(type(proof.get(k)) is not int for k in ('core_frame', 'counter_before', 'counter_after_raw', 'counter_after_fifo', 'raw_bytes', 'fifo_bytes', 'extra_emulated_frames'))
                or any(not isinstance(proof.get(k), str) or re.fullmatch(r'[0-9a-f]{64}', proof[k]) is None for k in ('raw_sha256', 'fifo_sha256', 'rgb_sha256'))
                or any(proof.get(k) != first for k in ('core_frame', 'counter_before', 'counter_after_raw', 'counter_after_fifo'))
                or proof.get('raw_bytes') != 153605 or proof.get('fifo_bytes') != 153605
                or proof.get('raw_sha256') != proof.get('fifo_sha256')
                or proof.get('harness_sha256') != baseline['harness_sha256']
                or proof.get('rom_sha256') != baseline['rom_sha256']
                or proof.get('extra_emulated_frames') != 0):
            raise RuntimeError('Frame transport proof identity mismatch')
        modules = baseline['frame_transport'].get('modules')
        if not isinstance(modules, dict) or set(modules) != {'frame_png.py', 'frame_transport.py'} or proof.get('modules') != modules:
            raise RuntimeError('Frame transport module proof differs')
        for name, identity in modules.items():
            if (not isinstance(identity, dict) or not isinstance(identity.get('path'), str)
                    or not Path(identity['path']).is_absolute() or Path(identity['path']).name != name
                    or not isinstance(identity.get('sha256'), str) or re.fullmatch(r'[0-9a-f]{64}', identity['sha256']) is None):
                raise RuntimeError('Frame transport module identity malformed')
        if modules['frame_transport.py']['sha256'] != baseline['frame_transport'].get('module_sha256'):
            raise RuntimeError('Frame transport module SHA differs')
        if baseline.get('frame_png_encoder_sha256') and modules['frame_png.py']['sha256'] != baseline['frame_png_encoder_sha256']:
            raise RuntimeError('Frame PNG module SHA differs')
        transport_proof_rgb = proof['rgb_sha256']
    if baseline['initial_core_frame'] != 0 and not baseline.get('parent_checkpoint'):
        raise RuntimeError('Nonzero initial frame requires a parent checkpoint')
    if not baseline.get('initial_game_save') and any((root / name).exists() for name in ('game.sav', 'game_save.json', 'loaded_game.sav')):
        raise RuntimeError('Game-save seed metadata missing')
    for key in ('rom_sha256', 'harness_sha256', 'libmgba_sha256'):
        if key in baseline and baseline[key] != checkpoint.get(key):
            raise RuntimeError(f'Parent baseline identity mismatch: {key}')
    if baseline.get('parent_checkpoint'):
        parent_path = Path(baseline['parent_checkpoint']).resolve()
        if not parent_path.is_file() or sha(parent_path) != baseline.get('parent_checkpoint_sha256'):
            raise RuntimeError('Parent checkpoint hash mismatch')
        parent = json.loads(parent_path.read_text())
        if parent['core_frame'] != baseline['initial_core_frame']:
            raise RuntimeError('Parent checkpoint boundary mismatch')
        for key in ('rom_sha256', 'harness_sha256', 'libmgba_sha256'):
            if parent.get(key) != checkpoint.get(key):
                raise RuntimeError(f'Parent chain identity mismatch: {key}')
        verify_parent(parent_path, parent, visited, frame_cache=frame_cache)
    if baseline.get('initial_game_save'):
        from game_save_evidence import verify_recorded_seed
        verify_recorded_seed(root, baseline)
    ledger = root / 'frames.jsonl'
    if not 0 <= checkpoint['ledger_bytes'] <= ledger.stat().st_size:
        raise RuntimeError('Parent ledger prefix missing or incomplete')
    with ledger.open('rb') as stream:
        prefix = stream.read(checkpoint['ledger_bytes'])
    if len(prefix) != checkpoint['ledger_bytes'] or (prefix and not prefix.endswith(b'\n')):
        raise RuntimeError('Parent ledger prefix missing or incomplete')
    if baseline.get('schema_version', 1) >= 2 and 'ledger_sha256' not in checkpoint:
        raise RuntimeError('Parent ledger digest missing')
    if 'ledger_sha256' in checkpoint and hashlib.sha256(prefix).hexdigest() != checkpoint['ledger_sha256']:
        raise RuntimeError('Parent ledger hash mismatch')
    frame = baseline['initial_core_frame']
    checked = set()
    for line in prefix.splitlines():
        row = json.loads(line)
        frame = (frame + 1) & 0xffffffff
        if row['core_frame'] != frame:
            raise RuntimeError('Parent ledger frame discontinuity')
        if transport_proof_rgb is not None and frame == ((baseline['initial_core_frame'] + 1) & 0xffffffff):
            if row.get('rgb_sha256') != transport_proof_rgb or row.get('image') != 'frames/' + transport_proof_rgb + '.png':
                raise RuntimeError('Frame transport proof does not match first ledger frame')
        image_path = (root / row['image']).resolve()
        if not image_path.is_relative_to(root):
            raise RuntimeError('Parent image path escapes run')
        identity = (str(image_path), row['rgb_sha256'])
        if identity not in checked:
            if frame_cache is not None:
                frame_cache.verify(image_path, row['rgb_sha256'])
            else:
                with Image.open(image_path) as image:
                    if image.size != (240, 160) or hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != row['rgb_sha256']:
                        raise RuntimeError('Parent image hash mismatch')
            checked.add(identity)
    if frame != checkpoint['core_frame']:
        raise RuntimeError('Parent ledger does not reach checkpoint')


def frame_module_source(module, name):
    source = Path(module.__file__).resolve()
    if source != ROOT / 'tools' / name:
        raise RuntimeError('Frame module import provenance differs: ' + name)
    return source


class Recorder:
    def __init__(self, args, *, frame_verification_cache=None):
        self.png_compress_level = getattr(args, 'png_compress_level', 6)
        self.lossless_palette_frames = getattr(args, 'lossless_palette_frames', False)
        self.no_contact_sheets = getattr(args, 'no_contact_sheets', False)
        if type(self.png_compress_level) is not int or not 0 <= self.png_compress_level <= 9:
            raise ValueError('PNG compression level must be an integer from 0 to 9')
        self.out = args.out.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        (self.out / 'frames').mkdir()
        self.proc = None
        self.log_archive = None
        self.frame_transport = None
        self.counter = 0
        self.committed = 0
        self.segment = 0
        self.last_checkpoint = None
        self.last_jev_report = None
        self.jev_requests = set()
        self.seen = set()
        self.pending_png = []
        self.protocol_failed = False
        self.min_free = args.min_free_gib * 1024**3
        self.timeout = args.timeout
        self.ledger = FrameLedger(self.out / 'frames.jsonl')
        self.actions = (self.out / 'actions.jsonl').open('x', buffering=1, encoding='utf-8')
        self.process_log = (self.out / 'process.log').open('x')
        try:
            self.check_disk()
            self.rom_sha = sha(args.rom)
            shutil.copyfile(args.rom, self.out / 'baseline.gba')
            if sha(self.out / 'baseline.gba') != self.rom_sha:
                raise RuntimeError('ROM copy hash mismatch')
            self.harness_sha = sha(args.harness)
            self.lib_sha = sha(LIBMGBA.resolve())
            seed = None
            game_save = args.game_save
            if game_save:
                if args.resume:
                    raise ValueError('Game-save boot and emulator-state resume are mutually exclusive')
                from game_save_evidence import verify_receipt, ANCHORED_KIND
                migration_source = getattr(args, 'game_save_source_rom_sha256', None)
                emulator_port = None
                expected_harness, expected_lib = self.harness_sha, self.lib_sha
                if getattr(args, 'game_save_emulator_port', False):
                    # Explicit opt-in: carry anchored cartridge bytes to a different harness/libmgba
                    # build (e.g. macOS -> Linux). Only the receipt's own recorded identity is
                    # accepted, and the cold boot below must still load the exact save bytes.
                    declared = json.loads(Path(game_save).read_text(encoding='utf-8'))
                    if declared.get('kind') != ANCHORED_KIND:
                        raise ValueError('Emulator port is only supported for anchored game-save receipts')
                    expected_harness, expected_lib = declared.get('harness_sha256'), declared.get('libmgba_sha256')
                    if expected_harness == self.harness_sha and expected_lib == self.lib_sha:
                        raise ValueError('Emulator port requested but harness and library already match the receipt')
                    emulator_port = {'source_harness_sha256': expected_harness,
                                     'source_libmgba_sha256': expected_lib}
                # An anchored receipt is a self-contained chain root: no source run is opened.
                saved, receipt = verify_receipt(game_save, expected_rom_sha256=self.rom_sha,
                                                migration_source_sha256=migration_source, frame_cache=frame_verification_cache,
                                                expected_harness_sha256=expected_harness,
                                                expected_libmgba_sha256=expected_lib)
                if migration_source is not None:
                    from game_save_evidence import verify_migration_storage
                    if receipt['kind'] == ANCHORED_KIND:
                        verify_migration_storage(None, self.out / 'baseline.gba', saved.stat().st_size,
                                                 source_types={t.encode() for t in receipt['save_storage']})
                    else:
                        verify_migration_storage(Path(receipt['source_checkpoint']).parent / 'baseline.gba',
                                                 self.out / 'baseline.gba', saved.stat().st_size)
                if receipt['libmgba_sha256'] != expected_lib:
                    raise ValueError('Game-save origin uses a different emulator library')
                shutil.copyfile(saved, self.out / 'game.sav')
                shutil.copyfile(game_save, self.out / 'game_save.json')
                shutil.copyfile(saved, self.out / 'working_game.sav')
                seed = {'save': 'game.sav', 'save_sha256': receipt['save_sha256'],
                        'receipt': 'game_save.json', 'receipt_sha256': sha(game_save),
                        'loaded_copy': 'loaded_game.sav'}
                if migration_source is not None:
                    seed['migration'] = {'source_rom_sha256': migration_source,
                                         'target_rom_sha256': self.rom_sha}
                if emulator_port is not None:
                    seed['emulator_port'] = emulator_port
                if any(sha(self.out / name) != seed['save_sha256']
                       for name in ('game.sav', 'working_game.sav')):
                    raise ValueError('Game-save seed copy mismatch')
            parent = None
            if args.resume:
                parent = json.loads(args.resume.read_text(encoding='utf-8'))
                verify_parent(args.resume, parent, frame_cache=frame_verification_cache)
                if parent['rom_sha256'] != self.rom_sha or parent['harness_sha256'] != self.harness_sha or parent['libmgba_sha256'] != self.lib_sha:
                    raise RuntimeError('Resume binary identity mismatch')
                state = (args.resume.resolve().parent / parent['state']).resolve()
                if not state.is_relative_to(args.resume.resolve().parent) or any(c.isspace() for c in str(state)):
                    raise RuntimeError('Invalid parent state path')
                if sha(state) != parent['state_sha256']:
                    raise RuntimeError('Resume state hash mismatch')
            env = harness_env()
            log_path = self.out / 'emulator.log'
            if getattr(args, 'gzip_emulator_log', False):
                from emulator_log_archive import LogArchive
                self.log_archive = LogArchive(self.out, self.min_free)
                log_path = self.log_archive.fifo
            command = [str(args.harness.resolve()), str(self.out / 'baseline.gba'), str(log_path)]
            if seed:
                command.append(str(self.out / 'working_game.sav'))
            if getattr(args, 'frame_fifo', False):
                import frame_transport
                for module, name in ((frame_png, 'frame_png.py'), (frame_transport, 'frame_transport.py')):
                    frame_module_source(module, name)
                self.frame_transport_modules = {name: {'path': str(frame_module_source(module, name)),
                    'sha256': sha(frame_module_source(module, name))}
                    for module, name in ((frame_png, 'frame_png.py'), (frame_transport, 'frame_transport.py'))}
                self.frame_transport_module_source = Path(frame_transport.__file__).resolve()
                self.frame_transport = frame_transport.FrameFIFO(self.out / 'frame.fifo', self.timeout)
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=self.process_log, env=env)
            self.selector = selectors.DefaultSelector()
            self.selector.register(self.proc.stdout, selectors.EVENT_READ)
            self.buffer = b''
            # FIFO reader is already open; native protocol readiness does not require log output.
            if parent:
                self.expect_state(self.cmd('loadstate ' + str(state)))
            self.counter = self.read_counter()
            self.committed = self.counter
            if seed:
                response = self.cmd('dumpsave ' + str(self.out / seed['loaded_copy']))
                if (self.counter != 0 or not response.startswith('OK dumpsave size=')
                        or sha(self.out / seed['loaded_copy']) != seed['save_sha256']
                        or self.read_counter() != 0):
                    raise RuntimeError('Cold boot did not load the exact game-save bytes at frame zero')
            if parent and self.counter != parent['core_frame']:
                raise RuntimeError('Resume frame counter mismatch')
            metadata = {'schema_version': 4, 'rom_sha256': self.rom_sha, 'harness_sha256': self.harness_sha,
                        'recorder_sha256': sha(Path(__file__)),
                        'libmgba_sha256': self.lib_sha, 'parent_checkpoint': str(args.resume.resolve()) if parent else None,
                        'parent_checkpoint_sha256': sha(args.resume) if parent else None,
                        'initial_core_frame': self.counter, 'capture': 'every frame, RGB PNG, no audio',
                        'visual_review': 'pending', 'min_free_gib': args.min_free_gib,
                        'png_compress_level': self.png_compress_level,
                        'contact_sheets': not self.no_contact_sheets}
            if self.lossless_palette_frames:
                metadata['capture'] = 'every frame, lossless RGB-equivalent PNG, no audio'
                metadata['frame_png_encoding'] = 'exact-palette-or-rgb-v1'
                metadata['frame_png_encoder_sha256'] = sha(Path(frame_png.__file__).resolve())
                metadata['pillow_version'] = pillow_version
            if self.frame_transport:
                metadata['frame_transport'] = {'format': 'bounded-shot-fifo-v1',
                    'module_sha256': sha(self.frame_transport_module_source),
                    'initial_verification': 'frame_transport_verification.json',
                    'modules': self.frame_transport_modules}
            if self.log_archive:
                metadata['emulator_log'] = {'format':'gzip-fifo-v1','archive':'emulator.log.gz',
                                            'receipt':'emulator.log.archive.json'}
            if seed:
                metadata['initial_game_save'] = seed
            save_json(self.out / 'baseline.json', metadata)
            self.checkpoint('initial')
            # Record one neutral frame so every session has an exact image hash
            # bound to a checkpoint before its first JEV decision.
            self.action('NONE', 1, 0)
        except BaseException as exc:
            self.close(exc)
            raise

    def check_disk(self):
        if getattr(self, 'log_archive', None):
            self.log_archive.check()
        if shutil.disk_usage(self.out).free < self.min_free:
            raise RuntimeError('Disk reserve reached; no next frame executed')

    def cmd(self, command):
        if getattr(self, 'log_archive', None):
            self.log_archive.check()
        if self.proc is None or self.proc.poll() is not None:
            raise RuntimeError('Emulator is not running')
        if self.protocol_failed or self.buffer:
            self.protocol_failed = True
            raise RuntimeError('Unexpected buffered emulator response')
        self.proc.stdin.write((command + '\n').encode())
        self.proc.stdin.flush()
        deadline = time.monotonic() + self.timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.protocol_failed = True
                raise TimeoutError('Emulator command timed out: ' + command)
            archived = getattr(self, 'log_archive', None)
            if archived:
                try:
                    archived.check()
                except BaseException:
                    self.protocol_failed = True  # An outstanding reply cannot be reused safely.
                    raise
            if not self.selector.select(min(remaining, .1) if archived else remaining):
                continue
            block = os.read(self.proc.stdout.fileno(), 65536)
            if not block:
                raise RuntimeError('Emulator closed stdout: ' + command)
            self.buffer += block
        line, self.buffer = self.buffer.split(b'\n', 1)
        reply = line.decode().strip()
        verb = command.split()[0]
        valid = reply.startswith('OK ' + verb + ' ') or reply == 'OK ' + verb
        if verb in ('frames', 'keys'):
            valid = reply == 'OK ' + command
        elif verb == 'shot':
            valid = reply == 'OK shot 240 160'
        if not valid or self.buffer:
            self.protocol_failed = True
            raise RuntimeError((command, reply, 'Unexpected emulator response'))
        return reply

    def read_counter(self):
        reply = self.cmd('framecounter')
        if not reply.startswith('OK framecounter '):
            raise RuntimeError(reply)
        return int(reply.split()[-1])

    @staticmethod
    def expect_state(reply):
        if not reply.endswith('ok=1'):
            raise RuntimeError(reply)

    def checkpoint(self, tag):
        for path in self.pending_png:
            sync_path(path)
        sync_path(self.out / 'frames')
        self.pending_png.clear()
        self.ledger.flush()
        os.fsync(self.ledger.fileno())
        state = self.out / (tag + '.ss0')
        self.expect_state(self.cmd('savestate ' + str(state)))
        sync_path(state)
        ledger_sha256, ledger_bytes = self.ledger.snapshot()
        metadata = {'baseline_sha256': sha(self.out / 'baseline.json'), 'core_frame': self.committed, 'rom_sha256': self.rom_sha,
                    'harness_sha256': self.harness_sha, 'libmgba_sha256': self.lib_sha,
                    'state': state.name, 'state_sha256': sha(state),
                    'ledger_sha256': ledger_sha256,
                    'ledger_bytes': ledger_bytes}
        if getattr(self, 'frame_transport_proof_sha', None):
            metadata['frame_transport_verification_sha256'] = self.frame_transport_proof_sha
        target = self.out / (tag + '.checkpoint.json')
        save_json(target, metadata)
        self.last_checkpoint = str(target)
        return target

    def capture(self, key):
        self.check_disk()
        self.cmd('frames 1')
        expected = (self.counter + 1) & 0xffffffff
        self.counter = self.read_counter()
        if self.counter != expected:
            raise RuntimeError(('Core frame discontinuity', expected, self.counter))
        if getattr(self, 'frame_transport', None):
            try:
                if not getattr(self, 'frame_transport_verified', False):
                    probe = self.out / 'frame_transport_probe.raw'
                    if probe.exists() or probe.is_symlink():
                        raise RuntimeError('Frame transport probe path already exists')
                    before = self.read_counter()
                    self.cmd('shot ' + str(probe))
                    regular = probe.read_bytes()
                    after_raw = self.read_counter()
                    data = self.frame_transport.capture(lambda path: self.cmd('shot ' + str(path)))
                    after_fifo = self.read_counter()
                    if (before, after_raw, after_fifo) != (self.counter,) * 3 or data != regular:
                        raise RuntimeError('Initial raw/FIFO frame identity differs')
                    proof = {'schema': 1, 'core_frame': self.counter, 'counter_before': before,
                        'counter_after_raw': after_raw, 'counter_after_fifo': after_fifo,
                        'raw_bytes': len(regular), 'fifo_bytes': len(data),
                        'raw_sha256': hashlib.sha256(regular).hexdigest(),
                        'fifo_sha256': hashlib.sha256(data).hexdigest(),
                        'rgb_sha256': hashlib.sha256(Image.frombytes('RGB', (240, 160), data[5:], 'raw', 'RGBX').tobytes()).hexdigest(),
                        'modules': self.frame_transport_modules,
                        'harness_sha256': self.harness_sha, 'rom_sha256': self.rom_sha,
                        'extra_emulated_frames': 0}
                    proof_path = self.out / 'frame_transport_verification.json'
                    save_json(proof_path, proof)
                    self.frame_transport_proof_sha = sha(proof_path)
                    self.frame_transport_verified = True
                    probe.unlink()
                else:
                    data = self.frame_transport.capture(lambda path: self.cmd('shot ' + str(path)))
            except BaseException:
                self.protocol_failed = True  # No uncertain frame/reply may enter a checkpoint.
                raise
        else:
            raw = self.out / 'current.raw'
            raw.unlink(missing_ok=True)  # A failed shot must never reuse the previous frame.
            self.cmd('shot ' + str(raw))
            data = raw.read_bytes()
        if len(data) != 153605 or struct.unpack('<HHB', data[:5]) != (240, 160, 4):
            raise RuntimeError('Unexpected framebuffer format')
        im = Image.frombytes('RGB', (240, 160), data[5:], 'raw', 'RGBX')
        digest = hashlib.sha256(im.tobytes()).hexdigest()
        rel = 'frames/' + digest + '.png'
        if digest not in self.seen:
            path = self.out / rel
            if getattr(self, 'lossless_palette_frames', False):
                path.write_bytes(encode_frame_png(im, self.png_compress_level))
            else:
                im.save(path, compress_level=self.png_compress_level)
            with Image.open(path) as restored:
                if hashlib.sha256(restored.convert('RGB').tobytes()).hexdigest() != digest:
                    raise RuntimeError('PNG roundtrip mismatch')
            self.seen.add(digest)
            self.pending_png.append(path)
        self.ledger.write(json.dumps({'core_frame': self.counter, 'keys': key, 'image': rel,
                                     'rgb_sha256': digest}) + '\n')
        self.committed = self.counter
        return im

    def action(self, key, count, hold=None):
        if hold is None:
            hold = default_hold(key)
        validate_action(key, count, hold)
        self.check_disk()
        self.segment += 1
        first = (self.counter + 1) & 0xffffffff
        self.actions.write(json.dumps({'segment': self.segment, 'start_core_frame': first,
                           'key': key, 'hold_frames': hold, 'release_frames': count,
                           'prior_checkpoint': self.last_checkpoint, 'status': 'started'}) + '\n')
        make_sheet = not getattr(self, 'no_contact_sheets', False)
        samples = []
        self.cmd('keys ' + str(KEYS[key]))
        for i in range(hold):
            im = self.capture(KEYS[key])
            if make_sheet and (i % max(1, hold // 18) == 0 or i == hold - 1):
                samples.append((self.counter, im.copy()))
        self.cmd('keys 0')
        for i in range(count):
            im = self.capture(0)
            if make_sheet and (i % max(1, count // 18) == 0 or i == count - 1):
                samples.append((self.counter, im.copy()))
        tag = f'{self.segment:04d}_{key}_{self.counter:07d}'
        png = self.out / (tag + '.png'); im.save(png, compress_level=self.png_compress_level)
        checkpoint = self.checkpoint(tag)
        sheet_path = None
        if make_sheet:
            sheet = Image.new('RGB', (960, ((len(samples) + 3) // 4) * 180), (32, 32, 32))
            draw = ImageDraw.Draw(sheet)
            for i, (frame, shot) in enumerate(samples):
                x, y = i % 4 * 240, i // 4 * 180
                sheet.paste(shot, (x, y + 20)); draw.text((x + 3, y + 3), str(frame), fill='white')
            sheet_path = self.out / (tag + '_sheet.png'); sheet.save(sheet_path, compress_level=self.png_compress_level)
        result = {'segment': self.segment, 'start_core_frame': first, 'end_core_frame': self.committed,
                  'status': 'captured', 'checkpoint': str(checkpoint), 'png': str(png), 'sheet': str(sheet_path) if sheet_path is not None else None,
                  'free_gib': round(shutil.disk_usage(self.out).free / 1024**3, 2), 'visual_review': 'pending'}
        self.actions.write(json.dumps(result) + '\n')
        print(json.dumps(result), flush=True)

    def jev_choice(self, candidate_path):
        """Ask JEV to select among checkpoint-bound candidates; execute only a bounded local macro."""
        self.last_jev_report = None
        from jev_game_choice import (JevError, load_input, payload, request_api, preflight_request, validate,
                                     validate_capture_binding, selected_macro)
        raw_path = Path(candidate_path)
        path = (ROOT / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
        if not path.is_relative_to((ROOT / 'temp').resolve()):
            raise ValueError('Candidate JSON must be under temp/')
        if self.proc is None or self.proc.poll() is not None or self.protocol_failed:
            raise RuntimeError('Emulator is not live and protocol-clean')
        if self.counter != self.committed:
            raise RuntimeError('Emulator frame is not at the committed checkpoint')
        doc, raw = load_input(path)
        if not self.last_checkpoint:
            raise RuntimeError('No committed checkpoint is available')
        checkpoint = Path(self.last_checkpoint)
        with (self.out / 'frames.jsonl').open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            end = stream.tell()
            pos = end - 1
            while pos >= 0:
                stream.seek(pos)
                if stream.read(1) == b'\n' and pos != end - 1:
                    break
                pos -= 1
            stream.seek(pos + 1)
            last_line = stream.read(end - pos - 1).decode('utf-8').strip()
        if not last_line:
            raise RuntimeError('No committed frame image is available')
        try:
            last_frame = json.loads(last_line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError('Frame ledger contains an invalid final record') from None
        if not isinstance(last_frame, dict):
            raise RuntimeError('Frame ledger final record is not an object')
        if last_frame.get('core_frame') != self.committed:
            raise RuntimeError('Frame ledger is not at the committed frame')
        checkpoint_hash = sha(checkpoint)
        validate_capture_binding(doc['state'], rom_sha256=self.rom_sha, frame=self.committed,
                                 checkpoint_sha256=checkpoint_hash,
                                 frame_image_sha256=last_frame.get('rgb_sha256'))
        jev_payload = payload(doc)
        wire = json.dumps(jev_payload, ensure_ascii=False, sort_keys=True).encode()
        request_hash = hashlib.sha256(wire).hexdigest()
        if request_hash in self.jev_requests:
            raise ValueError('This exact JEV request already ran in this recorder session')
        if len(self.jev_requests) >= 8:
            raise ValueError('JEV recorder session limit reached (8 requests)')
        self.check_disk()
        preflight_request('/v1/systemone', jev_payload)
        date_dir = time.strftime('%Y-%m-%d')
        report_path = ROOT / 'temp' / ('jev_' + date_dir) / f'capture_choice_{self.committed}_{time.time_ns()}.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_jev_report = str(report_path)
        attempt = {'schema_version': 1, 'status': 'request_started', 'request_sha256': request_hash,
                   'input_sha256': hashlib.sha256(raw).hexdigest(), 'rom_sha256': self.rom_sha,
                   'frame': self.committed, 'checkpoint_sha256': checkpoint_hash,
                   'frame_image_sha256': last_frame['rgb_sha256'], 'game_input_sent': False}
        save_json(report_path, attempt)
        # Record before sending: a network timeout may still have reached the provider.
        from jev_call_evidence import reserve, complete
        try:
            reservation = reserve(request_hash, report_path)
        except (JevError, OSError):
            attempt['status'] = 'request_rejected'
            save_json(report_path, attempt)
            raise
        self.jev_requests.add(request_hash)
        try:
            response = request_api('/v1/systemone', jev_payload)
        except Exception as exc:
            complete(reservation, 'api_or_response_error', error=exc)
            attempt.update({'status': 'api_or_response_error', 'error_type': type(exc).__name__})
            save_json(report_path, attempt)
            raise
        try:
            result = validate(response, doc['candidates'])
        except Exception as exc:
            complete(reservation, 'api_or_response_error', response=response, error=exc)
            attempt.update({'status': 'api_or_response_error', 'error_type': type(exc).__name__})
            usage = response.get('usage') if isinstance(response, dict) else None
            if isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                               for k in ('input_tokens', 'output_tokens')):
                attempt['usage'] = {k: usage[k] for k in ('input_tokens', 'output_tokens')}
            model = response.get('model') if isinstance(response, dict) else None
            if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', model):
                attempt['model'] = model
            save_json(report_path, attempt)
            raise
        macro = selected_macro(doc, result)
        complete(reservation, 'choice_recorded', response=response)
        report = {'schema_version': 1, 'status': 'choice_recorded', 'request_sha256': request_hash,
                  'input_sha256': hashlib.sha256(raw).hexdigest(), 'rom_sha256': self.rom_sha,
                  'frame': self.committed, 'checkpoint_sha256': checkpoint_hash,
                  'frame_image_sha256': last_frame['rgb_sha256'], **result,
                  'macro_planned': bool(macro), 'macro_steps': len(macro) if macro else 0}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(report_path, report)
        event = {'status': 'jev_choice', 'core_frame': self.committed, 'choice': result['choice'],
                 'confidence': result['confidence'],
                 'candidate_confidence_eligible': result['candidate_confidence_eligible'],
                 'report': str(report_path), 'macro_steps': len(macro) if macro else 0}
        self.actions.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.actions.flush(); os.fsync(self.actions.fileno())
        print(json.dumps(event, ensure_ascii=False), flush=True)
        return macro

    def record_jev_rejection(self, error):
        event = {'status': 'jev_rejected', 'core_frame': self.committed,
                 'error': f'{type(error).__name__}: {error}', 'report': self.last_jev_report}
        self.actions.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.actions.flush(); os.fsync(self.actions.fileno())
        print(json.dumps({'jev_error': event['error'], 'report': event['report']},
                         ensure_ascii=False), flush=True)

    def close(self, error=None):
        cleanup_errors = []
        if error is not None:
            try:
                self.actions.write(json.dumps({'segment': self.segment, 'status': 'failed',
                    'error': str(error), 'committed_core_frame': self.committed,
                    'last_good_checkpoint': self.last_checkpoint}) + '\n')
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if self.proc and self.proc.poll() is not None:
            cleanup_errors.append('Emulator exited before shutdown: ' + str(self.proc.returncode))
        # On capture failure the emulator may have advanced past the last recorded frame.
        # Never publish that state as a valid checkpoint.
        if self.proc and self.proc.poll() is None:
            try:
                if getattr(self, 'log_archive', None):
                    try:
                        self.log_archive.check()
                    except Exception:
                        # Collector failure can block the producer on FIFO write. Stop only our
                        # child immediately; never send commands across an uncertain response.
                        self.proc.kill()
                        raise
                if self.protocol_failed:
                    raise RuntimeError('Protocol timed out; skip further commands')
                self.cmd('keys 0')
                if error is None:
                    self.checkpoint('resume')
                self.cmd('quit')
            except Exception as exc:
                cleanup_errors.append(str(exc))
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
                    cleanup_errors.append('Killed own unresponsive emulator')
                except Exception as exc:
                    cleanup_errors.append('Emulator kill/wait failed: ' + str(exc))
            if self.proc.returncode != 0:
                cleanup_errors.append('Emulator shutdown exit code: ' + str(self.proc.returncode))
        if getattr(self, 'log_archive', None) and not self.log_archive.finished:
            try:
                self.log_archive.finish(producer_exited=self.proc is None or self.proc.poll() is not None,
                                        successful=error is None and not cleanup_errors and self.proc is not None)
            except BaseException as exc:
                cleanup_errors.append('Native log archive failed: ' + str(exc))
        if getattr(self, 'frame_transport', None):
            try:
                self.frame_transport.close()
            except BaseException as exc:
                cleanup_errors.append('Frame FIFO cleanup failed: ' + str(exc))
        for name in ('ledger', 'actions', 'process_log'):
            try:
                getattr(self, name).close()
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if hasattr(self, 'selector'):
            self.selector.close()
        result = {'status': 'failed' if error or cleanup_errors else 'closed', 'error': str(error) if error else None,
                  'last_observed_core_frame': self.counter, 'committed_core_frame': self.committed,
                  'last_good_checkpoint': self.last_checkpoint, 'cleanup_errors': cleanup_errors,
                  'emulator_exit_code': self.proc.returncode if self.proc else None}
        try:
            save_json(self.out / 'exit.json', result)
        finally:
            print(json.dumps(result), flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--harness', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    start = parser.add_mutually_exclusive_group()
    start.add_argument('--resume', type=Path)
    parser.add_argument('--cache-resume-frames', action='store_true',
                        help='With --resume, reuse bounded process-local RGB proofs; still read and hash every PNG')
    start.add_argument('--export-game-save', type=Path, help='Opt-in same-process verified SRAM export then cold boot; recheck PNG bytes while reusing bounded RGB proofs')
    parser.add_argument('--export-game-save-out', type=Path, help='New evidence directory required with --export-game-save')
    start.add_argument('--game-save', type=Path, help='Verified game_save_evidence.py receipt; cold boot with cartridge save. An anchored receipt (--anchored export) starts a new chain root that never re-verifies the source run')
    parser.add_argument('--game-save-source-rom-sha256', help='Explicit source SHA-256 for normal SRAM migration to a compatible patch ROM; never migrates emulator states')
    parser.add_argument('--game-save-emulator-port', action='store_true',
                        help='Explicit opt-in: boot an anchored game-save with a different harness/libmgba build '
                             '(e.g. macOS to Linux); records both identities in baseline initial_game_save.emulator_port')
    parser.add_argument('--min-free-gib', type=float, default=10)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--gzip-emulator-log', action='store_true',
                        help='Opt-in bounded FIFO gzip archive with verified stream receipt; quiet native startup supported')
    parser.add_argument('--png-compress-level', type=int, choices=range(10), default=3,
                        help='Lossless PNG compression (default 3 reduces capture CPU; 6 uses less disk)')
    parser.add_argument('--lossless-palette-frames', action='store_true',
                        help='Store smaller exact palette PNG frames when possible; preserve RGB hashes and all frames')
    parser.add_argument('--frame-fifo', action='store_true',
                        help='Opt-in bounded framebuffer FIFO; preserve every PNG/frame without temporary raw-file writes')
    parser.add_argument('--no-contact-sheets', action='store_true',
                        help='Omit duplicate contact sheets; preserve every frame, endpoint, checkpoint and ledger')
    args = parser.parse_args()
    if args.cache_resume_frames and not args.resume:
        parser.error('--cache-resume-frames requires --resume')
    if args.game_save_source_rom_sha256 and not (args.game_save or args.export_game_save):
        parser.error('--game-save-source-rom-sha256 requires --game-save')
    if args.game_save_emulator_port and not args.game_save:
        parser.error('--game-save-emulator-port requires --game-save')
    if args.min_free_gib < 1 or args.timeout <= 0:
        parser.error('Reserve must be >= 1 GiB and timeout positive')
    # The existing harness protocol splits paths at whitespace.
    for path in [args.out, args.harness, args.resume, args.export_game_save_out]:
        if path and any(c.isspace() for c in str(path.resolve())):
            parser.error('Harness paths cannot contain whitespace')
    if bool(args.export_game_save) != bool(args.export_game_save_out):
        parser.error('--export-game-save and --export-game-save-out must be used together')
    if args.export_game_save:
        export_out = args.export_game_save_out.resolve()
        capture_out = args.out.resolve()
        if export_out == capture_out or capture_out in export_out.parents:
            parser.error('Export evidence directory must not create the capture output directory')
        if export_out.exists() or capture_out.exists():
            parser.error('Export and capture output directories must both be new')
    frame_cache = FrameVerificationCache() if args.cache_resume_frames else None
    if args.export_game_save:
        from game_save_evidence import export
        frame_cache = FrameVerificationCache()
        args.game_save = export(args.export_game_save, args.harness, args.export_game_save_out,
                                frame_cache=frame_cache, announce=False)
    recorder = Recorder(args, frame_verification_cache=frame_cache)
    frame_cache = None  # Proofs are needed only for the adjacent verification, not the play session.
    print(json.dumps({'ready': True, 'out': str(recorder.out), 'core_frame': recorder.counter}), flush=True)
    error = None
    try:
        for line in sys.stdin:
            tokens = line.strip().split()
            if not tokens:
                continue
            if tokens[0] == 'quit':
                break
            if tokens[0] == 'note':
                recorder.actions.write(json.dumps({'note': ' '.join(tokens[1:]), 'core_frame': recorder.counter}, ensure_ascii=False) + '\n')
                print('NOTED', flush=True)
                continue
            if tokens[0] == 'jev':
                from jev_game_choice import JevError
                if len(tokens) != 2:
                    print(json.dumps({'input_error': 'Use jev temp/path/candidates.json'}), flush=True)
                    continue
                try:
                    macro = recorder.jev_choice(tokens[1])
                except (JevError, ValueError, KeyError, TypeError) as exc:
                    # Expected request/candidate errors are recoverable; disk/capture/runtime failures stay fatal.
                    recorder.record_jev_rejection(exc)
                    continue
                for step in macro or []:
                    recorder.action(step['key'], step['release_frames'], step['hold_frames'])
                if macro:
                    recorder.actions.write(json.dumps({'status': 'jev_macro_completed',
                        'core_frame': recorder.committed, 'steps': len(macro)}, ensure_ascii=False) + '\n')
                    recorder.actions.flush(); os.fsync(recorder.actions.fileno())
                continue
            try:
                key, count, hold = parse_action(tokens)
            except ValueError as exc:
                print(json.dumps({'input_error': str(exc)}), flush=True)
                continue
            recorder.action(key, count, hold)
    except BaseException as exc:
        error = exc
        raise
    finally:
        result = recorder.close(error)
        if error is None and result['status'] != 'closed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
