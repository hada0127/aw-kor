"""Cold-boot Part 1 communication-menu and link-client candidate read probe."""
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
SOURCE = ROOT / 'temp/release_C/rebind1/help/F_help_sweep'
OUT = ROOT / 'temp/release_C/verify2_compact_link'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert sha(ROM) == SHA
OUT.mkdir(parents=True, exist_ok=True)
save = OUT / 'game.sav'
shutil.copyfile(SOURCE / 'game.sav', save)
assert sha(save) == json.loads((SOURCE / 'game_save.json').read_text())['save_sha256']
rom = ROM.read_bytes()
controls = {code: struct.unpack_from('<I', rom, 0xDFAAB8 + code * 4)[0] + 2 for code in (20, 21, 22, 23)}
steps = [json.loads(s) for s in (SOURCE / 'actions.jsonl').read_text().splitlines()]
steps = [s for s in steps if s.get('status') == 'started' and 2 <= s['segment'] <= 58]
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
                   'control_reads': {str(code): sum(f'addr={p:08X}' in row or f'addr={p + 1:08X}' in row for row in rows)
                                     for code, p in controls.items()}})

def press(key, frames=2):
    driver.cmd(f'keys {KEYS[key]}')
    driver.frames(frames)
    driver.cmd('keys 0')
    driver.frames(45)

try:
    assert driver.cmd(f'watchaddr 08804FC8 8 r {log}') == 'OK watchaddr 08804FC8 len=8 set=8'
    for control in controls.values():
        assert driver.cmd(f'watchaddr {control:08X} 2 r KEEP') == f'OK watchaddr {control:08X} len=2 set=2'
    driver.frames(1)
    for step in steps:
        if step['key'] != 'NONE':
            driver.cmd(f'keys {KEYS[step["key"]]}')
            driver.frames(step['hold_frames'])
        driver.cmd('keys 0')
        driver.frames(step['release_frames'])
    capture('communication_menu')
    for index, key in enumerate(['A', 'A', 'DOWN', 'A', 'B', 'DOWN', 'A'], 1):
        press(key)
        capture(f'link_step_{index:02}_{key.lower()}')
finally:
    driver.close()

(OUT / 'receipt.json').write_text(json.dumps({
    'rom_sha256': SHA,
    'source_save': str((SOURCE / 'game.sav').relative_to(ROOT)),
    'source_save_sha256': sha(SOURCE / 'game.sav'),
    'cheat_tainted': True,
    'control_addresses': {str(code): f'0x{p:08X}' for code, p in controls.items()},
    'target_range': '0x08804FC8..0x08804FCF',
    'emulator_exit_code': driver.proc.returncode,
    'watch_log_sha256': sha(log),
    'events': events,
}, indent=2) + '\n')
print(json.dumps({'exit': driver.proc.returncode, 'events': events}))
