"""Cold-boot Part 2 surrender prompt watch on b32r5."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from qa_visual_regions import MGBADriver,KEYS
ROM=ROOT/'output/game_wars_korean_full.gba'
SOURCE=ROOT/'temp/release_C/rebind1/runs/C_3p_surrender'
OUT=ROOT/'temp/release_C/verify2_compact_part2'
SHA='7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def counts(p):
    rows=p.read_text().splitlines() if p.exists() else []
    return {'target_reads':sum('addr=08804FC' in r for r in rows),
            'live_choice_reads':sum('addr=08A34B6' in r for r in rows),
            'watch_lines':len(rows)}
assert sha(ROM)==SHA
OUT.mkdir(exist_ok=True)
save=OUT/'game.sav';shutil.copyfile(SOURCE/'game.sav',save)
assert sha(save)==json.loads((SOURCE/'game_save.json').read_text())['save_sha256']
steps=[json.loads(s) for s in (SOURCE/'actions.jsonl').read_text().splitlines()]
steps=[r for r in steps if r.get('status')=='started' and r['segment']>=2]
log=OUT/'watch.log';log.unlink(missing_ok=True)
driver=MGBADriver(ROM,OUT,ROOT/'temp/mgbah_linux',save)
shots=[]
try:
    for addr,size in [('08804FC8',8),('08A34B6C',16)]:
        reply=driver.cmd(f'watchaddr {addr} {size} r {log}')
        assert reply==f'OK watchaddr {addr} len={size} set={size}',reply
    driver.frames(1)
    for r in steps:
        key=r['key']
        if key!='NONE':
            driver.cmd(f'keys {KEYS[key]}');driver.frames(r['hold_frames'])
        driver.cmd('keys 0');driver.frames(r['release_frames'])
        if r['segment'] in (29,30,31,32):
            name=f's{r["segment"]:02}'
            driver.shot(name)
            shots.append({'segment':r['segment'], 'core_frame':int(driver.cmd('framecounter').split()[-1]),
                          'path':str((OUT/f'{name}.png').relative_to(ROOT)),
                          'sha256':sha(OUT/f'{name}.png'),**counts(log)})
finally:driver.close()
(OUT/'receipt.json').write_text(json.dumps({'rom_sha256':SHA,'cold_boot':True,
    'source_save':str((SOURCE/'game.sav').relative_to(ROOT)),
    'source_save_sha256':sha(SOURCE/'game.sav'),
    'cheat_tainted':True,'emulator_exit_code':driver.proc.returncode,
    'watch_log_sha256':sha(log),'shots':shots},indent=2)+'\n')
print(json.dumps({'exit':driver.proc.returncode,'shots':shots}))
