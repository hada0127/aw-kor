"""Translate observed campaign CO labels within their native 32x8 slots."""
import hashlib
import struct
from pathlib import Path
from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
BANK = 0xBF2BCC
SOURCE = BANK + 3 * 128
POINTERS = (0xB4E7B8, 0xB6DABC)
SOURCE_SHA256 = '4c78b94d92cb909547c076c2d366e8418b03b3c17b245b62f33fa96d0b580d2d'
TEXT = '호이프'
ACCESSOR = (0xB4E7AC, bytes.fromhex('00060249400c40187047'))
# lsls r0,r0,#24; ldr r1,[pc,#8]; lsrs r0,r0,#17; adds r0,r0,r1; bx lr.
# Runtime evidence: docs/research.md, 2026-09-22 campaign CO labels.
LABELS = (
    ('campaign_hoip', SOURCE, SOURCE_SHA256, TEXT, 1, 3, 5),
    ('campaign_ryo', BANK + 128,
     '9094979fd9125f74f48853e59357e3d0af8a893e1198d5fa64ac1da8e897e3cf', '료', 1, 3, 5),
    ('campaign_max', BANK + 2 * 128,
     'a38d629e8a9cc0a6499a8eafe424d590bc21df3a366a75a8ea799b955c46cbf8', '맥스', 1, 3, 5),
    ('campaign_domino', BANK + 4 * 128,
     '6f14425fa63449e140faf06d8e997db7aa83f32f17eb18e3ae063e05baf76267', '도미노', 1, 3, 5),
    ('campaign_billy', BANK + 5 * 128,
     'a81b739bb903b4dc8a4a44c7c148b8e1eb69bcd9ac4c2629ed07b30a9d557386', '빌리', 1, 3, 5),
    ('battle_ryo', 0xBD0130,
     'bdf717b79d5a5261b425d457c5d850a85a7669ad4e735b5235c5aeadd2373ca4', '료', 1, 4, 15),
    ('battle_max', 0xBD01B0,
     '93c989239416ce1d93d10c013fcf0fb5e07582607d3908e9d7a7d8fec0350708', '맥스', 1, 7, 15),
    # 2026-10-06: remaining Part 1 CO slots (campaign + battle HUD), native IDs; Korean names = CO_NAME_KO.
    ('campaign_catherine', BANK + 0 * 128,
     '2f7beb430d1efb7fff8f4370d95105d8f0e26e5ad5bfd7bf9776ce960b1512d1', '캐서린', 1, 3, 5),
    ('campaign_kikuchiyo', BANK + 6 * 128,
     '684893b024cf669cbf98cd435fb669a0c90fbaa546bfd77e192584e11a9d3089', '키쿠치요', 1, 3, 5),
    ('campaign_asuka', BANK + 7 * 128,
     'c04fa6c1372cebed887591679112c51d3fde1a8d9d91f5089905d04737a669ca', '아스카', 1, 3, 5),
    ('campaign_eagle', BANK + 8 * 128,
     'ae5e440821f500c37a921e9bf31cf570d880699658aa9feac36880305a666221', '이글', 1, 3, 5),
    ('campaign_mop', BANK + 9 * 128,
     '2436198d6d5e36ced89fb3604d9913697b7f301d493daba0f1d929ecf7a397a5', '모프', 1, 3, 5),
    ('campaign_sturm', BANK + 10 * 128,
     '95edc14db065a98da5a6560fbf9ecaa4e8aed515ce47bcecc82f55884d261ebf', '헬보우즈', 1, 3, 5),
    ('campaign_sturm_alt', BANK + 11 * 128,
     '95edc14db065a98da5a6560fbf9ecaa4e8aed515ce47bcecc82f55884d261ebf', '헬보우즈', 1, 3, 5),
    ('battle_domino', 0xBD02B0,
     '20e10bb5ec91d236e8413459300b57d9a6e0cc25c20ace5cb9721f9307b7a084', '도미노', 1, 7, 15),
    ('battle_billy', 0xBD0330,
     'f7eed52726f21795bf77eb9b67210075ff5670262f5659479fa74d1622765d9e', '빌리', 1, 7, 15),
    ('battle_kikuchiyo', 0xBD03B0,
     '3498cc2215fd91bdd2a97752f4caea074b075048698f0d6516d2c73dfa1baba7', '키쿠치요', 1, 7, 15),
    ('battle_asuka', 0xBD0430,
     '8a33dc523b0de93e62f7197b282e5ad83eecfa3e5e469c1c65aa58aaa69217e5', '아스카', 1, 7, 15),
    ('battle_eagle', 0xBD04B0,
     '9434abd389206c5fc9e35a9c6109181c543159ada9e92bb8393947087fe09992', '이글', 1, 7, 15),
    ('battle_mop', 0xBD0530,
     '74189ee08ad8e5f76f3da1b942c3c13f9edadf53082006673e3cbe0e56f62728', '모프', 1, 7, 15),
    ('battle_sturm', 0xBD05B0,
     'e9b2270e7beb8cd8a69f8fc42960dbcbaf0601a9fdf838f75ebc30c196f3bd51', '헬보우즈', 1, 7, 15),
)


