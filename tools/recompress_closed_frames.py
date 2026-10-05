"""Losslessly compact CLOSED capture RGB frames; never alter ledger or endpoints.

Requires an explicit run and --apply. Palette encoding is accepted only after an
exact RGB digest check. A batch's prepared receipt survives interruptions; both
old and replacement images satisfy the same immutable RGB/ledger contract.
Rerun with a fresh work directory after inspecting a failed receipt: existing P
frames are skipped, and never remove a .partial without checking its receipt.
No arbitrary concurrent writer to a CLOSED run is supported (stat/hash/lsof
checks fail closed on detected changes; they are not a hostile-writer lock).
Only post-replacement PNG checks permit read-only FDs of system Spotlight.
"""
from pathlib import Path
import argparse,ctypes,fcntl,hashlib,io,json,os,re,shlex,stat,struct,subprocess,time,zlib
from PIL import Image
from playthrough_capture import verify_parent
ROOT=Path(__file__).resolve().parent.parent
ACTIVE=('measured_live_tty','round32_recovery')

def digest(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def identity(path):
 s=path.lstat();return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,s.st_mode,s.st_uid,s.st_gid,s.st_flags)
SPOTLIGHT_EXECUTABLES=frozenset('/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/'+name for name in ('mdworker','mdworker_shared'))
def process_executable(pid):
 lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
 lib.proc_pidpath.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32];lib.proc_pidpath.restype=ctypes.c_int
 buf=ctypes.create_string_buffer(4096)
 if lib.proc_pidpath(pid,buf,len(buf))<=0:return None
 return str(Path(os.fsdecode(buf.value)).resolve())

def only_spotlight_readers(output,paths,*,allow_vanished=False):
 """Accept exact regular read FDs from the kernel-resolved system indexer only."""
 allowed={str(p) for p in paths};pid=None;entry=None;seen=0
 def valid(record):
  return (record is not None and set(record)=={'f','a','t','n'} and
          record['f'].isdigit() and record['a']=='r' and record['t']=='REG' and record['n'] in allowed)
 try:
  for token in output.split('\0'):
   token=token.removeprefix('\n')
   if not token:continue
   key,value=token[0],token[1:]
   if key in ('p','f') and entry is not None:
    if not valid(entry):return False
    seen+=1;entry=None
   if key=='p':
    if not value.isdigit():return False
    pid=int(value);executable=process_executable(pid)
    if executable not in SPOTLIGHT_EXECUTABLES:
     if not allow_vanished or executable is not None:return False
     try:os.kill(pid,0)
     except ProcessLookupError:pass
     except OSError:return False
     else:return False
   elif key=='f':
    if pid is None:return False
    entry={'f':value}
   elif key in ('a','t','n'):
    if entry is None or key in entry:return False
    entry[key]=value
   else:return False
  if entry is not None:
   if not valid(entry):return False
   seen+=1
  return seen>0
 except (OSError,ValueError):return False

def transient_spotlight_maps(output,paths):
 """Classify handles worth waiting for; never authorizes mapped or vanished PIDs."""
 # Replace known read-only-mmap lsof records with read FD syntax exclusively
 # for the existing trusted-process/path parser, then wait for a fresh result.
 mapped=output.replace('ftxt\0a \0tREG\0','f0\0ar\0tREG\0').replace('fmem\0a \0tREG\0','f0\0ar\0tREG\0')
 return only_spotlight_readers(mapped,paths,allow_vanished=True)

def recheck_partial_spotlight(paths,output,deadline):
 """A partial lsof match may return 1. Recheck both disjoint groups strictly.

 lsof's official tutorial/FAQ distinguish all-name matches from partial ones:
 https://lsof.readthedocs.io/en/stable/tutorial/
 Never accept rc=1 with records directly: every fresh partition must satisfy
 the pre-existing rc=0 exact reader or rc=1 entirely-empty contract.
 """
 listed={token.removeprefix('\n')[1:] for token in output.split('\0')
         if token.removeprefix('\n').startswith('n')}
 groups=([p for p in paths if str(p) in listed],[p for p in paths if str(p) not in listed])
 for group in groups:
  if not group:continue
  remaining=deadline-time.monotonic()
  if remaining<=0:raise ValueError('Partial lsof recheck deadline reached')
  try:
   result=subprocess.run(['/usr/sbin/lsof','-nP','-Fpfatn0','--',*[str(p) for p in group]],capture_output=True,text=True,timeout=remaining)
  except subprocess.TimeoutExpired as exc:raise ValueError('Partial lsof recheck timeout') from exc
  if result.returncode==1 and not result.stdout.strip() and not result.stderr.strip():continue
  if result.returncode==0 and not result.stderr and only_spotlight_readers(result.stdout,group):continue
  if result.returncode in (0,1) and not result.stderr and (only_spotlight_readers(result.stdout,group) or transient_spotlight_maps(result.stdout,group)):
   time.sleep(min(0.05,max(0,deadline-time.monotonic())))
   recheck_partial_spotlight(group,result.stdout,deadline);continue
  raise ValueError('Open file or uncertain partitioned lsof: '+result.stdout+result.stderr)

