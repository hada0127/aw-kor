import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from qa_visual_regions import MGBADriver,KEYS
ROM=ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba'
SOURCE=ROOT/'temp/release_C/rebind1/help/F_help_sweep'
OUT=ROOT/'temp/release_C/verify3/original_shop';OUT.mkdir(exist_ok=True)
save=OUT/'game.sav';shutil.copyfile(SOURCE/'game.sav',save)
d=MGBADriver(ROM,OUT,ROOT/'temp/mgbah_linux',save)
try:
 steps=[json.loads(x) for x in (SOURCE/'actions.jsonl').read_text().splitlines()]
 for r in steps:
  if r.get('status')!='started' or not 2<=r['segment']<=16:continue
  if r['key']!='NONE':d.cmd(f'keys {KEYS[r["key"]]}');d.frames(r['hold_frames'])
  d.cmd('keys 0');d.frames(r['release_frames'])
 for key in ['A','NONE','A','NONE','DOWN','NONE','A','NONE']+['A']*10:
  if key!='NONE':d.cmd(f'keys {KEYS[key]}');d.frames(1)
  d.cmd('keys 0');d.frames(90)
 d.shot('shop_list')
finally:d.close()
print(json.dumps({'rom_sha256':hashlib.sha256(ROM.read_bytes()).hexdigest(),'source_save_sha256':hashlib.sha256((SOURCE/'game.sav').read_bytes()).hexdigest(),'emulator_exit_code':d.proc.returncode,'frame_sha256':hashlib.sha256((OUT/'shop_list.png').read_bytes()).hexdigest()}))
