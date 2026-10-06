"""Per-platform location of the system libmgba and the harness launch environment.

macOS keeps the original Homebrew layout byte-for-byte (path, DYLD_* scrub and
DYLD_LIBRARY_PATH). On Linux the harness links the system libmgba directly, so
loader override variables are scrubbed to make the hashed library the one loaded.
"""
import os
import sys
from pathlib import Path

if sys.platform == 'darwin':
    LIBMGBA = Path('/opt/homebrew/lib/libmgba.dylib')
    _SCRUB_PREFIXES = ('DYLD_',)
    _EXTRA_ENV = {'DYLD_LIBRARY_PATH': '/opt/homebrew/lib'}
elif sys.platform.startswith('linux'):
    LIBMGBA = Path('/usr/lib/libmgba.so')
    _SCRUB_PREFIXES = ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT')
    _EXTRA_ENV = {}
else:
    raise RuntimeError('Unsupported platform for the mGBA harness: ' + sys.platform)


def harness_env(base=None):
    """Environment for launching the native harness against LIBMGBA."""
    source = os.environ if base is None else base
    env = {k: v for k, v in source.items() if not k.startswith(_SCRUB_PREFIXES)}
    env.update(_EXTRA_ENV)
    return env