def unused(paths,allow_spotlight=False):
 if not paths:return
 deadline=time.monotonic()+30.0
 while True:
  result=subprocess.run(['/usr/sbin/lsof','-nP','-Fpfatn0','--',*[str(p) for p in paths]],capture_output=True,text=True)
  if result.returncode==1 and not result.stdout.strip() and not result.stderr.strip():return
  if allow_spotlight and result.returncode==0 and not result.stderr and only_spotlight_readers(result.stdout,paths):return
  if allow_spotlight and result.returncode==1 and not result.stderr and only_spotlight_readers(result.stdout,paths):
   recheck_partial_spotlight(paths,result.stdout,deadline);return
  if allow_spotlight and result.returncode in (0,1) and not result.stderr and transient_spotlight_maps(result.stdout,paths):
   remaining=deadline-time.monotonic()
   if remaining<=0:raise ValueError('Transient Spotlight map deadline reached')
   time.sleep(min(0.05,remaining));continue
  # Spotlight briefly reads freshly replaced PNGs. Wait for the same strict
  # unused condition unless the narrow post-PNG exception above applies;
  # never retry an uncertain failure.
  if result.returncode!=0 or not result.stdout.strip() or result.stderr.strip():break
  remaining=deadline-time.monotonic()
  if remaining<=0:break
  time.sleep(min(0.25,remaining))
 raise ValueError('Open file or uncertain lsof: '+result.stdout+result.stderr)
def sync_dir(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def floor(extra=0):
 v=os.statvfs(ROOT)
 if v.f_bavail*v.f_frsize-extra-8*2**20<15*2**30:raise ValueError('15 GiB preservation floor')
def native_xattrs(path):
 # macOS Python omits os.listxattr; use the system's no-follow APIs directly.
 lib=ctypes.CDLL(None,use_errno=True)
 lib.listxattr.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int];lib.listxattr.restype=ctypes.c_ssize_t
 lib.getxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int];lib.getxattr.restype=ctypes.c_ssize_t
 name=os.fsencode(path);size=lib.listxattr(name,None,0,1)
 if size<0:raise OSError(ctypes.get_errno(),'listxattr failed')
 names=ctypes.create_string_buffer(size)
 if lib.listxattr(name,names,size,1)!=size:raise ValueError('xattr list changed')
 result={}
 for key in names.raw.split(b'\0'):
  if not key:continue
  n=lib.getxattr(name,key,None,0,0,1)
  if n<0:raise OSError(ctypes.get_errno(),'getxattr failed')
  buf=ctypes.create_string_buffer(n)
  if lib.getxattr(name,key,buf,n,0,1)!=n:raise ValueError('xattr value changed')
  result[key]=buf.raw
 return result

def preserve_xattrs(source,stage):
 original=native_xattrs(source);existing=native_xattrs(stage)
 # Usually only identical com.apple.provenance exists. Refuse to discard any
 # metadata; unusual differing attrs are unsupported by this pilot tool.
 if original!=existing:raise ValueError('Staged xattrs differ; original preserved')

def plain_rgb_chunks(raw):
 if raw[:8]!=b'\x89PNG\r\n\x1a\n':return False
 offset=8;types=[]
 while offset+12<=len(raw):
  size=struct.unpack_from('>I',raw,offset)[0];kind=raw[offset+4:offset+8];end=offset+12+size
  if end>len(raw) or kind not in (b'IHDR',b'IDAT',b'IEND'):return False
  if zlib.crc32(raw[offset+4:end-4])!=struct.unpack_from('>I',raw,end-4)[0]:return False
  types.append(kind);offset=end
  if kind==b'IEND':break
 return offset==len(raw) and len(types)>=3 and types[0]==b'IHDR' and types[-1]==b'IEND' and all(t==b'IDAT' for t in types[1:-1])

