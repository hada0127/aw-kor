"""VERIFY-2: cold-boot saved Part 1 shop, watch compact row through buy confirmation."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from qa_visual_regions import MGBADriver, KEYS

ROM = ROOT / 'output/game_wars_korean_full.gba'
OUT = ROOT / 'temp/release_C/verify2_compact_shop'
SOURCE = ROOT / 'temp/release_C/rebind1/help/F_help_sweep'
SHA = '7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_counts(path):
    rows = path.read_text().splitlines() if path.exists() else []
    return {'watch_lines': len(rows),
            'compact_row_reads': sum('addr=08804FC' in r for r in rows),
            'shop_list_control_reads': sum('addr=08DF8B6A' in r or 'addr=08DF8B6B' in r for r in rows)}

assert sha(ROM) == SHA
OUT.mkdir(exist_ok=True)
save = OUT / 'game.sav'
shutil.copyfile(SOURCE / 'game.sav', save)
assert sha(save) == json.loads((SOURCE / 'game_save.json').read_text())['save_sha256']
steps = [json.loads(line) for line in (SOURCE / 'actions.jsonl').read_text().splitlines()]
steps = [r for r in steps if r.get('status') == 'started' and 2 <= r['segment'] <= 16]
events = []
log = OUT / 'watch.log'
log.unlink(missing_ok=True)
driver = MGBADriver(ROM, OUT, ROOT / 'temp/mgbah_linux', save)
try:
    for addr, size in [('08804FC8', 8), ('08DF8B6A', 2)]:
        response = driver.cmd(f'watchaddr {addr} {size} r {log}')
        assert response == f'OK watchaddr {addr} len={size} set={size}', response
    driver.frames(1)
    for r in steps:
        key = r['key']
        if key != 'NONE':
            driver.cmd(f'keys {KEYS[key]}')
            driver.frames(r['hold_frames'])
        driver.cmd('keys 0')
        driver.frames(r['release_frames'])
        events.append({'segment':r['segment'], 'key':key,
                       'core_frame':int(driver.cmd('framecounter').split()[-1]),
                       **read_counts(log)})
    driver.shot('shop_menu')
    for i, key in enumerate(['A', 'NONE', 'A', 'NONE', 'DOWN', 'NONE', 'A', 'NONE'] + ['A'] * 25, 1):
        if key != 'NONE':
            driver.cmd(f'keys {KEYS[key]}')
            driver.frames(1)
        driver.cmd('keys 0')
        driver.frames(90)
        driver.shot(f'step{i:02}_{key}')
        events.append({'step':i,'key':key,
                       'core_frame':int(driver.cmd('framecounter').split()[-1]),
                       **read_counts(log)})
finally:
    driver.close()
(OUT / 'events.json').write_text(json.dumps({'rom_sha256':SHA,
    'source_save':str((SOURCE/'game.sav').relative_to(ROOT)),
    'source_save_sha256':sha(SOURCE/'game.sav'), 'steps':events,
    'watch_log_sha256':sha(log),
    'emulator_exit_code':driver.proc.returncode},indent=2)+'\n')
print(json.dumps({'watch':log.read_text().splitlines(), 'events':events[-8:]},ensure_ascii=False))
