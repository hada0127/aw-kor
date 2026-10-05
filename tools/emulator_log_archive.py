"""Opt-in bounded FIFO log capture. No emulator commands and no raw-log deletion."""
from pathlib import Path
import fcntl,gzip,hashlib,json,os,select,shutil,stat,threading,time

CHUNK=65536
SYNC_BYTES=1024*1024

def verification_timeout(raw_bytes, minimum=30):
 return max(minimum, raw_bytes/(1024*1024)+30)  # Allow at least 1 MiB/s restore throughput.

def durable(stream):
 stream.flush();os.fsync(stream.fileno())
 if hasattr(fcntl,'F_FULLFSYNC'):fcntl.fcntl(stream.fileno(),fcntl.F_FULLFSYNC)

def sync_dir(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

class LogArchive:
 def __init__(self,directory,min_free_bytes):
  self.directory=Path(directory).resolve();self.minimum=min_free_bytes
  self.fifo=self.directory/'emulator.log.fifo';self.stage=self.directory/'emulator.log.gz.partial';self.archive=self.directory/'emulator.log.gz'
  self.receipt=self.directory/'emulator.log.archive.json';self.failure_receipt=self.directory/'emulator.log.archive.failed.json'
  self.exited=threading.Event();self.abort_event=threading.Event();self.received=threading.Event()
  self.error=None;self.raw_sha=hashlib.sha256();self.raw_bytes=0;self.finished=False;self.thread=None;self.fd=None;self.durable_bytes=0
  if any(p.exists() or p.is_symlink() for p in (self.fifo,self.stage,self.archive,self.receipt,self.failure_receipt)):
   raise FileExistsError('Log archive destination already exists')
  self.check_space()
  os.mkfifo(self.fifo,0o600);self.fifo_identity=(self.fifo.stat().st_dev,self.fifo.stat().st_ino)
  try:
   self.fd=os.open(self.fifo,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
   self.thread=threading.Thread(target=self._collect,name='emulator-log-gzip',daemon=True);self.thread.start()
  except BaseException:
   if self.fd is not None:os.close(self.fd)
   self._remove_fifo();raise
 def check_space(self):
  if shutil.disk_usage(self.directory).free<self.minimum+2*CHUNK:
   raise RuntimeError('Log archive disk reserve reached')
 def check(self):
  if self.error is not None:raise RuntimeError('Log archive collector failed: '+repr(self.error)) from self.error
  if self.thread and not self.thread.is_alive() and not self.exited.is_set():
   raise RuntimeError('Log archive collector ended before producer shutdown')
 def wait_started(self,timeout):
  deadline=time.monotonic()+timeout
  while not self.received.wait(min(.05,max(0,deadline-time.monotonic()))):
   self.check()
   if time.monotonic()>=deadline:raise TimeoutError('Native log FIFO produced no startup bytes')
  self.check()
 def _collect(self):
  try:
   with self.stage.open('xb') as raw:
    try:
     with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=1,mtime=0,filename='') as compressed:
      while True:
       if self.abort_event.is_set():raise RuntimeError('Log collection aborted')
       ready,_,_=select.select([self.fd],[],[],.05)
       if not ready:
        if self.exited.is_set():
         # Explicit read distinguishes EOF from a quiet FIFO with a remaining writer.
         try:block=os.read(self.fd,CHUNK)
         except BlockingIOError:continue
        else:continue
       else:
        try:block=os.read(self.fd,CHUNK)
        except BlockingIOError:continue
       if not block:
        if self.exited.is_set():break
        self.abort_event.wait(.02);continue  # Startup EOF is not completion.
       self.check_space();compressed.write(block)
       self.raw_sha.update(block);self.raw_bytes+=len(block);self.received.set()
       if self.raw_bytes-self.durable_bytes>=SYNC_BYTES:
        compressed.flush();durable(raw);self.durable_bytes=self.raw_bytes
    finally:
     durable(raw)  # Preserve a recoverable gzip even on a collector exception.
  except BaseException as exc:self.error=exc
  finally:
   if self.fd is not None:os.close(self.fd);self.fd=None
 def _remove_fifo(self):
  try:
   s=self.fifo.lstat()
   if stat.S_ISFIFO(s.st_mode) and (s.st_dev,s.st_ino)==self.fifo_identity:self.fifo.unlink();sync_dir(self.directory)
  except FileNotFoundError:pass
 def _write_receipt(self,path,value):
  with path.open('x') as out:json.dump(value,out,indent=2);out.write('\n');durable(out)
  sync_dir(self.directory)
 def finish(self,*,producer_exited,successful,timeout=30):
  """Caller must stop/reap the producer first. Failure never creates a success receipt."""
  if self.finished:raise RuntimeError('Log archive finish called twice')
  self.finished=True
  failure=None
  try:
   if not producer_exited:raise RuntimeError('Producer must exit before log finalization')
   self.exited.set();self.thread.join(timeout)
   if self.thread.is_alive():raise TimeoutError('Log FIFO drain timeout')
   self.check()
   if not successful:raise RuntimeError('Producer/session did not close successfully')
   restored_sha=hashlib.sha256();restored_bytes=0;deadline=time.monotonic()+verification_timeout(self.raw_bytes,timeout)
   with gzip.open(self.stage,'rb') as restored:
    while True:
     if time.monotonic()>deadline:raise TimeoutError('Log restore verification timeout')
     block=restored.read(CHUNK)
     if not block:break
     restored_sha.update(block);restored_bytes+=len(block)
   if restored_sha.digest()!=self.raw_sha.digest() or restored_bytes!=self.raw_bytes:
    raise RuntimeError('Log restored stream SHA/length mismatch')
   with self.stage.open('rb') as stream:archive_sha=hashlib.file_digest(stream,'sha256').hexdigest()
   archive_bytes=self.stage.stat().st_size
   os.link(self.stage,self.archive);sync_dir(self.directory)
   result={'status':'verified','raw_sha256':self.raw_sha.hexdigest(),'raw_bytes':self.raw_bytes,
           'restored_sha256':restored_sha.hexdigest(),'restored_bytes':restored_bytes,
           'archive_sha256':archive_sha,'archive_bytes':archive_bytes,'archive':self.archive.name,
           'scope':'Exact bytes received from native FIFO; producer/session closed successfully'}
   self._write_receipt(self.receipt,result)
   self.stage.unlink();sync_dir(self.directory)
   return result
  except BaseException as exc:
   failure=exc;self.abort_event.set();self.thread.join(min(timeout,1))
   if not self.failure_receipt.exists():
    self._write_receipt(self.failure_receipt,{'status':'failed','error':repr(exc),'collector_error':repr(self.error),
      'received_bytes':self.raw_bytes,'received_sha256':self.raw_sha.hexdigest(),'partial':self.stage.name,
      'worker_stopped':not self.thread.is_alive(),'periodically_synced_raw_bytes':self.durable_bytes,
      'scope':'Received prefix only; no success claim. Abrupt process death may leave a truncated gzip tail; bytes not received cannot be recovered.'})
   raise
  finally:
   if not self.thread.is_alive():self._remove_fifo()
