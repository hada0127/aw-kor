import collections,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
import text_metrics as TM
from renderer_text import renderer_for_address
root=Path('docs/reports/name_grid_2026-10-23/evidence/t4')
recorded=json.loads((root/'analysis/textfit_baseline.json').read_text())
bteam=json.loads((root/'bteam/baseline_retry1_bteam_details.json').read_text())
before=json.loads(Path('temp/residual_20261024/trace_before.json').read_text())
after=json.loads(Path('temp/residual_20261024/trace.json').read_text())
def groups(rows):
 result={}
 for kind,predicate in [('overflow',lambda r:r['enc'] is None),('wider',lambda r:r['enc'] is not None and TM.visual_cells(r['ko'],renderer_for_address(r['a']))>TM.visual_cells(r['ja'],renderer_for_address(r['a']))),('layout_loss',lambda r:r['enc'] is not None and r['level']>=6)]:
  counts=collections.Counter(f"0x{r['a']:06X}" for r in rows if predicate(r))
  result[kind]={'events':sum(counts.values()),'unique_addresses':len(counts),'address_multiplicity':dict(sorted(counts.items()))}
 return result
b,a=groups(before),groups(after)
for kind in ('overflow','wider'):
 assert b[kind]['address_multiplicity']==recorded[kind]['set_with_multiplicity']
changes=[]
assert len(before)==len(after)
for x,y in zip(before,after):
 assert (x['a'],x['ko'],x['slot_override'])==(y['a'],y['ko'],y['slot_override'])
 if (x['enc'],x['level'])!=(y['enc'],y['level']):
  changes.append({'address':f"0x{x['a']:06X}",'text':x['ko'],'before_level':x['level'],'before_hex':x['enc'],'after_level':y['level'],'after_hex':y['enc']})
out={'source_revision':'420e61657e5c9fad4307b5cf81940bd79d6a1eae','scope':'source fit calls, not final ROM or runtime','tracked_evidence_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'analysis/textfit_baseline.json',root/'bteam/baseline_retry1_bteam_details.json']},'bteam_recorded':{'events':len(bteam),'unique_addresses':len({r['address'] for r in bteam}),'decisions':dict(collections.Counter(r['decision'] for r in bteam)),'addresses':[r['address'] for r in bteam]},'before':b,'after':a,'changed_fit_calls':changes}
Path('docs/reports/residual_2026-10-24/residual_sets.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{t:(v['events'],v['unique_addresses']) for t,v in d.items()} for k,d in [('before',b),('after',a)]}));print('changed calls',len(changes))
