"""Supplementary (not one of the 4 review commands): run the one test that uses TemporaryDirectory with TMPDIR unset
and record every tempfile.mkdtemp/mkstemp audit event path. Read-only w.r.t. repo sources."""
import sys, runpy, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
events = []
def hook(ev, args):
    if ev in ('tempfile.mkdtemp', 'tempfile.mkstemp'):
        events.append((ev, str(args[0])))
sys.addaudithook(hook)
sys.argv = ['test_part2_name_compose_build.py', '-v', 'NameComposeBuildTests.test_inputs_reject_stale_oversize_or_tampered_assets']
try:
    runpy.run_path(str(ROOT / 'tools/test_part2_name_compose_build.py'), run_name='__main__')
except SystemExit as e:
    code = e.code
inside = [p for _, p in events if Path(p).resolve().is_relative_to((ROOT / 'temp').resolve())]
print('AUDIT_EVENTS', json.dumps(events))
print('ALL_UNDER_ROOT_TEMP', bool(events) and len(inside) == len(events), 'count', len(events))
sys.exit(code if (events and len(inside) == len(events)) else 3)
