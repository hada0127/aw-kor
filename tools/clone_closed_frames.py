"""Opt-in byte-identical APFS cloning of ledger frames in two CLOSED runs.

No hardlinks or re-encoding. inode/ctime necessarily change; content, pathname,
creation/mtime, mode/owner/flags/xattrs remain preserved. Target access time
is restored to its value after initial verification reads; source reads may update atime.
A cooperative CLOSED-run ownership contract is required, as with recompression.
APFS st_blocks is not physical exclusive ownership: do not call its sum savings.
ROM mode checks 16MiB SHA, original logo/game code and GBA header checksum;
it does not require an untranslated title. Atomic replacement updates parent mtime.
During ROM probes, do not launch a new recorder or change its ancestry.
"""
import argparse,ctypes,fcntl,io,json,os,re,shlex,stat,struct,subprocess
from pathlib import Path
from PIL import Image
import recompress_closed_frames as C
EXCLUDED=('mission3_day16_round8_cold_live',)
class Attr(ctypes.Structure):
 _fields_=[('count',ctypes.c_ushort),('reserved',ctypes.c_ushort),('common',ctypes.c_uint32),('volume',ctypes.c_uint32),('directory',ctypes.c_uint32),('file',ctypes.c_uint32),('fork',ctypes.c_uint32)]
def birthtime(path):
 lib=ctypes.CDLL(None,use_errno=True)
 lib.getattrlist.argtypes=[ctypes.c_char_p,ctypes.POINTER(Attr),ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong];lib.getattrlist.restype=ctypes.c_int
 attrs=Attr(5,0,0x200,0,0,0,0);buf=ctypes.create_string_buffer(20)
 if lib.getattrlist(os.fsencode(path),ctypes.byref(attrs),buf,20,1):raise OSError(ctypes.get_errno(),'getattrlist birthtime')
 size,sec,nsec=struct.unpack('=Iqq',buf.raw)
 if size!=20:raise ValueError('Unexpected birthtime layout')
 return (sec,nsec)
def restore_birthtime(path,value):
 lib=ctypes.CDLL(None,use_errno=True)
 lib.setattrlist.argtypes=[ctypes.c_char_p,ctypes.POINTER(Attr),ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong];lib.setattrlist.restype=ctypes.c_int
 attrs=Attr(5,0,0x200,0,0,0,0);buf=ctypes.create_string_buffer(struct.pack('=qq',*value),16)
 if lib.setattrlist(os.fsencode(path),ctypes.byref(attrs),buf,16,1):raise OSError(ctypes.get_errno(),'setattrlist birthtime')
def metadata(path):
 s=path.lstat()
 return {'mode':s.st_mode,'uid':s.st_uid,'gid':s.st_gid,'flags':s.st_flags,
         'atime_ns':s.st_atime_ns,'mtime_ns':s.st_mtime_ns,'birthtime':birthtime(path),
         'xattrs':{k.hex():v.hex() for k,v in C.native_xattrs(path).items()}}
def plain_files(paths):
 for p in paths:
  s=p.lstat()
  if p.resolve()!=p or not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_flags or s.st_uid!=os.getuid():raise ValueError('Unsupported frame identity')
 result=subprocess.run(['/bin/ls','-lde',*map(str,paths)],capture_output=True,text=True)
 lines=result.stdout.splitlines()
 if result.returncode or result.stderr or len(lines)!=len(paths) or any(line.split()[0].endswith('+') for line in lines):raise ValueError('ACL unsupported or uncertain')
def clone(source,target,stage):
 lib=ctypes.CDLL(None,use_errno=True)
 lib.clonefile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];lib.clonefile.restype=ctypes.c_int
 lib.copyfile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_uint32];lib.copyfile.restype=ctypes.c_int
 # CLONE_NOFOLLOW | CLONE_NOFOLLOW_ANY. No fallback full copy.
 if lib.clonefile(os.fsencode(source),os.fsencode(stage),9):raise OSError(ctypes.get_errno(),'clonefile')
 # COPYFILE_METADATA = ACL | STAT | XATTR, never COPYFILE_DATA.
 if lib.copyfile(os.fsencode(target),os.fsencode(stage),None,7):raise OSError(ctypes.get_errno(),'copyfile metadata')
