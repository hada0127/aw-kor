#!/usr/bin/env python3
"""
PHASE 5-5: ROM Finalization - Update checksum and validate
"""

import sys
import struct
from pathlib import Path


def calculate_gba_checksum(rom_data: bytes, header_offset: int = 0xA0) -> int:
    """Calculate GBA ROM checksum"""
    # GBA checksum is at offset 0xBD (189)
    # It's calculated as: 0 - (sum of bytes 0xA0-0xBC) & 0xFF

    checksum_range = rom_data[header_offset:header_offset+29]  # 0xA0 to 0xBC (29 bytes)
    byte_sum = sum(checksum_range) & 0xFF

    checksum = (0 - byte_sum) & 0xFF
    return checksum


def update_checksum(rom_data: bytearray, header_offset: int = 0xA0) -> int:
    """Update ROM checksum"""
    new_checksum = calculate_gba_checksum(rom_data, header_offset)

    # Set checksum at 0xBD
    checksum_offset = header_offset + 0x1D  # 0xA0 + 0x1D = 0xBD
    rom_data[checksum_offset] = new_checksum

    return new_checksum


def verify_rom_header(rom_data: bytes) -> dict:
    """Verify ROM header information"""
    header_offset = 0xA0

    result = {
        'title': '',
        'game_code': '',
        'maker_code': '',
        'unit_code': '',
        'device_type': '',
        'rom_size': len(rom_data),
        'header_valid': False,
        'errors': []
    }

    try:
        # Title (0xA0-0xAB, 12 bytes)
        title_bytes = rom_data[0xA0:0xAC]
        result['title'] = title_bytes.decode('ascii', errors='ignore').strip('\x00')

        # Game code (0xAC-0xAF, 4 bytes)
        result['game_code'] = rom_data[0xAC:0xB0].decode('ascii', errors='ignore')

        # Maker code (0xB0-0xB1, 2 bytes)
        result['maker_code'] = rom_data[0xB0:0xB2].decode('ascii', errors='ignore')

        # Unit code (0xB2)
        result['unit_code'] = f"0x{rom_data[0xB2]:02X}"

        # Device type (0xB3)
        result['device_type'] = f"0x{rom_data[0xB3]:02X}"

        # Validate
        if 'GBWARS' in result['title']:
            result['header_valid'] = True
        else:
            result['errors'].append(f"Unexpected game title: {result['title']}")

    except Exception as e:
        result['errors'].append(f"Header parse error: {e}")

    return result


def calculate_file_hash(rom_data: bytes) -> str:
    """Calculate simple hash for verification"""
    import hashlib
    sha256 = hashlib.sha256(rom_data).hexdigest()
    return sha256[:16]  # First 16 chars


def main():
    print("="*60)
    print("PHASE 5-5: ROM Finalization")
    print("="*60)

    rom_path = 'output/game_wars_korean_v1.gba'
    output_path = 'output/game_wars_korean_final.gba'

    # Load ROM
    print("\n[Step 1] Loading ROM...")
    rom_file = Path(rom_path)

    if not rom_file.exists():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1

    with open(rom_path, 'rb') as f:
        rom_data = bytearray(f.read())

    print(f"  Loaded: {len(rom_data):,} bytes")
    print(f"  Hash: {calculate_file_hash(rom_data)}")

    # Verify header before changes
    print("\n[Step 2] Verifying ROM header...")
    header_info = verify_rom_header(rom_data)

    print(f"  Title: {header_info['title']}")
    print(f"  Game Code: {header_info['game_code']}")
    print(f"  Maker Code: {header_info['maker_code']}")
    print(f"  Header Valid: {header_info['header_valid']}")

    if not header_info['header_valid']:
        print(f"  WARNING: Header validation failed")
        for err in header_info['errors']:
            print(f"    - {err}")

    # Calculate old checksum
    old_checksum = rom_data[0xBD]
    print(f"\n[Step 3] Checksum update...")
    print(f"  Old checksum: 0x{old_checksum:02X}")

    # Update checksum
    new_checksum = update_checksum(rom_data)
    print(f"  New checksum: 0x{new_checksum:02X}")

    if old_checksum != new_checksum:
        print(f"  Status: UPDATED")
    else:
        print(f"  Status: No change needed")

    # Verify
    calculated_checksum = calculate_gba_checksum(rom_data)
    if rom_data[0xBD] == calculated_checksum:
        print(f"  Verification: PASS")
    else:
        print(f"  Verification: FAIL (calculated: 0x{calculated_checksum:02X})")

    # Save final ROM
    print("\n[Step 4] Saving final ROM...")
    with open(output_path, 'wb') as f:
        f.write(rom_data)

    final_file = Path(output_path)
    file_size_mb = final_file.stat().st_size / 1024 / 1024

    print(f"  Saved: {output_path}")
    print(f"  Size: {final_file.stat().st_size:,} bytes ({file_size_mb:.1f}MB)")
    print(f"  Hash: {calculate_file_hash(rom_data)}")

    # Final verification
    print("\n[Step 5] Final verification...")
    final_header = verify_rom_header(rom_data)

    print(f"  Title: {final_header['title']}")
    print(f"  Header Valid: {final_header['header_valid']}")
    print(f"  ROM Size: {final_header['rom_size']:,} bytes")

    # Summary
    print("\n" + "="*60)
    print("PHASE 5-5: Summary")
    print("="*60)

    if final_header['header_valid'] and rom_data[0xBD] == calculated_checksum:
        print("\n[SUCCESS] ROM finalization complete")
        print(f"  - Checksum updated: 0x{old_checksum:02X} -> 0x{new_checksum:02X}")
        print(f"  - Output: {output_path}")
        print(f"  - Size: {final_file.stat().st_size:,} bytes")
        print("\nNext: PHASE 6 (QA and Testing)")
        return 0
    else:
        print("\n[WARNING] ROM finalization with issues")
        if not final_header['header_valid']:
            print("  - Header validation failed")
        if rom_data[0xBD] != calculated_checksum:
            print(f"  - Checksum mismatch: expected 0x{calculated_checksum:02X}, got 0x{rom_data[0xBD]:02X}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
