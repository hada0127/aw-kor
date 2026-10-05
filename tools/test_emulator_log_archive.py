import gzip,hashlib,json,os,tempfile,threading,time,unittest,subprocess,sys,selectors,zlib
from pathlib import Path
from unittest.mock import patch,Mock
import emulator_log_archive as L
from playthrough_capture import Recorder
ROOT=Path(__file__).resolve().parent.parent

class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=ROOT/'temp');self.root=Path(self.temp.name);self.collectors=[]
 def tearDown(self):
  for collector in self.collectors:
   if not collector.finished:
    try:collector.finish(producer_exited=True,successful=False,timeout=.5)
    except Exception:pass
  self.temp.cleanup()
 def archive(self):
  collector=L.LogArchive(self.root,0);self.collectors.append(collector);return collector
 def write(self,collector,data):
  with collector.fifo.open('wb',buffering=0) as writer:writer.write(data)
 def test_startup_eof_is_not_completion_then_exact_multichunk_archive(self):
  c=self.archive();time.sleep(.03);self.assertTrue(c.thread.is_alive())
  with self.assertRaises(TimeoutError):c.wait_started(.02)
  data=(bytes(range(256))*256)*24
  thread=threading.Thread(target=self.write,args=(c,data));thread.start();c.wait_started(2);thread.join(3);self.assertFalse(thread.is_alive())
  result=c.finish(producer_exited=True,successful=True,timeout=3)
  self.assertEqual(gzip.decompress(c.archive.read_bytes()),data)
  self.assertEqual(result['raw_sha256'],hashlib.sha256(data).hexdigest());self.assertEqual(result['raw_bytes'],len(data))
  self.assertEqual(json.loads(c.receipt.read_text()),result);self.assertFalse(c.fifo.exists());self.assertFalse(c.stage.exists())
 def test_quiet_successful_producer_archives_empty_stream(self):
  c=self.archive();result=c.finish(producer_exited=True,successful=True,timeout=1)
  self.assertEqual(result['raw_bytes'],0);self.assertEqual(gzip.decompress(c.archive.read_bytes()),b'')
 def test_size_scaled_restore_deadline(self):
  self.assertEqual(L.verification_timeout(0),30)
  self.assertGreaterEqual(L.verification_timeout(3*1024**3),3072)
 def test_dangling_symlink_rejected(self):
  (self.root/'emulator.log.gz').symlink_to(self.root/'missing')
  with self.assertRaises(FileExistsError):self.archive()
 def test_failure_preserves_readable_received_prefix(self):
  c=self.archive();data=b'prefix'*20000;self.write(c,data);c.wait_started(1)
  deadline=time.monotonic()+2
  while c.raw_bytes<len(data) and time.monotonic()<deadline:time.sleep(.01)
  with patch.object(c,'check_space',side_effect=OSError('floor')):
   self.write(c,b'rejected');c.thread.join(2)
  with self.assertRaises(RuntimeError):c.finish(producer_exited=True,successful=True)
  self.assertEqual(gzip.decompress(c.stage.read_bytes()),data)
 def test_periodic_sync_before_shutdown(self):
  c=self.archive();data=b'x'*(L.SYNC_BYTES+L.CHUNK);self.write(c,data)
  deadline=time.monotonic()+2
  while c.durable_bytes<L.SYNC_BYTES and time.monotonic()<deadline:time.sleep(.01)
  self.assertGreaterEqual(c.durable_bytes,L.SYNC_BYTES)
  prefix=zlib.decompressobj(31).decompress(c.stage.read_bytes())
  self.assertTrue(data.startswith(prefix));self.assertGreaterEqual(len(prefix),L.SYNC_BYTES)
  c.finish(producer_exited=True,successful=True)
 def test_outstanding_command_collector_error_poison_protocol(self):
  r=Recorder.__new__(Recorder);r.log_archive=Mock();r.log_archive.check.side_effect=[None,RuntimeError('collector')]
  r.proc=Mock();r.proc.poll.return_value=None;r.protocol_failed=False;r.buffer=b'';r.timeout=1
  with self.assertRaisesRegex(RuntimeError,'collector'):r.cmd('frames 1')
  self.assertTrue(r.protocol_failed);r.proc.stdin.write.assert_called_once()
 def test_quiet_fifo_producer_protocol_precedes_first_log(self):
  c=self.archive()
  code="import sys; f=open(sys.argv[1],'wb',buffering=0); command=sys.stdin.readline().strip(); f.write(b'after command\\n'); print('OK '+command,flush=True); f.close()"
  proc=subprocess.Popen([sys.executable,'-c',code,str(c.fifo)],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
  r=Recorder.__new__(Recorder);r.log_archive=c;r.proc=proc;r.protocol_failed=False;r.buffer=b'';r.timeout=2;r.selector=selectors.DefaultSelector();r.selector.register(proc.stdout,selectors.EVENT_READ)
  try:
   self.assertEqual(r.cmd('framecounter'),'OK framecounter');self.assertEqual(proc.wait(timeout=2),0)
   result=c.finish(producer_exited=True,successful=True);self.assertEqual(result['raw_bytes'],14)
  finally:
   if proc.poll() is None:proc.kill();proc.wait()
   proc.stdin.close();proc.stdout.close();r.selector.close()
 def test_producer_must_be_reaped(self):
  c=self.archive()
  with self.assertRaisesRegex(RuntimeError,'Producer must exit'):c.finish(producer_exited=False,successful=True,timeout=.2)
  self.assertFalse(c.thread.is_alive());self.assertFalse(c.receipt.exists())
 def test_open_writer_drain_timeout_is_bounded(self):
  c=self.archive();writer=c.fifo.open('wb',buffering=0);writer.write(b'log\n');c.wait_started(1)
  try:
   start=time.monotonic()
   with self.assertRaisesRegex(TimeoutError,'drain'):c.finish(producer_exited=True,successful=True,timeout=.1)
   self.assertLess(time.monotonic()-start,1);self.assertFalse(c.receipt.exists())
  finally:writer.close()
 def test_collector_error_propagates_and_preserves_failure_evidence(self):
  c=self.archive()
  with patch.object(c,'check_space',side_effect=OSError('disk reserve')):
   self.write(c,b'log\n');c.thread.join(1)
  with self.assertRaisesRegex(RuntimeError,'collector failed'):c.check()
  with self.assertRaises(RuntimeError):c.finish(producer_exited=True,successful=True)
  self.assertTrue(c.stage.exists());self.assertTrue(c.failure_receipt.exists());self.assertFalse(c.receipt.exists())
 def test_restore_mismatch_preserves_stage_and_no_success(self):
  c=self.archive();self.write(c,b'log\n');c.wait_started(1);c.raw_sha=hashlib.sha256(b'wrong')
  with self.assertRaisesRegex(RuntimeError,'SHA/length'):c.finish(producer_exited=True,successful=True)
  self.assertTrue(c.stage.exists());self.assertFalse(c.archive.exists());self.assertFalse(c.receipt.exists())
 def test_existing_archive_or_symlink_not_overwritten(self):
  (self.root/'emulator.log.gz').write_bytes(b'proof')
  with self.assertRaises(FileExistsError):self.archive()
  self.assertEqual((self.root/'emulator.log.gz').read_bytes(),b'proof')
 def test_publication_failure_does_not_report_success(self):
  c=self.archive();self.write(c,b'log\n');c.wait_started(1)
  with patch.object(L.os,'link',side_effect=OSError('publish')):
   with self.assertRaises(OSError):c.finish(producer_exited=True,successful=True)
  self.assertTrue(c.stage.exists());self.assertTrue(c.failure_receipt.exists());self.assertFalse(c.receipt.exists())
 def test_disk_floor_before_fifo_creation(self):
  with patch.object(L.shutil,'disk_usage',return_value=type('Space',(),{'free':0})()):
   with self.assertRaisesRegex(RuntimeError,'reserve'):self.archive()
  self.assertFalse((self.root/'emulator.log.fifo').exists())
 def test_recorder_propagates_archive_failure_before_input(self):
  recorder=Recorder.__new__(Recorder)
  recorder.log_archive=type('Failed',(),{'check':lambda _:(_ for _ in ()).throw(RuntimeError('collector failed'))})()
  with self.assertRaisesRegex(RuntimeError,'collector failed'):recorder.cmd('frames 1')
  with self.assertRaisesRegex(RuntimeError,'collector failed'):recorder.check_disk()

 def test_collector_failure_shutdown_kills_own_child_without_commands(self):
  r=Recorder.__new__(Recorder);r.out=self.root;r.counter=0;r.committed=0;r.last_checkpoint=None;r.protocol_failed=False
  r.proc=Mock();r.proc.returncode=None;r.proc.poll.side_effect=lambda:r.proc.returncode
  r.proc.wait.side_effect=lambda timeout:setattr(r.proc,'returncode',-9)
  r.cmd=Mock();r.checkpoint=Mock();r.selector=Mock();r.log_archive=Mock();r.log_archive.finished=False
  r.log_archive.check.side_effect=RuntimeError('collector failed');r.log_archive.finish.side_effect=RuntimeError('archive failed')
  r.ledger=Mock();r.actions=Mock();r.process_log=Mock()
  result=r.close();r.proc.kill.assert_called_once();r.cmd.assert_not_called();r.checkpoint.assert_not_called()
  self.assertEqual(result['status'],'failed');self.assertTrue(any('collector failed' in x for x in result['cleanup_errors']))
 def test_recorder_archive_failure_prevents_closed_exit(self):
  for failure in [None,RuntimeError('archive receipt failed')]:
   out=self.root/('good' if failure is None else 'bad');out.mkdir()
   recorder=Recorder.__new__(Recorder);recorder.out=out;recorder.counter=0;recorder.committed=0;recorder.last_checkpoint=None;recorder.protocol_failed=False
   recorder.proc=Mock();recorder.proc.returncode=None;recorder.proc.poll.side_effect=lambda:recorder.proc.returncode
   recorder.proc.wait.side_effect=lambda timeout:setattr(recorder.proc,'returncode',0)
   recorder.cmd=Mock();recorder.checkpoint=Mock();recorder.selector=Mock()
   recorder.log_archive=Mock();recorder.log_archive.finished=False;recorder.log_archive.finish.side_effect=failure
   recorder.ledger=Mock();recorder.actions=Mock();recorder.process_log=Mock()
   result=recorder.close()
   self.assertEqual(result['status'],'closed' if failure is None else 'failed')
   self.assertEqual(json.loads((out/'exit.json').read_text())['status'],result['status'])
   recorder.log_archive.finish.assert_called_once_with(producer_exited=True,successful=True)

if __name__=='__main__':unittest.main()