def restore_stage_xattrs(stage,expected):
 # copyfile can refresh quarantine timestamps. Restore only staged values to
 # the destination's exact original bytes; never mutate source/target xattrs.
 desired={bytes.fromhex(k):bytes.fromhex(v) for k,v in expected.items()}
 existing=C.native_xattrs(stage)
 if existing.keys()-desired.keys():raise ValueError('Unexpected staged xattr')
 lib=ctypes.CDLL(None,use_errno=True)
 lib.setxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int];lib.setxattr.restype=ctypes.c_int
 for key,value in desired.items():
  if existing.get(key)==value:continue
  buf=ctypes.create_string_buffer(value,len(value))
  if lib.setxattr(os.fsencode(stage),key,buf,len(value),0,1):raise OSError(ctypes.get_errno(),'staged setxattr')
 if C.native_xattrs(stage)!=desired:raise ValueError('Staged xattr restoration differs')
def rgb_guard(raw,stem):
 with Image.open(io.BytesIO(raw)) as im:
  if im.format!='PNG' or im.size!=(240,160) or getattr(im,'n_frames',1)!=1:raise ValueError('Unsupported PNG')
  if C.digest(im.convert('RGB').tobytes())!=stem:raise ValueError('Ledger RGB differs')
def fsync_file(path):
 with path.open('rb') as f:os.fsync(f.fileno());fcntl.fcntl(f.fileno(),fcntl.F_FULLFSYNC)
def replace_pair(source,target,stage,receipt,guards,*,rom_sha=None,source_rom_sha=None,near_rom=False):
 C.floor();C.unchanged(guards);C.unused([source,target]);plain_files([source,target])
 before={p:C.identity(p) for p in (source,target)}
 if stage.parent.stat().st_dev!=before[target][0]:raise ValueError('Stage volume differs')
 if before[source][0]!=before[target][0] or before[source][1]==before[target][1]:raise ValueError('Requires different inodes on one volume')
 if near_rom and (rom_sha is None or source_rom_sha is None):raise ValueError('Near mode requires two ROM hashes')
 if rom_sha is not None and any(before[p][2]!=16777216 for p in (source,target)):raise ValueError('ROM size changed before clone')
 raw=target.read_bytes();source_raw=source.read_bytes();changed_pages=[]
 if near_rom:
  rom_guard(source_raw,source_rom_sha);rom_guard(raw,rom_sha)
  changed_pages=[i for i in range(0,len(raw),4096) if source_raw[i:i+4096]!=raw[i:i+4096]]
  if not changed_pages or len(changed_pages)>1024:raise ValueError('Near ROM requires 1..1024 different 4KiB pages')
  if free_bytes()-16777216-1048576<15*1024**3:raise ValueError('Insufficient floor reserve for private pages')
 else:
  if raw!=source_raw:raise ValueError('PNG/ROM bytes differ')
  if rom_sha is None:rgb_guard(raw,target.stem)
  else:rom_guard(raw,rom_sha)
 C.unchanged(before);original_meta=metadata(target);source_meta=metadata(source)
 clone(source,target,stage)
 if near_rom:
  # Only the private stage is writable. Every differing aligned page is copied
  # from the original target; no translation or new ROM content is generated.
  with stage.open('r+b') as stream:
   for offset in changed_pages:
    C.floor();stream.seek(offset)
    if stream.write(raw[offset:offset+4096])!=4096:raise OSError('Short stage page write')
   stream.flush();os.fsync(stream.fileno())
 restore_stage_xattrs(stage,original_meta['xattrs'])
 plain_files([stage])
 if stage.stat().st_ino in (source.stat().st_ino,target.stat().st_ino):raise ValueError('Clone inode is not distinct')
 if stage.read_bytes()!=raw:raise ValueError('Staged PNG bytes differ')
 # Restore timestamps after validation reads (reads may advance atime).
 os.utime(stage,ns=(original_meta['atime_ns'],original_meta['mtime_ns']))
 restore_birthtime(stage,original_meta['birthtime'])
 if metadata(stage)!=original_meta:raise ValueError('Staged metadata differs')
 fsync_file(stage);C.sync_dir(stage.parent)
 row={'status':'prepared','source':str(source),'target':str(target),'stage':str(stage),
      'content_kind':'gba-rom' if rom_sha else 'png',
      'file_sha256':C.digest(raw),'png_sha256':None if rom_sha else C.digest(raw),
      'rgb_sha256':None if rom_sha else target.stem,'bytes':len(raw),
      'source_sha256':C.digest(source_raw),'near_rom':near_rom,'private_page_offsets':changed_pages,
      'source_identity':before[source],'old_identity':before[target],
      'old_metadata':original_meta,'new_identity':C.identity(stage)}
 C.append_rows(receipt,[row]);C.sync_dir(stage.parent)
 C.floor();C.unused([source,target,stage]);C.unchanged(guards);C.unchanged(before)
 current_source_meta=metadata(source)
 if any(current_source_meta[k]!=v for k,v in source_meta.items() if k!='atime_ns'):raise ValueError('Source metadata changed before replace')
 if metadata(target)!=original_meta or metadata(stage)!=original_meta:raise ValueError('Target/stage metadata changed before replace')
 if source.read_bytes()!=source_raw or target.read_bytes()!=raw or stage.read_bytes()!=raw:raise ValueError('Bytes changed before replace')
 # Read-induced atime is not evidence mutation; keep original destination atime.
 os.utime(stage,ns=(original_meta['atime_ns'],original_meta['mtime_ns']))
 restore_birthtime(stage,original_meta['birthtime'])
 if metadata(stage)!=original_meta:raise ValueError('Final staged metadata differs')
 fsync_file(stage);C.unchanged(before);plain_files([source,target,stage])
 os.replace(stage,target);C.sync_dir(target.parent)
 if target.read_bytes()!=raw:raise ValueError('Post-replace byte mismatch')
 os.utime(target,ns=(original_meta['atime_ns'],original_meta['mtime_ns']))
 restore_birthtime(target,original_meta['birthtime'])
 fsync_file(target)
 if metadata(target)!=original_meta or target.stat().st_nlink!=1:raise ValueError('Post-replace metadata mismatch')
 C.unused([source,target],allow_spotlight=True);C.unchanged(guards);C.unchanged({source:before[source]})
 C.append_rows(receipt,[{**row,'status':'committed','new_identity':C.identity(target)}])
 return len(raw)
