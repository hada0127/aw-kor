"""Cold-boot natural Part 1 menu routes with compact-help read watches."""
import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from qa_visual_regions import MGBADriver,KEYS
ROM=ROOT/'output/game_wars_korean_full.gba'
SHA='7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'
ap=argparse.ArgumentParser();ap.add_argument('route',choices=['F_help_sweep','F7BE_b2']);args=ap.parse_args()
SOURCE=ROOT/'temp/release_C/rebind1/help'/args.route
OUT=ROOT/'temp/release_C/verify2_part1_help'/args.route
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(ROM)==SHA
OUT.mkdir(parents=True,exist_ok=True)
save=OUT/'game.sav';shutil.copyfile(SOURCE/'game.sav',save)
assert sha(save)==json.loads((SOURCE/'game_save.json').read_text())['save_sha256']
rom=ROM.read_bytes(); codes=(0,5,6,16,17,18,19)
targets={code:struct.unpack_from('<I',rom,0xDFAAB8+4*code)[0]+2 for code in codes}
control=0x08DFA6E2 if args.route=='F_help_sweep' else struct.unpack_from('<I',rom,0xDFAAB8+4*9)[0]+2
steps=[json.loads(s) for s in (SOURCE/'actions.jsonl').read_text().splitlines()]
steps=[s for s in steps if s.get('status')=='started' and s['segment']>=2]
log=OUT/'watch.log';log.unlink(missing_ok=True)
driver=MGBADriver(ROM,OUT,ROOT/'temp/mgbah_linux',save)
events=[]
def tally():
    rows=log.read_text().splitlines() if log.exists() else []
    return {'control_reads':sum(f'addr={control:08X}' in r or f'addr={control+1:08X}' in r for r in rows),
            'target_reads':{str(code):sum(f'addr={p:08X}' in r or f'addr={p+1:08X}' in r for r in rows)
                            for code,p in targets.items()}}
try:
    first=True
    for p in list(targets.values())+[control]:
        dest=str(log) if first else 'KEEP';first=False
        reply=driver.cmd(f'watchaddr {p:08X} 2 r {dest}')
        assert reply==f'OK watchaddr {p:08X} len=2 set=2',reply
    driver.frames(1)
    for row in steps:
        key=row['key']
        if key!='NONE':driver.cmd(f'keys {KEYS[key]}');driver.frames(row['hold_frames'])
        driver.cmd('keys 0');driver.frames(row['release_frames'])
        if row['segment'] in ((16,33,77) if args.route=='F_help_sweep' else (8,14)):
            name=f's{row["segment"]:02}';driver.shot(name)
            events.append({'segment':row['segment'], 'core_frame':int(driver.cmd('framecounter').split()[-1]),
                           'screenshot':str((OUT/f'{name}.png').relative_to(ROOT)),
                           'screenshot_sha256':sha(OUT/f'{name}.png'),**tally()})
finally:driver.close()
(OUT/'receipt.json').write_text(json.dumps({'rom_sha256':SHA,'source_save':str((SOURCE/'game.sav').relative_to(ROOT)),
    'source_save_sha256':sha(SOURCE/'game.sav'),'cheat_tainted':True,
    'watch_addresses':{str(k):f'0x{v:08X}' for k,v in targets.items()},
    'control_address':f'0x{control:08X}',
    'emulator_exit_code':driver.proc.returncode,'watch_log_sha256':sha(log),
    'events':events},indent=2)+'\n')
print(json.dumps({'exit':driver.proc.returncode,'events':events}))
