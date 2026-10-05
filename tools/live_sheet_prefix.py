"""Freeze committed action/ledger prefixes for optional live/failed-run sheet cleanup.

Only append beyond the recorded prefixes is allowed. Neither exit.json nor the
recorder is changed. Sheets must belong to completed actions at least 20 actions
behind the snapshot boundary. A failed suffix is never promoted to completion.
"""
import hashlib,json,re
from pathlib import Path
import prune_capture_sheets as P
from recompress_closed_frames import unused

def file_prefix(path,size,expected=None):
 before=P.regular(path,P.ROOT)
 if type(size) is not int or size<0 or before[2]<size:raise ValueError('Prefix truncated')
 digest=hashlib.sha256();remaining=size
 with path.open('rb') as stream:
  while remaining:
   part=stream.read(min(2**20,remaining))
   if not part:raise ValueError('Prefix truncated during read')
   digest.update(part);remaining-=len(part)
 after=P.regular(path,P.ROOT)
 if (before[0:2]+before[5:])!=(after[0:2]+after[5:]) or after[2]<size:raise ValueError('Prefix file replaced')
 result=digest.hexdigest()
 if expected is not None and result!=expected:raise ValueError('Committed prefix changed')
 return result,after[0:2]+after[5:]

class PrefixGuard:
 def __init__(self):self.prefixes=[];self.fixed={};self.boundary=set()
 def add_fixed(self,path):
  ident=P.regular(path,P.ROOT);digest=P.sha(path)
  if P.identity(path)!=ident:raise ValueError('Evidence changed during snapshot')
  self.fixed[path]=(ident,digest)
 def check(self,all_fixed=True):
  if not all_fixed and not self.boundary:raise ValueError('Missing boundary authority')
  for path,size,digest,ident in self.prefixes:
   _,current=file_prefix(path,size,digest)
   if current!=ident:raise ValueError('Prefix inode changed')
  for path,(ident,digest) in self.fixed.items():
   if not all_fixed and path not in self.boundary:continue
   if P.identity(path)!=ident or P.sha(path)!=digest:raise ValueError('Committed evidence changed')
 def check_plan(self,plan):
  paths={Path(plan[k]) for k in ('endpoint','checkpoint')}
  paths.update(Path(r['image']) for r in plan['samples'])
  for path in paths:
   ident,digest=self.fixed[path]
   if P.identity(path)!=ident or P.sha(path)!=digest:raise ValueError('Selected committed artifact changed')
 def evidence(self):
  return {'mode':'committed-prefix','prefixes':[{'path':str(p),'bytes':n,'sha256':d,'identity':i} for p,n,d,i in self.prefixes],
          'fixed_sha256':{str(p):d for p,(_,d) in self.fixed.items()},'retained_first_actions':20,'retained_recent_actions':20}