def encode_png(raw,rgb,reasons=None):
 def skip(reason):
  if reasons is not None:reasons.append(reason)
  return None
 with Image.open(io.BytesIO(raw)) as image:
  if image.format!='PNG' or image.size!=(240,160) or image.mode!='RGB' or image.info or getattr(image,'n_frames',1)!=1:return skip('unsupported_png_contract')
  if not plain_rgb_chunks(raw):return skip('nonstandard_chunks_or_trailing_data')
  pixels=image.tobytes()
  if digest(pixels)!=rgb:raise ValueError('Original RGB mismatch')
  if image.getcolors(256) is None:return skip('more_than_256_colors')
  palette=image.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  if palette.convert('RGB').tobytes()!=pixels:return skip('inexact_palette')
  out=io.BytesIO();palette.save(out,format='PNG',compress_level=6);new=out.getvalue()
 with Image.open(io.BytesIO(new)) as restored:
  if restored.size!=(240,160) or restored.mode!='P' or restored.info or digest(restored.convert('RGB').tobytes())!=rgb:return skip('inexact_encoded_rgb')
 return new if len(new)<len(raw) else skip('not_smaller')

def reference_exclusions():
 """Conservatively exclude whole runs referenced by durable frame-file proofs."""
 result=subprocess.run(['rg','--threads','1','--no-mmap','--text','--pcre2','--no-ignore','--hidden','-l',r'frames/[0-9a-f]{64}\.png',str(ROOT),
   '--glob','*.json','--glob','*.jsonl','--glob','*.md','--glob','*.py',
   '--glob','!**/.git/**','--glob','!**/node_modules/**','--glob','!**/frames/**',
   '--glob','!**/frames.jsonl','--glob','!/temp/frame_recompress*/**'],cwd=ROOT,capture_output=True,text=True)
 if result.returncode not in (0,1) or result.stderr:raise ValueError('Reference scan failed')
 runs=set();digests=set();evidence={}
 for name in result.stdout.splitlines():
  path=Path(name);before=identity(path);found=set()
  with path.open(errors='replace') as source:
   while text:=source.readline(1024*1024+1):
    if len(text)>1024*1024:raise ValueError('Oversized reference line requires bounded review: '+str(path))
    found.update(re.findall(r'frames/([0-9a-f]{64})\.png',text))
    for match in re.finditer(r'(output/qa/[^\s"\'<>]+?)/frames/[0-9a-f]{64}\.png',text):runs.add((ROOT/match.group(1)).resolve())
  if not found:raise ValueError('Frame reference could not be resolved')
  evidence[str(path.relative_to(ROOT))]=file_sha(path)
  if identity(path)!=before:raise ValueError('Frame reference changed during scan')
  digests.update(found)
 return runs,digests,evidence

def text_sha_tokens(path):
 tokens=set();carry=b'';first=True
 pattern=rb'(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])'
 with path.open('rb') as stream:
  while block:=stream.read(1024*1024):
   data=carry+block
   tokens.update(m.group().decode('ascii').lower() for m in re.finditer(pattern,data)
                 if (first or m.start()>0) and m.end()<len(data))
   carry=data[-66:];first=False
  tokens.update(m.group().decode('ascii').lower() for m in re.finditer(pattern,carry)
                if m.start()>0 or len(carry)<66)
 return tokens

def file_sha_references():
 result=subprocess.run(['rg','--threads','1','--no-mmap','--text','--pcre2','--no-ignore','--hidden','-l',r'(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',str(ROOT),
  '--glob','!**/.git/**','--glob','!**/node_modules/**','--glob','!**/frames/**',
  '--glob','!**/frames.jsonl','--glob','!/temp/frame_recompress*/**',
  '--glob','!/temp/cleanup_2026-10-03/**',
  '--glob','!**/*.{mkv,gba,png,ss0,gz,raw,sav,so,dylib,bin,bps,ips,zip,7z,o}'],cwd=ROOT,capture_output=True,text=True)
 if result.returncode not in (0,1) or result.stderr:raise ValueError('SHA reference scan failed')
 tokens=set();guards={}
 for name in result.stdout.splitlines():
  p=Path(name);before=identity(p)
  tokens.update(text_sha_tokens(p))
  if identity(p)!=before:raise ValueError('Reference changed during scan')
  guards[p]=before
 return tokens,guards

