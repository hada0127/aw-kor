"""Cold-boot Part 1 suspended VS battle, attempt native save confirmation."""
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from qa_visual_regions import MGBADriver, KEYS

ROM = ROOT / 'output/game_wars_korean_full.gba'
SHA = '7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a'
SOURCE = ROOT / 'temp/release_C/rebind1/help/F7BE_b2'
OUT = ROOT / 'temp/release_C/verify2_compact_part1_save'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert sha(ROM) == SHA
OUT.mkdir(parents=True, exist_ok=True)
save = OUT / 'game.sav'
shutil.copyfile(SOURCE / 'game.sav', save)
assert sha(save) == json.loads((SOURCE / 'game_save.json').read_text())['save_sha256']
rom = ROM.read_bytes()
control = struct.unpack_from('<I', rom, 0xDFAAB8 + 9 * 4)[0] + 2
steps = [json.loads(s) for s in (SOURCE / 'actions.jsonl').read_text().splitlines()]
steps = [s for s in steps if s.get('status') == 'started' and s['segment'] >= 2]
log = OUT / 'watch.log'
log.unlink(missing_ok=True)
driver = MGBADriver(ROM, OUT, ROOT / 'temp/mgbah_linux', save)
events = []

def capture(name):
    driver.shot(name)
    rows = log.read_text().splitlines() if log.exists() else []
    events.append({'name': name,
                   'core_frame': int(driver.cmd('framecounter').split()[-1]),
                   'screenshot_sha256': sha(OUT / (name + '.png')),
                   'target_reads': sum(any(f'addr={a:08X}' in row for a in range(0x08804FC8, 0x08804FD0)) for row in rows),
                   'control_reads': sum(f'addr={control:08X}' in row or f'addr={control + 1:08X}' in row for row in rows)})

def press(key, wait=45):
    driver.cmd(f'keys {KEYS[key]}')
    driver.frames(3)
    driver.cmd('keys 0')
    driver.frames(wait)

try:
    assert driver.cmd(f'watchaddr 08804FC8 8 r {log}') == 'OK watchaddr 08804FC8 len=8 set=8'
    assert driver.cmd(f'watchaddr {control:08X} 2 r KEEP') == f'OK watchaddr {control:08X} len=2 set=2'
    driver.frames(1)
    for step in steps:
        if step['key'] != 'NONE':
            driver.cmd(f'keys {KEYS[step["key"]]}')
            driver.frames(step['hold_frames'])
        driver.cmd('keys 0')
        driver.frames(step['release_frames'])
    capture('vs_continue')
    press('A', 600)
    capture('battle_entry')
    press('SELECT')
    capture('battle_select')
    for index, key in enumerate(['DOWN', 'DOWN', 'A'], 1):
        press(key, 90)
        capture(f'save_step_{index:02}_{key.lower()}')
finally:
    driver.close()

(OUT / 'receipt.json').write_text(json.dumps({
    'rom_sha256': SHA,
    'source_save': str((SOURCE / 'game.sav').relative_to(ROOT)),
    'source_save_sha256': sha(SOURCE / 'game.sav'),
    'cheat_tainted': True,
    'control_address': f'0x{control:08X}',
    'target_range': '0x08804FC8..0x08804FCF',
    'emulator_exit_code': driver.proc.returncode,
    'watch_log_sha256': sha(log),
    'events': events,
}, indent=2) + '\n')
print(json.dumps({'exit': driver.proc.returncode, 'events': events}))
