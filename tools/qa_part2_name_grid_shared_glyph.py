"""Check that the final ROM preserves the Part 2 dialogue dash picture."""
import argparse
import hashlib
from pathlib import Path


DASH_PIXELS_OFFSET = 0x809CD6
DASH_PIXELS_SIZE = 64
# SHA-256 of these 64 bytes in the b44 canonical ROM (1ac68443d8fa...).
B44_DASH_SHA256 = 'be419dc0b96ddc2fa1d67385f46909c1ea950eafaeba5fa59816cde935bc2bba'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', type=Path)
    args = parser.parse_args()
    with args.rom.open('rb') as handle:
        handle.seek(DASH_PIXELS_OFFSET)
        pixels = handle.read(DASH_PIXELS_SIZE)
    digest = hashlib.sha256(pixels).hexdigest()
    if digest != B44_DASH_SHA256:
        raise SystemExit(f'FAIL shared Part 2 dash 0x815B pixels: {digest}')
    print(f'PASS shared Part 2 dash 0x815B pixels: {digest}')


if __name__ == '__main__':
    main()