def historical_quiescence():
 """Explicit historical maintenance requires all capture processes to be stopped.

 A stopped verifier may retain an in-memory PNG cache: it rehashes file bytes on
 reuse, so changed encodings will be decoded again. It must remain stopped until
 this maintenance and its final parent verification finish.
 """
 result=subprocess.run(['ps','-axww','-o','pid=,state=,command='],capture_output=True,text=True)
 if result.returncode or result.stderr:raise ValueError('Cannot establish capture quiescence')
 for line in result.stdout.splitlines():
  parts=line.strip().split(None,2)
  if len(parts)!=3:raise ValueError('Malformed process inventory')
  pid,state,command=parts
  first=Path(command.split(None,1)[0]).name.lower()
  if not (first.startswith('python') or first.startswith('mgbah')):continue
  try:argv=shlex.split(command)
  except ValueError:raise ValueError('Unparseable process inventory')
  names={Path(a).name for a in argv}
  capture=any(n.startswith('playthrough_capture') for n in names)
  if any(a.startswith(('-c','-m')) for a in argv) and 'playthrough_capture' in command:capture=True
  native=any(n.startswith('mgbah') for n in names)
  if (capture or native) and 'T' not in state and int(pid)!=os.getpid():
   raise ValueError('Historical cleanup requires paused/closed capture processes')

def run_guard(run,allow_historical=False):
 if allow_historical:historical_quiescence()
 if run.resolve()!=run or not run.is_relative_to(ROOT/'output/qa') or (not allow_historical and any(x in str(run) for x in ACTIVE)):raise ValueError('Run outside closed-capture scope')
 e=json.loads((run/'exit.json').read_text());cp=json.loads((run/'resume.checkpoint.json').read_text())
 if e['status']!='closed' or e['emulator_exit_code']!=0 or e.get('cleanup_errors'):raise ValueError('Run is not cleanly CLOSED')
 if e['committed_core_frame']!=e['last_observed_core_frame'] or cp['core_frame']!=e['committed_core_frame'] or cp['ledger_bytes']!=(run/'frames.jsonl').stat().st_size:raise ValueError('Uncommitted capture suffix')
 protected=[run/n for n in ['exit.json','baseline.json','baseline.gba','frames.jsonl','actions.jsonl','resume.checkpoint.json','resume.ss0']]
 for p in protected:
  if p.resolve()!=p or not stat.S_ISREG(p.lstat().st_mode):raise ValueError('Invalid protected file')
 unused(protected)
 return cp,protected,{p:identity(p) for p in protected},{p:file_sha(p) for p in protected}

def unchanged(identities):
 if any(identity(p)!=value for p,value in identities.items()):raise ValueError('Closed capture metadata changed')

def append_rows(stream,rows):
 for row in rows:stream.write(json.dumps(row)+'\n')
 stream.flush();os.fsync(stream.fileno());fcntl.fcntl(stream.fileno(),fcntl.F_FULLFSYNC)

def select_window(paths,start_after,max_files):
 if start_after and not re.fullmatch('[0-9a-f]{64}',start_after):raise ValueError('Invalid resume cursor')
 paths=[p for p in paths if p.stem>start_after]
 return paths[:max_files] if max_files else paths