def ledger_names(run):
 names=set()
 with (run/'frames.jsonl').open() as stream:
  for line in stream:
   r=json.loads(line);h=r['rgb_sha256']
   if not re.fullmatch('[0-9a-f]{64}',h) or r['image']!='frames/'+h+'.png':raise ValueError('Noncanonical frame ledger')
   names.add(h+'.png')
 return names
def free_bytes():
 v=os.statvfs(C.ROOT);return v.f_bavail*v.f_frsize
def execute(source_run,target_run,work,max_files,apply,start_after=''):
 if source_run==target_run or any(x in str(r) for r in (source_run,target_run) for x in EXCLUDED):raise ValueError('Excluded or same run')
 guards={};hashes={}
 for run in (source_run,target_run):
  _,_,ids,sha=C.run_guard(run);guards.update(ids);hashes.update(sha)
 names=sorted(ledger_names(source_run)&ledger_names(target_run));C.unchanged(guards)
 if start_after and start_after not in names:raise ValueError('Cursor not in both ledgers')
 stats={'source_run':str(source_run),'target_run':str(target_run),'matched_names':len(names),'byte_identical_count':0,'logical_bytes':0,'replaced':0,'skipped_hardlinks':0,'last_considered':start_after,'free_before':free_bytes(),'status':'running'}
 with (work/'receipts.jsonl').open('x') as receipt:
  C.append_rows(receipt,[{'status':'scope','protected_sha256':{str(p):h for p,h in hashes.items()}}]);C.sync_dir(work)
  try:
   for name in names:
    if name<=start_after:continue
    if stats['byte_identical_count']>=max_files:break
    stats['last_considered']=name
    a=source_run/'frames'/name;b=target_run/'frames'/name
    if a.resolve()!=a or b.resolve()!=b:raise ValueError('Symlink frame')
    if a.lstat().st_nlink!=1 or b.lstat().st_nlink!=1:
     stats['skipped_hardlinks']+=1;continue
    plain_files([a,b]);C.floor()
    if max(a.stat().st_size,b.stat().st_size)>2**20:raise ValueError('PNG exceeds bounded buffer')
    if a.stat().st_size!=b.stat().st_size or a.read_bytes()!=b.read_bytes():continue
    stats['byte_identical_count']+=1;stats['logical_bytes']+=b.stat().st_size
    if apply:
     replace_pair(a,b,work/(name+'.partial'),receipt,guards);stats['replaced']+=1
   C.unchanged(guards)
   if any(C.file_sha(p)!=h for p,h in hashes.items()):raise ValueError('Protected run contents changed')
   stats['status']='complete'
  except Exception as exc:
   stats['status']='failed';stats['error']=str(exc)
   C.append_rows(receipt,[{'status':'failed','error':str(exc),'last_considered':stats['last_considered'],'replacement_may_have_occurred':True,'recovery':'Inspect prepared/committed receipt and target SHA/metadata before retry; no automatic rollback.'}])
   raise
  finally:
   stats['free_after']=free_bytes();stats['observed_free_delta']=stats['free_after']-stats['free_before'];stats['physical_savings_verified']=False
   (work/'summary.json').write_text(json.dumps(stats,indent=2));fsync_file(work/'summary.json');C.sync_dir(work)
 return stats
