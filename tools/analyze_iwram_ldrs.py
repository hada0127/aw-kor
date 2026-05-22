import capstone
import struct

data = open('/tmp/iwram_full.bin', 'rb').read()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.detail = True

for insn in md.disasm(data[0xe0:], 0x030065e0):
    if insn.mnemonic == 'ldr' and '[pc,' in insn.op_str:
        try:
            off = int(insn.op_str.split('#')[1].split(']')[0], 16)
            target_addr = (insn.address + 4) & ~3
            data_off = target_addr + off - 0x03006500
            val = struct.unpack('<I', data[data_off : data_off+4])[0]
            print(f"0x{insn.address:x}: {insn.mnemonic} {insn.op_str} -> 0x{val:08x}")
        except:
            pass
