import hashlib,io,json,os,tempfile,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import clone_closed_frames as M

class CloneTests(unittest.TestCase):
 def setUp(self):
  self.floor_patch=patch.object(M.C,'floor');self.floor_patch.start();self.addCleanup(self.floor_patch.stop)
  self.free_patch=patch.object(M,'free_bytes',return_value=20*1024**3);self.free_patch.start();self.addCleanup(self.free_patch.stop)
  self.tmp=tempfile.TemporaryDirectory(dir=M.C.ROOT/'temp');self.root=Path(self.tmp.name)
  im=Image.new('RGB',(240,160),(21,43,65));self.rgb=hashlib.sha256(im.tobytes()).hexdigest();b=io.BytesIO();im.save(b,format='PNG');self.raw=b.getvalue()
  (self.root/'a').mkdir();(self.root/'b').mkdir();self.a=self.root/'a'/(self.rgb+'.png');self.b=self.root/'b'/self.a.name
  self.a.write_bytes(self.raw);self.b.write_bytes(self.raw);self.stage=self.root/'frame.partial';self.receipt=self.root/'receipt.jsonl'
 def tearDown(self):self.tmp.cleanup()
 def call(self):
  with self.receipt.open('w') as receipt:return M.replace_pair(self.a,self.b,self.stage,receipt,{})
 def test_real_clone_metadata_cow_and_receipt(self):
  before=M.metadata(self.b);old_inode=self.b.stat().st_ino
  with patch.object(M.C,'unused'):
   self.assertEqual(self.call(),len(self.raw))
  self.assertEqual(self.b.read_bytes(),self.raw);self.assertEqual(self.b.stat().st_nlink,1)
  self.assertNotEqual(self.b.stat().st_ino,old_inode);self.assertNotEqual(self.a.stat().st_ino,self.b.stat().st_ino)
  after=M.metadata(self.b)
  for key in ('mode','uid','gid','flags','mtime_ns','birthtime','xattrs'):self.assertEqual(after[key],before[key])
  rows=[json.loads(s) for s in self.receipt.read_text().splitlines()];self.assertEqual([r['status'] for r in rows],['prepared','committed'])
  self.b.write_bytes(b'private edit');self.assertEqual(self.a.read_bytes(),self.raw)
 def test_real_xattrs_mode_and_distinct_creation_timestamp(self):
  os.chmod(self.b,0o640)
  subprocess.run(['/usr/bin/xattr','-w','com.example.clone-test','keep',str(self.b)],check=True)
  M.restore_birthtime(self.b,(1600000000,123456789))
  before=M.metadata(self.b)
  with patch.object(M.C,'unused'):self.call()
  after=M.metadata(self.b)
  for key in ('mode','uid','gid','flags','mtime_ns','birthtime','xattrs'):self.assertEqual(before[key],after[key])
 def test_quarantine_timestamp_exactly_preserved(self):
  value='0281;6ab0add4;;EE4F314E-C4E1-4D9A-A0A5-89D97A7A36DD'
  subprocess.run(['/usr/bin/xattr','-w','com.apple.quarantine',value,str(self.b)],check=True)
  before=M.metadata(self.b)
  with patch.object(M.C,'unused'):self.call()
  self.assertEqual(M.metadata(self.b)['xattrs'],before['xattrs'])
 def test_quarantine_regression_requires_restoration(self):
  value='0281;6ab0add4;;EE4F314E-C4E1-4D9A-A0A5-89D97A7A36DD'
  subprocess.run(['/usr/bin/xattr','-w','com.apple.quarantine',value,str(self.b)],check=True)
  original=M.clone
  def changed(source,target,stage):
   original(source,target,stage)
   subprocess.run(['/usr/bin/xattr','-w','com.apple.quarantine','0281;00000001;;changed',str(stage)],check=True)
  inode=self.b.stat().st_ino
  with patch.object(M.C,'unused'),patch.object(M,'clone',side_effect=changed),patch.object(M,'restore_stage_xattrs'):
   with self.assertRaisesRegex(ValueError,'Staged metadata'):self.call()
  self.assertEqual(self.b.stat().st_ino,inode);self.assertEqual(self.b.read_bytes(),self.raw)
  self.stage.unlink()
  with patch.object(M.C,'unused'),patch.object(M,'clone',side_effect=changed):self.call()
  self.assertEqual(M.C.native_xattrs(self.b)[b'com.apple.quarantine'],value.encode())
 def test_stage_extra_xattr_rejects_without_removal(self):
  self.stage.write_bytes(b'fixture')
  subprocess.run(['/usr/bin/xattr','-w','com.example.extra','stay',str(self.stage)],check=True)
  with self.assertRaisesRegex(ValueError,'Unexpected'):M.restore_stage_xattrs(self.stage,{})
  self.assertIn(b'com.example.extra',M.C.native_xattrs(self.stage))
 def test_extended_acl_is_not_silently_copied(self):
  result=subprocess.CompletedProcess([],0,'-rw-r--r--+ file\n 0: user:someone allow read\n','')
  with patch.object(M.subprocess,'run',return_value=result):
   with self.assertRaisesRegex(ValueError,'ACL'):M.plain_files([self.a])
 def test_lock_refusal_does_not_create_work(self):
  work=M.C.ROOT/'temp'/('frame_recompress_clone_uncreated_'+self.root.name)
  argv=['clone','--source-run',str(self.root/'a'),'--target-run',str(self.root/'b'),'--work',str(work)]
  with patch.object(sys,'argv',argv),patch.object(M.fcntl,'flock',side_effect=BlockingIOError('busy')):
   with self.assertRaises(BlockingIOError):M.main()
  self.assertFalse(work.exists())
 def test_birth_after_mtime_preserved(self):
  os.utime(self.b,ns=(1600000000000000000,1600000000000000000))
  M.restore_birthtime(self.b,(1700000000,123456789))
  before=M.metadata(self.b)
  with patch.object(M.C,'unused'):self.call()
  self.assertEqual(M.birthtime(self.b),before['birthtime'])
  self.assertEqual(self.b.stat().st_mtime_ns,before['mtime_ns'])
 def fixture_run(self,name):
  run=self.root/'output/qa'/name;run.mkdir(parents=True);(run/'frames').mkdir()
  (run/'frames'/self.a.name).write_bytes(self.raw)
  ledger=json.dumps({'rgb_sha256':self.rgb,'image':'frames/'+self.a.name})+'\n'
  (run/'frames.jsonl').write_text(ledger)
  (run/'exit.json').write_text(json.dumps({'status':'closed','emulator_exit_code':0,'cleanup_errors':[],'committed_core_frame':1,'last_observed_core_frame':1}))
  (run/'resume.checkpoint.json').write_text(json.dumps({'core_frame':1,'ledger_bytes':len(ledger.encode())}))
  for n in ('baseline.json','baseline.gba','actions.jsonl','resume.ss0'):(run/n).write_bytes(b'fixture')
  return run
 def test_execute_apply_cursor_and_failed_summary(self):
  a=self.fixture_run('a');b=self.fixture_run('b');work=self.root/'work';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   result=M.execute(a,b,work,1,True)
   self.assertEqual(result['replaced'],1)
   again=self.root/'again';again.mkdir();result=M.execute(a,b,again,1,True,result['last_considered'])
   self.assertEqual(result['replaced'],0)
   failed=self.root/'failed';failed.mkdir()
   replace=M.os.replace
   def after_replace(x,y):replace(x,y);raise OSError('post replace injected')
   with patch.object(M.os,'replace',side_effect=after_replace):
    with self.assertRaises(OSError):M.execute(a,b,failed,1,True)
  self.assertEqual(json.loads((failed/'summary.json').read_text())['status'],'failed')
  self.assertEqual(json.loads((failed/'receipts.jsonl').read_text().splitlines()[-1])['status'],'failed')
  self.assertEqual((b/'frames'/self.a.name).read_bytes(),self.raw)
 def test_execute_skips_hardlinks(self):
  a=self.fixture_run('a');b=self.fixture_run('b');os.link(b/'frames'/self.a.name,b/'endpoint.png');work=self.root/'work';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   result=M.execute(a,b,work,1,True)
  self.assertEqual(result['replaced'],0);self.assertEqual(result['skipped_hardlinks'],1)
 def test_different_bytes_and_rgb_fail_before_clone(self):
  for raw in (self.raw+b'extra',b'not png'):
   self.b.write_bytes(raw)
   with patch.object(M.C,'unused'),patch.object(M,'clone') as clone:
    with self.assertRaises(ValueError):self.call()
    clone.assert_not_called()
  self.b.write_bytes(self.raw);self.a=self.a.rename(self.a.with_name('0'*64+'.png'));self.b=self.b.rename(self.b.with_name(self.a.name))
  with patch.object(M.C,'unused'),patch.object(M,'clone') as clone:
   with self.assertRaises(ValueError):self.call()
   clone.assert_not_called()
 def test_hardlink_and_symlink_rejected(self):
  self.b.unlink();os.link(self.a,self.b)
  with self.assertRaises(ValueError):M.plain_files([self.a,self.b])
  self.b.unlink();self.b.symlink_to(self.a)
  with self.assertRaises(ValueError):M.plain_files([self.b])
 def test_native_failure_leaves_original(self):
  before=M.C.identity(self.b)
  with patch.object(M.C,'unused'),patch.object(M,'clone',side_effect=OSError('unsupported')):
   with self.assertRaises(OSError):self.call()
  self.assertEqual(M.C.identity(self.b),before);self.assertEqual(self.b.read_bytes(),self.raw)
 def test_stage_corruption_and_metadata_loss_leave_original(self):
  native=M.clone
  for kind in ('bytes','mode'):
   def broken(*args):
    native(*args)
    if kind=='bytes':args[2].write_bytes(b'bad')
    else:os.chmod(args[2],0o600)
   with patch.object(M.C,'unused'),patch.object(M,'clone',side_effect=broken):
    with self.assertRaises(ValueError):self.call()
   self.assertEqual(self.b.read_bytes(),self.raw);self.stage.unlink()
 def test_source_race_rejected_before_replace(self):
  calls=0
  def race(paths,**kwargs):
   nonlocal calls
   calls+=1
   if calls==2:self.a.write_bytes(b'changed')
  before=M.C.identity(self.b)
  with patch.object(M.C,'unused',side_effect=race):
   with self.assertRaises(ValueError):self.call()
  self.assertEqual(M.C.identity(self.b),before);self.assertEqual(self.b.read_bytes(),self.raw)
  self.assertEqual(json.loads(self.receipt.read_text())['status'],'prepared')
 def test_low_disk_and_open_file_leave_original(self):
  before=M.C.identity(self.b)
  for method in ('floor','unused'):
   with patch.object(M.C,method,side_effect=ValueError('guard')):
    with self.assertRaises(ValueError):self.call()
   self.assertEqual(M.C.identity(self.b),before)
 def test_excluded_run_and_ledger_rejected(self):
  with self.assertRaises(ValueError):M.execute(self.root,self.root,self.root,1,False)
  with self.assertRaises(ValueError):M.execute(self.root/'mission3_day16_round8_cold_live',self.root,self.root,1,False)
  (self.root/'frames.jsonl').write_text(json.dumps({'rgb_sha256':self.rgb,'image':'outside.png'})+'\n')
  with self.assertRaises(ValueError):M.ledger_names(self.root)
 def test_prepared_receipt_precedes_replace(self):
  replace=os.replace
  def checked(a,b):
   rows=[json.loads(s) for s in self.receipt.read_text().splitlines()]
   self.assertEqual(rows[-1]['status'],'prepared');self.assertEqual(b.read_bytes(),self.raw)
   return replace(a,b)
  with patch.object(M.C,'unused'),patch.object(M.os,'replace',side_effect=checked):self.call()
