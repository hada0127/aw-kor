"""Exact PNG proof reuse must never replace ledger/chain/image verification."""
import hashlib,io,json,os,sys,tempfile,time,unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
import playthrough_capture as P
import game_save_evidence as G

class CacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=P.ROOT/'temp');self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.png=self.root/'frame.png'
  Image.new('RGB',(240,160),(12,34,56)).save(self.png,compress_level=3)
  self.rgb=hashlib.sha256(Image.open(self.png).convert('RGB').tobytes()).hexdigest()
  (self.root/'baseline.gba').write_bytes(b'ROM');(self.root/'state.ss0').write_bytes(b'STATE')
  self.baseline={'schema_version':3,'initial_core_frame':0,'rom_sha256':P.sha(self.root/'baseline.gba'),'harness_sha256':'a'*64,'libmgba_sha256':'b'*64}
  P.save_json(self.root/'baseline.json',self.baseline)
  self.row={'core_frame':1,'image':'frame.png','rgb_sha256':self.rgb}
  (self.root/'frames.jsonl').write_text(json.dumps(self.row)+'\n')
  self.cp={**{k:self.baseline[k] for k in ('rom_sha256','harness_sha256','libmgba_sha256')},'core_frame':1,'state':'state.ss0','state_sha256':P.sha(self.root/'state.ss0'),'baseline_sha256':P.sha(self.root/'baseline.json'),'ledger_bytes':(self.root/'frames.jsonl').stat().st_size,'ledger_sha256':P.sha(self.root/'frames.jsonl')}
  self.cp_path=self.root/'frame.checkpoint.json';P.save_json(self.cp_path,self.cp)
 def verify(self,cache=None):P.verify_parent(self.cp_path,self.cp,frame_cache=cache)
 def test_exact_bytes_reuse_and_default_still_decodes(self):
  c=P.FrameVerificationCache();self.verify(c)
  with patch.object(P.Image,'open',side_effect=AssertionError('decode')):self.verify(c)
  self.assertEqual((c.decodes,c.hits),(1,1))
  with patch.object(P.Image,'open',side_effect=AssertionError('decode')):
   with self.assertRaisesRegex(AssertionError,'decode'):self.verify()
 def test_lossless_recompression_must_redecode(self):
  c=P.FrameVerificationCache();self.verify(c);old=self.png.read_bytes()
  Image.new('RGB',(240,160),(12,34,56)).save(self.png,compress_level=9)
  self.assertNotEqual(old,self.png.read_bytes());self.verify(c);self.assertEqual((c.decodes,c.hits),(2,0))
 def test_bad_pixels_size_and_truncation_agree_with_default(self):
  c=P.FrameVerificationCache();self.verify(c)
  good=self.png.read_bytes()
  for kind in ['pixels','size','truncated']:
   with self.subTest(kind=kind):
    if kind=='truncated':self.png.write_bytes(good[:40])
    else:Image.new('RGB',(1,1) if kind=='size' else (240,160),(0,0,0)).save(self.png)
    for cache in [None,c]:
     with self.assertRaises(Exception):self.verify(cache)
 def test_changed_expected_rgb_is_not_cached_success(self):
  c=P.FrameVerificationCache();self.verify(c)
  with self.assertRaisesRegex(RuntimeError,'hash mismatch'):c.verify(self.png,'f'*64)
  for digest in [self.rgb.upper(),self.rgb+' ',None]:
   with self.assertRaisesRegex(RuntimeError,'hash mismatch'):c.verify(self.png,digest)
 def test_bounded_cache_and_large_png_fallback(self):
  for c in [P.FrameVerificationCache(max_entries=0),P.FrameVerificationCache(max_png_bytes=1)]:
   self.verify(c);self.verify(c);self.assertEqual((c.decodes,c.hits),(2,0));self.assertEqual(len(c._proofs),0)
  c=P.FrameVerificationCache(max_entries=1);self.verify(c)
  other=self.root/'other.png';Image.new('RGB',(240,160),(3,2,1)).save(other)
  digest=hashlib.sha256(Image.open(other).convert('RGB').tobytes()).hexdigest()
  c.verify(other,digest);c.verify(other,digest);self.assertEqual(len(c._proofs),1);self.assertEqual(c.decodes,3)
 def test_ledger_and_baseline_still_checked_on_hit(self):
  c=P.FrameVerificationCache();self.verify(c)
  for path in [self.root/'frames.jsonl',self.root/'baseline.json']:
   old=path.read_bytes();path.write_bytes(old+b' ')
   if path.name=='frames.jsonl':
    changed=bytearray(old);changed[2]^=1;path.write_bytes(changed)
   for cache in [None,c]:
    with self.assertRaises(RuntimeError):self.verify(cache)
   path.write_bytes(old)
 def test_escape_rejected_even_with_matching_content(self):
  c=P.FrameVerificationCache();self.verify(c)
  outside=self.root/'child';outside.mkdir();(outside/'alias.png').symlink_to(self.png)
  baseline={**self.baseline};P.save_json(outside/'baseline.json',baseline)
  row={**self.row,'image':'alias.png'};(outside/'frames.jsonl').write_text(json.dumps(row)+'\n')
  cp={**self.cp,'baseline_sha256':P.sha(outside/'baseline.json'),'ledger_bytes':(outside/'frames.jsonl').stat().st_size,'ledger_sha256':P.sha(outside/'frames.jsonl')}
  for cache in [None,c]:
   with self.assertRaisesRegex(RuntimeError,'escapes'):P.verify_parent(outside/'cp.json',cp,frame_cache=cache)
 def test_concurrent_replacement_rejected(self):
  c=P.FrameVerificationCache();original=P.Image.open
  def replacing(*args,**kwargs):
   replacement=self.root/'new.png';replacement.write_bytes(self.png.read_bytes());os.replace(replacement,self.png)
   return original(*args,**kwargs)
  with patch.object(P.Image,'open',side_effect=replacing):
   with self.assertRaisesRegex(RuntimeError,'changed during'):self.verify(c)
  self.assertEqual(len(c._proofs),0)
 def test_parent_chain_is_revalidated_even_with_cached_images(self):
  c=P.FrameVerificationCache();self.verify(c)
  child=self.root/'child';child.mkdir()
  baseline={**self.baseline,'initial_core_frame':1,'parent_checkpoint':str(self.cp_path),'parent_checkpoint_sha256':P.sha(self.cp_path)}
  P.save_json(child/'baseline.json',baseline);(child/'frames.jsonl').write_bytes(b'')
  cp={**self.cp,'baseline_sha256':P.sha(child/'baseline.json'),'ledger_bytes':0,'ledger_sha256':P.sha(child/'frames.jsonl')}
  P.verify_parent(child/'cp.json',cp,frame_cache=c);self.assertEqual(c.hits,1)
  self.cp_path.write_bytes(self.cp_path.read_bytes()+b' ')
  for cache in [None,c]:
   with self.assertRaisesRegex(RuntimeError,'Parent checkpoint hash'):P.verify_parent(child/'cp.json',cp,frame_cache=cache)
 def receipt(self):
  out=self.root/'save';out.mkdir();(out/'game.sav').write_bytes(bytes(range(256))*2)
  r={k:self.cp[k] for k in ('rom_sha256','libmgba_sha256','core_frame','state_sha256')}
  r.update(kind='cartridge-save-from-recorded-checkpoint-v1',save='game.sav',save_sha256=P.sha(out/'game.sav'),source_checkpoint=str(self.cp_path),source_checkpoint_sha256=P.sha(self.cp_path),source_harness_sha256=self.cp['harness_sha256'])
  path=out/'game_save.json';P.save_json(path,r);return path
 def test_receipt_still_rejects_rom_state_save_checkpoint_mutation(self):
  receipt=self.receipt();c=P.FrameVerificationCache();self.verify(c);G.verify_receipt(receipt,frame_cache=c)
  for path in [self.root/'baseline.gba',self.root/'state.ss0',self.cp_path,receipt.parent/'game.sav']:
   old=path.read_bytes();path.write_bytes(old+b'changed')
   with self.assertRaises(ValueError):G.verify_receipt(receipt,frame_cache=c)
   path.write_bytes(old)
 def test_real_recorder_forwards_cache_before_native_launch(self):
  receipt=self.receipt();c=P.FrameVerificationCache();self.verify(c)
  harness=self.root/'harness';harness.write_bytes(b'dummy')
  args=SimpleNamespace(out=self.root/'cold',rom=self.root/'baseline.gba',harness=harness,resume=None,game_save=receipt,min_free_gib=1,timeout=1,png_compress_level=3)
  original=P.sha
  def digest(path):
   return 'b'*64 if 'libmgba' in Path(path).name and Path(path).suffix=='.dylib' else original(path)
  with patch.object(P,'sha',side_effect=digest),patch.object(P.subprocess,'Popen',side_effect=RuntimeError('native launch intentionally blocked')) as launch,patch('builtins.print'):
   with self.assertRaisesRegex(RuntimeError,'intentionally blocked'):P.Recorder(args,frame_verification_cache=c)
  launch.assert_called_once();self.assertEqual((c.decodes,c.hits),(1,1))
 def test_distinct_paths_reuse_bytes_but_reject_changed_alias(self):
  other=self.root/'second.png';other.write_bytes(self.png.read_bytes())
  rows=[self.row,{**self.row,'core_frame':2,'image':'second.png'}]
  (self.root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  self.cp.update(core_frame=2,ledger_bytes=(self.root/'frames.jsonl').stat().st_size,ledger_sha256=P.sha(self.root/'frames.jsonl'))
  c=P.FrameVerificationCache();self.verify(c)
  self.assertEqual((c.decodes,c.hits),(1,1))
  Image.new('RGB',(240,160),(200,100,50)).save(other)
  with self.assertRaisesRegex(RuntimeError,'Parent image hash mismatch'):self.verify(c)
 def test_resume_recorder_reuses_only_verified_png_bytes(self):
  c=P.FrameVerificationCache();self.verify(c)
  harness=self.root/'harness';harness.write_bytes(b'dummy')
  self.baseline['harness_sha256']=P.sha(harness);P.save_json(self.root/'baseline.json',self.baseline)
  self.cp.update(harness_sha256=P.sha(harness),baseline_sha256=P.sha(self.root/'baseline.json'))
  P.save_json(self.cp_path,self.cp)
  args=SimpleNamespace(out=self.root/'resume',rom=self.root/'baseline.gba',harness=harness,resume=self.cp_path,game_save=None,min_free_gib=1,timeout=1,png_compress_level=3)
  original=P.sha
  def digest(path):
   return 'b'*64 if 'libmgba' in Path(path).name and Path(path).suffix=='.dylib' else original(path)
  with patch.object(P,'sha',side_effect=digest),patch.object(P.subprocess,'Popen',side_effect=RuntimeError('native launch intentionally blocked')) as launch,patch('builtins.print'):
   with self.assertRaisesRegex(RuntimeError,'intentionally blocked'):P.Recorder(args,frame_verification_cache=c)
  launch.assert_called_once();self.assertEqual((c.decodes,c.hits),(1,1))
 def test_cli_resume_cache_is_opt_in_and_requires_resume(self):
  base=['capture','--rom','rom','--harness','harness','--out',str(self.root/'new')]
  with patch.object(sys,'argv',base+['--cache-resume-frames']),patch.object(P,'Recorder') as recorder,patch.object(sys,'stderr',io.StringIO()):
   with self.assertRaises(SystemExit):P.main()
   recorder.assert_not_called()
  for enabled in (False,True):
   seen=[]
   def recorder(args,*,frame_verification_cache):
    seen.append(frame_verification_cache)
    r=Mock();r.out=self.root;r.counter=0;r.close.return_value={'status':'closed'};return r
   argv=base+['--resume',str(self.cp_path)]+(['--cache-resume-frames'] if enabled else [])
   with patch.object(sys,'argv',argv),patch.object(sys,'stdin',io.StringIO('quit\n')),patch.object(P,'Recorder',side_effect=recorder),patch('builtins.print'):P.main()
   self.assertEqual(isinstance(seen[0],P.FrameVerificationCache),enabled)
 def test_cli_bad_export_paths_fail_before_export(self):
  base=['capture','--rom','rom','--harness','harness','--out',str(self.root/'cold'),'--export-game-save',str(self.cp_path)]
  for tail in [[],['--export-game-save-out',str(self.root/'cold')],['--export-game-save-out',str(self.root/'cold'/'nested')],['--export-game-save-out',str(self.root/'space here')],['--export-game-save-out',str(self.root/'new'),'--resume','cp']]:
   with patch.object(sys,'argv',base+tail),patch.object(G,'export') as export,patch.object(sys,'stderr',io.StringIO()):
    with self.assertRaises(SystemExit):P.main()
    export.assert_not_called()
 def test_cli_export_and_coldboot_share_only_same_process_context(self):
  receipt=self.receipt();seen=[]
  def export(cp,harness,out,*,frame_cache,announce):
   self.assertFalse(announce)
   self.verify(frame_cache);seen.append(frame_cache);return receipt
  def recorder(args,*,frame_verification_cache):
   self.assertIs(frame_verification_cache,seen[0]);G.verify_receipt(args.game_save,frame_cache=frame_verification_cache)
   r=Mock();r.out=self.root;r.counter=0;r.close.return_value={'status':'closed'};return r
  argv=['capture','--rom',str(self.root/'baseline.gba'),'--harness','dummy','--out',str(self.root/'cold'),'--export-game-save',str(self.cp_path),'--export-game-save-out',str(self.root/'newsave')]
  with patch.object(sys,'argv',argv),patch.object(sys,'stdin',io.StringIO('quit\n')),patch.object(G,'export',side_effect=export),patch.object(P,'Recorder',side_effect=recorder),patch('builtins.print'):P.main()
  self.assertEqual((seen[0].decodes,seen[0].hits),(1,1))

if __name__=='__main__':unittest.main()
