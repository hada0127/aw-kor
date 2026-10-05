"""Shared editor transactions and atomic files (macOS/Linux)."""
import fcntl
import functools
import json
import os
import shutil
from pathlib import Path
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


class EditorBusy(RuntimeError):
    pass


def editor_request(function):
    """Return a useful HTTP response instead of hanging during another build."""
    @functools.wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except EditorBusy as exc:
            return self._send(503, {"ok": False, "busy": True, "error": str(exc)})
        except (ValueError, OSError) as exc:
            return self._send(500, {"ok": False, "error": "데이터 읽기/저장 실패: " + str(exc)})
    return wrapped


class EditorLock:
    """Serialize read/modify/write across all editor threads and processes."""

    def __init__(self):
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._file = None

    def __enter__(self):
        return self.acquire(timeout=3)

    def acquire(self, timeout=3):
        deadline = time.monotonic() + timeout
        if not self._thread_lock.acquire(timeout=timeout):
            raise EditorBusy("빌드 또는 다른 편집기가 데이터를 사용 중입니다. 잠시 후 다시 시도하세요")
        try:
            if self._depth == 0:
                # Lock the persistent data directory inode: cleaning temp cannot
                # unlink a lock file and create two independent lock owners.
                self._file = os.open(ROOT / "data", os.O_RDONLY)
                try:
                    while True:
                        try:
                            fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            if time.monotonic() >= deadline:
                                raise EditorBusy("빌드 또는 다른 편집기가 데이터를 사용 중입니다. 잠시 후 다시 시도하세요")
                            time.sleep(.02)
                except BaseException:
                    os.close(self._file)
                    self._file = None
                    raise
            self._depth += 1
            return self
        except BaseException:
            self._thread_lock.release()
            raise

    def __exit__(self, *exc):
        try:
            self._depth -= 1
            if self._depth == 0:
                os.close(self._file)
                self._file = None
        finally:
            self._thread_lock.release()


EDITOR_LOCK = EditorLock()


def atomic_write_text(path, text):
    """Stage in project temp; publish one complete UTF-8 file with replace."""
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_bytes(path, payload):
    """Readers see either the old complete file or the new complete file."""
    path = Path(path)
    staging = ROOT / "temp" / "editor_writes"
    staging.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=staging)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_json(path, data, indent=2):
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=indent) + "\n")


def atomic_write_group(writes):
    """Prepare every payload and rollback inode before any publication.

    Caller holds EDITOR_LOCK. A caught publication failure restores old files
    using rename, without allocating their payload again on a full disk.
    """
    staging = ROOT / 'temp' / 'editor_writes'
    staging.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='group_', dir=staging))
    prepared = []
    published = []
    preserve = False
    try:
        for index, (target, payload) in enumerate(writes.items()):
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            old = run / f'{index}.old'
            new = run / f'{index}.new'
            if target.exists():
                os.link(target, old)
            with new.open('xb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(new, target.stat().st_mode & 0o777 if target.exists() else 0o600)
            prepared.append((target, new, old))
        try:
            for target, new, old in prepared:
                published.append((target, old))
                os.replace(new, target)
            for directory in {target.parent for target, _, _ in prepared}:
                fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except BaseException as failure:
            errors = []
            for target, old in reversed(published):
                try:
                    if old.exists():
                        os.replace(old, target)
                    else:
                        target.unlink(missing_ok=True)
                except OSError as exc:
                    errors.append((str(target), str(exc)))
            if errors:
                preserve = True
                raise RuntimeError(f'그룹 저장 복원 실패: {errors}; 복원 데이터: {run}') from failure
            raise
    finally:
        if not preserve:
            shutil.rmtree(run)