def rom_guard(raw,expected):
 if len(raw)!=16*1024*1024 or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid ROM size or expected SHA')
 if C.digest(raw)!=expected:raise ValueError('ROM SHA differs from baseline')
 original=C.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba'
 with original.open('rb') as f:header=f.read(0xc0)
 if len(header)!=0xc0 or raw[4:0xa0]!=header[4:0xa0] or raw[0xac:0xb2]!=header[0xac:0xb2]:raise ValueError('GBA logo/game identity differs')
 if raw[0xb2]!=0x96 or ((-sum(raw[0xa0:0xbd])-0x19)&255)!=raw[0xbd]:raise ValueError('Invalid GBA header checksum')
ANCHORED_KIND='cartridge-save-anchored-v1' # game_save_evidence.ANCHORED_KIND
def recorder_roots():
 result=subprocess.run(['/bin/ps','-axo','args='],capture_output=True,text=True)
 if result.returncode or result.stderr:raise ValueError('Cannot inventory active recorders')
 roots=set();starting=set()
 for line in result.stdout.splitlines():
  # Only direct Python recorder processes, not shells/review prompts containing text.
  fields=line.split(None,1)
  if len(fields)!=2 or 'python' not in Path(fields[0]).name.lower():continue
  args=shlex.split(line)
  if not any(Path(x).name=='playthrough_capture.py' for x in args[:4]):continue
  def option(name):
   if name not in args:return None
   index=args.index(name)
   if index+1>=len(args):raise ValueError('Incomplete recorder arguments')
   value=Path(args[index+1])
   return value if value.is_absolute() else C.ROOT/value
  out=option('--out');resume=option('--resume')
  if out is None:raise ValueError('Recorder output missing')
  roots.add(out);starting.add(out)
  rom=option('--rom')
  if rom and rom.name=='baseline.gba' and rom.is_relative_to(C.ROOT/'output/qa'):roots.add(rom.parent)
  if resume:roots.add(resume.parent)
  export=option('--export-game-save')
  if export:roots.add(export.parent)
  save=option('--game-save')
  if save:
   receipt=save # production CLI accepts the receipt itself
   if not receipt.exists():raise ValueError('Cannot resolve active game-save receipt')
   r=json.loads(receipt.read_text())
   # Anchored receipts are self-contained chain roots; their source run may be deleted.
   if r.get('kind')!=ANCHORED_KIND:roots.add(Path(r['source_checkpoint']).absolute().parent)
 return roots,starting