class RomCloneTests(unittest.TestCase):
 def setUp(self):
  CloneTests.setUp(self)
  self.recorder_patch=patch.object(M,'recorder_roots',return_value=(set(),set()));self.recorder_patch.start();self.addCleanup(self.recorder_patch.stop)
 tearDown=CloneTests.tearDown
 fixture_run=CloneTests.fixture_run
 def rom_runs(self):
  a=self.fixture_run('rom_a');b=self.fixture_run('rom_b')
  raw=(M.C.ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
  sha=M.C.digest(raw)
  for run in (a,b):
   (run/'baseline.gba').write_bytes(raw)
   (run/'baseline.json').write_text(json.dumps({'rom_sha256':sha}))
   cp=json.loads((run/'resume.checkpoint.json').read_text());cp.update(rom_sha256=sha,state='resume.ss0',state_sha256=M.C.file_sha(run/'resume.ss0'),ledger_sha256=M.C.file_sha(run/'frames.jsonl'));(run/'resume.checkpoint.json').write_text(json.dumps(cp))
  original=self.root/'original';original.mkdir(exist_ok=True)
  (original/'Game Boy Wars Advance 1+2 (Japan).gba').write_bytes(raw)
  live=self.root/'output/qa/live';live.mkdir(exist_ok=True);(live/'actions.jsonl').touch()
  return a,b,raw,sha
 def test_rom_header_size_and_baseline_digest(self):
  a,b,raw,sha=self.rom_runs()
  M.rom_guard(raw,sha)
  for bad in (raw[:-1],bytes([raw[0]^1])+raw[1:],raw[:0xbd]+bytes([raw[0xbd]^1])+raw[0xbe:]):
   with self.assertRaises(ValueError):M.rom_guard(bad,sha)
  bad=raw[:0xb2]+b'\x00'+raw[0xb3:]
  with self.assertRaisesRegex(ValueError,'header'):M.rom_guard(bad,M.C.digest(bad))
 def test_rom_real_clone_preserves_all_evidence(self):
  a,b,raw,sha=self.rom_runs();work=self.root/'romwork';work.mkdir()
  before=M.metadata(b/'baseline.gba');old=(b/'baseline.gba').stat().st_ino
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   result=M.execute_rom(a,b,work,True,[self.root/'output/qa/live'])
  self.assertEqual(result['replaced'],1);self.assertFalse(result['physical_savings_verified'])
  self.assertEqual((b/'baseline.gba').read_bytes(),raw)
  self.assertNotEqual(old,(b/'baseline.gba').stat().st_ino)
  self.assertNotEqual((a/'baseline.gba').stat().st_ino,(b/'baseline.gba').stat().st_ino)
  self.assertEqual((b/'baseline.gba').stat().st_nlink,1)
  for k in ('mode','uid','gid','flags','mtime_ns','birthtime','xattrs'):self.assertEqual(before[k],M.metadata(b/'baseline.gba')[k])
  rows=[json.loads(x) for x in (work/'receipts.jsonl').read_text().splitlines()]
  self.assertEqual(rows[1]['content_kind'],'gba-rom');self.assertIsNone(rows[1]['rgb_sha256'])
 def test_rom_mismatched_baseline_and_active_ancestor_rejected(self):
  a,b,raw,sha=self.rom_runs();work=self.root/'romwork';work.mkdir()
  live=self.root/'output/qa/live';live.mkdir(exist_ok=True);(live/'baseline.json').write_text(json.dumps({'parent_checkpoint':str(a/'resume.checkpoint.json')}))
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'Excluded'):M.execute_rom(a,b,work,True,[live])
   (live/'baseline.json').write_text('{}')
   (b/'baseline.json').write_text(json.dumps({'rom_sha256':'0'*64}))
   with self.assertRaisesRegex(ValueError,'contract differs|SHA differs'):M.execute_rom(a,b,work,True,[live])
 def test_rom_checkpoint_hash_rejects_before_clone(self):
  a,b,raw,sha=self.rom_runs();work=self.root/'romwork';work.mkdir()
  cp=json.loads((b/'resume.checkpoint.json').read_text());cp['ledger_sha256']='0'*64;(b/'resume.checkpoint.json').write_text(json.dumps(cp))
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'clone') as clone:
   with self.assertRaisesRegex(ValueError,'contract'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'])
   clone.assert_not_called()
 def test_rom_sha_correct_but_corrupt_logo_rejected(self):
  a,b,raw,sha=self.rom_runs();bad=raw[:4]+bytes([raw[4]^1])+raw[5:]
  with self.assertRaisesRegex(ValueError,'logo'):M.rom_guard(bad,M.C.digest(bad))
 def test_rom_exclusion_graph_changed_rejects_before_clone(self):
  a,b,raw,sha=self.rom_runs();work=self.root/'romwork';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'excluded_rom_runs',side_effect=[set(),{a}]),patch.object(M,'clone') as clone:
   with self.assertRaisesRegex(ValueError,'graph changed'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'])
   clone.assert_not_called()
   self.assertEqual(json.loads((work/'summary.json').read_text())['status'],'failed')
 def test_missing_exclusion_and_prebaseline_run(self):
  a,b,raw,sha=self.rom_runs()
  with patch.object(M.C,'ROOT',self.root):
   with self.assertRaisesRegex(ValueError,'does not exist'):M.excluded_rom_runs([self.root/'output/qa/typo'])
   self.assertIn(self.root/'output/qa/live',M.excluded_rom_runs([a]))
 def test_recomputed_header_checksum_and_game_code_reject(self):
  a,b,raw,sha=self.rom_runs()
  for offset in (0xac,0xbd):
   bad=raw[:offset]+bytes([raw[offset]^1])+raw[offset+1:]
   with self.assertRaises(ValueError):M.rom_guard(bad,M.C.digest(bad))
 def test_nonclean_discovery_and_ancestor_cycle(self):
  a,b,raw,sha=self.rom_runs()
  (a/'baseline.json').write_text(json.dumps({'rom_sha256':sha,'parent_checkpoint':str(b/'resume.checkpoint.json')}))
  (b/'baseline.json').write_text(json.dumps({'rom_sha256':sha,'parent_checkpoint':str(a/'resume.checkpoint.json')}))
  for change in ({'status':'failed'},{'emulator_exit_code':1},{'cleanup_errors':['failure']}):
   e={'status':'closed','emulator_exit_code':0,'cleanup_errors':[]};e.update(change);(a/'exit.json').write_text(json.dumps(e))
   with patch.object(M.C,'ROOT',self.root):
    result=M.excluded_rom_runs([self.root/'output/qa/live']);self.assertIn(a,result);self.assertIn(b,result)
 def test_recorder_startup_arguments_supply_missing_ancestry(self):
  self.recorder_patch.stop()
  output='/Users/example/output/qa/starting';parent='/Users/example/output/qa/parent/cp.json'
  response=subprocess.CompletedProcess([],0,f'/usr/bin/python3 tools/playthrough_capture.py --out {output} --resume {parent}\n','')
  with patch.object(M.subprocess,'run',return_value=response):
   roots,starting=M.recorder_roots();self.assertIn(Path(parent).parent,roots);self.assertIn(Path(output),starting)
 def test_recorder_baseline_rom_input_is_excluded(self):
  self.recorder_patch.stop();rom=M.C.ROOT/'output/qa/rom_input/baseline.gba'
  response=subprocess.CompletedProcess([],0,f'/usr/bin/python3 tools/playthrough_capture.py --out {M.C.ROOT}/output/qa/starting --rom {rom}\n','')
  with patch.object(M.subprocess,'run',return_value=response):
   roots,_=M.recorder_roots();self.assertIn(rom.parent,roots)
 def test_rom_existing_work_never_modified_on_preflight_failure(self):
  a,b,raw,sha=self.rom_runs();work=M.C.ROOT/'temp'/('frame_recompress_clone_existing_'+self.root.name);work.mkdir()
  self.addCleanup(work.rmdir)
  argv=['clone','--rom','--source-run',str(a),'--target-run',str(b),'--exclude-run',str(self.root/'output/qa/live'),'--work',str(work)]
  with patch.object(sys,'argv',argv),patch.object(M.fcntl,'flock'):
   with self.assertRaises(FileExistsError):M.main()
  self.assertEqual(list(work.iterdir()),[])
 def test_game_save_relative_receipt_ancestry(self):
  a,b,raw,sha=self.rom_runs();live=self.root/'output/qa/live';live.mkdir(exist_ok=True)
  (live/'baseline.json').write_text(json.dumps({'initial_game_save':{'receipt':'game_save.json'}}))
  (live/'game_save.json').write_text(json.dumps({'source_checkpoint':str(b/'resume.checkpoint.json')}))
  with patch.object(M.C,'ROOT',self.root):self.assertIn(b,M.excluded_rom_runs([live]))

class NearRomTests(unittest.TestCase):
 setUp=RomCloneTests.setUp
 tearDown=RomCloneTests.tearDown
 fixture_run=CloneTests.fixture_run
 rom_runs=RomCloneTests.rom_runs
 def setup_near(self,offsets=(0x2000,0x2fff,0x3000)):
  a,b,raw,sha=self.rom_runs();target=bytearray(raw)
  for offset in offsets:target[offset]^=1
  target=bytes(target);target_sha=M.C.digest(target);(b/'baseline.gba').write_bytes(target)
  (b/'baseline.json').write_text(json.dumps({'rom_sha256':target_sha}))
  cp=json.loads((b/'resume.checkpoint.json').read_text());cp['rom_sha256']=target_sha;(b/'resume.checkpoint.json').write_text(json.dumps(cp))
  return a,b,raw,target
 def test_real_near_clone_target_exact_and_source_unchanged(self):
  a,b,raw,target=self.setup_near();work=self.root/'near';work.mkdir();before=M.metadata(b/'baseline.gba');old=(b/'baseline.gba').stat().st_ino
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   result=M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
  self.assertEqual(result['replaced'],1);self.assertTrue(result['near_rom'])
  self.assertEqual((a/'baseline.gba').read_bytes(),raw);self.assertEqual((b/'baseline.gba').read_bytes(),target)
  self.assertNotEqual(old,(b/'baseline.gba').stat().st_ino);self.assertEqual((b/'baseline.gba').stat().st_nlink,1)
  rows=[json.loads(x) for x in (work/'receipts.jsonl').read_text().splitlines()];self.assertEqual(rows[-1]['private_page_offsets'],[0x2000,0x3000]);self.assertEqual(rows[-1]['source_sha256'],M.C.digest(raw));self.assertTrue(rows[-1]['near_rom']);self.assertEqual(rows[-1]['status'],'committed')
  for k in ('mode','uid','gid','flags','mtime_ns','birthtime','xattrs'):self.assertEqual(M.metadata(b/'baseline.gba')[k],before[k])
 def test_exact_mode_still_rejects_different_rom(self):
  a,b,raw,target=self.setup_near();work=self.root/'near';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'SHA differs'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'])
 def test_private_stage_corruption_rejected(self):
  a,b,raw,target=self.setup_near();work=self.root/'near';work.mkdir();old=(b/'baseline.gba').stat().st_ino;original=M.clone
  def corrupt(source,destination,stage):
   original(source,destination,stage)
   with stage.open('r+b') as f:f.seek(0x4000);f.write(bytes([raw[0x4000]^1]))
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'clone',side_effect=corrupt):
   with self.assertRaisesRegex(ValueError,'Staged PNG bytes'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
  self.assertEqual((b/'baseline.gba').stat().st_ino,old);self.assertEqual((b/'baseline.gba').read_bytes(),target)
  self.assertEqual((a/'baseline.gba').read_bytes(),raw)
 def test_over_limit_pages_and_floor_reserve_rejected(self):
  a,b,raw,target=self.setup_near(tuple(i*4096 for i in range(1,1026)));work=self.root/'near';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'clone') as clone:
   with self.assertRaisesRegex(ValueError,'1024'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
   clone.assert_not_called()
 def test_zero_pages_rejected_and_maximum_allowed_in_dry_run(self):
  a,b,raw,target=self.setup_near(());work=self.root/'zero';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'1..1024'):M.execute_rom(a,b,work,False,[self.root/'output/qa/live'],True)
  data=bytearray(raw)
  for i in range(1,1025):data[i*4096]^=1
  sha=M.C.digest(bytes(data));(b/'baseline.gba').write_bytes(data);(b/'baseline.json').write_text(json.dumps({'rom_sha256':sha}))
  cp=json.loads((b/'resume.checkpoint.json').read_text());cp['rom_sha256']=sha;(b/'resume.checkpoint.json').write_text(json.dumps(cp));work=self.root/'max';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   self.assertEqual(M.execute_rom(a,b,work,False,[self.root/'output/qa/live'],True)['private_4k_pages'],1024)
 def test_near_flag_requires_rom_and_bad_source_sha_rejected(self):
  argv=['clone','--near-rom','--source-run','a','--target-run','b','--work','c']
  with patch.object(sys,'argv',argv):
   with self.assertRaisesRegex(ValueError,'explicit --rom'):M.main()
  a,b,raw,target=self.setup_near();(a/'baseline.json').write_text(json.dumps({'rom_sha256':'0'*64}));work=self.root/'bad';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'contract differs'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
 def test_short_private_write_preserves_original_target(self):
  a,b,raw,target=self.setup_near();work=self.root/'short';work.mkdir();original=Path.open;inode=(b/'baseline.gba').stat().st_ino
  class ShortWriter:
   def __init__(self,f):self.f=f
   def __enter__(self):return self
   def __exit__(self,*args):self.f.close()
   def __getattr__(self,key):return getattr(self.f,key)
   def write(self,data):return self.f.write(data[:-1])
  def opened(path,*args,**kwargs):
   f=original(path,*args,**kwargs)
   return ShortWriter(f) if path==work/'baseline.gba.partial' and args and args[0]=='r+b' else f
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(Path,'open',opened):
   with self.assertRaisesRegex(OSError,'Short stage'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
  self.assertEqual((b/'baseline.gba').stat().st_ino,inode);self.assertEqual((b/'baseline.gba').read_bytes(),target);self.assertEqual((a/'baseline.gba').read_bytes(),raw)
 def test_floor_reserve_rejects_before_clone(self):
  a,b,raw,target=self.setup_near();work=self.root/'near';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'free_bytes',return_value=15*1024**3+4096),patch.object(M,'clone') as clone:
   with self.assertRaisesRegex(ValueError,'reserve'):M.execute_rom(a,b,work,True,[self.root/'output/qa/live'],True)
   clone.assert_not_called()

