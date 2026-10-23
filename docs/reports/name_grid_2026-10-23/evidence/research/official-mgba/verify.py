from build import R,run
import shlex,re,hashlib,json,subprocess
flags=(R/'build/CMakeFiles/mgba.dir/flags.make').read_text()
def f(k): return shlex.split(next(x.split('=',1)[1] for x in flags.splitlines() if x.startswith(k+' =')))
base=['clang',*f('C_DEFINES')]
run([*base,*f('C_INCLUDES'),*f('C_FLAGS'),'-fno-lto','-S',str(R/'abi_probe.c'),'-o',str(R/'abi-library.s')],'abi-library')
run([*base,'-I'+str(R/'build/include'),'-I'+str(R/'mgba-0.10.5/include'),'-S',str(R/'abi_probe.c'),'-o',str(R/'abi-harness.s')],'abi-harness')
vals=[]
for n in ['abi-library.s','abi-harness.s']:
 s=(R/n).read_text(); vals.append(re.findall(r'\.quad\s+(\d+)',s))
assert vals[0] and vals[0]==vals[1],vals
(R/'abi-values.json').write_text(json.dumps({'fields':['color_t.size','mCore.size','mCore.board','mCore.attachDebugger','mCore.savedataClone','mDebugger.size','mDebuggerEntryInfo.size','GBA.size','GBA.memory','GBA.sio','GBA.timing','GBASIO.size','GBASIODriver.size','mTimingEvent.size'],'library':vals[0],'harness':vals[1],'equal':True},indent=2)+'\n')
print('ABI compile-only constants MATCH',vals[0])
for name,args in [('file',['file',str(R/'build/libmgba.dylib'),str(R/'mgbah'),str(R/'mgba_link_harness')]),('link-library',['otool','-L',str(R/'build/libmgba.dylib')]),('link-single',['otool','-L',str(R/'mgbah')]),('link-dual',['otool','-L',str(R/'mgba_link_harness')]),('rpath',['otool','-l',str(R/'mgbah')]),('symbols',['nm','-gU',str(R/'build/libmgba.dylib')]),('tracked-clean',['git','status','--short','--untracked-files=no']),('memory',['vm_stat'])]: run(args,name)
paths=[R/'mgba-0.10.5.tar.gz',R/'build/libmgba.dylib',R/'mgbah',R/'mgba_link_harness',R.parents[2]/'tools/mgba_harness.c',R.parents[2]/'tools/mgba_link_harness.c']
(R/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p)+'\n' for p in paths))
print((R/'SHA256SUMS').read_text())