def validate_source(original):
    for _, address, digest, *_ in LABELS:
        if hashlib.sha256(original[address:address + 128]).hexdigest() != digest:
            raise AssertionError('campaign CO name source changed')
    for pointer in POINTERS:
        if struct.unpack_from('<I', original, pointer)[0] != BANK + 0x08000000:
            raise AssertionError('campaign CO name bank pointer changed')
    # The native accessor selects a fixed 32x8 slot using (uint8_t)id << 7.
    if original[ACCESSOR[0]:ACCESSOR[0] + len(ACCESSOR[1])] != ACCESSOR[1]:
        raise AssertionError('campaign CO name slot accessor changed')


def render_label(text=TEXT, white=1, shadow=3, outline=5):
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    ink = set()
    # Four-syllable names do not fit at 8px advance inside the 1px outline margin; use 7px.
    advance = 8 if len(text) * 8 <= 30 else 7
    for column, char in enumerate(text):
        grid, width, height, xoffset, _ = glyph_grid(font[ord(char)])
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    px, py = (32 - len(text) * advance) // 2 + column * advance + x + xoffset, y
                    if not (1 <= px < 31 and 0 <= py < 7):
                        raise AssertionError('campaign CO name glyph exceeds native cell')
                    ink.add((px, py))
    pixels = [[0] * 32 for _ in range(8)]
    # Native palette: white ink, gray lower shadow, black outline, transparent outside.
    for x, y in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < 32 and 0 <= y + dy < 8:
                    pixels[y + dy][x + dx] = outline
    for x, y in ink:
        pixels[y + 1][x + 1] = shadow
    for x, y in ink:
        pixels[y][x] = white
    raw = bytearray(128)
    for y in range(8):
        for x in range(32):
            index = x // 8 * 32 + y * 4 + x % 8 // 2
            raw[index] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def patch_campaign_name(rom, original):
    validate_source(original)
    for pointer in POINTERS:
        if rom[pointer:pointer + 4] != original[pointer:pointer + 4]:
            raise AssertionError('campaign CO live bank pointer changed')
    if bytes(rom[ACCESSOR[0]:ACCESSOR[0] + len(ACCESSOR[1])]) != ACCESSOR[1]:
        raise AssertionError('campaign CO live accessor changed')
    for _, address, _, text, white, shadow, outline in LABELS:
        rom[address:address + 128] = render_label(text, white, shadow, outline)
    return len(LABELS)


def capture_regions(rom, original):
    validate_source(original)
    for pointer in POINTERS:
        if rom[pointer:pointer + 4] != original[pointer:pointer + 4]:
            raise AssertionError('campaign CO final bank pointer changed')
    if bytes(rom[ACCESSOR[0]:ACCESSOR[0] + len(ACCESSOR[1])]) != ACCESSOR[1]:
        raise AssertionError('campaign CO final accessor changed')
    return tuple((a, bytes(rom[a:a + size])) for a, size in
                 [(row[1], 128) for row in LABELS] + [(a, 4) for a in POINTERS]
                 + [(ACCESSOR[0], len(ACCESSOR[1]))])


def verify_regions(rom, regions):
    if len(regions) != len(LABELS) + len(POINTERS) + 1:
        raise AssertionError('campaign CO name evidence missing')
    for address, expected in regions:
        if bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError('campaign CO name overwritten')
