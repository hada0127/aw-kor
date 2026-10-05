import io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,PngImagePlugin
import recompress_closed_frames as R
class RecompressionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=R.ROOT/'temp');self.root=Path(self.tmp.name);self.image=Image.new('RGB',(240,160),(1,2,3));self.raw=self.png(self.image);self.rgb=R.digest(self.image.tobytes())
 def tearDown(self):self.tmp.cleanup()
 def png(self,im,**kw):
  b=io.BytesIO();im.save(b,format='PNG',compress_level=1,**kw);return b.getvalue()
 def test_exact_palette_and_reject_wrong_rgb(self):
  # Uniform images can grow with a palette; use a nontrivial repeated pattern.
  im=Image.new('RGB',(240,160));im.putdata([(x%16*16,y%8*30,0) for y in range(160) for x in range(240)]);rgb=R.digest(im.tobytes());new=R.encode_png(self.png(im),rgb);self.assertIsNotNone(new)
  self.assertEqual(Image.open(io.BytesIO(new)).convert('RGB').tobytes(),im.tobytes())
  with self.assertRaisesRegex(ValueError,'RGB'):R.encode_png(self.png(im),'0'*64)
 def test_skip_alpha_metadata_palette_and_too_many_colors(self):
  meta=PngImagePlugin.PngInfo();meta.add_text('proof','do not strip')
  for raw in [self.png(self.image.convert('RGBA')),self.png(self.image,pnginfo=meta),self.png(self.image.convert('P'))]:self.assertIsNone(R.encode_png(raw,self.rgb))
  im=Image.new('RGB',(240,160));im.putdata([(i%256,(i//256)%256,0) for i in range(240*160)]);self.assertIsNone(R.encode_png(self.png(im),R.digest(im.tobytes())))
 def fixture(self):
  run=self.root/'output/qa/part1_test/closed';(run/'frames').mkdir(parents=True);im=Image.new('RGB',(240,160));im.putdata([(x%16*16,y%8*30,0) for y in range(160) for x in range(240)]);rgb=R.digest(im.tobytes());frame=run/'frames'/(rgb+'.png');frame.write_bytes(self.png(im));ledger=(json.dumps({'core_frame':1,'rgb_sha256':rgb,'image':'frames/'+frame.name})+'\n').encode();(run/'frames.jsonl').write_bytes(ledger)
  (run/'baseline.json').write_text(json.dumps({'initial_core_frame':0}));(run/'baseline.gba').write_bytes(b'fixture');(run/'actions.jsonl').write_text('');(run/'resume.ss0').write_bytes(b'fixture state');(run/'endpoint.png').write_bytes(self.raw)
  (run/'resume.checkpoint.json').write_text(json.dumps({'core_frame':1,'ledger_bytes':len(ledger),'ledger_sha256':R.digest(ledger)}));(run/'exit.json').write_text(json.dumps({'status':'closed','emulator_exit_code':0,'cleanup_errors':[],'committed_core_frame':1,'last_observed_core_frame':1}));return run,frame
 def execute(self,run):
  work=self.root/'work';work.mkdir()
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'floor'),(work/'receipt').open('w') as rec,(work/'progress').open('w') as prog:return R.process_run(run,work,200,200,rec,prog)
 def test_full_batch_preserves_ledger_endpoint_and_parent_contract(self):
  run,frame=self.fixture();before={p:p.read_bytes() for p in run.iterdir() if p.is_file()};old=frame.read_bytes();result=self.execute(run);self.assertEqual(result['replaced'],1);self.assertNotEqual(frame.read_bytes(),old);self.assertTrue(all(p.read_bytes()==b for p,b in before.items()));self.assertTrue(result['verify_parent_before_after'])
 def test_skip_hardlink_and_closed_guard(self):
  run,frame=self.fixture();os.link(frame,self.root/'copy.png');self.assertEqual(self.execute(run)['replaced'],0)
  with patch.object(R,'ROOT',self.root):
   (run/'exit.json').write_text(json.dumps({'status':'open','emulator_exit_code':0}))
   with self.assertRaisesRegex(ValueError,'CLOSED'):R.run_guard(run)
 def test_unused_fails_on_open_or_uncertain_result(self):
  import subprocess
  for result in [subprocess.CompletedProcess([],0,'open',''),subprocess.CompletedProcess([],1,'','warning')]:
   with patch.object(R.subprocess,'run',return_value=result),patch.object(R.time,'sleep'),patch.object(R.time,'monotonic',side_effect=[0,30]):
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([self.root/'x'])
 def test_metadata_drift_and_floor_fail_closed(self):
  p=self.root/'x';p.write_text('a');guard={p:R.identity(p)};p.write_text('b')
  with self.assertRaisesRegex(ValueError,'metadata'):R.unchanged(guard)
  with patch.object(R.os,'statvfs',return_value=type('V',(),{'f_bavail':0,'f_frsize':4096})()):
   with self.assertRaisesRegex(ValueError,'floor'):R.floor()
 def test_window_cursor_advances_past_previously_considered_files(self):
  paths=[Path(c*64+'.png') for c in ['1','2','3']]
  self.assertEqual(R.select_window(paths,'',1),paths[:1]);self.assertEqual(R.select_window(paths,'1'*64,1),paths[1:2])
  with self.assertRaisesRegex(ValueError,'cursor'):R.select_window(paths,'bad',1)
 def test_inexact_palette_is_logged_skip_and_trailing_data_skips(self):
  reasons=[]
  with patch.object(Image.Image,'quantize',return_value=Image.new('P',(240,160))):self.assertIsNone(R.encode_png(self.raw,self.rgb,reasons))
  self.assertEqual(reasons,['inexact_palette']);reasons=[];self.assertIsNone(R.encode_png(self.raw+b'extra',self.rgb,reasons));self.assertEqual(reasons,['nonstandard_chunks_or_trailing_data'])
 def test_xattr_difference_fails_closed(self):
  with patch.object(R,'native_xattrs',side_effect=[{b'proof':b'old'},{b'proof':b'new'}]):
   with self.assertRaisesRegex(ValueError,'xattrs'):R.preserve_xattrs(self.root/'a',self.root/'b')
 def test_reference_scan_covers_ignored_and_relative_hashes(self):
  (self.root/'data').mkdir();(self.root/'.gitignore').write_text('data/ignored.json\n');(self.root/'data/ignored.json').write_text(json.dumps({'source':'output/qa/run/frames/'+'a'*64+'.png'}));(self.root/'.hidden.json').write_text(json.dumps({'relative':'frames/'+'b'*64+'.png'}))
  with patch.object(R,'ROOT',self.root):runs,hashes,evidence=R.reference_exclusions()
  self.assertIn('a'*64,hashes);self.assertIn('b'*64,hashes);self.assertIn(self.root/'output/qa/run',runs)
 def test_historical_scope_requires_quiescence_and_keeps_closed_guard(self):
  import subprocess
  good=subprocess.CompletedProcess([],0,'123 T /usr/bin/python3 tools/playthrough_capture.py --resume x\n','')
  with patch.object(R.subprocess,'run',return_value=good):R.historical_quiescence()
  for line in ['123 R /usr/bin/python3 tools/playthrough_capture.py --resume x\n',
               '123 S /repo/temp/mgbah_game_save rom log\n']:
   with patch.object(R.subprocess,'run',return_value=subprocess.CompletedProcess([],0,line,'')):
    with self.assertRaisesRegex(ValueError,'paused/closed'):R.historical_quiescence()
  run,frame=self.fixture();new=run.parent/'measured_live_tty';run.rename(new)
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'historical_quiescence'):
   with self.assertRaisesRegex(ValueError,'scope'):R.run_guard(new)
   R.run_guard(new,True)
   (new/'exit.json').write_text(json.dumps({'status':'open','emulator_exit_code':0}))
   with self.assertRaisesRegex(ValueError,'CLOSED'):R.run_guard(new,True)
 def test_individually_referenced_png_is_unchanged_in_historical_mode(self):
  run,frame=self.fixture();old=frame.read_bytes();work=self.root/'work';work.mkdir()
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'floor'),patch.object(R,'historical_quiescence'),(work/'receipt').open('w') as rec,(work/'progress').open('w') as prog:
   result=R.process_run(run,work,200,200,rec,prog,excluded_digests={frame.stem},allow_historical=True)
  self.assertEqual(result['replaced'],0);self.assertEqual(frame.read_bytes(),old)
 def test_historical_cli_wires_guards_and_file_sha_exclusion(self):
  import sys
  run,frame=self.fixture();old=frame.read_bytes();work=self.root/'temp/frame_recompress_cli';work.parent.mkdir()
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'floor'),patch.object(R,'historical_quiescence') as quiet,patch.object(R,'reference_exclusions',return_value=({run},set(),{})),patch.object(R,'file_sha_references',return_value=({R.digest(old)},{})),patch.object(sys,'argv',['recompress','--run',str(run),'--work',str(work),'--apply','--allow-historical-closed']):
   R.main()
  self.assertGreater(quiet.call_count,0);self.assertEqual(frame.read_bytes(),old)
  self.assertIn('referenced_file_sha256',(work/'receipts.jsonl').read_text())
  self.assertTrue(json.loads((work/'invocation.json').read_text())['allow_historical_closed'])
 def test_sha_only_txt_reference_and_module_capture(self):
  import subprocess
  token='e'*64;(self.root/'proof.txt').write_text('sha256: '+token)
  with patch.object(R,'ROOT',self.root):tokens,guards=R.file_sha_references()
  self.assertIn(token,tokens);self.assertIn(self.root/'proof.txt',guards)
  for command in ['python3 -m playthrough_capture --resume x','python3 -c "import playthrough_capture"','python3 -mplaythrough_capture','python3 -cimport_playthrough_capture']:
   with patch.object(R.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'123 R '+command+'\n','')):
    with self.assertRaisesRegex(ValueError,'paused/closed'):R.historical_quiescence()
 def test_source_mutation_after_prepared_receipt_is_not_overwritten(self):
  run,frame=self.fixture();real=R.append_rows
  def mutate(stream,rows):
   real(stream,rows)
   if any(r.get('status')=='verified_before_replace' for r in rows):frame.write_bytes(b'external writer')
  with patch.object(R,'append_rows',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'replace guard'):self.execute(run)
  self.assertEqual(frame.read_bytes(),b'external writer')
 def test_reference_scan_ignores_own_receipts_independent_of_cwd(self):
  hist=self.root/'temp/frame_recompress_history';hist.mkdir(parents=True);(hist/'receipts.jsonl').write_text(json.dumps({'path':'output/qa/run/frames/'+'c'*64+'.png'}));away=self.root/'away';away.mkdir();previous=Path.cwd()
  try:
   os.chdir(away)
   with patch.object(R,'ROOT',self.root):runs,hashes,evidence=R.reference_exclusions()
  finally:os.chdir(previous)
  self.assertNotIn('c'*64,hashes);self.assertFalse(runs)
 def test_transient_reader_must_close_before_unused_succeeds(self):
  import subprocess
  outputs=[subprocess.CompletedProcess([],0,'reader',''),subprocess.CompletedProcess([],1,'','')]
  with patch.object(R.subprocess,'run',side_effect=outputs) as call,patch.object(R.time,'sleep') as sleep:R.unused([self.root/'x'])
  self.assertEqual(call.call_count,2);sleep.assert_called_once_with(0.25)
 def test_spotlight_exception_is_narrow_and_opt_in(self):
  import subprocess
  name=str(self.root/'frame.png');output='p123\0\nf3\0ar\0tREG\0n'+name+'\0\n'
  trusted=next(iter(R.SPOTLIGHT_EXECUTABLES))
  with patch.object(R,'process_executable',return_value=trusted):
   self.assertTrue(R.only_spotlight_readers(output,[Path(name)]))
   for bad in [output.replace('ar\0','aw\0'),output.replace('ar\0','au\0'),output.replace('ar\0',''),output.replace('f3\0','ftxt\0'),output.replace('tREG','tDIR'),output.replace(name,name+'x'),output+'bad\0',output.replace('ar\0','ar\0ar\0')]:self.assertFalse(R.only_spotlight_readers(bad,[Path(name)]))
   with patch.object(R.subprocess,'run',return_value=subprocess.CompletedProcess([],0,output,'')),patch.object(R.time,'sleep'),patch.object(R.time,'monotonic',side_effect=[0,0,30]):
    R.unused([Path(name)],allow_spotlight=True)
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([Path(name)])
  with patch.object(R,'process_executable',return_value='/tmp/mdworker'):self.assertFalse(R.only_spotlight_readers(output,[Path(name)]))
  with patch.object(R,'process_executable',return_value=None):self.assertFalse(R.only_spotlight_readers(output,[Path(name)]))
 def test_post_reader_mutation_is_detected(self):
  run,frame=self.fixture();work=self.root/'work';work.mkdir()
  def readers(paths,allow_spotlight=False):
   if allow_spotlight:frame.write_bytes(b'external mutation')
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused',side_effect=readers),patch.object(R,'floor'),(work/'receipt').open('w') as rec,(work/'progress').open('w') as prog:
   with self.assertRaisesRegex(ValueError,'after reader check'):R.process_run(run,work,200,200,rec,prog)
 def test_spotlight_mixed_processes_and_kernel_path(self):
  name=str(self.root/'frame.png');record='f3\0ar\0tREG\0n'+name+'\0\n';trusted=next(iter(R.SPOTLIGHT_EXECUTABLES))
  with patch.object(R,'process_executable',side_effect=[trusted,'/untrusted/mdworker']):self.assertFalse(R.only_spotlight_readers('p123\0\n'+record+'p456\0\n'+record,[Path(name)]))
  with patch.object(R,'process_executable',return_value=trusted):self.assertFalse(R.only_spotlight_readers('p123\0\n',[Path(name)]))
  own=R.process_executable(os.getpid());self.assertIsNotNone(own);self.assertNotIn(own,R.SPOTLIGHT_EXECUTABLES)
 def test_only_post_png_check_has_exception(self):
  run,frame=self.fixture();work=self.root/'work';work.mkdir()
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused') as calls,patch.object(R,'floor'),(work/'receipt').open('w') as rec,(work/'progress').open('w') as prog:R.process_run(run,work,200,200,rec,prog)
  exceptions=[c for c in calls.call_args_list if c.kwargs.get('allow_spotlight')]
  self.assertEqual(len(exceptions),1);self.assertEqual(exceptions[0].args[0],[frame])
 def test_reader_wait_uses_30_second_deadline_and_never_accepts_open(self):
  import subprocess
  opened=subprocess.CompletedProcess([],0,'p123\0\nf3\0aw\0tREG\0n/file\0\n','')
  with patch.object(R.subprocess,'run',return_value=opened) as calls,patch.object(R.time,'monotonic',side_effect=[10,10.1,39.9,40]),patch.object(R.time,'sleep') as sleeps:
   with self.assertRaisesRegex(ValueError,'lsof'):R.unused([self.root/'x'])
  self.assertEqual(calls.call_count,3);self.assertEqual(sleeps.call_count,2)
  self.assertAlmostEqual(sleeps.call_args_list[0].args[0],0.25);self.assertAlmostEqual(sleeps.call_args_list[1].args[0],0.1)
 def test_uncertain_lsof_fails_immediately_even_with_wait_budget(self):
  import subprocess
  uncertain=subprocess.CompletedProcess([],1,'','permission warning')
  with patch.object(R.subprocess,'run',return_value=uncertain) as calls,patch.object(R.time,'sleep') as sleeps:
   with self.assertRaisesRegex(ValueError,'lsof'):R.unused([self.root/'x'])
  self.assertEqual(calls.call_count,1);sleeps.assert_not_called()
 def test_partial_rc1_is_rechecked_as_disjoint_complete_groups(self):
  import subprocess
  a,b,c=[self.root/name for name in ['a','b','c']];output='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n'
  results=[subprocess.CompletedProcess([],1,output,''),subprocess.CompletedProcess([],0,output,''),subprocess.CompletedProcess([],1,'','')]
  with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=results) as calls:
   R.unused([a,b,c],allow_spotlight=True)
  self.assertEqual(calls.call_count,3)
  self.assertEqual(calls.call_args_list[1].args[0][4:],[str(a)])
  self.assertEqual(calls.call_args_list[2].args[0][4:],[str(b),str(c)])
  self.assertGreater(calls.call_args_list[1].kwargs['timeout'],0)
 def test_partial_recheck_rejects_writer_mmap_unknown_and_uncertainty(self):
  import subprocess
  a,b=[self.root/name for name in ['a','b']];record='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n';initial=subprocess.CompletedProcess([],1,record,'')
  for bad in [subprocess.CompletedProcess([],0,record.replace('ar\0','aw\0'),''),subprocess.CompletedProcess([],0,record.replace('ar\0','a \0'),''),subprocess.CompletedProcess([],1,'','error')]:
   with self.subTest(result=bad),patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=[initial,bad]):
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([a,b],allow_spotlight=True)
  with patch.object(R,'process_executable',side_effect=[next(iter(R.SPOTLIGHT_EXECUTABLES))]+['/unknown/process']*10),patch.object(R.subprocess,'run',side_effect=[initial,subprocess.CompletedProcess([],0,record,'')]):
   with self.assertRaisesRegex(ValueError,'lsof'):R.unused([a,b],allow_spotlight=True)
 def test_partial_initial_never_bypasses_non_opt_in_or_strict_parser(self):
  import subprocess
  a=self.root/'a';record='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n'
  for enabled,output in [(False,record),(True,record.replace('ar\0','au\0'))]:
   with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',return_value=subprocess.CompletedProcess([],1,output,'')) as calls:
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([a],allow_spotlight=enabled)
    self.assertEqual(calls.call_count,1)
 def test_partial_missing_partition_new_writer_and_timeout_rejected(self):
  import subprocess
  a,b=[self.root/name for name in ['a','b']];record='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n';first=subprocess.CompletedProcess([],1,record,'');clear=subprocess.CompletedProcess([],1,'','')
  writer=subprocess.CompletedProcess([],0,record.replace(str(a),str(b)).replace('ar\0','aw\0'),'')
  for last in [writer,subprocess.TimeoutExpired('lsof',1)]:
   with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=[first,clear,last]):
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([a,b],allow_spotlight=True)
 def test_partial_spotlight_can_close_during_recheck(self):
  import subprocess
  a,b=[self.root/name for name in ['a','b']];record='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n'
  partial=subprocess.CompletedProcess([],1,record,'');clear=subprocess.CompletedProcess([],1,'','')
  with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=[partial,partial,clear,clear]),patch.object(R.time,'sleep'):
   R.unused([a,b],allow_spotlight=True)
 def test_stream_tokens_boundary_nonutf8_and_long_hex(self):
  for offset in [0,2**20-65,2**20-64,2**20-32,2**20-1,2**20]:
   p=self.root/'proof.txt';p.write_bytes(b' '*offset+b'\xff\x00 frames/'+b'A'*64+b'.png '+b'b'*65+b' _'+b'C'*64)
   self.assertEqual(R.text_sha_tokens(p),{'a'*64,'c'*64})
 def test_cli_rgb_token_from_txt_protects_png(self):
  import sys
  run,frame=self.fixture();old=frame.read_bytes();work=self.root/'temp/frame_recompress_rgb';work.parent.mkdir()
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'floor'),patch.object(R,'historical_quiescence'),patch.object(R,'reference_exclusions',return_value=(set(),set(),{})),patch.object(R,'file_sha_references',return_value=({frame.stem},{})),patch.object(sys,'argv',['recompress','--run',str(run),'--work',str(work),'--apply','--allow-historical-closed']):R.main()
  self.assertEqual(frame.read_bytes(),old);self.assertEqual(json.loads((work/'summary.json').read_text())[0]['replaced'],0)
 def test_cli_reference_guard_is_wired_and_rejects_drift(self):
  import sys
  run,frame=self.fixture();work=self.root/'temp/frame_recompress_drift';work.parent.mkdir();proof=self.root/'proof.txt';proof.write_text('original');guards={proof:R.identity(proof)}
  def refs():
   proof.write_text('mutated');return set(),guards
  with patch.object(R,'ROOT',self.root),patch.object(R,'unused'),patch.object(R,'floor'),patch.object(R,'historical_quiescence'),patch.object(R,'reference_exclusions',return_value=(set(),set(),{})),patch.object(R,'file_sha_references',side_effect=refs),patch.object(sys,'argv',['recompress','--run',str(run),'--work',str(work),'--apply','--allow-historical-closed']):
   with self.assertRaisesRegex(ValueError,'metadata'):R.main()
 def test_transient_spotlight_map_waits_for_fresh_absence(self):
  import subprocess
  p=self.root/'a';record='p123\0\nftxt\0a \0tREG\0n'+str(p)+'\0\n'
  mapped=subprocess.CompletedProcess([],1,record,'');clear=subprocess.CompletedProcess([],1,'','')
  with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=[mapped,clear]) as calls,patch.object(R.time,'sleep') as sleep:
   R.unused([p],allow_spotlight=True)
  self.assertEqual(calls.call_count,2);sleep.assert_called_once()
 def test_transient_map_never_accepted_and_unknown_never_retried(self):
  import subprocess
  p=self.root/'a';record='p123\0\nftxt\0a \0tREG\0n'+str(p)+'\0\n';mapped=subprocess.CompletedProcess([],1,record,'')
  with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',return_value=mapped),patch.object(R.time,'monotonic',side_effect=[0,31]):
   with self.assertRaisesRegex(ValueError,'deadline'):R.unused([p],allow_spotlight=True)
  with patch.object(R,'process_executable',return_value='/unknown'),patch.object(R.subprocess,'run',return_value=mapped) as calls:
   with self.assertRaisesRegex(ValueError,'lsof'):R.unused([p],allow_spotlight=True)
  self.assertEqual(calls.call_count,1)
 def test_partition_map_must_be_rechecked_to_clear(self):
  import subprocess
  a,b=[self.root/n for n in ['a','b']];read='p123\0\nf3\0ar\0tREG\0n'+str(a)+'\0\n';mapped=read.replace('f3\0ar','ftxt\0a ')
  initial=subprocess.CompletedProcess([],1,read,'');mapping=subprocess.CompletedProcess([],1,mapped,'');clear=subprocess.CompletedProcess([],1,'','')
  with patch.object(R,'process_executable',return_value=next(iter(R.SPOTLIGHT_EXECUTABLES))),patch.object(R.subprocess,'run',side_effect=[initial,mapping,clear,clear]) as calls,patch.object(R.time,'sleep'):
   R.unused([a,b],allow_spotlight=True)
  self.assertEqual(calls.call_count,4)
 def test_vanished_pid_only_triggers_fresh_recheck(self):
  import subprocess
  p=self.root/'a';record='p123\0\nf3\0ar\0tREG\0n'+str(p)+'\0\n';opened=subprocess.CompletedProcess([],1,record,'');clear=subprocess.CompletedProcess([],1,'','')
  with patch.object(R,'process_executable',return_value=None),patch.object(R.os,'kill',side_effect=ProcessLookupError),patch.object(R.subprocess,'run',side_effect=[opened,clear]) as calls,patch.object(R.time,'sleep'):
   R.unused([p],allow_spotlight=True)
  self.assertEqual(calls.call_count,2)
  with patch.object(R,'process_executable',return_value=None),patch.object(R.os,'kill',side_effect=ProcessLookupError):self.assertFalse(R.only_spotlight_readers(record,[p]))
 def test_unresolved_live_or_permission_pid_still_rejected(self):
  import subprocess
  p=self.root/'a';record='p123\0\nf3\0ar\0tREG\0n'+str(p)+'\0\n';opened=subprocess.CompletedProcess([],1,record,'')
  for effect in [None,PermissionError]:
   with patch.object(R,'process_executable',return_value=None),patch.object(R.os,'kill',side_effect=effect),patch.object(R.subprocess,'run',return_value=opened) as calls:
    with self.assertRaisesRegex(ValueError,'lsof'):R.unused([p],allow_spotlight=True)
   self.assertEqual(calls.call_count,1)
if __name__=='__main__':unittest.main()
