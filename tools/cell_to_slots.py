
import struct

ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
SJIS_TABLE_ADDR = 0x08BE717A
FONT_BASE = 0x08B974D0

def get_sjis_index(sjis_code):
    with open(ROM_PATH, "rb") as f:
        f.seek(SJIS_TABLE_ADDR - 0x08000000)
        # Read a good chunk of the table
        table_data = f.read(10000)
        
        target = struct.pack(">H", sjis_code)
        idx = table_data.find(target)
        if idx == -1:
            return -1
        return idx // 2

def cell_slots(sjis_code):
    """
    Returns the 4 ROM slots for a given SJIS character in the dialogue font.
    """
    idx = get_sjis_index(sjis_code)
    if idx == -1:
        return None
    
    # Page 0 starts at index 9 (character 'ア')
    # If the character is before 'ア', we'll treat it as relative to index 9
    rel_idx = idx - 9
    
    page = rel_idx // 16
    chip = rel_idx % 16
    
    # Formula derived from trace:
    # TopExtra:    Slot 128 + (page+5)*32 + 3 + chip
    # Top:         Slot 128 + page*32 + chip
    # Bottom:      Slot 128 + page*32 + 16 + chip
    # BottomExtra: Slot 128 + (page+5)*32 + 19 + chip
    
    slots = {
        "top_extra": 128 + (page + 5) * 32 + 3 + chip,
        "top":         128 + page * 32 + chip,
        "bottom":      128 + page * 32 + 16 + chip,
        "bot_extra":   128 + (page + 5) * 32 + 19 + chip
    }
    
    return slots

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        code = int(sys.argv[1], 16)
        res = cell_slots(code)
        if res:
            print(f"SJIS 0x{code:04X}:")
            for k, v in res.items():
                addr = FONT_BASE + v * 32
                print(f"  {k:10}: Slot {v:4} (ROM 0x{addr:08X})")
        else:
            print("Character not found in table.")
    else:
        # Test with 'ア' (0x8341)
        res = cell_slots(0x8341)
        print("Test 'ア' (0x8341):", res)
        # Test with 'イ' (0x8343)
        res = cell_slots(0x8343)
        print("Test 'イ' (0x8343):", res)