def prepare(run,limit):
 guard=PrefixGuard()
 for name in ('exit.json','resume.checkpoint.json'):
  if (run/name).exists():guard.add_fixed(run/name)
 actions=run/'actions.jsonl';before=P.regular(actions,run)
 if before[2]>64*2**20:raise ValueError('Action snapshot exceeds bounded buffer')
 with actions.open('rb') as stream:raw=stream.read(before[2])
 end=raw.rfind(b'\n')+1
 if not end:raise ValueError('No complete actions')
 raw=raw[:end];digest,ident=file_prefix(actions,end,hashlib.sha256(raw).hexdigest());guard.prefixes.append((actions,end,digest,ident))
 starts={};captured=[];seen=set()
 for line in raw.splitlines():
  row=json.loads(line);status=row.get('status')
  if status=='started':
   if row['segment'] in starts:raise ValueError('Duplicate started segment')
   starts[row['segment']]=row
  elif status=='captured':
   segment=row['segment']
   if segment in seen or segment not in starts or (captured and segment<=captured[-1]['segment']):raise ValueError('Invalid captured order')
   seen.add(segment);captured.append(row)
 if len(captured)<=40:raise ValueError('No committed middle actions after retention')
 anchor=captured[-1];anchor_cp=Path(anchor['checkpoint']);guard.add_fixed(anchor_cp)
 checkpoint=json.loads(anchor_cp.read_text())
 if anchor_cp.parent!=run or checkpoint['core_frame']!=anchor['end_core_frame']:raise ValueError('Anchor checkpoint mismatch')
 for name,key in (('baseline.json','baseline_sha256'),(checkpoint['state'],'state_sha256')):
  path=run/name
  if path.parent!=run:raise ValueError('Invalid checkpoint artifact')
  guard.add_fixed(path)
  if P.sha(path)!=checkpoint[key]:raise ValueError('Checkpoint artifact SHA mismatch')
 guard.boundary=set(guard.fixed)
 protected=P.reference_names();plans=[]
 for row in captured[20:-20]:
  if row.get('sheet') is None:continue
  start=starts[row['segment']];expected=start['start_core_frame']+start['hold_frames']+start['release_frames']-1
  if row['start_core_frame']!=start['start_core_frame'] or row['end_core_frame']!=expected or expected>checkpoint['core_frame']:raise ValueError('Uncommitted action boundary')
  name=f"{row['segment']:04d}_{start['key']}_{expected:07d}"
  sheet=run/(name+'_sheet.png');endpoint=run/(name+'.png');cp=run/(name+'.checkpoint.json')
  if Path(row['sheet'])!=sheet or Path(row['png'])!=endpoint or Path(row['checkpoint'])!=cp:raise ValueError('Unexpected artifact path')
  if not sheet.exists() or sheet.name in protected:continue
  P.regular(sheet,run);guard.add_fixed(endpoint);guard.add_fixed(cp)
  if json.loads(cp.read_text())['core_frame']!=expected:raise ValueError('Action checkpoint frame mismatch')
  plans.append({'sheet':str(sheet),'endpoint':str(endpoint),'checkpoint':str(cp),'frames':P.sample_frames(start)})
  if len(plans)>=limit:break
 ledger=run/'frames.jsonl';size=checkpoint['ledger_bytes'];digest,ident=file_prefix(ledger,size,checkpoint['ledger_sha256']);guard.prefixes.append((ledger,size,digest,ident))
 wanted={f for plan in plans for f in plan['frames']};samples={};remaining=size;last=None
 with ledger.open('rb') as stream:
  while remaining:
   line=stream.readline(remaining);remaining-=len(line)
   if not line.endswith(b'\n'):raise ValueError('Checkpoint ends mid ledger record')
   row=json.loads(line);frame=row['core_frame']
   if last is not None and frame!=last+1:raise ValueError('Noncontiguous ledger prefix')
   last=frame
   if frame in wanted:
    rgb=row['rgb_sha256']
    if not re.fullmatch('[0-9a-f]{64}',rgb) or row['image']!='frames/'+rgb+'.png' or frame in samples:raise ValueError('Invalid frame evidence')
    path=run/row['image'];guard.add_fixed(path);samples[frame]={'frame':frame,'image':str(path),'rgb_sha256':rgb}
 if last!=checkpoint['core_frame'] or samples.keys()!=wanted:raise ValueError('Missing committed source frames')
 for plan in plans:plan['samples']=[samples[f] for f in plan.pop('frames')]
 guard.check()
 return plans,guard

def batch_guard(plans,guard):
 guard.check(all_fixed=False)
 for plan in plans:guard.check_plan(plan)
 paths=set()
 for plan in plans:
  paths.update(Path(plan[k]) for k in ('sheet','endpoint','checkpoint'))
  paths.update(Path(r['image']) for r in plan['samples'])
 paths=sorted(paths)
 for offset in range(0,len(paths),100):unused(paths[offset:offset+100])
 guard.check(all_fixed=False)
 return P.reference_names()
