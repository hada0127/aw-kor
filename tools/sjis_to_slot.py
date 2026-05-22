import struct
import os

ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
SJIS_TABLE_OFFSET = 0xBE717A
TABLE_SIZE = 8000 # Number of 2-byte entries to check

_cache = None

def _load_table():
    global _cache
    if _cache is not None:
        return _cache
    
    if not os.path.exists(ROM_PATH):
        return {}
        
    _cache = {}
    with open(ROM_PATH, "rb") as f:
        f.seek(SJIS_TABLE_OFFSET)
        data = f.read(TABLE_SIZE * 2)
        for i in range(0, len(data), 2):
            sjis = struct.unpack('>H', data[i:i+2])[0]
            if sjis != 0:
                if sjis not in _cache:
                    _cache[sjis] = i // 2
    return _cache

def sjis_to_slot(sjis_bytes: bytes) -> int:
    """
    Converts 2 SJIS bytes (Big-Endian as in TBL/CSV) to a font slot index.
    Example: sjis_to_slot(b'\\x83\\x41') -> 9
    """
    table = _load_table()
    if len(sjis_bytes) != 2:
        return None
    # Convert Big-Endian bytes to integer
    sjis_val = (sjis_bytes[0] << 8) | sjis_bytes[1]
    return table.get(sjis_val)

if __name__ == "__main__":
    # Self-test
    test_chars = [
        (b'\x83\x41', 9), # ア
        (b'\x83\x73', 95), # ピ
        (b'\x82\x50', 0), # ０
    ]
    
    for sjis, expected in test_chars:
        actual = sjis_to_slot(sjis)
        print(f"SJIS {sjis.hex()} -> Slot {actual} (Expected {expected})")
        if actual != expected:
            print("  MISMATCH!")
