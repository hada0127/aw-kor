"""Shared build/QA data lock and atomic file publication (macOS/Linux)."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


class DataBusy(RuntimeError):
    pass


class DataLock:
    """Serialize read/modify/write across build and QA processes."""

    def __init__(self):
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._file = None

    def __enter__(self):
        return self.acquire(timeout=3)

    def acquire(self, timeout=3):
        deadline = time.monotonic() + timeout
        if not self._thread_lock.acquire(timeout=timeout):
            raise DataBusy("다른 작업이 데이터를 사용 중입니다. 잠시 후 다시 시도하세요")
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
                                raise DataBusy("다른 작업이 데이터를 사용 중입니다. 잠시 후 다시 시도하세요")
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


DATA_LOCK = DataLock()


def atomic_write_text(path, text):
    """Stage in project temp; publish one complete UTF-8 file with replace."""
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_bytes(path, payload):
    """Readers see either the old complete file or the new complete file."""
    path = Path(path)
    staging = ROOT / "temp" / "atomic_writes"
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


