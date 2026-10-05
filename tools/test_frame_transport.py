import hashlib
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest
from frame_transport import FrameFIFO, FRAME_SIZE, HEADER

ROOT = Path(__file__).resolve().parents[1]
FRAME = HEADER + bytes(range(256)) * 600
assert len(FRAME) == FRAME_SIZE


class FrameTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.transport = FrameFIFO(self.root / 'frame.fifo', .5)
        self.addCleanup(self.transport.close)

    @staticmethod
    def writer(data, chunks=8192):
        def send(path):
            with path.open('wb') as stream:
                for i in range(0, len(data), chunks):
                    stream.write(data[i:i + chunks])
        return send

    def test_exact_repeat_no_regular_frame_file(self):
        inode = self.transport.path.stat().st_ino
        for _ in range(8):
            data = self.transport.capture(self.writer(FRAME, 1021))
            self.assertEqual(hashlib.sha256(data).digest(), hashlib.sha256(FRAME).digest())
            self.assertEqual(self.transport.path.stat().st_ino, inode)
            self.assertFalse(self.transport.thread.is_alive())
        self.assertEqual(list(self.root.iterdir()), [self.transport.path])
        self.assertEqual(self.transport.path.stat().st_size, 0)

    def test_delayed_writer_no_initial_eof_confusion(self):
        def send(path):
            time.sleep(.04)
            self.writer(FRAME)(path)
        self.assertEqual(self.transport.capture(send), FRAME)

    def test_short_and_invalid_header(self):
        with self.assertRaisesRegex(RuntimeError, 'length'):
            self.transport.capture(self.writer(FRAME[:-1]))
        self.assertTrue(self.transport.failed)
        self.assertFalse(self.transport.thread.is_alive())

    def test_bad_header(self):
        with self.assertRaisesRegex(RuntimeError, 'header'):
            self.transport.capture(self.writer(b'wrong' + FRAME[5:]))

    def test_oversize_drained_and_failed_no_stale_next_capture(self):
        with self.assertRaisesRegex(RuntimeError, 'length'):
            self.transport.capture(self.writer(FRAME + b'x' * 200000))
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            self.transport.capture(self.writer(FRAME))
        self.assertFalse(self.transport.thread.is_alive())

    def test_no_writer_timeout_thread_joined(self):
        self.transport.timeout = .035
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.transport.capture(lambda path: None)
        self.assertLess(time.monotonic() - start, .3)
        self.assertFalse(self.transport.thread.is_alive())

    def test_empty_writer_timeout(self):
        self.transport.timeout = .035
        with self.assertRaises(TimeoutError):
            self.transport.capture(self.writer(b''))
        self.assertFalse(self.transport.thread.is_alive())

    def test_command_failure_after_write_and_before_write(self):
        def send(path):
            self.writer(FRAME)(path)
            raise RuntimeError('writer reply failed')
        with self.assertRaisesRegex(RuntimeError, 'writer reply failed'):
            self.transport.capture(send)
        self.assertFalse(self.transport.thread.is_alive())

    def test_command_failure_no_writer(self):
        def send(path):
            raise RuntimeError('producer failed')
        with self.assertRaisesRegex(RuntimeError, 'producer failed'):
            self.transport.capture(send)
        self.assertFalse(self.transport.thread.is_alive())

    def test_writer_not_closed_before_timeout(self):
        self.transport.timeout = .035
        writer_fd = None
        def send(path):
            nonlocal writer_fd
            writer_fd = os.open(path, os.O_WRONLY)
            os.write(writer_fd, b'x')
        try:
            with self.assertRaises(TimeoutError):
                self.transport.capture(send)
            self.assertFalse(self.transport.thread.is_alive())
        finally:
            if writer_fd is not None:
                os.close(writer_fd)

    def test_leftover_bytes_rejected_before_command(self):
        fd = os.open(self.transport.path, os.O_WRONLY)
        os.write(fd, b'stale'); os.close(fd)
        called = []
        with self.assertRaisesRegex(RuntimeError, 'leftover'):
            self.transport.capture(lambda path: called.append(path))
        self.assertEqual(called, [])

    def test_open_writer_rejected_before_command(self):
        fd = os.open(self.transport.path, os.O_WRONLY)
        try:
            with self.assertRaisesRegex(RuntimeError, 'writer remains'):
                self.transport.capture(lambda path: None)
        finally:
            os.close(fd)

    def test_symlink_and_existing_path_not_removed(self):
        target = self.root / 'untouched'; target.write_bytes(b'proof')
        link = self.root / 'link'; link.symlink_to(target)
        for path in (link, target, self.transport.path):
            with self.assertRaises((ValueError, FileExistsError)):
                FrameFIFO(path, 1)
        self.assertEqual(target.read_bytes(), b'proof')

    def test_replaced_fifo_rejected_and_cleanup_does_not_unlink_substitute(self):
        self.transport.path.unlink()
        self.transport.path.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'replaced'):
            self.transport.capture(lambda path: None)
        with self.assertRaisesRegex(RuntimeError, 'cleanup'):
            self.transport.close()
        self.assertEqual(self.transport.path.read_bytes(), b'keep')

    def test_replacement_during_command_rejected(self):
        def send(path):
            self.writer(FRAME)(path)
            path.unlink(); path.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'replaced'):
            self.transport.capture(send)
        with self.assertRaisesRegex(RuntimeError, 'cleanup'):
            self.transport.close()

    def test_concurrent_capture_rejected(self):
        self.transport.lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, 'Concurrent'):
                self.transport.capture(lambda path: None)
        finally:
            self.transport.lock.release()

    def test_invalid_timeout(self):
        for timeout in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                FrameFIFO(self.root / 'bad', timeout)
        self.assertFalse((self.root / 'bad').exists())

if __name__ == '__main__':
    unittest.main()