def excluded_rom_runs(roots):
 # Never walk millions of frame PNGs. Discover recorder marker directories,
 # then follow checkpoint/save ancestry. ps also covers pre-baseline startup.
 if not roots:raise ValueError('ROM mode requires explicit active/ancestor exclusions')
 active,starting=recorder_roots();pending=[Path(x).absolute() for x in roots]+list(active)
 for root in pending:
  if not root.is_dir():raise ValueError('Exclusion root does not exist')
 markers={'baseline.json','baseline.gba','actions.jsonl','frames.jsonl','exit.json','resume.checkpoint.json'}
 for folder,dirs,files in os.walk(C.ROOT/'output/qa',followlinks=False):
  dirs[:]=[d for d in dirs if d!='frames' and not (Path(folder)/d).is_symlink()]
  if not markers.intersection(files):continue
  run=Path(folder)
  try:
   e=json.loads((run/'exit.json').read_text())
   closed=e.get('status')=='closed' and e.get('emulator_exit_code')==0 and not e.get('cleanup_errors')
  except FileNotFoundError:closed=False
  if not closed:pending.append(run)
 excluded=set()
 while pending:
  run=pending.pop()
  if run.resolve()!=run or not run.is_relative_to(C.ROOT/'output/qa'):raise ValueError('Invalid ancestor run path')
  if run in excluded:continue
  excluded.add(run);path=run/'baseline.json'
  if not path.exists():
   if run not in starting and not any((run/n).exists() for n in markers):raise ValueError('Exclusion root has no recorder evidence')
   continue # process arguments already supplied startup ancestry
  b=json.loads(path.read_text())
  cp=b.get('parent_checkpoint')
  if cp:pending.append(Path(cp).absolute().parent)
  save=b.get('initial_game_save')
  if save:
   receipt=Path(save['receipt'])
   if not receipt.is_absolute():receipt=run/receipt
   r=json.loads(receipt.read_text())
   if r.get('kind')!=ANCHORED_KIND:pending.append(Path(r['source_checkpoint']).absolute().parent)
 return excluded

def execute_rom(source_run,target_run,work,apply,exclude_runs,near_rom=False):
 excluded=excluded_rom_runs(exclude_runs)
 if source_run==target_run or any(r in excluded or any(x in str(r) for x in EXCLUDED) for r in (source_run,target_run)):raise ValueError('Excluded ROM run')
 guards={};hashes={};expected=[]
 for run in (source_run,target_run):
  cp,_,ids,sha=C.run_guard(run);guards.update(ids);hashes.update(sha)
  rom_sha=json.loads((run/'baseline.json').read_text())['rom_sha256']
  if cp.get('rom_sha256')!=rom_sha or cp.get('state')!='resume.ss0' or cp.get('state_sha256')!=sha[run/'resume.ss0'] or cp.get('ledger_sha256')!=sha[run/'frames.jsonl']:raise ValueError('Checkpoint ROM/state/ledger contract differs')
  if 'baseline_sha256' in cp and cp['baseline_sha256']!=sha[run/'baseline.json']:raise ValueError('Checkpoint baseline SHA differs')
  expected.append(rom_sha)
 if not near_rom and expected[0]!=expected[1]:raise ValueError('Baseline ROM SHA differs')
 source=source_run/'baseline.gba';target=target_run/'baseline.gba'
 plain_files([source,target]);C.unused([source,target])
 for path,expected_sha in zip((source,target),expected):
  if path.stat().st_size!=16*1024*1024:raise ValueError('Invalid ROM size')
  rom_guard(path.read_bytes(),expected_sha)
 private_pages=0
 if near_rom:
  a=source.read_bytes();b=target.read_bytes()
  private_pages=sum(a[i:i+4096]!=b[i:i+4096] for i in range(0,len(a),4096))
  if not 1<=private_pages<=1024:raise ValueError('Near ROM requires 1..1024 different 4KiB pages')
  del a,b
 elif source.read_bytes()!=target.read_bytes():raise ValueError('ROM bytes differ')
 C.unchanged(guards)
 # Target inode is intentionally replaced; its immutable SHA remains protected
 # by replace_pair and the final complete protected-file hash verification.
 guards.pop(target)
 stats={'kind':'baseline-rom-clone-v1','near_rom':near_rom,'private_4k_pages':private_pages,'common_page_bytes_upper_bound':16777216-private_pages*4096,'source_run':str(source_run),'target_run':str(target_run),'status':'running','replaced':0,'logical_bytes':0,'free_before':free_bytes(),'physical_savings_verified':False}
 with (work/'receipts.jsonl').open('x') as receipt:
  C.append_rows(receipt,[{'status':'scope','excluded_runs':sorted(map(str,excluded)),'protected_sha256':{str(p):h for p,h in hashes.items()}}]);C.sync_dir(work)
  try:
   if excluded_rom_runs(exclude_runs)!=excluded:raise ValueError('Exclusion graph changed')
   if apply:
    replace_pair(source,target,work/'baseline.gba.partial',receipt,guards,rom_sha=expected[1],source_rom_sha=expected[0],near_rom=near_rom);stats['replaced']=1;stats['logical_bytes']=16*1024*1024
   C.unchanged(guards)
   if any(C.file_sha(p)!=h for p,h in hashes.items()):raise ValueError('Protected run contents changed')
   if excluded_rom_runs(exclude_runs)!=excluded:raise ValueError('Exclusion graph changed after clone')
   stats['status']='complete'
  except BaseException as exc:
   stats['status']='failed';stats['error']=str(exc)
   C.append_rows(receipt,[{'status':'failed','error':str(exc),'replacement_may_have_occurred':True}]);raise
  finally:
   stats['free_after']=free_bytes();stats['observed_free_delta']=stats['free_after']-stats['free_before']
   (work/'summary.json').write_text(json.dumps(stats,indent=2));fsync_file(work/'summary.json');C.sync_dir(work)
 return stats
