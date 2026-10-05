"""Hash-bound build/QA evidence, inspired by hanpatch's manifest/stage ledger.

These hashes detect stale evidence, not maliciously forged local JSON. Build
receipts are development provenance, never a visual or translation approval.
"""
import hashlib
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
GENERATED = {'data/objlabel_sprites.json', 'data/sprite_build_layouts.json'}
BUILD_METADATA = ('temp/integrity_map.json', 'temp/repoint_manifest.json')
EXTERNAL_FONTS = [Path.home() / 'Library/Fonts/OkDanDan-Bold.otf',
                  Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'),
                  Path('/Library/Fonts/NanumGothicExtraBold.ttf'),
                  Path('/Library/Fonts/NanumGothicBold.ttf')]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def snapshot_inputs(root=ROOT):
    files = {}
    for directory in ('data', 'reference', 'tools'):
        for path in sorted((root / directory).rglob('*')):
            if not path.is_file() or any(p in ('__pycache__', '.DS_Store') for p in path.parts):
                continue
            files[path.relative_to(root).as_posix()] = sha(path)
    for name in ('requirements.txt',):
        if (root / name).exists():
            files[name] = sha(root / name)
    fonts = {str(p): sha(p) if p.is_file() else None for p in EXTERNAL_FONTS}
    import PIL
    payload = {'files': files, 'external_fonts': fonts, 'python': platform.python_version(),
               'pillow': PIL.__version__}
    return {**payload, 'digest': digest(payload)}


def write_json(path, value):
    from editor_storage import atomic_write_bytes
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def receipt_path(rom):
    return Path(str(rom) + '.build.json')


def snapshot_build_metadata():
    # These files define which payloads several QA gates inspect. Bind them to
    # the producing build so another candidate cannot silently replace them.
    return {name: sha(ROOT / name) for name in BUILD_METADATA}


def stable_build_inputs(before, after):
    def without_generated(value):
        return {**{k: v for k, v in value.items() if k not in ('files', 'digest')},
                'files': {k: v for k, v in value['files'].items() if k not in GENERATED}}
    if without_generated(before) != without_generated(after):
        raise ValueError('Build inputs changed during build; output provenance refused')


def write_build_receipt(rom, source, before, after, source_sha_before, *, repoint_enabled=True):
    stable_build_inputs(before, after)
    if sha(source) != source_sha_before:
        raise ValueError('Source ROM changed during build')
    value = {'schema': SCHEMA, 'stage': 'development_build', 'release_ready': False,
             'source_sha256': source_sha_before, 'rom_sha256': sha(rom),
             'inputs_before': before, 'inputs_after': after,
             'repoint_enabled': repoint_enabled,
             'build_metadata': snapshot_build_metadata() if repoint_enabled else None}
    write_json(receipt_path(rom), value)


def verify_build_receipt(rom, source, current):
    value = json.loads(receipt_path(rom).read_text())
    if value.get('schema') != SCHEMA or value.get('stage') != 'development_build':
        raise ValueError('Missing or unsupported build provenance')
    if value.get('rom_sha256') != sha(rom) or value.get('source_sha256') != sha(source):
        raise ValueError('Build receipt ROM/source mismatch')
    if value.get('inputs_after') != current:
        raise ValueError('Build receipt is stale for current inputs')
    if value.get('repoint_enabled') is not True:
        raise ValueError('Debug build without dialogue repointing cannot authorize packaging')
    if value.get('build_metadata') != snapshot_build_metadata():
        raise ValueError('Build QA metadata is stale or belongs to another candidate')
    return value


def verify_prepackage_report(report, rom, source, required_gates, current):
    if report.get('schema') != SCHEMA or report.get('stage') != 'prepackage_qa':
        raise ValueError('A hash-bound prepackage QA report is required')
    if report.get('rom_sha256') != sha(rom) or report.get('source_sha256') != sha(source):
        raise ValueError('QA report does not describe these ROMs')
    if report.get('inputs_before') != current or report.get('inputs_after') != current:
        raise ValueError('QA inputs changed or report is stale')
    verify_build_receipt(rom, source, current)
    rows = report.get('results', [])
    labels = [row.get('label') for row in rows]
    if len(labels) != len(set(labels)) or not set(required_gates) <= set(labels):
        raise ValueError('QA report has missing or duplicate required gates')
    if report.get('failed_count') != 0 or any(type(row.get('returncode')) is not int
                                             or row['returncode'] != 0
                                             or row.get('timed_out') is not False for row in rows):
        raise ValueError('QA report contains failed, incomplete or timed-out checks')
    return {'report_digest': digest(report), 'rom_sha256': report['rom_sha256'],
            'inputs_digest': current['digest'], 'gate_labels': sorted(labels)}
