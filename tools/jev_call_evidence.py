"""Persistent paid gameplay call reservations shared across recorder sessions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
from jev_triage import JevError

AUDIT_ROOT = Path(__file__).resolve().parents[1] / 'output/qa/jev_api_calls'
MAX_DAILY_CALLS = 8

def sync_directory():
    fd = os.open(AUDIT_ROOT, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

@contextmanager
def locked():
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    with (AUDIT_ROOT / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

def reserve(request_hash, report_path):
    if not re.fullmatch(r'[0-9a-f]{64}', request_hash):
        raise JevError('Invalid request evidence hash')
    today = datetime.now(timezone.utc).date().isoformat()
    path = AUDIT_ROOT / (request_hash + '.json')
    with locked():
        if path.exists():
            raise JevError('This gameplay request was already reserved; inspect its persistent report')
        count = 0
        for prior in AUDIT_ROOT.glob('*.json'):
            try:
                record = json.loads(prior.read_text())
                if (not isinstance(record, dict) or not isinstance(record.get('utc_date'), str)
                        or record.get('request_sha256') != prior.stem):
                    raise ValueError('Invalid reservation')
                count += record['utc_date'] == today
            except (OSError, ValueError, TypeError):
                raise JevError('Persistent JEV ledger is unreadable; refusing paid request') from None
        if count >= MAX_DAILY_CALLS:
            raise JevError('Daily gameplay API call limit reached')
        with path.open('x') as stream:
            json.dump({'schema': 1, 'status': 'request_started', 'request_sha256': request_hash,
                       'utc_date': today, 'report': str(report_path)}, stream)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        sync_directory()
    return path

def complete(path, status, response=None, error=None):
    with locked():
        record = json.loads(path.read_text())
        record['status'] = status
        if error is not None:
            record['error_type'] = type(error).__name__
        if isinstance(response, dict):
            usage = response.get('usage')
            if isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                    for k in ('input_tokens', 'output_tokens')):
                record['usage'] = {k: usage[k] for k in ('input_tokens', 'output_tokens')}
            model = response.get('model')
            if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', model):
                record['model'] = model
        pending = path.with_suffix('.pending')
        with pending.open('w') as stream:
            json.dump(record, stream); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(pending, path)
        sync_directory()
