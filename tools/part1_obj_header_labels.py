"""English window-header OBJ labels in the raw OBJ bank 0xBE801C (1D tiles).

The same bank's SPEC / INFO / COST / COMMENT labels are already Korean
(build_korean_full.patch_part2_info_screen_obj_labels: 정보 / 정보 / 비용 /
설명, render_32x8_obj_label style: black box index 5 in rows 1..7, white
index 1 Galmuri7 text).  Project policy (docs/success.md 2026-06-07: SPEC ->
정보, WEAPON -> 무기) translates these standalone English labels; only the
English subtitles under Korean menu titles are kept on purpose
(docs/reports/SPRITE_STYLE_REVISION_2026-09-07.md).  So the remaining
siblings are translated in the same style.

Observed composition (2026-10-06 fixG, OAM -> VRAM -> ROM tile match):
  MENU            32x8 at x8 y0: 0xBE94DC..0xBE951C + blank 0xBE953C
                  (output/qa/part1_2026-10-06/m20_cand_ea4c/0042_RIGHT_0005296.ss0)
  PRODUCTION INFO 32x8 + 32x8 + 16x8 at x8/40/72: 0xBE965C..0xBE977C (same state)
  BATTLE INFO     32x8 0xBE979C..0xBE97FC + 32x8 [0xBE973C..0xBE977C, blank]
                  (output/qa/part1_2026-10-01/round32_recovery/0252_A_0059704.ss0)
                  -> INFO (0xBE973C, 3 tiles) is shared by both headers
  SHOGUN PROFILE  32x8 + 32x8 + 16x8: 0xBE991C..0xBE9A3C
                  (output/qa/part1_2026-10-01/round32_recovery/0830_A_0160602.ss0)
Not observed in any of 61,899 savestates (composition assumed contiguous like
the observed ones, unverified): WEAPON 0xBE93BC (5 tiles), STOCK 0xBE955C,
GRADE 0xBE95DC, INFO 0xBE981C (3 tiles), PLAYER RANK 0xBE9ADC (8 tiles).

Because INFO is shared, PRODUCTION -> 생산 and BATTLE -> 전투 are right
aligned with their black box running into the INFO piece (정보, left aligned).
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
BOX, INK = 5, 1
# (address, tiles, Korean, alignment, English); original span sha256 in SHA256
LABELS = (
    (0xBE93BC, 5, '무기', 'left', 'WEAPON'),
    (0xBE94DC, 4, '메뉴', 'left', 'MENU'),
    (0xBE955C, 4, '보유', 'left', 'STOCK'),
    (0xBE95DC, 4, '등급', 'left', 'GRADE'),
    (0xBE965C, 7, '생산', 'right', 'PRODUCTION'),
    (0xBE973C, 3, '정보', 'join', 'INFO (shared by PRODUCTION/BATTLE INFO)'),
    (0xBE979C, 4, '전투', 'right', 'BATTLE'),
    (0xBE981C, 3, '정보', 'left', 'INFO'),
    (0xBE991C, 10, '사령관 프로필', 'left', 'SHOGUN PROFILE'),
    (0xBE9ADC, 8, '플레이어 랭크', 'left', 'PLAYER RANK'),
)
SPACE = 3


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def _ink(text):
    font, ink, cursor = _font(), [], 0
    for char in text:
        if char == ' ':
            cursor += SPACE
            continue
        grid, w, h, xo, yo = glyph_grid(font[ord(char)])
        top = 1 + 7 - h - yo
        for gy in range(h):
            for gx in range(w):
                if grid[gy][gx]:
                    ink.append((cursor + gx + xo, top + gy))
        cursor += w + 1
    return ink, cursor - 1


def render(tiles, text, align):
    width = tiles * 8
    ink, text_width = _ink(text)
    if align == 'right':
        x0 = width - 2 - text_width
        box0, box1 = x0 - 2, width
    elif align == 'join':
        x0 = 2
        box0, box1 = 0, x0 + text_width + 2
    else:
        x0 = 2
        box0, box1 = 0, x0 + text_width + 2
    if box0 < 0 or box1 > width:
        raise AssertionError(f'header label too wide: {text}')
    pixels = [[0] * width for _ in range(8)]
    for y in range(1, 8):
        for x in range(box0, box1):
            pixels[y][x] = BOX
    for x, y in ink:
        if not (0 <= x0 + x < width and 1 <= y <= 7):
            raise AssertionError(f'header glyph clipped: {text}')
        pixels[y][x0 + x] = INK
    raw = bytearray(tiles * 32)
    for y in range(8):
        for x in range(width):
            raw[(x // 8) * 32 + y * 4 + (x % 8) // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


SHA256 = {
    0xBE93BC: '7718b6184d2924f3fee7b7270a6eba827f0b6f7358e8d4caa7e7a4deea64415b',
    0xBE94DC: '118d47b7d5c2f48ca6380f59a1e03c582dcebd7f89a8db5800f99a7833ba3156',
    0xBE955C: '7cb840c4f716b2c9d946c570260390c3999bccb10b1c6f6e004c517748b3de05',
    0xBE95DC: '1823d8522d685b7c8d59feb1cbbf00e76de7ee1c0db5aab3efad81c1081259d2',
    0xBE965C: 'cec76e9e8f9222e803d107543dda7ad5f320086b5bcd5d5601a510a3a64d47b3',
    0xBE973C: '34336b8bf24481801260dd7f7fecda5eb19119af0584f85e4da4adf65b2b934d',
    0xBE979C: '306f914a6c00b46ff226928bedadb872fd1c657879e5c313256c33d059a1d14f',
    0xBE981C: '34336b8bf24481801260dd7f7fecda5eb19119af0584f85e4da4adf65b2b934d',
    0xBE991C: 'b642dbd3a191a8472794c35ae7e39193f9fd39e571c4a4751a8cfc4630a437a5',
    0xBE9ADC: '44e2f32cf3f735d19e19b28cc5d2c308b4c8d3fe1973097309b8918bbf039d45',
}


def _source(original, address, tiles):
    raw = bytes(original[address:address + tiles * 32])
    digest = SHA256[address]
    if digest is None or hashlib.sha256(raw).hexdigest() != digest:
        raise AssertionError(f'header label source changed {address:06X}')
    return raw


def expected_regions(original):
    return tuple((address, render(tiles, text, align))
                 for address, tiles, text, align, _ in LABELS
                 if _source(original, address, tiles) is not None)


def patch(rom, original):
    regions = expected_regions(original)
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'header label {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    return len(regions)


def capture(rom, original):
    return tuple((address, bytes(rom[address:address + len(new)]))
                 for address, new in expected_regions(original))


def verify(rom, regions):
    if tuple(address for address, _ in regions) != tuple(row[0] for row in LABELS):
        raise AssertionError('header label snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'header label overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original))
