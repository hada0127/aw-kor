import sys,json,contextlib,io,collections
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
import qa_text_fit as Q
records=[]
def trace(f,event,arg):
 if f.f_code.co_name=='check_text' and f.f_code.co_filename==Q.__file__:
  if event=='return':
   d=f.f_locals
   records.append({k:d.get(k) for k in ('a','ko','ja','slot_override','level')} | {'enc':None if d.get('enc') is None else d['enc'].hex()})
  return trace
buf=io.StringIO();sys.settrace(trace)
try:
 with contextlib.redirect_stdout(buf): rc=Q.main([])
finally: sys.settrace(None)
Path('temp/residual_20261024/trace.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
print(buf.getvalue()); print('rc',rc)
for r in records:
 if r['level'] and 6<=r['level']<=12: print(hex(r['a']),r['level'],r['ko'])

sys.exit(rc)
