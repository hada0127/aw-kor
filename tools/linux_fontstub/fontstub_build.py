"""Run tools/build_korean_full.py on Linux with missing macOS fonts stubbed.

Only for the differential overlay build (see overlay.py): the same stub is used
for the HEAD build (A) and the changed build (B), so font-rendered regions are
identical between A and B and drop out of the diff. Never ship a stub build.
usage: python3 fontstub_build.py <repo_root> <build args...>
"""
import os
import runpy
import sys

root = os.path.abspath(sys.argv[1])
SUB = os.path.join(root, 'reference', 'fonts', 'Galmuri11-Bold.ttf')
MISSING = ('/Library/Fonts/', '/System/Library/Fonts/', os.path.expanduser('~/Library/Fonts/'))

_exists = os.path.exists


def exists(path):
    p = os.fspath(path) if not isinstance(path, int) else path
    if isinstance(p, str) and p.startswith(MISSING):
        return True
    return _exists(path)


os.path.exists = exists

import builtins  # noqa: E402
import io  # noqa: E402
import pathlib  # noqa: E402


def _map(path):
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if isinstance(path, str) and path.startswith(MISSING):
        return SUB
    return path


_open = io.open


def stub_open(file, *a, **k):
    return _open(_map(file), *a, **k)


builtins.open = stub_open
io.open = stub_open
_pexists = pathlib.Path.exists
_pisfile = pathlib.Path.is_file
pathlib.Path.exists = lambda self, *a, **k: True if str(self).startswith(MISSING) else _pexists(self, *a, **k)
pathlib.Path.is_file = lambda self, *a, **k: True if str(self).startswith(MISSING) else _pisfile(self, *a, **k)
from PIL import ImageFont  # noqa: E402

_truetype = ImageFont.truetype


def truetype(font=None, size=10, index=0, *a, **k):
    if isinstance(font, os.PathLike):
        font = os.fspath(font)
    if isinstance(font, str) and font.startswith(MISSING):
        print(f'[fontstub] {font} -> {SUB}', file=sys.stderr)
        font, index = SUB, 0
    return _truetype(font, size, index, *a, **k)


ImageFont.truetype = truetype
# ---- optional write tracing (AW_TRACE_OUT=path.json) ----------------------
TRACE_OUT = os.environ.get('AW_TRACE_OUT')
ROM_SIZE = 0x1000000
_writes = {}          # root -> list[[start, stop]]
_font_roots = set()
_getframe = sys._getframe


def _root():
    f = _getframe(2)
    below = None
    depth = 0
    while f is not None and depth < 60:
        if f.f_code.co_name == 'main' and f.f_code.co_filename.endswith('build_korean_full.py'):
            if below is None or below.f_code.co_name in ('__setitem__', 'pack_into'):
                return 'build_korean_full.py:main'
            return os.path.basename(below.f_code.co_filename) + ':' + below.f_code.co_name
        below = f
        f = f.f_back
        depth += 1
    return '?'


def _record(start, stop):
    if stop <= start:
        return
    root = _root()
    lst = _writes.setdefault(root, [])
    if lst and lst[-1][1] == start:
        lst[-1][1] = stop
    else:
        lst.append([start, stop])


class TraceBA(bytearray):
    def __setitem__(self, key, value):
        if len(self) == ROM_SIZE:
            if isinstance(key, slice):
                start, stop, _ = key.indices(ROM_SIZE)
                _record(start, start + len(value) if key.step in (None, 1) else stop)
            else:
                k = key % ROM_SIZE
                _record(k, k + 1)
        bytearray.__setitem__(self, key, value)


import struct  # noqa: E402
_pack_into = struct.pack_into


def pack_into(fmt, buf, offset, *values):
    if isinstance(buf, TraceBA) and len(buf) == ROM_SIZE:
        _record(offset, offset + struct.calcsize(fmt))
    return _pack_into(fmt, buf, offset, *values)


def _font_used():
    f = _getframe(1)
    names = []
    while f is not None:
        if f.f_code.co_name == 'main' and f.f_code.co_filename.endswith('build_korean_full.py'):
            if names:
                _font_roots.add(names[-1])
            return
        names.append(os.path.basename(f.f_code.co_filename) + ':' + f.f_code.co_name)
        f = f.f_back


if TRACE_OUT:
    struct.pack_into = pack_into
    _plain_map = _map

    def _map(path):  # noqa: F811
        mapped = _plain_map(path)
        if mapped is SUB and path is not SUB:
            _font_used()
        return mapped

    _plain_truetype = ImageFont.truetype

    def truetype(font=None, size=10, index=0, *a, **k):  # noqa: F811
        p = os.fspath(font) if isinstance(font, os.PathLike) else font
        if isinstance(p, str) and p.startswith(MISSING):
            _font_used()
        return _plain_truetype(font, size, index, *a, **k)
    ImageFont.truetype = truetype

sys.argv = [os.path.join(root, 'tools', 'build_korean_full.py')] + sys.argv[2:]
sys.path.insert(0, os.path.join(root, 'tools'))
os.chdir(root)
import hashlib  # noqa: E402
import build_title_hangul  # noqa: E402
import part2_power_title_glyphs  # noqa: E402
SUB_SHA = hashlib.sha256(_open(SUB, 'rb').read()).hexdigest()
build_title_hangul.verify_menu_font = lambda: None
build_title_hangul.MENU_FONT_SHA256 = SUB_SHA
part2_power_title_glyphs.FONT_SHA256 = SUB_SHA
init = {'bytearray': TraceBA} if TRACE_OUT else None
try:
    runpy.run_path(sys.argv[0], init_globals=init, run_name='__main__')
finally:
    if TRACE_OUT:
        import json
        with _open(TRACE_OUT, 'w') as stream:
            json.dump({'font_roots': sorted(_font_roots), 'writes': _writes}, stream)
