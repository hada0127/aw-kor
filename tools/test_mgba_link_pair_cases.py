import argparse, ctypes, json, os, selectors, subprocess, time
from pathlib import Path
class Header(ctypes.Structure):
    _fields_=[('magic',ctypes.c_char*8),('version',ctypes.c_uint32),('size',ctypes.c_uint32),('state_size',ctypes.c_uint64*2),('state_hash',ctypes.c_uint64*2),('base',ctypes.c_int64*2),('tick_left',ctypes.c_int32*2),('xfer_left',ctypes.c_int32),('linked',ctypes.c_int32),('xfer_active',ctypes.c_int32),('xfer_mode',ctypes.c_int32),('node_mode',(ctypes.c_int32*2)*2),('siocnt',ctypes.c_uint16*2),('rcnt',ctypes.c_uint16*2),('keys_active',ctypes.c_uint16*2),('sio_data',(ctypes.c_uint16*6)*2),('multi',ctypes.c_uint16*4),('normal',ctypes.c_uint32*2),('multi_count',ctypes.c_uint64),('normal_count',ctypes.c_uint64),('header_hash',ctypes.c_uint64)]
def hash64(b):
 h=14695981039346656037
 for x in b:h=((h^x)*1099511628211)&((1<<64)-1)
 return h
