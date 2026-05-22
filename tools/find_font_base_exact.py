import struct
data = open('original/Game Boy Wars Advance 1+2 (Japan).gba', 'rb').read()
for i in range(len(data)-4):
    val = struct.unpack('<I', data[i:i+4])[0]
    if val == 0x08B98000:
        print(f"Found 0x{val:08x} at 0x{i:x}")