ORIGINAL_ROM_SHA='a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
def candidate_exclusions(exclude_runs):
 excluded=excluded_rom_runs(exclude_runs);shas=set();paths=set()
 for run in excluded:
  baseline=run/'baseline.json'
  if baseline.exists():shas.add(json.loads(baseline.read_text())['rom_sha256'])
 result=subprocess.run(['/bin/ps','-axo','args='],capture_output=True,text=True)
 if result.returncode or result.stderr:raise ValueError('Cannot inspect build/ROM inputs')
 for line in result.stdout.splitlines():
  if 'build_korean_full' in line:raise ValueError('Active build; candidate cloning forbidden')
  if 'python' not in line:continue
  args=shlex.split(line)
  if any(Path(x).name=='clone_closed_frames.py' for x in args):continue # this tool's --rom is a boolean, not a ROM input
  if any(('--rom' in x or '--base' in x) and ' ' in x for x in args):raise ValueError('Ambiguous wrapped ROM input')
  for i,token in enumerate(args):
   if token in ('--rom','--base'):
    if i+1>=len(args):raise ValueError('Incomplete ROM input option')
    value=Path(args[i+1])
    if not value.is_absolute():raise ValueError('Relative active ROM path has unknown process cwd')
    paths.add(value.resolve())
   elif token.startswith(('--rom=','--base=')):
    value=Path(token.split('=',1)[1])
    if not value.is_absolute():raise ValueError('Relative active ROM path has unknown process cwd')
    paths.add(value.resolve())
 return excluded,shas,paths