class CandidateCloneTests(unittest.TestCase):
 setUp=RomCloneTests.setUp
 tearDown=RomCloneTests.tearDown
 fixture_run=CloneTests.fixture_run
 rom_runs=RomCloneTests.rom_runs
 def candidates(self):
  a,b,raw,sha=self.rom_runs();target=bytearray(raw);target[0x2000]^=1;target=bytes(target)
  folder=self.root/'temp/job';folder.mkdir(parents=True);candidate=folder/'candidate.gba';candidate.write_bytes(target)
  receipt=Path(str(candidate)+'.build.json');value={'schema':1,'stage':'development_build','release_ready':False,'source_sha256':M.ORIGINAL_ROM_SHA,'rom_sha256':M.C.digest(target),'repoint_enabled':True,'inputs_before':{'files':{'a':'1'}},'inputs_after':{'files':{'a':'1'}}};receipt.write_text(json.dumps(value))
  manifest=self.root/'temp/manifest.json';manifest.write_text(json.dumps({'recommended_recent':[{'path':str(candidate.relative_to(self.root)),'sha256':M.C.digest(target),'receipt_sha256':M.C.file_sha(receipt)}],'remaining':[]}))
  return a,candidate,manifest,target
 def run_candidate(self,a,target,manifest,near=True):
  work=self.root/'work';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'candidate_exclusions',return_value=(set(),set(),set())):
   return M.execute_candidate(a,target,work,True,[self.root/'output/qa/live'],manifest,near)
 def test_real_candidate_content_receipt_metadata_unchanged(self):
  a,target,manifest,raw=self.candidates();receipt=Path(str(target)+'.build.json');proof=receipt.read_bytes();meta=M.metadata(target);old=target.stat().st_ino
  result=self.run_candidate(a,target,manifest);self.assertEqual(result['replaced'],1);self.assertEqual(target.read_bytes(),raw);self.assertEqual(receipt.read_bytes(),proof);self.assertNotEqual(target.stat().st_ino,old)
  for k in ('mode','uid','gid','flags','mtime_ns','birthtime','xattrs'):self.assertEqual(M.metadata(target)[k],meta[k])
 def test_candidate_exact_follower_preserves_manifest_and_receipt(self):
  a,first,manifest,raw=self.candidates();folder=self.root/'temp/job2';folder.mkdir();second=folder/'candidate.gba';second.write_bytes(raw)
  receipt=Path(str(second)+'.build.json');receipt.write_bytes(Path(str(first)+'.build.json').read_bytes());doc=json.loads(manifest.read_text());doc['remaining']=[{'path':str(second.relative_to(self.root)),'sha256':M.C.digest(raw),'receipt_sha256':M.C.file_sha(receipt)}];manifest.write_text(json.dumps(doc));manifest_bytes=manifest.read_bytes()
  self.run_candidate(a,first,manifest);work=self.root/'exact';work.mkdir()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'),patch.object(M,'candidate_exclusions',return_value=(set(),set(),set())):
   result=M.execute_candidate(a,second,work,True,[self.root/'output/qa/live'],manifest,False,first,include_remaining=True)
  self.assertEqual(result['replaced'],1);self.assertEqual(second.read_bytes(),raw);self.assertEqual(manifest.read_bytes(),manifest_bytes);self.assertNotEqual(first.stat().st_ino,second.stat().st_ino)
 def test_receipt_mutation_and_nonallowlisted_rejected(self):
  a,target,manifest,raw=self.candidates();receipt=Path(str(target)+'.build.json');receipt.write_text(receipt.read_text()+' ')
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'receipt changed'):M.candidate_guard(target,manifest,set(),set())
   manifest.write_text(json.dumps({'recommended_recent':[],'remaining':[]}))
   with self.assertRaisesRegex(ValueError,'allowlisted'):M.candidate_guard(target,manifest,set(),set())
 def test_ancestor_sha_and_active_input_rejected(self):
  a,target,manifest,raw=self.candidates()
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'ancestor'):M.candidate_guard(target,manifest,{M.C.digest(raw)},set())
   with self.assertRaisesRegex(ValueError,'active ROM'):M.candidate_guard(target,manifest,set(),{target})
 def test_unstable_receipt_and_release_authority_not_accepted(self):
  a,target,manifest,raw=self.candidates();receipt=Path(str(target)+'.build.json');value=json.loads(receipt.read_text());value['inputs_after']['files']['a']='2';receipt.write_text(json.dumps(value));doc=json.loads(manifest.read_text());doc['recommended_recent'][0]['receipt_sha256']=M.C.file_sha(receipt);manifest.write_text(json.dumps(doc))
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'inputs changed'):M.candidate_guard(target,manifest,set(),set())
   value['release_ready']=True;receipt.write_text(json.dumps(value));doc['recommended_recent'][0]['receipt_sha256']=M.C.file_sha(receipt);manifest.write_text(json.dumps(doc))
   with self.assertRaisesRegex(ValueError,'development candidate'):M.candidate_guard(target,manifest,set(),set())
 def test_active_build_refused(self):
  response=subprocess.CompletedProcess([],0,'nice -n 15 /usr/bin/python3 tools/build_korean_full.py --out temp/new/candidate.gba\n','')
  with patch.object(M,'excluded_rom_runs',return_value=set()),patch.object(M.subprocess,'run',return_value=response):
   with self.assertRaisesRegex(ValueError,'Active build'):M.candidate_exclusions(['unused'])
 def test_manifest_pin_and_remaining_scope(self):
  a,target,manifest,raw=self.candidates();sha=M.C.file_sha(manifest)
  doc=json.loads(manifest.read_text());doc['remaining']=doc['recommended_recent'];doc['recommended_recent']=[];manifest.write_text(json.dumps(doc))
  with patch.object(M.C,'ROOT',self.root),patch.object(M.C,'unused'):
   with self.assertRaisesRegex(ValueError,'manifest SHA'):M.candidate_guard(target,manifest,set(),set(),sha)
   with self.assertRaisesRegex(ValueError,'allowlisted'):M.candidate_guard(target,manifest,set(),set())
   self.assertEqual(M.candidate_guard(target,manifest,set(),set(),M.C.file_sha(manifest),True)[0],M.C.digest(raw))
 def test_wrapped_relative_and_symlink_active_input(self):
  a,target,manifest,raw=self.candidates();link=self.root/'temp/link.gba';link.symlink_to(target)
  response=subprocess.CompletedProcess([],0,'nice -n 15 python3 runner.py --rom='+str(link)+'\n','')
  with patch.object(M.C,'ROOT',self.root),patch.object(M,'excluded_rom_runs',return_value=set()),patch.object(M.subprocess,'run',return_value=response):
   self.assertIn(target,M.candidate_exclusions(['unused'])[2])
 def test_shell_and_module_builds_and_ambiguous_paths_refused(self):
  lines=[("sh -c 'python3 tools/build_korean_full.py --out x'",'Active build'),('python3 -m tools.build_korean_full --out x','Active build'),("sh -c 'python3 runner.py --rom candidate.gba'",'Ambiguous'),('python3 runner.py --rom candidate.gba','Relative')]
  for line,error in lines:
   with self.subTest(line=line),patch.object(M,'excluded_rom_runs',return_value=set()),patch.object(M.subprocess,'run',return_value=subprocess.CompletedProcess([],0,line,' ' if False else '')):
    with self.assertRaisesRegex(ValueError,error):M.candidate_exclusions(['unused'])
 def test_candidate_stage_failure_preserves_original(self):
  a,target,manifest,raw=self.candidates();old=target.stat().st_ino
  with patch.object(M,'restore_stage_xattrs',side_effect=OSError('injected xattr failure')):
   with self.assertRaisesRegex(OSError,'injected'):self.run_candidate(a,target,manifest)
  self.assertEqual(target.stat().st_ino,old);self.assertEqual(target.read_bytes(),raw)

if __name__=='__main__':unittest.main()