def process_run(run,work,batch_size,max_files,receipt,progress,start_after='',excluded_digests=frozenset(),allow_historical=False,excluded_file_shas=frozenset(),reference_guard=None):
 cp,protected,guards,hashes=run_guard(run,allow_historical)
 endpoints={p:file_sha(p) for p in run.iterdir() if p.is_file() and (p.suffix in ('.png','.ss0') or p.name.endswith('.checkpoint.json'))}
 verify_parent(run/'resume.checkpoint.json',cp)
 expected=set()
 with (run/'frames.jsonl').open() as stream:
  for line in stream:
   row=json.loads(line);rgb=row['rgb_sha256']
   if not re.fullmatch('[0-9a-f]{64}',rgb) or row['image']!='frames/'+rgb+'.png':raise ValueError('Noncanonical ledger frame')
   expected.add(rgb)
 eligible=[]
 for rgb in sorted(expected):
  p=run/'frames'/(rgb+'.png');s=p.lstat()
  if p.resolve()!=p or not stat.S_ISREG(s.st_mode):raise ValueError('Invalid frame path')
  if s.st_nlink==1 and rgb not in excluded_digests:eligible.append(p)
 if start_after and start_after not in expected:raise ValueError('Resume cursor is not in the run ledger')
 remaining_candidates=len([p for p in eligible if p.stem>start_after])
 eligible=select_window(eligible,start_after,max_files)
 totals={'run':str(run.relative_to(ROOT)),'considered':0,'replaced':0,'saved_bytes':0,'saved_allocated_bytes':0,'last_considered':start_after,'skipped':{}}
 for offset in range(0,len(eligible),batch_size):
  if allow_historical:historical_quiescence()
  if reference_guard:reference_guard()
  start=time.monotonic();paths=eligible[offset:offset+batch_size];unchanged(guards);floor();unused(protected+paths);prepared=[];skipped=[]
  acl=subprocess.run(['/bin/ls','-lde',*map(str,paths)],capture_output=True,text=True)
  if acl.returncode or acl.stderr or len(acl.stdout.splitlines())!=len(paths) or any(line.split()[0].endswith('+') for line in acl.stdout.splitlines()):raise ValueError('Extended ACL or uncertain ACL inspection')
  for p in paths:
   initial=identity(p)
   if initial[5]!=1:raise ValueError('New frame hard link')
   raw=p.read_bytes();rgb=p.stem;reasons=[]
   if digest(raw) in excluded_file_shas:
    totals['skipped']['referenced_file_sha256']=totals['skipped'].get('referenced_file_sha256',0)+1
    skipped.append({'path':str(p.relative_to(ROOT)),'status':'skipped','reason':'referenced_file_sha256','original_sha256':digest(raw),'rgb_sha256':rgb});continue
   new=encode_png(raw,rgb,reasons)
   if identity(p)!=initial:raise ValueError('Source changed during encoding')
   if new is None:
    reason=reasons[0];totals['skipped'][reason]=totals['skipped'].get(reason,0)+1
    skipped.append({'path':str(p.relative_to(ROOT)),'status':'skipped','reason':reason,'original_sha256':digest(raw),'rgb_sha256':rgb})
    continue
   floor(len(new));stage=work/(rgb+'.partial')
   with stage.open('xb') as out:out.write(new);out.flush();os.fsync(out.fileno())
   os.chmod(stage,stat.S_IMODE(initial[6]))
   st=p.stat();os.utime(stage,ns=(st.st_atime_ns,st.st_mtime_ns))
   if identity(stage)[7:]!=initial[7:]:raise ValueError('Stage ownership or flags differ')
   if file_sha(stage)!=digest(new):raise ValueError('Staged file differs')
   # Preserve any xattrs; mode is retained above. Reject extended ACLs rather
   # than silently discarding them (macOS ls mode has '+' for an ACL).
   preserve_xattrs(p,stage)
   with stage.open('rb') as synced:os.fsync(synced.fileno())
   prepared.append({'path':p,'stage':stage,'identity':initial,'rgb':rgb,'old_sha':digest(raw),'new_sha':digest(new),'old_bytes':len(raw),'new_bytes':len(new),'old_blocks':p.stat().st_blocks*512})
  unused(protected+paths);unchanged(guards)
  if allow_historical:historical_quiescence()
  if reference_guard:reference_guard()
  for item in prepared:
   if identity(item['path'])!=item['identity'] or file_sha(item['path'])!=item['old_sha']:raise ValueError('Original changed before batch')
  records=[{'path':str(i['path'].relative_to(ROOT)),'original_sha256':i['old_sha'],'new_sha256':i['new_sha'],'rgb_sha256':i['rgb'],'old_bytes':i['old_bytes'],'new_bytes':i['new_bytes'],'status':'verified_before_replace'} for i in prepared]
  sync_dir(work)
  append_rows(receipt,skipped+records)
  for item in prepared:
   p=item['path'];unchanged(guards)
   if identity(p)!=item['identity'] or file_sha(p)!=item['old_sha'] or file_sha(item['stage'])!=item['new_sha']:raise ValueError('Immediate replace guard failed')
   os.replace(item['stage'],p)
   if file_sha(p)!=item['new_sha']:raise ValueError('Installed bytes differ')
   with Image.open(p) as im:
    if im.size!=(240,160) or digest(im.convert('RGB').tobytes())!=item['rgb']:raise ValueError('Installed RGB differs')
   totals['saved_allocated_bytes']+=item['old_blocks']-p.stat().st_blocks*512
  sync_dir(run/'frames');unused(protected);unused(paths,allow_spotlight=True);unchanged(guards)
  for item in prepared:
   if file_sha(item['path'])!=item['new_sha']:raise ValueError('Installed bytes changed after reader check')
  append_rows(receipt,[dict(r,status='replaced_verified') for r in records]);totals['considered']+=len(paths);totals['replaced']+=len(prepared);totals['saved_bytes']+=sum(i['old_bytes']-i['new_bytes'] for i in prepared);totals['last_considered']=paths[-1].stem
  v=os.statvfs(ROOT);event=dict(totals,batch_seconds=round(time.monotonic()-start,3),free_gib=round(v.f_bavail*v.f_frsize/2**30,3));progress.write(json.dumps(event)+'\n');progress.flush();print(json.dumps(event),flush=True)
 unchanged(guards)
 if any(file_sha(p)!=h for p,h in (hashes|endpoints).items()):raise ValueError('Protected endpoint or capture bytes changed')
 verify_parent(run/'resume.checkpoint.json',cp)
 return dict(totals,descendant_reverification_required=allow_historical,verify_parent_before_after=True,endpoint_files_unchanged=len(endpoints),remaining_after_window=remaining_candidates-len(eligible))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='append',required=True);ap.add_argument('--work',required=True);ap.add_argument('--batch-size',type=int,default=200);ap.add_argument('--max-files',type=int,default=200);ap.add_argument('--start-after',default='');ap.add_argument('--apply',action='store_true');ap.add_argument('--allow-historical-closed',action='store_true',help='Allow formerly active or referenced closed runs only while all captures are paused; preserve every individually referenced PNG');args=ap.parse_args()
 if not args.apply:raise SystemExit('Explicit --apply required; use the recorded benchmark first')
 if not 1<=args.batch_size<=200 or args.max_files<0:raise ValueError('Invalid batch bounds')
 work=Path(args.work).absolute()
 if work.resolve()!=work or work.parent!=ROOT/'temp' or not work.name.startswith('frame_recompress'):raise ValueError('Work must be an unsymlinked temp/frame_recompress* directory')
 if args.start_after and len(args.run)!=1:raise ValueError('A cursor applies to one run only')
 work.mkdir(exist_ok=False);floor();excluded,excluded_digests,evidence=reference_exclusions();runs=[Path(p).absolute() for p in args.run]
 if len(set(runs))!=len(runs) or (not args.allow_historical_closed and any(p in excluded for p in runs)):raise ValueError('Duplicate or file-SHA-referenced run')
 lock=os.open(ROOT/'temp/frame_recompression.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  file_refs,reference_identities=file_sha_references() if args.allow_historical_closed else (set(),{})
  excluded_digests=set(excluded_digests)|file_refs
  reference_guard=(lambda:unchanged(reference_identities)) if reference_identities else None
  (work/'protected_file_shas.json').write_text(json.dumps(sorted(file_refs)))
  (work/'protected_rgb_digests.json').write_text(json.dumps(sorted(excluded_digests)))
  (work/'invocation.json').write_text(json.dumps({'runs':[str(r) for r in runs],'source_sha256':file_sha(Path(__file__)),'reference_evidence':evidence,'max_files':args.max_files,'batch_size':args.batch_size,'start_after':args.start_after,'excluded_digest_count':len(excluded_digests),'allow_historical_closed':args.allow_historical_closed},indent=2))
  with (work/'receipts.jsonl').open('x') as receipt,(work/'progress.jsonl').open('x') as progress:
   summaries=[process_run(run,work,args.batch_size,args.max_files,receipt,progress,args.start_after,excluded_digests,allow_historical=args.allow_historical_closed,excluded_file_shas=file_refs,reference_guard=reference_guard) for run in runs]
  (work/'summary.json').write_text(json.dumps(summaries,indent=2))
 finally:os.close(lock)
if __name__=='__main__':main()
