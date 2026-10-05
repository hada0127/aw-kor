"""Opt-in bounded FIFO transport for the unchanged native `shot` protocol.

One producer, one synchronous capture at a time. A failed transfer poisons this
transport; caller must terminate its own producer before closing the transport.
No framebuffer bytes are written to regular files by this module.
"""
from __future__ import annotations
import math
import os
from pathlib import Path
import select
import stat
import struct
import threading
import time

FRAME_SIZE = 5 + 240 * 160 * 4
HEADER = struct.pack('<HHB', 240, 160, 4)


class FrameFIFO:
    def __init__(self, path: Path, timeout: float):
        self.path = Path(path).absolute()
        if self.path.resolve() != self.path or any(c.isspace() for c in str(self.path)):
            raise ValueError('Noncanonical FIFO path')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('FIFO timeout must be finite and positive')
        self.timeout = timeout
        self.failed = False
        self.closed = False
        self.thread = None
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        # Existing regular files, FIFOs and symlinks are never reused or removed.
        os.mkfifo(self.path, 0o600)
        st = self.path.lstat()
        self.identity = (st.st_dev, st.st_ino)
        self.fd = None
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            self._check_path()
        except BaseException:
            if self.fd is not None:
                os.close(self.fd)
            if self._owned():
                self.path.unlink()
            raise

    def _owned(self):
        try:
            st = self.path.lstat()
            return stat.S_ISFIFO(st.st_mode) and (st.st_dev, st.st_ino) == self.identity
        except FileNotFoundError:
            return False

    def _check_path(self):
        if not self._owned():
            raise RuntimeError('Frame FIFO path was replaced')
        st = os.fstat(self.fd)
        if not stat.S_ISFIFO(st.st_mode) or (st.st_dev, st.st_ino) != self.identity:
            raise RuntimeError('Frame FIFO descriptor differs')

    def _empty(self):
        try:
            data = os.read(self.fd, 1)
        except BlockingIOError as exc:
            raise RuntimeError('Unexpected frame FIFO writer remains open') from exc
        if data:
            raise RuntimeError('Unexpected leftover frame FIFO data')

    def capture(self, send_shot):
        """Start reader before calling send_shot(path), then require close + reply.

        send_shot must enforce its own bounded protocol timeout and validate its
        response. No subsequent request is allowed following any error.
        """
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Concurrent frame FIFO capture')
        try:
            if self.closed or self.failed:
                raise RuntimeError('Frame FIFO is closed or failed')
            self._check_path()
            self._empty()
            self.cancel.clear()
            done = threading.Event()
            result = {}
            deadline = time.monotonic() + self.timeout

            def reader():
                data = bytearray()
                received = False
                oversized = False
                try:
                    while not self.cancel.is_set():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError('Frame FIFO transfer timed out')
                        readable, _, _ = select.select([self.fd], [], [], min(remaining, .01))
                        if not readable:
                            continue
                        try:
                            block = os.read(self.fd, 65536)
                        except BlockingIOError:
                            continue
                        if not block:
                            if received:
                                if oversized or len(data) != FRAME_SIZE:
                                    raise RuntimeError('Unexpected framebuffer length')
                                if data[:5] != HEADER:
                                    raise RuntimeError('Unexpected framebuffer header')
                                result['data'] = bytes(data)
                                return
                            # No writer yet, or a zero-byte failed writer. Deadline
                            # is the authority; avoid spinning on initial FIFO EOF.
                            self.cancel.wait(min(remaining, .001))
                            continue
                        received = True
                        capacity = FRAME_SIZE + 1 - len(data)
                        data.extend(block[:max(0, capacity)])
                        oversized |= len(data) > FRAME_SIZE
                        # Continue draining on oversized data so an ordinary
                        # producer can close and report failure without deadlock.
                    raise RuntimeError('Frame FIFO transfer cancelled')
                except BaseException as exc:
                    result['error'] = exc
                finally:
                    done.set()

            self.thread = threading.Thread(target=reader, name='frame-fifo-reader', daemon=True)
            self.thread.start()
            try:
                send_shot(self.path)
                if not done.wait(max(0, deadline - time.monotonic())):
                    raise TimeoutError('Frame FIFO transfer timed out')
                if 'error' in result:
                    raise result['error']
                self._check_path()
                self._empty()
                return result['data']
            finally:
                self.cancel.set()
                self.thread.join(timeout=.2)
                if self.thread.is_alive():
                    raise RuntimeError('Frame FIFO reader did not stop')
        except BaseException:
            self.failed = True
            raise
        finally:
            self.lock.release()

    def close(self):
        if self.closed:
            return
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Cannot close an active frame FIFO transfer')
        try:
            self.cancel.set()
            if self.thread:
                self.thread.join(timeout=.2)
                if self.thread.is_alive():
                    raise RuntimeError('Frame FIFO reader still active')
            os.close(self.fd)
            self.closed = True
            if self._owned():
                self.path.unlink()
            else:
                raise RuntimeError('Frame FIFO path changed before cleanup')
        finally:
            self.lock.release()
