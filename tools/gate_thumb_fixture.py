"""Execute the installed final-ROM gate on Unicorn's ARM7TDMI-compatible Thumb core."""
import hashlib
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

ROM_PATH = Path('output/game_wars_korean_gate_r3_0126.gba')
ROM = ROM_PATH.read_bytes()
SHA = hashlib.sha256(ROM).hexdigest()
assert SHA == '4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d'
POOL, SOURCE, CELL, DEST = 0x03000E00, 0x08D82474, 0x02012E0A, 0x02012D44
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
        UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
        UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC]
SP = 0x03007F00
PARENTS = (0x03000F20, 0x03000EC0, 0x030010A0,
           0x03001040, 0x03001220, 0x03001280)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else 'temp/gate_thumb_results.json')
results = []

def execute(name, entry, stop, *, pool=POOL, source=SOURCE, cell=CELL+4,
            col=2, owner=0, dst=DEST, post=None, check='accept',
            native_target=None):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    u.mem_map(0x08000000, 0x01000000)
    u.mem_write(0x08000000, ROM)
    u.mem_map(0x02000000, 0x40000)
    u.mem_map(0x03000000, 0x8000)
    u.mem_map(0x06000000, 0x18000)
    initial = [0xA0000000 + i*0x10101 for i in range(16)]
    initial[0] = pool if entry == 0x08F31E32 else 0xA0000000
    initial[1] = col
    initial[2] = 0 if check == 'return' else 0x22222222
    initial[3] = 0 if check == 'return' else 0x33333333
    initial[5] = source
    initial[6] = cell
    initial[7] = pool if entry == 0x08F31E00 else 0x77777777
    initial[13] = SP
    initial[14] = 0x08001235
    initial[15] = entry
    for i, reg in enumerate(REGS):
        u.reg_write(reg, initial[i])
    saved_frame=(0x44444444,source,cell,pool)
    u.mem_write(SP, struct.pack('<4I', *saved_frame))
    if POOL <= pool < 0x03001D00 and (pool-POOL) % 0x60 == 0:
        u.mem_write(pool, struct.pack('<I', owner))
        u.mem_write(pool+0x20, struct.pack('<I', source+2 if post is None else post))
        u.mem_write(pool+0x28, struct.pack('<I', dst))
    writes, reads, pcs = [], [], []
    def on_code(uc, address, size, _):
        pcs.append(address)
        if address in stop:
            uc.emu_stop()
        elif len(pcs) > 10000:
            raise AssertionError(f'{name}: instruction bound')
    def on_write(uc, access, address, size, value, _):
        writes.append((address,size,value))
    def on_read(uc, access, address, size, value, _):
        reads.append((address,size))
    u.hook_add(UC_HOOK_CODE, on_code)
    u.hook_add(UC_HOOK_MEM_WRITE, on_write)
    u.hook_add(UC_HOOK_MEM_READ, on_read)
    u.emu_start(entry | 1, 0, count=10001)
    ended = u.reg_read(UC_ARM_REG_PC)
    assert ended in stop, (name, hex(ended), [hex(p) for p in pcs[-8:]])
    after = [u.reg_read(r) for r in REGS]
    assert after[13] == SP+(16 if check == 'return' else 0) and after[14] == initial[14], (name, 'SP/LR', after[13:15])
    for i in ((8,9,10,11,12) if check in ('full','return') else (1,2,3,5,8,9,10,11,12)):
        assert after[i] == initial[i], (name, f'r{i}', hex(after[i]), hex(initial[i]))
    if check not in ('full','return'):
        assert after[2:4] == initial[2:4], name
    if entry == 0x08F31E00 and check not in ('full','return'):
        assert after[4] == initial[4] and after[7] == initial[7], (name,'source r4/r7')
    if check == 'reject':
        assert ended == 0x08F306DC, (name, hex(ended))
        assert all(SP-16 <= a < SP for a,_,_ in writes), (name, writes)
        assert after[6] == initial[6], (name, 'r6 changed')
    elif check == 'source':
        assert ended == 0x08F3063A and after[6] == initial[6]+4, (name,hex(ended))
        assert all(SP-16 <= a < SP for a,_,_ in writes), (name,writes)
    elif check == 'row':
        assert ended == 0x08F3068E, (name,hex(ended))
        assert after[6] == initial[6], (name,'row r6')
        row = ((cell-CELL) >> 7)
        assert after[0] == 0xD8+row*8+col, (name,hex(after[0]))
        expected = {cell,cell+0x40} | (set() if row in (2,4) else {cell-4,cell+0x3c})
        observed = {a for a,_,_ in writes if not SP-16 <= a < SP}
        assert observed == expected, (name,observed,expected)
        assert all(size == 2 for a,size,_ in writes if a in observed), name
    elif check == 'native':
        assert ended == native_target, (name,hex(ended))
        assert all(SP-16 <= a < SP for a,_,_ in writes), (name,writes)
    elif check == 'full':
        assert ended == 0x08F306DC, (name,hex(ended))
        assert 0x08F3063A in pcs and 0x08F31E32 in pcs and 0x08F3068E in pcs, (name,'continuations')
        assert any(0x02000000 <= a < 0x02040000 for a,_,_ in writes), (name,'tilemap')
        assert any(0x06000000 <= a < 0x06018000 for a,_,_ in writes), (name,'VRAM')
    elif check == 'return':
        assert ended == 0x08F306DE, (name,hex(ended))
        assert after[4:8] == list(saved_frame), (name,'outer r4-r7',after[4:8])
    if pool < POOL or pool >= 0x03001D00 or (pool-POOL) % 0x60:
        assert not any(pool <= a < pool+0x30 for a,_ in reads), (name,'invalid pool read')
    results.append(dict(name=name, entry=hex(entry), stop=hex(ended),
                        instructions=len(pcs)-1, writes=[hex(a) for a,_,_ in writes],
                        nonstack_writes=[hex(a) for a,_,_ in writes if not SP-16 <= a < SP],
                        r0=hex(after[0]), sp=hex(after[13]), lr=hex(after[14])))

