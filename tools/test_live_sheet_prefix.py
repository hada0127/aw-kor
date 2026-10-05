import hashlib,json,sys,unittest
from unittest.mock import patch
import test_prune_capture_sheets as fixtures
import live_sheet_prefix as L
import prune_capture_sheets as P

class LivePrefixTests(unittest.TestCase):
 def tearDown(self):fixtures.SheetPruningTests.tearDown(self)
 def setUp(self):
  fixtures.SheetPruningTests.setUp(self)
  (self.run/'baseline.json').write_text('{"initial_core_frame":0}')
  (self.run/'anchor.ss0').write_bytes(b'fixture state')
  for n in range(1,42):
   (self.run/f'{n:04d}_NONE_{n:07d}.checkpoint.json').write_text(json.dumps({'core_frame':n}))
  cp=json.loads((self.run/'resume.checkpoint.json').read_text())
  cp.update(baseline_sha256=P.sha(self.run/'baseline.json'),state='anchor.ss0',state_sha256=P.sha(self.run/'anchor.ss0'))
  (self.run/'0041_NONE_0000041.checkpoint.json').write_text(json.dumps(cp))
  (self.run/'exit.json').write_text('{"status":"failed","error":"disk guard"}')
  (self.root/'tools').mkdir();(self.root/'tools/live_sheet_prefix.py').write_text('fixture identity')
 def test_reference_scan_preexcludes_only_verified_own_records(self):
  own=self.root/'temp/owned';own.mkdir(parents=True)
  (own/'plan.json').write_text(json.dumps({'kind':'capture-sheet-pruning-v1'}))
  (own/'receipts.jsonl').write_text('0021_NONE_0000021_sheet.png')
  (own/'notes.txt').write_text('0022_NONE_0000022_sheet.png')
  original=P.subprocess.run;commands=[];outputs=[]
  def run(command,**kwargs):
   commands.append(command);result=original(command,**kwargs);outputs.append(result.stdout);return result
  with patch.object(P.subprocess,'run',side_effect=run):names=P.reference_names()
  self.assertNotIn('0021_NONE_0000021_sheet.png',names);self.assertIn('0022_NONE_0000022_sheet.png',names)
  self.assertIn('!/temp/owned/receipts.jsonl',commands[0]);self.assertNotIn('!/temp/owned/notes.txt',commands[0])
  self.assertFalse(any('receipts.jsonl:' in text for text in outputs));self.assertTrue(any('notes.txt:' in text for text in outputs))
 def test_glob_directory_cannot_hide_unverified_sibling(self):
  own=self.root/'temp/own*';own.mkdir(parents=True);(own/'plan.json').write_text(json.dumps({'kind':'capture-sheet-pruning-v1'}));(own/'receipts.jsonl').write_text('0021_NONE_0000021_sheet.png')
  sibling=self.root/'temp/own_unverified';sibling.mkdir();(sibling/'receipts.jsonl').write_text('0022_NONE_0000022_sheet.png')
  self.assertIn('0022_NONE_0000022_sheet.png',P.reference_names())
 def test_changed_excluded_plan_fails_reference_scan(self):
  own=self.root/'temp/owned';own.mkdir(parents=True);plan=own/'plan.json';plan.write_text(json.dumps({'kind':'capture-sheet-pruning-v1'}))
  original=P.subprocess.run
  def run(command,**kwargs):
   result=original(command,**kwargs);plan.write_text('{}');return result
  with patch.object(P.subprocess,'run',side_effect=run):
   with self.assertRaises(ValueError):P.reference_names()
 def test_missing_boundary_rejected(self):
  with self.assertRaisesRegex(ValueError,'boundary'):L.PrefixGuard().check(all_fixed=False)
 def test_cli_guard_batch_rejects_bad_range_and_missing_mode(self):
  for extra in (['--guard-batch-size','49','--committed-prefix'],['--guard-batch-size','201','--committed-prefix'],['--guard-batch-size','200']):
   with patch.object(sys,'argv',['prune']+extra):
    with self.assertRaises(SystemExit):P.main()
 def test_current_batch_checks_selected_not_future_but_final_checks_all(self):
  plans,guard=L.prepare(self.run,10)
  future=self.run/'future.txt';future.write_text('fixed');guard.add_fixed(future)
  future.write_text('changed')
  with patch.object(L,'unused'):L.batch_guard(plans,guard)
  with self.assertRaises(ValueError):guard.check()
  self.frame.write_bytes(b'changed')
  with patch.object(L,'unused'):
   with self.assertRaises(ValueError):L.batch_guard(plans,guard)
 def test_batch_keeps_anchor_verification(self):
  plans,guard=L.prepare(self.run,10);(self.run/'baseline.json').write_text('{}')
  with patch.object(L,'unused'):
   with self.assertRaises(ValueError):L.batch_guard(plans,guard)
 def test_prefix_retains_first_recent_and_failed_exit(self):
  before=(self.run/'exit.json').read_bytes();plans,guard=L.prepare(self.run,10)
  self.assertEqual([p['samples'][0]['frame'] for p in plans],[21]);guard.check()
  self.assertEqual((self.run/'exit.json').read_bytes(),before)
 def test_append_and_partial_action_suffix_allowed(self):
  plans,guard=L.prepare(self.run,10)
  with (self.run/'actions.jsonl').open('ab') as f:f.write(b'{"status":"started","segment":42}\n{"partial":')
  with (self.run/'frames.jsonl').open('ab') as f:f.write(b'{"uncommitted":')
  guard.check();new,_=L.prepare(self.run,10);self.assertEqual(len(new),1)
 def test_changed_prefix_truncate_and_replacement_rejected(self):
  for filename in ('actions.jsonl','frames.jsonl'):
   path=self.run/filename;raw=path.read_bytes();_,guard=L.prepare(self.run,10)
   path.write_bytes(b'X'+raw[1:])
   with self.assertRaises(ValueError):guard.check()
   path.write_bytes(raw);_,guard=L.prepare(self.run,10);path.write_bytes(raw[:-1])
   with self.assertRaises(ValueError):guard.check()
   path.write_bytes(raw);_,guard=L.prepare(self.run,10);stage=self.run/'replacement';stage.write_bytes(raw);stage.replace(path)
   with self.assertRaises(ValueError):guard.check()
 def test_anchor_sha_and_frame_boundary_rejected(self):
  path=self.run/'0041_NONE_0000041.checkpoint.json';raw=path.read_text();cp=json.loads(raw)
  for key,value in (('ledger_sha256','0'*64),('state_sha256','0'*64),('core_frame',42)):
   changed={**cp,key:value};path.write_text(json.dumps(changed))
   with self.assertRaises(ValueError):L.prepare(self.run,10)
  path.write_text(raw)
 def test_past_source_endpoint_checkpoint_changes_rejected(self):
  plans,guard=L.prepare(self.run,10)
  for path in (self.frame,self.run/'0021_NONE_0000021.png',self.run/'0021_NONE_0000021.checkpoint.json'):
   raw=path.read_bytes();path.write_bytes(raw+b'changed')
   with self.assertRaises(ValueError):guard.check_plan(plans[0])
   path.write_bytes(raw)
   plans,guard=L.prepare(self.run,10)
 def test_open_source_refused(self):
  plans,guard=L.prepare(self.run,10)
  with patch.object(L,'unused',side_effect=ValueError('writer')):
   with self.assertRaises(ValueError):L.batch_guard(plans,guard)
 def test_existing_exit_resume_are_fixed(self):
  for name in ('exit.json','resume.checkpoint.json'):
   plans,guard=L.prepare(self.run,10);p=self.run/name;raw=p.read_bytes();p.write_bytes(raw+b' ')
   with self.assertRaises(ValueError):guard.check()
   p.write_bytes(raw)
 def test_new_reference_at_batch_boundary_preserved(self):
  work=self.root/'temp/late_reference';name='0021_NONE_0000021_sheet.png'
  argv=['prune','--run',str(self.run),'--work',str(work),'--committed-prefix','--guard-batch-size','200','--apply']
  with patch.object(sys,'argv',argv),patch.object(L,'unused'),patch.object(P,'reference_names',side_effect=[set(),{name}]):P.main()
  self.assertTrue((self.run/name).exists())
 def test_apply_keeps_failed_exit_and_all_evidence(self):
  work=self.root/'temp/prune';before={p:p.read_bytes() for p in (self.run/'exit.json',self.frame,self.run/'frames.jsonl',self.run/'actions.jsonl',self.run/'0021_NONE_0000021.png')}
  argv=['prune','--run',str(self.run),'--work',str(work),'--committed-prefix','--guard-batch-size','200','--apply']
  with patch.object(sys,'argv',argv),patch.object(L,'unused'):P.main()
  self.assertFalse((self.run/'0021_NONE_0000021_sheet.png').exists())
  self.assertTrue((self.run/'0020_NONE_0000020_sheet.png').exists());self.assertTrue((self.run/'0022_NONE_0000022_sheet.png').exists())
  for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
  from playthrough_capture import verify_parent
  anchor=self.run/'0041_NONE_0000041.checkpoint.json'
  verify_parent(anchor,json.loads(anchor.read_text()))
  record=json.loads((work/'receipts.jsonl').read_text().splitlines()[-1]);P.restore_sheet(record,self.run/'0021_NONE_0000021_sheet.png')
  self.assertTrue((self.run/'0021_NONE_0000021_sheet.png').exists())