p=argparse.ArgumentParser();p.add_argument('--harness',required=True);p.add_argument('--rom',required=True);p.add_argument('--bios',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
for required in (a.harness,a.rom,a.bios):
 if not Path(required).is_file():p.error(f'missing prerequisite: {required}')
if not str(a.out.resolve()).startswith(str((Path(__file__).resolve().parents[1]/'temp').resolve())+os.sep):p.error('--out must be under temp/')
err=(a.out/'stderr.log').open('w')
save_dir=Path(__file__).resolve().parents[1]/'temp'
save_source=a.out/'host_source.sav'
save_source.write_bytes(bytes([0x31])*65536)
old_saves=set(save_dir.glob('save_probe_*'))
proc=subprocess.Popen([a.harness,'--bios',a.bios,'--host-skip-bios',a.rom,'-',str(a.out/'emulator.log'),str(save_source)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);pending=bytearray()
log=[]
def send(s):
 proc.stdin.write((s+'\n').encode());proc.stdin.flush();deadline=time.monotonic()+30
 while b'\n' not in pending:
  remaining=deadline-time.monotonic()
  if remaining<=0 or not selector.select(max(0,remaining)):
   log.append((s,'<timeout>'));raise TimeoutError(s)
  chunk=os.read(proc.stdout.fileno(),4096)
  if not chunk:log.append((s,'<eof>'));raise RuntimeError('emulator exited')
  pending.extend(chunk)
 raw,_,rest=pending.partition(b'\n');pending[:]=rest;r=raw.decode(errors='replace').strip();log.append((s,r));return r
def pair(name): return str(a.out/(name+'.pair'))
try:
 assert send('frames 2').startswith('OK ')
 private_saves=set(save_dir.glob('save_probe_*'))-old_saves
 assert len(private_saves)==1,private_saves
 private_save=private_saves.pop()
 send('keys 0 1');send('keys 1 2');send('savepair '+pair('held'));send('keys 0 0');send('keys 1 0');assert send('loadpair '+pair('held')).startswith('OK ');held=send('status');assert 'keys=1,2' in held,held
 with private_save.open('r+b') as save:
  save.write(b'\xA5\x5A')
 send(f'dumpmem 0 0E000000 16 {a.out}/sram_before.bin')
 sram_before=(a.out/'sram_before.bin').read_bytes()
 assert sram_before[:2]!=b'11',sram_before
 send('keys 0 16');send('keys 1 32');before=send('status');before_sio=send('sio');before_regs=[send(f'regs {i}') for i in (0,1)];save_before=private_save.read_bytes();send('savepair '+pair('before'))
 for i in (0,1):send(f'shot {i} {a.out}/before_{i}.raw')
 raw=Path(pair('held')).read_bytes();h=Header.from_buffer_copy(raw);n=ctypes.sizeof(Header);p0=raw[n:n+h.state_size[0]];p1=raw[n+h.state_size[0]:]
 # Hash-valid but the client payload is an incompatible host cartridge state.
 h.state_size[1]=len(p0);h.state_hash[1]=hash64(p0);h.header_hash=hash64(bytes(h)[:Header.header_hash.offset]);Path(pair('reject')).write_bytes(bytes(h)+p0+p0)
 rejection=send('loadpair '+pair('reject'));after=send('status');after_sio=send('sio');after_regs=[send(f'regs {i}') for i in (0,1)];send('savepair '+pair('after'))
 assert rejection.startswith('ERR '),rejection
 assert before==after,(before,after)
 assert before_sio==after_sio,(before_sio,after_sio)
 assert before_regs==after_regs,(before_regs,after_regs)
 send(f'dumpmem 0 0E000000 16 {a.out}/sram_after.bin')
 assert (a.out/'sram_after.bin').read_bytes()==sram_before,'mapped SRAM changed'
 assert private_save.read_bytes()==save_before,'file-backed SRAM changed'
 for i in (0,1):
  send(f'shot {i} {a.out}/after_{i}.raw')
  b0=(a.out/f'before_{i}.raw').read_bytes();b1=(a.out/f'after_{i}.raw').read_bytes();assert b0==b1,i
 # Invalid semantic header must be rejected before mutation.
 h.node_mode[0][0]=99;h.header_hash=hash64(bytes(h)[:Header.header_hash.offset]);Path(pair('malformed')).write_bytes(bytes(h)+p0+p0)
 assert send('loadpair '+pair('malformed')).startswith('ERR ')
 assert send('status')==before
 # Pending multiplayer SIO transfer is carried through save/load.
 for i in (0,1):send(f'w16 {i} 04000134 0');send(f'w16 {i} 04000128 2003')
 send('w16 0 04000128 2083');m=send('savepair '+pair('multi'));assert 'xfer_active=1' in m,m
 send('frames 2');multi_ref=send('status');assert 'xfer_active=1' in send('loadpair '+pair('multi'));send('frames 2');assert send('status')==multi_ref
 # Pending Normal transfer, with both nodes switched by SIOCNT.
 for i in (0,1):send(f'w16 {i} 04000128 0000')
 send('w16 1 04000128 1080');send('w16 0 04000128 1081');n=send('savepair '+pair('normal'))
 assert 'xfer_active=1' in n,n
 send('frames 2');normal_ref=send('status');assert 'xfer_active=1' in send('loadpair '+pair('normal'));send('frames 2');assert send('status')==normal_ref
 send('quit');exit=proc.wait(timeout=5);assert exit==0,exit
 assert not private_save.exists(),'private save clone survived normal exit'
 selector.close();proc.stdin.close();proc.stdout.close()
 proc=subprocess.Popen([a.harness,'--bios',a.bios,'--host-skip-bios','--rom2',a.rom,a.rom,'-',str(a.out/'emulator_rom2.log')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
 selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);pending=bytearray()
 assert send('frames 2').startswith('OK ')
 two_before=send('status');assert send('savepair '+pair('rom2')).startswith('OK ')
 send('frames 2');assert send('loadpair '+pair('rom2')).startswith('OK ')
 two_after=send('status');assert two_after==two_before,(two_before,two_after)
 send('quit');rom2_exit=proc.wait(timeout=5);assert rom2_exit==0,rom2_exit
 result={'exit_code':exit,'rom2_exit_code':rom2_exit,'rom2_restored':two_after==two_before,'held':held,'rejection':rejection,'rollback_unchanged':True,'sram_before':sram_before.hex(),'multi':m,'normal':n,'transcript':log}
except BaseException as e:
 result={'error':repr(e),'transcript':log};raise
finally:
 if proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=3)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 selector.close();err.close()
 if proc.stdin:proc.stdin.close()
 if proc.stdout:proc.stdout.close()
 (a.out/'cases.json').write_text(json.dumps(result,indent=2)+'\n')