def candidate_guard(path,manifest,excluded_shas,active_paths,manifest_sha=None,include_remaining=False):
 from localization_evidence import stable_build_inputs
 if path.resolve()!=path or not path.is_relative_to(C.ROOT/'temp') or path.name!='candidate.gba':raise ValueError('Candidate path outside explicit temp scope')
 if path in active_paths:raise ValueError('Candidate is an active ROM/build input')
 if manifest.resolve()!=manifest or not manifest.is_relative_to(C.ROOT/'temp'):raise ValueError('Manifest outside temp scope')
 plain_files([path,manifest]);manifest_id=C.identity(manifest);manifest_raw=manifest.read_bytes()
 if manifest_sha is not None and C.digest(manifest_raw)!=manifest_sha:raise ValueError('Candidate manifest SHA differs')
 doc=json.loads(manifest_raw)
 if not isinstance(doc.get('recommended_recent'),list) or not isinstance(doc.get('remaining'),list):raise ValueError('Candidate manifest schema differs')
 allowed=doc['recommended_recent']+(doc['remaining'] if include_remaining else []);matches=[r for r in allowed if C.ROOT/r['path']==path]
 if len(matches)!=1:raise ValueError('Candidate not uniquely allowlisted')
 row=matches[0];receipt=Path(str(path)+'.build.json');plain_files([receipt]);ids={p:C.identity(p) for p in (path,receipt)};ids[manifest]=manifest_id
 if ids[path][2]!=16777216:raise ValueError('Candidate size differs')
 if C.file_sha(receipt)!=row['receipt_sha256']:raise ValueError('Candidate receipt changed')
 value=json.loads(receipt.read_text());sha=value['rom_sha256']
 if value.get('schema')!=1 or value.get('stage')!='development_build' or value.get('release_ready') is not False or value.get('repoint_enabled') is not True:raise ValueError('Not a completed development candidate')
 if value.get('source_sha256')!=ORIGINAL_ROM_SHA or sha!=row['sha256']:raise ValueError('Candidate provenance differs')
 if sha in excluded_shas or sha==ORIGINAL_ROM_SHA:raise ValueError('Candidate matches active/ancestor/original SHA')
 stable_build_inputs(value['inputs_before'],value['inputs_after'])
 rom_guard(path.read_bytes(),sha);C.unchanged(ids);C.unused(list(ids))
 hashes={p:C.file_sha(p) for p in ids};C.unchanged(ids)
 return sha,ids,hashes

