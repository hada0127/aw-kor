"""Cold-boot b32r5 name confirm with compact-row and live-choice read watches."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from qa_visual_regions import MGBADriver

ROM = ROOT / 'output/game_wars_korean_full.gba'
OUT = ROOT / 'temp/release_C/verify2_compact_name'
SHA = '7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def counts(path):
    rows = path.read_text().splitlines() if path.exists() else []
    return {'target_reads':sum('addr=08804FC' in r for r in rows),
            'live_choice_reads':sum('addr=08D835B' in r for r in rows),
            'watch_lines':len(rows)}

assert sha(ROM)==SHA
OUT.mkdir(parents=True,exist_ok=True)
log=OUT/'watch.log';log.unlink(missing_ok=True)
actions=[
    ('frames',600),('keys',1),('frames',2),('keys',0),('frames',60),
    ('frames',60),('keys',1),('frames',2),('keys',0),('frames',90),
    ('frames',120),('frames',120),('frames',120),('frames',600),
    ('keys',1),('frames',2),('keys',0),('frames',90),
    ('keys',1),('frames',2),('keys',0),('frames',90),('frames',90),
    ('keys',1),('frames',2),('keys',0),('frames',30),('frames',60),
    ('keys',1),('frames',2),('keys',0),('frames',30),
    ('keys',1),('frames',2),('keys',0),('frames',30),
    ('keys',1),('frames',2),('keys',0),('frames',30),
    ('keys',1),('frames',2),('keys',0),('frames',30),
    ('keys',8),('frames',2),('keys',0),('frames',30),('frames',40),
    ('keys',16),('frames',2),('keys',0),('frames',30),
    ('keys',32),('frames',2),('keys',0),('frames',30),
]
driver=MGBADriver(ROM,OUT,ROOT/'temp/mgbah_linux')
shots=[]
try:
    for addr,size in [('08804FC8',8),('08D835BC',16)]:
        reply=driver.cmd(f'watchaddr {addr} {size} r {log}')
        assert reply==f'OK watchaddr {addr} len={size} set={size}',reply
    frame=0
    for op,value in actions:
        driver.cmd(f'{op} {value}')
        if op=='frames':
            frame+=value
            if frame in (2340,2372,2404):
                driver.shot(f'f{frame}')
                shots.append({'core_frame':frame,'path':str((OUT/f'f{frame}.png').relative_to(ROOT)),
                              'sha256':sha(OUT/f'f{frame}.png'),**counts(log)})
finally:
    driver.close()
(OUT/'receipt.json').write_text(json.dumps({'rom_sha256':SHA,'cold_boot':True,
    'save':None,'emulator_exit_code':driver.proc.returncode,
    'watch_log_sha256':sha(log),'shots':shots},indent=2)+'\n')
print(json.dumps({'exit':driver.proc.returncode,'shots':shots}))
