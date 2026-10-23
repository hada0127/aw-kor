from pathlib import Path
import os,subprocess,shlex,json
R=Path(__file__).resolve().parent
os.environ['TMPDIR']=str(R/'tmp')
def run(args,name):
 print(name,shlex.join(args),flush=True)
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (R/(name+'.log')).write_text(p.stdout)
 with (R/'commands.jsonl').open('a') as f: f.write(json.dumps({'name':name,'command':args,'exit':p.returncode})+'\n')
 print(p.stdout[-2200:], 'EXIT',p.returncode,flush=True)
 if p.returncode: raise SystemExit(p.returncode)
if __name__=='__main__':
 off=['BUILD_QT','BUILD_SDL','BUILD_GL','BUILD_GLES2','BUILD_GLES3','BUILD_STATIC','BUILD_LIBRETRO','BUILD_OPENEMU','BUILD_PERF','BUILD_TEST','BUILD_SUITE','BUILD_CINEMA','BUILD_ROM_TEST','BUILD_EXAMPLE','BUILD_PYTHON','BUILD_DOCGEN','USE_FFMPEG','USE_MINIZIP','USE_LIBZIP','USE_SQLITE3','USE_ELF','USE_LUA','USE_LZMA','USE_DISCORD_RPC','USE_EPOXY','USE_EDITLINE','USE_GDB_STUB']
 run(['cmake','-S',str(R/'mgba-0.10.5'),'-B',str(R/'build'),'-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DCMAKE_BUILD_TYPE=Release','-DSKIP_GIT=ON','-DBUILD_SHARED=ON','-DUSE_DEBUGGERS=ON','-DUSE_PNG=ON','-DUSE_ZLIB=ON',*['-D'+x+'=OFF' for x in off]],'configure')
 run(['nice','-n','10','cmake','--build',str(R/'build'),'--target','mgba','--parallel','2'],'build')
 flags=(R/'build/CMakeFiles/mgba.dir/flags.make').read_text()
 defs=shlex.split(next(x.split('=',1)[1] for x in flags.splitlines() if x.startswith('C_DEFINES =')))
 for src,out in [('mgba_harness.c','mgbah'),('mgba_link_harness.c','mgba_link_harness')]:
  run(['clang','-g',*defs,'-I'+str(R/'build/include'),'-I'+str(R/'mgba-0.10.5/include'),str(R.parents[2]/'tools'/src),'-L'+str(R/'build'),'-lmgba','-Wl,-rpath,@executable_path/build','-o',str(R/out)],'compile-'+out)