def execute_candidate(source_run,target,work,apply,exclude_runs,manifest,near_rom=False,source_candidate=None,manifest_sha=None,include_remaining=False):
 manifest_sha=manifest_sha or C.file_sha(manifest)
 scope=candidate_exclusions(exclude_runs);excluded,excluded_shas,active_paths=scope
 if source_run in excluded or any(x in str(source_run) for x in EXCLUDED):raise ValueError('Excluded source run')
 cp,_,guards,hashes=C.run_guard(source_run);source=source_run/'baseline.gba'
 source_sha=json.loads((source_run/'baseline.json').read_text())['rom_sha256']
 if cp.get('rom_sha256')!=source_sha or cp.get('state')!='resume.ss0' or cp.get('state_sha256')!=hashes[source_run/'resume.ss0'] or cp.get('ledger_sha256')!=hashes[source_run/'frames.jsonl']:raise ValueError('Source checkpoint contract differs')
 if 'baseline_sha256' in cp and cp['baseline_sha256']!=hashes[source_run/'baseline.json']:raise ValueError('Source baseline contract differs')
 target_sha,ids,sha=candidate_guard(target,manifest,excluded_shas,active_paths,manifest_sha,include_remaining);guards.update(ids);hashes.update(sha)
 if source_candidate:
  if near_rom or source_candidate==target:raise ValueError('Candidate source is exact-only and distinct')
  source_sha,ids,sha=candidate_guard(source_candidate,manifest,excluded_shas,active_paths,manifest_sha,include_remaining);guards.update(ids);hashes.update(sha);source=source_candidate
 plain_files([source,target]);rom_guard(source.read_bytes(),source_sha)
 a=source.read_bytes();b=target.read_bytes();private_pages=sum(a[i:i+4096]!=b[i:i+4096] for i in range(0,len(a),4096));del a,b
 if near_rom:
  if not 1<=private_pages<=1024:raise ValueError('Near ROM requires 1..1024 different 4KiB pages')
 elif source_sha!=target_sha or private_pages:raise ValueError('Exact candidate ROM differs')
 C.unchanged(guards);guards.pop(target)
 stats={'kind':'completed-candidate-rom-clone-v1','source':str(source),'target':str(target),'near_rom':near_rom,'private_4k_pages':private_pages,'common_page_bytes_upper_bound':16777216-private_pages*4096,'status':'running','replaced':0,'free_before':free_bytes(),'physical_savings_verified':False}
 with (work/'receipts.jsonl').open('x') as receipt:
  C.append_rows(receipt,[{'status':'scope','excluded_runs':sorted(map(str,excluded)),'excluded_rom_sha256':sorted(excluded_shas),'protected_sha256':{str(p):h for p,h in hashes.items()}}]);C.sync_dir(work)
  try:
   if candidate_exclusions(exclude_runs)!=scope:raise ValueError('Active/ancestor/build inputs changed')
   if apply:
    replace_pair(source,target,work/'candidate.gba.partial',receipt,guards,rom_sha=target_sha,source_rom_sha=source_sha,near_rom=near_rom);stats['replaced']=1
   C.unchanged(guards)
   if any(C.file_sha(p)!=h for p,h in hashes.items()):raise ValueError('Candidate/receipt/run evidence changed')
   if candidate_exclusions(exclude_runs)!=scope:raise ValueError('Active/ancestor/build inputs changed after clone')
   stats['status']='complete'
  except BaseException as exc:
   stats['status']='failed';stats['error']=str(exc);C.append_rows(receipt,[{'status':'failed','error':str(exc),'replacement_may_have_occurred':True}]);raise
  finally:
   stats['free_after']=free_bytes();stats['observed_free_delta']=stats['free_after']-stats['free_before']
   (work/'summary.json').write_text(json.dumps(stats,indent=2));fsync_file(work/'summary.json');C.sync_dir(work)
 return stats
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-run',required=True,type=Path);p.add_argument('--target-run',type=Path);p.add_argument('--work',required=True,type=Path);p.add_argument('--max-files',type=int,default=10);p.add_argument('--apply',action='store_true');p.add_argument('--start-after',default='');p.add_argument('--rom',action='store_true');p.add_argument('--near-rom',action='store_true');p.add_argument('--exclude-run',action='append',type=Path,default=[]);p.add_argument('--candidate-target',type=Path);p.add_argument('--candidate-source',type=Path);p.add_argument('--candidate-manifest',type=Path);p.add_argument('--candidate-manifest-sha256');p.add_argument('--include-remaining-candidates',action='store_true');a=p.parse_args()
 if a.candidate_target:
  if not a.rom or a.target_run or not a.candidate_manifest or not a.candidate_manifest_sha256:raise ValueError('Candidate mode requires --rom, manifest, and no target-run')
 elif not a.target_run or a.candidate_manifest or a.candidate_source or a.candidate_manifest_sha256 or a.include_remaining_candidates:raise ValueError('Missing target-run or candidate target')
 if a.near_rom and not a.rom:raise ValueError('Near ROM mode requires explicit --rom')
 if a.rom and (a.start_after or not a.exclude_run):raise ValueError('ROM mode requires exclusions and forbids frame cursor')
 if not a.rom and a.exclude_run:raise ValueError('ROM exclusions require ROM mode')
 if not 1<=a.max_files<=200:raise ValueError('Pilot limited to 200 files')
 work=a.work.absolute()
 if work.resolve()!=work or work.parent!=C.ROOT/'temp' or not work.name.startswith('frame_recompress_clone'):raise ValueError('Work must be fresh canonical temp directory')
 lock=os.open(C.ROOT/'temp/frame_recompression.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 created=False
 try:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);C.floor();work.mkdir(exist_ok=False);created=True
  if a.candidate_target:
   result=execute_candidate(a.source_run.absolute(),a.candidate_target.absolute(),work,a.apply,a.exclude_run,a.candidate_manifest.absolute(),a.near_rom,a.candidate_source.absolute() if a.candidate_source else None,a.candidate_manifest_sha256,a.include_remaining_candidates)
  else:
   result=execute_rom(a.source_run.absolute(),a.target_run.absolute(),work,a.apply,a.exclude_run,a.near_rom) if a.rom else execute(a.source_run.absolute(),a.target_run.absolute(),work,a.max_files,a.apply,a.start_after)
  print(json.dumps(result))
 except BaseException as exc:
  if a.rom and created and not (work/'summary.json').exists():
   (work/'summary.json').write_text(json.dumps({'kind':'completed-candidate-rom-clone-v1' if a.candidate_target else 'baseline-rom-clone-v1','status':'preflight_failed','source_run':str(a.source_run.absolute()),'target_run':str((a.candidate_target or a.target_run).absolute()),'error':str(exc),'replaced':0,'physical_savings_verified':False},indent=2))
   fsync_file(work/'summary.json');C.sync_dir(work)
  raise
 finally:os.close(lock)
if __name__=='__main__':main()