for i in range(40):
    p = POOL+i*0x60
    execute(f'source_slot_{i}',0x08F31E00,{0x08F3063A},pool=p,cell=CELL,check='source')
    execute(f'row_slot_{i}',0x08F31E32,{0x08F3068E},pool=p,check='row')
for i,p in enumerate(PARENTS):
    execute(f'parent_{i}',0x08F31E32,{0x08F3068E},pool=p,check='row')
for p in (POOL-0x60,POOL-1,0x03000DA0,POOL+1,POOL+0x20,
          POOL+0x40,0x03001D00,0x03001D60,0x02000E00,0xFFFFFFFF):
    execute(f'invalid_source_{p:08x}',0x08F31E00,{0x08F306DC},pool=p,cell=CELL,check='reject')
    execute(f'invalid_row_{p:08x}',0x08F31E32,{0x08F306DC},pool=p,check='reject')
for name,kw in [('owner',{'owner':1}),('dst_adjacent',{'dst':DEST+2}),
                ('dst_page',{'dst':0x02022D44}),('post_same',{'post':SOURCE}),
                ('post_plus4',{'post':SOURCE+4}),('source_below',{'source':0x08D8244B}),
                ('source_above',{'source':0x08D824AE})]:
    execute('guard_source_'+name,0x08F31E00,{0x08F306DC},cell=CELL,check='reject',**kw)
    if not name.startswith('source_'):
        execute('guard_row_'+name,0x08F31E32,{0x08F306DC},check='reject',**kw)
for row in (0,4):
    for col in (2,7):
        execute(f'boundary_r{row}_c{col}',0x08F31E32,{0x08F3068E},
                cell=CELL+row*0x80+2*col, col=col,check='row')
for name,cell,col in [('underflow',CELL-2,2),('past_row',CELL+5*0x80+4,2),
                      ('col_low',CELL+2,1),('col_high',CELL+16,8),
                      ('odd',CELL+5,2),('half_row',CELL+0x44,2)]:
    execute(name,0x08F31E32,{0x08F306DC},cell=cell,col=col,check='reject')
for i,p in enumerate(PARENTS):
    target = 0x08F307D4 if p in (0x03001040,0x03000EC0,0x030010A0) else 0x08F307A8
    execute(f'native_parent_{i}',0x08F31E32,{0x08F307A8,0x08F307D4},
            pool=p,source=0x08D82500,check='native',native_target=target)
for p in (POOL,0x03000F80,0x03000FE0,POOL+39*0x60):
    execute(f'full_lookup_row_{p:08x}',0x08F31E00,{0x08F306DC},
            pool=p,cell=CELL,check='full')
execute('return_after_row',0x08F31E32,{0x08F306DE},check='return')
execute('return_after_reject',0x08F31E32,{0x08F306DE},owner=1,check='return')
OUT.write_text(json.dumps({'rom_sha':SHA,'unicorn':__import__('unicorn').__version__,
                           'cases':results},indent=2))
print(f'PASS {len(results)} real Thumb cases, ROM {SHA}, evidence {OUT}')
